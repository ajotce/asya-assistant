# Observer snapshots (v0.5)

В v0.5 observer сохраняет снимки состояний сущностей для анализа паттернов во времени.

## Новые сущности

- `observed_entity_snapshots`
  - `user_id`, `provider`, `entity_type`, `entity_ref`
  - `normalized_state` (JSON, только safe metadata)
  - `observed_at`
  - `digest` (dedup по содержимому)
- `observed_entity_state_changes`
  - связь `snapshot_id` -> snapshot
  - `previous_snapshot_id` (опционально)
  - `change_kind`, `changed_fields`, `old_state`, `new_state`

## Источники snapshot

Observer читает `safe_error_metadata` подключений интеграций и строит snapshots для:

- `linear` tasks
- `todoist` tasks
- `google_calendar` events
- `gmail`/`imap` mail thread metadata

Содержимое писем/описаний не сохраняется. Поля вроде `subject`, `body`, `snippet`, токены и авторизационные данные вырезаются в snapshot service.

## Дедупликация

Перед сохранением считается SHA-256 digest от canonical JSON `normalized_state`.
Если digest совпал с последним snapshot той же сущности, новый snapshot не создаётся.

## Детекторы по истории

Добавлены history-based detector-ы:

- `RepeatedRescheduling` — повторные переносы (изменение `due_at`/`scheduled_at` >= 2 раз);
- `StaleTask` — задача долго без движения (`updated_at` старше 7 дней, не done);
- `DeadlineDrift` — заметный дрейф дедлайна (смещение >= 2 дней).

## Retention policy

Retention применяется при каждом observer run:

- удаляются snapshots старше `OBSERVER_SNAPSHOT_RETENTION_DAYS` (default: 30);
- связанные `observed_entity_state_changes` удаляются каскадно через FK.

## Наблюдаемость

Каждый sync observer пишет `activity_logs` событие `observer_sync` с метриками:

- `captured`: сколько новых snapshot создано;
- `retention_removed`: сколько старых snapshot удалено.
