# Asya v1.0

Asya — персональный AI-ассистент с multi-user архитектурой, памятью, интеграциями, голосовым режимом и публичным release-контуром.

Репозиторий: `ajotce/asya-assistant`  
Актуальная релизная линия: `v1.0.0` (готовность к тегу)

## Быстрый старт

1. Подготовьте окружение:
```bash
cp .env.example .env
```

2. Соберите frontend:
```bash
make build-frontend
```

3. Поднимите backend:
```bash
docker compose up --build
```

4. Проверьте health:
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/api/health
```

## Основные команды

```bash
make test
make lint
make build-frontend
```

Если локальный Python < 3.12, используйте контейнерные backend-проверки:
```bash
make backend-py312-pytest
make backend-py312-ruff
make backend-py312-mypy
make backend-py312-all
```

## Документация

- [Roadmap](docs/roadmap.md)
- [Acceptance v1.0](docs/acceptance/v1.0.md)
- [API](docs/api.md)
- [Architecture](docs/architecture.md)
- [Security](docs/security.md)
- [Security Audit v1.0](docs/security-audit-v1.0.md)
- [Load Test v1.0](docs/load-test-v1.0.md)
- [Deployment](docs/deployment.md)
- [Development](docs/development.md)
- [Testing](docs/testing.md)
- [User Guide](docs/user-guide.md)
- [FAQ](docs/faq.md)
- [Development Log](docs/development-log.md)

## Release

- Текущий release artifact: `CHANGELOG.md`
- Черновик анонса: `docs/release-v1.0-announcement.md` (не публиковать)

