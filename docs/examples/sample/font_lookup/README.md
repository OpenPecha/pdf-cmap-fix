# Custom `font_lookup` for `sample.pdf`

This folder holds **only** the JSON files needed to test `sample.pdf` with:

```bash
pdf-cmap-fix --font-lookup-dir docs/examples/sample/font_lookup ...
```

## Regenerate (Windows)

**Jomolhari:** If `Jomolhari*.ttf` (or `.otf`) is installed under `%WINDIR%\Fonts\`, build from that file so GIDs match your system font when possible:

```powershell
python scripts/gid/update_font_lookup.py --lookup-dir docs/examples/sample/font_lookup "$env:WINDIR\Fonts\Jomolhari-Regular.ttf"
```

If Jomolhari is **not** installed, use a **copy of the bundled** `pdf_cmap_fix/data/font_lookup/jomolhari.json` so the key `jomolhari` still resolves. If your PDF was built from a **different** Jomolhari build than the bundled map, refresh the JSON from the same `.ttf` you trust for that document.

## PUA-free gshape (local Windows fonts)

For `sample.pdf` with **synthetic glyph names** (`glyph00001`, …), tier-2 gname lookups often do not match; use **tier-3 gshape** built from your installed Jomolhari plus a public-Unicode gname table, then patch PUA out of the gshape JSON. Full steps: [local-jomolhari-gshape-pua-free.md](../../workflows/local-jomolhari-gshape-pua-free.md) (or run `python scripts/misc/run_local_gshape_jomolhari_pipeline.py`). The repo-wide batch workflow is [pua-free-font-lookups.md](../../workflows/pua-free-font-lookups.md).

**Cambria (TrueType collection):** `cambria.ttc` contains multiple faces. Use `--ttc-index` (default in script is `0` for `.ttc` if omitted):

```powershell
python scripts/gid/update_font_lookup.py --ttc-index 0 --lookup-dir docs/examples/sample/font_lookup "$env:WINDIR\Fonts\cambria.ttc"
```

That writes `cambria.json` (normalised key `cambria`), matching `AAAAAD+Cambria` in the PDF.

## Test commands (repo root)

```powershell
$env:PYTHONUTF8 = "1"
$LOOKUP = "docs/examples/sample/font_lookup"
pdf-cmap-fix --font-lookup-dir $LOOKUP docs/examples/sample/sample.pdf
pdf-cmap-fix --font-lookup-dir $LOOKUP -p docs/examples/sample/sample.pdf
pdf-cmap-fix --font-lookup-dir $LOOKUP --dump-cmap docs/examples/sample/sample.custom.cmap-dump.json docs/examples/sample/sample.pdf
```

Outputs are written next to `sample.pdf` (`sample.raw.txt`, `sample.patched.txt`, `sample.diff.txt`, `sample.patched.pdf`).

## Git

`*.json` in this folder are listed in the root `.gitignore` so generated maps are not committed; this `README.md` is tracked.
