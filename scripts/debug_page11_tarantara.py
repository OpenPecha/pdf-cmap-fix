#!/usr/bin/env python3
"""Debug FFFD sources on a tarantara PDF page (1-based page number).

Default page 4: folio label \"Page11:\" in the document body (not PDF page 11).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf_cmap_fix.content_streams import (  # noqa: E402
    _iter_text_strings,
    _resource_font_xref_map,
)
from pdf_cmap_fix.tounicode_core import (  # noqa: E402
    _gid_map_from_inner,
    _load_lookup_file_cached,
    _parse_tounicode,
)

PDF = ROOT / "docs/examples/tarantara/Taranatha-Ladakh-06-p1-959-without-folios.pdf"
# Folio label "Page11:" appears on PDF page 4 (see raw.txt === PAGE 4 ===).
PAGE_1BASED = int(sys.argv[1]) if len(sys.argv) > 1 else 4
PAGE_IDX = PAGE_1BASED - 1


def gid_hex(g: int) -> str:
    return f"0x{g:04X} ({g})"


def main() -> None:
    doc = fitz.open(PDF)
    page = doc[PAGE_IDX]

    print("=" * 70)
    print(f"PDF: {PDF.name}")
    print(f"Page {PAGE_1BASED} (index {PAGE_IDX})")
    print("=" * 70)

    # --- fonts on this page ---
    fonts: dict[int, dict] = {}
    for f in page.get_fonts(full=True):
        xref, _, ftype, basename, *_ = f
        if xref not in fonts:
            fonts[xref] = {"name": basename, "type": ftype}

    print("\nFonts on page:")
    for xref, info in sorted(fonts.items()):
        print(f"  xref={xref}  type={info['type']}  name={info['name']}")

    himalaya_xrefs = [
        x for x, i in fonts.items() if "Himalaya" in i["name"]
    ]
    if not himalaya_xrefs:
        print("No Himalaya font on page!")
        doc.close()
        return

    h_xref = himalaya_xrefs[0]
    print(f"\nPrimary Himalaya xref: {h_xref}")

    # --- ToUnicode ---
    font_obj = doc.xref_object(h_xref)
    m = re.search(r"/ToUnicode (\d+) 0 R", font_obj)
    tu_xref = int(m.group(1)) if m else None
    existing: dict[int, str] = {}
    if tu_xref:
        existing = _parse_tounicode(doc.xref_stream(tu_xref))
        print(f"ToUnicode xref={tu_xref}  entries={len(existing)}")

    # --- DB lookup ---
    db_path = ROOT / "pdf_cmap_fix/data/font_lookup/microsofthimalaya.json"
    db_map: dict[int, str] = {}
    loaded = _load_lookup_file_cached(db_path)
    if loaded:
        _, inner = loaded
        db_map = _gid_map_from_inner(inner)

    # --- PyMuPDF extraction ---
    pymupdf_text = page.get_text("text")
    fffd_count = pymupdf_text.count("\ufffd")
    print(f"\nPyMuPDF get_text: {len(pymupdf_text)} chars, FFFD count={fffd_count}")

    # Find FFFD contexts in PyMuPDF text
    marker = "ཀྤཱུ"
    if marker in pymupdf_text:
        idx = pymupdf_text.find(marker)
        print(f"\nContext around '{marker}' in PyMuPDF text:")
        print(repr(pymupdf_text[max(0, idx - 30) : idx + 60]))

    print("\nAll FFFD contexts (PyMuPDF text, up to 15):")
    for n, m in enumerate(re.finditer("\ufffd", pymupdf_text)):
        if n >= 15:
            print("  ...")
            break
        i = m.start()
        print(f"  [{n}] pos={i}: {repr(pymupdf_text[max(0, i - 25) : i + 25])}")

    # --- rawdict: char-by-char ---
    print("\n--- rawdict FFFD glyphs ---")
    blocks = page.get_text("rawdict", flags=0)["blocks"]
    fffd_chars: list[dict] = []
    all_chars: list[dict] = []
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    all_chars.append(char)
                    if char["c"] == "\ufffd":
                        fffd_chars.append(char)

    print(f"Total glyphs (rawdict): {len(all_chars)}")
    print(f"FFFD glyphs (rawdict): {len(fffd_chars)}")

    # Build linear text from rawdict for index alignment
    rawdict_text = "".join(c["c"] for c in all_chars)

    for n, fffd in enumerate(fffd_chars[:12]):
        # find index in linear string
        pos = rawdict_text.find("\ufffd", rawdict_text.find("\ufffd") if n == 0 else 0)
        # simpler: walk to nth fffd
        count = 0
        idx = -1
        for i, c in enumerate(all_chars):
            if c["c"] == "\ufffd":
                if count == n:
                    idx = i
                    break
                count += 1
        ctx_start = max(0, idx - 4)
        ctx_end = min(len(all_chars), idx + 5)
        ctx = "".join(all_chars[i]["c"] for i in range(ctx_start, ctx_end))
        print(f"  FFFD[{n}] origin={fffd.get('origin')}  context={repr(ctx)}")

    # --- content stream decode ---
    print("\n--- content stream (C2_0 / Himalaya) ---")
    stream = page.read_contents()
    name_to_xref = _resource_font_xref_map(doc, page)
    print("Resource fonts:", {k.decode("latin-1"): v for k, v in name_to_xref.items()})

    c2_name = None
    for k, v in name_to_xref.items():
        if v == h_xref:
            c2_name = k
            break
    print(f"Himalaya resource name: {c2_name!r}")

    def decode_payload(payload: bytes) -> tuple[str, list[tuple[int, str, str]]]:
        """Return (text, [(gid, mapped_char, status), ...])."""
        parts: list[tuple[int, str, str]] = []
        text = ""
        for k in range(0, len(payload) - 1, 2):
            gid = (payload[k] << 8) | payload[k + 1]
            if gid in existing:
                ch = existing[gid]
                status = "tu"
            elif gid in db_map:
                ch = db_map[gid]
                status = "db"
            else:
                ch = "\ufffd"
                status = "MISSING"
            parts.append((gid, ch, status))
            text += ch
        return text, parts

    all_c2_text = ""
    all_c2_parts: list[tuple[int, str, str]] = []
    string_idx = 0
    strings_with_fffd: list[dict] = []

    for fname, payload in _iter_text_strings(stream):
        if fname != c2_name:
            continue
        text, parts = decode_payload(payload)
        if "\ufffd" in text or any(p[2] == "MISSING" for p in parts):
            missing = [p for p in parts if p[2] == "MISSING"]
            strings_with_fffd.append(
                {
                    "idx": string_idx,
                    "missing": missing,
                    "text_snip": text[max(0, text.find("\ufffd") - 15) : text.find("\ufffd") + 20]
                    if "\ufffd" in text
                    else text[:40],
                    "full_len": len(text),
                }
            )
        all_c2_text += text
        all_c2_parts.extend(parts)
        string_idx += 1

    print(f"C2_0 strings parsed: {string_idx}")
    print(f"Manual decode total chars: {len(all_c2_text)}")
    print(f"Manual decode FFFD count: {all_c2_text.count(chr(0xFFFD))}")
    print(f"Strings with MISSING GIDs: {len(strings_with_fffd)}")

    if strings_with_fffd:
        print("\nFirst strings with missing GIDs:")
        for s in strings_with_fffd[:5]:
            print(f"  string #{s['idx']} len={s['full_len']}")
            for gid, _ch, st in s["missing"][:8]:
                db_u = db_map.get(gid, "")
                print(f"    {gid_hex(gid)}  db={repr(db_u) if db_u else '—'}")
            print(f"    snippet: {repr(s['text_snip'])}")

    # Search for ཀྤཱུ in manual decode
    if marker in all_c2_text:
        idx = all_c2_text.find(marker)
        print(f"\nManual decode context around '{marker}':")
        print(repr(all_c2_text[max(0, idx - 20) : idx + 50]))
    else:
        print(f"\n'{marker}' NOT in manual C2_0 decode")

    # --- Word ActualText markers (root cause on page 4) ---
    print("\n--- ActualText BDC markers ---")
    actual = list(
        re.finditer(rb"ActualText\s*<([0-9A-Fa-f]+)>", stream)
    )
    print(f"ActualText count: {len(actual)}")
    feff_markers = [m for m in actual if m.group(1).upper() == b"FEFFFFFD"]
    print(f"ActualText<FEFFFFFD>: {len(feff_markers)}")
    for m in feff_markers[:3]:
        print(f"  at {m.start()}: {repr(stream[m.end() : m.end() + 50])}")

    # --- hunt sentinel GIDs in stream ---
    print("\n--- sentinel / high GID scan in C2_0 payloads ---")
    sentinel_hits: list[tuple[int, int, str]] = []
    for fname, payload in _iter_text_strings(stream):
        if fname != c2_name:
            continue
        for k in range(0, len(payload) - 1, 2):
            gid = (payload[k] << 8) | payload[k + 1]
            if gid in (0xFEFF, 0xFFFD, 65279, 65533) or gid > 0x5000:
                sentinel_hits.append((gid, k, payload.hex()[k * 2 : k * 2 + 8]))

    if sentinel_hits:
        for gid, off, hx in sentinel_hits[:20]:
            print(f"  {gid_hex(gid)} at offset {off}  bytes={hx}")
    else:
        print("  No FEFF/FFFD/high GIDs in parsed C2_0 strings")

    # --- compare: find GID sequence for mantra line in stream ---
    print("\n--- search stream for GID sequence near ཀ (if in DB) ---")
    ka_gids = [g for g, u in db_map.items() if u == "ཀ"]
    sub_pa_gids = [g for g, u in db_map.items() if u == "ྤ"]
    print(f"DB GIDs for ཀ: {[gid_hex(g) for g in ka_gids[:5]]}")
    print(f"DB GIDs for ྤ: {[gid_hex(g) for g in sub_pa_gids[:5]]}")

    # Walk C2_0 and print triplets around tsek (་) GID 257 in existing
    tsek_gid = next((g for g, u in existing.items() if u == "་"), None)
    if tsek_gid:
        print(f"tsek GID in ToUnicode: {gid_hex(tsek_gid)}")
        for fname, payload in _iter_text_strings(stream):
            if fname != c2_name:
                continue
            gids = [(payload[k] << 8) | payload[k + 1] for k in range(0, len(payload) - 1, 2)]
            for i in range(len(gids) - 3):
                if gids[i] == tsek_gid and gids[i + 2] in (sub_pa_gids or [1037]):
                    mid = gids[i + 1]
                    if mid not in existing:
                        print(
                            f"  tsek -> {gid_hex(mid)} (MISSING tu) -> "
                            f"{gid_hex(gids[i+2])} db={repr(db_map.get(mid))}"
                        )

    # --- output JSON for agent ---
    out_path = ROOT / "docs/examples/tarantara/page11-debug.json"
    report = {
        "pdf_page": PAGE_1BASED,
        "note": 'Folio "Page11:" is usually PDF page 4, not page 11.',
        "himalaya_xref": h_xref,
        "pymupdf_fffd_count": fffd_count,
        "rawdict_fffd_count": len(fffd_chars),
        "manual_c2_fffd_count": all_c2_text.count("\ufffd"),
        "actualtext_fefffffd_count": len(feff_markers),
        "c2_strings": string_idx,
        "strings_with_missing": len(strings_with_fffd),
        "missing_samples": strings_with_fffd[:3],
        "root_cause": (
            "Word /ActualText<FEFFFFFD> in BDC spans; PyMuPDF emits U+FEFF+U+FFFD. "
            "Tj GIDs after EMC are mapped; not fixed by ToUnicode-only sentinel JSON."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")

    doc.close()


if __name__ == "__main__":
    main()
