#!/usr/bin/env bash
# Measure the ingest of a ~200 MB file on a running stack (scripts/dev.sh -d) and write the result to
# docs/STATUS.md (SPEC §4 «Производительность», §9 #6, ADR-015):
#   scripts/bench_ingest.sh            (DAYS=90 HR_INTERVAL=3 SEED=7 LIMIT_SEC=300 from the environment)
# Generates the file with htgen (90 days, two devices; heart rate every 3 s — htgen writes it only
# for the watch, so 5 s would give ~130 MB), registers a fresh user (a re-upload by the demo user
# would be all duplicates), uploads it through the frontend proxy and polls the job. Meanwhile it
# samples the memory of the worker and of postgres (`docker stats`; the worker streams the file in
# batches, the merge runs in SQL) and times GET /api/summary/day (the dashboard).
# The block between the bench_ingest marks in docs/STATUS.md is replaced, the rest is kept.
# Exit code: 0 — the job is done within LIMIT_SEC; 1 — slower, failed or the stack refused (the
# result is written whenever the job finished); 2 — the stack is not running.
# Needs Docker, uv and curl.
set -uo pipefail
cd "$(dirname "$0")/.."

DAYS="${DAYS:-90}"
HR_INTERVAL="${HR_INTERVAL:-3}"
SEED="${SEED:-7}"
LIMIT_SEC="${LIMIT_SEC:-300}"
TIMEOUT_SEC="${TIMEOUT_SEC:-1800}"
BASE_URL="${BASE_URL:-http://localhost:${FRONTEND_PORT:-5173}}"
STATUS_FILE="${STATUS_FILE:-docs/STATUS.md}"

json_field() {  # json_field NAME < json: the first string or number value of "NAME"
    sed -n "s/.*\"$1\":\"\{0,1\}\([^\",}]*\).*/\1/p" | head -n 1
}

to_mib() {  # to_mib "63.57MiB / 15.53GiB" -> 63.57
    awk '{
        if (match($1, /^[0-9.]+/) == 0) exit
        value = substr($1, 1, RLENGTH); unit = substr($1, RLENGTH + 1)
        if (unit ~ /^G/) value *= 1024; else if (unit ~ /^K/) value /= 1024; else if (unit == "B") value /= 1048576
        printf "%.1f", value
    }'
}

memory() {  # memory: "WORKER_MIB POSTGRES_MIB" (`docker stats` prints the container as it was given)
    local stats w p
    stats="$(docker stats --no-stream --format '{{.Container}} {{.MemUsage}}' "$worker" "$postgres")"
    w="$(printf '%s\n' "$stats" | awk -v id="$worker" '$1 == id { $1 = ""; print }' | to_mib)"
    p="$(printf '%s\n' "$stats" | awk -v id="$postgres" '$1 == id { $1 = ""; print }' | to_mib)"
    echo "${w:-} ${p:-}"
}

num() {  # num VALUE DIGITS: a number with a decimal comma
    LC_ALL=C printf "%.${2:-0}f" "$1" | tr . ,
}

epoch() {  # epoch ISO-8601 -> seconds since the epoch (with a fraction), empty if no tool can parse it
    local out=""
    out="$(date -d "$1" +%s.%N 2> /dev/null)"
    if [ -z "$out" ] && command -v python3 > /dev/null 2>&1; then
        out="$(python3 -c 'import sys, datetime; print(datetime.datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00")).timestamp())' "$1" 2> /dev/null)"
    fi
    printf '%s' "$out"
}

# Replaces the block between <!-- NAME:begin --> and <!-- NAME:end --> of the status file (or
# appends it); creates the file if there is none.
set_status_block() {  # set_status_block FILE NAME BODY_FILE
    local file="$1" begin="<!-- $2:begin -->" end="<!-- $2:end -->" body="$3" tmp
    if [ ! -f "$file" ]; then
        cat > "$file" << 'EOF'
# Статус проекта

> Полностью заполняется на шаге 13.2 (критерии §9, известные проблемы). Блоки между метками
> `<!-- …:begin -->` и `<!-- …:end -->` пишут скрипты `scripts/bench_ingest.*` и
> `scripts/fresh_clone_check.*` — руками их не правят.
EOF
    fi
    tmp="$(mktemp)"
    if grep -qF "$begin" "$file"; then
        awk -v begin="$begin" -v end="$end" -v body="$body" '
            $0 == begin { print; while ((getline line < body) > 0) print line; skip = 1; next }
            $0 == end { skip = 0 }
            !skip { print }
        ' "$file" > "$tmp"
    else
        { cat "$file"; printf '\n%s\n' "$begin"; cat "$body"; printf '%s\n' "$end"; } > "$tmp"
    fi
    tr -d '\r' < "$tmp" > "$file"
    rm -f "$tmp"
}

