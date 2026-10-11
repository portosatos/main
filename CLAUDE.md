# CLAUDE.md — правила работы в репозитории health-tracker

Этот файл читается в начале каждой сессии и после каждого сжатия контекста. Правила обязательны:
они важнее скорости и удобства.

## 1. Источник требований
- **ТЗ — `docs/SPEC.md`.** Это единственный источник требований. Перед каждым этапом перечитывай его
  разделы, относящиеся к этапу.
- SPEC меняется только с согласия пользователя. Каждое изменение фиксируется в `docs/DECISIONS.md`
  (новый ADR) и в `docs/PROMPTS.md` (дословно, что сказал пользователь, с меткой времени).
- Если требование неясно или противоречит другому, спроси пользователя. Не додумывай.
  Принятые без пользователя решения помечай в документах словом **«Допущение:»**.
- **Порядок работ — `docs/plan.md`** (утверждённый план). Он делит каждый этап §8 SPEC на шаги `X.Y` и для
  каждого шага задаёт «Тесты до кода», Done When, «Ручная проверка» и «Не делаем на этом шаге». Требования
  к продукту по-прежнему только в SPEC; если план и SPEC расходятся, спроси пользователя.
- **Восстановление контекста** в новой сессии или после сжатия: прочитай этот файл, хвост `docs/WORKLOG.md`
  (последние ~40 строк), `git log --oneline -20` и текущий шаг в `docs/plan.md`. Так станет понятно, на каком
  шаге и какой фиче остановились.

## 2. Пошаговая работа
- Работаем **последовательно по шагам** из `docs/plan.md` (шаг — часть этапа из раздела 8 SPEC).
  **Один шаг — одна новая сессия агента.** Пока не закончен текущий шаг, следующий не начинается.
  Начатый шаг самовольно не расширяется: если он не укладывается в сессию, остановись и предложи разделить его.
- Порядок внутри шага: тесты из «Тесты до кода» (red, см. раздел 3) → код → общий Done When и Done When шага.
- В конце **каждого шага** (не этапа):
  1. запусти линтеры и все тесты и убедись, что они зелёные;
  2. проверь, что все фичи шага закоммичены (см. раздел 3);
  3. сделай запись «Шаг X.Y завершён» в `docs/WORKLOG.md` и закоммить её;
  4. выполни `python scripts/check_process.py --step X.Y` и `git push`;
  5. дай пользователю отчёт: что сделано, таблица «пункт Done When → чем проверено → результат», какие решения
     приняты, что осталось, и раздел **«Проверьте руками»**: 2–5 действий в браузере или терминале с ожидаемым
     результатом. Пункты из раздела «Ручная проверка» шага входят в него обязательно;
  6. **жди команды пользователя «дальше»** (остановка после каждого шага). Пользователь сначала проходит
     ручную проверку. Если что-то не так, исправь коммитом `fix(...)` в рамках того же шага;
  7. запиши в WORKLOG, что ручная проверка пройдена (со слов пользователя), отметь шаг `[x]` в `docs/plan.md`
     с временем закрытия, закоммить и запушь.
- Ручные проверки из SPEC в Done When заменены тестами и командами, но **ручная проверка пользователем
  остаётся** и автоматическими проверками не заменяется.
- Если обнаружилась ошибка в уже закрытом шаге, исправь её отдельным коммитом `fix(...)` и запиши в WORKLOG.

## 3. Коммиты (особое требование заказчика: по истории видно, что работа шла постепенно)
- **Один коммит на одну завершённую фичу или подзадачу**, а не на шаг. На шаге обычно 2–6 коммитов.
  Коммит делается, когда фича работает и её тесты проходят.
- Формат — Conventional Commits, на английском: `feat(ingest): classify new/duplicate/conflict records`,
  `test(merge): per-minute single-source invariant`, `docs(worklog): step 3.2 finished`.
  В теле 1–3 строки о том, зачем это сделано, и строка `Stage: X.Y` — номер **шага** из `docs/plan.md`
  (например, `Stage: 3.2`).
