# Action Rollback (v0.5 J4)

## Что реализовано

В проект добавлен явный rollback-слой для действий, которые технически можно откатить безопасно.

Ключевые сущности:
- `ActionEvent` — запись выполненного действия с rollback metadata;
- `RollbackPlan` — preview плана отката (service-level модель);
- `RollbackStatus` — состояние отката (`not_requested`, `previewed`, `executed`, `skipped`, `failed`).

Rollback всегда explicit:
- сначала preview через API;
- затем execute только с явным подтверждением (`confirmed=true`).

Каждый rollback (успешный, skipped или failed) пишет событие в `activity_logs`.

## Safe rollback metadata

Для action event сохраняются:
- `provider`;
- `operation`;
- `target_id`;
- `previous_state` (только если безопасно и доступно);
- `reversible`;
- `rollback_strategy`;
- `rollback_deadline` (optional);
- `rollback_notes` (почему откат невозможен/ограничен);
- `safe_metadata` (без секретов).

## Поддержанные rollback-сценарии

Поддержаны стратегии:
- Todoist `create` -> `todoist_create_delete_or_close` (если есть `target_id`);
- Todoist `update` -> `todoist_update_restore_fields` (если есть `previous_state`);
- Linear `update` -> `linear_update_restore_fields` (если есть `previous_state`);
- Calendar `create` -> `calendar_create_delete_event` (если есть `target_id`);
- Calendar `update` -> `calendar_update_restore_fields` (если есть `previous_state`);
- Drive/Yandex/OneDrive `create` -> `drive_create_delete_file_if_safe` (если есть `target_id`);
- Memory/Rules/Personality -> `memory_version_rollback` (через существующий snapshot rollback).

Важно: для внешних провайдеров backend слой rollback сейчас реализует безопасный orchestration + metadata/logging; конкретные provider executors подключаются отдельно и в тестах мокируются.

## Неподдержанные rollback-сценарии

Явно помечаются как irreversible:
- отправленные email;
- внешне видимые comments/messages;
- любые действия без достаточного `previous_state`/`target_id`.

Bitrix write rollback не реализуется, так как Bitrix write вне допустимого scope.

## API

Добавлены endpoint-ы:

- `GET /api/actions/reversible`
  - список action events;
  - по умолчанию `reversible_only=true`;
  - для UI activity log.

- `GET /api/actions/{action_event_id}/rollback-preview`
  - preview rollback плана.

- `POST /api/actions/{action_event_id}/rollback`
  - execute rollback;
  - body: `{ "confirmed": true }`.

## UI (Activity Log)

На странице активности добавлена кнопка `Откатить` для reversible actions:
- доступна только если action связан с activity item и `reversible=true`;
- перед execute делается preview;
- затем запрашивается подтверждение пользователя.

## Ограничения текущего шага

- Нельзя обещать откат `email send`;
- rollback невозможен без safe previous state/target id;
- delete rollback выполняется только если хватает snapshot/backup metadata.
