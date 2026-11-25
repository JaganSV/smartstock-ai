"""Route dependencies: the only way a route gets an identity (ADR-015).

``get_current_user`` verifies the token and then reloads the user from the database, so the role
and ``is_active`` always come from the database, never from the token. ``require_roles`` and
``require_capability`` add the 403 check. Health and login are the only routes without them.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.rbac import ROLE_MATRIX
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.governance import User
from app.services.auth_service import load_active_user

__all__ = [
    "CurrentUser",
    "DbSession",
    "get_current_user",
    "get_db",
    "require_capability",
    "require_roles",
]

bearer_scheme = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    """401 for a missing, malformed or invalid token, or an unknown or inactive user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated()
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = int(claims["sub"])
    except (InvalidTokenError, ValueError):
        raise _unauthenticated() from None
    user = load_active_user(db, user_id)
    if user is None:
        raise _unauthenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Dependency that gives 403 ``FORBIDDEN`` unless the user's (database) role is in ``roles``."""
    allowed = frozenset(role.value for role in roles)

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="You do not have permission to do this.")
        return user

    return checker


def require_capability(capability: str) -> Callable[[User], User]:
    """``require_roles`` for the roles that hold ``capability`` in ``ROLE_MATRIX`` (BP 10.2)."""
    return require_roles(*ROLE_MATRIX[capability])
