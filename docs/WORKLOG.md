# WORKLOG

Журнал работы. Записи только добавляются, старые не правятся. Время берётся из системы
(`Get-Date -Format o` в PowerShell, `date -Iseconds` в bash), записывается с точностью до секунды.

## 2026-10-10T17:23:00+06:00 — Старт проекта
- Сессия агента для шага 0.1 начата (`Get-Date -Format o` → `2026-10-10T17:23:00.7983554+06:00`).
- Прочитаны `CLAUDE.md`, `docs/plan.md`, `docs/SPEC.md`.
- Окружение: git 2.55.0, Python 3.14.7, pytest 8.3.3, gh 2.102.0 (авторизован); `uv` не установлен
  (понадобится с шага 0.2); `git config user.name/user.email` не заданы.

## 2026-10-10T17:26:08+06:00 — Шаг 0.1 начат: репозиторий, журналы, проверка процесса
- План: коммит исходных CLAUDE.md/SPEC/plan/START_PROMPT → .gitattributes и .gitignore → перенос принятых
  решений плана в CLAUDE.md и SPEC (+ ADR, PROMPTS) → ADR из SPEC → agent-session/README → тесты
  check_process (red, strict-xfail) → стоп, ждём «ок» → check_process.py (feat) → DoD → отчёт.
- Решения пользователя по вопросам перед стартом записаны в PROMPTS.md: origin
  https://github.com/portosatos/main.git, автор portosatos <noreply>, стек делится на два ADR, push дважды.

## 2026-10-10T17:28:44+06:00 — Перенос принятых решений плана в CLAUDE.md и SPEC
- CLAUDE.md: §1 ссылка на docs/plan.md, §2 шаги и остановка после каждого шага, «Проверьте руками»,
  §3 `Stage: X.Y` и тесты до кода через strict-xfail, §4 формат записей шага в WORKLOG.
- SPEC: §5 Vitest + RTL + MSW, §6.2 структура (frontend-тесты, check_process/check_docs), §8 преамбула и этапы
  0/1/5/6/8/13, §9 #6/#20/#21, допущения F1/F5/F10/F11.
- DECISIONS: ADR-011…ADR-018 (решения плана 1–8). PROMPTS: ответы пользователя дословно.

## 2026-10-10T17:29:31+06:00 — ADR из SPEC и README для экспорта сессий
- DECISIONS: ADR-001…ADR-010 (стек backend и frontend отдельно, очередь на Postgres, SSE, исходные записи и
  производные минуты, классификация, объединение по минутам, день пробуждения, история поясов, планировщик).
  Итого 18 ADR. Добавлен docs/agent-session/README.md.

## 2026-10-10T17:30:49+06:00 — Тесты до кода шага 0.1: 8 xfailed
- scripts/tests/test_check_process.py: 7 тестов из плана + test_all_mode_allows_unfinished_last_step_only
  (режим --all нужен для CI на шаге 0.3 и для Done When шага 13.2).
- `python -m pytest scripts/tests -q` → 8 xfailed; с `--runxfail` → 8 failed, у всех причина
  `NotImplementedError: step 0.1: check_process.py is not implemented yet` (заглушка), а не ошибка теста.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T17:39:58+06:00 — Фича готова: scripts/check_process.py
- Пользователь ответил «ок» на тесты до кода. Реализован check_process.py (stdlib): --step X.Y и --all.
- `python -m pytest scripts/tests -q` → 8 passed; маркеры xfail сняты, `git grep -n "step 0.1: not implemented"` → пусто.
- Проблема: после реализации 2 теста упали из-за ошибки в самом хелпере теста (`repo.mkdir()` без
  `parents=True` для вложенных репозиториев). В красном прогоне её скрыла более ранняя положительная проверка.
  Исправлено в том же коммите, логика проверок в тестах не менялась.
- Вывод переключён на UTF-8: иначе на Windows кириллица в сообщениях через pipe шла в cp1251.

## 2026-10-10T17:40:09+06:00 — Шаг 0.1 завершён
- Коммиты: fc4030b docs: add spec and agent rules; 27fc72b chore: gitattributes & gitignore;
  8eb26fe docs: apply approved plan decisions; fff1d2f docs(decisions): ADRs from spec and agent-session readme;
  9c69435 test(process): check_process tests (red); 158b18e feat(process): check_process.py;
  e7ce997 docs(claude): add process check commands; этот коммит — запись о завершении.
- Тесты: 8 xfailed → 8 passed. 18 ADR. origin: https://github.com/portosatos/main.git.
- Не выполнено на шаге: scripts/test.ps1 ещё не существует (шаг 0.2); ruff не запускался (uv и ruff не
  установлены, backend/generator не трогали).
- Ждёт ручной проверки пользователя: diff коммита 8eb26fe «docs: apply approved plan decisions».

## 2026-10-10T17:48:24+06:00 — Шаг 0.1: ручная проверка пройдена
- Со слов пользователя: «принято» (diff 8eb26fe прочитан). Шаг закрыт, в docs/plan.md отмечен [x].
- По указанию пользователя команда проверки xfail-маркеров исключает docs/ (ADR-019, коммит a5cb23c).
- Следующий шаг: 0.2 (нужен установленный uv).

## 2026-10-10T18:04:39+06:00 — Шаг 0.2 начат: скелет backend и docker compose
- План: backend/ на uv (FastAPI, pydantic-settings, GET /api/health с проверкой БД), заглушка воркера
  `python -m app.worker`, Dockerfile, docker-compose.yml (postgres 16, mailpit, api, worker), .env.example,
  маркеры pytest unit/integration/mailpit, фикстура тестовой БД, scripts/dev|test|smoke.{ps1,sh}.
- Окружение: uv 0.13.0, Docker 29.8.2 + Compose v5.5.1, системный Python 3.14 (backend — на 3.12 через uv).
- Проблема: порт 5432 на машине занят локальным postgres (PID 5500). Допущение: postgres из compose
  публикуется на хост-порт 5433 (переопределяется `POSTGRES_HOST_PORT`), внутри сети compose — 5432.

## 2026-10-10T18:07:11+06:00 — Тесты до кода шага 0.2: 4 xfailed
- backend/tests/unit/test_config.py: test_settings_load_from_env, test_app_env_defaults_to_dev;
  backend/tests/integration/test_health.py: test_health_ok_when_db_up, test_health_503_when_db_unreachable
  (сверх плана: при недоступной БД ответ должен прийти быстрее 5 с — иначе healthcheck контейнера зависает).
- Фикстура тестовой БД `test_database_url` (tests/integration/conftest.py) создаёт `health_tracker_test` на
  postgres из compose; маркеры unit/integration ставятся по каталогу, mailpit зарегистрирован на будущее.
- `uv run pytest -q` → 4 xfailed; с `--runxfail` → 4 failed, у всех причина
  `NotImplementedError: step 0.2: Settings are not implemented yet` (заглушки app/config.py и app/main.py).
  Тесты health тоже падают на заглушке Settings: она нужна им для создания приложения, до заглушки
  create_app они не доходят. Фикстура тестовой БД при этом уже отработала (база создана).
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T18:18:59+06:00 — Фичи шага 0.2 готовы (пользователь ответил «ок» на тесты до кода, допущения 1–3 приняты)
- c57b7b4 docs(decisions): ADR-020 (postgres на 5433, compose без .env), ADR-021 (health пока только БД).
- 5a71cc5 feat(backend): settings and health endpoint — `uv run pytest -q` → 4 passed, маркеры сняты.
  При недоступной БД health отвечает 503 за ~2 с (таймаут `db_health_timeout_s`; на Windows отказ в
  соединении приходит не сразу).
- bc02f27 feat(worker): заглушка `python -m app.worker`, JSON-лог тика (structlog).
- 867da35 build(compose): образ backend на uv (не root, `init: true` — `docker compose stop` мгновенный),
  сервисы api (healthcheck по /api/health) и worker.
- 13974c3 feat(scripts): dev, test, smoke в .ps1 (совместимы с Windows PowerShell 5.1, только ASCII) и .sh.
  Проверены и негативные случаи smoke (недоступный URL → exit 1).
- cc60a14 style(lint): проблема — общий Done When запускает ruff из корня, а у scripts/ не было конфига, и
  ruff брал чужой (правила PLW). Решение: один корневой ruff.toml (line-length 100, кириллица разрешена —
  RUF001–003 выключены), scripts/check_process.py и его тесты переформатированы; поведение не менялось,
  8 тестов scripts/ зелёные, `check_process.py --step 0.1` → OK.
- 017218c docs(claude): раздел «Команды».

## 2026-10-10T18:18:59+06:00 — Шаг 0.2 завершён
- Коммиты: 6761e03, 16372ec, b4c054e, ec95bfc (test, red), c57b7b4, 5a71cc5 (feat), bc02f27, 867da35,
  13974c3, cc60a14, 017218c и этот.
- Тесты: 4 xfailed → 4 passed (backend) + 8 passed (scripts/). ruff check и format --check — exit 0.
- Done When: `docker compose up -d --build` → api/mailpit/postgres healthy, worker running; smoke.ps1 и
  smoke.sh → exit 0; `git ls-files --eol "scripts/*.sh"` → i/lf у всех трёх.
- Не выполнялось: CI (появится на шаге 0.3).
- Ждёт ручной проверки пользователя: http://localhost:8000/docs и http://localhost:8025.

## 2026-10-10T19:50:05+06:00 — Шаг 0.2: ручная проверка пройдена
- Со слов пользователя: «принято» (дифф e10b212..2ee6b94 прочитан, раздел «Проверьте руками» пройден).
  Шаг закрыт, в docs/plan.md отмечен [x] с заметками.
- Следующий шаг: 0.3 (скелет frontend и CI).

## 2026-10-10T19:56:19+06:00 — Шаг 0.3 начат: скелет frontend и CI
- План: frontend/ на Vite + React 18 + TS, Tailwind, `shadcn init` (button, card), Vitest + React Testing
  Library + MSW, `npm run check` (typecheck + lint + vitest + build); nginx.conf (proxy `/api`,
  `proxy_buffering off`), frontend Dockerfile, сервис frontend в compose на :5173; smoke проверяет frontend и
  proxy; GitHub Actions: ruff, pytest с service-контейнерами postgres и mailpit, `npm run check`, LF для
  `*.sh`, `check_process.py --all`; раздел «Команды» в CLAUDE.md.
