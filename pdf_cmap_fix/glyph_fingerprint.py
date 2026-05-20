"""
Stable outline fingerprints for TrueType / OpenType glyphs (fontTools).

Used for tier-3 ``font_lookup_gshape`` JSON keys and by
:mod:`pdf_cmap_fix.tounicode_core` when merging with a gshape lookup directory.
Uses ``HashPointPen`` with ``RoundingPointPen`` so composite transform components
match fontTools TTF vs UFO guidance (F2Dot14-style rounding).
"""
from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Optional

from fontTools.misc.fixedTools import floatToFixedToFloat
from fontTools.pens.hashPointPen import HashPointPen
from fontTools.pens.roundingPen import RoundingPointPen

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont


def glyph_advance_width(font: "TTFont", gname: str) -> int:
    if "hmtx" in font and gname in font["hmtx"].metrics:
        return int(font["hmtx"].metrics[gname][0])
    return 0


def fingerprint_glyph(font: "TTFont", gname: str) -> Optional[str]:
    """Return HashPointPen hash string, or ``None`` if the glyph cannot be drawn."""
    glyph_set = font.getGlyphSet()
    if gname not in glyph_set:
        return None
    glyph = glyph_set[gname]
    width = glyph_advance_width(font, gname)
    hpen = HashPointPen(width, glyph_set)
    rpen = RoundingPointPen(
        hpen,
        transformRoundFunc=partial(floatToFixedToFloat, precisionBits=14),
    )
    try:
        glyph.drawPoints(rpen)
    except Exception:
        return None
    return hpen.hash
