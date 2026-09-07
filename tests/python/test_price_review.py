import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item, PriceObservation, SaleListing
from dofus_touch_economy.schemas import PriceObservationCreate, SalePriceUpdate
from dofus_touch_economy.services.pricing import PriceService
from dofus_touch_economy.services.sales import SalesService

PACIFIC = ZoneInfo("America/Los_Angeles")


def test_review_uses_pacific_days_latest_relist_and_includes_unpriced_listings(
    session, catalog_item
) -> None:
    # Seven calendar days across the spring DST change is less than 168 hours.
    now = datetime(2026, 3, 15, 0, 1, tzinfo=PACIFIC)
    started = datetime(2026, 3, 8, 23, 59, tzinfo=PACIFIC)
    recent = PriceObservation(
        item_id=catalog_item.id,
        lot_quantity=1,
        total_price=900,
        observed_at=datetime(2026, 3, 9, 0, 1, tzinfo=PACIFIC).astimezone(UTC),
        market_context="Dodge",
        source="manual",
    )
    excluded_item = Item(
        display_name="Excluded Hat",
        normalized_name="excluded hat",
        category="Hat",
        identity_category="hat",
        touch_catalog_status="excluded",
    )
    session.add_all([recent, excluded_item])
    session.flush()
    due = [
        SaleListing(
            lot_quantity=1,
            item_id=catalog_item.id,
            asking_price=price,
            selling_started_at=started.astimezone(UTC),
        )
        for price in (1000, 1, None)
    ]
    not_due = [
        SaleListing(
            lot_quantity=1,
            item_id=catalog_item.id,
            asking_price=900,
            selling_started_at=now.astimezone(UTC) - timedelta(days=30),
            price_observation_id=recent.id,
        ),
        SaleListing(
            lot_quantity=1,
            item_id=catalog_item.id,
            asking_price=800,
            selling_started_at=now.astimezone(UTC) - timedelta(days=20),
            date_sold=now.astimezone(UTC) - timedelta(days=2),
        ),
        SaleListing(
            lot_quantity=1,
            item_id=catalog_item.id,
            asking_price=700,
            selling_started_at=now.astimezone(UTC) + timedelta(days=1),
        ),
        SaleListing(
            lot_quantity=1,
            item_id=excluded_item.id,
            asking_price=600,
            selling_started_at=now.astimezone(UTC) - timedelta(days=20),
        ),
    ]
    session.add_all([*due, *not_due])
    session.commit()
    rows = SalesService(session, "Dodge").price_review_listings(as_of=now, display_timezone=PACIFIC)
    assert {row.listing.uuid for row in rows} == {listing.uuid for listing in due}
    assert all(row.age_days == 7 for row in rows)
    by_price = {row.listing.asking_price: row for row in rows}
    assert by_price[1000].suggestion.suggested_price == 800
    assert by_price[1].suggestion is None
    assert by_price[None].suggestion is None
    assert all(row.listing.recipe_cost is None and row.suggested_profit is None for row in rows)
    assert all(row.current_price.unit_price == 900 for row in rows)


def test_relisting_is_per_listing_and_returns_after_seven_days(session, catalog_item) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=20)
    listings = [
        SaleListing(
            lot_quantity=1, item_id=catalog_item.id, asking_price=1000, selling_started_at=old
        )
        for _ in range(2)
    ]
    session.add_all(listings)
    session.commit()
    service = SalesService(session, "Dodge")
    # An unrelated item price observation must not reset either listing's clock.
    PriceService(session, "Dodge").record(
        catalog_item.uuid,
        PriceObservationCreate(
            lot_quantity=1,
            total_price=700,
            observed_at=now,
        ),
    )
    assert len(service.price_review_listings(as_of=now, display_timezone=PACIFIC)) == 2
    updated = service.update_price(listings[0].uuid, SalePriceUpdate(asking_price=950))
    assert updated.selling_started_at == old
    assert updated.relisted_at is not None
    assert updated.date_sold is None
    rows = service.price_review_listings(as_of=updated.relisted_at, display_timezone=PACIFIC)
    assert [row.listing.uuid for row in rows] == [listings[1].uuid]
    review_date = updated.relisted_at.astimezone(PACIFIC).replace(hour=0, minute=0, second=0)
    assert (
        len(
            service.price_review_listings(
                as_of=review_date + timedelta(days=6),
                display_timezone=PACIFIC,
            )
        )
        == 1
    )
    returned = service.price_review_listings(
        as_of=review_date + timedelta(days=7),
        display_timezone=PACIFIC,
    )
    assert len(returned) == 2
    relisted = next(row for row in returned if row.listing.uuid == listings[0].uuid)
    assert relisted.age_days == 7
    assert relisted.listing.relisted_at == updated.relisted_at
    assert session.scalar(select(func.count()).select_from(PriceObservation)) == 2


