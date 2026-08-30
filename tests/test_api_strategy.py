"""Tests for the public ``strategy=`` argument on the gid API.

Mirrors the CLI auto-selection (``test_auto_strategy.py``) but exercises it
through ``patch_pdf`` / ``extract_pdf_text`` / ``build_tounicode_dict`` so
programmatic callers can auto-select (or pin) a lookup strategy without going
through the CLI.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pdf_cmap_fix import build_tounicode_dict, extract_pdf_text, patch_pdf
from pdf_cmap_fix.gid.extractor import FONT_LOOKUP_DIR

REPO = Path(__file__).resolve().parents[1]
ISSUE16_PAGE = REPO / "tests" / "fixtures" / "issue16-page1.pdf"
EXPECTED_TIBETAN = "གང་ཐུགས་བདེ་ཆེན"


def _has_thai(text: str) -> bool:
    return any("฀" <= c <= "๿" for c in text)


def _pua_free_installed() -> bool:
    return (FONT_LOOKUP_DIR.parent / "font_lookup_gid_pua_free").is_dir()


def test_default_is_unchanged_and_adds_no_strategy_key(tmp_path):
    # strategy=None must behave exactly like before: default gid tier, and no
    # new "strategy" key bolted onto stats.
    res = patch_pdf(ISSUE16_PAGE, output_path=str(tmp_path / "o.pdf"), write_file=True)
    assert "strategy" not in res["stats"]


@pytest.mark.skipif(not _pua_free_installed(), reason="gid-pua-free tree not installed")
def test_named_strategy_pins_that_tree():
    res = extract_pdf_text(ISSUE16_PAGE, write_files=False, strategy="gid-pua-free")
    assert res["stats"]["strategy"] == "gid-pua-free"
    assert not _has_thai(res["patched"])
    assert EXPECTED_TIBETAN in res["patched"]


@pytest.mark.skipif(not _pua_free_installed(), reason="gid-pua-free tree not installed")
def test_subset_auto_selects_pua_free_for_issue16():
    # The issue #16 page is garbage under gid and clean under gid-pua-free, so an
    # auto-select over just those two must pick the PUA-free tree.
    res = extract_pdf_text(
        ISSUE16_PAGE, write_files=False, strategy=["gid", "gid-pua-free"]
    )
    assert res["stats"]["strategy"] == "gid-pua-free"
    assert not _has_thai(res["patched"])


def test_auto_yields_clean_tibetan():
    res = extract_pdf_text(ISSUE16_PAGE, write_files=False, strategy="auto")
    assert res["stats"]["strategy"]  # some strategy was chosen
    assert not _has_thai(res["patched"])
    assert EXPECTED_TIBETAN in res["patched"]


def test_build_tounicode_dict_accepts_strategy():
    out = build_tounicode_dict(ISSUE16_PAGE, strategy="auto")
    assert out["stats"]["strategy"]


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        extract_pdf_text(ISSUE16_PAGE, write_files=False, strategy="does-not-exist")


def test_strategy_and_font_lookup_dir_conflict():
    with pytest.raises(ValueError):
        extract_pdf_text(
            ISSUE16_PAGE,
            write_files=False,
            font_lookup_dir=FONT_LOOKUP_DIR,
            strategy="auto",
        )
