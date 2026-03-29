from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import (
    ARTIFACTS_DIR,
    ASPECT_NEGATIVE_PHRASES,
    ASPECT_POSITIVE_PHRASES,
    DATASETS_DIR,
    QUERY_BANK_VERSION,
    aspect_signature,
    dense_cosine,
    ensure_dir,
    load_absa_profiles,
    load_neighbor_map,
    load_profiles_dataframe,
    normalize_text,
    review_summary,
    write_json,
    write_jsonl,
)


def _genre_phrase(genres: list[str]) -> str:
    if not genres:
        return "movie"
    lowered = [g.lower() for g in genres[:2]]
    return " ".join(lowered)


def _aspect_phrases(tmdb_id: int, absa_profiles: dict[str, Any], top_n: int = 2) -> list[str]:
    profile = absa_profiles.get(str(tmdb_id))
    if not profile:
        return []
    scored: list[tuple[float, str]] = []
    for aspect, labels in (profile.get("scores") or {}).items():
        pos = float((labels or {}).get("positive", 0.0))
        neg = float((labels or {}).get("negative", 0.0))
        if pos >= neg and pos > 0.15:
            scored.append((pos, ASPECT_POSITIVE_PHRASES.get(aspect, aspect)))
        elif neg > pos and neg > 0.15:
            scored.append((neg, ASPECT_NEGATIVE_PHRASES.get(aspect, aspect)))
    scored.sort(reverse=True)
    phrases: list[str] = []
    for _, phrase in scored:
        if phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= top_n:
            break
    return phrases


def _keyword_query(row: pd.Series) -> str:
    parts: list[str] = []
    for genre in row.get("genres_list", [])[:2]:
        if genre:
            parts.append(genre.lower())
    for kw in row.get("keyword_terms", [])[:4]:
        if kw and kw not in parts:
            parts.append(kw)
    return normalize_text(" ".join(parts[:6]))


def _vibe_query(row: pd.Series, aspect_phrases: list[str]) -> str:
    genre_phrase = _genre_phrase(row.get("genres_list", []))
    if aspect_phrases:
        joined = " and ".join(aspect_phrases[:2])
        return normalize_text(f"looking for a {genre_phrase} film with {joined}")
    keywords = row.get("keyword_terms", [])
    keyword_tail = " ".join(keywords[:3]) if keywords else "rich atmosphere"
    return normalize_text(f"looking for a {genre_phrase} film with {keyword_tail}")


def _detailed_query(row: pd.Series, aspect_phrases: list[str]) -> str:
    base = normalize_text(row.get("review_summary") or row.get("overview_summary") or "")
    if not base:
        base = normalize_text(row.get("title", ""))
    tokens = base.split()
    snippet = " ".join(tokens[:28])
    genre_phrase = _genre_phrase(row.get("genres_list", []))
    if aspect_phrases:
        tail = " and ".join(aspect_phrases[:2])
        return normalize_text(f"I want a {genre_phrase} movie where {snippet} with {tail}")
    return normalize_text(f"I want a {genre_phrase} movie where {snippet}")


def _neighbor_score(movie_id: str, neighbor_rows: list[dict[str, Any]]) -> float:
    for rank, item in enumerate(neighbor_rows, start=1):
        if str(item.get("movie_id")) == movie_id:
            return 1.0 / float(rank)
    return 0.0


def _genre_jaccard(left: list[str], right: list[str]) -> float:
    lset = {g.lower() for g in left if g}
    rset = {g.lower() for g in right if g}
    if not lset or not rset:
        return 0.0
    return float(len(lset & rset)) / float(len(lset | rset))


def _mine_related_positives(
    row: pd.Series,
    df_by_id: dict[str, pd.Series],
    tfidf_neighbors: dict[str, list[dict[str, Any]]],
    sbert_neighbors: dict[str, list[dict[str, Any]]],
    absa_profiles: dict[str, Any],
) -> list[str]:
    source_id = str(row["movie_id"])
    source_tmdb = int(row["tmdb_id"])
    source_sig = aspect_signature(absa_profiles.get(str(source_tmdb)))
    candidate_ids = {
        str(item.get("movie_id"))
        for item in tfidf_neighbors.get(source_id, [])[:10] + sbert_neighbors.get(source_id, [])[:10]
        if item.get("movie_id")
    }
    scored: list[tuple[float, str]] = []
    for candidate_id in candidate_ids:
        cand = df_by_id.get(candidate_id)
        if cand is None or candidate_id == source_id:
            continue
        genre_score = _genre_jaccard(list(row.get("genres_list", [])), list(cand.get("genres_list", [])))
        tfidf_score = _neighbor_score(candidate_id, tfidf_neighbors.get(source_id, []))
        sbert_score = _neighbor_score(candidate_id, sbert_neighbors.get(source_id, []))
        cand_sig = aspect_signature(absa_profiles.get(str(int(cand["tmdb_id"]))))
        absa_score = dense_cosine(source_sig, cand_sig)
        score = (0.45 * genre_score) + (0.30 * max(tfidf_score, sbert_score)) + (0.25 * absa_score)
        if score >= 0.30:
            scored.append((score, candidate_id))
    scored.sort(reverse=True)
    out = [source_id]
    for _, candidate_id in scored[:2]:
        if candidate_id not in out:
            out.append(candidate_id)
    return out


