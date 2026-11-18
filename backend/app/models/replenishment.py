"""Replenishment recommendations and the insert-only approval decisions."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_now, pk_id
from app.models.enums import Decision, RecommendationStatus, check_in


class ReplenishmentRecommendation(Base):
    __tablename__ = "replenishment_recommendations"
    __table_args__ = (
        CheckConstraint("proposed_qty > 0", name="proposed_qty_positive"),
        CheckConstraint("final_qty IS NULL OR final_qty > 0", name="final_qty_positive"),
        CheckConstraint(check_in("status", RecommendationStatus), name="status_values"),
    )

    id: Mapped[int] = pk_id()
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("metric_snapshots.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    proposed_qty: Mapped[int]
    final_qty: Mapped[int | None]
    est_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(
        String(32), server_default=RecommendationStatus.PENDING.value, index=True
    )
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_interactions.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = created_now()


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        CheckConstraint(check_in("decision", Decision), name="decision_values"),
        CheckConstraint(
            "decision NOT IN ('ADJUST', 'REJECT') OR (reason IS NOT NULL AND length(reason) >= 5)",
            name="reason_required",
        ),
        CheckConstraint("decision <> 'ADJUST' OR new_qty IS NOT NULL", name="new_qty_required"),
    )

    id: Mapped[int] = pk_id()
    recommendation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("replenishment_recommendations.id", ondelete="RESTRICT"), index=True
    )
    decided_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32))
    previous_qty: Mapped[int]
    new_qty: Mapped[int | None]
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = created_now()
