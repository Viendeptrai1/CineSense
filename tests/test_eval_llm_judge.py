from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from Notebook_Report.retrieval import eval_llm_judge as judge


def _response(
    status_code: int,
    payload: dict,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request(
        "POST",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    )
    return httpx.Response(status_code, request=request, json=payload, headers=headers)


def test_call_gemini_retries_429_and_uses_api_header(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    responses = [
        _response(429, {"error": {"message": "rate limited"}}, headers={"Retry-After": "0"}),
        _response(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "binary_relevant": True,
                                            "relevance_score": 5,
                                            "constraint_match_score": 4,
                                            "review_signal_score": 4,
                                            "reasoning": "Matches the requested vibe.",
                                            "matched_clues": ["space visuals"],
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        ),
    ]
    sleep_calls: list[float] = []

    def fake_post(url: str, *, headers: dict[str, str], json: dict, timeout: int) -> httpx.Response:
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return responses.pop(0)

    monkeypatch.setattr(judge.httpx, "post", fake_post)
    monkeypatch.setattr(judge.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = judge._call_gemini(
        prompt="space visuals",
        model_name="gemini-2.5-flash",
        api_key="secret-key",
        timeout_s=10,
        max_retries=2,
        retry_base_s=0.1,
        retry_max_s=1.0,
    )

    assert result["binary_relevant"] is True
    assert len(calls) == 2
    assert calls[0]["headers"] == {"x-goog-api-key": "secret-key"}
    assert "secret-key" not in calls[0]["url"]
    assert sleep_calls == [0.0]


def test_call_gemini_raises_sanitized_error_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        _response(429, {"error": {"message": "quota exhausted"}}),
        _response(429, {"error": {"message": "quota exhausted"}}),
    ]

    monkeypatch.setattr(judge.httpx, "post", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(judge.time, "sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError) as excinfo:
        judge._call_gemini(
            prompt="space visuals",
            model_name="gemini-2.5-flash",
            api_key="secret-key",
            timeout_s=10,
            max_retries=1,
            retry_base_s=0.1,
            retry_max_s=1.0,
        )

    message = str(excinfo.value)
    assert "429" in message
    assert "secret-key" not in message
    assert "generativelanguage.googleapis.com" not in message


def test_run_judge_continues_and_writes_partial_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    query_bank = tmp_path / "retrieval_query_bank.jsonl"
    query_rows = [
        {"query_id": "q1", "query": "space visuals", "stratum": "vibe", "split": "judge"},
        {"query_id": "q2", "query": "courtroom drama", "stratum": "keyword", "split": "judge"},
    ]
    query_bank.write_text("\n".join(json.dumps(row) for row in query_rows) + "\n", encoding="utf-8")

    prompt_path = tmp_path / "rubric.md"
    prompt_path.write_text("Judge relevance.", encoding="utf-8")

    traces = [
        {
            "query_id": "q1",
            "query": "space visuals",
            "stratum": "vibe",
            "artifact_dir": "artifact/sbert_en_finetuned_latest",
            "model": "sbert_en_finetuned_latest",
            "rank": 1,
            "movie_id": "m1",
            "title": "Space Echoes",
            "genres": ["Science Fiction"],
            "overview": "A visual sci-fi journey.",
            "review_summary": "space survival visuals",
            "semantic_model_resolved": "sbert:sbert_en_finetuned_latest",
            "artifact_text_representation": "review_profile_then_movie_profile_then_title_genres",
        },
        {
            "query_id": "q2",
            "query": "courtroom drama",
            "stratum": "keyword",
            "artifact_dir": "artifact/sbert_en_finetuned_latest",
            "model": "sbert_en_finetuned_latest",
            "rank": 1,
            "movie_id": "m2",
            "title": "The Final Verdict",
            "genres": ["Drama"],
            "overview": "A legal battle.",
            "review_summary": "tense legal drama",
            "semantic_model_resolved": "sbert:sbert_en_finetuned_latest",
            "artifact_text_representation": "review_profile_then_movie_profile_then_title_genres",
        },
    ]
    outcomes: list[dict | Exception] = [
        {
            "binary_relevant": True,
            "relevance_score": 4,
            "constraint_match_score": 4,
            "review_signal_score": 4,
            "reasoning": "Relevant sci-fi vibe.",
            "matched_clues": ["space visuals"],
        },
        RuntimeError("Gemini request failed with status 429: quota exhausted"),
    ]

    def fake_build_traces(**_kwargs) -> list[dict]:
        return traces

    def fake_call(*_args, **_kwargs) -> dict:
        result = outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(judge, "LLM_JUDGE_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(judge, "PROMPT_PATH", prompt_path)
    monkeypatch.setattr(judge, "_build_traces", fake_build_traces)
    monkeypatch.setattr(judge, "_call_gemini", fake_call)
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

    outputs = judge.run_judge(
        query_bank_path=query_bank,
        models=["sbert_en_finetuned_latest"],
        max_queries=2,
        top_k=1,
        audit_size=4,
        seed=42,
        dry_run=False,
        absa_refine=False,
        rerank=False,
        semantic_backend="auto",
        timeout_s=10,
        sleep_s=0,
        max_retries=0,
        retry_base_s=0,
        retry_max_s=0,
        continue_on_error=True,
    )

    summary = json.loads(Path(outputs["summary"]).read_text(encoding="utf-8"))
    errors = [json.loads(line) for line in Path(outputs["errors"]).read_text(encoding="utf-8").splitlines() if line]

    assert summary["status"] == "partial"
    assert summary["judged_rows"] == 1
    assert summary["errors_count"] == 1
    assert len(errors) == 1
    assert "429" in errors[0]["error"]