def test_review_shows_current_cost_and_loss_at_suggested_price(
    session_factory, fixture_dir
) -> None:
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    with session_factory() as session:
        item = session.scalar(select(Item).where(Item.normalized_name == "synthetic widget"))
        session.add(
            SaleListing(
                lot_quantity=1,
                item_id=item.id,
                asking_price=3600,
                selling_started_at=datetime.now(UTC) - timedelta(days=8),
            )
        )
        session.commit()
        (row,) = SalesService(session, "Dodge").price_review_listings(
            as_of=datetime.now(UTC),
            display_timezone=PACIFIC,
        )
        assert row.listing.recipe_cost == Decimal(3500)
        assert row.listing.profit == Decimal(100)
        assert row.suggestion.suggested_price == 3000
        assert row.suggested_profit == Decimal(-500)


def test_page_navigation_pagination_sort_and_empty_state(
    client, session_factory, catalog_item
) -> None:
    empty = client.get("/sales/price-review")
    assert empty.status_code == 200
    assert "No active listings are due for price review." in empty.text
    assert re.search(
        r'href="/sales/price-review"\s+class="site-submenu-link is-active"\s+aria-current="page"',
        empty.text,
    )
    assert (
        empty.text.index(">Out of Stock Items</a>")
        < empty.text.index(">Price Review</a>")
        < empty.text.index(">Profit Opportunities</a>")
    )
    with session_factory() as session:
        listings = [
            SaleListing(
                lot_quantity=1,
                item_id=catalog_item.id,
                asking_price=100 + i,
                selling_started_at=datetime.now(UTC) - timedelta(days=8),
            )
            for i in range(51)
        ]
        session.add_all(listings)
        session.commit()
        highest_uuid = listings[-1].uuid
    first = client.get("/sales/price-review?sort=price&direction=desc")
    ids = re.findall(r'data-listing-uuid="([^"]+)"', first.text)
    assert first.status_code == 200
    assert len(ids) == 50 and ids[0] == str(highest_uuid)
    assert "1–50 of 51" in first.text and "6,375" in first.text
    second = client.get("/sales/price-review?sort=price&direction=desc&page=2")
    assert len(re.findall(r'data-listing-uuid="([^"]+)"', second.text)) == 1
    assert "51–51 of 51" in second.text
    assert "page=2" in second.text
    assert "Page 2 of 2" in client.get("/sales/price-review?page=999").text
    for query in ("page=0", "sort=invalid", "direction=invalid"):
        assert client.get("/sales/price-review?" + query).status_code == 422


@pytest.mark.parametrize("asking_price", ["950", "1,250"])
def test_price_review_save_records_relist_removes_only_selected_row_and_preserves_state(
    client,
    session_factory,
    catalog_item,
    asking_price,
) -> None:
    old = datetime.now(UTC) - timedelta(days=9)
    with session_factory() as session:
        listings = [
            SaleListing(
                lot_quantity=1, item_id=catalog_item.id, asking_price=1000, selling_started_at=old
            )
            for _ in range(2)
        ]
        session.add_all(listings)
        session.commit()
        selected, other = [listing.uuid for listing in listings]
    result = client.post(
        f"/sales/price-review/{selected}/price?sort=price&direction=asc&page=2",
        data={"asking_price": asking_price},
        follow_redirects=False,
    )
    assert result.status_code == 303
    assert (
        result.headers["location"]
        == "/sales/price-review?sort=price&direction=asc&page=2&updated=true"
    )
    page = client.get(result.headers["location"])
    assert "Sales price updated and relisted date recorded" in page.text
    assert f'data-listing-uuid="{selected}"' not in page.text
    assert f'data-listing-uuid="{other}"' in page.text
    with session_factory() as session:
        listing = session.scalar(select(SaleListing).where(SaleListing.uuid == selected))
        assert listing.asking_price == int(asking_price.replace(",", ""))
        assert listing.selling_started_at.replace(tzinfo=UTC) == old
        assert listing.date_sold is None
        assert listing.price_observation.observed_at > listing.selling_started_at
        assert listing.price_observation.source == "manual"
        assert session.scalar(select(func.count()).select_from(PriceObservation)) == 1
        assert session.scalar(select(func.count()).select_from(SaleListing)) == 2
    assert "Relisted Date" in client.get("/sales").text


