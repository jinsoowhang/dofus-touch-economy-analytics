from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item, PriceObservation, Recipe, SaleListing
from dofus_touch_economy.schemas import (
    PriceObservationCreate,
    SaleListingCreate,
    SalePriceUpdate,
)
from dofus_touch_economy.services.pricing import PriceService
from dofus_touch_economy.services.sales import (
    SaleItemNotFound,
    SaleListingConflict,
    SaleListingFilters,
    SaleListingNotFound,
    SalesService,
)


def test_manual_sale_moves_from_active_to_sold_and_back(session, catalog_item) -> None:
    service = SalesService(session, "Dodge")
    listing = service.start(
        SaleListingCreate(
            item_uuid=catalog_item.uuid,
            asking_price=50_000,
        )
    )

    assert listing.display_name == catalog_item.display_name
    assert listing.asking_price == 50_000
    assert listing.selling_started_at.tzinfo == UTC
    assert listing.relisted_at is None
    assert listing.date_sold is None
    assert [sale.uuid for sale in service.active()] == [listing.uuid]
    current_price = PriceService(session, "Dodge").current_for_item(catalog_item.id)
    assert current_price is not None
    assert current_price.total_price == 50_000

    sold = service.mark_sold(listing.uuid)

    assert sold.date_sold is not None
    assert sold.date_sold.tzinfo == UTC
    assert service.active() == []
    assert [sale.uuid for sale in service.sold()] == [listing.uuid]

    reopened = service.reopen(listing.uuid)

    assert reopened.date_sold is None
    assert [sale.uuid for sale in service.active()] == [listing.uuid]
    assert service.sold() == []


def test_completed_sale_profit_keeps_its_sale_time_recipe_cost(
    session_factory,
    fixture_dir,
) -> None:
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    with session_factory() as session:
        items = {item.normalized_name: item for item in session.scalars(select(Item)).all()}
        service = SalesService(session, "Dodge")
        listings = service.start_many(
            [
                SaleListingCreate(
                    item_uuid=items["synthetic widget"].uuid,
                    asking_price=5_000,
                ),
                SaleListingCreate(
                    item_uuid=items["synthetic widget"].uuid,
                    asking_price=4_500,
                ),
            ]
        )

        sold = service.mark_sold_many([listing.uuid for listing in listings])

        assert [(listing.recipe_cost, listing.profit) for listing in sold] == [
            (Decimal(3_500), Decimal(1_500)),
            (Decimal(3_500), Decimal(1_000)),
        ]
        stored_costs = list(
            session.scalars(select(SaleListing.recipe_cost_at_sale).order_by(SaleListing.id))
        )
        assert stored_costs == [Decimal(3_500), Decimal(3_500)]

        later_observed_at = datetime.now(UTC) + timedelta(seconds=1)
        prices = PriceService(session, "Dodge")
        prices.record(
            items["synthetic ore"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=1_500,
                observed_at=later_observed_at,
            ),
        )
        prices.record(
            items["synthetic fiber"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=1_000,
                observed_at=later_observed_at,
            ),
        )

        sold_after_price_change = service.sold(sort_field="profit", sort_direction="desc")
        filtered_sold = service.sold(filters=SaleListingFilters(minimum_profit=Decimal(1_200)))
        daily_totals = service.daily_totals(UTC, sold_after_price_change)

        assert [(listing.recipe_cost, listing.profit) for listing in sold_after_price_change] == [
            (Decimal(3_500), Decimal(1_500)),
            (Decimal(3_500), Decimal(1_000)),
        ]
        assert [listing.asking_price for listing in filtered_sold] == [5_000]
        assert daily_totals[0].cost_covered_price == 9_500
        assert daily_totals[0].total_cost == Decimal(7_000)
        assert daily_totals[0].total_profit == Decimal(2_500)

        reopened = service.reopen(listings[0].uuid)
        stored_reopened = session.scalar(
            select(SaleListing).where(SaleListing.uuid == listings[0].uuid)
        )

        assert reopened.recipe_cost == Decimal(6_000)
        assert reopened.profit == Decimal(-1_000)
        assert stored_reopened is not None
        assert stored_reopened.recipe_cost_at_sale is None


