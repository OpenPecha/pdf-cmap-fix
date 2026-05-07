"""
GID → Unicode mapping from OpenType fonts (cmap + GSUB decomposition).

Used by ``build_per_font_gid_maps.py``, diagnostics, and optional single-font
updates. Recursively decomposes GSUB data:

- **Lookup type 4** (ligature): ligature glyph → component glyph names.
- **Lookup type 2** (multiple substitution): one glyph → ordered sequence.
- **Lookup type 1** (single substitution): reverse map substitute → sources.
- **Lookup type 7** (extension): unwrapped to inner types 1/2/4.

Contexts (types 3, 5, 6, 8) are not expanded into a static map.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from fontTools.ttLib import TTFont


def normalise_name(path_or_name: str) -> str:
    stem = Path(path_or_name).stem
    return re.sub(r"[^a-z0-9]", "", stem.lower())


def _iter_subtables(lookup, target_type: int):
    """Yield inner subtables for *lookup*, unwrapping Extension (type 7)."""
    lt = lookup.LookupType
    if lt == target_type:
        for sub in lookup.SubTable:
            yield sub
        return
    if lt != 7:
        return
    for sub in lookup.SubTable:
        ext_type = getattr(sub, "ExtensionLookupType", None)
        ext_sub = getattr(sub, "ExtSubTable", None)
        if ext_type == target_type and ext_sub is not None:
            yield ext_sub


def gsub_lig_rules(font: TTFont) -> dict[str, list[str]]:
    """GSUB type-4 rules: {result_gname: [component_gnames]} including via Extension 7."""
    rules: dict[str, list[str]] = {}
    if "GSUB" not in font:
        return rules
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for sub in _iter_subtables(lookup, 4):
            for first, lig_list in sub.ligatures.items():
                for lig in lig_list:
                    rules[lig.LigGlyph] = [first] + list(lig.Component)
    return rules


def gsub_single_subst_reverse(font: TTFont) -> dict[str, list[str]]:
    """GSUB type 1: for each target glyph name, list of source names."""
    rev: dict[str, list[str]] = defaultdict(list)
    if "GSUB" not in font:
        return {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for sub in _iter_subtables(lookup, 1):
            mapping = getattr(sub, "mapping", None)
            if not mapping:
                continue
            for src, tgt in mapping.items():
                rev[tgt].append(src)
    return {k: v for k, v in rev.items()}


def gsub_multiple_subst_forward(font: TTFont) -> dict[str, list[str]]:
    """GSUB type 2: {input_gname: [output component gnames]}."""
    out: dict[str, list[str]] = {}
    if "GSUB" not in font:
        return out
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for sub in _iter_subtables(lookup, 2):
            mapping = getattr(sub, "mapping", None)
            if not mapping:
                continue
            for src, seq in mapping.items():
                out[src] = list(seq) if seq else []
    return out


def gsub_lookup_type_counts(font: TTFont) -> dict[int, int]:
    """Counts per GSUB lookup type; Extension (7) also counts inner types."""
    raw: dict[int, int] = defaultdict(int)
    if "GSUB" not in font:
        return {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        raw[lookup.LookupType] += 1
        if lookup.LookupType == 7:
            for sub in lookup.SubTable:
                inner = getattr(sub, "ExtensionLookupType", None)
                if inner is not None:
                    raw[inner] += 1
    return dict(sorted(raw.items()))


def build_gid_map(font: TTFont) -> dict[int, str]:
    """GID -> unicode sequence via cmap + recursive GSUB decomposition."""
    cmap = font.getBestCmap() or {}
    glyph_order = font.getGlyphOrder()
    rules = gsub_lig_rules(font)
    single_rev = gsub_single_subst_reverse(font)
    multiple_fwd = gsub_multiple_subst_forward(font)
    gname_to_uni = {gname: chr(cp) for cp, gname in cmap.items()}
    cache: dict[str, str] = {}

    def decompose(gname: str, depth: int = 0, visiting: set[str] | None = None) -> str:
        if gname in cache:
            return cache[gname]
        if depth > 60:
            return ""
        if visiting is None:
            visiting = set()
        if gname in visiting:
            return ""
        visiting.add(gname)
        try:
            if gname in gname_to_uni:
                result = gname_to_uni[gname]
            elif gname in rules:
                result = "".join(decompose(c, depth + 1, visiting) for c in rules[gname])
            elif gname in multiple_fwd:
                result = "".join(
                    decompose(c, depth + 1, visiting) for c in multiple_fwd[gname]
                )
            elif gname in single_rev:
                sources = sorted(
                    single_rev[gname],
                    key=lambda s: (0 if s in gname_to_uni else 1, s),
                )
                result = ""
                for src in sources:
                    r = decompose(src, depth + 1, visiting)
                    if r:
                        result = r
                        break
            else:
                result = ""
        finally:
            visiting.discard(gname)

        cache[gname] = result
        return result

    result: dict[int, str] = {}
    for gid, gname in enumerate(glyph_order):
        uni = decompose(gname)
        if uni:
            result[gid] = uni
    return result
