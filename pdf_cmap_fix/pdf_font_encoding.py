"""Resolve a simple (Type1 / MMType1 / TrueType) PDF font's char codes to
the ``{char_code (0..255): glyph_name}`` mapping the content stream uses.

This is the simple-font equivalent of the Type0 (Identity-H) assumption
"char code is the GID". Simple fonts in PDFs use a single-byte
``/Encoding`` whose contents are an optional ``/BaseEncoding`` name
(``StandardEncoding``, ``WinAnsiEncoding``, ``MacRomanEncoding``,
``MacExpertEncoding``) overridden one slot at a time by ``/Differences``.

The result is a complete 256-slot lookup so callers can resolve any
char code that may appear in a ``Tj`` / ``TJ`` / ``'`` / ``"`` operator
without re-parsing the font dict.

Empty slots remain ``""`` (a glyph name that no real font carries),
which downstream lookups treat as "no match" without raising.

Spec references: PDF 32000-1:2008 §9.6.5 (Character Encoding), §9.6.6
(predefined encodings) and Annex D.2 (the predefined encoding tables).
"""
from __future__ import annotations

import io
import re
from typing import Dict, Optional

import fitz
from fontTools.ttLib import TTFont

from fontTools.encodings.StandardEncoding import StandardEncoding
from fontTools.encodings.MacRoman import MacRoman as _MacRomanEncoding


# WinAnsiEncoding (PDF 32000-1:2008 Annex D.2). fontTools does not ship
# this table, but it is exactly the union of StandardEncoding's
# alphanumerics + a curated set of Windows-1252-style code points.
#
# The list is indexed by char code 0..255. Slots not assigned by the
# PDF standard are filled with the empty string.
WIN_ANSI_ENCODING: list = [""] * 256
for _code, _name in {
    32: "space", 33: "exclam", 34: "quotedbl", 35: "numbersign",
    36: "dollar", 37: "percent", 38: "ampersand", 39: "quotesingle",
    40: "parenleft", 41: "parenright", 42: "asterisk", 43: "plus",
    44: "comma", 45: "hyphen", 46: "period", 47: "slash",
    48: "zero", 49: "one", 50: "two", 51: "three", 52: "four",
    53: "five", 54: "six", 55: "seven", 56: "eight", 57: "nine",
    58: "colon", 59: "semicolon", 60: "less", 61: "equal", 62: "greater",
    63: "question", 64: "at",
    65: "A", 66: "B", 67: "C", 68: "D", 69: "E", 70: "F", 71: "G",
    72: "H", 73: "I", 74: "J", 75: "K", 76: "L", 77: "M", 78: "N",
    79: "O", 80: "P", 81: "Q", 82: "R", 83: "S", 84: "T", 85: "U",
    86: "V", 87: "W", 88: "X", 89: "Y", 90: "Z",
    91: "bracketleft", 92: "backslash", 93: "bracketright",
    94: "asciicircum", 95: "underscore", 96: "grave",
    97: "a", 98: "b", 99: "c", 100: "d", 101: "e", 102: "f", 103: "g",
    104: "h", 105: "i", 106: "j", 107: "k", 108: "l", 109: "m",
    110: "n", 111: "o", 112: "p", 113: "q", 114: "r", 115: "s",
    116: "t", 117: "u", 118: "v", 119: "w", 120: "x", 121: "y", 122: "z",
    123: "braceleft", 124: "bar", 125: "braceright", 126: "asciitilde",
    # 0x80..0x9F: Windows-1252 extras
    128: "Euro", 130: "quotesinglbase", 131: "florin",
    132: "quotedblbase", 133: "ellipsis", 134: "dagger",
    135: "daggerdbl", 136: "circumflex", 137: "perthousand",
    138: "Scaron", 139: "guilsinglleft", 140: "OE", 142: "Zcaron",
    145: "quoteleft", 146: "quoteright", 147: "quotedblleft",
    148: "quotedblright", 149: "bullet", 150: "endash",
    151: "emdash", 152: "tilde", 153: "trademark",
    154: "scaron", 155: "guilsinglright", 156: "oe", 158: "zcaron",
    159: "Ydieresis",
    # 0xA0..0xFF: Latin-1 supplement
    160: "space", 161: "exclamdown", 162: "cent", 163: "sterling",
    164: "currency", 165: "yen", 166: "brokenbar", 167: "section",
    168: "dieresis", 169: "copyright", 170: "ordfeminine",
    171: "guillemotleft", 172: "logicalnot", 173: "hyphen",
    174: "registered", 175: "macron", 176: "degree", 177: "plusminus",
    178: "twosuperior", 179: "threesuperior", 180: "acute",
    181: "mu", 182: "paragraph", 183: "periodcentered", 184: "cedilla",
    185: "onesuperior", 186: "ordmasculine", 187: "guillemotright",
    188: "onequarter", 189: "onehalf", 190: "threequarters",
    191: "questiondown",
    192: "Agrave", 193: "Aacute", 194: "Acircumflex", 195: "Atilde",
    196: "Adieresis", 197: "Aring", 198: "AE", 199: "Ccedilla",
    200: "Egrave", 201: "Eacute", 202: "Ecircumflex", 203: "Edieresis",
    204: "Igrave", 205: "Iacute", 206: "Icircumflex", 207: "Idieresis",
    208: "Eth", 209: "Ntilde", 210: "Ograve", 211: "Oacute",
    212: "Ocircumflex", 213: "Otilde", 214: "Odieresis", 215: "multiply",
    216: "Oslash", 217: "Ugrave", 218: "Uacute", 219: "Ucircumflex",
    220: "Udieresis", 221: "Yacute", 222: "Thorn", 223: "germandbls",
    224: "agrave", 225: "aacute", 226: "acircumflex", 227: "atilde",
    228: "adieresis", 229: "aring", 230: "ae", 231: "ccedilla",
    232: "egrave", 233: "eacute", 234: "ecircumflex", 235: "edieresis",
    236: "igrave", 237: "iacute", 238: "icircumflex", 239: "idieresis",
    240: "eth", 241: "ntilde", 242: "ograve", 243: "oacute",
    244: "ocircumflex", 245: "otilde", 246: "odieresis", 247: "divide",
    248: "oslash", 249: "ugrave", 250: "uacute", 251: "ucircumflex",
    252: "udieresis", 253: "yacute", 254: "thorn", 255: "ydieresis",
}.items():
    WIN_ANSI_ENCODING[_code] = _name


