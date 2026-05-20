"""
Create or refresh a single PUA-free gshape JSON from one ``.ttf`` / ``.otf`` / ``.ttc``.

Builds the gshape lookup (outline fingerprint → Unicode), then patches PUA values
using the matching gname PUA-free JSON supplied via ``--gname-json``.

Default lookup directory: ``pdf_cmap_fix/data/font_lookup_gshape_pua_free/``

Example::

    python scripts/pua/gshape/update_pua_free_gshape.py \\
      --gname-json ./builds/custom_gname_pua_free/jomolhari.json \\
      path/to/Jomolhari-Regular.ttf

    # Custom lookup directory
    python scripts/pua/gshape/update_pua_free_gshape.py \\
      --lookup-dir ./builds/custom_gshape_pua_free \\
      --gname-json ./builds/custom_gname_pua_free/jomolhari.json \\
      path/to/Jomolhari-Regular.ttf

    # Dry-run: show what would be written without writing
    python scripts/pua/gshape/update_pua_free_gshape.py \\
      --dry-run --gname-json path/to/jomolhari.json path/to/Jomolhari-Regular.ttf
"""
from __future__ import annotations

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
DEFAULT_LOOKUP_DIR = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gshape_pua_free"

from single_font_lookup import _write_one  # noqa: E402
from pua_gshape_patcher import first_inner_map, patch_gshape_data  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    import argparse

    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "fonts",
        nargs="*",
        type=Path,
        metavar="FONT",
        help="One or more .ttf / .otf paths",
    )
    p.add_argument("--lookup-dir", type=Path, default=None, metavar="DIR",
                   help="Directory for <key>.json (default: font_lookup_gshape_pua_free/)")
    p.add_argument("--gname-json", type=Path, default=None, metavar="PATH",
                   help="PUA-free gname JSON for this font (from scripts/pua/gname/)")
    p.add_argument("--key", type=str, default=None, metavar="NAME")
    p.add_argument("-o", "--output", type=Path, default=None, metavar="PATH")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ttc-index", type=int, default=None, metavar="N")
    args = p.parse_args(argv)

    fonts: list[Path] = list(args.fonts)
    if not fonts:
        sys.exit("Provide at least one font path.")
    if args.key is not None and len(fonts) != 1:
        sys.exit("--key requires exactly one font path")
    if args.output is not None and len(fonts) != 1:
        sys.exit("--output / -o requires exactly one font path")

    lookup_dir = (
        args.lookup_dir.resolve() if args.lookup_dir is not None else DEFAULT_LOOKUP_DIR.resolve()
    )
    print(f"Font lookup directory: {lookup_dir}  (kind=gshape PUA-free)")

    gname_json: Path | None = args.gname_json
    if gname_json is not None:
        gname_json = gname_json.expanduser().resolve()
        if not gname_json.is_file():
            sys.exit(f"--gname-json not found: {gname_json}")
        gname_data = json.loads(gname_json.read_text(encoding="utf-8"))
        _, gname_inner = first_inner_map(gname_data)
    else:
        gname_inner = None

    for fp in fonts:
        print(f"\nProcessing: {fp}")
        ttc_idx = args.ttc_index
        if ttc_idx is None and fp.suffix.lower() == ".ttc":
            ttc_idx = 0
        try:
            out_path, key, existed = _write_one(
                fp,
                lookup_dir,
                args.key,
                args.output,
                args.dry_run,
                ttc_index=ttc_idx if fp.suffix.lower() == ".ttc" else None,
                kind="gshape",
            )
        except FileNotFoundError as e:
            print(f"  ERROR not found: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"  ERROR {fp}: {exc}", file=sys.stderr)
            raise

        if args.dry_run or gname_inner is None:
            if gname_inner is None and not args.dry_run:
                print("  WARN: --gname-json not provided; gshape written unpatched.")
            continue

        # Load the just-written gshape JSON and patch it
        data = json.loads(out_path.read_text(encoding="utf-8"))
        suffix = fp.suffix.lower()
        fn = ttc_idx if suffix == ".ttc" else None
        font = TTFont(str(fp.resolve()), lazy=False, **({"fontNumber": fn} if fn is not None else {}))
        try:
            patched, no_gn, no_pua, collisions = patch_gshape_data(
                font=font,
                gshape_data=data,
                public_gname_inner=gname_inner,
            )
        finally:
            font.close()
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"  Gshape patch: {patched} rows updated, skipped (no gname)={no_gn}, "
            f"skipped (no PUA)={no_pua}, hash collisions={collisions}"
        )


if __name__ == "__main__":
    main()
