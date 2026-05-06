# Documentation index

| Document | Contents |
|----------|----------|
| [../README.md](../README.md) | Installation, CLI, Python API, bundled database provenance, per-font overlays, project layout |
| [approach.md](approach.md) | How ToUnicode patching, GSUB-based reverse DB construction (types 1, 2, 4 + Extension 7), and font matching work; whitespace caveat |
| [glossary-and-json.md](glossary-and-json.md) | Terms (Type0, GID, ToUnicode, CMap, GSUB, …) and JSON shapes (`reverse_db.json`, per-font JSONs, API outputs) |
| [font-inventory.md](font-inventory.md) | All 963 keys in the bundled `reverse_db.json` and the 968 keys in `pdf_cmap_fix/data/per_font/`, with the delta between them |
| [blog.md](blog.md) | Publication-ready article: problem, design, two worked examples, install, citation, acknowledgements |
| [examples/](examples/) | Five worked example PDFs with `.raw.txt` / `.patched.txt` / `.diff.txt` / `.patched.pdf` (and `.cmap-dump.json` for the two large InDesign / Word PDFs) |
| [examples/README.md](examples/README.md) | Index of the worked examples with one-line summaries and the exact reproduce command per example |
