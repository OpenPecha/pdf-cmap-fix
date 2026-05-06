"""
Diagnose how much extra coverage modelling GSUB **contextual** lookups
(types 5, 6, 8) and **alternate** (type 3) would buy on a single font.

Read-only: prints stats only, does not touch any DB or JSON file.

Usage::

    python scripts/diagnose_contextual_gsub.py path/to/Font.ttf [--limit 20]

Logic
-----
We compare three glyph populations:

* ``cmap_glyphs``      — glyph names directly addressable by Unicode codepoint
                         (atomic letters, signs, vowels, …).
* ``mapped_via_124``   — glyph names that current ``build_gid_map()`` resolves
                         to a non-empty Unicode string via cmap + GSUB
                         types 1, 2, 4 (Extension 7 unwraps to those).
* ``unmapped``         — everything else in ``getGlyphOrder()``.

Then for each contextual or alternate lookup we extract:

* ``ctx_inputs``       — glyphs that appear in the *input* sequence of a
                         contextual rule (the slot that gets a substitution
                         applied).
* ``ctx_subst_outputs``— the *output* glyphs of the inner type-1 / type-4
                         substitutions called by those contextual rules.
* ``alt_inputs``       — type-3 source glyphs.
* ``alt_outputs``      — type-3 alternate glyphs.

Numbers we print
----------------

* ``unmapped ∩ ctx_subst_outputs``: glyphs that the patcher currently can't
  resolve and that **are** the result of a contextual substitution. These are
  the only glyphs that explicit type-5/6/8 modelling could ever recover.
* ``unmapped ∩ alt_outputs``: same idea for type-3 alternates.
* sample of unmapped contextual outputs with a guess at "what they'd map to"
  (the inner substitution's *source* glyph's Unicode), so you can eyeball
  whether the recovery would be correct.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("pip install fonttools")

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_reverse_db import (  # noqa: E402
    _iter_subtables,
    build_gid_map,
    gsub_lig_rules,
    gsub_lookup_type_counts,
    gsub_multiple_subst_forward,
    gsub_single_subst_reverse,
)


def _resolve_lookup_index(lookup_list, idx: int):
    try:
        return lookup_list.Lookup[idx]
    except (IndexError, AttributeError):
        return None


def _inner_subst_outputs(font: TTFont) -> tuple[set[str], dict[str, list[str]]]:
    """Walk types 5/6 lookups and return (output_glyphs, output_to_sources).

    For each substitution actually triggered by a context rule we record the
    inner type-1 / type-4 mapping so we can guess the Unicode that *could* have
    produced this glyph.

    Type 8 is structurally similar; we treat it the same.
    """
    outputs: set[str] = set()
    out_to_src: dict[str, list[str]] = defaultdict(list)
    if "GSUB" not in font:
        return outputs, dict(out_to_src)
    lookup_list = font["GSUB"].table.LookupList

    def collect_inner(inner_idx: int) -> None:
        inner = _resolve_lookup_index(lookup_list, inner_idx)
        if inner is None:
            return
        for sub in _iter_subtables(inner, 1):
            mapping = getattr(sub, "mapping", None)
            if not mapping:
                continue
            for src, tgt in mapping.items():
                outputs.add(tgt)
                out_to_src[tgt].append(src)
        for sub in _iter_subtables(inner, 4):
            for first, lig_list in sub.ligatures.items():
                for lig in lig_list:
                    outputs.add(lig.LigGlyph)
                    out_to_src[lig.LigGlyph].extend([first] + list(lig.Component))

    def walk(lookup) -> None:
        for sub in lookup.SubTable:
            for attr in (
                "SubstLookupRecord",
            ):
                pass
            for rule_attr in (
                "ChainContextSubstFormat3",
                "ContextSubstFormat3",
            ):
                pass
            slr_lists = []
            if hasattr(sub, "SubstLookupRecord") and sub.SubstLookupRecord:
                slr_lists.append(sub.SubstLookupRecord)
            for set_attr in (
                "SubRuleSet",
                "ChainSubRuleSet",
                "SubClassSet",
                "ChainSubClassSet",
            ):
                rule_set = getattr(sub, set_attr, None)
                if not rule_set:
                    continue
                for rs in rule_set:
                    if rs is None:
                        continue
                    rules = (
                        getattr(rs, "SubRule", None)
                        or getattr(rs, "ChainSubRule", None)
                        or getattr(rs, "SubClassRule", None)
                        or getattr(rs, "ChainSubClassRule", None)
                        or []
                    )
                    for rule in rules:
                        slr = getattr(rule, "SubstLookupRecord", None)
                        if slr:
                            slr_lists.append(slr)
            for slr_list in slr_lists:
                for slr in slr_list:
                    collect_inner(slr.LookupListIndex)

    for lookup in lookup_list.Lookup:
        if lookup.LookupType in (5, 6, 8):
            walk(lookup)
        elif lookup.LookupType == 7:
            for sub in lookup.SubTable:
                inner_type = getattr(sub, "ExtensionLookupType", None)
                ext_sub = getattr(sub, "ExtSubTable", None)
                if inner_type in (5, 6, 8) and ext_sub is not None:
                    pseudo = type(
                        "PseudoLookup",
                        (),
                        {"LookupType": inner_type, "SubTable": [ext_sub]},
                    )
                    walk(pseudo)

    return outputs, dict(out_to_src)


def _alternate_outputs(font: TTFont) -> tuple[set[str], dict[str, list[str]]]:
    """Walk type-3 alternate lookups: src -> [alt1, alt2, ...]."""
    outputs: set[str] = set()
    out_to_src: dict[str, list[str]] = defaultdict(list)
    if "GSUB" not in font:
        return outputs, dict(out_to_src)
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for sub in _iter_subtables(lookup, 3):
            mapping = getattr(sub, "alternates", None) or getattr(sub, "Alternate", None)
            if not mapping:
                continue
            for src, alts in mapping.items():
                seq = list(alts) if not hasattr(alts, "Alternate") else list(alts.Alternate)
                for tgt in seq:
                    outputs.add(tgt)
                    out_to_src[tgt].append(src)
    return outputs, dict(out_to_src)


def diagnose(font_path: Path, *, limit: int = 20) -> None:
    font = TTFont(str(font_path), lazy=False)
    glyph_order = font.getGlyphOrder()
    cmap = font.getBestCmap() or {}
    gname_to_uni = {gname: chr(cp) for cp, gname in cmap.items()}

    gid_map = build_gid_map(font)
    mapped_gnames = {glyph_order[g] for g in gid_map.keys() if g < len(glyph_order)}
    unmapped_gnames = [g for g in glyph_order if g not in mapped_gnames]

    counts = gsub_lookup_type_counts(font)
    ctx_outputs, ctx_out_to_src = _inner_subst_outputs(font)
    alt_outputs, alt_out_to_src = _alternate_outputs(font)

    rules = gsub_lig_rules(font)
    single_rev = gsub_single_subst_reverse(font)
    multiple_fwd = gsub_multiple_subst_forward(font)

    print(f"Font: {font_path}")
    print(f"Total glyphs (getGlyphOrder)         : {len(glyph_order)}")
    print(f"  cmap-addressable (atomic Unicode)  : {len(gname_to_uni)}")
    print(f"  Mapped via cmap + GSUB 1/2/4       : {len(mapped_gnames)}")
    print(f"  Unmapped                           : {len(unmapped_gnames)}")
    print()
    print(f"GSUB lookup counts (incl. Extension inner): {counts}")
    print(f"  type-1 single   rules (target gnames)  : {len(single_rev)}")
    print(f"  type-2 multiple rules (source gnames)  : {len(multiple_fwd)}")
    print(f"  type-4 ligature rules (output gnames)  : {len(rules)}")
    print()

    ctx_unmapped = ctx_outputs - mapped_gnames
    alt_unmapped = alt_outputs - mapped_gnames
    print(f"Contextual (5/6/8) inner substitution outputs : {len(ctx_outputs)}")
    print(f"  ∩ unmapped (potential gain from modelling)  : {len(ctx_unmapped)}")
    print(f"Alternate  (3)    outputs                      : {len(alt_outputs)}")
    print(f"  ∩ unmapped                                   : {len(alt_unmapped)}")
    print()

    if ctx_unmapped:
        print(f"Sample of up to {limit} unmapped contextual outputs:")
        print("  gname                 inner-source(s) -> guessed unicode")
        print("  --------------------- ---------------------------------")
        for tgt in sorted(ctx_unmapped)[:limit]:
            srcs = ctx_out_to_src.get(tgt, [])
            guesses = []
            for s in srcs[:3]:
                u = gname_to_uni.get(s) or _try_resolve(s, gname_to_uni, rules, multiple_fwd, single_rev)
                if u:
                    guesses.append(f"{s}->{u!r}")
                else:
                    guesses.append(f"{s}->?")
            print(f"  {tgt:<22}{', '.join(guesses) if guesses else '(no inner srcs)'}")
        print()

    if alt_unmapped:
        print(f"Sample of up to {limit} unmapped alternate outputs:")
        for tgt in sorted(alt_unmapped)[:limit]:
            srcs = alt_out_to_src.get(tgt, [])
            guess = next(
                (gname_to_uni[s] for s in srcs if s in gname_to_uni), None
            )
            tag = repr(guess) if guess else "?"
            print(f"  {tgt:<22}-> guess {tag}")
        print()

    print("=== Verdict ===")
    if not ctx_unmapped and not alt_unmapped:
        print(
            "Modelling types 3/5/6/8 explicitly would NOT produce any new GID->Unicode "
            "row beyond what cmap + GSUB 1/2/4 already cover."
        )
    else:
        total = len(ctx_unmapped) + len(alt_unmapped)
        print(
            f"At most {total} additional GID(s) could gain a mapping if 3/5/6/8 were "
            "modelled (subject to context being applied correctly at extraction time)."
        )


def _try_resolve(
    gname: str,
    gname_to_uni: dict[str, str],
    rules: dict[str, list[str]],
    multiple_fwd: dict[str, list[str]],
    single_rev: dict[str, list[str]],
    depth: int = 0,
) -> str:
    """Best-effort one-step resolution to a Unicode string for the diagnostic."""
    if depth > 10:
        return ""
    if gname in gname_to_uni:
        return gname_to_uni[gname]
    if gname in rules:
        return "".join(
            _try_resolve(c, gname_to_uni, rules, multiple_fwd, single_rev, depth + 1)
            for c in rules[gname]
        )
    if gname in multiple_fwd:
        return "".join(
            _try_resolve(c, gname_to_uni, rules, multiple_fwd, single_rev, depth + 1)
            for c in multiple_fwd[gname]
        )
    if gname in single_rev:
        for src in single_rev[gname]:
            r = _try_resolve(src, gname_to_uni, rules, multiple_fwd, single_rev, depth + 1)
            if r:
                return r
    return ""


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("font", type=Path, help="Path to .ttf / .otf")
    p.add_argument("--limit", type=int, default=20, help="Sample size in tables (default 20)")
    args = p.parse_args(argv)
    if not args.font.is_file():
        sys.exit(f"font not found: {args.font}")
    diagnose(args.font, limit=args.limit)


if __name__ == "__main__":
    main()
