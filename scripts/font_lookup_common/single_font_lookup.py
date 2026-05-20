"""
Shared implementation for per-tier ``update_font_lookup.py`` CLIs under
``scripts/gid/``, ``scripts/gname/``, and ``scripts/gshape/``.

Uses the same cmap + GSUB pipeline as ``per_font_maps.py`` (``gid_map`` +
``_build_gid_map_safe``): cmap + GSUB types 1, 2, 4 with Extension 7 unwrapped.
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

REPO_ROOT = Path(__file__).resolve().parents[2]

from font_lookup_payload import build_lookup_json_payload  # noqa: E402
from per_font_maps import (  # noqa: E402
    _build_gid_map_safe,
    _resolve_font_key,
)

DEFAULT_LOOKUP_DIR = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup"
DEFAULT_LOOKUP_DIR_GNAME = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gname"
DEFAULT_LOOKUP_DIR_GSHAPE = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gshape"


def _default_lookup_dir_for_kind(kind: str) -> Path:
    if kind == "gname":
        return DEFAULT_LOOKUP_DIR_GNAME
    if kind == "gshape":
        return DEFAULT_LOOKUP_DIR_GSHAPE
    return DEFAULT_LOOKUP_DIR


def default_windows_himalaya_path() -> Path:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    return Path(windir) / "Fonts" / "himalaya.ttf"


def _write_one(
    font_path: Path,
    lookup_dir: Path,
    key_override: str | None,
    output_file: Path | None,
    dry_run: bool,
    *,
    ttc_index: int | None = None,
    kind: str = "gid",
) -> tuple[Path, str, bool]:
    """Returns (written_path, key, existed_before)."""
    font_path = font_path.resolve()
    if not font_path.is_file():
        raise FileNotFoundError(font_path)

    suffix = font_path.suffix.lower()
    font = None
    try:
        if suffix == ".ttc":
            fn = 0 if ttc_index is None else ttc_index
            font = TTFont(str(font_path), lazy=False, fontNumber=fn)
            source_id = f"{font_path}::{fn}"
        else:
            font = TTFont(str(font_path), lazy=False)
            source_id = str(font_path)
        gid_map, counts_int, warnings = _build_gid_map_safe(font, source_id)

        key = key_override if key_override else _resolve_font_key(str(font_path), font)

        if output_file is not None:
            out_path = output_file.resolve()
        else:
            out_path = lookup_dir / f"{key}.json"

        existed = out_path.is_file()

        payload = build_lookup_json_payload(
            font=font,
            key=key,
            gid_map=gid_map,
            counts_int=counts_int,
            kind=kind,
            source_id=source_id,
        )
        inner = payload[key]
        for w in warnings:
            print(f"  WARN {font_path.name}: {w}", file=sys.stderr)

        if dry_run:
            action = "would update" if existed else "would create"
            print(
                f"  [{action}] {out_path.name}  key={key!r}  kind={kind}  "
                f"gids_in_map={len(gid_map)}  inner_keys={len(inner)}"
            )
            return out_path, key, existed

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        kb = max(1, out_path.stat().st_size // 1024)
        action = "Updated" if existed else "Created"
        print(
            f"  {action} {out_path}  ({kb} KB)  key={key!r}  kind={kind}  "
            f"inner_keys={len(inner)}"
        )
        return out_path, key, existed
    finally:
        if font is not None:
            try:
                font.close()
            except Exception:
                pass


def main_for_kind(kind: str, argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=(
            f"Create or refresh per-font JSON (``lookup_kind`` = ``{kind}``) from "
            "``.ttf`` / ``.otf`` / ``.ttc``."
        ),
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
        default=None,
        metavar="DIR",
        help="Directory for <key>.json (default: pdf_cmap_fix/data font_lookup tree for this tier)",
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
    p.add_argument(
        "--ttc-index",
        type=int,
        default=None,
        metavar="N",
        help="For .ttc collections only: face index (0-based). Default 0 if omitted and path ends with .ttc",
    )
    args = p.parse_args(argv)

    fonts: list[Path] = list(args.fonts)
    if not fonts:
        fonts = [default_windows_himalaya_path()]

    if args.key is not None and len(fonts) != 1:
        sys.exit("--key requires exactly one font path")

    if args.output is not None and len(fonts) != 1:
        sys.exit("--output / -o requires exactly one font path")

    lookup_dir = (
        args.lookup_dir.resolve()
        if args.lookup_dir is not None
        else _default_lookup_dir_for_kind(kind).resolve()
    )

    print(f"Font lookup directory: {lookup_dir}  (kind={kind})")
    for fp in fonts:
        print(f"\nProcessing: {fp}")
        ttc_idx = args.ttc_index
        if ttc_idx is None and fp.suffix.lower() == ".ttc":
            ttc_idx = 0
        try:
            _write_one(
                fp,
                lookup_dir,
                args.key,
                args.output,
                args.dry_run,
                ttc_index=ttc_idx if fp.suffix.lower() == ".ttc" else None,
                kind=kind,
            )
        except FileNotFoundError as e:
            print(f"  ERROR not found: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"  ERROR {fp}: {exc}", file=sys.stderr)
            raise
