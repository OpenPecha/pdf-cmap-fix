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
# A Type0/Identity-H legacy font (TibetanChogyal) whose ToUnicode uses a 2-byte
# codespace -- must still be re-mapped through the table, not mis-matched by the
# GID tier to a sparse same-named lookup.
CHOGYAL_TYPE0 = DATA / "swift-path-chogyal-type0.pdf"

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


@pytest.mark.skipif(
    not CHOGYAL_TYPE0.is_file(), reason="Type0 Chogyal fixture not present"
)
def test_type0_legacy_font_converted_via_existing_tounicode() -> None:
    # Regression: a Type0/Identity-H legacy font with a 2-byte/4-hex ToUnicode
    # codespace used to fall through to the GID tier (sparse garbage match).
    # It must instead be re-mapped through the pytiblegenc table.
    rec = _records_by_font_name(CHOGYAL_TYPE0)["OZVHIQ+TibetanChogyal"]

    assert rec["pdf_font_type"] == "Type0"
    assert rec["db_name_matched"] == "TibetanChogyal"
    assert rec["changed"] > 0
    merged = rec["merged"]
    # Codes are 2-byte (== GID under Identity-H); the existing ToUnicode maps
    # them to Latin, which the table turns into Tibetan.
    assert merged[4] == "\u0f42"  # GA
    assert merged[5] == "\u0f44"  # NGA


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
