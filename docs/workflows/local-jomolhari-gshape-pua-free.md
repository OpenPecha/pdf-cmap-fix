# Local Jomolhari + Cambria gshape (Windows) and PUA-free patch

Fast path for developers working with [`docs/examples/sample/sample.pdf`](../examples/sample/sample.pdf) and **fonts installed on Windows** (including per-user `%LOCALAPPDATA%\Microsoft\Windows\Fonts`).

## Why gshape (not gname) for this PDF

Some PDFs expose only **synthetic glyph names** (`glyph00001`, …), so **tier-2 gname** lookups do not match. **Tier-3 gshape** (outline fingerprint) still matches when you index the same face you use for extraction.

## Steps (automated)

```powershell
$env:PYTHONUTF8 = "1"
cd path\to\pdf-cmap-fix
python scripts/misc/run_local_gshape_jomolhari_pipeline.py --pdf docs/examples/sample/sample.pdf
# or:
# .\scripts\misc\run_local_gshape_jomolhari_pipeline.ps1 --pdf docs/examples/sample/sample.pdf
```

This script:

1. Discovers **Jomolhari** (`*jomol*` under per-user Fonts, then `%WINDIR%\Fonts`).
2. Builds **gshape** JSON for Jomolhari + `cambria.ttc` into `docs/examples/sample/font_lookup_gshape_local/`.
3. Writes **public gname** Unicode from bundled `pdf_cmap_fix/data/font_lookup_gname/jomolhari.json` via `scripts/misc/inspect_pua_gname.py --rewrite-lookup` → `docs/examples/sample/jomolhari_gname_public_unicode.json`.
4. Rebuilds the Jomolhari gshape lookup from the TTF and patches PUA values via `scripts/pua/gshape/update_pua_free_gshape.py --gname-json`.
5. Optionally runs `python -m pdf_cmap_fix …` on each `--pdf` path.

## Manual equivalents

See [pua-free-font-lookups.md](pua-free-font-lookups.md) for the global batch and theory.

## Troubleshooting

- If bundled `font_lookup_gname/jomolhari.json` is missing, build tier-2 from archives first.
- If `pdf-cmap-fix` is not on `PATH`, `python -m pdf_cmap_fix` is supported after install.
