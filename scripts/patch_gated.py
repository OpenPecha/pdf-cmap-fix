"""Patch PDFs with a gate on false-positive legacy-font shape matches.

The stock ``_recover_codes_from_shapes()`` accepts a match on an ABSOLUTE
summed vote (``_DISTINCT_VOTE_MIN = 0.008``), so a font clears the bar by
having many glyphs rather than by matching well. Latin text faces therefore get
matched to legacy Tibetan fonts and their text is destroyed on patching.

This wraps that function and re-scores the match as vote-per-fingerprinted-glyph,
rejecting anything below ``MIN_PER_GLYPH``. Measured on the Thrangu corpus:

    genuine Tibetan matches   0.00128 - 0.02512
    Latin false positives     0.00012 - 0.00072

The gate is only applied when ``font_hint`` is None (i.e. the font was NOT
already identified by name) -- the hinted path is code recovery for an
already-known legacy face and must not be gated.

Usage:
    python scripts/patch_gated.py <folder>

Walks the folder recursively, skips anything already named ``*.patched.pdf``,
and writes ``<name>.patched.pdf`` beside each source. Prints a per-font report
at the end showing which shape matches were rejected.

Verify the result with ``scripts/verify_patched.py`` before converting to XML.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import numpy as np

from pdf_cmap_fix import glyph_shape_id as gs
from pdf_cmap_fix import patch_pdf
from pdf_cmap_fix import tounicode_core as tc

MIN_PER_GLYPH = 0.001

_orig_recover = tc._recover_codes_from_shapes
rejected: list[tuple] = []
accepted: list[tuple] = []
_cache: dict[int, tuple] = {}


def _score(doc, xref):
    """Return (winner_name, vote_per_glyph, n_glyphs) for a font's shape vote."""
    db = gs._db()
    if db is None:
        return None, 0.0, 0
    vecs, _codes, font_ids, fonts, family_ids = db
    try:
        tup = doc.extract_font(xref)
    except Exception:
        return None, 0.0, 0
    if not tup or len(tup) < 4 or not tup[3]:
        return None, 0.0, 0
    ttfont = tc._load_pdf_embedded_font(bytes(tup[3]))
    if ttfont is None:
        return None, 0.0, 0
    try:
        glyph_set = ttfont.getGlyphSet()
    except Exception:
        return None, 0.0, 0

    upem = None
    if "CFF " in ttfont:
        try:
            cff = ttfont["CFF "].cff
            fm = cff[cff.fontNames[0]].rawDict.get("FontMatrix")
            if fm and fm[0]:
                upem = round(1 / fm[0])
        except Exception:
            upem = None
    if not upem:
        upem = ttfont["head"].unitsPerEm if "head" in ttfont else 1000

    fps = []
    for _code, gname in tc.parse_pdf_encoding(doc, xref).items():
        if not gname or gname == ".notdef":
            continue
        fp = gs._fingerprint_glyph(glyph_set, gname, upem)
        if fp is not None:
            fps.append(fp)
    if not fps:
        return None, 0.0, 0

    votes: dict[int, float] = {}
    for fp in fps:
        d = np.abs(vecs - fp).mean(axis=1)
        i0 = int(np.argmin(d))
        if d[i0] > gs._ACCEPT:
            continue
        other = d[family_ids != family_ids[i0]]
        distinct = float(other.min()) - float(d[i0]) if other.size else 1.0
        votes[int(font_ids[i0])] = votes.get(int(font_ids[i0]), 0.0) + max(distinct, 0.0)
    if not votes:
        return None, 0.0, len(fps)
    fid = max(votes, key=votes.get)
    return fonts[fid], votes[fid] / len(fps), len(fps)


def gated_recover(doc, xref, *, is_type0, referenced, font_hint=None):
    if font_hint is not None:
        return _orig_recover(
            doc, xref, is_type0=is_type0, referenced=referenced, font_hint=font_hint
        )

    basename = ""
    try:
        m = re.search(r"/BaseFont /(\S+)", doc.xref_object(xref))
        basename = m.group(1) if m else ""
    except Exception:
        pass

    if xref in _cache:
        name, per_glyph, n = _cache[xref]
    else:
        t0 = time.time()
        print(f"    [score] {basename} xref={xref} ...", flush=True)
        name, per_glyph, n = _score(doc, xref)
        _cache[xref] = (name, per_glyph, n)
        print(
            f"    [score] {basename} -> {name} per_glyph={per_glyph:.5f} "
            f"n={n} ({time.time() - t0:.1f}s)",
            flush=True,
        )

    if name is not None and per_glyph < MIN_PER_GLYPH:
        rejected.append((basename, name, per_glyph, n))
        return None, {}
    if name is not None:
        accepted.append((basename, name, per_glyph, n))
    return _orig_recover(
        doc, xref, is_type0=is_type0, referenced=referenced, font_hint=font_hint
    )


tc._recover_codes_from_shapes = gated_recover


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    if not root.exists():
        print(f"No such folder: {root}")
        return 2

    pdfs = [p for p in sorted(root.rglob("*.pdf"))
            if not p.name.lower().endswith(".patched.pdf")]
    if not pdfs:
        print(f"No PDFs under {root}")
        return 1

    for pdf in pdfs:
        out = pdf.with_name(pdf.stem + ".patched.pdf")
        print(f"--> {pdf.name}", flush=True)
        patch_pdf(str(pdf), output_path=str(out))
        print(f"    wrote {out.name}", flush=True)

    print("\n=== shape matches REJECTED by gate (would have corrupted text) ===",
          flush=True)
    for bn, nm, pg, n in rejected:
        print(f"  {bn:42s} -> {nm:18s} per_glyph={pg:.5f} n={n}", flush=True)
    if not rejected:
        print("  (none)", flush=True)

    print("\n=== shape matches ACCEPTED ===", flush=True)
    for bn, nm, pg, n in accepted:
        print(f"  {bn:42s} -> {nm:18s} per_glyph={pg:.5f} n={n}", flush=True)
    if not accepted:
        print("  (none)", flush=True)

    print("\nDONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
