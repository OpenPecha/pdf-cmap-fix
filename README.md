# pdf-cmap-fix

Fix incorrect or incomplete PDF `/ToUnicode` CMaps so that text extraction, search, and copy-paste return correct Unicode.

Primary use case: **Tibetan stacked syllables** (Monlam, Himalaya, Jomolhari fonts) in Type0 / CID / Identity-H PDFs.  
**GitHub:** [OpenPecha/pdf-cmap-fix](https://github.com/OpenPecha/pdf-cmap-fix)

---

## How it works

1. **Build a GID→Unicode map offline** from the source font's `cmap` table and GSUB ligature rules. Each stacked syllable glyph is decomposed back to its Unicode components. Maps are stored as `pdf_cmap_fix/data/font_lookup/<key>.json` (~970 fonts shipped with the package).
2. **Match the PDF font** by normalising the embedded font name to a lookup key, then merge the correct Unicode strings into the font's `/ToUnicode` stream.
3. **Extract or patch.** The patched text matches what renders on screen.

---

## Install

Requires Python 3.8+.

```bash
pip install git+https://github.com/OpenPecha/pdf-cmap-fix.git
```

Development install:

```bash
git clone https://github.com/OpenPecha/pdf-cmap-fix.git
cd pdf-cmap-fix
python -m venv .venv
. .venv/Scripts/activate     # Windows PowerShell
# . .venv/bin/activate        # macOS / Linux
pip install -e ".[dev]"
pytest -q
```

---

## CLI quick start

```bash
# Extract text: writes document.raw.txt, document.patched.txt, document.diff.txt
pdf-cmap-fix document.pdf

# Write a patched PDF
pdf-cmap-fix -p document.pdf

# Dump the merged ToUnicode maps as JSON (no rewrite)
pdf-cmap-fix --dump-cmap document.cmap-dump.json document.pdf

# Batch
pdf-cmap-fix doc1.pdf doc2.pdf doc3.pdf

# Use a custom font lookup directory (your own or a CI artifact)
pdf-cmap-fix --font-lookup-dir path/to/font_lookup document.pdf
```

Windows note: prefix with `$env:PYTHONUTF8 = "1"` if the console raises encoding errors.

---

## Python API

```python
from pdf_cmap_fix import extract_pdf_text, patch_pdf, build_tounicode_dict

result  = extract_pdf_text("document.pdf")   # raw / patched / diff metadata
patch_pdf("document.pdf")                    # writes document.patched.pdf
cmap    = build_tounicode_dict("document.pdf")

# Use a custom lookup directory with any API call
result = extract_pdf_text("document.pdf", font_lookup_dir="path/to/font_lookup")
```

---

## Font lookup tiers

The default tier (GID) works for most PDFs. Try higher tiers when a font is not in the bundled data or when GIDs do not align.

| Tier | Inner key | Default data directory | Rebuild CLI |
|------|-----------|------------------------|-------------|
| **1** (default) | GID as decimal string | `pdf_cmap_fix/data/font_lookup/` | `scripts/gid/build_per_font_gid_maps.py` |
| **2** | PostScript glyph name | `pdf_cmap_fix/data/font_lookup_gname/` | `scripts/gname/build_per_font_gname_maps.py` |
| **3** | Outline fingerprint | `pdf_cmap_fix/data/font_lookup_gshape/` | `scripts/gshape/build_per_font_gshape_maps.py` |

Each tier also has a **PUA-free sibling** (`font_lookup_gname_pua_free/`, etc.) produced by `scripts/pua/`.

Entrypoint CLIs per tier: `pdf-cmap-fix` (tier 1), `pdf-cmap-fix-gname` (tier 2), `pdf-cmap-fix-gshape` (tier 3).  
See [docs/font-lookup-tiers-2-3.md](docs/font-lookup-tiers-2-3.md) and [docs/tiers/README.md](docs/tiers/README.md) for full details.

---

## Rebuilding font lookup data

### Bulk rebuild from ZIP archives

Place archives under `fonts/` at the repo root (gitignored). Later archives win on duplicate normalised font keys:

```bash
# Tier 1 (GID)
python scripts/gid/build_per_font_gid_maps.py \
    --zip fonts/bodyig.zip \
    --zip fonts/tibetan-fonts-main.zip \
    --zip fonts/tibetan-fonts-private-main.zip

# Tier 2 (glyph name)
python scripts/gname/build_per_font_gname_maps.py \
    --zip fonts/bodyig.zip \
    --zip fonts/tibetan-fonts-main.zip

# Tier 3 (outline hash)
python scripts/gshape/build_per_font_gshape_maps.py \
    --zip fonts/bodyig.zip \
    --zip fonts/tibetan-fonts-main.zip
```

Outputs: `pdf_cmap_fix/data/font_lookup/`, `font_lookup_gname/`, `font_lookup_gshape/` — one `<key>.json` per font face plus `_manifest.json`.

### Single font update

```bash
# Tier 1 (default output: pdf_cmap_fix/data/font_lookup/)
python scripts/gid/update_font_lookup.py path/to/font.ttf

# Tier 2
python scripts/gname/update_font_lookup.py path/to/font.ttf

# Tier 3
python scripts/gshape/update_font_lookup.py path/to/font.ttf

# Force key / custom directory / dry-run (all tiers)
python scripts/gid/update_font_lookup.py --key microsofthimalaya --dry-run path/to/font.ttf
```

### PUA-free variants (optional)

Build sibling trees with PUA values replaced by standard Unicode:

```bash
# Step 1: gname PUA-free (required before gshape / gid)
python scripts/pua/gname/build_pua_free_gname_maps.py \
    --zip fonts/bodyig.zip --zip fonts/tibetan-fonts-main.zip

# Step 2a: gshape PUA-free
python scripts/pua/gshape/build_pua_free_gshape_maps.py \
    --zip fonts/bodyig.zip \
    --gname-dir pdf_cmap_fix/data/font_lookup_gname_pua_free

# Step 2b: gid PUA-free (optional)
python scripts/pua/gid/build_pua_free_gid_maps.py \
    --zip fonts/bodyig.zip \
    --gname-dir pdf_cmap_fix/data/font_lookup_gname_pua_free

# Or run all steps at once
python scripts/pua/run_all.py --with-gid
```

See [docs/workflows/pua-free-font-lookups.md](docs/workflows/pua-free-font-lookups.md) for the full workflow.

---

## Worked examples

Reference PDFs and their raw/patched/diff outputs live in [docs/examples/](docs/examples/).

| Example | Producer | Pages | Font |
|---------|----------|-------|------|
| TI1055-01-001 | MS Word | 528 | Monlam Uni OuChan |
| TI1751-01-001 | InDesign | 528 | Monlam / Himalaya |
| TI803-01-001 | MS Word | 398 | Microsoft Himalaya |
| TI1461-01-001 | InDesign | 1 | Qomolangma + Monlam |
| TI1763-01-002 | MS Word | 1 | Monlam Uni OuChan 2 |
| sample | Mixed | — | Jomolhari + Cambria |

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/tiers/README.md](docs/tiers/README.md) | Tier map: data directories, script folders, PUA-free siblings |
| [docs/font-lookup-tiers-2-3.md](docs/font-lookup-tiers-2-3.md) | Tier 2 and 3 schema, `_meta` fields, CLI flags, merge behaviour |
| [docs/approach.md](docs/approach.md) | Technical deep-dive: GSUB walk, GID decomposition, ToUnicode patching |
| [docs/glossary-and-json.md](docs/glossary-and-json.md) | Terms (Type0, GID, GSUB, CMap …) and all JSON shapes |
| [docs/font-inventory.md](docs/font-inventory.md) | All ~970 normalised font keys shipped in `font_lookup/` |
| [docs/workflows/pua-free-font-lookups.md](docs/workflows/pua-free-font-lookups.md) | PUA-free batch pipeline with diagrams |
| [docs/workflows/local-jomolhari-gshape-pua-free.md](docs/workflows/local-jomolhari-gshape-pua-free.md) | Windows smoke path: local Jomolhari + Cambria gshape |
| [docs/examples/](docs/examples/) | Reference PDFs and extraction outputs |

