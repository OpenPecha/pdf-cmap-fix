# Worked examples: six lookup tiers

Reference PDFs demonstrating **pdf-cmap-fix** on real documents. Each example is processed with **six** bundled lookup directories under `pdf_cmap_fix/data/` so you can compare tiers on the same file.

| Lookup folder | CLI | Inner keys |
|---------------|-----|------------|
| `font_lookup/` | `pdf-cmap-fix` | GID (tier 1) |
| `font_lookup_gname/` | `pdf-cmap-fix-gname` | Glyph names (tier 2) |
| `font_lookup_gshape/` | `pdf-cmap-fix-gshape` | Outline hash (tier 3) |
| `font_lookup_gname_pua_free/` | `pdf-cmap-fix-gname` | gname, PUA patched |
| `font_lookup_gshape_pua_free/` | `pdf-cmap-fix-gshape` | gshape, PUA patched |
| `font_lookup_gid_pua_free/` | `pdf-cmap-fix` | gid, PUA patched |

See [README CLI by lookup tier](../../README.md#cli-by-lookup-tier) for flag details.

## Example PDFs

| Folder | Producer | Pages | Typical fonts | CLI-RUNS doc |
|--------|----------|-------|---------------|--------------|
| [sample/](sample/) | Mixed | — | Jomolhari, Cambria | [CLI-RUNS.md](sample/CLI-RUNS.md) |
| [TI1461-01-001/](TI1461-01-001/) | InDesign | 1 | Qomolangma, Monlam | [CLI-RUNS.md](TI1461-01-001/CLI-RUNS.md) |
| [TI1763-01-002/](TI1763-01-002/) | MS Word | 1 | Monlam Uni OuChan 2 | [CLI-RUNS.md](TI1763-01-002/CLI-RUNS.md) |
| [TI803-01-001/](TI803-01-001/) | MS Word | 398 | Microsoft Himalaya | [CLI-RUNS.md](TI803-01-001/CLI-RUNS.md) |
| [TI1055-01-001/](TI1055-01-001/) | MS Word | 528 | Monlam Uni OuChan | [CLI-RUNS.md](TI1055-01-001/CLI-RUNS.md) |
| [TI1751-01-001/](TI1751-01-001/) | InDesign | 528 | Monlam, Himalaya | [CLI-RUNS.md](TI1751-01-001/CLI-RUNS.md) |

**Runtime:** TI1055 and TI1751 are 528 pages; a full 6-tier matrix can take a long time per PDF.

## Output layout

```text
docs/examples/<example-id>/
  <example-id>.pdf
  CLI-RUNS.md              # commands and results table for this PDF
  cli-results/
    gid/
      console.txt
      <stem>.gid.raw.txt
      <stem>.gid.patched.txt
      <stem>.gid.diff.txt
    gname/
    gname_pua_free/
    gshape/
    gshape_pua_free/
    gid_pua_free/
```

Each example folder contains only the **PDF**, **CLI-RUNS.md**, and **cli-results/**. All tier text outputs live under `cli-results/<tier>/`.

**Repo size:** TI803, TI1055, and TI1751 store `console.txt` and `*.diff.txt` under `cli-results/` in git (not tier-prefixed `*.raw.txt` / `*.patched.txt`, which are multi‑MB per tier). Re-run the harness locally to regenerate full text extracts for those PDFs.

## Re-run all examples

From the repository root (after `pip install -e ".[dev]"`):

```powershell
$env:PYTHONUTF8 = "1"
.\scripts\docs\run_examples_all_tiers.ps1
```

Partial re-run:

```powershell
.\scripts\docs\run_examples_all_tiers.ps1 -Examples sample,TI1461-01-001
.\scripts\docs\run_examples_all_tiers.ps1 -OnlyTiers gid,gshape_pua_free
```

Master log: [cli-run.log](cli-run.log).

## What to look for

- **gid / gid_pua_free:** Best default for Type0 PDFs when GIDs match the bundled maps.
- **gname:** Works when PDF fonts expose real PostScript glyph names; often **no match** when names are synthetic (`glyph00001`, …).
- **gshape / gshape_pua_free:** Matches by outline shape; useful when gid keys differ but the same font file was indexed.

Compare `*.diff.txt` under each tier to see where patched extraction improves on raw text.
