# Architecture (Asya Local)

Документ описывает фактическую архитектуру текущего кода Asya Local.

## Состав системы
- Frontend: `React + Vite + TypeScript` (`frontend/`)
- Backend: `FastAPI` (`backend/`)
- Интеграция моделей/embeddings: VseLLM OpenAI-compatible API
- Локальный запуск: Docker Compose

## Backend слои

### API routes (`backend/app/api`)
- `routes_health.py` -> `/api/health`
- `routes_models.py` -> `/api/models`, `/api/models/probe-reasoning`, `/api/models/reasoning-cache`
- `routes_settings.py` -> `/api/settings`
- `routes_chat.py` -> `/api/chat/stream`
- `routes_chats.py` -> `/api/chats*` (list/create/rename/archive/delete/messages)
- `routes_session.py` -> `/api/session*`, `/api/session/{session_id}/files`
- `routes_usage.py` -> `/api/usage*`

### Services (`backend/app/services`)
- `settings_service.py` -> чтение/обновление настроек
- `vsellm_client.py` -> вызовы `/models` и `/embeddings`, нормализация model metadata (`supports_chat`, `supports_stream`, `supports_vision`)
- `chat_service.py` -> сбор контекста, SSE-стриминг, диагностика совместимости модели, vision/retrieval логика, fallback на non-stream при явной ошибке streaming
- `file_service.py` -> валидация/сохранение файлов, извлечение текста, chunking, embeddings

### Storage (`backend/app/storage`)
- `session_store.py` -> in-memory сессии и сообщения
- `file_store.py` -> in-memory метаданные файлов + пути к временным файлам
- `vector_store.py` -> in-memory векторный индекс по сессии
- `usage_store.py` -> in-memory usage (chat/embeddings)
- `sqlite.py` -> SQLite для persisted settings

### DB foundation Asya 0.2 (`backend/app/db`, `backend/alembic`)
- `app/db/base.py` -> базовый SQLAlchemy `DeclarativeBase` для будущих моделей.
- `app/db/session.py` -> `engine` + `SessionLocal` для SQLite (`ASYA_DB_PATH` -> `sqlite+pysqlite:///...`).
- `app/db/models/` -> пакет моделей 0.2:
  - `users`
  - `auth_sessions`
  - `chats`
  - `messages`
  - `file_meta`
  - `usage_records`
  - `access_requests`
  - `encrypted_secrets`
- `alembic.ini` + `alembic/env.py` + `alembic/versions/` -> инфраструктура миграций.
- Первая ревизия: `20260502_01` (создаёт базовую multi-user схему, endpoint-ы пока не используют эти таблицы).

### Repository/Service слой 0.2 (без API wiring)
- `backend/app/repositories/user_repository.py`:
  - поиск пользователя по `id`/`email`;
  - создание пользователя.
- `backend/app/repositories/chat_repository.py`:
  - список чатов пользователя;
  - чтение чата только в рамках `user_id`;
  - работа с `Base-chat` для пользователя.
- `backend/app/services/user_service.py`:
  - создание пользователя;
  - автоинициализация чатов через `ChatServiceV2`.
- `backend/app/services/chat_service_v2.py`:
  - гарантия одного активного `Base-chat` на пользователя;
  - CRUD-операции для пользовательских чатов;
  - безопасная защита `Base-chat` от удаления/архивации.

### Переход session/chat сообщений в БД (этап 0.2)
- `/api/session*` и `/api/chat/stream` теперь работают через user-scoped `Chat` + `Message` таблицы:
  - `session_id` в legacy API выступает как алиас `chat_id`;
  - история `user/assistant` сообщений сохраняется в `messages` и переживает рестарт backend.
- SSE-контракт не изменён (`token` / `thinking` / `error` / `done`).
- `thinking/reasoning` по-прежнему не сохраняется как обычное сообщение в истории.
- Все операции чтения/удаления сессии и отправки сообщений проверяют принадлежность чата текущему `user_id`.
- `Base-chat` гарантируется при login (помимо create-user flow), чтобы пользователь всегда имел дефолтный чат.
- Временный переходный слой:
  - embeddings-векторы (`SessionVectorStore`) пока остаются in-memory;
  - для retrieval-chunks `session_id` всё ещё используется как runtime-ключ.

### Перенос file metadata и usage records в БД (этап 0.2)
- `FileMeta` теперь persistится в БД при upload:
  - поля: `user_id`, `chat_id`, `filename`, `content_type`, `size`, `storage_path`, `extracted_text_status`, `extracted_text_meta`.
- `UsageRecord` теперь persistится в БД:
  - `kind=chat|embeddings`, `model`, токены, `user_id`, `chat_id`, `created_at`.
