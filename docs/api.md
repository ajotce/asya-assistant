# API (Asya Local)

Документ отражает фактические backend endpoint'ы текущей версии Asya Local.

Базовый префикс API: `/api`

## Группы endpoint'ов
- `/health`
- `/models`
- `/settings`
- `/chat`
- `/chats`
- `/session`
- `/files` (реализовано как `/session/{session_id}/files`)
- `/usage`
- `/auth`
- `/access-requests`
- `/admin/access-requests`

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

`ModelInfo` может включать (если провайдер отдает metadata):
- `id`
- `name`, `description`, `context_window`, `input_price`, `output_price`
- `supports_chat` (`true|false|null`)
- `supports_stream` (`true|false|null`)
- `supports_vision` (`true|false|null`)

Примечания по совместимости:
- если `supports_chat=false`, frontend помечает модель как неподходящую для chat/completions;
- если metadata неполная (`null`/отсутствует), модель не блокируется заранее.

Ошибки:
- `503` если API-ключ не настроен
- `502/504/429` при проблемах провайдера

### `POST /api/models/probe-reasoning`
Проверяет, какие модели реально присылают `reasoning_content` через provider streaming. Запускает короткие тестовые запросы (до 32 токенов) с `stream=true` и инспектирует delta.

Тело запроса (необязательное):
- `model_ids?: string[]` — явный список ID. Если опущен, backend берёт `/api/models` и фильтрует кандидатов эвристикой (`thinking`, `reasoning`, `-r1`, `o3`).
- `force?: boolean` — игнорировать кэш (24 часа) и переспросить провайдера.

Лимит: до 10 моделей за один вызов, чтобы не сжигать токены.

Успех `200`:
- `results[]`: `{ id, streams_reasoning, checked_at, error? }`.

### `GET /api/models/reasoning-cache`
Возвращает текущий кэш probe без обращения к провайдеру.

Успех `200`:
- `results[]`: то же, что у `/probe-reasoning`, но только записи моложе 24 часов.

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

## Auth (v1)

### `POST /api/auth/register`
Регистрирует пользователя при `AUTH_REGISTRATION_MODE=open`.

Тело:
- `email`
- `display_name`
- `password`

Поведение:
- при `open`: создаётся пользователь со статусом `active`, пароль хранится только как `pbkdf2_sha256` hash, автоматически создаётся `Base-chat`;
- при `closed`: создаётся `AccessRequest` со статусом `pending`, пользователь не создаётся.

Успех `200`:
- `status=registered` + `user`, или
- `status=request_saved` (если регистрация закрыта).

## Access Requests / Beta Flow (v1)

### `POST /api/access-requests`
Публичная подача заявки на beta-доступ.

Тело:
- `email`
- `display_name`

Поведение:
- создаёт заявку со статусом `pending`;
- если уже есть `pending` заявка на этот email, возвращает её же (предсказуемая idempotent-поведение).

Успех `200`:
- `status: "pending"`
- `request: { id, email, display_name, status, ... }`

### `GET /api/admin/access-requests`
Список заявок. Только для `role=admin`.

Ошибки:
- `401` без авторизации;
- `403` если пользователь не admin.

### `POST /api/admin/access-requests/{request_id}/approve`
Аппрув заявки. Только для `role=admin`.

Поведение:
- заявка должна быть `pending`;
- admin не может аппрувить заявку на свой собственный email;
- после approve создаётся новый пользователь (или активируется существующий);
- гарантируется `Base-chat` для пользователя.
- в текущем dev-режиме реальная отправка email/magic-link не выполняется в рамках этого endpoint.

### `POST /api/admin/access-requests/{request_id}/reject`
Отклонение заявки. Только для `role=admin`.

Поведение:
- заявка должна быть `pending`;
- admin не может отклонять заявку на свой собственный email.

### `POST /api/auth/login`
Логин по email+паролю.

Тело:
- `email`
- `password`

Успех `200`:
- возвращает профиль пользователя;
- в профиле возвращается `preferred_chat_id` (Base-chat или последний доступный чат пользователя);
- устанавливает `HttpOnly` cookie с opaque session token (имя из `AUTH_COOKIE_NAME`).

Ошибки:
- `401` при неверном пароле/email;
- `401` если пользователь не `active` (`pending`/`disabled`).

### `POST /api/auth/logout`
Инвалидирует текущую сессию:
- текущий session token помечается `revoked_at` в БД;
- cookie удаляется.

Успех: `200` (`{ "status": "ok" }`).

### `GET /api/auth/me`
Возвращает текущего пользователя по session cookie.

Успех `200`: профиль пользователя с `preferred_chat_id` (Base-chat или последний доступный чат).

Ошибки:
- `401` если cookie отсутствует/просрочена/отозвана или пользователь не `active`.

## Chat

