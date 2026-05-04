# Agent C: file storage providers (v0.5)

Сделано:

- Добавлены провайдеры `yandex_disk`, `onedrive`, `icloud_drive` в `IntegrationProvider`.
- Реализован общий контракт `FileStorageProvider`.
- Реализованы `YandexDiskIntegration` и `OneDriveIntegration`:
  - list files
  - get metadata
  - download
  - upload
  - create folder
  - delete только при `confirmed=true`.
- Добавлены mocked backend tests для обоих провайдеров.
- Добавлены UI карточки статуса интеграций Yandex.Disk, OneDrive, iCloud Drive на Status page.
- Принято решение по iCloud Drive: deferred до 2.0+ (см. ADR-016).

Ограничения:

- Реализован только API-слой операций по токену, без отдельного публичного endpoint-а file actions в этом шаге.
- Для OneDrive upload поддержан путь small-file `/content`; chunked upload session не покрыт этим шагом.
