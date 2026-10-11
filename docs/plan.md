# План реализации (на основе §8 `docs/SPEC.md`)

> Статус: **утверждён пользователем 2026-10-10T16:59:35+06:00**. Все вопросы закрыты, решения перечислены
> в разделе «Принятые решения» в конце файла. Шаг 0.1 начинается с переноса этих решений в `CLAUDE.md` и
> `docs/SPEC.md`: до этого переноса, если документы расходятся, **приоритет у этого плана**.
> Оставшиеся пометки «Допущение:» — решения агента, утверждённые вместе с планом.

---

## Как устроен план

### Шаг и этап
- **Этап** — пункт §8 SPEC. **Шаг** — часть этапа, которая помещается в одну сессию агента.
  Номер шага: `<этап>.<n>`, например `3.2`.
- Допущение: «одна сессия» — это не больше ~3–4 часов работы, ~15 изменённых файлов и одной новой подсистемы.
  Если шаг по ходу работы не укладывается, агент останавливается и предлагает разделить его. Начатый шаг
  самовольно не расширяется.
- **Решение (утверждено):** один шаг — одна новая сессия агента. Остановка с ожиданием «дальше»
  (`CLAUDE.md`, §2) делается **после каждого шага**, а не после этапа. В коммитах строка `Stage: 3.2` (номер шага).

### Тесты до кода
Каждый шаг идёт в таком порядке:
1. Пишутся тесты из списка «Тесты до кода». Запуск показывает, что они **красные по правильной причине**:
   функции нет или поведение не реализовано, а не ошибка импорта в самом тесте.
2. Красные тесты коммитятся **с маркером ожидаемого падения**, поэтому набор остаётся зелёным, а `CLAUDE.md`
   («нельзя коммитить красные тесты») не нарушается:
   - pytest: `@pytest.mark.xfail(strict=True, reason="step 3.2: not implemented")`;
   - Vitest: `test.fails(...)`; Playwright: `test.fail()`.
   Коммит `test(<scope>): <что> (red)`.
3. Пишется код. Strict-xfail на прошедшем тесте превращается в ошибку, поэтому маркеры **обязательно снимаются**
   в коммите с фичей `feat(<scope>): …`.
4. В WORKLOG записывается сводка красного прогона (`N xfailed`) и зелёного (`N passed`) с системным временем.

**Решение (утверждено):** так порядок «сначала тесты» виден прямо в истории git. Если тест на шаге появляется уже после кода
(например, регрессионный после найденного бага), это допустимо и отмечается в WORKLOG.

### Общий Done When (входит в каждый шаг, дальше не повторяется)
- [ ] `uv run --project backend ruff check . && uv run --project backend ruff format --check .` → exit 0
      (если трогали backend или generator, то и для generator).
- [ ] `scripts/test.ps1` (Windows) / `scripts/test.sh` → все unit и integration тесты зелёные, xfail-маркеров
      этого шага нет: `git grep -n "step <X.Y>: not implemented" -- ":!docs"` → пусто
      (`docs/` исключён: журналы цитируют эту строку, а WORKLOG править нельзя; ADR-019).
- [ ] Если трогали frontend: `npm --prefix frontend run check` (typecheck + lint + vitest + build) → exit 0.
- [ ] `python scripts/check_process.py --step <X.Y>` → exit 0. Скрипт проверяет: в WORKLOG есть записи «начат»
      и «завершён» с ISO-временем и смещением, время не убывает, WORKLOG только дополнялся; у всех коммитов шага
      Conventional Commits и строка `Stage: X.Y`; есть хотя бы один коммит `test(...)` раньше `feat(...)`.
- [ ] `git status --porcelain` → пусто; `git log origin/main..main` → пусто (всё запушено).
- [ ] Последний прогон CI на `main` зелёный: `gh run list --branch main --limit 1` → `completed success`
      (начиная с шага 0.3).

### Ручная проверка пользователем (не входит в Done When, но обязательна)
Автоматические проверки не заменяют ручные (решение пользователя). Порядок такой:
- в отчёте о шаге агент даёт раздел **«Проверьте руками»**: 2–5 действий в браузере или терминале с ожидаемым
  результатом. Если в шаге есть раздел «Ручная проверка», его пункты входят в отчёт обязательно;
- пользователь проходит их и только потом пишет «дальше». Если что-то не так, агент исправляет коммитом `fix(...)`
  в рамках того же шага;
- агент записывает в WORKLOG, что ручная проверка пройдена (со слов пользователя), с системным временем.

### Шаблон шага
> **Решение (утверждено):** используется этот шаблон.

```
### Шаг X.Y — Название
Этап SPEC: N · Зависит от: … · Критерии §9: закрывает #… / вклад в #…
Цель: одна фраза.
Объём: что входит.
Тесты до кода: файл::тест — что проверяет.
Done When: проверяемые пункты (тест или команда) сверх общего DoD.
Ручная проверка: что пользователь проверяет руками (если есть).
Не делаем на этом шаге: …
```

### Порядок и зависимости (кратко)
```
0.1 → 0.2 → 0.3
0.2 → 1.1 → 1.2 → 1.3 (+0.3)
0.1 → 2.1 → 2.2
1.2 + 2.1 → 3.1 → 3.2 → 3.3
1.2 → 4.1;  3.3 + 4.1 → 4.2 → 4.3 → 4.4
3.2 + 4.3 → 5.1;  5.1 + 1.3 → 5.2
4.4 + 5.2 → 6.1
4.4 + 5.1 → 7.1 → 7.2
4.4 + 7.1 → 8.1 → 8.2 → 8.3
1.1 + 4.1 → 9.1;  9.1 + 8.1 → 9.2
9.2 + 8.2 + 4.3 → 10.1
2.2 + 3.2 + 5.1 + 8.2 → 11.1
всё до 11.1 → 12.1 → 12.2 → 13.1 → 13.2
```

---

## Этап 0. Инициализация и журналы

### Шаг 0.1 — Репозиторий, журналы, проверка процесса
**Этап SPEC:** 0 · **Зависит от:** — · **Критерии §9:** вклад в #21, #22

**Статус:** [x] закрыт 2026-10-10T17:48:24+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-10T17:26:08+06:00.
Заметки: 18 ADR + ADR-019; сверх плана тест режима `--all`; ошибка в хелпере теста (`mkdir` без `parents`)
найдена после реализации и исправлена в `feat`; команда проверки маркеров в общем DoD исключает `docs/`
(ADR-019). Не выполнялось: ruff (не установлен, backend не трогали), `scripts/test.ps1` (появится на 0.2).

**Цель:** репозиторий, в котором с первого коммита есть правила, журналы и автоматическая проверка процесса.

**Объём:**
- **Первым делом — перенос утверждённых решений** (раздел «Принятые решения» в конце плана) в `CLAUDE.md`
  и `docs/SPEC.md`, одним коммитом `docs: apply approved plan decisions`. Плюс ADR на каждое решение
  в `DECISIONS.md` и дословные ответы пользователя в `PROMPTS.md`.
- `git init`, ветка `main`, у пользователя запрашивается URL GitHub, `git remote add`.
- `.gitattributes` (как в §4 SPEC) и `.gitignore` — **до** любых `.sh`.
- Коммит `CLAUDE.md`, `docs/SPEC.md`, `docs/plan.md`, `START_PROMPT.md`.
- `docs/WORKLOG.md` (запись «Старт проекта» с системным временем), `docs/DECISIONS.md` (ADR из SPEC: стек,
  очередь на Postgres, SSE, исходные записи и производные минуты, классификация, объединение по минутам,
  день пробуждения, история поясов, планировщик дайджеста, тесты до кода через strict-xfail),
  `docs/PROMPTS.md` (стартовый промпт и запрос на этот план), `docs/agent-session/README.md`.
- `scripts/check_process.py` — только stdlib, работает одинаково на Windows и Linux, поэтому пара `.ps1/.sh`
  не нужна.

**Тесты до кода** (`scripts/tests/test_check_process.py`, на временном git-репозитории):
- `test_worklog_timestamps_must_be_monotonic`
- `test_worklog_rejects_timestamp_without_offset`
- `test_step_requires_start_and_end_entries`
- `test_worklog_append_only_detects_deleted_lines`
- `test_commit_requires_conventional_format`
- `test_commit_requires_stage_trailer`
- `test_step_requires_test_commit_before_feat_commit`

**Done When:**
- [x] `python -m pytest scripts/tests -q` → зелёные.
- [x] `git check-attr eol -- scripts/x.sh` → `eol: lf`; `git check-attr eol -- Dockerfile` → `eol: lf`.
- [x] `python scripts/check_process.py --step 0.1` → exit 0.
- [x] `git remote -v` показывает GitHub; `git ls-remote origin main` совпадает с `git rev-parse main`.
- [x] Решения перенесены (проверка `git grep`, каждая команда находит совпадение):
      `git grep -n "после каждого шага" CLAUDE.md`, `git grep -n "Stage: X.Y" CLAUDE.md`,
      `git grep -n "xfail(strict=True" CLAUDE.md`, `git grep -n "Ручная проверка" CLAUDE.md`,
      `git grep -n "Vitest" docs/SPEC.md`, `git grep -n "docs/plan.md" CLAUDE.md`.
- [x] В `DECISIONS.md` есть ADR на каждое из решений 1–8: `git grep -c "^## ADR-" docs/DECISIONS.md` ≥ 18
      (10 из SPEC и 8 из плана).

**Ручная проверка:** пользователь читает diff коммита `docs: apply approved plan decisions` и подтверждает,
что решения перенесены верно.

**Не делаем на этом шаге:** код backend и frontend, docker, CI.

### Шаг 0.2 — Скелет backend и docker compose
**Этап SPEC:** 0 · **Зависит от:** 0.1 · **Критерии §9:** вклад в #1, #21

**Статус:** [x] закрыт 2026-10-10T19:50:05+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-10T18:04:39+06:00.
Заметки: postgres на хост-порту 5433 и compose без `.env` (ADR-020); `/api/health` пока проверяет только БД,
тик воркера — на шаге 3.2 (ADR-021); сверх плана — тест «health при недоступной БД отвечает < 5 с»;
один корневой `ruff.toml` на весь репозиторий, `scripts/` из шага 0.1 переформатированы под него (`cc60a14`).
Не выполнялось: CI (появится на шаге 0.3).

**Цель:** `docker compose up` поднимает postgres, mailpit, api и заглушку воркера; есть скрипты test и smoke.

**Объём:** `backend/` (uv, FastAPI, pydantic-settings, `GET /api/health` с проверкой БД), заглушка
`python -m app.worker` (цикл с логом), `Dockerfile`, `docker-compose.yml` (postgres 16, mailpit, api, worker),
`.env.example`, разметка тестов pytest (`unit`, `integration`, `mailpit`), фикстура тестовой БД,
`scripts/dev|test|smoke.{ps1,sh}`.

**Тесты до кода:**
- `backend/tests/unit/test_config.py::test_settings_load_from_env`
- `backend/tests/unit/test_config.py::test_app_env_defaults_to_dev`
- `backend/tests/integration/test_health.py::test_health_ok_when_db_up`
- `backend/tests/integration/test_health.py::test_health_503_when_db_unreachable`

