# Architecture (Asya Local)

Документ разделяет:
- фактическую архитектуру текущего кода (Asya 0.2 foundation);
- целевое расширение Asya 0.3 (memory/personality/spaces/activity) без изменения базовых принципов безопасности.

## 1. Текущее состояние (факт: 0.2)

### Технологии
- Frontend: `React + Vite + TypeScript` (`frontend/`)
- Backend: `FastAPI` (`backend/`)
- DB: `SQLite + SQLAlchemy + Alembic`
- LLM/Embeddings: VseLLM OpenAI-compatible API
- Локальный запуск: `Docker Compose`

### Базовые домены 0.2
- `users`, `auth_sessions`
- `chats`, `messages` (`Base-chat` обязателен)
- `file_meta`, `usage_records`
- `access_requests`, `encrypted_secrets`, `user_settings`

### Важные свойства 0.2
- auth на `HttpOnly` cookie;
- user-scoped доступ к чатам/сообщениям/файлам/usage/settings;
- защита admin-only endpoint-ов;
- reasoning не сохраняется как обычное сообщение;
- retrieval chunks пока runtime-only (in-memory vector store).

## 2. Целевая архитектура 0.3

Asya 0.3 добавляет новый слой поверх 0.2 без отказа от текущей архитектурной базы.

### Новые домены
- Memory:
  - `user_profile_facts`
  - `memory_episodes`
  - `memory_chunks`
  - `behavior_rules`
  - `assistant_personality_profiles`
  - `memory_changes`, `memory_versions`, `memory_snapshots`
- Spaces:
  - `spaces`
  - `space_memory_settings`
- Activity:
  - `activity_logs`

### Принципы
- Все сущности памяти и активности всегда связаны с `user_id`.
- Space-related сущности всегда связаны с `space_id`.
- Memory retrieval в chat работает только в рамках текущего пользователя и, при необходимости, текущего пространства.
- Статусы `forbidden`/`deleted` исключаются из контекста генерации.

## 3. Границы v0.3

В 0.3 не входят:
- внешние интеграции;
- голос, STT/TTS, wake word;
- дневник и тихий наблюдатель;
- web search;
- биллинг;
- сложная автономная эволюция личности.

## 4. Безопасность

- Никаких секретов в UI/логах/документации.
- `.env` и реальные ключи не коммитятся.
- Запрет cross-user data leakage обязателен для chat/memory/spaces/activity.
- `Asya-dev` — только admin-only пространство.

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
