"""
Tìm phim chỉ bằng cosine similarity: embed câu query rồi so với vector corpus
đã lưu trong artifact baseline (notebook 03 — tfidf_latest / word2vec_latest / sbert_latest).
Luồng này tách biệt Artifact (cửa hàng gợi ý) và Hybrid.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

BaselineName = Literal["sbert", "tfidf", "word2vec"]

SUBDIR: dict[str, str] = {
    "sbert": "sbert_latest",
    "tfidf": "tfidf_latest",
    "word2vec": "word2vec_latest",
}

_bundle_cache: dict[str, tuple[float, Any]] = {}


def baseline_artifact_root() -> Path:
    r = os.getenv("BASELINE_ARTIFACT_ROOT", "").strip()
    if r:
        return Path(r)
    return Path("Notebook_Report/training/artifacts")


def invalidate_baseline_cache() -> None:
    _bundle_cache.clear()


def _max_mtime(dir_path: Path) -> float:
    if not dir_path.is_dir():
        return 0.0
    mt = 0.0
    for p in dir_path.iterdir():
        if p.is_file():
            try:
                mt = max(mt, p.stat().st_mtime)
            except OSError:
                pass
    return mt


def _movie_rows(artifact_dir: Path) -> list[dict]:
    raw = json.loads((artifact_dir / "movie_index.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("movie_index.json must be a list")
    return raw


@dataclass
class _SbertBundle:
    kind: Literal["sbert"]
    model_label: str
    rows: list[dict]
    embeddings: np.ndarray
    model_name: str


@dataclass
class _TfidfBundle:
    kind: Literal["tfidf"]
    model_label: str
    rows: list[dict]
    vectorizer: Any
    matrix: Any


@dataclass
class _W2vBundle:
    kind: Literal["word2vec"]
    model_label: str
    rows: list[dict]
    doc_embeddings: np.ndarray
    model: Any
    dim: int


def _load_bundle_inner(artifact_dir: Path, baseline: BaselineName) -> _SbertBundle | _TfidfBundle | _W2vBundle:
    meta = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
    rows = _movie_rows(artifact_dir)
    n = len(rows)

    if baseline == "sbert":
        emb_path = artifact_dir / "embeddings.npy"
        if not emb_path.exists():
            raise FileNotFoundError("Thiếu embeddings.npy trong artifact SBERT baseline.")
        embeddings = np.load(emb_path)
        if embeddings.shape[0] < n:
            raise ValueError(f"Số hàng embeddings ({embeddings.shape[0]}) < số phim trong index ({n})")
        model_name = str(meta.get("model_name") or "sentence-transformers/all-MiniLM-L6-v2")
        short = model_name.split("/")[-1]
        return _SbertBundle(
            kind="sbert",
            model_label=f"baseline:sbert:{short}",
            rows=rows,
            embeddings=embeddings,
            model_name=model_name,
        )

    if baseline == "tfidf":
        import joblib
        from scipy.sparse import load_npz

        v_path = artifact_dir / "vectorizer.joblib"
        m_path = artifact_dir / "tfidf_matrix.npz"
        if not v_path.exists() or not m_path.exists():
            raise FileNotFoundError(
                "Thiếu vectorizer.joblib hoặc tfidf_matrix.npz — chạy lại notebook 03 với export TF-IDF đầy đủ.",
            )
        vectorizer = joblib.load(v_path)
        matrix = load_npz(m_path)
        if matrix.shape[0] < n:
            raise ValueError(f"Số hàng TF-IDF ({matrix.shape[0]}) < số phim trong index ({n})")
        mn = str(meta.get("model_name") or "tfidf")
        return _TfidfBundle(
            kind="tfidf",
            model_label=f"baseline:tfidf:{mn}",
            rows=rows,
            vectorizer=vectorizer,
            matrix=matrix,
        )

    if baseline == "word2vec":
        from gensim.models import Word2Vec

        wpath = artifact_dir / "word2vec.model"
        emb_path = artifact_dir / "embeddings.npy"
        if not wpath.exists() or not emb_path.exists():
            raise FileNotFoundError("Thiếu word2vec.model hoặc embeddings.npy trong artifact Word2Vec.")
        w2v = Word2Vec.load(str(wpath))
        doc_embeddings = np.load(emb_path)
        if doc_embeddings.shape[0] < n:
            raise ValueError(f"Số hàng Word2Vec ({doc_embeddings.shape[0]}) < số phim trong index ({n})")
        dim = int(doc_embeddings.shape[1])
        mn = str(meta.get("model_name") or "word2vec")
        return _W2vBundle(
            kind="word2vec",
            model_label=f"baseline:word2vec:{mn}",
            rows=rows,
            doc_embeddings=doc_embeddings,
            model=w2v,
            dim=dim,
        )

    raise ValueError(f"Unknown baseline: {baseline}")


def get_bundle(baseline: BaselineName) -> _SbertBundle | _TfidfBundle | _W2vBundle:
    root = baseline_artifact_root()
    sub = root / SUBDIR[baseline]
    if not sub.is_dir():
        raise FileNotFoundError(f"Không thấy thư mục baseline: {sub}")
    mt = _max_mtime(sub)
    cached = _bundle_cache.get(baseline)
    if cached is not None and cached[0] == mt:
        return cached[1]
    bundle = _load_bundle_inner(sub, baseline)
    _bundle_cache[baseline] = (mt, bundle)
    return bundle


def _w2v_query_vec(text: str, w2v: Any, dim: int) -> np.ndarray:
    tokens = str(text).lower().split()
    vecs = [w2v.wv[t] for t in tokens if t in w2v.wv]
    if not vecs:
        return np.zeros(dim, dtype=np.float64)
    return np.mean(vecs, axis=0)


def baseline_cosine_rank(
    baseline: BaselineName, query: str, limit: int
) -> tuple[list[dict[str, Any]], str, str]:
    """
    Trả về (danh sách item giống Recommendation route, model_label, artifact_version).
    """
    q = (query or "").strip()
    if len(q) < 2:
        return [], "", ""

    bundle = get_bundle(baseline)
    artifact_version = SUBDIR[baseline]

    n = len(bundle.rows)
    if bundle.kind == "sbert":
        n = min(n, bundle.embeddings.shape[0])
    elif bundle.kind == "tfidf":
        n = min(n, bundle.matrix.shape[0])
    else:
        n = min(n, bundle.doc_embeddings.shape[0])
    rows = bundle.rows[:n]

    if bundle.kind == "sbert":
        from api.recommender import _get_sbert_model

        model = _get_sbert_model(bundle.model_name)
        if model is None:
            raise RuntimeError("sentence-transformers không khả dụng")
        q_emb = model.encode([q], normalize_embeddings=True, convert_to_numpy=True)
        sims = cosine_similarity(q_emb, bundle.embeddings[:n]).ravel()
    elif bundle.kind == "tfidf":
        qv = bundle.vectorizer.transform([q])
        sims = cosine_similarity(qv, bundle.matrix[:n]).ravel()
    else:
        qv = _w2v_query_vec(q, bundle.model, bundle.dim)
        if float(np.linalg.norm(qv)) < 1e-12:
            sims = np.zeros(n, dtype=np.float64)
        else:
            sims = cosine_similarity(qv.reshape(1, -1), bundle.doc_embeddings[:n]).ravel()

    top_idx = np.argsort(-sims)[:limit]
    out: list[dict[str, Any]] = []
    for i in top_idx:
        row = rows[int(i)]
        sc = float(sims[int(i)])
        if np.isnan(sc):
            sc = 0.0
        out.append(
            {
                "movie_id": row["id"],
                "title": row.get("title"),
                "overview": row.get("overview"),
                "poster_path": row.get("poster_path"),
                "genres": row.get("genres", []),
                "review_count": row.get("review_count", 0),
                "score": sc,
                "score_breakdown": {"cosine_similarity": round(sc, 6)},
            }
        )

    return out, bundle.model_label, artifact_version
