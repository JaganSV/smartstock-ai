"""Admin governance reads: audit log and AI interaction metadata (BP 6.2 #33, 10.8)."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.ai_interactions import AiInteractionRepository
from app.repositories.audit import AuditRepository
from app.schemas.admin import AiInteractionItem, AuditLogItem
from app.schemas.common import Page, PageParams


def list_audit_log(
    session: Session,
    paging: PageParams,
    action: str | None = None,
    entity_type: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> Page[AuditLogItem]:
    rows, total = AuditRepository(session).search(
        paging.offset,
        paging.page_size,
        action=action,
        entity_type=entity_type,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    return Page[AuditLogItem](
        items=[AuditLogItem.model_validate(dict(row)) for row in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


def list_ai_interactions(
    session: Session,
    paging: PageParams,
    feature: str | None = None,
    validation_status: str | None = None,
) -> Page[AiInteractionItem]:
    """Metadata only: ``AiInteractionItem`` has no prompt, output or user-input field."""
    rows, total = AiInteractionRepository(session).search(
        paging.offset, paging.page_size, feature=feature, validation_status=validation_status
    )
    return Page[AiInteractionItem](
        items=[AiInteractionItem.model_validate(row, from_attributes=True) for row in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )
