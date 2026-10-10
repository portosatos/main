# Run all unit and integration tests: backend (pytest) and the scripts/ utilities.
# Starts the compose Postgres (host port 5433) for integration tests; the test database is
# TEST_DATABASE_URL from the environment (default: health_tracker_test on localhost:5433).
# Extra arguments go to the backend pytest run, e.g. scripts/test.ps1 -m unit
Set-Location (Split-Path $PSScriptRoot -Parent)

docker compose up -d --wait postgres
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: postgres did not start"; exit 1 }

Write-Host "== backend tests"
Push-Location backend
uv run pytest @args
$backendExit = $LASTEXITCODE
Pop-Location

Write-Host "== scripts/ tests"
uv run --project backend pytest scripts/tests -q
$scriptsExit = $LASTEXITCODE

if ($backendExit -ne 0 -or $scriptsExit -ne 0) {
    Write-Host "FAIL: backend=$backendExit scripts=$scriptsExit"
    exit 1
}
Write-Host "OK: all tests passed"
