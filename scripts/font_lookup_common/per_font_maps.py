"""
Shared bulk builder: one JSON per font from ZIP archives and/or font directories.

Used by tier bulk scripts under ``scripts/gid/``, ``scripts/gname/``, and ``scripts/gshape/`` with a fixed ``lookup_kind``.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
REPO_ROOT = _SCRIPTS.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from gid_map import (  # noqa: E402
    build_gid_map,
    gsub_lookup_type_counts,
    normalise_name,
)
from font_lookup_payload import build_lookup_json_payload  # noqa: E402
from font_sources import iter_fonts_from_dir, iter_fonts_from_zip  # noqa: E402


@dataclass
class Manifest:
    out_dir: Path
    lookup_kind: str = "gid"
    fonts_written: list[str] = field(default_factory=list)
    duplicates: list[tuple[str, str, str]] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def write(self) -> None:
        path = self.out_dir / "_manifest.json"
        unique = sorted(set(self.fonts_written))
        payload = {
            "lookup_kind": self.lookup_kind,
            "fonts_written": unique,
            "count": len(unique),
            "attempts": len(self.fonts_written),
            "duplicates": [
                {"key": k, "previous_source": prev, "new_source": new}
                for k, prev, new in self.duplicates
            ],
            "errors": [
                {"source": src, "error": err} for src, err in self.errors
            ],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _font_internal_names(font: TTFont) -> list[str]:
    """Return candidate names from the font's ``name`` table, best first."""
    names: list[str] = []
    try:
        name_table = font["name"]
    except Exception:
        return names
    for nameid in (6, 4, 1):  # PostScript, Full Name, Family
        try:
            rec = name_table.getDebugName(nameid)
        except Exception:
            rec = None
        if rec:
            names.append(rec)
    return names


