# Launch a single bot run. Used by the Scheduled Tasks created by install.ps1.
$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPy   = Join-Path $repoRoot "venv\Scripts\python.exe"

Set-Location $repoRoot
& $venvPy -m src.main 2>&1 | Tee-Object -FilePath (Join-Path $repoRoot "data\runs.log") -Append
