from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from api.recommender import RecommendationStore

from .common import (
    ARTIFACTS_DIR,
    LLM_JUDGE_RUNS_DIR,
    QUERY_BANK_VERSION,
    DATASETS_DIR,
    ensure_dir,
    normalize_text,
    review_summary,
    write_json,
    write_jsonl,
)

PROMPT_PATH = Path(__file__).with_name("judge_prompt_v1.md")
DEFAULT_MODELS = ["tfidf_latest", "sbert_latest", "sbert_en_finetuned_latest"]
JSON_RE = re.compile(r"\{.*\}", flags=re.DOTALL)
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _resolve_artifact(spec: str) -> Path:
    p = Path(spec)
    if p.is_dir():
        return p
    return ARTIFACTS_DIR / spec


def _balanced_sample(rows: list[dict[str, Any]], max_queries: int, seed: int) -> list[dict[str, Any]]:
    if max_queries <= 0 or len(rows) <= max_queries:
        return rows
    rng = random.Random(seed)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("stratum", "unknown"))].append(row)
    out: list[dict[str, Any]] = []
    per_group = max(1, max_queries // max(1, len(grouped)))
    for group_rows in grouped.values():
        pool = list(group_rows)
        rng.shuffle(pool)
        out.extend(pool[:per_group])
    if len(out) < max_queries:
        leftovers = [row for row in rows if row not in out]
        rng.shuffle(leftovers)
        out.extend(leftovers[: max_queries - len(out)])
    return out[:max_queries]


def _render_prompt(
    rubric: str,
    query_row: dict[str, Any],
    trace_row: dict[str, Any],
) -> str:
    return (
        f"{rubric.strip()}\n\n"
        f"## Candidate To Judge\n"
        f"- query: {query_row['query']}\n"
        f"- query_stratum: {query_row['stratum']}\n"
        f"- candidate_title: {trace_row['title']}\n"
        f"- candidate_genres: {', '.join(trace_row.get('genres', []))}\n"
        f"- candidate_overview: {trace_row.get('overview', '')}\n"
        f"- candidate_review_summary: {trace_row.get('review_summary', '')}\n"
    )


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = JSON_RE.search(text)
        if not match:
            raise
        return json.loads(match.group(0))


def _retry_delay(
    attempt: int,
    retry_after: str | None,
    retry_base_s: float,
    retry_max_s: float,
) -> float:
    if retry_after:
        try:
            return min(retry_max_s, max(0.0, float(retry_after.strip())))
        except ValueError:
            pass
    return min(retry_max_s, retry_base_s * (2 ** max(0, attempt - 1)))


def _response_error_message(response: httpx.Response) -> str:
    message = ""
    try:
        payload = response.json()
        error = payload.get("error", {})
        if isinstance(error, dict):
            message = normalize_text(error.get("message", ""))
    except Exception:
        message = ""
    base = f"Gemini request failed with status {response.status_code}"
    return f"{base}: {message}" if message else base


def _call_gemini(
    prompt: str,
    model_name: str,
    api_key: str,
    timeout_s: int,
    max_retries: int,
    retry_base_s: float,
    retry_max_s: float,
) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    headers = {"x-goog-api-key": api_key}

    last_error = "Gemini request failed."
    for attempt in range(1, max_retries + 2):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout_s)
            if response.status_code in RETRYABLE_STATUS_CODES:
                last_error = _response_error_message(response)
                if attempt > max_retries:
                    break
                delay_s = _retry_delay(
                    attempt=attempt,
                    retry_after=response.headers.get("Retry-After"),
                    retry_base_s=retry_base_s,
                    retry_max_s=retry_max_s,
                )
                print(
                    f"[warn] {last_error}; retrying in {delay_s:.1f}s "
                    f"(attempt {attempt}/{max_retries})"
                )
                time.sleep(delay_s)
                continue

            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            response = exc.response
            if response is not None:
                raise RuntimeError(_response_error_message(response)) from exc
            raise RuntimeError("Gemini request failed before a response was returned.") from exc
        except httpx.HTTPError as exc:
            last_error = f"Gemini transport error: {exc.__class__.__name__}"
            if attempt > max_retries:
                break
            delay_s = _retry_delay(
                attempt=attempt,
                retry_after=None,
                retry_base_s=retry_base_s,
                retry_max_s=retry_max_s,
            )
            print(
                f"[warn] {last_error}; retrying in {delay_s:.1f}s "
                f"(attempt {attempt}/{max_retries})"
            )
            time.sleep(delay_s)
            continue
        except ValueError as exc:
            raise RuntimeError(f"Gemini returned invalid JSON: {exc}") from exc

        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if not text.strip():
            raise RuntimeError("Gemini returned an empty response body.")
        try:
            parsed = _extract_json(text)
        except ValueError as exc:
            raise RuntimeError(f"Gemini returned malformed JSON content: {exc}") from exc
        parsed.setdefault("binary_relevant", False)
        parsed.setdefault("relevance_score", 0)
        parsed.setdefault("constraint_match_score", 0)
        parsed.setdefault("review_signal_score", 0)
        parsed.setdefault("reasoning", "")
        parsed.setdefault("matched_clues", [])
        return parsed

    raise RuntimeError(last_error)


