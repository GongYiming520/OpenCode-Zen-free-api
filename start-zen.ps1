<#
  start-zen.ps1 - start the bridge in the background (Windows)

  Normal use: double-click start-zen.bat.

  Options:
    -Port 8790          HTTP port of the OpenAI-compatible endpoint
    -OcPort 4097        port used by the internal opencode serve
    -HomeDir DIR        opencode data directory (default: .opencode-home)
    -OpenCodeBin PATH   explicit opencode binary
    -FullPrompt         use opencode's full system prompt
#>
param(
  [int]$Port = 8790,
  [int]$OcPort = 4097,
  [string]$HomeDir = "",
  [string]$OpenCodeBin = "",
  [switch]$FullPrompt
)

$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$bridge = Join-Path $dir "oc_bridge.py"

function Test-Bridge {
  param([int]$P)
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$P/health" -TimeoutSec 2
    return [bool]$r.ok
  } catch {
    return $false
  }
}

if (Test-Bridge -P $Port) {
  Write-Output "The bridge is already running on port $Port."
  Write-Output "  Base URL : http://127.0.0.1:$Port/v1"
  Write-Output "  API Key  : any non-empty string"
  Write-Output "  Health   : http://127.0.0.1:$Port/health"
  exit 0
}

if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
  Write-Output "ERROR: port $Port is already in use by another program."
  Write-Output "Stop that program, or run start-zen.bat with a different -Port."
  exit 1
}

# ---------- Python ----------
$pyExe = $null
$pyArgs = @()
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) {
  $pyExe = $cmd.Source
} else {
  $cmd = Get-Command py -ErrorAction SilentlyContinue
  if ($cmd) {
    $pyExe = $cmd.Source
    $pyArgs = @("-3")
  }
}
if (-not $pyExe) {
  Write-Output "ERROR: Python 3 was not found."
  Write-Output "Install it from https://www.python.org/downloads/ and try again."
  exit 1
}
& $pyExe @pyArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
if ($LASTEXITCODE -ne 0) {
  Write-Output "ERROR: Python 3.8 or newer is required."
  & $pyExe @pyArgs --version
  exit 1
}

# ---------- opencode ----------
function Find-OpenCode {
  if ($OpenCodeBin -and (Test-Path -LiteralPath $OpenCodeBin)) { return $OpenCodeBin }
  if ($env:OPENCODE_BIN -and (Test-Path -LiteralPath $env:OPENCODE_BIN)) { return $env:OPENCODE_BIN }
  foreach ($name in @("opencode.exe", "opencode.cmd")) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
  }
  $c = Get-Command opencode -ErrorAction SilentlyContinue
  if ($c -and $c.Source -notmatch "\.ps1$") { return $c.Source }

  $prefix = $null
  try { $prefix = (& npm prefix -g 2>$null | Select-Object -First 1) } catch {}
  if ($prefix) {
    foreach ($p in @(
      (Join-Path $prefix "opencode.exe"),
      (Join-Path $prefix "opencode.cmd"),
      (Join-Path $prefix "node_modules\opencode-ai\bin\opencode.exe")
    )) {
      if (Test-Path -LiteralPath $p) { return $p }
    }
  }
  foreach ($p in @(
    (Join-Path $env:LOCALAPPDATA "opencode\bin\opencode.exe"),
    (Join-Path $env:USERPROFILE ".opencode\bin\opencode.exe"),
    (Join-Path $env:APPDATA "npm\opencode.cmd")
  )) {
    if ($p -and (Test-Path -LiteralPath $p)) { return $p }
  }
  return $null
}

$oc = Find-OpenCode
if (-not $oc) {
  Write-Output "opencode was not found. Installing it with npm ..."
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Output "ERROR: Node.js / npm was not found."
    Write-Output "Install Node.js 18+ from https://nodejs.org/ and try again."
    exit 1
  }
  & npm i -g opencode-ai
  if ($LASTEXITCODE -ne 0) {
    Write-Output "ERROR: 'npm i -g opencode-ai' failed."
    Write-Output "Install opencode manually from https://opencode.ai and pass -OpenCodeBin PATH."
    exit 1
  }
  $oc = Find-OpenCode
}
if (-not $oc) {
  Write-Output "ERROR: could not locate the opencode binary after installation."
  exit 1
}

# ---------- isolated data directory ----------
if (-not $HomeDir) {
  $HomeDir = Join-Path $dir ".opencode-home"
}
if (-not (Test-Path -LiteralPath $HomeDir)) {
  New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
}

$env:PYTHONUTF8 = "1"
$log = Join-Path $dir "bridge.log"
$errLog = Join-Path $dir "bridge-err.log"
$pidFile = Join-Path $dir "bridge.pid"

$argList = @(
  "-u", ('"{0}"' -f $bridge),
  "--port", "$Port",
  "--oc-port", "$OcPort",
  "--opencode-bin", ('"{0}"' -f $oc),
  "--home", ('"{0}"' -f $HomeDir)
)
if ($FullPrompt) { $argList += "--full-prompt" }

$proc = Start-Process -FilePath $pyExe -ArgumentList ($pyArgs + $argList) `
  -WorkingDirectory $dir -WindowStyle Hidden `
  -RedirectStandardOutput $log -RedirectStandardError $errLog -PassThru

$proc.Id | Out-File -FilePath $pidFile -Encoding ascii
Write-Output "bridge pid: $($proc.Id) (saved to bridge.pid)"

$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  if (Test-Bridge -P $Port) { $ok = $true; break }
  if ($proc.HasExited) { break }
  Start-Sleep -Seconds 1
}

if ($ok) {
  Write-Output ""
  Write-Output "============================================================"
  Write-Output " OpenCode Zen Bridge is running"
  Write-Output "   Base URL : http://127.0.0.1:$Port/v1"
  Write-Output "   API Key  : any non-empty string"
  Write-Output "   Model    : deepseek-v4.1-flash-free"
  Write-Output "   Health   : http://127.0.0.1:$Port/health"
  Write-Output "   Data dir : $HomeDir"
  Write-Output "   Stop     : double-click stop-zen.bat"
  Write-Output "============================================================"
} else {
  Write-Output "ERROR: the bridge did not become healthy."
  Write-Output "--- bridge.log ---"
  Get-Content -LiteralPath $log -Encoding utf8 -Tail 30 -ErrorAction SilentlyContinue
  Write-Output "--- bridge-err.log ---"
  Get-Content -LiteralPath $errLog -Encoding utf8 -Tail 30 -ErrorAction SilentlyContinue
  if (-not $proc.HasExited) {
    Write-Output "The process is still running (pid $($proc.Id)); check the logs above."
  }
  exit 1
}
