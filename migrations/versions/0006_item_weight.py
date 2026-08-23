"""record Dofus Touch item weight

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-22 20:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store the nonnegative carrying weight supplied by the live Touch catalog."""
    op.add_column(
        "items",
        sa.Column(
            "weight",
            sa.Integer(),
            sa.CheckConstraint(
                "weight IS NULL OR weight >= 0",
                name="ck_items_nonnegative_weight",
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove live catalog item weight."""
    op.drop_column("items", "weight")