---

## Project structure

```text
pdf_cmap_fix/                     installable package
  __init__.py                     public API: extract_pdf_text, patch_pdf, …
  __main__.py                     python -m pdf_cmap_fix  (tier 1)
  tounicode_core.py               shared ToUnicode merge + tier filter
  glyph_fingerprint.py            HashPointPen outline hashing (tier 3)
  gid/extractor.py                tier 1 CLI + API
  gname/extractor.py              tier 2 CLI + API
  gshape/extractor.py             tier 3 CLI + API
  data/
    font_lookup/                  tier 1 — shipped in wheel  (~970 JSON files)
    font_lookup_gname/            tier 2 — rebuild from ZIPs
    font_lookup_gshape/           tier 3 — rebuild from ZIPs
    font_lookup_gname_pua_free/   optional PUA-free sibling (gitignored)
    font_lookup_gshape_pua_free/  optional PUA-free sibling (gitignored)
    font_lookup_gid_pua_free/     optional PUA-free sibling (gitignored)

scripts/
  font_lookup_common/             shared library imported by all tier CLIs
    gid_map.py                    GSUB walk + GID decomposition
    per_font_maps.py              bulk ZIP/dir builder
    single_font_lookup.py         single-font updater
    font_lookup_payload.py        payload builder (gid / gname / gshape)
    font_sources.py               ZIP + directory font iterator
    pua_gname_rewriter.py         PUA → Unicode via uni* glyph names
    pua_gshape_patcher.py         gshape PUA patch via fingerprint→gname
    pua_gid_patcher.py            GID PUA patch via glyph order + gname
    pua_utils.py                  PUA detection helpers
    font_archive_index.py         ZIP key index builder
  gid/                            tier 1 CLIs
    build_per_font_gid_maps.py    bulk ZIP/dir → font_lookup/
    update_font_lookup.py         single font → one JSON
  gname/                          tier 2 CLIs
    build_per_font_gname_maps.py
    update_font_lookup.py
  gshape/                         tier 3 CLIs
    build_per_font_gshape_maps.py
    update_font_lookup.py
  pua/                            PUA-free builders
    gname/build_pua_free_gname_maps.py   bulk → font_lookup_gname_pua_free/
    gname/update_pua_free_gname.py       single font
    gshape/build_pua_free_gshape_maps.py bulk + --gname-dir
    gshape/update_pua_free_gshape.py     single font + --gname-json
    gid/build_pua_free_gid_maps.py       bulk + --gname-dir
    gid/update_pua_free_gid.py           single font + --gname-json
    inventory.py                         scan lookup trees for PUA
    verify.py                            exit 1 if any PUA remains
    run_all.py                           orchestrator (all tiers in order)
  misc/
    inspect_pua_gname.py          interactive PUA map analysis
    patch_gid_lookup_from_gname_json.py  patch GID JSON from gname sidecar
    diagnose_contextual_gsub.py   GSUB type 5/6/8 diagnostic
    run_local_gshape_jomolhari_pipeline.py  Windows Jomolhari smoke pipeline

fonts/                            gitignored ZIP archives
  bodyig.zip
  tibetan-fonts-main.zip
  tibetan-fonts-private-main.zip

docs/
  README.md                       documentation index
  approach.md                     technical deep-dive
  glossary-and-json.md
  font-lookup-tiers-2-3.md
  font-inventory.md
  tiers/
    README.md                     tier map quick reference
    data-layout.md                data directory legend
  workflows/
    pua-free-font-lookups.md      global PUA-free batch
    local-jomolhari-gshape-pua-free.md  Windows smoke path
  examples/
    TI1055-01-001/                MS Word 528-page example
    TI1751-01-001/                InDesign 528-page example
    TI803-01-001/                 MS Word, Microsoft Himalaya
    TI1461-01-001/                InDesign, Qomolangma + Monlam
    TI1763-01-002/                MS Word, Monlam Uni OuChan 2
    sample/                       Jomolhari + Cambria sample

tests/
pyproject.toml
```

---

## Limits

- Supported: **Type0 / CID / Identity-H** PDFs where PDF char codes equal font GIDs.
- Not supported: TrueType simple-encoding PDFs (e.g. some Ghostscript outputs) where char codes are Ghostscript-assigned integers unrelated to font GIDs.

See [docs/approach.md](docs/approach.md) for the full rationale.

---

## License

MIT
