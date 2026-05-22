# Run all six tier CLIs on every docs/examples/*.pdf using pdf_cmap_fix/data/font_lookup* trees.
# Outputs: docs/examples/<example>/cli-results/<tier>/
# Log: docs/examples/cli-run.log
#
# Usage (from repo root):
#   .\scripts\docs\run_examples_all_tiers.ps1
#   .\scripts\docs\run_examples_all_tiers.ps1 -Examples sample,TI1461-01-001
#   .\scripts\docs\run_examples_all_tiers.ps1 -OnlyTiers gid,gshape -GenerateDocs

param(
    [string[]]$Examples = @(),
    [string[]]$OnlyTiers = @(),
    [switch]$GenerateDocs,
    [switch]$SkipRun
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
chcp 65001 | Out-Null

$REPO = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$EXAMPLES_ROOT = Join-Path $REPO "docs\examples"
$DATA = Join-Path $REPO "pdf_cmap_fix\data"
$LOG_PATH = Join-Path $EXAMPLES_ROOT "cli-run.log"

$tiersAll = @(
    @{ Name = "gid";             Cli = "pdf-cmap-fix";        LookupSub = "font_lookup" }
    @{ Name = "gname";           Cli = "pdf-cmap-fix-gname";  LookupSub = "font_lookup_gname" }
    @{ Name = "gname_pua_free";  Cli = "pdf-cmap-fix-gname";  LookupSub = "font_lookup_gname_pua_free" }
    @{ Name = "gshape";          Cli = "pdf-cmap-fix-gshape"; LookupSub = "font_lookup_gshape" }
    @{ Name = "gshape_pua_free"; Cli = "pdf-cmap-fix-gshape"; LookupSub = "font_lookup_gshape_pua_free" }
    @{ Name = "gid_pua_free";    Cli = "pdf-cmap-fix";        LookupSub = "font_lookup_gid_pua_free" }
)

$exampleMeta = @{
    "sample"         = @{ Desc = "Mixed; Jomolhari + Cambria"; Pages = "varies" }
    "TI1055-01-001"  = @{ Desc = "MS Word; Monlam Uni OuChan"; Pages = "528" }
    "TI1751-01-001"  = @{ Desc = "InDesign; Monlam / Himalaya"; Pages = "528" }
    "TI803-01-001"   = @{ Desc = "MS Word; Microsoft Himalaya"; Pages = "398" }
    "TI1461-01-001"  = @{ Desc = "InDesign; Qomolangma + Monlam"; Pages = "1" }
    "TI1763-01-002"  = @{ Desc = "MS Word; Monlam Uni OuChan 2"; Pages = "1" }
}

$cliModules = @{
    "pdf-cmap-fix"        = "pdf_cmap_fix.gid.extractor"
    "pdf-cmap-fix-gname"  = "pdf_cmap_fix.gname.extractor"
    "pdf-cmap-fix-gshape" = "pdf_cmap_fix.gshape.extractor"
}

function Resolve-CliExe {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Invoke-TierCli {
    param(
        [string]$CliName,
        [string]$LookupDir,
        [string]$PdfPath
    )
    $exe = Resolve-CliExe $CliName
    if ($exe) {
        $out = & $exe --font-lookup-dir $LookupDir $PdfPath 2>&1
        return @{ Output = $out; Exit = $LASTEXITCODE }
    }
    $mod = $cliModules[$CliName]
    if (-not $mod) {
        throw "Unknown CLI: $CliName"
    }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        throw "Neither $CliName nor python on PATH. From repo root: pip install -e ."
    }
    $out = & $py.Source -m $mod --font-lookup-dir $LookupDir $PdfPath 2>&1
    return @{ Output = $out; Exit = $LASTEXITCODE }
}

function Parse-ConsoleStats {
    param([string]$Text)
    $stats = @{
        Exit = 0
        Match = "?"
        Upgrades = "?"
        DiffLines = "?"
        MatchedFonts = @()
        NoMatchFonts = @()
    }
    if (-not $Text) { return $stats }
    if ($Text -match '\[matched\]\s+([^\r\n]+)') {
        $stats.MatchedFonts = [regex]::Matches($Text, '\[matched\]\s+([^\r\n]+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
        $stats.Match = "MATCH"
    }
    if ($Text -match '\[no DB match\]\s+([^\r\n]+)') {
        $stats.NoMatchFonts = [regex]::Matches($Text, '\[no DB match\]\s+([^\r\n]+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
        if ($stats.Match -eq "?") { $stats.Match = "no-match" }
    }
    if ($Text -match 'patched:\s+\d+\s+\((\d+) GID upgrades\)') { $stats.Upgrades = $Matches[1] }
    if ($Text -match 'Lines changed:\s+(\d+)') { $stats.DiffLines = $Matches[1] }
    return $stats
}

function Write-CliRunsMarkdown {
    param([string]$ExampleId, [hashtable]$RunsForExample)

    $meta = $exampleMeta[$ExampleId]
    if (-not $meta) { $meta = @{ Desc = "Example PDF"; Pages = "?" } }

    $pdfPath = "docs/examples/$ExampleId/$ExampleId.pdf"
    if ($ExampleId -eq "sample") { $pdfPath = "docs/examples/sample/sample.pdf" }

    $lines = @(
        "# CLI runs: $ExampleId",
        "",
        "**PDF:** ``$pdfPath``",
        "",
        "**About:** $($meta.Desc) ($($meta.Pages) pages)",
        "",
        "Each row is one lookup tier from ``pdf_cmap_fix/data/``. Text outputs live under ``cli-results/<tier>/``.",
        "",
        "Re-run from repo root:",
        "",
        '```powershell',
        '$env:PYTHONUTF8 = "1"',
        ".\scripts\docs\run_examples_all_tiers.ps1 -Examples $ExampleId",
        '```',
        "",
        "## Results by tier",
        "",
        "| Tier | Lookup directory | CLI | Match | GID upgrades | Diff lines | Outputs |",
        "|------|------------------|-----|-------|--------------|------------|---------|"
    )

    foreach ($t in $tiersAll) {
        $key = $t.Name
        if (-not $RunsForExample.ContainsKey($key)) { continue }
        $r = $RunsForExample[$key]
        $lookupRel = "pdf_cmap_fix/data/$($t.LookupSub)"
        $outDir = "cli-results/$key"
        $stem = if ($ExampleId -eq "sample") { "sample" } else { $ExampleId }
        $outLink = "$outDir/${stem}.$key.diff.txt"
        $lines += "| **$key** | ``$lookupRel/`` | ``$($t.Cli)`` | $($r.Match) | $($r.Upgrades) | $($r.DiffLines) | [$outDir]($outDir/) |"
    }

    $lines += @(
        "",
        "## Example commands (extract text)",
        ""
    )

    foreach ($t in $tiersAll) {
        $lookupRel = "pdf_cmap_fix/data/$($t.LookupSub)"
        $lines += @(
            "### $($t.Name)",
            "",
            '```powershell',
            "$($t.Cli) --font-lookup-dir $lookupRel $pdfPath",
            '```',
            "",
            "Outputs copied to ``docs/examples/$ExampleId/cli-results/$($t.Name)/``.",
            ""
        )
    }

    $lines += @(
        "## Patch PDF (optional, not run by default)",
        "",
        '```powershell',
        "pdf-cmap-fix --font-lookup-dir pdf_cmap_fix/data/font_lookup $pdfPath -p",
        '```',
        ""
    )

    $outPath = Join-Path (Join-Path $EXAMPLES_ROOT $ExampleId) "CLI-RUNS.md"
    $lines | Set-Content -Path $outPath -Encoding utf8
    Write-Host "Wrote $outPath"
}

# Discover PDFs
$pdfs = Get-ChildItem -Path $EXAMPLES_ROOT -Directory | ForEach-Object {
    $pdf = Get-ChildItem -Path $_.FullName -Filter "*.pdf" -File | Where-Object { $_.Name -notmatch '\.patched\.' } | Select-Object -First 1
    if ($pdf) {
        [pscustomobject]@{ Id = $_.Name; Path = $pdf.FullName }
    }
} | Sort-Object Id

if ($Examples.Count -gt 0) {
    $pdfs = $pdfs | Where-Object { $Examples -contains $_.Id }
}

$tierList = $tiersAll
if ($OnlyTiers.Count -gt 0) {
    $tierList = $tiersAll | Where-Object { $OnlyTiers -contains $_.Name }
}

$runLog = @()
if (-not $SkipRun) {
    $hdr = "# Examples CLI matrix $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    if ($Examples.Count -eq 0) {
        $hdr | Set-Content $LOG_PATH -Encoding utf8
    } elseif (Test-Path $LOG_PATH) {
        Add-Content $LOG_PATH -Value "" -Encoding utf8
        Add-Content $LOG_PATH -Value $hdr -Encoding utf8
    } else {
        $hdr | Set-Content $LOG_PATH -Encoding utf8
    }
}

Set-Location $REPO

# Collect stats for doc generation: exampleId -> tierName -> stats
$allStats = @{}

foreach ($ex in $pdfs) {
    $allStats[$ex.Id] = @{}
    $cliResultsRoot = Join-Path (Join-Path $EXAMPLES_ROOT $ex.Id) "cli-results"
    New-Item -ItemType Directory -Force -Path $cliResultsRoot | Out-Null

    foreach ($tier in $tierList) {
        $lookupDir = Join-Path $DATA $tier.LookupSub
        if (-not (Test-Path $lookupDir)) {
            Write-Warning "Missing lookup dir: $lookupDir"
            continue
        }
        if (-not (Get-ChildItem $lookupDir -Filter "*.json" -ErrorAction SilentlyContinue | Select-Object -First 1)) {
            Write-Warning "No JSON in $lookupDir"
            continue
        }

        $tierOut = Join-Path $cliResultsRoot $tier.Name
        New-Item -ItemType Directory -Force -Path $tierOut | Out-Null

        $stem = [IO.Path]::GetFileNameWithoutExtension($ex.Path)
        $pdfDir = Split-Path $ex.Path -Parent
        $lookupArg = $lookupDir

        Write-Host "`n=== $($tier.Name) / $($ex.Id) / $stem ==="

        if ($SkipRun) {
            $consolePath = Join-Path $tierOut "console.txt"
            if (Test-Path $consolePath) {
                $console = Get-Content $consolePath -Raw
                $parsed = Parse-ConsoleStats $console
                $allStats[$ex.Id][$tier.Name] = $parsed
            }
            continue
        }

        $consolePath = Join-Path $tierOut "console.txt"
        try {
            $run = Invoke-TierCli -CliName $tier.Cli -LookupDir $lookupArg -PdfPath $ex.Path
        } catch {
            Write-Warning $_.Exception.Message
            continue
        }
        $run.Output | Tee-Object -FilePath $consolePath
        $exit = $run.Exit

        foreach ($ext in @("raw.txt", "patched.txt", "diff.txt")) {
            $src = Join-Path $pdfDir "$stem.$ext"
            if (Test-Path $src) {
                Copy-Item $src (Join-Path $tierOut "$stem.$($tier.Name).$ext") -Force
            }
        }

        $console = Get-Content $consolePath -Raw -ErrorAction SilentlyContinue
        $parsed = Parse-ConsoleStats $console
        $parsed.Exit = $exit
        $allStats[$ex.Id][$tier.Name] = $parsed

        $msg = "[{0}] {1}  exit={2}  match={3}  upgrades={4}  diff_lines={5}" -f `
            $tier.Name, $ex.Id, $exit, $parsed.Match, $parsed.Upgrades, $parsed.DiffLines
        Write-Host $msg
        Add-Content $LOG_PATH -Value $msg -Encoding utf8
        $runLog += $msg
    }
}

foreach ($id in $allStats.Keys) {
    Write-CliRunsMarkdown -ExampleId $id -RunsForExample $allStats[$id]
}

Write-Host "`nLog: $LOG_PATH"
Write-Host "Examples root: $EXAMPLES_ROOT"
