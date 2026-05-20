"""
Windows-friendly pipeline: discover Jomolhari + Cambria, build local gshape lookup,
derive public gname from bundled tier-2 Jomolhari, patch gshape JSON, optionally run pdf-cmap-fix.

Uses per-user and system font directories for Jomolhari discovery (``*jomol*`` substring).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def discover_jomolhari() -> Path | None:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
    for base in (local, windir / "Fonts"):
        if not base.is_dir():
            continue
        for f in sorted(base.iterdir()):
            if "jomol" in f.name.lower() and f.suffix.lower() in (".ttf", ".otf"):
                return f
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "examples" / "sample" / "font_lookup_gshape_local",
    )
    p.add_argument(
        "--public-gname-out",
        type=Path,
        default=REPO_ROOT / "docs" / "examples" / "sample" / "jomolhari_gname_public_unicode.json",
    )
    p.add_argument("--pdf", type=Path, nargs="*", default=None, help="Run pdf-cmap-fix on these PDFs last")
    p.add_argument("--skip-gshape-build", action="store_true")
    args = p.parse_args(argv)

    py = sys.executable
    jom = discover_jomolhari()
    if jom is None:
        print("No Jomolhari font found under LOCALAPPDATA or WINDIR Fonts.", file=sys.stderr)
        return 1
    cambria = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "cambria.ttc"
    if not cambria.is_file():
        print(f"Cambria not found: {cambria}", file=sys.stderr)
        return 1

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    bundled_gname = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gname" / "jomolhari.json"
    if not bundled_gname.is_file():
        print(f"Missing bundled gname (build tier-2 first): {bundled_gname}", file=sys.stderr)
        return 1

    if not args.skip_gshape_build:
        subprocess.run(
            [
                py,
                str(SCRIPTS / "gid" / "update_font_lookup.py"),
                "--kind",
                "gshape",
                "--lookup-dir",
                str(out_dir),
                "--ttc-index",
                "0",
                str(jom),
                str(cambria),
            ],
            cwd=str(REPO_ROOT),
            check=True,
        )

    pub = args.public_gname_out.expanduser().resolve()
    pub.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            py,
            str(SCRIPTS / "misc" / "inspect_pua_gname.py"),
            str(bundled_gname),
            "--rewrite-lookup",
            str(pub),
        ],
        cwd=str(REPO_ROOT),
        check=True,
    )

    # Rebuild jomolhari gshape from scratch and patch with the public gname JSON.
    subprocess.run(
        [
            py,
            str(SCRIPTS / "pua" / "gshape" / "update_pua_free_gshape.py"),
            "--lookup-dir",
            str(out_dir),
            "--gname-json",
            str(pub),
            str(jom),
        ],
        cwd=str(REPO_ROOT),
        check=True,
    )

    if args.pdf:
        for pdf in args.pdf:
            subprocess.run(
                [
                    py,
                    "-m",
                    "pdf_cmap_fix",
                    "--font-lookup-dir",
                    str(out_dir),
                    str(pdf.expanduser().resolve()),
                ],
                cwd=str(REPO_ROOT),
                check=True,
            )

    print("Pipeline OK:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
