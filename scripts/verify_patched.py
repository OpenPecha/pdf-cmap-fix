"""Post-patch verification for pdf-cmap-fix output.

Compares every ``*.patched.pdf`` against its original and fails loudly on the
two regressions that are otherwise invisible:

  LATIN LOSS  Latin text that extracted correctly BEFORE patching no longer
              does. Detected by counting ASCII-letter runs of 4+ characters
              (real words) in both files: a large drop means a Latin font was
              mis-identified as legacy Tibetan and overwritten.

  U+2423      OPEN BOX characters left in the output. These come from glyph
              names pdf-cmap-fix could not resolve (e.g. /visiblespace), where
              PyMuPDF then filled the gap with the wrong character.

Also reports Tibetan character gain, which should be large and positive -- a
patched legacy PDF that gained no Tibetan was not actually fixed.

Usage:
    python scripts/verify_patched.py <root-folder>

Exit status is 1 if any file fails, so it can gate a batch pipeline.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

OPEN_BOX = chr(0x2423)
TIBETAN = re.compile(r"[ༀ-࿿]")
WORD = re.compile(r"[A-Za-z]{4,}")

# A patched file may legitimately lose a few stray Latin runs (a legacy font
# whose Latin-looking garbage really was Tibetan). Losing most of them is not
# legitimate.
LATIN_LOSS_FAIL_RATIO = 0.5


def scan(path: Path):
    doc = fitz.open(path)
    words = tib = boxes = 0
    for i in range(doc.page_count):
        t = doc[i].get_text()
        words += len(WORD.findall(t))
        tib += len(TIBETAN.findall(t))
        boxes += t.count(OPEN_BOX)
    return words, tib, boxes


def main() -> int:
    root = Path(sys.argv[1])
    patched = sorted(root.rglob("*.patched.pdf"))
    if not patched:
        print(f"No *.patched.pdf under {root}")
        return 0

    failures = []
    for p in patched:
        orig = p.with_name(p.name[: -len(".patched.pdf")] + ".pdf")
        if not orig.is_file():
            print(f"?? {p.name}: no original alongside, skipped")
            continue

        ow, ot, _ = scan(orig)
        pw, pt, pb = scan(p)

        problems = []
        if ow and pw < ow * LATIN_LOSS_FAIL_RATIO:
            problems.append(f"LATIN LOSS {ow}->{pw} English words")
        if pb:
            problems.append(f"{pb} x U+2423 OPEN BOX remain")
        if pt <= ot:
            problems.append(f"no Tibetan gained ({ot}->{pt})")

        status = "FAIL" if problems else "ok  "
        print(f"{status} {p.relative_to(root)}")
        print(f"       english words {ow:>7} -> {pw:<7}"
              f"  tibetan {ot:>7} -> {pt:<7}  open-box {pb}")
        for msg in problems:
            print(f"       !! {msg}")
        if problems:
            failures.append(p)

    print()
    if failures:
        print(f"{len(failures)} of {len(patched)} file(s) FAILED verification:")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"All {len(patched)} patched file(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
