<#
.SYNOPSIS
  One-command startup for the BrandRank POC: backend (FastAPI/uvicorn) + frontend (Vite).

.DESCRIPTION
  Starts both servers as background jobs from a single terminal, waits for the
  backend health check to pass, then reports both URLs. Replaces the manual
  "open two terminals, activate venv, remember the right commands" dance.

.EXAMPLE
  # From anywhere:
  .\complete-codebase\scripts\start-dev.ps1

.EXAMPLE
  # Stop everything later:
  .\complete-codebase\scripts\start-dev.ps1 -Stop
#>
param(
  [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot   # complete-codebase/
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$jobNameBackend = 'brandrank-backend'
$jobNameFrontend = 'brandrank-frontend'

if ($Stop) {
  Write-Host 'Stopping backend/frontend jobs...' -ForegroundColor Cyan
  Get-Job -Name $jobNameBackend, $jobNameFrontend -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job
  Write-Host 'Stopped.' -ForegroundColor Green
  return
}

# Clean up any stale jobs from a previous run in this same PowerShell session.
Get-Job -Name $jobNameBackend, $jobNameFrontend -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue

$venvActivate = Join-Path $backendDir '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $venvActivate)) {
  throw "Backend virtual environment not found at $venvActivate. Run scripts\setup-env.ps1 first."
}

Write-Host 'Starting backend (uvicorn) as background job...' -ForegroundColor Cyan
Start-Job -Name $jobNameBackend -ScriptBlock {
  param($backendDir, $venvActivate)
  Set-Location $backendDir
  & $venvActivate
  python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
} -ArgumentList $backendDir, $venvActivate | Out-Null

Write-Host 'Waiting for backend health check...' -ForegroundColor Cyan
$healthy = $false
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 1
  try {
    $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 -ErrorAction Stop
    if ($resp) { $healthy = $true; break }
  } catch {
    # Backend still starting; keep polling.
  }
}

if (-not $healthy) {
  Write-Host 'Backend did not become healthy in time. Job output so far:' -ForegroundColor Red
  Receive-Job -Name $jobNameBackend | Out-Host
  throw 'Backend failed to start. See output above.'
}
Write-Host 'Backend healthy at http://127.0.0.1:8000 (docs: /docs)' -ForegroundColor Green

if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
  Write-Host 'Frontend dependencies not installed yet. Run scripts\setup-env.ps1 first.' -ForegroundColor Yellow
}

Write-Host 'Starting frontend (vite) as background job...' -ForegroundColor Cyan
Start-Job -Name $jobNameFrontend -ScriptBlock {
  param($frontendDir)
  Set-Location $frontendDir
  npm run dev
} -ArgumentList $frontendDir | Out-Null

Start-Sleep -Seconds 4
Write-Host ''
Write-Host '================================================================' -ForegroundColor Green
Write-Host ' Backend:  http://127.0.0.1:8000/docs   (Swagger UI)' -ForegroundColor Green
Write-Host ' Frontend: http://localhost:5173/' -ForegroundColor Green
Write-Host '================================================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Both servers are running as PowerShell background jobs in THIS session.' -ForegroundColor Cyan
Write-Host 'Useful commands:' -ForegroundColor Cyan
Write-Host '  Get-Job                          # see status'
Write-Host '  Receive-Job -Name brandrank-backend -Keep   # view backend log output'
Write-Host '  Receive-Job -Name brandrank-frontend -Keep  # view frontend log output'
Write-Host '  .\scripts\start-dev.ps1 -Stop     # stop both servers'
Write-Host ''
Write-Host 'NOTE: Closing this PowerShell window stops both jobs. Keep it open.' -ForegroundColor Yellow
