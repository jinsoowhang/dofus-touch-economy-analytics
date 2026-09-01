from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dofus_touch_economy.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("dataset", "checksum", name="uq_import_batches_dataset_checksum"),
        CheckConstraint(
            "accepted_count >= 0 AND rejected_count >= 0 AND warning_count >= 0",
            name="ck_import_batches_nonnegative_counts",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(Uuid, default=uuid4, unique=True, nullable=False)
    dataset: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source_records: Mapped[list[SourceRecord]] = relationship(
        back_populates="import_batch", cascade="all, delete-orphan"
    )


class SourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "row_number", name="uq_source_records_batch_row"),
        CheckConstraint("row_number > 0", name="ck_source_records_positive_row_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    validation_messages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    import_batch: Mapped[ImportBatch] = relationship(back_populates="source_records")
    source_item_names: Mapped[list[SourceItemName]] = relationship(
        back_populates="source_record", cascade="all, delete-orphan"
    )
    recipe: Mapped[Recipe | None] = relationship(back_populates="source_record")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint(
            "normalized_name", "identity_category", name="uq_items_normalized_identity"
        ),
        CheckConstraint(
            "created_source IN ('imported', 'manual')",
            name="ck_items_created_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(Uuid, default=uuid4, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String)
    identity_category: Mapped[str] = mapped_column(String, nullable=False)
    created_source: Mapped[str] = mapped_column(String(16), default="imported", nullable=False)
    icon_source_url: Mapped[str | None] = mapped_column(String(500))
    weight: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("weight IS NULL OR weight >= 0", name="ck_items_nonnegative_weight"),
    )
    touch_catalog_status: Mapped[str | None] = mapped_column(
        String(16),
        CheckConstraint(
            "touch_catalog_status IS NULL OR touch_catalog_status IN ('verified', 'excluded')",
            name="ck_items_touch_catalog_status",
        ),
    )
    touch_catalog_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    touch_catalog_exclusion_reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    recipes: Mapped[list[Recipe]] = relationship(back_populates="crafted_item")
    price_observations: Mapped[list[PriceObservation]] = relationship(back_populates="item")
    sale_listings: Mapped[list[SaleListing]] = relationship(back_populates="item")


class SourceItemName(Base):
    __tablename__ = "source_item_names"
    __table_args__ = (
        UniqueConstraint(
            "source_record_id",
            "source_field",
            "position",
            name="uq_source_item_names_record_field_position",
        ),
        CheckConstraint("position >= 0 AND position <= 8", name="ck_source_item_names_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id", ondelete="CASCADE"), nullable=False
    )
    source_field: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    resolution_status: Mapped[str] = mapped_column(String, nullable=False)

    source_record: Mapped[SourceRecord] = relationship(back_populates="source_item_names")
    item: Mapped[Item | None] = relationship()


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(Uuid, default=uuid4, unique=True, nullable=False)
    crafted_item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    profession: Mapped[str] = mapped_column(String, nullable=False)
    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    crafted_item: Mapped[Item] = relationship(back_populates="recipes")
    source_record: Mapped[SourceRecord] = relationship(back_populates="recipe")
    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.position",
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_ingredients_recipe_position"),
        CheckConstraint("position > 0 AND position <= 8", name="ck_recipe_ingredients_position"),
        CheckConstraint("quantity > 0", name="ck_recipe_ingredients_positive_quantity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    item: Mapped[Item | None] = relationship()


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        CheckConstraint("lot_quantity > 0", name="ck_price_observations_positive_lot_quantity"),
        CheckConstraint("total_price > 0", name="ck_price_observations_positive_total_price"),
        CheckConstraint(
            "(invalidated_at IS NULL AND invalidation_reason IS NULL) OR "
            "(invalidated_at IS NOT NULL AND invalidation_reason IS NOT NULL)",
            name="ck_price_observations_invalidation_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(Uuid, default=uuid4, unique=True, nullable=False)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    lot_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    market_context: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidation_reason: Mapped[str | None] = mapped_column(Text)

    item: Mapped[Item] = relationship(back_populates="price_observations")
    sale_listing: Mapped[SaleListing | None] = relationship(
        back_populates="price_observation",
        uselist=False,
    )


class SaleListing(Base):
    __tablename__ = "sale_listings"
    __table_args__ = (
        UniqueConstraint(
            "price_observation_id",
            name="uq_sale_listings_price_observation_id",
        ),
        CheckConstraint(
            "lot_quantity > 0",
            name="ck_sale_listings_positive_lot_quantity",
        ),
        CheckConstraint(
            "asking_price IS NULL OR asking_price > 0",
            name="ck_sale_listings_positive_asking_price",
        ),
        CheckConstraint(
            "date_sold IS NULL OR date_sold >= selling_started_at",
            name="ck_sale_listings_valid_sale_date",
        ),
        CheckConstraint(
            "recipe_cost_at_sale IS NULL OR recipe_cost_at_sale >= 0",
            name="ck_sale_listings_nonnegative_recipe_cost_at_sale",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(Uuid, default=uuid4, unique=True, nullable=False)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    price_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("price_observations.id", ondelete="RESTRICT")
    )
    lot_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    asking_price: Mapped[int | None] = mapped_column(Integer)
    selling_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    date_sold: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    recipe_cost_at_sale: Mapped[Decimal | None] = mapped_column(Numeric(38, 9))
    listing_source: Mapped[str | None] = mapped_column(String(40), default="manual")
    listing_capture_uuid: Mapped[UUID | None] = mapped_column(Uuid)
    sale_source: Mapped[str | None] = mapped_column(String(40))
    sale_capture_uuid: Mapped[UUID | None] = mapped_column(Uuid)

    item: Mapped[Item] = relationship(back_populates="sale_listings")
    price_observation: Mapped[PriceObservation | None] = relationship(back_populates="sale_listing")
    capture_actions: Mapped[list[SaleCaptureListingAction]] = relationship(
        back_populates="sale_listing",
        order_by="SaleCaptureListingAction.effective_at, SaleCaptureListingAction.id",
    )


class SaleCaptureBatch(Base):
    __tablename__ = "sale_capture_batches"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "workspace_id",
            "channel_id",
            "parent_message_ts",
            name="uq_sale_capture_batches_message",
        ),
        CheckConstraint("provider IN ('slack')", name="ck_sale_capture_batches_provider"),
        CheckConstraint(
            "requested_action IS NULL OR requested_action IN ('sold', 'market')",
            name="ck_sale_capture_batches_action",
        ),
        CheckConstraint(
            "status IN ('received', 'awaiting_action', 'queued', 'extracting', "
            "'awaiting_confirmation', 'needs_review', 'committing', 'committed', "
            "'rejected', 'retry_wait', 'failed')",
            name="ck_sale_capture_batches_status",
        ),
        CheckConstraint(
            "receipt_status IN ('none', 'pending', 'sent', 'retry_wait', 'failed')",
            name="ck_sale_capture_batches_receipt_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_sale_capture_batches_attempt_count"),
        CheckConstraint(
            "(decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_sale_capture_batches_decision_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(Uuid, default=uuid4, unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="slack", nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_message_ts: Mapped[str] = mapped_column(String(40), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(100))
    requester_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    requested_action: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40), default="received", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    schema_version: Mapped[str | None] = mapped_column(String(100))
    primary_response_id: Mapped[str | None] = mapped_column(String(100))
    verification_prompt_version: Mapped[str | None] = mapped_column(String(100))
    verification_response_id: Mapped[str | None] = mapped_column(String(100))
    extraction_json: Mapped[str | None] = mapped_column(Text)
    verification_json: Mapped[str | None] = mapped_column(Text)
    validation_json: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[str | None] = mapped_column(String(100))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    preview_message_ts: Mapped[str | None] = mapped_column(String(40))
    receipt_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    receipt_message_ts: Mapped[str | None] = mapped_column(String(40))

    files: Mapped[list[SaleCaptureFile]] = relationship(
        back_populates="capture_batch",
        cascade="all, delete-orphan",
        order_by="SaleCaptureFile.attachment_order",
    )
    listing_actions: Mapped[list[SaleCaptureListingAction]] = relationship(
        back_populates="capture_batch",
        cascade="all, delete-orphan",
        order_by="SaleCaptureListingAction.id",
    )


class SaleCaptureFile(Base):
    __tablename__ = "sale_capture_files"
    __table_args__ = (
        UniqueConstraint(
            "capture_batch_id",
            "attachment_order",
            name="uq_sale_capture_files_batch_order",
        ),
        UniqueConstraint(
            "capture_batch_id",
            "provider_file_id",
            name="uq_sale_capture_files_batch_provider_file",
        ),
        CheckConstraint(
            "attachment_order > 0",
            name="ck_sale_capture_files_positive_order",
        ),
        CheckConstraint("byte_size > 0", name="ck_sale_capture_files_positive_size"),
        CheckConstraint(
            "sha256 IS NULL OR length(sha256) = 64",
            name="ck_sale_capture_files_sha256",
        ),
        CheckConstraint(
            "status IN ('pending', 'downloaded', 'invalid', 'purged')",
            name="ck_sale_capture_files_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capture_batch_id: Mapped[int] = mapped_column(
        ForeignKey("sale_capture_batches.id", ondelete="CASCADE"), nullable=False
    )
    attachment_order: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_file_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    local_relative_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    capture_batch: Mapped[SaleCaptureBatch] = relationship(back_populates="files")


class SaleCaptureListingAction(Base):
    __tablename__ = "sale_capture_listing_actions"
    __table_args__ = (
        UniqueConstraint(
            "capture_batch_id",
            "sale_listing_id",
            "action",
            name="uq_sale_capture_listing_actions_batch_listing_action",
        ),
        CheckConstraint(
            "action IN ('created', 'marked_sold')",
            name="ck_sale_capture_listing_actions_action",
        ),
        CheckConstraint(
            "asking_price > 0",
            name="ck_sale_capture_listing_actions_positive_price",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capture_batch_id: Mapped[int] = mapped_column(
        ForeignKey("sale_capture_batches.id", ondelete="CASCADE"), nullable=False
    )
    sale_listing_id: Mapped[int] = mapped_column(
        ForeignKey("sale_listings.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    asking_price: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    capture_batch: Mapped[SaleCaptureBatch] = relationship(back_populates="listing_actions")
    sale_listing: Mapped[SaleListing] = relationship(back_populates="capture_actions")
