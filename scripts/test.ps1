# Run all unit and integration tests: backend (pytest), the generator and the scripts/ utilities.
# Starts the compose Postgres (host port 5433) and Mailpit (SMTP 1025, API 8025) for integration
# tests (the mailpit marker: a real digest in Mailpit); the test database is
# TEST_DATABASE_URL from the environment (default: health_tracker_test on localhost:5433).
# -All (or --all) also runs the e2e scenarios afterwards (scripts/e2e.ps1, the e2e stack).
# Other arguments go to the backend pytest run, e.g. scripts/test.ps1 -m unit
Set-Location (Split-Path $PSScriptRoot -Parent)

$all = $false
$rest = @()
foreach ($arg in $args) {
    if ($arg -eq "-All" -or $arg -eq "--all") { $all = $true } else { $rest += $arg }
}

docker compose up -d --wait postgres mailpit
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: postgres or mailpit did not start"; exit 1 }

Write-Host "== backend tests"
Push-Location backend
uv run pytest @rest
$backendExit = $LASTEXITCODE
Pop-Location

Write-Host "== generator tests"
Push-Location generator
uv run pytest -q
$generatorExit = $LASTEXITCODE
Pop-Location

Write-Host "== scripts/ tests"
uv run --project backend pytest scripts/tests -q
$scriptsExit = $LASTEXITCODE

$e2eExit = 0
if ($all) {
    Write-Host "== e2e"
    & (Join-Path $PSScriptRoot "e2e.ps1")
    $e2eExit = $LASTEXITCODE
}

if ($backendExit -ne 0 -or $generatorExit -ne 0 -or $scriptsExit -ne 0 -or $e2eExit -ne 0) {
    Write-Host "FAIL: backend=$backendExit generator=$generatorExit scripts=$scriptsExit e2e=$e2eExit"
    exit 1
}
if ($all) { Write-Host "OK: all tests passed (with e2e)" } else { Write-Host "OK: all tests passed" }
