"""Shape-based identification of obfuscated-name legacy Tibetan CFF fonts.

When the PostScript name is fully obfuscated AND the outlines are CFF/Type1 (so
the glyf-only hash path cannot read them), the font is recovered by matching
glyph *shapes* against the vendored reference DB (``glyph_shape_id``). The
fixture is the Gen-prefixed Chogyal excerpt with its font names scrubbed at
runtime, so only shape matching can resolve it.

The distinctiveness gate must also REJECT non-Tibetan faces (a Latin period has
the same shape as a Tibetan tsheg): that is covered by the existing decoy tests
in ``test_pytiblegenc_simple_fonts.py`` (Times/NewBaskerville stay unconverted)
and by ``test_latin_optima_and_lucida_are_not_converted`` (Optima / Lucida Grande).
TrueType fonts are identified by exact outline hash, not this bitmap matcher.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix import glyph_shape_id
from pdf_cmap_fix.gid.extractor import collect_font_merges

DATA = Path(__file__).resolve().parent / "data"
FIXTURE = DATA / "mipham-namthar-gen-chogyal-excerpt.pdf"

pytestmark = pytest.mark.skipif(
    not FIXTURE.is_file() or not glyph_shape_id.available(),
    reason="fixture or numpy/shape-DB unavailable",
)


def _name_scrubbed_doc() -> fitz.Document:
    """Open the fixture with every embedded Tibetan font name replaced by an
    opaque subset tag, so name + glyf-hash resolution both fail."""
    doc = fitz.open(str(FIXTURE))
    junk = (f"AAAAA{c}+Obf{i:04d}" for i, c in enumerate("ABCDEFGHIJ"))
    for x in range(1, doc.xref_length()):
        bf = doc.xref_get_key(x, "BaseFont")
        if bf and "Tibetan" in bf[1]:
            doc.xref_set_key(x, "BaseFont", "/" + next(junk))
    # round-trip so the edited names are what the extractor reads
    return fitz.open(stream=doc.tobytes(), filetype="pdf")


def test_obfuscated_cff_identified_by_shape() -> None:
    doc = _name_scrubbed_doc()
    try:
        records, _ = collect_font_merges(doc)
    finally:
        doc.close()
    by_match = {r["db_name_matched"] for r in records if r["changed"] > 0}
    # The body face and at least one Sanskrit subface recovered purely by shape.
    assert "TibetanChogyal" in by_match
    assert any(n and n.startswith("TibetanChogyalSkt") for n in by_match)
    for r in records:
        if r["changed"]:
            assert r["to_unicode_xref"] is None  # synthesised from scratch


def test_obfuscated_cff_extracts_tibetan_after_apply() -> None:
    from pdf_cmap_fix.tounicode_core import apply_font_merges_to_doc

    doc = _name_scrubbed_doc()
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
    # Same correct Tibetan as the name-based path, recovered shape-only.
    assert "སྔོན་གླེང" in text
    assert "སེངྒེ" in text   # the cross-family-confusable subfont glyph
    assert sum(1 for ch in text if "ༀ" <= ch <= "࿿") > 500


def test_unit_recover_matches_reference() -> None:
    # Direct matcher unit test: identify_and_recover on a known glyph set.
    import io
    from pdf_cmap_fix.tounicode_core import _load_pdf_embedded_font
    from pdf_cmap_fix.pdf_font_encoding import parse_pdf_encoding

    doc = fitz.open(str(FIXTURE))
    try:
        # main Tibetan font xref
        xref = next(
            x for x in range(1, doc.xref_length())
            if (doc.xref_get_key(x, "BaseFont") or (None, ""))[1].endswith("TibetanChogyal")
        )
        buf = doc.extract_font(xref)[3]
        tt = _load_pdf_embedded_font(bytes(buf))
        upem = tt["head"].unitsPerEm if "head" in tt else 1000
        if "CFF " in tt:
            fm = tt["CFF "].cff[tt["CFF "].cff.fontNames[0]].rawDict.get("FontMatrix")
            if fm and fm[0]:
                upem = round(1 / fm[0])
        pairs = list(parse_pdf_encoding(doc, xref).items())
        font, mapping = glyph_shape_id.identify_and_recover(tt.getGlyphSet(), upem, pairs)
    finally:
        doc.close()
    assert font == "TibetanChogyal"
    assert len(mapping) > 50
