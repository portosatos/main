# API

Полная схема — OpenAPI: `http://localhost:8000/docs` (Swagger сам добавляет заголовок `X-Requested-With: ht`) или
`/openapi.json`. Здесь — правила, которых нет в схеме. Все маршруты, кроме `/api/health` и `/api/auth/register|login`,
требуют cookie сессии `ht_session` (без неё → 401) и отдают только данные пользователя этой сессии. Список маршрутов —
SPEC §6.3. Разделы дополняются по мере появления маршрутов.

## Сводки (`/api/summary/*`, SPEC F6–F7, ADR-037, ADR-038)

Читают `daily_summaries`. **Дата без строки — `no_data`:** `wear_minutes = 0`, `night_valid = false`, все метрики и
`sleep_start`/`sleep_end` — `null`, не 0. Даты — локальные даты пользователя (по истории поясов, ADR-033).

| Запрос | Ответ |
|---|---|
| `GET /api/summary/day?date=2026-10-07` | `{day, previous, delta}` — день, день D−1 и разница |
| `GET /api/summary/week?week=2026-W41` | `{week, start, end, days[7], metrics, previous, delta}` |
| `GET /api/summary/range?from=2026-10-01&to=2026-10-31` | массив дней, обе границы включительно |

**День** (`DayOut`): `date, status (no_data|partial|complete), wear_minutes, steps, active_minutes, sleep_minutes,
sleep_start, sleep_end, night_valid, resting_hr, peak_hr, goals`. Пульс округлён до 0,1. `goals` — прогресс целей
(раздел «Цели»).

**Разница** (`delta`): по каждой из метрик `steps, active_minutes, sleep_minutes, resting_hr, peak_hr` —
`{abs, pct}` или `null` («нет данных для сравнения»):
- `abs` — текущее минус прошлое, `pct` — процент от прошлого, оба округлены до 0,1 и считаются от показанных
  (уже округлённых) значений; `pct = null`, если прошлое значение 0;
- `null`, если значения нет хотя бы с одной стороны;
- в дневной сводке разница по сну — только если обе ночи валидны (`night_valid = true`), иначе `null` (ADR-037).
  Шаги, активность и пульс сравниваются по любым непустым значениям, в том числе в дни `partial`.

**Неделя:** ISO-неделя `YYYY-Www`, пн–вс локальных дат. `metrics.<метрика> = {value, days, of: 7}`: `value` —
значение по базе, `days` — размер базы («шаги: 3 из 7 дней»), при пустой базе `value = null`, `days = 0`.

| Метрика | `value` | База |
|---|---|---|
| `steps`, `active_minutes` | среднее | дни `complete` |
| `sleep_minutes` | среднее | валидные ночи, при любом статусе дня |
| `resting_hr` | среднее | дни, где посчитан |
| `peak_hr` | максимум | дни, где посчитан |

Средние округлены до 0,1. `goals.{steps|sleep} = {achieved_days, of: 7}` — «цель выполнена N из 7 дней».
`previous` — то же для предыдущей ISO-недели (`{week, start, end, metrics, goals}`, без дней), `delta` — разница
значений недели и предыдущей.

**Ошибки (422):** неделя не в формате `YYYY-Www` (`2026-w41`, `2026-41`, `2026-W5`), недели нет в году (`W00`,
`W54`, `W53` 52-недельного года, например `2025-W53`); `from` позже `to`; диапазон длиннее 366 дней; параметр не
передан или дата не `YYYY-MM-DD`.

Пример (неделя с пропуском):
```json
{"week": "2026-W41", "start": "2026-10-05", "end": "2026-10-11",
 "metrics": {"steps": {"value": 9000.0, "days": 3, "of": 7},
             "sleep_minutes": {"value": 450.0, "days": 3, "of": 7}, "...": "..."},
 "days": [{"date": "2026-10-08", "status": "no_data", "wear_minutes": 0, "steps": null, "...": "..."}],
 "previous": {"week": "2026-W40", "...": "..."},
 "delta": {"steps": {"abs": 3000.0, "pct": 50.0}, "sleep_minutes": null, "...": "..."}}
```

## Текущий пользователь (`/api/auth/*`, ADR-041)

