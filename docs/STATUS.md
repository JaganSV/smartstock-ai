# Project Status

## Phase P0: Foundation & scaffolding (BOB-P0-01 / BOB-P0-01-R2)

**Status: P0 gate passed on the native toolchain, except the items below that are explicitly NOT RUN.**

- Deferred to P10: Docker validation (`docker compose up --build`, image builds). The Dockerfiles and `docker-compose.yml` are present and updated per ADR-013, but NOT RUN: deferred to P10 (ADR-013).
- The real "PostgreSQL service stopped" check was NOT RUN: the shell is not elevated, so `Stop-Service` was denied. The DB-down path was verified instead by starting the backend with `POSTGRES_PORT=59999` (unreachable); see the R2 report.

### Tool versions (host)

| Tool | Version |
| --- | --- |
| Git | 2.56.1.windows.1 |
| Node.js | v26.13.1 (LTS codename "Lithium") |
| npm | 11.20.0 |
| Python (venv) | 3.12.0 (`py -3.12`) |
| GNU Make | 3.81 (GnuWin32; also runs from Git Bash) |
| PostgreSQL | 16.16 (service `postgresql-x64-16`) |

### Pinned versions

Python: direct pins in `backend/pyproject.toml`; full transitive lock in `backend/requirements.lock` (`pip freeze --exclude-editable`, Python 3.12.0). Python `>=3.12,<3.13`.

| Package | Version |
| --- | --- |
| fastapi | 0.163.1 |
| uvicorn[standard] | 0.54.0 |
| pydantic | 2.14.3 |
| pydantic-settings | 2.16.3 |
| sqlalchemy | 2.1.9 |
| alembic | 1.20.1 |
| psycopg[binary] | 3.3.9 |
| pandas | 3.1.1 |
| numpy | 2.5.5 |
| pytest (dev) | 9.2.0 |
| pytest-cov (dev) | 7.1.0 |
| httpx (dev) | 0.28.1 |
| ruff (dev) | 0.17.5 |
| mypy (dev) | 2.4.1 |
| setuptools (build) | 80.9.0 |

Node: exact versions in `frontend/package.json`; full tree in `frontend/package-lock.json`. The versions below are those resolved in the lock.

| Package | Version |
| --- | --- |
| react, react-dom | 18.3.1 |
| @mui/material, @mui/icons-material | 7.3.11 |
| @emotion/react | 11.14.0 |
| @emotion/styled | 11.14.1 |
| recharts | 2.15.4 |
| axios | 1.21.1 |
| react-router-dom | 6.30.6 |
| vite | 5.4.21 |
| @vitejs/plugin-react | 4.7.0 |
| typescript | 5.9.3 |
| vitest | 2.1.9 |
| @testing-library/react | 16.3.3 |
| @testing-library/dom | 10.4.2 |
| @testing-library/jest-dom | 6.10.0 |
| jsdom | 25.0.1 |
| eslint, @eslint/js | 9.39.5 |
| typescript-eslint | 8.73.0 |
| eslint-plugin-react-hooks | 5.2.0 |
| globals | 15.15.0 |
| prettier | 3.10.1 |
| @types/react | 18.3.31 |
| @types/react-dom | 18.3.7 |

Pin changes: none. Every pin installed and passed lint, typecheck and tests unchanged.

Base images (Docker, not run): `postgres:16`, `python:3.12-slim`, `node:lts-slim` (tags, not digests).

### Known items

- `npm install` reports 17 vulnerabilities (5 moderate, 10 high, 2 critical). `npm audit fix --force` was not run (it makes breaking changes outside P0 scope). To be reviewed before P10.
- `npm` warns that `esbuild@0.21.5` has a postinstall script not covered by `allowScripts`; the dev server and tests work.
- pytest shows a `StarletteDeprecationWarning` from `fastapi.testclient` (httpx vs httpx2). Not suppressed; no pin changed.
