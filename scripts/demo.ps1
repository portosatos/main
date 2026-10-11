# Demo of the app (SPEC §8 stage 13): starts the stack, generates a month of data for the demo user,
# uploads it and opens the dashboard and Mailpit in the browser.
#   scripts/demo.ps1 [-Reset] [-NoOpen] [-Days 30] [-Seed 42]
# -Reset first runs `docker compose down -v`: ALL data of the local stack (database, uploads, Mailpit)
# is deleted, the demo starts from scratch. -NoOpen does not open the browser.
# The file: htgen in the demo user's zone (`timezone` of /api/auth/me), -Days days up to yesterday,
# one whole day (six days ago) without any device — a hatched «нет данных» column on the dashboard —
# and three short nights at the end (`short-sleep`): R1 opens, and its digest comes to Mailpit after
# the digest window (DIGEST_WINDOW_MINUTES, 15 min by default; quiet hours move it).
# Needs Docker, uv and curl.exe; the demo user is DEMO_USER_EMAIL / DEMO_USER_PASSWORD.
param(
    [switch]$Reset,
    [switch]$NoOpen,
    [int]$Days = 30,
    [int]$Seed = 42
)

Set-Location (Split-Path $PSScriptRoot -Parent)
$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { 5173 }
$mailpitPort = if ($env:MAILPIT_UI_PORT) { $env:MAILPIT_UI_PORT } else { 8025 }
$baseUrl = "http://localhost:$frontendPort"
$mailpitUrl = "http://localhost:$mailpitPort"
$email = if ($env:DEMO_USER_EMAIL) { $env:DEMO_USER_EMAIL } else { "demo@example.com" }
$password = if ($env:DEMO_USER_PASSWORD) { $env:DEMO_USER_PASSWORD } else { "demo12345" }
$headers = @{ "X-Requested-With" = "ht" }

if ($Reset) {
    Write-Host "== docker compose down -v (all local data is deleted)"
    docker compose down -v
    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: docker compose down -v"; exit 1 }
}

Write-Host "== docker compose up -d --build --wait"
docker compose up -d --build --wait
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: the stack did not start"; exit 1 }

Write-Host "== demo user"
$web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
try {
    $login = @{ email = $email; password = $password } | ConvertTo-Json
    $null = Invoke-RestMethod -Uri "$baseUrl/api/auth/login" -Method Post -WebSession $web -Headers $headers `
        -ContentType "application/json" -Body $login -TimeoutSec 10
    # The file is made by real time: a shifted dev Clock would put it away from the user's today.
    $clock = Invoke-RestMethod -Uri "$baseUrl/api/dev/clock" -WebSession $web -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($clock -and $clock.offset_seconds -ne 0) {
        Write-Host "The dev Clock was shifted by $($clock.offset_seconds) s; resetting it to 0"
        $null = Invoke-RestMethod -Uri "$baseUrl/api/dev/clock" -Method Post -WebSession $web -Headers $headers `
            -ContentType "application/json" -Body '{"offset_seconds": 0}' -TimeoutSec 10
    }
    $me = Invoke-RestMethod -Uri "$baseUrl/api/auth/me" -WebSession $web -TimeoutSec 10
} catch {
    Write-Host "FAIL: demo login $baseUrl ($email) -> $($_.Exception.Message)"
    exit 1
}
$today = [datetime]::ParseExact($me.today, "yyyy-MM-dd", $null)
$gap = $today.AddDays(-6).ToString("yyyy-MM-dd")
$gapEnd = $today.AddDays(-5).ToString("yyyy-MM-dd")
$yesterday = $today.AddDays(-1).ToString("yyyy-MM-dd")
Write-Host "$email, zone $($me.timezone), today $($me.today)"

$dir = Join-Path ([System.IO.Path]::GetTempPath()) "ht-demo"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$file = Join-Path $dir "demo_d${Days}_s${Seed}_$($me.today).ndjson"
Write-Host "== htgen --tz $($me.timezone) --days $Days --gap ${gap}T00:00/${gapEnd}T00:00 --scenario short-sleep"
uv run --project generator htgen --tz $me.timezone --days $Days --seed $Seed `
    --gap "${gap}T00:00/${gapEnd}T00:00" --scenario short-sleep --out $file
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: htgen"; exit 1 }

Write-Host "== upload"
$env:DEMO_USER_EMAIL = $email
$env:DEMO_USER_PASSWORD = $password
& (Join-Path $PSScriptRoot "upload.ps1") $file -BaseUrl $baseUrl
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: upload"; exit 1 }
Remove-Item -LiteralPath $file -ErrorAction SilentlyContinue

$dashboard = "$baseUrl/?date=$yesterday"
Write-Host ""
Write-Host "Demo is ready:"
Write-Host "  app        $dashboard  (login $email / $password)"
Write-Host "  no data    $baseUrl/?date=$gap  (the day without any device)"
Write-Host "  week       $baseUrl/?view=week&date=$yesterday"
Write-Host "  R1         $baseUrl/recommendations  (three short nights)"
Write-Host "  mail       $mailpitUrl  (the R1 digest comes after the digest window, 15 min by default)"
if (-not $NoOpen) {
    Start-Process $dashboard
    Start-Process $mailpitUrl
}
Write-Host "OK: demo"
exit 0
