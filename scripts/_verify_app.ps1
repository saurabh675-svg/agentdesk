$ErrorActionPreference = 'Stop'
$root = 'C:\Users\saura\agentdesk'
$installDir = 'C:\Users\saura\AppData\Local\Programs\AgentDesk'
$out = Join-Path $root 'installer\verify-final.txt'
Remove-Item $out -Force -ErrorAction SilentlyContinue
function Log($text) { $text | Out-File -FilePath $out -Encoding utf8 -Append }

try {
    $exe = Join-Path $installDir 'AgentDesk.exe'
    Log "exe exists: $(Test-Path $exe)"
    Log "product version: $((Get-Item $exe).VersionInfo.ProductVersion)"
    Log "file version: $((Get-Item $exe).VersionInfo.FileVersion)"
    Log "app dir: $(Test-Path (Join-Path $installDir 'resources\app\electron\main.js'))"
    Log "backend main: $(Test-Path (Join-Path $installDir 'resources\backend\app\main.py'))"
    Log "runtime python: $(Test-Path (Join-Path $installDir 'resources\runtime\python\python.exe'))"
    Log "model: $(Test-Path (Join-Path $installDir 'resources\runtime\models\qwen2.5-1.5b-instruct-q4_k_m.gguf'))"
    Log "desktop shortcut OneDrive: $(Test-Path 'C:\Users\saura\OneDrive\Desktop\AgentDesk.lnk')"
    Log "desktop shortcut legacy: $(Test-Path 'C:\Users\saura\Desktop\AgentDesk.lnk')"
    Log "start menu shortcut: $(Test-Path 'C:\Users\saura\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\AgentDesk.lnk')"
    Log "port 8756: $((Get-NetTCPConnection -LocalPort 8756 -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count)"
    Log "port 11435: $((Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count)"

    $token = $null
    $procs = Get-CimInstance Win32_Process -Filter "Name='AgentDesk.exe'" -ErrorAction SilentlyContinue
    foreach ($proc in $procs) {
        if ($proc.CommandLine -match '--agentdesk-api-token=([0-9a-f]{64})') {
            $token = $Matches[1]
            break
        }
    }
    Log "processes: $(($procs | Measure-Object).Count)"
    Log "token found: $([bool]$token)"
    if (-not $token) { throw 'No AgentDesk API token found in renderer process arguments' }

    $headers = @{ Authorization = "Bearer $token" }
    $base = 'http://127.0.0.1:8756'
    $health = Invoke-RestMethod -Uri "$base/api/health" -Headers $headers -TimeoutSec 15
    Log "health: $($health | ConvertTo-Json -Compress)"
    $settings = Invoke-RestMethod -Uri "$base/api/settings" -Headers $headers -TimeoutSec 15
    Log "settings gateway: $($settings.gateway); provider: $($settings.provider); keys: $((($settings.keys).PSObject.Properties.Name | Sort-Object) -join ',')"
    Log "settings local model: $($settings.local_model_path)"
    $sessions = Invoke-RestMethod -Uri "$base/api/sessions" -Headers $headers -TimeoutSec 15
    Log "sessions endpoint ok: $([bool]$sessions)"
    $automations = Invoke-RestMethod -Uri "$base/api/automations" -Headers $headers -TimeoutSec 15
    Log "automations endpoint ok: $($null -ne $automations)"
    $mcp = Invoke-RestMethod -Uri "$base/api/extensions/mcp/servers" -Headers $headers -TimeoutSec 30
    Log "mcp servers: $(($mcp | ForEach-Object { "$($_.id)=$($_.status)" }) -join '; ')"
    $earn = Invoke-RestMethod -Uri "$base/api/earnings/overview" -Headers $headers -TimeoutSec 30
    Log "earnings overview keys: $(($earn.PSObject.Properties.Name | Sort-Object) -join ',')"
    $sandbox = Invoke-RestMethod -Uri "$base/api/sandbox/session" -Headers $headers -TimeoutSec 15
    $sandboxRun = Invoke-RestMethod -Uri "$base/api/sandbox/run" -Method Post -Headers $headers -ContentType 'application/json' -Body (@{ sandbox_id = $sandbox.session_id; command = 'echo installed-sandbox-ok' } | ConvertTo-Json) -TimeoutSec 60
    Log "sandbox: exit=$($sandboxRun.exit_code) output=$($sandboxRun.output.Trim())"
    $ui = Get-Content (Join-Path $installDir 'resources\app\frontend\dist\index.html') -Raw
    Log "ui bundle: $($ui -replace '\s+', ' ')"
    Log 'VERIFY OK'
} catch {
    Log "VERIFY FAILED: $($_ | Out-String)"
}
