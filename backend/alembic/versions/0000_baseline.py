"""baseline

Baseline revision; pgvector deferred to P7 per ADR-014.

Revision ID: 0000
Revises:
Create Date: 2026-11-17
"""

from collections.abc import Sequence

revision: str = "0000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
