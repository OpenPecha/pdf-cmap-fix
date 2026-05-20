"""Tests for gname/gshape ``update_font_lookup.py`` via ``font_lookup_common``."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_COMMON = REPO / "scripts" / "font_lookup_common"


def _system_ttf() -> Path | None:
    for p in (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ):
        if p.is_file():
            return p
    return None


@pytest.mark.skipif(_system_ttf() is None, reason="no common system TTF found")
def test_gname_inner_entry_count_matches_gid_map(tmp_path: Path) -> None:
    if str(SCRIPTS_COMMON) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_COMMON))
    from per_font_maps import _build_gid_map_safe
    import single_font_lookup as sfl

    path = _system_ttf()
    font = TTFont(str(path), lazy=False)
    try:
        gid_map, _, _ = _build_gid_map_safe(font, str(path))
    finally:
        font.close()

    sfl._write_one(path, tmp_path, None, None, False, kind="gname")
    written = next(tmp_path.glob("*.json"))
    data = json.loads(written.read_text(encoding="utf-8"))
    meta = data["_meta"]
    assert meta["lookup_kind"] == "gname"
    key = next(k for k in data if k != "_meta")
    inner = data[key]
    assert len(inner) == len(gid_map)
    assert meta["entries"] == len(gid_map)


@pytest.mark.skipif(_system_ttf() is None, reason="no common system TTF found")
def test_gshape_hash_collision_recorded_in_meta(tmp_path: Path) -> None:
    if str(SCRIPTS_COMMON) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_COMMON))
    import font_lookup_payload as flp
    import single_font_lookup as sfl

    path = _system_ttf()

    def _fake_fp(font, gname: str):
        if gname in ("a", "b"):
            return "forced_same_hash"
        from pdf_cmap_fix.glyph_fingerprint import fingerprint_glyph as _real_fp

        return _real_fp(font, gname)

    with patch.object(flp, "fingerprint_glyph", side_effect=_fake_fp):
        sfl._write_one(path, tmp_path, None, None, False, kind="gshape")

    written = next(tmp_path.glob("*.json"))
    data = json.loads(written.read_text(encoding="utf-8"))
    meta = data["_meta"]
    assert meta["lookup_kind"] == "gshape"
    hc = meta.get("hash_collisions") or []
    assert any(c.get("fingerprint") == "forced_same_hash" for c in hc)
