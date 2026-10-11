#!/usr/bin/env bash
# Fresh clone check (SPEC §9 #1 and #21, ADR-015): clones the repository into a temporary folder,
# checks the line endings of the files for the containers, copies .env.example to .env, starts the
# stack with `docker compose up --build`, runs the clone's scripts/smoke.sh (health, frontend and its
# proxy, Mailpit, the demo user's login, SSE) and stops it with `down -v`. The result goes to the block
# between the fresh_clone_check marks of docs/STATUS.md.
#   scripts/fresh_clone_check.sh [--default-ports] [--keep]     (SOURCE=URL BRANCH=main from the environment)
# The stack of the clone is its own compose project, health-tracker-fresh: docker-compose.yml names
# the project health-tracker, so a clone in another folder would otherwise take over the containers
# and volumes of the dev stack. Its images are built under other names (IMAGE_PREFIX of
# docker-compose.yml: health-tracker-fresh-backend:dev, ...) and removed at the end, so the dev
# stack's images are not replaced by the clone's code.
# Ports: by default other ones (app 5175, api 8002, Mailpit 8027 and 1027, postgres 5435) through the
# environment, which compose prefers to .env — the dev stack keeps running. --default-ports uses the
# ports of .env.example (app http://localhost:5173), exactly what a fresh clone gets; stop the dev
# stack first: docker compose stop.
# SOURCE is `origin` of this repository by default: the check sees what is pushed. --keep leaves the
# clone and its stack running. Exit code: 0 — every check passed; 1 — something failed.
set -uo pipefail
cd "$(dirname "$0")/.."
root="$(pwd)"

default_ports=0
keep=0
for arg in "$@"; do
    case "$arg" in
        --default-ports) default_ports=1 ;;
        --keep) keep=1 ;;
        *) echo "usage: scripts/fresh_clone_check.sh [--default-ports] [--keep]" >&2; exit 2 ;;
    esac
done
SOURCE="${SOURCE:-$(git remote get-url origin)}"
BRANCH="${BRANCH:-main}"
STATUS_FILE="${STATUS_FILE:-docs/STATUS.md}"
project="health-tracker-fresh"

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

port_busy() {  # port_busy PORT: something accepts connections on localhost:PORT (7 — refused, 28 — timeout)
    local code
    curl -s -o /dev/null -m 1 "http://127.0.0.1:$1/" 2> /dev/null
    code=$?
    [ "$code" -ne 7 ] && [ "$code" -ne 28 ]
}

if [ "$default_ports" -eq 1 ]; then
    ports=(FRONTEND_PORT=5173 API_PORT=8000 MAILPIT_UI_PORT=8025 MAILPIT_SMTP_PORT=1025 POSTGRES_HOST_PORT=5433)
else
    ports=(FRONTEND_PORT=5175 API_PORT=8002 MAILPIT_UI_PORT=8027 MAILPIT_SMTP_PORT=1027 POSTGRES_HOST_PORT=5435)
fi
busy=()
for pair in "${ports[@]}"; do
    if port_busy "${pair#*=}"; then busy+=("$pair"); fi
done
if [ "${#busy[@]}" -gt 0 ]; then
    if [ "$default_ports" -eq 1 ]; then hint="stop the dev stack first: docker compose stop"; else hint="free them or use --default-ports"; fi
    echo "FAIL ports in use: ${busy[*]}; $hint"
    exit 1
fi
for pair in "${ports[@]}"; do export "${pair?}"; done

work="$(mktemp -d)"
clone="$work/health-tracker"
checks="$work/checks.md"
smoke_out="$work/smoke.txt"
: > "$checks"
: > "$smoke_out"
failed=0
started=0
commit="?"
begin_s=$SECONDS

check() {  # check NAME OK(0/1) DETAIL
    if [ "$2" -eq 1 ]; then
        printf '| %s | да | %s |\n' "$1" "$3" >> "$checks"
        echo "OK   $1 - $3"
    else
        printf '| %s | **нет** | %s |\n' "$1" "$3" >> "$checks"
        echo "FAIL $1 - $3"
        failed=1
    fi
}

cleanup() {
    if [ "$started" -eq 1 ] && [ "$keep" -eq 0 ]; then
        echo "== docker compose down -v (project $project)"
        (cd "$clone" && COMPOSE_PROJECT_NAME="$project" IMAGE_PREFIX="$project" docker compose down -v > /dev/null 2>&1)
        docker image rm "$project-backend:dev" "$project-frontend:dev" > /dev/null 2>&1
    fi
    if [ "$keep" -eq 0 ]; then rm -rf "$work"; fi
}

