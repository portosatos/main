#!/usr/bin/env bash
# Run all unit and integration tests: backend (pytest), the generator and the scripts/ utilities.
# Starts the compose Postgres (host port 5433) and Mailpit (SMTP 1025, API 8025) for integration
# tests (the mailpit marker: a real digest in Mailpit); the test database is
# TEST_DATABASE_URL from the environment (default: health_tracker_test on localhost:5433).
# --all (or -All) also runs the e2e scenarios afterwards (scripts/e2e.sh, the e2e stack).
# Other arguments go to the backend pytest run, e.g. scripts/test.sh -m unit
set -uo pipefail
cd "$(dirname "$0")/.."

all=0
args=()
for arg in "$@"; do
    if [ "$arg" = "--all" ] || [ "$arg" = "-All" ]; then all=1; else args+=("$arg"); fi
done

docker compose up -d --wait postgres mailpit || { echo "FAIL: postgres or mailpit did not start"; exit 1; }

echo "== backend tests"
(cd backend && uv run pytest "${args[@]}")
backend_exit=$?

echo "== generator tests"
(cd generator && uv run pytest -q)
generator_exit=$?

echo "== scripts/ tests"
uv run --project backend pytest scripts/tests -q
scripts_exit=$?

e2e_exit=0
if [ "$all" -eq 1 ]; then
    echo "== e2e"
    scripts/e2e.sh
    e2e_exit=$?
fi

if [ "$backend_exit" -ne 0 ] || [ "$generator_exit" -ne 0 ] || [ "$scripts_exit" -ne 0 ] || [ "$e2e_exit" -ne 0 ]; then
    echo "FAIL: backend=$backend_exit generator=$generator_exit scripts=$scripts_exit e2e=$e2e_exit"
    exit 1
fi
if [ "$all" -eq 1 ]; then echo "OK: all tests passed (with e2e)"; else echo "OK: all tests passed"; fi
