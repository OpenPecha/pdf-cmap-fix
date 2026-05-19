"""Shared helpers for detecting PUA in font lookup JSON string values."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def in_pua_bmp(c: str) -> bool:
    o = ord(c)
    return 0xE000 <= o <= 0xF8FF


def in_pua_supplementary(c: str) -> bool:
    o = ord(c)
    return 0xF0000 <= o <= 0xFFFFD or 0x100000 <= o <= 0x10FFFD


def value_has_pua(s: str) -> bool:
    return any(in_pua_bmp(c) or in_pua_supplementary(c) for c in s)


def iter_inner_string_entries(data: dict[str, Any]) -> Any:
    """Yield (outer_key, inner_key, value) for string values in nested lookup dicts."""
    for font_key, inner in data.items():
        if font_key == "_meta" or not isinstance(inner, dict):
            continue
        for k, v in inner.items():
            if isinstance(v, str) and v:
                yield font_key, k, v


def count_pua_in_lookup_json(path: Path) -> tuple[int, int, int]:
    """Return (rows_with_pua, total_string_rows, rows_bmp_pua)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    total = 0
    with_pua = 0
    bmp_only = 0
    for _, _, v in iter_inner_string_entries(data):
        total += 1
        if value_has_pua(v):
            with_pua += 1
            if any(in_pua_bmp(c) for c in v):
                bmp_only += 1
    return with_pua, total, bmp_only
