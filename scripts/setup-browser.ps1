# Optional stronger browser driver for AgentDesk.
#
# The default driver is Playwright + your real Chrome, which is what most
# sites trust. This script installs the optional undetected driver
# (patchright, Apache-2.0) for the sites that still show a human check.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup-browser.ps1
#
# It installs into the project's own environment, so no admin rights are
# needed and nothing outside the repo is touched.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $venv)) {
  Write-Host "Backend virtual environment not found: $venv" -ForegroundColor Red
  Write-Host "Create it first (uv venv backend\.venv) and install requirements." -ForegroundColor Yellow
  exit 1
}

Write-Host "Installing patchright (undetected Playwright) into the backend venv..." -ForegroundColor Cyan
& $venv -m pip install --upgrade patchright
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }

Write-Host "Downloading patchright's patched Chromium (only needed for the patchright driver)..." -ForegroundColor Cyan
& $venv -m patchright install chromium
if ($LASTEXITCODE -ne 0) { Write-Host "patchright install failed" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Done. Check what the app can use:" -ForegroundColor Green
Write-Host "  GET /api/browser/drivers"
Write-Host ""
Write-Host "To switch drivers, set browser_driver in Settings -> Browser"
Write-Host "(playwright = real Chrome, patchright = patched Chromium)."
