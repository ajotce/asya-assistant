# Asya Assistant (MVP)

Asya — персональный ИИ-ассистент в формате PWA-веб-приложения с локальным backend.

Репозиторий: `ajotce/asya-assistant`  
Текущий фокус: базовая структура проекта и документация MVP.

## Базовая структура
- `frontend/` — React + Vite + TypeScript.
- `backend/` — FastAPI + Docker.
- `docs/` — документация и решения по MVP.

## Быстрый старт
```bash
cp .env.example .env
docker compose up --build
```

## Базовые команды
```bash
make dev
make test
make lint
make build-frontend
```

## Важные документы
- `AGENTS.md`
- `asya-mvp-tech-spec.md`
- `asya-mvp-development-plan.md`
