"""Walk PDF content streams to discover which GIDs each font actually uses.

This is used by :func:`pdf_cmap_fix.tounicode_core.collect_font_merges` to
filter the set of GIDs eligible for an upgrade. Without it, a Type0
subset font matched against a 1500-entry DB lookup would be flagged as
having ~1400 "missing" mappings even though its CMap is complete for the
~50-100 GIDs that the document actually references - leading to a no-op
re-write of every subset's ToUnicode stream.

The parser is intentionally minimal: it only needs to tell us *which*
GIDs each ``/Fname`` (Type0 / Identity-H) refers to in ``Tj``, ``TJ``,
``'`` and ``"`` text-show operators. It does not interpret positioning,
state, or graphics. For each text string we read 2 bytes at a time as
GID values - which is what Identity-H means.

Anything we cannot parse is silently dropped: callers fall back to the
existing-ToUnicode keys, which for Word-style subsets already lists the
exact referenced GIDs.
"""
from __future__ import annotations

import re
from typing import Dict, Iterator, Optional, Set, Tuple

import fitz

# Match a font-selection op like ``/F2 12 Tf``. We re-search a small
# backward window when the bytes ``Tf`` appear, rather than tokenising
# the whole stream up-front.
_TF_RE = re.compile(rb"/([A-Za-z][A-Za-z0-9_]*)\s+[-+]?[\d.]+\s+Tf")
# ``/Fname size_xref 0 R`` references inside a /Font resource dict.
_FONT_REF_RE = re.compile(r"/([A-Za-z][A-Za-z0-9_]*)\s+(\d+)\s+0\s+R")

_OCTAL_ESCAPES = {0x6E: 0x0A, 0x72: 0x0D, 0x74: 0x09, 0x62: 0x08, 0x66: 0x0C}


def _decode_pdf_literal(blob: bytes) -> bytes:
    """Decode a PDF literal-string body (without the surrounding parens)."""
    out = bytearray()
    i = 0
    n = len(blob)
    while i < n:
        b = blob[i]
        if b != 0x5C:  # backslash
            out.append(b)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        nxt = blob[i]
        if nxt in b"nrtbf":
            out.append(_OCTAL_ESCAPES[nxt])
            i += 1
        elif nxt in b"()\\":
            out.append(nxt)
            i += 1
        elif nxt == 0x0A:
            i += 1
        elif nxt == 0x0D:
            i += 1
            if i < n and blob[i] == 0x0A:
                i += 1
        elif 0x30 <= nxt <= 0x37:  # octal escape, up to 3 digits
            j = 0
            val = 0
            while j < 3 and i + j < n and 0x30 <= blob[i + j] <= 0x37:
                val = (val << 3) | (blob[i + j] - 0x30)
                j += 1
            out.append(val & 0xFF)
            i += j
        else:
            out.append(nxt)
            i += 1
    return bytes(out)


def _decode_hex_string(blob: bytes) -> bytes:
    """Decode the body of a ``<...>`` hex string into raw bytes."""
    hex_blob = bytes(b for b in blob if b not in b" \t\r\n")
    if len(hex_blob) % 2 == 1:
        hex_blob += b"0"
    try:
        return bytes.fromhex(hex_blob.decode("ascii"))
    except ValueError:
        return b""


def _scan_string(stream: bytes, start: int) -> Tuple[int, bytes]:
    """Return ``(end, payload)`` for a ``(...)`` literal starting at ``start``."""
    n = len(stream)
    depth = 1
    j = start
    body_start = j
    while j < n and depth > 0:
        ch = stream[j]
        if ch == 0x5C:  # escape: skip the next byte
            j += 2
            continue
        if ch == 0x28:  # '('
            depth += 1
        elif ch == 0x29:  # ')'
            depth -= 1
            if depth == 0:
                break
        j += 1
    return j + 1, _decode_pdf_literal(stream[body_start:j])


def _scan_hex(stream: bytes, start: int) -> Tuple[int, bytes]:
    """Return ``(end, payload)`` for a ``<...>`` hex string starting at ``start``."""
    n = len(stream)
    j = start
    while j < n and stream[j] != 0x3E:  # '>'
        j += 1
    return j + 1, _decode_hex_string(stream[start:j])


def _peek_op(stream: bytes, pos: int) -> Optional[bytes]:
    """Return the next non-whitespace operator token after ``pos``."""
    n = len(stream)
    j = pos
    while j < n and stream[j] in b" \t\r\n":
        j += 1
    if j >= n:
        return None
    k = j
    while k < n and stream[k] not in b" \t\r\n()<>[]/%{}":
        k += 1
    return stream[j:k] or None


