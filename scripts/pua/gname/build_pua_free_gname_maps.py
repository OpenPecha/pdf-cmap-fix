"""
Bulk-write **PUA-free gname** per-font JSON from ZIP archives and/or directories.

Reads each font, builds the gname lookup (glyph name → Unicode), then rewrites any
PUA values whose glyph name follows the ``uni…`` encoding convention.  Output goes
directly to ``font_lookup_gname_pua_free/`` (no intermediate gname dir needed).

This must run **before** ``scripts/pua/gshape/`` and ``scripts/pua/gid/`` — both
those scripts take ``--gname-dir`` pointing at the output of this script.

Example::

    # Bulk from ZIP archives
    python scripts/pua/gname/build_pua_free_gname_maps.py \\
      --zip fonts/bodyig.zip --zip fonts/tibetan-fonts-main.zip

    # Custom output directory
    python scripts/pua/gname/build_pua_free_gname_maps.py \\
      --zip fonts/bodyig.zip -o ./builds/custom_gname_pua_free

    # From a folder of loose .ttf / .otf
    python scripts/pua/gname/build_pua_free_gname_maps.py \\
      --fonts-dir /path/to/fonts -o ./builds/custom_gname_pua_free
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2]  # scripts/
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

REPO_ROOT = _SCRIPTS.parent
DEFAULT_OUT = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup_gname_pua_free"

from per_font_maps import run_per_font_cli  # noqa: E402
from pua_gname_rewriter import rewrite_gname_lookup_pua_values  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    run_per_font_cli(
        argv,
        kind="gname",
        default_out=DEFAULT_OUT,
        description=(
            "Write one PUA-free gname JSON per font. "
            "Glyph name -> Unicode, with PUA values rewritten using uni... name decoding."
        ),
        example_invocation=(
            "python scripts/pua/gname/build_pua_free_gname_maps.py "
            "--zip fonts/bodyig.zip --zip fonts/tibetan-fonts-main.zip"
        ),
        pua_postprocess_fn=rewrite_gname_lookup_pua_values,
    )


if __name__ == "__main__":
    main()
