"""Unit tests for ``pdf_cmap_fix.pdf_font_encoding.parse_pdf_encoding``.

We use ``unittest.mock`` to fake the fitz.Document.xref_get_key /
xref_object surface so the tests run without a real PDF on disk.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pdf_cmap_fix.pdf_font_encoding import (
    WIN_ANSI_ENCODING,
    _base_encoding_table,
    _parse_differences,
    parse_pdf_encoding,
)


def _make_doc(encoding_key, encoding_obj_text=None, font_obj_text="<<>>"):
    """Build a mock fitz.Document that returns the given /Encoding key
    and the corresponding xref_object text."""
    doc = MagicMock()
    # font xref 1, encoding xref 2
    def _xref_object(xref):
        if xref == 1:
            return font_obj_text
        if xref == 2:
            return encoding_obj_text or "<<>>"
        return None
    def _xref_get_key(xref, key):
        if xref == 1 and key == "Encoding":
            return encoding_key
        return None
    doc.xref_object.side_effect = _xref_object
    doc.xref_get_key.side_effect = _xref_get_key
    return doc


def test_win_ansi_encoding_table_is_complete_for_letters() -> None:
    assert WIN_ANSI_ENCODING[65] == "A"
    assert WIN_ANSI_ENCODING[97] == "a"
    assert WIN_ANSI_ENCODING[32] == "space"
    assert WIN_ANSI_ENCODING[200] == "Egrave"


def test_base_encoding_table_recognises_predefined_names() -> None:
    assert _base_encoding_table("WinAnsiEncoding")[65] == "A"
    assert _base_encoding_table("/WinAnsiEncoding")[65] == "A"
    assert _base_encoding_table("StandardEncoding")[65] == "A"
    assert _base_encoding_table("MacRomanEncoding")[65] == "A"
    # Unknown name -> empty table.
    assert _base_encoding_table("MumbleEncoding") == [""] * 256
    # MacExpert is treated as empty (rare ornament-only encoding).
    assert _base_encoding_table("MacExpertEncoding") == [""] * 256


def test_parse_differences_simple_run() -> None:
    table = ["base"] * 256
    out = _parse_differences("1 /uniE1D4 /uniE170 /uniE173", table)
    assert out[0] == "base"  # untouched
    assert out[1] == "uniE1D4"
    assert out[2] == "uniE170"
    assert out[3] == "uniE173"
    assert out[4] == "base"


def test_parse_differences_jumps_to_explicit_codes() -> None:
    table = ["b"] * 256
    out = _parse_differences("1 /A /B 127 /Y 200 /Z", table)
    assert out[1] == "A"
    assert out[2] == "B"
    assert out[127] == "Y"
    assert out[200] == "Z"
    assert out[3] == "b"  # gap is preserved
    assert out[128] == "b"


def test_parse_differences_handles_dotted_names() -> None:
    table = ["b"] * 256
    out = _parse_differences("5 /E14D.tsheg /uniE12C", table)
    assert out[5] == "E14D.tsheg"
    assert out[6] == "uniE12C"


def test_parse_pdf_encoding_returns_empty_when_no_encoding_key() -> None:
    doc = _make_doc(encoding_key=None)
    assert parse_pdf_encoding(doc, 1) == {}


def test_parse_pdf_encoding_name_form() -> None:
    """/Encoding /WinAnsiEncoding (direct name reference)."""
    doc = _make_doc(encoding_key=("name", "WinAnsiEncoding"))
    enc = parse_pdf_encoding(doc, 1)
    assert enc[65] == "A"
    assert enc[97] == "a"
    assert enc[200] == "Egrave"


def test_parse_pdf_encoding_indirect_dict_with_differences() -> None:
    """/Encoding 2 0 R, where xref 2 is an encoding dict."""
    enc_obj = """<<
        /Type /Encoding
        /BaseEncoding /WinAnsiEncoding
        /Differences [
            1 /uniE1D4 /uniE170 /uniE173
            13 /E14D.tsheg
            127 /uniE14E
        ]
    >>"""
    doc = _make_doc(
        encoding_key=("xref", "2 0 R"),
        encoding_obj_text=enc_obj,
    )
    enc = parse_pdf_encoding(doc, 1)
    # /Differences overrides
    assert enc[1] == "uniE1D4"
    assert enc[2] == "uniE170"
    assert enc[3] == "uniE173"
    assert enc[13] == "E14D.tsheg"
    assert enc[127] == "uniE14E"
    # Base encoding still applies for slots not overridden
    assert enc[65] == "A"
    assert enc[32] == "space"


def test_parse_pdf_encoding_inline_dict() -> None:
    """/Encoding << ... >>  (inline dict)."""
    enc_text = """<<
        /BaseEncoding /StandardEncoding
        /Differences [ 100 /asciitilde 110 /backslash ]
    >>"""
    doc = _make_doc(encoding_key=("dict", enc_text))
    enc = parse_pdf_encoding(doc, 1)
    assert enc[100] == "asciitilde"
    assert enc[110] == "backslash"
    # StandardEncoding base entries
    assert enc[65] == "A"


def test_parse_pdf_encoding_dict_without_base_uses_standard() -> None:
    enc_text = "<< /Differences [ 1 /foo /bar ] >>"
    doc = _make_doc(encoding_key=("dict", enc_text))
    enc = parse_pdf_encoding(doc, 1)
    assert enc[1] == "foo"
    assert enc[2] == "bar"
    # StandardEncoding's 'A' should still be present.
    assert enc[65] == "A"


def test_parse_pdf_encoding_ignores_dot_notdef() -> None:
    """``/.notdef`` is a glyph name we want to keep as-is."""
    enc_text = "<< /BaseEncoding /WinAnsiEncoding /Differences [ 173 /.notdef ] >>"
    doc = _make_doc(encoding_key=("dict", enc_text))
    enc = parse_pdf_encoding(doc, 1)
    assert enc[173] == ".notdef"
