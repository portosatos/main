#!/usr/bin/env bash
# E2E scenarios (Playwright, e2e/) against the e2e stack: docker-compose.yml + docker-compose.e2e.yml,
# its own project and ports (app http://localhost:5174, Mailpit http://localhost:8026), so the dev
# stack keeps running. Installs e2e/node_modules and Chromium on the first run; needs Docker, Node 22+
# and uv (the scenarios generate their files with htgen).
# --down stops the e2e stack afterwards; other arguments go to `playwright test`, e.g.
#   scripts/e2e.sh 02-upload --headed
set -uo pipefail
cd "$(dirname "$0")/.."

down=0
args=()
for arg in "$@"; do
    if [ "$arg" = "--down" ]; then down=1; else args+=("$arg"); fi
done
compose=(docker compose -f docker-compose.yml -f docker-compose.e2e.yml)

echo "== e2e stack"
"${compose[@]}" up -d --build --wait || { echo "FAIL: the e2e stack did not start"; exit 1; }

echo "== playwright"
if [ ! -d e2e/node_modules ]; then
    npm ci --prefix e2e || { echo "FAIL: npm ci in e2e"; exit 1; }
fi
(cd e2e && npx playwright install chromium) || { echo "FAIL: playwright install chromium"; exit 1; }
(cd e2e && npx playwright test "${args[@]}")
code=$?

if [ "$down" -eq 1 ]; then "${compose[@]}" down; fi
if [ "$code" -ne 0 ]; then
    echo "FAIL: e2e (report: npx --prefix e2e playwright show-report e2e/playwright-report)"
    exit "$code"
fi
echo "OK: e2e passed"
