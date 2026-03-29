"""
English spell hints for search queries (optional, pyspellchecker).

Does not replace domain-specific names (e.g. Doraemon) if not in the dictionary;
still helps common typos (thriler → thriller).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any


def _similar_enough(original: str, candidate: str) -> bool:
    """Tránh sửa quá mạnh (vd. doramon → dragon) — chỉ giữ khi gần nghĩa ký tự."""
    if not original or not candidate:
        return False
    if abs(len(original) - len(candidate)) > 4:
        return False
    return SequenceMatcher(None, original, candidate).ratio() >= 0.82


@lru_cache(maxsize=1)
def _get_spellchecker() -> Any | None:
    try:
        from spellchecker import SpellChecker  # type: ignore[import-untyped]

        return SpellChecker()
    except Exception:
        return None


def apply_autocorrect_english(text: str) -> tuple[str, bool]:
    """
    Token-level correction for Latin letters. Returns (new_text, changed).

    Skips: numbers, punctuation-only tokens, hyphenated tokens, very short tokens.
    """
    sc = _get_spellchecker()
    raw = text or ""
    if sc is None or not raw.strip():
        return raw, False

    changed = False
    out: list[str] = []

    for m in re.finditer(r"[A-Za-z]+|[^A-Za-z\s]+|\s+", raw):
        chunk = m.group(0)
        if chunk.isspace() or not chunk.strip():
            out.append(chunk)
            continue
        if not re.match(r"^[A-Za-z]+$", chunk):
            out.append(chunk)
            continue
        if len(chunk) < 2:
            out.append(chunk)
            continue

        lower = chunk.lower()
        if lower in sc:
            out.append(chunk)
            continue

        unknown = sc.unknown([lower])
        if not unknown:
            out.append(chunk)
            continue

        cand = sc.correction(lower)
        if not cand or cand == lower or not _similar_enough(lower, cand):
            out.append(chunk)
            continue

        fixed = cand
        if chunk[0].isupper():
            fixed = cand.capitalize()
        out.append(fixed)
        changed = True

    new_text = "".join(out)
    return new_text, changed
