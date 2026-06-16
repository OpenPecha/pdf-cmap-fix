"""Build the glyph-shape fingerprint DB used by ``pdf_cmap_fix.glyph_shape_id``.

Walks one or more reference-font directories, keeps every font whose
PostScript/family name resolves -- via this package's own pytiblegenc
normalisation -- to a known conversion table, and fingerprints each
byte-addressable glyph with the SAME representation-independent routine the
runtime matcher uses (so the DB and the matcher can never drift apart).

Output (written next to the package data):
  pdf_cmap_fix/data/pytiblegenc/glyph_shape_db.npz     vecs uint8[N,4096], codes, font_ids
  pdf_cmap_fix/data/pytiblegenc/glyph_shape_fonts.json  font_id -> table name

Usage:
  python scripts/shape/build_shape_db.py /path/to/font-dir [/path/to/another-font-dir ...]

Note: the reference fonts are NOT vendored; only these derived low-resolution
coverage fingerprints (64x64) are. Some faces (e.g. the Esam* family) are skipped
when every available copy has an unreadable 'glyf' table -- they are reported.
"""
import glob
import json
import os
import sys

import numpy as np
from fontTools.ttLib import TTFont

# Import the runtime fingerprint so the DB stays byte-compatible with matching.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from pdf_cmap_fix import glyph_shape_id as G
from pdf_cmap_fix import pytiblegenc_tables as ptg

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "pdf_cmap_fix",
                       "data", "pytiblegenc")


def _byte_to_glyph(cmap, b):
    if b in cmap:
        return cmap[b]
    try:
        u = ord(bytes([b]).decode("cp1252"))
        if u in cmap:
            return cmap[u]
    except Exception:
        pass
    return cmap.get(0xF000 + b)


def resolve_table(path):
    try:
        t = TTFont(path, fontNumber=0, lazy=True)
        names = t["name"]
        cands = []
        for nid in (6, 1, 4):
            rec = names.getName(nid, 3, 1) or names.getName(nid, 1, 0)
            if rec:
                cands.append(rec.toUnicode())
        t.close()
    except Exception:
        return None
    for c in cands:
        name, _ = ptg.table_for(c)
        if name:
            return name
    return None


def fingerprints_for(path):
    """(name byte_code -> uint8 fingerprint) for one font file, or []"""
    out = []
    t = TTFont(path, fontNumber=0)
    upem = t["head"].unitsPerEm
    cmap = t.getBestCmap() or {}
    gs = t.getGlyphSet()
    for b in range(32, 256):
        gname = _byte_to_glyph(cmap, b)
        if not gname or gname == ".notdef":
            continue
        fp = G._fingerprint_glyph(gs, gname, upem)
        if fp is None:
            continue
        out.append((b, (fp * 255).astype(np.uint8)))
    return out


def main(repos):
    files = []
    for repo in repos:
        for ext in ("ttf", "otf", "TTF", "OTF"):
            files += glob.glob(os.path.join(repo, "**", f"*.{ext}"), recursive=True)
    cand = {}
    for path in sorted(set(files)):
        name = resolve_table(path)
        if name:
            try:
                t = TTFont(path, fontNumber=0, lazy=True)
                ncodes = len(t.getBestCmap() or {})
                t.close()
            except Exception:
                ncodes = 0
            cand.setdefault(name, []).append((ncodes, path))
    print(f"scanned {len(set(files))} files; {len(cand)} resolve to a tiblegenc table")

    vecs, codes, font_ids, font_names, skipped = [], [], [], [], []
    for fid, name in enumerate(sorted(cand)):
        font_names.append(name)
        got = []
        for _, path in sorted(cand[name], reverse=True):
            try:
                got = fingerprints_for(path)
            except Exception:
                got = []
            if got:
                break
        if not got:
            skipped.append(name)
        for b, fp in got:
            vecs.append(fp); codes.append(b); font_ids.append(fid)

    np.savez_compressed(
        os.path.join(OUT_DIR, "glyph_shape_db.npz"),
        vecs=np.array(vecs, np.uint8),
        codes=np.array(codes, np.int16),
        font_ids=np.array(font_ids, np.int16),
    )
    with open(os.path.join(OUT_DIR, "glyph_shape_fonts.json"), "w", encoding="utf-8") as fh:
        json.dump(font_names, fh, ensure_ascii=False)
    print(f"wrote {len(vecs)} glyphs, {len(font_names)} fonts")
    if skipped:
        print(f"skipped (no readable copy): {skipped}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: build_shape_db.py <font-repo-dir> [<font-repo-dir> ...]")
    main(sys.argv[1:])
