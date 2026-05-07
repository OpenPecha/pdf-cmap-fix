# Changelog

## 0.3.0 — 2026-05-06

### Breaking

- **Runtime** no longer loads a merged `pdf_cmap_fix/data/reverse_db.json`. Patching and extraction load **`pdf_cmap_fix/data/font_lookup/<key>.json`** (directory renamed from `per_font/`). The Python API **`collect_font_merges`**, **`patch_doc`**, **`patch_pdf`**, **`extract_pdf_text`**, and **`build_tounicode_dict`** take keyword-only **`font_lookup_dir=`** (no in-memory merged `rev_db`).
- **Removed `overlay_maps=`** and CLI **`--overlay-db`**. Use **`font_lookup_dir=`** or **`pdf-cmap-fix --font-lookup-dir DIR`** so all GID maps come from one directory of `<key>.json` files (refresh a file with **`scripts/update_font_lookup.py`**).

### Added

- **`pdf_cmap_fix.FONT_LOOKUP_DIR`** — path to the bundled font lookup directory.
- **`scripts/gid_map.py`** — shared cmap + GSUB decomposition (`build_gid_map`, `normalise_name`, helpers).

### Removed

- **`scripts/build_reverse_db.py`** and **`scripts/build_glyph_db.py`** — merged / legacy builders not used for runtime font lookup.
- **`scripts/update_reverse_db_from_windows_himalaya.py`** — replaced by **`scripts/update_font_lookup.py`** (any local font → `font_lookup/<key>.json`).

### Documentation

- README, **approach.md**, **glossary-and-json.md**, **font-inventory.md**, and **examples/README.md** updated for the `font_lookup/` layout.
- **approach.md**: Align database scope (multi-ZIP build), supported-fonts narrative, TI1751/TI1055 benchmark metrics, file layout (optional `*.patched.pdf`, `*.cmap-dump.json`), and rebuild commands with root **README**.
- **glossary-and-json.md**: Clarify **`--dump-cmap`** output size and UTF-8 surrogate sanitisation for rare broken ToUnicode strings.

### CLI / tooling

- **`--dump-cmap`**: Sanitise lone UTF-16 surrogates before writing JSON so dumps succeed on all platforms.

## 0.2.0 — 2026-04-28

### Documentation & data

- Expanded **README**: installation (`pip install git+…`), full Python API reference, CLI quick start, bundled database provenance (build date **2026-04-28**, ZIP sources, update workflow).
- Added **docs/README.md** (index), **docs/glossary-and-json.md** (terms + JSON formats), **docs/font-inventory.md** (all **962** normalised keys).
- Bundled **`reverse_db.json`** regenerated from `bodyig.zip`, `tibetan-fonts-main.zip`, and `tibetan-fonts-private-main.zip` (~16 MB).

### Breaking

- Package renamed from `tibetan-pdf-fix` / `tibetan_pdf_fix` to **`pdf-cmap-fix`** / **`pdf_cmap_fix`** (no shim).
- CLI: `tibetan-pdf-fix` → **`pdf-cmap-fix`**.
- API: `extract_tibetan_pdf` → **`extract_pdf_text`**, `patch_tibetan_pdf` → **`patch_pdf`**.

### Added

- **`build_tounicode_dict(pdf_path)`** — returns per-font `existing`, `merged`, and `overrides` without mutating the PDF.
- **`collect_font_merges`** — lower-level merge inspection.
- CLI **`--dump-cmap OUT.json`** for JSON export of the same structure.
- **`scripts/font_sources.py`** — shared zip / directory iteration (`.ttf`, `.otf`).

### Deprecated / superseded (historical)

- Legacy **`build_glyph_db`** / merged **`reverse_db.json`** tooling — dropped in **0.3.0** in favour of **`gid_map.py`** + **`font_lookup/`** only.

## 0.1.0 — earlier

- Initial `tibetan-pdf-fix` release.
