# Deployment

Документ описывает развёртывание Asya на VPS с публичным доменом (v0.4+).

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
- `MASTER_ENCRYPTION_KEY=<fernet-key>`
- `AUTH_SESSION_HASH_SECRET=<случайная строка>`
- OAuth redirect URI-переменные (`*_OAUTH_REDIRECT_URI`)
- SMTP-переменные (`EMAIL_TRANSPORT=smtp`, `SMTP_*`)
- Telegram webhook URL (`TELEGRAM_WEBHOOK_URL`)

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

- `GET /api/health` для liveness/readiness.
- `docker compose logs -f backend caddy` для runtime-диагностики.
