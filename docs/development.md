# Development

## Цель текущего этапа
Поддерживать и проверять базовую структуру проекта:
- `frontend/`
- `backend/`
- `docs/`
- базовые конфигурационные файлы в корне репозитория.

## Базовые команды запуска
```bash
cp .env.example .env
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm run build"
docker compose up --build
```

## Локальный Docker запуск backend
```bash
docker compose up -d --build
docker compose ps
curl http://localhost:${ASYA_PORT}/api/health
curl -I http://localhost:${ASYA_PORT}/
curl -I http://localhost:${ASYA_PORT}/manifest.webmanifest
```

Если нужно посмотреть логи:
```bash
docker compose logs -f backend
```

Остановка:
```bash
docker compose down
```

## Локальные команды проверки
```bash
make test
make build-frontend
```

## Правила этапа
- Не добавлять функции вне MVP.
- Не менять архитектуру без отдельного запроса.
- Не коммитить `.env` и реальные ключи.
- Для локального MVP frontend должен открываться через backend URL (same-origin с `/api`).
