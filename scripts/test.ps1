# Run all unit and integration tests: backend (pytest), the generator and the scripts/ utilities.
# Starts the compose Postgres (host port 5433) and Mailpit (SMTP 1025, API 8025) for integration
# tests (the mailpit marker: a real digest in Mailpit); the test database is
# TEST_DATABASE_URL from the environment (default: health_tracker_test on localhost:5433).
# Extra arguments go to the backend pytest run, e.g. scripts/test.ps1 -m unit
Set-Location (Split-Path $PSScriptRoot -Parent)

docker compose up -d --wait postgres mailpit
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: postgres or mailpit did not start"; exit 1 }

Write-Host "== backend tests"
Push-Location backend
uv run pytest @args
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

if ($backendExit -ne 0 -or $generatorExit -ne 0 -or $scriptsExit -ne 0) {
    Write-Host "FAIL: backend=$backendExit generator=$generatorExit scripts=$scriptsExit"
    exit 1
}
Write-Host "OK: all tests passed"
