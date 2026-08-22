from datetime import UTC, datetime
from uuid import uuid4

import pytest

from dofus_touch_economy.models import Item, SaleListing
from dofus_touch_economy.schemas import (
    PriceObservationCreate,
    SaleListingCreate,
    SalePriceUpdate,
)
from dofus_touch_economy.services.pricing import PriceService
from dofus_touch_economy.services.sales import (
    SaleItemNotFound,
    SaleListingConflict,
    SaleListingNotFound,
    SalesService,
)


def test_manual_sale_moves_from_active_to_sold(session, catalog_item) -> None:
    service = SalesService(session)
    listing = service.start(
        SaleListingCreate(
            item_uuid=catalog_item.uuid,
            asking_price=50_000,
        )
    )

    assert listing.display_name == catalog_item.display_name
    assert listing.asking_price == 50_000
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
    assert sales[0].asking_price == observation.total_price


def test_sales_reject_unknown_items_and_invalid_transitions(session) -> None:
    service = SalesService(session)

    with pytest.raises(SaleItemNotFound):
        service.start(SaleListingCreate(item_uuid=uuid4()))
    with pytest.raises(SaleListingNotFound):
        service.mark_sold(uuid4())


def test_sale_cannot_be_marked_sold_twice(session, catalog_item) -> None:
    service = SalesService(session)
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid))
    service.mark_sold(listing.uuid)

    with pytest.raises(SaleListingConflict):
        service.mark_sold(listing.uuid)


def test_sale_can_be_duplicated_and_repriced_independently(session, catalog_item) -> None:
    service = SalesService(session)
    original = service.start(
        SaleListingCreate(
            item_uuid=catalog_item.uuid,
            asking_price=50_000,
        )
    )

    duplicate = service.duplicate(original.uuid)

    assert duplicate.uuid != original.uuid
    assert duplicate.item_uuid == original.item_uuid
    assert duplicate.asking_price == original.asking_price

    updated = service.update_price(
        duplicate.uuid,
        SalePriceUpdate(asking_price=45_000),
    )
    active_by_uuid = {listing.uuid: listing for listing in service.active()}
    assert updated.asking_price == 45_000
    assert active_by_uuid[original.uuid].asking_price == 50_000
    assert active_by_uuid[duplicate.uuid].asking_price == 45_000


def test_sold_sale_price_cannot_be_changed(session, catalog_item) -> None:
    service = SalesService(session)
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid))
    service.mark_sold(listing.uuid)

    with pytest.raises(SaleListingConflict):
        service.update_price(listing.uuid, SalePriceUpdate(asking_price=1_000))


def test_unknown_sale_cannot_be_duplicated_or_repriced(session) -> None:
    service = SalesService(session)
    listing_uuid = uuid4()

    with pytest.raises(SaleListingNotFound):
        service.duplicate(listing_uuid)
    with pytest.raises(SaleListingNotFound):
        service.update_price(listing_uuid, SalePriceUpdate(asking_price=1_000))
    with pytest.raises(SaleListingNotFound):
        service.delete(listing_uuid)


@pytest.mark.parametrize(
    ("sort_field", "sort_direction", "expected"),
    [
        ("name", "desc", ["Zeta Belt", "Synthetic Ore", "Alpha Hat"]),
        ("category", "asc", ["Zeta Belt", "Alpha Hat", "Synthetic Ore"]),
        ("price", "desc", ["Alpha Hat", "Zeta Belt", "Synthetic Ore"]),
        ("started", "asc", ["Synthetic Ore", "Zeta Belt", "Alpha Hat"]),
    ],
)
def test_active_sales_sort_by_each_displayed_field(
    session,
    catalog_item,
    sort_field,
    sort_direction,
    expected,
) -> None:
    alpha = Item(
        display_name="Alpha Hat",
        normalized_name="alpha hat",
        category="Hat",
        identity_category="hat",
    )
    zeta = Item(
        display_name="Zeta Belt",
        normalized_name="zeta belt",
        category="Belt",
        identity_category="belt",
    )
    session.add_all([alpha, zeta])
    session.flush()
    session.add_all(
        [
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100,
                selling_started_at=datetime(2026, 8, 20, tzinfo=UTC),
            ),
            SaleListing(
                item_id=zeta.id,
                lot_quantity=1,
                asking_price=200,
                selling_started_at=datetime(2026, 8, 21, tzinfo=UTC),
            ),
            SaleListing(
                item_id=alpha.id,
                lot_quantity=1,
                asking_price=300,
                selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    results = SalesService(session).active(sort_field, sort_direction)

    assert [result.display_name for result in results] == expected


@pytest.mark.parametrize(
    ("sort_field", "sort_direction", "expected"),
    [
        ("name", "desc", ["Zeta Belt", "Synthetic Ore", "Alpha Hat"]),
        ("price", "desc", ["Alpha Hat", "Zeta Belt", "Synthetic Ore"]),
        ("started", "asc", ["Synthetic Ore", "Zeta Belt", "Alpha Hat"]),
        ("sold", "desc", ["Alpha Hat", "Zeta Belt", "Synthetic Ore"]),
    ],
)
def test_sold_sales_sort_by_each_displayed_field(
    session,
    catalog_item,
    sort_field,
    sort_direction,
    expected,
) -> None:
    alpha = Item(
        display_name="Alpha Hat",
        normalized_name="alpha hat",
        category="Hat",
        identity_category="hat",
    )
    zeta = Item(
        display_name="Zeta Belt",
        normalized_name="zeta belt",
        category="Belt",
        identity_category="belt",
    )
    session.add_all([alpha, zeta])
    session.flush()
    session.add_all(
        [
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100,
                selling_started_at=datetime(2026, 8, 20, tzinfo=UTC),
                date_sold=datetime(2026, 8, 23, tzinfo=UTC),
            ),
            SaleListing(
                item_id=zeta.id,
                lot_quantity=1,
                asking_price=200,
                selling_started_at=datetime(2026, 8, 21, tzinfo=UTC),
                date_sold=datetime(2026, 8, 24, tzinfo=UTC),
            ),
            SaleListing(
                item_id=alpha.id,
                lot_quantity=1,
                asking_price=300,
                selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                date_sold=datetime(2026, 8, 25, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    results = SalesService(session).sold(sort_field, sort_direction)

    assert [result.display_name for result in results] == expected


def test_active_or_sold_sale_can_be_deleted(session, catalog_item) -> None:
    service = SalesService(session)
    active = service.start(SaleListingCreate(item_uuid=catalog_item.uuid))
    sold = service.start(SaleListingCreate(item_uuid=catalog_item.uuid))
    service.mark_sold(sold.uuid)

    assert service.delete(active.uuid).uuid == active.uuid
    assert service.delete(sold.uuid).uuid == sold.uuid
    assert service.active() == []
    assert service.sold() == []

    with pytest.raises(SaleListingNotFound):
        service.delete(active.uuid)


def test_deleting_sale_keeps_linked_price_observation(session, catalog_item) -> None:
    observation = PriceService(session, "Dodge").record(
        catalog_item.uuid,
        PriceObservationCreate(
            lot_quantity=10,
            total_price=125_000,
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        ),
    )
    listing = SalesService(session).active()[0]

    SalesService(session).delete(listing.uuid)

    current = PriceService(session, "Dodge").current_for_item(catalog_item.id)
    assert current is not None
    assert current.observation_uuid == observation.observation_uuid