def _iter_text_strings(stream: bytes) -> Iterator[Tuple[Optional[bytes], bytes]]:
    """Yield ``(font_name_or_None, payload_bytes)`` for every text-show op.

    We track the most recently selected ``/Fname size Tf`` and emit it
    alongside each string. ``Tj``, ``TJ``, ``'`` and ``"`` are all
    handled the same way - we only care about the bytes shown, not the
    spacing semantics.
    """
    cur_font: Optional[bytes] = None
    i = 0
    n = len(stream)
    while i < n:
        c = stream[i]
        if c == 0x25:  # '%' comment, runs to EOL
            while i < n and stream[i] not in b"\r\n":
                i += 1
            continue
        if c == 0x28:  # '(' literal string
            i, payload = _scan_string(stream, i + 1)
            op = _peek_op(stream, i)
            if op in (b"Tj", b"'", b'"'):
                yield cur_font, payload
            continue
        if c == 0x3C:  # '<' hex string (or '<<' which we ignore here)
            if i + 1 < n and stream[i + 1] == 0x3C:
                i += 2
                continue
            i, payload = _scan_hex(stream, i + 1)
            op = _peek_op(stream, i)
            if op in (b"Tj", b"'", b'"'):
                yield cur_font, payload
            continue
        if c == 0x5B:  # '[' TJ array - concatenate every string inside
            i += 1
            buf = bytearray()
            while i < n and stream[i] != 0x5D:
                ch = stream[i]
                if ch == 0x28:
                    i, payload = _scan_string(stream, i + 1)
                    buf += payload
                elif ch == 0x3C and (i + 1 >= n or stream[i + 1] != 0x3C):
                    i, payload = _scan_hex(stream, i + 1)
                    buf += payload
                else:
                    i += 1
            i += 1  # skip ']'
            op = _peek_op(stream, i)
            if op == b"TJ":
                yield cur_font, bytes(buf)
            continue
        if c == 0x54 and stream[i : i + 2] == b"Tf":
            # Resolve the font from a small backward window. We want
            # the match whose ``Tf`` lines up with our position, so we
            # take the *last* occurrence inside the window. A full
            # tokeniser would be more robust but is overkill here.
            window = stream[max(0, i - 64) : i + 2]
            matches = _TF_RE.findall(window)
            if matches:
                cur_font = matches[-1]
            i += 2
            continue
        i += 1


def _resource_font_xref_map(
    doc: fitz.Document, page: fitz.Page
) -> Dict[bytes, int]:
    """Return ``{b"F2": font_xref}`` for one page (resolves /Resources)."""
    out: Dict[bytes, int] = {}
    seen: Set[int] = set()
    cur = page.xref
    fonts_obj_xref: Optional[int] = None
    while cur and cur not in seen:
        seen.add(cur)
        font_entry = doc.xref_get_key(cur, "Resources/Font")
        if font_entry and font_entry[0] == "xref":
            fonts_obj_xref = int(font_entry[1].split()[0])
            break
        if font_entry and font_entry[0] == "dict":
            for m in _FONT_REF_RE.finditer(font_entry[1]):
                out[m.group(1).encode("latin-1")] = int(m.group(2))
            return out
        parent = doc.xref_get_key(cur, "Parent")
        cur = int(parent[1].split()[0]) if parent and parent[0] == "xref" else 0
    if fonts_obj_xref is not None:
        try:
            font_dict_str = doc.xref_object(fonts_obj_xref)
        except Exception:
            return out
        for m in _FONT_REF_RE.finditer(font_dict_str):
            out[m.group(1).encode("latin-1")] = int(m.group(2))
    return out


def collect_referenced_gids(
    doc: fitz.Document,
    *,
    type0_xrefs: Optional[Set[int]] = None,
) -> Dict[int, Set[int]]:
    """Return ``{font_xref: {gid, ...}}`` for Type0 (Identity-H) fonts.

    For each page we walk the content stream once, attribute every text
    string to the most recent ``/Fname size Tf`` selection, look the
    name up in the page's ``/Resources/Font`` dictionary, and decode
    the string two bytes at a time as GIDs. ``type0_xrefs``, when
    provided, restricts which fonts get recorded - callers typically
    pass the set of Type0 font xrefs they discovered in advance to
    avoid recording GIDs from simple-encoding TrueType fonts.
    """
    out: Dict[int, Set[int]] = {}
    for pno in range(len(doc)):
        page = doc[pno]
        try:
            stream = page.read_contents()
        except Exception:
            continue
        if not stream:
            continue
        name_to_xref = _resource_font_xref_map(doc, page)
        if not name_to_xref:
            continue
        for fname, payload in _iter_text_strings(stream):
            if fname is None:
                continue
            xref = name_to_xref.get(fname)
            if xref is None:
                continue
            if type0_xrefs is not None and xref not in type0_xrefs:
                continue
            bucket = out.setdefault(xref, set())
            if len(payload) < 2:
                continue
            for k in range(0, len(payload) - 1, 2):
                bucket.add((payload[k] << 8) | payload[k + 1])
    return out
