<#
  stop-zen.ps1 - stop the background bridge started by start-zen.ps1

  It reads bridge.pid and kills that process tree (bridge + opencode serve).
  If the pid file is missing, it falls back to finding oc_bridge.py processes
  that belong to this directory.
#>
param(
  [int]$Port = 8790
)

$ErrorActionPreference = "Continue"
$dir = $PSScriptRoot
$pidFile = Join-Path $dir "bridge.pid"
$stopped = $false

function Stop-Tree {
  param([int]$ProcessId)
  Write-Output "stopping pid $ProcessId (and child processes)"
  & taskkill /PID $ProcessId /T /F 2>$null | Out-Null
}

if (Test-Path -LiteralPath $pidFile) {
  $saved = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($saved -match "^\d+$") {
    $p = Get-Process -Id ([int]$saved) -ErrorAction SilentlyContinue
    if ($p) {
      Stop-Tree -ProcessId ([int]$saved)
      $stopped = $true
    }
  }
  Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

if (-not $stopped) {
  $needle = [regex]::Escape((Join-Path $dir "oc_bridge.py"))
  $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -and $_.CommandLine -match $needle
  }
  foreach ($proc in $procs) {
    Stop-Tree -ProcessId $proc.ProcessId
    $stopped = $true
  }
}

if (-not $stopped) {
  Write-Output "No bridge process found for this directory."
} else {
  Write-Output "Done."
}

Start-Sleep -Milliseconds 500
$listen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listen) {
  Write-Output "Warning: port $Port is still listening (pid $($listen.OwningProcess))."
  Write-Output "It may belong to another program; check before stopping it."
}
