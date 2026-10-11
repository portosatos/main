# Статус проекта

> Заполнен на шаге 13.2 (2026-10-11). Статусы: **работает** — проверка из SPEC §9 выполнена полностью;
> **частично** — выполнена не вся; **нет** — не сделано. Блоки между метками `<!-- …:begin -->` и
> `<!-- …:end -->` пишут скрипты `scripts/bench_ingest.*` и `scripts/fresh_clone_check.*` — руками их не правят.
> Проверяет файл `python scripts/check_docs.py`.

## Критерии готовности (SPEC §9)

Последние прогоны: `scripts/test.ps1 -All` 2026-10-11 22:51–22:59 (шаг 13.1) → exit 0: backend 321 passed, генератор 54,
`scripts/tests` 8, e2e 40 (сценарии 01–10, хелперы и 20 скриншотных); на шаге 13.2 — `scripts/test.ps1` без e2e (итог —
в [WORKLOG](WORKLOG.md)); frontend `npm --prefix frontend run check` → 51 тест. CI — job'ы backend, generator, frontend,
e2e, process в `.github/workflows/ci.yml`.

| # | Критерий | Статус | Чем доказано |
|---|---|---|---|
| 1 | Запуск одной командой | работает | `scripts/fresh_clone_check.ps1 -DefaultPorts` на Windows → exit 0: клон, `.env` из `.env.example`, `docker compose up --build`, `:5173` и демо-вход (блок ниже); ADR-055 |
| 2 | Приём сна, шагов, пульса | работает | e2e `02-upload.spec.ts` (отчёт загрузки, сводка заполнена); `test_classify.py`, `test_ingest_jobs.py`, `test_generator_contract.py::test_htgen_output_zero_invalid_zero_conflict` |
| 3 | Генератор: период и пропуски | частично | Генератор: 54 теста (`test_gaps_tz.py::test_random_gaps_bounded_by_max_hours`, `test_explicit_gap_has_no_records_for_device`), `htgen --days 90 --gap-prob 0.05` → exit 0 (шаг 6.1). **Не выполнено:** пропуски `--gap-prob` выпадают у одного устройства, второе их закрывает, и дашборд «нет данных» не показывает. Виден явный `--gap` без `@device`: e2e `05-gap.spec.ts`, демо (`scripts/demo.ps1`), скриншот `screenshots/dashboard-week-1280.png` |
| 4 | Несколько устройств, без суммы шагов | работает | property-тест `test_merge.py::test_merged_minute_single_source_never_sum`; `test_day_metrics.py::test_phone_only_walk_plus_both_walk_day_equals_5000`; `test_merge.py::test_walk_both_devices_watch_wins_2000` |
| 5 | Невыровненные интервалы не теряются | работает | `test_minutes.py::test_adjacent_unaligned_intervals_minute_0801_equals_60`; property-тест `test_minutes.py::test_sum_steps_minute_equals_sum_raw` |
| 6 | Большой файл не блокирует UI | работает | `scripts/bench_ingest.ps1`: 197 МБ за 237,5 с (≤ 300 с), пик памяти воркера 66 MiB, p95 `GET /api/summary/day` во время обработки 19 мс (блок ниже); e2e `02-upload.spec.ts` (переход по страницам во время загрузки). Ручная проверка пользователем (загрузка ~200 МБ через UI) не подтверждена |
| 7 | Сводка обновляется по мере обработки | работает | e2e `02-upload.spec.ts` (данные до `ingest.done`); `test_summaries.py::test_summaries_exist_before_job_done`; `test_events.py::test_summary_updated_contains_dates` |
| 8 | Повторная загрузка без дублей | работает | `test_ingest_jobs.py::test_reupload_same_file_zero_new_all_duplicate`; `test_classify.py::test_same_key_different_count_conflict_first_kept`, `test_overlapping_steps_different_bounds_conflict`; `test_ingest_batch.py::test_stream_then_file_all_duplicate_totals_unchanged`; e2e `03-reupload.spec.ts` |
| 9 | Пропуск = нет данных; правила не срабатывают | работает | `test_day_metrics.py::test_no_data_day_steps_null_not_zero`; `test_rule_engine.py::test_unknown_leaves_state_unchanged`, `test_r1.py::test_invalid_night_in_window_unknown`, `test_r2.py::test_partial_day_in_window_unknown`; e2e `05-gap.spec.ts` |
| 10 | Дневная и недельная сводки со сравнением | работает | `test_summary_api.py::test_day_summary_with_delta_vs_previous_day`, `test_week_sleep_avg_over_valid_nights_including_partial_days`, `test_week_steps_avg_over_complete_days_only`; скриншоты `screenshots/dashboard-day-1280.png`, `screenshots/dashboard-week-1280.png` |
| 11 | Цели и прогресс; уведомление сразу | работает | `test_goals.py::test_achievement_created_once_when_data_crosses_threshold_mid_ingest`, `test_reupload_does_not_create_second_achievement`, `test_week_progress_n_of_7`; e2e `09-goal-toast.spec.ts` |
| 12 | Правила R1–R6, видны, отключаются | работает | unit `test_r1.py`–`test_r6.py`; `test_rules_api.py::test_disable_closes_open_as_closed_rule_disabled`; `test_rule_engine_db.py::test_evaluate_user_skips_rule_disabled_by_user`; e2e `10-disabled-rule.spec.ts`; скриншот `screenshots/rules-1280.png` |
| 13 | Нет ежедневного повтора, автозакрытие | работает | `test_rule_engine.py::test_no_duplicate_while_still_true_next_day`, `test_resolves_on_close_condition`; `test_rule_engine_db.py::test_evaluate_user_opens_once_and_resolves`; e2e `06-rule-mail-resolve.spec.ts` |
| 14 | Рекомендации за день — в одном письме | работает | `test_planner.py::test_three_recs_within_window_send_15_min_after_last`, `test_recs_every_10_min_capped_60_min_after_first`, `test_after_todays_digest_new_rec_goes_tomorrow`; `test_dispatcher.py::test_one_email_with_all_pending`; e2e `08-digest-limit.spec.ts` |
| 15 | Тихие часы откладывают письма | работает | `test_planner.py::test_quiet_hours_across_midnight`, `test_rec_in_quiet_hours_sends_at_quiet_end`, `test_daily_limit_rechecked_after_quiet_shift`; e2e `07-quiet-hours.spec.ts` |
| 16 | История рекомендаций с отзывом | работает | `test_recommendations_api.py::test_feedback_set_change_clear_with_timestamp`, `test_feedback_emits_event`; e2e `04-two-tabs.spec.ts` («Полезно» во второй вкладке), `10-disabled-rule.spec.ts` (история); скриншот `screenshots/recommendations-1280.png` |
| 17 | Сон в правильный день | работает | `test_sleep.py::test_sleep_2340_0710_attributed_to_wake_day`; `test_goals.py::test_sleep_goal_counted_on_wake_day` |
| 18 | Смена пояса без потерь и удвоений | работает | `test_summaries.py::test_tz_move_period_sum_equals_sum_of_merged_minutes`; `test_localtime.py::test_msk_to_nyc_move_day_is_31h`; `test_tz_change.py::test_tz_change_preserves_period_totals`, `test_past_tz_change_recomputes_affected_dates` |
| 19 | Две вкладки | работает | e2e `04-two-tabs.spec.ts` (загрузка, отключение правила и отзыв видны во второй вкладке); `test_events.py::test_other_user_does_not_receive_events` |
| 20 | Изоляция пользователей, dev-эндпоинты закрыты | работает | `test_security_sweep.py::test_all_id_routes_return_404_for_other_users_resources`, `test_all_mutating_routes_require_csrf_header`, `test_all_dev_routes_404_in_prod`; `test_summary_api.py::test_summary_returns_only_own_data` |
| 21 | Скрипты работают после клона на Windows | работает | `.gitattributes`; `fresh_clone_check.ps1`: LF у 11 файлов (`*.sh`, `Dockerfile`, `*.conf`), smoke клона 7/7 (блок ниже); CI job `process` (`git ls-files --eol`); у каждого `.sh` есть `.ps1` |
| 22 | Процесс прозрачен | работает | `python scripts/check_process.py --all` → exit 0; коммиты по фичам с `Stage: X.Y` и тестами до кода (`git log`); [WORKLOG](WORKLOG.md), [DECISIONS](DECISIONS.md) (ADR-001–055), [PROMPTS](PROMPTS.md), [`CLAUDE.md`](../CLAUDE.md); CI зелёный (`gh run list --branch main --limit 1`) |
| 23 | Честный статус | работает | Этот файл и [NEXT](NEXT.md); `python scripts/check_docs.py` → exit 0; невыполненное помечено (#3 — «частично», «Известные проблемы» ниже) |

## Известные проблемы и ограничения

- **Пропуски `--gap-prob` не видны на дашборде** (#3): случайный пропуск бывает у одного устройства, второе закрывает
  эти минуты. Для видимого пропуска — явный `--gap FROM/TO` без `@device` (так делают e2e 05 и демо).
- **Один воркер — одна задача за раз.** Большой файл одного пользователя задерживает загрузку другого; параллельность
  есть только при `docker compose up --scale worker=2` (не проверялось на стеке). См. [NEXT](NEXT.md).
- **Обработка 200 МБ — 237 с при ориентире 300 с** (запас ~20 %) на i5-12400F; на слабой машине может не уложиться.
  Postgres во время замера занимал ~2 ГиБ.
- **Ручные проверки шагов 13.1 и 13.2** (загрузка ~200 МБ через UI, `demo.ps1` с нуля, README в чистой папке) со слов
  пользователя пока не подтверждены.
- Только dev-развёртывание: HTTPS, бэкапов и мониторинга нет; почта — только Mailpit (SPEC §10).
- `scripts/demo.ps1 -Reset` стирает все данные dev-стека (`docker compose down -v`).

## Замеры производительности

Блоки ниже пишут скрипты; повторить — `scripts/bench_ingest.ps1` и `scripts/fresh_clone_check.ps1` на запущенном стеке.

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