**Done When:**
- [x] `docker compose up -d --build` → `docker compose ps` показывает все сервисы `running`/`healthy`.
- [x] `scripts/smoke.ps1` и `scripts/smoke.sh` → exit 0: `/api/health` отвечает 200, Mailpit `:8025` отвечает 200.
- [x] `git ls-files --eol "scripts/*.sh"` → у всех `i/lf`.

**Ручная проверка:** Открыть `http://localhost:8000/docs` и `http://localhost:8025`: обе страницы открываются.

**Не делаем на этом шаге:** frontend, миграции и модели, авторизация, CI.

### Шаг 0.3 — Скелет frontend и CI
**Этап SPEC:** 0 · **Зависит от:** 0.2 · **Критерии §9:** вклад в #1, #21, #22

**Статус:** [x] закрыт 2026-10-10T20:14:30+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-10T19:56:19+06:00.
Заметки: расширение smoke закоммичено красным без маркера (ADR-022); Tailwind v4, React 18, TypeScript ~6.0,
Node 22 в Docker и CI (ADR-023); MSW 2 вместо 3 — peer `@vitest/mocker`, иначе `npm ci` на Node 22 падает
(уточнение ADR-023); nginx на хост-порту 5173, CI с `fetch-depth: 0` и сервисом mailpit (ADR-024);
`setup-uv` закреплён на `v10.3.0`. README-скелет из SPEC §8 (этап 0) по решению пользователя — на шаге 13.2.

**Цель:** frontend за nginx на том же origin, что и API, и CI, который проверяет каждый push.

**Объём:** Vite + React + TS, Tailwind, `shadcn init` (button, card), **Vitest + React Testing Library + MSW**
(см. вопрос 3), `npm run check`, `nginx.conf` (proxy `/api`, `proxy_buffering off` для SSE), frontend `Dockerfile`,
сервис в compose. GitHub Actions: ruff и pytest с service-контейнерами postgres и mailpit, `npm run check`,
проверка LF для `*.sh`, `check_process.py --all`. Заполнить раздел «Команды» в `CLAUDE.md`.

**Тесты до кода:**
- `frontend/src/App.test.tsx::renders app shell with title «Трекер здоровья»`
- расширение smoke: `GET :5173/` → 200, `GET :5173/api/health` → 200 (proxy через nginx)

**Done When:**
- [x] `npm --prefix frontend run check` → exit 0.
- [x] `docker compose up -d --build && scripts/smoke.ps1` → exit 0, включая проверки frontend и proxy.
- [x] `gh run list --branch main --limit 1` → `completed success`.
- [x] Каждая команда из раздела «Команды» `CLAUDE.md` выполняется с exit 0 (демо и генератор ещё не существуют — шаги 13.1 и 2.1).

**Ручная проверка:** Открыть `http://localhost:5173`: видна оболочка «Трекер здоровья». На GitHub во вкладке Actions последний прогон зелёный.

**Не делаем на этом шаге:** страницы, авторизация, дизайн.

---

## Этап 1. БД, Clock и авторизация

### Шаг 1.1 — Alembic, тестовая БД, Clock
**Этап SPEC:** 1 · **Зависит от:** 0.2 · **Критерии §9:** вклад в #20

**Статус:** [x] закрыт 2026-10-10T20:37:40+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-10T20:18:24+06:00.
Заметки: async `Clock.now()`/`read()` с кешем сдвига 1 с, сдвиг только при `APP_ENV=dev`, `|offset| ≤ 10 лет`,
миграции командой контейнера api, воркер ждёт healthy api (ADR-025); интеграционные тесты в транзакции с откатом,
тест «воркер и api» коммитит и чистит `dev_clock`; сверх плана — 4 теста (UTC при чужом поясе, кеш, 422, регэксп).
Исправлена ошибка шага 0.3: nginx держал старый IP api после пересоздания контейнера → 502 (`82bddcc`).
На шаге 1.2: `POST /api/dev/clock` должен попасть под CSRF.

**Цель:** миграции, изоляция тестов и единый источник времени.

**Объём:** async engine, Alembic (первая миграция — `dev_clock`), фикстуры (мигрированная тестовая БД, откат
транзакции на каждый тест), `app.clock.Clock` (системное время + сдвиг из `dev_clock` в dev, короткий кеш),
`GET/POST /api/dev/clock` — роутер подключается только при `APP_ENV=dev`.

**Тесты до кода:**
- `unit/test_clock.py::test_now_is_utc_aware`
- `unit/test_clock.py::test_offset_applied_in_dev`
- `unit/test_clock.py::test_offset_ignored_in_prod`
- `integration/test_dev_clock_api.py::test_set_and_get_offset_in_dev`
- `integration/test_dev_clock_api.py::test_dev_routes_404_in_prod`
- `integration/test_dev_clock_api.py::test_worker_and_api_see_same_offset`
- `unit/test_invariants.py::test_no_direct_now_calls_outside_clock` — сканирует `app/` на `datetime.now(`,
  `date.today(`, `time.time(`; закрепляет инвариант из `CLAUDE.md`, §5
- `integration/test_migrations.py::test_upgrade_downgrade_upgrade_head`

**Done When:**
- [x] `docker compose exec api alembic current` → `(head)`.
- [x] `curl -X POST :8000/api/dev/clock` с `APP_ENV=prod` → 404.

**Не делаем на этом шаге:** пользователи, UI dev-панели.

### Шаг 1.2 — Авторизация (backend)
**Этап SPEC:** 1 · **Зависит от:** 1.1 · **Критерии §9:** вклад в #1, #20

**Статус:** [x] закрыт 2026-10-10T20:59:48+06:00 (принят пользователем, ручная проверка пройдена: пункты 1, 2, 4, 5; флаги cookie
проверены консультантом через curl, DevTools не открывали). Начат 2026-10-10T20:41:33+06:00.
Заметки: сессия — абсолютные 14 дней по Clock, `sessions.id = sha256(token)`; CSRF — ASGI-middleware до маршрутизации
(без заголовка на любой изменяющий запрос → 403, в том числе `/api/dev/clock`); Swagger `/docs` сам шлёт заголовок;
сид `python -m app.seed` после миграций (`DEMO_USER_*`, пароль следует за env); ADR-026. Сверх плана — 3 теста и
README-скелет (по просьбе пользователя). На шаге 1.3: frontend шлёт `X-Requested-With: ht` на всех изменяющих запросах.

**Цель:** регистрация, вход, выход и сессии по cookie с защитой от CSRF.

**Объём:** `users` (с `notify_email`, полями тихих часов), `user_timezones` (начальный пояс из тела регистрации),
`sessions`, argon2id, cookie `ht_session`, middleware для `X-Requested-With`, `register/login/logout/me`, истечение
сессии по `Clock`, идемпотентный сид демо-пользователя при старте api, зависимость `current_user`.
- Допущение: при регистрации frontend передаёт пояс браузера (`Intl…timeZone`), он становится первой записью
  истории. В SPEC начальный пояс не определён.

**Тесты до кода** (`integration/test_auth.py`, если не указано иное):
- `test_register_sets_httponly_samesite_lax_cookie`
- `test_register_duplicate_email_409`
- `test_register_invalid_timezone_422`
- `test_register_creates_initial_timezone_record`
- `test_login_wrong_password_401`
- `test_me_without_cookie_401`
- `test_mutating_request_without_csrf_header_403`
- `test_logout_invalidates_session`
- `test_session_expires_after_14_days_by_clock`
- `test_cookie_secure_flag_in_prod`
- `unit/test_passwords.py::test_hash_is_argon2id`
- `test_seed_demo_user_idempotent`

**Done When:**
- [x] `scripts/smoke.*` дополнен входом демо-пользователя → exit 0 (`/api/auth/me` отвечает 200 с cookie).

**Ручная проверка:** В Swagger (`/docs`) зарегистрироваться, войти, вызвать `/api/auth/me`. В DevTools → Application → Cookies у `ht_session` стоят HttpOnly и SameSite=Lax.

**Не делаем на этом шаге:** frontend, ограничение частоты входа, восстановление пароля, сид правил (он на шаге 8.1).

### Шаг 1.3 — Frontend: вход, layout, dev-панель
**Этап SPEC:** 1 · **Зависит от:** 1.2, 0.3 · **Критерии §9:** вклад в #1

**Статус:** [x] закрыт 2026-10-10T22:13:33+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-10T21:01:49+06:00.
Заметки: `react-router` 7 (8.x требует React 19); shadcn `Input` на `forwardRef` — компоненты shadcn v4 написаны
под React 19, в React 18 `ref` терялся; при 401 вне `/api/auth/*` — навигация на `/login` и очистка кеша; dev-панель
внизу layout, сдвиг в часах и кнопками, скрыта при 404; Vitest с `TZ=UTC`; ADR-027. Сверх плана — 4 теста до кода
и 1 после (выход). Smoke `GET :5173/login` был зелёным и до кода (SPA-fallback nginx с шага 0.3).

**Цель:** пользователь входит через UI и видит каркас приложения; в dev видна панель времени.

**Объём:** API-клиент (`credentials: include`, `X-Requested-With`, при 401 переход на `/login`), TanStack Query,
React Router, страницы входа и регистрации (react-hook-form + zod), защищённый layout с шапкой и пустыми пунктами
меню, `DevPanel` (текущее время `Clock`, установка сдвига, ссылка на Mailpit).

**Тесты до кода** (Vitest + RTL + MSW):
- `api/client.test.ts::adds X-Requested-With on mutating requests`
- `api/client.test.ts::redirects to /login on 401`
- `pages/Login.test.tsx::shows validation errors in Russian`
- `pages/Login.test.tsx::navigates to / after successful login`
- `pages/Register.test.tsx::sends browser timezone`
- `components/ProtectedRoute.test.tsx::unauthenticated user is redirected`
- `components/DevPanel.test.tsx::hidden when /api/dev/clock returns 404`
- `components/DevPanel.test.tsx::sets offset and shows new time`

**Done When:**
- [x] `docker compose up -d --build && scripts/smoke.*` → exit 0 (`GET :5173/login` → 200).

**Ручная проверка:** Зарегистрироваться, войти и выйти через UI. Сдвинуть время на dev-панели: показанное время меняется.

**Не делаем на этом шаге:** содержимое дашборда, колокольчик уведомлений.

---

## Этап 2. Формат данных и генератор

### Шаг 2.1 — Генератор: основа
**Этап SPEC:** 2 · **Зависит от:** 0.1 · **Критерии §9:** вклад в #3

**Статус:** [x] закрыт 2026-10-10T22:51:01+06:00 (принят пользователем, ручная проверка пройдена консультантом). Начат 2026-10-10T22:28:04+06:00.
Заметки: пакет `htgen` (hatchling, argparse, только `tzdata`); период — локальные даты включительно, только `--days` →
до вчера; пояс `Europe/Moscow` до `--tz` (шаг 2.2); `Random` на (seed, дата, назначение), дата владеет окном
`[00:00, 24:00)`, поэтому сон через полночь — два соседних интервала; `--devices`; телефон 90–97% на прогулках;
`--unaligned` — сдвиг 1–59 с; закрытый stdout → exit 0; ADR-028. Сверх плана — 5 тестов до кода и 1 после
(закрытый pipe); два теста сна поправлены после red-коммита (первая ночь может быть полной).

