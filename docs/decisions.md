# Decisions

Дата обновления: 2026-05-04

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

## ADR-014: Фаза v0.5 разрабатывается через feature-ветки от 0.5-extended

Решение: для v0.5 вводится обязательный workflow через feature-ветки с базой `0.5-extended`.

Ключевые принципы:

- `0.5-extended` — интеграционная ветка фазы;
- каждая задача делается в отдельной ветке `feature/0.5-...`;
- один агент работает в пределах своего feature-scope;
- merge в `main` выполняется только после интеграции и приёмки фазы;
- прямые функциональные коммиты в `main` в рамках v0.5 не допускаются.

## ADR-015: Централизация документации v0.5 через координатора

Решение: central docs обновляются координатором фазы, а агенты ведут feature-notes в своих ветках.

Ключевые принципы:

- central docs: `docs/roadmap.md`, `docs/decisions.md`, `docs/architecture.md`, `docs/api.md`, `docs/security.md`, `docs/integrations.md`;
- feature docs: рабочие заметки агентов в `docs/v0.5/agent-notes/`;
- при merge feature-ветки координатор сводит изменения в central docs и устраняет противоречия;
- если решение влияет на архитектуру или процесс, оно фиксируется отдельным ADR.

## ADR-016: iCloud Drive в web-Asya откладывается до нативного приложения

Решение: в v0.5 не реализуем iCloud Drive в web-Asya как рабочую интеграцию файлового провайдера.

Контекст:

- для web backend нам нужна стабильная модель `list/metadata/download/upload/delete` по пользовательскому диску;
- публичные web API Apple ориентированы на CloudKit контейнеры конкретного приложения, а не на произвольный доступ к пользовательскому iCloud Drive;
- workaround через неофициальные протоколы/автоматизацию браузера не проходит по требованиям надёжности и безопасности.

Ключевые принципы:

- iCloud Drive в v0.5 отображается как `not_connected`/`planned`;
- никаких неофициальных reverse-engineered API или headless workaround в прод-коде;
- возвращаемся к реализации в фазе 2.0+ в рамках нативного приложения и Apple-энтitlements.

## ADR-017: Конвертация DOCX → PDF через отдельный LibreOffice headless контейнер

Решение: конвертация DOCX в PDF выполняется не в основном backend image, а через отдельный сервис-контейнер с LibreOffice в headless-режиме.

Контекст:

- пользователю нужно получать `docx` и `pdf` одновременно;
- установка LibreOffice в backend image увеличивает размер образа, ухудшает local dev и смешивает зоны ответственности;
- для v0.5 приоритет — изолированная и предсказуемая конвертация с понятной обработкой ошибок.

Ключевые принципы:

- отдельный контейнер `document-converter` (LibreOffice headless) в Docker Compose;
- backend общается с конвертером по внутренней сети compose, без публичной экспозиции наружу;
- вход/выход конвертации обрабатываются во временной директории с обязательным cleanup;
- при ошибке конвертации API возвращает понятное пользовательское сообщение без технических секретов;
- при недоступности конвертера `docx` остаётся доступным, а ошибка `pdf` явно сигнализируется.
