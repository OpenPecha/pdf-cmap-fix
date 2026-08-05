"""
Detect and neutralise duplicate stroke+fill text objects.

Some DTP tools (observed so far: InDesign, on Tibetan title text set with
a "stroke" character style) paint the same glyph run **twice** as two
separate ``BT ... ET`` text objects at the identical text-matrix origin --
once under a stroke-only render mode (``1 Tr``) and again under the
default fill mode (``0 Tr`` / unset) -- to fake a bold or outlined look
without a real bold font. Naive text extraction (including PyMuPDF's
``get_text("text")``, which pdf-cmap-fix relies on for the final
raw/patched text after ToUnicode patching) has no notion of paint mode: it
sees both draws as independent characters at the same position, so the
extracted string contains each affected syllable twice, e.g.
``ཆེད་ དུ ་ བརྗརྗོད་ པ།`` instead of ``ཆེད་ དུ་ བརྗོད་ པ།``.

This is a **page-content duplication**, not a ToUnicode/GID mapping
bug -- the correct ToUnicode CMap for each glyph is still whatever it
was; the glyph is just physically drawn twice. It therefore survives
ToUnicode correction untouched and needs its own pass, applied here
directly to the page content stream (the same technique pdf-cmap-fix
already uses in ``strip_word_actualtext_sentinels`` to remove Word's
ActualText sentinel wrappers).

Detection is intentionally conservative: two ``BT ... ET`` text objects
are only considered a duplicate pair if they are *adjacent* in the
content stream (only non-text-showing tokens such as ``Q``, ``q``,
color operators, clip paths, or ``gs`` may sit between them) and they
resolve to the exact same ``(x, y)`` text-matrix origin *and* the exact
same concatenated shown-text payload (``Tj``/``'``/``"``/``TJ``
operands, with ``TJ`` kerning numbers stripped so only the string parts
are compared). When three or more duplicate passes are chained, every
occurrence after the first is neutralised.

IMPORTANT -- why this *blanks* text rather than deleting the block:
a ``BT ... ET`` text object is not self-contained. Operators inside it
(``Tf`` font selection, ``cs``/``scn`` fill colour, ``Tc``/``Tw``
spacing, ``Tr`` render mode, ...) are graphics-state changes that
persist forward in the content stream until something else changes
them again -- they are not undone at the following ``ET``. An earlier
version of this pass deleted the whole duplicate block outright, which
also deleted those state-setting operators; on at least one real PDF
that silently changed the fill colourspace/state inherited by later,
*unrelated* text later in the same stream and made an unrelated
character vanish from extraction. Blanking only the shown-text
operands (``(...)Tj`` -> ``()Tj``, ``[...]TJ`` -> ``[]TJ``, etc.)
removes the duplicate glyphs from rendering and extraction while
leaving every other operator -- and therefore all downstream graphics
state -- untouched.
"""
from __future__ import annotations

import re
from typing import Optional

import fitz

_TEXT_OBJECT_RE = re.compile(rb"BT(.*?)ET", re.DOTALL)

_NUM = rb"([\-0-9.]+)"
_TM_RE = re.compile(rb"\s+".join([_NUM] * 6) + rb"\s+Tm")

# A ``cm`` (coordinate-matrix) operator immediately preceding this text
# object's ``BT``. Many DTP-generated PDFs (observed: this pattern, not
# just InDesign titles) wrap *every* glyph run in its own
# ``q <cm> BT <Tm identity-ish> ... ET Q``, where the *real* page
# position lives entirely in the ``cm`` translation and the ``Tm``
# inside the text object is a constant/near-constant per-glyph matrix
# (e.g. always ``108 0 0 105 0 1.458333 Tm``). Looking at ``Tm`` alone
# in such a file makes every glyph on the page look like it shares the
# same "origin", which caused false-positive duplicate matches between
# unrelated words that happened to render identical text.
_PRECEDING_CM_RE = re.compile(rb"\s+".join([_NUM] * 6) + rb"\s+cm\s*$")
_CM_LOOKBACK_WINDOW = 200

