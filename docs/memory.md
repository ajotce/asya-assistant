# Memory (Asya 0.3)

Документ фиксирует целевой и реалистичный scope памяти для Asya 0.3.

## Цель
Сделать память управляемой, прозрачной и безопасной в multi-user контуре.

## Доменная модель (v0.3)
- `UserProfileFact`: структурированный факт о пользователе.
- `MemoryEpisode`: значимый эпизод из диалога.
- `MemoryChunk`: embedding-чанк для поиска по памяти.
- `BehaviorRule`: правило/предпочтение поведения.
- `MemoryChange`: запись изменения памяти.
- `MemoryVersion`: версия набора памяти.
- `MemorySnapshot`: снимок состояния памяти.

## Статусы памяти
- `confirmed`
- `inferred`
- `needs_review`
- `outdated`
- `forbidden`
- `deleted`

## Правила записи
- Явное «запомни» -> допустим `confirmed`.
- Автоизвлечение из диалога -> `inferred` или `needs_review`.
- Явное «забудь» -> `forbidden` или `deleted`.

## Правила использования
- В chat context можно использовать только память текущего пользователя.
- При наличии пространств — фильтр по текущему `space_id`.
- `forbidden` и `deleted` никогда не участвуют в генерации.
- `outdated` не используется, если по тому же ключу есть `confirmed` факт.
- Чувствительные данные (пароли, токены, ключи, платёжные данные) не должны записываться автоматически.
- Если память противоречит текущему явному сообщению пользователя, приоритет всегда у текущего сообщения.

## Memory Feed
Лента памяти должна позволять:
- просмотр источника и статуса записи;
- подтверждение/понижение доверия;
- редактирование;
- запрет использования;
- откат по версии/изменению.

## Snapshots и Rollback (реализовано)

Реализованы операции:
- `POST /api/memory/snapshots` — ручное создание snapshot;
- `GET /api/memory/snapshots` — список snapshot текущего пользователя;
- `GET /api/memory/snapshots/{snapshot_id}` — summary snapshot;
- `POST /api/memory/snapshots/{snapshot_id}/rollback` — откат состояния памяти к snapshot.

Что входит в snapshot:
- факты профиля пользователя (включая статусы и source);
- правила поведения;
- personality profile (base + space overlays);
- per-space memory settings;
- метаданные memory episodes (summary/status/source/chat_id/space_id).

Поведение rollback:
- user-scoped (чужой snapshot недоступен);
- состояние восстанавливается по данным snapshot;
- данные, отсутствующие в snapshot, физически не удаляются, а логически архивируются/скрываются (`deleted`/`archived` где применимо);
- создаются `memory_changes` (kind=`rollback`) и `activity_logs` (event=`memory_rollback`).

## Автоматические snapshots (lazy стратегия)

Без фоновых scheduler/очередей:
- weekly lazy snapshot: создаётся автоматически при первом memory-изменении новой ISO-недели;
- anomaly snapshot: создаётся автоматически при аномально большом числе memory changes после последнего snapshot (порог в коде).

TODO (если понадобится позже):
- настраиваемые пороги auto-snapshot на пользователя/пространство;
- отдельная админ-видимость auto/manual snapshot типа в UI.

## Границы v0.3
Не входит:
- автономная самоэволюция памяти без контроля пользователя;
- внешние интеграции источников памяти;
- скрытые фоновые автоматизации без явной трассировки в activity log.

## Текущая реализация (DB foundation)

Реализованы таблицы:
- `user_profile_facts` (`status` из `confirmed|inferred|needs_review|outdated|forbidden|deleted`),
- `memory_episodes` (`user_id`, `chat_id`, optional `space_id`),
- `memory_chunks` (embedding payload для retrieval),
- `memory_changes` (журнал изменений),
- `memory_snapshots` (снимки состояния).

Все memory-сущности user-scoped на уровне схемы и индексов.

## Backend Memory Service (реализовано)

Добавлен `MemoryService` и repository-слой для:
- `user_profile_facts`
- `memory_episodes` (list)
- `behavior_rules`
- `assistant_personality_profiles` (base profile)
- `memory_changes` (versioning)
- `activity_logs`

Реализованные статусы памяти:
- `confirmed`
- `inferred`
- `needs_review`
- `outdated`
- `forbidden`
- `deleted`

Правило active-list:
- `forbidden` и `deleted` исключаются из активного списка фактов (`GET /api/memory/facts` по умолчанию).

Версионирование:
- каждое изменение факта/правила/личности создаёт запись в `memory_changes` с `old_value/new_value`.

## Memory Extraction Pipeline (Asya 0.3)

Добавлен безопасный post-processing pipeline извлечения памяти из диалога:
- запускается после завершения user-request и сохранения assistant response;
- не влияет на SSE-поток ответа пользователю;
- ошибки extraction изолируются и не ломают chat response.

Источник и правила:
- извлекаются только кандидаты: факты о пользователе, стиль ответа, правила поведения, важные эпизоды/решения;
- явное `запомни` -> `confirmed`;
- автоматическое извлечение -> `needs_review` (или `inferred` для эпизодов);
- `забудь` -> релевантные факты помечаются `forbidden`.

Безопасность extraction:
- не сохраняются пароли, токены, API-ключи, платёжные данные и очевидные секреты;
- reasoning/thinking не извлекается как память.

Флаг:
- `MEMORY_EXTRACTION_ENABLED=true|false` (по умолчанию `true`).

## Memory Retrieval в chat context (реализовано)

`ChatService.build_messages_payload` добавляет отдельный compact system-блок `Контекст долговременной памяти`, если память разрешена в пространстве и есть релевантные данные.

Источники:
- `UserProfileFact` (ограничение `user_id` + текущий `space_id|global`),
- `BehaviorRule` (`active`, с учётом scope `global/user/space`),
- `MemoryEpisode` (user+space scoped, top релевантных к текущему сообщению),
- `AssistantPersonalityProfile` (base + optional space overlay).

Space toggles:
- `memory_read_enabled=false` полностью отключает memory retrieval для чата пространства;
- `behavior_rules_enabled=false` отключает добавление правил в prompt;
- `personality_overlay_enabled=false` отключает space overlay личности.

Личность в memory context:
- personality base и space overlay включают параметры тона, юмора, инициативности, мягкого возражения и обращения по имени;
- overlay уточняет поведение в рамках пространства и не перезаписывает базовый профиль глобально.

Ограничение объёма:
- факты: до 8,
- правила: до 6,
- эпизоды: до 3,
- длинные поля обрезаются перед добавлением в prompt.

Приватность:
- внутренние ID, сырые объекты и полный prompt не пишутся в activity.
- в `activity_logs` пишется только событие `memory_used_in_response` с безопасным `meta` (счётчики использованных блоков).

## Frontend UI памяти (реализовано)

Добавлена вкладка `Память`:
- список фактов профиля (key/value/status/source/даты);
- список правил поведения (title/instruction/status/source/даты);
- список эпизодов памяти (summary/status/source/даты);
- карточка личности Asya.
- для всех списков есть состояния `loading`, `empty` и `error`, плюс ручное обновление данных.

Доступные действия в UI:
- факт: подтвердить, редактировать, пометить устаревшим, запретить, скрыть (status=`deleted`);
- факт/правило: ручное создание;
- правило: редактировать текст;
- правило: отключить;
- личность: редактирование и сохранение параметров.

Технические ID пользователю не показываются.
