# CLI runs: TI1055-01-001

**PDF:** `docs/examples/TI1055-01-001/TI1055-01-001.pdf`

**About:** MS Word; Monlam Uni OuChan (528 pages)

Each row is one lookup tier from `pdf_cmap_fix/data/`. Text outputs live under `cli-results/<tier>/`.

Re-run from repo root:

```powershell
$env:PYTHONUTF8 = "1"
.\scripts\docs\run_examples_all_tiers.ps1 -Examples TI1055-01-001 -Clean -DumpCmap
```

## Results by tier

| Tier | Lookup directory | CLI | Match | GID upgrades | Diff lines | Outputs |
|------|------------------|-----|-------|--------------|------------|---------|
| **gid** | `pdf_cmap_fix/data/font_lookup/` | `pdf-cmap-fix` | MATCH | 103 | 10205 | [cli-results/gid](cli-results/gid/) |
| **gname** | `pdf_cmap_fix/data/font_lookup_gname/` | `pdf-cmap-fix-gname` | MATCH | 1 | 294 | [cli-results/gname](cli-results/gname/) |
| **gname_pua_free** | `pdf_cmap_fix/data/font_lookup_gname_pua_free/` | `pdf-cmap-fix-gname` | MATCH | 1 | 294 | [cli-results/gname_pua_free](cli-results/gname_pua_free/) |
| **gshape** | `pdf_cmap_fix/data/font_lookup_gshape/` | `pdf-cmap-fix-gshape` | MATCH | 15 | 3367 | [cli-results/gshape](cli-results/gshape/) |
| **gshape_pua_free** | `pdf_cmap_fix/data/font_lookup_gshape_pua_free/` | `pdf-cmap-fix-gshape` | MATCH | 15 | 3367 | [cli-results/gshape_pua_free](cli-results/gshape_pua_free/) |
| **gid_pua_free** | `pdf_cmap_fix/data/font_lookup_gid_pua_free/` | `pdf-cmap-fix` | MATCH | 103 | 10205 | [cli-results/gid_pua_free](cli-results/gid_pua_free/) |

## Example commands (extract text)

### gid

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

Outputs copied to `docs/examples/TI1055-01-001/cli-results/gid/`.

### gname

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

Outputs copied to `docs/examples/TI1055-01-001/cli-results/gname/`.

### gname_pua_free

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname_pua_free docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

Outputs copied to `docs/examples/TI1055-01-001/cli-results/gname_pua_free/`.

### gshape

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

Outputs copied to `docs/examples/TI1055-01-001/cli-results/gshape/`.

### gshape_pua_free

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape_pua_free docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

Outputs copied to `docs/examples/TI1055-01-001/cli-results/gshape_pua_free/`.

### gid_pua_free

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup_gid_pua_free docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

Outputs copied to `docs/examples/TI1055-01-001/cli-results/gid_pua_free/`.

## Cmap dump (dict JSON)

Generate the merged ToUnicode map as JSON (no PDF rewrite) for each tier:

### gid

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup --dump-cmap docs/examples/TI1055-01-001/cli-results/gid/TI1055-01-001.gid.cmap-dump.json docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

### gname

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname --dump-cmap docs/examples/TI1055-01-001/cli-results/gname/TI1055-01-001.gname.cmap-dump.json docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

### gname_pua_free

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname_pua_free --dump-cmap docs/examples/TI1055-01-001/cli-results/gname_pua_free/TI1055-01-001.gname_pua_free.cmap-dump.json docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

### gshape

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape --dump-cmap docs/examples/TI1055-01-001/cli-results/gshape/TI1055-01-001.gshape.cmap-dump.json docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

### gshape_pua_free

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape_pua_free --dump-cmap docs/examples/TI1055-01-001/cli-results/gshape_pua_free/TI1055-01-001.gshape_pua_free.cmap-dump.json docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

### gid_pua_free

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup_gid_pua_free --dump-cmap docs/examples/TI1055-01-001/cli-results/gid_pua_free/TI1055-01-001.gid_pua_free.cmap-dump.json docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

## Patch PDF (optional, not run by default)

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup docs/examples/TI1055-01-001/TI1055-01-001.pdf -p
```

