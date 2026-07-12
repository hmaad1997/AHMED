$ErrorActionPreference = 'Stop'
$exe = "dist\QuranReciterID.exe"
if (!(Test-Path $exe)) { throw "EXE not built at $exe" }

$env:QRI_HEADLESS = '1'
$env:QRI_SKIP_AI = '1'
$env:QRI_SKIP_DB = '1'
$env:QRI_LOG_FILE = (Resolve-Path ".").Path + "\smoke_exe_backend.log"

$proc = Start-Process -FilePath $exe -PassThru -WindowStyle Hidden
Write-Host "Launched headless PID=$($proc.Id); polling /health..."
$ok = $false
for ($i=0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 2
  if ($proc.HasExited) {
    Write-Host "EXE exited early with code $($proc.ExitCode)"
    if (Test-Path $env:QRI_LOG_FILE) { Get-Content $env:QRI_LOG_FILE -Tail 200 }
    throw "EXE exited before /health responded"
  }
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 4 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ok = $true; Write-Host "OK after $($i*2)s: $($r.Content)"; break }
  } catch { Write-Host "  [$($i*2)s] not ready yet..." }
}
try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
Get-Process | Where-Object { $_.ProcessName -like "QuranReciter*" } | Stop-Process -Force -ErrorAction SilentlyContinue
if (Test-Path $env:QRI_LOG_FILE) { Get-Content $env:QRI_LOG_FILE -Tail 200 }
if (-not $ok) { throw "EXE did not respond on /health within 180s" }