- Окружение: Node v24.19.0, npm 11.17.0 (в Docker и CI — Node 22 LTS, как в SPEC §4), gh 2.102.0 (вошёл как
  portosatos, репозиторий portosatos/main публичный, прогонов Actions ещё нет), порт 5173 свободен.

## 2026-10-10T20:00:14+06:00 — Тесты до кода шага 0.3: 1 expected fail (Vitest) + smoke красный на frontend
- f300132 chore(frontend): скелет Vite + React 18 + TS, ESLint, Vitest + RTL + MSW (`onUnhandledFrame: "error"`
  — запрос без мока роняет тест), `npm run check`; App — заглушка `<div />`. Версии: vite 8, vitest 5,
  msw 3, eslint 10, typescript ~6.0 (7.x не поддерживается typescript-eslint).
- b8d7067 test(frontend): app shell title test (red)
- `npm --prefix frontend run test` → 1 expected fail. Без `.fails` тест падает по правильной причине:
  `Unable to find an accessible element with the role "banner"` (заглушка рендерит пустой `<div />`).
- Расширение smoke (`scripts/smoke.ps1` и `smoke.sh`: `GET :5173/` и `GET :5173/api/health`) на текущем стеке:
  api и mailpit — OK, frontend и proxy — FAIL (соединение отклонено: сервиса frontend ещё нет), exit 1 в обоих.
  Smoke пока не закоммичен: вопрос пользователю, как коммитить красную проверку без маркера.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T20:07:08+06:00 — Фичи шага 0.3 (пользователь ответил «ок»: smoke по рекомендации, допущения приняты)
- 274ab71 test(smoke): расширение smoke закоммичено красным (ADR-022); зелёное с 618534d.
- 9bac22e docs(decisions): ADR-022 (красный smoke без маркера), ADR-023 (версии frontend), ADR-024 (nginx на 5173, CI).
- 33da40c feat(frontend): Tailwind v4 + `shadcn init` (radix, button, card), оболочка с заголовком
  «Трекер здоровья»; маркер `test.fails` снят, `npm run check` → 1 passed, exit 0. Сгенерированные shadcn
  компоненты экспортируют `buttonVariants` — правило react-refresh для `src/components/ui` выключено.
- Проблема: `docker compose build frontend` упал на `npm ci` — `@vitest/mocker` 5 требует peer `msw@^2.4.9`,
  npm 10 (Node 22) на конфликте с msw 3 отказывается ставить, локальный npm 11 (Node 24) это пропускал.
  Решение: 2071f4c build(frontend) — msw 2 (`onUnhandledRequest`), уточнение в ADR-023.
- 618534d build(compose): образ frontend (Node 22 → nginx 1.29), nginx.conf (`/api` → api:8000,
  `proxy_buffering off`, SPA fallback), сервис frontend на :5173. `docker compose up -d --build --wait` → все
  healthy; smoke.sh и smoke.ps1 → 4×OK, exit 0; `/dashboard` → 200 text/html.
- 352f9b6 ci: github actions for backend, frontend and process checks — до пуша: yaml валиден, `check_process.py --all` → OK.

## 2026-10-10T20:10:07+06:00 — Шаг 0.3 завершён
- Коммиты: cd545de, f300132 (chore), b8d7067 (test, red), 911571d, 274ab71 (test smoke, red), 9bac22e,
  33da40c (feat), 2071f4c, 618534d, 352f9b6 (ci), 7c534aa, a3382b7 и этот.
- Тесты: Vitest 1 expected fail → 1 passed; backend 4 passed, scripts/ 8 passed (`scripts/test.ps1` и
  `test.sh` → exit 0). ruff check и format --check → exit 0; `git grep "step 0.3: not implemented"` → пусто.
- Done When: `npm --prefix frontend run check` → exit 0; `docker compose up -d --build --wait` → все healthy
  (worker — running), smoke.ps1 и smoke.sh → 4×OK, exit 0; CI на 7c534aa → completed success (backend,
  frontend, process); команды раздела «Команды» → exit 0 (демо и генератор ещё не существуют — шаги 13.1 и 2.1).
- Проверено в браузере: `http://localhost:5173` — оболочка «Трекер здоровья», на 375 px без горизонтального
  скролла; кнопка «Состояние API» → `/api/health` через proxy → `{"status":"ok","db":"ok"}`.
- Замечание: npm 11 откладывает install-скрипт msw (`npm warn allow-scripts`); он копирует браузерный
  service worker, для тестов в Node не нужен.
- Ждёт ручной проверки пользователя: `http://localhost:5173` и вкладка Actions на GitHub.

## 2026-10-10T20:14:30+06:00 — Шаг 0.3: ручная проверка пройдена
- Со слов пользователя: «принято» (дифф 54cd99b..2add1a4 прочитан, раздел «Проверьте руками» пройден).
  Шаг закрыт, в docs/plan.md отмечен [x] с заметками.
- Решение пользователя: README-скелет (SPEC §8, этап 0) делается на шаге 13.2.
- Следующий шаг: 1.1 (Alembic, тестовая БД, Clock).

## 2026-10-10T20:18:24+06:00 — Шаг 1.1 начат: Alembic, тестовая БД, Clock
- План: async engine и фабрика сессий; Alembic (async env.py, первая миграция `dev_clock`, применение при
  старте api); фикстуры pytest — мигрированная тестовая БД и откат транзакции на каждый тест;
  `app.clock.Clock` (системное время UTC + сдвиг из `dev_clock` только при `APP_ENV=dev`, кеш ~1 с);
  `GET/POST /api/dev/clock` (роутер подключается только в dev); воркер получает «сейчас» через тот же Clock.
- Порядок: каркас (заглушки) → тесты до кода (strict xfail) → стоп до «ок» → миграция → Clock → dev API.
- Примечание: в промпте сессии написано «шаг 0.2 в docs/plan.md» — прочитаны и шаг 0.2, и шаг 1.1.

## 2026-10-10T20:21:13+06:00 — Тесты до кода: 12 тестов, 13 xfailed, 5 passed
- Каркас до тестов (интерфейсы, чтобы тесты падали на поведении, а не на импорте):
  6e76caa build(backend) — Alembic 1.20 с async env.py, миграций нет; 5bdc90e refactor(backend) — фабрика
  сессий `create_sessionmaker`, `create_app(sessionmaker=...)`, заглушки `Clock`/`create_clock` и
  `worker_context` (NotImplementedError), воркер перенесён в `app/worker/main.py`.
- Красные тесты: 83c757b test(core). `uv run pytest -q` → 5 passed, 13 xfailed (12 тестов;
  у `test_worker_and_api_see_same_offset` вторым xfail считается teardown очистки: таблицы `dev_clock` ещё нет).
- Причины (`--runxfail`): Clock — `NotImplementedError: step 1.1`; dev API — 404 вместо 200/422 (роутера
  нет); миграции — `'dev_clock' in set()` (миграций нет); инвариант — `app/clock.py must read the system time`.
- Сверх плана: `test_now_is_utc_even_if_system_now_is_not`, `test_offset_is_cached_until_invalidated`,
  `test_post_rejects_out_of_range_offset`, `test_forbidden_pattern_matches_known_calls` (проверка самого
  регэкспа, зелёный сразу — не поведение шага).
- Допущение: `test_no_direct_now_calls_outside_clock` сегодня прошёл бы и без кода (прямых вызовов нет),
  поэтому он ещё требует, чтобы системное время читал именно `app/clock.py`; `test_dev_routes_404_in_prod`
  содержит контроль «в dev тот же маршрут → 200», иначе 404 в prod проходил бы при опечатке в пути.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T20:32:14+06:00 — Фичи шага 1.1 (пользователь ответил «ок, решения принимаю»)
- 0170316 feat(db): миграция `0001` (`dev_clock`, `CHECK id = 1`), `alembic upgrade head` в команде контейнера
  api, воркер ждёт healthy api. `alembic check` → «No new upgrade operations detected»; маркер снят с
  `test_upgrade_downgrade_upgrade_head`.
- 5de272f feat(core): `Clock` (UTC, сдвиг только в dev, кеш 1 с, `invalidate`), `read/write_dev_offset`,
  `create_clock`; маркеры сняты с unit-тестов и инварианта.
- 3522a54 feat(dev): `GET/POST /api/dev/clock` (роутер только при `APP_ENV=dev`, `|offset| ≤ 10 лет`),
  `worker_context`, тик воркера пишет в лог время Clock и сдвиг. `uv run pytest -q` → 17 passed.
- Проблема: после пересоздания контейнера api запрос через nginx `:5173/api/...` → 502 (nginx разрешил `api`
  в IP один раз при старте; ошибка закрытого шага 0.3). Решение: 82bddcc fix(frontend) — `resolver 127.0.0.11`
  и переменная в `proxy_pass`. Проверено: `docker compose up -d --force-recreate api` → `:5173/api/health` → 200.
- 696bbd9 docs(decisions) ADR-025; 3f0970b docs(claude) — команды миграций и dev-времени.
- Проблема (без последствий): правка файлов через Python `write_text` на Windows дала CRLF в рабочей копии
  `backend/Dockerfile` (eol=lf); исправлено до коммита, в индексе LF.

## 2026-10-10T20:32:15+06:00 — Шаг 1.1 завершён
- Коммиты: 628b13a, 6e76caa (build), 5bdc90e (refactor, заглушки), 83c757b (test, red), c8606be, 0170316,
  5de272f, 3522a54 (feat), 82bddcc (fix шага 0.3), 696bbd9, 3f0970b и этот.
- Тесты: красный прогон 5 passed, 13 xfailed → зелёный 17 passed (backend), scripts/ 8 passed;
  `scripts/test.ps1` и `scripts/test.sh` → exit 0. ruff check и format --check → exit 0;
  `git grep "step 1.1: not implemented" -- ":!docs"` → пусто; `npm --prefix frontend run check` → exit 0.
- Done When шага: `docker compose exec api alembic current` → `0001 (head)`; api с `APP_ENV=prod`:
  `POST` и `GET :8000/api/dev/clock` → 404 (затем api возвращён в dev, сдвиг сброшен в 0).
