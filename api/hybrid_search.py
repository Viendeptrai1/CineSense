"""
Multi-field movie search pipeline (3 stages: recall → rerank → ABSA).

Used by FastAPI hybrid search mode and re-exported from Notebook_Report/hybrid_search_pipeline.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from rank_bm25 import BM25Okapi
from transformers import AutoModel, AutoTokenizer

try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:  # pragma: no cover
    raise ImportError("pip install sentence-transformers") from e

ASPECTS = ["script", "acting", "visuals", "music", "pacing", "direction", "overall"]
SENTIMENTS = ["negative", "neutral", "positive"]
NUM_ABSA_LABELS = len(ASPECTS) * len(SENTIMENTS)


class AbsaClassifier(nn.Module):
    """Transformer backbone + linear 21 nhãn (multi-label ABSA)."""

    def __init__(self, model_name: str):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(model_name)
        self.head = nn.Linear(self.backbone.config.hidden_size, NUM_ABSA_LABELS)

    def forward(self, input_ids, attention_mask):
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0, :]
        return self.head(cls)


def movie_absa_vector(scores: dict[str, Any]) -> np.ndarray:
    out: list[float] = []
    for a in ASPECTS:
        asp = scores.get(a) or {}
        for s in SENTIMENTS:
            out.append(float(asp.get(s, 0.0)))
    return np.asarray(out, dtype=np.float64)


def _norm_tokens(s: str) -> list[str]:
    return [t for t in re.sub(r"[^a-zA-Z0-9\s]+", " ", str(s).lower()).split() if t]


def _tokenize_bm25(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(s).lower())


def _find_data_dir(explicit: Path | None) -> Path:
    if explicit is not None and explicit.is_dir():
        return explicit.resolve()
    cur = Path.cwd().resolve()
    if cur.name == "Notebook_Report" and (cur / "cleaned_profiles.csv").exists():
        return cur
    for p in [cur, *cur.parents]:
        cand = p / "Notebook_Report"
        if (cand / "cleaned_profiles.csv").exists():
            return cand.resolve()
    return cur


def title_bm25_fuzzy_scores(
    query: str,
    titles: list[str],
    bm25: BM25Okapi,
    fuzzy_top_m: int,
    bm25_fuzzy_alpha: float,
) -> np.ndarray:
    n = len(titles)
    q_tok = _tokenize_bm25(query)
    bm25_raw = np.asarray(bm25.get_scores(q_tok), dtype=np.float64)
    mx = float(bm25_raw.max()) if bm25_raw.size else 0.0
    bm25_norm = bm25_raw / mx if mx > 0 else bm25_raw

    m = min(fuzzy_top_m, n)
    if m <= 0:
        return bm25_norm

    top_idx = np.argpartition(-bm25_raw, m - 1)[:m]
    fused = bm25_norm.copy()
    for i in top_idx:
        qn = " ".join(_norm_tokens(query))
        tn = " ".join(_norm_tokens(titles[i]))
        fz = float(SequenceMatcher(None, qn, tn).ratio()) if qn and tn else 0.0
        fused[i] = bm25_fuzzy_alpha * bm25_norm[i] + (1.0 - bm25_fuzzy_alpha) * fz
    return fused


def genre_keyword_scores_vectorized(df: pd.DataFrame, query: str) -> np.ndarray:
    return df["genres"].apply(lambda g: _genre_keyword_score_single(query, g)).to_numpy(dtype=np.float64)


def _genre_keyword_score_single(query: str, genres_str: str) -> float:
    q_tokens = set(_norm_tokens(query))
    if not q_tokens:
        return 0.0
    genres = {g.strip().lower() for g in str(genres_str).split(",") if g and g.strip()}
    if not genres:
        return 0.0
    genre_tokens: set[str] = set()
    for g in genres:
        genre_tokens.update(_norm_tokens(g))
    hits = sum(1 for tok in q_tokens if tok in genre_tokens)
    return hits / max(1, len(q_tokens))


def minmax_norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-12:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def stage2_weights(num_query_tokens: int) -> tuple[float, float, float]:
    if num_query_tokens <= 3:
        return (1.0, 0.85, 0.35)
    return (0.25, 0.85, 0.9)


def absa_cosine_bonus_for_row_indices(
    full_df: pd.DataFrame,
    row_indices: list[int],
    absa_profiles: dict[str, Any],
    query_probs: np.ndarray,
    scale: float,
) -> np.ndarray:
    m = len(row_indices)
    bonus = np.zeros(m, dtype=np.float64)
    if not absa_profiles:
        return bonus

    q = np.asarray(query_probs, dtype=np.float64).ravel()
    if q.size != NUM_ABSA_LABELS:
        return bonus
    qn = np.linalg.norm(q)
    q = q / qn if qn > 1e-12 else q

    for j, i in enumerate(row_indices):
        tid = str(full_df.iloc[i]["tmdb_id"])
        rec = absa_profiles.get(tid)
        if not rec:
            continue
        mv = movie_absa_vector(rec.get("scores", {}))
        mn = np.linalg.norm(mv)
        mv = mv / mn if mn > 1e-12 else mv
        bonus[j] = scale * float(np.dot(q, mv))
    return bonus


@dataclass
class PipelineConfig:
    data_dir: Path | None = None
    cleaned_csv: str = "cleaned_profiles.csv"
    absa_profiles_json: str = "absa/absa_movie_profiles.json"
    absa_artifact_dir: str = "absa/artifacts/absa_distilroberta_latest"
    sbert_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_batch_size: int = 64
    sbert_show_progress: bool = False
    recall_top_k: int = 50
    bm25_fuzzy_top_m: int = 96
    bm25_fuzzy_alpha: float = 0.55
    stage3_absa_scale: float = 15.0
    absa_max_length: int = 256
    final_top_k: int = 10
    recall_channel_weights: tuple[float, float, float] = (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)


@dataclass
class MultiFieldMoviePipeline:
    """Stage1 recall → Stage2 rerank → Stage3 ABSA (model + profile JSON)."""

    config: PipelineConfig = field(default_factory=PipelineConfig)
    _df: pd.DataFrame | None = field(default=None, repr=False)
    _bm25: Any = field(default=None, repr=False)
    _sbert: SentenceTransformer | None = field(default=None, repr=False)
    _doc_embeddings: np.ndarray | None = field(default=None, repr=False)
    _absa_profiles: dict[str, Any] = field(default_factory=dict, repr=False)
    _absa_model: nn.Module | None = field(default=None, repr=False)
    _absa_tok: Any = field(default=None, repr=False)
    _absa_device: str = field(default="cpu", repr=False)

    def fit(self) -> None:
        cfg = self.config
        root = _find_data_dir(cfg.data_dir)
        csv_path = root / cfg.cleaned_csv
        if not csv_path.exists():
            raise FileNotFoundError(f"Không thấy {csv_path}")

        df = pd.read_csv(csv_path)
        for col in ["genres", "movie_profile", "review_profile"]:
            if col not in df.columns:
                df[col] = ""
        df["title"] = df["title"].fillna("").astype(str)
        df["tmdb_id"] = df["tmdb_id"].astype(str)
        df["genres"] = df["genres"].fillna("").astype(str)
        df["review_profile"] = df["review_profile"].fillna("").astype(str)
        df["movie_profile"] = df["movie_profile"].fillna("").astype(str)

        def semantic_text(row: pd.Series) -> str:
            rp = str(row.get("review_profile", "")).strip()
            if len(rp) >= 24:
                return rp[:8000]
            mp = str(row.get("movie_profile", "")).strip()
            if len(mp) >= 8:
                return mp[:8000]
            t = str(row.get("title", ""))
            g = str(row.get("genres", ""))
            return f"{t} | {g}"

        df["_semantic_text"] = df.apply(semantic_text, axis=1)

        self._df = df.reset_index(drop=True)
        titles = self._df["title"].tolist()
        tokenized = [_tokenize_bm25(t) for t in titles]
        self._bm25 = BM25Okapi(tokenized)

        prof_path = root / cfg.absa_profiles_json
        if prof_path.exists():
            self._absa_profiles = json.loads(prof_path.read_text(encoding="utf-8"))
        else:
            self._absa_profiles = {}

        self._sbert = SentenceTransformer(cfg.sbert_model)
        texts = self._df["_semantic_text"].astype(str).tolist()
        self._doc_embeddings = np.asarray(
            self._sbert.encode(
                texts,
                batch_size=cfg.semantic_batch_size,
                show_progress_bar=cfg.sbert_show_progress,
                normalize_embeddings=True,
            ),
            dtype=np.float64,
        )

        artifact_dir = root / cfg.absa_artifact_dir
        ckpt = artifact_dir / "model.pt"
        if ckpt.exists():
            ck = torch.load(ckpt, map_location="cpu")
            model_name = ck.get("model_name", "distilroberta-base")
            model = AbsaClassifier(model_name)
            model.load_state_dict(ck["state_dict"], strict=True)
            tok_dir = artifact_dir / "tokenizer"
            if tok_dir.exists():
                tokenizer = AutoTokenizer.from_pretrained(tok_dir)
            else:
                tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._absa_device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(self._absa_device)
            model.eval()
            self._absa_model = model
            self._absa_tok = tokenizer
        else:
            self._absa_model = None
            self._absa_tok = None

    def infer_absa_query_probs(self, query: str) -> np.ndarray:
        if self._absa_model is None or self._absa_tok is None:
            return np.zeros(NUM_ABSA_LABELS, dtype=np.float64)
        enc = self._absa_tok(
            str(query),
            max_length=self.config.absa_max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        input_ids = enc["input_ids"].to(self._absa_device)
        attention_mask = enc["attention_mask"].to(self._absa_device)
        with torch.no_grad():
            logits = self._absa_model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.sigmoid(logits).cpu().numpy().squeeze(0)
        return probs.astype(np.float64)

    def search(self, query: str, limit: int | None = None) -> pd.DataFrame:
        if self._df is None or self._bm25 is None or self._doc_embeddings is None or self._sbert is None:
            raise RuntimeError("Gọi fit() trước khi search().")

        cfg = self.config
        df = self._df
        n = len(df)
        q = str(query)

        title_raw = title_bm25_fuzzy_scores(
            q,
            df["title"].astype(str).tolist(),
            self._bm25,
            cfg.bm25_fuzzy_top_m,
            cfg.bm25_fuzzy_alpha,
        )
        genre_raw = genre_keyword_scores_vectorized(df, q)

        q_emb = self._sbert.encode([q], normalize_embeddings=True, show_progress_bar=False)
        qv = np.asarray(q_emb, dtype=np.float64).reshape(1, -1)
        sbert_raw = (self._doc_embeddings @ qv.T).ravel()

        t_n = minmax_norm(title_raw)
        g_n = minmax_norm(genre_raw)
        s_n = minmax_norm(sbert_raw)

        w1r, w2r, w3r = cfg.recall_channel_weights
        recall_score = w1r * t_n + w2r * g_n + w3r * s_n

        k = min(cfg.recall_top_k, n)
        cand_idx = np.argpartition(-recall_score, k - 1)[:k]
        cand_idx = cand_idx[np.argsort(-recall_score[cand_idx])]

        ntok = len(_norm_tokens(q))
        w1, w2, w3 = stage2_weights(ntok)

        rows: list[dict[str, Any]] = []
        for i in cand_idx:
            ti, gi, si = float(t_n[i]), float(g_n[i]), float(s_n[i])
            stage2 = w1 * ti + w2 * gi + w3 * si
            rows.append(
                {
                    "idx": int(i),
                    "tmdb_id": df.iloc[i]["tmdb_id"],
                    "title": df.iloc[i]["title"],
                    "genres": df.iloc[i]["genres"],
                    "score_title": ti,
                    "score_genre": gi,
                    "score_sbert": si,
                    "score_stage2": stage2,
                }
            )

        sub = pd.DataFrame(rows)
        idx_list = [int(x) for x in sub["idx"].tolist()]

        q_absa = self.infer_absa_query_probs(q)
        absa_cos = absa_cosine_bonus_for_row_indices(
            df,
            idx_list,
            self._absa_profiles,
            q_absa,
            cfg.stage3_absa_scale,
        )
        sub["absa_query_profile_cos"] = absa_cos
        sub["score_final"] = sub["score_stage2"] + sub["absa_query_profile_cos"]

        sub = sub.drop(columns=["idx"])
        top_n = int(limit) if limit is not None else cfg.final_top_k
        top_n = max(1, min(top_n, n))
        return (
            sub.sort_values("score_final", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )


def run_demo() -> None:
    cfg = PipelineConfig(sbert_show_progress=True)
    pipe = MultiFieldMoviePipeline(cfg)
    pipe.fit()
    queries = [
        "Incpetion",
        "action horror",
        "mind-bending dream and time loop story",
        "great visuals but pacing was too slow",
    ]
    for q in queries:
        print("\n=== Query:", q, "===")
        print(pipe.search(q).to_string())


if __name__ == "__main__":
    run_demo()