- `/api/usage` и `/api/usage/session/{session_id}` строятся по DB-записям `UsageRecord` и ограничены текущим пользователем.
- При удалении/архивации сессии (чата) удаляются связанные runtime-артефакты и DB-метаданные (`FileMeta`, `UsageRecord`) в рамках владельца.

### Auth v1 слой (минимальный, cookie session)
- `backend/app/services/auth_service.py`:
  - регистрация (`open`) или сохранение `AccessRequest` (`closed`);
  - `bcrypt` hash пароля;
  - login/logout/me через `auth_sessions`.
- `backend/app/repositories/auth_session_repository.py`:
  - создание сессии;
  - поиск активной сессии по hash токена;
  - revoke сессии.
- `backend/app/api/routes_auth.py` + `backend/app/api/deps_auth.py`:
  - endpoint-ы `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`;
  - dependency `get_current_user` по `HttpOnly` cookie;
- в БД хранится только hash сессионного токена, не raw token.
- `login/me` дополнительно возвращают `preferred_chat_id` (Base-chat или последний доступный чат), чтобы frontend после входа открывал существующий чат.

### Шифрование пользовательских секретов (инфраструктура 0.2)
- Добавлен backend-сервис `SecretCryptoService` (`backend/app/services/secret_crypto_service.py`):
  - шифрование/дешифрование через Fernet;
  - ключ берётся из `MASTER_ENCRYPTION_KEY`;
  - при отсутствии ключа выбрасывается явная ошибка конфигурации без вывода секретов.
- Для хранения секретов добавлены:
  - `EncryptedSecretRepository` (`backend/app/repositories/encrypted_secret_repository.py`);
  - `EncryptedSecretService` (`backend/app/services/encrypted_secret_service.py`).
- В `encrypted_secrets.encrypted_value` сохраняется только ciphertext (`bytes`), plaintext в БД не пишется.
- Ошибки дешифрования при неверном ключе возвращаются как безопасная доменная ошибка без раскрытия значения секрета.

### Access Request / Beta Invite flow (v1)
- `backend/app/services/access_request_service.py`:
  - submit заявки (`pending`);
  - idempotent-поведение для повторной заявки на тот же email (возврат текущей pending-заявки);
  - admin approve/reject;
  - approve создаёт/активирует пользователя и гарантирует `Base-chat`.
- `backend/app/repositories/access_request_repository.py`:
  - операции чтения/создания/обновления access request.
- `backend/app/services/access_request_notifier.py`:
  - `DevLogAccessRequestNotifier` как mock/dev-слой уведомлений;
  - точка расширения для будущих email/Telegram интеграций без хранения секретов в текущем шаге.
- `backend/app/api/routes_access_requests.py`:
  - `POST /api/access-requests` (public submit);
  - `GET /api/admin/access-requests`, `POST /api/admin/access-requests/{id}/approve`, `POST /api/admin/access-requests/{id}/reject` (admin-only).

## Данные и жизненный цикл

### Настройки
- Хранятся в SQLite (`assistant_name`, `system_prompt`, `selected_model`)
- Загружаются/обновляются через `/api/settings`
- `VSELLM_API_KEY` хранится только в `.env` backend

### Сессии
- Создаются через `POST /api/session`
- Сообщения живут только в runtime (`SessionStore`)
- При `DELETE /api/session/{session_id}` удаляются:
  - сообщения сессии
  - file bindings
  - временные файлы
  - векторные чанки
  - usage сессии

### Файлы и retrieval
`POST /api/session/{session_id}/files`:
- валидирует лимиты и формат
- сохраняет файл во временный каталог `TMP_DIR`
- для PDF/DOCX/XLSX извлекает текст
- режет текст на чанки
- получает embeddings и сохраняет в `SessionVectorStore`

`POST /api/chat/stream`:
- берет историю только текущей сессии
- добавляет системный промт
- при наличии документных чанков делает retrieval и добавляет контекст
- для `file_ids` прикладывает только изображения (data URL)
- отдает SSE события `token`, `thinking` (опционально), `error`, `done`
- если провайдер присылает reasoning (`reasoning_content`/`reasoning`/`thinking` в delta или `message.*`), backend эмитит отдельный `event: thinking` перед/между `event: token`; reasoning не пишется в `SessionStore` и не передаётся провайдеру в следующих запросах
- для reasoning-моделей, чей upstream не отдаёт reasoning при `stream=true` (`deepseek-r1-*`, `openai/o1-*`, `openai/o3-*`), backend заранее переключается на non-stream запрос и эмитит `event: thinking` chunked-блоками до `event: token`
- при provider-ошибках `400/404/422` пытается извлечь точную причину из ответа провайдера и возвращает понятное сообщение с ID модели
- при явном указании провайдера на неподдерживаемый `stream=true` выполняет безопасный non-stream retry и маппит его в SSE