def _build_traces(
    queries: list[dict[str, Any]],
    artifact_dir: Path,
    top_k: int,
    absa_refine: bool,
    rerank: bool,
    semantic_backend: str,
) -> list[dict[str, Any]]:
    store = RecommendationStore.load_from_artifact(artifact_dir)
    model_label = artifact_dir.name
    traces: list[dict[str, Any]] = []
    for query_row in queries:
        results, debug = store.search_movies_with_debug(
            query=query_row["query"],
            limit=top_k,
            query_type="auto",
            filters=None,
            absa_refine=absa_refine,
            explain=False,
            user_history=None,
            rerank=rerank,
            weights_override=None,
            semantic_backend=semantic_backend,
        )
        for rank, item in enumerate(results, start=1):
            movie = store.movie_index.get(str(item["movie_id"]), {})
            traces.append(
                {
                    "query_id": query_row["query_id"],
                    "query": query_row["query"],
                    "stratum": query_row["stratum"],
                    "artifact_dir": str(artifact_dir),
                    "model": model_label,
                    "rank": rank,
                    "movie_id": item["movie_id"],
                    "title": normalize_text(item.get("title", "")),
                    "genres": movie.get("genres", item.get("genres", [])),
                    "overview": normalize_text(movie.get("overview", item.get("overview", ""))),
                    "review_summary": review_summary(movie.get("search_text", ""), max_words=52),
                    "semantic_model_resolved": (debug or {}).get("semantic_model_resolved"),
                    "artifact_text_representation": (debug or {}).get("artifact_text_representation"),
                }
            )
    return traces


def _write_human_audit_sample(
    judged_rows: list[dict[str, Any]],
    output_path: Path,
    audit_size: int,
    seed: int,
) -> None:
    rng = random.Random(seed)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in judged_rows:
        grouped[(str(row["model"]), str(row["stratum"]))].append(row)
    per_group = max(1, audit_size // max(1, len(grouped)))
    sample: list[dict[str, Any]] = []
    for rows in grouped.values():
        pool = list(rows)
        rng.shuffle(pool)
        sample.extend(pool[:per_group])
    if len(sample) < audit_size:
        leftovers = [row for row in judged_rows if row not in sample]
        rng.shuffle(leftovers)
        sample.extend(leftovers[: audit_size - len(sample)])
    sample = sample[:audit_size]

    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "query_id",
                "model",
                "rank",
                "stratum",
                "query",
                "movie_id",
                "title",
                "judge_binary_relevant",
                "judge_relevance_score",
                "judge_reasoning",
                "human_binary_relevant",
                "human_relevance_score",
                "human_notes",
            ],
        )
        writer.writeheader()
        for row in sample:
            writer.writerow(
                {
                    "query_id": row["query_id"],
                    "model": row["model"],
                    "rank": row["rank"],
                    "stratum": row["stratum"],
                    "query": row["query"],
                    "movie_id": row["movie_id"],
                    "title": row["title"],
                    "judge_binary_relevant": row["binary_relevant"],
                    "judge_relevance_score": row["relevance_score"],
                    "judge_reasoning": row["reasoning"],
                    "human_binary_relevant": "",
                    "human_relevance_score": "",
                    "human_notes": "",
                }
            )


