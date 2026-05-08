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

## ADR-014 (R1, этап 0): Голос real-time — список вариантов и критерии выбора

Решение (этап 0): финальный выбор не принят, зафиксирован shortlist провайдеров и критерии оценки. Окончательное решение принимает агент на этапе 5B.

Варианты для оценки:

- Picovoice Porcupine (wake-word engine)
- OpenWakeWord (open-source wake-word)
- Yandex SpeechKit (STT/TTS)
- GigaChat (speech/LLM ecosystem)

Критерии выбора:

- Точность wake-word на русском языке (false positive / false negative)
- Задержка (latency) в режиме активной вкладки
- Стабильность в браузерном окружении (PWA)
- Стоимость на пользователя и при росте нагрузки
- Доступность SDK/API и простота интеграции в текущую архитектуру
- Privacy и требования к передаче аудио-данных
- Операционные риски: vendor lock-in, лимиты, региональная доступность

## ADR-015 (R6, этап 0): БД и масштабирование — предварительная рекомендация

Решение (этап 0): рекомендован целевой переход на PostgreSQL + pgvector. Финальное решение по rollout фиксируется на этапе 3A.

Контекст:

- SQLite хорошо закрывает ранние фазы, но ограничивает масштабирование по concurrency, migration workflow и операционному сопровождению в облаке.
- Для семантического поиска в 1.0 нужен production-grade аналог `sqlite-vec` — `pgvector`.

Managed-варианты для оценки:

- Yandex Managed PostgreSQL
- AWS RDS PostgreSQL
- Neon

Предварительная рекомендация:

- Для основного сценария 1.0 выбрать managed PostgreSQL у основного cloud-провайдера проекта.
- Использовать `pgvector` как стандартный vector extension.
- Миграцию SQLite → PostgreSQL проводить через отдельный проверяемый migration-script на тестовой БД перед production rollout.

## ADR-016 (R6, 1.0.1 audit confirmation): PostgreSQL rollout target for cloud

Решение (подтверждение по итогам cloud-readiness audit 2026-05-08):
- Для фазы 1.0 production target — PostgreSQL (managed) + `pgvector`.
- Приоритетный вариант для текущего контура проекта: **Yandex Managed PostgreSQL** (минимум операционной нагрузки, встроенные backup/failover, проще пройти 1.0 SLA).
- Допустимые эквиваленты для того же архитектурного решения: AWS RDS PostgreSQL / Selectel Managed PostgreSQL.

Где допустим self-managed PostgreSQL:
- Только как исключение при жёстких ограничениях по бюджету/регуляторике/спецтопологии.
- В этом случае обязательны: managed-like backup policy, мониторинг, failover runbook, тест восстановления.

Почему:
- SQLite + локальный FS не выдерживают target-модель горизонтального масштабирования (`N > 1`) и cloud native deployment.
- `pgvector` покрывает потребность 1.0 в vector search без отдельного vector DB.
- Managed PG снижает операционные риски и объём инфраструктурных задач в релизном окне 1.0.

Последствия:
- В 1.0.2 убирается SQLite как production-default, вводится cloud-first DB config.
- В 1.0.3 выполняется миграция SQLite -> PostgreSQL с idempotent migration script и dry-run.
- Все новые DB-изменения в 1.0 ветке должны быть совместимы с PostgreSQL как primary target.

## ADR-017 (1.0.2): Scheduler и process-local runtime state в multi-instance

Решение:
- `pending actions` больше не process-local: хранятся в таблице `pending_actions` с TTL.
- `ReasoningProbeCache`, runtime `SessionFileStore`, runtime vector/usage cache в 1.0.2 остаются process-local и считаются **ephemeral**.
- `APScheduler` остаётся in-process только для local/dev. Для production multi-instance его нужно отключать (`SCHEDULER_ENABLED=false`) и выносить в отдельный single-instance worker/queue.

Почему:
- process-local state ломает консистентность при `N > 1` инстансах;
- полный переход на Redis/Celery выходит за рамки 1.0.2 и не должен блокировать текущий cloud-readiness этап.

Последствия:
- подтверждения `/confirm` устойчивы к роутингу между инстансами;
- для production rollout обязателен отдельный шаг по distributed scheduler (план 1.0.6/1.0.7+).
