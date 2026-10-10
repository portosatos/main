#!/usr/bin/env bash
# Start the whole stack in the foreground: postgres, mailpit, api, worker, frontend.
# Extra arguments go to `docker compose up`, e.g. scripts/dev.sh -d
set -euo pipefail
cd "$(dirname "$0")/.."
exec docker compose up --build "$@"
