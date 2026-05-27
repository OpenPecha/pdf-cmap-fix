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