def test_daily_totals_separate_all_sales_from_cost_covered_sales(
    session,
    catalog_item,
) -> None:
    uncosted_item = Item(
        display_name="Uncosted Cape",
        normalized_name="uncosted cape",
        category="Cape",
        identity_category="cape",
    )
    session.add(uncosted_item)
    session.flush()
    sold_at = datetime(2026, 8, 23, tzinfo=UTC)
    session.add_all(
        [
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100,
                selling_started_at=sold_at - timedelta(days=1),
                date_sold=sold_at,
                recipe_cost_at_sale=Decimal(80),
            ),
            SaleListing(
                item_id=uncosted_item.id,
                lot_quantity=1,
                asking_price=1_000,
                selling_started_at=sold_at - timedelta(days=1),
                date_sold=sold_at,
            ),
        ]
    )
    session.commit()

    daily_total = SalesService(session, "Dodge").daily_totals(UTC)[0]

    assert daily_total.total_price == 1_100
    assert daily_total.cost_covered_price == 100
    assert daily_total.total_cost == Decimal(80)
    assert daily_total.total_profit == Decimal(20)
    assert daily_total.sold_count == 2
    assert daily_total.costed_count == 1


def test_legacy_completed_sale_reconstructs_cost_only_from_sale_time_history(
    session_factory,
    fixture_dir,
) -> None:
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    with session_factory() as session:
        items = {item.normalized_name: item for item in session.scalars(select(Item)).all()}
        recipe = session.scalar(select(Recipe))
        latest_recorded_at = session.scalar(
            select(PriceObservation.recorded_at)
            .order_by(PriceObservation.recorded_at.desc())
            .limit(1)
        )
        assert recipe is not None
        assert latest_recorded_at is not None
        sold_at = latest_recorded_at.replace(tzinfo=UTC) + timedelta(seconds=1)
        recipe.created_at = sold_at + timedelta(seconds=1)
        session.add(
            SaleListing(
                item_id=items["synthetic widget"].id,
                lot_quantity=1,
                asking_price=5_000,
                selling_started_at=sold_at - timedelta(seconds=1),
                date_sold=sold_at,
            )
        )
        session.commit()
        service = SalesService(session, "Dodge")

        [legacy_sale] = service.sold()

        assert legacy_sale.recipe_cost == Decimal(3_500)
        assert legacy_sale.profit == Decimal(1_500)

        PriceService(session, "Dodge").record(
            items["synthetic ore"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=2_000,
                observed_at=sold_at + timedelta(seconds=1),
            ),
        )

        [legacy_sale_after_later_price] = service.sold()

        assert legacy_sale_after_later_price.recipe_cost == Decimal(3_500)
        assert legacy_sale_after_later_price.profit == Decimal(1_500)


def test_out_of_stock_requires_sales_history_and_no_active_listing(
    session,
    catalog_item,
) -> None:
    service = SalesService(session, "Dodge")

    assert service.out_of_stock() == []

    first = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=100))
    service.mark_sold(first.uuid)

    [out_of_stock] = service.out_of_stock()
    assert out_of_stock.item_uuid == catalog_item.uuid
    assert out_of_stock.sold_count == 1
    assert out_of_stock.suggested_restock_quantity == 3
    assert out_of_stock.last_sale_price == 100
    assert out_of_stock.current_price == 100
    assert out_of_stock.recipe_cost is None
    assert out_of_stock.last_sale_profit is None
    assert out_of_stock.last_sale_roi is None
    assert out_of_stock.is_craftable is False

    active = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=200))

    assert service.out_of_stock() == []

    service.mark_sold(active.uuid)
    [out_of_stock_again] = service.out_of_stock()
    assert out_of_stock_again.sold_count == 2
    assert out_of_stock_again.suggested_restock_quantity == 3
    assert out_of_stock_again.last_sale_price == 200
    assert out_of_stock_again.current_price == 200


