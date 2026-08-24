"""record authoritative Dofus Touch catalog status

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-23 21:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VIOLET_ARROW_REASON = "Normalized item name absent from Ankama's live Dofus Touch item catalog."


def upgrade() -> None:
    """Store the latest authoritative Touch membership check without deleting provenance."""
    op.add_column(
        "items",
        sa.Column(
            "touch_catalog_status",
            sa.String(length=16),
            sa.CheckConstraint(
                "touch_catalog_status IS NULL OR touch_catalog_status IN ('verified', 'excluded')",
                name="ck_items_touch_catalog_status",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "items",
        sa.Column("touch_catalog_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("touch_catalog_exclusion_reason", sa.String(length=300), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE items SET touch_catalog_status = 'excluded', "
            "touch_catalog_checked_at = CURRENT_TIMESTAMP, "
            "touch_catalog_exclusion_reason = :reason "
            "WHERE normalized_name = 'violet arrow helmet'"
        ).bindparams(reason=VIOLET_ARROW_REASON)
    )


def downgrade() -> None:
    """Remove authoritative Touch membership metadata."""
    op.drop_column("items", "touch_catalog_exclusion_reason")
    op.drop_column("items", "touch_catalog_checked_at")
    op.drop_column("items", "touch_catalog_status")
