# Measure the ingest of a ~200 MB file on a running stack (scripts/dev.ps1 -d) and write the result to
# docs/STATUS.md (SPEC §4 «Производительность», §9 #6, ADR-015):
#   scripts/bench_ingest.ps1 [-Days 90] [-HrInterval 3] [-Seed 7] [-LimitSec 300]
# Generates the file with htgen (90 days, two devices; heart rate every 3 s — htgen writes it only
# for the watch, so 5 s would give ~130 MB), registers a fresh user (a re-upload by the demo user
# would be all duplicates), uploads it through the frontend proxy and polls the job. Meanwhile it
# samples the memory of the worker and of postgres (`docker stats`; the worker streams the file in
# batches, the merge runs in SQL) and times GET /api/summary/day (the dashboard).
# The block between the bench_ingest marks in docs/STATUS.md is replaced, the rest is kept.
# Exit code: 0 — the job is done within -LimitSec; 1 — slower, failed or the stack refused (the
# result is written whenever the job finished); 2 — the stack is not running.
# Needs Docker, uv and curl.exe (Windows 10 and later). Saved with a UTF-8 BOM: Windows PowerShell 5.1
# reads a file without it in the ANSI code page, and the Russian report would be garbled.
param(
    [int]$Days = 90,
    [int]$HrInterval = 3,
    [int]$Seed = 7,
    [int]$LimitSec = 300,
    [int]$TimeoutSec = 1800,
    [string]$BaseUrl = "http://localhost:$(if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { 5173 })",
    [string]$StatusFile = "docs/STATUS.md"
)

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$utf8 = New-Object System.Text.UTF8Encoding $false

function Get-Json([string]$Url, [string]$Jar) {
    $raw = & curl.exe -s -m 10 -b $Jar $Url
    return ($raw -join "`n") | ConvertFrom-Json
}

# Memory of the worker and postgres, MiB: @{ worker = ...; postgres = ... } (`docker stats` prints the
# container as it was given).
function Get-Memory {
    $memory = @{}
    foreach ($line in @(docker stats --no-stream --format "{{.Container}} {{.MemUsage}}" $worker $postgres)) {
        $id, $usage = "$line".Split(" ", 2)
        if ($id -eq $worker) { $memory.worker = ConvertTo-MiB $usage }
        if ($id -eq $postgres) { $memory.postgres = ConvertTo-MiB $usage }
    }
    return $memory
}

# "63.57MiB / 15.53GiB" -> 63.57 (MiB)
function ConvertTo-MiB([string]$Usage) {
    if ($Usage -notmatch "^\s*([\d.]+)\s*([KMG]i?B|B)") { return $null }
    $value = [double]::Parse($Matches[1], [System.Globalization.CultureInfo]::InvariantCulture)
    switch -regex ($Matches[2]) {
        "^G" { return $value * 1024 }
        "^M" { return $value }
        "^K" { return $value / 1024 }
        default { return $value / 1024 / 1024 }
    }
}

function Format-Num([double]$Value, [int]$Digits = 0) {
    return $Value.ToString("N$Digits", [System.Globalization.CultureInfo]::GetCultureInfo("ru-RU"))
}

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

try {
    $health = Invoke-WebRequest -Uri "$BaseUrl/api/health" -UseBasicParsing -TimeoutSec 10
    if ($health.StatusCode -ne 200) { throw "HTTP $($health.StatusCode)" }
} catch {
    Write-Host "FAIL the stack does not answer at $BaseUrl/api/health ($($_.Exception.Message)); start it: scripts/dev.ps1 -d"
    exit 2
}
$worker = (docker compose ps -q worker) | Select-Object -First 1
$postgres = (docker compose ps -q postgres) | Select-Object -First 1
if (-not $worker -or -not $postgres) {
    Write-Host "FAIL no running worker or postgres container of the compose project; start it: scripts/dev.ps1 -d"
    exit 2
}

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) "ht-bench-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
New-Item -ItemType Directory -Path $workDir | Out-Null
$file = Join-Path $workDir "bench_d${Days}_hr${HrInterval}_s${Seed}.ndjson"
$jar = Join-Path $workDir "cookies.txt"
$body = Join-Path $workDir "register.json"