**Объём:** `generator/` (свой `pyproject`, argparse — допущение, без лишних зависимостей), `docs/DATA_FORMAT.md`,
meta-строка, модели часов и телефона, `--start/--end/--days`, `--seed`, `--hr-interval`, `--unaligned`, `--out`,
суточный профиль (сон, прогулки, сидячие периоды). Детерминизм обеспечивается отдельным seed на каждый день
(`seed + дата`) — это нужно для шага 2.2.

**Тесты до кода** (`generator/tests/`):
- `test_same_seed_byte_identical_output`
- `test_period_bounds_respected`
- `test_first_line_is_meta_with_devices`
- `test_every_timestamp_has_offset`
- `test_steps_intervals_do_not_overlap_per_device` (hypothesis по seed и периодам)
- `test_walks_recorded_by_both_devices_phone_90_to_97_percent`
- `test_unaligned_produces_non_minute_boundaries`
- `test_phone_has_no_hr`

**Done When:**
- [x] `uv run --project generator htgen --days 7 --seed 1 --out sample.ndjson` → exit 0, файл не пустой.

**Не делаем на этом шаге:** пропуски, смена пояса, сценарии, `--stream`.

### Шаг 2.2 — Генератор: пропуски, пояса, сценарии
**Этап SPEC:** 2 · **Зависит от:** 2.1 · **Критерии §9:** вклад в #3

**Статус:** [x] закрыт 2026-10-10T23:27:16+06:00 (принят пользователем, ручная проверка пройдена консультантом). Начат 2026-10-10T23:00:22+06:00.
Заметки: `Timeline` — смещение каждой метки по поясу в момент записи, окно даты от первого момента даты до первого
момента следующей (день переезда 31 ч / 17 ч); `--gap` — время без смещения местное, `@device` необязателен;
случайные пропуски по (seed, дата, устройство), 1 ч … `--gap-max-hours` (30), без перекрытий, с просмотром назад;
сценарии от конца периода, свои генераторы случайных чисел, `recovery` только отдельно, минимальная длина периода;
без новых опций вывод побайтно как на шаге 2.1; ADR-029. Сверх плана — тест с хешем вывода шага 2.1 и 14 случаев
ошибок разбора (после кода). Кракозябры в сообщениях об ошибке при pipe в Git Bash — не исправлять (решение пользователя).

**Цель:** генератор умеет пропуски, смену пояса и сценарии для каждого правила.

**Объём:** `--gap`, `--gap-prob`, `--gap-max-hours`, `--tz`, `--tz-change`, `--scenario`
(`short-sleep`, `sedentary`, `high-rhr`, `irregular`, `worse-week`, `recovery`).

**Тесты до кода:**
- `test_explicit_gap_has_no_records_for_device`
- `test_random_gaps_bounded_by_max_hours`
- `test_tz_change_switches_offset_at_instant`
- `test_overlapping_periods_same_seed_identical_records_in_intersection`
- `test_scenario_short_sleep_last_3_nights_under_6h`
- `test_scenario_sedentary_steps_and_active_minutes_low`
- `test_scenario_high_rhr_last_2_days_elevated`
- `test_scenario_irregular_bedtime_stdev_over_90`
- `test_scenario_worse_week_avg_sleep_drop_over_60`
- `test_scenario_recovery_fixes_each_condition`

**Done When:**
- [x] `htgen --days 90 --devices watch,phone --gap-prob 0.05 --seed 42 --out big.ndjson` → exit 0.

**Ручная проверка:** Сгенерировать файл с `--tz-change` и `--gap`, открыть его в редакторе и найти место смены смещения и пропуск.

**Не делаем на этом шаге:** `--stream` (шаг 11.1).

---

## Этап 3. Приём данных

### Шаг 3.1 — Исходные таблицы, парсер, классификация
**Этап SPEC:** 3 · **Зависит от:** 1.2, 2.1 · **Критерии §9:** вклад в #2, #8

**Статус:** [x] закрыт 2026-10-10T23:53:36+06:00 (принят пользователем, ручная проверка пройдена консультантом). Начат 2026-10-10T23:32:22+06:00.
Заметки: миграция 0003 (`btree_gist`, `devices`, минимальная `ingest_jobs`, `steps_raw` с `steps_raw_no_overlap`,
`sleep_raw`, `hr_point`); парсер — построчно с пределом строки 1 МиБ, `
`, пустые строки, BOM, смещения в байтах;
устройства из meta создаются при чтении meta; классификация — `COPY` в staging, SQL против сохранённых, затем пачка
в порядке строк; ADR-030. Сверх плана — 2 интеграционных теста (`invalid` в отчёте, изоляция пользователей) и тест
длинной строки (после кода). **Риск по скорости (указание пользователя):** 129 тыс. записей принимаются за 10,6 с →
около 4 мин на 3 млн только на приём, при цели SPEC §4 ≤ 5 мин на весь файл; на шаге 3.2 замерить загрузку файла
за 90 дней и записать результат.

**Цель:** сервисная функция `ingest_records(user, records) → Counts`, корректно делящая записи на
new/duplicate/conflict/invalid. HTTP пока нет.

**Объём:** миграция (`btree_gist`, `devices`, `steps_raw` с exclusion constraint, `sleep_raw`, `hr_point`,
минимальная `ingest_jobs`), потоковый NDJSON-парсер (номер строки и смещение в байтах), валидация (§7.2),
автосоздание устройств, staging через `COPY` и классификация SQL-запросом.

**Тесты до кода:**
- `unit/test_parser.py`: `test_valid_lines_parsed`, `test_invalid_json_is_invalid`, `test_timestamp_without_offset_invalid`,
  `test_end_not_after_start_invalid`, `test_bpm_out_of_range_invalid`, `test_interval_over_24h_invalid`,
  `test_byte_offsets_tracked`
- `integration/test_classify.py`: `test_new_records_inserted`, `test_same_key_same_value_duplicate`,
  `test_same_key_different_count_conflict_first_kept`, `test_overlapping_steps_different_bounds_conflict`,
  `test_adjacent_steps_intervals_both_new`, `test_overlapping_sleep_allowed`, `test_hr_same_ts_different_bpm_conflict`,
  `test_in_batch_duplicates_collapsed`, `test_device_autocreated_from_meta`,
  `test_unknown_device_created_as_phone_with_warning`
- `integration/test_generator_contract.py::test_htgen_output_zero_invalid_zero_conflict`

**Done When:** только общий DoD.

**Не делаем на этом шаге:** HTTP-загрузка, воркер, минутные таблицы, сводки.

### Шаг 3.2 — Очередь, воркер, загрузка файла
**Этап SPEC:** 3 · **Зависит от:** 3.1 · **Критерии §9:** вклад в #2, #6, #8

**Статус:** [x] закрыт 2026-10-11T00:36:57+06:00 (принят пользователем, ручная проверка пройдена консультантом). Начат 2026-10-11T00:01:51+06:00.
Заметки: миграция 0004 (`jobs`, `worker_heartbeat`, прогресс и контрольная точка в `ingest_jobs`); захват задачи —
`SKIP LOCKED` + advisory lock по пользователю, пробуждение по `LISTEN jobs` и тик 30 с, возврат зависших через 5 мин
по `Clock`; контрольная точка коммитится вместе с пачкой (возобновление точное, итог как без перерыва); SIGTERM
возвращает задачу в очередь сразу; `/api/health` → `worker.status`; потоковый multipart → volume `ingest`, 500 МБ;
`scripts/upload.{ps1,sh}`; ADR-031. Сверх плана — тест пробуждения по NOTIFY. **Замер:** 30 дней (554 тыс. записей) —
32 с, 90 дней (1,66 млн, 129 МБ) — 94 с, ≈ 170 с на 3 млн только на приём. **Ограничение:** в compose один воркер —
задачи разных пользователей идут по очереди (кандидат в `docs/NEXT.md`).
**Подсказка для ручной проверки (исправлено по замечанию пользователя):** файл htgen с другим `--seed` за те же
даты даёт тому же пользователю в основном `conflict`, а не `new` (пульс в те же моменты и пересекающиеся интервалы
шагов с другими значениями). Чтобы снова увидеть
`new`, загружайте новым пользователем или за другие даты (`--start`/`--end`).

> Указание пользователя при приёмке шага 3.1 (2026-10-10T23:53:36+06:00): замерить загрузку файла за 90 дней
> (`htgen --days 90`, приём через воркер) и записать результат в WORKLOG; риск — см. заметки шага 3.1.

**Цель:** файл загружается по HTTP и обрабатывается в фоне с прогрессом, контрольными точками и
возобновлением после сбоя.

**Объём:** `jobs` (`SKIP LOCKED`, пробуждение через `LISTEN`, возврат зависших задач в очередь по `Clock`), цикл
воркера и heartbeat (`/api/health` показывает последний тик), advisory lock по пользователю, прогресс и
контрольная точка в `ingest_jobs`, `POST /api/ingest/files` (запись в volume, лимит 500 МБ, ответ 202),
`GET /api/ingest/jobs[/{id}]`, первые 50 ошибок, `scripts/upload.{ps1,sh}`.

**Тесты до кода** (`integration/test_ingest_jobs.py`):
- `test_upload_returns_202_before_processing_done`
- `test_job_completes_with_counts_per_class`
- `test_reupload_same_file_zero_new_all_duplicate`
- `test_partially_overlapping_file_new_only_for_new_part`
- `test_worker_crash_after_batch_k_resumes_same_result` (тестовый хук «упасть после пачки k»)
- `test_stale_lock_requeued_after_5_min_by_clock`
- `test_same_user_jobs_sequential_different_users_parallel`
- `test_upload_over_limit_413`
- `test_job_of_other_user_404`
- `test_errors_capped_at_50`
- `test_health_reports_worker_heartbeat`

**Done When:**
- [ ] `htgen --days 30 --seed 7 --out f.ndjson && scripts/upload.ps1 f.ndjson` → итоговый статус задачи `done`.

**Ручная проверка:** Дважды загрузить один файл через `scripts/upload.ps1`: во второй раз в отчёте 0 `new`.

**Не делаем на этом шаге:** SSE, минутные таблицы, сводки.

### Шаг 3.3 — Минутные таблицы и пересборка
**Этап SPEC:** 3 · **Зависит от:** 3.2 · **Критерии §9:** **закрывает #5**, вклад в #8

