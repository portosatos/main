#!/usr/bin/env bash
# Smoke check of a running stack (scripts/dev.sh or docker compose up):
# GET /api/health, the Mailpit UI, the frontend (nginx) with its /login route and /api/health
# through the frontend proxy must answer 200 (waits up to TIMEOUT_SEC for each); then the demo user
# logs in through the frontend proxy and GET /api/auth/me with the session cookie must answer 200,
# and the first event of GET /api/events (SSE) must come through the proxy within SSE_FIRST_BYTE_SEC
# (nginx must not buffer the stream).
set -uo pipefail

API_URL="${API_URL:-http://localhost:${API_PORT:-8000}}"
MAILPIT_URL="${MAILPIT_URL:-http://localhost:${MAILPIT_UI_PORT:-8025}}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${FRONTEND_PORT:-5173}}"
DEMO_USER_EMAIL="${DEMO_USER_EMAIL:-demo@example.com}"
DEMO_USER_PASSWORD="${DEMO_USER_PASSWORD:-demo12345}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
SSE_FIRST_BYTE_SEC="${SSE_FIRST_BYTE_SEC:-2}"

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

check_demo_login() {
    local base="$1" jar code
    jar="$(mktemp)"
    curl -s -o /dev/null -m 10 -c "$jar" -X POST "$base/api/auth/login"         -H 'Content-Type: application/json' -H 'X-Requested-With: ht'         --data "{\"email\": \"$DEMO_USER_EMAIL\", \"password\": \"$DEMO_USER_PASSWORD\"}"
    code="$(curl -s -o /dev/null -m 10 -b "$jar" -w '%{http_code}' "$base/api/auth/me")"
    rm -f "$jar"
    if [ "$code" = "200" ]; then
        echo "OK   demo login $base/api/auth/me -> 200 ($DEMO_USER_EMAIL)"
        return 0
    fi
    echo "FAIL demo login $base ($DEMO_USER_EMAIL) -> /api/auth/me HTTP $code"
    return 1
}

# The stream never ends: curl stops after SSE_FIRST_BYTE_SEC and prints what has arrived so far.
check_sse_first_byte() {
    local base="$1" jar out code
    jar="$(mktemp)"
    curl -s -o /dev/null -m 10 -c "$jar" -X POST "$base/api/auth/login"         -H 'Content-Type: application/json' -H 'X-Requested-With: ht'         --data "{\"email\": \"$DEMO_USER_EMAIL\", \"password\": \"$DEMO_USER_PASSWORD\"}"
    out="$(curl -sN -m "$SSE_FIRST_BYTE_SEC" -b "$jar" -w '
%{http_code}' "$base/api/events")"
    rm -f "$jar"
    code="$(printf '%s' "$out" | tail -n 1)"
    if [ "$code" = "200" ] && printf '%s' "$out" | grep -q '^event: ready'; then
        echo "OK   sse $base/api/events -> 200, first event within ${SSE_FIRST_BYTE_SEC} s"
        return 0
    fi
    echo "FAIL sse $base/api/events -> HTTP $code, no 'event: ready' within ${SSE_FIRST_BYTE_SEC} s"
    return 1
}

status=0
check_200 "api health" "$API_URL/api/health" || status=1
check_200 "mailpit ui" "$MAILPIT_URL/" || status=1
check_200 "frontend" "$FRONTEND_URL/" || status=1
check_200 "frontend login page" "$FRONTEND_URL/login" || status=1
check_200 "api via frontend proxy" "$FRONTEND_URL/api/health" || status=1
check_demo_login "$FRONTEND_URL" || status=1
check_sse_first_byte "$FRONTEND_URL" || status=1
exit "$status"
