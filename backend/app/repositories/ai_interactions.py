"""AI interaction log repository."""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, select

from app.models.governance import AiInteraction
from app.repositories.base import Repository


class AiInteractionRepository(Repository[AiInteraction]):
    """Insert-only (BP 10.8) except ``set_feedback``, the single permitted update."""

    model = AiInteraction

    def set_feedback(self, id: uuid.UUID, value: int) -> bool:
        """Set the user feedback (-1 or 1; enforced by a CHECK). True if the row exists."""
        interaction = self.get(id)
        if interaction is None:
            return False
        interaction.feedback = value
        self.session.flush()
        return True

    def search(
        self,
        offset: int,
        limit: int,
        feature: str | None = None,
        validation_status: str | None = None,
    ) -> tuple[Sequence[AiInteraction], int]:
        """One page (newest first) and the total count. Callers expose metadata columns only."""
        conditions: list[ColumnElement[bool]] = []
        if feature is not None:
            conditions.append(AiInteraction.feature == feature)
        if validation_status is not None:
            conditions.append(AiInteraction.validation_status == validation_status)
        total = int(
            self.session.execute(
                select(func.count()).select_from(AiInteraction).where(*conditions)
            ).scalar_one()
        )
        stmt = (
            select(AiInteraction)
            .where(*conditions)
            .order_by(AiInteraction.created_at.desc(), AiInteraction.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.session.scalars(stmt).all(), total
