#!/usr/bin/env bash
# Chạy CineSense API (backend).
# Yêu cầu: venv + database (mặc định SQLite ./data/cinesense.db sau khi chạy scripts/seed_sqlite_from_csv.py).

set -e
cd "$(dirname "$0")/.."
echo "Starting CineSense API at http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
exec python -m uvicorn api.main:app --reload --port 8000
