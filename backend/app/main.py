"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app import __version__
from app.api.v1 import health
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from app.db.session import get_session_factory
from app.services.analytics_service import recalculate_on_startup


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    """Build the app. ``session_factory`` defaults to the settings-built one (tests inject one)."""
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """FR-B5: optional synchronous startup recalculation. A failure never stops the app."""
        if settings.recalc_on_startup_enabled:
            factory = session_factory if session_factory is not None else get_session_factory()
            app.state.startup_recalc = recalculate_on_startup(factory)
        yield

    app = FastAPI(title="SmartStock AI", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # from settings only; wildcard is rejected
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    # Added last => outermost, so the request ID is set before CORS and handlers run.
    app.add_middleware(RequestIdMiddleware)

    register_exception_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