`POST /api/auth/register`, `POST /api/auth/login` и `GET /api/auth/me` отдают
`{id, email, notify_email, today, timezone}`. `today` — локальная дата пользователя «сейчас»: время `Clock` (в dev —
со сдвигом dev-панели) в поясе, который действует в этот момент по истории поясов; `timezone` — этот пояс (ADR-051).
Дашборд без даты в адресе открывается на этот день; время в интерфейсе показывается в этом поясе.

## Устройства (`/api/devices`, SPEC F2, ADR-041)

| Запрос | Ответ |
|---|---|
| `GET /api/devices` | устройства пользователя по порядку регистрации: `{id, external_id, kind (watch\|phone), name, created_at, last_data_at}` |
| `PATCH /api/devices/{id}` с `{name}` | устройство с новым именем; событие `devices.changed` вкладкам пользователя |

- `last_data_at` — начало последней минуты, которую покрывает хоть одна запись устройства (шаги, сон, пульс;
  `coverage_minute`), или `null`, если записей нет.
- Имя обрезается по краям; пустое или длиннее 100 символов → 422. Чужое или несуществующее устройство → 404.
  Устройства создаёт загрузка (SPEC F2), тип и `external_id` не меняются.

## Цели (`/api/goals`, SPEC F8, ADR-043)

| Запрос | Ответ |
|---|---|
| `GET /api/goals` | `[{kind: "steps", target, valid_from}, {kind: "sleep", target, valid_from}]` — цели, действующие сейчас |
| `PUT /api/goals` с `{steps, sleep}` | то же после изменения; событие `goal.changed {kinds}` |

- `steps` — шагов в день, целое 100–100 000; `sleep` — часов сна, 1–16 (дробное, например 7.5). Оба поля обязательны,
  иначе 422. По умолчанию 8000 и 8, `valid_from = null`.
- Изменённая цель — новая версия с `valid_from` = «сейчас» по `Clock`; действует с локальной даты `valid_from`, прошлые
  дни считаются по своей цели. Те же значения ещё раз — без новой версии и без события.
- Прогресс дня в сводках: `goals.steps|sleep = {target, percent, achieved}`. `target` — цель того дня; `percent` —
  процент от цели, округлён вниз, `null` без значения; `achieved` — значение ≥ цели. Сон — день пробуждения.
- Достижение (первое выполнение цели за дату) создаётся при пересчёте сводок — по ходу загрузки, а не в конце — и
  после `PUT`, изменившего цель, для сегодняшнего дня: уведомление и события `notification.created`, `goal.achieved`.
  Повторно за ту же дату и вид — никогда.

## Уведомления (`/api/notifications`, SPEC F8, ADR-043)

| Запрос | Ответ |
|---|---|
| `GET /api/notifications?limit=50` | `{items: [{id, type, payload, created_at, read_at}], unread}` — новые сверху, `limit` 1–200; `unread` — все непрочитанные |
| `POST /api/notifications/read` с `{ids: [...]}` или `{}` | `{unread}`; без `ids` — прочитаны все; событие `notifications.read` |

- `type = "goal.achieved"`: `payload = {kind, local_date, target, value}` (`value` — шаги или часы с точностью 0,1).
- `type = "recommendation.opened"`: `payload = {recommendation_id, rule_code, title, anchor_date}` (ADR-048).
- `ids` — до 100; чужие и уже прочитанные игнорируются без ошибки.

## Правила (`/api/rules`, SPEC F9, ADR-048)

| Запрос | Ответ |
|---|---|
| `GET /api/rules` | `[{code, title, description, params, enabled, changed_at}]` — R1–R6 по порядку каталога |
| `PATCH /api/rules/{code}` с `{enabled}` | правило после изменения; неизвестный код → 404 |

- Нет записи в `user_rules` — правило включено, `changed_at = null`. Переключение в то же состояние ничего не меняет.
- Выключение закрывает открытую рекомендацию правила: `status = closed_rule_disabled`, `resolve_reason = rule_disabled`,
  событие `recommendation.resolved`. Включение сразу оценивает правила (может прийти `recommendation.opened`). Затем —
  `rule.toggled {code, enabled}`.

## Рекомендации (`/api/recommendations`, SPEC F9, ADR-048)

