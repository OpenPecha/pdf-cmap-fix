"""
Create or refresh **gshape** (outline hash → Unicode) per-font JSON from ``.ttf`` / ``.otf`` / ``.ttc``.

Default output: ``pdf_cmap_fix/data/font_lookup_gshape/``. Shared implementation:
``scripts/font_lookup_common/single_font_lookup.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

from single_font_lookup import main_for_kind  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    main_for_kind("gshape", argv)


if __name__ == "__main__":
    main()
