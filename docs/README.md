# Documentation index

| Document | Contents |
|----------|----------|
| [tiers/README.md](tiers/README.md) | **Tier map:** which `pdf_cmap_fix/data/` directory is tier 1 / 2 / 3 (and PUA-free siblings); links to scripts by folder |
| [../README.md](../README.md) | Install, CLI, Python API, font lookup workflows (bulk ZIP rebuild, single-font script, tiers 2–3, PUA-free), project layout |
| [workflows/pua-free-font-lookups.md](workflows/pua-free-font-lookups.md) | Global PUA-free batch using the new `scripts/pua/` structure: inventory PUA, rewrite **gname**, patch **gshape** (and optional **gid**) into `*_pua_free/` trees; archive-only fonts; verification |
| [workflows/local-jomolhari-gshape-pua-free.md](workflows/local-jomolhari-gshape-pua-free.md) | Windows fast path: local Jomolhari + Cambria gshape, public gname from bundled tier-2, in-place gshape patch |
| [font-lookup-tiers-2-3.md](font-lookup-tiers-2-3.md) | Tier 2 (glyph name) and tier 3 (outline hash) lookup JSON: schema, `_meta`, CLI flags, merge status |
| [approach.md](approach.md) | How ToUnicode patching, GSUB-based GID→Unicode construction (types 1, 2, 4 + Extension 7), and font matching work; whitespace caveat |
| [glossary-and-json.md](glossary-and-json.md) | Terms (Type0, GID, ToUnicode, CMap, GSUB, …) and JSON shapes (`font_lookup/*.json`, `font_lookup_gname/`, `font_lookup_gshape/`, API outputs) |
| [font-inventory.md](font-inventory.md) | Keys shipped under `pdf_cmap_fix/data/font_lookup/` (~968) |
| [examples/](examples/) | Sample PDFs + reference outputs (`.raw.txt` / `.patched.txt` / `.diff.txt` / `.patched.pdf` / `.cmap-dump.json`); narrative in [approach.md § Worked examples](approach.md#worked-examples) |
