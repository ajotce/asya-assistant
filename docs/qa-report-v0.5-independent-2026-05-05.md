# QA Report v0.5 (independent)

Дата проверки: 2026-05-05 (повторный независимый rerun)  
Ветка: `0.5-extended`  
Роль: независимая QA-проверка перед релизным решением.

Проверка по коду и документации:
- `docs/roadmap.md`
- `docs/acceptance/v0.5.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/integrations.md`
- `docs/integrations/github.md`
- `docs/security.md`

## Blocking issues

Не обнаружены.

## Major issues

Не обнаружены.

## Minor issues

1. В ответах diary API по-прежнему присутствует `source_audio_path` (`backend/app/api/routes_diary.py`).
Это не блокирует релиз по текущим критериям, но увеличивает раскрытие внутренней структуры хранения.

## Docs inconsistencies

Критичных расхождений между документацией и проверенным поведением не обнаружено.

## Проверка ключевых рисков

- Утечки setup token в логах (email/notifier): не обнаружены.
  - `backend/app/services/email_transport.py`: логируется только `to`, `subject`, `body_len`.
  - `backend/app/services/access_request_notifier.py`: для approve нет `setup_link`/`token` в логе.
- Bitrix fallback: при недоступном модуле endpoints возвращают `409`.
- GitHub read-only: write-методы для GitHub API routes отклоняются (`405`), read-routes работают в рамках текущих тестов.

## Запуск проверок

Backend quality gate (Python 3.12 в контейнере):
- `make backend-py312-pytest` -> OK (`169 passed`)
- `make backend-py312-ruff` -> OK
- `make backend-py312-mypy` -> OK (`Success: no issues found in 141 source files`)
- `alembic heads` -> OK (`20260502_08 (head)`)
- `alembic current` -> OK (`20260502_08 (head) (mergepoint)`)
- Отдельного migration-check скрипта в репозитории не найдено.

Frontend quality gate:
- `cd frontend && npm run lint` -> OK
- `cd frontend && npm test` -> OK (`7 files, 27 tests passed`)
- `cd frontend && npm run build` -> OK

Smoke-тесты integrations API:
- `pytest tests/test_integrations_api.py tests/test_github_api.py tests/test_bitrix_fallback_api.py` -> OK (`7 passed`)
- Дополнительный rerun smoke в `python:3.12-slim`:
  - `pytest tests/test_integrations_api.py tests/test_github_api.py tests/test_bitrix_fallback_api.py tests/test_access_request_notifier.py tests/test_email_transport.py tests/test_action_router_v05.py` -> OK (`19 passed`)

Примечание по локальному окружению QA:
- команды backend через локальный `python3.9` (вне контейнера) дают ожидаемые ошибки совместимости SQLAlchemy-аннотаций (`Mapped[str | None]`);
- это не дефект ветки `0.5-extended`, а ограничение локального рантайма QA-машины; релевантный gate для проекта — `py312`, он зелёный.

## Release recommendation

`ready`

Основание: все запрошенные quality gates зелёные, блокирующие security-проблемы логирования закрыты, fallback/read-only поведение интеграций подтверждено тестами.
