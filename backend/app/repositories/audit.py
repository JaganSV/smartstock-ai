"""Audit log repository."""

from app.models.governance import AuditLog
from app.repositories.base import Repository


class AuditRepository(Repository[AuditLog]):
    """Insert-only (BP §10.8): inherits get/list/add and defines no update or delete."""

    model = AuditLog
