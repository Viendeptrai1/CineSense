#!/usr/bin/env python3
"""
Populate SQLite core_* tables from Notebook_Report CSVs + movie_index.json.

UUIDs for core_movies match `movie_index.json` so recommendation artifacts stay aligned.
Review primary keys are stable: uuid5 over external review_id.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5
from typing import Any

from sqlalchemy import delete

# Repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl_pipeline.database import (  # noqa: E402
    CoreGenre,
    CoreMovie,
    CoreReview,
    core_movie_genres,
    get_session,
    init_database,
)


def _default_movie_index_path() -> Path:
    candidates = [
        ROOT / "Notebook_Report/training/artifacts/sbert_en_finetuned_latest/movie_index.json",
        ROOT / "Notebook_Report/training/artifacts/tfidf_latest/movie_index.json",
        ROOT / "Notebook_Report/training/artifacts/word2vec_latest/movie_index.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def load_movie_index(path: Path) -> dict[int, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, dict[str, Any]] = {}
    for row in data:
        tid = int(row["tmdb_id"])
        out[tid] = row
    return out


def parse_genres_cell(s: str | None) -> list[str]:
    if not s or not str(s).strip():
        return []
    return [g.strip() for g in str(s).split(",") if g.strip()]


def parse_release_date(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    raw = str(s).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def parse_datetime_cell(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    raw = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def avatar_url_from_path(p: str | None) -> str | None:
    if not p or not str(p).strip():
        return None
    p = str(p).strip()
    if p.startswith("http"):
        return p
    return f"https://image.tmdb.org/t/p/original{p}"


def _float_cell(v: Any) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _int_cell(v: Any) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def clear_core(session: Any) -> None:
    session.execute(delete(CoreReview))
    session.execute(delete(core_movie_genres))
    session.execute(delete(CoreMovie))
    session.execute(delete(CoreGenre))
    session.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed SQLite from CSV + movie_index.json")
    parser.add_argument(
        "--movie-index",
        type=Path,
        default=_default_movie_index_path(),
        help="Path to movie_index.json (artifact)",
    )
    parser.add_argument(
        "--movies-csv",
        type=Path,
        default=ROOT / "Notebook_Report/cinesense_movies.csv",
    )
    parser.add_argument(
        "--reviews-csv",
        type=Path,
        default=ROOT / "Notebook_Report/cinesense_reviews.csv",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Skip deleting existing core_* rows first (may duplicate genre links if re-run)",
    )
    args = parser.parse_args()

    if not args.movie_index.exists():
        print(f"Missing movie_index: {args.movie_index}", file=sys.stderr)
        return 1
    if not args.movies_csv.exists():
        print(f"Missing movies CSV: {args.movies_csv}", file=sys.stderr)
        return 1
    if not args.reviews_csv.exists():
        print(f"Missing reviews CSV: {args.reviews_csv}", file=sys.stderr)
        return 1

    init_database()
    index_by_tmdb = load_movie_index(args.movie_index)

    # Collect genre names
    all_genres: set[str] = set()
    with args.movies_csv.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_genres.update(parse_genres_cell(row.get("genres")))
    for row in index_by_tmdb.values():
        for g in row.get("genres") or []:
            if isinstance(g, str) and g.strip():
                all_genres.add(g.strip())

    sorted_genres = sorted(all_genres)
    name_to_id = {name: i + 1 for i, name in enumerate(sorted_genres)}

    session = get_session()
    try:
        if not args.no_clear:
            clear_core(session)

        for name, gid in name_to_id.items():
            session.merge(CoreGenre(id=gid, name=name))
        session.commit()

        inserted_movies = 0
        with args.movies_csv.open(newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tmdb_id = int(row["tmdb_id"])
                meta = index_by_tmdb.get(tmdb_id)
                if not meta:
                    continue
                movie_uuid = UUID(str(meta["id"]))
                title = (row.get("title") or meta.get("title") or "").strip() or "Untitled"
                overview = (row.get("overview") or meta.get("overview") or "") or None
                poster = (row.get("poster_path") or meta.get("poster_path") or "") or None
                if poster == "":
                    poster = None
                rd = parse_release_date(row.get("release_date"))
                if rd is None and meta.get("release_year"):
                    try:
                        y = int(meta["release_year"])
                        rd = date(y, 1, 1)
                    except (TypeError, ValueError):
                        rd = None

                def _float(v: Any) -> float | None:
                    if v is None or str(v).strip() == "":
                        return None
                    try:
                        return float(v)
                    except ValueError:
                        return None

                def _int(v: Any) -> int | None:
                    if v is None or str(v).strip() == "":
                        return None
                    try:
                        return int(float(v))
                    except ValueError:
                        return None

                pop = _float(row.get("popularity"))
                va = _float(row.get("vote_average"))
                vc = _int(row.get("vote_count"))

                cm = CoreMovie(
                    id=movie_uuid,
                    tmdb_id=tmdb_id,
                    title=title,
                    original_title=None,
                    overview=overview,
                    release_date=rd,
                    poster_path=poster,
                    backdrop_path=None,
                    popularity=pop,
                    vote_average=va,
                    vote_count=vc,
                    original_language="en",
                )
                session.merge(cm)
                session.flush()

                genres = parse_genres_cell(row.get("genres"))
                if not genres and meta.get("genres"):
                    genres = [str(g).strip() for g in (meta.get("genres") or []) if str(g).strip()]
                for gname in genres:
                    gid = name_to_id.get(gname)
                    if gid is None:
                        continue
                    session.execute(
                        core_movie_genres.insert().values(movie_id=movie_uuid, genre_id=gid)
                    )
                inserted_movies += 1

        session.commit()
        print(f"Upserted core_movies: {inserted_movies}")

        inserted_reviews = 0
        with args.reviews_csv.open(newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = (row.get("review_id") or "").strip()
                if not ext_id:
                    continue
                tmdb_id = int(row["tmdb_id"])
                meta = index_by_tmdb.get(tmdb_id)
                if not meta:
                    continue
                movie_uuid = UUID(str(meta["id"]))
                rid = uuid5(NAMESPACE_URL, f"cinesense:review:{ext_id}")
                content = (row.get("content") or "").strip()
                if not content:
                    continue
                rating = _float_cell(row.get("rating"))
                src = (row.get("source") or "tmdb").strip() or "tmdb"
                cr = CoreReview(
                    id=rid,
                    movie_id=movie_uuid,
                    external_review_id=ext_id,
                    source=src,
                    language="en",
                    author_username=(row.get("author") or None) or None,
                    author_name=(row.get("author_name") or None) or None,
                    author_avatar_url=avatar_url_from_path(row.get("avatar_path")),
                    content=content,
                    rating=rating,
                    source_created_at=parse_datetime_cell(row.get("created_at")),
                    source_url=(row.get("url") or None) or None,
                )
                session.merge(cr)
                inserted_reviews += 1

        session.commit()
        print(f"Upserted core_reviews: {inserted_reviews}")
    finally:
        session.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
