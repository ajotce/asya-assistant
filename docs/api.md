# API (MVP Draft)

Текущий статус: реализованы базовые endpoints health/models/chat stream/session.

## Базовые принципы
- Все endpoint-ы используют префикс `/api`.
- API-ключи и секреты не возвращаются frontend.

## Реализованные endpoint-ы
- `GET /api/health`
- `GET /api/models`
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/session`
- `GET /api/session/{session_id}`
- `DELETE /api/session/{session_id}`
- `POST /api/session/{session_id}/files`
- `POST /api/chat/stream`

Пример ответа:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "local",
  "vsellm": {
    "api_key_configured": false,
    "base_url": "https://api.vsellm.ru/v1",
    "reachable": null
  },
  "model": {
    "selected": "openai/gpt-5-mini"
  },
  "files": {
    "enabled": true,
    "status": "готов"
  },
  "session": {
    "enabled": true,
    "active_sessions": 0
  },
  "last_error": null
}
```

## OpenAPI / Swagger
- OpenAPI schema: `GET /openapi.json`
- Swagger UI: `GET /docs`

`GET /api/health` дополнительно возвращает:
- `vsellm.reachable` — доступность VseLLM API (если проверка выполнена);
- `model.selected` — текущая глобальная модель из backend settings;
- `files` — статус файлового модуля;
- `session.active_sessions` — количество активных временных сессий;
- `last_error` — безопасное текстовое описание последней ошибки проверки (если есть).

## `GET /api/models`
Возвращает список моделей из VseLLM через backend.

Примеры ответов:

Если API VseLLM вернул только ID:
```json
[
  { "id": "openai/gpt-5" }
]
```

Если API VseLLM вернул расширенные поля:
```json
[
  {
    "id": "openai/gpt-5",
    "description": "Demo model",
    "supports_vision": true
  }
]
```

Важно:
- Backend не выдумывает цены, описания и другие поля.
- API-ключ никогда не возвращается во frontend.

Ошибки (пример):
```json
{
  "detail": "Ошибка авторизации VseLLM. Проверьте API-ключ на backend."
}
```

## Settings endpoints

### `GET /api/settings`
Возвращает настройки MVP:
- `assistant_name`
- `system_prompt`
- `selected_model`
- `api_key_configured` (только статус, без ключа)

Пример:
```json
{
  "assistant_name": "Asya",
  "system_prompt": "Ты — Asya...",
  "selected_model": "openai/gpt-5",
  "api_key_configured": false
}
```

### `PUT /api/settings`
Обновляет настройки MVP.

Request:
```json
{
  "assistant_name": "Ася",
  "system_prompt": "Работай кратко и по делу.",
  "selected_model": "openai/gpt-5"
}
```

Валидация:
- пустые значения недопустимы;
- лишние поля отклоняются (`422`);
- API-ключ через этот endpoint не принимается и не возвращается.

## `POST /api/chat/stream`
Потоковый endpoint чата (SSE).

Request body:
```json
{
  "session_id": "session-123",
  "message": "Привет, Ася"
}
```

Принципы работы:
- использует глобальную модель из `DEFAULT_CHAT_MODEL`;
- добавляет системный промт из `DEFAULT_SYSTEM_PROMPT`;
- использует только временный контекст текущей backend-сессии (in-memory);
- не хранит долгосрочную историю чатов.

Формат SSE-событий:
```text
event: token
data: {"text":"Привет"}

event: error
data: {"message":"Понятное сообщение об ошибке"}

event: done
data: {"usage":null}
```

Типовые ошибки:
- отсутствует `VSELLM_API_KEY` -> `event:error` с сообщением;
- отсутствует или удалена `session_id` -> `event:error` с сообщением;
- ошибка авторизации/лимитов/доступности модели -> `event:error` с понятным текстом;
- сетевой timeout -> `event:error` и завершение потока.

## Session endpoints

### `POST /api/session`
Создаёт новую временную backend-сессию.

Response:
```json
{
  "session_id": "uuid",
  "created_at": "2026-04-25T09:00:00.000000+00:00"
}
```

### `GET /api/session/{session_id}`
Возвращает текущее состояние временной сессии.

Response:
```json
{
  "session_id": "uuid",
  "created_at": "2026-04-25T09:00:00.000000+00:00",
  "message_count": 2,
  "file_ids": ["file-123"]
}
```

### `DELETE /api/session/{session_id}`
Очищает и удаляет временную сессию (контекст сообщений и file bindings).

### `POST /api/session/{session_id}/files`
Привязывает `file_id` к текущей сессии.

Request:
```json
{
  "file_id": "file-123"
}
```

## Планируемые endpoint-ы MVP
- `POST /api/files`
- `GET /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
- `GET /api/usage/session/{session_id}`
