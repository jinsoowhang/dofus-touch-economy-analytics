from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from dofus_touch_economy.models import Item, SaleListing
from dofus_touch_economy.routers.web import _dashboard_chart
from dofus_touch_economy.services.dashboard import DashboardService

PACIFIC = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 9, 6, 2, tzinfo=UTC)


def test_dashboard_periods_profit_coverage_and_current_inventory(session, catalog_item) -> None:
    other = Item(display_name="Other Hat", normalized_name="other hat", identity_category="hat")
    session.add(other)
    session.flush()
    for item_id, sold_at, price, cost in [
        (catalog_item.id, datetime(2026, 8, 30, 6, 59, tzinfo=UTC), 50, 20),
        (catalog_item.id, datetime(2026, 8, 30, 7, tzinfo=UTC), 100, 80),
        (other.id, datetime(2026, 9, 6, 1, tzinfo=UTC), 200, 240),
        (catalog_item.id, datetime(2026, 9, 2, 12, tzinfo=UTC), 300, None),
        (catalog_item.id, NOW + timedelta(hours=1), 9_000, 1),
    ]:
        session.add(
            SaleListing(
                item_id=item_id,
                lot_quantity=1,
                asking_price=price,
                recipe_cost_at_sale=None if cost is None else Decimal(cost),
                selling_started_at=sold_at - timedelta(days=1),
                date_sold=sold_at,
            )
        )
    for price, started_at in [(1_000, NOW - timedelta(days=10)), (2_000, NOW)]:
        session.add(
            SaleListing(
                item_id=other.id, lot_quantity=1, asking_price=price, selling_started_at=started_at
            )
        )
    session.commit()

    report = DashboardService(session, "Dodge", display_timezone=PACIFIC, as_of=NOW).report(7)

    assert report.current.started_on == date(2026, 8, 30)
    assert report.current.ended_on == date(2026, 9, 5)
    assert report.previous.started_on == date(2026, 8, 23)
    assert report.previous.ended_on == date(2026, 8, 29)
    assert report.previous.profit == 30
    assert report.current.sold_count == 3
    assert report.current.revenue == 600
    assert report.current.cost == 320
    assert report.current.profit == -20
    assert report.current.covered_count == 2
    assert report.current.coverage == Decimal(2) / 3
    assert report.current.margin == Decimal(-20) / 300
    assert report.current.average_days_to_sell == 1
    assert len(report.daily) == 7
    by_day = {day.ended_on: day for day in report.daily}
    assert by_day[date(2026, 8, 30)].profit == 20
    assert by_day[date(2026, 8, 31)].profit == 0
    assert by_day[date(2026, 8, 31)].coverage is None
    assert by_day[date(2026, 9, 2)].profit is None
    assert by_day[date(2026, 9, 2)].revenue == 300
    assert by_day[date(2026, 9, 5)].profit == -40
    assert report.active_count == 2
    assert report.active_value == 3_000
    assert report.price_review_count == 0
    assert report.last_sold_at == datetime(2026, 9, 6, 1, tzinfo=UTC)
    assert [item.profit for item in report.profit_items] == [20, -40]
    assert report.profit_items[0].covered_count == 1
    assert report.profit_items[0].sold_count == 2


@pytest.mark.parametrize("days", [7, 30, 90])
def test_dashboard_empty_and_stale_history_does_not_move_window(session, catalog_item, days):
    service = DashboardService(session, "Dodge", display_timezone=PACIFIC, as_of=NOW)
    empty = service.report(days)
    assert len(empty.daily) == days
    assert empty.current.profit == 0
    assert empty.current.margin is None
    assert empty.current.coverage is None
    assert empty.last_sold_at is None
    assert empty.profit_items == ()
    session.add(
        SaleListing(
            item_id=catalog_item.id,
            lot_quantity=1,
            asking_price=500,
            selling_started_at=NOW - timedelta(days=400),
            date_sold=NOW - timedelta(days=399),
            recipe_cost_at_sale=100,
        )
    )
    session.commit()
    stale = service.report(days)
    assert stale.current == empty.current
    assert stale.last_sold_at == NOW - timedelta(days=399)


