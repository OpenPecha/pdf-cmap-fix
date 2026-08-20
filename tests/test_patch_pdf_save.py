"""patch_pdf must not use PyMuPDF garbage levels that merge duplicate objects.

garbage>=3 walks every xref to merge duplicates (level 4 also compares stream
bytes). On a 300-page tagged PDF with tens of thousands of objects that is
~100s natively and hangs the in-browser Pyodide worker, for a ~1% size win.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from pdf_cmap_fix.gid.extractor import patch_pdf
from pdf_cmap_fix.tounicode_core import _PDF_SAVE_KW


def test_save_kwargs_stay_below_duplicate_merge() -> None:
    assert _PDF_SAVE_KW.get("garbage", 0) <= 2
    assert _PDF_SAVE_KW.get("deflate") is True


def test_patch_pdf_does_not_use_expensive_garbage(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(src)
    doc.close()

    captured: dict = {}
    real = fitz.Document.tobytes

    def spy(self, *args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return real(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Document, "tobytes", spy)

    patch_pdf(src, output_path=tmp_path / "out.pdf", write_file=True)

    garbage = captured["kwargs"].get("garbage", 0)
    assert garbage <= 2, (
        f"tobytes(garbage={garbage}) merges duplicate objects and is "
        "minutes-slow on large tagged PDFs"
    )
    assert captured["kwargs"].get("deflate") is True