- Сверх плана: воркер видит сдвиг из БД (лог `worker_tick` с `offset_seconds: 86400` после POST);
  smoke.ps1 и smoke.sh → 4×OK.
- Ждёт ручной проверки пользователя: `/docs` с разделом dev, POST сдвига, лог воркера, 404 в prod.

## 2026-10-10T20:37:40+06:00 — Шаг 1.1: ручная проверка пройдена
- Со слов пользователя: «принято» (дифф d5b05aa..dbdb7a1 прочитан, раздел «Проверьте руками» пройден).
  Шаг закрыт, в docs/plan.md отмечен [x] с заметками.
- Следующий шаг: 1.2 (авторизация, backend).

## 2026-10-10T20:41:39+06:00 — Шаг 1.2 начат: авторизация (backend)
- План: модели и миграция `0002` (`users` с `notify_email` и тихими часами, `user_timezones`, `sessions`,
  расширение `citext`); argon2id; `register/login/logout/me`; cookie `ht_session` (HttpOnly, SameSite=Lax,
  Secure в prod); серверная сессия на 14 дней по `Clock`; middleware CSRF (`X-Requested-With: ht` на всех
  изменяющих запросах, в том числе `POST /api/dev/clock`); зависимость `current_user`; идемпотентный сид
  демо-пользователя при старте api; smoke дополняется входом демо-пользователя.
- Порядок: заглушки → тесты до кода (strict xfail) и расширение smoke (red, ADR-022) → стоп до «ок» → код.
- Примечание: в промпте сессии написано «шаг 0.2 в docs/plan.md» — по смыслу это шаг 1.2, прочитан он.

## 2026-10-10T20:44:45+06:00 — Тесты до кода: 13 тестов (20 с параметрами), 20 xfailed, 17 passed
- a19a73b refactor(backend): заглушки `hash_password`, `verify_password`, `seed_demo_user`
  (`NotImplementedError`), чтобы тесты падали на поведении, а не на импорте.
- b607ef5 test(auth) (red): `integration/test_auth.py` и `unit/test_passwords.py` со strict xfail;
  `uv run pytest -q` → 17 passed, 20 xfailed. Причины с `--runxfail`: маршрутов `/api/auth/*` нет → 404
  вместо 201/401/403/409/422; заглушки → `NotImplementedError`; в `/docs` нет `requestInterceptor`.
- Smoke (ADR-022, без маркера): `scripts/smoke.ps1` и `smoke.sh` → 4×OK, `FAIL demo login … 404`, exit 1.
  Красный до фичи auth; в `scripts/test.*` и CI smoke не входит.
- Сверх плана: `test_register_rejects_bad_email_or_short_password_422`, `test_verify_never_raises_on_a_broken_hash`,
  `test_swagger_ui_sends_csrf_header` (иначе ручная проверка через `/docs` упрётся в 403).
- Изменён тест шага 1.1: `api_client` вынесен в `tests/integration/client.py` и по умолчанию шлёт
  `X-Requested-With: ht` (после CSRF-middleware `POST /api/dev/clock` без заголовка → 403).
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T20:56:38+06:00 — Фичи шага 1.2 (пользователь ответил «ок, допущения принимаю»)
- b36f26e feat(db): миграция `0002` — `users` (citext email, тихие часы выключены, 22:00–08:00),
  `user_timezones` (`UNIQUE(user_id, valid_from)`), `sessions` (`id = sha256(token)`); `alembic check` →
  «No new upgrade operations detected»; зависимости argon2-cffi и email-validator.
- 234392a feat(auth): argon2id (`verify_password` не падает на битом хеше); маркер снят с `unit/test_passwords.py`.
- be7e396 feat(auth): `register/login/logout/me`, cookie `ht_session`, сессия 14 дней по Clock, `current_user`;
  34 passed, 3 xfailed (CSRF, Swagger, сид ещё с маркерами — маркер модуля заменён на маркеры этих трёх тестов).
- ac726db feat(auth): ASGI-middleware CSRF (403 без `X-Requested-With: ht` на всех изменяющих методах, в том
  числе `POST /api/dev/clock`), `/docs` с `requestInterceptor`; 36 passed, 1 xfailed.
- 76933a9 feat(auth): сид `python -m app.seed` после миграций, `DEMO_USER_*` в compose и `.env.example`;
  37 passed. Стек пересобран: в логе api `demo_user_created`; после `docker compose restart api` повторной записи
  нет, в БД 1 пользователь и 1 запись пояса; smoke.ps1 и smoke.sh → 5×OK (красное окно smoke: b607ef5..76933a9).
- 85702aa docs(prompts), ba9f2e2 docs(decisions) ADR-026, dee76d7 docs(claude) — команды (демо-пользователь, CSRF).
- Проблема: длинная команда с несколькими heredoc в Git Bash упала с «unexpected EOF» до записи файлов
  (ничего не изменилось); файлы написаны инструментом Write.
- Проверка в браузере: Swagger `/docs` → «Try it out» на `POST /api/auth/login` (демо) → 200, curl в Swagger
  содержит `X-Requested-With: ht`, затем `/api/auth/me` → 200, `document.cookie` не видит `ht_session` (HttpOnly).

## 2026-10-10T20:56:38+06:00 — Шаг 1.2 завершён
- Коммиты: d4934e6, a19a73b (refactor, заглушки), b607ef5 (test, red), b567847, b36f26e, 234392a, be7e396, ac726db,
  76933a9 (feat), 85702aa, ba9f2e2, dee76d7 и этот.
- Тесты: красный прогон 17 passed, 20 xfailed → зелёный 37 passed (backend), scripts/ 8 passed;
  `scripts/test.ps1` и `scripts/test.sh` → exit 0. ruff check и format --check → exit 0;
  `git grep "step 1.2: not implemented" -- ":!docs"` → пусто; `npm --prefix frontend run check` → exit 0
  (frontend не менялся).
- Done When шага: `scripts/smoke.ps1` и `smoke.sh` → exit 0, `OK demo login …/api/auth/me -> 200`;
  `docker compose exec api alembic current` → `0002 (head)`.
- Сверх плана: 3 теста (422 на email/пароль, битый хеш, Swagger с CSRF-заголовком); тест шага 1.1 переведён на
  общий клиент с CSRF-заголовком.
- Ждёт ручной проверки пользователя: Swagger — регистрация, вход, `/me`; флаги cookie в DevTools; 403 без заголовка.

## 2026-10-10T20:59:48+06:00 — Шаг 1.2: ручная проверка пройдена
- Со слов пользователя: «принято». Пройдены пункты 1, 2, 4, 5 раздела «Проверьте руками» (регистрация и вход
  в Swagger, `/me`, 403 без CSRF-заголовка, выход → 401). Пункт 3 (флаги cookie в DevTools) пользователь не
  выполнял: флаги проверил консультант через curl; автоматически они покрыты тестами
  `test_register_sets_httponly_samesite_lax_cookie` и `test_cookie_secure_flag_in_prod`.
- По просьбе пользователя до закрытия шага добавлен README-скелет: 30f2f1c docs(readme); a873da3 docs(prompts).
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками. Следующий шаг: 1.3 (frontend: вход, layout, dev-панель).

## 2026-10-10T21:01:49+06:00 — Шаг 1.3 начат: frontend — вход, layout, dev-панель
- План: зависимости (React Router, TanStack Query, react-hook-form, zod); API-клиент (`credentials: include`,
  `X-Requested-With: ht` на изменяющих запросах, при 401 переход на `/login`); страницы входа и регистрации
  (ошибки на русском, регистрация передаёт пояс браузера); `ProtectedRoute` по `/api/auth/me`; layout с шапкой,
  пустыми пунктами меню и кнопкой «Выйти»; `DevPanel` (время `Clock`, установка сдвига, ссылка на Mailpit),
  скрыта, если `/api/dev/clock` → 404; smoke дополняется `GET :5173/login` → 200.
- Порядок: зависимости и заглушки модулей (тесты должны падать на поведении, а не на импорте) → тесты до кода
  (`test.fails`) → стоп до «ок» → код.

## 2026-10-10T21:08:19+06:00 — Тесты до кода шага 1.3: 12 expected fail
- 2ccaa96 build(frontend): `react-router` 7 (8.x требует React 19, а SPEC фиксирует React 18), TanStack Query 5,
  react-hook-form 7, zod 4, `@hookform/resolvers`; shadcn `input`, `label`.
- 55fcef9 refactor(frontend): заглушки `api/client.ts` (бросает «not implemented»), страниц входа и регистрации
  (только заголовок), `ProtectedRoute` (пускает всех), `DevPanel` (показана всегда, без часов).
- 6ac7b94 test(frontend) (red): 8 тестов из плана и 4 сверх плана (cookie `credentials: include`, нет редиректа
  на 401 от `/api/auth/*`, сообщение сервера при неверном пароле, пароль короче 8 символов) — все `test.fails`.
  Vitest запускается с `TZ=UTC`. Smoke дополнен `GET :5173/login` (уже 200: SPA-fallback nginx с шага 0.3).
- Красный прогон (`npx vitest run`): 6 файлов, 1 passed | 12 expected fail. Без маркеров причины такие:
  клиент — `Error: not implemented`; страницы — нет поля «Email» / кнопки «Войти»; ProtectedRoute — не найдена
  «Страница входа» (пустил на закрытую); DevPanel — запроса к `/api/dev/clock` нет, время не показано.
  `npm --prefix frontend run check` → exit 0.
- Проблема: длинная команда с несколькими heredoc в Git Bash снова упала с «unexpected EOF» до записи файлов;
  тесты записаны инструментом Write.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T21:18:21+06:00 — Фичи шага 1.3 (пользователь ответил «ок, допущения принимаю»)
- 084632b feat(frontend): API-клиент — `credentials: include`, `X-Requested-With: ht` на изменяющих методах,
  401 вне `/api/auth/*` → навигация на `/login`; маркеры сняты с `api/client.test.ts` (4 passed).
- ca3d9d7 feat(frontend): страницы входа и регистрации (react-hook-form + zod, ошибки на русском, сообщение
  сервера в `role="alert"`, пояс браузера при регистрации). Проблема: значения полей не доходили до формы
  («expected string, received undefined») — shadcn v4 генерирует `Input` под React 19, где `ref` — prop;
  в React 18 он терялся. Решение: `Input` на `forwardRef` (ADR-027).
