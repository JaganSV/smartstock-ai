# Defects

Defects found and fixed during BOB-P0-01-R2 validation runs.

| ID | Phase | Description | Fix | File |
| --- | --- | --- | --- | --- |
| D-P0-001 | P0 | `make lint`: `ruff format --check` failed because the new baseline migration had no trailing newline. | Ran `ruff format` on the file. | `backend/alembic/versions/0000_baseline.py` |
| D-P0-002 | P0 | `make typecheck`: mypy strict error `Argument "headers" to "_error_response" has incompatible type "Mapping[str, str] | None"; expected "dict[str, str] | None"`. | Widened the parameter type to `Mapping[str, str] | None`. | `backend/app/core/errors.py` |
| D-P0-003 | P0 | `make migrate` from `backend/` failed: `Settings` read `.env` relative to the working directory, so `postgres_password` and `jwt_secret` were reported missing (`.env` is at the repo root). | Resolve `.env` from the repo root via `Path(__file__)`. | `backend/app/core/config.py` |
| D-P0-004 | P0 | `make lint`: ruff `I001` (import block not formatted) after the D-P0-003 edit. | `ruff check --fix` / `ruff format`. | `backend/app/core/config.py` |
