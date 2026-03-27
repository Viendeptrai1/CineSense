from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _resolve_artifact_dir() -> Path:
    configured = os.getenv("RECOMMENDER_ARTIFACT_DIR")
    if configured:
        return Path(configured)
    # Use notebook-exported artifacts as the single default source.
    candidates = [
        Path("Notebook_Report/training/artifacts/sbert_en_latest"),
        Path("Notebook_Report/training/artifacts/sbert_latest"),
        Path("Notebook_Report/training/artifacts/tfidf_latest"),
        Path("Notebook_Report/training/artifacts/word2vec_latest"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@dataclass
class RecommendationStore:
    artifact_dir: Path
    metadata: dict[str, Any]
    movie_index: dict[str, dict[str, Any]]
    similar_by_movie: dict[str, list[dict[str, Any]]]
    search_ids: list[str]
    search_docs: list[str]
    tfidf_vectorizer: Any | None
    tfidf_matrix: Any | None
    absa_movie_profiles: dict[str, Any]

    @classmethod
    def load(cls) -> "RecommendationStore":
        artifact_dir = _resolve_artifact_dir()
        metadata = {}
        movie_index: dict[str, dict[str, Any]] = {}
        similar_by_movie: dict[str, list[dict[str, Any]]] = {}
        search_ids: list[str] = []
        search_docs: list[str] = []
        tfidf_vectorizer = None
        tfidf_matrix = None
        absa_movie_profiles: dict[str, Any] = {}

        metadata_path = artifact_dir / "metadata.json"
        index_path = artifact_dir / "movie_index.json"
        similar_path = artifact_dir / "similar_by_movie.json"

        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if index_path.exists():
            rows = json.loads(index_path.read_text(encoding="utf-8"))
            movie_index = {row["id"]: row for row in rows}
            # Build search docs for query-time semantic scoring.
            for row in rows:
                rid = row["id"]
                search_ids.append(rid)
                title = str(row.get("title", "") or "")
                overview = str(row.get("overview", "") or "")
                genres = " ".join(row.get("genres", []) or [])
                search_docs.append(f"title: {title} | genres: {genres} | overview: {overview}".strip())

        if similar_path.exists():
            similar_by_movie = json.loads(similar_path.read_text(encoding="utf-8"))

        if search_docs:
            try:
                tfidf_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, max_df=0.9)
                tfidf_matrix = tfidf_vectorizer.fit_transform(search_docs)
            except Exception:
                tfidf_vectorizer = None
                tfidf_matrix = None

        # Optional ABSA movie profile exported from Notebook_Report/04.
        absa_candidates = [
            Path("Notebook_Report/absa/absa_movie_profiles.json"),
            Path("absa/absa_movie_profiles.json"),
        ]
        for ap in absa_candidates:
            if ap.exists():
                try:
                    absa_movie_profiles = json.loads(ap.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass

        return cls(
            artifact_dir=artifact_dir,
            metadata=metadata,
            movie_index=movie_index,
            similar_by_movie=similar_by_movie,
            search_ids=search_ids,
            search_docs=search_docs,
            tfidf_vectorizer=tfidf_vectorizer,
            tfidf_matrix=tfidf_matrix,
            absa_movie_profiles=absa_movie_profiles,
        )

    def is_ready(self) -> bool:
        return bool(self.movie_index and self.similar_by_movie)

    def similar_movies(self, movie_id: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.similar_by_movie.get(movie_id, [])
        output = []
        for row in rows[:limit]:
            candidate = self.movie_index.get(row["movie_id"])
            if not candidate:
                continue
            output.append(
                {
                    "movie_id": candidate["id"],
                    "title": candidate.get("title"),
                    "overview": candidate.get("overview"),
                    "poster_path": candidate.get("poster_path"),
                    "genres": candidate.get("genres", []),
                    "review_count": candidate.get("review_count", 0),
                    "score": float(row.get("score", 0.0)),
                }
            )
        return output

    def trending_movies(self, limit: int = 10) -> list[dict[str, Any]]:
        ranked = sorted(
            self.movie_index.values(),
            key=lambda m: (m.get("review_count", 0), m.get("release_year") or 0),
            reverse=True,
        )
        return [
            {
                "movie_id": row["id"],
                "title": row.get("title"),
                "overview": row.get("overview"),
                "poster_path": row.get("poster_path"),
                "genres": row.get("genres", []),
                "review_count": row.get("review_count", 0),
                "score": None,
            }
            for row in ranked[:limit]
        ]

    def search_movies(
        self,
        query: str,
        limit: int = 10,
        query_type: str = "auto",
        filters: Optional[dict[str, Any]] = None,
        absa_refine: bool = True,
        explain: bool = False,
        weights_override: Optional[dict[str, float]] = None,
    ) -> list[dict[str, Any]]:
        prepared = self._prepare_search(
            query=query,
            query_type=query_type,
            filters=filters,
            absa_refine=absa_refine,
            weights_override=weights_override,
        )
        if prepared is None:
            return []
        q, norm_tokens, w_title, w_genre, w_sem, intents, active_filters, semantic_map = prepared

        def _title_score(query_text: str, title: str) -> float:
            qn = " ".join(norm_tokens(query_text))
            tn = " ".join(norm_tokens(title))
            if not qn or not tn:
                return 0.0
            ratio = SequenceMatcher(None, qn, tn).ratio()
            qset = set(qn.split())
            tset = set(tn.split())
            overlap = (len(qset & tset) / max(1, len(qset))) if qset else 0.0
            return 0.6 * ratio + 0.4 * overlap

        def _genre_score(query_text: str, genres: list[str]) -> float:
            qset = set(norm_tokens(query_text))
            if not qset:
                return 0.0
            gset: set[str] = set()
            for g in genres or []:
                gset.update(norm_tokens(g))
            if not gset:
                return 0.0
            hits = sum(1 for tok in qset if tok in gset)
            return hits / max(1, len(qset))
        filter_genres = {str(g).lower() for g in active_filters.get("genres", []) if str(g).strip()}
        min_year = active_filters.get("min_year")
        max_year = active_filters.get("max_year")
        min_rating = active_filters.get("min_rating")

        scored = []
        for row in self.movie_index.values():
            title = str(row.get("title", "") or "")
            genres = row.get("genres", []) or []
            mid = row["id"]
            row_year = row.get("release_year")
            row_rating = row.get("average_rating")

            if min_year is not None and (row_year is None or row_year < int(min_year)):
                continue
            if max_year is not None and (row_year is None or row_year > int(max_year)):
                continue
            if min_rating is not None and (row_rating is None or float(row_rating) < float(min_rating)):
                continue
            if filter_genres:
                row_genres_norm = {str(g).lower() for g in genres}
                if not (row_genres_norm & filter_genres):
                    continue

            t_score = _title_score(q, title)
            g_score = _genre_score(q, genres)
            s_score = float(semantic_map.get(mid, 0.0))

            # Stage-2 weighted score on 0..100 scale
            base_score = 100.0 * ((w_title * t_score) + (w_genre * g_score) + (w_sem * s_score))

            # Stage-3 ABSA bonus (if movie profile exists)
            bonus = 0.0
            if absa_refine and intents and self.absa_movie_profiles:
                mp = self.absa_movie_profiles.get(str(row.get("tmdb_id", ""))) or self.absa_movie_profiles.get(mid)
                if mp:
                    scores = mp.get("scores", {})
                    for aspect, sent in intents:
                        bonus += 20.0 * float(scores.get(aspect, {}).get(sent, 0.0))

            final_score = base_score + bonus
            if final_score > 0:
                scored.append((final_score, row, t_score, g_score, s_score, bonus))

        scored.sort(key=lambda item: (item[0], item[1].get("review_count", 0)), reverse=True)
        return [
            {
                "movie_id": row["id"],
                "title": row.get("title"),
                "overview": row.get("overview"),
                "poster_path": row.get("poster_path"),
                "genres": row.get("genres", []),
                "review_count": row.get("review_count", 0),
                "score": float(score),
                "score_breakdown": (
                    {
                        "title": float(round(t_score, 6)),
                        "genre": float(round(g_score, 6)),
                        "semantic": float(round(s_score, 6)),
                        "absa_bonus": float(round(bonus, 6)),
                        "final": float(round(score, 6)),
                    }
                    if explain
                    else None
                ),
            }
            for score, row, t_score, g_score, s_score, bonus in scored[:limit]
        ]

    def search_movies_with_debug(
        self,
        query: str,
        limit: int = 10,
        query_type: str = "auto",
        filters: Optional[dict[str, Any]] = None,
        absa_refine: bool = True,
        explain: bool = False,
        weights_override: Optional[dict[str, float]] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        prepared = self._prepare_search(
            query=query,
            query_type=query_type,
            filters=filters,
            absa_refine=absa_refine,
            weights_override=weights_override,
        )
        if prepared is None:
            return ([], None)
        q, norm_tokens, w_title, w_genre, w_sem, intents, active_filters, semantic_map = prepared
        rows = self.search_movies(
            query=query,
            limit=limit,
            query_type=query_type,
            filters=filters,
            absa_refine=absa_refine,
            explain=explain,
            weights_override=weights_override,
        )
        debug = {
            "query_raw": query,
            "query_normalized": q,
            "tokens": norm_tokens(query),
            "query_type_requested": query_type,
            "weights": {"title": float(w_title), "genre": float(w_genre), "semantic": float(w_sem)},
            "filters": active_filters,
            "absa_refine": bool(absa_refine),
            "absa_intents": [{"aspect": a, "sentiment": s} for a, s in intents],
            "semantic_ready": bool(self.tfidf_vectorizer is not None and self.tfidf_matrix is not None and semantic_map),
            "absa_profile_ready": bool(self.absa_movie_profiles),
        }
        return (rows, debug)

    def _prepare_search(
        self,
        query: str,
        query_type: str,
        filters: Optional[dict[str, Any]],
        absa_refine: bool,
        weights_override: Optional[dict[str, float]],
    ) -> tuple[
        str,
        Any,
        float,
        float,
        float,
        list[tuple[str, str]],
        dict[str, Any],
        dict[str, float],
    ] | None:
        q = (query or "").strip().lower()
        query_terms = {token for token in q.split() if token}
        if not q or not query_terms:
            return None

        def _norm_tokens(s: str) -> list[str]:
            return [t for t in re.sub(r"[^a-zA-Z0-9\s]+", " ", str(s).lower()).split() if t]

        def _weights(query_text: str) -> tuple[float, float, float]:
            n = len(_norm_tokens(query_text))
            if query_type == "title":
                return (1.0, 0.7, 0.2)
            if query_type == "genre":
                return (0.4, 1.0, 0.3)
            if query_type == "context":
                return (0.2, 0.7, 1.0)
            if n <= 3:
                return (1.0, 0.8, 0.3)
            if n <= 6:
                return (0.7, 0.8, 0.6)
            return (0.2, 0.8, 1.0)

        def _infer_absa_intents(query_text: str) -> list[tuple[str, str]]:
            qt = query_text.lower()
            mapping = {
                "overall": {"positive": ["hay", "xuất sắc", "good", "great", "amazing", "excellent"]},
                "script": {"positive": ["kịch bản hay", "plot twist", "script", "story", "mind-bending"]},
                "visuals": {"positive": ["kỹ xảo đẹp", "cgi", "visual", "visuals", "cinematography"]},
                "acting": {"positive": ["diễn xuất", "acting", "actor", "performance"]},
                "pacing": {"positive": ["pace", "nhịp độ", "cuốn", "fast paced"]},
                "music": {"positive": ["nhạc", "soundtrack", "music"]},
                "direction": {"positive": ["đạo diễn", "director", "direction"]},
            }
            intents: list[tuple[str, str]] = []
            for aspect, sent_map in mapping.items():
                for sent, kws in sent_map.items():
                    if any(kw in qt for kw in kws):
                        intents.append((aspect, sent))
            return intents

        w_title, w_genre, w_sem = _weights(q)
        if weights_override:
            w_title = float(weights_override.get("title", w_title))
            w_genre = float(weights_override.get("genre", w_genre))
            w_sem = float(weights_override.get("semantic", w_sem))
        intents = _infer_absa_intents(q) if absa_refine else []
        active_filters = filters or {}

        semantic_map: dict[str, float] = {}
        if self.tfidf_vectorizer is not None and self.tfidf_matrix is not None and self.search_ids:
            try:
                qv = self.tfidf_vectorizer.transform([q])
                sims = cosine_similarity(qv, self.tfidf_matrix).ravel()
                mx = float(np.max(sims)) if sims.size else 0.0
                norm = sims / mx if mx > 0 else sims
                semantic_map = {mid: float(norm[i]) for i, mid in enumerate(self.search_ids)}
            except Exception:
                semantic_map = {}

        return (q, _norm_tokens, w_title, w_genre, w_sem, intents, active_filters, semantic_map)


_store: RecommendationStore | None = None


def get_recommendation_store() -> RecommendationStore:
    global _store
    if _store is None:
        _store = RecommendationStore.load()
    return _store


def reload_recommendation_store() -> RecommendationStore:
    global _store
    _store = RecommendationStore.load()
    return _store