- dcbd3cc feat(frontend): `ProtectedRoute` (401 на `/me` → `/login` с возвратом), layout — шапка, email,
  «Выйти», пустые пункты меню SPEC §6.4. `App.test.tsx` переписан (оболочка теперь требует сессию) и дополнен
  тестом «выход ведёт на страницу входа» — **тест после кода**. Проблема: `RouterProvider` из `react-router/dom`
  в Vitest давал вторую копию контекста («useLocation() may be used only in the context of a <Router>») —
  взят `RouterProvider` из `react-router`.
- 8c51594 feat(frontend): dev-панель — время `Clock` (тикает), сдвиг в часах, «+1 ч», «+1 д», «Сброс», ссылка
  на Mailpit, скрыта при 404; 14 passed, `test.fails` в `frontend/src` не осталось.
- c76bc69 docs(decisions) ADR-027, e640fbc docs(claude) — команды (dev-панель, Mailpit, shadcn и `ref`).
- Проверка в браузере (встроенный браузер, стек compose): выход → `/login`; пустая форма → «Введите email»,
  «Введите пароль»; вход demo → `/`; «+1 д» → «Время Clock: 11.10.2026 …», «Сдвиг: 24 ч»; на 375 px
  `scrollWidth = clientWidth = 375`; «Сброс» → `GET /api/dev/clock` даёт `offset_seconds: 0`.

## 2026-10-10T21:18:21+06:00 — Шаг 1.3 завершён
- Коммиты: 017aa20, 2ccaa96 (build), 55fcef9 (refactor, заглушки), 6ac7b94 (test, red), d702de8, 48374bb,
  084632b, ca3d9d7, dcbd3cc, 8c51594 (feat), c76bc69, e640fbc и этот.
- Тесты: красный прогон 1 passed | 12 expected fail → зелёный 14 passed (frontend, из них 1 тест после кода);
  backend 37 passed, scripts/ 8 passed; `scripts/test.ps1` и `scripts/test.sh` → exit 0; ruff check и
  format --check → exit 0; `npm --prefix frontend run check` → exit 0; `git grep "step 1.3: not implemented"
  -- ":!docs"` → пусто.
- Done When шага: `docker compose up -d --build`, `scripts/smoke.ps1` и `smoke.sh` → exit 0, в том числе
  `OK frontend login page http://localhost:5173/login -> 200`.
- Сверх плана: 4 теста до кода и 1 после (выход); `Input` на `forwardRef`.
- Ждёт ручной проверки пользователя: регистрация, вход и выход через UI; сдвиг времени на dev-панели.

## 2026-10-10T22:13:33+06:00 — Шаг 1.3: ручная проверка пройдена
- Со слов пользователя: «я проверил, все работает. принято». Пройдены пункты раздела «Проверьте руками»:
  ошибки пустой формы, регистрация, вход и выход через UI, сдвиг времени на dev-панели и сброс, вёрстка
  на 375 px и ссылка на Mailpit.
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками. Следующий шаг по плану: 2.1 (генератор: основа).

## 2026-10-10T22:28:04+06:00 — Шаг 2.1 начат: генератор — основа
- План: пакет `generator/` (свой `pyproject`, entry point `htgen`, argparse, из зависимостей только `tzdata`;
  pytest и hypothesis — dev); `docs/DATA_FORMAT.md`; meta-строка; модели часов (шаги поминутно, пульс каждые
  `--hr-interval` с, сон) и телефона (шаги интервалами по 5 мин, сон ±20 мин, без пульса); `--start/--end/--days`,
  `--seed`, `--unaligned`, `--out`; суточный профиль (сон, прогулки, сидячие периоды); детерминизм —
  отдельный генератор случайных чисел на каждую дату (`seed + дата`). Тесты генератора — в `scripts/test.*` и CI.
- Порядок: каркас пакета и заглушки (тесты падают на поведении, а не на импорте) → тесты до кода
  (`xfail(strict=True)`) → стоп до «ок» → код.

## 2026-10-10T22:31:33+06:00 — Тесты до кода шага 2.1: 18 xfailed
- 17ad01d build(generator): пакет `htgen` (hatchling, `[project.scripts] htgen = "htgen.cli:main"`, зависимость
  `tzdata`, dev — pytest и hypothesis), заглушки `cli.main` и `cli.resolve_period` (бросают
  `NotImplementedError`), 2 теста пакета (passed); тесты генератора добавлены в `scripts/test.ps1`,
  `scripts/test.sh` и в CI (job `generator`); `ruff.toml`: `generator/src` в `src`.
- 23e12f8 test(generator) (red): 8 тестов из плана и 5 сверх плана (выбор периода и ошибки, ошибка CLI → exit 2,
  валидация SPEC 7.2, шаг пульса `--hr-interval`, суточный профиль: сон 6–9 ч, прогулка и сидячий период
  каждый день, сон телефона в пределах ±20 мин от часов). Маркер
  `xfail(strict=True, raises=NotImplementedError)`: тест, упавший по другой причине, был бы `failed`.
- Красный прогон (`cd generator; uv run pytest -q`): `2 passed, 18 xfailed`; с `--runxfail` все 18 падают
  с `NotImplementedError: step 2.1`.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T22:46:02+06:00 — Фичи шага 2.1 (пользователь ответил «ок, допущения принимаю»)
- 9e337fa feat(generator): CLI (argparse), `resolve_period`, meta-строка, вывод UTF-8 + LF (stdout или `--out`);
  маркеры сняты с 5 тестов `test_cli.py`. Пока записей нет, после meta оставлена заглушка
  `NotImplementedError`, иначе тесты вывода падали бы на `AssertionError` и strict-xfail с `raises=` дал бы `failed`.
- 430c638 feat(generator): суточный профиль (`profile.py`: ночи, прогулки, сидячие периоды, лёгкая активность —
  отдельный `Random` на (seed, дата, назначение)) и модели устройств (`devices.py`). Маркеры сняты, кроме тестов
  с `--unaligned` (там до следующей фичи заглушка). Проблема: `test_daily_profile…` и
  `test_phone_sleep…` считали, что период всегда обрезает первую ночь. При отбое после полуночи
  (seed 5: 00:05) первая ночь целиком внутри периода, и вышло 4 ночи вместо 3. **Исправлены сами тесты**:
  проверяют полные ночи с подъёмом в каждую дату, кроме первой. Проверка устойчивости (скрипт во временной
  папке): тесты прогулок, профиля и сна на seed 0–59 → 0 падений.
- ea61992 feat(generator): `--unaligned` — сдвиг сетки шагов 1–59 с на дату; сняты последние маркеры (20 passed).
- ac63ff8 fix(generator): `htgen … | head` на Windows падал с `OSError: [Errno 22]`; теперь закрытый stdout → exit 0.
  Регрессионный `test_closed_stdout_pipe_is_not_an_error` — **тест после кода**.
- 7d8d842, e84783d docs(data-format): `docs/DATA_FORMAT.md` (формат ht.v1, валидация, опции и модели `htgen`, разрез
  сна в полночь, `--out` вместо `>` в PowerShell 5.1); c4c840e ADR-028; 3750deb ci — в задаче CI `generator` запуск
  `htgen --days 7 --seed 1 --out sample.ndjson` и `test -s`; f0adad4 — команды в CLAUDE.md, раздел README.

## 2026-10-10T22:46:02+06:00 — Шаг 2.1 завершён
- Коммиты: a888c9d, 17ad01d (build), 23e12f8 (test, red), b7e3cef, 1bb0d53, 9e337fa, 430c638, ea61992 (feat),
  ac63ff8 (fix), 7d8d842, c4c840e, 3750deb, f0adad4, e84783d и этот.
- Тесты: красный прогон `2 passed, 18 xfailed` → зелёный `21 passed` (generator; 1 тест после кода);
  backend 37 passed, scripts/ 8 passed; `scripts/test.ps1` и `scripts/test.sh` → exit 0, `OK: all tests passed`;
  ruff check и format --check → exit 0; `git grep -n "step 2.1: not implemented" -- ":!docs"` → пусто.
  Frontend не менялся.
- Done When шага: `uv run --project generator htgen --days 7 --seed 1 --out sample.ndjson` → exit 0,
  129 387 строк, 10 МБ, период 2026-10-03…2026-10-09 (только `--days` → до вчера).
- Сверх плана: 5 тестов до кода и 1 после; `--devices`; обработка закрытого stdout.
- Ждёт ручной проверки пользователя: запуск `htgen`, просмотр файла (meta, смещения, прогулки на обоих
  устройствах), повтор с тем же seed → тот же хеш, `--unaligned`.

## 2026-10-10T22:51:01+06:00 — Шаг 2.1: ручная проверка пройдена
- Со слов пользователя: «принято»; ручную проверку провёл консультант. Пройдено: `htgen` запускается (exit 0),
  meta на месте, у всех меток есть смещение, одинаковый seed даёт одинаковый хеш, прогулки пишут оба устройства
  (телефон 92–96% от часов), у телефона нет пульса, `--unaligned` даёт невыровненные границы.
- Пункт 5 раздела «Проверьте руками» (ошибка периода → exit 2) в ответе не упомянут; он покрыт тестом
  `test_bad_period_is_a_usage_error`.
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками. Следующий шаг по плану: 2.2 (генератор: пропуски, пояса, сценарии).

## 2026-10-10T23:00:22+06:00 — Шаг 2.2 начат: генератор — пропуски, пояса, сценарии
- План: `--tz` и `--tz-change "момент=пояс"` (смещение каждой метки — по поясу, действующему в этот момент; окно
  даты — от первого момента этой локальной даты до первого момента следующей, поэтому сутки переезда длиннее
  или короче 24 ч); пропуски `--gap "from/to@device"` (явные) и `--gap-prob`, `--gap-max-hours` (случайные, свой
  `Random` на (seed, дата, устройство), без перекрытий) — устройство в пропуске не пишет ничего; `--scenario`
  (`short-sleep`, `sedentary`, `high-rhr`, `irregular`, `worse-week`, `recovery`) от конца периода.
  Без новых опций вывод побайтно тот же, что на шаге 2.1. Документация — `docs/DATA_FORMAT.md`, ADR-029.
