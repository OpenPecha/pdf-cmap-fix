"""Regression: the shape matcher must decline identity-stripped PDFs.

Acrobat Distiller rewrites every embedded face as ``CIDFont+F<n>`` -- the
``/BaseFont`` *and* the embedded ``name`` table -- and renames glyphs to
``glyph00001``. Name and glyf-hash resolution both correctly fail, but the
shape matcher used to accept whatever the distinctiveness vote returned.

On the fixture, a Latin table-of-contents face (periods, digits, a-z) had its
glyphs scatter their nearest matches across eleven unrelated reference
families and still cleared the absolute ``_DISTINCT_VOTE_MIN`` sum, "matching"
Esama. The synthesised ToUnicode then mapped ``0x20`` -> ``ཕྱྭ``, ``.`` ->
``༑`` and ``45`` -> ``༤༥``, i.e. it *corrupted* a span that extracted
perfectly before patching.

See ``_FAMILY_AGREEMENT_MIN`` / ``_MATCH_DIST_MEDIAN_MAX`` in
``pdf_cmap_fix.glyph_shape_id``.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix import glyph_shape_id
from pdf_cmap_fix.gid.extractor import collect_font_merges, patch_doc
from pdf_cmap_fix.tounicode_core import apply_font_merges_to_doc

DATA = Path(__file__).resolve().parent / "data"
FIXTURE = DATA / "distiller-cidfont-fn-excerpt.pdf"

# The table-of-contents leader line on page 1: ASCII periods, ASCII "45".
TOC_ASCII = " .......................................................................... 45 "
# What the ungated shape match produced instead.
TOC_CORRUPT_MARKERS = ("ཕྱྭ", "༑", "༤༥")

pytestmark = pytest.mark.skipif(
    not FIXTURE.is_file() or not glyph_shape_id.available(),
    reason="fixture or numpy/shape-DB unavailable",
)


def _spans(doc: fitz.Document, font_substr: str) -> list[str]:
    out: list[str] = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if font_substr in span["font"]:
                        out.append(span["text"])
    return out


def test_no_font_is_matched() -> None:
    """Every face is identity-stripped, so nothing should be patched."""
    doc = fitz.open(str(FIXTURE))
    try:
        records, stats = collect_font_merges(doc)
    finally:
        doc.close()
    assert stats["patched"] == 0
    assert stats["upgrades"] == 0
    assert not [r for r in records if r.get("changed")]


def test_toc_span_survives_patching() -> None:
    """A span that extracts correctly before patching must be unchanged after."""
    doc = fitz.open(str(FIXTURE))
    try:
        before = _spans(doc, "CIDFont+F9")
        assert TOC_ASCII in before, "fixture no longer contains the ASCII TOC span"

        records, _ = collect_font_merges(doc)
        apply_font_merges_to_doc(doc, records)
        data = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    reopened = fitz.open(stream=data, filetype="pdf")
    try:
        after = _spans(reopened, "CIDFont+F9")
        text = "".join(page.get_text() for page in reopened)
    finally:
        reopened.close()

    assert TOC_ASCII in after
    for marker in TOC_CORRUPT_MARKERS:
        assert marker not in text, f"fabricated {marker!r} reintroduced"


def test_patch_does_not_inflate_text_layer() -> None:
    """Mapping a space to a 3-codepoint stack used to grow the text layer."""
    doc = fitz.open(str(FIXTURE))
    try:
        before = len("".join(page.get_text() for page in doc))
        patch_doc(doc)
        after = len("".join(page.get_text() for page in doc))
    finally:
        doc.close()
    assert after == before


def test_shape_matcher_rejects_the_toc_face() -> None:
    """Unit-level: the consensus gate, not luck, is what rejects it.

    Relaxing both consensus thresholds must bring the false match back --
    otherwise this file would keep passing for an unrelated reason.
    """
    doc = fitz.open(str(FIXTURE))
    try:
        _records, gated = collect_font_merges(doc)
    finally:
        doc.close()

    saved = (
        glyph_shape_id._FAMILY_AGREEMENT_MIN,
        glyph_shape_id._MATCH_DIST_MEDIAN_MAX,
    )
    glyph_shape_id._FAMILY_AGREEMENT_MIN = 0.0
    glyph_shape_id._MATCH_DIST_MEDIAN_MAX = float("inf")
    doc = fitz.open(str(FIXTURE))
    try:
        _records, ungated = collect_font_merges(doc)
    finally:
        doc.close()
        (
            glyph_shape_id._FAMILY_AGREEMENT_MIN,
            glyph_shape_id._MATCH_DIST_MEDIAN_MAX,
        ) = saved

    assert ungated["patched"] > 0
    assert gated["patched"] == 0
