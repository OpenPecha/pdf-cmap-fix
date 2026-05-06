"""Smoke test for ``scripts/build_per_font_gid_maps.py``."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
HIMALAYA = SCRIPTS / "MicrosoftHimalaya.ttf"


@pytest.mark.skipif(not HIMALAYA.is_file(), reason="MicrosoftHimalaya.ttf not present")
def test_per_font_writer_outputs_gid_map(tmp_path: Path) -> None:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import build_per_font_gid_maps as bpf

    bpf.main(["--fonts-dir", str(SCRIPTS), "--output-dir", str(tmp_path)])

    out = tmp_path / "microsofthimalaya.json"
    assert out.is_file(), "per-font JSON not written"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "microsofthimalaya" in payload
    gmap = payload["microsofthimalaya"]
    # ka + shapkyu / ka + yata are reachable via Single+Ligature decomposition
    # (regression for the GSUB type 1 + 4 fix).
    # We do not pin glyph IDs across font versions; assert the unicode strings exist.
    values = set(gmap.values())
    assert "\u0f40\u0f74" in values  # ka + shapkyu (ུ)
    assert "\u0f40\u0fb1" in values  # ka + yata (ྱ)

    manifest = json.loads((tmp_path / "_manifest.json").read_text(encoding="utf-8"))
    assert "microsofthimalaya" in manifest["fonts_written"]
    assert manifest["count"] == 1
