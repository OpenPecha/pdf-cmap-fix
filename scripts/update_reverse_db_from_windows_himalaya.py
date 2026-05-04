"""
Update bundled reverse_db.json using Windows Microsoft Himalaya.

Loads ``%WINDIR%\\Fonts\\himalaya.ttf`` (override with ``--font``), rebuilds the
GID→Unicode map with the same logic as ``build_reverse_db.py``, and replaces
only the normalised key ``himalaya`` in ``pdf_cmap_fix/data/reverse_db.json``.
All other font entries are left unchanged.

Requires: pip install fonttools

Does **not** copy the TTF into the repo; reads the system font path directly.

Usage::

    python scripts/update_reverse_db_from_windows_himalaya.py
    python scripts/update_reverse_db_from_windows_himalaya.py --font "D:\\Fonts\\himalaya.ttf"
    python scripts/update_reverse_db_from_windows_himalaya.py -o out.json
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

from build_reverse_db import build_gid_map, normalise_name  # noqa: E402

REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_DB = REPO_ROOT / "pdf_cmap_fix" / "data" / "reverse_db.json"


def default_windows_himalaya_path() -> Path:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    return Path(windir) / "Fonts" / "himalaya.ttf"


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--font",
        type=Path,
        default=None,
        metavar="PATH",
        help=f"path to himalaya.ttf (default: {default_windows_himalaya_path()})",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_DB,
        metavar="PATH",
        help=f"reverse_db.json to write (default: {DEFAULT_DB})",
    )
    args = p.parse_args(argv)

    font_path = args.font if args.font is not None else default_windows_himalaya_path()
    font_path = font_path.resolve()
    if not font_path.is_file():
        sys.exit(f"Font not found: {font_path}")

    out_path = args.output.resolve()
    if not out_path.is_file():
        sys.exit(f"reverse_db.json not found: {out_path}")

    print(f"Reading font: {font_path}")
    font = TTFont(str(font_path), lazy=False)
    gid_map = build_gid_map(font)
    key = normalise_name(str(font_path))
    if key != "himalaya":
        print(f"WARN: normalised stem is {key!r}, expected 'himalaya' — updating key {key!r}")

    rev_db = json.loads(out_path.read_text(encoding="utf-8"))
    rev_db[key] = {str(gid): uni for gid, uni in gid_map.items()}
    out_path.write_text(json.dumps(rev_db, ensure_ascii=False, indent=2), encoding="utf-8")

    kb = out_path.stat().st_size // 1024
    print(f"Updated key {key!r}: {len(rev_db[key])} GID entries")
    print(f"Total keys in DB: {len(rev_db)}")
    print(f"Wrote {out_path} ({kb} KB)")


if __name__ == "__main__":
    main()
