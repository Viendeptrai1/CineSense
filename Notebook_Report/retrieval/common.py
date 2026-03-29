from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = ROOT / "Notebook_Report"
TRAINING_DIR = NOTEBOOK_DIR / "training"
ARTIFACTS_DIR = TRAINING_DIR / "artifacts"
DATASETS_DIR = TRAINING_DIR / "datasets"
LLM_JUDGE_RUNS_DIR = NOTEBOOK_DIR / "llm_judge_runs"

QUERY_BANK_VERSION = "retrieval_query_bank_v1"
DEFAULT_BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_FINE_TUNED_ARTIFACT = ARTIFACTS_DIR / "sbert_en_finetuned_latest"

TOKEN_RE = re.compile(r"[a-z0-9]+")

GENRE_ALIASES = {
    "Science Fiction": "science fiction",
    "TV Movie": "tv movie",
}

ASPECT_POSITIVE_PHRASES = {
    "script": "a smart script",
    "acting": "strong acting",
    "visuals": "striking visuals",
    "music": "an emotional soundtrack",
    "pacing": "steady pacing",
    "direction": "confident direction",
    "overall": "a satisfying overall experience",
}

ASPECT_NEGATIVE_PHRASES = {
    "script": "messy writing",
    "acting": "uneven acting",
    "visuals": "plain visuals",
    "music": "forgettable music",
    "pacing": "slow pacing",
    "direction": "shaky direction",
    "overall": "mixed reception",
}

ASPECTS = ["script", "acting", "visuals", "music", "pacing", "direction", "overall"]
SENTIMENTS = ["negative", "neutral", "positive"]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def stable_movie_id(tmdb_id: int | str) -> str:
    return str(uuid5(NAMESPACE_URL, f"cinesense:core_movie:{int(tmdb_id)}"))


def normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def truncate_text(text: str, max_chars: int = 8000) -> str:
    text = normalize_text(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def split_genres(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_text(v) for v in value if normalize_text(v)]
    raw = normalize_text(value)
    if not raw:
        return []
    return [part for part in [normalize_text(x) for x in raw.split(",")] if part]


def retrieval_text_from_row(row: dict[str, Any] | pd.Series) -> str:
    rp = normalize_text(row.get("review_profile", ""))
    if len(rp) >= 24:
        return truncate_text(rp)
    mp = normalize_text(row.get("movie_profile", ""))
    if len(mp) >= 8:
        return truncate_text(mp)
    title = normalize_text(row.get("title", ""))
    genres = row.get("genres_list")
    if not genres:
        genres = split_genres(row.get("genres", ""))
    genre_text = ", ".join(genres)
    return truncate_text(f"{title} | {genre_text}")


def retrieval_text_source(row: dict[str, Any] | pd.Series) -> str:
    rp = normalize_text(row.get("review_profile", ""))
    if len(rp) >= 24:
        return "review_profile"
    mp = normalize_text(row.get("movie_profile", ""))
    if len(mp) >= 8:
        return "movie_profile"
    return "title_genres"


def tokenize(text: Any) -> list[str]:
    tokens = TOKEN_RE.findall(str(text or "").lower())
    return [tok for tok in tokens if tok not in ENGLISH_STOP_WORDS and len(tok) > 1]


def ordered_keywords(text: Any, top_n: int = 4) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tok in tokenize(text):
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= top_n:
            break
    return out


def review_summary(text: Any, max_words: int = 36) -> str:
    tokens = str(text or "").split()
    if not tokens:
        return ""
    if len(tokens) <= max_words:
        return " ".join(tokens)
    return " ".join(tokens[:max_words]).strip() + " ..."


def aspect_signature(profile: dict[str, Any] | None) -> np.ndarray:
    vec: list[float] = []
    if not profile:
        return np.zeros(len(ASPECTS) * len(SENTIMENTS), dtype=np.float32)
    scores = profile.get("scores", {})
    for aspect in ASPECTS:
        aspect_scores = scores.get(aspect, {})
        for sentiment in SENTIMENTS:
            vec.append(float(aspect_scores.get(sentiment, 0.0)))
    return np.asarray(vec, dtype=np.float32)


def dense_cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def load_absa_profiles() -> dict[str, Any]:
    path = NOTEBOOK_DIR / "absa" / "absa_movie_profiles.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_neighbor_map(artifact_name: str) -> dict[str, list[dict[str, Any]]]:
    path = ARTIFACTS_DIR / artifact_name / "similar_by_movie.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return raw


def relative_to_root(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def load_profiles_dataframe() -> pd.DataFrame:
    csv_path = NOTEBOOK_DIR / "cleaned_profiles.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing {csv_path}. Run Notebook_Report/02_Data_Preprocessing_EDA.ipynb first."
        )
    df = pd.read_csv(csv_path).fillna("")
    required_cols = {"tmdb_id", "title", "overview", "genres", "movie_profile", "review_profile"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"cleaned_profiles.csv missing columns: {sorted(missing)}")

    df = df.copy()
    df["tmdb_id"] = df["tmdb_id"].astype(int)
    df["movie_id"] = df["tmdb_id"].apply(stable_movie_id)
    df["genres_list"] = df["genres"].apply(split_genres)
    df["search_text"] = df.apply(retrieval_text_from_row, axis=1)
    df["search_text_source"] = df.apply(retrieval_text_source, axis=1)
    df["review_summary"] = df["review_profile"].apply(review_summary)
    df["overview_summary"] = df["overview"].apply(review_summary)
    df["keyword_terms"] = df.apply(
        lambda row: ordered_keywords(f"{row.get('overview', '')} {row.get('review_summary', '')}", top_n=5),
        axis=1,
    )
    return df


def movie_index_row(row: pd.Series) -> dict[str, Any]:
    release_year = None
    release_raw = normalize_text(row.get("release_date", ""))
    if len(release_raw) >= 4 and release_raw[:4].isdigit():
        release_year = int(release_raw[:4])
    popularity_raw = row.get("popularity")
    try:
        popularity = float(popularity_raw) if popularity_raw not in ("", None) else None
    except (TypeError, ValueError):
        popularity = None
    return {
        "id": row["movie_id"],
        "tmdb_id": int(row["tmdb_id"]),
        "title": normalize_text(row.get("title", "")),
        "overview": normalize_text(row.get("overview", "")),
        "poster_path": normalize_text(row.get("poster_path", "")) or None,
        "genres": list(row.get("genres_list", [])),
        "release_year": release_year,
        "popularity": popularity,
        "review_count": int(math.ceil(float(row.get("review_token_count") or 0) / 80.0))
        if str(row.get("review_token_count", "")).strip()
        else 0,
        "search_text": normalize_text(row.get("search_text", "")),
        "search_text_source": normalize_text(row.get("search_text_source", "")),
    }
