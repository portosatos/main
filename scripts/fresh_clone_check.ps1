# Fresh clone check (SPEC §9 #1 and #21, ADR-015): clones the repository into a temporary folder,
# checks the line endings of the files for the containers, copies .env.example to .env, starts the
# stack with `docker compose up --build`, runs the clone's scripts/smoke.ps1 (health, frontend and its
# proxy, Mailpit, the demo user's login, SSE) and stops it with `down -v`. The result goes to the block
# between the fresh_clone_check marks of docs/STATUS.md.
#   scripts/fresh_clone_check.ps1 [-DefaultPorts] [-Source URL] [-Branch main] [-Keep]
# The stack of the clone is its own compose project, health-tracker-fresh: docker-compose.yml names
# the project health-tracker, so a clone in another folder would otherwise take over the containers
# and volumes of the dev stack. Its images are built under other names (IMAGE_PREFIX of
# docker-compose.yml: health-tracker-fresh-backend:dev, ...) and removed at the end, so the dev
# stack's images are not replaced by the clone's code.
# Ports: by default other ones (app 5175, api 8002, Mailpit 8027 and 1027, postgres 5435) through the
# environment, which compose prefers to .env — the dev stack keeps running. -DefaultPorts uses the
# ports of .env.example (app http://localhost:5173), exactly what a fresh clone gets; stop the dev
# stack first: docker compose stop.
# -Source is `origin` of this repository by default: the check sees what is pushed. -Keep leaves the
# clone and its stack running. Exit code: 0 — every check passed; 1 — something failed.
# Saved with a UTF-8 BOM: Windows PowerShell 5.1 reads a file without it in the ANSI code page.
param(
    [switch]$DefaultPorts,
    [string]$Source = "",
    [string]$Branch = "main",
    [switch]$Keep,
    [string]$StatusFile = "docs/STATUS.md"
)

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$utf8 = New-Object System.Text.UTF8Encoding $false
if (-not $Source) { $Source = (git remote get-url origin) }
$project = "health-tracker-fresh"
$images = @("$project-backend:dev", "$project-frontend:dev")

# Replaces the block between <!-- NAME:begin --> and <!-- NAME:end --> of the status file (or
# appends it); creates the file if there is none.
function Set-StatusBlock([string]$Path, [string]$Name, [string]$Body) {
    $begin = "<!-- ${Name}:begin -->"
    $end = "<!-- ${Name}:end -->"
    $block = "$begin`n$($Body.TrimEnd())`n$end"
    if (Test-Path -LiteralPath $Path) {
        $text = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).Path, $utf8) -replace "`r`n", "`n"
    } else {
        $text = "# Статус проекта`n`n> Полностью заполняется на шаге 13.2 (критерии §9, известные проблемы). Блоки между метками`n> ``<!-- …:begin -->`` и ``<!-- …:end -->`` пишут скрипты ``scripts/bench_ingest.*`` и`n> ``scripts/fresh_clone_check.*`` — руками их не правят.`n"
    }
    $pattern = [regex]::Escape($begin) + "[\s\S]*?" + [regex]::Escape($end)
    if ($text -match $pattern) {
        $text = [regex]::Replace($text, $pattern, { param($m) $block })
    } else {
        $text = $text.TrimEnd() + "`n`n$block`n"
    }
    [System.IO.File]::WriteAllText((Join-Path $root $Path), $text, $utf8)
}

