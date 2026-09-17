<#
.SYNOPSIS
  Checks and (re)installs everything the BrandRank POC needs to run locally.

.DESCRIPTION
  Verifies Node.js, Python, the backend virtual environment, backend/frontend
  dependencies, and reports whether PostgreSQL is reachable. Safe to re-run
  any time; it only installs what's missing.

.EXAMPLE
  .\complete-codebase\scripts\setup-env.ps1
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot   # complete-codebase/
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'

function Write-Check($label, $ok, $detail = '') {
  $mark = if ($ok) { '[OK]  ' } else { '[MISS]' }
  $color = if ($ok) { 'Green' } else { 'Red' }
  Write-Host "$mark $label $detail" -ForegroundColor $color
}

Write-Host '== 1. Node.js ==' -ForegroundColor Cyan
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
  $nodeVersion = (node -v)
  Write-Check 'Node.js found' $true "(version $nodeVersion, path: $($node.Source))"
} else {
  Write-Check 'Node.js found' $false
  Write-Host '  -> Install Node.js LTS from https://nodejs.org/ (or your company software portal), then re-open PowerShell.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '== 2. npm ==' -ForegroundColor Cyan
$npm = Get-Command npm -ErrorAction SilentlyContinue
Write-Check 'npm found' ([bool]$npm) $(if ($npm) { "(path: $($npm.Source))" } else { '' })

Write-Host ''
Write-Host '== 3. Python ==' -ForegroundColor Cyan
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  Write-Check 'Python found' $true "(version $(python --version), path: $($python.Source))"
} else {
  Write-Check 'Python found' $false
  Write-Host '  -> Install Python 3.11+ from https://python.org/ or your company software portal.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '== 4. Backend virtual environment ==' -ForegroundColor Cyan
$venvActivate = Join-Path $backendDir '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $venvActivate)) {
  Write-Check 'Backend .venv exists' $false
  if ($python) {
    Write-Host '  Creating virtual environment...' -ForegroundColor Yellow
    Push-Location $backendDir
    python -m venv .venv
    Pop-Location
    Write-Check 'Backend .venv created' $true
  }
} else {
  Write-Check 'Backend .venv exists' $true
}

Write-Host ''
Write-Host '== 5. Backend Python dependencies ==' -ForegroundColor Cyan
if (Test-Path $venvActivate) {
  Push-Location $backendDir
  & $venvActivate
  Write-Host '  Installing/verifying requirements.txt (only installs what is missing)...' -ForegroundColor Yellow
  pip install -q -r requirements.txt
  Pop-Location
  Write-Check 'Backend dependencies installed' $true
} else {
  Write-Check 'Backend dependencies installed' $false '(no venv to install into)'
}

Write-Host ''
Write-Host '== 6. Frontend npm dependencies ==' -ForegroundColor Cyan
if ($npm) {
  if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Write-Host '  Running npm install (first time only, may take a minute)...' -ForegroundColor Yellow
    Push-Location $frontendDir
    npm install
    Pop-Location
  }
  Write-Check 'Frontend node_modules present' (Test-Path (Join-Path $frontendDir 'node_modules'))
} else {
  Write-Check 'Frontend node_modules present' $false '(npm not available)'
}

Write-Host ''
Write-Host '== 7. .env file ==' -ForegroundColor Cyan
$envPath = Join-Path $root '.env'
if (Test-Path $envPath) {
  Write-Check '.env exists' $true
} else {
  Write-Check '.env exists' $false
  $examplePath = Join-Path $root '.env.example'
  if (Test-Path $examplePath) {
    Copy-Item $examplePath $envPath
    Write-Host '  -> Created .env from .env.example. Review it before running ingestion.' -ForegroundColor Yellow
  }
}

Write-Host ''
Write-Host '== 8. PostgreSQL reachability (optional; only needed for dual/postgres storage mode) ==' -ForegroundColor Cyan
$pgReachable = $false
try {
  $tcp = New-Object System.Net.Sockets.TcpClient
  $connectTask = $tcp.ConnectAsync('127.0.0.1', 5432)
  if ($connectTask.Wait(1500)) { $pgReachable = $true }
  $tcp.Close()
} catch { $pgReachable = $false }
Write-Check 'PostgreSQL listening on 127.0.0.1:5432' $pgReachable
if (-not $pgReachable) {
  Write-Host '  -> PostgreSQL is not required to run the app (default BAI_STORAGE_MODE=duckdb).' -ForegroundColor Yellow
  Write-Host '  -> See project-brain/04-KNOWN-BLOCKERS.md for Postgres setup options.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Setup check complete.' -ForegroundColor Green
Write-Host 'Next: .\complete-codebase\scripts\start-dev.ps1' -ForegroundColor Cyan
