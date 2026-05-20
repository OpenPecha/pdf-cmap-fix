# Windows: UTF-8 console + local Jomolhari / Cambria gshape PUA-free pipeline.
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $here)
Set-Location $root
python "$here\run_local_gshape_jomolhari_pipeline.py" @args
