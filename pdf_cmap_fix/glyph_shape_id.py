"""Representation-independent glyph-shape font identification.

The exact outline-hash path (:mod:`glyph_outline_id`) only works for TrueType
``glyf`` outlines: a legacy Tibetan font embedded as **CFF/Type1** (cubic
charstrings) under an obfuscated name can be neither name-resolved nor
hash-matched, so its ToUnicode could not be synthesised at all.

This module matches glyph *shapes* instead, which are identical across curve
representations (cubic CFF vs quadratic TrueType), unitsPerEm and glyph names.
Each glyph is rasterised to a normalised coverage bitmap; matching is a nearest
bitmap by mean-abs distance, in two stages:

  1. **font vote** -- each embedded glyph's nearest reference glyph votes for a
     reference font; the majority wins (decisive even between near-identical
     cousins like Chogyal vs Classic),
  2. **per-glyph** -- within the voted font only, each code's glyph is matched to
     recover its native byte code (then converted via the pytiblegenc table).

The reference DB (``data/pytiblegenc/glyph_shape_db.npz``) is generated offline
from the reference Tibetan fonts by ``scripts/shape/build_shape_db.py``.

NumPy is imported lazily: if it is unavailable the whole module degrades to
"no shape match" and callers fall back to the existing paths.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Must stay in sync with the DB build (scripts/shape/build_shape_db.py).
_N = 64           # fingerprint grid side
_SS = 2           # supersampling
_WINDOW = 1.5     # em window (bbox-corner-aligned glyph fits in [0, WINDOW]^2)
_STEPS = 10       # bezier flattening steps

# Gates (tuned on the validated corpus: same-glyph distance ~<0.02; real Tibetan
# faces reach a family-distinctiveness margin >=0.013 even on a 2-glyph subfont,
# while Latin faces sharing only generic marks top out at ~0.0002).
_ACCEPT = 0.05            # max mean-abs distance to trust a single glyph match
_DISTINCT_VOTE_MIN = 0.008  # min summed distinctiveness weight to accept a font
# AGL/native-byte corroboration: a Latin face with MacRoman names (Optima,
# Lucida Grande) can still accumulate a vote above ``_DISTINCT_VOTE_MIN``
# because many letterforms sit inside ``_ACCEPT`` of some Tibetan stack. Real
# legacy fonts that *use* those AGL names as native slots recover the same
# byte; Latin decoys recover a scrambled byte. Need this many AGL-named
# matches before judging, and reject when agreement is below the ratio.
_AGL_CORROBORATE_MIN = 4
_AGL_CORROBORATE_RATIO = 0.25

_DATA = Path(__file__).resolve().parent / "data" / "pytiblegenc"
_DB_FILE = _DATA / "glyph_shape_db.npz"
_FONTS_FILE = _DATA / "glyph_shape_fonts.json"


def _family_key(name: str) -> str:
    """Coarse design-family key: strip face suffixes so e.g. ``TibetanChogyal``
    and ``TibetanChogyalSkt1`` share a family but ``TibetanMachine`` does not.
    Used to measure how *family-distinctive* a matched glyph is."""
    import re
    n = name.replace(" ", "")
    n = re.sub(r"(Skt\d+|Web\d+|Bod-?Yig|\d+)$", "", n)
    return n.rstrip("-_").lower()


@lru_cache(maxsize=1)
def _db():
    """``(vecs[N,D] float32 in 0..1, codes[N], font_ids[N], font_names[list],
    family_ids[N])`` or ``None`` when numpy or the data file is unavailable."""
    try:
        import numpy as np
    except Exception:
        return None
    if not _DB_FILE.is_file() or not _FONTS_FILE.is_file():
        return None
    try:
        d = np.load(_DB_FILE)
        vecs = d["vecs"].astype(np.float32) / 255.0
        codes = d["codes"]
        font_ids = d["font_ids"]
        fonts = json.loads(_FONTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    fam_of_font = {}
    for i, nm in enumerate(fonts):
        fam_of_font[i] = _family_key(nm)
    fam_names = sorted(set(fam_of_font.values()))
    fam_index = {f: k for k, f in enumerate(fam_names)}
    family_ids = np.array([fam_index[fam_of_font[int(f)]] for f in font_ids], dtype=np.int32)
    return vecs, codes, font_ids, fonts, family_ids


def available() -> bool:
    return _db() is not None


# ---- fingerprint (must match the DB build exactly) ------------------------
def _bez_q(p0, p1, p2, n):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (i / n for i in range(1, n + 1))]


def _bez_c(p0, p1, p2, p3, n):
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
            for t in (i / n for i in range(1, n + 1))]


def _flatten(pen_value) -> List[List[Tuple[float, float]]]:
    contours: List[List[Tuple[float, float]]] = []
    cur: List[Tuple[float, float]] = []
    last = None
    for op, pts in pen_value:
        if op == "moveTo":
            cur = [pts[0]]; last = pts[0]
        elif op == "lineTo":
            cur.append(pts[0]); last = pts[0]
        elif op == "qCurveTo":
            offs, on = list(pts[:-1]), pts[-1]
            p0 = last
            if len(offs) == 1:
                cur += _bez_q(p0, offs[0], on, _STEPS)
            else:
                for j, c in enumerate(offs):
                    nxt = offs[j + 1] if j + 1 < len(offs) else on
                    mid = ((c[0] + nxt[0]) / 2, (c[1] + nxt[1]) / 2) if j + 1 < len(offs) else on
                    cur += _bez_q(p0, c, mid, _STEPS); p0 = mid
            last = on
        elif op == "curveTo":
            p1, p2, p3 = pts; cur += list(_bez_c(last, p1, p2, p3, _STEPS)); last = p3
        elif op in ("closePath", "endPath"):
            if cur:
                contours.append(cur); cur = []
    if cur:
        contours.append(cur)
    return contours


def _fingerprint(contours, upem):
    import numpy as np
    pts = [(x / upem, y / upem) for c in contours for (x, y) in c]
    if not pts:
        return None
    minx = min(p[0] for p in pts); miny = min(p[1] for p in pts)
    M = _N * _SS
    scale = M / _WINDOW
    grid = np.zeros((M, M), dtype=np.float32)
    edges = []
    for c in contours:
        q = [((x / upem - minx) * scale, (y / upem - miny) * scale) for (x, y) in c]
        for i in range(len(q)):
            x1, y1 = q[i]; x2, y2 = q[(i + 1) % len(q)]
            if y1 != y2:
                edges.append((x1, y1, x2, y2))
    for row in range(M):
        yc = row + 0.5
        xs = []
        for x1, y1, x2, y2 in edges:
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                xs.append(x1 + (yc - y1) / (y2 - y1) * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(np.ceil(xs[k] - 0.5)); xb = int(np.floor(xs[k + 1] - 0.5))
            if xb >= xa:
                grid[row, max(0, xa):min(M, xb + 1)] = 1.0
    return grid.reshape(_N, _SS, _N, _SS).mean(axis=(1, 3)).ravel()


def _fingerprint_glyph(glyph_set, gname, upem):
    from fontTools.pens.recordingPen import RecordingPen
    if gname not in glyph_set:
        return None
    rp = RecordingPen()
    try:
        glyph_set[gname].draw(rp)
    except Exception:
        return None
    try:
        return _fingerprint(_flatten(rp.value), upem)
    except Exception:
        return None


# ---- matching -------------------------------------------------------------
def identify_and_recover(
    glyph_set,
    upem: int,
    code_to_gname: Iterable[Tuple[int, str]],
    *,
    font_hint: Optional[str] = None,
) -> Tuple[Optional[str], Dict[int, int]]:
    """Match an embedded font's glyph shapes against the reference DB.

    ``code_to_gname`` yields ``(code, glyph_name)`` pairs -- the codes a caller
    wants resolved (PDF char codes for simple fonts, GIDs for Type0) and the
    embedded glyph name to draw for each.

    Returns ``(matched_font_name, {code: native_byte_code})``. ``font_hint``
    restricts both stages to one reference font (used when the conversion table
    is already known by name but code recovery failed on a CFF outline).
    """
    db = _db()
    if db is None:
        return None, {}
    import numpy as np
    vecs, codes, font_ids, fonts, family_ids = db

    pairs = list(code_to_gname)
    fps: Dict[int, "np.ndarray"] = {}
    for code, gname in pairs:
        # .notdef (and other non-glyph placeholders) carry no font identity --
        # their box outline matches some sibling's notdef in every family and,
        # being numerous in a full /Encoding, would outvote the real glyphs.
        if not gname or gname == ".notdef":
            continue
        fp = _fingerprint_glyph(glyph_set, gname, upem)
        if fp is not None:
            fps[code] = fp
    if not fps:
        return None, {}

    if font_hint is not None and font_hint in fonts:
        # The conversion table is already known by name (the font IS legacy
        # Tibetan); we only need code recovery, so no font-ID gate applies.
        target_id = fonts.index(font_hint)
    else:
        # Stage 1: distinctiveness-weighted vote. Each glyph votes for its
        # nearest reference face, weighted by how *family-distinctive* that match
        # is (nearest distance in a different design family minus its own). Marks
        # shared across every font (a Latin period == a Tibetan tsheg) carry ~0
        # weight; only genuinely Tibetan shapes accumulate weight. This rejects
        # non-Tibetan faces (Times/Palatino) that happen to share common glyphs,
        # while still trusting tiny but distinctive Sanskrit subfonts. Large
        # Latin faces (Optima, Lucida Grande) can still sneak over the sum
        # gate; they are rejected by the AGL/native-byte check below.
        votes: Dict[int, float] = {}
        for fp in fps.values():
            d = np.abs(vecs - fp).mean(axis=1)
            i0 = int(np.argmin(d))
            if d[i0] > _ACCEPT:
                continue
            other = d[family_ids != family_ids[i0]]
            distinct = float(other.min()) - float(d[i0]) if other.size else 1.0
            w = distinct if distinct > 0 else 0.0
            votes[int(font_ids[i0])] = votes.get(int(font_ids[i0]), 0.0) + w
        if not votes:
            return None, {}
        target_id = max(votes, key=votes.get)
        if votes[target_id] < _DISTINCT_VOTE_MIN:
            return None, {}

    # Stage 2: within the chosen font, recover each code's native byte code.
    mask = font_ids == target_id
    fvecs = vecs[mask]
    fcodes = codes[mask]
    out: Dict[int, int] = {}
    for code, fp in fps.items():
        d = np.abs(fvecs - fp).mean(axis=1)
        j = int(np.argmin(d))
        if d[j] <= _ACCEPT:
            out[code] = int(fcodes[j])
    if not out:
        return None, {}
    # font_hint means the caller already resolved the conversion table by name;
    # don't second-guess it. Otherwise reject a vote whose recovered native
    # bytes disagree with the AGL values of the embedded glyph names -- the
    # signature of a Latin font false-positive.
    if font_hint is None and _agl_native_mismatch(pairs, out):
        return None, {}
    return fonts[target_id], out


def _agl_native_mismatch(
    pairs: List[Tuple[int, str]], code_to_native: Dict[int, int]
) -> bool:
    """True when AGL glyph names and recovered native bytes disagree.

    Legacy Tibetan fonts reuse MacRoman glyph names as *native slots*
    (``'A'`` is byte 65 in the conversion table), so a correct match recovers
    ``native == ord(AGL(name))``. A Latin decoy voted as Ededris-vowa recovers
    scrambled bytes. Glyphs without a single-character AGL mapping (``MT33``,
    ``.notdef.2``, ``uni0F40``) are ignored; too few named matches is a no-op
    so tiny Sanskrit subsets keep working.
    """
    try:
        from fontTools.agl import toUnicode
    except Exception:
        return False
    gname_by_code = {code: gname for code, gname in pairs}
    agree = disagree = 0
    for code, native in code_to_native.items():
        ch = toUnicode(gname_by_code.get(code, "") or "")
        if len(ch) != 1:
            continue
        if native == ord(ch):
            agree += 1
        else:
            disagree += 1
    checked = agree + disagree
    if checked < _AGL_CORROBORATE_MIN:
        return False
    return agree / checked < _AGL_CORROBORATE_RATIO