| Запрос | Ответ |
|---|---|
| `GET /api/recommendations?status=…&rule=R1&limit=200` | `[{id, rule_code, title, status, opened_at, anchor_date, context, resolved_at, resolve_reason, feedback, feedback_at}]` — новые сверху |
| `PUT /api/recommendations/{id}/feedback` с `{value: "useful" \| "not_useful"}` | рекомендация; событие `recommendation.feedback {id, feedback}` |
| `DELETE /api/recommendations/{id}/feedback` | рекомендация без отметки (`feedback`, `feedback_at` — `null`); событие с `feedback: null` |

- `status` — `open`, `resolved`, `closed_rule_disabled`, можно повторять: вкладка «Активные» — `status=open`, «История» —
  `status=resolved&status=closed_rule_disabled`. Без `status` — все. `limit` 1–500. Неизвестные значения → 422.
- `resolve_reason`: `auto` — закрыта условием правила, `rule_disabled` — правило выключено.
- Отзыв можно поставить на любую рекомендацию. Та же отметка ещё раз — без изменений и без события. Чужая или
  несуществующая рекомендация → 404.

## Дайджесты (`/api/digests`, SPEC F10, ADR-050, `docs/EMAIL.md`)

| Запрос | Ответ |
|---|---|
| `GET /api/digests?limit=20` | `{notify_email, warning, pending, items: [{id, status, local_date, planned_at, plan_reason, sent_at, to_email, subject, recommendations, error}]}` — сначала запланированный, потом отправленные (новые сверху); `limit` 1–100 |

- `status`: `planned` — запланирован (у пользователя не больше одного), `sent` — отправлен. План пересчитывает диспетчер
  воркера раз в 30 с: новая рекомендация попадает в запланированный дайджест в пределах тика.
- `plan_reason`: `window` (15 мин после последней рекомендации), `max_delay` (60 мин после первой), `daily_limit`
  (дайджест за эти местные сутки уже был — 00:00 следующих), `quiet_hours` (конец тихих часов).
- `local_date` — местная дата времени плана (у отправленного — дата отправки); `recommendations` — ожидающие записи
  (у запланированного) или рекомендации в письме (у отправленного). `to_email` и `subject` — после отправки.
- `error` — последняя неудачная отправка (SMTP недоступен, таймаут 10 с); следующий тик повторяет, успех очищает.
- `warning: "no_notify_email"` — почта для писем не указана: письма не планируются и не отправляются, записи ждут.

## Настройки (`/api/settings`, SPEC F10, F11, ADR-051, `docs/TIMEZONES.md`)

| Запрос | Ответ |
|---|---|
| `GET /api/settings` | `{notify_email, quiet_enabled, quiet_start, quiet_end, timezone}` |
| `PATCH /api/settings` `{"notify_email": "me@example.com", "quiet_enabled": true, "quiet_start": "22:00", "quiet_end": "08:00"}` | то же; любые поля из четырёх |
| `GET /api/settings/timezones` | `{current, items: [{tz, valid_from, valid_to, current}]}` — история, новые сверху |
| `POST /api/settings/timezones` `{"tz": "America/New_York", "valid_from": "2026-10-05T08:00"}` | 201, история целиком |

- PATCH меняет только переданные поля; значение, равное текущему, ничего не меняет и событий не шлёт. Лишнее поле
  (например, `timezone`) → 422: пояс меняется только через историю.
- `notify_email`: адрес или `""`/`null` — писем не будет (`warning: "no_notify_email"` в `/api/digests`).
- `quiet_start`, `quiet_end` — местное время строго `HH:MM` (`7:15`, `07:15:30`, `24:00` → 422); через полночь можно;
  начало, равное концу, — тихие часы выключены (ADR-017). Диспетчер подхватывает изменения на следующем тике (30 с).
- `timezone` и `current` — пояс, действующий сейчас (`Clock`) по истории.
- `tz` — имя из базы IANA, с учётом регистра (`europe/moscow`, `UTC+3` → 422). `valid_from`: без поля — сейчас;
  со смещением — как есть; **без смещения — местное время нового пояса**. Позже `Clock.now()` или раньше 1970 → 422.
  Момент, где уже есть запись, или пояс, который в этот момент уже действует, → 409.