def _mine_hard_negative(
    row: pd.Series,
    df_by_id: dict[str, pd.Series],
    genre_to_ids: dict[str, list[str]],
    positives: set[str],
    tfidf_neighbors: dict[str, list[dict[str, Any]]],
    sbert_neighbors: dict[str, list[dict[str, Any]]],
    absa_profiles: dict[str, Any],
) -> str | None:
    source_id = str(row["movie_id"])
    source_tmdb = int(row["tmdb_id"])
    source_sig = aspect_signature(absa_profiles.get(str(source_tmdb)))
    pool: list[str] = []
    for genre in row.get("genres_list", [])[:2]:
        pool.extend(genre_to_ids.get(genre.lower(), []))
    pool.extend(str(item.get("movie_id")) for item in tfidf_neighbors.get(source_id, [])[:20])
    pool.extend(str(item.get("movie_id")) for item in sbert_neighbors.get(source_id, [])[:20])

    best: tuple[float, str] | None = None
    for candidate_id in pool:
        if not candidate_id or candidate_id == source_id or candidate_id in positives:
            continue
        cand = df_by_id.get(candidate_id)
        if cand is None:
            continue
        genre_score = _genre_jaccard(list(row.get("genres_list", [])), list(cand.get("genres_list", [])))
        if genre_score <= 0.0:
            continue
        cand_sig = aspect_signature(absa_profiles.get(str(int(cand["tmdb_id"]))))
        absa_score = dense_cosine(source_sig, cand_sig)
        tfidf_score = _neighbor_score(candidate_id, tfidf_neighbors.get(source_id, []))
        sbert_score = _neighbor_score(candidate_id, sbert_neighbors.get(source_id, []))
        hardness = (0.65 * genre_score) + (0.35 * max(tfidf_score, sbert_score)) - (0.45 * absa_score)
        if best is None or hardness > best[0]:
            best = (hardness, candidate_id)
    return best[1] if best is not None else None


def _assign_splits(entries: list[dict[str, Any]], seed: int, dev_per_stratum: int, judge_per_stratum: int) -> None:
    rng = random.Random(seed)
    grouped: dict[str, list[int]] = defaultdict(list)
    for idx, item in enumerate(entries):
        grouped[str(item["stratum"])].append(idx)

    for indices in grouped.values():
        rng.shuffle(indices)
        judge_idx = set(indices[:judge_per_stratum])
        dev_idx = set(indices[judge_per_stratum : judge_per_stratum + dev_per_stratum])
        for idx in indices:
            if idx in judge_idx:
                entries[idx]["split"] = "judge"
            elif idx in dev_idx:
                entries[idx]["split"] = "dev"
            else:
                entries[idx]["split"] = "train"


