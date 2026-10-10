# Upload an NDJSON file to a running stack and wait for its ingest report:
#   scripts/upload.ps1 FILE
# Logs in as the demo user (DEMO_USER_EMAIL / DEMO_USER_PASSWORD) through the frontend proxy,
# POSTs the file to /api/ingest/files, polls /api/ingest/jobs/{id} every second until the job is
# done or failed and prints the report with the upload and processing times.
# Exit code: 0 - job done; 1 - job failed, timed out or the API refused; 2 - usage.
# Windows PowerShell 5.1 has no multipart upload, so the requests go through curl.exe
# (shipped with Windows 10 and later).
param(
    [Parameter(Position = 0)][string]$File,
    [string]$BaseUrl = "http://localhost:$(if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { 5173 })",
    [string]$DemoEmail = $(if ($env:DEMO_USER_EMAIL) { $env:DEMO_USER_EMAIL } else { "demo@example.com" }),
    [string]$DemoPassword = $(if ($env:DEMO_USER_PASSWORD) { $env:DEMO_USER_PASSWORD } else { "demo12345" }),
    [int]$TimeoutSec = 1800
)

if (-not $File -or -not (Test-Path -LiteralPath $File -PathType Leaf)) {
    Write-Host "usage: scripts/upload.ps1 FILE   (an existing NDJSON file)"
    exit 2
}
$path = (Resolve-Path -LiteralPath $File).Path
$jar = [System.IO.Path]::GetTempFileName()
$loginBody = [System.IO.Path]::GetTempFileName()

try {
    # The JSON goes through a file: PowerShell 5.1 mangles double quotes in native arguments.
    $login = @{ email = $DemoEmail; password = $DemoPassword } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($loginBody, $login)
    $code = & curl.exe -s -o NUL -m 10 -w "%{http_code}" -c $jar -X POST "$BaseUrl/api/auth/login" `
        -H "Content-Type: application/json" -H "X-Requested-With: ht" --data-binary "@$loginBody"
    if ($code -ne "200") {
        Write-Host "FAIL login $BaseUrl ($DemoEmail) -> HTTP $code"
        exit 1
    }

    $size = (Get-Item -LiteralPath $path).Length
    Write-Host "Uploading $path ($size bytes) to $BaseUrl ..."
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    $response = & curl.exe -s -b $jar -H "X-Requested-With: ht" `
        -F "file=@$path;type=application/x-ndjson" -w "`n%{http_code}" "$BaseUrl/api/ingest/files"
    $lines = @($response)
    $code = $lines[-1]
    $body = ($lines[0..($lines.Count - 2)] -join "`n")
    if ($code -ne "202") {
        Write-Host "FAIL upload -> HTTP $code $body"
        exit 1
    }
    $jobId = ($body | ConvertFrom-Json).job_id
    $uploadSec = [int]$clock.Elapsed.TotalSeconds
    Write-Host "Uploaded in $uploadSec s, job $jobId"

    $job = $null
    $processing = [System.Diagnostics.Stopwatch]::StartNew()
    while ($processing.Elapsed.TotalSeconds -lt $TimeoutSec) {
        $raw = & curl.exe -s -m 10 -b $jar "$BaseUrl/api/ingest/jobs/$jobId"
        $job = ($raw -join "`n") | ConvertFrom-Json
        Write-Host "  status=$($job.status) progress=$($job.progress)"
        if ($job.status -eq "done" -or $job.status -eq "failed") { break }
        Start-Sleep -Seconds 1
    }

    Write-Host "Report:"
    $job | Select-Object id, filename, status, bytes_total, bytes_done, created_at, started_at, finished_at |
        Format-List | Out-String | Write-Host
    $job.counts | Format-Table total, new, duplicate, conflict, invalid | Out-String | Write-Host
    if ($job.errors) {
        Write-Host "Errors (first $(@($job.errors).Count)):"
        $job.errors | Format-Table line, kind, reason -AutoSize | Out-String -Width 200 | Write-Host
    }
    foreach ($warning in @($job.warnings)) { if ($warning) { Write-Host "Warning: $warning" } }
    Write-Host "Processing took $([int]$processing.Elapsed.TotalSeconds) s, total $([int]$clock.Elapsed.TotalSeconds) s"
    if ($job.status -eq "done") {
        Write-Host "OK   job $jobId done"
        exit 0
    }
    Write-Host "FAIL job $jobId status=$($job.status)"
    exit 1
} finally {
    Remove-Item -LiteralPath $jar, $loginBody -ErrorAction SilentlyContinue
}
