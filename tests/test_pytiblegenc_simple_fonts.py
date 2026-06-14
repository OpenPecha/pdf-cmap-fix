"""Regression tests for pytiblegenc-table conversion of legacy simple fonts.

The fixture is page 1 of ``JKW-KABAB-Volume-01.pdf``, which embeds several
legacy non-Unicode Tibetan fonts (``Dedris-*``, i.e. Ededris) as symbolic
simple TrueType subsets plus a ``TimesNewRomanPSMT`` decoy.

These fonts have no usable GSUB/cmap, so the GSUB-derived lookups can't help.
Instead each code's *existing* (wrong, Latin-ish) ToUnicode character is
re-mapped through pytiblegenc's curated per-font table. ``Dedris-a`` resolves to
the ``Ededris-a`` table via pytiblegenc's ``Dedris -> Ededris`` alias.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix.gid.extractor import collect_font_merges

EXCERPT = Path(__file__).resolve().parent / "data" / "jkw-kabab-excerpt.pdf"

pytestmark = pytest.mark.skipif(
    not EXCERPT.is_file(), reason="JKW-KABAB excerpt fixture not present"
)


def _records_by_font_name() -> dict[str, dict]:
    doc = fitz.open(str(EXCERPT))
    try:
        records, _ = collect_font_merges(doc)
    finally:
        doc.close()
    return {r["pdf_font_name"]: r for r in records}


def test_dedris_a_maps_codes_to_tibetan_via_existing_tounicode() -> None:
    rec = _records_by_font_name()["KSWSGG+Dedris-a"]

    # Resolved through the Dedris -> Ededris alias.
    assert rec["db_name_matched"] == "Ededris-a"
    assert rec["changed"] > 0

    merged = rec["merged"]
    # The mapping keys on the *existing* ToUnicode char, not the raw byte:
    # code 34's existing '$' -> table[36] = GA (raw byte 34 has no table row).
    assert merged[33] == "\u0f40"          # KA
    assert merged[34] == "\u0f42"          # GA
    assert merged[40] == "\u0f62\u0fab"    # RA + subjoined DZA (stack)
    assert merged[48] == "\u0f56\u0fb1"    # BA + subjoined YA (stack)


def test_simple_dedris_vowa_is_converted() -> None:
    rec = _records_by_font_name()["PLHYWC+Dedris-vowa"]
    assert rec["db_name_matched"] == "Ededris-vowa"
    assert rec["changed"] > 0
    # head mark (yig mgo) -- the leading ornament of the page
    assert rec["merged"][34] == "\u0f04\u0f05"


def test_times_new_roman_is_not_converted() -> None:
    rec = _records_by_font_name()["JJGQVW+TimesNewRomanPSMT"]
    assert rec["db_name_matched"] is None
    assert rec["db_key_matched"] is None
    assert rec["changed"] == 0
