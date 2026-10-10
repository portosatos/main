# Smoke check of a running stack (scripts/dev.ps1 or docker compose up):
# GET /api/health, the Mailpit UI, the frontend (nginx) and /api/health through the frontend
# proxy must answer 200. Waits up to -TimeoutSec for each.
param(
    [string]$ApiUrl = "http://localhost:$(if ($env:API_PORT) { $env:API_PORT } else { 8000 })",
    [string]$MailpitUrl = "http://localhost:$(if ($env:MAILPIT_UI_PORT) { $env:MAILPIT_UI_PORT } else { 8025 })",
    [string]$FrontendUrl = "http://localhost:$(if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { 5173 })",
    [int]$TimeoutSec = 60
)

function Test-Http200([string]$Name, [string]$Url) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $last = "no answer"
    while ($true) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Host "OK   $Name $Url -> 200"
                return $true
            }
            $last = "HTTP $($response.StatusCode)"
        } catch {
            $last = $_.Exception.Message
        }
        if ((Get-Date) -ge $deadline) { break }
        Start-Sleep -Seconds 2
    }
    Write-Host "FAIL $Name $Url -> $last (waited $TimeoutSec s)"
    return $false
}

$apiOk = Test-Http200 "api health" "$ApiUrl/api/health"
$mailpitOk = Test-Http200 "mailpit ui" "$MailpitUrl/"
$frontendOk = Test-Http200 "frontend" "$FrontendUrl/"
$proxyOk = Test-Http200 "api via frontend proxy" "$FrontendUrl/api/health"
if ($apiOk -and $mailpitOk -and $frontendOk -and $proxyOk) { exit 0 }
exit 1
