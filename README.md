# Asya Local

Asya Local — локальная PWA-версия персонального ИИ-ассистента Asya с backend на FastAPI.

Репозиторий: `ajotce/asya-assistant`

## Один сценарий запуска с нуля

### 1. Подготовка окружения
Нужны:
- Docker + Docker Compose
- `python3` (локально, если запускаете backend тесты без контейнера)

### 2. Подготовка переменных
```bash
cp .env.example .env
```

По умолчанию приложение доступно на `http://localhost:8000`.
Если вы измените `ASYA_PORT` в `.env`, используйте свой порт.

### 3. Сборка frontend
```bash
make build-frontend
```

### 4. Запуск backend + раздача frontend
```bash
docker compose up --build
```

Compose поднимет два сервиса:
- `backend`
- `document-converter` (LibreOffice headless для DOCX → PDF)

При старте backend автоматически запускает Alembic bootstrap:
- для чистой БД применяется `upgrade head`;
- для legacy БД 0.2 без `alembic_version` выполняется безопасный `stamp` до `20260502_03` и затем `upgrade` до актуальной схемы v0.3.

### 5. Проверка, что всё поднялось
В новом терминале:
```bash
PORT=$(grep '^ASYA_PORT=' .env | cut -d= -f2)
curl "http://localhost:${PORT}/api/health"
curl "http://localhost:${PORT}/" | head -n 2
curl "http://localhost:${PORT}/manifest.webmanifest" | head -n 2
```

Ожидаемо:
- `/api/health` возвращает `200` и JSON со `status: "ok"`;
- `/` возвращает HTML (начинается с `<!doctype html>`);
- `/manifest.webmanifest` возвращает JSON манифеста.

### 6. Остановка
```bash
docker compose down
```

## Основные команды разработки
```bash
make lint            # frontend ESLint
make build-frontend  # сборка frontend
make test            # backend pytest
```

Backend требует Python `>=3.12`. Если локально версия ниже (например, 3.9), используйте контейнерные команды:

```bash
make backend-py312-pytest
make backend-py312-ruff
make backend-py312-mypy
make backend-py312-all
```

Frontend unit-тесты:
```bash
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm test"
```

## Alpha/Beta onboarding (v0.4)

- Публичная форма: `POST /api/access-requests`.
- Admin approve/reject: `/api/admin/access-requests/*`.
- При approve создаётся one-time setup link (`/setup-password?token=...`) для задания пароля.
- Это не passwordless login: после setup пользователь входит через обычный email+password.

## Production запуск (Caddy)

- Локальный сценарий остаётся через `docker-compose.yml`.
- Production: `docker compose -f docker-compose.prod.yml up --build -d`.

## DOCX → PDF converter

Для конвертации документов backend использует отдельный сервис `document-converter`.
Нужные env-переменные:
- `DOC_CONVERTER_ENABLED=true`
- `DOC_CONVERTER_URL=http://document-converter:8090`
- `DOC_CONVERTER_TIMEOUT_SECONDS=30`

## Документы проекта
- `AGENTS.md`
- `CLAUDE.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/testing.md`
- `docs/development-log.md`
- `docs/decisions.md`
- `docs/archive/mvp/asya-mvp-tech-spec.md`
- `docs/archive/mvp/asya-mvp-development-plan.md`
- `docs/archive/mvp/codex-mvp-completion-prompts.md`
