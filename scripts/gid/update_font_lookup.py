"""
Create or refresh per-font JSON lookup files from local ``.ttf`` / ``.otf`` / ``.ttc``.

Uses the same cmap + GSUB pipeline as ``build_per_font_gid_maps.py`` (see
``scripts/font_lookup_common/``). **This entrypoint is tier 1 only**
(``_meta.lookup_kind``: ``gid``). For glyph-name or outline-hash lookups, run
``scripts/gname/update_font_lookup.py`` or ``scripts/gshape/update_font_lookup.py``.

Requires: pip install fonttools

Examples::

    python scripts/gid/update_font_lookup.py
    python scripts/gid/update_font_lookup.py D:\\Fonts\\MicrosoftHimalaya.ttf
    python scripts/gid/update_font_lookup.py fonts/A.ttf fonts/B.otf
    python scripts/gid/update_font_lookup.py --lookup-dir pdf_cmap_fix/data/font_lookup my.ttf
    python scripts/gid/update_font_lookup.py --key microsofthimalaya path/to/MicrosoftHimalaya.ttf
    python scripts/gid/update_font_lookup.py --ttc-index 0 --lookup-dir OUT C:\\Windows\\Fonts\\cambria.ttc
    python scripts/gid/update_font_lookup.py --dry-run C:\\Windows\\Fonts\\himalaya.ttf
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
    main_for_kind("gid", argv)


if __name__ == "__main__":
    main()
