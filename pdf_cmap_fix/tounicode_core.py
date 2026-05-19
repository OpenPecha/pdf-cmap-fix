"""
Shared ToUnicode merge logic for tier-specific CLIs (gid / gname / gshape).

``collect_font_merges(..., lookup_dir=..., tier=...)`` only uses JSON files whose
``_meta.lookup_kind`` matches ``tier`` (``gid`` also accepts absent ``lookup_kind``).
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Tuple

import fitz
from fontTools.ttLib import TTFont

LookupTier = Literal["gid", "gname", "gshape"]

PREVIEW_LINES = 15
PREVIEW_DIFF = 8


def _strip_prefix(name: str) -> str:
    return name.split("+", 1)[1] if "+" in name else name


def _decode_pdf(s: str) -> str:
    return re.sub(
        r"#([0-9A-Fa-f]{2})",
        lambda m: chr(int(m.group(1), 16)),
        s,
    )


def _normalise_name(name: str) -> str:
    name = _strip_prefix(name)
    for _ in range(3):
        d = _decode_pdf(name)
        if d == name:
            break
        name = d
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_db_index(font_keys: Iterable[str]) -> dict:
    return {re.sub(r"[^a-z0-9]", "", k.lower()): k for k in font_keys}


def _pick_best_font_key(db_index: dict, pdf_basename: str) -> Optional[str]:
    """Return the font key that best matches a PDF base font name."""
    pdf_key = _normalise_name(pdf_basename)
    best_key: Optional[str] = None
    best_score, best_delta = 0, 10**9
    for db_norm, db_key in db_index.items():
        if pdf_key == db_norm:
            score = 3
        elif pdf_key in db_norm:
            score = 2
        elif db_norm in pdf_key:
            score = 1
        else:
            continue
        delta = abs(len(db_norm) - len(pdf_key))
        if score > best_score or (score == best_score and delta < best_delta):
            best_score, best_delta, best_key = score, delta, db_key
    return best_key


def _discover_lookup_keys(lookup_dir: Path) -> list[str]:
    if not lookup_dir.is_dir():
        return []
    return sorted(
        p.stem for p in lookup_dir.glob("*.json") if p.name != "_manifest.json"
    )


def _load_lookup_file(path: Path) -> Optional[Tuple[str, dict[str, str]]]:
    """Load one lookup JSON. Returns ``(lookup_kind, inner)`` or ``None``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
    kind = meta.get("lookup_kind", "gid")
    if kind not in ("gid", "gname", "gshape"):
        kind = "gid"
    inner: Optional[dict[str, str]] = None
    for k, v in data.items():
        if k == "_meta" or not isinstance(v, dict) or not v:
            continue
        inner = {}
        for k2, u in v.items():
            if not isinstance(u, str):
                continue
            inner[str(k2)] = u
        break
    if not inner:
        return None
    return (kind, inner)


