"""Diagnose why specific fonts in a PDF fail to match the pdf-cmap-fix DB.

Reuses the tool's own internal matching functions (name normalisation,
DB-key picking, lookup loading, GID/glyph-name resolution) so the result
reflects exactly what the real run does -- no re-implementation drift.

Usage:
    python diagnose_unmatched_font.py <pdf_path> [strategy] [name_substr ...]

    strategy defaults to "gname" (the strategy pdf-cmap-fix auto-selected
    for this PDF). name_substr filters which embedded fonts to inspect
    (case-insensitive substring match against the PDF BaseFont name);
    omit to inspect every font in the document.

Example:
    python diagnose_unmatched_font.py "01.pdf" gname MonlamUniOuChan MinionPro
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import fitz
from fontTools.ttLib import TTFont

from pdf_cmap_fix import tounicode_core as core
from pdf_cmap_fix.gid.extractor import FONT_LOOKUP_DIR


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf_path = Path(sys.argv[1])
    strategy = sys.argv[2] if len(sys.argv) > 2 else "gname"
    name_filters = [s.lower() for s in sys.argv[3:]]

    specs = core._default_strategy_specs(FONT_LOOKUP_DIR)
    if strategy not in specs:
        sys.exit(f"unknown strategy {strategy!r}; choices: {', '.join(specs)}")
    tier, lookup_dir = specs[strategy]
    print(f"strategy={strategy}  tier={tier}  lookup_dir={lookup_dir}")

    keys_disk = core._discover_lookup_keys(lookup_dir)
    db_index = core._build_db_index(keys_disk)
    name_index = core._load_name_index_cached(lookup_dir)
    print(f"lookup files on disk: {len(keys_disk)}")
    print(f"name_index present:   {name_index is not None}")
    print()

    doc = fitz.open(str(pdf_path))
    seen: set[int] = set()
    for pno in range(len(doc)):
        for f in doc[pno].get_fonts(full=True):
            xref, _, ftype, basename, _, _, _ = f
            if xref in seen:
                continue
            seen.add(xref)
            if name_filters and not any(nf in basename.lower() for nf in name_filters):
                continue

            print("=" * 70)
            print(f"xref={xref}  ftype={ftype}  basename={basename!r}")

            embedded_names = core._extract_font_names(doc, xref)
            print(f"  embedded name-table candidates: {embedded_names}")

            picked = None
            if name_index is not None:
                pdf_norm_candidates = []
                for cand in [*embedded_names, basename]:
                    q = core._normalise_name(cand)
                    if q and q not in pdf_norm_candidates:
                        pdf_norm_candidates.append(q)
                print(f"  normalised candidates (index path): {pdf_norm_candidates}")
                matched_name, cand_ids = core._resolve_index_font_ids(
                    name_index, pdf_norm_candidates
                )
                print(f"  index match -> name={matched_name!r} ids={cand_ids}")
                picked = cand_ids[0] if cand_ids else None
            else:
                for cand in embedded_names:
                    picked = core._pick_best_font_key(db_index, cand)
                    if picked:
                        print(f"  matched via embedded name {cand!r} -> {picked}")
                        break
                if picked is None:
                    picked = core._pick_best_font_key(db_index, basename)
                    print(f"  matched via basename {basename!r} -> {picked}")

            if not picked:
                print("  RESULT: no DB key picked at all (name matching itself failed)")
                continue

            path = lookup_dir / f"{picked}.json"
            if not path.is_file():
                print(f"  RESULT: picked key {picked!r} but file missing: {path}")
                continue
            loaded = core._load_lookup_file_cached(path)
            if loaded is None:
                print(f"  RESULT: lookup file failed to parse: {path}")
                continue
            match_kind, inner = loaded
            print(f"  loaded lookup: kind={match_kind}  entries={len(inner)}")
            if match_kind != tier:
                print(f"  RESULT: lookup kind {match_kind!r} != requested tier {tier!r} -> rejected")
                continue

            is_type0 = ftype == "Type0"
            cand_map = core._compute_db_map(doc, xref, is_type0, match_kind, inner)
            print(f"  computed {{code/gid -> unicode}} map size: {len(cand_map)}")

            try:
                tup = doc.extract_font(xref)
            except Exception as e:
                print(f"  extract_font() raised: {e}")
                tup = None
            if not tup or len(tup) < 4 or not tup[3]:
                print("  RESULT: font program not extractable/embedded -> gname/gshape resolution impossible")
                continue
            buf = tup[3]
            print(f"  extract_font ok: ext={tup[1]!r}  buf_len={len(buf)}")
            try:
                tt = TTFont(io.BytesIO(bytes(buf)), lazy=False)
                go = tt.getGlyphOrder()
                print(f"  embedded glyph order ({len(go)} glyphs), sample: {go[:12]}")
                sample_db_keys = list(inner.keys())[:12]
                print(f"  DB lookup key sample ({len(inner)} total): {sample_db_keys}")
                overlap = len(set(go) & set(inner.keys()))
                print(f"  glyph-name overlap between embedded font and DB: {overlap} / {len(go)}")
                if overlap == 0:
                    print("  RESULT: embedded glyph names share NOTHING with the DB's glyph-name "
                          "keys -- this subset was almost certainly re-named/stripped during "
                          "subsetting, so glyph-name (gname) lookup cannot work for this font. "
                          "Try --gid or --gshape strategy for this font instead.")
                else:
                    print(f"  RESULT: {cand_map and 'map built OK' or 'map still empty despite overlap -- investigate further'}")
            except Exception as e:
                print(f"  RESULT: TTFont failed to parse embedded font buffer: {e}")

    doc.close()


if __name__ == "__main__":
    main()
