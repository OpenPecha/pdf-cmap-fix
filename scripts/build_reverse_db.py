"""
Build the reverse glyph matching database.

Repository: https://github.com/OpenPecha/pdf-cmap-fix — see README for font ZIP
sources and ``Updating reverse_db.json``.

For each font (from zip archives and/or recursive directories), derives:
  GID -> correct Unicode sequence

by recursively decomposing GSUB data:

- **Lookup type 4** (ligature): ligature glyph → component glyph names.
- **Lookup type 2** (multiple substitution): one glyph → ordered sequence (split).
- **Lookup type 1** (single substitution): reverse map substitute → source glyphs so
  intermediate glyphs such as ``tibKa2`` resolve toward cmap entries (e.g. ``tibKa`` → ཀ).
- **Lookup type 7** (extension): unwrapped transparently to its inner subtable so the
  collectors above see types 1/2/4 even when they are stored via 32-bit offsets.

Other lookup types are not expanded yet (alternate, contextual, chained, reverse-chain).

Usage
-----
    python scripts/build_reverse_db.py --fonts-dir ../tibetan-fonts
    python scripts/build_reverse_db.py --zip scripts/bodyig.zip
    python scripts/build_reverse_db.py --zip a.zip --fonts-dir ../fonts --output out.json

If no --zip / --fonts-dir is given, uses scripts/bodyig.zip when that file exists.

Duplicate normalised font keys: later sources win (overwrite); a warning is printed.

Output is written to pdf_cmap_fix/data/reverse_db.json by default.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from font_sources import iter_fonts_from_dir, iter_fonts_from_zip
REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_ZIP = SCRIPTS_DIR / "bodyig.zip"
DEFAULT_OUT = REPO_ROOT / "pdf_cmap_fix" / "data" / "reverse_db.json"


def _configure_stdio_utf8() -> None:
    """Avoid UnicodeEncodeError when printing font paths on Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except Exception:
                pass


def normalise_name(path_or_name: str) -> str:
    stem = Path(path_or_name).stem
    return re.sub(r"[^a-z0-9]", "", stem.lower())


def _iter_subtables(lookup, target_type: int):
    """Yield (effective_type, subtable) for *lookup*, unwrapping Extension (type 7).

    For a non-extension lookup whose ``LookupType == target_type`` this yields each
    raw subtable. For Extension lookups we follow ``ExtSubTable`` (via fontTools'
    ``ExtensionPosFormat1``-equivalent for GSUB) and yield only those whose inner
    type matches ``target_type``.
    """
    lt = lookup.LookupType
    if lt == target_type:
        for sub in lookup.SubTable:
            yield sub
        return
    if lt != 7:
        return
    for sub in lookup.SubTable:
        ext_type = getattr(sub, "ExtensionLookupType", None)
        ext_sub = getattr(sub, "ExtSubTable", None)
        if ext_type == target_type and ext_sub is not None:
            yield ext_sub


def gsub_lig_rules(font: TTFont) -> dict[str, list[str]]:
    """All GSUB type-4 rules: {result_gname: [component_gnames]}.

    Includes type-4 subtables that are wrapped inside Extension (type 7) lookups.
    """
    rules: dict[str, list[str]] = {}
    if "GSUB" not in font:
        return rules
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for sub in _iter_subtables(lookup, 4):
            for first, lig_list in sub.ligatures.items():
                for lig in lig_list:
                    rules[lig.LigGlyph] = [first] + list(lig.Component)
    return rules


