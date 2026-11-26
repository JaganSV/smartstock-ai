"""Authentication endpoints: POST /auth/login (public) and GET /auth/me (any role)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import CurrentUser, DbSession
from app.core.config import Settings, get_settings
from app.core.rbac import capabilities_for
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse, UserOut
from app.services.auth_service import AuthService, RequestContext
from app.services.errors import AccountLockedError, AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"description": "Invalid username or password."},
        429: {"description": "Locked"},
    },
)
def login(
    body: LoginRequest,
    request: Request,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    context = RequestContext(
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )
    try:
        result = AuthService(db, settings).login(body.username, body.password, context)
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}
        ) from None
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"}
        ) from None
    user = result.user
    return LoginResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserOut(id=user.id, username=user.username, role=user.role),
    )


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        capabilities=capabilities_for(user.role),
    )