**Статус:** [x] закрыт 2026-10-11T01:10:02+06:00 (принят пользователем, ручная проверка пройдена консультантом). Начат 2026-10-11T00:41:14+06:00.
Заметки: миграция 0005; пересчёт минут, задетых новыми записями, после каждой пачки в её транзакции (слитые
диапазоны, `DELETE` + один `INSERT … SELECT` на таблицу); шаги суммируются в `numeric`, хранятся в `real` —
пересборка совпадает с инкрементальным расчётом побитово; сон — объединение интервалов (`range_agg`), порог 30 с;
`rebuild_user` под advisory lock пользователя, кусками по 7 дней; `htadmin` — обёртка над `python -m app.cli`;
ADR-032. Сверх плана — тест командной строки `htadmin`. Ошибка в ожидании теста покрытия (10 с сна — не минута сна)
найдена после кода и исправлена в `feat`. **Замер (90 дней, 1,66 млн записей):** с пересчётом 85–86 с на прогретом
стеке (127 с — первый прогон после пересборки), без пересчёта 66 с → пересчёт ≈ +20 с (~30 %); память воркера
≈ 60 МБ; повтор — 30 с; `htadmin rebuild` — 11,4 с. Оценка на 3 млн записей — 2,5–4 мин.

**Цель:** производные `steps_minute`, `sleep_minute` и `coverage_minute` из исходных записей; шаги не теряются.

**Объём:** `services/minutes.py` (вклады интервалов в минуты, пересчёт затронутых диапазонов после каждой пачки),
CLI `htadmin rebuild --user`.

**Тесты до кода:**
- `integration/test_minutes.py::test_adjacent_unaligned_intervals_minute_0801_equals_60`
- `integration/test_minutes.py::test_sum_steps_minute_equals_sum_raw` (hypothesis, непересекающиеся интервалы)
- `integration/test_minutes.py::test_sleep_minute_marked_if_covered_30s_or_more`
- `integration/test_minutes.py::test_coverage_from_steps_sleep_and_hr`
- `integration/test_minutes.py::test_recompute_idempotent`
- `integration/test_rebuild.py::test_rebuild_equals_incremental`
- `integration/test_rebuild.py::test_reupload_leaves_derived_tables_unchanged` (сравнение хешей таблиц)

**Done When:**
- [ ] `docker compose exec api htadmin rebuild --user demo@example.com` → exit 0.

**Не делаем на этом шаге:** объединение устройств, локальные даты, сводки.

---

## Этап 4. Объединение, дни, сводки

### Шаг 4.1 — Локальное время по истории поясов
**Этап SPEC:** 4 · **Зависит от:** 1.2 · **Критерии §9:** вклад в #17, #18

**Статус:** [x] закрыт 2026-10-11T01:29:26+06:00 (принят пользователем, ручная проверка пройдена консультантом). Начат 2026-10-11T01:14:17+06:00.
Заметки: чистый класс `TzHistory(records)` (строки `UserTimezone` подходят как есть): `zone_at`, `local_date`,
`ranges_for_date` → UTC-интервалы `[start, end)`, отсортированные, соседние куски склеены. Запись действует с
`valid_from` включительно; первый пояс действует и до своего `valid_from` (данные до регистрации); сутки начинаются с
первого мгновения даты (00:00, `fold=0`; в «дыре» перевода — её конец, Сантьяго 01:00); ADR-033. Загрузчик истории
из БД — на шагах 4.2–4.3. Сверх плана — тесты первого пояса до регистрации и проверки ввода. **Важно для шагов
12–13:** дни считаются по поясу пользователя, а `htgen` по умолчанию пишет `Europe/Moscow` — в демо-скрипте и e2e
генератор нужно запускать с `--tz` пояса пользователя.

**Цель:** `localtime.py`: время → локальная дата и локальная дата → набор UTC-интервалов, по истории поясов.

**Тесты до кода** (`unit/test_localtime.py`):
- `test_local_date_uses_tz_active_at_event`
- `test_msk_to_nyc_move_day_is_31h`
- `test_westward_move_after_midnight_splits_day_into_two_ranges`
- `test_eastward_move_short_day`
- `test_every_minute_maps_to_exactly_one_date` (hypothesis: интервалы дат разбивают время без пересечений и дыр)
- `test_dst_transition_23h_and_25h_days`
- `test_ranges_for_date_roundtrip`

**Done When:** только общий DoD.

**Не делаем на этом шаге:** API смены пояса и пересчёт (шаг 10.1).

### Шаг 4.2 — Объединение устройств и дневные метрики (без сна)
**Этап SPEC:** 4 · **Зависит от:** 3.3, 4.1 · **Критерии §9:** **закрывает #4**, вклад в #9

**Статус:** [x] закрыт 2026-10-11T08:36:28+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T08:11:49+06:00.
Заметки: `merge.py` — чистые `device_order` (часы → телефоны, `created_at`, при равенстве `external_id`),
`merge_steps` (источник — первое покрывающее устройство, без шагов — 0), `merge_hr` (первое устройство с пульсом в
минуте); `metrics.py` — `day_metrics` и чистая `summarize_day` (ношение, статус, шаги, активные минуты, пульс в покое
p10 минутных медиан при ≥ 60 минутах с ровно 0 шагов, пик — максимум минутных медиан); `localtime.load_tz_history`;
`docs/MERGE_RULES.md`, ADR-034. Сон, `daily_summaries` и пересчёт «грязных» дат — шаг 4.3. **Перед демо (13.1):**
очистить демо-пользователя и загрузить заново одним файлом — сейчас в dev-БД смесь данных разных seed.
**Известная ошибка вне шага:** `scripts/upload.sh` в Git Bash с абсолютным путём `/c/...` → `HTTP 000` (относительный
путь и `upload.ps1` работают) — исправить коммитом `fix(scripts)` на одном из следующих шагов.

**Цель:** `merge.py` (значение и `source_device_id` на минуту) и метрики шагов, активности, пульса и ношения.

**Тесты до кода:**
- `unit/test_merge.py::test_merged_minute_single_source_never_sum` (hypothesis)
- `unit/test_merge.py::test_walk_both_devices_watch_wins_2000`
- `unit/test_merge.py::test_watch_covered_minute_without_steps_is_zero_not_phone`
- `unit/test_merge.py::test_earliest_registered_device_wins_among_same_kind`
- `unit/test_merge.py::test_hr_phone_points_only_where_watch_missing`
- `integration/test_day_metrics.py::test_phone_only_walk_plus_both_walk_day_equals_5000`
- `integration/test_day_metrics.py::test_status_boundaries_0_719_720_minutes`
- `integration/test_day_metrics.py::test_no_data_day_steps_null_not_zero`
- `integration/test_day_metrics.py::test_resting_hr_p10_requires_60_rest_minutes`
- `integration/test_day_metrics.py::test_peak_hr_ignores_single_spike`
- `integration/test_day_metrics.py::test_active_minutes_threshold_100`

**Done When:** только общий DoD.

**Не делаем на этом шаге:** сон, сохранение в `daily_summaries`, API.

### Шаг 4.3 — Сон, валидность ночи, `daily_summaries`, «грязные» даты
**Этап SPEC:** 4 · **Зависит от:** 4.2 · **Критерии §9:** **закрывает #17**, вклад в #2, #7, #9, #18

**Статус:** [x] закрыт 2026-10-11T09:11:49+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T08:43:34+06:00.
Заметки: `services/sleep.py` — чистые сессии (разрывы ≤ 30 мин, длина — минуты сна, от 30 мин, дата — последняя минута
сна, основная — самая длинная, при равенстве поздняя); `merge.merge_sleep`; сон в `metrics.compute_day` (окно 48 ч назад
/ 2 ч вперёд). **SPEC F6 уточнён (ADR-035):** `night_valid` — в окне [начало − 60 мин, конец + 60 мин] нет пропуска
данных длиннее 30 мин. `daily_summaries` (миграция 0006) — производная, день `no_data` строки не имеет;
`summaries.affected_dates` (±91 мин и дни пробуждения задетых сессий), даты ждут в `ingest_jobs.dirty_dates` и
пересчитываются после первой пачки, затем не реже раза в ~2 с и в конце задачи; `htadmin rebuild` пересобирает и сводки;
`TzHistory.dates_between`; ADR-036. Сверх плана — property-тест `dates_between` и тест падения воркера между сбросами.
**Для 4.4:** день без строки в `daily_summaries` = `no_data`. **Для 5.1:** событие `summary.updated {dates}` слать в месте
сброса (`flush_summaries` в `worker/handlers.py`). **Для 10.1:** `recompute_dates` принимает любой набор дат.

**Цель:** полная дневная сводка, которая пересчитывается по ходу загрузки.

**Объём:** сессии сна и атрибуция по дню пробуждения, основная сессия, `night_valid`, таблица `daily_summaries`,
отслеживание «грязных» дат при загрузке (сброс не реже раза в ~2 с), включение сводок в `htadmin rebuild`.

**Тесты до кода:**
- `unit/test_sleep.py::test_sleep_2340_0710_attributed_to_wake_day`
- `unit/test_sleep.py::test_gap_le_30_min_merged_gt_30_split`
- `unit/test_sleep.py::test_session_under_30_min_ignored`
- `unit/test_sleep.py::test_main_session_is_longest`
- `unit/test_sleep.py::test_night_valid_requires_data_60_min_around_and_no_inner_gap_over_30`
- `unit/test_sleep.py::test_watch_removed_mid_night_makes_night_invalid`
- `integration/test_summaries.py::test_night_valid_on_partial_day`
- `integration/test_summaries.py::test_tz_move_period_sum_equals_sum_of_merged_minutes`
- `integration/test_summaries.py::test_summaries_exist_before_job_done` (хук «пауза после пачки k»)
- `integration/test_summaries.py::test_only_dirty_dates_recomputed`
- `integration/test_summaries.py::test_rebuild_reproduces_summaries`

**Done When:**
- [ ] `docker compose exec api htadmin rebuild --user demo@example.com` → exit 0, и после него `daily_summaries`
      совпадает с исходным (проверяется тем же тестом).

**Не делаем на этом шаге:** недельная сводка, HTTP API сводок, события.

### Шаг 4.4 — Недельная сводка и API сводок
**Этап SPEC:** 4 · **Зависит от:** 4.3 · **Критерии §9:** **закрывает #10 (backend)**, вклад в #9

**Статус:** [x] закрыт 2026-10-11T09:40:48+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T09:15:42+06:00.
Заметки: `services/weekly.py` (ISO-неделя `YYYY-Www`, дни без строки — `no_data` с `null`, базы F7, разница) и
`api/summary.py`; формат и правила — `docs/API.md`, ADR-038. **SPEC F7 уточнён (ADR-037):** разница по сну в дневной
сводке — только если обе ночи валидны, остальные метрики — по любым непустым значениям. Разница `{abs, pct}` до 0,1 от
показанных значений, `pct = null` при прошлом 0; средние недели до 0,1, пик — максимум; `range` ≤ 366 дней; параметры
обязательны, неверные → 422. **Для 6.1:** «N из 7» — `metrics.<m>.days`, разницу не пересчитывать на клиенте, статус
дня для пометки «неполные» — `days[].status`. **Для 8.x:** `week_metrics` и `parse_week` пригодны для R4 (сон
недели по валидным ночам).

**Цель:** `GET /api/summary/day|week|range` со сравнением с прошлым периодом и базами усреднения.

