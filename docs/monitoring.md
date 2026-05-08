# Monitoring (Sentry / Prometheus / Grafana / Loki)

Статус: реализовано в задаче `1.0.6` для локального мониторинга через Docker Compose profile `monitoring`.

## 1. Цель и scope наблюдаемости

В фазе 1.0.6 наблюдаемость закрывает три слоя:

- error tracking: `Sentry` для runtime-исключений backend;
- metrics: `Prometheus` + `Grafana` для HTTP/LLM/DB/integrations;
- centralized logs (local): `Loki` + `Promtail` для логов контейнеров.

Cloud logging (Yandex Cloud Logging или ELK через Terraform) остаётся на этап `1.0.5`.

## 2. Sentry

### 2.1 Переменные окружения

В `.env` (или секретах окружения):

- `SENTRY_DSN`
- `SENTRY_TRACES_SAMPLE_RATE` (по умолчанию `0.0`)
- `SENTRY_PROFILES_SAMPLE_RATE` (по умолчанию `0.0`)

Если `SENTRY_DSN` пустой, инициализация Sentry отключена.

### 2.2 Что санитайзится перед отправкой

`before_send` фильтр в `backend/app/main.py`:

- удаляет `request.data` (raw body);
- удаляет `request.cookies`;
- редактирует чувствительные поля по ключам (`authorization`, `cookie`, `token`, `password`, `secret`, `api_key`, `session` и т.п.).

Требование безопасности выполняется: в Sentry не отправляются raw bodies и токены.

### 2.3 Проверка Sentry

Для smoke-теста используйте test-route (только при `ENABLE_TEST_ROUTES=true`):

```bash
curl -i http://localhost:8000/api/test/sentry
```

Ожидаемо: `500`, событие появляется в Sentry-проекте.

## 3. Prometheus метрики

### 3.1 Endpoint

- endpoint: `/metrics` (конфигурируется через `METRICS_PATH`);
- формат: Prometheus text exposition;
- защита:
  - если заданы `METRICS_BASIC_AUTH_USERNAME` и `METRICS_BASIC_AUTH_PASSWORD`, используется Basic Auth;
  - иначе действует `METRICS_IP_ALLOWLIST` (поддерживаются одиночные IP и CIDR-сети, например `172.16.0.0/12`).

### 3.2 Базовые HTTP метрики

Через `prometheus-fastapi-instrumentator`:

- `http_requests_total`
- `http_request_duration_seconds_*` (bucket/sum/count)

Используются для RPS, latency (p50/p95/p99), error rate.

### 3.3 Кастомные метрики Asya

- `asya_active_sessions` — активные auth sessions;
- `asya_integration_api_calls_total{provider,operation,status}` — внешние integration API calls;
- `asya_llm_tokens_used_total{kind,model}` — токены LLM и embeddings;
- `asya_db_pool_checked_out` — checked out connections пула SQLAlchemy;
- `asya_expired_integration_tokens{provider}` — количество `expired` integration tokens;
- `asya_llm_provider_up` — доступность LLM-провайдера (1/0).

## 4. Grafana

### 4.1 Dashboard

Файл:

- `infra/grafana/dashboards/asya-overview.json`

Графики:

- RPS;
- latency p50/p95/p99;
- 5xx rate;
- LLM tokens;
- DB pool checked-out;
- integration API calls;
- active sessions.

### 4.2 Локальный доступ

После запуска monitoring stack:

- Grafana: `http://localhost:3000`
- default credentials: `admin/admin` (меняются через `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`).

## 5. Alerts (Prometheus rule groups)

Файл:

- `infra/grafana/alerts.yaml`

Настроенные алерты:

- `AsyaHighErrorRate` — `error_rate > 5%` за 5 минут;
- `AsyaHighLatencyP95` — `p95_latency > 2s` за 10 минут;
- `AsyaDatabaseUnavailable` — backend scrape недоступен;
- `AsyaLLMProviderUnavailable` — `asya_llm_provider_up == 0`;
- `AsyaIntegrationTokensExpiredMassively` — массово истёкшие integration tokens.

## 6. Loki + Promtail (локальная централизация логов)

Локально используется стек:

- `loki` — хранилище логов;
- `promtail` — сбор логов контейнеров через Docker socket.

В Grafana datasource `Loki` создаётся автоматически (provisioning).

## 7. Как запустить локально

```bash
docker compose up --build -d

docker compose \
  -f docker-compose.yml \
  -f docker-compose.monitoring.yml \
  --profile monitoring up -d
```

Проверка:

```bash
curl -u "$METRICS_BASIC_AUTH_USERNAME:$METRICS_BASIC_AUTH_PASSWORD" \
  http://localhost:8000/metrics | head
```

Если basic auth не задан, запрос идёт без `-u` и разрешается только с IP из `METRICS_IP_ALLOWLIST`.

## 8. Acceptance checks для 1.0.6

- `/metrics` доступен и защищён;
- Prometheus scrapes backend метрики;
- Grafana показывает dashboard `Asya Overview`;
- Loki получает backend logs;
- Sentry получает backend exceptions при включённом `SENTRY_DSN`.
