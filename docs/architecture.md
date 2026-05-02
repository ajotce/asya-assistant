# Architecture (Asya Local)

Документ фиксирует фактическую архитектуру после завершения v0.3 и foundation-слой v0.4 для интеграций.

## 1. Текущее состояние (факт: v0.3 + v0.4 foundation)

### Технологии
- Frontend: `React + Vite + TypeScript` (`frontend/`)
- Backend: `FastAPI` (`backend/`)
- DB: `SQLite + SQLAlchemy + Alembic`
- LLM/Embeddings: VseLLM OpenAI-compatible API
- Локальный запуск: `Docker Compose`

### Базовые домены
- `users`, `auth_sessions`
- `chats`, `messages` (`Base-chat` обязателен)
- `file_meta`, `usage_records`
- `access_requests`, `encrypted_secrets`, `user_settings`
- `signup_tokens` (one-time setup link для alpha/beta onboarding)
- `spaces`, `space_memory_settings`
- `user_profile_facts`, `memory_episodes`, `memory_chunks`
- `behavior_rules`, `assistant_personality_profiles`
- `memory_changes`, `memory_snapshots`, `activity_logs`
- `integration_connections` (v0.4 foundation, без вызовов внешних API)

### Важные свойства 0.2
- auth на `HttpOnly` cookie;
- user-scoped доступ к чатам/сообщениям/файлам/usage/settings;
- защита admin-only endpoint-ов;
- reasoning не сохраняется как обычное сообщение;
- retrieval chunks пока runtime-only (in-memory vector store).

## 2. Foundation интеграций v0.4

В v0.4 добавлен единый user-scoped слой подключения интеграций, чтобы не дублировать хранение токенов по провайдерам.

### IntegrationConnection
- Таблица: `integration_connections`.
- Ключ: уникальная пара `(user_id, provider)`.
- Поля состояния: `status`, `scopes`, `connected_at`, `last_refresh_at`, `last_sync_at`.
- Ошибки: только `safe_error_metadata` (без токенов и секретов).
- Access/refresh tokens хранятся только в `encrypted_secrets` через существующий crypto-слой.

### Принципы
- Все сущности памяти и активности всегда связаны с `user_id`.
- Space-related сущности всегда связаны с `space_id`.
- Memory retrieval в chat работает только в рамках текущего пользователя и, при необходимости, текущего пространства.
- Статусы `forbidden`/`deleted` исключаются из контекста генерации.

## 3. Границы v0.4 foundation шага

В этом шаге не входят:
- реализация внешних OAuth/API flows провайдеров;
- background sync jobs и observer runtime;
- Telegram bot runtime, voice runtime и уведомления.

## 4. Безопасность

- Никаких секретов в UI/логах/документации.
- `.env` и реальные ключи не коммитятся.
- Запрет cross-user data leakage обязателен для chat/memory/spaces/activity/integrations.
- `Asya-dev` — только admin-only пространство.
- Activity log хранит только safe metadata (без тел писем, аудио, содержимого файлов и секретов).

## 10. Action routing (v0.4 finalization)

Добавлен `ActionRouter`, встроенный в `ChatService`:
- распознаёт tool-команды;
- создаёт `pending action`;
- требует явное подтверждение `/confirm <id>`;
- после confirm логирует событие в `activity_logs`.

Поддерживаемые инструменты:
- `calendar list/create`
- `todoist list/create`
- `linear update`
- `gmail search/draft`

## 5. Совместимость

В 0.3 должны оставаться работоспособными (или иметь документированную миграцию):
- `/api/health`, `/api/models`, `/api/settings`
- `/api/auth*`, `/api/chat/stream`, `/api/chats*`, `/api/session*`, `/api/usage*`.

## 6. Реализованная DB-основа v0.3 (backend)

Добавлены таблицы уровня БД и связи:
- `spaces` (user-scoped пространства),
- `space_memory_settings` (per-space toggles памяти/правил/personality),
- `user_profile_facts` (факты профиля со статусом),
- `memory_episodes` (эпизоды с `user_id`, `chat_id`, optional `space_id`),
- `memory_chunks` (чанки для embedding-поиска),
- `behavior_rules` (scope/strictness/status/source),
- `assistant_personality_profiles` (base + space overlay),
- `memory_changes` (история изменений),
- `memory_snapshots` (снимки памяти),
- `activity_logs` (прозрачная лента действий).

Дополнительно `chats` расширен полем `space_id` (nullable) для безопасной привязки чатов к пространствам.

Во всех новых сущностях пользовательских данных присутствует `user_id`; индексы добавлены под user-scoped выборки.

## 7. Spaces backend слой (реализовано)

Реализован отдельный `SpaceService` + repository/API слой.

Ключевые инварианты:
- дефолтное пространство пользователя создаётся автоматически (`Default`);
- служебное `Asya-dev` создаётся только для admin;
- `Base-chat` сохраняется как обязательный базовый чат и создаётся в дефолтном пространстве;
- операции над пространствами и их настройками строго user-scoped.

Схема связей:
- `spaces.user_id -> users.id`
- `space_memory_settings.space_id -> spaces.id`
- `chats.space_id -> spaces.id` (nullable)

## 8. Extraction в chat flow (реализовано)

`ChatService.stream_chat` после сохранения assistant-message запускает best-effort `MemoryExtractionService`.

Свойства:
- synchronous post-processing внутри backend lifecycle без Celery/очередей;
- extraction вызывается после token generation/saving assistant message;
- исключения extraction глушатся локально и не прерывают SSE `done` event.

Это даёт управляемое накопление памяти без риска поломки основного потока ответа.

## 9. Retrieval памяти в chat flow (реализовано)

В `ChatService.build_messages_payload` контекст собирается слоями:
1. `system_prompt` из пользовательских настроек;
2. `memory context` (если разрешён для пространства);
3. file retrieval context (runtime vector store);
4. history + текущее user message.

Memory context собирается только из данных текущего пользователя и релевантного пространства:
- facts: `user_profile_facts` (`space_id = null|chat.space_id`);
- rules: `behavior_rules` (`active`, scope-aware);
- episodes: `memory_episodes` (`space_id = null|chat.space_id`);
- personality: base + optional space overlay (тон, юмор, инициативность, мягкое возражение, обращение по имени).

Space toggles (`space_memory_settings`) влияют прямо на assembly:
- `memory_read_enabled` — on/off всего memory retrieval;
- `behavior_rules_enabled` — включение/выключение блока правил;
- `personality_overlay_enabled` — включение/выключение overlay.

Защита:
- `forbidden`/`deleted` никогда не попадают в prompt;
- `outdated` отбрасывается при конфликте с `confirmed` фактом;
- записывается activity event `memory_used_in_response` без сохранения полного prompt/секретов;
- file retrieval и vision pipeline сохраняют прежнее поведение.
- personality constraints явно прокидываются в контекст: без имитации сознания, без роли терапевта, без морализаторства.
