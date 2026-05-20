"""Tests for ``pdf_cmap_fix.glyph_fingerprint`` (used by tier-3 lookup builds)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

from pdf_cmap_fix import glyph_fingerprint as gf


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
def test_fingerprint_glyph_stable_across_runs() -> None:
    path = _system_ttf()
    font = TTFont(str(path), lazy=False)
    try:
        h1 = gf.fingerprint_glyph(font, "A")
        h2 = gf.fingerprint_glyph(font, "A")
        assert h1 is not None and h1 == h2
    finally:
        font.close()


@pytest.mark.skipif(_system_ttf() is None, reason="no common system TTF found")
def test_fingerprint_glyph_differs_for_distinct_glyphs() -> None:
    path = _system_ttf()
    font = TTFont(str(path), lazy=False)
    try:
        a = gf.fingerprint_glyph(font, "A")
        b = gf.fingerprint_glyph(font, "B")
        assert a is not None and b is not None
        assert a != b
    finally:
        font.close()