def _summarize(judged_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_model_stratum: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in judged_rows:
        by_model[str(row["model"])].append(row)
        by_model_stratum[(str(row["model"]), str(row["stratum"]))].append(row)

    summary = {"judged_rows": len(judged_rows), "by_model": [], "by_model_stratum": []}
    for model, rows in sorted(by_model.items()):
        summary["by_model"].append(
            {
                "model": model,
                "mean_relevance_score": round(
                    sum(float(r["relevance_score"]) for r in rows) / max(1, len(rows)),
                    4,
                ),
                "binary_relevant_rate": round(
                    sum(1 for r in rows if bool(r["binary_relevant"])) / max(1, len(rows)),
                    4,
                ),
                "count": len(rows),
            }
        )
    for (model, stratum), rows in sorted(by_model_stratum.items()):
        summary["by_model_stratum"].append(
            {
                "model": model,
                "stratum": stratum,
                "mean_relevance_score": round(
                    sum(float(r["relevance_score"]) for r in rows) / max(1, len(rows)),
                    4,
                ),
                "binary_relevant_rate": round(
                    sum(1 for r in rows if bool(r["binary_relevant"])) / max(1, len(rows)),
                    4,
                ),
                "count": len(rows),
            }
        )
    return summary


def _persist_outputs(
    scores_path: Path,
    errors_path: Path,
    summary_path: Path,
    audit_path: Path,
    judged_rows: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    *,
    audit_size: int,
    seed: int,
    trace_count: int,
    query_count: int,
    top_k: int,
    model_name: str,
    status: str,
) -> None:
    write_jsonl(scores_path, judged_rows)
    write_jsonl(errors_path, errors)
    _write_human_audit_sample(judged_rows, audit_path, audit_size=audit_size, seed=seed)
    summary = _summarize(judged_rows)
    summary.update(
        {
            "query_bank_version": QUERY_BANK_VERSION,
            "query_count": query_count,
            "top_k": top_k,
            "judge_model": model_name,
            "trace_count": trace_count,
            "completed_rows": len(judged_rows) + len(errors),
            "errors_count": len(errors),
            "status": status,
            "human_audit_sample_path": str(audit_path),
        }
    )
    if errors:
        summary["error_examples"] = [row["error"] for row in errors[:3]]
    write_json(summary_path, summary)


def run_judge(
    query_bank_path: Path,
    models: list[str],
    max_queries: int,
    top_k: int,
    audit_size: int,
    seed: int,
    dry_run: bool,
    absa_refine: bool,
    rerank: bool,
    semantic_backend: str,
    timeout_s: int,
    sleep_s: float,
    max_retries: int,
    retry_base_s: float,
    retry_max_s: float,
    continue_on_error: bool,
) -> dict[str, Path]:
    rows = _load_jsonl(query_bank_path)
    judge_queries = [row for row in rows if row.get("split") == "judge"]
    judge_queries = _balanced_sample(judge_queries, max_queries=max_queries, seed=seed)

    run_dir = ensure_dir(LLM_JUDGE_RUNS_DIR / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    traces_path = run_dir / "retrieval_traces.jsonl"
    scores_path = run_dir / "judge_scores.jsonl"
    errors_path = run_dir / "judge_errors.jsonl"
    summary_path = run_dir / "summary.json"
    audit_path = run_dir / "human_audit_sample.csv"

    all_traces: list[dict[str, Any]] = []
    for model_spec in models:
        artifact_dir = _resolve_artifact(model_spec)
        traces = _build_traces(
            queries=judge_queries,
            artifact_dir=artifact_dir,
            top_k=top_k,
            absa_refine=absa_refine,
            rerank=rerank,
            semantic_backend=semantic_backend,
        )
        all_traces.extend(traces)

    write_jsonl(traces_path, all_traces)

    judged_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if dry_run:
        write_json(
            summary_path,
            {"dry_run": True, "trace_count": len(all_traces), "judged_rows": 0, "errors_count": 0},
        )
        return {
            "run_dir": run_dir,
            "traces": traces_path,
            "summary": summary_path,
            "errors": errors_path,
        }

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Export it in the environment instead of hard-coding.")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    rubric = PROMPT_PATH.read_text(encoding="utf-8")
    query_lookup = {row["query_id"]: row for row in judge_queries}

    for idx, trace in enumerate(all_traces, start=1):
        query_row = query_lookup[trace["query_id"]]
        prompt = _render_prompt(rubric, query_row, trace)
        try:
            judgement = _call_gemini(
                prompt,
                model_name=model_name,
                api_key=api_key,
                timeout_s=timeout_s,
                max_retries=max_retries,
                retry_base_s=retry_base_s,
                retry_max_s=retry_max_s,
            )
            judged_rows.append({**trace, **judgement, "judge_model": model_name})
            status = "completed"
        except RuntimeError as exc:
            error_row = {
                **trace,
                "judge_model": model_name,
                "error": str(exc),
            }
            errors.append(error_row)
            status = "partial" if judged_rows else "failed"
            print(
                f"[warn] skipped row {idx}/{len(all_traces)} "
                f"query_id={trace['query_id']} model={trace['model']} rank={trace['rank']}: {exc}"
            )
            if not continue_on_error:
                _persist_outputs(
                    scores_path,
                    errors_path,
                    summary_path,
                    audit_path,
                    judged_rows,
                    errors,
                    audit_size=audit_size,
                    seed=seed,
                    trace_count=len(all_traces),
                    query_count=len(judge_queries),
                    top_k=top_k,
                    model_name=model_name,
                    status=status,
                )
                raise

        status = "completed"
        if errors and judged_rows:
            status = "partial"
        elif errors and not judged_rows:
            status = "failed"
        _persist_outputs(
            scores_path,
            errors_path,
            summary_path,
            audit_path,
            judged_rows,
            errors,
            audit_size=audit_size,
            seed=seed,
            trace_count=len(all_traces),
            query_count=len(judge_queries),
            top_k=top_k,
            model_name=model_name,
            status=status,
        )
        if sleep_s > 0 and idx < len(all_traces):
            time.sleep(sleep_s)
    final_status = "completed"
    if errors and judged_rows:
        final_status = "partial"
    elif errors and not judged_rows:
        final_status = "failed"
    _persist_outputs(
        scores_path,
        errors_path,
        summary_path,
        audit_path,
        judged_rows,
        errors,
        audit_size=audit_size,
        seed=seed,
        trace_count=len(all_traces),
        query_count=len(judge_queries),
        top_k=top_k,
        model_name=model_name,
        status=final_status,
    )
    return {
        "run_dir": run_dir,
        "traces": traces_path,
        "scores": scores_path,
        "errors": errors_path,
        "summary": summary_path,
        "human_audit": audit_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gemini LLM-as-a-Judge on retrieval traces")
    parser.add_argument(
        "--query-bank",
        type=Path,
        default=DATASETS_DIR / QUERY_BANK_VERSION / "retrieval_query_bank.jsonl",
    )
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--max-queries", type=int, default=36)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--audit-size", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--sleep-s", type=float, default=0.2)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--retry-base-s", type=float, default=5.0)
    parser.add_argument("--retry-max-s", type=float, default=60.0)
    parser.add_argument("--semantic-backend", default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-absa-refine", action="store_true")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    outputs = run_judge(
        query_bank_path=args.query_bank,
        models=args.models,
        max_queries=args.max_queries,
        top_k=args.top_k,
        audit_size=args.audit_size,
        seed=args.seed,
        dry_run=args.dry_run,
        absa_refine=not args.no_absa_refine,
        rerank=args.rerank,
        semantic_backend=args.semantic_backend,
        timeout_s=args.timeout_s,
        sleep_s=args.sleep_s,
        max_retries=args.max_retries,
        retry_base_s=args.retry_base_s,
        retry_max_s=args.retry_max_s,
        continue_on_error=not args.fail_fast,
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