- **Тесты до кода** (видно в истории git):
  1. тесты из «Тесты до кода» пишутся первыми и запускаются: они должны быть **красными по правильной причине**
     (поведение не реализовано, а не ошибка импорта в самом тесте);
  2. они коммитятся с маркером ожидаемого падения: pytest — `@pytest.mark.xfail(strict=True, reason="step X.Y: not implemented")`,
     Vitest — `test.fails(...)`, Playwright — `test.fail()`. Коммит `test(<scope>): <что> (red)`.
     Такой коммит **не считается коммитом с красными тестами**: набор остаётся зелёным;
  3. маркеры обязательно снимаются в коммите с фичей `feat(<scope>): …` (strict-xfail на прошедшем тесте —
     ошибка). Проверка: `git grep -n "step X.Y: not implemented" -- ":!docs"` → пусто
     (`docs/` исключён: журналы могут цитировать эту строку);
  4. в WORKLOG записывается сводка красного (`N xfailed`) и зелёного (`N passed`) прогонов с системным временем.
  Тест, добавленный после кода (например, регрессионный после бага), допустим и отмечается в WORKLOG.
- **Запрещено:** squash; `--amend` и `rebase` запушенных коммитов; `push --force`; `--no-verify`;
  коммит секретов (`.env` в `.gitignore`, в репозитории только `.env.example`); коммит, после которого
  проект не собирается или тесты красные.
- Ветка `main`, линейная история. Пуш в GitHub — в конце каждого этапа, можно и чаще.

## 4. Временные метки и журналы (особое требование заказчика)
- Время **берётся из системы**, его нельзя выдумывать: `Get-Date -Format o` в PowerShell или `date -Iseconds` в bash.
- **`docs/WORKLOG.md`** — записи только добавляются, старые не правятся. Формат:
  ```markdown
  ## 2026-10-10T14:03:12+03:00 — Шаг 3.1 начат: исходные таблицы, парсер, классификация
  - План: ...
  ## 2026-10-10T14:40:02+03:00 — Тесты до кода: 18 xfailed
  ## 2026-10-10T15:47:40+03:00 — Фича готова: классификация записей new/duplicate/conflict
  - Коммит: a1b2c3d feat(ingest): ...
  - Проблемы / как решили: ...
  ## 2026-10-10T16:20:05+03:00 — Шаг 3.1 завершён
  - Итог, коммиты, Done When, что проверить вручную
  ## 2026-10-10T16:45:30+03:00 — Шаг 3.1: ручная проверка пройдена
  ```
  Каждый заголовок `##` начинается с ISO-времени **со смещением** (`+03:00` или `Z`); время не убывает.
  Записи шага называются строго `Шаг X.Y начат: …` и `Шаг X.Y завершён` — по ним работает
  `scripts/check_process.py`.
  Записи обязательны: при старте проекта, в начале и в конце каждого шага, после каждой фичи
  (можно одной строкой с хэшем коммита), после ручной проверки пользователем, при каждом значимом решении или
  проблеме, в конце проекта (время окончания и общая длительность).
- **`docs/DECISIONS.md`** — журнал решений в формате ADR. Каждая запись: номер, дата и время, контекст,
  рассмотренные варианты, выбор и причина, последствия.
- **`docs/PROMPTS.md`** — стартовый промпт и все ключевые указания пользователя дословно, с метками времени.
- **Экспорт сессии агента обязателен.** Его кладёт пользователь в `docs/agent-session/`. В конце проекта
  напомни ему об этом.

## 5. Инварианты кода
- «Сейчас» на backend берётся **только через `app.clock.Clock`**. Прямые `datetime.now()`, `time.time()` и
  `date.today()` в бизнес-логике запрещены, исключение — сам `Clock`.
- В БД всё время хранится в UTC (`timestamptz`). Локальные даты считает только `services/localtime.py`
  по истории часовых поясов пользователя.
- Каждый запрос к пользовательским данным фильтруется по `user_id` текущей сессии.
- Исходные записи телеметрии (`steps_raw`, `sleep_raw`, `hr_point`) — источник истины. Минутные таблицы и
  `daily_summaries` — производные: их можно в любой момент пересчитать из исходных записей.
- Загрузка, пересчёты и отправка писем идемпотентны: повтор не меняет результат.
- Скрипты `.sh` хранятся с LF (см. `.gitattributes`). Для каждого `.sh` есть аналог `.ps1`, потому что
  у заказчика Windows.
- **Dev clock после проверок** (указание пользователя, шаг 8.2): после любой проверки со сдвигом dev clock вернуть
  `offset_seconds` в 0 (`POST /api/dev/clock` `{"offset_seconds": 0}` или «Сброс» на dev-панели), убедиться, что
  `GET /api/dev/clock` → `offset_seconds: 0`, и записать это в WORKLOG. Чужой сдвиг, найденный на стеке, — тоже
  сбросить в 0 после проверки и записать, какой он был.

