# Development Guide

## Требования
- Docker и Docker Compose
- Python 3.12+ (для локального запуска backend в будущем)
- Node.js 20+ (для локального запуска frontend в будущем)

## Команды
```bash
cp .env.example .env
docker compose up --build
```

## Backend skeleton (этап 1)
Локальный запуск backend:
```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Проверка health-check:
```bash
curl http://127.0.0.1:8000/api/health
```

Запуск тестов backend:
```bash
cd backend
python3 -m pytest -q
```

## VseLLM (этап 5: список моделей)
Переменные окружения:
```env
VSELLM_API_KEY=
VSELLM_BASE_URL=https://api.vsellm.ru/v1
```

Правила безопасности:
- API-ключ хранится только на backend в `.env`.
- API-ключ нельзя передавать во frontend.
- API-ключ нельзя логировать.

Проверка endpoint:
```bash
curl http://127.0.0.1:8000/api/models
```

Типовые ошибки:
- не задан `VSELLM_API_KEY` -> `503`;
- неверный ключ -> `401/403`;
- rate limit -> `429`;
- проблемы сети/доступности VseLLM -> `502/504`.

## Streaming chat (этап 8)
Проверка streaming endpoint:
```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session-1","message":"Привет"}'
```

Ожидается `text/event-stream` с событиями `token`, `error` (если есть проблема), `done`.

## Полезные make-команды
```bash
make dev
make test
make lint
make build-frontend
```

## Правила работы с `.env`
- Использовать `.env.example` как шаблон.
- Никогда не коммитить `.env`.
- Не хранить реальные секреты в репозитории.

## Git workflow (обязательно)
- Работать маленькими логическими шагами по этапам из `asya-mvp-development-plan.md`.
- После каждого завершенного шага:
  - запустить доступные проверки;
  - сделать осмысленный commit;
  - выполнить push в GitHub.
- Рекомендуемый режим: отдельная рабочая ветка под этап и merge после проверки.
- Не делать бессмысленные commit-сообщения (`update files`, `fix stuff`).
- Не коммитить `.env`, реальные ключи и секреты.

## Добавление backend endpoint-ов
- Использовать префикс `/api/*`.
- Описывать модели запросов/ответов через Pydantic.
- Сохранять совместимость OpenAPI.

## Обновление frontend API-типов
- Для каждого endpoint создавать/обновлять типы в `frontend/src/types/`.
- Не использовать `any` без необходимости.
