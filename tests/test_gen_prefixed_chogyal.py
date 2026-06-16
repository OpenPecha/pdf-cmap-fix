"""Regression test: ``Gen_``-prefixed Tibetan Chogyal CFF/Type1 subsets.

Real-world case (Mipham namthar, Dilgo Khyentse ed.) that reached production via
the Easy Tibetan Copy web app reporting "0 fonts fixed". The PDF embeds the
Tibetan Chogyal family as Type1/CFF subsets with:

  * a wrapper PostScript name ``Gen_TibetanChogyal`` / ``Gen.TibetanChogyalSkt1``
    (the ``Gen_``/``Gen.`` prefix kept the pytiblegenc name lookup from
    resolving), and
  * glyph names ``MT<byte>`` -- the font's native single-byte code, NOT an Adobe
    Glyph List name, so the from-scratch /Encoding route produced nothing, and
  * no ToUnicode and a CFF outline (so the glyf-only outline fallback bailed).

Fix: ``table_for`` peels the wrapper prefix, and the from-scratch Encoding route
recovers the byte from an ``MT<byte>`` glyph name before converting it through
the per-font table. Fixture is page 3 of the source PDF (first body-text page).
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix import pytiblegenc_tables as ptg
from pdf_cmap_fix.gid.extractor import collect_font_merges

DATA = Path(__file__).resolve().parent / "data"
FIXTURE = DATA / "mipham-namthar-gen-chogyal-excerpt.pdf"

pytestmark = pytest.mark.skipif(
    not FIXTURE.is_file(), reason="Gen-Chogyal excerpt fixture not present"
)


def _records_by_font_name() -> dict[str, dict]:
    doc = fitz.open(str(FIXTURE))
    try:
        records, _ = collect_font_merges(doc)
    finally:
        doc.close()
    return {r["pdf_font_name"]: r for r in records}


def test_table_for_peels_wrapper_prefix() -> None:
    # The Gen_/Gen. wrapper prefix must not block the per-font table lookup.
    assert ptg.table_for("Gen_TibetanChogyal")[0] == "TibetanChogyal"
    assert ptg.table_for("Gen.TibetanChogyalSkt1")[0] == "TibetanChogyalSkt1"
    assert ptg.table_for("GJGOOJ+Gen_TibetanChogyal")[0] == "TibetanChogyal"
    # ...but only when the peeled remainder is itself a real table (no guessing).
    assert ptg.table_for("Gen_NotARealTibetanFont")[0] is None
    assert ptg.table_for("Helvetica")[0] is None


def test_gen_prefixed_chogyal_rebuilt_from_mt_glyph_names() -> None:
    rec = _records_by_font_name()["GJGOOJ+Gen_TibetanChogyal"]

    assert rec["pdf_font_type"] == "Type1"
    assert rec["db_name_matched"] == "TibetanChogyal"   # prefix peeled
    assert rec["to_unicode_xref"] is None               # synthesised from scratch
    assert rec["changed"] > 0

    values = set(rec["merged"].values())
    # MT<byte> glyph names recovered to bytes, converted via the Chogyal table.
    assert "ག" in values        # GA
    assert "ས" in values        # SA
    assert "༄༅" in values       # yig-mgo head ornament


def test_gen_prefixed_page_extracts_tibetan_after_apply() -> None:
    from pdf_cmap_fix.tounicode_core import apply_font_merges_to_doc

    doc = fitz.open(str(FIXTURE))
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

    # "sngon gleng" (preface) opens the page; before the fix it yielded zero
    # Tibetan code points ("0 fonts fixed").
    assert "སྔོན་གླེང" in text
    assert sum(1 for ch in text if "ༀ" <= ch <= "࿿") > 500
