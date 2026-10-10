# Трекер здоровья (Health Tracker)

> **Статус: в разработке.** Готовы скелет стека, миграции, служебное время (`Clock`), авторизация, страницы
> входа и dev-панель (шаги 0.1–1.3 из [`docs/plan.md`](docs/plan.md)) и основа генератора тестовых данных
> (шаг 2.1). Загрузки данных пока нет: она появится на этапе 3.
> Подробный ход работы — в [`docs/WORKLOG.md`](docs/WORKLOG.md).

Веб-приложение собирает данные с часов и телефона (шаги, сон, пульс), объединяет их без двойного счёта,
считает дневные и недельные сводки, ведёт цели, выдаёт рекомендации по правилам и присылает их на почту
дайджестом не чаще раза в сутки с учётом тихих часов. Полное ТЗ — [`docs/SPEC.md`](docs/SPEC.md).

## Чем делали

<!-- Заполняет пользователь: модель, инструмент и почему выбраны они. -->
_Раздел заполнит автор проекта._

## Предварительные требования

- Docker Desktop (Windows, macOS) или Docker Engine с Compose v2 (Linux).
- Git.
- Для разработки без Docker: Python 3.12 и [`uv`](https://docs.astral.sh/uv/), Node.js 22 LTS.

## Запуск

```bash
git clone https://github.com/portosatos/main.git health-tracker
cd health-tracker
docker compose up --build
```

`.env` не обязателен: у всех настроек есть значения по умолчанию. Чтобы их поменять, скопируйте
`.env.example` в `.env` (`cp .env.example .env` или `Copy-Item .env.example .env` в PowerShell).

После старта:

| Что | Адрес |
|---|---|
| Приложение (nginx, `/api` проксируется в api) | http://localhost:5173 |
| API и Swagger | http://localhost:8000/docs |
| Mailpit (письма) | http://localhost:8025 |
| PostgreSQL | `localhost:5433` |

Демо-пользователь создаётся при старте api: `demo@example.com` / `demo12345` (меняется через `DEMO_USER_*`
в `.env`). Все изменяющие запросы к API требуют заголовок `X-Requested-With: ht`; Swagger добавляет его сам.

Проверить, что стек работает: `scripts/smoke.ps1` (Windows) или `scripts/smoke.sh`.

## Тесты

```bash
scripts/test.sh
```

На Windows — `scripts/test.ps1`. Скрипт поднимает PostgreSQL из compose и запускает тесты backend, генератора
и утилит `scripts/`. Frontend: `npm ci --prefix frontend` (один раз), затем `npm --prefix frontend run check`.

## Тестовые данные

```bash
uv run --project generator htgen --days 7 --seed 1 --out sample.ndjson
```

Генератор `htgen` пишет NDJSON с часов и телефона: шаги, сон, пульс. Одинаковый seed даёт одинаковый файл.
Опции — `htgen --help`, формат и модели устройств — [`docs/DATA_FORMAT.md`](docs/DATA_FORMAT.md).

## Документация

- [`docs/SPEC.md`](docs/SPEC.md) — техническое задание.
- [`docs/plan.md`](docs/plan.md) — план по шагам и их статус.
- [`docs/WORKLOG.md`](docs/WORKLOG.md) — журнал работы с временными метками.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — принятые решения (ADR).
- [`docs/PROMPTS.md`](docs/PROMPTS.md) — указания заказчика дословно.
- [`docs/DATA_FORMAT.md`](docs/DATA_FORMAT.md) — формат входных данных и генератор `htgen`.
- [`CLAUDE.md`](CLAUDE.md) — правила работы агента и команды.

Демо-сценарий и отчёт о статусе требований появятся на этапе 13.
