# Development Log

## 2026-04-25
- Что сделано:
  - Создан базовый каркас проекта (frontend/backend/docs).
  - Добавлены базовые конфигурационные файлы: `docker-compose.yml`, `Makefile`, `frontend/package.json`, `backend/pyproject.toml`, `backend/Dockerfile`.
  - Обновлен `README.md` и создана документация: `docs/decisions.md`, `docs/development.md`, `docs/testing.md`, `docs/api.md`.
  - В документацию добавлены явные правила Git workflow: коммит и push после каждого завершенного логического шага.
- Какие файлы изменены:
  - `README.md`
  - `docs/development.md`
  - `docs/development-log.md`
  - `docker-compose.yml`
  - `Makefile`
  - `frontend/*`
  - `backend/*`
  - `docs/*`
- Какие тесты запущены:
  - Нет (на этапе 0 тестовый контур еще не реализован).
- Какие проблемы остались:
  - Не реализован полноценный backend-каркас этапа 1.
  - Не реализован frontend-каркас этапа 2 с экранами Chat/Settings/Status.
- Следующий рекомендуемый шаг:
  - Этап 1: backend-каркас FastAPI с конфигурацией и health-check в Docker.
