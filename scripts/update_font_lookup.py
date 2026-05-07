"""
Create or refresh one or more ``font_lookup/<key>.json`` files from local ``.ttf`` / ``.otf``.

Uses the same GID→Unicode pipeline as ``build_per_font_gid_maps.py`` (``gid_map`` +
``_build_gid_map_safe``): cmap + GSUB types 1, 2, 4 with Extension 7 unwrapped.

- **New font:** resolves a normalised key (filename stem or ``name`` table), writes
  ``{lookup_dir}/{key}.json`` if missing.
- **Existing entry:** same path is overwritten when you point at a newer font build.

Requires: pip install fonttools

Examples::

    # Default: Windows Himalaya → pdf_cmap_fix/data/font_lookup/himalaya.json
    python scripts/update_font_lookup.py

    # One or more font files → one JSON each under font_lookup/
    python scripts/update_font_lookup.py D:\\Fonts\\MicrosoftHimalaya.ttf
    python scripts/update_font_lookup.py fonts/A.ttf fonts/B.otf

    # Custom package font_lookup directory
    python scripts/update_font_lookup.py --lookup-dir pdf_cmap_fix/data/font_lookup my.ttf

    # Force JSON key / filename stem (single font only), e.g. match PDF subset name
    python scripts/update_font_lookup.py --key microsofthimalaya path/to/MicrosoftHimalaya.ttf

    # Preview actions only
    python scripts/update_font_lookup.py --dry-run C:\\Windows\\Fonts\\himalaya.ttf
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_per_font_gid_maps import (  # noqa: E402
    _build_gid_map_safe,
    _resolve_font_key,
)

REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_LOOKUP_DIR = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup"


def default_windows_himalaya_path() -> Path:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    return Path(windir) / "Fonts" / "himalaya.ttf"


def _write_one(
    font_path: Path,
    lookup_dir: Path,
    key_override: str | None,
    output_file: Path | None,
    dry_run: bool,
) -> tuple[Path, str, bool]:
    """Returns (written_path, key, existed_before)."""
    font_path = font_path.resolve()
    if not font_path.is_file():
        raise FileNotFoundError(font_path)

    font = TTFont(str(font_path), lazy=False)
    source_id = str(font_path)
    gid_map, counts_int, warnings = _build_gid_map_safe(font, source_id)

    key = key_override if key_override else _resolve_font_key(str(font_path), font)

    if output_file is not None:
        out_path = output_file.resolve()
    else:
        out_path = lookup_dir / f"{key}.json"

    existed = out_path.is_file()

    multi = sum(1 for v in gid_map.values() if len(v) > 1)
    counts = {str(k): v for k, v in counts_int.items()}
    payload: dict = {
        key: {str(gid): uni for gid, uni in gid_map.items()},
        "_meta": {
            "source": source_id,
            "gids_mapped": len(gid_map),
            "multi_char_stacks": multi,
            "gsub_lookup_counts": counts,
        },
    }

    for w in warnings:
        print(f"  WARN {font_path.name}: {w}", file=sys.stderr)

    if dry_run:
        action = "would update" if existed else "would create"
        print(f"  [{action}] {out_path.name}  key={key!r}  gids={len(gid_map)}")
        return out_path, key, existed

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    kb = max(1, out_path.stat().st_size // 1024)
    action = "Updated" if existed else "Created"
    print(f"  {action} {out_path}  ({kb} KB)  key={key!r}  gids={len(gid_map)}")
    return out_path, key, existed


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "fonts",
        nargs="*",
        type=Path,
        metavar="FONT",
        help="One or more .ttf / .otf paths (default: %%WINDIR%%\\Fonts\\himalaya.ttf if omitted)",
    )
    p.add_argument(
        "--lookup-dir",
        type=Path,
        default=DEFAULT_LOOKUP_DIR,
        metavar="DIR",
        help=f"Directory for <key>.json (default: {DEFAULT_LOOKUP_DIR})",
    )
    p.add_argument(
        "--key",
        type=str,
        default=None,
        metavar="NAME",
        help="Force normalised key / filename stem (only with exactly one font)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="Exact output JSON path (only with exactly one font; overrides --lookup-dir name)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without writing",
    )
    args = p.parse_args(argv)

    fonts: list[Path] = list(args.fonts)
    if not fonts:
        fonts = [default_windows_himalaya_path()]

    if args.key is not None and len(fonts) != 1:
        sys.exit("--key requires exactly one font path")

    if args.output is not None and len(fonts) != 1:
        sys.exit("--output / -o requires exactly one font path")

    lookup_dir = args.lookup_dir.resolve()

    print(f"Font lookup directory: {lookup_dir}")
    for fp in fonts:
        print(f"\nProcessing: {fp}")
        try:
            _write_one(
                fp,
                lookup_dir,
                args.key,
                args.output,
                args.dry_run,
            )
        except FileNotFoundError as e:
            print(f"  ERROR not found: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"  ERROR {fp}: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
