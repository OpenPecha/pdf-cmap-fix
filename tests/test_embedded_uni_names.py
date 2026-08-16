"""Quartz / Affinity TrueType subsets with no /Encoding and uni* glyph names.

Affinity Publisher (macOS Quartz) embeds per-page symbolic TrueType subsets
of Unicode Tibetan faces (here DodrupchenChayigUni). The /Font dict has no
/Encoding; the subset cmap keys *are* the 1-byte char codes; glyph names are
``uniXXXX`` / ``uniXXXXYYYY``. The PDF ToUnicode maps stacked syllables to
ASCII (``'``, ``,``, ``0``) while leaving single-codepoint glyphs correct.

The extractor must read the built-in cmap and decode those names -- a font
lookup cannot help (the face is not in the shipped DB, and tier-1 GID maps
do not apply to simple fonts).
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix.gid.extractor import collect_font_merges, extract_pdf_text
from pdf_cmap_fix.pdf_font_encoding import (
    parse_embedded_ttf_encoding,
    parse_pdf_encoding,
    resolve_simple_encoding,
)
from pdf_cmap_fix.tounicode_core import (
    _tounicode_from_embedded_uni_names,
    _unicode_from_uni_glyph_name,
)

DATA = Path(__file__).resolve().parent / "data"
EXCERPT = DATA / "lopon-thekchog-excerpt.pdf"

pytestmark = pytest.mark.skipif(
    not EXCERPT.is_file(), reason="Lopon Thekchog excerpt fixture not present"
)


def _dodrupchen_xref(doc: fitz.Document) -> int:
    for f in doc[0].get_fonts(full=True):
        if "Dodrupchen" in f[3]:
            return f[0]
    raise AssertionError("DodrupchenChayigUni font not found in excerpt")


def test_unicode_from_uni_glyph_name_decodes_stacks() -> None:
    assert _unicode_from_uni_glyph_name("uni0F42") == "ག"
    assert _unicode_from_uni_glyph_name("uni0F400F74") == "ཀུ"
    assert _unicode_from_uni_glyph_name("uni0F660FA8") == "སྨ"
    assert _unicode_from_uni_glyph_name("uni0F040F05") == "༄༅"
    assert _unicode_from_uni_glyph_name("comma") is None
    assert _unicode_from_uni_glyph_name("uniF001") is None


def test_excerpt_has_no_pdf_encoding_but_embedded_cmap() -> None:
    doc = fitz.open(str(EXCERPT))
    try:
        xref = _dodrupchen_xref(doc)
        assert parse_pdf_encoding(doc, xref) == {}
        enc = parse_embedded_ttf_encoding(doc, xref)
        assert enc[0x27] == "uni0F400F74"
        assert enc[0x2C] == "uni0F660FA8"
        assert enc[0x30] == "uni0F4A0F71"
        assert resolve_simple_encoding(doc, xref) == enc
    finally:
        doc.close()


def test_embedded_uni_names_upgrade_ascii_tounicode() -> None:
    doc = fitz.open(str(EXCERPT))
    try:
        xref = _dodrupchen_xref(doc)
        existing = {0x27: "'", 0x2C: ",", 0x21: "ག"}
        db_map = _tounicode_from_embedded_uni_names(doc, xref, existing)
        assert db_map is not None
        assert db_map[0x27] == "ཀུ"
        assert db_map[0x2C] == "སྨ"
        assert db_map[0x21] == "ག"
    finally:
        doc.close()


def test_collect_font_merges_patches_dodrupchen_via_uni_names() -> None:
    doc = fitz.open(str(EXCERPT))
    try:
        records, stats = collect_font_merges(doc, verbose=False)
    finally:
        doc.close()

    rec = next(r for r in records if "Dodrupchen" in r["pdf_font_name"])
    assert rec["db_name_matched"] == "embedded-uni-names"
    assert rec["changed"] > 0
    assert rec["merged"][0x27] == "ཀུ"
    assert rec["merged"][0x2C] == "སྨ"
    assert rec["merged"][0x30] == "ཊཱ"
    assert rec["merged"][0x31] == "ཀྐ"
    assert rec["merged"][0x32] == "ཞུ"
    assert rec["merged"][0x25] == "༄༅"
    assert stats["patched"] >= 1


def test_extract_pdf_text_recovers_title() -> None:
    result = extract_pdf_text(EXCERPT, write_files=False, verbose=False)
    assert "ཀུན་བཟང་སྨོན་ལམ་ཊཱིཀྐ་བཞུགས་སོ།" in result["patched"]
    assert "།'ན་བཟང་,ོན་ལམ་" in result["raw"]
    assert "།'ན་བཟང་,ོན་ལམ་" not in result["patched"]
