# `scripts/gid/` — tier 1 (GID → Unicode) lookup builds

Run from the **repository root**. These tools emit JSON whose inner keys are **GID strings** (decimal) → **Unicode strings**, with `_meta.lookup_kind` defaulting to **`gid`**.

PUA-free builds into **`pdf_cmap_fix/data/font_lookup_gid_pua_free/`** are produced by **[`scripts/pua/gid/`](../pua/gid/README.md)** — builds GID maps from fonts and patches values using a gname PUA-free sidecar.

## What lives here

| Item | Role |
|------|------|
| [`build_per_font_gid_maps.py`](build_per_font_gid_maps.py) | **Bulk rebuild** from one or more **ZIPs** and/or **directories** of fonts (`--zip`, `--fonts-dir`, repeatable). Writes `pdf_cmap_fix/data/font_lookup/` by default, or `-o` / `--output-dir` for a **custom** tree. Tier 2/3 bulk builds: [`scripts/gname/build_per_font_gname_maps.py`](../gname/build_per_font_gname_maps.py), [`scripts/gshape/build_per_font_gshape_maps.py`](../gshape/build_per_font_gshape_maps.py). |
| [`update_font_lookup.py`](update_font_lookup.py) | **Tier 1 only** — one or more faces from `.ttf` / `.otf` / `.ttc` → GID-keyed JSON. For gname/gshape single-font refresh, use `scripts/gname/update_font_lookup.py` or `scripts/gshape/update_font_lookup.py`. |

Shared bulk + cmap/GSUB + single-font logic lives in **[`scripts/font_lookup_common/`](../font_lookup_common/README.md)** (`per_font_maps.py`, `gid_map.py`, `font_lookup_payload.py`, `font_sources.py`, `single_font_lookup.py`).

**Related (not in this folder):** [`scripts/misc/diagnose_contextual_gsub.py`](../misc/diagnose_contextual_gsub.py) — maintainer diagnostic for GSUB contextual / alternate coverage.

## Typical commands

```bash
# Full corpus from archives (defaults under pdf_cmap_fix/data/font_lookup/)
python scripts/gid/build_per_font_gid_maps.py \
  --zip fonts/bodyig.zip \
  --zip fonts/tibetan-fonts-main.zip \
  --zip fonts/tibetan-fonts-private-main.zip

# Custom output directory from ZIPs only (creates <key>.json + _manifest.json there)
python scripts/gid/build_per_font_gid_maps.py --zip myfonts.zip -o /path/to/custom_font_lookup

# Build from a folder of loose .ttf / .otf (recursive scan) into a custom tree
python scripts/gid/build_per_font_gid_maps.py \
  --fonts-dir /path/to/my/font/folder \
  -o ./builds/custom_gid_lookup

# Combine ZIPs + local directories in one run (later sources win on duplicate keys)
python scripts/gid/build_per_font_gid_maps.py \
  --zip fonts/bodyig.zip \
  --fonts-dir ./extra_fonts \
  -o ./builds/mixed_corpus_gid

# One font file → one JSON under a custom lookup folder (creates dir if needed; overwrites same key)
python scripts/gid/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup \
  path/to/MyFont.ttf

# Several font files at once into the same custom folder
python scripts/gid/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup \
  fonts/A.ttf fonts/B.otf path/to/C.ttf

# Force the JSON stem / lookup key (single font only), e.g. match a PDF embedded font name tag
python scripts/gid/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup \
  --key microsofthimalaya \
  "D:/Fonts/Microsoft Himalaya.ttf"

# Exact output path (single font only; overrides the usual <lookup-dir>/<key>.json name)
python scripts/gid/update_font_lookup.py \
  -o ./builds/custom_font_lookup/myalias.json \
  path/to/ActualFontName.ttf

# TrueType collection: pick face index, still under a custom lookup dir
python scripts/gid/update_font_lookup.py \
  --lookup-dir ./builds/custom_font_lookup \
  --ttc-index 0 \
  "C:/Windows/Fonts/cambria.ttc"

# Preview what would be written (no files touched)
python scripts/gid/update_font_lookup.py --dry-run --lookup-dir ./builds/custom_font_lookup path/to/font.ttf

# Refresh one key inside the shipped package tree (overwrites that JSON in place)
python scripts/gid/update_font_lookup.py \
  --lookup-dir pdf_cmap_fix/data/font_lookup \
  path/to/MicrosoftHimalaya.ttf
```

For end-user PDF patching, use the **`pdf-cmap-fix`** CLI (or `pdf_cmap_fix` Python API) with `--font-lookup-dir` pointing at your built folder.
