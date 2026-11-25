param([switch]$ReuseStaged)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$manifest = Get-Content package.json -Raw | ConvertFrom-Json
$root = (Get-Location).Path
$release = Join-Path $root "release-$($manifest.version)"
$setup = Join-Path $release "AgentDesk-Setup-$($manifest.version).exe"
if (Test-Path -LiteralPath $setup) { throw "Versioned installer already exists: $setup" }
if ($ReuseStaged) {
    if (-not (Test-Path -LiteralPath (Join-Path $release 'win-unpacked/AgentDesk.exe'))) {
        throw 'The staged AgentDesk executable is missing'
    }
} else {
    if (Test-Path -LiteralPath $release) { throw "Versioned output already exists: $release" }
    New-Item -Path $release -ItemType Directory | Out-Null
    $env:AGENTDESK_RELEASE_DIR = $release
    node scripts/build-installer.mjs --directory
    if ($LASTEXITCODE -ne 0) { throw 'Electron build failed' }
}

$compiler = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$bootstrap = Join-Path $release 'SetupBootstrap.exe'
& $compiler /nologo /target:winexe /platform:x64 "/out:$bootstrap" /reference:System.Windows.Forms.dll /reference:Microsoft.CSharp.dll (Join-Path $root "installer\SetupBootstrap.cs")
if ($LASTEXITCODE -ne 0) { throw 'Setup bootstrap compilation failed' }

$sevenZip = (Get-ChildItem -LiteralPath 'installer/build-cache/electron-builder' -Recurse -Filter 7za.exe -File | Select-Object -First 1).FullName
if (-not $sevenZip) { throw 'The staged 7-Zip extractor is missing' }
$archive = Join-Path $release 'AgentDesk-x64.7z'
Push-Location -LiteralPath (Join-Path $release 'win-unpacked')
try {
    & $sevenZip a -t7z -mx=1 -ms=off -mmt=4 -bsp0 $archive '.\*'
    if ($LASTEXITCODE -ne 0) { throw 'Archive creation failed' }
}
finally { Pop-Location }
& .\installer\runtime\python\python.exe scripts/assemble-setup.py $bootstrap $sevenZip $archive $setup
if ($LASTEXITCODE -ne 0) { throw 'Setup assembly failed' }
Get-FileHash -LiteralPath $setup -Algorithm SHA256 | ForEach-Object {
    "$($_.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($setup))"
} | Set-Content -LiteralPath (Join-Path $release 'SHA256SUMS.txt') -Encoding ascii

# ---- Optional code signing (requires a valid code-signing cert on this machine) ----
$signTool = Get-ChildItem -LiteralPath "$env:ProgramFiles (x86)\\Windows Kits\\10\\bin\\*" -Filter signtool.exe -Recurse -File | Select-Object -First 1
if ($signTool) {
    $certSubject = $env:AGENTDESK_CODESIGN_CERT
    if ($certSubject) {
        Write-Host "Signing installer with certificate: $certSubject"
        & $signTool sign /f $env:AGENTDESK_CODESIGN_CERT_FILE /p $env:AGENTDESK_CODESIGN_CERT_PWD /tr http://timestamp.digicert.com /td SHA256 /fd SHA256 $setup
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Code signing failed; installer is unsigned.' }
        & $signTool verify /pa $setup
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Signature verification failed.' }
    } else {
        Write-Host 'No AGENTDESK_CODESIGN_CERT env var set — skipping code signing. Installer will be unsigned (SmartScreen warning on fresh machines).'
    }
} else {
    Write-Host 'SignTool not found — skipping code signing.'
}

# ---- SBOM: list every file in the release with SHA-256 ----
$sbom = Join-Path $release 'SBOM.txt'
$sbomFiles = @()
Get-ChildItem -LiteralPath $release -Recurse -File | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    $relPath = $_.FullName.Substring($release.Length).TrimStart('\')
    $sbomFiles += "$($hash.Hash.ToLowerInvariant())  $relPath"
}
$sbomFiles | Set-Content -LiteralPath $sbom -Encoding ascii
Write-Host "SBOM written to $sbom"
Write-Host "Release complete: $setup"
