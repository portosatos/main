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
