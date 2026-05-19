# Data layout vs tier (package `pdf_cmap_fix/data/`)

These directory names are **fixed** by the build scripts and the extractor defaults. They are **not** nested under a `tiers/` folder in the repo; separation is by **parallel sibling directories** so the wheel can ship tier 1 only while tiers 2–3 stay optional build outputs.

| Path | `_meta.lookup_kind` | Notes |
|------|---------------------|--------|
| `font_lookup/` | `gid` | Shipped with `pip install`; ~970 `<key>.json` + `_manifest.json` |
| `font_lookup_gname/` | `gname` | Rebuild from font ZIPs or `scripts/gname/update_font_lookup.py` |
| `font_lookup_gshape/` | `gshape` | Rebuild from font ZIPs or `scripts/gshape/update_font_lookup.py` |
| `font_lookup_gname_pua_free/` | `gname` | Output of `scripts/pua/gname/build_pua_free_gname_maps.py` |
| `font_lookup_gshape_pua_free/` | `gshape` | Output of `scripts/pua/gshape/build_pua_free_gshape_maps.py` |
| `font_lookup_gid_pua_free/` | `gid` | Optional; `scripts/pua/gid/build_pua_free_gid_maps.py` |

PUA-free trees are often **gitignored**; regenerate with [`scripts/pua/run_all.py`](../../scripts/pua/run_all.py).
