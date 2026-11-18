"""AI interaction log repository."""

import uuid

from app.models.governance import AiInteraction
from app.repositories.base import Repository


class AiInteractionRepository(Repository[AiInteraction]):
    """Insert-only (BP §10.8) except ``set_feedback``, the single permitted update."""

    model = AiInteraction

    def set_feedback(self, id: uuid.UUID, value: int) -> bool:
        """Set the user feedback (-1 or 1; enforced by a CHECK). True if the row exists."""
        interaction = self.get(id)
        if interaction is None:
            return False
        interaction.feedback = value
        self.session.flush()
        return True
