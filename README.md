# pdf-cmap-fix

Fix incorrect or incomplete PDF `/ToUnicode` CMaps so extraction, search, and copy-paste return correct Unicode.

Primary use case: Tibetan stacked syllables (Monlam, Himalaya, Jomolhari).  
General scope: any **Type0 / CID / Identity-H** PDF font whose key exists in `pdf_cmap_fix/data/font_lookup/`.

**GitHub:** [OpenPecha/pdf-cmap-fix](https://github.com/OpenPecha/pdf-cmap-fix)

## Documentation

- [Docs index](docs/README.md)
- [Technical approach](docs/approach.md) (includes [worked examples](docs/approach.md#worked-examples))
- [Glossary and JSON formats](docs/glossary-and-json.md)
- [Font inventory](docs/font-inventory.md)
- [Example PDFs and outputs](docs/examples/)
- [Publication article](docs/blog.md)

## Install

Requires Python 3.8+.

```bash
pip install "pdf-cmap-fix @ git+https://github.com/OpenPecha/pdf-cmap-fix.git"
# shorthand:
pip install git+https://github.com/OpenPecha/pdf-cmap-fix.git
```

Development install:

```bash
git clone https://github.com/OpenPecha/pdf-cmap-fix.git
cd pdf-cmap-fix
python -m venv .venv && . .venv/Scripts/activate    # Windows PowerShell
# . .venv/bin/activate                               # macOS / Linux
pip install -e ".[dev]"
pytest -q
```

Verify install:

```bash
pdf-cmap-fix --help
python -c "from pdf_cmap_fix import FONT_LOOKUP_DIR; print(FONT_LOOKUP_DIR)"
```

## CLI quick start

```bash
# Extract + compare (writes .raw.txt / .patched.txt / .diff.txt)
pdf-cmap-fix document.pdf

# Write patched PDF
pdf-cmap-fix -p document.pdf

# Dump merged ToUnicode maps as JSON (no PDF rewrite)
pdf-cmap-fix --dump-cmap document.cmap-dump.json document.pdf
```

Batch multiple PDFs:

```bash
pdf-cmap-fix doc1.pdf doc2.pdf doc3.pdf
```

Quick reference — use another folder of `<key>.json` files at runtime (details below):

```bash
pdf-cmap-fix --font-lookup-dir path/to/font_lookup document.pdf
```

Windows note: if console output raises encoding issues, use UTF-8 (`chcp 65001`) or call Python API with `verbose=False`.

## Font lookup workflows

Runtime reads **GID → Unicode** maps from JSON files: **`font_lookup/<normalised_key>.json`**.  
Use the following in order from “nothing to do” to “maintainers rebuild everything.”

### 1. Bundled package data (default)

Installed copies ship **`pdf_cmap_fix/data/font_lookup/`** (~970 JSON files plus **`_manifest.json`**). The CLI and Python API load from there unless you override `font_lookup_dir`.

No setup is required for normal use.

### 2. Full rebuild from font archives (all fonts)

Use this when you refresh upstream font ZIPs and want to regenerate **every** per-face JSON in one pass.

1. Put the archives under **`scripts/`** (they are git‑ignored). Recommended **order** — later archives **win** when the normalised font key collides:

   - `scripts/bodyig.zip`
   - `scripts/tibetan-fonts-main.zip`
   - `scripts/tibetan-fonts-private-main.zip`

2. From the repository root:

```bash
pip install fonttools   # already satisfied after editable install
python scripts/build_per_font_gid_maps.py \
    --zip scripts/bodyig.zip \
    --zip scripts/tibetan-fonts-main.zip \
    --zip scripts/tibetan-fonts-private-main.zip
```

This writes **`pdf_cmap_fix/data/font_lookup/<key>.json`** for each decoded face and **`_manifest.json`** (index, duplicate report, read errors).  
Optional: **`--fonts-dir`** and **`--zip`** can be combined; **`-o` / `--output-dir`** writes to another directory instead of the default package path.

GSUB coverage matches the rest of the tooling (types **1, 2, 4** + Extension **7** wrappers); see [Technical approach](docs/approach.md) for limits (e.g. contextual lookups 5 / 6 / 8).

### 3. Single font file → one `<key>.json`

Use this when you only need **one** face updated (for example a newer **Microsoft Himalaya** build on Windows) without rebuilding the whole corpus.

```bash
# One or more .ttf / .otf → one JSON each under font_lookup/
python scripts/update_font_lookup.py path/to/MicrosoftHimalaya.ttf

# Explicit output directory (defaults to pdf_cmap_fix/data/font_lookup)
python scripts/update_font_lookup.py --lookup-dir pdf_cmap_fix/data/font_lookup path/to/font.ttf

# Force the JSON stem / lookup key (single font only), e.g. to match a PDF subset name
python scripts/update_font_lookup.py --key microsofthimalaya path/to/MicrosoftHimalaya.ttf

# Preview only
python scripts/update_font_lookup.py --dry-run path/to/font.ttf
```

With **no arguments**, the script defaults to **`%WINDIR%\Fonts\himalaya.ttf`** and writes **`himalaya.json`** into the default lookup dir.

Requires **`pip install fonttools`** (included with the package / dev install).

### 4. Custom directory at runtime (`--font-lookup-dir`)

Use this when you want **patching and extraction** to read maps from **your** directory (a fork of `font_lookup`, a CI artifact, or a folder you assembled from steps 2–3) **without** replacing files inside the installed package.

**CLI** — all modes honour the same directory:

```bash
pdf-cmap-fix --font-lookup-dir /path/to/font_lookup document.pdf
pdf-cmap-fix --font-lookup-dir /path/to/font_lookup -p document.pdf
pdf-cmap-fix --font-lookup-dir /path/to/font_lookup --dump-cmap out.json document.pdf
```

**Python API** — pass **`font_lookup_dir=`** to `extract_pdf_text`, `patch_pdf`, `build_tounicode_dict`, `collect_font_merges`, and `patch_doc`.

Discovery only loads **`*.json`** stems present in that folder (plus `_manifest.json` is ignored for matching). To find which **`db_key`** a PDF needs, run **`--dump-cmap`** or verbose CLI and match **`[matched] … -> <key>`**, or check [Font inventory](docs/font-inventory.md).

## Python API (minimal)

```python
from pdf_cmap_fix import extract_pdf_text, patch_pdf, build_tounicode_dict

result = extract_pdf_text("document.pdf")           # returns raw/patched/stats/diff metadata
patch_pdf("document.pdf")                           # writes document.patched.pdf
cmap = build_tounicode_dict("document.pdf")         # per-font existing/merged/overrides maps
```

Optional: **`font_lookup_dir=Path("…")`** — same meaning as **`--font-lookup-dir`** (see [Font lookup workflows](#font-lookup-workflows)).

For full signatures and return schemas, see [Technical approach](docs/approach.md) and [Glossary and JSON formats](docs/glossary-and-json.md).

## Limits

- Supported path: **Type0 / CID / Identity-H** PDFs.
- Unsupported by this strategy: most **TrueType simple-encoding** PDFs (for example some Ghostscript outputs), where PDF char codes do not preserve original font GIDs.

Details and rationale: [Why only Type0 fonts?](docs/approach.md#why-only-type0-fonts)

## Worked examples

Reference PDFs and generated outputs live in [docs/examples/](docs/examples/).  
For metrics, reproduce commands, and interpretation, see [docs/approach.md#worked-examples](docs/approach.md#worked-examples).

## Project structure

```text
pdf_cmap_fix/
  extractor.py
  data/font_lookup/
scripts/
  build_per_font_gid_maps.py
  update_font_lookup.py
  gid_map.py
docs/
  README.md
  approach.md
  glossary-and-json.md
  font-inventory.md
  blog.md
  examples/
tests/
```

## License

MIT