# One Tj/'/" string operand, or one TJ array operand -- operand plus the
# operator that shows it, so we can find-and-replace the operand in place.
_SHOW_OP_RE = re.compile(
    rb"(<[0-9A-Fa-f\s]*>|\((?:\\.|[^\\()])*\))(\s*)(Tj|'|\")"
    rb"|(\[(?:\\.|[^\[\]\\])*\])(\s*)(TJ)"
)

# Inside a TJ array: the literal string pieces only (kerning numbers
# between them are display-width adjustments, not shown text).
_TJ_STRING_PIECE_RE = re.compile(rb"<[0-9A-Fa-f\s]*>|\((?:\\.|[^\\()])*\)")


def _normalise_operand(raw: bytes) -> bytes:
    """Strip an operand down to just its literal content bytes so two
    operators that show the same text compare equal regardless of
    whether the text was emitted as one operand or split across
    several (e.g. ``(.)(- )Tj Tj`` vs a single ``(.- )Tj``).
    """
    if raw.startswith(b"["):
        return b"".join(_normalise_operand(p) for p in _TJ_STRING_PIECE_RE.findall(raw))
    if raw.startswith(b"("):
        return raw[1:-1]
    if raw.startswith(b"<"):
        return re.sub(rb"\s+", b"", raw[1:-1]).upper()
    return raw


def _preceding_cm(stream: bytes, bt_start: int) -> Optional[tuple[float, ...]]:
    """Return the 6 numbers of a ``cm`` operator immediately preceding the
    ``BT`` at *bt_start* (only whitespace between ``cm`` and ``BT``), or
    ``None`` if the text object isn't wrapped that way.
    """
    window = stream[max(0, bt_start - _CM_LOOKBACK_WINDOW) : bt_start]
    m = _PRECEDING_CM_RE.search(window)
    if not m:
        return None
    try:
        return tuple(float(g) for g in m.groups())
    except ValueError:
        return None


def _text_object_signature(
    stream: bytes,
    bt_start: int,
    block: bytes,
) -> tuple[Optional[tuple[float, float]], bytes]:
    """Return ``(origin_xy, shown_bytes)`` for one ``BT ... ET`` block.

    ``origin_xy`` is the *last* ``Tm`` translation seen in the block,
    composed with a ``cm`` matrix immediately preceding the ``BT`` if one
    is present (see :data:`_PRECEDING_CM_RE` for why: some PDFs put the
    real page position in ``cm`` and use a constant/near-constant ``Tm``
    for every single glyph run, which would otherwise make unrelated
    glyphs look like they share one "origin"). Rounded to 2 decimal
    places; ``None`` if the block never sets ``Tm`` (such blocks are
    never treated as dedup candidates, since their effective position
    depends on state carried over from a preceding block, which this
    conservative pass does not track).
    """
    tm_origin = None
    for m in _TM_RE.finditer(block):
        try:
            tm_origin = (float(m.group(5)), float(m.group(6)))
        except ValueError:
            continue

    origin = None
    if tm_origin is not None:
        cm = _preceding_cm(stream, bt_start)
        if cm is not None:
            a, b, c, d, e, f = cm
            tx, ty = tm_origin
            origin = (round(a * tx + c * ty + e, 2), round(b * tx + d * ty + f, 2))
        else:
            origin = (round(tm_origin[0], 2), round(tm_origin[1], 2))

    shown = bytearray()
    for m in _SHOW_OP_RE.finditer(block):
        raw = m.group(1) or m.group(4)
        shown += _normalise_operand(raw)
    return origin, bytes(shown)


def _blank_shown_text(block: bytes) -> bytes:
    """Return *block* with every Tj/'/"/TJ operand replaced by an empty
    string/array of the same operand kind. All other operators (Tf, Tm,
    Td/TD, Tr, colour, spacing, ...) are left byte-for-byte intact, so
    graphics state carried forward to the rest of the content stream is
    unaffected -- only the glyphs themselves stop being painted/shown.
    """

    def _replace(m: re.Match) -> bytes:
        if m.group(1) is not None:
            operand, gap, op = m.group(1), m.group(2), m.group(3)
            empty = b"<>" if operand.startswith(b"<") else b"()"
            return empty + gap + op
        operand, gap, op = m.group(4), m.group(5), m.group(6)
        return b"[]" + gap + op

    return _SHOW_OP_RE.sub(_replace, block)


