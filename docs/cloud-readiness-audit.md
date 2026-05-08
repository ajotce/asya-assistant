# Cloud-readiness audit (1.0.1)

Дата: 2026-05-08  
Ветка: `1.0/1.0.1-cloud-audit`  
База: `1.0-public`

Цель аудита: зафиксировать блокеры и риски для cloud deployment (Yandex Cloud / AWS / Selectel) и горизонтального масштабирования (`N > 1` инстансов).

## Scope

Проверены:
- `backend/app/*`, `backend/alembic*`, `.env.example`, `docker-compose.yml`
- `frontend/src/*`, `frontend/vite.config.ts`

Исключено из таблицы как noise:
- unit/integration tests;
- `package-lock` и внешние dependency-метаданные;
- vendor URL провайдеров OAuth/STT/TTS как таковые (они ожидаемо внешние и уже конфигурируемые).

## Findings

| # | Файл:строка | Проблема | Категория | Приоритет (P0/P1/P2) | Подзадача 1.0.2.X |
|---|---|---|---|---|---|
| 1 | `backend/app/core/config.py:30` | `SQLITE_PATH` default указывает на локальный файл (`./data/asya.sqlite3`), что закрепляет SQLite-first runtime. | DB / Stateful storage | P1 | `1.0.2.A: Подготовить DB config к cloud-first режиму (POSTGRES_* как primary, SQLite только dev fallback).` |
| 2 | `backend/app/core/config.py:31` | `ASYA_DB_PATH` default = локальный SQLite (`./data/asya-0.2.sqlite3`), не подходит для multi-instance production. | DB / Stateful storage | P0 | `1.0.2.B: Убрать SQLite как production-default; ввести явный `DATABASE_URL`/`POSTGRES_*` и fail-fast для prod без Postgres.` |
| 3 | `backend/alembic.ini:4` | Alembic по умолчанию смотрит на SQLite URL (`sqlite+pysqlite:///./data/asya-0.2.sqlite3`). | DB migration | P1 | `1.0.2.C: Перевести Alembic config на env-driven URL без sqlite hard default.` |
| 4 | `backend/app/core/config.py:156` | `asya_db_url` property всегда формирует `sqlite+pysqlite:///...`; отсутствует переключение на Postgres DSN. | DB / Cloud readiness | P0 | `1.0.2.D: Добавить универсальный `DATABASE_URL` builder с поддержкой Postgres и безопасной валидацией env.` |
| 5 | `backend/app/db/session.py:10` | `_ensure_parent_dir` создает parent directory для sqlite-файла; логика привязана к локальному FS. | DB adapter coupling | P1 | `1.0.2.E: Изолировать SQLite-specific path logic в dev-only ветку и убрать из общего engine bootstrap.` |
| 6 | `backend/app/bootstrap_db.py:3` | Bootstrap-скрипт использует `sqlite3` и `sqlite_master`; migration bootstrap SQLite-specific. | DB migration / SQLite-specific | P1 | `1.0.2.F: Разделить bootstrap на dialect-aware flow; SQLite legacy path оставить только для migration tool 1.0.3.` |
| 7 | `backend/app/storage/runtime.py:9` | `SessionStore` in-memory singleton в процессе; при `N>1` инстансах состояние сессий расходится между pod-ами. | Horizontal scaling / Process-local state | P0 | `1.0.2.G: Удалить in-memory session store из runtime; хранить session state только в DB/Redis.` |
| 8 | `backend/app/storage/runtime.py:10` | `SessionFileStore` инициализируется в локальный `TMP_DIR`; данные файлов process-local. | File storage / Horizontal scaling | P0 | `1.0.2.H: Вынести файл-хранилище в provider abstraction (S3-compatible primary, локальный только dev).` |
| 9 | `backend/app/storage/file_store.py:28` | При старте `SessionFileStore` выполняет `shutil.rmtree(self._root)`: удаление локального state, несовместимо с shared runtime и рестартами. | Data durability / Stateful FS | P0 | `1.0.2.I: Убрать destructive reset tmp-root; ввести TTL cleanup job для ephemeral cache без массового удаления.` |
| 10 | `backend/app/services/file_service.py:127` | Upload-поток пишет файлы на локальный диск (`target_path.open("wb")`) и сохраняет `storage_path` как FS path. | File storage | P0 | `1.0.2.J: Перевести upload pipeline на storage provider API (S3 object key вместо local path).` |
| 11 | `backend/app/services/diary_service.py:135` | Аудио дневника сохраняется на локальный FS (`DIARY_AUDIO_DIR`), что ломает multi-instance доступ и durability. | File storage / Product data | P0 | `1.0.2.K: Перевести diary audio в S3-compatible storage с object-key в БД.` |
| 12 | `backend/app/api/routes_health.py:83` | Есть только `/api/health`; отсутствуют стандартные `/healthz` и `/readyz` для k8s probes. | Observability / Probes | P1 | `1.0.2.L: Добавить `/healthz` (liveness alias) и `/readyz` (readiness с DB/storage checks).` |
| 13 | `backend/app/api/routes_health.py:83` | Текущий health endpoint содержит внешнюю проверку VseLLM, что может флапать readiness из-за внешнего API, не отражая готовность pod к трафику. | Observability / Probe semantics | P1 | `1.0.2.M: Разделить liveness/readiness и external dependency checks; внешние проверки вынести в diagnostics endpoint.` |
| 14 | `backend/app/core/logging.py:7` | Формат логов строковый (`%(asctime)s...`), не JSON-структура; усложняет централизованный ingestion в cloud logging stack. | Logging / Observability | P1 | `1.0.2.N: Ввести JSON logging formatter для stdout/stderr (structured fields: ts, level, logger, event, request_id).` |
| 15 | `backend/app/services/scheduler_service.py:19` | APScheduler in-process запускается в каждом инстансе (`BackgroundScheduler`), что приведет к дублированию observer jobs при масштабировании. | Horizontal scaling / Scheduler | P0 | `1.0.2.O: Вынести scheduler в отдельный worker/queue или distributed scheduler с leader election.` |
| 16 | `backend/app/storage/runtime.py:13` | `ReasoningProbeCache` in-memory; кэш не разделяется между инстансами и нестабилен после рестартов. | Horizontal scaling / Caching | P2 | `1.0.2.P: Перевести runtime cache на Redis (или отключить shared-cache assumptions в UI).` |
| 17 | `backend/app/storage/runtime.py:14` | `pending_actions_store` — process-local dict; подтверждения action могут теряться/расходиться между инстансами. | Horizontal scaling / State consistency | P0 | `1.0.2.Q: Хранить pending actions в DB (или Redis с TTL), убрать process-local dict.` |
| 18 | `backend/app/api/routes_telegram.py:1` + `.env.example:52` | В конфиге есть `TELEGRAM_WEBHOOK_URL`, но в runtime нет webhook endpoint и URL не используется (только polling flow). | Integrations / Telegram cloud mode | P1 | `1.0.2.R: Реализовать webhook-mode для Telegram (configurable `TELEGRAM_WEBHOOK_URL`) либо удалить мертвый env до внедрения.` |
| 19 | `frontend/src/api/client.ts:69` | Frontend всегда использует относительные `/api` пути; отсутствует runtime API base override для CDN/separate frontend-host сценария. | Frontend cloud config | P1 | `1.0.2.S: Добавить runtime-config для API base URL (`window.__ASYA_CONFIG__`/env-injected config).` |
| 20 | `frontend/src/pages/SettingsPage.tsx:56` | IMAP preset `ProtonMail Bridge` жестко ссылается на `127.0.0.1:1143`; для cloud users это вводит невалидный default. | Frontend hardcoded host | P2 | `1.0.2.T: Пометить preset как local-only и скрывать/дизейблить в cloud profile.` |
| 21 | `frontend/vite.config.ts:8` | Dev proxy жестко на `http://localhost:8000`; не блокер prod, но зашит локальный assumption в tooling. | Frontend dev tooling | P2 | `1.0.2.U: Вынести proxy target в env (`VITE_DEV_API_PROXY_TARGET`) для унификации команд dev/staging.` |
| 22 | `.env.example:23` | В примере окружения закреплен `/app/data` и SQLite file path как дефолт операционного режима. | Config hygiene | P1 | `1.0.2.V: Пересобрать `.env.example` под cloud-first (Postgres/S3/health/logging blocks) и явно пометить SQLite как dev-only.` |