**Тесты до кода** (`integration/test_summary_api.py`):
- `test_day_summary_with_delta_vs_previous_day`
- `test_day_delta_null_when_previous_no_data`
- `test_week_sleep_avg_over_valid_nights_including_partial_days`
- `test_week_steps_avg_over_complete_days_only`
- `test_week_returns_base_counts`
- `test_week_empty_base_returns_null`
- `test_range_returns_status_per_day_with_nulls`
- `test_iso_week_param_edges_w01_w53`
- `test_summary_returns_only_own_data`

**Done When:** только общий DoD.

**Ручная проверка:** В `/docs` вызвать `/api/summary/week` для недели с пропуском: видны базы «N из 7» и `null` вместо нуля.

**Не делаем на этом шаге:** UI, цели в сводке.

---

## Этап 5. Реальное время и загрузка в UI

### Шаг 5.1 — Шина событий и SSE
**Этап SPEC:** 5 · **Зависит от:** 3.2, 4.3 · **Критерии §9:** вклад в #7, #19

**Статус:** [x] закрыт 2026-10-11T10:22:16+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T09:43:52+06:00.
Заметки: `services/events.py` — `publish` (`NOTIFY user_events` в транзакции вызывающего, `{user_id, type, data}`),
`publish_summary_updated` (части < 8000 байт), `EventHub` (одно LISTEN-соединение `ht-events` на процесс API, фон в
lifespan, переподключение 0,2 → 5 с, после него `resync`); `GET /api/events` на sse-starlette (`ready` первым, keep-alive
15 с, вход своей короткой сессией БД, без LISTEN 5 с → 503). Воркер: `ingest.progress` (queued/processing/после пачек не
чаще раза в 1 с), `ingest.done` (done/failed, `counts` как в отчёте), `summary.updated` при сбросе дат; ADR-039,
`docs/API.md`. Тесты SSE — на настоящем uvicorn (ASGI-транспорт httpx не отдаёт поток). **Для 5.2:** `useEvents` на
`resync` делает то же, что после переподключения EventSource (перезапрос всего); nginx уже с `proxy_buffering off`.
**Для 7.x/8.x/10.1:** свои события — через `events.publish` в транзакции изменения.

**Цель:** события от воркера доходят до всех открытых вкладок пользователя за ≤ 2 с.

**Объём:** `events.py` (`NOTIFY`/`LISTEN`, переподключение), `GET /api/events` (sse-starlette, keep-alive),
события `ingest.progress`, `ingest.done`, `summary.updated`. Ручная проверка из §8 SPEC заменена тестами.

**Тесты до кода** (`integration/test_events.py`):
- `test_two_sse_clients_same_user_both_receive_within_2s`
- `test_other_user_does_not_receive_events`
- `test_ingest_emits_progress_at_least_every_2s_and_done`
- `test_summary_updated_contains_dates`
- `test_large_date_set_split_into_payloads_under_8kb`
- `test_events_requires_auth_401`
- `test_listener_recovers_after_db_connection_drop`

**Done When:** только общий DoD.

**Не делаем на этом шаге:** UI, события целей и правил (добавляются на своих шагах).

### Шаг 5.2 — Страница «Загрузка» и `useEvents`
**Этап SPEC:** 5 · **Зависит от:** 5.1, 1.3 · **Критерии §9:** вклад в #6, #8, #19

**Статус:** [x] закрыт 2026-10-11T10:51:39+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T10:24:59+06:00.
Заметки: `hooks/useEvents.ts` — один EventSource на вкладку в `AppLayout`, таблица `handlers` «событие → ключи»:
`summary.updated` — точечно день / ISO-неделя (`lib/dates.ts::isoWeek`) / диапазоны с этими датами, `ingest.progress`
известной задачи — в кэш списка без запроса, `ingest.done` — список загрузок и устройства; повторное `ready` и `resync`
— перезапрос всего; `CLOSED` — свой повтор 1 → 30 с и перепроверка `/api/auth/me`. Страница `/upload`: XHR
`api/ingest.ts::sendFile`, состояние передачи в `lib/transfer.ts` (переживает уход со страницы), бар «Обработка» — задача
вкладки или последняя активная; история с «Ошибки (N)». Smoke ждёт `event: ready` через `:5173` ≤ 2 с (ловит медленный
поток, проверено заглушкой). ADR-040. Ручная проверка: 15,7 МБ в двух вкладках; перетаскивание 90-дневного файла мышью
пользователем не подтверждено. **Для 6.1:** ключи сводок — `lib/queryKeys.ts::summaryKeys` (`["summary","day"|"week"|
"range",…]`), тогда перезапрос по `summary.updated` работает без своего кода; устройства — `devicesKey`; сетку страницы
делать с `grid-cols-1` (`minmax(0,1fr)`), иначе широкие таблицы и графики растягивают страницу на 375 px.

**Цель:** загрузка с двумя прогресс-барами и история загрузок; интерфейс сам обновляется по событиям.

**Тесты до кода:**
- `hooks/useEvents.test.ts::maps each event type to invalidated query keys`
- `hooks/useEvents.test.ts::refetches everything after reconnect`
- `pages/Upload.test.tsx::upload bar follows XHR progress`
- `pages/Upload.test.tsx::processing bar follows ingest.progress`
- `pages/Upload.test.tsx::history shows new/duplicate/conflict/invalid and expandable errors`
- smoke: первый байт SSE через nginx `:5173/api/events` приходит ≤ 2 с (буферизация выключена)

**Done When:**
- [ ] `scripts/smoke.*` с проверкой SSE через nginx → exit 0.

**Ручная проверка:** Открыть «Загрузку» в двух вкладках и загрузить в одной 90-дневный файл: прогресс движется в обеих, во время обработки можно переходить по страницам. (Это ручная проверка из §8 SPEC, этап 5.)

**Не делаем на этом шаге:** дашборд.

---

## Этап 6. Дашборд

### Шаг 6.1 — Устройства и дашборд
**Этап SPEC:** 6 · **Зависит от:** 4.4, 5.2 · **Критерии §9:** **закрывает #3, #10 (UI)**, вклад в #9

**Статус:** [x] закрыт 2026-10-11T11:30:54+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T10:58:48+06:00.
Заметки: `GET/PATCH /api/devices` (`last_data_at` — последняя минута `coverage_minute`, имя 1–100, событие
`devices.changed`); `today` в ответах `/api/auth/*` по `Clock` и истории поясов (решение пользователя); дашборд — день
или ISO-неделя из адреса (`/?date=…`, `/?view=week&week=…`), без них — `today`; `SummaryCard`, `DaysChart` (Recharts 3.10),
`GapBar` (пропуск — штриховка «нет данных», неполный день — светлый столбец «неполн.»); подписи и форматы —
`lib/metrics.ts`; ADR-041. Замечания приёмки: (1) после проверок со сдвигом dev clock — всегда «Сброс» и
`offset_seconds = 0`; (2) `--gap-prob` даёт пропуск одного устройства, его закрывает второе — **для 12.1 и 13.1** пропуск
на дашборде делать `--gap FROM/TO` без `@device`; (3) «Последние данные» устройств сейчас в поясе браузера — **для
10.1:** показывать в поясе пользователя. **Для 7.2:** «сегодня» для тостов — `useMe().data.today`; новые события —
строкой в `handlers` `useEvents.ts`.

**Цель:** день и неделя на дашборде с пропусками, неполными днями и сравнением; страница устройств.

**Объём:** `GET/PATCH /api/devices`, страницы «Дашборд» и «Устройства», компоненты `SummaryCard`, `GapBar`,
графики Recharts (`null` показывается как штрихованный пропуск).

**Тесты до кода:**
- `integration/test_devices_api.py::test_list_and_rename`
- `integration/test_devices_api.py::test_rename_other_user_device_404`
- `pages/Dashboard.test.tsx::no_data day shows «нет данных», not 0`
- `pages/Dashboard.test.tsx::partial day shows «неполные данные (носили N ч)»`
- `pages/Dashboard.test.tsx::missing comparison shows «нет данных для сравнения»`
- `pages/Dashboard.test.tsx::week cards show base counts («сон: 6 из 7 ночей»)`
- `components/GapBar.test.tsx::null value rendered as hatched gap`
- `pages/Dashboard.test.tsx::refetches on summary.updated`

**Done When:** только общий DoD.

**Ручная проверка:** Держать дашборд открытым во время обработки 90-дневного файла: сводка заполняется по ходу. День с пропуском показан как «нет данных», неполный день — с подписью. При ширине 375 px в DevTools ничего не наезжает. (Ручная проверка из §8 SPEC, этап 6.)

**Не делаем на этом шаге:** прогресс целей (7.2), полировка вёрстки (проверка 375 px — шаг 13.1).

---

## Этап 7. Цели

### Шаг 7.1 — Цели и достижения (backend)
**Этап SPEC:** 7 · **Зависит от:** 4.4, 5.1 · **Критерии §9:** вклад в #11

**Статус:** [x] закрыт 2026-10-11T13:34:08+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T12:05:37+06:00 (Codex),
продолжен 2026-10-11T13:03:28+06:00 в Claude Code.
Заметки: ADR-043. Версия цели действует с локальной даты `valid_from`, до первой — 8000 шагов / 8 ч; `GET/PUT /api/goals`
(`[{kind, target, valid_from}]`, шаги 100–100 000, сон 1–16 ч); у дней сводок `goals.{kind} = {target, percent, achieved}`
(процент вниз), у недель `{achieved_days, of: 7}`; цель выполнена при значении ≥ цели при любом статусе дня.
Достижения — `services/goals.py::record_achievements` в конце каждого `recompute_dates` (загрузка, `htadmin rebuild`) и
после `PUT`, изменившего цель (сегодняшний день); один раз на вид и дату; события `notification.created` → `goal.achieved`
(`show_toast` — сегодня/вчера по `Clock`), `goal.changed`, новое `notifications.read`; `GET /api/notifications` →
`{items, unread}`, `POST /api/notifications/read` `{ids}` или `{}`. Записанное достижение не отменяется, если значение
потом уменьшилось. Данные, загруженные до 7.1, достижений не имеют — их создаёт `htadmin rebuild` (без тостов, кроме
сегодня/вчера). **Для 7.2:** четыре события — строками в `handlers` `useEvents.ts`; тост — только по `show_toast`;
счётчик — `unread` из `GET /api/notifications`. **Для 8.1 (R2):** цель дня — `GoalBook.target("steps", day)`.
**Для 10.1:** пересчёт после смены пояса через `recompute_dates` сам создаст достижения.

**Объём:** `goals` с историей, `GET/PUT /api/goals`, прогресс в API сводок, `goal_achievements` при пересчёте,
`notifications` и `GET/POST` для них, события `goal.achieved` (с признаком «показать тост»),
`notification.created`, `goal.changed`.

**Тесты до кода** (`integration/test_goals.py`):
- `test_default_goals_8000_steps_8h_sleep`
- `test_put_creates_new_version_past_days_use_old_target`
- `test_achievement_created_once_when_data_crosses_threshold_mid_ingest`
- `test_reupload_does_not_create_second_achievement`
- `test_toast_flag_only_for_today_and_yesterday_by_clock`
- `test_sleep_goal_counted_on_wake_day`
- `test_week_progress_n_of_7`
- `test_notifications_list_mark_read_and_isolation`

