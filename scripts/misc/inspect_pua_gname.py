"""
Inspect and analyse PUA content in a tier-2 ``font_lookup_gname`` JSON.

Rows whose glyph name matches AGL-style ``uni`` + 4-hex-digit chunks encode the
intended Unicode sequence in the *name*. When the JSON *value* uses BMP PUA
(``U+E000``–``U+F8FF``) or supplementary PUA planes and differs from that parse,
we record ``value -> parsed_from_name`` for post-processing extracted text.

Core logic lives in ``scripts/font_lookup_common/pua_gname_rewriter.py``.
To build a PUA-free gname JSON from fonts directly, use ``scripts/pua/gname/``.

Usage (repo root)::

    python scripts/misc/inspect_pua_gname.py pdf_cmap_fix/data/font_lookup_gname/jomolhari.json
    python scripts/misc/inspect_pua_gname.py path/to/font.json --test-text "༧ང་"

    # Preview 30 rows + write full map (PUA string → standard string) as JSON
    python scripts/misc/inspect_pua_gname.py pdf_cmap_fix/data/font_lookup_gname/jomolhari.json \\
        --preview 30 --write-map docs/examples/sample/pua_map_jomolhari.json

    # Write a **new** gname JSON where PUA values are replaced by Unicode from ``uni…`` names
    python scripts/misc/inspect_pua_gname.py pdf_cmap_fix/data/font_lookup_gname/jomolhari.json \\
        --rewrite-lookup out/jomolhari_gname_no_pua.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
_COMMON = _SCRIPTS / "font_lookup_common"
for _d in (_COMMON,):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from pua_gname_rewriter import (  # noqa: E402
    apply_pua_map,
    build_pua_map,
    decode_uni_glyph_name,
    load_full_lookup,
    load_inner,
    rewrite_gname_lookup_pua_values,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("json_path", type=Path, help="font_lookup_gname/*.json")
    p.add_argument(
        "--test-text",
        type=str,
        default=None,
        metavar="STR",
        help="Apply PUA→Unicode map to this string and print before/after",
    )
    p.add_argument(
        "--max-collisions",
        type=int,
        default=12,
        help="How many collision lines to print (default 12)",
    )
    p.add_argument(
        "--preview",
        type=int,
        default=0,
        metavar="N",
        help="Print first N PUA→Unicode rows (codepoint hex + repr)",
    )
    p.add_argument(
        "--write-map",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write full map as JSON array of {pua, pua_codepoints, unicode, unicode_codepoints}",
    )
    p.add_argument(
        "--rewrite-lookup",
        type=Path,
        default=None,
        metavar="OUT",
        help="Read gname JSON, replace PUA inner values using uni-name decode, write OUT",
    )
    args = p.parse_args(argv)

    path = args.json_path.expanduser().resolve()
    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        return 1

    inner = load_inner(path)
    m, collisions = build_pua_map(inner)

    uni_named = sum(1 for g in inner if decode_uni_glyph_name(g) is not None)
    print(f"File: {path}")
    print(f"Inner entries: {len(inner)}")
    print(f"Decodable uni* glyph names: {uni_named}")
    print(f"PUA→standard map entries: {len(m)}")
    print(f"Collisions (same PUA value, different parse): {len(collisions)}")
    for row in collisions[: max(0, args.max_collisions)]:
        val, a, b, gname = row
        print(f"  collision val={val!r} was {a!r} also {b!r} (gname {gname})")

    if args.rewrite_lookup is not None:
        full = load_full_lookup(path)
        n = rewrite_gname_lookup_pua_values(full)
        out_rw = args.rewrite_lookup.expanduser().resolve()
        out_rw.parent.mkdir(parents=True, exist_ok=True)
        out_rw.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
        print()
        print(f"Rewrote {n} glyph rows (PUA → Unicode from uni* names). Wrote {out_rw}")
        if collisions:
            print(f"WARN: {len(collisions)} collisions in map build (should be 0)", file=sys.stderr)

    if args.preview > 0:
        print()
        print(f"Preview (first {args.preview} entries, sorted by PUA U+ hex):")
        rows = sorted(m.items(), key=lambda kv: [ord(c) for c in kv[0]])
        for pua_s, uni_s in rows[: args.preview]:
            pua_pts = " ".join(f"U+{ord(c):04X}" for c in pua_s)
            uni_pts = " ".join(f"U+{ord(c):04X}" for c in uni_s)
            print(f"  {pua_pts}")
            print(f"    -> {uni_pts}  | repr: {uni_s!r}")

    if args.write_map is not None:
        out_path = args.write_map.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rows_out = []
        for pua_s, uni_s in sorted(m.items(), key=lambda kv: [ord(c) for c in kv[0]]):
            rows_out.append(
                {
                    "pua": pua_s,
                    "pua_codepoints": [ord(c) for c in pua_s],
                    "unicode": uni_s,
                    "unicode_codepoints": [ord(c) for c in uni_s],
                }
            )
        out_path.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print()
        print(f"Wrote {len(rows_out)} map rows to {out_path}")

    if args.test_text is not None:
        t = args.test_text
        after = apply_pua_map(t, m)
        print()
        print("Test --test-text")
        print(f"  before ({len(t)} chars): {t!r}")
        print(f"  after  ({len(after)} chars): {after!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
