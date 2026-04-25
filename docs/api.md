# API

Текущий документ фиксирует минимальную API-базу для MVP и служит оглавлением до полной OpenAPI-документации.

## Базовые принципы
- Префикс backend endpoint-ов: `/api/*`.
- Секреты и API-ключи не возвращаются во frontend.
- Полная схема API доступна через OpenAPI/Swagger backend.

## Базовые группы endpoint-ов MVP
- `/health`
- `/models`
- `/settings`
- `/chat`
- `/files`
- `/session`
- `/usage`

## Документация backend
- OpenAPI schema: `GET /openapi.json`
- Swagger UI: `GET /docs`
