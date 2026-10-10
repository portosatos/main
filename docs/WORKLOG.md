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
