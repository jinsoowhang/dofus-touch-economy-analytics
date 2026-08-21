from datetime import UTC, datetime
from uuid import uuid4

import pytest

from dofus_touch_economy.schemas import PriceObservationCreate, SaleListingCreate
from dofus_touch_economy.services.pricing import PriceService
from dofus_touch_economy.services.sales import (
    SaleItemNotFound,
    SaleListingConflict,
    SaleListingNotFound,
    SalesService,
)


def test_manual_sale_moves_from_active_to_sold(session, catalog_item) -> None:
    service = SalesService(session)
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, lot_quantity=10))

    assert listing.display_name == catalog_item.display_name
    assert listing.lot_quantity == 10
    assert listing.total_price is None
    assert listing.selling_started_at.tzinfo == UTC
    assert listing.date_sold is None
    assert [sale.uuid for sale in service.active()] == [listing.uuid]

    sold = service.mark_sold(listing.uuid)

    assert sold.date_sold is not None
    assert sold.date_sold.tzinfo == UTC
    assert service.active() == []
    assert [sale.uuid for sale in service.sold()] == [listing.uuid]


def test_price_record_automatically_starts_a_sale(session, catalog_item) -> None:
    observation = PriceService(session, "Dodge").record(
        catalog_item.uuid,
        PriceObservationCreate(
            lot_quantity=1,
            total_price=125_000,
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        ),
    )

    sales = SalesService(session).active()

    assert len(sales) == 1
    assert sales[0].item_uuid == catalog_item.uuid
    assert sales[0].total_price == observation.total_price
    assert sales[0].lot_quantity == 1


def test_sales_reject_unknown_items_and_invalid_transitions(session) -> None:
    service = SalesService(session)

    with pytest.raises(SaleItemNotFound):
        service.start(SaleListingCreate(item_uuid=uuid4(), lot_quantity=1))
    with pytest.raises(SaleListingNotFound):
        service.mark_sold(uuid4())


def test_sale_cannot_be_marked_sold_twice(session, catalog_item) -> None:
    service = SalesService(session)
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, lot_quantity=1))
    service.mark_sold(listing.uuid)

    with pytest.raises(SaleListingConflict):
        service.mark_sold(listing.uuid)
