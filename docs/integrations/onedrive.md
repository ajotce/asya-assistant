# OneDrive integration (v0.5)

Статус: implemented (mocked integration tests).

## Scope

- list files
- get metadata
- download
- upload (small files via Graph `/content`)
- create folder
- delete (только с явным `confirmed=true` через action policy)

## API base

- `https://graph.microsoft.com/v1.0`
- OAuth access token в заголовке `Authorization: Bearer <token>`

## Security

- access token хранится в `encrypted_secrets` с именем `integration:onedrive:access_token`
- содержимое файлов не пишется в логи
- удаление без подтверждения блокируется

## Supported operations mapping

- list: `GET /me/drive/root/children` или `GET /me/drive/root:/{path}:/children`
- metadata: `GET /me/drive/root:/{path}`
- download: `GET /me/drive/root:/{path}:/content`
- upload: `PUT /me/drive/root:/{path}:/content`
- create folder: `POST /me/drive/root:/{parent}:/children`
- delete: `DELETE /me/drive/root:/{path}`
