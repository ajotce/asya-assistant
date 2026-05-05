# v0.5 Parallel Plan

Цель: дать нескольким агентам безопасный параллельный workflow в фазе `v0.5` без конфликтов по коду и документации.

## 1. Ветвление

- Базовая ветка фазы: `0.5-extended`.
- Каждый агент работает в отдельной ветке: `feature/0.5-<scope>-<name>`.
- Feature-ветка создаётся только от актуальной `0.5-extended`.
- Прямые merge в `main` в рамках v0.5 запрещены.

## 2. Порядок merge

1. Агент завершает свой scope в feature-ветке.
2. Агент обновляет только свои feature-notes в `docs/v0.5/agent-notes/`.
3. Агент прогоняет проверки, релевантные изменению.
4. Merge feature-ветки в `0.5-extended`.
5. Координатор сводит central docs и разрешает конфликты между feature-ветками.
6. После закрытия acceptance v0.5 — merge `0.5-extended` в `main`.

## 3. Зоны ответственности (рекомендуемое разбиение)

### Agent A: Integrations platform extension

Scope:
- расширение провайдеров интеграций v0.5 (без изменения базовой security-модели).

Можно менять:
- `backend/app/integrations/**`
- `backend/app/services/integration_connection_service.py`
- `backend/app/api/routes_integrations.py`
- `backend/app/repositories/integration_connection_repository.py`
- `backend/tests/test_oauth_foundation.py`
- `backend/tests/test_integrations_api.py`

Нельзя менять без согласования с координатором:
- `backend/app/services/encrypted_secret_service.py`
- `backend/app/services/secret_crypto_service.py`
- central docs.

### Agent B: Mail providers (IMAP/Gmail extension layer)

Scope:
- v0.5 почтовые провайдеры и общий mail provider contract.

Можно менять:
- `backend/app/integrations/**`
- `backend/app/services/action_router.py` (только mail-команды)
- `backend/tests/test_chat.py` (только сценарии команд)
- `backend/tests/test_integrations_api.py`

Нельзя менять без согласования:
- observer/diary/voice модули.

### Agent C: File storage providers (Drive-like)

Scope:
- абстракция file storage provider + провайдеры v0.5.

Можно менять:
- `backend/app/storage/**`
- `backend/app/integrations/**` (только file-related provider adapters)
- `backend/app/api/routes_integrations.py` (только file endpoints)
- профильные тесты в `backend/tests/`

Нельзя менять без согласования:
- auth/session/security ядро.

### Agent D: Documents/templates pipeline

Scope:
- шаблоны документов, генерация артефактов, интеграция с хранилищем.

Можно менять:
- `backend/app/services/**` (только document/template сервисы)
- `backend/app/api/**` (только document/template endpoints)
- `backend/tests/**` по документам
- frontend document UI (если выделено отдельно)

Нельзя менять без согласования:
- существующий chat stream core в `chat_service.py` (кроме точек расширения).

### Agent E: Observer/briefing/rollback workflows

Scope:
- расширения `observer`, `notification center`, `rollback action`, `briefing data sources`.

Можно менять:
- `backend/app/services/observer_service.py`
- `backend/app/services/notification_center_service.py`
- `backend/app/notifications/**`
- `backend/app/repositories/activity_log_repository.py`
- `backend/app/api/routes_observer.py`
- профильные тесты

Нельзя менять без согласования:
- integrations OAuth base, crypto services.

## 4. Центральные документы, которые сводит только координатор

- `docs/roadmap.md`
- `docs/decisions.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/integrations.md`
- `docs/security.md`
- `docs/deployment.md`
- `docs/acceptance/v0.5.md`

Агенты не редактируют эти файлы напрямую, кроме явно согласованных случаев.

## 5. Feature docs, которые ведут агенты

- `docs/v0.5/agent-notes/<feature-name>.md`

Минимум в каждом note:
- цель feature-ветки;
- затронутые файлы;
- миграции/контракты;
- выполненные проверки;
- открытые вопросы для координатора.

## 6. Блокировки и конфликты

- Если изменение требует модификации shared контракта (`OAuthIntegration`, `EncryptedSecretService`, `ActionRouter`, `NotificationCenter`, `ActivityLogRepository`) — сначала согласовать с координатором.
- Если два агента неизбежно меняют один и тот же файл, координатор назначает owner этого файла и определяет порядок merge.
- При конфликте архитектурных решений агент не переписывает чужой код молча, а фиксирует блокер в feature-note.
