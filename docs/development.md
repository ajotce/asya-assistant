# Development

## Цель текущего этапа
Поддерживать и проверять текущее MVP-ядро:
- backend API + локальный Docker запуск;
- frontend PWA (чат/настройки/состояние);
- сессионный контекст, загрузку файлов и retrieval через embeddings;
- актуальность документации и проверок.

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

`make build-frontend` работает в двух режимах:
- если локально доступен `npm`, используется локальная сборка;
- если `npm` не установлен, автоматически используется `node:20-alpine` контейнер.

## Минимальная PWA-проверка (MVP)
```bash
# после сборки frontend
ls -la frontend/dist
ls -la frontend/dist/icons
cat frontend/dist/manifest.webmanifest
```

Критерии:
- в `dist` присутствуют `manifest.webmanifest` и иконки;
- приложение открывается через backend URL того же origin, что и `/api/*`;
- интерфейс корректно адаптируется для iPhone Safari и Mac;
- offline-режим и долгосрочное хранение чатов в браузере не добавляются.

## Правила этапа
- Не добавлять функции вне MVP.
- Не менять архитектуру без отдельного запроса.
- Не коммитить `.env` и реальные ключи.
- Для локального MVP frontend должен открываться через backend URL (same-origin с `/api`).