def build_query_bank(
    seed: int = 42,
    dev_per_stratum: int = 75,
    judge_per_stratum: int = 40,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    output_dir = output_dir or (DATASETS_DIR / QUERY_BANK_VERSION)
    ensure_dir(output_dir)

    df = load_profiles_dataframe()
    absa_profiles = load_absa_profiles()
    tfidf_neighbors = load_neighbor_map("tfidf_latest")
    sbert_neighbors = load_neighbor_map("sbert_latest")

    df_by_id = {str(row["movie_id"]): row for _, row in df.iterrows()}
    genre_to_ids: dict[str, list[str]] = defaultdict(list)
    for _, row in df.iterrows():
        for genre in row.get("genres_list", []):
            genre_to_ids[str(genre).lower()].append(str(row["movie_id"]))

    entries: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    triplet_rows: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        aspect_phrases = _aspect_phrases(int(row["tmdb_id"]), absa_profiles, top_n=2)
        query_map = {
            "keyword": _keyword_query(row),
            "vibe": _vibe_query(row, aspect_phrases),
            "detailed": _detailed_query(row, aspect_phrases),
        }
        positives = _mine_related_positives(row, df_by_id, tfidf_neighbors, sbert_neighbors, absa_profiles)
        hard_negative = _mine_hard_negative(
            row=row,
            df_by_id=df_by_id,
            genre_to_ids=genre_to_ids,
            positives=set(positives),
            tfidf_neighbors=tfidf_neighbors,
            sbert_neighbors=sbert_neighbors,
            absa_profiles=absa_profiles,
        )

        for stratum, query in query_map.items():
            if len(query) < 8:
                continue
            query_id = f"{QUERY_BANK_VERSION}:{row['movie_id']}:{stratum}"
            entry = {
                "query_id": query_id,
                "version": QUERY_BANK_VERSION,
                "query": query[:280],
                "stratum": stratum,
                "source_movie_id": str(row["movie_id"]),
                "source_tmdb_id": int(row["tmdb_id"]),
                "source_title": normalize_text(row.get("title", "")),
                "genres": list(row.get("genres_list", [])),
                "aspect_hints": aspect_phrases,
                "search_text_source": normalize_text(row.get("search_text_source", "")),
                "source_summary": review_summary(row.get("search_text", ""), max_words=42),
                "positive_movie_ids": positives,
                "hard_negative_movie_id": hard_negative,
            }
            entries.append(entry)

    _assign_splits(entries, seed=seed, dev_per_stratum=dev_per_stratum, judge_per_stratum=judge_per_stratum)

    for entry in entries:
        source = df_by_id[entry["source_movie_id"]]
        for positive_id in entry["positive_movie_ids"]:
            positive = df_by_id.get(positive_id)
            if positive is None:
                continue
            pair_rows.append(
                {
                    "query_id": entry["query_id"],
                    "split": entry["split"],
                    "stratum": entry["stratum"],
                    "query": entry["query"],
                    "positive_movie_id": positive_id,
                    "positive_title": normalize_text(positive.get("title", "")),
                    "positive_text": normalize_text(positive.get("search_text", "")),
                    "source_movie_id": entry["source_movie_id"],
                    "same_movie": positive_id == entry["source_movie_id"],
                    "aspect_hints": list(entry.get("aspect_hints", [])),
                    "shared_genres": sorted(
                        {g.lower() for g in source.get("genres_list", [])}
                        & {g.lower() for g in positive.get("genres_list", [])}
                    ),
                }
            )
        negative_id = entry.get("hard_negative_movie_id")
        if negative_id:
            negative = df_by_id.get(str(negative_id))
            positive = df_by_id.get(entry["source_movie_id"])
            if negative is not None and positive is not None:
                triplet_rows.append(
                    {
                        "query_id": entry["query_id"],
                        "split": entry["split"],
                        "stratum": entry["stratum"],
                        "query": entry["query"],
                        "positive_movie_id": entry["source_movie_id"],
                        "positive_title": normalize_text(positive.get("title", "")),
                        "positive_text": normalize_text(positive.get("search_text", "")),
                        "negative_movie_id": str(negative_id),
                        "negative_title": normalize_text(negative.get("title", "")),
                        "negative_text": normalize_text(negative.get("search_text", "")),
                    }
                )

    query_bank_path = output_dir / "retrieval_query_bank.jsonl"
    pairs_path = output_dir / "retrieval_train_pairs.jsonl"
    triplets_path = output_dir / "retrieval_train_triplets.jsonl"
    judge_path = output_dir / "retrieval_judge_queries.jsonl"
    metadata_path = output_dir / "metadata.json"

    judge_rows = [row for row in entries if row.get("split") == "judge"]

    write_jsonl(query_bank_path, entries)
    write_jsonl(pairs_path, pair_rows)
    write_jsonl(triplets_path, triplet_rows)
    write_jsonl(judge_path, judge_rows)
    write_json(
        metadata_path,
        {
            "version": QUERY_BANK_VERSION,
            "artifact_sources": [
                str(ARTIFACTS_DIR / "tfidf_latest"),
                str(ARTIFACTS_DIR / "sbert_latest"),
            ],
            "counts": {
                "queries_total": len(entries),
                "pairs_total": len(pair_rows),
                "triplets_total": len(triplet_rows),
                "judge_queries_total": len(judge_rows),
            },
            "split_counts": {
                split: sum(1 for item in entries if item.get("split") == split)
                for split in ("train", "dev", "judge")
            },
            "stratum_counts": {
                stratum: sum(1 for item in entries if item.get("stratum") == stratum)
                for stratum in ("keyword", "vibe", "detailed")
            },
            "seed": seed,
            "dev_per_stratum": dev_per_stratum,
            "judge_per_stratum": judge_per_stratum,
        },
    )

    return {
        "query_bank": query_bank_path,
        "pairs": pairs_path,
        "triplets": triplets_path,
        "judge_queries": judge_path,
        "metadata": metadata_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build diversified English retrieval query bank")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATASETS_DIR / QUERY_BANK_VERSION,
        help="Directory for JSONL outputs.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dev-per-stratum", type=int, default=75)
    parser.add_argument("--judge-per-stratum", type=int, default=40)
    args = parser.parse_args()

    paths = build_query_bank(
        seed=args.seed,
        dev_per_stratum=args.dev_per_stratum,
        judge_per_stratum=args.judge_per_stratum,
        output_dir=args.output_dir,
    )
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
