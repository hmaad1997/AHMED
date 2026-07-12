$ErrorActionPreference = 'Stop'
$exe = "dist\QuranReciterID.exe"
if (!(Test-Path $exe)) { throw "EXE not built at $exe" }
$proc = Start-Process -FilePath $exe -PassThru -WindowStyle Hidden
Write-Host "Launched PID=$($proc.Id); polling /health..."
$ok = $false
for ($i=0; $i -lt 60; $i++) {
  Start-Sleep -Seconds 5
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 4 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ok = $true; Write-Host "OK after $($i*5)s: $($r.Content)"; break }
  } catch { Write-Host "  [$($i*5)s] not ready yet..." }
}
try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
Get-Process | Where-Object { $_.ProcessName -like "QuranReciter*" } | Stop-Process -Force -ErrorAction SilentlyContinue
if (-not $ok) { throw "EXE did not respond on /health within 300s" }
