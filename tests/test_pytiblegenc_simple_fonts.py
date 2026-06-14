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

DATA = Path(__file__).resolve().parent / "data"
EXCERPT = DATA / "jkw-kabab-excerpt.pdf"
# Same page with the Dedris-a font's BaseFont, FontName and embedded name table
# scrubbed to an obfuscated name, so only outline identification can recover it.
OBFUSCATED = DATA / "jkw-kabab-obfuscated.pdf"

pytestmark = pytest.mark.skipif(
    not EXCERPT.is_file(), reason="JKW-KABAB excerpt fixture not present"
)


def _records_by_font_name(path: Path = EXCERPT) -> dict[str, dict]:
    doc = fitz.open(str(path))
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


@pytest.mark.skipif(
    not OBFUSCATED.is_file(), reason="obfuscated-name fixture not present"
)
def test_obfuscated_font_identified_via_glyph_outlines() -> None:
    # The font name is fully obfuscated (no table resolves by name), so this
    # can only match by hashing the embedded glyph outlines against glyph_db.csv.
    rec = _records_by_font_name(OBFUSCATED)["ZQXJVK+Obf00001"]

    assert rec["db_name_matched"] == "Ededris-a"
    assert rec["changed"] > 0
    merged = rec["merged"]
    assert merged[33] == "\u0f40"          # KA
    assert merged[34] == "\u0f42"          # GA
    assert merged[40] == "\u0f62\u0fab"    # RA + subjoined DZA


def test_glyph_lookup_recovers_char_missing_from_direct_table() -> None:
    # Ported pytiblegenc glyph-lookup fallback: 'Ededris-d1' has no entry for the
    # space slot in its own conversion table, but that glyph's outline matches a
    # sibling font where it is a subjoined-U vowel, so it is recovered.
    from pdf_cmap_fix import pytiblegenc_tables as ptg

    assert " " not in ptg._base().get("Ededris-d1", {})
    assert ptg.convert_char("Ededris-d1", " ") == "\u0f74"
    # A direct table hit still resolves without the fallback.
    assert ptg.convert_char("Ededris-a", "!") == "\u0f40"


def test_identify_candidates_resolves_subset_to_source_font() -> None:
    import io

    from fontTools.ttLib import TTFont

    from pdf_cmap_fix import pytiblegenc_tables as ptg
    from pdf_cmap_fix.glyph_outline_id import identify_candidates

    doc = fitz.open(str(EXCERPT))
    try:
        xref = next(
            f[0]
            for f in doc[0].get_fonts(full=True)
            if f[3].endswith("+Dedris-a")
        )
        ttfont = TTFont(io.BytesIO(bytes(doc.extract_font(xref)[3])), lazy=False)
    finally:
        doc.close()

    candidates = identify_candidates(ttfont)
    # Tightest (smallest superset) match first.
    assert candidates[0] == "Dedris-a"
    name, table = ptg.table_for_candidates(candidates)
    assert name == "Ededris-a"
    assert table is not None