- Порядок: тесты до кода (`xfail(strict=True)`) → стоп до «ок» → код.

## 2026-10-10T23:03:58+06:00 — Шаг 2.2: тесты до кода — 15 xfailed
- Коммит: 93d24b9 test(generator): … (red). `generator/tests/test_gaps_tz.py` (4 теста плана,
  7 случаев), `generator/tests/test_scenarios.py` (6 тестов плана, 8 случаев), хелперы дневных метрик в `conftest.py`.
- Красный прогон: `cd generator; uv run pytest -q` → `22 passed, 15 xfailed`. Причина у всех 15 (`--runxfail`):
  `htgen: error: unrecognized arguments: --gap … / --gap-prob … / --tz … / --scenario …` — опций нет.
- Сверх плана: `test_output_without_step_2_2_options_is_unchanged` (хеш вывода шага 2.1, зелёный сразу).
- Проблемы: прогон части «без сценария» на текущем коде показал ошибки в самих тестах (последний вечер периода
  считался сессией сна следующей даты; у обычного дня бывает < 15 активных минут); исправлены до коммита.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T23:22:12+06:00 — Фичи шага 2.2 (пользователь ответил «ок, допущения 1–5 принимаю»)
- ecf003a feat(generator): `Timeline` — `--tz`, `--tz-change` (повторяемый), смещение каждой метки по поясу в момент
  записи, окно даты от первого момента даты до первого момента следующей (день переезда 31 ч / 17 ч), время
  суток в профиле от начала окна, перекрывшиеся ночи короткого дня — один сон. Снят маркер с теста смены пояса.
- 7fe3773 feat(generator): `--gap` (местное время без смещения, `@watch|@phone` или все), `--gap-prob`,
  `--gap-max-hours` (по умолчанию 30): случайные пропуски по (seed, дата, устройство) с просмотром назад, без
  перекрытий и с запасом 1 ч. Сняты маркеры с тестов пропусков и пересечения периодов (проверено, что в
  пересечении есть пропуск, начатый до второго периода).
- 0fb1ead feat(generator): `--scenario` — short-sleep, sedentary, high-rhr, irregular, worse-week, recovery от конца
  периода, свои генераторы случайных чисел, минимальная длина периода. Сняты последние маркеры (`51 passed`).
  Проверка устойчивости (копия тестов сценариев во временной папке, seed 0–19): 0 падений.
- a7cc107 test(generator): ошибки разбора новых опций → exit 2 (14 случаев) — **тесты после кода**: до кода опции
  были неизвестны и тоже давали exit 2, красными они быть не могли.
- e2bc5ca docs(data-format): пояса, пропуски, сценарии; команды в CLAUDE.md и README. a39c11e ci: в задаче `generator`
  команда Done When шага (90 дней, `--gap-prob 0.05`). 8772fea ADR-029.

## 2026-10-10T23:22:12+06:00 — Шаг 2.2 завершён
- Коммиты: d702e4b, 93d24b9 (test, red), 821d5dc, 5a6fbd1, ecf003a, 7fe3773, 0fb1ead (feat), a7cc107 (test после кода),
  e2bc5ca, a39c11e, 8772fea и этот.
- Тесты: красный прогон `22 passed, 15 xfailed` → зелёный `51 passed` (generator; 1 тест сверх плана с хешем шага 2.1
  и 14 случаев после кода); backend 37 passed, scripts/ 8 passed; `scripts/test.ps1` и `scripts/test.sh` → exit 0,
  `OK: all tests passed`; ruff check и format --check → exit 0; `git grep -n "step 2.2: not implemented" -- ":!docs"` → пусто.
  Frontend и backend не менялись.
- Done When шага: `uv run --project generator htgen --days 90 --devices watch,phone --gap-prob 0.05 --seed 42 --out big.ndjson`
  → exit 0, 1 621 919 строк, 126 МБ, около 9 с; у часов 4 случайных пропуска (3,7; 12,2; 15,2; 21,2 ч).
- Ждёт ручной проверки пользователя: файл с `--tz-change` и `--gap` в редакторе (место смены смещения и пропуск),
  сценарий, ошибка опции → exit 2.

## 2026-10-10T23:27:16+06:00 — Шаг 2.2: ручная проверка пройдена
- Со слов пользователя: «принято»; ручную проверку провёл консультант, все 5 пунктов совпали: смена пояса
  14:59+03:00 → 08:00-04:00; в пропуске у часов 0 записей, телефон пишет; short-sleep — последние 3 ночи 5,1–5,3 ч;
  ошибка high-rhr → exit 2, русский текст в PowerShell читается; хеши с `--gap-prob` совпадают.
- Решение пользователя: кракозябры в сообщениях `htgen` при выводе через pipe в Git Bash не исправлять.
- `big.ndjson` (файл Done When, в `.gitignore`) удалён из корня по просьбе пользователя.
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками. Следующий шаг по плану: 3.1 (исходные таблицы, парсер,
  классификация).

## 2026-10-10T23:32:22+06:00 — Шаг 3.1 начат: исходные таблицы, парсер, классификация
- План: заглушки интерфейсов (`app/services/ingest/`: `parse_lines`, `create_ingest_job`, `ingest_records`), чтобы
  тесты падали на поведении, а не на импорте → тесты из «Тесты до кода» (red, strict-xfail) → миграция 0003
  (`btree_gist`, `devices`, минимальная `ingest_jobs`, `steps_raw` с exclusion constraint, `sleep_raw`, `hr_point`) →
  потоковый парсер NDJSON → автосоздание устройств, staging через `COPY`, классификация SQL-запросом.
- Не делаем: HTTP-загрузка, воркер, минутные таблицы, сводки.

## 2026-10-10T23:35:48+06:00 — Шаг 3.1: тесты до кода, 50 xfailed
- 5fe844b refactor(ingest): заглушки `parse_lines`, `create_ingest_job`, `ingest_records`/`Counts` (`NotImplementedError`).
- 600873d test(ingest) (red): `unit/test_parser.py` (7 тестов плана, 36 случаев с параметрами),
  `integration/test_classify.py` (10 тестов плана + 2 сверх плана: строки `invalid` с номерами в отчёте, устройства
  и записи у каждого пользователя свои), `integration/test_generator_contract.py` (htgen 3 дня: `--unaligned`,
  смена пояса, случайные пропуски).
- Красный прогон: backend `37 passed, 50 xfailed`. С `--runxfail` все 50 падают с `NotImplementedError: step 3.1`
  (36 — в `parse_lines`, 14 — в `create_ingest_job`); htgen в контрактном тесте запускается и пишет файл.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-10T23:49:27+06:00 — Фичи шага 3.1 (пользователь ответил «ок, допущения 1–7 принимаю»)
- 07271be docs(prompts): промпт сессии шага 3.1 записан с опозданием (после «ок»), с пометкой об этом.
- 7f4a748 feat(db): миграция 0003 — `btree_gist`, `devices`, минимальная `ingest_jobs`, `steps_raw` с exclusion
  constraint `steps_raw_no_overlap`, `sleep_raw`, `hr_point`; `create_ingest_job`. upgrade → downgrade → upgrade
  проходит, `alembic check` чист; constraint проверен вручную в psql (пересечение → ошибка, соседние — вставлены).
- d0f1351 feat(ingest): потоковый парсер, снят маркер с `test_parser.py` (36 passed).
  Проблема: в первом варианте коммита в конце `test_parser.py` осталась лишняя пустая строка (ruff format
  не прошёл бы на этом коммите); коммиты не были запушены — пересобраны через `git reset --soft`.
- da03fe9 test(ingest): строка длиннее 1 МиБ — **тест после кода** (допущение 6 из ответа на «тесты до кода»).
- 0a4337a feat(ingest): `DeviceResolver` (устройства из meta, неизвестное → phone с предупреждением) и
  классификация: `COPY` в staging, SQL против сохранённых, затем пачка в порядке строк. Сняты последние маркеры.
  Проблема: неделя htgen (129 155 записей) принималась 15,8 с; причина — `line = ANY(массив)` в INSERT;
  заменено на соединение с `unnest` → 10,6 с, повтор (всё `duplicate`) 4,6 с.
- b1872ef docs: правила разбора и классификации в `docs/DATA_FORMAT.md`, ADR-030.

## 2026-10-10T23:49:27+06:00 — Шаг 3.1 завершён
- Коммиты: 1cb1a96, 5fe844b (refactor, заглушки), 600873d (test, red), e238137, 07271be, 7f4a748, d0f1351 (feat),
  da03fe9 (test после кода), 0a4337a (feat), b1872ef и этот.
- Тесты: красный прогон `37 passed, 50 xfailed` → зелёный backend `88 passed` (51 новых: 37 парсера, 13 классификации,
  1 контракт с htgen); generator 51 passed, scripts/ 8 passed; `scripts/test.ps1` и `scripts/test.sh` → exit 0,
  `OK: all tests passed`; ruff check и format --check → exit 0; `git grep -n "step 3.1: not implemented" -- ":!docs"`
  → пусто; `alembic check` → «No new upgrade operations detected».
- Стек: `docker compose up -d --build --wait` → все healthy, `alembic current` → `0003 (head)`, `scripts/smoke.sh` → OK.
- Done When шага — только общий DoD. Frontend и generator не менялись.
- Ждёт ручной проверки пользователя: таблица `steps_raw` и её constraint в psql, тесты классификации и контракта
  с подробным выводом, дифф.

## 2026-10-10T23:53:36+06:00 — Шаг 3.1: ручная проверка пройдена
- Со слов пользователя: «принято»; ручную проверку провёл консультант: `\d steps_raw` — ключ и `steps_raw_no_overlap`
  на месте; `test_parser` 37 passed, `test_classify` 13 passed, контракт с генератором 1 passed.
- Риск по скорости (указание пользователя): 129 тыс. записей за 10,6 с → около 4 мин на 3 млн только на приём
  (цель SPEC §4 — ≤ 5 мин на весь файл). На шаге 3.2 замерить загрузку файла за 90 дней и записать результат;
  указание добавлено в начало шага 3.2 в docs/plan.md.
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками. Следующий шаг по плану: 3.2 (очередь, воркер, загрузка файла).

