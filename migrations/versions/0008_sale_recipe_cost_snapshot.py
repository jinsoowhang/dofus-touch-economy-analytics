"""snapshot recipe cost when a listing is sold

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-24 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a nullable immutable cost basis for completed sale listings."""
    op.add_column(
        "sale_listings",
        sa.Column(
            "recipe_cost_at_sale",
            sa.Numeric(precision=38, scale=9),
            sa.CheckConstraint(
                "recipe_cost_at_sale IS NULL OR recipe_cost_at_sale >= 0",
                name="ck_sale_listings_nonnegative_recipe_cost_at_sale",
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the completed-sale recipe cost snapshot."""
    op.drop_column("sale_listings", "recipe_cost_at_sale")
