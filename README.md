# Asya Assistant (MVP)

Asya — персональный ИИ-ассистент в формате PWA-веб-приложения с локальным backend.

Репозиторий: `ajotce/asya-assistant`  
Текущий этап: базовая структура проекта и инфраструктура MVP.

## Структура проекта
- `frontend/` — React + Vite + TypeScript (PWA интерфейс).
- `backend/` — FastAPI + Docker (локальный API).
- `docs/` — документация, решения и журнал разработки.

## Быстрый старт
```bash
cp .env.example .env
docker compose up --build
```

Backend будет доступен по адресу `http://localhost:${ASYA_PORT}` (по умолчанию `8000`).

Проверка health endpoint:
```bash
curl http://localhost:${ASYA_PORT}/api/health
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
make build-frontend  # сборка frontend
make lint            # пока заглушка для будущей lint-конфигурации
```

## Обязательные документы
- `AGENTS.md`
- `asya-mvp-tech-spec.md`
- `asya-mvp-development-plan.md`
