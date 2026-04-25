# API (MVP Draft)

Текущий статус: реализован backend skeleton этапа 1 с базовым health-check.

## Базовые принципы
- Все endpoint-ы используют префикс `/api`.
- API-ключи и секреты не возвращаются frontend.

## Реализованные endpoint-ы
- `GET /api/health`
- `GET /api/models`

Пример ответа:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "local",
  "vsellm": {
    "api_key_configured": false,
    "base_url": "https://api.vsellm.ru/v1"
  }
}
```

## OpenAPI / Swagger
- OpenAPI schema: `GET /openapi.json`
- Swagger UI: `GET /docs`

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

## Планируемые endpoint-ы MVP
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/session`
- `GET /api/session/{session_id}`
- `DELETE /api/session/{session_id}`
- `POST /api/chat/stream`
- `POST /api/files`
- `GET /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
- `GET /api/usage/session/{session_id}`