## 2026-10-11T00:01:57+06:00 — Шаг 3.2 начат: очередь, воркер, загрузка файла
- План: заглушки интерфейсов (очередь `app/worker/queue.py`, обработчик `ingest_file`, роутер `/api/ingest`),
  чтобы тесты падали на поведении, а не на импорте → 11 тестов из «Тесты до кода» в
  `integration/test_ingest_jobs.py` (red, strict-xfail) → миграция 0004 (`jobs`, `worker_heartbeat`, поля
  прогресса и контрольной точки в `ingest_jobs`) → очередь (`SKIP LOCKED`, `NOTIFY/LISTEN`, возврат зависших
  по `Clock`) и цикл воркера с heartbeat и advisory lock по пользователю → `POST /api/ingest/files` (потоковая
  запись в volume, 500 МБ, 202), `GET /api/ingest/jobs[/{id}]` → `/api/health` с тиком воркера →
  `scripts/upload.{ps1,sh}` → замер загрузки файла за 90 дней (указание пользователя при приёмке 3.1).
- Не делаем: SSE, минутные таблицы, сводки.

## 2026-10-11T00:06:11+06:00 — Шаг 3.2: тесты до кода, 12 xfailed
- c32a9f4 refactor(worker): заглушки `Worker` (`tick`, `claim`, `process`, `run_until_idle`, `run`),
  `SimulatedCrash`, `enqueue`/`requeue_stale`, роуты `/api/ingest/*`, настройки `ingest_dir`,
  `ingest_max_bytes`, `worker_stale_after_s` (`NotImplementedError`).
- f3d1c34 test(ingest): `integration/test_ingest_jobs.py` — 11 тестов плана и 1 сверх плана
  (`test_worker_wakes_on_notify_without_waiting_for_tick`). Тесты коммитят по-настоящему (API, воркер и очередь —
  разные соединения), пользователи `@jobs.example.com` удаляются фикстурой до и после теста.
- Красный прогон: backend `88 passed, 12 xfailed`. С `--runxfail`: 10 падают с `NotImplementedError: step 3.2`
  в `POST /api/ingest/files`, health — `KeyError: 'worker'` (поля нет), NOTIFY-тест — `NotImplementedError`
  в `Worker.run`.
- Проблема / как решили: в первом прогоне тесты падали не по той причине — 422 при регистрации: домен `.test`
  зарезервирован и отклоняется `email-validator`; заменён на `jobs.example.com` до коммита.
- Остановка: жду «ок» пользователя перед кодом.

## 2026-10-11T00:26:52+06:00 — Фичи шага 3.2 (пользователь ответил «ок, допущения 1–13 принимаю»)
- 74263a4 docs(prompts): разрешение и допущения 1–13.
- e3f104d feat(db): миграция 0004 — `jobs` (identity, частичный уникальный `dedup_key` в `queued`),
  `worker_heartbeat`, в `ingest_jobs` — `file_path`, `bytes_total`, `bytes_done`, `lines_done`, `warnings`.
  upgrade → downgrade → upgrade проходит, `alembic check` чист.
- 54097ab feat(ingest): `POST /api/ingest/files` (потоковый multipart → volume, 413, 202), `GET /api/ingest/jobs[/{id}]`,
  `enqueue` с NOTIFY. Сняты маркеры с тестов 413 и 404 (маркер перенесён с модуля на отдельные тесты).
- a0d73d4 feat(worker): `claim` (`SKIP LOCKED` + advisory lock), цикл с LISTEN и тиком, `requeue_stale` по `Clock`,
  `ingest_file` с контрольной точкой в транзакции пачки, возврат задачи в очередь при SIGTERM.
  Проблема / как решили: тесты падения и зависшей задачи ставили часы на фиксированную дату 2026-10-01, а задача
  ставится в очередь по системному времени и в это «время» ещё не готова к запуску — ошибка теста, а не кода;
  часы теста теперь стартуют после загрузки (исправлено в этом же коммите, описано в теле).
- c4736a5 feat(health): `worker: {status, last_tick_at}`; снят последний маркер. `test_health_ok_when_db_up` проверяет
  `status`/`db` и наличие `worker` вместо точного словаря.
- ae66890 feat(scripts): `scripts/upload.{sh,ps1}`, volume `ingest`, `/data/ingest` в Dockerfile, nginx 501m.
  Проблема: Python на Windows записал `Dockerfile` и `nginx.conf` с CRLF — возвращены в LF до коммита.
- 08b4a5f docs: `DATA_FORMAT.md` (загрузка и отчёт), ADR-031, «Команды» в CLAUDE.md, `INGEST_DIR` в `.env.example`.
- Зелёный прогон: backend `100 passed` (12 новых), тесты задач 5 раз подряд — `11 passed` без сбоев.

## 2026-10-11T00:26:52+06:00 — Замер загрузки (указание пользователя при приёмке 3.1)
- Стек в Docker Desktop на ноутбуке разработки, `scripts/upload.*` через `:5173`, новый пользователь (все записи `new`).
- `htgen --days 30 --seed 7`: 554 258 записей, 43 МБ → `done` за 32 с; повтор того же файла — 20 с, 0 `new`, 554 258 `duplicate`.
- `htgen --days 90 --seed 7`: 1 662 526 записей, 129 МБ → `done` за 94 с (≈ 17,7 тыс. записей/с), память воркера ≈ 60 МБ.
  Оценка для 3 млн записей (SPEC §4): ≈ 170 с только на приём, без минутных таблиц (шаг 3.3). Риск из 3.1 снижен
  (было ≈ 4 мин на приём), окончательная проверка — шаг 13.1.
- `docker compose restart worker` посреди файла за 90 дней: `job_interrupted` → задача сразу в очереди → `attempt 2`
  → `done`, итог 1 662 526 `new`, 0 `duplicate` (как без рестарта).
- Замерочные пользователи `bench90@`, `restart90@example.com` удалены из dev-БД.

## 2026-10-11T00:27:01+06:00 — Шаг 3.2 завершён
- Коммиты: f5968be, ddc38b8 (docs), c32a9f4 (refactor, заглушки), f3d1c34 (test, red), 28540e8, 74263a4 (docs),
  e3f104d, 54097ab, a0d73d4, c4736a5, ae66890 (feat), 08b4a5f, 4761953 и этот (docs).
- Тесты: красный прогон `88 passed, 12 xfailed` → зелёный backend `100 passed` (12 новых: 11 по плану, 1 сверх плана —
  воркер просыпается по NOTIFY); generator 51 passed, scripts/ 8 passed; `scripts/test.ps1` и `scripts/test.sh` → exit 0,
  `OK: all tests passed`; ruff check и format --check → exit 0; `git grep -n "step 3.2: not implemented" -- ":!docs"`
  → пусто; `alembic check` → «No new upgrade operations detected»; `npm --prefix frontend run check` → exit 0 (14 tests,
  build), т.к. менялся `frontend/nginx.conf`.
- Стек: `docker compose up -d --build --wait` → всё healthy, `alembic current` → `0004 (head)`, `scripts/smoke.sh` → OK,
  `/api/health` → `worker.status: ok`.
- Done When шага: `htgen --days 30 --seed 7 --out f.ndjson` + `scripts/upload.ps1 f.ndjson` → `done`, exit 0;
  `scripts/upload.sh` того же файла → 0 `new`, exit 0.
- Ждёт ручной проверки пользователя: двойная загрузка через `scripts/upload.ps1` (во второй раз 0 `new`), health,
  дифф.

## 2026-10-11T00:37:17+06:00 — Шаг 3.2: ручная проверка пройдена
- Со слов пользователя: «принято»; ручную проверку провёл консультант: загрузка новым пользователем — 554 041 `new`,
  повтор — 0 `new` / 554 041 `duplicate`; `restart worker` на 22 % → `attempt 2`, итог 554 041 `new`, 0 `duplicate`;
  health `ok` → `stale` после остановки воркера (HTTP 200) → `ok` после старта.
- Исправление подсказки из отчёта (указание пользователя): в «Проверьте руками» я предложил при уже загруженных данных
  взять другой `--seed`, но за те же даты это даёт тому же пользователю в основном `conflict`, а не `new`. Чтобы
  увидеть `new`, нужен новый пользователь или другие даты; верная подсказка записана в заметки шага в docs/plan.md.
- Из dev-БД удалены пользователи консультанта `consult1791657006@example.com` и `restart1791657088@example.com`
  (каскадом — их задачи, устройства и записи). Остались `demo@example.com` и `check1791650917@example.com`
  (не подпадает под шаблоны, не трогал).
- Ограничение «один воркер в compose — задачи разных пользователей по очереди» записано кандидатом в `docs/NEXT.md`
  (файл создан; полный список из SPEC §3.2 — на шаге 13.2).
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками. Следующий шаг по плану: 3.3 (минутные таблицы и пересборка).

## 2026-10-11T00:41:14+06:00 — Шаг 3.3 начат: минутные таблицы и пересборка
- План: заглушки `services/minutes.py` и `app/cli.py` (htadmin) → тесты до кода (`integration/test_minutes.py`,
  `integration/test_rebuild.py`, strict xfail) → миграция 0005 (`steps_minute`, `sleep_minute`, `coverage_minute`)
  → пересчёт затронутых минут каждой пачки в той же транзакции → `htadmin rebuild --user` → замер файла за 90 дней.
- Прочитано: CLAUDE.md, шаг 3.3 в docs/plan.md, SPEC F3, F4.3, §4 (производительность, `htadmin rebuild`), §7.1.

## 2026-10-11T00:44:27+06:00 — Шаг 3.3: тесты до кода, 9 xfailed
- Коммиты: 1f7fa80 refactor(minutes): заглушки `DirtyMinutes`, `recompute`, `rebuild_user`, `cli.run` (NotImplementedError);
  dae3f7d test(minutes) (red): `integration/test_minutes.py` (5 тестов по плану, первый — в двух вариантах
  `batch_size` 1 и 5000), `integration/test_rebuild.py` (2 по плану + сверх плана `test_cli_rebuild_by_email`);
  в backend dev-зависимости добавлен `hypothesis`.