def gsub_single_subst_reverse(font: TTFont) -> dict[str, list[str]]:
    """GSUB type 1 (single subst): for each *target* glyph name, list of *source* names.

    Several sources may map to the same substitute (e.g. ``tibKa`` and ``tibKa3`` → ``tibKa2``).
    Extension (type 7) lookups whose inner type is 1 are also collected.
    """
    rev: dict[str, list[str]] = defaultdict(list)
    if "GSUB" not in font:
        return {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for sub in _iter_subtables(lookup, 1):
            mapping = getattr(sub, "mapping", None)
            if not mapping:
                continue
            for src, tgt in mapping.items():
                rev[tgt].append(src)
    return {k: v for k, v in rev.items()}


def gsub_multiple_subst_forward(font: TTFont) -> dict[str, list[str]]:
    """GSUB type 2 (multiple subst): {input_gname: [output component gnames]}.

    Extension (type 7) lookups whose inner type is 2 are also collected.
    """
    out: dict[str, list[str]] = {}
    if "GSUB" not in font:
        return out
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for sub in _iter_subtables(lookup, 2):
            mapping = getattr(sub, "mapping", None)
            if not mapping:
                continue
            for src, seq in mapping.items():
                out[src] = list(seq) if seq else []
    return out


def gsub_lookup_type_counts(font: TTFont) -> dict[int, int]:
    """Return {LookupType: count} for diagnostics; Extension (7) lookups are reported
    as their *inner* type as well, summed alongside the explicit count."""
    raw: dict[int, int] = defaultdict(int)
    if "GSUB" not in font:
        return {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        raw[lookup.LookupType] += 1
        if lookup.LookupType == 7:
            for sub in lookup.SubTable:
                inner = getattr(sub, "ExtensionLookupType", None)
                if inner is not None:
                    raw[inner] += 1
    return dict(sorted(raw.items()))


def build_gid_map(font: TTFont) -> dict[int, str]:
    """GID -> unicode sequence via cmap + recursive GSUB decomposition."""
    cmap = font.getBestCmap() or {}
    glyph_order = font.getGlyphOrder()
    rules = gsub_lig_rules(font)
    single_rev = gsub_single_subst_reverse(font)
    multiple_fwd = gsub_multiple_subst_forward(font)
    gname_to_uni = {gname: chr(cp) for cp, gname in cmap.items()}
    cache: dict[str, str] = {}

    def decompose(gname: str, depth: int = 0, visiting: set[str] | None = None) -> str:
        if gname in cache:
            return cache[gname]
        if depth > 60:
            return ""
        if visiting is None:
            visiting = set()
        if gname in visiting:
            return ""
        visiting.add(gname)
        try:
            if gname in gname_to_uni:
                result = gname_to_uni[gname]
            elif gname in rules:
                result = "".join(decompose(c, depth + 1, visiting) for c in rules[gname])
            elif gname in multiple_fwd:
                result = "".join(
                    decompose(c, depth + 1, visiting) for c in multiple_fwd[gname]
                )
            elif gname in single_rev:
                sources = sorted(
                    single_rev[gname],
                    key=lambda s: (0 if s in gname_to_uni else 1, s),
                )
                result = ""
                for src in sources:
                    r = decompose(src, depth + 1, visiting)
                    if r:
                        result = r
                        break
            else:
                result = ""
        finally:
            visiting.discard(gname)

        cache[gname] = result
        return result

    result: dict[int, str] = {}
    for gid, gname in enumerate(glyph_order):
        uni = decompose(gname)
        if uni:
            result[gid] = uni
    return result


def _process_font(
    label: str,
    font: TTFont,
    db: dict[str, dict[str, str]],
    seen_keys: dict[str, str],
) -> None:
    key = normalise_name(label)
    short = Path(label).name
    if key in seen_keys:
        prev = seen_keys[key]
        print(f"  WARN duplicate key {key!r}: replacing {prev} -> {short}")
    seen_keys[key] = short

    print(f"  {short} … ", end="", flush=True)
    try:
        gid_map = build_gid_map(font)
        multi = sum(1 for v in gid_map.values() if len(v) > 1)
        db[key] = {str(gid): uni for gid, uni in gid_map.items()}
        print(f"{len(gid_map)} GIDs mapped, {multi} multi-char stacks")
    except Exception as exc:
        print(f"ERROR: {exc}")


def build_database(zips: list[Path], font_dirs: list[Path]) -> dict[str, dict[str, str]]:
    db: dict[str, dict[str, str]] = {}
    seen_keys: dict[str, str] = {}

    for zp in zips:
        if not zp.is_file():
            print(f"SKIP (not a file): {zp}", file=sys.stderr)
            continue
        print(f"\n== Zip: {zp} ==")
        for entry, data in iter_fonts_from_zip(zp):
            try:
                font = TTFont(io.BytesIO(data), lazy=False)
                _process_font(entry, font, db, seen_keys)
            except Exception as exc:
                print(f"  ERROR {entry}: {exc}")

    for d in font_dirs:
        if not d.is_dir():
            print(f"SKIP (not a directory): {d}", file=sys.stderr)
            continue
        print(f"\n== Directory: {d} ==")
        for path, _ in iter_fonts_from_dir(d):
            try:
                font = TTFont(str(path), lazy=False)
                _process_font(str(path), font, db, seen_keys)
            except Exception as exc:
                print(f"  ERROR {path}: {exc}")

    return db


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build GID→Unicode reverse database from TTF/OTF fonts.",
    )
    p.add_argument(
        "--zip",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="Zip file containing fonts (repeatable).",
    )
    p.add_argument(
        "--fonts-dir",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="Directory to scan recursively for .ttf/.otf (repeatable).",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=f"Output JSON path (default: {DEFAULT_OUT})",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    _configure_stdio_utf8()
    args = parse_args(argv)
    zips: list[Path] = list(args.zip)
    font_dirs: list[Path] = list(args.fonts_dir)

    if not zips and not font_dirs:
        if DEFAULT_ZIP.is_file():
            zips = [DEFAULT_ZIP]
            print(f"No --zip/--fonts-dir; using default {DEFAULT_ZIP}")
        else:
            sys.exit(
                "Provide at least one --zip or --fonts-dir, or place bodyig.zip in scripts/.\n"
                "Example: python scripts/build_reverse_db.py --fonts-dir ../tibetan-fonts"
            )

    out_path = args.output or DEFAULT_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    db = build_database(zips, font_dirs)
    out_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}  ({out_path.stat().st_size // 1024} KB)")
    print(f"Fonts in DB: {len(db)}")


if __name__ == "__main__":
    main()