def _dedupe_stream(stream: bytes) -> tuple[bytes, int]:
    """Blank the shown text of the second (and any further) of a run of
    adjacent ``BT ... ET`` text objects that share the same ``Tm`` origin
    and the same shown text. Returns ``(new_stream, n_neutralised)``.
    """
    matches = list(_TEXT_OBJECT_RE.finditer(stream))
    if len(matches) < 2:
        return stream, 0

    to_blank: list[tuple[int, int]] = []
    prev_origin: Optional[tuple[float, float]] = None
    prev_shown: Optional[bytes] = None
    prev_has_content = False
    for m in matches:
        origin, shown = _text_object_signature(stream, m.start(), m.group(1))
        has_content = bool(shown)
        if (
            has_content
            and prev_has_content
            and origin is not None
            and origin == prev_origin
            and shown == prev_shown
        ):
            to_blank.append((m.start(1), m.end(1)))
            # Keep comparing subsequent objects against the *kept* block
            # so 3+ chained duplicate passes are all collapsed to one.
            continue
        prev_origin, prev_shown, prev_has_content = origin, shown, has_content

    if not to_blank:
        return stream, 0

    out = bytearray(stream)
    for start, end in sorted(to_blank, reverse=True):
        out[start:end] = _blank_shown_text(bytes(out[start:end]))
    return bytes(out), len(to_blank)


#
# --- Jittered n-copy fake-bold repeats (within a single BT...ET object) ----
#
# A second, unrelated way PDF producers fake bold/heavy-ink Tibetan text:
# instead of two stroke+fill BT...ET objects at one shared absolute origin
# (the InDesign pattern above), the same glyph run is shown 3-5+ times in a
# row *inside one text object*, each repeat preceded by a small *relative*
# ``Td``/``TD`` nudge (a few thousandths of a text-space unit -- a fraction
# of a point once the text/CTM scale is applied), e.g.:
#
#   (ཨང་)Tj
#   -0.03 0    TD
#   (ཨང་)Tj
#   0.03  0.03 TD
#   (ཨང་)Tj
#   -0.03 0    TD
#   (ཨང་)Tj
#   0.015 -0.015 TD
#   (ཨང་)Tj
#
# Real inter-character advances in the same documents are an order of
# magnitude larger (observed >= ~0.3 in text-space units for the smallest
# real glyph), so a small-move threshold well below that cleanly separates
# "bold jitter" from "the next character". Combined with requiring the
# shown text to match *exactly*, this is conservative in the same spirit as
# the stroke+fill pass above: genuine adjacent repeated words move by a
# real glyph advance, not a sub-glyph nudge.
#
# Unlike the stroke+fill case, we can't just delete/blank on ``Tm`` origin
# equality -- these runs use relative moves and often never call ``Tm`` at
# all within the object. Instead we walk the stream's ``Tf``/``Td``/``TD``/
# show-operator tokens in order and collapse any run of 2+ consecutive
# shows that are (a) separated only by one small relative move and (b) show
# identical text, keeping the first and blanking the rest -- exactly as the
# stroke+fill pass keeps the first duplicate and blanks the following ones.

_JITTER_EPS_X = 0.1
_JITTER_EPS_Y = 0.05

_BT_ET_TOKEN_RE = re.compile(rb"\bBT\b|\bET\b")
_TD_TOKEN_RE = re.compile(rb"([\-0-9.]+)\s+([\-0-9.]+)\s+(?:TD|Td)\b")
_TF_TOKEN_RE = re.compile(rb"/([A-Za-z][A-Za-z0-9_.]*)\s+[-+]?[\d.]+\s+Tf")


def _iter_jitter_tokens(stream: bytes):
    """Yield ``(kind, match)`` for the token types the jitter pass cares
    about, in stream order: ``"bt"``/``"et"``, ``"tf"`` (font selection),
    ``"td"`` (relative move), and ``"show"`` (Tj/'/"/TJ). Everything else
    in the content stream is invisible to this pass -- it only needs to
    know when a small move immediately precedes a repeat of the same text.
    """
    positions = []
    for m in _BT_ET_TOKEN_RE.finditer(stream):
        kind = "bt" if m.group(0) == b"BT" else "et"
        positions.append((m.start(), kind, m))
    for m in _TF_TOKEN_RE.finditer(stream):
        positions.append((m.start(), "tf", m))
    for m in _TD_TOKEN_RE.finditer(stream):
        positions.append((m.start(), "td", m))
    for m in _SHOW_OP_RE.finditer(stream):
        positions.append((m.start(), "show", m))
    positions.sort(key=lambda p: p[0])
    for _, kind, m in positions:
        yield kind, m