def _base_encoding_table(name: str) -> list:
    """Return the 256-slot table for a predefined base encoding name."""
    if name in ("WinAnsiEncoding", "/WinAnsiEncoding"):
        return list(WIN_ANSI_ENCODING)
    if name in ("MacRomanEncoding", "/MacRomanEncoding"):
        return list(_MacRomanEncoding)
    if name in ("StandardEncoding", "/StandardEncoding"):
        return list(StandardEncoding)
    if name in ("MacExpertEncoding", "/MacExpertEncoding"):
        # Mac Expert is extremely rare and only used by ornament fonts;
        # treat it as an empty table -- callers will fall back to
        # /Differences-only.
        return [""] * 256
    return [""] * 256


# Parse /Differences arrays like ``[1 /uniE1D4 /uniE170 127 /uniE14E]``.
# Each "code" is an integer between 0 and 255; each "/name" reassigns
# successive code slots from the most recent integer.
_DIFFS_TOKEN_RE = re.compile(
    r"(\d+)|/([A-Za-z._0-9][A-Za-z._0-9]*)"
)


def _parse_differences(diffs_text: str, table: list) -> list:
    """Apply a /Differences body (already stripped of [] brackets) on top
    of an existing 256-slot ``table``. Returns a new list (the input is
    not modified)."""

    out = list(table)
    cur = -1
    for m in _DIFFS_TOKEN_RE.finditer(diffs_text):
        if m.group(1) is not None:
            cur = int(m.group(1))
        else:
            if 0 <= cur <= 255:
                out[cur] = m.group(2)
            cur += 1
    return out


def _xref_object_safe(doc: fitz.Document, xref: int) -> Optional[str]:
    if xref <= 0:
        return None
    try:
        return doc.xref_object(xref)
    except Exception:
        return None


def parse_pdf_encoding(
    doc: fitz.Document, font_xref: int
) -> Dict[int, str]:
    """Return ``{char_code: glyph_name}`` for a simple-encoding PDF font.

    Handles three shapes the PDF spec allows for the ``/Encoding`` entry:

    * Name (e.g. ``/WinAnsiEncoding``) -- the corresponding predefined
      table is returned verbatim.
    * Dict (the common case) -- a ``/BaseEncoding`` name is loaded if
      present (default: ``StandardEncoding``), then the ``/Differences``
      array is applied on top.
    * Missing -- returns an empty mapping. Call
      :func:`resolve_simple_encoding` to fall back to the embedded
      TrueType cmap (Quartz / Affinity / some Ghostscript subsets).

    Slots that remain unassigned are omitted from the returned dict so
    the caller can use ``.get(code)`` cleanly.
    """

    obj_text = _xref_object_safe(doc, font_xref)
    if obj_text is None:
        return {}

    enc_key = None
    try:
        enc_key = doc.xref_get_key(font_xref, "Encoding")
    except Exception:
        return {}

    if not enc_key:
        return {}

    kind, value = enc_key[0], enc_key[1]
    table: list

    if kind == "name":
        # ``/WinAnsiEncoding`` etc.
        table = _base_encoding_table(value)
    elif kind == "xref":
        # Indirect reference to a dictionary -- read it.
        try:
            ref_xref = int(value.split()[0])
        except (ValueError, IndexError):
            return {}
        enc_obj_text = _xref_object_safe(doc, ref_xref)
        if enc_obj_text is None:
            return {}
        table = _table_from_encoding_dict_text(enc_obj_text)
    elif kind == "dict":
        # Inline dictionary.
        table = _table_from_encoding_dict_text(value)
    else:
        return {}

    return {cc: gn for cc, gn in enumerate(table) if gn}


