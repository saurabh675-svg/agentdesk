# Install the four native toolchains AgentDesk uses, side by side, into
# .toolchains/ inside the repository (no admin rights, no global state).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-setup.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-setup.ps1 -Toolchains rust,cpp,dotnet
#
# After it finishes, scripts/dev-env.ps1 sets the environment for a shell:
#
#   . scripts/dev-env.ps1
#
param(
  [string[]]$Toolchains = @("rust", "cpp", "dotnet"),
  [string]$Root = (Split-Path $PSScriptRoot -Parent)
)

$ErrorActionPreference = 'Stop'
$rootPath = Join-Path $Root '.toolchains'
New-Item -ItemType Directory -Force -Path $rootPath | Out-Null

function Install-Rust {
  Write-Host "==> Rust (GNU host, pairs with the llvm-mingw C++ toolchain)"
  $cargoHome = Join-Path $rootPath 'cargo'
  $rustupHome = Join-Path $rootPath 'rustup'
  $installer = Join-Path $rootPath 'rustup-init.exe'
  if (-not (Test-Path $installer)) {
    Invoke-WebRequest -Uri 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-gnu/rustup-init.exe' -OutFile $installer
  }
  $env:CARGO_HOME = $cargoHome
  $env:RUSTUP_HOME = $rustupHome
  & $installer -y --default-host x86_64-pc-windows-gnu --default-toolchain stable --profile minimal --no-modify-path
  Write-Host "   cargo: $(Join-Path $cargoHome 'bin\cargo.exe')"
}

function Install-Cpp {
  Write-Host "==> clang/llvm-mingw (C and C++ compiler)"
  $installDir = Join-Path $rootPath 'llvmmingw'
  if (Test-Path $installDir) { Write-Host "   already present"; return }
  $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/mstorsjo/llvm-mingw/releases/latest'
  $asset = $release.assets | Where-Object { $_.name -like '*ucrt-x86_64.zip' } | Select-Object -First 1
  if (-not $asset) { throw "no llvm-mingw ucrt x86_64 asset found" }
  $zip = Join-Path $rootPath 'llvm-mingw.zip'
  Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath $installDir -Force
  Write-Host "   clang: $(Get-ChildItem $installDir -Recurse -Filter clang++.exe | Select-Object -First 1 -ExpandProperty FullName)"
}

function Install-Dotnet {
  Write-Host "==> .NET 9 SDK (Windows sidecar)"
  $dotnetDir = Join-Path $rootPath 'dotnet'
  if (Test-Path (Join-Path $dotnetDir 'dotnet.exe')) { Write-Host "   already present"; return }
  $script = Join-Path $rootPath 'dotnet-install.ps1'
  if (-not (Test-Path $script)) {
    Invoke-WebRequest -Uri 'https://dot.net/v1/dotnet-install.ps1' -OutFile $script
  }
  & $script -Channel 9.0 -InstallDir $dotnetDir
  Write-Host "   dotnet: $(Join-Path $dotnetDir 'dotnet.exe')"
}

foreach ($tool in $Toolchains) {
  switch ($tool.ToLower()) {
    'rust' { Install-Rust }
    'cpp' { Install-Cpp }
    'dotnet' { Install-Dotnet }
    default { Write-Warning "unknown toolchain: $tool" }
  }
}

Write-Host ""
Write-Host "Toolchains ready under $rootPath"
Write-Host "Run '. scripts/dev-env.ps1' in a shell before building the native parts."
