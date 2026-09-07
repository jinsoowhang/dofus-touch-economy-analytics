from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event, func, select

from dofus_touch_economy.models import Item, PriceObservation, SaleListing
from dofus_touch_economy.services.home import HomeService
from dofus_touch_economy.services.sales import SalesService

PACIFIC = ZoneInfo("America/Los_Angeles")


@pytest.mark.parametrize(
    "weekday, expected_focus",
    [
        (0, "price-priorities"),
        (1, None),
        (2, None),
        (3, None),
        (4, "relist"),
        (5, None),
        (6, None),
    ],
)
def test_weekly_rotation_keeps_daily_order_and_uses_pacific_date(session, weekday, expected_focus):
    # UTC is already the following day; the routine still belongs to the Pacific day.
    as_of = datetime(2026, 9, 8, 1, tzinfo=UTC) + timedelta(days=weekday)
    report = HomeService(session, display_timezone=PACIFIC).report(as_of=as_of)
    assert report.today.weekday() == weekday
    assert [task.key for task in report.daily_tasks] == [
        "sales",
        "restock",
        "opportunities",
        "dashboard",
    ]
    assert (report.focus.key if report.focus else None) == expected_focus
    assert len(report.week) == 7
    assert [(day.weekday(), task.key) for day, task in report.week if task] == [
        (0, "price-priorities"),
        (4, "relist"),
    ]
    assert report.next_day_at.astimezone(PACIFIC).hour == 0
    assert report.next_day_at.date() == report.today + timedelta(days=1)
    assert report.snapshot.sold_today == 0
    assert report.snapshot.active_count == 0
    assert report.snapshot.last_sold_at is None


def test_home_snapshot_counts_known_revenue_inventory_and_pacific_review_days(
    session, catalog_item
):
    as_of = datetime(2026, 3, 15, 0, 1, tzinfo=PACIFIC).astimezone(UTC)
    day_start = datetime(2026, 3, 15, tzinfo=PACIFIC).astimezone(UTC)
    old = as_of - timedelta(days=30)
    out = Item(
        display_name="Sold Out Hat",
        normalized_name="sold out hat",
        category="Hat",
        identity_category="hat",
    )
    session.add(out)
    session.flush()
    relist = PriceObservation(
        item_id=catalog_item.id,
        lot_quantity=1,
        total_price=800,
        observed_at=as_of,
        market_context="Dodge",
        source="manual",
    )
    session.add(relist)
    session.flush()
    session.add_all(
        [
            SaleListing(
                item_id=catalog_item.id, lot_quantity=1, asking_price=1000, selling_started_at=old
            ),
            SaleListing(
                item_id=catalog_item.id, lot_quantity=1, asking_price=None, selling_started_at=old
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=800,
                selling_started_at=old,
                price_observation_id=relist.id,
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=1,
                selling_started_at=datetime(2026, 3, 8, 23, 59, tzinfo=PACIFIC).astimezone(UTC),
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=600,
                selling_started_at=datetime(2026, 3, 9, 0, 1, tzinfo=PACIFIC).astimezone(UTC),
            ),
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=300,
                selling_started_at=old,
                date_sold=day_start - timedelta(seconds=1),
            ),
            SaleListing(
                item_id=out.id,
                lot_quantity=1,
                asking_price=400,
                selling_started_at=old,
                date_sold=day_start,
            ),
            SaleListing(
                item_id=out.id,
                lot_quantity=1,
                asking_price=None,
                selling_started_at=old,
                date_sold=as_of,
            ),
            SaleListing(
                item_id=out.id,
                lot_quantity=1,
                asking_price=99999,
                selling_started_at=old,
                date_sold=as_of + timedelta(seconds=1),
            ),
        ]
    )
    session.commit()
    report = HomeService(session, display_timezone=PACIFIC).report(as_of=as_of)
    snapshot = report.snapshot
    assert snapshot.active_count == 5
    assert snapshot.active_value == 2401 and snapshot.unpriced_active_count == 1
    assert snapshot.sold_today == 2 and snapshot.revenue_today == 400
    assert snapshot.unpriced_sold_today == 1 and snapshot.last_sold_at == as_of
    assert snapshot.out_of_stock_count == 1
    assert snapshot.price_review_count == 3
    assert snapshot.price_review_count == len(
        SalesService(session, "Dodge").price_review_listings(as_of=as_of, display_timezone=PACIFIC)
    )
    # Replenishing an out-of-stock item clears the Home backlog too.
    session.add(
        SaleListing(item_id=out.id, lot_quantity=1, asking_price=400, selling_started_at=as_of)
    )
    session.commit()
    assert (
        HomeService(session, display_timezone=PACIFIC)
        .report(as_of=as_of)
        .snapshot.out_of_stock_count
        == 0
    )


def test_home_page_is_read_only_and_has_small_query_count(client, session_factory, catalog_item):
    with session_factory() as session:
        session.add(
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=1000,
                selling_started_at=datetime.now(UTC) - timedelta(days=10),
            )
        )
        session.commit()
        listing_count = session.scalar(select(func.count()).select_from(SaleListing))
        price_count = session.scalar(select(func.count()).select_from(PriceObservation))
    statements = []
    engine = session_factory.kw["bind"]

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get("/")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert len(statements) == 5
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert "Home · Dofus Touch Economy" in response.text
    assert 'href="/" class="site-tab is-active" aria-current="page"' in response.text
    assert 'data-task-key="sales"' in response.text
    assert 'data-task-key="dashboard"' in response.text
    assert 'id="home-storage-error" role="status" hidden' in response.text
    assert 'href="/price-priorities"' in response.text
    assert 'href="/sales/price-review"' in response.text
    assert "Checkmarks stay in this browser" in response.text
    assert 'src="/static/home.js?v=' in response.text
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SaleListing)) == listing_count
        assert session.scalar(select(func.count()).select_from(PriceObservation)) == price_count


def test_home_handles_dst_reset_time(session):
    report = HomeService(session, display_timezone=PACIFIC).report(
        as_of=datetime(2026, 11, 1, 0, 0, tzinfo=PACIFIC)
    )
    assert report.next_day_at.astimezone(UTC) == datetime(2026, 11, 2, 8, tzinfo=UTC)
