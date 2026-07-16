#!/usr/bin/env python3
"""
Bulk-fix PDF ToUnicode CMaps for an entire folder tree.

Usage
-----
    # Safe default: writes <name>.patched.pdf next to each original
    python bulk_fix_pdfs.py "D:\\monlam_dharmaduta\\task\\archive_filtered_pdf\\IE3CN26447"

    # Mirror the tree into a separate output folder (originals untouched)
    python bulk_fix_pdfs.py INPUT_DIR --output-dir OUTPUT_DIR

    # Overwrite originals in place (keeps a .bak.pdf backup unless --no-backup)
    python bulk_fix_pdfs.py INPUT_DIR --in-place

    # See what would happen without writing anything
    python bulk_fix_pdfs.py INPUT_DIR --dry-run

    # Skip auto-detection and force one tier (much faster if you already know
    # the font family, e.g. gid works for Monlam/Himalaya/Jomolhari)
    python bulk_fix_pdfs.py INPUT_DIR --strategy gid

Note on speed: --strategy auto (the default) scores every PDF against all six
bundled lookup strategies before picking the best one, which is thorough but
slow on large archives. If you know the font family already, pass an explicit
--strategy (gid, gid-pua-free, gname, gname-pua-free, gshape, gshape-pua-free)
to skip that scoring step and go much faster.

Run from the repo root (or after `pip install -e .` / `pip install
git+https://github.com/OpenPecha/pdf-cmap-fix.git`) so `pdf_cmap_fix` is
importable.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
import time
from pathlib import Path

try:
    from pdf_cmap_fix import tounicode_core as core
    from pdf_cmap_fix.gid.extractor import FONT_LOOKUP_DIR as GID_LOOKUP_DIR
except ImportError:
    sys.exit(
        "Could not import pdf_cmap_fix. Install it first, e.g.:\n"
        "  pip install -e .\n"
        "or run this script from the repository root with the venv active."
    )

STRATEGY_SPECS = core._default_strategy_specs(GID_LOOKUP_DIR)  # noqa: SLF001
STRATEGY_CHOICES = ["auto", *STRATEGY_SPECS]

REPORT_FIELDS = [
    "relative_path",
    "status",
    "strategy",
    "fonts_seen",
    "patched",
    "upgrades",
    "no_change",
    "no_match",
    "output_path",
    "elapsed_s",
    "error",
]


def find_pdfs(root: Path) -> list[Path]:
    """All *.pdf under root, skipping anything this tool already generated."""
    pdfs = []
    for p in root.rglob("*.pdf"):
        if p.name.endswith(".patched.pdf") or p.name.endswith(".bak.pdf"):
            continue
        pdfs.append(p)
    return sorted(pdfs)


def resolve_output_path(pdf_path: Path, root: Path, args: argparse.Namespace) -> Path:
    if args.in_place:
        return pdf_path
    if args.output_dir:
        rel = pdf_path.relative_to(root)
        out = Path(args.output_dir) / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    return pdf_path.with_name(f"{pdf_path.stem}.patched.pdf")


def fix_one(pdf_path: Path, root: Path, args: argparse.Namespace) -> dict:
    row = {f: "" for f in REPORT_FIELDS}
    row["relative_path"] = str(pdf_path.relative_to(root))
    start = time.time()

    out_path = resolve_output_path(pdf_path, root, args)

    if args.skip_existing and not args.in_place and out_path.exists():
        row["status"] = "skipped (exists)"
        row["output_path"] = str(out_path)
        return row

    if args.dry_run:
        row["status"] = "dry-run"
        row["output_path"] = str(out_path)
        return row

    try:
        if args.strategy == "auto":
            strategy_name, tier, lookup_dir, _ = core._select_auto_strategy(  # noqa: SLF001
                pdf_path, strategies=STRATEGY_SPECS, verbose=False
            )
        else:
            strategy_name = args.strategy
            tier, lookup_dir = STRATEGY_SPECS[args.strategy]

        if args.in_place and not args.no_backup:
            backup = pdf_path.with_suffix(".bak.pdf")
            if not backup.exists():
                shutil.copy2(pdf_path, backup)

        result = core.patch_pdf(
            pdf_path,
            output_path=out_path,
            lookup_dir=lookup_dir,
            tier=tier,
            verbose=False,
        )
        stats = result["stats"]
        row.update(
            status="ok",
            strategy=strategy_name,
            fonts_seen=stats["fonts_seen"],
            patched=stats["patched"],
            upgrades=stats["upgrades"],
            no_change=stats["no_change"],
            no_match=stats["no_match"],
            output_path=str(result["output_path"]),
        )
    except Exception as exc:  # noqa: BLE001 - one bad PDF must not kill the batch
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"

    row["elapsed_s"] = f"{time.time() - start:.2f}"
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir", type=Path, help="Root folder to scan recursively for PDFs")
    out_group = ap.add_mutually_exclusive_group()
    out_group.add_argument("--output-dir", type=Path, help="Mirror the folder tree here; originals untouched")
    out_group.add_argument("--in-place", action="store_true", help="Overwrite each original PDF")
    ap.add_argument("--no-backup", action="store_true", help="With --in-place, skip writing a .bak.pdf copy")
    ap.add_argument("--strategy", choices=STRATEGY_CHOICES, default="auto", help="Default: auto (best of all tiers)")
    ap.add_argument("--skip-existing", action="store_true", help="Skip files whose output already exists")
    ap.add_argument("--dry-run", action="store_true", help="List what would happen; write nothing")
    ap.add_argument("--report", type=Path, default=None, help="CSV report path (default: alongside input_dir)")
    args = ap.parse_args()

    root = args.input_dir.resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    pdfs = find_pdfs(root)
    if not pdfs:
        sys.exit(f"No PDFs found under {root}")

    report_path = args.report or (root.parent / f"{root.name}_fix_report.csv")

    print(f"Found {len(pdfs)} PDF(s) under {root}")
    if args.in_place:
        print("Mode: IN-PLACE" + (" (no backup)" if args.no_backup else " (with .bak.pdf backup)"))
    elif args.output_dir:
        print(f"Mode: mirrored output -> {args.output_dir.resolve()}")
    else:
        print("Mode: sibling *.patched.pdf files (originals untouched)")
    if args.dry_run:
        print("DRY RUN -- nothing will be written")

    rows = []
    ok = failed = skipped = 0
    t0 = time.time()
    for i, pdf_path in enumerate(pdfs, 1):
        rel = pdf_path.relative_to(root)
        print(f"[{i}/{len(pdfs)}] {rel} ...", end=" ", flush=True)
        row = fix_one(pdf_path, root, args)
        rows.append(row)
        status = row["status"]
        if status == "ok":
            ok += 1
            print(f"ok  strategy={row['strategy']} patched={row['patched']} upgrades={row['upgrades']}")
        elif status == "error":
            failed += 1
            print(f"ERROR: {row['error']}")
        else:
            skipped += 1
            print(status)

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s -- ok: {ok}  failed: {failed}  skipped: {skipped}")
    print(f"Report: {report_path}")
    if failed:
        print(f"\n{failed} file(s) failed -- see the 'error' column in the report.")


if __name__ == "__main__":
    main()