def test_out_of_stock_restock_quantity_counts_only_registered_sales_days(
    session,
) -> None:
    items = [
        Item(
            display_name=name,
            normalized_name=name.casefold(),
            category="Hat",
            identity_category="hat",
        )
        for name in ("Fast Hat", "Medium Hat", "Slow Hat", "Activity Marker")
    ]
    session.add_all(items)
    session.flush()
    fast, medium, slow, activity_marker = items
    started_at = datetime(2026, 8, 1, 12, tzinfo=UTC)
    session.add_all(
        [
            SaleListing(
                item_id=fast.id,
                lot_quantity=1,
                asking_price=100,
                selling_started_at=started_at,
                date_sold=datetime(2026, 8, 2, 12, tzinfo=UTC),
            ),
            SaleListing(
                item_id=medium.id,
                lot_quantity=1,
                asking_price=200,
                selling_started_at=started_at,
                date_sold=datetime(2026, 9, 1, 12, tzinfo=UTC),
            ),
            SaleListing(
                item_id=slow.id,
                lot_quantity=1,
                asking_price=300,
                selling_started_at=started_at,
                date_sold=datetime(2026, 10, 1, 12, tzinfo=UTC),
            ),
            *[
                SaleListing(
                    item_id=activity_marker.id,
                    lot_quantity=1,
                    asking_price=50,
                    selling_started_at=started_at,
                    date_sold=datetime(2026, month, day, 12, tzinfo=UTC),
                )
                for month, day in (
                    (8, 3),
                    (8, 20),
                    (9, 2),
                    (9, 3),
                    (9, 4),
                    (9, 5),
                )
            ],
            SaleListing(
                item_id=activity_marker.id,
                lot_quantity=1,
                asking_price=50,
                selling_started_at=datetime(2026, 10, 2, 12, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    results = SalesService(session, "Dodge").out_of_stock(UTC)

    assert {item.display_name: item.suggested_restock_quantity for item in results} == {
        "Fast Hat": 3,
        "Medium Hat": 2,
        "Slow Hat": 1,
    }


def test_best_sellers_group_completed_sales_and_rank_decision_metrics(
    session,
    catalog_item,
) -> None:
    premium_hat = Item(
        display_name="Premium Hat",
        normalized_name="premium hat",
        category="Hat",
        identity_category="hat",
    )
    session.add(premium_hat)
    session.flush()
    session.add_all(
        [
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100,
                selling_started_at=datetime(2026, 8, 10, tzinfo=UTC),
                date_sold=datetime(2026, 8, 11, tzinfo=UTC),
                recipe_cost_at_sale=Decimal(25),
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=300,
                selling_started_at=datetime(2026, 8, 12, tzinfo=UTC),
                date_sold=datetime(2026, 8, 15, tzinfo=UTC),
                recipe_cost_at_sale=Decimal(50),
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=None,
                selling_started_at=datetime(2026, 8, 16, tzinfo=UTC),
                date_sold=datetime(2026, 8, 18, tzinfo=UTC),
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=500,
                selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
            ),
            SaleListing(
                item_id=premium_hat.id,
                lot_quantity=1,
                asking_price=1_000,
                selling_started_at=datetime(2026, 8, 17, tzinfo=UTC),
                date_sold=datetime(2026, 8, 21, tzinfo=UTC),
                recipe_cost_at_sale=Decimal(900),
            ),
        ]
    )
    session.commit()
    PriceService(session, "Dodge").record(
        catalog_item.uuid,
        PriceObservationCreate(
            lot_quantity=1,
            total_price=500,
            observed_at=datetime(2026, 8, 22, tzinfo=UTC),
        ),
    )

    report = SalesService(session, "Dodge").best_sellers()

    assert [item.display_name for item in report.items] == ["Synthetic Ore", "Premium Hat"]
    ore, hat = report.items
    assert ore.sold_count == 3
    assert ore.priced_sale_count == 2
    assert ore.total_revenue == 400
    assert ore.average_sale_price == Decimal(200)
    assert ore.average_days_to_sell == Decimal(2)
    assert ore.active_listing_count == 1
    assert ore.current_price == Decimal(500)
    assert ore.total_profit == Decimal(325)
    assert ore.last_sold_at == datetime(2026, 8, 18, tzinfo=UTC)
    assert hat.sold_count == 1
    assert hat.total_revenue == 1_000
    assert hat.total_profit == Decimal(100)
    assert report.total_sold_count == 4
    assert report.priced_sale_count == 3
    assert report.total_revenue == 1_400
    assert report.average_days_to_sell == Decimal("2.5")
    assert report.best_seller is ore
    assert report.top_revenue_item is hat
    assert report.top_profit_item is ore


def test_priced_sale_updates_current_price_and_preserves_history(session, catalog_item) -> None:
    price_service = PriceService(session, "Dodge")
    previous = price_service.record(
        catalog_item.uuid,
        PriceObservationCreate(
            lot_quantity=1,
            total_price=100_000,
            observed_at=datetime(2020, 1, 1, tzinfo=UTC),
        ),
    )

    listing = SalesService(session, "Dodge").start(
        SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=98_000)
    )

    current = price_service.current_for_item(catalog_item.id)
    history = price_service.history_for_item(catalog_item.id)
    stored_listing = session.scalar(select(SaleListing).where(SaleListing.uuid == listing.uuid))
    assert current is not None
    assert current.total_price == 98_000
    assert [observation.total_price for observation in history] == [98_000, 100_000]
    assert history[1].observation_uuid == previous.observation_uuid
    assert stored_listing is not None
    assert stored_listing.price_observation_id is not None


def test_price_record_does_not_start_a_sale(session, catalog_item) -> None:
    observation = PriceService(session, "Dodge").record(
        catalog_item.uuid,
        PriceObservationCreate(
            lot_quantity=1,
            total_price=125_000,
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        ),
    )

    current = PriceService(session, "Dodge").current_for_item(catalog_item.id)

    assert SalesService(session, "Dodge").active() == []
    assert current is not None
    assert current.observation_uuid == observation.observation_uuid


def test_sales_reject_unknown_items_and_invalid_transitions(session) -> None:
    service = SalesService(session, "Dodge")

    with pytest.raises(SaleItemNotFound):
        service.start(SaleListingCreate(item_uuid=uuid4(), asking_price=100))
    with pytest.raises(SaleListingNotFound):
        service.mark_sold(uuid4())


def test_start_many_adds_one_atomic_listing_and_price_per_item(session, catalog_item) -> None:
    second_item = Item(
        display_name="Synthetic Ring",
        normalized_name="synthetic ring",
        category="Ring",
        identity_category="ring",
    )
    session.add(second_item)
    session.commit()
    service = SalesService(session, "Dodge")

    listings = service.start_many(
        [
            SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=1_000),
            SaleListingCreate(item_uuid=second_item.uuid, asking_price=2_000),
        ]
    )

    assert [(listing.display_name, listing.asking_price) for listing in listings] == [
        ("Synthetic Ore", 1_000),
        ("Synthetic Ring", 2_000),
    ]
    assert len({listing.selling_started_at for listing in listings}) == 1
    assert len(service.active()) == 2
    assert len(session.scalars(select(PriceObservation)).all()) == 2

    with pytest.raises(SaleItemNotFound):
        service.start_many(
            [
                SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=3_000),
                SaleListingCreate(item_uuid=uuid4(), asking_price=4_000),
            ]
        )
    assert len(service.active()) == 2
    assert len(session.scalars(select(PriceObservation)).all()) == 2