- Запись действует до следующей (`valid_to`), поздние записи не удаляются. Если переезд раньше всей истории, прежний
  первый пояс остаётся на время до переезда — запись с `valid_from: null` («с начала истории»).
- После `POST` воркер пересчитывает затронутые даты (`summary.updated`) и оценивает правила — задача `tz_changed`.

## Приём данных (`/api/ingest/*`, SPEC F3, ADR-031, ADR-052, `docs/DATA_FORMAT.md`)

- `POST /api/ingest/files` (multipart, поле `file`, до 500 МБ) и `POST /api/ingest/batch`
  (`{"devices": [...], "records": [...]}`, до 5000 записей, больше → 413) → `202 {"job_id"}`; обрабатывает воркер.
- `GET /api/ingest/jobs?limit=50` (новые сначала, `limit` 1–200), `GET /api/ingest/jobs/{id}` — отчёт; чужая задача
  → 404. `source` — `file` или `stream`; у пачки `filename: null`, `line` в `errors` — номер записи в `records` с 1.
- Правила: в конце задачи файла — сразу; после пачек потока — через 10 с по `Clock`, пачки за эти 10 с
  присоединяются к ждущей оценке (задача `evaluate_rules`).

## События (`GET /api/events`, SSE, SPEC F12, ADR-039)

Поток Server-Sent Events пользователя сессии (без cookie → 401; API ещё не слушает БД → 503 через 5 с). Каждое
событие — `event: <тип>` и `data: <JSON>`; раз в 15 с (`SSE_PING_S`) — комментарий-keep-alive (`: ping - …`). Событие
доходит до всех открытых вкладок пользователя за ≤ 2 с после коммита, другим пользователям не приходит. Данные
маленькие — идентификаторы и даты; сами данные интерфейс перезапрашивает через REST.

| Событие | Данные | Когда |
|---|---|---|
| `ready` | `{}` | первым, сразу после подписки: дальше поток не пропускает событий |
| `resync` | `{}` | события могли потеряться (API переподключился к БД, вкладка не успевала читать) — перезапросить всё |
| `ingest.progress` | `{job_id, status, bytes_done, bytes_total, counts}` | задача поставлена (`queued`), начата или возобновлена (`processing`), после пачки — не чаще раза в 1 с (не реже раза в 2 с) |
| `ingest.done` | то же, `status` — `done` или `failed` | задача закончена |
| `summary.updated` | `{dates: ["2026-10-01", …]}` | пересчитаны сводки этих локальных дат (по ходу загрузки, не реже раза в ~2 с); длинный список приходит несколькими событиями |
| `devices.changed` | `{device_id}` | устройство переименовано (`PATCH /api/devices/{id}`) |
| `goal.changed` | `{kinds: ["steps", "sleep"]}` | цели изменены (`PUT /api/goals`) |
| `notification.created` | `{id, type}` | новое уведомление в колокольчике; приходит перед своим `goal.achieved` |
| `goal.achieved` | `{kind, local_date, target, value, show_toast, notification_id}` | цель выполнена впервые за дату; тост — только при `show_toast` (дата — сегодня или вчера по `Clock`) |
| `notifications.read` | `{ids: [...]}` или `{all: true}` | уведомления отмечены прочитанными |
| `recommendation.opened` | `{id, rule_code, anchor_date}` | открыта рекомендация (в конце загрузки файла, через 10 с после пачек потока, по таймеру воркера, при включении правила, после смены пояса); перед ним — `notification.created` |
| `recommendation.resolved` | `{id, rule_code, status}` | рекомендация закрыта: `status` — `resolved` (условием правила) или `closed_rule_disabled` |
| `recommendation.feedback` | `{id, feedback}` | отзыв поставлен, изменён или снят (`null`) |
| `rule.toggled` | `{code, enabled}` | правило включено или выключено |
| `digest.sent` | `{id, local_date, count}` | дайджест отправлен (`count` — рекомендаций в письме) |
| `settings.changed` | `{fields: ["quiet_enabled", …]}` | изменены настройки (`PATCH /api/settings`, поля — изменённые) или добавлен пояс (`{fields: ["timezone"]}`) |

`counts = {new, duplicate, conflict, invalid}` — как в отчёте `GET /api/ingest/jobs/{id}`. Прогресс —
`bytes_done / bytes_total`.
