# scripts/pua/gid — PUA-free GID lookup builder

Builds `font_lookup_gid_pua_free/`: one JSON per font where GID → Unicode with PUA values replaced by the standard Unicode from the matching gname PUA-free sidecar.

**Requires `font_lookup_gname_pua_free/` to exist.** Run `scripts/pua/gname/` first.

## What lives here

| Script | Purpose |
|--------|---------|
| [`build_pua_free_gid_maps.py`](build_pua_free_gid_maps.py) | **Bulk** — ZIP archives or font directory + `--gname-dir` → `font_lookup_gid_pua_free/` |
| [`update_pua_free_gid.py`](update_pua_free_gid.py) | **Single font** — one `.ttf` / `.otf` / `.ttc` + `--gname-json` → one JSON |

Shared logic lives in **[`scripts/font_lookup_common/`](../../font_lookup_common/README.md)** (`pua_gid_patcher.py`, `per_font_maps.py`, `single_font_lookup.py`).

---

## Commands

### Bulk from ZIP archives

```bash
python scripts/pua/gid/build_pua_free_gid_maps.py \
  --zip fonts/bodyig.zip \
  --gname-dir pdf_cmap_fix/data/font_lookup_gname_pua_free
```

### Custom directories

```bash
python scripts/pua/gid/build_pua_free_gid_maps.py \
  --zip fonts/bodyig.zip \
  --gname-dir ./builds/custom_gname_pua_free \
  -o ./builds/custom_gid_pua_free
```

### From a folder of loose fonts

```bash
python scripts/pua/gid/build_pua_free_gid_maps.py \
  --fonts-dir /path/to/fonts \
  --gname-dir pdf_cmap_fix/data/font_lookup_gname_pua_free
```

### Single font

```bash
python scripts/pua/gid/update_pua_free_gid.py \
  --lookup-dir ./builds/custom_gid_pua_free \
  --gname-json ./builds/custom_gname_pua_free/microsofthimalaya.json \
  path/to/MicrosoftHimalaya.ttf
```

### Dry-run

```bash
python scripts/pua/gid/update_pua_free_gid.py \
  --dry-run --gname-json path/to/font.json path/to/Font.ttf
```

---

## Output

Default: `pdf_cmap_fix/data/font_lookup_gid_pua_free/<key>.json`

Each file has the same structure as a regular GID JSON, plus patching metadata in `_meta` (`gid_rows_patched_from_gname_json`, `gid_patch_missing_gname_entries`).

Fonts without a matching gname sidecar in `--gname-dir` are written **unpatched** (with a warning).
