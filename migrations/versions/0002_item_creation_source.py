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
    with op.batch_alter_table("items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_source",
                sa.String(length=16),
                server_default="imported",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_items_created_source",
            "created_source IN ('imported', 'manual')",
        )


def downgrade() -> None:
    """Remove item creation provenance."""
    with op.batch_alter_table("items") as batch_op:
        batch_op.drop_constraint("ck_items_created_source", type_="check")
        batch_op.drop_column("created_source")