def _table_from_encoding_dict_text(dict_text: str) -> list:
    """Given the textual form of an Encoding dictionary, return its
    256-slot resolved table."""

    base_match = re.search(
        r"/BaseEncoding\s+/([A-Za-z]+)", dict_text
    )
    base_name = base_match.group(1) if base_match else "StandardEncoding"
    table = _base_encoding_table(base_name)

    diff_match = re.search(
        r"/Differences\s*\[(.*?)\]", dict_text, re.DOTALL
    )
    if diff_match:
        table = _parse_differences(diff_match.group(1), table)
    return table


# Preferred cmap platforms for a TrueType font's built-in encoding
# (PDF 32000-1:2008 §9.6.6.4): Windows Symbol, then Macintosh Roman.
_BUILTIN_CMAP_PREF = (
    (3, 0),
    (1, 0),
)


def _char_code_from_cmap_key(cp: int, platform_id: int, plat_enc_id: int) -> Optional[int]:
    """Map a cmap codepoint to a 1-byte PDF char code, or ``None``.

    Windows Symbol (3, 0) often stores keys in ``0xF000..0xF0FF``; the PDF
    char code is the low byte. Macintosh Roman (1, 0) and remapped subset
    cmaps use the codepoint itself when it already fits in a byte.
    """
    if platform_id == 3 and plat_enc_id == 0 and 0xF000 <= cp <= 0xF0FF:
        return cp & 0xFF
    if 0 <= cp <= 255:
        return cp
    return None


def _cmap_table_to_encoding(table) -> Dict[int, str]:
    out: Dict[int, str] = {}
    plat, enc = table.platformID, table.platEncID
    for cp, gname in table.cmap.items():
        if not gname or gname == ".notdef":
            continue
        code = _char_code_from_cmap_key(cp, plat, enc)
        if code is None:
            continue
        out[code] = gname
    return out


def parse_embedded_ttf_encoding(
    doc: fitz.Document, font_xref: int
) -> Dict[int, str]:
    """Read ``{char_code: glyph_name}`` from an embedded TrueType cmap.

    Used when the PDF ``/Font`` dict has no ``/Encoding`` (symbolic Quartz /
    Affinity subsets, some Ghostscript outputs). The subset cmap is the
    built-in encoding: its keys *are* the 1-byte codes the content stream
    uses, and the glyph names are whatever the subsetter kept (often
    ``uniXXXX`` / ``uniXXXXYYYY`` for Unicode Tibetan faces).
    """
    try:
        tup = doc.extract_font(font_xref)
        if not tup or len(tup) < 4:
            return {}
        buf = tup[3]
        if not buf or not isinstance(buf, (bytes, bytearray)):
            return {}
        tt = TTFont(io.BytesIO(bytes(buf)), lazy=False)
    except Exception:
        return {}
    try:
        cmap = tt.get("cmap")
        if cmap is None or not getattr(cmap, "tables", None):
            return {}
        for plat, enc in _BUILTIN_CMAP_PREF:
            for table in cmap.tables:
                if table.platformID == plat and table.platEncID == enc and table.cmap:
                    resolved = _cmap_table_to_encoding(table)
                    if resolved:
                        return resolved
        # Last resort: any cmap whose keys all collapse to a single byte
        # (typical of a subsetter that remapped a Unicode cmap in place).
        for table in cmap.tables:
            if not table.cmap:
                continue
            if all(
                _char_code_from_cmap_key(cp, table.platformID, table.platEncID) is not None
                for cp in table.cmap
            ):
                resolved = _cmap_table_to_encoding(table)
                if resolved:
                    return resolved
        return {}
    finally:
        try:
            tt.close()
        except Exception:
            pass


def resolve_simple_encoding(
    doc: fitz.Document, font_xref: int
) -> Dict[int, str]:
    """``/Encoding`` if present, otherwise the embedded TrueType cmap."""
    enc = parse_pdf_encoding(doc, font_xref)
    if enc:
        return enc
    return parse_embedded_ttf_encoding(doc, font_xref)
