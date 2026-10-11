#!/usr/bin/env bash
# Demo of the app (SPEC §8 stage 13): starts the stack, generates a month of data for the demo user,
# uploads it and opens the dashboard and Mailpit in the browser.
#   scripts/demo.sh [--reset] [--no-open]          (DAYS=30 SEED=42 from the environment)
# --reset first runs `docker compose down -v`: ALL data of the local stack (database, uploads, Mailpit)
# is deleted, the demo starts from scratch. --no-open does not open the browser.
# The file: htgen in the demo user's zone (`timezone` of /api/auth/me), DAYS days up to yesterday,
# one whole day (six days ago) without any device — a hatched «нет данных» column on the dashboard —
# and three short nights at the end (`short-sleep`): R1 opens, and its digest comes to Mailpit after
# the digest window (DIGEST_WINDOW_MINUTES, 15 min by default; quiet hours move it).
# Needs Docker, uv and curl; the demo user is DEMO_USER_EMAIL / DEMO_USER_PASSWORD.
set -uo pipefail
cd "$(dirname "$0")/.."

reset=0
open_browser=1
for arg in "$@"; do
    case "$arg" in
        --reset) reset=1 ;;
        --no-open) open_browser=0 ;;
        *) echo "usage: scripts/demo.sh [--reset] [--no-open]" >&2; exit 2 ;;
    esac
done
DAYS="${DAYS:-30}"
SEED="${SEED:-42}"
BASE_URL="http://localhost:${FRONTEND_PORT:-5173}"
MAILPIT_URL="http://localhost:${MAILPIT_UI_PORT:-8025}"
DEMO_USER_EMAIL="${DEMO_USER_EMAIL:-demo@example.com}"
DEMO_USER_PASSWORD="${DEMO_USER_PASSWORD:-demo12345}"

json_field() {  # json_field NAME < json: the first string or number value of "NAME"
    sed -n "s/.*\"$1\":\"\{0,1\}\([^\",}]*\).*/\1/p" | head -n 1
}

add_days() {  # add_days YYYY-MM-DD N
    date -d "$1 $2 day" +%F 2> /dev/null \
        || python3 -c 'import sys, datetime; print(datetime.date.fromisoformat(sys.argv[1]) + datetime.timedelta(days=int(sys.argv[2])))' "$1" "$2"
}

open_url() {
    if command -v xdg-open > /dev/null 2>&1; then xdg-open "$1" > /dev/null 2>&1 &
    elif command -v open > /dev/null 2>&1; then open "$1"
    elif command -v cmd.exe > /dev/null 2>&1; then cmd.exe //c start "" "$1"
    else echo "open $1 in the browser"
    fi
}

if [ "$reset" -eq 1 ]; then
    echo "== docker compose down -v (all local data is deleted)"
    docker compose down -v || { echo "FAIL: docker compose down -v"; exit 1; }
fi

echo "== docker compose up -d --build --wait"
docker compose up -d --build --wait || { echo "FAIL: the stack did not start"; exit 1; }

echo "== demo user"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
jar="$work/cookies.txt"
code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -c "$jar" -X POST "$BASE_URL/api/auth/login" \
    -H 'Content-Type: application/json' -H 'X-Requested-With: ht' \
    --data "{\"email\": \"$DEMO_USER_EMAIL\", \"password\": \"$DEMO_USER_PASSWORD\"}")"
[ "$code" = "200" ] || { echo "FAIL: demo login $BASE_URL ($DEMO_USER_EMAIL) -> HTTP $code"; exit 1; }
# The file is made by real time: a shifted dev Clock would put it away from the user's today.
offset="$(curl -s -m 10 -b "$jar" "$BASE_URL/api/dev/clock" | json_field offset_seconds)"
if [ -n "$offset" ] && [ "$offset" != "0" ]; then
    echo "The dev Clock was shifted by $offset s; resetting it to 0"
    curl -s -o /dev/null -m 10 -b "$jar" -X POST "$BASE_URL/api/dev/clock" -H 'Content-Type: application/json' \
        -H 'X-Requested-With: ht' --data '{"offset_seconds": 0}'
fi
me="$(curl -s -m 10 -b "$jar" "$BASE_URL/api/auth/me")"
today="$(printf '%s' "$me" | json_field today)"
zone="$(printf '%s' "$me" | json_field timezone)"
gap="$(add_days "$today" -6)"
gap_end="$(add_days "$today" -5)"
yesterday="$(add_days "$today" -1)"
echo "$DEMO_USER_EMAIL, zone $zone, today $today"

file="$work/demo_d${DAYS}_s${SEED}_$today.ndjson"
echo "== htgen --tz $zone --days $DAYS --gap ${gap}T00:00/${gap_end}T00:00 --scenario short-sleep"
uv run --project generator htgen --tz "$zone" --days "$DAYS" --seed "$SEED" \
    --gap "${gap}T00:00/${gap_end}T00:00" --scenario short-sleep --out "$file" || { echo "FAIL: htgen"; exit 1; }

echo "== upload"
# curl of Git for Windows needs a Windows path for -F file=@... (an MSYS path gives HTTP 000).
upload_file="$file"
if command -v cygpath > /dev/null 2>&1; then upload_file="$(cygpath -w "$file")"; fi
DEMO_USER_EMAIL="$DEMO_USER_EMAIL" DEMO_USER_PASSWORD="$DEMO_USER_PASSWORD" BASE_URL="$BASE_URL" \
    scripts/upload.sh "$upload_file" || { echo "FAIL: upload"; exit 1; }

dashboard="$BASE_URL/?date=$yesterday"
echo
echo "Demo is ready:"
echo "  app        $dashboard  (login $DEMO_USER_EMAIL / $DEMO_USER_PASSWORD)"
echo "  no data    $BASE_URL/?date=$gap  (the day without any device)"
echo "  week       $BASE_URL/?view=week&date=$yesterday"
echo "  R1         $BASE_URL/recommendations  (three short nights)"
echo "  mail       $MAILPIT_URL  (the R1 digest comes after the digest window, 15 min by default)"
if [ "$open_browser" -eq 1 ]; then
    open_url "$dashboard"
    open_url "$MAILPIT_URL"
fi
echo "OK: demo"
exit 0
