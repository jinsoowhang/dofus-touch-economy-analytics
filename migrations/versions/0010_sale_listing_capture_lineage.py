"""add provider-neutral capture lineage to sale listings

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable generic current listing and sale lineage."""
    op.add_column(
        "sale_listings",
        sa.Column("listing_source", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "sale_listings",
        sa.Column("listing_capture_uuid", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "sale_listings",
        sa.Column("sale_source", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "sale_listings",
        sa.Column("sale_capture_uuid", sa.Uuid(), nullable=True),
    )
    op.execute(sa.text("UPDATE sale_listings SET listing_source = 'manual'"))
    op.execute(
        sa.text("UPDATE sale_listings SET sale_source = 'manual' WHERE date_sold IS NOT NULL")
    )


def downgrade() -> None:
    """Remove current capture lineage from normalized sale listings."""
    op.drop_column("sale_listings", "sale_capture_uuid")
    op.drop_column("sale_listings", "sale_source")
    op.drop_column("sale_listings", "listing_capture_uuid")
    op.drop_column("sale_listings", "listing_source")
