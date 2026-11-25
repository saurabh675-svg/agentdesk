# Put the repository-local toolchains on PATH for the current shell.
#
#   . scripts/dev-env.ps1
#
$root = Split-Path $PSScriptRoot -Parent
$toolchains = Join-Path $root '.toolchains'

$env:CARGO_HOME = Join-Path $toolchains 'cargo'
$env:RUSTUP_HOME = Join-Path $toolchains 'rustup'
$env:DOTNET_ROOT = Join-Path $toolchains 'dotnet'
$env:DOTNET_CLI_HOME = Join-Path $toolchains 'dotnet-home'
$env:NUGET_PACKAGES = Join-Path $toolchains 'nuget'
$env:APPDATA = Join-Path $toolchains 'appdata'
$env:TEMP = Join-Path $root '.tmp'
$env:TMP = $env:TEMP

$paths = @(
  (Join-Path $toolchains 'cargo\bin'),
  (Join-Path $toolchains 'dotnet'),
  (Join-Path $toolchains 'llvmmingw\llvm-mingw-20261117-ucrt-x86_64\bin')
)
foreach ($candidate in $paths) {
  if (Test-Path $candidate) {
    $env:PATH = "$candidate;$env:PATH"
  }
}
# Any llvm-mingw folder (the date suffix changes with releases).
$llvmmingw = Get-ChildItem (Join-Path $toolchains 'llvmmingw') -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
if ($llvmmingw) {
  $bin = Join-Path $llvmmingw.FullName 'bin'
  if (Test-Path $bin) { $env:PATH = "$bin;$env:PATH" }
}

Write-Host "toolchain env ready (cargo: $(Get-Command cargo -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1))"
