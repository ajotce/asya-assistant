# API (Asya Local)

Документ описывает фактическое API после завершения v0.3 и foundation-слоя интеграций v0.4.

Базовый префикс: `/api`

## 1. Фактические API группы
- `/health`
- `/models`
- `/settings`
- `/chat`
- `/chats`
- `/session`
- `/usage`
- `/auth`
- `/access-requests`
- `/admin/access-requests`
- `/integrations`
- `/integrations/telegram`
- `/storage`
- `/voice`

Все user-data endpoint-ы должны работать только в рамках `current user`.

## 2. Контракт безопасности (обязательно для 0.2/0.3)
- `401` без валидной сессии там, где требуется auth.
- `403` для admin-only операций без роли admin.
- `404` вместо утечки факта существования чужих user-scoped сущностей.
- Никогда не возвращать секреты, токены, ключи, plaintext защищённых данных.

## 3. Integrations API (v0.4 foundation)

- `GET /api/integrations` — список статусов подключений по поддерживаемым provider.
- `GET /api/integrations/{provider}` — состояние конкретного provider.
- `DELETE /api/integrations/{provider}` — безопасное отключение интеграции текущего пользователя.

Поддерживаемые provider:
- `linear`
- `google_calendar`
- `todoist`
- `gmail`
- `google_drive`
- `yandex_disk`
- `onedrive`
- `icloud_drive`
- `telegram`

Статусы:
- `not_connected`
- `connected`
- `expired`
- `revoked`
- `error`

Ограничения:
- endpoint-ы user-scoped;
- токены/refresh-токены никогда не возвращаются в API;
- metadata ошибок хранится и возвращается только в safe-виде (`safe_error_metadata`).

## 4. OAuth/PKCE foundation (service layer)

Реализован backend service-слой для OAuth-подключений (без публичных callback endpoint-ов в этом шаге):
- базовые сущности:
  - `OAuthProviderConfig`
  - `OAuthTokens`
  - `OAuthState`
  - `OAuthIntegration`
- методы:
  - `authorization_url(user_id, redirect_uri, scopes)`
  - `exchange_code(code, state)`
  - `refresh_access_token(refresh_token)`
  - `revoke(token)`
  - `get_authenticated_client(user_id)`

PKCE и state:
- `code_challenge_method=S256`
- state хранится в БД (`oauth_states`)
- state одноразовый
- state имеет TTL
- state привязан к `user_id` и `provider`

## 5. Целевые API группы Asya 0.3 (план)

### 3.1 Spaces
- `GET /api/spaces`
- `POST /api/spaces`
- `PATCH /api/spaces/{space_id}`
- `POST /api/spaces/{space_id}/archive`
- `GET /api/spaces/{space_id}/settings`
- `PUT /api/spaces/{space_id}/settings`

Требования:
- user-scoped доступ;
- `Asya-dev` только для admin.

### 3.2 Memory
- `GET /api/memory/feed`
- `POST /api/memory/facts`
- `PATCH /api/memory/facts/{fact_id}`
- `POST /api/memory/facts/{fact_id}/confirm`
- `POST /api/memory/facts/{fact_id}/forbid`
- `POST /api/memory/episodes`
- `POST /api/memory/snapshots`
- `POST /api/memory/rollback`

Требования:
- статусная модель: `confirmed/inferred/needs_review/outdated/forbidden/deleted`;
- запрет использования `forbidden/deleted` в chat context.

### 3.3 Personality / Rules
- `GET /api/personality`
- `PUT /api/personality`
- `GET /api/behavior-rules`
- `POST /api/behavior-rules`
- `PATCH /api/behavior-rules/{rule_id}`

### 3.4 Activity Log
- `GET /api/activity-log`

Требования:
- события только текущего пользователя;
- без раскрытия секретов.

## 4. Совместимость с chat endpoint

`POST /api/chat/stream` в 0.3 остаётся основным endpoint генерации, но контекст может дополняться релевантной памятью, правилами и personality overlay текущего пространства.

Дополнение v0.4 finalization:
- `POST /api/auth/setup-password` — установка пароля по одноразовому signup token;
- `POST /api/admin/access-requests/{id}/approve` теперь возвращает `setup_link`;
- в `POST /api/chat/stream` добавлен command-routing для tools:
  - `/tool calendar list|create ...`
  - `/tool todoist list|create ...`
  - `/tool linear update ...`
  - `/tool gmail search|draft ...`
  - `/confirm <pending_action_id>` для исполнения pending action.

## 5. Статус реализации 0.3 (актуально)

Для `spaces/memory/personality/activity` реализованы рабочие backend endpoint-ы и user-scoped проверки доступа.

## 6. Реализованные Spaces API