try {
    Write-Host "== htgen --days $Days --hr-interval $HrInterval --seed $Seed"
    $genClock = [System.Diagnostics.Stopwatch]::StartNew()
    uv run --project generator htgen --days $Days --hr-interval $HrInterval --seed $Seed --out $file
    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL htgen"; exit 1 }
    $size = (Get-Item -LiteralPath $file).Length
    $lines = 0
    $reader = New-Object System.IO.StreamReader($file)
    try { while ($null -ne $reader.ReadLine()) { $lines++ } } finally { $reader.Dispose() }
    Write-Host "File: $(Format-Num ($size / 1MB) 1) MB, $(Format-Num $lines) lines, generated in $([int]$genClock.Elapsed.TotalSeconds) s"

    # A fresh user in the zone htgen writes by default.
    $email = "bench-$([guid]::NewGuid().ToString('N').Substring(0, 12))@example.com"
    $register = @{ email = $email; password = "bench-pass-123"; timezone = "Europe/Moscow" } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($body, $register)
    $code = & curl.exe -s -o NUL -m 10 -w "%{http_code}" -c $jar -X POST "$BaseUrl/api/auth/register" `
        -H "Content-Type: application/json" -H "X-Requested-With: ht" --data-binary "@$body"
    if ($code -ne "201") { Write-Host "FAIL register $email -> HTTP $code"; exit 1 }
    $me = Get-Json "$BaseUrl/api/auth/me" $jar
    $day = ([datetime]::ParseExact($me.today, "yyyy-MM-dd", $null)).AddDays(-1).ToString("yyyy-MM-dd")
    Write-Host "User: $email (today $($me.today))"

    $before = Get-Memory

    Write-Host "== upload"
    $transfer = [System.Diagnostics.Stopwatch]::StartNew()
    $response = & curl.exe -s -b $jar -H "X-Requested-With: ht" `
        -F "file=@$file;type=application/x-ndjson" -w "`n%{http_code}" "$BaseUrl/api/ingest/files"
    $transfer.Stop()
    $out = @($response)
    if ($out[-1] -ne "202") { Write-Host "FAIL upload -> HTTP $($out[-1]) $($out[0..($out.Count - 2)] -join ' ')"; exit 1 }
    $jobId = (($out[0..($out.Count - 2)] -join "`n") | ConvertFrom-Json).job_id
    Write-Host "Uploaded in $([int]$transfer.Elapsed.TotalSeconds) s, job $jobId"

    $peak = $before.worker
    $peakDb = $before.postgres
    $samples = 0
    $latencies = New-Object System.Collections.Generic.List[double]
    $job = $null
    $wait = [System.Diagnostics.Stopwatch]::StartNew()
    while ($wait.Elapsed.TotalSeconds -lt $TimeoutSec) {
        $memory = Get-Memory
        $mem = $memory.worker
        if ($null -ne $mem) {
            $samples++
            if ($mem -gt $peak) { $peak = $mem }
        }
        if ($memory.postgres -gt $peakDb) { $peakDb = $memory.postgres }
        $timing = & curl.exe -s -o NUL -m 30 -b $jar -w "%{http_code} %{time_total}" "$BaseUrl/api/summary/day?date=$day"
        $parts = "$timing".Split(" ")
        if ($parts[0] -eq "200") {
            $latencies.Add([double]::Parse($parts[1], [System.Globalization.CultureInfo]::InvariantCulture) * 1000)
        }
        $job = Get-Json "$BaseUrl/api/ingest/jobs/$jobId" $jar
        Write-Host ("  {0,4} s  status={1} progress={2:N2} worker={3:N0} MiB" -f [int]$wait.Elapsed.TotalSeconds, $job.status, $job.progress, $mem)
        if ($job.status -eq "done" -or $job.status -eq "failed") { break }
    }
    if (-not $job -or ($job.status -ne "done" -and $job.status -ne "failed")) {
        Write-Host "FAIL job $jobId is still $($job.status) after $TimeoutSec s; nothing written to $StatusFile"
        exit 1
    }

    $created = [DateTimeOffset]::Parse($job.created_at)
    $finished = [DateTimeOffset]::Parse($job.finished_at)
    $processingSec = ($finished - $created).TotalSeconds
    $totalSec = $transfer.Elapsed.TotalSeconds + $processingSec
    $sorted = @($latencies | Sort-Object)
    if ($sorted.Count -gt 0) {
        $p95 = $sorted[[Math]::Max(0, [int][Math]::Ceiling(0.95 * $sorted.Count) - 1)]
        $latencyText = "p95 $(Format-Num $p95) мс, макс. $(Format-Num $sorted[-1]) мс (запросов: $($sorted.Count))"
    } else {
        $latencyText = "нет ответов 200"
    }
    $ok = $job.status -eq "done" -and $totalSec -le $LimitSec
    $verdict = if ($job.status -ne "done") { "**нет: задача $($job.status)**" }
    elseif ($ok) { "да ($(Format-Num $totalSec) с ≤ $LimitSec с)" }
    else { "**нет: $(Format-Num $totalSec) с > $LimitSec с**" }

    $os = (Get-CimInstance Win32_OperatingSystem).Caption
    $cpu = ((Get-CimInstance Win32_Processor) | Select-Object -First 1).Name.Trim()
    $ram = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
    $dockerInfo = (docker info --format "{{.ServerVersion}}|{{.NCPU}}|{{.MemTotal}}") -split "\|"
    $counts = $job.counts
    $now = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")

    $report = @"
## Замер загрузки большого файла (``scripts/bench_ingest.ps1``)

- Когда: $now (системное время); ``scripts/bench_ingest.ps1 -Days $Days -HrInterval $HrInterval -Seed $Seed``.
- Машина: $os; $cpu; ОЗУ $(Format-Num $ram 1) ГиБ. Docker $($dockerInfo[0]): $($dockerInfo[1]) CPU, $(Format-Num ([double]$dockerInfo[2] / 1GB) 1) ГиБ.
- Файл: htgen ``--days $Days --hr-interval $HrInterval --seed $Seed`` (часы и телефон; пульс только с часов) —
  $(Format-Num ($size / 1MB) 1) МБ, $(Format-Num $lines) строк. Свежий пользователь ``$email``, загрузка через ``:5173``.

| Показатель | Значение |
|---|---|
| Передача файла (HTTP, ``POST /api/ingest/files``) | $(Format-Num $transfer.Elapsed.TotalSeconds 1) с |
| Обработка (задача: ``created_at`` → ``finished_at``) | $(Format-Num $processingSec 1) с |
| Всего | $(Format-Num $totalSec 1) с |
| Пиковая память воркера (``docker stats``, замеров: $samples) | $(Format-Num $peak 0) MiB (до загрузки $(Format-Num $before.worker 0) MiB) |
| Пиковая память postgres (там же) | $(Format-Num $peakDb 0) MiB (до загрузки $(Format-Num $before.postgres 0) MiB) |
| ``GET /api/summary/day`` во время обработки | $latencyText |
| Записи: всего / новые / дубли / конфликты / некорректные | $(Format-Num $counts.total) / $(Format-Num $counts.new) / $(Format-Num $counts.duplicate) / $(Format-Num $counts.conflict) / $(Format-Num $counts.invalid) |
| Статус задачи | $($job.status) |
| Ориентир SPEC §4: ≤ $LimitSec с | $verdict |
"@
    Set-StatusBlock $StatusFile "bench_ingest" $report
    Write-Host ""
    Write-Host $report
    Write-Host "Written to $StatusFile"
    if ($ok) { Write-Host "OK   ingest of $(Format-Num ($size / 1MB) 0) MB took $(Format-Num $totalSec) s"; exit 0 }
    Write-Host "FAIL job $($job.status), $(Format-Num $totalSec) s (limit $LimitSec s)"
    exit 1
} finally {
    Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
}
