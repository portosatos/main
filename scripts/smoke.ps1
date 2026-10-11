# Smoke check of a running stack (scripts/dev.ps1 or docker compose up):
# GET /api/health, the Mailpit UI, the frontend (nginx) with its /login route and /api/health
# through the frontend proxy must answer 200 (waits up to -TimeoutSec for each); then the demo user
# logs in through the frontend proxy and GET /api/auth/me with the session cookie must answer 200,
# and the first event of GET /api/events (SSE) must come through the proxy within -SseFirstByteSec
# (nginx must not buffer the stream).
param(
    [string]$ApiUrl = "http://localhost:$(if ($env:API_PORT) { $env:API_PORT } else { 8000 })",
    [string]$MailpitUrl = "http://localhost:$(if ($env:MAILPIT_UI_PORT) { $env:MAILPIT_UI_PORT } else { 8025 })",
    [string]$FrontendUrl = "http://localhost:$(if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { 5173 })",
    [string]$DemoEmail = $(if ($env:DEMO_USER_EMAIL) { $env:DEMO_USER_EMAIL } else { "demo@example.com" }),
    [string]$DemoPassword = $(if ($env:DEMO_USER_PASSWORD) { $env:DEMO_USER_PASSWORD } else { "demo12345" }),
    [int]$TimeoutSec = 60,
    [int]$SseFirstByteSec = 2
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

function Test-DemoLogin([string]$BaseUrl) {
    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $body = @{ email = $DemoEmail; password = $DemoPassword } | ConvertTo-Json
    try {
        $null = Invoke-WebRequest -Uri "$BaseUrl/api/auth/login" -Method Post -UseBasicParsing `
            -TimeoutSec 10 -WebSession $web -ContentType "application/json" -Body $body `
            -Headers @{ "X-Requested-With" = "ht" }
        $me = Invoke-WebRequest -Uri "$BaseUrl/api/auth/me" -UseBasicParsing -TimeoutSec 10 -WebSession $web
        if ($me.StatusCode -eq 200) {
            Write-Host "OK   demo login $BaseUrl/api/auth/me -> 200 ($DemoEmail)"
            return $true
        }
        $last = "HTTP $($me.StatusCode)"
    } catch {
        $last = $_.Exception.Message
    }
    Write-Host "FAIL demo login $BaseUrl ($DemoEmail) -> $last"
    return $false
}

# Invoke-WebRequest waits for the end of the body, and the stream never ends: HttpClient reads the
# first chunk instead.
function Test-SseFirstByte([string]$BaseUrl) {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.CookieContainer = New-Object System.Net.CookieContainer
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(10)
    try {
        $body = @{ email = $DemoEmail; password = $DemoPassword } | ConvertTo-Json
        $login = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, "$BaseUrl/api/auth/login")
        $login.Headers.Add("X-Requested-With", "ht")
        $login.Content = New-Object System.Net.Http.StringContent($body, [System.Text.Encoding]::UTF8, "application/json")
        $null = $client.SendAsync($login).Result.EnsureSuccessStatusCode()

        $watch = [System.Diagnostics.Stopwatch]::StartNew()
        $send = $client.GetAsync("$BaseUrl/api/events", [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead)
        if (-not $send.Wait($SseFirstByteSec * 1000)) { $last = "no response headers"; throw "timeout" }
        $response = $send.Result
        $code = [int]$response.StatusCode
        if ($code -ne 200) { $last = "HTTP $code"; throw "status" }
        $stream = $response.Content.ReadAsStreamAsync().Result
        $buffer = New-Object byte[] 4096
        $text = ""
        while ($text -notmatch "(?m)^event: ready") {
            $left = $SseFirstByteSec * 1000 - $watch.ElapsedMilliseconds
            $read = $stream.ReadAsync($buffer, 0, $buffer.Length)
            if ($left -le 0 -or -not $read.Wait([int][Math]::Max($left, 0))) { $last = "HTTP 200, no 'event: ready'"; throw "timeout" }
            if ($read.Result -eq 0) { $last = "HTTP 200, stream closed"; throw "closed" }
            $text += [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read.Result)
        }
        Write-Host "OK   sse $BaseUrl/api/events -> 200, first event in $($watch.ElapsedMilliseconds) ms"
        return $true
    } catch {
        if (-not $last) { $last = $_.Exception.Message }
    } finally {
        $client.Dispose()
    }
    Write-Host "FAIL sse $BaseUrl/api/events -> $last (within $SseFirstByteSec s)"
    return $false
}

$apiOk = Test-Http200 "api health" "$ApiUrl/api/health"
$mailpitOk = Test-Http200 "mailpit ui" "$MailpitUrl/"
$frontendOk = Test-Http200 "frontend" "$FrontendUrl/"
$loginPageOk = Test-Http200 "frontend login page" "$FrontendUrl/login"
$proxyOk = Test-Http200 "api via frontend proxy" "$FrontendUrl/api/health"
$loginOk = Test-DemoLogin $FrontendUrl
$sseOk = Test-SseFirstByte $FrontendUrl
if ($apiOk -and $mailpitOk -and $frontendOk -and $loginPageOk -and $proxyOk -and $loginOk -and $sseOk) { exit 0 }
exit 1