## SQLite-specific inventory для задачи 1.0.3

Найденные SQLite-специфичные места в runtime-коде:
- `backend/app/core/config.py:30-31,160`
- `backend/app/db/session.py:10-14`
- `backend/app/bootstrap_db.py:3,10-13,28-33,43`
- `backend/app/storage/sqlite.py:3,12-14`
- `backend/alembic.ini:4`

Найдено по паттернам:
- `PRAGMA`: не найдено в `backend/app/*`.
- `INSERT OR REPLACE`: не найдено в `backend/app/*`.
- `sqlite-vec`: не найдено в `backend/app/*` (в коде runtime сейчас не используется).

## Secrets check

Критичных hardcoded секретов (API keys / tokens) в runtime-коде не найдено.  
Секреты читаются из env (`Settings`) и/или encrypted storage слоя.  
Риск для follow-up: `AUTH_SESSION_HASH_SECRET` имеет слабый dev default (`dev-change-me`) — для production нужен fail-fast policy.

## Stateful storage map

Текущее состояние:
- `/app/data`: SQLite DB (`ASYA_DB_PATH`, `SQLITE_PATH`) и `diary_audio_dir` (по env).
- `/app/tmp`: `SessionFileStore` (session uploads, temp extracted files).
- In-memory process state: session store, vector store, usage store, pending actions, reasoning cache.