**Done When:** только общий DoD.

**Не делаем на этом шаге:** UI.

### Шаг 7.2 — Цели в UI, колокольчик, тосты
**Этап SPEC:** 7 · **Зависит от:** 7.1, 6.1 · **Критерии §9:** вклад в #11

**Статус:** [x] закрыт 2026-10-11T14:02:32+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T13:36:45+06:00.
Заметки: ADR-044. Страница `/goals` (форма react-hook-form + zod, диапазоны API, сон с запятой; текущая ISO-неделя по
`today`), `GoalProgress` в карточках «Шаги» и «Сон» дашборда (шкала до 100 %, текст — настоящий процент), у недели —
«цель выполнена N из 7 дней»; тосты `sonner` только по `show_toast` (`lib/toasts.ts`, `id` = `notification_id`);
колокольчик `Bell` (radix Popover, `unread`, последние 50, «Прочитать все»); в `handlers` `useEvents.ts` — `goal.changed`,
`notification.created`, `notifications.read`, `goal.achieved`. Найдено на живой проверке: shadcn `Button` не пробрасывал
`ref` на React 18 — список колокольчика оставался за экраном; `Button` переведён на `forwardRef` (fix, регрессионный
тест). **Для 8.3:** уведомления о рекомендациях — новый `type` в `Bell.tsx::describe` и строки в `handlers`; новые
триггеры Radix (`asChild`) — только на компонентах с `forwardRef`. **Перед демо (13.1) — чистка демо-пользователя:** после
живой проверки со сдвигом dev clock (+1 день) у `demo@example.com` остались загруженные данные, сводки и достижения
(уведомления) за 12.10 и две версии цели шагов с `valid_from` 2026-10-12 (3000, затем 8000); после отката часов
`GET /api/goals` показывает версию из «будущего». Перед 13.1 пересоздать демо-данные (удалить пользователя или его
данные за даты позже реального «сегодня» и версии целей с будущим `valid_from`) и проверить `GET /api/dev/clock` →
`offset_seconds: 0`.

**Тесты до кода:**
- `pages/Goals.test.tsx::validates and saves goals`
- `components/GoalProgress.test.tsx::shows percent of target`
- `components/Toasts.test.tsx::goal.achieved with toast=true shows toast`
- `components/Toasts.test.tsx::goal.achieved with toast=false shows no toast`
- `components/Bell.test.tsx::unread count updates on notification.created`

**Done When:** только общий DoD.

**Ручная проверка:** Поставить цель ниже сегодняшних шагов и загрузить данные за сегодня: тост появляется в обеих вкладках, на колокольчике +1.

**Не делаем на этом шаге:** уведомления о рекомендациях (8.3).

---

## Этап 8. Правила и рекомендации

### Шаг 8.1 — Движок правил, R1, R2
**Этап SPEC:** 8 · **Зависит от:** 4.4, 7.1 · **Критерии §9:** вклад в #9, #12, #13

**Статус:** [x] закрыт 2026-10-11T14:40:19+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T14:08:23+06:00.
Заметки: ADR-045. `services/rules/`: `base.py` (`Day`, `Facts`, `Verdict` — `fire`/`close`/`hold`/`unknown`, `Rule`),
`engine.py` (`plan_actions` — машина состояний, `evaluate_user` — в транзакции вызывающего), `r1.py`, `r2.py`
(`PARAMS`), `catalog.py`; миграция 0010 — `rules` (сид R1–R6), `user_rules` (нет строки — включено), `recommendations`
(`uq_recommendations_open`). Закрытие — только по опорной дате; R1: сегодня, если ночь валидна, иначе вчера; R2 — вчера.
Оценка — в транзакции, завершающей задачу загрузки. **Для 8.2:** R3–R6 — в `engine.RULES` (`LOOKBACK` — по
`window_days`, R3 нужно 16 дней, R4 — 3 недели); тесты опорных дат и `test_evaluated_after_ingest_done` (вызов уже
есть в `worker/handlers.py`). **Для 8.3:** уведомление, события `recommendation.*` — в `evaluate_user` (там уже лог
`recommendation_opened`/`_resolved`); `resolve_reason` для отключения — `closed_rule_disabled` в `status`.
**Исправлено на шаге (ошибка 4.3, ADR-046):** сессия сна на краю данных пользователя не относится ни к какому дню, пока
не придут продолжение или данные после неё (SPEC F5). Уже посчитанные сводки старых пользователей (в т. ч. демо)
меняются только при пересчёте — перед 13.1 сделать `htadmin rebuild` (вместе с чисткой из заметки 7.2). Тестовые
пользователи живой проверки: `rules81@example.com` (данные до 13.10), `edge81@example.com`.

**Объём:** `rules` (сид R1–R6 с описаниями), `user_rules`, `recommendations` (частичный уникальный индекс),
интерфейс правила (`fire` / `close` / `unknown`), машина состояний, R1, R2, оценка правил после завершения загрузки.

**Тесты до кода:**
- `unit/test_rule_engine.py`: `test_opens_when_condition_true`, `test_no_duplicate_while_still_true_next_day`,
  `test_resolves_on_close_condition`, `test_unknown_leaves_state_unchanged`, `test_disabled_rule_not_evaluated`
- `integration/test_rule_engine_db.py::test_partial_unique_index_prevents_two_open`
- `unit/test_r1.py`: `test_fires_on_3_valid_nights_under_6h`, `test_invalid_night_in_window_unknown`,
  `test_fires_on_valid_nights_of_partial_days`, `test_closes_on_night_ge_7h`, `test_6_to_7h_keeps_open`
- `unit/test_r2.py`: `test_fires_on_3_complete_days_under_half_goal`, `test_partial_day_in_window_unknown`,
  `test_closes_on_goal_met_day`, `test_uses_goal_valid_on_that_day`

**Done When:** только общий DoD.

**Не делаем на этом шаге:** R3–R6, API, UI, письма.

### Шаг 8.2 — R3–R6, опорные даты, триггеры оценки
**Этап SPEC:** 8 · **Зависит от:** 8.1 · **Критерии §9:** вклад в #9, #12, #13

**Статус:** [x] закрыт 2026-10-11T15:31:01+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T14:47:52+06:00.
Заметки: ADR-047. R3–R6 (`r3.py`–`r6.py`, пороги — `PARAMS`, каталог берёт их оттуда); опорные даты — `base.yesterday`,
`base.last_night`, R4 — воскресенье последней завершённой ISO-недели; «сегодня» и местное время отбоя — `engine.make_facts`
по Clock и истории поясов; `LOOKBACK` = 20 дней. R5 — σ кратчайших разностей от кругового среднего (делим на n).
Оценка: в конце задачи загрузки (с 8.1) и в воркере при старте и раз в `RULES_TICK_S` (3600 с, `Worker.rules_tick`,
лог `rules_tick`); пользователь с идущей задачей пропускается (`queue.try_lock_user`). Сверх плана:
`test_hourly_tick_skips_user_with_running_job`, `test_plain_data_open_nothing`. `test_evaluated_after_ingest_done` зелёный
с начала (вызов с 8.1). На живой проверке найден чужой сдвиг dev clock +25 ч — по указанию пользователя в CLAUDE.md §5
добавлено правило: после проверок со сдвигом возвращать `offset_seconds` в 0 и писать это в WORKLOG. **Для 8.3:** оценка
при включении правила — вызвать `evaluate_user` в транзакции `PATCH /api/rules` (или под `queue.try_lock_user`);
события `recommendation.*` и уведомления — в `evaluate_user` (общая точка для загрузки и `rules_tick`). **Для 10.1 и
11.1:** оценка при смене пояса и потоковый дебаунс — тот же `evaluate_user`. Тестовые пользователи живой проверки:
`rules82@example.com`, `tick82@example.com` (у них данные за 12.10 и рекомендации, открытые при сдвиге часов).

**Тесты до кода:**
- `unit/test_r3.py`: `test_baseline_requires_7_values`, `test_fires_2_days_ge_baseline_plus_7`, `test_closes_below_baseline_plus_4`
- `unit/test_r4.py`: `test_requires_5_valid_nights_each_week`, `test_fires_on_drop_ge_60`, `test_closes_under_30`
- `unit/test_r5.py`: `test_circular_stdev_2330_vs_0030_is_60`, `test_requires_5_of_7_valid_nights`, `test_fires_over_90_closes_under_60`
- `unit/test_r6.py`: `test_fires_5_complete_days_under_15_active`, `test_closes_on_active_day`
- `unit/test_anchors.py`: `test_r2_r3_r6_anchor_yesterday_by_clock`, `test_r1_r5_anchor_today_if_valid_night`,
  `test_r4_anchor_last_complete_iso_week`
- `integration/test_rule_triggers.py`: `test_evaluated_after_ingest_done`, `test_hourly_tick_evaluates_on_day_change`

**Done When:**
- [ ] Загрузка `htgen --scenario <s>` для каждого из шести сценариев открывает соответствующую рекомендацию
      (параметризованный интеграционный тест `test_scenarios_open_expected_rule`).

**Не делаем на этом шаге:** потоковый дебаунс (11.1), пересчёт при смене пояса (10.1).

### Шаг 8.3 — API и UI правил и рекомендаций, отзывы
**Этап SPEC:** 8 · **Зависит от:** 8.2, 7.2 · **Критерии §9:** **закрывает #12 (backend/UI)**, вклад в #16

**Статус:** [x] закрыт 2026-10-11T17:08:47+06:00 (принят пользователем, ручная проверка пройдена). Начат 2026-10-11T15:36:55+06:00.
Заметки: ADR-048 (допущения 1–7), `docs/RULES.md`. Отключение — `closed_rule_disabled`, включение — `evaluate_user` в
транзакции `PATCH`; уведомление и события открытия — одна точка `engine.notify_opened`, закрытия — `engine.publish_resolved`.
Сверх плана: `useEvents.test.ts::rule and recommendation events…`, `Bell.test.tsx::describes a recommendation notification`.
Записи о фичах в WORKLOG восстановлены по `git log` после сжатия контекста. **Для 9.x:** запись в `email_outbox` (SPEC F9, F10)
делать в `engine.notify_opened`, чтобы её давали все три пути открытия (загрузка, таймер, включение правила).

**Объём:** `GET/PATCH /api/rules`, `GET /api/recommendations`, `PUT/DELETE …/feedback`, события
`rule.toggled`, `recommendation.*`, страницы «Правила» и «Рекомендации», `docs/RULES.md`, дисклеймер.

**Тесты до кода:**
- `integration/test_rules_api.py`: `test_list_rules_with_enabled_flag`, `test_disable_closes_open_as_closed_rule_disabled`,
  `test_history_preserved_after_disable`, `test_reenable_triggers_evaluation`, `test_toggle_emits_event`
- `integration/test_recommendations_api.py`: `test_filters_by_status_and_rule`, `test_feedback_set_change_clear_with_timestamp`,
  `test_feedback_emits_event`, `test_other_user_recommendation_404`
- `pages/Rules.test.tsx::toggle calls API and reflects state`
- `pages/Recommendations.test.tsx::active and history tabs`, `::feedback buttons reflect saved value`,
  `::disclaimer is shown`

