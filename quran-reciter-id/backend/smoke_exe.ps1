$ErrorActionPreference = 'Stop'
$exe = "dist\QuranReciterID.exe"
if (!(Test-Path $exe)) { throw "EXE not built at $exe" }

$env:QRI_HEADLESS = '1'
Remove-Item Env:\QRI_SKIP_AI -ErrorAction SilentlyContinue
Remove-Item Env:\QRI_SKIP_DB -ErrorAction SilentlyContinue
$env:QRI_LOG_FILE = (Resolve-Path ".").Path + "\smoke_exe_backend.log"
if (Test-Path $env:QRI_LOG_FILE) { Remove-Item $env:QRI_LOG_FILE -Force }

$proc = Start-Process -FilePath $exe -PassThru -WindowStyle Hidden
Write-Host "Launched full headless EXE PID=$($proc.Id); polling /health until AI+DB are ready..."
$ok = $false
$last = ""
for ($i=0; $i -lt 450; $i++) {
  Start-Sleep -Seconds 2
  if ($proc.HasExited) {
    Write-Host "EXE exited early with code $($proc.ExitCode)"
    if (Test-Path $env:QRI_LOG_FILE) { Get-Content $env:QRI_LOG_FILE -Tail 300 }
    throw "EXE exited before AI/database became ready"
  }
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5 -UseBasicParsing
    if ($r.StatusCode -eq 200) {
      $h = $r.Content | ConvertFrom-Json
      $last = $r.Content
      Write-Host "  [$($i*2)s] ai=$($h.ai_status) db=$($h.db_status) builtin=$($h.builtin_reciters)"
      if ($h.ai_status -eq 'error') { throw "AI load error: $($h.ai_error)" }
      if ($h.db_status -eq 'error') { throw "DB load error: $($h.db_error)" }
      if ($h.ai_status -eq 'ready' -and $h.db_status -eq 'ready' -and [int]$h.builtin_reciters -ge 100) {
        $ok = $true
        Write-Host "FULL EXE OK after $($i*2)s: $($r.Content)"
        break
      }
    }
  } catch {
    Write-Host "  [$($i*2)s] not ready / error: $($_.Exception.Message)"
  }
}
try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
Get-Process | Where-Object { $_.ProcessName -like "QuranReciter*" } | Stop-Process -Force -ErrorAction SilentlyContinue
if (Test-Path $env:QRI_LOG_FILE) { Get-Content $env:QRI_LOG_FILE -Tail 300 }
if (-not $ok) { throw "EXE did not reach AI+DB ready within 900s. Last health: $last" }