run() {
    echo "== git clone $SOURCE ($BRANCH) -> $clone"
    if git clone --quiet --branch "$BRANCH" "$SOURCE" "$clone"; then
        check "git clone" 1 "$SOURCE, ветка $BRANCH"
    else
        check "git clone" 0 "$SOURCE, ветка $BRANCH"
        return
    fi
    cd "$clone" || return
    commit="$(git log -1 --format='%h %s')"

    # §9 #21: scripts and files for the Linux containers keep LF in the checkout (.gitattributes).
    local eol not_lf count
    eol="$(git ls-files --eol -- '*.sh' '**/Dockerfile' 'Dockerfile' '*.conf')"
    count="$(printf '%s\n' "$eol" | grep -c .)"
    not_lf="$(printf '%s\n' "$eol" | grep -v 'w/lf' | awk 'NF { print $NF }' | paste -sd, -)"
    if [ "$count" -gt 0 ] && [ -z "$not_lf" ]; then
        check ".gitattributes: LF у *.sh, Dockerfile, *.conf" 1 "$count файлов, не LF: нет"
    else
        check ".gitattributes: LF у *.sh, Dockerfile, *.conf" 0 "$count файлов, не LF: ${not_lf:-?}"
    fi

    cp .env.example .env
    if [ -f .env ]; then check "cp .env.example .env" 1 ".env из .env.example"; else check "cp .env.example .env" 0 "нет .env"; fi

    export COMPOSE_PROJECT_NAME="$project"
    export IMAGE_PREFIX="$project"
    export APP_URL="http://localhost:$FRONTEND_PORT"
    echo "== docker compose up --build -d --wait (project $project)"
    local up_s=$SECONDS
    started=1
    if docker compose up --build -d --wait; then
        check "docker compose up --build" 1 "проект $project, $((SECONDS - up_s)) с до healthy"
    else
        check "docker compose up --build" 0 "проект $project"
        docker compose ps
        docker compose logs --tail 50
        return
    fi

    echo "== scripts/smoke.sh of the clone"
    API_URL="http://localhost:$API_PORT" MAILPIT_URL="http://localhost:$MAILPIT_UI_PORT" \
        FRONTEND_URL="http://localhost:$FRONTEND_PORT" bash scripts/smoke.sh > "$smoke_out" 2>&1
    local code=$?
    cat "$smoke_out"
    if [ "$code" -eq 0 ]; then ok=1; else ok=0; fi
    check "scripts/smoke.sh клона" "$ok" "exit $code; приложение http://localhost:$FRONTEND_PORT, вход demo@example.com"
}

run
cd "$root" || exit 1
report="$(mktemp)"
now="$(date +%Y-%m-%dT%H:%M:%S%:z 2> /dev/null || date -Iseconds)"
if [ "$default_ports" -eq 1 ]; then mode="порты .env.example (\`--default-ports\`)"; else mode="другие порты через окружение"; fi
if [ "$failed" -eq 1 ]; then verdict="**не пройдена**"; else verdict="пройдена, exit 0"; fi
{
    echo "## Проверка чистого клона (\`scripts/fresh_clone_check.sh\`)"
    echo
    echo "- Когда: $now (системное время), $((SECONDS - begin_s)) с; итог: $verdict."
    echo "- Машина: $(uname -sr); Docker $(docker version --format '{{.Server.Version}}'), Compose $(docker compose version --short); $(git --version)."
    echo "- Клон: $SOURCE, ветка $BRANCH, коммит \`$commit\`; проект compose \`$project\`, $mode: ${ports[*]}."
    echo
    echo "| Проверка | Пройдена | Подробности |"
    echo "|---|---|---|"
    cat "$checks"
    echo
    echo "Вывод \`scripts/smoke.sh\` клона:"
    echo
    echo '```text'
    tr -d '\r' < "$smoke_out"
    echo '```'
} > "$report"
cleanup
set_status_block "$STATUS_FILE" fresh_clone_check "$report"
rm -f "$report"
echo "Written to $STATUS_FILE"
if [ "$failed" -eq 1 ]; then echo "FAIL: fresh clone check"; exit 1; fi
echo "OK: fresh clone check"
exit 0
