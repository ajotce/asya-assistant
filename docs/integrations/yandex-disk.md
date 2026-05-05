# Yandex.Disk integration (v0.5)

Статус: implemented (mocked integration tests).

## Scope

- list files
- get metadata
- download
- upload
- create folder
- delete (только с явным `confirmed=true` через action policy)

## API base

- `https://cloud-api.yandex.net/v1/disk`
- OAuth access token в заголовке `Authorization: OAuth <token>`

## Security

- access token хранится в `encrypted_secrets` с именем `integration:yandex_disk:access_token`
- содержимое файлов не пишется в логи
- удаление без подтверждения блокируется

## Supported operations mapping

- list/metadata: `GET /resources`
- download: `GET /resources/download` + загрузка по `href`
- upload: `GET /resources/upload` + `PUT` по `href`
- create folder: `PUT /resources`
- delete: `DELETE /resources`
