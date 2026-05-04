# v0.5 Interfaces Contract

Документ фиксирует контракты, которыми должны пользоваться v0.5 feature-ветки.

Важно: если существующий интерфейс v0.4 уже покрывает задачу, не переписываем его.

## 1. Integration provider

Статус: уже есть в v0.4, переиспользуем.

Базовый контракт:
- `backend/app/integrations/oauth_base.py`
- `class OAuthIntegration(ABC)`

Ключевые методы:
- `authorization_url(user_id, redirect_uri, scopes) -> str`
- `consume_state(user_id, state_token) -> OAuthState`
- `exchange_code(code, state) -> OAuthTokens`
- `refresh_access_token(refresh_token) -> OAuthTokens`
- `revoke(token) -> None`
- `get_authenticated_client(user_id) -> AuthenticatedOAuthClient`

Правило v0.5:
- новые OAuth-провайдеры подключаются через существующий `OAuthIntegration` и `build_oauth_integration(...)`.
- секреты access/refresh token хранятся только через `EncryptedSecretService`.

## 2. File storage provider

Статус: отдельного provider-контракта в явном виде нет, но есть storage-слой (`backend/app/storage/*`).

Контракт v0.5 (документный, для новых модулей):
- `put_file(user_id, path, content, mime_type) -> StoredFileRef`
- `get_file(user_id, file_id) -> bytes`
- `delete_file(user_id, file_id) -> bool`
- `list_files(user_id, prefix=None, limit=...) -> list[StoredFileRef]`

Требования:
- user-scoped изоляция;
- без логирования содержимого файлов;
- provider-agnostic идентификаторы файлов в API.

Примечание:
- пока не меняем существующий runtime storage v0.4; добавляем v0.5 providers поверх текущего слоя минимально.

## 3. Mail provider

Статус: общего mail provider интерфейса в коде v0.4 нет (есть command-routing и OAuth база).

Контракт v0.5 (документный):
- `list_threads(user_id, query, limit) -> list[MailThread]`
- `get_thread(user_id, thread_id) -> MailThreadDetail`
- `create_draft(user_id, draft_input) -> DraftResult`
- `send_message(user_id, message_id_or_payload) -> SendResult`
- `mark_read(user_id, message_id) -> bool` (опционально)

Требования:
- поддержка confirm-before-send через `ActionRouter`;
- safe metadata в activity log (без body/token/header);
- единый формат ошибок для UI/action layer.

## 4. Document template provider

Статус: готового общего интерфейса в v0.4 нет.

Контракт v0.5 (документный):
- `list_templates(user_id) -> list[TemplateMeta]`
- `get_template(user_id, template_id) -> TemplateMeta`
- `render_template(user_id, template_id, payload) -> RenderArtifact`
- `export_artifact(user_id, artifact_id, format) -> ExportedFileRef`

Требования:
- поддержка минимум `docx` и `pdf`;
- шаблоны и результат рендера user-scoped;
- ошибки рендера возвращаются безопасно, без утечек данных пользователя.

## 5. Rollback action

Статус: частично есть через activity log и отдельные rollback сценарии (memory snapshots).

Контракт v0.5 (документный):
- `preview_rollback(user_id, action_id) -> RollbackPreview`
- `execute_rollback(user_id, action_id) -> RollbackResult`
- `can_rollback(user_id, action_id) -> bool`

Требования:
- rollback только в рамках текущего `user_id`;
- идемпотентность повторного rollback-запроса;
- запись результата rollback в activity log.

## 6. Briefing data source

Статус: явного интерфейса нет, но данные есть в observer/diary/activity/memory/integrations.

Контракт v0.5 (документный):
- `source_name() -> str`
- `collect(user_id, date_from, date_to, limit) -> BriefingItems`
- `priority() -> int` (для порядка сборки)

Базовые источники:
- observer (`ObserverService`)
- diary (`DiaryService`)
- activity log (`ActivityLogRepository`)
- integrations summary (`IntegrationConnectionService`)

Требования:
- only user-scoped data;
- no raw secrets;
- ограничение объёма данных для стабильного prompt/runtime.

## 7. Минимальные изменения интерфейсов в коде

На текущем шаге изменения в коде не требуются.

Причина:
- `OAuthIntegration`, `EncryptedSecretService`, `ActionRouter`, `NotificationCenter` и voice provider контракты уже достаточно стабильны для параллельной v0.5 разработки.
- недостающие контракты (`mail/file/document/briefing/rollback`) можно сначала вести как согласованный doc-contract и внедрять в отдельных feature-ветках, не ломая v0.4 основу.
