"""Audit log repository: insert-only for writes; read methods for lockout and the admin list."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, RowMapping, func, or_, select

from app.models.governance import AuditLog, User
from app.repositories.base import Repository

LOGIN_FAILED = "LOGIN_FAILED"
LOGIN_SUCCESS = "LOGIN_SUCCESS"
USER_ENTITY = "user"


class AuditRepository(Repository[AuditLog]):
    """Insert-only (BP 10.8): inherits get/list/add and defines no update or delete.

    The read methods below carry no business rules; the lockout decision is the auth service's.
    """

    model = AuditLog

    def _recent_failures(self, username: str, since: datetime) -> list[ColumnElement[bool]]:
        """WHERE clauses: this user's LOGIN_FAILED rows since ``since``, after the last success."""
        latest_success = (
            select(func.max(AuditLog.occurred_at))
            .where(
                AuditLog.action == LOGIN_SUCCESS,
                AuditLog.entity_type == USER_ENTITY,
                AuditLog.entity_id == username,
            )
            .scalar_subquery()
        )
        return [
            AuditLog.action == LOGIN_FAILED,
            AuditLog.entity_type == USER_ENTITY,
            AuditLog.entity_id == username,
            AuditLog.occurred_at >= since,
            or_(latest_success.is_(None), AuditLog.occurred_at > latest_success),
        ]

    def count_recent_login_failures(self, username: str, since: datetime) -> int:
        """LOGIN_FAILED rows for ``username`` (lower case) since ``since`` and newer than the
        latest LOGIN_SUCCESS for that username. The same rule applies to unknown usernames."""
        stmt = (
            select(func.count())
            .select_from(AuditLog)
            .where(*self._recent_failures(username, since))
        )
        return int(self.session.execute(stmt).scalar_one())

    def oldest_recent_login_failure(self, username: str, since: datetime) -> datetime | None:
        """Time of the oldest counted failure (when it ages out, the lock can end)."""
        stmt = select(func.min(AuditLog.occurred_at)).where(*self._recent_failures(username, since))
        return self.session.execute(stmt).scalar_one()

    def search(
        self,
        offset: int,
        limit: int,
        action: str | None = None,
        entity_type: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> tuple[Sequence[RowMapping], int]:
        """One page of audit rows (newest first) with the joined username, and the total count."""
        conditions: list[ColumnElement[bool]] = []
        if action is not None:
            conditions.append(AuditLog.action == action)
        if entity_type is not None:
            conditions.append(AuditLog.entity_type == entity_type)
        if occurred_from is not None:
            conditions.append(AuditLog.occurred_at >= occurred_from)
        if occurred_to is not None:
            conditions.append(AuditLog.occurred_at <= occurred_to)
        total = int(
            self.session.execute(
                select(func.count()).select_from(AuditLog).where(*conditions)
            ).scalar_one()
        )
        stmt = (
            select(
                AuditLog.id,
                AuditLog.occurred_at,
                AuditLog.user_id,
                User.username,
                AuditLog.action,
                AuditLog.entity_type,
                AuditLog.entity_id,
                AuditLog.details,
                AuditLog.request_id,
                AuditLog.ip_address,
            )
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(*conditions)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.session.execute(stmt).mappings().all(), total