def test_sale_cannot_be_marked_sold_twice(session, catalog_item) -> None:
    service = SalesService(session, "Dodge")
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=100))
    service.mark_sold(listing.uuid)

    with pytest.raises(SaleListingConflict):
        service.mark_sold(listing.uuid)


def test_bulk_sale_mutations_are_atomic_and_limited_to_active_rows(
    session,
    catalog_item,
) -> None:
    service = SalesService(session, "Dodge")
    listings = [
        service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=price))
        for price in (100, 200, 300)
    ]

    with pytest.raises(SaleListingNotFound):
        service.mark_sold_many([listings[0].uuid, uuid4()])
    assert len(service.active()) == 3
    assert service.sold() == []

    sold = service.mark_sold_many([listings[0].uuid, listings[1].uuid])
    assert {listing.uuid for listing in sold} == {listings[0].uuid, listings[1].uuid}
    assert len({listing.date_sold for listing in sold}) == 1
    assert len(service.active()) == 1

    with pytest.raises(SaleListingConflict):
        service.delete_active_many([listings[0].uuid, listings[2].uuid])
    assert len(service.active()) == 1
    assert len(service.sold()) == 2

    deleted = service.delete_active_many([listings[2].uuid])
    assert [listing.uuid for listing in deleted] == [listings[2].uuid]
    assert service.active() == []
    assert len(service.sold()) == 2


def test_active_sale_cannot_be_reopened(session, catalog_item) -> None:
    service = SalesService(session, "Dodge")
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=100))

    with pytest.raises(SaleListingConflict):
        service.reopen(listing.uuid)


def test_sale_can_be_duplicated_and_repriced_independently(session, catalog_item) -> None:
    service = SalesService(session, "Dodge")
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
    assert updated.relisted_at is not None
    assert updated.relisted_at > updated.selling_started_at
    assert active_by_uuid[original.uuid].asking_price == 50_000
    assert active_by_uuid[duplicate.uuid].asking_price == 45_000
    assert active_by_uuid[original.uuid].relisted_at is None
    assert active_by_uuid[duplicate.uuid].relisted_at == updated.relisted_at
    history = PriceService(session, "Dodge").history_for_item(catalog_item.id)
    assert [observation.total_price for observation in history] == [45_000, 50_000]