def _resolve_font_key(label: str, font: TTFont) -> str:
    """Pick a non-empty, filesystem-safe key for *label* / *font*."""
    key = normalise_name(label)
    if key:
        return key
    for cand in _font_internal_names(font):
        k2 = normalise_name(cand)
        if k2:
            return k2
    digest = hashlib.sha1(label.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"font_{digest}"


def _build_gid_map_safe(
    font: TTFont, source_id: str
) -> tuple[dict[int, str], dict[str, int], list[str]]:
    """Run :func:`build_gid_map` with a graceful retry if GSUB is corrupt."""
    warnings: list[str] = []
    try:
        gid_map = build_gid_map(font)
        counts = gsub_lookup_type_counts(font)
        return gid_map, counts, warnings
    except Exception as exc:
        warnings.append(f"GSUB unreadable ({exc!r}); retrying cmap-only")
        try:
            if "GSUB" in font:
                del font["GSUB"]
        except Exception:
            pass
        gid_map = build_gid_map(font)
        return gid_map, {}, warnings


def _process_font(
    label: str,
    source_id: str,
    font: TTFont,
    out_dir: Path,
    seen: dict[str, str],
    manifest: Manifest,
    *,
    kind: str = "gid",
    pua_postprocess_fn: "Callable[[dict], int] | None" = None,
) -> None:
    key = _resolve_font_key(label, font)
    if key in seen:
        manifest.duplicates.append((key, seen[key], source_id))
        print(f"  WARN duplicate key {key!r}: {seen[key]} -> {source_id}")
    seen[key] = source_id

    short = Path(label).name
    print(f"  {short} … ", end="", flush=True)
    try:
        gid_map, counts_int, warnings = _build_gid_map_safe(font, source_id)
        for w in warnings:
            print(f"\n    WARN {w}")
            manifest.errors.append((source_id, w))
        payload = build_lookup_json_payload(
            font=font,
            key=key,
            gid_map=gid_map,
            counts_int=counts_int,
            kind=kind,
            source_id=source_id,
        )
        if pua_postprocess_fn is not None:
            pua_rows = pua_postprocess_fn(payload)
        else:
            pua_rows = 0
        inner = payload[key]
        multi = payload["_meta"]["multi_char_stacks"]
        counts = payload["_meta"]["gsub_lookup_counts"]
        out_path = out_dir / f"{key}.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.fonts_written.append(key)
        pua_note = f", pua_rewritten={pua_rows}" if pua_rows else ""
        print(
            f"{len(gid_map)} GIDs, inner={len(inner)}, {multi} multi-char, "
            f"GSUB={counts or '{}'}{pua_note}, wrote {out_path.name}"
        )
    except Exception as exc:
        manifest.errors.append((source_id, str(exc)))
        print(f"ERROR: {exc}")


def build_per_font(
    zips: list[Path],
    font_dirs: list[Path],
    out_dir: Path,
    *,
    kind: str = "gid",
    pua_postprocess_fn: "Callable[[dict], int] | None" = None,
) -> Manifest:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(out_dir=out_dir, lookup_kind=kind)
    seen: dict[str, str] = {}

    for zp in zips:
        if not zp.is_file():
            print(f"SKIP (not a file): {zp}", file=sys.stderr)
            continue
        print(f"\n== Zip: {zp} ==")
        for entry, data in iter_fonts_from_zip(zp):
            source_id = f"{zp.name}::{entry}"
            try:
                font = TTFont(io.BytesIO(data), lazy=False)
            except Exception as exc:
                print(f"  ERROR opening {entry}: {exc}")
                manifest.errors.append((source_id, str(exc)))
                continue
            try:
                _process_font(
                    entry, source_id, font, out_dir, seen, manifest,
                    kind=kind, pua_postprocess_fn=pua_postprocess_fn,
                )
            finally:
                font.close()

    for d in font_dirs:
        if not d.is_dir():
            print(f"SKIP (not a directory): {d}", file=sys.stderr)
            continue
        print(f"\n== Directory: {d} ==")
        for path, _ in iter_fonts_from_dir(d):
            source_id = str(path)
            try:
                font = TTFont(str(path), lazy=False)
            except Exception as exc:
                print(f"  ERROR opening {path}: {exc}")
                manifest.errors.append((source_id, str(exc)))
                continue
            try:
                _process_font(
                    str(path), source_id, font, out_dir, seen, manifest,
                    kind=kind, pua_postprocess_fn=pua_postprocess_fn,
                )
            finally:
                font.close()

    return manifest


def run_per_font_cli(
    argv: list[str] | None,
    *,
    kind: str,
    default_out: Path,
    description: str,
    example_invocation: str,
    pua_postprocess_fn: "Callable[[dict], int] | None" = None,
) -> None:
    """Run the per-font bulk builder CLI.

    ``pua_postprocess_fn`` — if provided, called on each payload dict *before*
    writing.  Should mutate the dict in-place and return the number of rows
    changed.  Used by PUA-free gname bulk scripts.
    """
    p = argparse.ArgumentParser(
        description=description,
    )
    p.add_argument(
        "--zip",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="Zip file containing fonts (repeatable).",
    )
    p.add_argument(
        "--fonts-dir",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="Directory to scan recursively for .ttf / .otf (repeatable).",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory for per-font JSON (default: tier-specific under pdf_cmap_fix/data/).",
    )
    args = p.parse_args(argv)
    zips: list[Path] = list(args.zip)
    font_dirs: list[Path] = list(args.fonts_dir)
    if not zips and not font_dirs:
        sys.exit(
            "Provide at least one --zip or --fonts-dir. Example:\n  " + example_invocation
        )

    out_dir = (args.output_dir or default_out).resolve()

    manifest = build_per_font(zips, font_dirs, out_dir, kind=kind, pua_postprocess_fn=pua_postprocess_fn)
    manifest.write()
    unique_count = len(set(manifest.fonts_written))
    print(
        f"\nWrote {unique_count} unique per-font JSON files under "
        f"{manifest.out_dir} ({len(manifest.fonts_written)} attempts)."
    )
    if manifest.duplicates:
        print(f"Duplicates (later won): {len(manifest.duplicates)}")
    if manifest.errors:
        print(f"Errors / warnings: {len(manifest.errors)}")
