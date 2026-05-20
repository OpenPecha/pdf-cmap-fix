"""
Core gshape PUA-patch logic: build fingerprint→gname map from a TTFont and
replace PUA values in a gshape lookup JSON using a public-Unicode gname sidecar.

Imported by ``scripts/pua/gshape/`` CLIs and ``scripts/misc/``.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pdf_cmap_fix.glyph_fingerprint import fingerprint_glyph  # noqa: E402


def _in_pua_bmp(c: str) -> bool:
    o = ord(c)
    return 0xE000 <= o <= 0xF8FF


def _in_pua_supplementary(c: str) -> bool:
    o = ord(c)
    return 0xF0000 <= o <= 0xFFFFD or 0x100000 <= o <= 0x10FFFD


def value_has_pua(s: str) -> bool:
    return any(_in_pua_bmp(c) or _in_pua_supplementary(c) for c in s)


def first_inner_map(data: dict) -> tuple[str, dict]:
    """Return (key, inner_dict) for the first non-_meta inner dict."""
    for k, v in data.items():
        if k == "_meta" or not isinstance(v, dict):
            continue
        return k, v
    raise ValueError("no inner map in JSON")


def build_hash_to_gname(font: TTFont) -> tuple[dict[str, str], int]:
    """Map fingerprint string -> glyph name (last wins on collision). Returns (map, collision_count)."""
    out: dict[str, str] = {}
    collisions = 0
    for gname in font.getGlyphOrder():
        h = fingerprint_glyph(font, gname)
        if not h:
            continue
        if h in out and out[h] != gname:
            collisions += 1
        out[h] = gname
    return out, collisions


def patch_gshape_data(
    *,
    font: TTFont,
    gshape_data: dict,
    public_gname_inner: dict[str, str],
) -> tuple[int, int, int, int]:
    """
    Mutates the gshape inner dict in ``gshape_data`` in place. Returns
    (rows_patched, rows_skipped_no_gname, rows_skipped_no_pua, hash_collisions).
    """
    _, inner = first_inner_map(gshape_data)
    h2g, hash_collisions = build_hash_to_gname(font)

    patched = 0
    no_gname = 0
    no_pua = 0
    for h, old_u in list(inner.items()):
        gname = h2g.get(h)
        if not gname or gname not in public_gname_inner:
            no_gname += 1
            continue
        new_u = public_gname_inner[gname]
        if not value_has_pua(old_u):
            no_pua += 1
            continue
        if new_u == old_u:
            no_pua += 1
            continue
        inner[h] = new_u
        patched += 1

    meta = gshape_data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
        gshape_data["_meta"] = meta
    meta["gshape_rows_patched_from_public_gname"] = patched
    meta["gshape_patch_skipped_no_hash_to_gname"] = no_gname
    meta["gshape_patch_skipped_no_pua_in_value"] = no_pua
    meta["gshape_patch_font_hash_collisions"] = hash_collisions
    return patched, no_gname, no_pua, hash_collisions
