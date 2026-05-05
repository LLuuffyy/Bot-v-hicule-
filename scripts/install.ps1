# Bot-v-hicule installer for Windows.
# Run from PowerShell (admin recommended for the scheduled task step).
#
# What it does:
#   1. Creates a Python virtual environment in .\venv
#   2. Installs Python dependencies from requirements.txt
#   3. Installs the Playwright Chromium browser
#   4. Registers two daily Scheduled Tasks (07h30 and 19h30)
#
# After running this script:
#   - Copy .env.example to .env and fill in your Gmail credentials
#   - Run scripts\facebook_login.py once to authenticate Facebook
#   - Trigger a manual run with scripts\run.ps1 to verify everything works

$ErrorActionPreference = "Stop"

$repoRoot  = Split-Path -Parent $PSScriptRoot
$venvDir   = Join-Path $repoRoot "venv"
$venvPy    = Join-Path $venvDir "Scripts\python.exe"
$runScript = Join-Path $repoRoot "scripts\run.ps1"

Write-Host "==> Repo root: $repoRoot"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found in PATH. Install Python 3.11+ from https://www.python.org/downloads/ and tick 'Add Python to PATH'."
}

if (-not (Test-Path $venvDir)) {
    Write-Host "==> Creating virtual environment in $venvDir"
    python -m venv $venvDir
}

Write-Host "==> Upgrading pip"
& $venvPy -m pip install --upgrade pip

Write-Host "==> Installing requirements"
& $venvPy -m pip install -r (Join-Path $repoRoot "requirements.txt")

Write-Host "==> Installing Playwright Chromium browser"
& $venvPy -m playwright install chromium

Write-Host "==> Registering scheduled tasks"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runScript`"" `
    -WorkingDirectory $repoRoot

$morning = New-ScheduledTaskTrigger -Daily -At 7:30am
$evening = New-ScheduledTaskTrigger -Daily -At 7:30pm

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName "BotVehicule-Matin" `
    -Action $action -Trigger $morning -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName "BotVehicule-Soir" `
    -Action $action -Trigger $evening -Settings $settings -Force | Out-Null

Write-Host ""
Write-Host "==> Done."
Write-Host "Next steps:"
Write-Host "  1. Copy .env.example to .env and fill GMAIL_USER / GMAIL_APP_PASSWORD / NOTIFY_EMAIL"
Write-Host "  2. Run: $venvPy scripts\facebook_login.py    (one-time FB login)"
Write-Host "  3. Run: scripts\run.ps1                       (test the full pipeline)"
