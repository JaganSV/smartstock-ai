# Defects

Defects found and fixed during validation runs (BOB-P0-01-R2, BOB-P1-01, BOB-P1-02).

| ID | Phase | Description | Fix | File |
| --- | --- | --- | --- | --- |
| D-P0-001 | P0 | `make lint`: `ruff format --check` failed because the new baseline migration had no trailing newline. | Ran `ruff format` on the file. | `backend/alembic/versions/0000_baseline.py` |
| D-P0-002 | P0 | `make typecheck`: mypy strict error `Argument "headers" to "_error_response" has incompatible type "Mapping[str, str] | None"; expected "dict[str, str] | None"`. | Widened the parameter type to `Mapping[str, str] | None`. | `backend/app/core/errors.py` |
| D-P0-003 | P0 | `make migrate` from `backend/` failed: `Settings` read `.env` relative to the working directory, so `postgres_password` and `jwt_secret` were reported missing (`.env` is at the repo root). | Resolve `.env` from the repo root via `Path(__file__)`. | `backend/app/core/config.py` |
| D-P0-004 | P0 | `make lint`: ruff `I001` (import block not formatted) after the D-P0-003 edit. | `ruff check --fix` / `ruff format`. | `backend/app/core/config.py` |
| D-P1-001 | P1 | mypy strict: `levels_with_policies` return type did not match `Row[...]` generics. | Return a plain `list[tuple[InventoryLevel, InventoryPolicy | None]]`. | `backend/app/repositories/inventory.py` |
| D-P1-002 | P1 | mypy strict: `Result.rowcount` is not on the typed `Result`, so `set_feedback` needed a `type: ignore`. | Reimplemented `set_feedback` via `get()` and attribute assignment plus flush (no ignore needed). | `backend/app/repositories/ai_interactions.py` |
| D-P1-003 | P1 | Spec requires an index on `audit_log (occurred_at)`; the first autogenerate had only `(entity_type, entity_id)` and `user_id`. | Added `ix_audit_log_occurred_at` to the model and the reviewed migration. | `backend/app/models/governance.py`, `backend/alembic/versions/0001_core_schema.py` |
| D-P1-004 | P1 | Test bug: the insert-only API test counted the class attribute `model` as a public method. | List only functions (`inspect.getmembers(..., isfunction)`). | `backend/tests/integration/test_repositories.py` |
| D-P1-005 | P1 | Alembic `DeprecationWarning`: no `path_separator` in `alembic.ini`. | Added `path_separator = os`. | `backend/alembic.ini` |
| D-P1-006 | P1 | ruff E501 on a long docstring line in the integration conftest. | Shortened the docstring. | `backend/tests/integration/conftest.py` |
| D-P1-007 | P1-02 | `INSERT ... RETURNING` result was consumed with `dict(result.tuples())`; `Result.tuples()` is deprecated in SQLAlchemy 2.1 and the dict conversion failed at runtime (`ChunkedIteratorResult is not subscriptable`). | Replaced with a small `_id_map()` that reads `(key, id)` rows directly. No deprecation warnings remain. | `backend/data/seed/generator.py` |
| D-P1-008 | P1-02 | Integration test compared `inventory_levels.as_of` as an ISO string; the DB session returned the same instant in the local time zone (`+05:30`). | Compare the instant in UTC (`astimezone(UTC)`). The stored value was correct. | `backend/tests/integration/test_seed_db.py` |
| D-P1-009 | P1-02 | Test used `dict(...)` over a `.tuples()` result to build the status counts (same deprecation as D-P1-007). | Iterate the rows directly. | `backend/tests/integration/test_seed_db.py` |
| D-P1-010 | P1-02 | `make lint` secret scan flagged `docs/evidence/seed_report.md`: SHA-256 checksums (64 hex chars) match the long-string pattern. | Excluded that exact path from the scan (comment in the Makefile). Every other file is still scanned. | `Makefile` |
| D-P1-011 | P1-02 | Draft code carried two `type: ignore` comments (a NumPy array annotation and test `tmp_path` typing). | Removed both before the first commit: typed the array alias `IntArray` and used `Path` for `tmp_path`. The tree has no `type: ignore` in `app/`, `data/` or `tests/`. | `backend/data/seed/report.py`, `backend/tests/integration/test_seed_db.py` |
