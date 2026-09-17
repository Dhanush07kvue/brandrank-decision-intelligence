<#
.SYNOPSIS
  Adds a new brand/date data drop and ingests it in one command.

.DESCRIPTION
  Copies a source folder (e.g. a OneDrive brand export folder) into
  data/input/, then triggers ingestion via the running backend API, polls
  progress, and prints a summary (files processed, rows parsed/rejected,
  quarantined files) plus current dataset-status and quality counts.

  Requires the backend to already be running (see start-dev.ps1).

  Brand/date are derived by the backend from folder and file names already
  present in the source data (see project-brain/01-ARCHITECTURE.md,
  "Brand detection" section) -- you do NOT need to edit .env per brand.

.PARAMETER SourcePath
  Path to a folder containing the new brand's raw CSV export (e.g. a
  OneDrive-synced "5Aug2026-tylenol" or "Aveeno_Visibilitymodule_30Jul2026"
  style folder). If omitted, ingestion runs against whatever is already in
  data/input/ without copying anything new.

.EXAMPLE
  .\complete-codebase\scripts\ingest-new-data.ps1 -SourcePath "C:\...\5Aug2026-tylenol"

.EXAMPLE
  # Just re-ingest whatever is already sitting in data/input/:
  .\complete-codebase\scripts\ingest-new-data.ps1
#>
param(
  [string]$SourcePath,
  [string]$ApiBase = 'http://127.0.0.1:8000/api'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot   # complete-codebase/
$inputDir = Join-Path $root 'data\input'

Write-Host 'Checking backend is reachable...' -ForegroundColor Cyan
try {
  Invoke-RestMethod -Uri "$ApiBase/health" -TimeoutSec 3 | Out-Null
} catch {
  throw "Backend is not reachable at $ApiBase. Start it first with scripts\start-dev.ps1."
}
Write-Host 'Backend is healthy.' -ForegroundColor Green

if ($SourcePath) {
  if (-not (Test-Path $SourcePath)) { throw "SourcePath not found: $SourcePath" }
  $destName = Split-Path -Leaf $SourcePath
  $destPath = Join-Path $inputDir $destName
  Write-Host "Copying '$SourcePath' -> '$destPath' ..." -ForegroundColor Cyan
  Copy-Item -Path $SourcePath -Destination $destPath -Recurse -Force
  Write-Host 'Copy complete.' -ForegroundColor Green
} else {
  Write-Host 'No -SourcePath given; ingesting whatever is already in data\input\.' -ForegroundColor Yellow
}

Write-Host 'Starting ingestion job...' -ForegroundColor Cyan
$job = Invoke-RestMethod -Method Post -Uri "$ApiBase/ingest/start" -Body '{}' -ContentType 'application/json'

do {
  Start-Sleep -Milliseconds 750
  $progress = Invoke-RestMethod -Uri "$ApiBase/ingest/progress/$($job.job_id)"
  $status = "{0}/{1} files ({2}%) - {3}" -f $progress.processed_files, $progress.total_files, $progress.percentage, $progress.stage
  Write-Progress -Activity 'Ingesting BrandRank data' -Status $status -PercentComplete $progress.percentage
} while ($progress.status -in @('QUEUED', 'RUNNING'))
Write-Progress -Activity 'Ingesting BrandRank data' -Completed

if ($progress.status -eq 'FAILED') {
  throw "Ingestion failed: $($progress.error)"
}

Write-Host ''
Write-Host '== Ingestion summary ==' -ForegroundColor Green
"{0} files, {1} parsed rows, {2} rejected rows, {3} quarantined files" -f `
  $progress.summary.physical_files, $progress.summary.parsed_rows, `
  $progress.summary.rejected_rows, $progress.summary.quarantined_files | Write-Host

Write-Host ''
Write-Host '== Dataset status (all brands ingested so far) ==' -ForegroundColor Green
Invoke-RestMethod "$ApiBase/dataset-status" | Format-List

Write-Host ''
Write-Host '== Quality snapshot ==' -ForegroundColor Green
Invoke-RestMethod "$ApiBase/quality" | Format-List

Write-Host ''
Write-Host '== Ingestion errors / quarantined files (first 10) ==' -ForegroundColor Green
$errors = Invoke-RestMethod "$ApiBase/ingestion-errors"
if ($errors.Count -eq 0) {
  Write-Host '  None.' -ForegroundColor Green
} else {
  $errors | Select-Object -First 10 | Format-Table -AutoSize
  Write-Host "  ($($errors.Count) total -- see /api/ingestion-errors for the full list)" -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Evaluating signals against latest data...' -ForegroundColor Cyan
Invoke-RestMethod -Method Post "$ApiBase/signals/evaluate" | Select-Object run_id, evaluated_signal_count | Format-List

Write-Host 'Done. Refresh the frontend (http://localhost:5173) to see updated data.' -ForegroundColor Green
