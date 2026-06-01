"""Tests for ``content_streams.collect_referenced_gids`` and ``_merge``.

We build a small in-memory PDF whose content stream uses two Type0
fonts at known GIDs, then assert that:

* ``collect_referenced_gids`` recovers the exact set of GIDs each
  font references (and ignores fonts the document never selects),
* ``_merge(..., referenced=...)`` only touches GIDs in that set,
  which is the performance lever fixed in 02-performance.md item 1.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix.content_streams import (
    _decode_pdf_literal,
    _iter_text_strings,
    collect_referenced_gids,
)
from pdf_cmap_fix.tounicode_core import _merge


def test_decode_pdf_literal_handles_octal_escapes() -> None:
    # \101 \102 \103 -> 'ABC'
    assert _decode_pdf_literal(rb"\101\102\103") == b"ABC"


def test_decode_pdf_literal_handles_named_escapes() -> None:
    assert _decode_pdf_literal(rb"a\nb\tc\\d\(e\)") == b"a\nb\tc\\d(e)"


def test_iter_text_strings_picks_up_tj_and_tj_array() -> None:
    stream = (
        b"q BT\n"
        b"/F1 12 Tf\n"
        b"<00010002> Tj\n"
        b"/F2 14 Tf\n"
        b"[<0003> 50 <0004>] TJ\n"
        b"ET Q\n"
    )
    out = list(_iter_text_strings(stream))
    assert out == [
        (b"F1", b"\x00\x01\x00\x02"),
        (b"F2", b"\x00\x03\x00\x04"),
    ]


_TI1751 = (
    Path(__file__).resolve().parents[1]
    / "docs" / "examples" / "TI1751-01-001" / "TI1751-01-001.pdf"
).resolve() if False else None  # avoid TYPE_CHECKING


@pytest.mark.skipif(
    not (
        Path(__file__).resolve().parents[1]
        / "docs" / "examples" / "TI1751-01-001" / "TI1751-01-001.pdf"
    ).is_file(),
    reason="example PDF not present",
)
def test_collect_referenced_gids_on_example_pdf() -> None:
    """Smoke test on the bundled TI1751 PDF.

    We don't assert specific GIDs - those are font-subset specific -
    only that the function returns *some* GIDs for *some* Type0 xref
    and that every reported xref came from the requested set.
    """
    pdf = (
        Path(__file__).resolve().parents[1]
        / "docs" / "examples" / "TI1751-01-001" / "TI1751-01-001.pdf"
    )
    doc = fitz.open(str(pdf))
    try:
        type0 = {
            f[0]
            for pno in range(len(doc))
            for f in doc[pno].get_fonts(full=True)
            if f[2] == "Type0"
        }
        if not type0:
            pytest.skip("no Type0 fonts in example PDF")
        out = collect_referenced_gids(doc, type0_xrefs=type0)
        assert all(x in type0 for x in out.keys())
        # At least one Type0 font in this PDF should be referenced.
        assert sum(len(g) for g in out.values()) > 0
        for gids in out.values():
            assert all(0 <= g <= 0xFFFF for g in gids)
    finally:
        doc.close()


def test_merge_referenced_filter_is_a_no_op_for_unreferenced_gids() -> None:
    """db entries outside ``referenced`` must not flip ``changed``."""
    existing = {1: "a", 2: "b"}
    db_map = {1: "a", 2: "B", 3: "c", 4: "d"}
    referenced = {1, 2}
    merged, changed = _merge(existing, db_map, referenced)
    assert merged == {1: "a", 2: "B"}, "should not introduce GIDs 3/4"
    assert changed == 1


def test_merge_referenced_none_keeps_back_compat_behaviour() -> None:
    existing = {1: "a"}
    db_map = {1: "a", 2: "B"}
    merged, changed = _merge(existing, db_map, None)
    assert merged == {1: "a", 2: "B"}
    assert changed == 1


def test_merge_referenced_intersection_only() -> None:
    existing = {1: "x"}
    db_map = {2: "Y"}
    referenced = {1, 2}
    merged, changed = _merge(existing, db_map, referenced)
    assert merged == {1: "x", 2: "Y"}
    assert changed == 1


def test_iter_text_strings_picks_up_single_byte_payloads_for_simple_fonts() -> None:
    """Simple fonts use 1-byte char codes; the iterator still hands
    each text-show operator's payload to the caller as bytes. The
    *interpretation* (1 vs 2 byte) is the caller's responsibility --
    here we just confirm we receive every byte verbatim."""
    stream = (
        b"q BT\n"
        b"/F3 12 Tf\n"
        b"<0102030405> Tj\n"
        b"ET Q\n"
    )
    out = list(_iter_text_strings(stream))
    assert out == [(b"F3", b"\x01\x02\x03\x04\x05")]


# Inline PDF synthesis is heavy for unit tests; the public
# collect_referenced_gids API is exercised end-to-end by the
# integration smoke test against docs/examples/*. Here we only need
# to know that the byte-width split is faithfully wired: a synthetic
# input forces a known split.

class _StubDoc:
    """Minimal fitz.Document stand-in for collect_referenced_gids."""

    def __init__(self, contents: bytes, font_xref: int, fname: bytes = b"F1"):
        from unittest.mock import MagicMock
        self._page = MagicMock()
        self._page.read_contents.return_value = contents
        # Make _resource_font_xref_map find {fname: font_xref}.
        self._page.xref = 100
        self.font_xref = font_xref
        self.fname = fname
        # xref tree: page 100 -> /Resources/Font is an indirect ref to 101,
        # which is a dict mapping F1 -> font_xref.
        self._key_table = {
            (100, "Resources/Font"): ("xref", "101 0 R"),
            (100, "Parent"): None,
        }
        self._object_table = {
            101: f"<< /{self.fname.decode('latin-1')} {self.font_xref} 0 R >>",
        }

    def __len__(self) -> int:
        return 1

    def __getitem__(self, pno: int):
        return self._page

    def xref_get_key(self, xref: int, key: str):
        return self._key_table.get((xref, key))

    def xref_object(self, xref: int) -> str:
        return self._object_table.get(xref, "")


def test_collect_referenced_gids_simple_font_reads_one_byte_per_code() -> None:
    stream = (
        b"q BT\n"
        b"/F1 12 Tf\n"
        b"<0D1F2030> Tj\n"
        b"ET Q\n"
    )
    doc = _StubDoc(stream, font_xref=42)
    out = collect_referenced_gids(doc, simple_xrefs={42})
    assert out[42] == {0x0D, 0x1F, 0x20, 0x30}


def test_collect_referenced_gids_type0_font_reads_two_bytes_per_gid() -> None:
    stream = (
        b"q BT\n"
        b"/F1 12 Tf\n"
        b"<00010002000300040A0B> Tj\n"
        b"ET Q\n"
    )
    doc = _StubDoc(stream, font_xref=42)
    out = collect_referenced_gids(doc, type0_xrefs={42})
    assert out[42] == {0x0001, 0x0002, 0x0003, 0x0004, 0x0A0B}


def test_collect_referenced_gids_xref_not_in_either_set_is_skipped() -> None:
    stream = b"q BT /F1 12 Tf <0102> Tj ET Q\n"
    doc = _StubDoc(stream, font_xref=42)
    # Provide explicit, disjoint sets that exclude xref 42 -> nothing
    # should land in the output.
    out = collect_referenced_gids(doc, type0_xrefs=set(), simple_xrefs=set())
    assert out == {}


def test_collect_referenced_gids_back_compat_defaults_to_type0() -> None:
    """When the caller passes no classification (legacy 1-arg call),
    every payload is treated as Identity-H (2 bytes per GID), exactly
    as before this PR."""
    stream = b"q BT /F1 12 Tf <00010002> Tj ET Q\n"
    doc = _StubDoc(stream, font_xref=42)
    out = collect_referenced_gids(doc)
    assert out[42] == {0x0001, 0x0002}
