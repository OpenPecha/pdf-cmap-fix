"""Regression tests for name-index (font-ID) based font matching.

Both cases use a two-page excerpt of a real PDF (``Swift Path (Eng) v 4,00``):

* page 1 embeds ``TimesNewRomanPSMT`` / ``TimesNewRomanPS-ItalicMT`` (Type0),
  which must NOT match any Tibetan lookup. The legacy filename-stem matcher
  picked ``ma`` (from ``MA______.TTF``, whose real name is "Mantra") because
  ``"ma"`` is a substring of ``"timesnewromanpsmt"``.
* page 2 embeds ``TibetanChogyalUnicode-141208`` (Type0). The correct match is
  the 2014 release whose PostScript name is ``TibetanChogyalUnicode`` (indexed
  as ``tibetanchogyalunicode``), NOT the unrelated 218-glyph ``tibetanchogyal``
  font and NOT the different 2017 release ``tibetanchogyalunicode170221``.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from pdf_cmap_fix.gid.extractor import FONT_LOOKUP_DIR, collect_font_merges

EXCERPT = Path(__file__).resolve().parent / "data" / "swift-path-excerpt.pdf"

pytestmark = pytest.mark.skipif(
    not EXCERPT.is_file() or not (FONT_LOOKUP_DIR / "_name_index.json").is_file(),
    reason="excerpt fixture or font-ID lookup index not present",
)


def _records_by_font_name() -> dict[str, dict]:
    doc = fitz.open(str(EXCERPT))
    try:
        records, _ = collect_font_merges(doc)
    finally:
        doc.close()
    return {r["pdf_font_name"]: r for r in records}


def _matched_font_meta(record: dict) -> dict:
    """Load the ``_meta`` of the lookup file the record matched."""
    fid = record["db_key_matched"]
    assert fid is not None
    data = json.loads((FONT_LOOKUP_DIR / f"{fid}.json").read_text(encoding="utf-8"))
    return data["_meta"]


def test_times_new_roman_does_not_match_a_tibetan_font() -> None:
    by_name = _records_by_font_name()
    for name in (
        "BLFHIQ+TimesNewRomanPSMT",
        "THCGAG+TimesNewRomanPS-ItalicMT",
    ):
        assert name in by_name, f"expected {name} in excerpt"
        rec = by_name[name]
        assert rec["db_key_matched"] is None, (
            f"{name} should not match any lookup, got "
            f"{rec.get('db_name_matched')!r}"
        )
        assert rec["changed"] == 0


def test_tibetan_chogyal_unicode_matches_correct_2014_release() -> None:
    by_name = _records_by_font_name()
    name = "SGMVMI+TibetanChogyalUnicode-141208"
    assert name in by_name
    rec = by_name[name]

    assert rec["db_name_matched"] == "tibetanchogyalunicode", (
        "should resolve to the TibetanChogyalUnicode PostScript name, not the "
        f"date-suffixed alias, got {rec['db_name_matched']!r}"
    )
    assert rec["db_key_matched"] is not None
    assert rec["changed"] > 0

    meta = _matched_font_meta(rec)
    # The matched face must be the 2014 release (PS name TibetanChogyalUnicode,
    # ~1000+ mapped GIDs), not the sparse 218-glyph "tibetanchogyal" (TICGN)
    # font nor the different 2017 release.
    norms = {n["norm"] for n in meta.get("names", [])}
    assert "tibetanchogyalunicode" in norms
    assert "tibetanchogyalunicode170221" not in norms
    assert "170221" not in meta.get("source", "")
    assert meta.get("gids_mapped", 0) > 900
