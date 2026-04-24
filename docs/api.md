# API (MVP Draft)

Текущий статус: реализован только каркас backend без прикладных endpoint-ов (этап 0).

## Базовые принципы
- Все endpoint-ы используют префикс `/api`.
- API-ключи и секреты не возвращаются frontend.

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
