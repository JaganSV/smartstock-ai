"""Service errors -> HTTP errors for the read endpoints, and their OpenAPI response entries."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import HTTPException

from app.core.errors import ErrorEnvelope
from app.services.errors import NoSalesDataError, NoSnapshotError, NotFoundError


@contextmanager
def service_errors() -> Iterator[None]:
    """``NotFoundError`` -> 404 ``NOT_FOUND``; no snapshot / no sales -> 409 ``CONFLICT``."""
    try:
        yield
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (NoSnapshotError, NoSalesDataError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries using the BP 6.1 envelope."""
    descriptions = {
        404: "Unknown id (path or filter).",
        409: "No analytics snapshot available. Run a recalculation.",
    }
    return {code: {"model": ErrorEnvelope, "description": descriptions[code]} for code in codes}
