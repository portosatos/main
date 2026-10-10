#!/usr/bin/env bash
# Upload an NDJSON file to a running stack and wait for its ingest report:
#   scripts/upload.sh FILE
# Logs in as the demo user (DEMO_USER_EMAIL / DEMO_USER_PASSWORD) through the frontend proxy,
# POSTs the file to /api/ingest/files, polls /api/ingest/jobs/{id} every second until the job is
# done or failed and prints the report with the upload and processing times.
# Exit code: 0 — job done; 1 — job failed, timed out or the API refused; 2 — usage.
set -uo pipefail

FILE="${1:-}"
BASE_URL="${BASE_URL:-http://localhost:${FRONTEND_PORT:-5173}}"
DEMO_USER_EMAIL="${DEMO_USER_EMAIL:-demo@example.com}"
DEMO_USER_PASSWORD="${DEMO_USER_PASSWORD:-demo12345}"
TIMEOUT_SEC="${TIMEOUT_SEC:-1800}"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
    echo "usage: scripts/upload.sh FILE   (an existing NDJSON file)" >&2
    exit 2
fi

jar="$(mktemp)"
trap 'rm -f "$jar"' EXIT

json_field() {  # json_field NAME < json: the first string or number value of "NAME"
    sed -n "s/.*\"$1\":\"\{0,1\}\([^\",}]*\).*/\1/p" | head -n 1
}

code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -c "$jar" -X POST "$BASE_URL/api/auth/login" \
    -H 'Content-Type: application/json' -H 'X-Requested-With: ht' \
    --data "{\"email\": \"$DEMO_USER_EMAIL\", \"password\": \"$DEMO_USER_PASSWORD\"}")"
if [ "$code" != "200" ]; then
    echo "FAIL login $BASE_URL ($DEMO_USER_EMAIL) -> HTTP $code"
    exit 1
fi

size="$(wc -c < "$FILE" | tr -d ' ')"
echo "Uploading $FILE ($size bytes) to $BASE_URL ..."
started=$SECONDS
response="$(curl -s -b "$jar" -H 'X-Requested-With: ht' \
    -F "file=@$FILE;type=application/x-ndjson" -w '\n%{http_code}' "$BASE_URL/api/ingest/files")"
code="$(printf '%s\n' "$response" | tail -n 1)"
body="$(printf '%s\n' "$response" | sed '$d')"
if [ "$code" != "202" ]; then
    echo "FAIL upload -> HTTP $code $body"
    exit 1
fi
job_id="$(printf '%s' "$body" | json_field job_id)"
uploaded=$SECONDS
echo "Uploaded in $((uploaded - started)) s, job $job_id"

status=""
while [ $((SECONDS - uploaded)) -lt "$TIMEOUT_SEC" ]; do
    job="$(curl -s -m 10 -b "$jar" "$BASE_URL/api/ingest/jobs/$job_id")"
    status="$(printf '%s' "$job" | json_field status)"
    progress="$(printf '%s' "$job" | json_field progress)"
    echo "  status=$status progress=$progress"
    case "$status" in done | failed) break ;; esac
    sleep 1
done

echo "Report:"
if command -v python3 > /dev/null 2>&1; then
    printf '%s' "$job" | python3 -m json.tool
else
    printf '%s\n' "$job"
fi
echo "Processing took $((SECONDS - uploaded)) s, total $((SECONDS - started)) s"
if [ "$status" = "done" ]; then
    echo "OK   job $job_id done"
    exit 0
fi
echo "FAIL job $job_id status=${status:-unknown}"
exit 1