- Красный прогон: backend `100 passed, 9 xfailed`. С `--runxfail` все 9 падают с `UndefinedTableError: relation
  "steps_minute" / "sleep_minute" / "coverage_minute" does not exist` — минутных таблиц ещё нет (это часть шага),
  ошибок импорта в тестах нет.
- Ждёт подтверждения пользователя («ок»).

## 2026-10-11T01:05:50+06:00 — Шаг 3.3: фичи готовы
- 5dcac1f feat(db): миграция 0005 — `steps_minute`, `sleep_minute`, `coverage_minute`, PK `(device_id, minute_utc)`.
  С таблицами красные тесты падают уже на поведении: пустые таблицы (assert) и `NotImplementedError: step 3.3`.
- dcf6a34 feat(minutes): пересчёт задетых минут после каждой пачки в её транзакции, `rebuild_user` под advisory
  lock пользователя; сняты маркеры 8 тестов.
  - Проблема / как решили: ошибка в самом тесте `test_coverage_from_steps_sleep_and_hr` — ожидал минуту сна 11:00,
    но сон 11:00:50–11:01:05 покрывает её лишь 10 с (< 30 с). Ожидание исправлено на «минут сна нет» в том же
    коммите; код не менялся.
- 49209b4 feat(cli): `htadmin rebuild --user`, обёртка `htadmin` в образе; снят последний маркер.
  - Проблема / как решили: первая правка Dockerfile записала `printf` с реальными переводами строк, сборка упала
    (`unknown instruction: cd`); исправлено до коммита.
- 31688c9 docs: ADR-032, команда в CLAUDE.md. Ошибка: в ADR сначала было время не из системы, исправлено до коммита
  на системное 2026-10-11T01:03:09+06:00.
- Зелёный прогон: backend `109 passed` (9 новых), generator 51 passed, scripts/ 8 passed.

## 2026-10-11T01:05:50+06:00 — Замер загрузки за 90 дней с пересчётом минут (указание пользователя)
- `htgen --days 90 --seed 7` (1 662 526 записей, 129 МБ), `scripts/upload.sh` через `:5173`, новые пользователи,
  ноутбук разработки, Docker Desktop. Все прогоны — `done`, 1 662 526 `new`.
- С пересчётом: 127 с (первый прогон сразу после пересборки стека), затем 86 с и 85 с.
- Без пересчёта (вызов `recompute` временно отключён, без коммита, воркер пересобран): 66 с в тех же условиях.
  Вклад пересчёта — около 20 с (~30 %). На шаге 3.2 было 94 с (один прогон, условия не сравнивались).
- Память воркера при загрузке с пересчётом — около 60 МБ (как на 3.2).
- Повтор того же файла: 30 с, 0 `new`, md5 трёх минутных таблиц до и после совпадают.
- `htadmin rebuild` этого пользователя: 11,4 с (178 174 / 80 859 / 258 265 строк), md5 до и после совпадают.
- Оценка для 3 млн записей — 2,5–4 мин (≤ 5 мин SPEC §4). Замерочные пользователи `bench33*@example.com` удалены.

## 2026-10-11T01:05:50+06:00 — Шаг 3.3 завершён
- Коммиты: 914ee5c (docs), 1f7fa80 (refactor, заглушки), dae3f7d (test, red), 7a13ed2, 3c6f1a2 (docs), 5dcac1f,
  dcf6a34, 49209b4 (feat), 31688c9 (docs) и этот (docs).
- Тесты: красный прогон `100 passed, 9 xfailed` → зелёный backend `109 passed`; `scripts/test.ps1` и
  `scripts/test.sh` → exit 0, `OK: all tests passed`; ruff check и format --check → exit 0;
  `git grep -n "step 3.3: not implemented" -- ":!docs"` → пусто; `alembic check` → «No new upgrade operations
  detected»; frontend не менялся.
- Стек: `docker compose up -d --build --wait` → healthy, `alembic current` → `0005 (head)`, `scripts/smoke.sh` → OK,
  `/api/health` → `worker.status: ok`.
- Done When шага: `docker compose exec api htadmin rebuild --user demo@example.com` → exit 0 (2 устройства,
  62 248 / 30 124 / 86 336 строк, 3,4 с).
- Ждёт ручной проверки пользователя и чтения диффа.

## 2026-10-11T01:10:02+06:00 — Шаг 3.3: ручная проверка пройдена
- Со слов пользователя: «принято»; ручную проверку провёл консультант: `htadmin rebuild --user demo@example.com` →
  exit 0; `nobody@example.com` → exit 1 с сообщением; файл с интервалами 08:00:30–08:01:30 и 08:01:30–08:02:30 по
  60 шагов → минуты 30/60/30; повторная загрузка → 0 `new`, 2 `duplicate`, `steps_minute` не изменилась.
- Из dev-БД удалён пользователь консультанта `minute1791659289@example.com` (каскадом — 1 устройство, 2 задачи,
  записи и минуты). Остались `demo@example.com` и `check1791650917@example.com`.
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками. Следующий шаг по плану: 4.1 (локальное время по истории поясов).

## 2026-10-11T01:14:22+06:00 — Шаг 4.1 начат: локальное время по истории поясов
- План: заглушки `services/localtime.py` (`TzHistory`: `zone_at`, `local_date`, `ranges_for_date`) → тесты до кода
  `unit/test_localtime.py` (7 по плану, strict xfail) → реализация → ADR о границах суток и времени до первой записи.
- Прочитано: CLAUDE.md, шаг 4.1 в docs/plan.md, SPEC F5, F6 (статусы дня), §6.2, §7.1 (`user_timezones`), §8 этап 4,
  §9 #17, #18; ADR-009.

## 2026-10-11T01:17:23+06:00 — Шаг 4.1: тесты до кода, 9 xfailed
- Коммиты: 62da020 refactor(localtime): заглушка `TzHistory` (`zone_at`, `local_date`, `ranges_for_date`,
  NotImplementedError); 3da42c1 test(localtime) (red): `unit/test_localtime.py` — 7 тестов по плану и 2 сверх плана
  (`test_before_first_record_first_tz_applies` — Допущение: до первой записи истории действует первый пояс;
  `test_records_order_and_validation`). Маркер — `xfail(strict=True, raises=NotImplementedError, …)`: тест, упавший
  по другой причине, был бы ошибкой, а не xfail.
- Красный прогон: `9 xfailed`; с `--runxfail` все 9 падают с `NotImplementedError: step 4.1`. Весь backend:
  `109 passed, 9 xfailed`. ruff check и format --check → exit 0.
- Ожидаемые границы для Сантьяго (переход в полночь) и Берлина сверены с tzdata отдельным запуском zoneinfo.
- Ждёт подтверждения пользователя («ок»).

## 2026-10-11T01:26:03+06:00 — Фича готова: локальные даты по истории поясов
- Коммит: 1bec388 feat(localtime): `TzHistory` — `zone_at`, `local_date`, `ranges_for_date`; маркеры шага сняты.
  Сутки в поясе — `[00:00 дня, 00:00 следующего)` с `fold=0` (00:00 в «дыре» → конец дыры), обрезка периодом записи,
  первый пояс действует и до своего `valid_from`, соседние куски склеиваются.
- 5af6a69 docs(prompts), fd3df50 docs(localtime): ADR-033 (допущения 1–3, приняты пользователем).
- Зелёный прогон: `unit/test_localtime.py` → `9 passed`. Дополнительно, без коммита: стресс-прогон property-тестов
  (3000 примеров «каждая минута — одна дата» и 20 000 «туда и обратно») → OK, 59 с.
- Заметка пользователя: дни считаются по поясу пользователя, а `htgen` по умолчанию пишет `Europe/Moscow` — в
  демо-скрипте и e2e (шаги 12–13) генератор запускать с `--tz` пояса пользователя (записано в ADR-033).

## 2026-10-11T01:26:03+06:00 — Шаг 4.1 завершён
- Коммиты: 0eb8c39 (docs), 62da020 (refactor, заглушка), 3da42c1 (test, red), 7e14be6, 5af6a69 (docs),
  1bec388 (feat), fd3df50 (docs) и этот (docs).
- Тесты: красный прогон `9 xfailed` (с `--runxfail` — 9 × `NotImplementedError`) → зелёный backend `118 passed`
  (9 новых); `scripts/test.ps1` и `scripts/test.sh` → exit 0, `OK: all tests passed` (backend 118, generator 51,
  scripts 8); ruff check и format --check → exit 0; `git grep -n "step 4.1: not implemented" -- ":!docs"` → пусто.
  Frontend, generator, миграции не менялись.
- Done When шага: только общий DoD.
- Ждёт ручной проверки пользователя и чтения диффа.

## 2026-10-11T01:29:26+06:00 — Шаг 4.1: ручная проверка пройдена
- Со слов пользователя: «принято»; ручную проверку провёл консультант: `unit/test_localtime.py` → 9 passed; MSK→NYC —
  один интервал 31 ч; переезд на запад после полуночи — два куска 2 ч + 24 ч; Берлин — сутки 23 ч и 25 ч; ADR-033 на месте.
- Шаг закрыт, в docs/plan.md отмечен [x] с заметками (в том числе про `htgen --tz` для шагов 12–13). Следующий шаг по
  плану: 4.2 (объединение устройств и дневные метрики без сна).

## 2026-10-11T08:11:49+06:00 — Шаг 4.2 начат: объединение устройств и дневные метрики (без сна)
- План: заглушки интерфейса `services/merge.py` (порядок устройств, объединение шагов по покрытию, пульса по наличию
  точек; значение + `source_device_id`) и `services/metrics.py` (метрики дня: ношение, статус, шаги, активные минуты,
  пульс в покое и пик) → тесты до кода `unit/test_merge.py` (5) и `integration/test_day_metrics.py` (6), strict xfail
  → реализация → `docs/MERGE_RULES.md` и ADR.
- Прочитано: CLAUDE.md, шаг 4.2 в docs/plan.md, SPEC F2, F4 (4.3, 4.4), F5, F6, F7, §7.1, §8 этап 4, §9 #4, #9;
  ADR-007, ADR-032, ADR-033.

