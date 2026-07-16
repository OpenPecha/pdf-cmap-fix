"""Regression tests for Word ActualText<FEFFFFFD> sentinel stripping.

Bug history: the original regex used unbounded ``<<.*?`` / ``(.*?)`` with
DOTALL. On InDesign PDFs (many legitimate per-stack ActualText spans plus
occasional FEFFFFFD sentinels) it matched from the *first* /Span on the
page to a distant sentinel, deleting every operator in between - silently
destroying rendered page content (observed: Druklugs-v156.pdf, 37/246
pages, ~11 KB / 13 lines lost on page 6).
"""

from pdf_cmap_fix.tounicode_core import (
    _strip_word_actualtext_sentinels_in_stream,
    _text_show_ops_preserved,
)

# Word-style: sentinel span is self-contained -> wrapper removed, Tj kept.
WORD_STYLE = (
    b"BT\n/C2_0 1 Tf\n"
    b"/Span<</ActualText<FEFFFFFD>>> BDC \n<0384>Tj\nEMC \n"
    b"<0100>Tj\nET"
)

# InDesign-style: legitimate ActualText spans surround one sentinel.
# The old regex matched from the FIRST /Span to the sentinel's EMC and
# deleted the legitimate span and the unwrapped Tj between them.
INDESIGN_STYLE = (
    b"BT\n/C2_0 1 Tf\n24 0 0 24 19.8 535.7 Tm\n"
    b"<0149>Tj\n"
    b"/Span<</ActualText<FEFF0F400F7C>>> BDC \n<0134>Tj\nEMC \n"
    b"<0169014400FF>Tj\n"
    b"1 0 0 1 0 -26 Tm\n"
    b"/Span<</ActualText<FEFFFFFD>>> BDC \n<0167>Tj\nEMC \n"
    b"<00FF>Tj\nET"
)


def test_word_style_wrapper_removed_payload_kept():
    out, n = _strip_word_actualtext_sentinels_in_stream(WORD_STYLE)
    assert n == 1
    assert b"FEFFFFFD" not in out
    assert b"<0384>Tj" in out
    assert b"<0100>Tj" in out


def test_indesign_style_does_not_cross_spans():
    out, n = _strip_word_actualtext_sentinels_in_stream(INDESIGN_STYLE)
    assert n == 1
    assert b"FEFFFFFD" not in out
    # the legitimate ActualText span must survive untouched
    assert b"/Span<</ActualText<FEFF0F400F7C>>> BDC" in out
    # every text-show operator must survive, in order
    assert _text_show_ops_preserved(INDESIGN_STYLE, out)
    # only the ~40-byte wrapper may be removed
    assert len(INDESIGN_STYLE) - len(out) < 60


def test_no_sentinel_stream_untouched():
    stream = b"BT\n<0149>Tj\n/Span<</ActualText<FEFF0F40>>> BDC <0134>Tj EMC\nET"
    out, n = _strip_word_actualtext_sentinels_in_stream(stream)
    assert n == 0
    assert out == stream


def test_guard_blocks_lossy_rewrite():
    # If the regex ever regresses to swallowing show operators, the
    # preservation guard must refuse the rewrite (return original, 0).
    before = b"<0149>Tj <0150>Tj"
    after_lossy = b"<0149>Tj"
    assert not _text_show_ops_preserved(before, after_lossy)
