# Backup and Restore Runbook (1.0.7)

## Что бэкапится

1. PostgreSQL:
- hourly `BACKUP_MODE=incremental`: WAL LSN marker (инкрементальная точка, требует WAL archiving в infra 1.0.5);
- daily `BACKUP_MODE=full`: full logical SQL dump (schema + data).

2. Object Storage:
- hourly off-site sync в отдельный bucket/регион.

Каждый backup-объект сопровождается `manifest.json`:
- `timestamp`
- `size_bytes`
- `checksum_sha256`
- `source_instance`

## Скрипты

- `infra/backups/pg_backup.sh`
- `infra/backups/s3_sync_backup.sh`
- `infra/backups/restore_pg.sh`
- `infra/backups/cleanup_old_backups.sh`

## Расписание (reference)

- hourly: `pg-backup@incremental.service`
- daily: `pg-backup@full.service`
- hourly: `s3-offsite-sync.service`
- daily: `backup-cleanup.service`

Реальная установка scheduler выполняется в 1.0.5 (Terraform).

## Restore (staging)

1. Выберите full backup (`*.sql.gz`).
2. Убедитесь, что target DB — staging (`name contains stage/staging`).
3. Выполните:

```bash
export RESTORE_CONFIRM=YES
export BACKUP_OBJECT_KEY='backups/postgresql/full/<timestamp>/pg-full-<timestamp>.sql.gz'
./infra/backups/restore_pg.sh
```

4. Проверьте целостность:
- row counts по ключевым таблицам;
- sample checksum (`md5(string_agg(...))`).

## Incremental recovery note

Hourly incremental в 1.0.7 хранит WAL LSN marker. Полный point-in-time recovery требует WAL archiving/restore pipeline, который внедряется в 1.0.5 Terraform/Cloud deploy.

## Retention

`cleanup_old_backups.sh` удаляет объекты старше `BACKUP_RETENTION_DAYS` (default 30) c поддержкой pagination `list-objects-v2`.

## Ежемесячный drill

Не реже 1 раза в месяц:
- восстановить последний full backup в staging;
- сверить row count/checksum;
- зафиксировать дату, backup key, длительность и результат.