function Test-PortBusy([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        return ($connect.AsyncWaitHandle.WaitOne(500) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

if ($DefaultPorts) {
    $ports = [ordered]@{ FRONTEND_PORT = 5173; API_PORT = 8000; MAILPIT_UI_PORT = 8025; MAILPIT_SMTP_PORT = 1025; POSTGRES_HOST_PORT = 5433 }
} else {
    $ports = [ordered]@{ FRONTEND_PORT = 5175; API_PORT = 8002; MAILPIT_UI_PORT = 8027; MAILPIT_SMTP_PORT = 1027; POSTGRES_HOST_PORT = 5435 }
}
$busy = @($ports.Keys | Where-Object { Test-PortBusy $ports[$_] } | ForEach-Object { "$_=$($ports[$_])" })
if ($busy.Count -gt 0) {
    $hint = if ($DefaultPorts) { "stop the dev stack first: docker compose stop" } else { "free them or use -DefaultPorts" }
    Write-Host "FAIL ports in use: $($busy -join ', '); $hint"
    exit 1
}

$checks = New-Object System.Collections.Generic.List[string]
$failed = $false
function Add-Check([string]$Name, [bool]$Ok, [string]$Detail) {
    $script:checks.Add("| $Name | $(if ($Ok) { 'да' } else { '**нет**' }) | $Detail |")
    if (-not $Ok) { $script:failed = $true }
    Write-Host "$(if ($Ok) { 'OK  ' } else { 'FAIL' }) $Name - $Detail"
}

$work = Join-Path ([System.IO.Path]::GetTempPath()) "ht-fresh-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$clone = Join-Path $work "health-tracker"
New-Item -ItemType Directory -Path $work | Out-Null
$saved = @{}
foreach ($name in @($ports.Keys) + @("COMPOSE_PROJECT_NAME", "IMAGE_PREFIX", "APP_URL")) { $saved[$name] = [Environment]::GetEnvironmentVariable($name) }
$smokeText = ""
$commit = "?"
$started = $false
$watch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    Write-Host "== git clone $Source ($Branch) -> $clone"
    git clone --quiet --branch $Branch $Source $clone
    Add-Check "git clone" ($LASTEXITCODE -eq 0) "$Source, ветка $Branch"
    if ($LASTEXITCODE -ne 0) { throw "clone" }
    Push-Location $clone
    $commit = (git log -1 --format="%h %s")

    # §9 #21: scripts and files for the Linux containers keep LF in a Windows checkout (.gitattributes).
    $eol = @(git ls-files --eol -- "*.sh" "**/Dockerfile" "Dockerfile" "*.conf")
    $notLf = @($eol | Where-Object { $_ -notmatch "w/lf" })
    Add-Check ".gitattributes: LF у *.sh, Dockerfile, *.conf" ($eol.Count -gt 0 -and $notLf.Count -eq 0) `
        "$($eol.Count) файлов, не LF: $(if ($notLf.Count) { ($notLf | ForEach-Object { ($_ -split "\s+")[-1] }) -join ', ' } else { 'нет' })"

    Copy-Item .env.example .env
    Add-Check "cp .env.example .env" (Test-Path .env) ".env из .env.example"

    $env:COMPOSE_PROJECT_NAME = $project
    $env:IMAGE_PREFIX = $project
    foreach ($name in $ports.Keys) { Set-Item "env:$name" ([string]$ports[$name]) }
    $env:APP_URL = "http://localhost:$($ports.FRONTEND_PORT)"

    Write-Host "== docker compose up --build -d --wait (project $project)"
    $up = [System.Diagnostics.Stopwatch]::StartNew()
    docker compose up --build -d --wait
    $upOk = $LASTEXITCODE -eq 0
    $started = $true
    Add-Check "docker compose up --build" $upOk "проект $project, $([int]$up.Elapsed.TotalSeconds) с до healthy"
    if (-not $upOk) { docker compose ps; docker compose logs --tail 50; throw "up" }

    Write-Host "== scripts/smoke.ps1 of the clone"
    $smoke = & (Join-Path $clone "scripts\smoke.ps1") -ApiUrl "http://localhost:$($ports.API_PORT)" `
        -MailpitUrl "http://localhost:$($ports.MAILPIT_UI_PORT)" -FrontendUrl "http://localhost:$($ports.FRONTEND_PORT)" 6>&1
    $smokeCode = $LASTEXITCODE
    $smokeText = ($smoke | ForEach-Object { "$_" }) -join "`n"
    Write-Host $smokeText
    Add-Check "scripts/smoke.ps1 клона" ($smokeCode -eq 0) "exit $smokeCode; приложение http://localhost:$($ports.FRONTEND_PORT), вход demo@example.com"
} catch {
    if (-not $failed) { Add-Check "проверка" $false $_.Exception.Message }
} finally {
    if ($started -and -not $Keep) {
        Write-Host "== docker compose down -v (project $project)"
        docker compose down -v 2>&1 | Out-Null
        docker image rm @images 2>&1 | Out-Null
    }
    if ((Get-Location).Path -eq $clone) { Pop-Location }
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
    if (-not $Keep) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}

$os = (Get-CimInstance Win32_OperatingSystem).Caption
$docker = (docker version --format "{{.Server.Version}}")
$compose = (docker compose version --short)
$git = (git --version)
$now = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")
$portsText = ($ports.Keys | ForEach-Object { "$_=$($ports[$_])" }) -join ", "
$mode = if ($DefaultPorts) { "порты .env.example (``-DefaultPorts``)" } else { "другие порты через окружение" }
$report = @"
## Проверка чистого клона (``scripts/fresh_clone_check.ps1``)

- Когда: $now (системное время), $([int]$watch.Elapsed.TotalSeconds) с; итог: $(if ($failed) { '**не пройдена**' } else { 'пройдена, exit 0' }).
- Машина: $os; Docker $docker, Compose $compose; $git.
- Клон: $Source, ветка $Branch, коммит ``$commit``; проект compose ``$project``, ${mode}: $portsText.

| Проверка | Пройдена | Подробности |
|---|---|---|
$($checks -join "`n")

Вывод ``scripts/smoke.ps1`` клона:

``````text
$smokeText
``````
"@
Set-StatusBlock $StatusFile "fresh_clone_check" $report
Write-Host "Written to $StatusFile"
if ($failed) { Write-Host "FAIL: fresh clone check"; exit 1 }
Write-Host "OK: fresh clone check"
exit 0
