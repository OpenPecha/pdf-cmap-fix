"""
pdf_cmap_fix
============

Fix incorrect or incomplete PDF ``/ToUnicode`` CMaps using a GSUB-derived
GID→Unicode database (primarily Tibetan Monlam / Himalaya / Jomolhari fonts),
then extract text or emit a patched PDF.

The default public API is **tier 1 (gid)**. For glyph-name or outline-hash
lookups, use ``pdf_cmap_fix.gname.extractor`` or ``pdf_cmap_fix.gshape.extractor``
(or the ``pdf-cmap-fix-gname`` / ``pdf-cmap-fix-gshape`` console scripts).

Public API (gid)
----------------
    from pdf_cmap_fix import extract_pdf_text, patch_pdf, build_tounicode_dict

    result = extract_pdf_text("doc.pdf")
    print(result["patched"])

    patch_pdf("doc.pdf")  # writes doc.patched.pdf

    cmap = build_tounicode_dict("doc.pdf")  # no PDF mutation; ``fonts`` / ``stats``
"""

from .gid.extractor import (
    FONT_LOOKUP_DIR,
    build_tounicode_dict,
    collect_font_merges,
    extract_all,
    extract_pdf_text,
    patch_doc,
    patch_pdf,
)
from .gname.extractor import FONT_LOOKUP_GNAME_DIR
from .gshape.extractor import FONT_LOOKUP_GSHAPE_DIR

__version__ = "0.3.0"
__all__ = [
    "FONT_LOOKUP_DIR",
    "FONT_LOOKUP_GNAME_DIR",
    "FONT_LOOKUP_GSHAPE_DIR",
    "build_tounicode_dict",
    "collect_font_merges",
    "extract_all",
    "extract_pdf_text",
    "patch_doc",
    "patch_pdf",
]
