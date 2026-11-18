# SmartStock AI

SmartStock AI is a simulated enterprise retail inventory copilot: deterministic Python analytics produce every number, and IBM Granite on IBM watsonx.ai explains them and answers supplier-policy questions through RAG. All data is synthetic.

> Status: Phase P0 (foundation and scaffolding). No business logic, database schema or AI code yet.

The developer toolchain is native Windows (ADR-013). Run every `make` target from **Git Bash**.

## Prerequisites

| Tool | Check |
| --- | --- |
| Git | `git --version` |
| Node.js (LTS) | `node --version`, `npm --version` |
| Python 3.12 (never 3.13) | `py -3.12 --version` |
| GNU Make, runnable from Git Bash | `make --version` |
| PostgreSQL 16 for Windows (service running, `psql` on PATH) | `psql --version`, `Get-Service postgresql*` |

pgvector is deferred to P7 (ADR-014); do not install it now.

## Quick start (native Windows)

```bash
# 1. Configuration (set POSTGRES_PASSWORD and JWT_SECRET in .env; it is git-ignored)
cp .env.example .env

# 2. Create the local DB role and database (asks for the PostgreSQL superuser password)
make db-create
#    equivalent: psql -U postgres -h localhost -v ON_ERROR_STOP=1 \
#      -v app_password='<POSTGRES_PASSWORD from .env>' -f backend/scripts/create_local_db.sql

# 3. Backend virtualenv (Python 3.12) and dependencies
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
backend/.venv/Scripts/python.exe -m pip install -e "backend[dev]"

# 4. Frontend dependencies
cd frontend && npm ci && cd ..

# 5. Migrate and run (separate terminals)
make migrate
make dev-backend
make dev-frontend
```

## URLs

| Service | URL |
| --- | --- |
| Backend health | http://localhost:8000/api/v1/health |
| Backend readiness | http://localhost:8000/api/v1/health/ready |
| Frontend | http://localhost:5173 |

PowerShell users: call `curl.exe`, not the `curl` alias (which is `Invoke-WebRequest`).

## Make targets

| Target | Description |
| --- | --- |
| `make db-create` | Create the `smartstock` role and database via `psql` |
| `make migrate` | `alembic upgrade head` from the venv |
| `make dev-backend` | uvicorn with reload on port 8000 |
| `make dev-frontend` | Vite dev server on port 5173 |
| `make test` | Backend (pytest) and frontend (vitest) tests |
| `make lint` | Ruff, ESLint and the secret scan |
| `make typecheck` | `mypy` (strict on `app/`) and `tsc --noEmit` |
| `make format` | Ruff format and Prettier |
| `make seed` | Placeholder (not implemented until P1) |
| `make eval` | Placeholder (not implemented until P6) |
| `make up` / `down` / `logs` | Docker Compose wrappers (see below) |

## Docker (P10)

`docker-compose.yml` and the Dockerfiles are kept so the project stays Docker-ready, but they are not executed or validated until P10, on a Docker-capable machine (ADR-013). The `make up`, `down` and `logs` targets print a reminder and then call Docker Compose.

See `docs/STATUS.md` for pinned versions and phase status.
