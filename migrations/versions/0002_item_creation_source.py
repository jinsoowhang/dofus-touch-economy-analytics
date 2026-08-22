"""record item creation source

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add creation provenance to existing and future catalog items."""
    op.add_column(
        "items",
        sa.Column(
            "created_source",
            sa.String(length=16),
            sa.CheckConstraint(
                "created_source IN ('imported', 'manual')",
                name="ck_items_created_source",
            ),
            server_default="imported",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove item creation provenance."""
    op.drop_column("items", "created_source")
