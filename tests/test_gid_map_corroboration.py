"""Tier-1 GID maps must not overwrite a ToUnicode that is already correct.

Real-world case: ``Opening and Concluding Prayers`` (Padmakara, InDesign) embeds
both legacy ANSI Tibetan (``TibetanChogyal``) and four *different releases* of
the Unicode ``TibetanChogyalUnicode`` family. The legacy faces were repaired
correctly, but the name matcher collapsed the Unicode releases onto one DB entry
(``tibetanchogyalunicodeid`` and ``tibetanchogyalunicode130917u`` both resolve to
``tibetanchogyalunicode`` via the prefix rule), and ``_merge`` then applied that
map unconditionally -- replacing correct Tibetan with values from an unrelated
glyph space (``རྟ`` -> U+F41B, ``༈`` -> ``༉``). 126 already-correct lines broke.

Tier-1 keys are raw GIDs, so they only transfer when the embedded font program
shares the DB font's glyph order; a name match cannot establish that. The fonts
involved are not redistributable, so these tests exercise the decision function
directly rather than through a PDF fixture.
"""
from __future__ import annotations

from pdf_cmap_fix.tounicode_core import (
    MIN_GID_CONFLICTS,
    _gid_map_corroborated,
    _is_tibetan_text,
)


def test_is_tibetan_text_separates_unicode_from_legacy_stand_ins() -> None:
    assert _is_tibetan_text("ཀ")
    assert _is_tibetan_text("སྒྲུབ")
    # Legacy ANSI fonts map codes to Latin-ish stand-ins -- not real Unicode.
    assert not _is_tibetan_text("!")
    assert not _is_tibetan_text("7'Ü#")
    assert not _is_tibetan_text("")
    # PUA is outside the Tibetan block and must not count as protected text.
    assert not _is_tibetan_text("")
    # Mixed content is not wholly Tibetan.
    assert not _is_tibetan_text("ཀa")


def test_rejects_map_from_a_different_glyph_order() -> None:
    # Shape of the real failure: every Tibetan entry contradicted, none agree.
    existing = {13: "༈", 16: "་", 18: "།", 782: "རྟ", 820: "ལྷ"}
    db_map = {13: "༉", 16: "༌", 18: "༏", 782: "", 820: ""}

    assert not _gid_map_corroborated(existing, db_map)


def test_accepts_stacked_syllable_decomposition() -> None:
    # The tool's primary purpose: the DB extends what the PDF only partly had.
    existing = {40: "ས", 41: "བ", 42: "ག", 43: "མ", 44: "ད"}
    db_map = {40: "སྒྲུབ", 41: "བསྐྱེད", 42: "གྲུབ", 43: "མཁྱེན", 44: "དགྲ"}

    assert _gid_map_corroborated(existing, db_map)


def test_accepts_map_that_merely_agrees() -> None:
    existing = {5: "ༀ", 6: "ཀ", 7: "ཁ", 8: "ག", 9: "ང"}

    assert _gid_map_corroborated(existing, dict(existing))


def test_single_corroboration_is_enough_to_accept() -> None:
    # Deliberately conservative: we only reject on *zero* corroboration, so a
    # genuine map with a noisy tail is never dropped.
    existing = {40: "ས", 13: "༈", 16: "་", 18: "།", 782: "རྟ"}
    db_map = {40: "སྒྲུབ", 13: "༉", 16: "༌", 18: "༏", 782: ""}

    assert _gid_map_corroborated(existing, db_map)


def test_legacy_font_entries_are_not_protected() -> None:
    # A legacy ANSI face holds Latin stand-ins; replacing them wholesale is the
    # correct repair, so the guard must stay inert here.
    existing = {33: "!", 34: '"', 35: "#", 36: "$", 37: "%", 38: "&"}
    db_map = {33: "ཀ", 34: "ཁ", 35: "ག", 36: "ང", 37: "ཅ", 38: "ཆ"}

    assert _gid_map_corroborated(existing, db_map)


def test_thin_evidence_does_not_reject() -> None:
    # Below the conflict floor we have no basis to overrule the name match.
    existing = {13: "༈", 16: "་"}
    db_map = {13: "༉", 16: "༌"}

    assert len(existing) < MIN_GID_CONFLICTS
    assert _gid_map_corroborated(existing, db_map)


def test_gap_filling_alone_never_rejects() -> None:
    # Codes absent from the existing map carry no evidence either way.
    existing: dict[int, str] = {}
    db_map = {345: "༝", 359: "ཀ", 364: "ཁ", 381: "ག", 399: "པ"}

    assert _gid_map_corroborated(existing, db_map)


def test_only_referenced_codes_are_weighed() -> None:
    # Contradictions on GIDs the page never draws must not condemn the map.
    existing = {13: "༈", 16: "་", 18: "།", 782: "རྟ", 40: "ས"}
    db_map = {13: "༉", 16: "༌", 18: "༏", 782: "", 40: "སྒྲུབ"}

    assert not _gid_map_corroborated(existing, db_map, referenced={13, 16, 18, 782})
    assert _gid_map_corroborated(existing, db_map, referenced={40})
