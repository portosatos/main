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
