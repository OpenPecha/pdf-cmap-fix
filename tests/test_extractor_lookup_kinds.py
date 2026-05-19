"""Tests for extractor gname / gshape lookup resolution."""
from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock

from typing import Optional

import pytest
from fontTools.ttLib import TTFont

from pdf_cmap_fix import tounicode_core as ex
from pdf_cmap_fix.glyph_fingerprint import fingerprint_glyph


def _arial_ttf_bytes() -> Optional[bytes]:
    for p in (
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ):
        if p.is_file():
            return p.read_bytes()
    return None


@pytest.mark.skipif(_arial_ttf_bytes() is None, reason="no common Arial-like TTF")
def test_load_lookup_file_gid_default() -> None:
    import tempfile

    payload = {
        "arial": {"65": "A"},
        "_meta": {"source": "test"},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f)
        p = Path(f.name)
    try:
        r = ex._load_lookup_file(p)
        assert r is not None
        kind, inner = r
        assert kind == "gid"
        assert inner["65"] == "A"
        m = ex._gid_map_from_inner(inner)
        assert m[65] == "A"
    finally:
        p.unlink(missing_ok=True)


@pytest.mark.skipif(_arial_ttf_bytes() is None, reason="no common Arial-like TTF")
def test_resolve_db_gid_map_gname() -> None:
    buf = _arial_ttf_bytes()
    assert buf is not None
    doc = MagicMock()
    doc.extract_font.return_value = ("arial", "ttf", "", buf)
    inner = {"A": "\u2603"}
    r = ex._resolve_db_gid_map(doc, 1, "gname", inner)
    f = TTFont(io.BytesIO(buf))
    try:
        gid_a = f.getGlyphOrder().index("A")
    finally:
        f.close()
    assert r.get(gid_a) == "\u2603"
    doc.extract_font.assert_called_once_with(1)


@pytest.mark.skipif(_arial_ttf_bytes() is None, reason="no common Arial-like TTF")
def test_resolve_db_gid_map_gshape() -> None:
    buf = _arial_ttf_bytes()
    assert buf is not None
    f = TTFont(io.BytesIO(buf))
    try:
        gid_a = f.getGlyphOrder().index("A")
        h = fingerprint_glyph(f, "A")
    finally:
        f.close()
    assert h is not None
    doc = MagicMock()
    doc.extract_font.return_value = ("arial", "ttf", "", buf)
    inner = {h: "\u2604"}
    r = ex._resolve_db_gid_map(doc, 1, "gshape", inner)
    assert r.get(gid_a) == "\u2604"
