# Security (Asya)

## Обновление v0.5 (2026-05-05)

- GitHub интеграция работает в read-only режиме (репозитории/issues/pulls/commits/read file/search).
- Write-операции GitHub и Bitrix24 в API/action-router не включены в текущий scope.
- При отсутствии модуля интеграции backend возвращает контролируемый `409`, а не stack trace/500.
- По итогам финализации v0.5 убрано логирование raw email-body и setup-link/token из dev notifier/transport.

## Секреты интеграций (v0.4 foundation)

- Access token и refresh token интеграций не хранятся в `integration_connections`.
- Токены сохраняются только в `encrypted_secrets` через `EncryptedSecretService` + `SecretCryptoService`.
- Для шифрования используется `MASTER_ENCRYPTION_KEY` (Fernet).
- API `GET /api/integrations*` не возвращает токены и raw secrets.
- OAuth state (`state_token`, `code_verifier`) хранится в таблице `oauth_states` с TTL и one-time use.

## User isolation

- Все операции интеграций фильтруются по `user_id`.
- Пользователь видит только свои подключения и может отключить только свои токены.
- При `DELETE /api/integrations/{provider}` токены удаляются только для текущего пользователя.
- OAuth callback может завершить обмен кода только для state, который принадлежит текущему `user_id` и `provider`.

## K8: Export и удаление аккаунта (v1.0.8)

- User export выполняется как background job и доступен только владельцу аккаунта.
- Выгрузка отдается архивом ZIP по одноразовому URL с TTL 24 часа.
- После первого успешного скачивания `download_token` инвалидируется.
- В export никогда не включаются:
  - `encrypted_secrets`;
  - access/refresh tokens интеграций;
  - любые plaintext secrets.
- Delete account выполняется в 2 шага:
  - запрос `confirmation_token` (TTL 15 минут);
  - подтверждение паролем + токеном.
- Перед удалением всегда выполняется auto-export.
- После удаления:
  - пользовательские записи и secrets удаляются физически;
  - object storage файлы пользователя удаляются;
  - остаётся только запись в `DeletedUserAudit` (метаданные удаления без персональных данных).

## Safe error metadata

- Для ошибок интеграций используется только `safe_error_metadata`.
- Запрещено сохранять в metadata токены, email-body, auth headers, API keys и любой plaintext секретов.

## PKCE требования (foundation)

- Используется `code_challenge_method=S256`.
- `code_verifier` генерируется случайно и валидной длины.
- `state_token` генерируется криптостойко и используется один раз.
- Просроченный или повторно использованный state отклоняется.

## Object storage security (1.0.4)

- Для S3-compatible хранилищ используется private bucket policy (публичный доступ запрещён).
- Доступ к пользовательским файлам на скачивание выдаётся только через `presigned_url`.
- TTL для `presigned_url` на пользовательские файлы: 24 часа (86400 секунд).
- В инфраструктуре (Terraform этап 1.0.5) policy должна явно запрещать `public-read` ACL и анонимный `GetObject`.
- Включается server-side encryption at-rest на стороне storage-провайдера (SSE-S3/SSE-KMS по возможностям
  целевого провайдера: Yandex/AWS/Selectel).
