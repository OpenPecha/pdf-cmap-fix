# Lookup tiers (runtime data + maintainer scripts)

Use this page as a **map** between tier numbers, **`pdf_cmap_fix/data/`** directories, and **`scripts/`** subfolders.

## Runtime: which directory do I pass to `--font-lookup-dir`?

| Tier | Inner map keys | Data directory (under `pdf_cmap_fix/data/`) | PUA-reduced sibling (optional) |
|------|----------------|-----------------------------------------------|--------------------------------|
| **1** | GID (decimal string) | `font_lookup/` | `font_lookup_gid_pua_free/` |
| **2** | PostScript glyph name | `font_lookup_gname/` | `font_lookup_gname_pua_free/` |
| **3** | Outline fingerprint | `font_lookup_gshape/` | `font_lookup_gshape_pua_free/` |

Each JSON file sets **`_meta.lookup_kind`** to `gid`, `gname`, or `gshape`. The extractor reads whichever folder you point at.

## Maintainer: where is the CLI for each tier?

| Tier | Scripts folder |
|------|----------------|
| 1 | [`scripts/gid/`](../../scripts/gid/) |
| 2 | [`scripts/gname/`](../../scripts/gname/) |
| 3 | [`scripts/gshape/`](../../scripts/gshape/) |
| PUA-free builders (all tiers) | [`scripts/pua/`](../../scripts/pua/) — `gname/`, `gshape/`, `gid/` subfolders; `run_all.py` orchestrates |
| Shared (Python library) | [`scripts/font_lookup_common/`](../../scripts/font_lookup_common/) — `gid_map.py`, `per_font_maps.py`, `single_font_lookup.py`, …; imported by the three tier folders |

Full command list: [`scripts/README.md`](../../scripts/README.md).

## Deeper reading

- [font-lookup-tiers-2-3.md](../font-lookup-tiers-2-3.md) — schema, merge behaviour, flags for tiers 2–3  
- [glossary-and-json.md](../glossary-and-json.md) — JSON shapes and terms  
- [workflows/pua-free-font-lookups.md](../workflows/pua-free-font-lookups.md) — global PUA-free batch + diagrams  
- [data-layout.md](data-layout.md) — same tier ↔ directory table for copy-paste  