## 6. Команды
> Агент поддерживает этот раздел в актуальном состоянии; заполняется на этапе 0.
- Запуск всего: `docker compose up --build` или `scripts/dev.ps1` / `scripts/dev.sh` (`-d` — в фоне).
  Порты на хосте: приложение **5173** (nginx, `/api` проксируется в api; ADR-024), api 8000 (`/docs`),
  Mailpit UI 8025 и SMTP 1025, postgres **5433** (ADR-020).
- Smoke запущенного стека: `scripts/smoke.ps1` / `scripts/smoke.sh` (`/api/health`, Mailpit, frontend `:5173/`
  и `:5173/api/health` через proxy → 200, вход демо-пользователя и `:5173/api/auth/me` → 200, первое событие
  `:5173/api/events` за ≤ 2 с — `SSE_FIRST_BYTE_SEC` / `-SseFirstByteSec`).
- Тесты: `scripts/test.ps1` / `scripts/test.sh` — поднимают postgres и mailpit из compose, запускают pytest backend,
  генератора и `scripts/tests`. Аргументы уходят в pytest backend (`-m unit`, `-m integration`). Тестовая БД —
  `TEST_DATABASE_URL` из окружения (по умолчанию `health_tracker_test` на `localhost:5433`), создаётся сама.
- Миграции (Alembic, `backend/alembic/`): применяются сами при старте api; текущая ревизия —
  `docker compose exec api alembic current` → `(head)`. Локально: `cd backend; uv run alembic upgrade head`
  (нужен `DATABASE_URL`), новая миграция — `uv run alembic revision --autogenerate -m "..."`, проверка, что
  модели и миграции совпадают, — `uv run alembic check`.
- Демо-пользователь: `demo@example.com` / `demo12345` (`DEMO_USER_*` в `.env`), создаётся при старте api
  (`python -m app.seed` после миграций, идемпотентно). Все изменяющие запросы к API — с заголовком
  `X-Requested-With: ht`, иначе 403 (ADR-026); Swagger `/docs` добавляет его сам.
- Dev-время (только `APP_ENV=dev`): `GET /api/dev/clock`, `POST /api/dev/clock` с `{"offset_seconds": 86400}`
  (сдвиг; 0 — сброс). При `APP_ENV=prod` → 404. В UI — dev-панель внизу страниц после входа
  (`http://localhost:5173`, ADR-027); ссылка на Mailpit — `VITE_MAILPIT_URL` или тот же хост, порт 8025.
- Только backend: `cd backend; uv run pytest`. Линтер: `uv run --project backend ruff check .` и
  `uv run --project backend ruff format --check .`
- Frontend (Node 22+): `npm ci --prefix frontend` (один раз), `npm --prefix frontend run check` (typecheck +
  lint + vitest + build), `npm --prefix frontend run dev` — Vite на `http://localhost:5173` с proxy `/api` →
  `localhost:8000` (сервис frontend из compose при этом остановить: `docker compose stop frontend`).
  Компоненты shadcn: `cd frontend; npx shadcn@latest add <name>` (под React 19: компонент, которому передают
  `ref`, переписать на `forwardRef`, ADR-027). Часть тестов: `cd frontend; npx vitest run src/pages`.
- CI: `.github/workflows/ci.yml` на каждый push в `main` и PR; последний прогон —
  `gh run list --branch main --limit 1`, логи упавшего — `gh run view <id> --log-failed`.
- Демо (появится на шаге 13.1): `scripts/demo.ps1` / `scripts/demo.sh`
- Генератор (`generator/`, формат — `docs/DATA_FORMAT.md`, ADR-028, ADR-029): `uv run --project generator htgen --help`;
  пример — `uv run --project generator htgen --days 7 --seed 1 --out sample.ndjson` (`*.ndjson` в `.gitignore`,
  без `--out` пишет в stdout); пояса, пропуски и сценарии — `--tz-change "2026-10-05T12:00Z=America/New_York"`,
  `--gap "2026-10-03T00:00/2026-10-04T12:00@watch"`, `--gap-prob 0.05`, `--scenario short-sleep`.
  Тесты: `cd generator; uv run pytest` (входят в `scripts/test.*` и CI).
