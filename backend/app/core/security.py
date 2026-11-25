"""Password hashing (bcrypt, cost 12) and access tokens (PyJWT, HS256), per ADR-015.

Passwords and token values are never logged here. The role in a token is informational only:
``app.api.deps.get_current_user`` reads the role and ``is_active`` from the database per request.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.models.governance import User

BCRYPT_COST = 12
MAX_PASSWORD_BYTES = 72  # bcrypt's input limit; longer input is rejected, never truncated
ISSUER = "smartstock-backend"
ALGORITHM = "HS256"  # pinned; the settings reject any other value
REQUIRED_CLAIMS = ["sub", "username", "role", "iat", "exp", "jti", "iss"]

# bcrypt hash (cost 12, like real hashes) of random bytes, made once at import. Checked when
# the username does not exist, so unknown users cost the same time as wrong passwords. It protects
# nothing; it is generated rather than hard-coded so no hash literal sits in the source (ADR-015).
DUMMY_HASH: str = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt(rounds=12)).decode()


class PasswordTooLongError(ValueError):
    """The password is longer than 72 bytes (bcrypt would silently ignore the rest)."""


class InvalidTokenError(Exception):
    """The token is missing a claim, expired, tampered with, or signed with another algorithm."""


def _password_bytes(plain: str) -> bytes:
    data = plain.encode("utf-8")
    if len(data) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return data


def hash_password(plain: str) -> str:
    """bcrypt hash (cost 12) as a UTF-8 string. Raises ``PasswordTooLongError`` above 72 bytes."""
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt(rounds=BCRYPT_COST)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time check (``bcrypt.checkpw``). Over-long or malformed input is simply False."""
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("utf-8"))
    except ValueError:  # too long, or a malformed hash
        return False


def create_access_token(user: User, now: datetime | None = None) -> tuple[str, int]:
    """Signed token for ``user`` and its lifetime in seconds."""
    settings = get_settings()
    issued = now or datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    claims: dict[str, Any] = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": issued,
        "exp": issued + lifetime,
        "jti": secrets.token_hex(16),
        "iss": ISSUER,
    }
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Verified claims. Algorithms are pinned to HS256, so ``alg=none`` and HS512 are rejected.

    Checks the signature, ``exp``, ``iat`` and ``iss`` and that every required claim is present.
    Raises ``InvalidTokenError`` (never the library's exceptions) on any failure.
    """
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(type(exc).__name__) from None  # the class name only, no token text
    return claims
