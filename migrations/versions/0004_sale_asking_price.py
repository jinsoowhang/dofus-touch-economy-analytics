"""add editable sale asking prices

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-21 17:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store a sale-specific price and seed it from linked observations."""
    op.add_column(
        "sale_listings",
        sa.Column(
            "asking_price",
            sa.Integer(),
            sa.CheckConstraint(
                "asking_price IS NULL OR asking_price > 0",
                name="ck_sale_listings_positive_asking_price",
            ),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE sale_listings SET asking_price = ("
            "SELECT total_price FROM price_observations "
            "WHERE price_observations.id = sale_listings.price_observation_id"
            ") WHERE price_observation_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    """Remove sale-specific prices."""
    op.drop_column("sale_listings", "asking_price")
