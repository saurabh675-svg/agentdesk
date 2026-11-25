# Copy the current repo build into an installed AgentDesk (needs elevation when
# the install lives under Program Files).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy-install.ps1
#
# Environment overrides:
#   AGENTDESK_INSTALL_DIR  default: C:\Program Files\AgentDesk
#   AGENTDESK_REPO_DIR     default: the repository root
param(
  [string]$InstallDir = $(if ($env:AGENTDESK_INSTALL_DIR) { $env:AGENTDESK_INSTALL_DIR } else { "C:\Program Files\AgentDesk" }),
  [string]$RepoDir = $(if ($env:AGENTDESK_REPO_DIR) { $env:AGENTDESK_REPO_DIR } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }),
  [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$resources = Join-Path $InstallDir 'resources'
if (-not (Test-Path $resources)) { throw "Install dir not found: $resources" }

# --- backend ---------------------------------------------------------------
$backendSrc = Join-Path $RepoDir 'backend\app'
$backendDst = Join-Path $resources 'backend\app'
Copy-Item (Join-Path $backendSrc '*.py') $backendDst -Force
Copy-Item (Join-Path $backendSrc 'routes\*.py') (Join-Path $backendDst 'routes') -Force
Copy-Item (Join-Path $backendSrc 'tools\*.py') (Join-Path $backendDst 'tools') -Force
Copy-Item (Join-Path $backendSrc 'engine\*.py') (Join-Path $backendDst 'engine') -Force
'backend synced'

# --- frontend --------------------------------------------------------------
if (-not $SkipFrontend) {
  $uiSrc = Join-Path $RepoDir 'frontend\dist'
  $uiDst = Join-Path $resources 'app\frontend\dist'
  if (Test-Path $uiSrc) {
    Get-ChildItem (Join-Path $uiDst 'assets') -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Copy-Item (Join-Path $uiSrc '*') $uiDst -Recurse -Force
    'frontend synced'
  } else {
    'frontend dist missing - run npm run build:ui first'
  }
}

# --- docs / sdk ------------------------------------------------------------
foreach ($pair in @(
  @('docs\openapi.json', 'docs\openapi.json'),
  @('sdk-ts\generated', 'sdk-ts\generated'),
  @('sdk-py\generated', 'sdk-py\generated'),
  @('examples\browser', 'examples\browser')
)) {
  $src = Join-Path $RepoDir $pair[0]
  $dst = Join-Path $resources $pair[1]
  if (Test-Path $src) {
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item $src $dst -Recurse -Force
  }
}
'docs + sdks synced'
'DEPLOY_OK'