def _dedupe_jitter_stream(stream: bytes) -> tuple[bytes, int]:
    """Blank all but the first of each run of jittered same-text repeats.

    Returns ``(new_stream, n_neutralised)``.
    """
    to_blank: list[tuple[int, int]] = []
    run_text: Optional[bytes] = None
    run_count = 0
    small_move_pending = False
    cur_font: Optional[bytes] = None

    def _flush():
        nonlocal run_text, run_count
        run_text = None
        run_count = 0

    for kind, m in _iter_jitter_tokens(stream):
        if kind in ("bt", "et"):
            _flush()
            small_move_pending = False
            continue
        if kind == "tf":
            font = m.group(1)
            if font != cur_font:
                _flush()
            cur_font = font
            small_move_pending = False
            continue
        if kind == "td":
            try:
                dx, dy = float(m.group(1)), float(m.group(2))
            except ValueError:
                _flush()
                small_move_pending = False
                continue
            if abs(dx) <= _JITTER_EPS_X and abs(dy) <= _JITTER_EPS_Y:
                small_move_pending = True
            else:
                _flush()
                small_move_pending = False
            continue
        # kind == "show"
        raw = m.group(1) if m.group(1) is not None else m.group(4)
        shown = _normalise_operand(raw)
        if small_move_pending and shown and run_text is not None and shown == run_text:
            run_count += 1
            to_blank.append((m.start(1) if m.group(1) is not None else m.start(4),
                              m.end(1) if m.group(1) is not None else m.end(4)))
        else:
            run_text = shown if shown else None
            run_count = 1
        small_move_pending = False

    if not to_blank:
        return stream, 0

    out = bytearray(stream)
    n = 0
    for start, end in sorted(to_blank, reverse=True):
        operand = bytes(out[start:end])
        empty = b"<>" if operand.startswith(b"<") else b"()"
        out[start:end] = empty
        n += 1
    return bytes(out), n


def dedupe_stroke_fill_duplicates(doc: fitz.Document) -> dict[str, int]:
    """Neutralise duplicate/jittered fake-bold text objects on every page
    content stream in *doc*, in place (in-memory only; the caller decides
    whether/where to write the result back out).

    Runs two independent passes over each content stream:

    1. :func:`_dedupe_stream` -- InDesign-style stroke+fill duplicates:
       two whole ``BT...ET`` objects at the identical absolute ``Tm``
       origin.
    2. :func:`_dedupe_jitter_stream` -- same-text repeats inside a single
       ``BT...ET`` object, separated by small relative ``Td``/``TD``
       nudges instead of a shared absolute origin.

    See the module docstring for why ToUnicode/GID correction alone
    cannot fix either pattern, and why duplicates are *blanked* (their
    shown-text operands emptied) rather than deleted.
    """
    seen_stream_xrefs: set[int] = set()
    objects_removed = 0
    streams_changed = 0
    jitter_removed = 0
    jitter_streams_changed = 0
    for pno in range(len(doc)):
        page = doc[pno]
        try:
            content_xrefs = page.get_contents()
        except Exception:
            continue
        for xref in content_xrefs:
            if xref in seen_stream_xrefs:
                continue
            seen_stream_xrefs.add(xref)
            try:
                stream = doc.xref_stream(xref)
            except Exception:
                continue
            stream, n = _dedupe_stream(stream)
            changed = n > 0
            if n > 0:
                objects_removed += n
                streams_changed += 1
            stream, jn = _dedupe_jitter_stream(stream)
            if jn > 0:
                jitter_removed += jn
                jitter_streams_changed += 1
                changed = True
            if not changed:
                continue
            try:
                doc.update_stream(xref, stream)
            except Exception:
                continue
    return dict(
        duplicate_text_objects_removed=objects_removed,
        strokefill_streams_changed=streams_changed,
        jitter_duplicate_text_removed=jitter_removed,
        jitter_streams_changed=jitter_streams_changed,
    )