def test_failed_review_updates_preserve_rows_and_do_not_append_observations(
    client,
    session_factory,
    catalog_item,
) -> None:
    with session_factory() as session:
        listing = SaleListing(
            lot_quantity=1,
            item_id=catalog_item.id,
            asking_price=1000,
            selling_started_at=datetime.now(UTC) - timedelta(days=9),
        )
        sold = SaleListing(
            lot_quantity=1,
            item_id=catalog_item.id,
            asking_price=1000,
            selling_started_at=datetime.now(UTC) - timedelta(days=9),
            date_sold=datetime.now(UTC),
        )
        session.add_all([listing, sold])
        session.commit()
        listing_uuid, sold_uuid = listing.uuid, sold.uuid
    for value in ("0", "-1", "1.5", "bad", ""):
        result = client.post(
            f"/sales/price-review/{listing_uuid}/price", data={"asking_price": value}
        )
        assert result.status_code == 422
        assert f'data-listing-uuid="{listing_uuid}"' in result.text
        assert f'value="{value}"' in result.text
        assert 'role="alert"' in result.text and 'aria-invalid="true"' in result.text
    for target, status in ((uuid4(), 404), (sold_uuid, 409)):
        result = client.post(f"/sales/price-review/{target}/price", data={"asking_price": "900"})
        assert result.status_code == status
        assert "Price Review" in result.text
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PriceObservation)) == 0
        assert (
            session.scalar(select(SaleListing.asking_price).where(SaleListing.uuid == listing_uuid))
            == 1000
        )


@pytest.mark.parametrize(
    ("asking_price", "sale_median", "expected"),
    [
        (119_000, None, 113_000),
        (119_500, None, 114_000),
        (130_000, None, 124_000),
        (120_000, None, 114_000),
        (150_000, 113_050, 113_000),
        (1_600, None, 1_000),
        (1_000, None, 950),
    ],
)
def test_price_review_rounds_displayed_and_applied_suggestions(
    client, session_factory, catalog_item, asking_price, sale_median, expected
) -> None:
    now = datetime.now(UTC)
    with session_factory() as session:
        listing = SaleListing(
            item_id=catalog_item.id,
            lot_quantity=1,
            asking_price=asking_price,
            selling_started_at=now - timedelta(days=8),
        )
        session.add(listing)
        if sale_median is not None:
            session.add(
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=sale_median,
                    selling_started_at=now - timedelta(days=10),
                    date_sold=now - timedelta(days=9),
                )
            )
        session.commit()
        listing_uuid = listing.uuid
    page = client.get("/sales/price-review")
    assert page.status_code == 200
    assert f"<strong>{expected:,}</strong>" in page.text
    assert f'name="asking_price" value="{expected}"' in page.text
    assert f"Apply suggested price {expected:,} to" in page.text
    result = client.post(
        f"/sales/price-review/{listing_uuid}/price",
        data={"asking_price": str(expected)},
    )
    assert result.status_code == 200
    assert f'data-listing-uuid="{listing_uuid}"' not in result.text
    with session_factory() as session:
        listing = session.scalar(select(SaleListing).where(SaleListing.uuid == listing_uuid))
        assert listing.asking_price == expected
        assert listing.price_observation.total_price == expected
        assert 0 < expected < asking_price
