.PHONY: dev test lint build-frontend

dev:
	docker compose up --build

test:
	cd backend && python3 -m pytest -q

lint:
	@echo "Lint configuration is not implemented yet (stage 0)."

build-frontend:
	cd frontend && npm run build
