# Security (Asya)

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

## Safe error metadata

- Для ошибок интеграций используется только `safe_error_metadata`.
- Запрещено сохранять в metadata токены, email-body, auth headers, API keys и любой plaintext секретов.

## PKCE требования (foundation)

- Используется `code_challenge_method=S256`.
- `code_verifier` генерируется случайно и валидной длины.
- `state_token` генерируется криптостойко и используется один раз.
- Просроченный или повторно использованный state отклоняется.
