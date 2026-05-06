"""
Write one JSON per font with its GID -> Unicode map.

Reads ``.ttf`` / ``.otf`` from one or more zip archives and/or directories
(recursively) using :mod:`font_sources`, builds the map with
:func:`build_reverse_db.build_gid_map` (which handles GSUB lookup types
1, 2, 4 and Extension/7 wrappers), then writes a small per-font JSON file
into the package data directory.

File layout::

    pdf_cmap_fix/data/per_font/<normalised_name>.json

Each file is shaped exactly like one entry of the merged ``reverse_db.json``::

    {
      "<normalised_name>": { "gid_str": "unicode_str", ... },
      "_meta": {
          "source": "<archive_or_dir>::<member_path>",
          "gids_mapped": <int>,
          "multi_char_stacks": <int>,
          "gsub_lookup_counts": {"1": ..., "2": ..., "4": ..., "7": ...}
      }
    }

The ``_meta`` block is a sibling key (not nested inside the font dict) so the
extractor's overlay merge (``--overlay-db``) ignores it cleanly: only dict
values are merged into the reverse DB and the font key already maps to the GID
dict.

Usage::

    python scripts/build_per_font_gid_maps.py \\
        --zip scripts/bodyig.zip \\
        --zip scripts/tibetan-fonts-main.zip \\
        --zip scripts/tibetan-fonts-private-main.zip
    python scripts/build_per_font_gid_maps.py --fonts-dir scripts
    python scripts/build_per_font_gid_maps.py --zip a.zip -o other_dir/per_font
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_reverse_db import (  # noqa: E402
    build_gid_map,
    gsub_lookup_type_counts,
    normalise_name,
)
from font_sources import iter_fonts_from_dir, iter_fonts_from_zip  # noqa: E402

REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_OUT = REPO_ROOT / "pdf_cmap_fix" / "data" / "per_font"


@dataclass
class Manifest:
    out_dir: Path
    fonts_written: list[str] = field(default_factory=list)
    duplicates: list[tuple[str, str, str]] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def write(self) -> None:
        path = self.out_dir / "_manifest.json"
        unique = sorted(set(self.fonts_written))
        payload = {
            "fonts_written": unique,
            "count": len(unique),
            "attempts": len(self.fonts_written),
            "duplicates": [
                {"key": k, "previous_source": prev, "new_source": new}
                for k, prev, new in self.duplicates
            ],
            "errors": [
                {"source": src, "error": err} for src, err in self.errors
            ],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _font_internal_names(font: TTFont) -> list[str]:
    """Return candidate names from the font's ``name`` table, best first."""
    names: list[str] = []
    try:
        name_table = font["name"]
    except Exception:
        return names
    for nameid in (6, 4, 1):  # PostScript, Full Name, Family
        try:
            rec = name_table.getDebugName(nameid)
        except Exception:
            rec = None
        if rec:
            names.append(rec)
    return names


