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
# 1. Configuration. Set POSTGRES_PASSWORD, JWT_SECRET and the password inside TEST_DATABASE_URL
#    in .env (git-ignored)
cp .env.example .env

# 2. Create the local DB role and the smartstock and smartstock_test databases
#    (asks for the PostgreSQL superuser password)
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
| `make test` | Backend unit + integration (pytest, `REQUIRE_TEST_DB=1`: an unreachable test DB fails) and frontend (vitest) tests |
| `make test-unit` | Backend unit tests only (no database needed) |
| `make lint` | Ruff, ESLint and the secret scan |
| `make typecheck` | `mypy` (strict on `app/`) and `tsc --noEmit` |
| `make format` | Ruff format and Prettier |
| `make seed` | Seed the dev DB with the deterministic synthetic dataset (seed 42); see "Seeding" |
| `make recalc` | Recalculate analytics on the dev DB and write a dated snapshot; see "Recalculation" |
| `make eval` | Placeholder (not implemented until P6) |
| `make up` / `down` / `logs` | Docker Compose wrappers (see below) |

## Recalculation

`make recalc` runs the analytics on the seeded dev database and writes one dated snapshot (150 `product_metrics` rows plus one `audit_log` row, in one transaction). Run `make migrate` and `make seed` first.

```bash
make recalc
cd backend && .venv/Scripts/python -m app.cli recalc --triggered-by cli --report ../docs/evidence/p2_risk_distribution.md
```

Exit codes: 0 ok, 1 analytics or data error (for example an empty `sales_daily`), 2 bad arguments, 3 database error. The backend also recalculates once at startup when `RECALC_ON_STARTUP=true` (default on when `APP_ENV=local`); a failure is logged and the app keeps running. `GET /api/v1/health/ready` reports `analytics` as `ok`, `no_snapshot` or `error`.
## Seeding

`make seed` loads the synthetic dataset into the dev database (run `make migrate` first). It is deterministic: the same seed gives identical data, every time. Re-running replaces the seeded tables in one transaction, so the result never changes.

```bash
make seed                                          # seed 42, data_as_of_date 2026-09-30
cd backend && .venv/Scripts/python -m data.seed.generator --dry-run                # no DB access
cd backend && .venv/Scripts/python -m data.seed.generator --seed 43 --dry-run      # different data
```

Options: `--seed N`, `--as-of YYYY-MM-DD`, `--dry-run`, `--report-path PATH`. Exit codes: 0 ok, 1 coverage failure, 2 refused (`APP_ENV` must be `local` or `test`) or bad arguments, 3 database error. It writes `docs/evidence/seed_report.md` (scenario coverage and checksums). All data is synthetic and all entities are fictional; currency is INR.

Seeded tables: categories, suppliers, warehouses, products, inventory_policies, inventory_levels, incoming_stock, sales_daily. Users are not seeded until P3.

## Docker (P10)

`docker-compose.yml` and the Dockerfiles are kept so the project stays Docker-ready, but they are not executed or validated until P10, on a Docker-capable machine (ADR-013). The `make up`, `down` and `logs` targets print a reminder and then call Docker Compose.

See `docs/STATUS.md` for pinned versions and phase status.
