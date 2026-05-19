"""Regression: gshape patch must mutate the live inner dict (not a copy)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_COMMON = REPO / "scripts" / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

from pua_gshape_patcher import first_inner_map, patch_gshape_data, build_hash_to_gname  # noqa: E402


def test_first_inner_map_is_same_object_as_nested_dict() -> None:
    data = {"face": {"h1": "x"}, "_meta": {}}
    key, inner = first_inner_map(data)
    assert key == "face"
    inner["h1"] = "y"
    assert data["face"]["h1"] == "y"


def test_patch_gshape_data_mutates_original_inner(monkeypatch) -> None:
    """Stable hash→gname map + PUA in value → in-place replacement on original dict."""
    import pua_gshape_patcher

    def fake_build_hash_to_gname(_font):
        return {"fp1": "uni0041"}, 0

    monkeypatch.setattr(pua_gshape_patcher, "build_hash_to_gname", fake_build_hash_to_gname)

    data = {"inner": {"fp1": "\uf305"}, "_meta": {}}
    patched, no_gn, no_pua, collisions = patch_gshape_data(
        font=object(),
        gshape_data=data,
        public_gname_inner={"uni0041": "A"},
    )
    assert patched == 1
    assert no_gn == 0
    assert no_pua == 0
    assert collisions == 0
    assert data["inner"]["fp1"] == "A"
    assert data["_meta"]["gshape_rows_patched_from_public_gname"] == 1
