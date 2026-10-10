#!/usr/bin/env bash
# Run all unit and integration tests: backend (pytest), the generator and the scripts/ utilities.
# Starts the compose Postgres (host port 5433) for integration tests; the test database is
# TEST_DATABASE_URL from the environment (default: health_tracker_test on localhost:5433).
# Extra arguments go to the backend pytest run, e.g. scripts/test.sh -m unit
set -uo pipefail
cd "$(dirname "$0")/.."

docker compose up -d --wait postgres || { echo "FAIL: postgres did not start"; exit 1; }

echo "== backend tests"
(cd backend && uv run pytest "$@")
backend_exit=$?

echo "== generator tests"
(cd generator && uv run pytest -q)
generator_exit=$?

echo "== scripts/ tests"
uv run --project backend pytest scripts/tests -q
scripts_exit=$?

if [ "$backend_exit" -ne 0 ] || [ "$generator_exit" -ne 0 ] || [ "$scripts_exit" -ne 0 ]; then
    echo "FAIL: backend=$backend_exit generator=$generator_exit scripts=$scripts_exit"
    exit 1
fi
echo "OK: all tests passed"
