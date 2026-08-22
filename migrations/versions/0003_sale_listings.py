"""track active and completed sale listings

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create sale listings and seed manual price records made today."""
    op.create_table(
        "sale_listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("price_observation_id", sa.Integer(), nullable=True),
        sa.Column("lot_quantity", sa.Integer(), nullable=False),
        sa.Column("selling_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_sold", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "lot_quantity > 0",
            name="ck_sale_listings_positive_lot_quantity",
        ),
        sa.CheckConstraint(
            "date_sold IS NULL OR date_sold >= selling_started_at",
            name="ck_sale_listings_valid_sale_date",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["price_observation_id"],
            ["price_observations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "price_observation_id",
            name="uq_sale_listings_price_observation_id",
        ),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_sale_listings_date_sold", "sale_listings", ["date_sold"])
    op.create_index("ix_sale_listings_item_id", "sale_listings", ["item_id"])
    op.execute(
        sa.text(
            "INSERT INTO sale_listings "
            "(uuid, item_id, price_observation_id, lot_quantity, selling_started_at) "
            "SELECT lower(hex(randomblob(16))), item_id, id, lot_quantity, recorded_at "
            "FROM price_observations "
            "WHERE source = 'manual' AND date(recorded_at) = date('now')"
        )
    )


def downgrade() -> None:
    """Remove sale listing tracking."""
    op.drop_index("ix_sale_listings_item_id", table_name="sale_listings")
    op.drop_index("ix_sale_listings_date_sold", table_name="sale_listings")
    op.drop_table("sale_listings")
