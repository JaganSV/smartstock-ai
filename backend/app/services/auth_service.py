"""Login: verification, audit-derived lockout and token issue (ADR-015).

``AuthService.login`` owns its transaction: every outcome writes one audit row and commits, so a
failed attempt is counted even though the request ends in an error. Nothing here logs or audits a
password or a token. The lockout rule is the same for existing and unknown usernames, and an
unknown user costs one bcrypt verification against ``DUMMY_HASH`` like a wrong password does.
"""

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import NoReturn

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import DUMMY_HASH, create_access_token, verify_password
from app.models.governance import AuditLog, User
from app.repositories.audit import USER_ENTITY, AuditRepository
from app.repositories.users import UsersRepository
from app.services.errors import AccountLockedError, AuthenticationError

logger = logging.getLogger(__name__)

LOGIN_SUCCESS = "LOGIN_SUCCESS"
LOGIN_FAILED = "LOGIN_FAILED"
LOGIN_LOCKED = "LOGIN_LOCKED"
INVALID_CREDENTIALS_MESSAGE = "Invalid username or password."


@dataclass(frozen=True)
class RequestContext:
    """Who is calling, for the audit row."""

    ip_address: str | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    expires_in: int
    user: User


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.audit = AuditRepository(session)
        self.users = UsersRepository(session)

    def _record(
        self,
        action: str,
        username: str,
        context: RequestContext,
        details: dict[str, object],
        user_id: int | None = None,
    ) -> None:
        self.audit.add(
            AuditLog(
                action=action,
                user_id=user_id,
                entity_type=USER_ENTITY,
                entity_id=username,
                details=details,
                request_id=context.request_id,
                ip_address=context.ip_address,
            )
        )

    def _retry_after(self, username: str, since: datetime, now: datetime) -> int:
        """Seconds until the oldest counted failure leaves the window (at least 1)."""
        oldest = self.audit.oldest_recent_login_failure(username, since)
        if oldest is None:
            return 1
        ends = oldest + timedelta(minutes=self.settings.login_lock_minutes)
        return max(1, math.ceil((ends - now).total_seconds()))

    def login(self, username: str, password: str, context: RequestContext) -> LoginResult:
        """Verify and return a token, or raise ``AccountLockedError`` / ``AuthenticationError``."""
        username = username.lower()
        now = datetime.now(UTC)
        since = now - timedelta(minutes=self.settings.login_lock_minutes)

        # Locked is decided from the audit log alone; the password is not looked at.
        failures = self.audit.count_recent_login_failures(username, since)
        if failures >= self.settings.login_max_failures:
            retry_after = self._retry_after(username, since, now)
            self._record(
                LOGIN_LOCKED,
                username,
                context,
                {"reason": "too_many_failures", "retry_after_seconds": retry_after},
            )
            self.session.commit()
            logger.warning("Login refused: account locked")
            raise AccountLockedError(retry_after)

        user = self.users.get_by_username(username)
        if user is None:
            verify_password(password, DUMMY_HASH)  # same cost as a real check: no timing oracle
            self._fail(username, context, "bad_credentials", None)
        password_ok = verify_password(password, user.password_hash)
        if not user.is_active:
            self._fail(username, context, "inactive", user.id)
        if not password_ok:
            self._fail(username, context, "bad_credentials", user.id)

        self._record(LOGIN_SUCCESS, username, context, {}, user_id=user.id)
        self.session.commit()
        token, expires_in = create_access_token(user)
        logger.info("Login succeeded for user id %d", user.id)
        return LoginResult(access_token=token, expires_in=expires_in, user=user)

    def _fail(
        self, username: str, context: RequestContext, reason: str, user_id: int | None
    ) -> NoReturn:
        """Audit LOGIN_FAILED, commit, and raise the one generic authentication error."""
        self._record(LOGIN_FAILED, username, context, {"reason": reason}, user_id=user_id)
        self.session.commit()
        logger.warning("Login failed: %s", reason)
        raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)


def load_active_user(session: Session, user_id: int) -> User | None:
    """The user for a token's ``sub``, or None if missing or deactivated (role comes from here)."""
    user = UsersRepository(session).get(user_id)
    return user if user is not None and user.is_active else None
