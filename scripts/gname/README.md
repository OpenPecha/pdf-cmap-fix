# `scripts/gname/` — tier 2 (glyph name → Unicode) lookup builds

Run from the **repository root**. These tools emit JSON whose inner keys are **PostScript glyph names** → **Unicode strings**, with `_meta.lookup_kind` **`gname`**.

Shared cmap + GSUB + bulk + single-font logic lives under **[`scripts/font_lookup_common/`](../font_lookup_common/README.md)** (`gid_map.py`, `font_lookup_payload.py`, `per_font_maps.py`, `single_font_lookup.py`, …). Tier 1 bulk / single-font CLIs: [`scripts/gid/`](../gid/README.md). Tier 3: [`scripts/gshape/`](../gshape/README.md).

PUA-free builds into **`pdf_cmap_fix/data/font_lookup_gname_pua_free/`** are produced by **[`scripts/pua/gname/`](../pua/gname/README.md)** — builds gname from fonts and rewrites PUA values using `uni…` glyph name decoding.

## What lives here

| Item | Role |
|------|------|
| [`build_per_font_gname_maps.py`](build_per_font_gname_maps.py) | **Bulk rebuild** from one or more **ZIPs** and/or **directories** of fonts (`--zip`, `--fonts-dir`, repeatable). Writes **`pdf_cmap_fix/data/font_lookup_gname/`** by default, or **`-o` / `--output-dir`** for a **custom** tree (`<key>.json` + `_manifest.json`). Same flags as tier 1 / 3 bulk scripts. |
| [`update_font_lookup.py`](update_font_lookup.py) | **Tier 2 only** — one or more faces from `.ttf` / `.otf` / `.ttc` → glyph-name–keyed JSON. Same flags as [`scripts/gid/update_font_lookup.py`](../gid/update_font_lookup.py) (`--lookup-dir`, `--key`, `-o`, `--dry-run`, `--ttc-index`). Implementation: [`scripts/font_lookup_common/single_font_lookup.py`](../font_lookup_common/single_font_lookup.py). |

## Typical commands

```bash
# Full corpus from archives (defaults under pdf_cmap_fix/data/font_lookup_gname/)
python scripts/gname/build_per_font_gname_maps.py \
  --zip fonts/bodyig.zip \
  --zip fonts/tibetan-fonts-main.zip \
  --zip fonts/tibetan-fonts-private-main.zip

# Custom output directory from ZIPs only (creates <key>.json + _manifest.json there)
python scripts/gname/build_per_font_gname_maps.py --zip myfonts.zip -o /path/to/custom_font_lookup_gname

# Build from a folder of loose .ttf / .otf (recursive scan) into a custom tree
python scripts/gname/build_per_font_gname_maps.py \
  --fonts-dir /path/to/my/font/folder \
  -o ./builds/custom_gname_lookup

# Combine ZIPs + local directories in one run (later sources win on duplicate keys)
python scripts/gname/build_per_font_gname_maps.py \
  --zip fonts/bodyig.zip \
  --fonts-dir ./extra_fonts \
  -o ./builds/mixed_corpus_gname

# One font file → one JSON under a custom lookup folder (creates dir if needed; overwrites same key)
python scripts/gname/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gname \
  path/to/MyFont.ttf

# Several font files at once into the same custom folder
python scripts/gname/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gname \
  fonts/A.ttf fonts/B.otf path/to/C.ttf

# Force the JSON stem / lookup key (single font only), e.g. match a normalised PDF font name
python scripts/gname/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gname \
  --key microsofthimalaya \
  "D:/Fonts/Microsoft Himalaya.ttf"

# Exact output path (single font only; overrides the usual <lookup-dir>/<key>.json name)
python scripts/gname/update_font_lookup.py \
  -o ./builds/custom_font_lookup_gname/myalias.json \
  path/to/ActualFontName.ttf

# TrueType collection: pick face index, still under a custom lookup dir
python scripts/gname/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup_gname \
  --ttc-index 0 \
  "C:/Windows/Fonts/cambria.ttc"

# Preview what would be written (no files touched)
python scripts/gname/update_font_lookup.py --dry-run --lookup-dir ./builds/custom_font_lookup_gname path/to/font.ttf

# Refresh one key inside the shipped package tree (overwrites that JSON in place)
python scripts/gname/update_font_lookup.py \
  --lookup-dir pdf_cmap_fix/data/font_lookup_gname \
  path/to/MicrosoftHimalaya.ttf
```

For end-user PDF patching at tier 2, use the **`pdf-cmap-fix-gname`** CLI (or the matching Python entrypoint) with **`--font-lookup-dir`** pointing at your built folder.
