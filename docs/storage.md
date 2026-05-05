# Storage abstraction (v0.5)

Цель: единый слой работы с внешними файловыми хранилищами без превращения Asya в основное хранилище.

## Компоненты

- `FileStorageProvider` — контракт провайдера.
- `FileStorageFile` / `FileStorageFolder` — единые DTO.
- `FileStorageService` — фасад + registry провайдеров.

## Поддерживаемые провайдеры

- `google_drive`
- `yandex_disk`
- `onedrive`

## Базовые операции

- `list`
- `search`
- `read`
- `write`
- `delete` (только с подтверждением для destructive action)
- `move`
- `share`
- `get_link`

## User defaults

В `user_settings` добавлены:

- `default_storage_provider`
- `default_storage_folders` (map provider -> folder/path)

## Безопасность

- токены хранятся только в `encrypted_secrets`;
- содержимое файлов не логируется;
- операции удаления должны проходить через confirmation policy на вызывающем уровне.
