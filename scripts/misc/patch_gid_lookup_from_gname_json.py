"""
Patch a tier-1 **GID** font lookup JSON using Unicode strings from a tier-2 **gname**
JSON (e.g. ``jomolhari_gname_public_unicode.json``).

For each decimal GID key, resolves the glyph name from a **full** ``.ttf`` / ``.ttc`` face
and replaces the stored Unicode when the gname table has an entry for that name.

Use when the PDF exposes **synthetic glyph names** (``glyph00001`` …) so gname lookup cannot
match, but you still want public Tibetan strings from a normalized gname file.

Example::

    python scripts/misc/patch_gid_lookup_from_gname_json.py \\
      --font \"$env:LOCALAPPDATA\\\\Microsoft\\\\Windows\\\\Fonts\\\\Jomolhari-Regular.ttf\" \\
      --gid-json docs/examples/sample/font_lookup_local_windows/jomolhariregular.json \\
      --gname-json docs/examples/sample/jomolhari_gname_public_unicode.json \\
      --out-key jomolhari \\
      --out docs/examples/sample/font_lookup_local_windows/jomolhari.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")


def _first_inner_map(data: dict) -> tuple[str, dict]:
    for k, v in data.items():
        if k == "_meta" or not isinstance(v, dict):
            continue
        return k, v
    raise ValueError("no inner map in JSON")


def patch_gid_lookup_with_gname_inner(
    *,
    font: TTFont,
    gid_key: str,
    gid_inner: dict,
    gname_inner: dict[str, str],
    out_key: str | None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Return ``(resolved_out_key, new_inner, meta_updates)``."""
    go = font.getGlyphOrder()
    resolved_out = out_key or gid_key
    patched_inner: dict[str, str] = {}
    changed = 0
    missing_gname = 0
    for gid_str, uni in gid_inner.items():
        if not isinstance(uni, str):
            continue
        try:
            gid = int(str(gid_str))
        except ValueError:
            continue
        if gid < 0 or gid >= len(go):
            patched_inner[str(gid_str)] = uni
            continue
        gname = go[gid]
        if gname in gname_inner:
            new_u = gname_inner[gname]
            if new_u != uni:
                changed += 1
            patched_inner[str(gid_str)] = new_u
        else:
            patched_inner[str(gid_str)] = uni
            missing_gname += 1
    meta_updates: dict[str, Any] = {
        "lookup_kind": "gid",
        "gid_rows_patched_from_gname_json": changed,
        "gid_patch_missing_gname_entries": missing_gname,
    }
    return resolved_out, patched_inner, meta_updates


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--font", type=Path, required=True, help="Full font file used when the GID JSON was built")
    p.add_argument("--gid-json", type=Path, required=True, help="Tier-1 JSON from scripts/gid/update_font_lookup.py")
    p.add_argument("--gname-json", type=Path, required=True, help="Tier-2 JSON (e.g. public-Unicode gname file)")
    p.add_argument("--out", type=Path, required=True, help="Output tier-1 JSON path")
    p.add_argument(
        "--out-key",
        type=str,
        default=None,
        help="Top-level / inner key for output (default: keep key from --gid-json)",
    )
    p.add_argument("--ttc-index", type=int, default=None, help="Face index if --font is .ttc")
    args = p.parse_args(argv)

    font_path = args.font.expanduser().resolve()
    if not font_path.is_file():
        print(f"Font not found: {font_path}", file=sys.stderr)
        return 1

    gid_data = json.loads(Path(args.gid_json).expanduser().resolve().read_text(encoding="utf-8"))
    gname_data = json.loads(Path(args.gname_json).expanduser().resolve().read_text(encoding="utf-8"))

    gid_key, gid_inner = _first_inner_map(gid_data)
    _, gname_inner = _first_inner_map(gname_data)

    suffix = font_path.suffix.lower()
    if suffix == ".ttc":
        fn = 0 if args.ttc_index is None else args.ttc_index
        font = TTFont(str(font_path), lazy=False, fontNumber=fn)
    else:
        font = TTFont(str(font_path), lazy=False)
    try:
        out_key, patched_inner, meta_updates = patch_gid_lookup_with_gname_inner(
            font=font,
            gid_key=gid_key,
            gid_inner=gid_inner,
            gname_inner=gname_inner,
            out_key=args.out_key,
        )
        go_len = len(font.getGlyphOrder())
    finally:
        font.close()

    meta = gid_data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
    meta = {**meta, **meta_updates}

    out_obj = {out_key: patched_inner, "_meta": meta}
    out_path = args.out.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"GID source key: {gid_key!r} -> output key: {out_key!r}")
    print(f"Glyph order length: {go_len}")
    print(f"GID entries written: {len(patched_inner)}")
    print(f"Patched (value changed): {meta_updates['gid_rows_patched_from_gname_json']}")
    print(f"GIDs with no gname-json entry (kept original): {meta_updates['gid_patch_missing_gname_entries']}")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
