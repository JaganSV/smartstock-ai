# Project Status

## Phase P1 (part 2): Synthetic data seed generator (BOB-P1-02)

**Status: implemented and validated; awaiting architect review.** Seed 42, t0 2026-09-30. Full outputs are in the BOB-P1-02 report; the generated evidence is `docs/evidence/seed_report.md`.

- Generator: `backend/data/seed/` (`catalog`, `scenarios`, `demand`, `stock`, `report`, `generator`), run with `make seed` (CLI `python -m data.seed.generator`). No new dependencies; pins unchanged.
- Seeded tables and counts (seed 42): categories 5, suppliers 5, warehouses 3, products 50, inventory_policies 150, inventory_levels 150, sales_daily 13,500, **incoming_stock 113**.
- Not seeded: `metric_snapshots`, `product_metrics`, `replenishment_recommendations`, `approval_decisions`, `executive_reports`, `documents`, `ai_interactions`, `audit_log`, `users`.
- **Currency assumption: all monetary values are INR** (cost bands, prices and revenue).
- **Deviation from BP 5.4 (recorded, not dropped):** the "4 seeded demo users" are **deferred to P3**, which owns password hashing. `users` stays empty until then (BOB-P1-02 7.9).
- Determinism: one `numpy.random.default_rng(seed)`; no `random`, `uuid`, wall clock or hash-dependent ordering in the data path. The RNG stream is only guaranteed for the pinned NumPy (2.5.5), so a NumPy upgrade can change the checksums and the report records the NumPy version.
- Checksums use natural keys (SKU, warehouse code) rather than surrogate ids, so they match between the generated data and the data read back from the database, across re-seeds.
- Scenario formulas in `data/seed/scenarios.py` are generator **design targets** only. They are not business logic, `app/` never imports `data/`, and P2 implements the real formulas independently (enforced by `tests/unit/test_import_boundaries.py`).
- Where a random draw would miss a band, the value is fitted back deterministically (clamping `available`, scaling the last 14 or 30 days of demand). There are no RNG retry loops.
- `secret-scan` excludes the exact path `docs/evidence/seed_report.md`: it lists SHA-256 checksums (64 hex characters), which match the long-string pattern but are not secrets.
- `mypy` now covers `app` and `data/seed` (strict), and pytest coverage covers `app` and `data/seed`.
- `REQUIRE_TEST_DB` (Q4): `make test` defaults to `1` (unreachable test DB fails); see `docs/TEST_STRATEGY.md`.

## Phase P1 (part 1): Database schema, migrations and repositories (BOB-P1-01)

**Status: implemented; finally accepted after the E1 re-run evidence in BOB-P1-02 (commit A).**

- Alembic head: `0001_core_schema` (17 tables plus `alembic_version`). `document_chunks` and the `vector` extension are absent (ADR-014).
- Databases: `smartstock` (dev) and `smartstock_test` (integration tests), both owned by `smartstock`.
- No new dependencies; pins unchanged.

### BP §5 clarifications

These are clarifications from BP §9.2, not design changes (recorded as required by BOB-P1-01 §7.3):

- `documents.status` (`UPLOADED`/`INDEXED`/`FAILED`, default `UPLOADED`).
- `documents.injection_warning` (boolean, default false).

### Interpretations made in BOB-P1-01 (for architect confirmation)

- Columns are NOT NULL unless §7.3 says `null`/`null allowed`. This was applied to columns whose nullability the table did not state (for example `product_metrics.*`, `inventory_levels.as_of`).
- `approval_decisions.decision` and similar columns with a CHECK but no stated default are NOT NULL with no default.
- `ai_interactions.validation_status` and `feature` are NOT NULL.
- `audit_log` has an index on `occurred_at` and one on `(entity_type, entity_id)` (spec: `index on (occurred_at), (entity_type, entity_id)`), plus `user_id` (every FK is indexed).
- `sales_daily`: besides the PK `(product_id, warehouse_id, sale_date)` and the required `sale_date` index, `warehouse_id` has its own index (FK rule).
- `UNIQUE` constraint names follow the requested convention (`uq_<table>_<first column>`), so `UNIQUE(product_id, warehouse_id)` is named `uq_inventory_levels_product_id`.
- `AiInteractionRepository.set_feedback` returns `True`/`False` (row found or not) and flushes; it does not commit.
- Every table is mapped without ORM `relationship()` objects (thin layer; joins are explicit queries).

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

- `npm` warns that `esbuild@0.21.5` has a postinstall script not covered by `allowScripts`; the dev server and tests work.

### C3: npm audit summary (BOB-P1-01, 2026-11-18; nothing upgraded)

The P0 report quoted 17 vulnerabilities. `npm audit` now reports **8 (2 critical, 1 high, 5 moderate)**; the advisory database changed and the lock file did not. `npm audit --omit=dev` reports **2 moderate** (both runtime). Architect decides by P4.

| Package | Severity | Runtime or dev-only | Vulnerable range | Fix offered by npm (all semver-major) | Advisories |
| --- | --- | --- | --- | --- | --- |
| vitest | critical | dev-only | <=4.1.10 | vitest@5.1.1 | GHSA-5xrq-8626-4rwp, GHSA-82fw-gwwq-j7x9 |
| tinypool | critical | dev-only | <=2.1.1 | vitest@5.1.1 | GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr |
| vite | high | dev-only | <=6.4.3 | vite@8.3.8 | 8 advisories, e.g. GHSA-4w7w-66w2-5vf9 (path traversal in optimized deps `.map` handling) |
| esbuild | moderate | dev-only | <=0.24.2 | vite@8.3.8 | GHSA-67mh-4wv8-2f99 (dev server accepts requests from any website) |
| @vitest/mocker | moderate | dev-only | <=4.1.11 | vitest@5.1.1 | GHSA-82fw-gwwq-j7x9, GHSA-qxg6-89mg-rqv8 |
| vite-node | moderate | dev-only | <=2.2.0-beta.2 | vitest@5.1.1 | via vitest/vite |
| react-router | moderate | runtime | 6.0.0 - 7.17.0 | react-router-dom@7.18.6 | GHSA-wrjc-x8rr-h8h6 (open redirect), GHSA-337j-9hxr-rhxg (constructor injection in SSR hydration) |
| react-router-dom | moderate | runtime | 6.0.0-alpha.0 - 7.17.0 | react-router-dom@7.18.6 | via react-router |

Notes: all the critical and high findings are in the test/dev toolchain (Vitest, Vite) and affect developer machines running dev servers. The two runtime findings are in React Router. The SSR hydration advisory does not apply (client-side SPA only). The open-redirect advisory concerns `<Link>`/`useNavigate` with untrusted URLs. Every fix is a major-version bump (Vitest 5, Vite 8, React Router 7), so none was applied.

### C4: Starlette/httpx deprecation warning in pytest

Full text:

```
.venv\Lib\site-packages\fastapi\testclient.py:1
  ...\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa
```

Source: `starlette/testclient.py` (Starlette 1.10.0) tries `import httpx2` first and, if missing, falls back to `httpx` and emits this warning. `fastapi.testclient` re-exports Starlette's `TestClient`, so the warning fires on import. The only real fix is to add `httpx2` as a dev dependency (a new package, outside the pinned set), so it is **not fixed** and is recorded here. Suppressing it with a `filterwarnings` entry was not done, to avoid hiding future deprecations. Proposal for the architect: swap `httpx==0.28.1` for `httpx2` in the dev extras once a version is approved.