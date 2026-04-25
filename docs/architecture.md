# Architecture (MVP)

## Общее
Asya MVP состоит из:
- Frontend (PWA, React/Vite) — клиентский интерфейс.
- Backend (FastAPI) — API, интеграция с VseLLM, временные сессии.

## Backend API
Все endpoints используют префикс `/api`.
Текущие ключевые группы:
- health (`/api/health`)
- models (`/api/models`)
- session (`/api/session*`)
- chat streaming (`/api/chat/stream`)

## Временные backend-сессии
Сессии реализованы in-memory в `SessionStore`:
- при `POST /api/session` создается `session_id`;
- контекст сообщений хранится только внутри этой сессии;
- file bindings (`file_id`) хранятся только внутри этой сессии;
- `DELETE /api/session/{session_id}` удаляет контекст и file bindings.

Ограничения MVP:
- долговременная история чатов не создается;
- долговременная память пользователя не создается;
- при перезапуске backend in-memory сессии теряются (допустимо для MVP).

## Streaming chat
`POST /api/chat/stream`:
- принимает `session_id` и сообщение;
- добавляет системный промт;
- использует глобальную модель из backend-настроек;
- учитывает только сообщения текущей сессии;
- отдает SSE (`token`, `error`, `done`).

## Файлы
На текущем этапе реализована только привязка `file_id` к сессии через `/api/session/{session_id}/files`.
Полная загрузка/обработка файлов будет реализована отдельным этапом.

## Безопасность
- `VSELLM_API_KEY` хранится только на backend в `.env`.
- API-ключ не возвращается в API-ответах.
- API-ключ не логируется.
