"""Admin governance endpoints (ADMIN only, capability ``view_governance``)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_capability
from app.models.enums import AiFeature, ValidationStatus
from app.schemas.admin import AiInteractionItem, AuditLogItem
from app.schemas.common import Page, PageParams, page_params
from app.services import governance_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_capability("view_governance"))],
)

Paging = Annotated[PageParams, Depends(page_params)]


@router.get("/audit-log", response_model=Page[AuditLogItem])
def audit_log(
    db: DbSession,
    paging: Paging,
    action: Annotated[str | None, Query(max_length=64)] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    occurred_from: Annotated[datetime | None, Query(alias="from")] = None,
    occurred_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> Page[AuditLogItem]:
    return governance_service.list_audit_log(
        db, paging, action, entity_type, occurred_from, occurred_to
    )


@router.get("/ai-interactions", response_model=Page[AiInteractionItem])
def ai_interactions(
    db: DbSession,
    paging: Paging,
    feature: AiFeature | None = None,
    validation_status: ValidationStatus | None = None,
) -> Page[AiInteractionItem]:
    return governance_service.list_ai_interactions(
        db,
        paging,
        feature.value if feature else None,
        validation_status.value if validation_status else None,
    )
