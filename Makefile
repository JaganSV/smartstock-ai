SHELL := bash

.PHONY: up down logs db-create migrate dev-backend dev-frontend test test-unit test-backend test-frontend lint lint-backend lint-frontend secret-scan typecheck typecheck-backend typecheck-frontend format seed recalc eval

# Host (native) Python from the Python 3.12 venv; Git Bash path style.
VENV := .venv/Scripts

# Secret-scan patterns: api keys, PEM blocks, long base64-like strings.
SECRET_RE = (api[_-]?key[[:space:]]*=[[:space:]]*[A-Za-z0-9]{8,}|apikey=|-----BEGIN|[A-Za-z0-9+]{40,}={0,2})

# --- Docker wrappers (validated in P10, ADR-013) ---
up:
	@echo "Docker targets are validated in P10 (ADR-013)"
	docker compose up --build -d

down:
	@echo "Docker targets are validated in P10 (ADR-013)"
	docker compose down

logs:
	@echo "Docker targets are validated in P10 (ADR-013)"
	docker compose logs -f

# --- Native development ---
# Needs the PostgreSQL superuser password (psql prompts, or set PGPASSWORD).
# The app role's password is read from .env and passed as a psql variable.
db-create:
	@pw="$$(grep -E '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"; \
	psql -U postgres -h localhost -v ON_ERROR_STOP=1 -v app_password="$$pw" -f backend/scripts/create_local_db.sql

migrate:
	cd backend && $(VENV)/alembic upgrade head

dev-backend:
	cd backend && $(VENV)/uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev -- --port 5173

test: test-backend test-frontend

# REQUIRE_TEST_DB=1 (default here) makes an unreachable test DB a failure, not a skip.
test-backend:
	cd backend && REQUIRE_TEST_DB=$${REQUIRE_TEST_DB:-1} $(VENV)/python -m pytest

# Unit tests only (no database needed).
test-unit:
	cd backend && $(VENV)/python -m pytest -m "not integration"

test-frontend:
	cd frontend && npm run test

lint: lint-backend lint-frontend secret-scan

lint-backend:
	cd backend && $(VENV)/python -m ruff check . && $(VENV)/python -m ruff format --check .

lint-frontend:
	cd frontend && npm run lint

# Fails (non-zero exit) if any tracked/untracked-but-not-ignored file matches a secret pattern.
# docs/evidence/seed_report.md is excluded by exact path: it lists SHA-256 checksums (64 hex chars),
# which match the long-string pattern but are not secrets (BOB-P1-02).
secret-scan:
	@if git grep --untracked -nIiE '$(SECRET_RE)' -- . ':!.env.example' ':!Makefile' ':!frontend/package-lock.json' ':!backend/requirements.lock' ':!docs/evidence/seed_report.md'; then \
		echo "Secret scan FAILED: potential secret found above"; exit 1; \
	else \
		echo "Secret scan passed"; \
	fi

typecheck: typecheck-backend typecheck-frontend

typecheck-backend:
	cd backend && $(VENV)/python -m mypy

typecheck-frontend:
	cd frontend && npm run typecheck

format:
	cd backend && $(VENV)/python -m ruff check --fix . && $(VENV)/python -m ruff format .
	cd frontend && npm run format

# Deterministic synthetic data (seed 42, t0 2026-09-30). Refuses to run unless APP_ENV is local/test.
seed:
	cd backend && PYTHONIOENCODING=utf-8 $(VENV)/python -m data.seed.generator

# Recalculate analytics on the dev database and write a dated snapshot (BOB-P2-02).
recalc:
	cd backend && PYTHONIOENCODING=utf-8 $(VENV)/python -m app.cli recalc --triggered-by cli

eval:
	@echo "Not implemented until P6"
