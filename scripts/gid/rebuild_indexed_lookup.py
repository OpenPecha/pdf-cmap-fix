"""
Rebuild the tier-1 (GID -> Unicode) font-lookup database from local font
*source folders*, keyed by a **non-semantic content-hash font ID** instead of a
filename, and emit a separate ``_name_index.json`` that maps font names to those
IDs.

Why
---
The historical builder (``build_per_font_gid_maps.py``) keyed each per-font JSON
by ``normalise_name(filename)``. That made the matcher fuzzy-match PDF font
names against *filenames*, which is unreliable:

* a filename typo (``TibetanChosgyalUnicode 1.1.ttf`` -> ``tibetanchosgyalunicode11``)
  hides a font whose real PostScript name is ``TibetanChogyalUnicode``;
* short filename stems (``ma`` from ``MA______.TTF``) substring-match unrelated
  long PDF names (``TimesNewRomanPSMT``).

This script decouples the *identity* of a font (a content hash) from how it is
*looked up* (its name-table names). The name index records, per role
(``ps`` / ``full`` / ``family`` / ``filename``), which font IDs carry each
normalised name, so the matcher can prefer the PostScript name and fall back to
secondary names, and so several distinct fonts can legitimately share a name.

Output layout (under ``--out``)::

    <id>.json            one per unique font face (key is the content-hash ID)
    _name_index.json     { "ps": {norm: [id,...]}, "full": {...}, ... }
    _rebuild_manifest.json

Resumable
---------
A font whose ``<id>.json`` already exists is skipped (only its hash is
computed, which is cheap). Re-running after an interruption resumes where it
stopped. Pass ``--force`` to rebuild everything, or ``--index-only`` to just
regenerate ``_name_index.json`` from JSON already on disk.

Progress
--------
Prints ``[i/N]`` for every font face, plus a periodic summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Optional

try:
    from fontTools.ttLib import TTFont, TTLibError
    from fontTools.ttLib.ttCollection import TTCollection
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("pip install fonttools")

_SCRIPTS = Path(__file__).resolve().parent.parent
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

REPO_ROOT = _SCRIPTS.parent
DEFAULT_OUT = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_byid"
DEFAULT_ROOTS = [
    Path("/home/eroux/BUDA/softs/tibetan-fonts"),
    Path("/home/eroux/BUDA/softs/tibetan-fonts-private"),
]

from font_lookup_payload import build_lookup_json_payload  # noqa: E402
from per_font_maps import _build_gid_map_safe  # noqa: E402

_FONT_SUFFIXES = (".ttf", ".otf", ".ttc")
_NAME_ROLES = (("ps", 6), ("full", 4), ("family", 1))


def _norm_name(s: str) -> str:
    """Normalise a font *name-table* string (no path/stem handling)."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _iter_source_fonts(roots: list[Path]) -> Iterator[tuple[str, Path, Optional[int]]]:
    """Yield ``(source_id, path, ttc_index)`` for every font face under *roots*.

    ``source_id`` is the path relative to the root's *parent* (so it keeps the
    root folder name, e.g. ``tibetan-fonts/Unicode .../X.ttf``); a ``.ttc`` face
    gets a ``::<index>`` suffix.
    """
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            print(f"  SKIP (not a directory): {root}", file=sys.stderr)
            continue
        anchor = root.parent
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _FONT_SUFFIXES:
                continue
            # Skip macOS archive cruft: AppleDouble resource forks (``._x.ttf``)
            # and anything under a ``__MACOSX`` directory are not real fonts.
            if path.name.startswith("._") or "__MACOSX" in path.parts:
                continue
            rel = path.relative_to(anchor).as_posix()
            if path.suffix.lower() == ".ttc":
                try:
                    n = len(TTCollection(str(path)).fonts)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ERROR reading collection {rel}: {exc}", file=sys.stderr)
                    continue
                for i in range(n):
                    yield f"{rel}::{i}", path, i
            else:
                yield rel, path, None


