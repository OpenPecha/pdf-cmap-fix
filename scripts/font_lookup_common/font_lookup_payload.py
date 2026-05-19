"""
Build per-font lookup JSON payloads (tier 1 gid, tier 2 gname, tier 3 gshape).

Shared by ``single_font_lookup.py`` and ``per_font_maps.py`` (``scripts/font_lookup_common/``).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pdf_cmap_fix.glyph_fingerprint import fingerprint_glyph  # noqa: E402

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont


def build_lookup_json_payload(
    *,
    font: "TTFont",
    key: str,
    gid_map: dict[int, str],
    counts_int: dict[int, int],
    kind: str,
    source_id: str,
) -> dict[str, Any]:
    """Return ``{ key: inner_map, "_meta": {...} }`` for one font face."""
    multi = sum(1 for v in gid_map.values() if len(v) > 1)
    counts = {str(k): v for k, v in counts_int.items()}
    meta: dict[str, Any] = {
        "lookup_kind": kind,
        "source": source_id,
        "gids_mapped": len(gid_map),
        "multi_char_stacks": multi,
        "gsub_lookup_counts": counts,
    }

    if kind == "gid":
        inner: dict[str, str] = {str(gid): uni for gid, uni in gid_map.items()}
    elif kind == "gname":
        glyph_order = font.getGlyphOrder()
        inner = {}
        gname_collisions: list[dict[str, object]] = []
        for gid, uni in sorted(gid_map.items()):
            gname = glyph_order[gid]
            if gname in inner:
                if inner[gname] != uni:
                    gname_collisions.append(
                        {
                            "glyph_name": gname,
                            "kept_unicode": inner[gname],
                            "skipped_gid": gid,
                            "skipped_unicode": uni,
                        }
                    )
                continue
            inner[gname] = uni
        meta["entries"] = len(inner)
        if gname_collisions:
            meta["glyph_name_collisions"] = gname_collisions
    elif kind == "gshape":
        glyph_order = font.getGlyphOrder()
        inner = {}
        hash_collisions: list[dict[str, object]] = []
        skipped: list[dict[str, object]] = []
        for gid, uni in sorted(gid_map.items()):
            gname = glyph_order[gid]
            fp = fingerprint_glyph(font, gname)
            if fp is None:
                skipped.append({"gid": gid, "glyph_name": gname})
                continue
            if fp in inner:
                if inner[fp] != uni:
                    hash_collisions.append(
                        {
                            "fingerprint": fp,
                            "kept_unicode": inner[fp],
                            "skipped_gid": gid,
                            "skipped_glyph_name": gname,
                            "skipped_unicode": uni,
                        }
                    )
                continue
            inner[fp] = uni
        meta["entries"] = len(inner)
        meta["fingerprint_method"] = (
            "HashPointPen+RoundingPointPen(floatToFixedToFloat 14-bit)"
        )
        if hash_collisions:
            meta["hash_collisions"] = hash_collisions
        if skipped:
            meta["skipped_no_fingerprint"] = skipped
    else:
        raise ValueError(f"unknown lookup kind: {kind!r}")

    return {key: inner, "_meta": meta}
