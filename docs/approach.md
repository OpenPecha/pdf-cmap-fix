# Technical Approach

## The Problem

Tibetan script uses stacked syllables — consonant clusters written vertically
where a base consonant is combined with superscript or subscript letters:

```
ཀྱི་  =  ཀ (ka) + ྱ (subjoined-ya) + ི (i-vowel) + ་ (tsek)
རྡོ་  =  ར (ra) + ྡ (subjoined-da) + ོ (o-vowel) + ་ (tsek)
སྤྱོད =  ས (sa) + ྤ (subjoined-pa) + ྱ (subjoined-ya) + ོ (o-vowel) + ད (da)
```

When such documents are exported to PDF, the font shaping engine merges these
multi-codepoint sequences into a single glyph (a **ligature**).  Each ligature
has a **Glyph ID (GID)** in the font.  The PDF contains a mapping called the
**ToUnicode CMap** that should map each GID back to the correct Unicode
sequence so that copy-paste and text extraction tools work correctly.

In practice, this mapping is frequently wrong or incomplete:

- **InDesign PDFs (Type0/CID)**: The ToUnicode may exist but omit subjoined
  letters — e.g. GID for `རྡོ་` is mapped to `རོ་` (the base + vowel only),
  silently dropping `ྡ`.
- **Word PDFs (Type0/CID)**: Word sometimes inserts an incorrect extra
  subjoined-ja (`ྗ`) into vowel-only glyphs — every `ོ` becomes `ྗོ`.
- **Ghostscript PDFs (TrueType)**: The PDF char-codes are Ghostscript-assigned
  sequential integers that do not correspond to font GIDs.  The ToUnicode
  covers only simple consonants; stacked glyphs have no mapping at all.

## The Solution

### Step 1 — Build a Reverse GID map per font

The shipped **`pdf_cmap_fix/data/font_lookup/<key>.json`** files (968 unique keys;
see [font-inventory.md](font-inventory.md)) are produced by
**`scripts/build_per_font_gid_maps.py`** from the same archives **README** lists:
**`scripts/bodyig.zip`**, **`scripts/tibetan-fonts-main.zip`**, and
**`scripts/tibetan-fonts-private-main.zip`**, merged **in order** so **later**
inputs override earlier entries when the normalised font stem collides.

The GSUB walk is implemented in **`scripts/gid_map.py`** (`build_gid_map`).

For each font file:

1. Load the font with `fontTools`.
2. Read the **cmap** table: `codepoint → glyph_name` for atomic characters.
3. Walk the **GSUB lookup list** and collect the substitution rules we can
   reverse statically:
   - **Type 4 (ligature)** — `lig_glyph → [component_glyphs]`.
   - **Type 2 (multiple)** — `one_glyph → [component_glyphs]` (split, then
     recurse).
   - **Type 1 (single)** — `target_glyph ← [source_glyphs]` (so intermediate
     glyphs such as `tibKa2` resolve back through `tibKa` to a `cmap` entry).
   - **Type 7 (extension)** — wrappers that hold a 32‑bit offset to one of
     types 1/2/4 above; transparently unwrapped to the inner subtable.
4. Recursively decompose each glyph back to its atomic components and then to
   their Unicode code points; the recursion stops when it reaches a `cmap`
   entry or runs out of rules.

This gives us the **reverse mapping**: `GID → correct Unicode sequence` for
every glyph in the font, including complex stacked syllables.

```python
# simplified sketch — see scripts/gid_map.py for the full walk.
def decompose(gname):
    if gname in cmap_reverse:           # atomic letter or digit
        return cmap_reverse[gname]
    if gname in lig_rules:              # GSUB type 4 (ligature)
        return "".join(decompose(c) for c in lig_rules[gname])
    if gname in multiple_fwd:           # GSUB type 2 (one -> many)
        return "".join(decompose(c) for c in multiple_fwd[gname])
    if gname in single_rev:             # GSUB type 1 (substitute -> source)
        for src in single_rev[gname]:
            r = decompose(src)
            if r:
                return r
    return ""                           # truly unmappable glyph
```

Lookup types **3 (alternate)** and **5 / 6 / 8 (contextual / chained /
reverse‑chain)** are *not* reduced to a static `GID → Unicode` column. They
depend on surrounding glyphs at shaping time and would require simulating the
shaper to reverse safely. In practice, for the Tibetan corpus we ship, the
inner substitutions called by contextual lookups are themselves type 1 / 4 and
are already covered by the walk above; see
`scripts/diagnose_contextual_gsub.py` for a per‑font check that prints how
many glyphs (if any) would gain a mapping from explicit contextual modelling.

