.PHONY: dev test lint build-frontend

dev:
	docker compose up --build

test:
	cd backend && python3 -m pytest -q

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
