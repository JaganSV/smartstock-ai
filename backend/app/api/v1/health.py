"""Health endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.core.errors import DetailedHTTPException, ErrorEnvelope
from app.db.session import get_db
from app.services.analytics_service import STARTUP_ERROR, analytics_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    ai: str
    analytics: str  # "ok" | "no_snapshot" | "error" (additive, BOB-P2-02)


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="smartstock-backend", version=__version__)


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ErrorEnvelope}})
def ready(request: Request, db: Annotated[Session, Depends(get_db)]) -> ReadyResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("Database readiness check failed", exc_info=exc)
        # Analytics cannot be read without the database, so it is reported as "error" in details.
        raise DetailedHTTPException(
            503, "Database unavailable", {"database": "unavailable", "analytics": "error"}
        ) from exc
    startup_failed = getattr(request.app.state, "startup_recalc", None) == STARTUP_ERROR
    return ReadyResponse(
        status="ready",
        database="ok",
        ai="not_configured",
        analytics=analytics_status(db, startup_failed),
    )
