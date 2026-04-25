# Architecture (MVP)

Документ описывает фактическую архитектуру текущего кода MVP Asya.

## Состав системы
- Frontend: `React + Vite + TypeScript` (`frontend/`)
- Backend: `FastAPI` (`backend/`)
- Интеграция моделей/embeddings: VseLLM OpenAI-compatible API
- Локальный запуск: Docker Compose

## Backend слои

### API routes (`backend/app/api`)
- `routes_health.py` -> `/api/health`
- `routes_models.py` -> `/api/models`
- `routes_settings.py` -> `/api/settings`
- `routes_chat.py` -> `/api/chat/stream`
- `routes_session.py` -> `/api/session*`, `/api/session/{session_id}/files`
- `routes_usage.py` -> `/api/usage*`

### Services (`backend/app/services`)
- `settings_service.py` -> чтение/обновление настроек
- `vsellm_client.py` -> вызовы `/models` и `/embeddings`, нормализация model metadata (`supports_chat`, `supports_stream`, `supports_vision`)
- `chat_service.py` -> сбор контекста, SSE-стриминг, диагностика совместимости модели, vision/retrieval логика, fallback на non-stream при явной ошибке streaming
- `file_service.py` -> валидация/сохранение файлов, извлечение текста, chunking, embeddings

### Storage (`backend/app/storage`)
- `session_store.py` -> in-memory сессии и сообщения
- `file_store.py` -> in-memory метаданные файлов + пути к временным файлам
- `vector_store.py` -> in-memory векторный индекс по сессии
- `usage_store.py` -> in-memory usage (chat/embeddings)
- `sqlite.py` -> SQLite для persisted settings

## Данные и жизненный цикл

### Настройки
- Хранятся в SQLite (`assistant_name`, `system_prompt`, `selected_model`)
- Загружаются/обновляются через `/api/settings`
- `VSELLM_API_KEY` хранится только в `.env` backend

### Сессии
- Создаются через `POST /api/session`
- Сообщения живут только в runtime (`SessionStore`)
- При `DELETE /api/session/{session_id}` удаляются:
  - сообщения сессии
  - file bindings
  - временные файлы
  - векторные чанки
  - usage сессии

### Файлы и retrieval
`POST /api/session/{session_id}/files`:
- валидирует лимиты и формат
- сохраняет файл во временный каталог `TMP_DIR`
- для PDF/DOCX/XLSX извлекает текст
- режет текст на чанки
- получает embeddings и сохраняет в `SessionVectorStore`

`POST /api/chat/stream`:
- берет историю только текущей сессии
- добавляет системный промт
- при наличии документных чанков делает retrieval и добавляет контекст
- для `file_ids` прикладывает только изображения (data URL)
- отдает SSE события `token`, `thinking` (опционально), `error`, `done`
- если провайдер присылает reasoning (`reasoning_content`/`reasoning`/`thinking` в delta или `message.*`), backend эмитит отдельный `event: thinking` перед/между `event: token`; reasoning не пишется в `SessionStore` и не передаётся провайдеру в следующих запросах
- при provider-ошибках `400/404/422` пытается извлечь точную причину из ответа провайдера и возвращает понятное сообщение с ID модели
- при явном указании провайдера на неподдерживаемый `stream=true` выполняет безопасный non-stream retry и маппит его в SSE

## Совместимость моделей
- `/api/models` не хардкодит whitelist моделей: используются provider metadata и эвристики по `capabilities`/`endpoints`.
- Явное `supports_chat=false` считается сильным сигналом: такая модель не должна использоваться как chat-модель.
- Если metadata неполная, модель не блокируется заранее; фактическая проверка происходит на chat-запросе.
- Явное `supports_vision=false` продолжает блокировать image input заранее.

## Vision-поведение
- Проверка идет по `/api/models` metadata
- Предзапрет только при явном `supports_vision=false`
- Если capability неизвестен, backend пробует запрос и возвращает ошибку провайдера, если он отклонит image input

## Usage в MVP
- `/api/usage` и `/api/usage/session/{session_id}`
- Chat usage собирается из stream-ответов, если провайдер присылает `usage`
- Embeddings usage собирается из upload/retrieval pipeline
- Стоимость не рассчитывается (`cost.status=unavailable`)

## Frontend и раздача
- Frontend собирается в `frontend/dist`
- В local-режиме backend может раздавать frontend из `FRONTEND_DIST_PATH`
- SPA fallback включен для не-API путей
- Вкладки `Чат`/`Настройки`/`Состояние` синхронизируются с URL (`/`, `/settings`, `/status`), но после первого открытия вкладка не размонтируется: компонент остаётся в runtime и скрывается через `hidden`. Это сохраняет состояние `ChatPage` до обновления страницы без `localStorage`/`IndexedDB`.

## Ограничения MVP (по текущей реализации)
- Один пользователь
- Нет долговременной памяти/истории чатов
- Нет авторизации
- Нет внешних интеграций (Todoist/Calendar/CRM)
- Нет web search