def test_sold_sale_price_cannot_be_changed(session, catalog_item) -> None:
    service = SalesService(session, "Dodge")
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=100))
    service.mark_sold(listing.uuid)

    with pytest.raises(SaleListingConflict):
        service.update_price(listing.uuid, SalePriceUpdate(asking_price=1_000))


def test_unknown_sale_cannot_be_duplicated_or_repriced(session) -> None:
    service = SalesService(session, "Dodge")
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
        ("relisted", "asc", ["Zeta Belt", "Alpha Hat", "Synthetic Ore"]),
        ("relisted", "desc", ["Alpha Hat", "Zeta Belt", "Synthetic Ore"]),
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
    zeta_relist = PriceObservation(
        item_id=zeta.id,
        lot_quantity=1,
        total_price=200,
        observed_at=datetime(2026, 8, 23, tzinfo=UTC),
        market_context="Dodge",
    )
    alpha_relist = PriceObservation(
        item_id=alpha.id,
        lot_quantity=1,
        total_price=300,
        observed_at=datetime(2026, 8, 24, tzinfo=UTC),
        market_context="Dodge",
    )
    session.add_all([zeta_relist, alpha_relist])
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
                price_observation_id=zeta_relist.id,
                lot_quantity=1,
                asking_price=200,
                selling_started_at=datetime(2026, 8, 21, tzinfo=UTC),
            ),
            SaleListing(
                item_id=alpha.id,
                price_observation_id=alpha_relist.id,
                lot_quantity=1,
                asking_price=300,
                selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    results = SalesService(session, "Dodge").active(sort_field, sort_direction)

    assert [result.display_name for result in results] == expected


def test_active_price_reviews_flag_week_old_listings_and_suggest_markdowns(
    session,
    catalog_item,
) -> None:
    no_history_item = Item(
        display_name="No History Hat",
        normalized_name="no history hat",
        category="Hat",
        identity_category="hat",
    )
    young_item = Item(
        display_name="Young Hat",
        normalized_name="young hat",
        category="Hat",
        identity_category="hat",
    )
    session.add_all([no_history_item, young_item])
    session.flush()
    median_review_listing = SaleListing(
        item_id=catalog_item.id,
        lot_quantity=1,
        asking_price=1_000,
        selling_started_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
    )
    markdown_review_listing = SaleListing(
        item_id=no_history_item.id,
        lot_quantity=1,
        asking_price=200,
        selling_started_at=datetime(2026, 8, 16, 12, tzinfo=UTC),
    )
    young_listing = SaleListing(
        item_id=young_item.id,
        lot_quantity=1,
        asking_price=300,
        selling_started_at=datetime(2026, 8, 17, 12, tzinfo=UTC),
    )
    session.add_all(
        [
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=700,
                selling_started_at=datetime(2026, 8, 1, tzinfo=UTC),
                date_sold=datetime(2026, 8, 2, tzinfo=UTC),
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=800,
                selling_started_at=datetime(2026, 8, 3, tzinfo=UTC),
                date_sold=datetime(2026, 8, 4, tzinfo=UTC),
            ),
            median_review_listing,
            markdown_review_listing,
            young_listing,
        ]
    )
    session.commit()
    service = SalesService(session, "Dodge")

    reviews = service.active_price_reviews(
        service.active(),
        as_of=datetime(2026, 8, 23, 12, tzinfo=UTC),
        display_timezone=ZoneInfo("America/Los_Angeles"),
    )

    assert set(reviews) == {median_review_listing.uuid, markdown_review_listing.uuid}
    assert reviews[median_review_listing.uuid].age_days == 8
    assert reviews[median_review_listing.uuid].suggested_price == 750
    assert reviews[median_review_listing.uuid].suggestion_basis == "completed_sales_median"
    assert reviews[median_review_listing.uuid].completed_sale_count == 2
    assert reviews[markdown_review_listing.uuid].age_days == 7
    assert reviews[markdown_review_listing.uuid].suggested_price == 190
    assert reviews[markdown_review_listing.uuid].suggestion_basis == "standard_markdown"


