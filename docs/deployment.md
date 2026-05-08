# Deployment

Документ описывает развёртывание Asya на VPS/облако с учётом cloud-readiness фиксов 1.0.2.

## 1. Требования к серверу

- Docker + Docker Compose
- Публичный IP
- Домен (A-запись на IP сервера)
- Открытые порты: 80, 443, 22

## 2. Reverse proxy

Выбран `Caddy`.

- локальный запуск остаётся через `docker-compose.yml` (без proxy);
- production запуск через `docker-compose.prod.yml` + `Caddyfile`.

Запуск production:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

## 3. Переменные окружения

Ключевые production-переменные:

- `APP_ENV=production`
- `ASYA_HOST=0.0.0.0`
- `PUBLIC_BASE_URL=https://<ваш-домен>`
- `PUBLIC_DOMAIN=<ваш-домен>`
- `AUTH_COOKIE_SECURE=true`
- `LOG_FORMAT=json` (structured logs в stdout/stderr)
- `MASTER_ENCRYPTION_KEY=<fernet-key>`
- `AUTH_SESSION_HASH_SECRET=<случайная строка>`
- `ASYA_DATABASE_URL=postgresql+psycopg://...` (рекомендуемый primary способ)
- `DATABASE_URL=...` поддерживается как backward-compatible alias
- или полный блок `POSTGRES_*` (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE`)
- `OBJECT_STORAGE_BACKEND=local|s3` (object storage abstraction, по умолчанию `local` для dev)
- `OBJECT_STORAGE_LOCAL_DIR=/app/data/blob` (для `local` backend)
- `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` (для `s3` backend)
- `S3_PRESIGN_ENDPOINT` (опционально; endpoint для выдачи presigned URL, если он отличается от внутреннего `S3_ENDPOINT`)
- OAuth redirect URI-переменные (`*_OAUTH_REDIRECT_URI`)
- SMTP-переменные (`EMAIL_TRANSPORT=smtp`, `SMTP_*`)
- `SCHEDULER_ENABLED=false` для multi-instance production (локальный in-process scheduler не должен стартовать на каждом pod).
- `SCHEDULER_INSTANCE_ROLE=leader` для выделенного scheduler-инстанса (остальные `follower`).

Примечания:
- SQLite fallback (`ASYA_DB_PATH`) допустим только для local/dev.
- В `APP_ENV=production` backend работает в fail-fast режиме: без `DATABASE_URL`/`POSTGRES_*` запуск считается некорректным.

## 4. Security checklist

- [ ] SSH только по ключам (`PasswordAuthentication no`, `PermitRootLogin no`).
- [ ] Firewall включён: разрешены только `22/tcp`, `80/tcp`, `443/tcp`.
- [ ] Fail2ban включён для SSH.
- [ ] `.env` заполнен на сервере и не попадает в git.
- [ ] `AUTH_COOKIE_SECURE=true` и публичный URL использует HTTPS.
- [ ] `MASTER_ENCRYPTION_KEY` и `AUTH_SESSION_HASH_SECRET` заданы и длинные.
- [ ] SMTP работает (письма approve/reject/setup-link доходят).
- [ ] Логи проверены: нет токенов/секретов/тел писем/аудио/контента файлов.
- [ ] Настроен backup `data/*.sqlite3` и периодическая проверка восстановления.

## 5. Наблюдаемость

- `GET /healthz` — liveness probe (процесс жив).
- `GET /readyz` — readiness probe (DB + writable tmp готовы).
- `GET /api/health` — legacy подробный health endpoint (оставлен для обратной совместимости).
- `docker compose logs -f backend caddy` для runtime-диагностики.
- Все backend-логи пишутся в stdout/stderr в JSON-формате с полями `ts`, `level`, `logger`, `event`, `request_id`.
- Локальный monitoring stack (Prometheus/Grafana/Loki/Promtail) запускается через:
  `docker compose -f docker-compose.yml -f docker-compose.monitoring.yml --profile monitoring up -d`.
- Детальная инструкция по метрикам/алертам/Sentry: `docs/monitoring.md`.
