"""
Bulk-write **PUA-free gshape** per-font JSON from ZIP archives and/or directories.

For each font from the source(s):

1. Build the gshape lookup in memory (outline fingerprint -> Unicode) -- the same
   pipeline as ``scripts/gshape/build_per_font_gshape_maps.py``.
2. Load the matching ``<key>.json`` from ``--gname-dir`` (gname PUA-free output).
3. Patch PUA values using ``patch_gshape_data(font, gshape_data, gname_inner)``.
4. Write the patched JSON to ``--output-dir``.

``--gname-dir`` must point at the output of ``scripts/pua/gname/build_pua_free_gname_maps.py``.
Fonts without a matching gname file are written unpatched (with a warning).

Example::

    python scripts/pua/gshape/build_pua_free_gshape_maps.py \\
      --zip fonts/bodyig.zip \\
      --gname-dir pdf_cmap_fix/data/font_lookup_gname_pua_free

    # Custom dirs
    python scripts/pua/gshape/build_pua_free_gshape_maps.py \\
      --zip fonts/bodyig.zip \\
      --gname-dir ./builds/custom_gname_pua_free \\
      -o ./builds/custom_gshape_pua_free

    # From a directory of fonts
    python scripts/pua/gshape/build_pua_free_gshape_maps.py \\
      --fonts-dir /path/to/fonts \\
      --gname-dir pdf_cmap_fix/data/font_lookup_gname_pua_free
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

_SCRIPTS = Path(__file__).resolve().parents[2]  # scripts/
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

REPO_ROOT = _SCRIPTS.parent
DEFAULT_GNAME_DIR = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gname_pua_free"
DEFAULT_OUT = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gshape_pua_free"

from font_sources import iter_fonts_from_dir, iter_fonts_from_zip  # noqa: E402
from per_font_maps import (  # noqa: E402
    Manifest,
    _build_gid_map_safe,
    _resolve_font_key,
)
from font_lookup_payload import build_lookup_json_payload  # noqa: E402
from pua_gshape_patcher import first_inner_map, patch_gshape_data  # noqa: E402


def _process_font_gshape_pua(
    label: str,
    source_id: str,
    font: TTFont,
    out_dir: Path,
    gname_dir: Path,
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

        payload = build_lookup_json_payload(
            font=font,
            key=key,
            gid_map=gid_map,
            counts_int=counts_int,
            kind="gshape",
            source_id=source_id,
        )

        gname_path = gname_dir / f"{key}.json"
        if gname_path.is_file():
            gname_data = json.loads(gname_path.read_text(encoding="utf-8"))
            _, gname_inner = first_inner_map(gname_data)
            patched, no_gn, no_pua, collisions = patch_gshape_data(
                font=font,
                gshape_data=payload,
                public_gname_inner=gname_inner,
            )
            patch_note = f", gshape_patched={patched}"
        else:
            patch_note = " (no gname sidecar — unpatched)"
            print(f"\n    WARN no gname file for {key!r}", end="")

        inner = payload[key]
        multi = payload["_meta"]["multi_char_stacks"]
        counts = payload["_meta"]["gsub_lookup_counts"]
        out_path = out_dir / f"{key}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.fonts_written.append(key)
        print(
            f"{len(gid_map)} GIDs, inner={len(inner)}, {multi} multi-char, "
            f"GSUB={counts or '{}'}{patch_note}, wrote {out_path.name}"
        )
    except Exception as exc:
        manifest.errors.append((source_id, str(exc)))
        print(f"ERROR: {exc}")


def build_pua_free_gshape(
    zips: list[Path], font_dirs: list[Path], out_dir: Path, gname_dir: Path
) -> Manifest:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(out_dir=out_dir, lookup_kind="gshape")
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
            try:
                _process_font_gshape_pua(entry, source_id, font, out_dir, gname_dir, seen, manifest)
            finally:
                font.close()

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
            try:
                _process_font_gshape_pua(str(path), source_id, font, out_dir, gname_dir, seen, manifest)
            finally:
                font.close()

    return manifest


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--zip", action="append", default=[], type=Path, metavar="PATH",
                   help="Zip file containing fonts (repeatable).")
    p.add_argument("--fonts-dir", action="append", default=[], type=Path, metavar="PATH",
                   help="Directory to scan recursively for .ttf / .otf (repeatable).")
    p.add_argument("-o", "--output-dir", type=Path, default=None, metavar="DIR",
                   help=f"Output directory (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})")
    p.add_argument("--gname-dir", type=Path, default=None, metavar="DIR",
                   help=f"PUA-free gname dir (default: {DEFAULT_GNAME_DIR.relative_to(REPO_ROOT)})")
    args = p.parse_args(argv)

    zips: list[Path] = list(args.zip)
    font_dirs: list[Path] = list(args.fonts_dir)
    if not zips and not font_dirs:
        sys.exit(
            "Provide at least one --zip or --fonts-dir. Example:\n  "
            "python scripts/pua/gshape/build_pua_free_gshape_maps.py "
            "--zip fonts/bodyig.zip --gname-dir pdf_cmap_fix/data/font_lookup_gname_pua_free"
        )

    out_dir = (args.output_dir or DEFAULT_OUT).resolve()
    gname_dir = (args.gname_dir or DEFAULT_GNAME_DIR).resolve()

    if not gname_dir.is_dir():
        print(
            f"WARN: --gname-dir {gname_dir} does not exist. "
            "Run scripts/pua/gname/build_pua_free_gname_maps.py first.",
            file=sys.stderr,
        )

    manifest = build_pua_free_gshape(zips, font_dirs, out_dir, gname_dir)
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
