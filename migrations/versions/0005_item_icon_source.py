"""record locally cached item icon sources

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-21 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record the source URL only after an icon is cached successfully."""
    op.add_column(
        "items",
        sa.Column("icon_source_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """Remove cached icon source metadata."""
    op.drop_column("items", "icon_source_url")