def test_dashboard_unknown_cost_is_not_zero_profit(session, catalog_item):
    session.add(
        SaleListing(
            item_id=catalog_item.id,
            lot_quantity=1,
            asking_price=500,
            selling_started_at=NOW - timedelta(days=1),
            date_sold=NOW,
        )
    )
    session.commit()
    report = DashboardService(session, "Dodge", as_of=NOW).report()
    assert report.current.revenue == 500
    assert report.current.profit is None
    assert report.current.cost is None
    assert report.current.margin is None
    assert report.current.coverage == 0
    assert report.profit_items == ()


def test_daily_profit_chart_separates_incomplete_subtotals_from_complete_losses(
    session, catalog_item
):
    for offset, price, cost in [(0, 100, 500), (0, 200, None), (1, 100, 150)]:
        session.add(
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=price,
                recipe_cost_at_sale=cost,
                selling_started_at=NOW - timedelta(days=3),
                date_sold=NOW - timedelta(days=offset),
            )
        )
    session.commit()
    report = DashboardService(session, "Dodge", as_of=NOW).report(7)
    chart = _dashboard_chart(report.daily, "profit")
    assert report.current.profit == -450
    assert report.daily[-1].profit == -400
    assert chart["points"][-1]["y"] > chart["zero_y"]
    assert len(chart["segments"]) == 6
    assert "1 of 2 sales" in chart["points"][-1]["coverage_label"]
    assert "-400 kamas" in chart["points"][-1]["coverage_label"]
    assert chart["points"][-2]["y"] > chart["zero_y"]
    assert chart["points"][-2]["label"] == "-50"
    assert chart["points"][-3]["y"] == chart["zero_y"]
    assert _dashboard_chart(report.daily, "revenue")["points"][-1]["label"] == "300"


def test_dashboard_filters_apply_to_both_periods_inventory_and_rankings(session, catalog_item):
    hat = Item(
        display_name="Synthetic Hat",
        normalized_name="synthetic hat",
        category="Hat",
        identity_category="hat",
    )
    session.add(hat)
    session.flush()
    for item in (catalog_item, hat):
        for offset in (0, 8):
            session.add(
                SaleListing(
                    item_id=item.id,
                    lot_quantity=1,
                    asking_price=100,
                    recipe_cost_at_sale=40,
                    selling_started_at=NOW - timedelta(days=20),
                    date_sold=NOW - timedelta(days=offset),
                )
            )
        session.add(
            SaleListing(
                item_id=item.id,
                lot_quantity=1,
                asking_price=500,
                selling_started_at=NOW - timedelta(days=20),
            )
        )
    session.commit()
    service = DashboardService(session, "Dodge", as_of=NOW)
    filtered = service.report(7, categories=(" HAT ",), item_query="  SYNTHETIC  ")
    assert filtered.current.sold_count == filtered.previous.sold_count == 1
    assert filtered.current.profit == filtered.previous.profit == 60
    assert filtered.current.revenue == 100
    assert filtered.active_count == filtered.price_review_count == 1
    assert filtered.active_value == 500
    assert [item.display_name for item in filtered.profit_items] == [hat.display_name]
    assert sum(day.sold_count for day in filtered.daily) == 1
    assert set(filtered.categories) == {"Hat", "Ore"}
    assert service.report(7, categories=("hat", "ore")).current.sold_count == 2
    empty = service.report(7, categories=("hat",), item_query="ore")
    assert empty.current.sold_count == empty.previous.sold_count == empty.active_count == 0
    assert empty.last_sold_at is None
    assert empty.profit_items == ()
    assert empty.categories == filtered.categories


def test_profit_line_connects_partial_days_but_never_invents_unknown_values(session, catalog_item):
    for offset, cost in [(0, 80), (0, None), (1, 50), (1, None), (2, None), (3, 20)]:
        session.add(
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100,
                recipe_cost_at_sale=cost,
                selling_started_at=NOW - timedelta(days=5),
                date_sold=NOW - timedelta(days=offset),
            )
        )
    session.commit()
    report = DashboardService(session, "Dodge", as_of=NOW).report(7)
    chart = _dashboard_chart(report.daily, "profit")
    assert chart["points"][-1]["label"] == "20"
    assert chart["points"][-2]["label"] == "50"
    assert chart["points"][-3]["y"] is None
    left, right = chart["points"][-2:]
    assert chart["segments"][-1] == f"{left['x']},{left['y']} {right['x']},{right['y']}"
    assert len(chart["segments"]) == 4