if [ "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$BASE_URL/api/health")" != "200" ]; then
    echo "FAIL the stack does not answer at $BASE_URL/api/health; start it: scripts/dev.sh -d"
    exit 2
fi
worker="$(docker compose ps -q worker | head -n 1)"
postgres="$(docker compose ps -q postgres | head -n 1)"
if [ -z "$worker" ] || [ -z "$postgres" ]; then
    echo "FAIL no running worker or postgres container of the compose project; start it: scripts/dev.sh -d"
    exit 2
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
file="$work/bench_d${DAYS}_hr${HR_INTERVAL}_s${SEED}.ndjson"
jar="$work/cookies.txt"
# curl of Git for Windows needs a Windows path for -F file=@... (an MSYS path gives HTTP 000).
curl_file="$file"
if command -v cygpath > /dev/null 2>&1; then curl_file="$(cygpath -w "$file")"; fi

echo "== htgen --days $DAYS --hr-interval $HR_INTERVAL --seed $SEED"
uv run --project generator htgen --days "$DAYS" --hr-interval "$HR_INTERVAL" --seed "$SEED" --out "$file" \
    || { echo "FAIL htgen"; exit 1; }
size="$(wc -c < "$file" | tr -d ' ')"
lines="$(wc -l < "$file" | tr -d ' ')"
size_mb="$(awk -v s="$size" 'BEGIN { printf "%.1f", s / 1048576 }')"
echo "File: $size_mb MB, $lines lines"

# A fresh user in the zone htgen writes by default.
email="bench-$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n')@example.com"
code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -c "$jar" -X POST "$BASE_URL/api/auth/register" \
    -H 'Content-Type: application/json' -H 'X-Requested-With: ht' \
    --data "{\"email\": \"$email\", \"password\": \"bench-pass-123\", \"timezone\": \"Europe/Moscow\"}")"
[ "$code" = "201" ] || { echo "FAIL register $email -> HTTP $code"; exit 1; }
today="$(curl -s -m 10 -b "$jar" "$BASE_URL/api/auth/me" | json_field today)"
day="$(date -d "$today -1 day" +%F 2> /dev/null || python3 -c 'import sys, datetime; print(datetime.date.fromisoformat(sys.argv[1]) - datetime.timedelta(days=1))' "$today")"
echo "User: $email (today $today)"

read -r mem_before db_before <<< "$(memory)"

echo "== upload"
started="$(date +%s.%N)"
response="$(curl -s -b "$jar" -H 'X-Requested-With: ht' \
    -F "file=@$curl_file;type=application/x-ndjson" -w '\n%{http_code}' "$BASE_URL/api/ingest/files")"
uploaded="$(date +%s.%N)"
code="$(printf '%s\n' "$response" | tail -n 1)"
[ "$code" = "202" ] || { echo "FAIL upload -> HTTP $code $(printf '%s\n' "$response" | sed '$d')"; exit 1; }
job_id="$(printf '%s\n' "$response" | sed '$d' | json_field job_id)"
transfer="$(awk -v a="$started" -v b="$uploaded" 'BEGIN { print b - a }')"
echo "Uploaded in $(num "$transfer") s, job $job_id"

peak="${mem_before:-0}"
peak_db="${db_before:-0}"
samples=0
latencies="$work/latencies.txt"
: > "$latencies"
status=""
job=""
while [ "$(awk -v a="$uploaded" -v b="$(date +%s.%N)" 'BEGIN { print int(b - a) }')" -lt "$TIMEOUT_SEC" ]; do
    read -r mem db <<< "$(memory)"
    if [ -n "$mem" ]; then
        samples=$((samples + 1))
        peak="$(awk -v a="$peak" -v b="$mem" 'BEGIN { print (b > a ? b : a) }')"
    fi
    if [ -n "${db:-}" ]; then peak_db="$(awk -v a="$peak_db" -v b="$db" 'BEGIN { print (b > a ? b : a) }')"; fi
    timing="$(curl -s -o /dev/null -m 30 -b "$jar" -w '%{http_code} %{time_total}' "$BASE_URL/api/summary/day?date=$day")"
    if [ "${timing%% *}" = "200" ]; then
        awk -v t="${timing#* }" 'BEGIN { printf "%.1f\n", t * 1000 }' >> "$latencies"
    fi
    job="$(curl -s -m 10 -b "$jar" "$BASE_URL/api/ingest/jobs/$job_id")"
    status="$(printf '%s' "$job" | json_field status)"
    echo "  status=$status progress=$(printf '%s' "$job" | json_field progress) worker=${mem:-?} MiB"
    case "$status" in done | failed) break ;; esac
done
case "$status" in
    done | failed) ;;
    *) echo "FAIL job $job_id is still ${status:-unknown} after $TIMEOUT_SEC s; nothing written to $STATUS_FILE"; exit 1 ;;
esac

