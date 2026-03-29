"""
Shim: mã nguồn chính nằm trong ``api.hybrid_search``.

Thư mục ``api`` được thêm vào sys.path từ project root (thư mục cha của
``Notebook_Report``), nên notebook vẫn import được khi kernel cwd là
``Notebook_Report``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from api.hybrid_search import *  # noqa: E402, F403
