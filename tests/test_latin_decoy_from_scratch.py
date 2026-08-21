"""Latin fonts on mixed-script pages must not get a from-scratch Tibetan map.

DJKR / Siddhartha's Intent books set English in Optima and Lucida Grande next
to TibetanClassic (and a tiny TibetanClassicSkt3 stack). Neither Latin face
has a ToUnicode; the from-scratch tier used to identify them as Ededris-vowa
by fuzzy glyph-shape matching and remap MacRoman into stacked-Sanskrit soup.

See ``bug1/BUG.md``. The visible garbage was blamed on Skt3; that companion
only contributes the vaidurya stack ``རྻ``. The broken lines are Optima-Regular
(the romanised translation) and LucidaGrande (the commentary).
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix.gid.extractor import collect_font_merges
from pdf_cmap_fix.glyph_shape_id import _agl_native_mismatch
from pdf_cmap_fix.tounicode_core import apply_font_merges_to_doc

DATA = Path(__file__).resolve().parent / "data"
EXCERPT = DATA / "uttaratantra-djkr-excerpt.pdf"
_needs_excerpt = pytest.mark.skipif(
    not EXCERPT.is_file(), reason="Uttaratantra DJKR excerpt fixture not present"
)


def _records_by_font_name(path: Path = EXCERPT) -> dict[str, dict]:
    doc = fitz.open(str(path))
    try:
        records, _ = collect_font_merges(doc)
    finally:
        doc.close()
    return {r["pdf_font_name"]: r for r in records}


def test_agl_native_mismatch_rejects_scrambled_latin() -> None:
    # Optima-like: AGL names recover the wrong native bytes.
    pairs = [(ord(ch), ch) for ch in "ABCDEFGH"]
    scrambled = {ord(ch): 44 for ch in "ABCDEFGH"}
    assert _agl_native_mismatch(pairs, scrambled) is True
    # Legacy TibetanClassic-like: AGL name *is* the native slot.
    identity = {ord(ch): ord(ch) for ch in "ABCDEFGH"}
    assert _agl_native_mismatch(pairs, identity) is False
    # Tiny Skt subset: too few AGL names to judge.
    assert _agl_native_mismatch([(109, "m"), (52, "four")], {109: 109, 52: 52}) is False
    # Non-AGL names (Chogyal ``MT<byte>``) are ignored.
    mt = [(33, "MT33"), (34, "MT34"), (35, "MT35"), (36, "MT36")]
    assert _agl_native_mismatch(mt, {33: 1, 34: 2, 35: 3, 36: 4}) is False


@_needs_excerpt
def test_latin_optima_and_lucida_are_not_converted() -> None:
    by_name = _records_by_font_name()
    assert "RPGOWK+Optima-Regular" not in by_name
    assert "LGCOSG+LucidaGrande" not in by_name
    assert "HIYHLY+Optima-Italic" not in by_name
    assert "JPIERX+TimesNewRomanPSMT" not in by_name


@_needs_excerpt
def test_tibetan_classic_and_skt3_still_converted() -> None:
    by_name = _records_by_font_name()
    classic = by_name["BTQSWF+TibetanClassic"]
    assert classic["db_name_matched"] == "TibetanClassic"
    assert classic["changed"] > 0
    skt3 = by_name["FTJXXM+TibetanClassicSkt3"]
    assert skt3["db_name_matched"] == "TibetanClassicSkt3"
    # The subset only embeds two glyphs; 'four' is the vaidurya r+ya-ta stack.
    assert skt3["merged"][ord("4")] == "རྻ"


@_needs_excerpt
def test_page_keeps_english_and_recovers_tibetan() -> None:
    doc = fitz.open(str(EXCERPT))
    try:
        records, _ = collect_font_merges(doc)
        apply_font_merges_to_doc(doc, records)
        data = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    reopened = fitz.open(stream=data, filetype="pdf")
    try:
        text = reopened.load_page(0).get_text()
    finally:
        reopened.close()

    # Optima-Regular romanisation -- previously stacked-Sanskrit garbage.
    assert "Progressively, through what is seen" in text
    # LucidaGrande commentary -- previously the same soup.
    assert "not as though that reflection is useless" in text
    # TibetanClassic verse.
    assert "རིམ་གྱིས་དེ་མཐོང" in text
    # TibetanClassicSkt3 vaidurya stack in བཻ་ཌཱུརྻ.
    assert "བཻ་ཌཱུརྻ" in text
