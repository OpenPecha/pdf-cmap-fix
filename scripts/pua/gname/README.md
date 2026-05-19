# scripts/pua/gname — PUA-free gname lookup builder

Builds `font_lookup_gname_pua_free/`: one JSON per font where glyph name → Unicode with all PUA values replaced by the standard Unicode decoded from `uni…` glyph names.

**Run this tier first.** `scripts/pua/gshape/` and `scripts/pua/gid/` both consume the output via `--gname-dir`.

## What lives here

| Script | Purpose |
|--------|---------|
| [`build_pua_free_gname_maps.py`](build_pua_free_gname_maps.py) | **Bulk** — ZIP archives or a font directory → `font_lookup_gname_pua_free/` |
| [`update_pua_free_gname.py`](update_pua_free_gname.py) | **Single font** — one `.ttf` / `.otf` / `.ttc` → one JSON in `font_lookup_gname_pua_free/` |

Shared logic (PUA rewriting, bulk pipeline, single-font CLI) lives in **[`scripts/font_lookup_common/`](../../font_lookup_common/README.md)** (`pua_gname_rewriter.py`, `per_font_maps.py`, `single_font_lookup.py`).

---

## Commands

### Bulk from ZIP archives

```bash
python scripts/pua/gname/build_pua_free_gname_maps.py \
  --zip fonts/bodyig.zip --zip fonts/tibetan-fonts-main.zip
```

### Custom output directory

```bash
python scripts/pua/gname/build_pua_free_gname_maps.py \
  --zip fonts/bodyig.zip -o ./builds/custom_gname_pua_free
```

### From a folder of loose .ttf / .otf

```bash
python scripts/pua/gname/build_pua_free_gname_maps.py \
  --fonts-dir /path/to/fonts -o ./builds/custom_gname_pua_free
```

### Single font

```bash
python scripts/pua/gname/update_pua_free_gname.py \
  --lookup-dir ./builds/custom_gname_pua_free path/to/MyFont.ttf
```

### Force key / preview

```bash
# Force the output key name
python scripts/pua/gname/update_pua_free_gname.py \
  --key jomolhari path/to/Jomolhari-Regular.ttf

# Dry-run: show what would be written without writing
python scripts/pua/gname/update_pua_free_gname.py --dry-run path/to/MyFont.ttf
```

---

## Output

Default: `pdf_cmap_fix/data/font_lookup_gname_pua_free/<key>.json`

Each file has the same structure as a regular gname JSON, plus `_meta.pua_to_unicode_from_uni_names: true` and `_meta.pua_rows_rewritten: N`.
