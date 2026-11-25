# Self-signed code signing — free alternative to a paid cert.
# Usage (PowerShell, as Administrator not required for user store):
#   powershell -ExecutionPolicy Bypass -File scripts\sign-selfsigned.ps1
# Creates/uses CN=AgentDesk Local, signs release/*.exe, exports .cer.
$ErrorActionPreference = 'Stop'
$subject = 'CN=AgentDesk Local'
$cert = Get-ChildItem Cert:\CurrentUser\My |
  Where-Object { $_.Subject -eq $subject -and $_.HasPrivateKey } |
  Select-Object -First 1
if (-not $cert) {
  $cert = New-SelfSignedCertificate -Type Custom -Subject $subject `
    -KeyUsage DigitalSignature -FriendlyName 'AgentDesk Local' `
    -CertStoreLocation 'Cert:\CurrentUser\My' `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')
}
Write-Host "Cert thumbprint: $($cert.Thumbprint)"
$cerPath = Join-Path $PSScriptRoot '..\release\AgentDesk-Local.cer'
Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null
Write-Host "Exported public cert: $cerPath"
Write-Host "Users install it once: double-click the .cer -> Install -> Local Machine -> Trusted Root Certification Authorities"
$signtool = Get-Command signtool -ErrorAction SilentlyContinue
if (-not $signtool) {
  $kit = 'C:\Program Files (x86)\Windows Kits\10\bin'
  $signtool = Get-ChildItem $kit -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like '*\x64\*' } | Select-Object -First 1
}
if (-not $signtool) { Write-Warning 'signtool not found — install Windows SDK. Cert + .cer are ready.'; exit 0 }
$signtoolPath = if ($signtool -is [string]) { $signtool } else { $signtool.FullName }
$files = Get-ChildItem (Join-Path $PSScriptRoot '..\release\*.exe') -ErrorAction SilentlyContinue
foreach ($f in $files) {
  & $signtoolPath sign /fd SHA256 /a /s My /sha1 $cert.Thumbprint $f.FullName
  Write-Host "Signed $($f.Name)"
}
Write-Host 'Done. Run node scripts/checksums.mjs next.'
