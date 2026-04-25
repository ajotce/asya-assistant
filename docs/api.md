# API (MVP)

Документ отражает фактические backend endpoint'ы текущего MVP.

Базовый префикс API: `/api`

## Группы endpoint'ов MVP
- `/health`
- `/models`
- `/settings`
- `/chat`
- `/session`
- `/files` (в MVP реализовано как `/session/{session_id}/files`)
- `/usage`

## Health

### `GET /api/health`
Расширенный статус для страницы `Состояние Asya`.

Возвращает:
- `status`, `version`, `environment`, `last_error`
- `uptime_seconds`
- `vsellm` (`api_key_configured`, `base_url`, `reachable`)
- `model.selected`
- `files`
- `embeddings` (`enabled`, `model`, `status`, `last_error`)
- `storage` (`session_store`, `file_store`, `tmp_dir`, `writable`)
- `session` (`enabled`, `active_sessions`)

## Models

### `GET /api/models`
Список моделей из VseLLM OpenAI-compatible API.

Ошибки:
- `503` если API-ключ не настроен
- `502/504/429` при проблемах провайдера

## Settings

### `GET /api/settings`
Возвращает текущие настройки:
- `assistant_name`
- `system_prompt`
- `selected_model`
- `api_key_configured`

### `PUT /api/settings`
Обновляет настройки.

Тело запроса:
- `assistant_name`
- `system_prompt`
- `selected_model`

Ошибки:
- `400` при валидации

## Chat

### `POST /api/chat/stream`
Streaming chat через SSE (`text/event-stream`).

Тело запроса:
- `session_id: string`
- `message: string`
- `file_ids?: string[]` (только для изображений)

SSE события:
- `event: token` -> `{ "text": "..." }`
- `event: error` -> `{ "message": "..." }`
- `event: done` -> `{ "usage": ... }`

Примечания:
- backend использует только контекст текущей сессии;
- для документов retrieval идет через embeddings/векторный индекс сессии;
- запрос с изображениями блокируется заранее только если модель явно `supports_vision=false`.

## Session

### `POST /api/session`
Создает сессию.

Успех: `201`, тело:
- `session_id`
- `created_at`

### `GET /api/session/{session_id}`
Состояние сессии.

Успех: `200`, тело:
- `session_id`
- `created_at`
- `message_count`
- `file_ids`

Ошибки:
- `404` с текстом `Сессия не найдена.`

### `DELETE /api/session/{session_id}`
Удаляет сессию и временные данные (сообщения, файлы, векторы, usage по сессии).

Успех: `204`

Ошибки:
- `404` с текстом `Сессия не найдена.`

## Files

### `POST /api/session/{session_id}/files`
Загрузка файлов в текущую сессию (`multipart/form-data`, поле `files`).

Ограничения MVP:
- до 10 файлов за запрос
- до 256 МБ на файл
- типы: PDF, DOCX, XLSX, изображения

Для документов backend:
- извлекает текст
- режет на чанки
- строит embeddings
- кладет в временный векторный индекс сессии

Для изображений backend:
- валидирует payload через Pillow
- сохраняет файл в временное хранилище сессии

Успех: `201`, тело:
- `session_id`
- `files[]` (`file_id`, `filename`, `content_type`, `size_bytes`)
- `file_ids[]`

Типовые ошибки:
- `404` `Сессия не найдена.`
- `400` по лимитам/формату/повреждённым файлам
- `502/504/429` при ошибках embeddings API

## Usage

### `GET /api/usage`
Сводный usage runtime:
- `chat` (`status=available|unavailable`, токены)
- `embeddings` (`status=available|unavailable`, токены)
- `cost` (`status=unavailable` в MVP, без расчета стоимости)
- `runtime` (`active_sessions`, `selected_model`, `embedding_model`)

### `GET /api/usage/session/{session_id}`
Usage по конкретной сессии:
- `chat`
- `embeddings`
- `cost`
- `runtime` (`session_id`, `created_at`, `message_count`, `user_messages`, `assistant_messages`, `file_count`, `chunks_indexed`)

Ошибки:
- `404` `Сессия не найдена.`

## Локальная раздача frontend через backend
Когда `SERVE_FRONTEND=true` и `frontend/dist` собран:
- `GET /` -> `index.html`
- `GET /assets/*`, `GET /icons/*`, `GET /manifest.webmanifest` -> статика
- SPA-пути (`/chat`, `/settings`, `/status`) -> fallback на `index.html`

## OpenAPI
- `GET /openapi.json`
- `GET /docs`
