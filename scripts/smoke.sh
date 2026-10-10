#!/usr/bin/env bash
# Smoke check of a running stack (scripts/dev.sh or docker compose up):
# GET /api/health and the Mailpit UI must answer 200. Waits up to TIMEOUT_SEC for each.
set -uo pipefail

API_URL="${API_URL:-http://localhost:${API_PORT:-8000}}"
MAILPIT_URL="${MAILPIT_URL:-http://localhost:${MAILPIT_UI_PORT:-8025}}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"

check_200() {
    local name="$1" url="$2" code="000"
    local deadline=$((SECONDS + TIMEOUT_SEC))
    while :; do
        code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$url")"
        if [ "$code" = "200" ]; then
            echo "OK   $name $url -> 200"
            return 0
        fi
        [ "$SECONDS" -ge "$deadline" ] && break
        sleep 2
    done
    echo "FAIL $name $url -> HTTP $code (waited ${TIMEOUT_SEC} s)"
    return 1
}

status=0
check_200 "api health" "$API_URL/api/health" || status=1
check_200 "mailpit ui" "$MAILPIT_URL/" || status=1
exit "$status"
