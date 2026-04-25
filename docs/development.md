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
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm test"
```

`make build-frontend` работает в двух режимах:
- если локально доступен `npm`, используется локальная сборка;
- если `npm` не установлен, автоматически используется `node:20-alpine` контейнер.

Frontend unit-тесты запускаются через `vitest` (`frontend/src/pages/StatusPage.test.tsx` проверяет ключевые карточки страницы состояния).

## Frontend Chat + Files (MVP)
- В `ChatPage` поддержан выбор до 10 файлов перед отправкой сообщения.
- Файлы проходят клиентскую проверку (тип/размер/лимит) до отправки.
- Если файлы выбраны, frontend сначала загружает их в `POST /api/session/{session_id}/files`, затем отправляет чат-запрос в `POST /api/chat/stream` с `file_ids`.
- При успешной отправке локальный список выбранных файлов очищается.
- При переключении вкладок `Чат`/`Настройки`/`Состояние` страницы не размонтируются повторно: уже открытые вкладки скрываются, поэтому runtime-состояние чата (текущая backend-сессия и видимая история) сохраняется до перезагрузки страницы.
- История чатов и долгосрочное хранение на frontend не добавляются.

## Страница «Состояние Asya» (MVP)
На `StatusPage` отображаются:
- backend online/offline;
- доступность VseLLM API и base URL без API-ключа;
- выбранная модель;
- статус VseLLM API-ключа;
- uptime backend;
- статус файлового контура;
- статус embeddings (статус + модель + последняя ошибка, если есть);
- активные runtime-сессии;
- usage по chat/embeddings/cost из `/api/usage` (если провайдер прислал usage);
- статус временного хранилища (session/files + writable) и `tmp` путь.

UX страницы держим максимально простым: только ключевые статусы без перегруженных технических деталей.

Минимальная ручная проверка:
```bash
docker compose up -d --build backend
curl http://localhost:${ASYA_PORT}/api/health
# открыть в браузере: http://localhost:${ASYA_PORT}/status
docker compose down
```

Прямые URL `/`, `/settings` и `/status` должны открывать соответствующие вкладки frontend через backend SPA fallback.

## Ручной smoke для chat/files
```bash
docker compose up -d backend
curl http://localhost:${ASYA_PORT}/api/health
```

Далее в UI проверить три сценария:
- сообщение без файла;
- сообщение с документом (PDF/DOCX/XLSX);
- сообщение с изображением (и понятная ошибка, если модель без vision).

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