**Done When:** только общий DoD.

**Ручная проверка:** Загрузить `--scenario short-sleep`: R1 появляется в «Активных». Отключить R1: рекомендация уходит в историю со статусом «правило отключено». Поставить «полезно» во вкладке 1: отметка видна во вкладке 2.

**Не делаем на этом шаге:** письма.

---

## Этап 9. Письма

### Шаг 9.1 — Планировщик `plan_send_time`
**Этап SPEC:** 9 · **Зависит от:** 1.1, 4.1 · **Критерии §9:** вклад в #14, #15

**Статус:** [x] закрыт 2026-10-11T17:38:04+06:00 (принят пользователем: «принято»). Начат 2026-10-11T17:14:59+06:00.
Заметки: ADR-049. Логика и причина — `plan_send(...) → SendPlan(at, reason)`, `plan_send_time` — обёртка с сигнатурой
SPEC (пункт 1 пользователь не принял в первом виде, тесты поправлены отдельным коммитом до кода). Даты дайджестов только
растут (`<=`), просроченное `T` → `now` (причина остаётся `window`/`max_delay`), причина — последнее сдвинувшее правило.
Сверх плана: 3 теста (переезд на запад, просроченное время, обёртка). **Для 9.2:** `last_digest_local_date` — наибольшая
`local_date` отправленных дайджестов; диспетчер вызывает `plan_send` с окном и потолком из `DIGEST_*` (env) и пишет
`at`/`reason` в `planned_at`/`plan_reason`.

**Цель:** чистая функция планирования с исчерпывающими тестами, без БД и SMTP.

**Тесты до кода** (`unit/test_planner.py`, фиксированный `Clock`):
- `test_three_recs_within_window_send_15_min_after_last`
- `test_recs_every_10_min_capped_60_min_after_first`
- `test_after_todays_digest_new_rec_goes_tomorrow`
- `test_tomorrow_shift_hits_quiet_hours_sends_at_quiet_end`
- `test_rec_in_quiet_hours_sends_at_quiet_end`
- `test_quiet_hours_across_midnight`
- `test_daily_limit_rechecked_after_quiet_shift`
- `test_daily_limit_uses_local_date_after_tz_change`
- `test_quiet_disabled_ignored`
- `test_quiet_start_equals_end_treated_as_disabled` — допущение, в SPEC этот случай не описан
- `test_plan_reason_reported`

**Done When:** только общий DoD.

**Не делаем на этом шаге:** outbox, SMTP, диспетчер.

### Шаг 9.2 — Outbox, диспетчер, Mailpit
**Этап SPEC:** 9 · **Зависит от:** 9.1, 8.1 · **Критерии §9:** вклад в #14, #15

**Статус:** [x] закрыт 2026-10-11T18:33:15+06:00 (принят пользователем: «все нормально продолжац»). Начат 2026-10-11T17:41:21+06:00.
Заметки: ADR-050, `docs/EMAIL.md`. Запланированный дайджест — строка `email_digests` с `sent_at IS NULL`; диспетчер — три
транзакции (план / отправка / ошибка), SMTP с таймаутом 10 с, своя advisory-блокировка; тема со склонением (отступление
от текста SPEC). `warning: "no_notify_email"` в `GET /api/digests`, UI — шаг 10.1 (заметка там). Исправлены две ошибки
шага 9.1 в тихих часах при переводе часов (`fix(notify)` 4c599b2, a19374a). Сверх плана: 2 теста SMTP (условия
пользователя), регрессионные и property-тест планировщика. **Для 10.1:** ближайший дайджест — элемент `status: "planned"`
из `GET /api/digests`; смена пояса и тихих часов подхватывается диспетчером на следующем тике.

**Объём:** `email_outbox` (запись в одной транзакции с открытием рекомендации), `email_digests`
(частичный уникальный индекс по `local_date`), тик диспетчера раз в 30 с, `aiosmtplib`, письмо в текстовом и
HTML-виде, `GET /api/digests`, событие `digest.sent`, очередь дайджестов на dev-панели, `docs/EMAIL.md`.

**Тесты до кода:**
- `integration/test_outbox.py::test_outbox_row_in_same_transaction_as_open` (при откате нет ни того, ни другого)
- `integration/test_dispatcher.py`: `test_one_email_with_all_pending`, `test_repeated_tick_no_resend`,
  `test_resolved_before_send_skipped_and_excluded`, `test_no_open_left_no_email_limit_not_consumed`,
  `test_no_notify_email_no_send_and_warning_flag`, `test_digests_api_shows_planned_at_and_reason`
- `integration/test_mailpit.py::test_digest_arrives_in_mailpit_with_subject` (маркер `mailpit`, через API Mailpit)
- `components/DevPanel.test.tsx::shows digest queue`

**Done When:**
- [ ] `scripts/test.* -m mailpit` → зелёный при поднятом compose.

**Ручная проверка:** После срабатывания правила промотать время на dev-панели на 1 ч: в Mailpit одно письмо со всеми рекомендациями. Вызвать ещё одно срабатывание в те же сутки: письма нет.

**Не делаем на этом шаге:** UI настроек (10.1).

---

## Этап 10. Настройки

### Шаг 10.1 — Настройки и смена пояса
**Этап SPEC:** 10 · **Зависит от:** 9.2, 8.2, 4.3 · **Критерии §9:** **закрывает #18**, вклад в #15

**Статус:** [x] закрыт 2026-10-11T19:24:45+06:00 (принят пользователем: «Принято»; ручная проверка — со слов пользователя, пункты 1–5
совпали; следов пунктов 1–4 на dev-стеке агент не нашёл, см. WORKLOG). Начат 2026-10-11T18:38:36+06:00.
Заметки: ADR-051, `docs/TIMEZONES.md`. «Действует с» без смещения — время нового пояса; запись действует до следующей,
поздние не удаляются; переезд раньше всей истории сохраняет прежний пояс записью «с начала истории» (1970-01-01,
`valid_from: null`). Пересчёт — задача `tz_changed` (даты отрезка по новой истории + сводки окна −12/+14 ч, затем
правила). `timezone` в `/api/auth/me`, время в UI — в поясе пользователя. Исправлена ошибка 9.2: без адреса план письма
удаляется (`fix(notify)` 25001ac). **Для 11.1:** тик дайджестов ждёт разбора очереди (ADR-050, заметка там).
**Для 12.x/13.1:** переезд задним числом раньше записи регистрации не меняет текущий пояс — в e2e и демо указывать дату
после регистрации или переезд «сейчас».
Заметки шага 9.2: **Для 10.1: предупреждение в UI, если notify_email пуст** (SPEC F10; указание пользователя на шаге 9.2,
ADR-050). Флаг уже есть: `GET /api/digests` → `warning: "no_notify_email"`. Ближайший дайджест — тот же ответ
(элемент со `status: "planned"`).

**Объём:** `GET/PATCH /api/settings`, `GET/POST /api/settings/timezones` (`valid_from`), задача `tz_changed`
(пересчёт затронутых дат и правил), событие `settings.changed`, страница «Настройки», ближайший дайджест,
`docs/TIMEZONES.md`.

**Тесты до кода:**
- `integration/test_settings_api.py`: `test_update_email_and_quiet_hours`, `test_invalid_quiet_hours_422`,
  `test_invalid_iana_tz_422`, `test_future_valid_from_rejected` (допущение: переезд «в будущем» не разрешён),
  `test_settings_changed_event_reaches_second_client`
- `integration/test_tz_change.py`: `test_past_tz_change_recomputes_affected_dates`,
  `test_tz_change_preserves_period_totals`, `test_tz_change_reevaluates_rules`
- `pages/Settings.test.tsx`: `::saves settings`, `::shows timezone history and next digest`

**Done When:** только общий DoD.

**Ручная проверка:** Включить тихие часы, покрывающие текущее время, и вызвать срабатывание: в Mailpit пусто, пока dev-панелью не промотать время до конца тихих часов. Сменить пояс с датой в прошлом: итоги шагов за неделю не изменились.

**Не делаем на этом шаге:** подтверждение почты.

---

## Этап 11. Потоковый режим

### Шаг 11.1 — Поток и сквозная проверка изоляции
**Этап SPEC:** 11 · **Зависит от:** 2.2, 3.2, 5.1, 8.2 · **Критерии §9:** **закрывает #20**, вклад в #8

Заметки: **Для 11.1** (указание пользователя на шаге 10.1, ADR-050 «Известное ограничение»): тик дайджестов в
`Worker.run` идёт только между вызовами `run_until_idle()`, поэтому, пока воркер разбирает очередь загрузок, письма ждут
(задержка — не больше времени разбора очереди). Поток пачек даёт много задач подряд: вынести тик дайджестов (и правил)
из цикла разбора очереди — отдельная задача asyncio или проверка сроков между задачами — и проверить тестом, что письмо
уходит вовремя при непрерывной очереди.

**Объём:** `POST /api/ingest/batch`, `htgen --stream` (вход по email и паролю), дебаунс оценки правил 10 с по `Clock`.
Последний backend-шаг, поэтому сюда добавлена сквозная проверка изоляции по всем маршрутам.
- Допущение: сквозной тест — дополнение к §9 #20, чтобы новые маршруты не выпадали из проверки.

**Тесты до кода:**
- `integration/test_ingest_batch.py`: `test_batch_202_same_classification_as_file`, `test_batch_over_5000_rejected`,
  `test_stream_then_file_all_duplicate_totals_unchanged`, `test_rule_evaluation_debounced_10s`
- `generator/tests/test_stream.py::test_stream_mode_posts_batches_and_logs_in` (против тестового uvicorn)
- `integration/test_security_sweep.py`: `test_all_id_routes_return_404_for_other_users_resources` (обход OpenAPI),
  `test_all_mutating_routes_require_csrf_header`, `test_all_dev_routes_404_in_prod`

**Done When:**
- [ ] `htgen --days 3 --stream --url http://localhost:8000 --batch-size 1000` → exit 0, в `/api/ingest/jobs`
      появились задачи со статусом `done`.

**Ручная проверка:** Запустить `htgen --stream --rate 2` при открытом дашборде: цифры обновляются в реальном времени.

**Не делаем на этом шаге:** WebSocket, токены устройств.

---

## Этап 12. E2E-тесты (Playwright)

### Шаг 12.1 — Инфраструктура e2e и сценарии 1–5
**Этап SPEC:** 12 · **Зависит от:** все шаги до 11.1 · **Критерии §9:** **закрывает #7, #8, #9, #19**, вклад в #6, #16

**Объём:** `e2e/` (Playwright TS), `docker-compose.e2e.yml` (`APP_ENV=dev`, `DIGEST_WINDOW_MINUTES=1`), хелперы
(`newUser`, `genFixture`, `clock.set`, `mailpit.messages`), `scripts/e2e.{ps1,sh}`, job e2e в CI.
Найденные баги исправляются коммитами `fix(...)`. Если исправление тянет на отдельную фичу — остановка и вопрос
пользователю.

