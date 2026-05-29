# CLI runs: TI1763-01-002

**PDF:** `docs/examples/TI1763-01-002/TI1763-01-002.pdf`

**About:** MS Word; Monlam Uni OuChan 2 (1 pages)

Each row is one lookup tier from `pdf_cmap_fix/data/`. Text outputs live under `cli-results/<tier>/`.

Re-run from repo root:

```powershell
$env:PYTHONUTF8 = "1"
.\scripts\docs\run_examples_all_tiers.ps1 -Examples TI1763-01-002 -Clean -DumpCmap
```

## Results by tier

| Tier | Lookup directory | CLI | Match | GID upgrades | Diff lines | Outputs |
|------|------------------|-----|-------|--------------|------------|---------|
| **gid** | `pdf_cmap_fix/data/font_lookup/` | `pdf-cmap-fix` | MATCH | 44 | 17 | [cli-results/gid](cli-results/gid/) |
| **gname** | `pdf_cmap_fix/data/font_lookup_gname/` | `pdf-cmap-fix-gname` | MATCH | 2 | 1 | [cli-results/gname](cli-results/gname/) |
| **gname_pua_free** | `pdf_cmap_fix/data/font_lookup_gname_pua_free/` | `pdf-cmap-fix-gname` | MATCH | 2 | 1 | [cli-results/gname_pua_free](cli-results/gname_pua_free/) |
| **gshape** | `pdf_cmap_fix/data/font_lookup_gshape/` | `pdf-cmap-fix-gshape` | MATCH | 42 | 16 | [cli-results/gshape](cli-results/gshape/) |
| **gshape_pua_free** | `pdf_cmap_fix/data/font_lookup_gshape_pua_free/` | `pdf-cmap-fix-gshape` | MATCH | 42 | 16 | [cli-results/gshape_pua_free](cli-results/gshape_pua_free/) |
| **gid_pua_free** | `pdf_cmap_fix/data/font_lookup_gid_pua_free/` | `pdf-cmap-fix` | MATCH | 44 | 17 | [cli-results/gid_pua_free](cli-results/gid_pua_free/) |

## Example commands (extract text)

### gid

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

Outputs copied to `docs/examples/TI1763-01-002/cli-results/gid/`.

### gname

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

Outputs copied to `docs/examples/TI1763-01-002/cli-results/gname/`.

### gname_pua_free

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname_pua_free docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

Outputs copied to `docs/examples/TI1763-01-002/cli-results/gname_pua_free/`.

### gshape

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

Outputs copied to `docs/examples/TI1763-01-002/cli-results/gshape/`.

### gshape_pua_free

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape_pua_free docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

Outputs copied to `docs/examples/TI1763-01-002/cli-results/gshape_pua_free/`.

### gid_pua_free

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup_gid_pua_free docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

Outputs copied to `docs/examples/TI1763-01-002/cli-results/gid_pua_free/`.

## Cmap dump (dict JSON)

Generate the merged ToUnicode map as JSON (no PDF rewrite) for each tier:

### gid

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup --dump-cmap docs/examples/TI1763-01-002/cli-results/gid/TI1763-01-002.gid.cmap-dump.json docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

### gname

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname --dump-cmap docs/examples/TI1763-01-002/cli-results/gname/TI1763-01-002.gname.cmap-dump.json docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

### gname_pua_free

```powershell
pdf-cmap-fix-gname --font-lookup-dir pdf_cmap_fix/data/font_lookup_gname_pua_free --dump-cmap docs/examples/TI1763-01-002/cli-results/gname_pua_free/TI1763-01-002.gname_pua_free.cmap-dump.json docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

### gshape

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape --dump-cmap docs/examples/TI1763-01-002/cli-results/gshape/TI1763-01-002.gshape.cmap-dump.json docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

### gshape_pua_free

```powershell
pdf-cmap-fix-gshape --font-lookup-dir pdf_cmap_fix/data/font_lookup_gshape_pua_free --dump-cmap docs/examples/TI1763-01-002/cli-results/gshape_pua_free/TI1763-01-002.gshape_pua_free.cmap-dump.json docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

### gid_pua_free

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup_gid_pua_free --dump-cmap docs/examples/TI1763-01-002/cli-results/gid_pua_free/TI1763-01-002.gid_pua_free.cmap-dump.json docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

## Patch PDF (optional, not run by default)

```powershell
pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup docs/examples/TI1763-01-002/TI1763-01-002.pdf -p
```

