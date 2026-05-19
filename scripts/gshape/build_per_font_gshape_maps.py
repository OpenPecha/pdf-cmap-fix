"""
Bulk-write **outline fingerprint → Unicode** per-font JSON from ZIP archives and/or directories.

Tier 1: ``scripts/gid/build_per_font_gid_maps.py``. Tier 2: ``scripts/gname/build_per_font_gname_maps.py``.

Shared bulk logic: ``scripts/font_lookup_common/per_font_maps.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

REPO_ROOT = _SCRIPTS.parent
DEFAULT_OUT = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gshape"

from per_font_maps import run_per_font_cli  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    run_per_font_cli(
        argv,
        kind="gshape",
        default_out=DEFAULT_OUT,
        description=(
            "Write one JSON per font (outline hash → Unicode) using HashPointPen fingerprints."
        ),
        example_invocation=(
            "python scripts/gshape/build_per_font_gshape_maps.py "
            "--zip fonts/bodyig.zip --zip fonts/tibetan-fonts-main.zip"
        ),
    )


if __name__ == "__main__":
    main()
