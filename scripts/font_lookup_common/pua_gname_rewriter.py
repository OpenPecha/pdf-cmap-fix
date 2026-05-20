"""
Core gname PUA-rewrite logic: decode ``uni…`` glyph names to Unicode and replace
PUA values in gname lookup JSON.

Imported by ``scripts/pua/gname/`` CLIs and ``scripts/misc/inspect_pua_gname.py``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_RE_UNI_NAME = re.compile(r"^uni([0-9A-Fa-f]+)$")


def _in_pua_bmp(c: str) -> bool:
    o = ord(c)
    return 0xE000 <= o <= 0xF8FF


def _in_pua_supplementary(c: str) -> bool:
    o = ord(c)
    return 0xF0000 <= o <= 0xFFFFD or 0x100000 <= o <= 0x10FFFD


def value_has_pua(s: str) -> bool:
    return any(_in_pua_bmp(c) or _in_pua_supplementary(c) for c in s)


def decode_uni_glyph_name(gname: str) -> str | None:
    """Decode ``uni0F400F72`` → two codepoints. Returns None if not uni+4-hex chunks."""
    m = _RE_UNI_NAME.match(gname)
    if not m:
        return None
    body = m.group(1)
    if len(body) % 4 != 0:
        return None
    try:
        return "".join(chr(int(body[i : i + 4], 16)) for i in range(0, len(body), 4))
    except ValueError:
        return None


def build_pua_map(inner: dict[str, str]) -> tuple[dict[str, str], list[tuple[str, str, str, str]]]:
    """
    Returns (mapping, collisions) where mapping is PUA value → decoded Unicode
    and each collision is (pua_value, old_target, new_target, gname).
    """
    m: dict[str, str] = {}
    collisions: list[tuple[str, str, str, str]] = []
    for gname, val in inner.items():
        if gname == "_meta":
            continue
        parsed = decode_uni_glyph_name(gname)
        if parsed is None:
            continue
        if parsed == val:
            continue
        if not value_has_pua(val):
            continue
        if val in m:
            if m[val] != parsed:
                collisions.append((val, m[val], parsed, gname))
            continue
        m[val] = parsed
    return m, collisions


def apply_pua_map(text: str, m: dict[str, str]) -> str:
    """Replace longest keys first so multi-codepoint PUA strings match."""
    if not m:
        return text
    keys = sorted(m.keys(), key=len, reverse=True)
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        matched = False
        for k in keys:
            if text.startswith(k, i):
                out.append(m[k])
                i += len(k)
                matched = True
                break
        if not matched:
            out.append(text[i])
            i += 1
    return "".join(out)


def rewrite_gname_lookup_pua_values(data: dict[str, Any]) -> int:
    """In-place: replace inner values where ``uni…`` name decodes to non-PUA and value has PUA.

    Returns number of rows rewritten.
    """
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
        data["_meta"] = meta
    n = 0
    for font_key, inner in data.items():
        if font_key == "_meta" or not isinstance(inner, dict):
            continue
        for gname, val in list(inner.items()):
            if not isinstance(val, str):
                continue
            parsed = decode_uni_glyph_name(gname)
            if parsed is None:
                continue
            if parsed == val:
                continue
            if not value_has_pua(val):
                continue
            inner[gname] = parsed
            n += 1
    meta["pua_to_unicode_from_uni_names"] = True
    meta["pua_rows_rewritten"] = n
    return n


def load_inner(path: Path) -> dict[str, str]:
    """Load the first non-_meta inner dict from a gname lookup JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for k, v in data.items():
        if k == "_meta" or not isinstance(v, dict):
            continue
        return dict(v)
    raise ValueError("No inner glyph map found in JSON")


def load_full_lookup(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
