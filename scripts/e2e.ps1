# E2E scenarios (Playwright, e2e/) against the e2e stack: docker-compose.yml + docker-compose.e2e.yml,
# its own project and ports (app http://localhost:5174, Mailpit http://localhost:8026), so the dev
# stack keeps running. Installs e2e/node_modules and Chromium on the first run; needs Docker, Node 22+
# and uv (the scenarios generate their files with htgen).
# -Down stops the e2e stack afterwards; other arguments go to `playwright test`, e.g.
#   scripts/e2e.ps1 02-upload --headed
Set-Location (Split-Path $PSScriptRoot -Parent)

$down = $false
$rest = @()
foreach ($arg in $args) {
    if ($arg -eq "-Down" -or $arg -eq "--down") { $down = $true } else { $rest += $arg }
}
$compose = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.e2e.yml")

Write-Host "== e2e stack"
docker @compose up -d --build --wait
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: the e2e stack did not start"; exit 1 }

Write-Host "== playwright"
if (-not (Test-Path e2e/node_modules)) {
    npm ci --prefix e2e
    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: npm ci in e2e"; exit 1 }
}
Push-Location e2e
npx playwright install chromium
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "FAIL: playwright install chromium"; exit 1 }
npx playwright test @rest
$code = $LASTEXITCODE
Pop-Location

if ($down) { docker @compose down }
if ($code -ne 0) {
    Write-Host "FAIL: e2e (report: npx --prefix e2e playwright show-report e2e/playwright-report)"
    exit $code
}
Write-Host "OK: e2e passed"