def test_repricing_resets_active_price_review_clock(session, catalog_item) -> None:
    now = datetime.now(UTC)
    listing = SaleListing(
        item_id=catalog_item.id,
        lot_quantity=1,
        asking_price=1_000,
        selling_started_at=now - timedelta(days=8),
    )
    session.add(listing)
    session.commit()
    service = SalesService(session, "Dodge")

    before_update = service.active_price_reviews(
        service.active(),
        as_of=now,
        display_timezone=ZoneInfo("America/Los_Angeles"),
    )

    assert listing.uuid in before_update

    updated = service.update_price(
        listing.uuid,
        SalePriceUpdate(asking_price=950),
    )
    assert updated.relisted_at is not None

    after_update = service.active_price_reviews(
        service.active(),
        as_of=updated.relisted_at,
        display_timezone=ZoneInfo("America/Los_Angeles"),
    )

    assert listing.uuid not in after_update


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

    results = SalesService(session, "Dodge").sold(sort_field, sort_direction)

    assert [result.display_name for result in results] == expected


def test_sales_filters_use_item_category_price_and_pacific_activity_date(
    session,
    catalog_item,
) -> None:
    alpha = Item(
        display_name="Alpha Hat",
        normalized_name="alpha hat",
        category="Hat",
        identity_category="hat",
    )
    beta = Item(
        display_name="Beta Hat",
        normalized_name="beta hat",
        category="Hat",
        identity_category="hat",
    )
    session.add_all([alpha, beta])
    session.flush()
    session.add_all(
        [
            SaleListing(
                item_id=alpha.id,
                lot_quantity=1,
                asking_price=125,
                selling_started_at=datetime(2026, 8, 22, 6, 30, tzinfo=UTC),
            ),
            SaleListing(
                item_id=beta.id,
                lot_quantity=1,
                asking_price=250,
                selling_started_at=datetime(2026, 8, 22, 7, 30, tzinfo=UTC),
            ),
            SaleListing(
                item_id=alpha.id,
                lot_quantity=1,
                asking_price=300,
                selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                date_sold=datetime(2026, 8, 23, 6, 30, tzinfo=UTC),
            ),
            SaleListing(
                item_id=beta.id,
                lot_quantity=1,
                asking_price=400,
                selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                date_sold=datetime(2026, 8, 23, 7, 30, tzinfo=UTC),
            ),
        ]
    )
    session.commit()
    service = SalesService(session, "Dodge")
    pacific = ZoneInfo("America/Los_Angeles")

    combined = service.active(
        filters=SaleListingFilters(
            item_query="alpha",
            category="hat",
            minimum_price=100,
            maximum_price=200,
            date_from=date(2026, 8, 21),
            date_to=date(2026, 8, 21),
            display_timezone=pacific,
        )
    )
    exact_item = service.active(filters=SaleListingFilters(item_uuid=beta.uuid))
    later_active = service.active(
        filters=SaleListingFilters(
            date_from=date(2026, 8, 22),
            display_timezone=pacific,
        )
    )
    earlier_sold = service.sold(
        filters=SaleListingFilters(
            maximum_price=350,
            date_from=date(2026, 8, 22),
            date_to=date(2026, 8, 22),
            display_timezone=pacific,
        )
    )

    assert [listing.display_name for listing in combined] == ["Alpha Hat"]
    assert [listing.display_name for listing in exact_item] == ["Beta Hat"]
    assert [listing.display_name for listing in later_active] == ["Beta Hat"]
    assert [listing.display_name for listing in earlier_sold] == ["Alpha Hat"]
    assert service.active(filters=SaleListingFilters(minimum_profit=0)) == []


def test_active_or_sold_sale_can_be_deleted(session, catalog_item) -> None:
    service = SalesService(session, "Dodge")
    active = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=100))
    sold = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=200))
    service.mark_sold(sold.uuid)

    assert service.delete(active.uuid).uuid == active.uuid
    assert service.delete(sold.uuid).uuid == sold.uuid
    assert service.active() == []
    assert service.sold() == []

    with pytest.raises(SaleListingNotFound):
        service.delete(active.uuid)


def test_deleting_sale_keeps_linked_price_observation(session, catalog_item) -> None:
    service = SalesService(session, "Dodge")
    listing = service.start(SaleListingCreate(item_uuid=catalog_item.uuid, asking_price=125_000))
    stored_listing = session.scalar(select(SaleListing).where(SaleListing.uuid == listing.uuid))
    assert stored_listing is not None
    assert stored_listing.price_observation is not None
    observation_uuid = stored_listing.price_observation.uuid

    service.delete(listing.uuid)

    current = PriceService(session, "Dodge").current_for_item(catalog_item.id)
    assert current is not None
    assert current.observation_uuid == observation_uuid
