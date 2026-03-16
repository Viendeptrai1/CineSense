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
        print(f"   status={data.get('status')}, movies_count={data.get('movies_count')}")
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
            print("   ABSA model not loaded (train first: python -m training.models.absa_model)")
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

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
