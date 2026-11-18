"""Replenishment recommendations and approval decisions."""

from app.models.replenishment import ApprovalDecision, ReplenishmentRecommendation
from app.repositories.base import Repository


class ReplenishmentRepository(Repository[ReplenishmentRecommendation]):
    model = ReplenishmentRecommendation


class ApprovalDecisionRepository(Repository[ApprovalDecision]):
    """Insert-only (BP §10.8): inherits get/list/add and defines no update or delete."""

    model = ApprovalDecision
