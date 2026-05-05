# Integrations (Asya v0.5)

## Координаторская сводка (2026-05-05)

- Базовая ветка интеграции: `0.5-extended`.
- Сведены изменения `chat-actions-v05` и `observer-state-snapshots` (включая GitHub read-only API/tool routing).
- Ветка `0.5/file-storage-providers` отсутствует в репозитории (локально и на `origin`).
- Ветки `0.5/github-readonly`, `0.5/bitrix24-readonly`, `0.5/imap-mail`, `0.5/document-templates`,
  `0.5/briefings`, `0.5/memory-personality-evolution`, `0.5/action-rollback` не содержат уникальных
  коммитов относительно текущей `0.5-extended`.
- Для частичных сборок добавлены safe fallback-ы: если модуль провайдера не включён в текущий build,
  соответствующие endpoints возвращают `409` с явным сообщением.

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