def _resolve_font_key(label: str, font: TTFont) -> str:
    """Pick a non-empty, filesystem-safe key for *label* / *font*.

    Strategy:
      1. ``normalise_name(label)`` (matches the reverse_db merge key when ASCII).
      2. ``normalise_name`` of any font internal name (PostScript / Full / Family).
      3. ``font_<sha1[:10]>`` of the original label as a last resort.
    """
    key = normalise_name(label)
    if key:
        return key
    for cand in _font_internal_names(font):
        k2 = normalise_name(cand)
        if k2:
            return k2
    digest = hashlib.sha1(label.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"font_{digest}"


def _build_gid_map_safe(
    font: TTFont, source_id: str
) -> tuple[dict[int, str], dict[str, int], list[str]]:
    """Run :func:`build_gid_map` with a graceful retry if GSUB is corrupt.

    Returns ``(gid_map, gsub_counts, warnings)``. On the first failure we drop
    the GSUB table from the in-memory font and retry with cmap-only.
    """
    warnings: list[str] = []
    try:
        gid_map = build_gid_map(font)
        counts = gsub_lookup_type_counts(font)
        return gid_map, counts, warnings
    except Exception as exc:
        warnings.append(f"GSUB unreadable ({exc!r}); retrying cmap-only")
        try:
            if "GSUB" in font:
                del font["GSUB"]
        except Exception:
            pass
        gid_map = build_gid_map(font)
        return gid_map, {}, warnings


def _process_font(
    label: str,
    source_id: str,
    font: TTFont,
    out_dir: Path,
    seen: dict[str, str],
    manifest: Manifest,
) -> None:
    key = _resolve_font_key(label, font)
    if key in seen:
        manifest.duplicates.append((key, seen[key], source_id))
        print(f"  WARN duplicate key {key!r}: {seen[key]} -> {source_id}")
    seen[key] = source_id

    short = Path(label).name
    print(f"  {short} … ", end="", flush=True)
    try:
        gid_map, counts_int, warnings = _build_gid_map_safe(font, source_id)
        for w in warnings:
            print(f"\n    WARN {w}")
            manifest.errors.append((source_id, w))
        multi = sum(1 for v in gid_map.values() if len(v) > 1)
        counts = {str(k): v for k, v in counts_int.items()}
        payload: dict[str, Any] = {
            key: {str(g): u for g, u in gid_map.items()},
            "_meta": {
                "source": source_id,
                "gids_mapped": len(gid_map),
                "multi_char_stacks": multi,
                "gsub_lookup_counts": counts,
            },
        }
        out_path = out_dir / f"{key}.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.fonts_written.append(key)
        print(
            f"{len(gid_map)} GIDs, {multi} multi-char, "
            f"GSUB={counts or '{}'}, wrote {out_path.name}"
        )
    except Exception as exc:
        manifest.errors.append((source_id, str(exc)))
        print(f"ERROR: {exc}")


def build_per_font(
    zips: list[Path], font_dirs: list[Path], out_dir: Path
) -> Manifest:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(out_dir=out_dir)
    seen: dict[str, str] = {}

    for zp in zips:
        if not zp.is_file():
            print(f"SKIP (not a file): {zp}", file=sys.stderr)
            continue
        print(f"\n== Zip: {zp} ==")
        for entry, data in iter_fonts_from_zip(zp):
            source_id = f"{zp.name}::{entry}"
            try:
                font = TTFont(io.BytesIO(data), lazy=False)
            except Exception as exc:
                print(f"  ERROR opening {entry}: {exc}")
                manifest.errors.append((source_id, str(exc)))
                continue
            _process_font(entry, source_id, font, out_dir, seen, manifest)

    for d in font_dirs:
        if not d.is_dir():
            print(f"SKIP (not a directory): {d}", file=sys.stderr)
            continue
        print(f"\n== Directory: {d} ==")
        for path, _ in iter_fonts_from_dir(d):
            source_id = str(path)
            try:
                font = TTFont(str(path), lazy=False)
            except Exception as exc:
                print(f"  ERROR opening {path}: {exc}")
                manifest.errors.append((source_id, str(exc)))
                continue
            _process_font(str(path), source_id, font, out_dir, seen, manifest)

    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Write one JSON per font (GID -> Unicode) under "
            "pdf_cmap_fix/data/per_font/. GSUB types handled: 1, 2, 4 (and 7 wrappers)."
        )
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
        help="Directory to scan recursively for .ttf / .otf (repeatable).",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_OUT,
        metavar="DIR",
        help=f"Output directory for per-font JSON (default: {DEFAULT_OUT})",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    zips: list[Path] = list(args.zip)
    font_dirs: list[Path] = list(args.fonts_dir)
    if not zips and not font_dirs:
        sys.exit(
            "Provide at least one --zip or --fonts-dir. Example:\n"
            "  python scripts/build_per_font_gid_maps.py --zip scripts/bodyig.zip"
        )

    manifest = build_per_font(zips, font_dirs, args.output_dir)
    manifest.write()
    unique_count = len(set(manifest.fonts_written))
    print(
        f"\nWrote {unique_count} unique per-font JSON files under "
        f"{manifest.out_dir} ({len(manifest.fonts_written)} attempts)."
    )
    if manifest.duplicates:
        print(f"Duplicates (later won): {len(manifest.duplicates)}")
    if manifest.errors:
        print(f"Errors / warnings: {len(manifest.errors)}")


if __name__ == "__main__":
    main()
