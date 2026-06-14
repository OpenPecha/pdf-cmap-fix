"""Curated char -> Unicode conversion tables for legacy non-Unicode Tibetan fonts.

The tables (``data/pytiblegenc/tiblegenc.csv`` and ``utfc.csv``) and the
font-name normalisation/alias rules are vendored from ``pytiblegenc``
(https://github.com/buda-base/pydeduff, ``pytiblegenc/char_converter.py``).

These legacy fonts (Ededris/Dedris, TibetanChogyal, LTibetan, Esam*, ...) carry
no usable GSUB/cmap, so pdf-cmap-fix's GSUB-derived lookups produce garbage for
them. Instead, the PDF's *existing* ToUnicode already yields a (wrong) Latin-ish
character per code; re-mapping that character's codepoint through the per-font
table here recovers the correct Unicode -- exactly how ``pytiblegenc`` converts
the text downstream.

This module is pure-Python with no third-party dependencies.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

# How error/unconvertible glyphs are encoded in the source tables.
ERROR_CHR = "\u0f20\u0f20\u0f20\u0f20"  # "༠༠༠༠"

_DATA_DIR = Path(__file__).resolve().parent / "data" / "pytiblegenc"
# tiblegenc.csv is the primary table; utfc.csv only fills gaps (matches the
# base/utfc precedence in pytiblegenc's ``_convert_char``).
_TABLE_FILES = ("tiblegenc.csv", "utfc.csv")

# Vendored from pytiblegenc.char_converter.FONT_ALIASES.
FONT_ALIASES = {
    "Dedris-syma": "Ededris-sym",
    "Ededris-syma": "Ededris-sym",
    "TibetanClassicSkt": "TibetanClassicSkt1",
    "TibetanChogyalSkt": "TibetanChogyalSkt1",
}


def normalize_font_name(font_name: str, weight: Optional[str] = None) -> str:
    """Vendored from pytiblegenc.char_converter.normalize_font_name.

    ``weight`` is ``"b"``, ``"i"`` or ``"bi"`` (only relevant to the legacy
    WordPerfect path; unused here but kept for parity).
    """
    if font_name in FONT_ALIASES:
        font_name = FONT_ALIASES[font_name]
    if font_name.startswith("Dedris"):
        font_name = "Ed" + font_name[1:]
    if font_name.startswith("Sam") and len(font_name) == 4:
        font_name = "Es" + font_name[1:]
    if font_name.endswith("Normal"):
        font_name = font_name[:-6].strip()
    if weight == "b":
        font_name += "Skt1"
    if weight == "i":
        font_name += "Skt2"
    if weight == "bi":
        font_name += "Skt3"
    return font_name


def _strip_subset_prefix(font_name: str) -> str:
    """Drop a 6-letter PDF subset tag, e.g. ``KSWSGG+Dedris-a`` -> ``Dedris-a``."""
    if "+" in font_name:
        font_name = font_name.split("+", 1)[1]
    return font_name.strip()


def _load_one(path: Path, base: dict[str, dict[str, str]]) -> None:
    """Merge one CSV into ``base`` (existing entries win, like pytiblegenc)."""
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh, quotechar='"'):
            # row[2] may be empty (glyph we deliberately don't convert).
            if len(row) < 3:
                continue
            font_name, cp_str, value = row[0], row[1], row[2]
            try:
                unicp = int(cp_str)
            except ValueError:
                continue
            fmap = base.setdefault(font_name, {})
            # cp1252 alias key for low codepoints (matches get_base_from_file).
            if unicp < 256:
                try:
                    alt = bytes([unicp]).decode("cp1252")
                except (ValueError, UnicodeDecodeError):
                    alt = None
                if alt is not None and alt not in fmap:
                    fmap[alt] = value
            key = chr(unicp)
            if key not in fmap:
                fmap[key] = value


@lru_cache(maxsize=1)
def _base() -> dict[str, dict[str, str]]:
    base: dict[str, dict[str, str]] = {}
    for name in _TABLE_FILES:
        path = _DATA_DIR / name
        if path.is_file():
            _load_one(path, base)
    return base


def table_for(font_name: str) -> Tuple[Optional[str], Optional[dict[str, str]]]:
    """Resolve a PDF font name to ``(normalised_name, char_map)`` or ``(None, None)``.

    Strips a subset prefix, applies pytiblegenc's normalisation/aliases, then
    looks up the per-font conversion table.
    """
    if not font_name:
        return None, None
    norm = normalize_font_name(_strip_subset_prefix(font_name))
    table = _base().get(norm)
    if table is None:
        return None, None
    return norm, table


def table_for_candidates(
    candidates: list[str],
) -> Tuple[Optional[str], Optional[dict[str, str]]]:
    """Resolve the first outline-identified candidate name that has a table.

    ``candidates`` is ordered tightest-match-first (see
    :func:`pdf_cmap_fix.glyph_outline_id.identify_candidates`); we normalise
    each through the alias rules and return the first one backed by a
    conversion table, or ``(None, None)``.
    """
    base = _base()
    for cand in candidates:
        norm = normalize_font_name(_strip_subset_prefix(cand))
        table = base.get(norm)
        if table is not None:
            return norm, table
    return None, None


def convert_char(table: dict[str, str], ch: str) -> Optional[str]:
    """Map a single extracted character through ``table``.

    Returns the replacement string (always non-empty), or ``None`` when the
    character is absent, an error sentinel, or maps to the empty string (a
    glyph the source table deliberately drops, e.g. spacing).
    """
    value = table.get(ch)
    if value is None or value == ERROR_CHR or value == "":
        return None
    return value


def convert_text(table: dict[str, str], text: str) -> Optional[str]:
    """Re-map every character of an existing ToUnicode value through ``table``.

    Returns the concatenated Unicode string, or ``None`` if any character is
    unconvertible (so the caller keeps the existing mapping for that code).
    """
    parts: list[str] = []
    for ch in text:
        value = convert_char(table, ch)
        if value is None:
            return None
        parts.append(value)
    out = "".join(parts)
    return out or None
