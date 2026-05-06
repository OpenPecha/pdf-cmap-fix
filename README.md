# pdf-cmap-fix

Fix missing or wrong **PDF `/ToUnicode` CMap** entries so text extraction and copy-paste match what you see on the page. The primary use case is **Tibetan** stacked syllables (Monlam, Himalaya, Jomolhari): producers often embed incomplete or incorrect Unicode mappings for ligature glyphs. The same mechanism applies to **any** Type0 / Identity-H font present in the bundled GSUB-derived database.

**GitHub:** [OpenPecha/pdf-cmap-fix](https://github.com/OpenPecha/pdf-cmap-fix)

**Documentation:** [docs/README.md](docs/README.md) · [Approach](docs/approach.md) · [Glossary & JSON formats](docs/glossary-and-json.md) · [Font inventory](docs/font-inventory.md) · [Worked examples](docs/examples/README.md) · [Article](docs/blog.md)

---

## Table of contents

1. [Installation](#installation)
2. [Quick start (CLI)](#quick-start-cli)
3. [Per-font overlays](#per-font-overlays)
4. [Python API reference](#python-api-reference)
5. [Bundled reverse database (font sources)](#bundled-reverse-database-font-sources)
6. [Updating `reverse_db.json` in the future](#updating-reverse_dbjson-in-the-future)
7. [Migration from `tibetan-pdf-fix`](#migration-from-tibetan-pdf-fix-01x)
8. [Supported fonts & limits](#supported-fonts--limits)
9. [How it works](#how-it-works)
10. [Worked examples](#worked-examples)
11. [Project structure](#project-structure)
12. [License](#license)

---

## Installation

Requires **Python 3.8+** plus the runtime dependencies declared in `pyproject.toml` (`pymupdf`, `fontTools`). All install paths below pull these in automatically.

### Pick the path that matches what you want to do

| You want to … | Use this command |
|---------------|------------------|
| **Use the CLI / library on your own PDFs** | install from Git (recipe A) |
| **Reproduce the worked examples or run the tests** | editable checkout with dev extras (recipe B) |
| **Rebuild `reverse_db.json` or per-font JSONs from font ZIPs** | recipe B + put the ZIPs under `scripts/` (recipe C) |
| **Pin to a tagged release** | recipe D (replace `<tag>`) |
| **Use it inside a notebook (Colab / Jupyter)** | recipe E |

Each recipe is independent — you only need the one(s) that match your task.

#### A. Install from Git (recommended for end users)

```bash
pip install "pdf-cmap-fix @ git+https://github.com/OpenPecha/pdf-cmap-fix.git"
# Equivalent shorthand:
pip install git+https://github.com/OpenPecha/pdf-cmap-fix.git
```

This downloads the wheel built from `main`, including the bundled `reverse_db.json` (~16 MB) and ~970 per-font JSONs as package data. After it completes, the CLI **`pdf-cmap-fix`** is on your `PATH`.

#### B. Editable checkout for development / reproducing examples

```bash
git clone https://github.com/OpenPecha/pdf-cmap-fix.git
cd pdf-cmap-fix
python -m venv .venv && . .venv/Scripts/activate    # Windows PowerShell
# . .venv/bin/activate                              # macOS / Linux
pip install -e ".[dev]"
pytest -q
```

The `[dev]` extras pull in `pytest` for the test suite.

#### C. Rebuild data files locally (optional)

The merged database and per-font folder are already shipped with the package; rebuild them only if you have updated the upstream font archives. Place the three font ZIPs under `scripts/` (they are git‑ignored):

```bash
scripts/bodyig.zip
scripts/tibetan-fonts-main.zip
scripts/tibetan-fonts-private-main.zip
```

Then, from recipe B's checkout:

```bash
python scripts/build_reverse_db.py \
    --zip scripts/bodyig.zip \
    --zip scripts/tibetan-fonts-main.zip \
    --zip scripts/tibetan-fonts-private-main.zip \
    -o pdf_cmap_fix/data/reverse_db.json

python scripts/build_per_font_gid_maps.py \
    --zip scripts/bodyig.zip \
    --zip scripts/tibetan-fonts-main.zip \
    --zip scripts/tibetan-fonts-private-main.zip
```

Recipes A + B already include `fontTools`, so no extra `pip install` is needed.

#### D. Pin to a tagged release

```bash
pip install "pdf-cmap-fix @ git+https://github.com/OpenPecha/pdf-cmap-fix.git@<tag>"
```

#### E. Notebooks (Colab / Jupyter)

```python
%pip install "pdf-cmap-fix @ git+https://github.com/OpenPecha/pdf-cmap-fix.git"
import pdf_cmap_fix
pdf_cmap_fix.extract_pdf_text("doc.pdf", verbose=False)   # avoid console encoding issues
```

### Verify the install

```bash
pdf-cmap-fix --help
python -c "import pdf_cmap_fix, json, pathlib; \
           db = json.loads((pathlib.Path(pdf_cmap_fix.__file__).parent/'data'/'reverse_db.json').read_text(encoding='utf-8')); \
           print(len(db), 'fonts in reverse_db.json')"
```

You should see the help banner and a font count of around **963**.

---

## Quick start (CLI)

```bash
# Inspect: writes  document.raw.txt  document.patched.txt  document.diff.txt
pdf-cmap-fix document.pdf

# Multiple PDFs in one run
pdf-cmap-fix doc1.pdf doc2.pdf doc3.pdf

# Emit a patched PDF (same ToUnicode logic, original input is never overwritten)
pdf-cmap-fix --patch-pdf document.pdf      # writes document.patched.pdf
pdf-cmap-fix -p doc1.pdf doc2.pdf          # short form

# Dump merged ToUnicode as JSON (no PDF is modified)
pdf-cmap-fix --dump-cmap cmap.json document.pdf
```

Large PDFs with **many** Type0 font objects can make `--dump-cmap` slow and the JSON huge; prefer [`build_tounicode_dict`](#build_tounicode_dict) in Python if you need to filter by font name or xref.

On **Windows**, the default CLI prints Tibetan previews using the console encoding; if you see **`UnicodeEncodeError`**, switch the terminal to UTF-8 (`chcp 65001`) or call **`extract_pdf_text(..., verbose=False)`** from Python so nothing is printed to the console.

---

## Per-font overlays

The bundled `pdf_cmap_fix/data/reverse_db.json` is a single merged DB. We also ship one **small JSON per face** under `pdf_cmap_fix/data/per_font/<key>.json` — same shape as one entry of the merged DB, plus a `_meta` block with provenance and GSUB lookup counts. A `_manifest.json` lists every key written.

Use them when:

- you want to **inspect** what the GSUB walk produced for a single face,
- a PDF embeds a face whose **per-font** map has more entries than the bundled merged DB (e.g. **Microsoft Himalaya** subsets),
- you maintain a downstream font and want to ship a **patch** without rebuilding the 16 MB merged DB.

CLI:

```bash
pdf-cmap-fix \
    --overlay-db pdf_cmap_fix/data/per_font/microsofthimalaya.json \
    your.pdf
pdf-cmap-fix -p \
    --overlay-db pdf_cmap_fix/data/per_font/monlamuniouchan2.json \
    your.pdf
```

Multiple `--overlay-db` flags are merged in order; later overlays override earlier overrides, and any overlay overrides the bundled DB on key collision. The runtime merge picks up only the dict-valued top-level keys (the font map), so the `_meta` block is ignored.

To find the right per-font key for a PDF without guessing, run with `--dump-cmap` and look at the printed `[matched] PDF_FONT -> db_key` lines (one per Type0 font in the document). The `db_key` is the file stem in `pdf_cmap_fix/data/per_font/`. The full inventory of per-font keys is in [`docs/font-inventory.md`](docs/font-inventory.md#per-font-gid-maps-pdf_cmap_fixdataper_font) and in [`pdf_cmap_fix/data/per_font/_manifest.json`](pdf_cmap_fix/data/per_font/_manifest.json).

---

## Python API reference

Import the public API from **`pdf_cmap_fix`**:

```python
from pdf_cmap_fix import (
    extract_pdf_text,
    patch_pdf,
    build_tounicode_dict,
    collect_font_merges,
    patch_doc,
    extract_all,
)
```

Optional: load a custom JSON database with `json.loads(...)` and pass as `rev_db=` where supported.

| Function | Purpose |
|----------|---------|
| **`extract_pdf_text`** | Opens the PDF twice: extract raw text, then patch ToUnicode in memory and extract again. Can write `.raw.txt`, `.patched.txt`, `.diff.txt`. |
| **`patch_pdf`** | Applies merged ToUnicode streams and returns bytes (and optionally writes `*.patched.pdf`). |
| **`build_tounicode_dict`** | No PDF mutation: returns per-font `existing` / `merged` / `overrides` plus `stats`. |
| **`collect_font_merges`** | Lower-level: scan the document and compute merge records without writing streams. |
| **`patch_doc`** | Apply merges to an already-open **`fitz.Document`** using `collect_font_merges` + stream updates. |
| **`extract_all`** | Extract plain text from every page (with whitespace/ligature flags); used inside `extract_pdf_text`. |

### `extract_pdf_text`

```python
extract_pdf_text(
    pdf_path,
    output_dir=None,
    write_files=True,
    rev_db=None,
    *,
    verbose=False,
) -> dict
```

| Return key | Type | Description |
|------------|------|-------------|
| `raw` | `str` | Text extracted before patching. |
| `patched` | `str` | Text extracted after ToUnicode merge. |
| `stats` | `dict` | `fonts_seen`, `patched`, `upgrades`, `no_change`, `no_match`. |
| `diff_lines` | `list` | Line indices and raw/patched pairs where lines differ. |
| `char_delta` | `int` | `len(patched) - len(raw)`. |

If `write_files` is true (default), writes `{stem}.raw.txt`, `{stem}.patched.txt`, `{stem}.diff.txt` next to the PDF (or under `output_dir`).

### `patch_pdf`

```python
patch_pdf(
    pdf_path,
    output_path=None,
    write_file=True,
    rev_db=None,
    *,
    verbose=False,
) -> dict
```

| Return key | Description |
|------------|-------------|
| `pdf_bytes` | Patched PDF as `bytes`. |
| `stats` | Same counters as above. |
| `output_path` | `Path` where the file was written, or `None` if `write_file=False`. |

Default output path: `{stem}.patched.pdf` beside the input.

### `build_tounicode_dict`

```python
build_tounicode_dict(pdf_path, rev_db=None) -> dict
```

Returns `fonts` (list of per-font records), `by_font_xref` (dict keyed by xref string), and `stats`. See [docs/glossary-and-json.md](docs/glossary-and-json.md) for field-level documentation.

### `collect_font_merges`

```python
collect_font_merges(doc: fitz.Document, rev_db: dict, *, verbose=False)
-> tuple[list[dict], dict]
```

Returns `(records, stats)`. Each record includes `font_xref`, `to_unicode_xref`, `pdf_font_name`, `db_key_matched`, `existing`, `merged`, `overrides`, `changed`.

### `patch_doc`

```python
patch_doc(doc: fitz.Document, rev_db: dict, *, verbose=False) -> dict[str, int]
```

Mutates **`doc`** in place (writes ToUnicode streams where `changed > 0`). Returns **`stats`**.

### `extract_all`

```python
extract_all(doc: fitz.Document) -> str
```

Full-document text with page banners (`=== PAGE n ===`). Used internally after patching.

---

## Bundled reverse database (font sources)

The file **`pdf_cmap_fix/data/reverse_db.json`** ships with the package (~**16 MB** on disk as of the build below). It maps **normalised font key → { GID string → Unicode string }**, built offline from TrueType/OpenType sources using cmap + GSUB type-4 ligature decomposition (see `scripts/build_reverse_db.py`).

| Property | Value |
|----------|--------|
| **Build date** | **2026-04-28** |
| **Font entries (keys)** | **963** in the merged DB; **968** unique per-font JSONs in `pdf_cmap_fix/data/per_font/` |
| **Full key list** | [docs/font-inventory.md](docs/font-inventory.md) |

### How this copy was produced

Sources were combined **in order**; **later** archives override earlier entries when the **normalised font key** collides (same stem after lowercasing and stripping non-alphanumeric characters):

1. **`scripts/bodyig.zip`** — legacy “bodyig”-style corpus bundled with this repo for reproducibility.
2. **`scripts/tibetan-fonts-main.zip`** — snapshot of the **public** [OpenPecha `tibetan-fonts`](https://github.com/openpecha/tibetan-fonts) **`main`** branch (downloaded as ZIP).
3. **`scripts/tibetan-fonts-private-main.zip`** — snapshot of the **private** Tibetan fonts repo **`main`** branch (downloaded as ZIP).

Command used (from repository root):

```bash
python scripts/build_reverse_db.py ^
  --zip scripts/bodyig.zip ^
  --zip scripts/tibetan-fonts-main.zip ^
  --zip scripts/tibetan-fonts-private-main.zip ^
  -o pdf_cmap_fix/data/reverse_db.json
```

**Why ZIP instead of `git clone`?** On Windows, cloning large font repositories can fail when paths contain characters NTFS rejects (for example `:`). Reading **`.ttf` / `.otf` directly from ZIP files** avoids extracting those paths to disk and matches how CI or contributors can refresh the database without a full checkout.

---

## Updating `reverse_db.json` in the future

When upstream font repositories add or change faces:

1. Download fresh **`main`** ZIP archives (or clone on Linux/macOS / WSL if you prefer `--fonts-dir`).
2. Re-run `build_reverse_db.py` with the same `--zip` order (or adjust order deliberately if you want a different precedence).
3. Replace `pdf_cmap_fix/data/reverse_db.json` and record the **new build date** in this README (and optionally in `CHANGELOG.md`).
4. Regression-test on known PDFs (for example under `docs/examples/`) before tagging a release.

Optional inputs:

```bash
pip install fonttools
python scripts/build_reverse_db.py --fonts-dir path/to/fonts -o pdf_cmap_fix/data/reverse_db.json
python scripts/build_reverse_db.py --zip scripts/bodyig.zip --fonts-dir ../more-fonts -o out.json
```

If you omit `--zip` and `--fonts-dir`, the script defaults to **`scripts/bodyig.zip`** when that file exists.

### Per-font JSONs (`pdf_cmap_fix/data/per_font/`)

Built by [`scripts/build_per_font_gid_maps.py`](scripts/build_per_font_gid_maps.py) from the same three font ZIPs that feed `reverse_db.json`. The same GSUB scope is used: cmap + types **1, 2, 4** plus **type 7 (extension)** wrappers. Contextual lookups (3 / 5 / 6 / 8) are intentionally not reduced to a static GID → Unicode map (see [`docs/approach.md`](docs/approach.md#step-1--build-a-reverse-gid-database)).

To regenerate after a font ZIP update:

```bash
python scripts/build_per_font_gid_maps.py \
    --zip scripts/bodyig.zip \
    --zip scripts/tibetan-fonts-main.zip \
    --zip scripts/tibetan-fonts-private-main.zip
```

The script writes one JSON per face to `pdf_cmap_fix/data/per_font/<normalised_key>.json` plus `_manifest.json` with the index, duplicate report, and any read errors. Usage of these files at runtime is documented in [Per-font overlays](#per-font-overlays) above.

See also **Rebuild** notes in [CHANGELOG.md](CHANGELOG.md).

---

## Migration from `tibetan-pdf-fix` (0.1.x)

| Old (removed) | New (0.2.0) |
|---------------|-------------|
| PyPI / import `tibetan_pdf_fix` | `pdf_cmap_fix` |
| CLI `tibetan-pdf-fix` | `pdf-cmap-fix` |
| `extract_tibetan_pdf(...)` | `extract_pdf_text(...)` |
| `patch_tibetan_pdf(...)` | `patch_pdf(...)` |
| *(new)* | `build_tounicode_dict(...)` — merged CMaps as dicts **without** patching PDF bytes |
| `pip install …` same git URL | Package name **`pdf-cmap-fix`** |

There is **no** compatibility shim: update imports and the CLI name.

---

## Supported fonts & limits

The bundled database covers **963** normalised font keys drawn from the archives above, plus **968** unique per‑font GID maps in `pdf_cmap_fix/data/per_font/` (see [docs/font-inventory.md](docs/font-inventory.md)). Only **Type0 / CID / Identity-H** fonts are handled (PDF character code = original GID in the subset). **TrueType simple-encoding** PDFs (typical of some Ghostscript workflows) are **not** supported by this path.

---

## How it works

1. Match each embedded Type0 font name to an entry in `reverse_db.json`.
2. Parse the PDF’s existing ToUnicode CMap.
3. Merge: the database replaces entries wherever it has a GID mapping (GSUB-derived mappings are treated as authoritative).
4. Optionally write streams back (`patch_pdf` / `extract_pdf_text`) or only return dicts (`build_tounicode_dict`).

Details: [`docs/approach.md`](docs/approach.md).

---

## Worked examples

Five real Tibetan PDFs are committed under [`docs/examples/`](docs/examples/) with their `*.raw.txt`, `*.patched.txt`, `*.diff.txt`, and `*.patched.pdf`. Headline counters (read from each `*.diff.txt` header):

| Example | Producer | Pages | Lines changed | Char delta | Notable fonts |
|---------|----------|------:|--------------:|-----------:|---------------|
| [`TI1055-01-001/`](docs/examples/TI1055-01-001/) | MS Word | 528 | **10,205** | **−23,725** | Monlam Uni OuChan 2 |
| [`TI1751-01-001/`](docs/examples/TI1751-01-001/) | InDesign | 528 | **5,295** | **+10,093** | Monlam Uni OuChan 2, Dedris‑*, Microsoft Himalaya, Jomolhari |
| [`TI803-01-001/`](docs/examples/TI803-01-001/) | MS Word | 398 | **9,356** | **−23,922** | Microsoft Himalaya |
| [`TI1461-01-001/`](docs/examples/TI1461-01-001/) | InDesign | 1 | 25 | −2 | Qomolangma‑Uchen‑Sarchen/Sarchung, Monlam Uni OuChan 1/5 |
| [`TI1763-01-002/`](docs/examples/TI1763-01-002/) | MS Word | 1 | 17 | +127 | Monlam Uni OuChan 2 |

Negative `Char delta` means the patcher removed spurious characters Word had injected; positive means it restored subjoined letters that InDesign had dropped. See [`docs/examples/README.md`](docs/examples/README.md) for representative before/after lines and the exact reproduce command per example (with `--overlay-db` where it helps).

### Beyond Tibetan (smoke test)

The pipeline is **not** Tibetan-specific: any Identity-H Type0 font whose glyph IDs align with a font used to build `reverse_db.json` can be fixed the same way. For a minimal Latin test, build a tiny database from a font with `fi`/`fl` ligatures and validate non-empty `overrides` on a deliberately broken PDF.

---

## Project structure

```
pdf_cmap_fix/                  Python package (installed)
├── extractor.py               Patch / extract / build_tounicode_dict / CLI / --overlay-db
└── data/
    ├── reverse_db.json        GID → Unicode (bundled; ~16 MB; ~963 keys)
    └── per_font/              One JSON per face (~970 files; overlay-friendly)
        ├── _manifest.json     Index, duplicates, errors
        └── <key>.json         e.g. monlamuniouchan2.json, microsofthimalaya.json
scripts/
├── font_sources.py                              Enumerate fonts from zip and/or directories
├── build_reverse_db.py                          Rebuild reverse_db.json (GSUB types 1/2/4 + Extension 7)
├── build_per_font_gid_maps.py                   Per-font JSONs (writes pdf_cmap_fix/data/per_font/)
├── update_reverse_db_from_windows_himalaya.py   In-place refresh of `himalaya` row from %WINDIR%\Fonts\himalaya.ttf
├── diagnose_contextual_gsub.py                  Per-font GSUB 5/6/8 coverage diagnostic (read-only)
└── build_glyph_db.py                            Deprecated — use build_reverse_db.py
docs/
├── README.md                  Documentation index
├── approach.md                Design / pipeline
├── glossary-and-json.md       Terms + JSON shapes
├── font-inventory.md          All bundled DB keys + per_font keys
├── blog.md                    Article (publication-ready)
└── examples/                  Five worked example PDFs + reference outputs
    └── README.md              Index + reproduce commands
tests/                         pytest (optional [dev] install)
```

---

## License

MIT
