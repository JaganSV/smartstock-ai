"""Governance: users, AI interaction log and the insert-only audit log."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR

from app.models.base import Base, created_now, pk_id
from app.models.enums import AiFeature, UserRole, ValidationStatus, check_in


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(check_in("role", UserRole), name="role_values"),)

    id: Mapped[int] = pk_id()
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    created_at: Mapped[datetime] = created_now()


class AiInteraction(Base):
    __tablename__ = "ai_interactions"
    __table_args__ = (
        CheckConstraint(check_in("feature", AiFeature), name="feature_values"),
        CheckConstraint(
            check_in("validation_status", ValidationStatus), name="validation_status_values"
        ),
        CheckConstraint("feedback IN (-1, 1)", name="feedback_values"),
        Index("ix_ai_interactions_feature_created_at", "feature", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    feature: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[str] = mapped_column(String(100))
    prompt_template_id: Mapped[str] = mapped_column(String(64))
    prompt_template_version: Mapped[str] = mapped_column(String(16))
    input_hash: Mapped[str] = mapped_column(CHAR(64))
    sanitized_user_input: Mapped[str | None] = mapped_column(Text)
    context_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    raw_output: Mapped[str | None] = mapped_column(Text)
    parsed_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(String(32))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    latency_ms: Mapped[int | None]
    feedback: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = created_now()


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_occurred_at", "occurred_at"),
        Index("ix_audit_log_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id: Mapped[int] = pk_id()
    occurred_at: Mapped[datetime] = created_now()
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(45))
