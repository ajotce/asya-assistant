# API (MVP Draft)

Текущий статус: реализован backend skeleton этапа 1 с базовым health-check.

## Базовые принципы
- Все endpoint-ы используют префикс `/api`.
- API-ключи и секреты не возвращаются frontend.

## Реализованные endpoint-ы
- `GET /api/health`

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

## Планируемые endpoint-ы MVP
- `GET /api/models`
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
