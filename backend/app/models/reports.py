"""Executive reports."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_now, pk_id
from app.models.enums import ReportScope, check_in


class ExecutiveReport(Base):
    __tablename__ = "executive_reports"
    __table_args__ = (
        CheckConstraint(check_in("scope_type", ReportScope), name="scope_type_values"),
        CheckConstraint("(scope_type = 'ALL') = (scope_id IS NULL)", name="scope_id_rule"),
    )

    id: Mapped[int] = pk_id()
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("metric_snapshots.id", ondelete="RESTRICT"), index=True
    )
    scope_type: Mapped[str] = mapped_column(String(32))
    scope_id: Mapped[int | None] = mapped_column(BigInteger)
    verified_metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    narrative_md: Mapped[str] = mapped_column(Text)
    ai_interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_interactions.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = created_now()
