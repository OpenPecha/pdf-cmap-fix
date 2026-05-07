"""Smoke tests for ``scripts/gid_map.py`` (``build_gid_map``, ``normalise_name``)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"


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
def test_build_gid_map_smoke() -> None:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import gid_map as gm

    font = TTFont(str(_system_ttf()), lazy=False)
    m = gm.build_gid_map(font)
    assert len(m) >= 50
    assert any(v.strip() and ord(v[0]) < 0x80 for v in m.values())


def test_normalise_font_stem() -> None:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import gid_map as gm

    assert gm.normalise_name("fonts/Monlam Uni OuChan2.ttf") == "monlamuniouchan2"


@pytest.mark.skipif(
    not (SCRIPTS / "MicrosoftHimalaya.ttf").is_file(),
    reason="scripts/MicrosoftHimalaya.ttf not present",
)
def test_build_gid_map_microsoft_himalaya_shapkyu_yata() -> None:
    """GSUB single + ligature must yield ka+vowel, not vowel alone."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import gid_map as gm

    font = TTFont(str(SCRIPTS / "MicrosoftHimalaya.ttf"), lazy=False)
    m = gm.build_gid_map(font)
    go = font.getGlyphOrder()
    gi_shap = go.index("tibKa_Shapkyu")
    gi_yata = go.index("tibKa_Yata")
    assert m.get(gi_shap) == "\u0f40\u0f74"  # ka + shapkyu (ུ)
    assert m.get(gi_yata) == "\u0f40\u0fb1"  # ka + yata (ྱ)
