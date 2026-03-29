"""
Quick API smoke test: health, ABSA, and optional search/recommendations.

Run with backend up: uvicorn api.main:app --port 8000
  python scripts/test_api.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test CineSense API")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    ok = True
    movies = []

    # 1. Health
    print("1. GET /health")
    try:
        r = httpx.get(f"{base}/health", timeout=10)
        r.raise_for_status()
        data = r.json()
        db_ok = data.get("database_connected")
        print(
            f"   status={data.get('status')}, database_connected={db_ok}, movies_count={data.get('movies_count')}"
        )
        if db_ok is False:
            print("   FAIL: database not connected")
            ok = False
    except Exception as e:
        print(f"   FAIL: {e}")
        ok = False

    # 2. ABSA analyze (raw text)
    print("2. POST /absa/analyze (text)")
    try:
        r = httpx.post(
            f"{base}/absa/analyze",
            json={"text": "The script was weak but the acting was brilliant and visuals stunning."},
            timeout=30,
        )
        if r.status_code == 503:
            print("   ABSA model not loaded (export artifact from Kaggle_ABSA_Train_Standalone.ipynb or notebook 04 first)")
        else:
            r.raise_for_status()
            data = r.json()
            aspects = data.get("aspects") or []
            print(f"   aspects: {aspects}")
            if aspects:
                print("   OK: got aspect-sentiment pairs")
    except httpx.HTTPStatusError as e:
        print(f"   HTTP {e.response.status_code}: {e.response.text[:200]}")
        ok = False
    except Exception as e:
        print(f"   FAIL: {e}")
        ok = False

    # 3. List movies (first page)
    print("3. GET /movies")
    try:
        r = httpx.get(f"{base}/movies", params={"page": 1, "page_size": 2}, timeout=10)
        r.raise_for_status()
        data = r.json()
        total = data.get("total", 0)
        movies = data.get("movies") or []
        print(f"   total={total}, first page size={len(movies)}")
    except Exception as e:
        print(f"   FAIL: {e}")
        ok = False
        movies = []
    # 4. Similar movies (if we have a movie_id)
    if not movies:
        print("4. Skip similar (no movies)")
    elif movies[0].get("id"):
        movie_id = movies[0]["id"]
        print(f"4. GET /movies/{{movie_id}}/similar (movie_id={movie_id[:8]}...)")
        try:
            r = httpx.get(f"{base}/movies/{movie_id}/similar", params={"limit": 3}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                print(f"   results={data.get('total_results', 0)}")
            elif r.status_code == 503:
                print("   (recommendation artifact not loaded)")
            else:
                print(f"   {r.status_code}")
        except Exception as e:
            print(f"   FAIL: {e}")
    else:
        print("4. Skip similar (no movie id)")

    # 5. Recommendation search (artifact engine)
    print("5. POST /recommendations/search (engine=artifact)")
    try:
        r = httpx.post(
            f"{base}/recommendations/search",
            json={
                "query": "space adventure science fiction",
                "limit": 3,
                "absa_refine": False,
            },
            timeout=30,
        )
        if r.status_code == 503:
            print("   (recommendation artifact not loaded)")
        else:
            r.raise_for_status()
            data = r.json()
            n = len(data.get("results") or [])
            extra = ""
            if data.get("engines_used") is not None:
                extra += f", engines_used={data.get('engines_used')}"
            if data.get("query_effective"):
                extra += f", query_effective={data.get('query_effective')!r}"
            print(f"   results={n}, model={data.get('model')}{extra}")
    except Exception as e:
        print(f"   FAIL: {e}")
        ok = False

    # 6. Recommendation search (artifact with debug + rerank)
    print("6. POST /recommendations/search (artifact + debug)")
    try:
        r = httpx.post(
            f"{base}/recommendations/search",
            json={
                "query": "space adventure science fiction with strong visuals",
                "limit": 3,
                "absa_refine": True,
                "explain": True,
                "debug": True,
                "rerank": True,
            },
            timeout=60,
        )
        if r.status_code == 503:
            print(f"   (artifact recommender unavailable: {r.text[:200]})")
        else:
            r.raise_for_status()
            data = r.json()
            n = len(data.get("results") or [])
            extra = ""
            if data.get("engines_used") is not None:
                extra += f", engines_used={data.get('engines_used')}"
            if data.get("debug"):
                extra += ", debug=yes"
            print(f"   results={n}, model={data.get('model')}{extra}")
    except Exception as e:
        print(f"   FAIL: {e}")
        ok = False

    # 7. Baseline cosine (evaluation endpoint)
    print("7. POST /recommendations/baseline-cosine")
    try:
        r = httpx.post(
            f"{base}/recommendations/baseline-cosine",
            json={
                "query": "space adventure",
                "limit": 2,
                "baseline": "tfidf",
            },
            timeout=45,
        )
        if r.status_code == 503:
            print("   (baseline artifact not ready)")
        else:
            r.raise_for_status()
            data = r.json()
            print(
                f"   results={len(data.get('results') or [])}, baseline={data.get('baseline')}, model={data.get('model')}"
            )
    except Exception as e:
        print(f"   FAIL: {e}")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
