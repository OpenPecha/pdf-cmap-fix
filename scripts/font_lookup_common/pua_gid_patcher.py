"""
Core GID PUA-patch logic: for each GID in a tier-1 lookup, resolve the glyph name
from the font's glyph order and replace the stored Unicode with the value from a
gname PUA-free sidecar when available.

Imported by ``scripts/pua/gid/`` CLIs.
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")


def first_inner_map(data: dict) -> tuple[str, dict]:
    """Return (key, inner_dict) for the first non-_meta inner dict."""
    for k, v in data.items():
        if k == "_meta" or not isinstance(v, dict):
            continue
        return k, v
    raise ValueError("no inner map in JSON")


def patch_gid_lookup_with_gname_inner(
    *,
    font: TTFont,
    gid_key: str,
    gid_inner: dict,
    gname_inner: dict[str, str],
    out_key: str | None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Return ``(resolved_out_key, new_inner, meta_updates)``.

    For each GID string key: resolves the glyph name from the font's glyph order
    and replaces the Unicode value with the entry from ``gname_inner`` when present.
    """
    go = font.getGlyphOrder()
    resolved_out = out_key or gid_key
    patched_inner: dict[str, str] = {}
    changed = 0
    missing_gname = 0
    for gid_str, uni in gid_inner.items():
        if not isinstance(uni, str):
            continue
        try:
            gid = int(str(gid_str))
        except ValueError:
            continue
        if gid < 0 or gid >= len(go):
            patched_inner[str(gid_str)] = uni
            continue
        gname = go[gid]
        if gname in gname_inner:
            new_u = gname_inner[gname]
            if new_u != uni:
                changed += 1
            patched_inner[str(gid_str)] = new_u
        else:
            patched_inner[str(gid_str)] = uni
            missing_gname += 1
    meta_updates: dict[str, Any] = {
        "lookup_kind": "gid",
        "gid_rows_patched_from_gname_json": changed,
        "gid_patch_missing_gname_entries": missing_gname,
    }
    return resolved_out, patched_inner, meta_updates