- Поток (ADR-052): `uv run --project generator htgen --days 3 --stream --url http://localhost:8000 --batch-size 1000
  --rate 2` (вход — `--email`/`--password`, иначе `DEMO_USER_*` из env, иначе демо) → пачки в `POST /api/ingest/batch`
  (`{"devices": [...], "records": [...]}`, ≤ 5000, задача `ingest_batch`, `source: stream`). Правила после пачек —
  задача `evaluate_rules` через 10 с по Clock (`dedup_key`, пачки присоединяются); воркер просыпается к `run_after`,
  тики heartbeat, правил и дайджестов — отдельные задачи asyncio. Сквозная проверка маршрутов —
  `tests/integration/test_security_sweep.py` (новый маршрут с id в пути — классифицировать там).
- Загрузка файла в запущенный стек: `scripts/upload.ps1 FILE` / `scripts/upload.sh FILE` — вход демо-пользователем
  через `:5173`, `POST /api/ingest/files`, опрос задачи до `done`/`failed`, отчёт; exit 0 только при `done` (другой
  пользователь — `DEMO_USER_EMAIL`/`DEMO_USER_PASSWORD`). Файлы — volume `ingest` (`/data/ingest`, общий для api и
  worker), лимит 500 МБ. Воркер: `docker compose logs -f worker` (JSON-логи `job_started`/`job_done`), тик в
  `GET /api/health` → `worker.status`. Очередь — таблица `jobs`, отчёты — `ingest_jobs` (ADR-031).
- Минутные таблицы (`steps_minute`, `sleep_minute`, `coverage_minute`, ADR-032) пересчитываются воркером после каждой
  пачки. Сводки `daily_summaries` (ADR-036) — по «грязным» датам: после первой пачки, затем не реже раза в ~2 с и в
  конце задачи (даты ждут в `ingest_jobs.dirty_dates`). Полная пересборка пользователя (минуты и сводки):
  `docker compose exec api htadmin rebuild --user demo@example.com`
  (локально — `cd backend; uv run python -m app.cli rebuild --user …`); неизвестный email → exit 1.
- API сводок (ADR-038, правила — `docs/API.md`): `GET /api/summary/day?date=2026-10-07`, `/api/summary/week?week=2026-W41`,
  `/api/summary/range?from=…&to=…` (≤ 366 дней); дата без строки в `daily_summaries` — `no_data` с `null`.
- События (SSE, ADR-039, `docs/API.md`): `GET /api/events` — поток `ready`, `ingest.progress`, `ingest.done`,
  `summary.updated {dates}`, `resync`; публикация — `services/events.py` (`NOTIFY user_events`). Посмотреть руками:
  `curl.exe -N -b "ht_session=<cookie>" http://localhost:5173/api/events`. Соединение LISTEN API в Postgres —
  `application_name = 'ht-events'` в `pg_stat_activity`.
- Frontend и события (ADR-040): `hooks/useEvents.ts` (один EventSource на вкладку в `AppLayout`, таблица `handlers`
  «событие → ключи»), ключи запросов — `lib/queryKeys.ts`. Страница «Загрузка» — `http://localhost:5173/upload`
  (XHR-передача — `api/ingest.ts::sendFile`, её состояние — `lib/transfer.ts`). В тестах — фейки
  `test/fakeEventSource.ts` и `test/fakeXhr.ts`.
- Проверка процесса шага: `python scripts/check_process.py --step X.Y` (вся история: `--all`)
- Тесты утилит `scripts/`: `python -m pytest scripts/tests -q`
- Дашборд и устройства (ADR-041): `http://localhost:5173/?date=2026-10-07`, `/?view=week&week=2026-W41` (без параметров —
  `today` из `/api/auth/me` по `Clock`), `http://localhost:5173/devices`; API — `GET /api/devices`,
  `PATCH /api/devices/{id}` `{"name": "…"}` (событие `devices.changed`). Компоненты — `SummaryCard`, `DaysChart`
  (Recharts), `GapBar` (пропуск — штриховка); подписи и форматы метрик — `lib/metrics.ts`.
- Цели и уведомления (ADR-043, `docs/API.md`): `GET/PUT /api/goals` `{"steps": 10000, "sleep": 7.5}`, прогресс — поле
  `goals` в `/api/summary/*`; `GET /api/notifications`, `POST /api/notifications/read` `{"ids": [...]}` (без `ids` — все).
  Достижения пишет `services/goals.py::record_achievements` в конце каждого `recompute_dates`; события `goal.achieved`
  (`show_toast`), `notification.created`, `notifications.read`, `goal.changed`.
