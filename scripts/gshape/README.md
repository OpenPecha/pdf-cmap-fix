# `scripts/gshape/` — tier 3 (outline hash → Unicode) lookup builds

Run from the **repository root**. These tools emit JSON whose inner keys are **outline fingerprint strings** → **Unicode strings**, with `_meta.lookup_kind` **`gshape`**.

Shared cmap + GSUB + fingerprint + bulk + single-font logic lives under **[`scripts/font_lookup_common/`](../font_lookup_common/README.md)** (plus `pdf_cmap_fix/glyph_fingerprint.py` for tier 3). Tier 1: [`scripts/gid/`](../gid/README.md). Tier 2: [`scripts/gname/`](../gname/README.md).

PUA-free builds under **`pdf_cmap_fix/data/font_lookup_gshape_pua_free/`** are produced by **[`scripts/pua/gshape/`](../pua/gshape/README.md)** — which builds gshape from scratch and patches PUA values using a gname PUA-free sidecar.

## What lives here

| Item | Role |
|------|------|
| [`build_per_font_gshape_maps.py`](build_per_font_gshape_maps.py) | **Bulk rebuild** from one or more **ZIPs** and/or **directories** of fonts (`--zip`, `--fonts-dir`, repeatable). Writes **`pdf_cmap_fix/data/font_lookup_gshape/`** by default, or **`-o` / `--output-dir`** for a **custom** tree (`<key>.json` + `_manifest.json`). Same flags as tier 1 / 2 bulk scripts. |
| [`update_font_lookup.py`](update_font_lookup.py) | **Tier 3 only** — one or more faces from `.ttf` / `.otf` / `.ttc` → outline-hash–keyed JSON. Same flags as [`scripts/gid/update_font_lookup.py`](../gid/update_font_lookup.py) (`--lookup-dir`, `--key`, `-o`, `--dry-run`, `--ttc-index`). Implementation: [`scripts/font_lookup_common/single_font_lookup.py`](../font_lookup_common/single_font_lookup.py). |

## Typical commands

```bash
# Full corpus from archives (defaults under pdf_cmap_fix/data/font_lookup_gshape/)
python scripts/gshape/build_per_font_gshape_maps.py \
  --zip fonts/bodyig.zip \
  --zip fonts/tibetan-fonts-main.zip \
  --zip fonts/tibetan-fonts-private-main.zip

# Custom output directory from ZIPs only (creates <key>.json + _manifest.json there)
python scripts/gshape/build_per_font_gshape_maps.py --zip myfonts.zip -o /path/to/custom_font_lookup_gshape

# Build from a folder of loose .ttf / .otf (recursive scan) into a custom tree
python scripts/gshape/build_per_font_gshape_maps.py \
  --fonts-dir /path/to/my/font/folder \
  -o ./builds/custom_gshape_lookup

# Combine ZIPs + local directories in one run (later sources win on duplicate keys)
python scripts/gshape/build_per_font_gshape_maps.py \
  --zip fonts/bodyig.zip \
  --fonts-dir ./extra_fonts \
  -o ./builds/mixed_corpus_gshape

# One font file → one JSON under a custom lookup folder (creates dir if needed; overwrites same key)
python scripts/gshape/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gshape \
  path/to/MyFont.ttf

# Several font files at once into the same custom folder
python scripts/gshape/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gshape \
  fonts/A.ttf fonts/B.otf path/to/C.ttf

# Force the JSON stem / lookup key (single font only), e.g. match a normalised PDF font name
python scripts/gshape/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gshape \
  --key microsofthimalaya \
  "D:/Fonts/Microsoft Himalaya.ttf"

# Exact output path (single font only; overrides the usual <lookup-dir>/<key>.json name)
python scripts/gshape/update_font_lookup.py \
  -o ./builds/custom_font_lookup_gshape/myalias.json \
  path/to/ActualFontName.ttf

# TrueType collection: pick face index, still under a custom lookup dir
python scripts/gshape/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gshape \
  --ttc-index 0 \
  "C:/Windows/Fonts/cambria.ttc"

# Preview what would be written (no files touched)
python scripts/gshape/update_font_lookup.py --dry-run --lookup-dir ./builds/custom_font_lookup_gshape path/to/font.ttf

# Refresh one key inside the shipped package tree (overwrites that JSON in place)
python scripts/gshape/update_font_lookup.py \
  --lookup-dir pdf_cmap_fix/data/font_lookup_gshape \
  path/to/MicrosoftHimalaya.ttf
```

For end-user PDF patching at tier 3, use the **`pdf-cmap-fix-gshape`** CLI with **`--font-lookup-dir`** pointing at your built folder.
