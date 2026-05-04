# File storage abstraction: notes for coordinator

Что свести в central docs:

1. `docs/api.md`
- добавить раздел Storage API:
  - `GET /api/storage/providers`
  - `GET /api/storage/files`
  - `POST /api/storage/files`
  - `GET /api/storage/files/{provider}/{item_id}`

2. `docs/architecture.md`
- зафиксировать новый сервисный слой:
  - `FileStorageProvider`
  - `FileStorageService`
  - provider registry (`google_drive`, `yandex_disk`, `onedrive`)

3. `docs/decisions.md`
- при необходимости вынести отдельный ADR по принципу "Asya не является primary storage".

4. Compatibility note
- default provider теперь хранится в `user_settings`.