### `POST /api/chat/stream`
Streaming chat через SSE (`text/event-stream`).

Тело запроса:
- `session_id: string`
- `message: string`
- `file_ids?: string[]` (только для изображений)

SSE события:
- `event: token` -> `{ "text": "..." }`
- `event: thinking` -> `{ "text": "..." }` (только если provider реально присылает reasoning)
- `event: error` -> `{ "message": "..." }`
- `event: done` -> `{ "usage": ... }`

Примечания:
- endpoint требует авторизацию (`current user`);
- backend использует только контекст текущей сессии;
- для документов retrieval идет через embeddings/векторный индекс сессии;
- запрос с изображениями блокируется заранее только если модель явно `supports_vision=false`;
- если модель по metadata явно не поддерживает chat/completions, backend возвращает понятную ошибку с ID модели;
- для ошибок провайдера `400/404/422` backend пытается извлечь точную причину из provider body и возвращает её пользователю без секретов;
- если провайдер явно сообщает, что модель не поддерживает `stream=true`, backend делает безопасный fallback на non-stream completion и отдает ответ в SSE `event: token` + `event: done`;
- `event: thinking` эмитится, если в delta провайдера есть `reasoning_content` / `reasoning` / `thinking` (для stream) или соответствующие поля в `message.*` (для non-stream fallback). Reasoning не дублируется в `event: token`, не сохраняется в истории сессии и не отправляется обратно провайдеру в последующих сообщениях;
- для reasoning-моделей, у которых текущий VseLLM upstream не пробрасывает reasoning через стрим (например, `deepseek-r1-*`, `openai/o1-*`, `openai/o3-*`), backend заранее переходит на non-stream запрос и эмитит `event: thinking` (chunked) до `event: token` — поведение SSE-контракта при этом не меняется.

## Chats

### `GET /api/chats`
Список чатов текущего пользователя (`Base-chat` + обычные не удалённые чаты).

### `POST /api/chats`
Создаёт обычный чат.

Тело:
- `title`

### `PATCH /api/chats/{chat_id}`
Переименовывает чат.

Тело:
- `title`

### `POST /api/chats/{chat_id}/archive`
Архивирует обычный чат.

Ошибки:
- `400` для `Base-chat`

### `DELETE /api/chats/{chat_id}`
Удаляет обычный чат по текущей backend-логике (soft-delete + cleanup runtime/file/usage артефактов).

Ошибки:
- `400` для `Base-chat`

### `GET /api/chats/{chat_id}/messages`
Возвращает историю сообщений чата из БД.

## Session

### `POST /api/session`
Создает сессию.

Примечание:
- в переходном слое Asya 0.2 `session_id` = `chat_id` из БД.

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

Примечание:
- доступ только к сессиям текущего пользователя.

### `DELETE /api/session/{session_id}`
Удаляет сессию и временные данные (сообщения, файлы, векторы, usage по сессии).

Успех: `204`

Ошибки:
- `404` с текстом `Сессия не найдена.`
- `400` для `Base-chat`.

## Files

### `POST /api/session/{session_id}/files`
Загрузка файлов в текущую сессию (`multipart/form-data`, поле `files`).

Ограничения:
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

Примечание по 0.2:
- metadata загруженных файлов теперь сохраняются в БД (`file_meta`) с привязкой к `user_id` и `chat_id`.

Типовые ошибки:
- `404` `Сессия не найдена.`
- `400` по лимитам/формату/повреждённым файлам
- `502/504/429` при ошибках embeddings API

## Usage

### `GET /api/usage`
Сводный usage runtime:
- `chat` (`status=available|unavailable`, токены)
- `embeddings` (`status=available|unavailable`, токены)
- `cost` (`status=unavailable`, без расчета стоимости)
- `runtime` (`active_sessions`, `selected_model`, `embedding_model`)

Примечание по 0.2:
- `chat`/`embeddings` usage агрегируются по `usage_records` текущего пользователя в БД.

### `GET /api/usage/session/{session_id}`
Usage по конкретной сессии:
- `chat`
- `embeddings`
- `cost`
- `runtime` (`session_id`, `created_at`, `message_count`, `user_messages`, `assistant_messages`, `file_count`, `chunks_indexed`)

Ошибки:
- `404` `Сессия не найдена.`

Примечание по 0.2:
- endpoint возвращает данные только по сессии, принадлежащей текущему пользователю.

## Локальная раздача frontend через backend
Когда `SERVE_FRONTEND=true` и `frontend/dist` собран:
- `GET /` -> `index.html`
- `GET /assets/*`, `GET /icons/*`, `GET /manifest.webmanifest` -> статика
- SPA-пути (`/chat`, `/settings`, `/status`) -> fallback на `index.html`

## OpenAPI
- `GET /openapi.json`
- `GET /docs`