## Reasoning probe
- `POST /api/models/probe-reasoning` запускает короткий streaming-запрос (до 32 токенов) к моделям-кандидатам и фиксирует, какие реально присылают `reasoning_content`/`reasoning`/`thinking` в delta.
- Если `model_ids` не передан, кандидаты выбираются эвристикой по ID: содержит `thinking`, `reasoning`, `-r1`, `o3` (см. `is_likely_reasoning_model` в `vsellm_client.py`).
- Результаты кэшируются в process-памяти (`ReasoningProbeCache`, TTL 24 часа); `force=true` обходит кэш.
- `GET /api/models/reasoning-cache` отдает текущий кэш без обращения к провайдеру.
- Frontend `SettingsPage` использует ответ для бейджа `✅` напротив подтверждённых моделей в селекте моделей; для неподтверждённых, но похожих по эвристике, ставит `🧠`.

## Совместимость моделей
- `/api/models` не хардкодит whitelist моделей: используются provider metadata и эвристики по `capabilities`/`endpoints`.
- Явное `supports_chat=false` считается сильным сигналом: такая модель не должна использоваться как chat-модель.
- Если metadata неполная, модель не блокируется заранее; фактическая проверка происходит на chat-запросе.
- Явное `supports_vision=false` продолжает блокировать image input заранее.

## Vision-поведение
- Проверка идет по `/api/models` metadata
- Предзапрет только при явном `supports_vision=false`
- Если capability неизвестен, backend пробует запрос и возвращает ошибку провайдера, если он отклонит image input

## Usage
- `/api/usage` и `/api/usage/session/{session_id}`
- Chat usage собирается из stream-ответов, если провайдер присылает `usage`
- Embeddings usage собирается из upload/retrieval pipeline
- Стоимость не рассчитывается (`cost.status=unavailable`)

## Frontend и раздача
- Frontend собирается в `frontend/dist`
- В local-режиме backend может раздавать frontend из `FRONTEND_DIST_PATH`
- SPA fallback включен для не-API путей
- Вкладки `Чат`/`Настройки`/`Состояние` синхронизируются с URL (`/`, `/settings`, `/status`), но после первого открытия вкладка не размонтируется: компонент остаётся в runtime и скрывается через `hidden`. Это сохраняет состояние `ChatPage` до обновления страницы без `localStorage`/`IndexedDB`.

## Текущие технические ограничения
- Один пользователь
- Нет долговременной памяти/истории чатов
- Нет авторизации
- Нет внешних интеграций
- Нет web search
- Новый SQLAlchemy/Alembic контур пока не подключён к действующим endpoint-ам (добавлен как подготовительный слой 0.2).

## Целевая архитектура Asya 0.2 (план, ещё не факт)

Важно: этот раздел описывает целевое состояние 0.2 и не означает, что всё уже реализовано в текущем коде.

### Цели 0.2
- Перевести runtime-данные в persistent storage (SQLite) с миграциями Alembic.
- Добавить multi-user auth и изоляцию данных по `user_id`.
- Поддержать multiple chats для пользователя и обязательный чат `Base-chat`.
- Сохранить текущее поведение chat/files/retrieval/model-selection, постепенно заменяя in-memory слой.

### Целевые backend-компоненты
- DB слой:
  - SQLAlchemy-модели (`User`, `AuthSession`, `Chat`, `Message`, `FileMeta`, `UsageRecord`, `BetaInvite`/`AccessRequest`, при необходимости `EncryptedSecret`).
  - Alembic миграции как единственный механизм изменения схемы.
- Auth слой:
  - вход по magic-link и/или паролю;
  - web-session/cookie модель с `HttpOnly` (и `Secure` для production).
- Service/Repository слой:
  - user-scoped доступ к чатам, сообщениям, файлам и usage;
  - проверка, что пользователь не может читать/изменять чужие данные.

### Целевые API-принципы 0.2
- Переход к user-aware endpoint-ам без резкой потери обратной совместимости.
- Все сущности чатов и файлов должны быть связаны с владельцем (`user_id`).
- `Base-chat` должен создаваться автоматически для нового пользователя и быть защищён от случайного удаления.

### Целевой frontend-контур 0.2
- Минимальный UI для:
  - входа/выхода;
  - регистрации по заявке или инвайту;
  - базового кабинета;
  - списка чатов и операций create/rename/delete;
  - выбора и использования `Base-chat` по умолчанию.
- Текущие вкладки `Чат`, `Настройки`, `Состояние` должны остаться рабочими во время миграции.

### Явные границы 0.2
- Не включать в 0.2 долгосрочную память, формирование личности, голосовой режим, web search и новые внешние интеграции без отдельного решения.
