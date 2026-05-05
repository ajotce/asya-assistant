# Agent E: observer state snapshots

Ветка: `0.5/observer-state-snapshots`

Что сделано:

1. Добавлены модели и миграция:
   - `ObservedEntitySnapshot`
   - `ObservedEntityStateChange`
2. Добавлен `ObserverSnapshotService`:
   - sanitize safe-state (без sensitive content)
   - digest dedup
   - compare with previous snapshot
   - запись `state_change`
   - retention cleanup
3. Observer подключён к snapshots:
   - захват snapshot-ов из metadata Linear/Todoist/Calendar/Mail
   - `observer_sync` activity c `captured`/`retention_removed`
4. Добавлены detector-ы истории:
   - `RepeatedRescheduling`
   - `StaleTask`
   - `DeadlineDrift`
5. Добавлены тесты:
   - `test_observer_snapshot_service.py`
   - `test_observer_service_snapshots.py`

Ограничения текущей реализации:

- snapshots строятся из `safe_error_metadata` подключения; если провайдер не кладёт туда entity metadata, история не пополняется;
- detector-ы не читают сырые API провайдеров напрямую в этом шаге.
