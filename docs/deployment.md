# Deployment

Документ описывает развёртывание Asya на VPS с публичным доменом (v0.4+).

## 1. Требования к серверу

- Docker + Docker Compose
- Публичный IP
- Домен (A-запись на IP сервера)
- Открытые порты: 80, 443, 22

## 2. Reverse proxy (Caddy)

Рекомендуется Caddy для автоматических Let's Encrypt сертификатов.

Пример `Caddyfile`:

```
asya.example.com {
    reverse_proxy localhost:8000
}
```

### 2.1. Docker-вариант

В `docker-compose.yml` добавить сервис Caddy:

```yaml
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    restart: unless-stopped
```

## 3. Переменные окружения

Обязательные для продакшена:

```env
# Основные
APP_ENV=production
ASYA_HOST=0.0.0.0
ASYA_PORT=8000

# Безопасность
MASTER_ENCRYPTION_KEY=<сгенерировать: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
AUTH_SESSION_HASH_SECRET=<случайная строка 64+ символов>
AUTH_COOKIE_NAME=asya_session
AUTH_COOKIE_SECURE=true
AUTH_SESSION_TTL_HOURS=168
AUTH_REGISTRATION_MODE=open

# VseLLM
VSELLM_API_KEY=<ключ>
VSELLM_BASE_URL=https://api.vsellm.ru/v1

# База данных
ASYA_DB_PATH=./data/asya-0.2.sqlite3

# Telegram (опционально)
TELEGRAM_BOT_TOKEN=<токен от @BotFather>
TELEGRAM_BOT_USERNAME=<имя бота без @>
TELEGRAM_LINK_WEBHOOK_SECRET=<случайная строка>

# Голос (опционально)
YANDEX_SPEECHKIT_API_KEY=<ключ>
YANDEX_SPEECHKIT_FOLDER_ID=<folder_id>
GIGACHAT_API_KEY=<ключ>

# Интеграции (опционально)
LINEAR_OAUTH_CLIENT_ID=<...>
LINEAR_OAUTH_CLIENT_SECRET=<...>
GOOGLE_OAUTH_CLIENT_ID=<...>
GOOGLE_OAUTH_CLIENT_SECRET=<...>
TODOIST_OAUTH_CLIENT_ID=<...>
TODOIST_OAUTH_CLIENT_SECRET=<...>
```

## 4. Первый запуск

```bash
# Клонировать репозиторий
git clone <repo-url> && cd asya-assistant

# Настроить .env из .env.example
cp .env.example .env
# Заполнить обязательные переменные

# Собрать frontend
make build-frontend

# Запустить
docker compose up --build -d

# Создать первого пользователя (если registration_mode=closed)
docker compose exec backend python -m backend.cli user create --login admin@example.com --password <пароль> --role admin
```

## 5. Обновление

```bash
git pull
make build-frontend
docker compose up --build -d
```

## 6. Безопасность

- SSH только по ключу (запретить PasswordAuthentication)
- Firewall: ufw allow 22/tcp; ufw allow 80/tcp; ufw allow 443/tcp
- Fail2ban для SSH
- Регулярное резервное копирование файла БД (`data/asya-*.sqlite3`)
- Не хранить `.env` в репозитории (уже в `.gitignore`)

## 7. Мониторинг

- `GET /api/health` — проверка здоровья
- Логи: `docker compose logs -f backend`
- Рекомендуется подключить UptimeRobot или аналогичный сервис для внешнего мониторинга `/api/health`
