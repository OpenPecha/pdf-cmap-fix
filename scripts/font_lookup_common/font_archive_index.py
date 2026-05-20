"""
Build ``font_lookup_key -> {zip, member}`` from the same zip list used for
per-font lookup builds. Later zips win on duplicate keys (same rule as
``build_per_font_gid_maps``).

Imported by ``scripts/pua/gshape/``, ``scripts/pua/gid/``, and the PUA batch
orchestration scripts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
REPO_ROOT = _SCRIPTS.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from font_sources import iter_fonts_from_zip  # noqa: E402
from gid_map import normalise_name  # noqa: E402


def _font_internal_names(font: TTFont) -> list[str]:
    names: list[str] = []
    try:
        name_table = font["name"]
    except Exception:
        return names
    for nameid in (6, 4, 1):
        try:
            rec = name_table.getDebugName(nameid)
        except Exception:
            rec = None
        if rec:
            names.append(rec)
    return names


def resolve_font_key(label: str, font: TTFont) -> str:
    key = normalise_name(label)
    if key:
        return key
    for cand in _font_internal_names(font):
        k2 = normalise_name(cand)
        if k2:
            return k2
    digest = hashlib.sha1(label.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"font_{digest}"


def build_archive_key_index(zips: list[Path]) -> dict[str, dict[str, str]]:
    """Returns mapping ``key -> {"zip": str, "member": str}`` (absolute zip path strings)."""
    out: dict[str, dict[str, str]] = {}
    for zp in zips:
        zp = zp.resolve()
        if not zp.is_file():
            continue
        for entry, data in iter_fonts_from_zip(zp):
            try:
                font = TTFont(io.BytesIO(data), lazy=False)
            except Exception:
                continue
            try:
                key = resolve_font_key(entry, font)
            finally:
                font.close()
            out[key] = {"zip": str(zp), "member": entry}
    return out


def default_zip_paths() -> list[Path]:
    """Preferred: ``fonts/<name>.zip`` at repo root; falls back to ``scripts/<name>.zip``."""
    names = ("bodyig.zip", "tibetan-fonts-main.zip", "tibetan-fonts-private-main.zip")
    fonts_dir = REPO_ROOT / "fonts"
    scripts_dir = REPO_ROOT / "scripts"
    resolved: list[Path] = []
    for n in names:
        p_fonts = fonts_dir / n
        p_scripts = scripts_dir / n
        if p_fonts.is_file():
            resolved.append(p_fonts)
        elif p_scripts.is_file():
            resolved.append(p_scripts)
        else:
            resolved.append(p_fonts)
    return resolved


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--zip",
        action="append",
        default=[],
        type=Path,
        help="Zip path (repeatable); default: fonts/*.zip then scripts/*.zip",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "docs" / "build" / "font_archive_key_index.json",
        help="Write JSON index",
    )
    args = p.parse_args(argv)
    zips = [Path(z).expanduser().resolve() for z in args.zip] if args.zip else default_zip_paths()
    idx = build_archive_key_index(zips)
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "zips": [str(z) for z in zips],
        "count": len(idx),
        "keys": idx,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Indexed {len(idx)} font keys from {len(zips)} zips -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