Each face’s map is written as one JSON file under `pdf_cmap_fix/data/font_lookup/`:

```json
{
  "monlamuniouchan2": {
    "216": "ོ",
    "390": "ལྔ",
    "1042": "རྐྱུ"
  },
  ...
}
```

The earliest documentation referred only to **`bodyig.zip`** (Monlam / Himalaya /
Jomolhari-heavy); the **bundled** database now aggregates many more faces—see
the full key list in [font-inventory.md](font-inventory.md).

### Font lookup JSONs

**[`scripts/build_per_font_gid_maps.py`](../scripts/build_per_font_gid_maps.py)** writes one JSON per face into **`pdf_cmap_fix/data/font_lookup/<normalised_key>.json`**, plus **`_manifest.json`**. The extractor loads **`font_lookup/<matched_key>.json`** on demand (lazy read per matched font), from the bundled directory or from **`--font-lookup-dir`** / **`font_lookup_dir=`** (see **[Font lookup workflows](../README.md#font-lookup-workflows)** in the README). The same GSUB walk (types 1, 2, 4 with type‑7 wrappers unwrapped) is used.

A `_meta` block carries provenance and GSUB lookup counts and is ignored when resolving GIDs:

```json
{
  "monlamuniouchan2": { "216": "ོ", "390": "ལྔ", "1042": "རྐྱུ", "...": "..." },
  "_meta": {
    "source": "tibetan-fonts-main.zip::.../MonlamUniOuChan2.ttf",
    "gids_mapped": 3247,
    "multi_char_stacks": 2410,
    "gsub_lookup_counts": {"1": 6, "2": 1, "4": 12, "6": 4}
  }
}
```

The full list of keys we ship is in [font-inventory.md](font-inventory.md#font-lookup-gid-maps-pdf_cmap_fixdatafont_lookup).

### Step 2 — Match PDF Font to Database Entry

PDF fonts have names like `FPFIFO+Monlam#2320Uni#2320OuChan2`.  We normalise
both the PDF name and every DB key by:

1. Stripping the 6-character subset prefix (`FPFIFO+`).
2. Decoding PDF hex-escapes (`#23` → `#`, then `#20` → ` `) up to 3 times
   (InDesign double-encodes font names).
3. Stripping all non-alphanumeric characters and lowercasing.

`FPFIFO+Monlam#2320Uni#2320OuChan2` → `monlamuniouchan2` ✓

Scoring ranks exact matches above prefix/substring matches, with ties broken
by shortest name-length difference.

### Step 3 — Patch the ToUnicode CMap

For each matched Type0 font in the PDF:

1. Read the existing ToUnicode CMap stream.
2. For every GID where our DB has a mapping, **replace** the existing entry
   with the DB value — unconditionally, because the GSUB decomposition of the
   original full font is the authoritative source.
3. Write the merged CMap back into the PDF in memory (`pymupdf` updates the
   in-memory document).  The **input PDF file on disk is never modified**.

The new CMap uses 2-byte GID format (`<XXXX>`) as required for Type0/CID
Identity-H fonts.

### Text extraction vs patched PDF

After the CMap merge, the library can do either of the following (same patch,
same font matching rules):

| Mode | API | CLI | On disk |
|------|-----|-----|---------|
| Extract text | `extract_pdf_text` | `pdf-cmap-fix file.pdf` | Writes `file.raw.txt`, `file.patched.txt`, `file.diff.txt` next to the PDF (or another `output_dir`).  Does **not** change the original PDF. |
| Emit patched PDF | `patch_pdf` | `pdf-cmap-fix --patch-pdf file.pdf` (alias `-p`) | Writes `file.patched.pdf` by default (or a path you pass).  The original PDF is still untouched. |
| Dict only (no PDF write) | `build_tounicode_dict` | `pdf-cmap-fix --dump-cmap out.json file.pdf` | Writes JSON with per-font `existing`, `merged`, and `overrides` maps. |

The patched PDF is a normal PDF with corrected ToUnicode streams, so
copy-paste, search, and downstream extractors that honour ToUnicode will see the
same corrected Tibetan Unicode as in `extract_pdf_text`'s `patched` string.

### Why "Replace Unconditionally"?

Early versions of this tool merged by keeping the *longer* of the two
sequences.  This was wrong for Word-generated PDFs (TI1055):

| GID | Word ToUnicode | Correct |
|-----|---------------|---------|
| 216 | `ྗོ` (2 chars, wrong) | `ོ` (1 char, correct) |
| 390 | `ལྗོ` (3 chars, wrong) | `ལ` (1 char) |

Word inserted a spurious subjoined-ja (`ྗ`, U+0F97) into many vowel-only
glyphs.  The authoritative DB value is always correct because it comes from
the actual font's GSUB table rather than from Word's heuristics.

### Whitespace and PDF positioning

The patcher only rewrites `/ToUnicode` streams; it never inserts, deletes, or
reorders whitespace. Apparent “double spaces” inside Tibetan stacks in
`*.patched.txt` (for example `སྤྱ  ོད`) come from PyMuPDF's text extraction,
which interprets PDF `TJ` kerning offsets between glyphs as whitespace when the
gap exceeds a heuristic threshold. Tibetan stack glyphs are physically wider
than Latin characters, so the surrounding kerning often crosses that threshold.
Counting whitespace runs in `*.raw.txt` vs `*.patched.txt` line‑by‑line shows
identical totals — the spaces were already in the raw extraction; they only
become visible once the surrounding `U+FFFD` placeholders are replaced with
readable Tibetan letters.

Three options if you need cleaner whitespace downstream: (a) drop
`fitz.TEXT_PRESERVE_WHITESPACE` in `extract_all` (less aggressive heuristic,
risk of losing real word separators on some PDFs), (b) extract via
`get_text("words"|"dict")` and join glyphs yourself with a width‑aware threshold,
or (c) collapse runs of two or more ASCII spaces between consecutive Tibetan
characters in a post‑processing step. Option (c) is what we recommend for
downstream NLP pipelines because it is local, reversible, and never touches
spaces between Tibetan and other scripts.

### Why Only Type0 Fonts?

Type0/CID fonts with **Identity-H encoding** preserve the original font GIDs
in the PDF.  Char code `N` in the PDF content stream = GID `N` in the
original font = GID `N` in our font lookup map.  The mapping is exact.

TrueType **simple-encoding** fonts (e.g. Ghostscript-generated PDFs) assign
their own sequential char codes (1, 2, 3, ...) per-subset.  Char code 1 is
Ghostscript's *first used glyph*, which may be GID 3 or GID 1042 or anything
else in the original font.  Without reading the embedded subset's glyph order
and matching it against the full font's glyph order, there is no reliable way
to map char codes back to original GIDs.  Patching these blindly produces
garbled output.

## Supported Fonts

Matching uses **normalised keys** matching **`font_lookup/<key>.json`** stems (lowercase
letters and digits only). See [font-inventory.md](font-inventory.md). Example keys still common in Tibetan
publications include **`monlamuniouchan2`**, **`himalaya`**, **`jomolhari`**, and
many others from the combined font ZIPs.

Fonts **not** yet supported (TrueType simple encoding):

- Himalaya-G variant used in older Ghostscript PDFs (PUA codepoints F001-F04B,
  predating Tibetan Unicode standardisation)
- Any Ghostscript-generated PDF where Tibetan fonts are embedded as TrueType
  simple fonts with sequential char-code assignment

## Worked examples

Sample PDFs and reference outputs live under **[`docs/examples/`](examples/)** (one subdirectory per document). Each folder ships:

- **`*.pdf`** — original input.
- **`*.raw.txt`** — text extracted **before** patching (broken Unicode as the PDF exposes it today).
- **`*.patched.txt`** — text after the `/ToUnicode` merge.
- **`*.diff.txt`** — line-by-line raw vs patched; the first lines record **`Lines changed`** and **`Char delta`**.
- **`*.patched.pdf`** — same document with corrected `/ToUnicode` streams (`pdf-cmap-fix -p`); glyphs on the page are unchanged.
- **`*.cmap-dump.json`** — per-font merged ToUnicode as JSON (`pdf-cmap-fix --dump-cmap`).

All five examples were generated with the bundled **`pdf_cmap_fix/data/font_lookup/*.json`**. If your maps differ from the committed reference outputs, refresh **`font_lookup/<key>.json`** (e.g. **`scripts/update_font_lookup.py`**) or pass **`--font-lookup-dir`**.

### Index

| Example | Producer | Pages | Lines changed | Char delta | Notable fonts |
|---------|----------|------:|--------------:|-----------:|---------------|
| [`TI1055-01-001/`](examples/TI1055-01-001/) | MS Word | 528 | **10,205** | **−23,725** | Monlam Uni OuChan 2, Calibri, Cambria |
| [`TI1751-01-001/`](examples/TI1751-01-001/) | InDesign | 528 | **2,545** | **+9,969** | Monlam Uni OuChan 2, Dedris‑*, Microsoft Himalaya, Jomolhari |
| [`TI803-01-001/`](examples/TI803-01-001/) | MS Word | 398 | **9,356** | **−23,922** | Microsoft Himalaya, Calibri, Cambria |
| [`TI1461-01-001/`](examples/TI1461-01-001/) | InDesign | 1 | 25 | **+30** | Qomolangma‑Uchen‑Sarchen/Sarchung, Monlam Uni OuChan 1/5 |
| [`TI1763-01-002/`](examples/TI1763-01-002/) | MS Word | 1 | 17 | +127 | Monlam Uni OuChan 2 |

`Lines changed` and `Char delta` come from the header of each `*.diff.txt`.

### Reproduce

From the repository root, after `pip install -e .`:

```bash
# Default extract + diff (uses bundled font_lookup/*.json)
pdf-cmap-fix docs/examples/TI1055-01-001/TI1055-01-001.pdf
pdf-cmap-fix -p docs/examples/TI1055-01-001/TI1055-01-001.pdf
pdf-cmap-fix --dump-cmap docs/examples/TI1055-01-001/TI1055-01-001.cmap-dump.json \
    docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

For PDFs that embed **Microsoft Himalaya** subsets, ensure **`microsofthimalaya.json`** reflects the GSUB type **1/2/4/7** walk (refresh with **`scripts/update_font_lookup.py`** if needed), then:

```bash
pdf-cmap-fix docs/examples/TI803-01-001/TI803-01-001.pdf
pdf-cmap-fix -p docs/examples/TI803-01-001/TI803-01-001.pdf
```

**TI1763** (Monlam Uni OuChan 2; lookup key **`monlamuniouchan2`**):

```bash
pdf-cmap-fix docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

### What each example illustrates

#### `TI1055-01-001` — Word inserting spurious subjoined‑ja

Word silently injects `ྗ` (subjoined‑ja, U+0F97) into vowel‑only glyphs of Monlam Uni OuChan 2. The patched output **shrinks** as the spurious characters are removed.

```
RAW:      བྗོད་གངས་ཅན་... ཐྗོས་བསམ་སྗོམ་...
PATCHED:  བོད་གངས་ཅན་... ཐོས་བསམ་སྒོམ་...
```

#### `TI1751-01-001` — InDesign dropping subjoined letters

InDesign’s `/ToUnicode` for the same Monlam family **omits** subjoined letters; the patched output **grows** as `ྵ`/`ྱ`/`ྡ`/… are restored.

```
RAW:      འོད་གསལ་ཀོང་ཡངས་... རྣལ་འབོར་པ་... ཀི་ཟབ་གཏེར།
PATCHED:  འོད་གསལ་ཀློང་ཡངས་... རྣལ་འབྱོར་པ་... ཀྱི་ཟབ་གཏེར།
```

#### `TI803-01-001` — Word + Microsoft Himalaya subsets

Same Word symptom as TI1055, but on a **Microsoft Himalaya** subset. The **`microsofthimalaya.json`** lookup (GSUB type 1/2/4/7) recovers stack glyphs that a cmap‑only or older map may leave as `U+FFFD`; regenerate that JSON if your font build differs from the bundled file.

#### `TI1461-01-001` — InDesign, mixed Qomolangma + Monlam

Single‑page sample from a multi‑font InDesign export. The patcher resolves stacks for **Qomolangma‑Uchen‑Sarchen / Sarchung** and **Monlam Uni OuChan 1 / 5**.

#### `TI1763-01-002` — Word, single page, Monlam Uni OuChan 2

Smallest end‑to‑end read. With an up‑to‑date **`monlamuniouchan2.json`**, patched text has **no residual `U+FFFD`**; an older map alone may leave a few.

> Spaces inside Tibetan stacks (e.g. `སྤྱ  ོད`) come from PyMuPDF and PDF kerning; they appear in `*.raw.txt` too. See [Whitespace and PDF positioning](#whitespace-and-pdf-positioning).

### Extended metrics: TI1751-01-001 (InDesign, 528 pages)

Metrics use the **bundled** `font_lookup/` and current extractor; counts can shift slightly if data or tooling changes.

| Metric | Value |
|--------|-------|
| Pages | 528 |
| Type0 fonts seen (with `/ToUnicode`) | 2,163 |
| Lines differing (`.diff.txt`, page-banner format) | ~2,545 |
| Char delta (`patched` − `raw`) | ~+9,969 |

Tibetan body text is largely **Monlam Uni OuChan2**; the publication also embeds other Type0/Latin/CJK fonts (Calibri, Himalaya, Dedris, PMingLiU, …)—see the **`--dump-cmap`** JSON for per-font names and xref IDs.

Representative fixes:

| RAW (wrong) | PATCHED (correct) |
|-------------|-------------------|
| `ཀོང་ཡངས་` | `ཀློང་ཡངས་` (added subjoined-la) |
| `རྣལ་འབོར་` | `རྣལ་འབྱོར་` (added subjoined-ya) |
| `ཀི་` | `ཀྱི་` (added subjoined-ya) |
| `རོ་རེའི་` | `རྡོ་རྗེའི་` (added subjoined-da, subjoined-ja) |
| `སིང་` | `སྙིང་` (added subjoined-nya) |
| `བིན་རླབས་` | `བྱིན་རླབས་` (added subjoined-ya) |

### Extended metrics: TI1055-01-001 (Microsoft Word, 528 pages)

| Metric | Value |
|--------|-------|
| Pages | 528 |
| Type0 fonts seen (with `/ToUnicode`) | 4 |
| Lines differing (`.diff.txt`) | ~10,205 |
| Char delta | ~−23,725 (shorter = removal of spurious characters) |

Representative fixes:

| RAW (wrong) | PATCHED (correct) |
|-------------|-------------------|
| `བྗོད་` | `བོད་` (removed spurious ྗ) |
| `དང་པྗོ་` | `དང་པོ་` (removed spurious ྗ) |
| `མྱིག་` | `མིག་` (corrected subjoined-ya) |
| `ཐྗོས་བསམ་སྗོམ་` | `ཐོས་བསམ་སྒོམ་` (spurious ྗ removed) |
| `གྲངས་གྱིས་མ་ལྗོང་` | `གྲངས་གྱིས་མ་ལོང་` (spurious ྗ removed) |

The negative char delta is expected: Word had inserted spurious multi-codepoint sequences for glyphs that should map to a single codepoint, so the corrected output is shorter but accurate.

## File Layout

```
pdf-cmap-fix/
├── pdf_cmap_fix/                  Python package (installed)
│   ├── __init__.py
│   ├── extractor.py               Patch ToUnicode; extract; build_tounicode_dict; CLI; --font-lookup-dir
│   └── data/
│       └── font_lookup/           One JSON per face (~970 files); runtime GID → Unicode source
│           ├── _manifest.json     Index + duplicates + read errors
│           └── <key>.json         e.g. monlamuniouchan2.json, microsofthimalaya.json
├── scripts/
│   ├── font_sources.py                          Enumerate fonts from zip and/or directories
│   ├── gid_map.py                               cmap + GSUB decomposition (`build_gid_map`)
│   ├── build_per_font_gid_maps.py               Rebuild pdf_cmap_fix/data/font_lookup/
│   ├── update_font_lookup.py                  Create/update one font_lookup JSON from a local font
│   └── diagnose_contextual_gsub.py              Optional GSUB 5/6/8 coverage report
├── docs/
│   ├── README.md             Documentation index
│   ├── approach.md           This file
│   ├── glossary-and-json.md  Terms + JSON shapes
│   ├── font-inventory.md     All bundled font_lookup keys
│   ├── blog.md               Article (publication-ready)
│   └── examples/             Worked examples (one folder per PDF)
│       ├── TI1055-01-001/    MS Word, 528 pages
│       ├── TI1751-01-001/    InDesign, 528 pages
│       ├── TI803-01-001/     MS Word, 398 pages, Microsoft Himalaya
│       ├── TI1461-01-001/    InDesign, 1 page, mixed Qomolangma + Monlam
│       └── TI1763-01-002/    MS Word, 1 page, Monlam Uni OuChan 2
├── tests/
├── pyproject.toml
├── README.md
└── .gitignore
```

## Rebuilding font lookup

Instructions for **bulk ZIP rebuilds**, **single-font `update_font_lookup.py`**, and runtime **`--font-lookup-dir`** are maintained in the root **[README.md](../README.md#font-lookup-workflows)** (**Font lookup workflows**).
