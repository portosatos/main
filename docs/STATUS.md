# Статус проекта

> Полностью заполняется на шаге 13.2 (критерии §9, известные проблемы). Блоки между метками
> `<!-- …:begin -->` и `<!-- …:end -->` пишут скрипты `scripts/bench_ingest.*` и
> `scripts/fresh_clone_check.*` — руками их не правят.

<!-- bench_ingest:begin -->
## Замер загрузки большого файла (`scripts/bench_ingest.ps1`)

- Когда: 2026-10-11T22:44:32+06:00 (системное время); `scripts/bench_ingest.ps1 -Days 90 -HrInterval 3 -Seed 7`.
- Машина: Microsoft Windows 10 Pro; 12th Gen Intel(R) Core(TM) i5-12400F; ОЗУ 31,8 ГиБ. Docker 29.8.2: 12 CPU, 15,5 ГиБ.
- Файл: htgen `--days 90 --hr-interval 3 --seed 7` (часы и телефон; пульс только с часов) —
  197,4 МБ, 2 699 219 строк. Свежий пользователь `bench-2b5cf318d924@example.com`, загрузка через `:5173`.

| Показатель | Значение |
|---|---|
| Передача файла (HTTP, `POST /api/ingest/files`) | 0,6 с |
| Обработка (задача: `created_at` → `finished_at`) | 236,9 с |
| Всего | 237,5 с |
| Пиковая память воркера (`docker stats`, замеров: 118) | 66 MiB (до загрузки 64 MiB) |
| Пиковая память postgres (там же) | 2 038 MiB (до загрузки 1 902 MiB) |
| `GET /api/summary/day` во время обработки | p95 19 мс, макс. 29 мс (запросов: 118) |
| Записи: всего / новые / дубли / конфликты / некорректные | 2 699 218 / 2 699 218 / 0 / 0 / 0 |
| Статус задачи | done |
| Ориентир SPEC §4: ≤ 300 с | да (237 с ≤ 300 с) |
<!-- bench_ingest:end -->

<!-- fresh_clone_check:begin -->
## Проверка чистого клона (`scripts/fresh_clone_check.ps1`)

- Когда: 2026-10-11T22:50:34+06:00 (системное время), 35 с; итог: пройдена, exit 0.
- Машина: Microsoft Windows 10 Pro; Docker 29.8.2, Compose 5.5.1; git version 2.55.0.windows.5.
- Клон: https://github.com/portosatos/main.git, ветка main, коммит `5bea529 docs(decisions): ADR-055 bench, demo, fresh clone check and screenshots; commands in CLAUDE.md`; проект compose `health-tracker-fresh`, порты .env.example (`-DefaultPorts`): FRONTEND_PORT=5173, API_PORT=8000, MAILPIT_UI_PORT=8025, MAILPIT_SMTP_PORT=1025, POSTGRES_HOST_PORT=5433.

| Проверка | Пройдена | Подробности |
|---|---|---|
| git clone | да | https://github.com/portosatos/main.git, ветка main |
| .gitattributes: LF у *.sh, Dockerfile, *.conf | да | 11 файлов, не LF: нет |
| cp .env.example .env | да | .env из .env.example |
| docker compose up --build | да | проект health-tracker-fresh, 24 с до healthy |
| scripts/smoke.ps1 клона | да | exit 0; приложение http://localhost:5173, вход demo@example.com |

Вывод `scripts/smoke.ps1` клона:

```text
OK   api health http://localhost:8000/api/health -> 200
OK   mailpit ui http://localhost:8025/ -> 200
OK   frontend http://localhost:5173/ -> 200
OK   frontend login page http://localhost:5173/login -> 200
OK   api via frontend proxy http://localhost:5173/api/health -> 200
OK   demo login http://localhost:5173/api/auth/me -> 200 (demo@example.com)
OK   sse http://localhost:5173/api/events -> 200, first event in 64 ms
```
<!-- fresh_clone_check:end -->
