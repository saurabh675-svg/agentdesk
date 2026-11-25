<#
.SYNOPSIS
Recreates installer\runtime for the electron-builder installer.

.DESCRIPTION
The Setup.exe bundles a self-contained Python 3.11 runtime, Playwright Chromium,
and the tiny-brain GGUF model. That folder is intentionally excluded from the
handoff zip (~2.4 GB) because the exact same bytes are already inside Setup.exe.

This script rebuilds it from, in priority order:
  1. an installed AgentDesk (preferred - exact match), or
  2. the original source locations used on the build machine.

Run it from anywhere, then: npm run build:installer
#>
$ErrorActionPreference = "Stop"

$repo        = Split-Path -Parent $PSScriptRoot
$dest        = Join-Path $repo "installer\runtime"
$installed   = Join-Path $env:LOCALAPPDATA "Programs\AgentDesk\resources\runtime"
$sitePkgs    = Join-Path $repo "backend\.venv\Lib\site-packages"
$uvPython    = Join-Path $env:APPDATA "uv\python\cpython-3.11-windows-x86_64-none"
$playwright  = Join-Path $env:LOCALAPPDATA "ms-playwright"
$model       = Join-Path $HOME ".llama\qwen2.5-1.5b-instruct-q4_k_m.gguf"

function Copy-Tree([string]$from, [string]$to) {
  if (-not (Test-Path $from)) { throw "Missing source: $from" }
  New-Item -ItemType Directory -Force -Path $to | Out-Null
  robocopy $from $to /E /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $from" }
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null

# Prefer staging from the original source tree; fall back to the installed app if
# the source is missing (another machine building from an extracted zip).
$useInstalled = $false
if (-not (Test-Path (Join-Path $uvPython "python.exe")) -and (Test-Path (Join-Path $installed "python\python.exe"))) {
  $useInstalled = $true
}
if ($useInstalled) {
  Write-Host "Staging from installed runtime: $installed"
  foreach ($part in @("python", "playwright", "models")) {
    Copy-Tree (Join-Path $installed $part) (Join-Path $dest $part)
  }
}
else {
  Write-Host "Staging from source locations."
  Copy-Tree $uvPython (Join-Path $dest "python")
  Copy-Tree $sitePkgs (Join-Path $dest "python\Lib\site-packages")
  foreach ($p in @("chromium-1255", "chromium_headless_shell-1255", "ffmpeg-1013", "winldd-1007")) {
    Copy-Tree (Join-Path $playwright $p) (Join-Path $dest "playwright\$p")
  }
  if (-not (Test-Path $model)) { throw "Missing model: $model" }
  New-Item -ItemType Directory -Force -Path (Join-Path $dest "models") | Out-Null
  Copy-Item $model (Join-Path $dest "models\") -Force
}

$py = Join-Path $dest "python\python.exe"
& $py -c "import fastapi, uvicorn, playwright, llama_cpp; print('runtime ok')"
if ($LASTEXITCODE -ne 0) { throw "Staged runtime failed its import check." }
Write-Host "Runtime ready at $dest"