Добавлены endpoint-ы:
- `GET /api/spaces` — список пространств текущего пользователя;
- `POST /api/spaces` — создать пространство;
- `PATCH /api/spaces/{space_id}` — переименовать пространство;
- `POST /api/spaces/{space_id}/archive` — архивировать пространство;
- `GET /api/spaces/{space_id}/settings` — получить memory settings пространства;
- `PUT /api/spaces/{space_id}/settings` — обновить memory settings пространства.

Также обновлён `POST /api/chats`: поддерживает optional `space_id`; если не передан, чат создаётся в дефолтном пространстве пользователя.

## 7. Реализованные Memory API

Добавлены endpoint-ы:
- `GET /api/memory/facts`
- `POST /api/memory/facts`
- `PATCH /api/memory/facts/{fact_id}`
- `POST /api/memory/facts/{fact_id}/status`
- `POST /api/memory/facts/{fact_id}/forbid`
- `GET /api/memory/rules`
- `POST /api/memory/rules`
- `PATCH /api/memory/rules/{rule_id}`
- `POST /api/memory/rules/{rule_id}/disable`
- `GET /api/memory/episodes`
- `GET /api/memory/changes`
- `GET /api/memory/snapshots`
- `POST /api/memory/snapshots`
- `GET /api/memory/snapshots/{snapshot_id}`
- `POST /api/memory/snapshots/{snapshot_id}/rollback`
- `GET /api/activity-log`
- `GET /api/personality`
- `PUT /api/personality`

Все endpoint-ы работают в рамках текущего пользователя.

## 8. Memory Extraction Runtime Behavior

Extraction не имеет отдельного публичного endpoint и выполняется внутри `POST /api/chat/stream` после успешного сохранения ответа ассистента.

Управление:
- `MEMORY_EXTRACTION_ENABLED=false` полностью отключает extraction pipeline.

Наблюдаемость:
- результат extraction отражается через уже реализованные endpoint-ы:
  - `GET /api/memory/facts`
  - `GET /api/memory/rules`
  - `GET /api/memory/episodes`
  - `GET /api/memory/changes`
  - `GET /api/activity-log`

Activity filters:
- `GET /api/activity-log` поддерживает query-параметры:
  - `limit`
  - `event_type`
  - `entity_type`
  - `space_id`
  - `date_from` (ISO datetime)
  - `date_to` (ISO datetime)

## 9. Memory-aware chat context (реализовано)

`POST /api/chat/stream` теперь добавляет compact memory context (отдельный system message) перед file retrieval context:
- факты пользователя;
- правила поведения;
- релевантные эпизоды;
- personality base и optional space overlay.

Ограничения и безопасность:
- только текущий `user_id`;
- фильтр по текущему `chat.space_id` + global (`space_id=null`) записи;
- исключаются `forbidden` и `deleted`;
- `outdated` не добавляется при конфликте с `confirmed` фактом по тому же ключу;
- при конфликте памяти с текущим сообщением приоритет у текущего явного запроса пользователя.

Space settings:
- `memory_read_enabled=false` отключает memory retrieval;
- `behavior_rules_enabled=false` отключает блок правил;
- `personality_overlay_enabled=false` отключает overlay личности.

Наблюдаемость:
- при использовании memory context в ответе пишется activity event `memory_used_in_response`;
- event содержит только безопасный `meta` (счётчики и flags), без полного prompt и без секретов.

Personality API:
- `GET /api/personality` — базовый personality profile пользователя;
- `PUT /api/personality` — обновление базового profile;
- `GET /api/personality/overlay/{space_id}` — чтение/создание overlay профиля пространства;
- `PUT /api/personality/overlay/{space_id}` — обновление overlay профиля пространства.

Параметры profile:
- `name`, `tone`, `style_notes`, `is_active`,
- `humor_level` (0..2),
- `initiative_level` (0..2),
- `can_gently_disagree` (bool),
- `address_user_by_name` (bool).

Spaces API во frontend (используется в `ChatPage`):
- `GET /api/spaces`
- `POST /api/spaces`
- `PATCH /api/spaces/{space_id}`
- `POST /api/spaces/{space_id}/archive`
- `GET /api/spaces/{space_id}/settings`
- `PUT /api/spaces/{space_id}/settings`

Чаты:
- `POST /api/chats` принимает optional `space_id` и создаёт чат в выбранном пространстве.

## 10. Voice API (v0.4)

- `GET  /api/voice/settings` — получить настройки голоса пользователя
- `PUT  /api/voice/settings` — обновить настройки голоса
- `POST /api/voice/stt` — распознавание речи (body: сырое аудио, Content-Type: audio/webm)
- `POST /api/voice/tts` — синтез речи (body: `{"text": "..."}`)

Лимиты: максимальный размер аудио для STT — 15 MB (`VOICE_MAX_AUDIO_BYTES`).

## 11. Telegram Integration API (v0.4)

## 12. Documents API (v0.5)