Для облака (target-state):
- DB -> managed PostgreSQL.
- User/product files -> S3-compatible storage.
- Ephemeral cache -> local tmp/redis с явными TTL и без хранения source of truth.
- Process-local state -> вынести в DB/Redis/queue.

## Plan for Этап 2 (1.0.2)

Порядок выполнения (sequential backbone):
1. `1.0.2.A/B/C/D/E/F/V` — DB/config cleanup, cloud-first env model, отделение SQLite legacy path. Объём: `M`.
2. `1.0.2.L/M/N` — health/readiness/logging standardization (`/healthz`, `/readyz`, JSON logs). Объём: `S-M`.
3. `1.0.2.G/O/Q/P` — устранение process-local state и single-instance scheduler assumptions. Объём: `M-L`.
4. `1.0.2.H/I/J/K` — storage abstraction + S3 migration path для uploads/diary audio. Объём: `L`.
5. `1.0.2.R` — Telegram webhook-mode (или явное defer с cleanup env). Объём: `S-M`.
6. `1.0.2.S/T/U` — frontend runtime config/hardcoded host cleanup. Объём: `S`.

Что можно делать параллельно (при общем sequential этапе):
- Параллельно после шага 1: ветка observability (`L/M/N`) и ветка frontend (`S/T/U`).
- Параллельно после шага 3: Telegram (`R`) отдельно от S3 migration (`H/I/J/K`).
- Не параллелить между собой: DB/config migration (`A..F`) и storage migration (`H..K`), чтобы избежать конфликтов в `config`/migration pipeline.

## Сводка приоритетов

- `P0`: 8
- `P1`: 10
- `P2`: 4

## Status after 1.0.2

Легенда:
- ✅ закрыто в 1.0.2
- ⚠️ частично / временное решение в 1.0.2
- ⏭️ перенесено в 1.0.3+ (за рамками текущего шага)

P0:
- #2 ✅
- #4 ✅
- #7 ⚠️ process-local runtime session store помечен как ephemeral; source of truth для chat state уже в БД.
- #8 ⏭️ (S3/provider abstraction планируется в 1.0.4, сейчас local/dev fallback)
- #9 ✅
- #10 ⏭️ (полный storage provider migration в 1.0.4)
- #11 ⏭️ (полный diary audio S3 migration в 1.0.4)
- #15 ⚠️ добавлен explicit production warning + policy (`SCHEDULER_ENABLED=false`), но distributed scheduler ещё не внедрён.
- #17 ✅

P1:
- #1 ✅
- #3 ✅
- #5 ✅
- #6 ✅
- #12 ✅
- #13 ✅
- #14 ✅
- #18 ✅ (`TELEGRAM_WEBHOOK_URL` удалён из `.env.example` как неиспользуемый до внедрения webhook-mode)
- #19 ✅
- #22 ✅

P2:
- #16 ⚠️ явно помечен как process-local ephemeral (без Redis на этом этапе).
- #20 ✅
- #21 ✅
