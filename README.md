# Asya Assistant (MVP)

Asya — персональный ИИ-ассистент в формате PWA-веб-приложения с локальным backend.

Репозиторий: `ajotce/asya-assistant`  
Текущий этап: рабочее MVP-ядро (backend + базовый frontend + PWA + сессии + файлы + embeddings).

## Структура проекта
- `frontend/` — React + Vite + TypeScript (PWA интерфейс).
- `backend/` — FastAPI + Docker (локальный API).
- `docs/` — документация, решения и журнал разработки.

## Быстрый старт
```bash
cp .env.example .env
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm run build"
docker compose up --build
```

Backend будет доступен по адресу `http://localhost:${ASYA_PORT}` (по умолчанию `8000`).

Проверка health endpoint:
```bash
curl http://localhost:${ASYA_PORT}/api/health
```

Проверка, что frontend отдается backend (тот же origin):
```bash
curl -I http://localhost:${ASYA_PORT}/
curl -I http://localhost:${ASYA_PORT}/manifest.webmanifest
```

Запуск в фоне и просмотр статуса:
```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Остановка:
```bash
docker compose down
```

## Базовые команды
```bash
make dev             # локальный запуск через docker compose
make test            # backend тесты (pytest)
make build-frontend  # сборка frontend (через npm или через docker, если npm не установлен)
make lint            # frontend lint (ESLint для TypeScript + React)
```

## Обязательные документы
- `AGENTS.md`
- `asya-mvp-tech-spec.md`
- `asya-mvp-development-plan.md`
