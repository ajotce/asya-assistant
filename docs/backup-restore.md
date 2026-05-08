# Локальные бэкапы SQLite (1.0.7)

В рамках задачи 1.0.7 бэкапы выполняются только на локальный диск (Mac), без S3 и cloud.

## Переменные окружения

- `SQLITE_PATH` — путь к SQLite-файлу (например, `./data/asya.sqlite3`).
- `BACKUP_DIR` — директория для бэкапов (по умолчанию `./backups`).

В `.env.example`:

```env
BACKUP_DIR=./backups
```

## Ручной запуск бэкапа

Через `make`:

```bash
make backup
```

Напрямую скриптом:

```bash
./infra/backup/backup_sqlite.sh ./data/asya.sqlite3 ./backups
```

или через env:

```bash
SQLITE_PATH=./data/asya.sqlite3 BACKUP_DIR=./backups ./infra/backup/backup_sqlite.sh
```

После копирования скрипт запускает:

```bash
sqlite3 <backup_file> "PRAGMA integrity_check;"
```

Если результат не `ok`, файл бэкапа удаляется и скрипт завершается с `exit 1`.

Формат имени бэкапа:

- `asya_backup_YYYYMMDD_HHMMSS.db`

Retention:

- хранится только 30 последних файлов, более старые удаляются автоматически.

## Автоматизация через cron

Пример ежедневного запуска в 02:30:

```cron
30 2 * * * cd /absolute/path/to/asya-assistant && /usr/bin/make backup >> /absolute/path/to/asya-assistant/backups/backup.log 2>&1
```

`/absolute/path/to/asya-assistant` замените на реальный путь к репозиторию.

## Восстановление

Через `make`:

```bash
make backup-restore BACKUP=./backups/asya_backup_20260508_023000.db
```

По умолчанию `restore_sqlite.sh` перед перезаписью вызывает `docker compose down`.

Если нужно восстановить без остановки Docker Compose (явное подтверждение риска):

```bash
make backup-restore BACKUP=./backups/asya_backup_20260508_023000.db FORCE=1
```

Напрямую скриптом:

```bash
./infra/backup/restore_sqlite.sh [--force] <backup_file> <destination_sqlite_path>
```

После восстановления скрипт проверяет целостность через `PRAGMA integrity_check`.

## Ручная проверка целостности бэкапа

```bash
sqlite3 ./backups/asya_backup_20260508_023000.db "PRAGMA integrity_check;"
```

Ожидаемый результат:

```text
ok
```
