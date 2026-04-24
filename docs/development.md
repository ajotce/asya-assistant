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
