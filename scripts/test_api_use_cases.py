"""
Integration tests: use cases với payload phức tạp hơn smoke test cơ bản.

Chạy khi backend đã bật:
  .venv/bin/python scripts/test_api_use_cases.py [--base-url http://localhost:8000]

Mã thoát 0 nếu mọi bắt buộc pass; 503 (artifact/hybrid/ABSA chưa sẵn sàng) được ghi SKIP, không fail cả suite.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from typing import Any

import httpx

BASE_DEFAULT = "http://127.0.0.1:8000"


def _abbrev(msg: str, n: int = 120) -> str:
    return msg if len(msg) <= n else msg[: n - 3] + "..."


class CaseResult:
    def __init__(self, name: str) -> None:
        self.name = name
        self.status = "PENDING"
        self.detail = ""

    def ok(self, detail: str = "") -> None:
        self.status = "OK"
        self.detail = detail

    def skip(self, detail: str = "") -> None:
        self.status = "SKIP"
        self.detail = detail

    def fail(self, detail: str = "") -> None:
        self.status = "FAIL"
        self.detail = detail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_DEFAULT)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    results: list[CaseResult] = []
    movie_id: str | None = None
    indexed_movie_id: str | None = None

    # Long timeout for hybrid first warm-up (SBERT encode corpus)
    hybrid_timeout = 300.0

    with httpx.Client(base_url=base) as client:
        # --- UC1: Health ---
        r1 = CaseResult("UC1 GET /health — hệ thống sống + DB")
        try:
            r = client.get("/health", timeout=10)
            r.raise_for_status()
            d = r.json()
            if d.get("status") != "healthy":
                r1.fail(f"status={d.get('status')}")
            elif d.get("database_connected") is not True:
                r1.fail("database_connected is not true")
            else:
                r1.ok(f"movies_count={d.get('movies_count')}")
        except Exception as e:
            r1.fail(str(e))
        results.append(r1)

        # --- UC2: Danh sách phim + lấy id ---
        r2 = CaseResult("UC2 GET /movies — phân trang & UUID")
        try:
            r = client.get("/movies", params={"page": 1, "page_size": 5}, timeout=15)
            r.raise_for_status()
            d = r.json()
            movies = d.get("movies") or []
            if not movies:
                r2.fail("empty movies list")
            elif not movies[0].get("id"):
                r2.fail("movie missing id")
            else:
                movie_id = movies[0]["id"]
                r2.ok(f"total={d.get('total')}, sample_id={str(movie_id)[:8]}…")
        except Exception as e:
            r2.fail(str(e))
        # Movie đầu catalog có thể không nằm trong movie_index của artifact — lấy id từ trending
        try:
            rt = client.get("/recommendations/trending", params={"limit": 1}, timeout=15)
            if rt.status_code == 200:
                tr = rt.json().get("results") or []
                if tr and tr[0].get("movie_id"):
                    indexed_movie_id = tr[0]["movie_id"]
        except Exception:
            pass
        results.append(r2)

        # --- UC3: Chi tiết phim ---
        r3 = CaseResult("UC3 GET /movies/{id} — metadata đầy đủ")
        if not movie_id:
            r3.skip("no movie_id")
        else:
            try:
                r = client.get(f"/movies/{movie_id}", timeout=15)
                r.raise_for_status()
                d = r.json()
                if not d.get("title"):
                    r3.fail("no title")
                else:
                    r3.ok(f"title={_abbrev(d['title'], 50)}")
            except Exception as e:
                r3.fail(str(e))
        results.append(r3)

        # --- UC4: ABSA — câu nhiều khía cạnh + từ lóng ---
        r4 = CaseResult("UC4 POST /absa/analyze — text phức tạp")
        complex_text = (
            "The pacing dragged in act two and the plot had holes, but the cinematography "
            "was gorgeous, soundtrack emotional, and the lead performance carried the film; "
            "dialogue felt wooden at times yet the twist ending redeemed it."
        )
        try:
            r = client.post("/absa/analyze", json={"text": complex_text}, timeout=60)
            if r.status_code == 503:
                r4.skip("ABSA model not loaded (503)")
            else:
                r.raise_for_status()
                aspects = r.json().get("aspects") or []
                if len(aspects) < 2:
                    r4.fail(f"expected >=2 aspects, got {len(aspects)}")
                else:
                    r4.ok(f"{len(aspects)} aspects: {aspects[:3]}…")
        except Exception as e:
            r4.fail(str(e))
        results.append(r4)

        # --- UC5: Similar (id phải có trong recommendation index) ---
        r5 = CaseResult("UC5 GET /movies/{id}/similar — id từ trending")
        mid = indexed_movie_id
        if not mid:
            r5.skip("no indexed movie_id from trending")
        else:
            try:
                r = client.get(f"/movies/{mid}/similar", params={"limit": 5}, timeout=15)
                if r.status_code == 503:
                    r5.skip("artifacts not ready (503)")
                elif r.status_code != 200:
                    r5.fail(f"HTTP {r.status_code}: {_abbrev(r.text)}")
                else:
                    n = r.json().get("total_results", 0)
                    r5.ok(f"neighbors={n}")
            except Exception as e:
                r5.fail(str(e))
        results.append(r5)

        # --- UC6: Trending ---
        r6 = CaseResult("UC6 GET /recommendations/trending")
        try:
            r = client.get("/recommendations/trending", params={"limit": 5}, timeout=15)
            if r.status_code == 503:
                r6.skip("artifacts (503)")
            else:
                r.raise_for_status()
                n = len(r.json().get("results") or [])
                r6.ok(f"results={n}")
        except Exception as e:
            r6.fail(str(e))
        results.append(r6)

        # --- UC7: Artifact search — truy vấn dài, typo, sentiment + thể loại ---
        r7 = CaseResult("UC7 POST search engine=artifact — query phức tạp")
        artifact_queries = [
            {
                "query": "psychological thriller non-linear timeline unreliable narrator 1990s",
                "limit": 8,
                "engine": "artifact",
                "query_type": "auto",
                "absa_refine": True,
                "explain": True,
                "user_history": ["noir detective", "slow burn drama"],
                "rerank": False,
            },
            {
                "query": "Incpetion dream heist",  # typo deliberate
                "limit": 5,
                "engine": "artifact",
                "filters": {"genres": ["Science Fiction"], "min_year": 2005},
                "absa_refine": False,
            },
        ]
        try:
            all_ok = True
            summaries = []
            for payload in artifact_queries:
                rr = client.post("/recommendations/search", json=payload, timeout=45)
                if rr.status_code == 503:
                    r7.skip("artifact store not ready (503)")
                    all_ok = False
                    break
                rr.raise_for_status()
                data = rr.json()
                results_list = data.get("results") or []
                if not results_list:
                    all_ok = False
                    summaries.append("empty results")
                    break
                first = results_list[0]
                if not first.get("movie_id"):
                    all_ok = False
                    summaries.append("missing movie_id")
                    break
                summaries.append(f"n={len(results_list)} top={_abbrev(first.get('title') or '', 30)}")
            if all_ok and r7.status == "PENDING":
                r7.ok("; ".join(summaries))
        except Exception as e:
            r7.fail(str(e))
        results.append(r7)

        # --- UC8: Hybrid — cùng ý định tìm, ABSA-heavy query, debug ---
        r8 = CaseResult("UC8 POST search engine=hybrid — vibe + explain + debug")
        hybrid_payload = {
            "query": "great visuals but pacing too slow emotional ending",
            "limit": 6,
            "engine": "hybrid",
            "explain": True,
            "debug": True,
            "absa_refine": True,
            "filters": {"min_year": 2010},
            "user_history": ["ignored-by-design"],
            "rerank": True,
        }
        try:
            rr = client.post("/recommendations/search", json=hybrid_payload, timeout=hybrid_timeout)
            if rr.status_code == 503:
                r8.skip(f"hybrid unavailable: {_abbrev(rr.text, 200)}")
            else:
                rr.raise_for_status()
                data = rr.json()
                if not str(data.get("model", "")).startswith("hybrid"):
                    r8.fail(f"model should start with hybrid:, got {data.get('model')}")
                elif not data.get("results"):
                    r8.fail("empty hybrid results")
                else:
                    dbg = data.get("debug") or {}
                    notes = dbg.get("hybrid_notes") or []
                    first = data["results"][0]
                    br = first.get("score_breakdown") or {}
                    if hybrid_payload["explain"] and not br:
                        r8.fail("explain=true but no score_breakdown")
                    elif dbg.get("engine") != "hybrid":
                        r8.fail("debug.engine != hybrid")
                    else:
                        r8.ok(
                            f"n={len(data['results'])}, debug_notes={len(notes)}, "
                            f"absa_in_breakdown={br.get('absa_bonus') is not None}"
                        )
        except Exception as e:
            r8.fail(str(e))
        results.append(r8)

        # --- UC9: So sánh thứ tự artifact vs hybrid (cùng query) ---
        r9 = CaseResult("UC9 So sánh ranking artifact vs hybrid (query cố định)")
        q = "space exploration crew isolation mystery"
        try:
            ra = client.post(
                "/recommendations/search",
                json={"query": q, "limit": 10, "engine": "artifact", "absa_refine": False},
                timeout=45,
            )
            rh = client.post(
                "/recommendations/search",
                json={"query": q, "limit": 10, "engine": "hybrid", "explain": False},
                timeout=hybrid_timeout,
            )
            if ra.status_code == 503 or rh.status_code == 503:
                r9.skip("one engine returned 503")
            else:
                ra.raise_for_status()
                rh.raise_for_status()
                ids_a = [x.get("movie_id") for x in ra.json().get("results") or []]
                ids_h = [x.get("movie_id") for x in rh.json().get("results") or []]
                if not ids_a or not ids_h:
                    r9.fail("empty results on one side")
                else:
                    same_top = ids_a[0] == ids_h[0]
                    overlap = len(set(ids_a) & set(ids_h))
                    r9.ok(
                        f"top_match={same_top}, overlap_in_top10={overlap}/10 "
                        f"(khác thứ tự là bình thường giữa hai engine)"
                    )
        except Exception as e:
            r9.fail(str(e))
        results.append(r9)

        # --- UC10: Validation 422 ---
        r10 = CaseResult("UC10 POST search — query quá ngắn → 422")
        try:
            r = client.post(
                "/recommendations/search",
                json={"query": "a", "engine": "artifact"},
                timeout=10,
            )
            if r.status_code != 422:
                r10.fail(f"expected 422, got {r.status_code}")
            else:
                r10.ok("validation error as expected")
        except Exception as e:
            r10.fail(str(e))
        results.append(r10)

        # --- UC11: Reload (idempotent) ---
        r11 = CaseResult("UC11 POST /recommendations/reload")
        try:
            r = client.post("/recommendations/reload", timeout=120)
            if r.status_code != 200:
                r11.fail(f"HTTP {r.status_code}")
            else:
                d = r.json()
                r11.ok(f"ready={d.get('ready')}, model={d.get('model')}")
        except Exception as e:
            r11.fail(str(e))
        results.append(r11)

        # --- UC12: UUID giả → similar 404 ---
        r12 = CaseResult("UC12 GET similar — movie_id không tồn tại → 404")
        fake = str(uuid.uuid4())
        try:
            r = client.get(f"/movies/{fake}/similar", params={"limit": 3}, timeout=10)
            if r.status_code == 404:
                r12.ok("404 as expected")
            elif r.status_code == 503:
                r12.skip("503 artifacts")
            else:
                r12.fail(f"expected 404, got {r.status_code}")
        except Exception as e:
            r12.fail(str(e))
        results.append(r12)

    # Report
    fail_count = sum(1 for x in results if x.status == "FAIL")
    skip_count = sum(1 for x in results if x.status == "SKIP")
    ok_count = sum(1 for x in results if x.status == "OK")

    print("\n========== Use-case integration tests ==========\n")
    for x in results:
        print(f"[{x.status:4}] {x.name}")
        if x.detail:
            print(f"       → {x.detail}")
    print(
        f"\nTổng: OK={ok_count}, SKIP={skip_count}, FAIL={fail_count} "
        f"(SKIP = môi trường chưa train / thiếu artifact hoặc hybrid data)\n"
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