def _gid_map_from_inner(inner: dict[str, str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for g, u in inner.items():
        try:
            out[int(g)] = u
        except (ValueError, TypeError):
            continue
    return out


def _resolve_db_gid_map(
    doc: fitz.Document,
    font_xref: int,
    lookup_kind: str,
    inner: dict[str, str],
) -> dict[int, str]:
    """Map PDF GIDs to Unicode using embedded font + gname or gshape table."""
    if lookup_kind == "gid":
        return _gid_map_from_inner(inner)
    ext_font: Optional[TTFont] = None
    try:
        try:
            tup = doc.extract_font(font_xref)
        except Exception:
            return {}
        if not tup or len(tup) < 4:
            return {}
        buf = tup[3]
        if not buf or not isinstance(buf, (bytes, bytearray)):
            return {}
        ext_font = TTFont(io.BytesIO(bytes(buf)), lazy=False)
        go = ext_font.getGlyphOrder()
        resolved: dict[int, str] = {}
        n = min(len(go), 0x10000)
        if lookup_kind == "gshape":
            from pdf_cmap_fix.glyph_fingerprint import fingerprint_glyph
        for gid in range(n):
            gname = go[gid]
            if lookup_kind == "gname":
                u = inner.get(gname)
                if u:
                    resolved[gid] = u
            elif lookup_kind == "gshape":
                h = fingerprint_glyph(ext_font, gname)
                if h and h in inner:
                    resolved[gid] = inner[h]
        return resolved
    except Exception:
        return {}
    finally:
        if ext_font is not None:
            try:
                ext_font.close()
            except Exception:
                pass


def _parse_tounicode(stream: bytes) -> dict:
    text = stream.decode("latin-1")
    result: dict = {}

    for blk in re.finditer(r"beginbfchar(.*?)endbfchar", text, re.DOTALL):
        for m in re.finditer(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk.group(1)):
            try:
                code = int(m.group(1), 16)
                uni = "".join(
                    chr(int(m.group(2)[i : i + 4], 16))
                    for i in range(0, len(m.group(2)), 4)
                )
                result[code] = uni
            except (ValueError, OverflowError):
                pass

    for blk in re.finditer(r"beginbfrange(.*?)endbfrange", text, re.DOTALL):
        for m in re.finditer(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>",
            blk.group(1),
        ):
            try:
                lo = int(m.group(1), 16)
                hi = int(m.group(2), 16)
                base = int(m.group(3), 16)
                for off in range(hi - lo + 1):
                    result[lo + off] = chr(base + off)
            except (ValueError, OverflowError):
                pass

    return result


def _build_tounicode_type0(mapping: dict) -> bytes:
    entries = [
        f"<{gid:04X}> <{''.join(f'{ord(c):04X}' for c in uni)}>"
        for gid, uni in sorted(mapping.items())
    ]
    lines = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        "<0000> <FFFF>",
        "endcodespacerange",
        f"{len(entries)} beginbfchar",
        *entries,
        "endbfchar",
        "endcmap",
        "CMapName currentdict /CMap defineresource pop",
        "end",
        "end",
    ]
    return "\n".join(lines).encode("latin-1")


def _merge(existing: dict, db_map: dict) -> tuple:
    merged = dict(existing)
    changed = 0
    for gid, db_uni in db_map.items():
        if db_uni != existing.get(gid, ""):
            merged[gid] = db_uni
            changed += 1
    return merged, changed


def _overrides(existing: dict, merged: dict) -> dict:
    out = {}
    for k, v in merged.items():
        if existing.get(k, "") != v:
            out[k] = v
    return out


def collect_font_merges(
    doc: fitz.Document,
    *,
    lookup_dir: Path,
    tier: LookupTier,
    verbose: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Scan Type0 fonts with ToUnicode; compute merged maps without writing PDF.

    Only JSON whose ``_meta.lookup_kind`` matches ``tier`` is used (``gid`` tier
    also accepts files with missing ``lookup_kind``). Merge output is always
    GID → Unicode for the PDF cmap.
    """
    cache: dict[tuple[str, str], Optional[Tuple[str, dict[str, str]]]] = {}

    keys_disk = _discover_lookup_keys(lookup_dir)
    db_index = _build_db_index(keys_disk)

    stats = dict(fonts_seen=0, patched=0, upgrades=0, no_change=0, no_match=0)
    records: list[dict[str, Any]] = []
    seen: set = set()
    reported: set = set()

    for pno in range(len(doc)):
        for f in doc[pno].get_fonts(full=True):
            xref, _, ftype, basename, _, _, _ = f
            if xref in seen:
                continue
            seen.add(xref)

            if ftype != "Type0":
                continue
            stats["fonts_seen"] += 1

            font_obj = doc.xref_object(xref)
            m = re.search(r"/ToUnicode (\d+) 0 R", font_obj)
            if not m:
                stats["no_change"] += 1
                continue
            tu_xref = int(m.group(1))
            try:
                tu_stream = doc.xref_stream(tu_xref)
            except Exception:
                stats["no_change"] += 1
                continue

            existing = _parse_tounicode(tu_stream)

            picked = _pick_best_font_key(db_index, basename)
            match_kind = ""
            if picked is None:
                db_map, db_key = None, None
            else:
                path = lookup_dir / f"{picked}.json"
                if path.is_file():
                    cache_key = (str(path.resolve()), tier)
                    if cache_key not in cache:
                        raw = _load_lookup_file(path)
                        if raw is not None and raw[0] == tier:
                            cache[cache_key] = raw
                        else:
                            cache[cache_key] = None
                    loaded = cache[cache_key]
                    db_map = None
                    db_key = None
                    if loaded is not None:
                        match_kind, inner = loaded
                        if match_kind == "gid":
                            db_map = _gid_map_from_inner(inner)
                            if db_map:
                                db_key = picked
                            else:
                                db_map = None
                        else:
                            db_map = _resolve_db_gid_map(doc, xref, match_kind, inner)
                            if db_map:
                                db_key = picked
                            else:
                                db_map = None
                else:
                    db_map, db_key = None, None
            if not db_map:
                db_map, db_key = None, None

            if db_map is None:
                stats["no_match"] += 1
                norm = _normalise_name(basename)
                if verbose and norm not in reported:
                    reported.add(norm)
                    print(f"  [no DB match] {basename}")
                merged = dict(existing)
                changed = 0
                overrides = {}
            else:
                norm = _normalise_name(basename)
                if verbose and norm not in reported:
                    reported.add(norm)
                    print(f"  [matched] {basename[:50]} -> {db_key}  [{match_kind}]")
                merged, changed = _merge(existing, db_map)
                overrides = _overrides(existing, merged)

            records.append(
                {
                    "font_xref": xref,
                    "to_unicode_xref": tu_xref,
                    "pdf_font_name": basename,
                    "db_key_matched": db_key,
                    "existing": existing,
                    "merged": merged,
                    "overrides": overrides,
                    "changed": changed,
                }
            )

            if db_map is None:
                pass
            elif changed == 0:
                stats["no_change"] += 1
            else:
                stats["patched"] += 1
                stats["upgrades"] += changed

    return records, stats


def apply_font_merges_to_doc(doc: fitz.Document, records: list[dict[str, Any]]) -> None:
    """Write merged ToUnicode streams for records with changed > 0."""
    for r in records:
        if r["changed"] <= 0:
            continue
        doc.update_stream(
            r["to_unicode_xref"],
            _build_tounicode_type0(r["merged"]),
        )


def patch_doc(
    doc: fitz.Document,
    *,
    lookup_dir: Path,
    tier: LookupTier,
    verbose: bool = False,
) -> dict[str, int]:
    records, stats = collect_font_merges(
        doc,
        lookup_dir=lookup_dir,
        tier=tier,
        verbose=verbose,
    )
    apply_font_merges_to_doc(doc, records)
    return stats


def extract_all(doc: fitz.Document) -> str:
    pages = []
    for pno in range(len(doc)):
        text = doc[pno].get_text(
            "text",
            flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES,
        )
        pages.append(f"=== PAGE {pno+1} ===\n{text.strip()}")
    return "\n".join(pages)


def build_tounicode_dict(
    pdf_path,
    *,
    lookup_dir: Path,
    tier: LookupTier,
) -> dict[str, Any]:
    pdf_path = Path(pdf_path)

    doc = fitz.open(str(pdf_path))
    try:
        records, stats = collect_font_merges(
            doc,
            lookup_dir=lookup_dir,
            tier=tier,
            verbose=False,
        )
    finally:
        doc.close()

    by_xref = {str(r["font_xref"]): r for r in records}
    return {"fonts": records, "by_font_xref": by_xref, "stats": stats}


def patch_pdf(
    pdf_path,
    output_path=None,
    write_file: bool = True,
    *,
    lookup_dir: Path,
    tier: LookupTier,
    verbose: bool = False,
) -> dict:
    pdf_path = Path(pdf_path)
    stem = pdf_path.stem

    out_path: Optional[Path] = None
    if write_file:
        out_path = Path(output_path) if output_path else pdf_path.parent / f"{stem}.patched.pdf"

    doc = fitz.open(str(pdf_path))
    try:
        stats = patch_doc(
            doc,
            lookup_dir=lookup_dir,
            tier=tier,
            verbose=verbose,
        )
        pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    if write_file and out_path is not None:
        out_path.write_bytes(pdf_bytes)

    return dict(pdf_bytes=pdf_bytes, stats=stats, output_path=out_path)


def extract_pdf_text(
    pdf_path,
    output_dir=None,
    write_files: bool = True,
    *,
    lookup_dir: Path,
    tier: LookupTier,
    verbose: bool = False,
) -> dict:
    pdf_path = Path(pdf_path)
    out_dir = Path(output_dir) if output_dir else pdf_path.parent
    stem = pdf_path.stem

    doc_raw = fitz.open(str(pdf_path))
    raw_text = extract_all(doc_raw)
    doc_raw.close()

    doc_pat = fitz.open(str(pdf_path))
    try:
        stats = patch_doc(
            doc_pat,
            lookup_dir=lookup_dir,
            tier=tier,
            verbose=verbose,
        )
        patched_text = extract_all(doc_pat)
    finally:
        doc_pat.close()

    raw_lines = raw_text.splitlines()
    pat_lines = patched_text.splitlines()
    diff_lines = [
        (i, r, p)
        for i, (r, p) in enumerate(zip(raw_lines, pat_lines))
        if r != p
    ]
    char_delta = len(patched_text) - len(raw_text)

    if write_files:
        (out_dir / f"{stem}.raw.txt").write_text(raw_text, encoding="utf-8")
        (out_dir / f"{stem}.patched.txt").write_text(patched_text, encoding="utf-8")
        with open(out_dir / f"{stem}.diff.txt", "w", encoding="utf-8") as df:
            df.write(
                f"PDF:           {pdf_path.name}\n"
                f"Lines changed: {len(diff_lines)}\n"
                f"Char delta:    {char_delta:+d}\n\n"
            )
            for i, r, p in diff_lines:
                df.write(f"--- line {i+1} RAW:\n{r}\n")
                df.write(f"+++ line {i+1} PATCHED:\n{p}\n\n")

    return dict(
        raw=raw_text,
        patched=patched_text,
        stats=stats,
        diff_lines=diff_lines,
        char_delta=char_delta,
    )


def _serialise_cmap_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert int-keyed inner dicts to str for JSON."""

    def cmap_dict(d: dict) -> dict[str, str]:
        return {str(k): v for k, v in sorted(d.items())}

    out_fonts = []
    for r in payload["fonts"]:
        out_fonts.append(
            {
                "font_xref": r["font_xref"],
                "to_unicode_xref": r["to_unicode_xref"],
                "pdf_font_name": r["pdf_font_name"],
                "db_key_matched": r["db_key_matched"],
                "existing": cmap_dict(r["existing"]),
                "merged": cmap_dict(r["merged"]),
                "overrides": cmap_dict(r["overrides"]),
                "changed": r["changed"],
            }
        )
    return {"fonts": out_fonts, "stats": payload["stats"]}


def _sanitise_json_utf8(obj: Any) -> Any:
    """Replace lone UTF-16 surrogates so ``json`` output can be written as UTF-8."""

    def _fix_str(s: str) -> str:
        return "".join("\ufffd" if 0xD800 <= ord(c) <= 0xDFFF else c for c in s)

    if isinstance(obj, str):
        return _fix_str(obj)
    if isinstance(obj, dict):
        return {_fix_str(k) if isinstance(k, str) else k: _sanitise_json_utf8(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitise_json_utf8(x) for x in obj]
    return obj


def _printable(s: str) -> str:
    return "".join(c if c >= " " else f"[{ord(c):02X}]" for c in s)


def _show_preview(label: str, text: str, n: int = PREVIEW_LINES) -> None:
    print(f"\n  --- {label} (first {n} non-empty lines) ---")
    count = 0
    for line in text.splitlines():
        if line.strip() and not line.startswith("=== PAGE"):
            print(f"    {_printable(line)}")
            count += 1
            if count >= n:
                break


def _show_diff_sample(raw: str, patched: str, n: int = PREVIEW_DIFF) -> None:
    raw_lines = raw.splitlines()
    pat_lines = patched.splitlines()
    diffs = [(i, r, p) for i, (r, p) in enumerate(zip(raw_lines, pat_lines)) if r != p]
    print(f"\n  --- Sample of changed lines ({min(n, len(diffs))} of {len(diffs)}) ---")
    for i, r, p in diffs[:n]:
        print(f"    line {i+1}:")
        print(f"      RAW:     {_printable(r)}")
        print(f"      PATCHED: {_printable(p)}")


def cli_main(
    argv: list[str],
    *,
    tier: LookupTier,
    default_lookup_dir: Path,
    usage_text: str,
    program_label: str,
) -> None:
    """Shared argv parser and driver for tier CLIs."""
    import io as io_mod

    if hasattr(sys.stdout, "buffer") and not isinstance(
        sys.stdout, io_mod.TextIOWrapper
    ):
        sys.stdout = io_mod.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    if not argv:
        sys.exit(usage_text)
    if argv[0] in ("-h", "--help"):
        sys.stdout.write(usage_text)
        sys.exit(0)

    font_lookup_cli: Optional[Path] = None
    i = 0
    while i < len(argv):
        if argv[i] == "--font-lookup-dir" and i + 1 < len(argv):
            font_lookup_cli = Path(argv[i + 1])
            i += 2
            continue
        break
    argv = argv[i:]

    lookup_root = (
        font_lookup_cli.expanduser().resolve()
        if font_lookup_cli is not None
        else default_lookup_dir.resolve()
    )
    if not lookup_root.is_dir():
        flag = "--font-lookup-dir" if font_lookup_cli is not None else "default lookup dir"
        sys.exit(f"font lookup directory not found ({flag}): {lookup_root}")

    dump_cmap: Optional[str] = None
    patch_pdf_mode = False
    rest = list(argv)
    if rest and rest[0] in ("--patch-pdf", "-p"):
        patch_pdf_mode = True
        rest = rest[1:]
    elif rest and rest[0] == "--dump-cmap":
        if len(rest) < 2:
            sys.exit(f"{program_label} --dump-cmap requires OUTPUT.json and at least one PDF")
        dump_cmap = rest[1]
        rest = rest[2:]

    pdf_args = rest
    if not pdf_args:
        sys.exit(usage_text)

    n_lookup = len(_discover_lookup_keys(lookup_root))
    print(f"Loading font lookup ({tier}) ...")
    print(f"  {n_lookup} font JSON files under {lookup_root}")

    for arg in pdf_args:
        pdf_path = Path(arg)
        if not pdf_path.exists():
            print(f"  SKIP (not found): {arg}", file=sys.stderr)
            continue

        stem = pdf_path.stem
        print(f"\n{'='*65}")
        print(f"  PDF: {pdf_path.name}")
        print(f"{'='*65}")

        if dump_cmap is not None:
            out_json = Path(dump_cmap)
            if len(pdf_args) > 1:
                out_json = out_json.parent / f"{out_json.stem}_{pdf_path.stem}{out_json.suffix}"
            payload = build_tounicode_dict(
                pdf_path,
                lookup_dir=lookup_root,
                tier=tier,
            )
            serial = _sanitise_json_utf8(_serialise_cmap_result(payload))
            out_json.parent.mkdir(parents=True, exist_ok=True)
            out_json.write_text(json.dumps(serial, ensure_ascii=False, indent=2), encoding="utf-8")
            s = payload["stats"]
            print(f"  fonts seen:    {s['fonts_seen']}")
            print(f"  would patch:   {s['patched']}  ({s['upgrades']} GID upgrades)")
            print(f"  no change:     {s['no_change']}")
            print(f"  no DB match:   {s['no_match']}")
            print(f"  Written: {out_json}")
            continue

        if patch_pdf_mode:
            print("\n[Patch-only mode] Rewriting ToUnicode CMaps ...")
            result = patch_pdf(
                pdf_path,
                lookup_dir=lookup_root,
                tier=tier,
                verbose=True,
            )
            stats = result["stats"]
            pdf_bytes = result["pdf_bytes"]
            out_path = result["output_path"]
            print(f"  fonts seen:    {stats['fonts_seen']}")
            print(f"  patched:       {stats['patched']}  ({stats['upgrades']} GID upgrades)")
            print(f"  no change:     {stats['no_change']}")
            print(f"  no DB match:   {stats['no_match']}")
            print(f"  Written: {out_path}  ({len(pdf_bytes):,} bytes)")
            continue

        print("\n[Phase 1] Raw extraction ...")
        result = extract_pdf_text(
            pdf_path,
            lookup_dir=lookup_root,
            tier=tier,
            verbose=True,
        )
        raw_text = result["raw"]
        patched_text = result["patched"]
        stats = result["stats"]
        diff_lines = result["diff_lines"]
        char_delta = result["char_delta"]
        pages = len(raw_text.split("=== PAGE "))
        print(f"  {len(raw_text):,} chars, {pages-1} pages")
        _show_preview("RAW TEXT", raw_text)

        print("\n[Phase 2] Patched result ...")
        print(f"  fonts seen:    {stats['fonts_seen']}")
        print(f"  patched:       {stats['patched']}  ({stats['upgrades']} GID upgrades)")
        print(f"  no change:     {stats['no_change']}")
        print(f"  no DB match:   {stats['no_match']}")
        print(f"  Written: {pdf_path.parent}/{stem}.{{raw,patched,diff}}.txt")
        _show_preview("PATCHED TEXT", patched_text)
        print("\n[Diff]")
        print(
            f"  Lines changed: {len(diff_lines)} / "
            f"{max(len(raw_text.splitlines()), len(patched_text.splitlines()))}"
        )
        print(f"  Char delta:    {char_delta:+d}")
        _show_diff_sample(raw_text, patched_text)

    print("\nDone.")
