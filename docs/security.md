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

## Удаление учётки и выгрузка данных (K8)

- Удаление учётки реализовано как двухшаговый процесс: пароль (`DELETE /api/me`) + confirmation token (`DELETE /api/me/confirm`).
- Confirmation token имеет TTL 5 минут.
- Перед фактическим удалением запускается export пользовательских данных.
- Ссылка на скачивание архива одноразовая и ограничена TTL 24 часа.
- Архив принципиально не содержит интеграционные токены и данные из `encrypted_secrets`.
- После удаления сохраняется только минимальный audit-след в `deleted_user_audits`:
  - `user_id` (без FK),
  - `email`,
  - `deleted_at`,
  - `had_export`.

## Safe error metadata

- Для ошибок интеграций используется только `safe_error_metadata`.
- Запрещено сохранять в metadata токены, email-body, auth headers, API keys и любой plaintext секретов.

## PKCE требования (foundation)

- Используется `code_challenge_method=S256`.
- `code_verifier` генерируется случайно и валидной длины.
- `state_token` генерируется криптостойко и используется один раз.
- Просроченный или повторно использованный state отклоняется.
