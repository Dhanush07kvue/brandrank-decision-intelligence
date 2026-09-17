param(
  [string]$ApiBase = 'http://127.0.0.1:8000/api'
)

$demoPassword = 'KENVUE-DEMO-2026'

Write-Host 'Checking backend...' -ForegroundColor Cyan
Invoke-RestMethod "$ApiBase/health" | Out-Host

Write-Host 'Seeding labelled DEMO_FIXTURE records...' -ForegroundColor Cyan
Invoke-RestMethod -Method Post "$ApiBase/seed-fixtures" | Out-Host

Write-Host 'Starting ingestion with demo override...' -ForegroundColor Cyan
$body = @{ override_existing = $true; password = $demoPassword } | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri "$ApiBase/ingest/start" -ContentType 'application/json' -Body $body

do {
  Start-Sleep -Milliseconds 500
  $progress = Invoke-RestMethod "$ApiBase/ingest/progress/$($job.job_id)"
  $status = "{0}/{1} files ({2}%) - {3}" -f $progress.processed_files, $progress.total_files, $progress.percentage, $progress.stage
  Write-Progress -Activity 'Kenvue data ingestion' -Status $status -PercentComplete $progress.percentage
} while ($progress.status -in @('QUEUED', 'RUNNING'))

if ($progress.status -eq 'FAILED') {
  Write-Progress -Activity 'Kenvue data ingestion' -Completed
  throw $progress.error
}

Write-Progress -Activity 'Kenvue data ingestion' -Completed
Write-Host ("Completed: {0} files, {1} parsed rows, {2} rejected rows, {3} quarantined files." -f $progress.summary.physical_files, $progress.summary.parsed_rows, $progress.summary.rejected_rows, $progress.summary.quarantined_files) -ForegroundColor Green

Write-Host 'Evaluating signals...' -ForegroundColor Cyan
Invoke-RestMethod -Method Post "$ApiBase/signals/evaluate" | Select-Object run_id, evaluated_signal_count | Format-List

Write-Host 'Dataset status:' -ForegroundColor Cyan
Invoke-RestMethod "$ApiBase/dataset-status" | Select-Object latest_run_id, physical_files_discovered, canonical_observations | Format-List
