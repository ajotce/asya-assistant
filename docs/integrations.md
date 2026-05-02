# Integrations (Asya v0.4)

## Что сделано в foundation шаге

- Реализован общий OAuth 2.0 + PKCE слой для `linear`, `google_calendar`, `todoist`.
- Реализовано хранение OAuth state в БД (`oauth_states`), а не в памяти.
- Реализованы one-time use, TTL и строгая привязка state к `user_id` + `provider`.
- Реализован единый базовый интерфейс `OAuthIntegration`:
  - `authorization_url(user_id, redirect_uri, scopes)`
  - `exchange_code(code, state)`
  - `refresh_access_token(refresh_token)`
  - `revoke(token)`
  - `get_authenticated_client(user_id)`
- Реальные API провайдеров на этом шаге не подключаются (кроме OAuth endpoints для token/revoke flow в абстракции).

## Модель OAuth state

Таблица `oauth_states`:
- `user_id`
- `provider`
- `state_token` (unique)
- `code_verifier`
- `redirect_uri`
- `scopes`
- `expires_at`
- `used_at`
- `safe_error_metadata`

## Безопасность

- Access/refresh tokens не хранятся в `oauth_states` и не хранятся в `integration_connections`.
- Секреты токенов хранятся только в `encrypted_secrets` через `EncryptedSecretService`.
- В API и логах запрещён вывод raw tokens.
- Ошибки провайдера отражаются только безопасной metadata.

## Тестовый режим

- Добавлен `MockOAuthIntegration` для unit/integration тестов OAuth flow.
- Проверяется полный цикл: URL авторизации -> callback state consume -> code exchange -> encrypted token storage.
- Проверяются ошибки: invalid state, expired state, reused state, ownership mismatch.
