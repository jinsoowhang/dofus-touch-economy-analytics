from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from dofus_touch_economy.models import PriceObservation, SaleListing
from dofus_touch_economy.schemas import SaleListingCreate
from dofus_touch_economy.services.sales import SaleListingConflict, SalesService

CAPTURE_UUID = UUID("00000000-0000-0000-0000-000000000123")
OBSERVED_AT = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)


def test_capture_listing_creation_flushes_exact_lineage_without_committing(
    session,
    session_factory,
    catalog_item,
) -> None:
    listings = SalesService(session, "Dodge").create_listings_at(
        [SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=42_000)],
        selling_started_at=OBSERVED_AT,
        source="slack_market_capture",
        capture_uuid=CAPTURE_UUID,
    )

    assert len(listings) == 1
    listing = listings[0]
    assert listing.selling_started_at == OBSERVED_AT
    assert listing.listing_source == "slack_market_capture"
    assert listing.listing_capture_uuid == CAPTURE_UUID
    assert listing.price_observation is not None
    assert listing.price_observation.observed_at == OBSERVED_AT
    assert listing.price_observation.source == "slack_market_capture"
    with session_factory() as independent_session:
        assert independent_session.scalar(select(func.count(SaleListing.id))) == 0


def test_capture_mark_sold_flushes_exact_time_and_lineage_without_committing(
    session,
    session_factory,
    catalog_item,
) -> None:
    listing = SalesService(session, "Dodge").create_listings_at(
        [SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=42_000)],
        selling_started_at=OBSERVED_AT,
        source="slack_market_capture",
        capture_uuid=CAPTURE_UUID,
    )[0]
    session.commit()
    sold_at = OBSERVED_AT + timedelta(hours=2)

    updated = SalesService(session, "Dodge").mark_listings_sold_at(
        [listing.uuid],
        sold_at=sold_at,
        source="slack_sold_capture",
        capture_uuid=CAPTURE_UUID,
    )

    assert updated[0].date_sold == sold_at
    assert updated[0].sale_source == "slack_sold_capture"
    assert updated[0].sale_capture_uuid == CAPTURE_UUID
    with session_factory() as independent_session:
        persisted = independent_session.scalar(
            select(SaleListing).where(SaleListing.uuid == listing.uuid)
        )
        assert persisted is not None
        assert persisted.date_sold is None


def test_capture_mark_sold_rejects_time_before_listing_start(session, catalog_item) -> None:
    listing = SalesService(session, "Dodge").create_listings_at(
        [SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=42_000)],
        selling_started_at=OBSERVED_AT,
        source="slack_market_capture",
        capture_uuid=CAPTURE_UUID,
    )[0]
    session.commit()

    with pytest.raises(SaleListingConflict, match="before"):
        SalesService(session, "Dodge").mark_listings_sold_at(
            [listing.uuid],
            sold_at=OBSERVED_AT - timedelta(seconds=1),
            source="slack_sold_capture",
            capture_uuid=CAPTURE_UUID,
        )

    session.refresh(listing)
    assert listing.date_sold is None


def test_manual_sales_set_manual_current_lineage_and_reopen_clears_sale_lineage(
    session,
    catalog_item,
) -> None:
    service = SalesService(session, "Dodge")
    response = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=42_000))
    listing = session.scalar(select(SaleListing).where(SaleListing.uuid == response.uuid))
    assert listing is not None
    assert listing.listing_source == "manual"
    observation = session.get(PriceObservation, listing.price_observation_id)
    assert observation is not None
    assert observation.source == "manual"

    service.mark_sold(response.uuid)
    session.refresh(listing)
    assert listing.sale_source == "manual"
    assert listing.sale_capture_uuid is None

    service.reopen(response.uuid)
    session.refresh(listing)
    assert listing.date_sold is None
    assert listing.recipe_cost_at_sale is None
    assert listing.sale_source is None
    assert listing.sale_capture_uuid is None
