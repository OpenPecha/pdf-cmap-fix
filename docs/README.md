# Documentation index

| Document | Contents |
|----------|----------|
| [../README.md](../README.md) | Install, CLI, Python API, **[Font lookup workflows](../README.md#font-lookup-workflows)** (bundled data, bulk ZIP rebuild, single-font script, `--font-lookup-dir`), project layout |
| [approach.md](approach.md) | How ToUnicode patching, GSUB-based GID→Unicode construction (types 1, 2, 4 + Extension 7), and font matching work; whitespace caveat |
| [glossary-and-json.md](glossary-and-json.md) | Terms (Type0, GID, ToUnicode, CMap, GSUB, …) and JSON shapes (`font_lookup/*.json`, API outputs) |
| [font-inventory.md](font-inventory.md) | Keys shipped under `pdf_cmap_fix/data/font_lookup/` (~968) |
| [blog.md](blog.md) | Publication-ready article: problem, design, two worked examples, install, citation, acknowledgements |
| [examples/](examples/) | Sample PDFs + reference outputs (`.raw.txt` / `.patched.txt` / `.diff.txt` / `.patched.pdf` / `.cmap-dump.json`); narrative in [approach.md § Worked examples](approach.md#worked-examples) |
