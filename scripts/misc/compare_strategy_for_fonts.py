"""Spot-check specific pages of a PDF under different pdf-cmap-fix strategies.

Finds the pages whose fonts match given name substrings (default:
MonlamUniOuChan / MinionPro -- the fonts that have no gname DB match in
01.pdf), then prints each matching page's extracted text under the gname,
gid, and gshape strategies side by side, so you can eyeball whether the
strategy that "wins" on whole-document quality score actually renders these
specific passages correctly.

Usage:
    python compare_strategy_for_fonts.py <pdf_path> [max_pages] [name_substr ...]

Example:
    python compare_strategy_for_fonts.py "01.pdf" 3 MonlamUniOuChan MinionPro
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

from pdf_cmap_fix import tounicode_core as core
from pdf_cmap_fix.gid.extractor import FONT_LOOKUP_DIR


def pages_using_fonts(doc: fitz.Document, targets: list[str]) -> list[int]:
    pages = []
    for pno in range(len(doc)):
        names = [f[3] for f in doc[pno].get_fonts(full=True)]
        if any(any(t.lower() in n.lower() for t in targets) for n in names):
            pages.append(pno)
    return pages


def extract_pages_text(pdf_path: Path, lookup_dir: Path, tier: str, pages: list[int]) -> list[str]:
    doc = fitz.open(str(pdf_path))
    core.patch_doc(doc, lookup_dir=lookup_dir, tier=tier, verbose=False)
    out = [doc[pno].get_text() for pno in pages]
    doc.close()
    return out


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf_path = Path(sys.argv[1])
    max_pages = 3
    rest = sys.argv[2:]
    if rest and rest[0].isdigit():
        max_pages = int(rest[0])
        rest = rest[1:]
    targets = rest or ["MonlamUniOuChan", "MinionPro"]

    doc = fitz.open(str(pdf_path))
    pages = pages_using_fonts(doc, targets)
    doc.close()
    print(f"targets: {targets}")
    print(f"pages referencing target fonts: {[p + 1 for p in pages]}  ({len(pages)} total)")
    if not pages:
        return
    sample = pages[:max_pages]
    print(f"showing first {len(sample)} of those pages under each strategy\n")

    specs = core._default_strategy_specs(FONT_LOOKUP_DIR)
    per_strategy: dict[str, list[str]] = {}
    for name in ["gname", "gid", "gshape"]:
        tier, lookup_dir = specs[name]
        per_strategy[name] = extract_pages_text(pdf_path, lookup_dir, tier, sample)

    for i, pno in enumerate(sample):
        print("#" * 70)
        print(f"PAGE {pno + 1}")
        for name in ["gname", "gid", "gshape"]:
            print(f"\n----- strategy={name} -----")
            print(per_strategy[name][i][:1500])
        print()


if __name__ == "__main__":
    main()
