# `scripts/font_lookup_common/` — shared tier 1–3 lookup build library

Python modules used by **`scripts/gid/`**, **`scripts/gname/`**, **`scripts/gshape/`**, **`scripts/pua/`**, and **`scripts/misc/`**. Not a CLI entrypoint: run the tier-specific scripts in the tier folders.

| Module | Role |
|--------|------|
| [`gid_map.py`](gid_map.py) | cmap + GSUB (types 1, 2, 4, Extension 7) → per-GID Unicode strings. |
| [`font_lookup_payload.py`](font_lookup_payload.py) | Build JSON payloads for **gid** / **gname** / **gshape** inner maps from a `gid_map` and `TTFont`. |
| [`font_sources.py`](font_sources.py) | Iterate fonts from ZIPs and recursive directories (`.ttf` / `.otf`). |
| [`per_font_maps.py`](per_font_maps.py) | Shared **bulk** ZIP/dir → per-font JSON + `_manifest.json` (`run_per_font_cli`). |
| [`single_font_lookup.py`](single_font_lookup.py) | Shared **single-font** refresh (`main_for_kind`, `_write_one`) for all tiers. |

Tier CLIs prepend this directory to `sys.path` and import these modules by plain name (no package).