def _font_id(path: Path, ttc_index: Optional[int]) -> str:
    """Content-hash font ID (stable, non-semantic). Dedups identical files."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    if ttc_index is not None:
        h.update(f"::{ttc_index}".encode("ascii"))
    return h.hexdigest()[:16]


def _open_font(path: Path, ttc_index: Optional[int]) -> TTFont:
    if ttc_index is not None:
        return TTFont(str(path), lazy=False, fontNumber=ttc_index)
    return TTFont(str(path), lazy=False)


def _collect_names(font: TTFont) -> list[dict[str, str]]:
    """Return ``[{role, raw, norm}]`` for PS / full / family names that exist."""
    out: list[dict[str, str]] = []
    try:
        name_table = font["name"]
    except Exception:  # noqa: BLE001
        return out
    seen: set[tuple[str, str]] = set()
    for role, nameid in _NAME_ROLES:
        try:
            raw = name_table.getDebugName(nameid)
        except Exception:  # noqa: BLE001
            raw = None
        if not raw:
            continue
        raw = raw.strip()
        norm = _norm_name(raw)
        if not norm or (role, norm) in seen:
            continue
        seen.add((role, norm))
        out.append({"role": role, "raw": raw, "norm": norm})
    return out


def _process_one(
    source_id: str,
    path: Path,
    ttc_index: Optional[int],
    out_dir: Path,
    *,
    force: bool,
) -> tuple[str, Optional[str]]:
    """Build (or skip) one font face. Returns ``(status, font_id)``.

    ``status`` is one of ``written`` / ``skipped`` / ``error``.
    """
    try:
        font_id = _font_id(path, ttc_index)
    except Exception as exc:  # noqa: BLE001
        print(f"      ERROR hashing {source_id}: {exc}", file=sys.stderr)
        return "error", None

    out_path = out_dir / f"{font_id}.json"
    if out_path.is_file() and not force:
        return "skipped", font_id

    try:
        font = _open_font(path, ttc_index)
    except (TTLibError, Exception) as exc:  # noqa: BLE001
        print(f"      ERROR opening {source_id}: {exc}", file=sys.stderr)
        return "error", font_id

    try:
        gid_map, counts_int, warnings = _build_gid_map_safe(font, source_id)
        for w in warnings:
            print(f"      WARN {source_id}: {w}", file=sys.stderr)
        payload = build_lookup_json_payload(
            font=font,
            key=font_id,
            gid_map=gid_map,
            counts_int=counts_int,
            kind="gid",
            source_id=source_id,
        )
        meta = payload["_meta"]
        meta["font_id"] = font_id
        meta["source"] = source_id
        meta["filename"] = Path(source_id.split("::", 1)[0]).name
        meta["names"] = _collect_names(font)
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(out_path)
        return "written", font_id
    except Exception as exc:  # noqa: BLE001
        print(f"      ERROR building {source_id}: {exc}", file=sys.stderr)
        return "error", font_id
    finally:
        try:
            font.close()
        except Exception:  # noqa: BLE001
            pass


def build_name_index(out_dir: Path) -> dict[str, Any]:
    """(Re)build ``_name_index.json`` from every ``<id>.json`` on disk."""
    index: dict[str, dict[str, list[str]]] = {role: {} for role, _ in _NAME_ROLES}
    index["filename"] = {}
    font_count = 0
    for jp in sorted(out_dir.glob("*.json")):
        if jp.name.startswith("_"):
            continue
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = data.get("_meta", {})
        font_id = meta.get("font_id") or jp.stem
        font_count += 1
        for n in meta.get("names", []):
            role = n.get("role")
            norm = n.get("norm")
            if role in index and norm:
                index[role].setdefault(norm, [])
                if font_id not in index[role][norm]:
                    index[role][norm].append(font_id)
        fname = meta.get("filename")
        if fname:
            fnorm = _norm_name(Path(fname).stem)
            if fnorm:
                index["filename"].setdefault(fnorm, [])
                if font_id not in index["filename"][fnorm]:
                    index["filename"][fnorm].append(font_id)
    payload = {
        "_meta": {
            "description": "name -> [font_id] index for tier-1 GID lookup",
            "roles_priority": ["ps", "full", "family", "filename"],
            "font_count": font_count,
        },
        **index,
    }
    out_path = out_dir / "_name_index.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"font_count": font_count, "out_path": str(out_path)}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", action="append", type=Path, default=None, metavar="DIR",
                   help="Font source root (repeatable). Defaults to the two BUDA font folders.")
    p.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT, metavar="DIR",
                   help=f"Output directory (default: {DEFAULT_OUT})")
    p.add_argument("--force", action="store_true", help="Rebuild even if <id>.json exists.")
    p.add_argument("--index-only", action="store_true",
                   help="Only regenerate _name_index.json from existing JSON.")
    p.add_argument("--limit", type=int, default=0, metavar="N",
                   help="Process at most N font faces (smoke testing).")
    args = p.parse_args(argv)

    roots = [r for r in (args.root or DEFAULT_ROOTS)]
    out_dir: Path = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.index_only:
        print(f"Rebuilding name index from {out_dir} ...")
        info = build_name_index(out_dir)
        print(f"  wrote {info['out_path']}  ({info['font_count']} fonts)")
        return

    print(f"Output dir: {out_dir}")
    print(f"Roots:      {[str(r) for r in roots]}")
    print("Enumerating font faces ...")
    faces = list(_iter_source_fonts(roots))
    if args.limit:
        faces = faces[: args.limit]
    total = len(faces)
    print(f"  {total} font faces found")

    written = skipped = errors = 0
    ids_seen: dict[str, str] = {}
    duplicates = 0
    t0 = time.time()
    for i, (source_id, path, ttc_index) in enumerate(faces, 1):
        status, font_id = _process_one(source_id, path, ttc_index, out_dir, force=args.force)
        if status == "written":
            written += 1
        elif status == "skipped":
            skipped += 1
        else:
            errors += 1
        if font_id is not None:
            if font_id in ids_seen and ids_seen[font_id] != source_id:
                duplicates += 1
            ids_seen.setdefault(font_id, source_id)
        tag = {"written": "+", "skipped": "=", "error": "!"}[status]
        print(f"  [{i}/{total}] {tag} {source_id}")
        if i % 50 == 0 or i == total:
            rate = i / max(1e-6, time.time() - t0)
            print(
                f"    -- progress: {i}/{total}  written={written} skipped={skipped} "
                f"errors={errors} dup={duplicates}  ({rate:.1f} fonts/s)"
            )

    manifest = {
        "roots": [Path(r).name for r in roots],
        "faces_seen": total,
        "written": written,
        "skipped": skipped,
        "errors": errors,
        "duplicate_content_faces": duplicates,
        "unique_font_ids": len(ids_seen),
    }
    (out_dir / "_rebuild_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\nBuilding name index ...")
    info = build_name_index(out_dir)
    print(f"  wrote {info['out_path']}  ({info['font_count']} fonts)")
    print(
        f"\nDone. faces={total} written={written} skipped={skipped} errors={errors} "
        f"unique_ids={len(ids_seen)} dup_content={duplicates}"
    )


if __name__ == "__main__":
    main()
