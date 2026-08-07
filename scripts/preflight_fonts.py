"""Pre-flight font triage for pdf-cmap-fix.

Run this BEFORE patching a batch. For every simple font in every PDF under a
root, it reports how pdf-cmap-fix will resolve that font:

  NAME    resolved by pytiblegenc name lookup -- safe, this is the intended path
  SHAPE   no name match, will fall back to outline-fingerprint voting
  --      no legacy match at all, font left alone

For SHAPE rows it prints the vote-per-fingerprinted-glyph score and a verdict:

  PATCH   score >= MIN_PER_GLYPH -- will be treated as a legacy Tibetan font
  gated   score <  MIN_PER_GLYPH -- rejected, font left alone

A Latin text font (Times, Arial, Optima, Baskerville, ...) showing PATCH is the
bug that destroys English text: check it before running the batch. A genuinely
Tibetan font showing "gated" is the opposite failure -- real content silently
left unconverted.

Usage:
    python scripts/preflight_fonts.py <root-folder> [--min 0.001]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import fitz
import numpy as np

from pdf_cmap_fix import glyph_shape_id as gs
from pdf_cmap_fix import pytiblegenc_tables as ptg
from pdf_cmap_fix import tounicode_core as tc

# Latin families we expect to see in mixed-script books. Only used to colour the
# verdict -- never to make a patching decision.
LATIN_HINT = re.compile(
    r"(Times|Arial|Helvetica|Optima|Americana|Lucida|Trebuchet|Baskerville|"
    r"Garamond|Palatino|Minion|Myriad|Calibri|Cambria|Georgia|Verdana|"
    r"Courier|Wingdings|ZapfDingbats|Symbol)",
    re.I,
)


def shape_score(doc, xref):
    """(winner_font, vote_per_glyph, n_glyphs) for the shape vote, or (None,0,0)."""
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

    votes = {}
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--min", type=float, default=0.001, help="gate threshold")
    args = ap.parse_args()

    pdfs = [p for p in sorted(args.root.rglob("*.pdf"))
            if not p.name.lower().endswith(".patched.pdf")]
    if not pdfs:
        print(f"No PDFs under {args.root}")
        return

    warnings = []
    for pdf in pdfs:
        print(f"\n=== {pdf.relative_to(args.root)}")
        doc = fitz.open(pdf)
        seen = set()
        for x in range(1, doc.xref_length()):
            try:
                o = doc.xref_object(x)
            except Exception:
                continue
            if "/BaseFont" not in o:
                continue
            if not any(f"/Subtype /{t}" in o for t in ("Type1", "MMType1", "TrueType")):
                continue
            m = re.search(r"/BaseFont /(\S+)", o)
            if not m:
                continue
            base = m.group(1)
            short = base.split("+")[-1]
            if short in seen:
                continue
            seen.add(short)

            named, _ = ptg.table_for(base)
            if named:
                print(f"  NAME   {short:34s} -> {named}")
                continue

            win, per, n = shape_score(doc, x)
            if win is None:
                print(f"  --     {short:34s}    (no legacy match, left alone)")
                continue
            verdict = "PATCH" if per >= args.min else "gated"
            looks_latin = bool(LATIN_HINT.search(short))
            flag = ""
            if verdict == "PATCH" and looks_latin:
                flag = "   <== LATIN FONT WOULD BE PATCHED"
                warnings.append((str(pdf.relative_to(args.root)), short, win, per, n))
            elif verdict == "gated" and not looks_latin:
                flag = "   <== possible Tibetan font being skipped"
                warnings.append((str(pdf.relative_to(args.root)), short, win, per, n))
            print(f"  SHAPE  {short:34s} -> {win:20s} "
                  f"per_glyph={per:.5f} n={n:<4d} {verdict}{flag}")

    print("\n" + "=" * 78)
    if warnings:
        print("REVIEW THESE BEFORE PATCHING:")
        for f, font, win, per, n in warnings:
            print(f"  {f}\n      {font} -> {win}  per_glyph={per:.5f} n={n}")
    else:
        print("No suspicious font resolutions found.")


if __name__ == "__main__":
    sys.exit(main())
