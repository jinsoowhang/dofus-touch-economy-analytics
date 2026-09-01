"""add local sale screenshot capture audit tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-29 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create private capture intake, file, and listing-action history."""
    op.create_table(
        "sale_capture_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("channel_id", sa.String(length=100), nullable=False),
        sa.Column("parent_message_ts", sa.String(length=40), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=True),
        sa.Column("requester_user_id", sa.String(length=100), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("requested_action", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("schema_version", sa.String(length=100), nullable=True),
        sa.Column("primary_response_id", sa.String(length=100), nullable=True),
        sa.Column("verification_prompt_version", sa.String(length=100), nullable=True),
        sa.Column("verification_response_id", sa.String(length=100), nullable=True),
        sa.Column("extraction_json", sa.Text(), nullable=True),
        sa.Column("verification_json", sa.Text(), nullable=True),
        sa.Column("validation_json", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", sa.String(length=100), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("preview_message_ts", sa.String(length=40), nullable=True),
        sa.Column("receipt_status", sa.String(length=20), nullable=False),
        sa.Column("receipt_message_ts", sa.String(length=40), nullable=True),
        sa.CheckConstraint("provider IN ('slack')", name="ck_sale_capture_batches_provider"),
        sa.CheckConstraint(
            "requested_action IS NULL OR requested_action IN ('sold', 'market')",
            name="ck_sale_capture_batches_action",
        ),
        sa.CheckConstraint(
            "status IN ('received', 'awaiting_action', 'queued', 'extracting', "
            "'awaiting_confirmation', 'needs_review', 'committing', 'committed', "
            "'rejected', 'retry_wait', 'failed')",
            name="ck_sale_capture_batches_status",
        ),
        sa.CheckConstraint(
            "receipt_status IN ('none', 'pending', 'sent', 'retry_wait', 'failed')",
            name="ck_sale_capture_batches_receipt_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_sale_capture_batches_attempt_count",
        ),
        sa.CheckConstraint(
            "(decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_sale_capture_batches_decision_pair",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "workspace_id",
            "channel_id",
            "parent_message_ts",
            name="uq_sale_capture_batches_message",
        ),
        sa.UniqueConstraint("uuid"),
    )
    op.create_table(
        "sale_capture_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capture_batch_id", sa.Integer(), nullable=False),
        sa.Column("attachment_order", sa.Integer(), nullable=False),
        sa.Column("provider_file_id", sa.String(length=100), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("local_relative_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attachment_order > 0",
            name="ck_sale_capture_files_positive_order",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_sale_capture_files_positive_size"),
        sa.CheckConstraint(
            "sha256 IS NULL OR length(sha256) = 64",
            name="ck_sale_capture_files_sha256",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'downloaded', 'invalid', 'purged')",
            name="ck_sale_capture_files_status",
        ),
        sa.ForeignKeyConstraint(
            ["capture_batch_id"],
            ["sale_capture_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "capture_batch_id",
            "attachment_order",
            name="uq_sale_capture_files_batch_order",
        ),
        sa.UniqueConstraint(
            "capture_batch_id",
            "provider_file_id",
            name="uq_sale_capture_files_batch_provider_file",
        ),
    )
    op.create_index(
        "ix_sale_capture_files_sha256",
        "sale_capture_files",
        ["sha256"],
    )
    op.create_table(
        "sale_capture_listing_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capture_batch_id", sa.Integer(), nullable=False),
        sa.Column("sale_listing_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asking_price", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('created', 'marked_sold')",
            name="ck_sale_capture_listing_actions_action",
        ),
        sa.CheckConstraint(
            "asking_price > 0",
            name="ck_sale_capture_listing_actions_positive_price",
        ),
        sa.ForeignKeyConstraint(
            ["capture_batch_id"],
            ["sale_capture_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sale_listing_id"],
            ["sale_listings.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "capture_batch_id",
            "sale_listing_id",
            "action",
            name="uq_sale_capture_listing_actions_batch_listing_action",
        ),
    )


def downgrade() -> None:
    """Remove private screenshot capture audit tables."""
    op.drop_table("sale_capture_listing_actions")
    op.drop_index("ix_sale_capture_files_sha256", table_name="sale_capture_files")
    op.drop_table("sale_capture_files")
    op.drop_table("sale_capture_batches")