**Тесты до кода** (это сами e2e; сначала пишутся с `test.fail()`, где поведение ещё не проверено):
- `e2e/01-auth.spec.ts` — регистрация, вход, выход
- `e2e/02-upload.spec.ts` — прогресс меняется; во время обработки можно перейти на другую страницу;
  сводка появляется до `ingest.done`
- `e2e/03-reupload.spec.ts` — итоги те же, 0 `new`
- `e2e/04-two-tabs.spec.ts` — загрузка, отключение правила и отметка «полезно» в первой вкладке видны во второй ≤ 2 с
- `e2e/05-gap.spec.ts` — день с пропуском показан как «нет данных»

**Done When:**
- [ ] `scripts/e2e.ps1` → все сценарии 1–5 зелёные.
- [ ] Job e2e в CI зелёный.

**Ручная проверка:** Запустить `npx playwright test --headed` (или открыть HTML-отчёт Playwright) и просмотреть прогоны сценариев 1–5.

**Не делаем на этом шаге:** сценарии 6–10.

### Шаг 12.2 — E2E-сценарии 6–10
**Этап SPEC:** 12 · **Зависит от:** 12.1 · **Критерии §9:** **закрывает #11, #12, #13, #14, #15, #16**

**Тесты до кода:**
- `e2e/06-rule-mail-resolve.spec.ts` — `short-sleep` → R1 в UI → письмо в Mailpit → `recovery` → рекомендация закрыта
- `e2e/07-quiet-hours.spec.ts` — в тихие часы письма нет, после окончания приходит
- `e2e/08-digest-limit.spec.ts` — второе срабатывание в те же сутки без письма; сдвиг `Clock` на следующие сутки →
  второе письмо; за одни сутки не больше одного письма
- `e2e/09-goal-toast.spec.ts` — цель достигнута → тост
- `e2e/10-disabled-rule.spec.ts` — отключённое правило не срабатывает, история видна

**Done When:**
- [ ] `scripts/e2e.ps1` → все 10 сценариев зелёные; `scripts/test.ps1 -All` (unit + integration + e2e) → exit 0.

**Ручная проверка:** Просмотреть headed-прогон или trace сценариев 6–10. Открыть Mailpit и убедиться, что письма выглядят нормально.

**Не делаем на этом шаге:** новые фичи.

---

## Этап 13. Документация и сдача

### Шаг 13.1 — Замер, демо, скриншоты, проверка на Windows
**Этап SPEC:** 13 · **Зависит от:** 12.2 · **Критерии §9:** **закрывает #1, #6, #21**

**Объём:**
- `scripts/bench_ingest.{ps1,sh}`: генерирует ~200 МБ, загружает, замеряет время и пиковую память воркера
  (`docker stats`), пишет результат в `docs/STATUS.md`. Ручная проверка из §9 #6 заменена этой командой.
- `scripts/demo.{ps1,sh}`: compose → генерация → загрузка → открыть дашборд и Mailpit.
- `scripts/fresh_clone_check.{ps1,sh}`: клонирует репозиторий во временную папку, `cp .env.example .env`,
  `docker compose up --build`, smoke, вход демо-пользователя.
- `e2e/screenshots.spec.ts`: скриншоты страниц в `docs/screenshots/` при ширине 1280 и 375 плюс проверка, что
  при 375 px нет горизонтального скролла.

**Тесты до кода:**
- `e2e/screenshots.spec.ts::no horizontal scroll at 375px` для каждой страницы

**Done When:**
- [ ] `scripts/bench_ingest.ps1` → exit 0, в `STATUS.md` записаны время и память. Если время > 5 мин,
      шаг не закрыт: честная запись в STATUS и вопрос пользователю.
- [ ] `scripts/fresh_clone_check.ps1` на Windows → exit 0 (закрывает #1 и #21). Вывод сохраняется в
      `docs/STATUS.md`.
- [ ] `scripts/demo.ps1` → exit 0.
- [ ] `npx playwright test e2e/screenshots.spec.ts` → зелёный, файлы в `docs/screenshots/`.

**Ручная проверка:** Загрузить ~200 МБ файл через UI и во время обработки пользоваться приложением: интерфейс не подвисает. Сравнить ощущения с цифрой в STATUS.md. Выполнить `scripts/demo.ps1` с нуля. (Ручная проверка из §9 #6.)

**Не делаем на этом шаге:** оптимизацию производительности. Если замер плохой, решение принимает пользователь.

### Шаг 13.2 — Документация и сдача
**Этап SPEC:** 13 · **Зависит от:** 13.1 · **Критерии §9:** **закрывает #22, #23**

**Объём:** `README.md` (описание, предварительные требования, запуск за 3 команды, демо, тесты, ссылки на docs,
использованные шаблоны и генераторы: Vite template, shadcn/ui CLI; **место для модели и инструмента — заполняет
пользователь**), `docs/STATUS.md`, `docs/NEXT.md`, финальная запись WORKLOG (время окончания и общая длительность),
напоминание пользователю положить экспорт сессии в `docs/agent-session/`.

**Тесты до кода** (`scripts/tests/test_check_docs.py`, проверяют `scripts/check_docs.py`):
- `test_readme_has_required_sections`
- `test_status_lists_every_criterion_1_to_23_with_status_and_evidence`
- `test_status_values_restricted_to_works_partial_broken`
- `test_relative_links_in_docs_resolve`
- `test_next_md_not_empty`

**Done When:**
- [ ] `python scripts/check_docs.py` → exit 0.
- [ ] `python scripts/check_process.py --all` → exit 0 по всей истории.
- [ ] `gh run list --branch main --limit 1` → `completed success`.

**Ручная проверка:** Пройти README с нуля в чистой папке. Заполнить раздел «Чем делали» (модель, инструмент, почему). Положить экспорт сессии в `docs/agent-session/`.

**Не делаем на этом шаге:** новые фичи и исправления сверх найденных при документировании (они идут в NEXT.md).

---

## Матрица покрытия §9 → шаги

Жирным выделен шаг, который **закрывает** критерий (после него проверка из §9 выполняется полностью).
Остальные шаги в строке дают вклад.

| # | Критерий §9 | Шаги | Закрывает |
|---|---|---|---|
| 1 | Запуск одной командой | 0.2, 0.3, 1.2, 1.3, **13.1** | 13.1 |
| 2 | Приём сна, шагов, пульса | 3.1, 3.2, **4.3** | 4.3 |
| 3 | Генератор: период и пропуски | 2.1, 2.2, **6.1** | 6.1 |
| 4 | Несколько устройств, без суммы шагов | **4.2** | 4.2 |
| 5 | Невыровненные интервалы не теряются | 3.1, **3.3** | 3.3 |
| 6 | Большой файл не блокирует UI | 3.2, 5.2, 12.1, **13.1** | 13.1 |
| 7 | Сводка обновляется по мере обработки | 4.3, 5.1, **12.1** | 12.1 |
| 8 | Повторная загрузка без дублей | 3.1, 3.2, 3.3, 11.1, **12.1** | 12.1 |
| 9 | Пропуск = нет данных; правила не срабатывают | 4.2, 4.3, 6.1, 8.1, 8.2, **12.1** | 12.1 |
| 10 | Дневная и недельная сводки со сравнением | 4.4, **6.1** | 6.1 |
| 11 | Цели и прогресс; уведомление сразу | 7.1, 7.2, **12.2** | 12.2 |
| 12 | Правила R1–R6, видны, отключаются | 8.1, 8.2, 8.3, **12.2** | 12.2 |
| 13 | Нет ежедневного повтора, автозакрытие | 8.1, 8.2, **12.2** | 12.2 |
| 14 | Рекомендации за день — в одном письме | 9.1, 9.2, **12.2** | 12.2 |
| 15 | Тихие часы откладывают письма | 9.1, 9.2, 10.1, **12.2** | 12.2 |
| 16 | История рекомендаций с отзывом | 8.3, 12.1, **12.2** | 12.2 |
| 17 | Сон в правильный день | 4.1, **4.3** | 4.3 |
| 18 | Смена пояса без потерь и удвоений | 4.1, 4.3, **10.1** | 10.1 |
| 19 | Две вкладки | 5.1, 5.2, **12.1** | 12.1 |
| 20 | Изоляция пользователей, dev-эндпоинты закрыты | 1.1, 1.2, 3.2, 4.4, 6.1, 7.1, 8.3, **11.1** | 11.1 |
| 21 | Скрипты работают после клона на Windows | 0.1, 0.2, 0.3, **13.1** | 13.1 |
| 22 | Процесс прозрачен | 0.1 и каждый шаг через общий DoD, **13.2** | 13.2 |
| 23 | Честный статус | **13.2** | 13.2 |

Контроль: у всех 23 критериев есть закрывающий шаг, критериев без шага нет.

---

## Принятые решения (утверждены 2026-10-10T16:59:35+06:00)

Агент переносит их в `CLAUDE.md` и `docs/SPEC.md` **первым делом на шаге 0.1** (одним коммитом), заводит ADR
на каждое и сохраняет ответы пользователя в `PROMPTS.md` дословно.

| # | Решение | Ответ пользователя (дословно) | Куда переносится |
|---|---|---|---|
| 1 | Шаблон шага — тот, что в этом плане | «Принять шаблон агента, он хороший» | — (уже в плане) |
| 2 | Один шаг = одна новая сессия агента; «дальше» после каждого шага; в коммитах `Stage: X.Y`; источник порядка работ — `docs/plan.md` | «Да. Это и есть «новая сессия на шаг»» | `CLAUDE.md` §1 (ссылка на plan.md), §2, §3 |
| 3 | Frontend unit-тесты: Vitest + React Testing Library + MSW | «Да, иначе у UI-шагов не будет тестов до кода» | SPEC §5 (стек), §6.2 (структура) |
| 4 | Тесты до кода: коммит `test(...) (red)` со `xfail(strict=True)` / `test.fails` / `test.fail()`, маркеры снимаются в коммите `feat(...)`; такой коммит не считается «красным» | «Да, удачное решение: в истории будет видно, что тесты появились раньше кода» | `CLAUDE.md` §3 |
| 5 | Ручные проверки из SPEC в Done When заменены тестами и командами (§8 этапы 5–6, §9 #6, #21 через `fresh_clone_check.ps1`). **Ручная проверка пользователем при этом остаётся**: раздел «Проверьте руками» в каждом отчёте, «дальше» — только после неё, факт записывается в WORKLOG | «Да. Но руками всё равно проверяйте сами, это пункт вашей схемы» | `CLAUDE.md` §2 (пункт отчёта); SPEC §8, §9 #6, #21 |
| 6 | Сид правил переносится с этапа 1 на шаг 8.1 | «Да» | SPEC §8 (этапы 1 и 8) |
| 7 | Допущения плана: начальный пояс из браузера при регистрации; тихие часы с началом = концом выключены; переезд с датой в будущем запрещён; сквозной тест изоляции по всем маршрутам; утилиты `check_process.py` и `check_docs.py` | «Принять» | SPEC F1/F5, F10, F11, §9 #20, §8 этапы 0 и 13 |
| 8 | Перенос решений 2–7 в SPEC и CLAUDE.md выполняет агент на шаге 0.1, с ADR и записью в PROMPTS | «Да» | — (этот раздел) |
