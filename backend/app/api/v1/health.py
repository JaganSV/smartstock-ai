"""Health endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.core.errors import ErrorEnvelope
from app.db.session import get_db

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


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="smartstock-backend", version=__version__)


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ErrorEnvelope}})
def ready(db: Annotated[Session, Depends(get_db)]) -> ReadyResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("Database readiness check failed", exc_info=exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return ReadyResponse(status="ready", database="ok", ai="not_configured")
