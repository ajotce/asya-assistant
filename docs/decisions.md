# Decisions

Дата обновления: 2026-05-02

## ADR-001: Локальный режим остаётся базовым режимом разработки
Решение: backend запускается локально в Docker Compose, frontend работает same-origin через backend-раздачу.

## ADR-002: API-ключи и чувствительные секреты только на backend
Решение: `VSELLM_API_KEY` и `MASTER_ENCRYPTION_KEY` хранятся только в backend `.env`.

## ADR-003: Фундамент 0.2 сохраняется как основа для 0.3
Решение: auth, user isolation, chats/files/usage и Alembic/SQLAlchemy-контур из 0.2 не ломаются и расширяются поэтапно.

## ADR-004: Scope Asya 0.3 ограничен памятью, личностью, пространствами и прозрачностью
Решение: в 0.3 входят memory/personality/spaces/memory feed/activity log.

Не входят без отдельного запроса:
- внешние интеграции;
- голос;
- дневник;
- тихий наблюдатель;
- web search;
- биллинг.

## ADR-005: Управляемая память с явными статусами
Решение: вводится статусная модель памяти (`confirmed`, `inferred`, `needs_review`, `outdated`, `forbidden`, `deleted`) и запрет на использование `forbidden/deleted` в chat context.

## ADR-006: Личность 0.3 — базовая и управляемая
Решение: в 0.3 реализуется только базовая личность (base profile + space overlay) без сложной автономной эволюции.

## ADR-007: Пространства user-scoped + admin-only `Asya-dev`
Решение: пространства являются пользовательскими контекстами; `Asya-dev` доступно только администратору.

## ADR-008: Прозрачность изменений через memory feed и activity log
Решение: изменения памяти должны быть наблюдаемыми, подтверждаемыми, откатываемыми и журналируемыми без утечки секретов.

## ADR-009: Единый OAuth/PKCE слой для интеграций v0.4
Решение: для `linear`, `google_calendar`, `todoist` используется общий слой `OAuthIntegration` + `OAuthStateService`.

Ключевые принципы:
- PKCE (`S256`) обязателен;
- state хранится в БД (`oauth_states`) с TTL и one-time use;
- state привязан к `user_id` и `provider`;
- access/refresh token хранятся только в `encrypted_secrets`;
- provider-specific API логика не добавляется до отдельного шага после foundation.

## ADR-010: aiogram для Telegram-бота

Решение: для Telegram-бота выбран `aiogram` (вместо `python-telegram-bot`).

Контекст: оба фреймворка зрелые и активно поддерживаются. aiogram выбран потому что:

- Нативная асинхронность (asyncio-first дизайн);
- Более компактный DSL для фильтров (F.voice, Command, etc.);
- Широко используется в русскоязычном комьюнити;
- Проще интеграция в FastAPI lifespan (polling в фоновом asyncio task).

## ADR-011: Абстрактный голосовой слой (Voice providers)

Решение: вводится интерфейсный слой `SpeechToTextProvider` / `TextToSpeechProvider` с конкретными реализациями (mock, yandex_speechkit, gigachat).

Ключевые принципы:

- Единый `VoiceService` фасад с методами `transcribe` / `synthesize`;
- Провайдер выбирается per-user через `UserVoiceSettings`;
- Mock-провайдер — дефолтный, не требует API-ключей;
- Лимиты на размер аудио применяются до передачи внешнему провайдеру;
- Аудио и транскрипты не пишутся в логи.

## ADR-012: Notification Center как точка отправки уведомлений

Решение: вводится `NotificationCenter` с регистрируемыми `NotificationChannel`.

Ключевые принципы:

- Каналы: in-app (activity log), telegram (`TelegramNotificationChannel`);
- Все отправки логируются в activity log с пометкой `notification_sent`;
- Никаких реальных отправок во внешние API в тестах;
- При ошибке отправки — исключение глушится локально, не прерывая бизнес-логику.

## ADR-013: Alpha/Beta onboarding через one-time setup link (не passwordless)

Решение: доступ после approve выдаётся через одноразовую setup-ссылку для установки пароля (`/setup-password?token=...`).

Ключевые принципы:

- это не passwordless login: ссылка только для первичной установки пароля;
- после установки пароля пользователь входит обычным login+password flow;
- токен одноразовый и с TTL;
- raw-токен не хранится, хранится только hash;
- approve/reject уведомления отправляются через email transport abstraction (mock/smtp).