## 2026-10-11T08:15:15+06:00 — Шаг 4.2: тесты до кода, 15 xfailed
- Коммиты: 4e81d57 refactor(merge): заглушки `merge.py` (`device_order`, `merge_steps`, `merge_hr`, `Merged`) и
  `metrics.py` (`DayMetrics`, `day_metrics`), NotImplementedError; 7953a96 test(merge) (red): `unit/test_merge.py` (5) и
  `integration/test_day_metrics.py` (6 тестов, 10 случаев с параметрами). Маркер —
  `xfail(strict=True, raises=NotImplementedError, …)` на модуль.
- Красный прогон: `15 xfailed`; с `--runxfail` все 15 падают с `NotImplementedError: step 4.2`. Весь backend:
  `118 passed, 15 xfailed`. ruff check и format --check → exit 0.
- Проблема: Docker Desktop был не запущен (integration-тесты → ERROR подключения); запущен, postgres поднят.
- Допущения в тестах (ждут подтверждения): (1) устройства, зарегистрированные в один момент (одна meta-строка), —
  по `external_id`; (2) пульс минуты — медиана её точек, пульс в покое — 10-й перцентиль минутных медиан с линейной
  интерполяцией, «минута без шагов» — объединённое значение ровно 0; (3) минута относится к дате своего начала.
- Ждёт подтверждения пользователя («ок»).

## 2026-10-11T08:31:05+06:00 — Фичи готовы: объединение устройств и метрики дня
- Коммиты: dcff735 feat(merge): `device_order`, `merge_steps`, `merge_hr`, маркеры `test_merge` сняты (5 passed);
  5df8cce feat(metrics): `day_metrics` и чистая `summarize_day`, `localtime.load_tz_history`, маркеры
  `test_day_metrics` сняты (10 passed); 05e7e6f docs(prompts); aba7c53 docs(merge): `docs/MERGE_RULES.md`, ADR-034.
- Зелёный прогон: backend `133 passed` (15 новых). Дополнительно, без коммита: property-тест объединения на 5000
  примерах → OK, 19 с; живой стек: `day_metrics` демо-пользователя за 1–7 октября — `complete`, 1440 минут, шаги
  6911–18206, пульс в покое 51–57, пик 110–120.5.
- Проблема (вне шага): `scripts/upload.sh` в Git Bash на Windows с абсолютным путём `/c/...` → `HTTP 000`; с
  относительным путём и `upload.ps1` работает. Предложено отдельной задачей.

## 2026-10-11T08:31:05+06:00 — Шаг 4.2 завершён
- Коммиты: 6e40428 (docs), 4e81d57 (refactor, заглушки), 7953a96 (test, red), 5d8d6fc, 05e7e6f (docs),
  dcff735 (feat merge), 5df8cce (feat metrics), aba7c53 (docs) и этот (docs).
- Тесты: красный прогон `15 xfailed` (с `--runxfail` — 15 × `NotImplementedError`) → зелёный backend `133 passed`;
  `scripts/test.ps1` и `scripts/test.sh` → exit 0, `OK: all tests passed` (backend 133, generator 51, scripts 8);
  ruff check и format --check → exit 0; `git grep -n "step 4.2: not implemented" -- ":!docs"` → пусто.
  Frontend, generator, миграции не менялись.
- Done When шага: только общий DoD. §9 #4 закрыт тестами (property-инвариант и сценарий 5000).
- Ждёт ручной проверки пользователя и чтения диффа.

## 2026-10-11T08:36:28+06:00 — Шаг 4.2: ручная проверка пройдена
- Со слов пользователя: «принято»; 15 passed; на живом стеке новый пользователь, файл с двумя устройствами (прогулка
  на обоих 2000/1900, часы на руке без шагов при 500 у телефона, прогулка только на телефоне 3000) → steps=5000,
  wear=60, active=40, resting_hr=None, peak=95; соседний день no_data со всеми None; MERGE_RULES.md и ADR-034 на месте.
- Заметки в плане: перед демо (13.1) очистить демо-пользователя и загрузить заново одним файлом (сейчас смесь seed);
  `upload.sh` с абсолютным путём в Git Bash — исправить `fix`-коммитом на одном из следующих шагов (отдельной сессией
  не запускается, решение пользователя).
- Шаг закрыт, в docs/plan.md отмечен [x]. Следующий шаг по плану: 4.3 (сон, валидность ночи, `daily_summaries`,
  «грязные» даты).

## 2026-10-11T08:43:34+06:00 — Шаг 4.3 начат: сон, валидность ночи, `daily_summaries`, «грязные» даты
- План: чистый `services/sleep.py` (сессии из объединённых минут сна, разрывы ≤ 30 мин, сессии от 30 мин, день
  пробуждения, основная сессия, `night_valid`); `merge.merge_sleep`; сон в `DayMetrics`/`day_metrics`; таблица
  `daily_summaries` (миграция 0006); «грязные» даты при загрузке: считаются после каждой пачки, хранятся в задаче
  вместе с контрольной точкой, сброс в сводки не реже раза в ~2 с и в конце задачи; сводки в `htadmin rebuild`.
- Сначала тесты из «Тесты до кода» (11 по плану), красный прогон, остановка до «ок» пользователя.

## 2026-10-11T08:51:43+06:00 — Тесты до кода: 21 xfailed
- Коммиты: 89028bc refactor(summaries): заглушки `services/sleep.py`, `merge.merge_sleep`, `services/summaries.py`
  (NotImplementedError), модель и миграция 0006 (`daily_summaries`, `ingest_jobs.dirty_dates`), хук воркера
  `on_batch` (пауза после пачки k) и `summary_flush_s`, `make_user(tz=…)` в тестовых помощниках;
  85aad07 test(summaries) (red): `unit/test_sleep.py` (6 тестов, 16 случаев) и `integration/test_summaries.py` (5).
- Красный прогон: `21 xfailed`; с `--runxfail` 19 падают с `NotImplementedError: step 4.3`, 2 — на `assert set() == …`
  (грязные даты и сводки ещё не считаются при загрузке; маркер `raises=(NotImplementedError, AssertionError)`).
  Весь backend: `133 passed, 21 xfailed`. ruff check и format --check → exit 0.
- Допущения в тестах (ждут подтверждения): длина сессии — минуты сна без разрывов; дата сессии — дата её последней
  минуты сна; при равенстве основная — более поздняя; день без сессий — сон `null`, `night_valid = false`;
  `night_valid` — в окне [начало − 60 мин, конец + 60 мин) нет пропуска данных длиннее 30 мин; день `no_data` строки
  в `daily_summaries` не имеет.
- Ждёт подтверждения пользователя («ок»).

## 2026-10-11T09:04:09+06:00 — Фичи готовы: сон и дневные сводки
- Решение пользователя (08:53): допущения 1–4 приняты, правило `night_valid` — «в окне [начало − 60 мин, конец + 60 мин]
  нет пропуска данных длиннее 30 минут»; оформлено как уточнение SPEC F6 (68ef7cb docs(spec), ADR-035).
- Коммиты: eee361f feat(sleep): сессии, день пробуждения, `night_valid`, `merge_sleep`, сон в `day_metrics`, маркеры
  `test_sleep` сняты (16 passed); c5fe1a4 feat(summaries): `recompute_dates`, `affected_dates`, `rebuild_summaries`,
  `TzHistory.dates_between`, грязные даты в `ingest_records` и в задаче, сброс в воркере, сводки в `htadmin rebuild`,
  маркеры `test_summaries` сняты (5 passed); f5f8542 test(summaries); c364232 docs(summaries): ADR-036, MERGE_RULES.
- Тесты после кода (сверх плана): property-тест `test_dates_between_are_dates_whose_ranges_meet_the_window`;
  `test_pending_dates_survive_worker_crash` (интервал сброса час, падение после пачки 3: дата ждёт в
  `ingest_jobs.dirty_dates`, продолженная задача досчитывает, итог = пересборке). Тест пересборки усилен до коммита
  фичи: строки удаляются до `cli.run`, иначе он прошёл бы и без пересборки сводок.
- Зелёный прогон: backend `156 passed`; `scripts/test.ps1` и `scripts/test.sh` → exit 0 (backend 156, generator 51,
  scripts 8).
- Живой стек: api и worker пересобраны, `alembic current` → `0006 (head)`; `htadmin rebuild --user demo@example.com` →
  exit 0, 30 строк, повтор — тот же md5; загрузка `htgen` за 1–3 августа (55 440 записей) — 5 с, `computed_at` дат
  03:00:44 / 46 / 47 при окончании задачи в 03:00:47 (сводки появляются по ходу), после неё `htadmin rebuild` даёт тот
  же md5 (33 строки).
- Проблем не было.

## 2026-10-11T09:04:09+06:00 — Шаг 4.3 завершён
- Коммиты: 131ac00 (docs), 89028bc (refactor, заглушки и схема), 85aad07 (test, red), 08cf9db (docs), 68ef7cb (docs,
  SPEC F6 + ADR-035), eee361f (feat sleep), c5fe1a4 (feat summaries), f5f8542 (test), c364232 (docs) и этот (docs).
- Тесты: красный `21 xfailed` → зелёный backend `156 passed`; ruff check и format --check → exit 0;
  `git grep -n "step 4.3: not implemented" -- ":!docs"` → пусто. Frontend и generator не менялись.
- Done When шага: `htadmin rebuild` → exit 0, `daily_summaries` совпадает с исходной (`test_rebuild_reproduces_summaries`
  и живой стек). §9 #17 закрыт `test_sleep_2340_0710_attributed_to_wake_day`.
- Ждёт ручной проверки пользователя и чтения диффа.

## 2026-10-11T09:11:49+06:00 — Шаг 4.3: ручная проверка пройдена
- Со слов пользователя: «принято»; `htadmin rebuild` трижды — хеш `daily_summaries` (без `computed_at`) одинаковый; новый
  пользователь, `htgen` 2026-07-01..14 → 14 дней `complete`, сон относится к дню пробуждения (23:37 → 07:05), первая ночь
  `night_valid = f`; `computed_at` растёт по ходу загрузки (03:07:24 … 03:07:45) и не позже `finished_at`; тесты сна и
  сводок 22 passed; ADR-035 и SPEC F6 совпадают с решением пользователя.
- Шаг закрыт, в docs/plan.md отмечен [x]. Следующий шаг по плану: 4.4 (недельная сводка и API сводок).
