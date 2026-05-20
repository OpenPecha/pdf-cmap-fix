"""
Orchestrate the full PUA-free lookup rebuild:

  1. (Optional) Inventory existing lookup trees for PUA.
  2. Build ``font_lookup_gname_pua_free/`` from ZIP archives.
  3. Build ``font_lookup_gshape_pua_free/`` (requires step 2).
  4. (Optional) Build ``font_lookup_gid_pua_free/`` — pass ``--with-gid``.
  5. (Optional) Verify: exit 1 if any PUA remains.

Prerequisites: ZIP archives present under ``fonts/`` (bodyig.zip, tibetan-fonts-main.zip …).
Point at custom ZIPs with ``--zip``.

Example::

    python scripts/pua/run_all.py --with-gid
    python scripts/pua/run_all.py --dry-run
    python scripts/pua/run_all.py --zip fonts/bodyig.zip --with-gid
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="Pass --dry-run to batch steps where applicable")
    p.add_argument("--with-gid", action="store_true", help="Also build font_lookup_gid_pua_free/")
    p.add_argument(
        "--zip",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="ZIP archive to process (repeatable; default: fonts/ discovery)",
    )
    p.add_argument("--skip-inventory", action="store_true")
    p.add_argument("--skip-verify", action="store_true")
    args = p.parse_args(argv)

    py = sys.executable
    zip_flags = [flag for z in args.zip for flag in ("--zip", str(z))]

    if not args.skip_inventory:
        manifest = REPO_ROOT / "docs" / "build" / "font_lookup_pua_manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        _run([py, "scripts/pua/inventory.py", "--out", str(manifest)])

    # Step 1: gname PUA-free (must run first)
    _run([py, "scripts/pua/gname/build_pua_free_gname_maps.py", *zip_flags])

    data = REPO_ROOT / "pdf_cmap_fix" / "data"
    gname_dir = str(data / "font_lookup_gname_pua_free")

    # Step 2a: gshape PUA-free
    _run([
        py, "scripts/pua/gshape/build_pua_free_gshape_maps.py",
        *zip_flags,
        "--gname-dir", gname_dir,
    ])

    # Step 2b: gid PUA-free (optional)
    if args.with_gid:
        _run([
            py, "scripts/pua/gid/build_pua_free_gid_maps.py",
            *zip_flags,
            "--gname-dir", gname_dir,
        ])

    if not args.skip_verify:
        dirs = [
            str(data / "font_lookup_gname_pua_free"),
            str(data / "font_lookup_gshape_pua_free"),
        ]
        if args.with_gid:
            dirs.append(str(data / "font_lookup_gid_pua_free"))
        _run([py, "scripts/pua/verify.py", *dirs])

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
