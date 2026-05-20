"""
Bulk-write **GID → Unicode** per-font JSON from ZIP archives and/or font directories.

For glyph-name or outline-hash keys, use ``scripts/gname/build_per_font_gname_maps.py``
or ``scripts/gshape/build_per_font_gshape_maps.py`` instead.

Examples::

    python scripts/gid/build_per_font_gid_maps.py \\
        --zip fonts/bodyig.zip \\
        --zip fonts/tibetan-fonts-main.zip \\
        --zip fonts/tibetan-fonts-private-main.zip

    python scripts/gid/build_per_font_gid_maps.py --fonts-dir scripts
    python scripts/gid/build_per_font_gid_maps.py --zip a.zip -o other_dir/font_lookup
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_COMMON = _SCRIPTS / "font_lookup_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

REPO_ROOT = _SCRIPTS.parent
DEFAULT_OUT = REPO_ROOT / "pdf_cmap_fix" / "data" / "font_lookup"

from per_font_maps import run_per_font_cli  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    run_per_font_cli(
        argv,
        kind="gid",
        default_out=DEFAULT_OUT,
        description=(
            "Write one JSON per font (GID decimal string → Unicode) under the output "
            "directory. GSUB types handled: 1, 2, 4 (and 7 wrappers)."
        ),
        example_invocation="python scripts/gid/build_per_font_gid_maps.py --zip fonts/bodyig.zip",
    )


if __name__ == "__main__":
    main()
