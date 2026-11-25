"""Admin governance response schemas (audit log, AI interaction metadata)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: int
    occurred_at: datetime
    user_id: int | None
    username: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict[str, Any]
    request_id: str | None
    ip_address: str | None


class AiInteractionItem(BaseModel):
    """Metadata only: no prompt, raw output or user input (BP 10.8)."""

    id: uuid.UUID
    created_at: datetime
    user_id: int | None
    feature: str
    model_id: str
    prompt_template_id: str
    prompt_template_version: str
    validation_status: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    feedback: int | None
