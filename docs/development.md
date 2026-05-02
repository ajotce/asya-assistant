# Development

Документ описывает текущую практику разработки и приоритеты этапа Asya 0.3.

## 1. Приоритет этапа
Asya 0.3 = память + личность + пространства + memory feed + activity feed.

Не добавлять без отдельного запроса:
- внешние интеграции;
- голос;
- дневник;
- тихого наблюдателя;
- web search;
- биллинг.

## 2. Обязательный старт задачи
1. Проверить репозиторий и ветку (`0.2-multi-user`).
2. Проверить `git status`.
3. Прочитать `README.md`, `AGENTS.md`, `CLAUDE.md`.
4. Прочитать релевантные `docs/*`.
5. Изучить текущую реализацию до правок.
6. Сформировать короткий план.

## 3. Техническая база (не меняется)
- FastAPI + React/Vite/TS
- SQLite + SQLAlchemy + Alembic
- Docker Compose
- VseLLM/OpenAI-compatible API
- Backend-only хранение секретов (`VSELLM_API_KEY`, `MASTER_ENCRYPTION_KEY`)

## 4. Подход к реализации 0.3
- Маленькие завершённые этапы.
- Сначала DB schema + миграции, затем repository/service, затем API, затем UI.
- Строгая user isolation на каждом endpoint.
- Документация обновляется в том же PR/изменении, где меняется поведение.

## 5. Безопасность
- Никогда не коммитить `.env`, ключи, токены, приватные данные.
- Не выводить секреты в ответы и логи.
- Исключить cross-user data leakage.
- `Asya-dev` только для admin.

## 6. Базовые команды
```bash
make test
make lint
make build-frontend
```

## 7. Backend checks в окружении без Python 3.12

Backend проекта требует Python `>=3.12`. Если локально системный Python ниже, используйте контейнерные команды:

```bash
make backend-py312-pytest
make backend-py312-ruff
make backend-py312-mypy
make backend-py312-all
```

Это официальный fallback для машин, где локальный Python несовместим с backend.

Frontend unit tests:
```bash
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm test"
```
