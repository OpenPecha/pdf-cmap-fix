# CLI runs: TI1751-01-001

**PDF:** `docs/examples/TI1751-01-001/TI1751-01-001.pdf`

**About:** InDesign; Monlam / Himalaya (528 pages)

Each row is one lookup tier from `pdf_cmap_fix/data/`. Text outputs live under `cli-results/<tier>/`.

Re-run from repo root:

```powershell
$env:PYTHONUTF8 = "1"
.\scripts\docs\run_examples_all_tiers.ps1 -Examples TI1751-01-001
```

## Results by tier

| Tier | Lookup directory | CLI | Match | GID upgrades | Diff lines | Outputs |
|------|------------------|-----|-------|--------------|------------|---------|
| **gid** | `pdf_cmap_fix/data/font_lookup/` | `pdf-cmap-fix` | MATCH | 5107240 | 2545 | [cli-results/gid](cli-results/gid/) |
| **gname** | `pdf_cmap_fix/data/font_lookup_gname/` | `pdf-cmap-fix-gname` | no-match | 0 | 0 | [cli-results/gname](cli-results/gname/) |
| **gname_pua_free** | `pdf_cmap_fix/data/font_lookup_gname_pua_free/` | `pdf-cmap-fix-gname` | no-match | 0 | 0 | [cli-results/gname_pua_free](cli-results/gname_pua_free/) |
| **gshape** | `pdf_cmap_fix/data/font_lookup_gshape/` | `pdf-cmap-fix-gshape` | MATCH | 5281881 | 2541 | [cli-results/gshape](cli-results/gshape/) |
| **gshape_pua_free** | `pdf_cmap_fix/data/font_lookup_gshape_pua_free/` | `pdf-cmap-fix-gshape` | MATCH | 5281877 | 2541 | [cli-results/gshape_pua_free](cli-results/gshape_pua_free/) |
| **gid_pua_free** | `pdf_cmap_fix/data/font_lookup_gid_pua_free/` | `pdf-cmap-fix` | MATCH | 5107240 | 2545 | [cli-results/gid_pua_free](cli-results/gid_pua_free/) |

## Example commands (extract text)

### gid

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup docs/examples/TI1751-01-001/TI1751-01-001.pdf
```

Outputs copied to `docs/examples/TI1751-01-001/cli-results/gid/`.

### gname

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname docs/examples/TI1751-01-001/TI1751-01-001.pdf
```

Outputs copied to `docs/examples/TI1751-01-001/cli-results/gname/`.

### gname_pua_free

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname_pua_free docs/examples/TI1751-01-001/TI1751-01-001.pdf
```

Outputs copied to `docs/examples/TI1751-01-001/cli-results/gname_pua_free/`.

### gshape

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape docs/examples/TI1751-01-001/TI1751-01-001.pdf
```

Outputs copied to `docs/examples/TI1751-01-001/cli-results/gshape/`.

### gshape_pua_free

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape_pua_free docs/examples/TI1751-01-001/TI1751-01-001.pdf
```

Outputs copied to `docs/examples/TI1751-01-001/cli-results/gshape_pua_free/`.

### gid_pua_free

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup_gid_pua_free docs/examples/TI1751-01-001/TI1751-01-001.pdf
```

Outputs copied to `docs/examples/TI1751-01-001/cli-results/gid_pua_free/`.

## Patch PDF (optional, not run by default)

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup docs/examples/TI1751-01-001/TI1751-01-001.pdf -p
```

