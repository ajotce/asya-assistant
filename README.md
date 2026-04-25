# Asya Assistant (MVP)

Asya — персональный ИИ-ассистент в формате PWA с локальным backend.

Репозиторий: `ajotce/asya-assistant`

## Один сценарий запуска с нуля

### 1. Подготовка окружения
Нужны:
- Docker + Docker Compose
- `python3` (для `make test`)

### 2. Подготовка переменных
```bash
cp .env.example .env
```

По умолчанию приложение будет доступно на `http://localhost:8000`.
Если измените `ASYA_PORT` в `.env`, используйте свой порт.

### 3. Сборка frontend
```bash
make build-frontend
```

### 4. Запуск backend + раздача frontend
```bash
docker compose up --build
```

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

Frontend unit-тесты:
```bash
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm test"
```

## Документы проекта
- `AGENTS.md`
- `asya-mvp-tech-spec.md`
- `asya-mvp-development-plan.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/testing.md`
