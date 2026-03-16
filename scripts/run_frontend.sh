#!/usr/bin/env bash
# Chạy frontend (trang web).
# Mở http://localhost:3000 sau khi chạy.

set -e
cd "$(dirname "$0")/../frontend"
echo "Starting frontend at http://localhost:3000"
exec python3 -m http.server 3000