created="$(epoch "$(printf '%s' "$job" | json_field created_at)")"
finished="$(epoch "$(printf '%s' "$job" | json_field finished_at)")"
if [ -n "$created" ] && [ -n "$finished" ]; then
    processing="$(awk -v a="$created" -v b="$finished" 'BEGIN { print b - a }')"
    processing_how="задача: \`created_at\` → \`finished_at\`"
else
    processing="$(awk -v a="$uploaded" -v b="$(date +%s.%N)" 'BEGIN { print b - a }')"
    processing_how="от ответа 202 до статуса в опросе"
fi
total="$(awk -v a="$transfer" -v b="$processing" 'BEGIN { print a + b }')"
count="$(wc -l < "$latencies" | tr -d ' ')"
if [ "$count" -gt 0 ]; then
    p95="$(sort -n "$latencies" | awk -v n="$count" 'BEGIN { k = int(0.95 * n); if (k < 0.95 * n) k++; if (k < 1) k = 1 } NR == k { print }')"
    max="$(sort -n "$latencies" | tail -n 1)"
    latency_text="p95 $(num "$p95") мс, макс. $(num "$max") мс (запросов: $count)"
else
    latency_text="нет ответов 200"
fi
ok=0
if [ "$status" != "done" ]; then
    verdict="**нет: задача $status**"
elif awk -v t="$total" -v l="$LIMIT_SEC" 'BEGIN { exit !(t <= l) }'; then
    ok=1
    verdict="да ($(num "$total") с ≤ $LIMIT_SEC с)"
else
    verdict="**нет: $(num "$total") с > $LIMIT_SEC с**"
fi

counts() { printf '%s' "$job" | sed -n 's/.*"counts":{\([^}]*\)}.*/\1/p' | json_field "$1"; }
cpu="$(sed -n 's/^model name[[:space:]]*: //p' /proc/cpuinfo 2> /dev/null | head -n 1)"
[ -n "$cpu" ] || cpu="$(sysctl -n machdep.cpu.brand_string 2> /dev/null || echo "?")"
ram="$(awk '/^MemTotal/ { printf "%.1f", $2 / 1048576 }' /proc/meminfo 2> /dev/null)"
[ -n "$ram" ] || ram="$(sysctl -n hw.memsize 2> /dev/null | awk '{ printf "%.1f", $1 / 1073741824 }')"
IFS='|' read -r docker_version docker_cpu docker_mem <<< "$(docker info --format '{{.ServerVersion}}|{{.NCPU}}|{{.MemTotal}}')"
now="$(date +%Y-%m-%dT%H:%M:%S%:z 2> /dev/null || date -Iseconds)"

report="$work/report.md"
cat > "$report" << EOF
## Замер загрузки большого файла (\`scripts/bench_ingest.sh\`)

- Когда: $now (системное время); \`DAYS=$DAYS HR_INTERVAL=$HR_INTERVAL SEED=$SEED scripts/bench_ingest.sh\`.
- Машина: $(uname -sr); $cpu; ОЗУ $(num "${ram:-0}" 1) ГиБ. Docker $docker_version: $docker_cpu CPU, $(num "$(awk -v m="$docker_mem" 'BEGIN { print m / 1073741824 }')" 1) ГиБ.
- Файл: htgen \`--days $DAYS --hr-interval $HR_INTERVAL --seed $SEED\` (часы и телефон; пульс только с часов) —
  $(num "$size_mb" 1) МБ, $lines строк. Свежий пользователь \`$email\`, загрузка через \`$BASE_URL\`.

| Показатель | Значение |
|---|---|
| Передача файла (HTTP, \`POST /api/ingest/files\`) | $(num "$transfer" 1) с |
| Обработка ($processing_how) | $(num "$processing" 1) с |
| Всего | $(num "$total" 1) с |
| Пиковая память воркера (\`docker stats\`, замеров: $samples) | $(num "$peak") MiB (до загрузки $(num "${mem_before:-0}") MiB) |
| Пиковая память postgres (там же) | $(num "$peak_db") MiB (до загрузки $(num "${db_before:-0}") MiB) |
| \`GET /api/summary/day\` во время обработки | $latency_text |
| Записи: всего / новые / дубли / конфликты / некорректные | $(counts total) / $(counts new) / $(counts duplicate) / $(counts conflict) / $(counts invalid) |
| Статус задачи | $status |
| Ориентир SPEC §4: ≤ $LIMIT_SEC с | $verdict |
EOF
set_status_block "$STATUS_FILE" bench_ingest "$report"
echo
cat "$report"
echo "Written to $STATUS_FILE"
if [ "$ok" -eq 1 ]; then
    echo "OK   ingest of $size_mb MB took $(num "$total") s"
    exit 0
fi
echo "FAIL job $status, $(num "$total") s (limit $LIMIT_SEC s)"
exit 1
