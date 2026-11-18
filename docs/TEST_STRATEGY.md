# Test Strategy

## Layers

- **Backend unit tests** (`backend/tests/unit/`, pytest): no database. FastAPI dependency overrides replace the DB; the seed generator's pure generation is tested in memory.
- **Backend integration tests** (`backend/tests/integration/`, marker `integration`): run against a real PostgreSQL 16 database (`smartstock_test`, URL in `TEST_DATABASE_URL`). The DB is migrated to head once per session; each test runs in a transaction that is rolled back (SAVEPOINT mode, so tests can provoke `IntegrityError`). No SQLite.
- **Evaluation tests** (`backend/tests/evaluation/`): added in P6.
- **Frontend tests**: Vitest + React Testing Library with a mocked API client.

## Strict mode for integration tests: `REQUIRE_TEST_DB`

| Value | Unreachable / unset test DB | Where it is the default |
| --- | --- | --- |
| `1` | integration tests **fail** with a clear message | `make test` / `make test-backend` |
| `0` (or unset) | integration tests are **skipped** with a clear message | plain `pytest`, ad-hoc runs |

`make test-unit` runs `-m "not integration"`, so it never touches the database and is unaffected by the flag.

Examples:

```bash
make test                                   # strict: needs the test DB
REQUIRE_TEST_DB=0 make test                 # tolerant: skips integration tests if the DB is down
make test-unit                              # unit tests only
REQUIRE_TEST_DB=1 TEST_DATABASE_URL=postgresql+psycopg://x:y@localhost:59999/none make test   # fails clearly
```

The intent is that a green `make test` always means the integration layer really ran.

## Coverage

`pytest --cov` reports on `app/` (models and repositories are held at 100%) and on `data/seed/` (target at least 85%).
