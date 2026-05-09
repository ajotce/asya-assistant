.PHONY: dev test lint build-frontend backup backup-restore backend-py312-pytest backend-py312-ruff backend-py312-mypy backend-py312-all

dev:
	docker compose up --build

test:
	cd backend && python3 -m pytest -q

backend-py312-pytest:
	docker run --rm -v "$$PWD/backend:/work" -w /work python:3.12-slim sh -lc "pip install -q fastapi slowapi aiogram 'uvicorn[standard]' pydantic pydantic-settings SQLAlchemy alembic httpx python-multipart cryptography apscheduler pillow pymupdf python-docx openpyxl pytest && PYTHONPATH=/work python -m pytest -q"

backend-py312-ruff:
	docker run --rm -v "$$PWD/backend:/work" -w /work python:3.12-slim sh -lc "pip install -q ruff && PYTHONPATH=/work python -m ruff check app tests"

backend-py312-mypy:
	docker run --rm -v "$$PWD/backend:/work" -w /work python:3.12-slim sh -lc "pip install -q mypy fastapi slowapi aiogram 'uvicorn[standard]' pydantic pydantic-settings SQLAlchemy alembic httpx python-multipart cryptography apscheduler pillow pymupdf python-docx openpyxl types-openpyxl && PYTHONPATH=/work python -m mypy app"

backend-py312-all: backend-py312-pytest backend-py312-ruff backend-py312-mypy

lint:
	@if command -v npm >/dev/null 2>&1; then \
		cd frontend && npm run lint; \
	else \
		docker run --rm -v "$$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm run lint"; \
	fi

build-frontend:
	@if command -v npm >/dev/null 2>&1; then \
		cd frontend && npm run build; \
	else \
		docker run --rm -v "$$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm run build"; \
	fi

backup:
	@set -a; [ -f .env ] && . ./.env; set +a; \
	SQLITE_PATH="$${SQLITE_PATH:-./data/asya.sqlite3}" \
	BACKUP_DIR="$${BACKUP_DIR:-./backups}" \
	./infra/backup/backup_sqlite.sh

backup-restore:
	@if [ -z "$(BACKUP)" ]; then \
		echo "Usage: make backup-restore BACKUP=<path-to-backup-file> [FORCE=1]"; \
		exit 1; \
	fi
	@set -a; [ -f .env ] && . ./.env; set +a; \
	DEST_PATH="$${SQLITE_PATH:-./data/asya.sqlite3}"; \
	if [ "$${FORCE:-0}" = "1" ]; then \
		./infra/backup/restore_sqlite.sh --force "$(BACKUP)" "$$DEST_PATH"; \
	else \
		./infra/backup/restore_sqlite.sh "$(BACKUP)" "$$DEST_PATH"; \
	fi
