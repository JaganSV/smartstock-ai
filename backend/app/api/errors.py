"""Service errors -> HTTP errors for the read endpoints, and their OpenAPI response entries."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import HTTPException

from app.core.errors import DetailedHTTPException, ErrorEnvelope
from app.services.errors import (
    NoSalesDataError,
    NoSnapshotError,
    NotFoundError,
    SnapshotStaleError,
)


@contextmanager
def service_errors() -> Iterator[None]:
    """``NotFoundError`` -> 404 ``NOT_FOUND``; no snapshot / no sales -> 409 ``CONFLICT``;
    stale snapshot -> 409 ``CONFLICT`` with ``details.fields`` (names only, never values)."""
    try:
        yield
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (NoSnapshotError, NoSalesDataError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except SnapshotStaleError as exc:
        raise DetailedHTTPException(409, str(exc), {"fields": exc.fields}) from None


DESCRIPTIONS = {
    403: "The role does not hold the required capability.",
    404: "Unknown id (path or filter).",
    409: "No analytics snapshot available. Run a recalculation.",
}


def error_responses(*codes: int, **overrides: str) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries using the BP 6.1 envelope. ``overrides`` replace a
    description by status, e.g. ``error_responses(409, d409="...")``."""
    return {
        code: {
            "model": ErrorEnvelope,
            "description": overrides.get(f"d{code}", DESCRIPTIONS[code]),
        }
        for code in codes
    }
