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

## Standing rule: gate outputs come from the final committed tree (A3)

The `make lint`, `make typecheck` and `make test` outputs pasted into a phase report must come from a run made **after the last commit, with `git status --short` empty**. A run on an uncommitted or later-edited tree is not evidence. If any file changes after the run, commit it and run all three gates again.

## Coverage

`pytest --cov` reports on `app/` (models and repositories are held at 100%) and on `data/seed/` (target at least 85%).

BOB-P2-02 targets: pp/analytics at least 95% and pp/services at least 90%. Final-tree values: 99.57% and 95.45%. Integration tests that call the recalculation service commit, so they use the seeded_engine and empty_engine fixtures (	ests/integration/conftest.py), which remove snapshots, metric rows and audit rows before and after every test.
