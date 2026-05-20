"""
Create or refresh a single PUA-free gname JSON from one ``.ttf`` / ``.otf`` / ``.ttc`` file.

Builds the gname lookup for the face, then rewrites any PUA values whose glyph name
encodes the intended Unicode via the ``uni…`` naming convention.

Default lookup directory: ``pdf_cmap_fix/data/font_lookup_gname_pua_free/``

Example::

    python scripts/pua/gname/update_pua_free_gname.py path/to/MyFont.ttf

    # Custom output directory
    python scripts/pua/gname/update_pua_free_gname.py \\
      --lookup-dir ./builds/custom_gname_pua_free path/to/MyFont.ttf

    # Force key name
    python scripts/pua/gname/update_pua_free_gname.py \\
      --key jomolhari path/to/Jomolhari-Regular.ttf

    # Preview without writing
    python scripts/pua/gname/update_pua_free_gname.py --dry-run path/to/MyFont.ttf
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2]  # scripts/
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

REPO_ROOT = _SCRIPTS.parent
DEFAULT_LOOKUP_DIR = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gname_pua_free"

from single_font_lookup import _write_one, main_for_kind  # noqa: E402
from pua_gname_rewriter import rewrite_gname_lookup_pua_values  # noqa: E402


def _pua_main(argv: list[str] | None = None) -> None:
    """Thin wrapper: build gname lookup then apply PUA rewrite before writing."""
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
    p.add_argument(
        "--lookup-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory for <key>.json (default: font_lookup_gname_pua_free/)",
    )
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
        args.lookup_dir.resolve()
        if args.lookup_dir is not None
        else DEFAULT_LOOKUP_DIR.resolve()
    )
    print(f"Font lookup directory: {lookup_dir}  (kind=gname PUA-free)")

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
                kind="gname",
            )
        except FileNotFoundError as e:
            print(f"  ERROR not found: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"  ERROR {fp}: {exc}", file=sys.stderr)
            raise

        if args.dry_run:
            continue

        # Apply PUA rewrite to the just-written JSON
        data = json.loads(out_path.read_text(encoding="utf-8"))
        n = rewrite_gname_lookup_pua_values(data)
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if n:
            print(f"  PUA rewrite: {n} rows updated for key={key!r}")


if __name__ == "__main__":
    _pua_main()