- Цели в UI (ADR-044): страница `http://localhost:5173/goals` (форма, неделя), прогресс в карточках дашборда —
  `GoalProgress`, колокольчик в шапке — `Bell` (`unread`, «Прочитать все»), тосты — `sonner` (`Toasts` в `AppLayout`,
  `lib/toasts.ts::showGoalToast`, только при `show_toast`).
- Правила (ADR-045, ADR-047): `services/rules/` — `engine.py` (`plan_actions` — машина состояний, `evaluate_user` —
  оценка пользователя: в конце задачи загрузки, при старте воркера и раз в час — `Worker.rules_tick`, интервал
  `RULES_TICK_S`, 3600 с), правила `r1.py`–`r6.py` (пороги — `PARAMS`, опорные даты — `base.py`), каталог R1–R6 —
  `catalog.py` (сид — миграция 0010). Таблицы `rules`, `user_rules` (нет строки — включено), `recommendations`
  (одна открытая на правило — `uq_recommendations_open`). Логи воркера `recommendation_opened` / `recommendation_resolved`,
  `rules_tick`. После сдвига dev clock переоценить сразу — `docker compose restart worker`.
- Правила и рекомендации в API и UI (ADR-048, `docs/RULES.md`, `docs/API.md`): `GET /api/rules`,
  `PATCH /api/rules/{code}` `{"enabled": false}` (выключение закрывает открытую как `closed_rule_disabled`, включение сразу
  оценивает), `GET /api/recommendations?status=open&rule=R1` (`status` повторяется), `PUT/DELETE
  /api/recommendations/{id}/feedback` `{"value": "useful"}`. Открытие рекомендации — уведомление и события в
  `engine.evaluate_user` (`notify_opened`). Страницы `http://localhost:5173/rules`, `/recommendations`; пороги словами и
  снимок значений — `lib/rules.ts`, дисклеймер — `components/Disclaimer.tsx`.
- Планировщик дайджеста (ADR-049): `services/notify/planner.py` — `plan_send(...) → SendPlan(at, reason)` (окно 15 мин,
  потолок 60 мин, лимит по местной дате, тихие часы), `plan_send_time` — сигнатура SPEC F10, обёртка. Тесты —
  `cd backend; uv run pytest tests/unit/test_planner.py`.
- Письма (ADR-050, `docs/EMAIL.md`): outbox пишет `engine.notify_opened`; диспетчер — `services/notify/dispatcher.py`,
  тик воркера раз в 30 с (`DIGEST_TICK_S`), лог `digest_sent` / `digest_send_failed`. SMTP — Mailpit (`SMTP_HOST`, в compose
  `mailpit`; таймаут `SMTP_TIMEOUT_S` 10 с), окно и потолок — `DIGEST_WINDOW_MINUTES` / `DIGEST_MAX_DELAY_MINUTES`.
  Очередь — `GET /api/digests` (`warning: "no_notify_email"` без почты) и таблица на dev-панели; событие `digest.sent`.
  Письма в Mailpit: `http://localhost:8025`, API — `curl "http://localhost:8025/api/v1/search?query=to:demo@example.com"`.
  Тест с настоящим Mailpit — `scripts/test.ps1 -m mailpit` / `scripts/test.sh -m mailpit` (скрипты тестов поднимают
  postgres и mailpit).
- Настройки и пояса (ADR-051, `docs/TIMEZONES.md`, `docs/API.md`): страница `http://localhost:5173/settings`;
  `GET/PATCH /api/settings` `{"notify_email": "", "quiet_enabled": true, "quiet_start": "22:00", "quiet_end": "08:00"}`
  (пустая почта — писем нет), `GET/POST /api/settings/timezones` `{"tz": "America/New_York", "valid_from": "2026-10-05T08:00"}`
  (без смещения — время нового пояса; без `valid_from` — сейчас; запись действует до следующей). Переезд ставит задачу
  `tz_changed` (`services/timezones.py`: пересчёт дат и правила), событие `settings.changed {fields}`; `timezone` — в
  `/api/auth/me`. Тесты — `tests/integration/test_settings_api.py`, `test_tz_change.py`.