- `POST /api/documents/fill` (`multipart/form-data`)
  - fields:
    - `template`: DOCX-файл
    - `values_json`: JSON-объект значений для placeholder-токенов (`{{key}}`)
    - `output`: `docx` | `pdf` | `both`
    - `filename_base`: базовое имя выходных файлов
  - response: JSON с массивом файлов (`filename`, `content_type`, `content_base64`)
- `POST /api/documents/convert` (`multipart/form-data`)
  - fields:
    - `file`: DOCX-файл
    - `filename_base`: базовое имя PDF
  - response: JSON с одним PDF-файлом (`filename`, `content_type`, `content_base64`)

Ошибки:
- `400` — неверный формат входных данных;
- `502` — ошибка/недоступность DOCX→PDF конвертера;
- сообщения ошибок должны быть user-readable.

## 13. Document Templates API (v0.5, H1/H2)

- `GET /api/document-templates`
  - список шаблонов текущего пользователя.
- `POST /api/document-templates`
  - создание карточки шаблона (`name`, `description`, `provider`, `file_id`, `fields`, `output_settings`).
- `PATCH /api/document-templates/{template_id}`
  - обновление карточки шаблона.
- `DELETE /api/document-templates/{template_id}`
  - удаление карточки шаблона.
- `POST /api/document-templates/{template_id}/fill`
  - body: `{"values": {...}, "preview_only": true|false}`
  - `preview_only=true`: возвращает JSON:
    - `missing_fields: string[]`
    - `invalid_fields: Record<string,string>`
    - `ready: boolean`
  - `preview_only=false`: возвращает сгенерированный DOCX-файл (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`).

Валидация на fill:
- `required` поля обязательны;
- `vin`: 17 символов, только `[A-HJ-NPR-Z0-9]` (без `I`, `O`, `Q`);
- `email`, `phone`, `date`: базовая проверка формата.

User isolation:
- все endpoint-ы `document-templates` user-scoped;
- доступ к чужому `template_id` возвращает `404`.

- `GET  /api/integrations/telegram/status` — статус привязки аккаунта

## 12. IMAP Integration API (v0.5)

- `POST /api/integrations/imap/test` — проверка IMAP параметров подключения.
- `POST /api/integrations/imap/connect` — сохранить encrypted credentials и подключить IMAP.
- `GET  /api/integrations/imap/folders` — список доступных папок.
- `GET  /api/integrations/imap/messages?folder=INBOX&limit=30` — список писем.
- `GET  /api/integrations/imap/messages/{uid}?folder=INBOX` — чтение письма.
- `GET  /api/integrations/imap/search?q=...&folder=INBOX&limit=30` — поиск писем.
- `POST /api/integrations/imap/messages/{uid}/read?folder=INBOX` — пометить как прочитанное.
- `DELETE /api/integrations/imap` — отключить IMAP и удалить связанные секреты.

Ограничения безопасности:
- пароль/app password и другие credentials не возвращаются через API;
- все endpoint-ы user-scoped;
- в safe error metadata допускаются только безопасные сообщения без содержимого писем.
- `POST /api/integrations/telegram/link-token` — создать one-time токен для привязки
- `POST /api/integrations/telegram/unlink` — отвязать аккаунт
- `POST /api/integrations/telegram/notify-test` — отправить тестовое уведомление

Привязка: пользователь получает `one_time_token`, переходит по ссылке `https://t.me/<bot>?start=<token>` в Telegram — бот обрабатывает `/start <token>` и связывает аккаунты.
## 4.1 Storage API (v0.5 foundation)

- `GET /api/storage/providers` — список поддерживаемых file storage providers.
- `GET /api/storage/files` — list/search файлов в provider (`provider`, `path`, optional `search`).
- `POST /api/storage/files` — upload файла в provider (`provider`, `path`, multipart `file`).
- `GET /api/storage/files/{provider}/{item_id}` — metadata файла/папки.

Принципы:
- user-scoped доступ;
- default provider берётся из `user_settings.default_storage_provider`, если query `provider` не передан;
- содержимое файлов не логируется;
- секреты токенов в API не возвращаются.


## 12. Briefings API (v0.5)

- `GET /api/briefings/settings` — настройки morning/evening и каналов доставки.
- `PATCH /api/briefings/settings` — обновить настройки брифингов.
- `POST /api/briefings/generate` — ручная генерация (`kind`: `morning`/`evening`).
- `GET /api/briefings/archive?limit=20` — архив последних брифингов.
- `GET /api/briefings/{briefing_id}` — получить markdown/content выбранного брифинга.

Особенности:
- in-app уведомление пишется в Notification Center (`notification_sent` + `notification_center`).
- при включённом Telegram delivery отправляется текст брифинга + кнопка `Открыть в Asya`.
- если в настройках дневника `briefing_enabled=false`, раздел дневника не включается в содержимое брифинга.
