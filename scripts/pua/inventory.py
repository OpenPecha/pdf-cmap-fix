"""
Scan tier-1 / tier-2 / tier-3 font lookup JSON trees for BMP or supplementary PUA in values.

Writes a manifest (JSON) listing per-stem counts for keys that need PUA remediation.

Usage::

    python scripts/pua/inventory.py
    python scripts/pua/inventory.py --out docs/build/font_lookup_pua_manifest.json
    python scripts/pua/inventory.py --verify-dir pdf_cmap_fix/data/font_lookup_gshape_pua_free
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent  # scripts/
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

REPO_ROOT = _SCRIPTS.parent
DEFAULT_DATA = REPO_ROOT / "pdf_cmap_fix" / "data"

from pua_utils import count_pua_in_lookup_json  # noqa: E402


def scan_dir(label: str, root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.glob("*.json")):
        if path.name == "_manifest.json":
            continue
        try:
            pua_n, total, bmp_n = count_pua_in_lookup_json(path)
        except (OSError, json.JSONDecodeError) as e:
            rows.append(
                {
                    "stem": path.stem,
                    "tier": label,
                    "path": str(path.relative_to(REPO_ROOT)),
                    "error": str(e),
                }
            )
            continue
        if pua_n == 0:
            continue
        rows.append(
            {
                "stem": path.stem,
                "tier": label,
                "path": str(path.relative_to(REPO_ROOT)),
                "rows_with_pua": pua_n,
                "rows_bmp_pua": bmp_n,
                "total_string_rows": total,
            }
        )
    return rows


def verify_dir(root: Path) -> tuple[int, list[str]]:
    """Return (bad_count, messages) for any remaining PUA in *root*."""
    bad: list[str] = []
    if not root.is_dir():
        return 0, [f"not a directory: {root}"]
    for path in sorted(root.glob("*.json")):
        if path.name == "_manifest.json":
            continue
        try:
            pua_n, _, _ = count_pua_in_lookup_json(path)
        except (OSError, json.JSONDecodeError) as e:
            bad.append(f"{path}: {e}")
            continue
        if pua_n:
            bad.append(f"{path}: {pua_n} rows still contain PUA")
    return len(bad), bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA,
        help="pdf_cmap_fix/data (default)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write manifest JSON (default: print summary only)",
    )
    p.add_argument(
        "--verify-dir",
        type=Path,
        default=None,
        help="If set, scan this directory only and exit 1 if any PUA remains",
    )
    args = p.parse_args(argv)

    if args.verify_dir is not None:
        root = args.verify_dir.expanduser().resolve()
        n, msgs = verify_dir(root)
        for m in msgs:
            print(m)
        return 1 if n else 0

    root = args.data_root.expanduser().resolve()
    tiers = [
        ("gid", root / "font_lookup"),
        ("gname", root / "font_lookup_gname"),
        ("gshape", root / "font_lookup_gshape"),
    ]
    all_rows: list[dict[str, object]] = []
    for label, sub in tiers:
        found = scan_dir(label, sub)
        all_rows.extend(found)
        print(f"{label}: {len(found)} files with PUA (of scanned in {sub})")

    stems_with_pua = sorted({str(r["stem"]) for r in all_rows if "rows_with_pua" in r})
    try:
        dr = str(root.relative_to(REPO_ROOT))
    except ValueError:
        dr = str(root)
    manifest = {
        "data_root": dr,
        "files_with_pua": len(all_rows),
        "unique_stems": len(stems_with_pua),
        "stems": stems_with_pua,
        "details": all_rows,
    }
    if args.out:
        out = args.out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(f"Unique stems with PUA in any tier: {len(stems_with_pua)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
