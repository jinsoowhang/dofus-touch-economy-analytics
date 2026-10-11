import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from html import unescape
from urllib.parse import parse_qs, urlparse

import pytest

from dofus_touch_economy.models import SaleListing
from dofus_touch_economy.routers import web
from dofus_touch_economy.services.sales import DailySalesTotal


@pytest.mark.parametrize("period", [None, "7", "14", "30", "60", "90", "historical"])
def test_chart_range_uses_inclusive_pacific_days_and_selected_totals(
    client, session_factory, catalog_item, monkeypatch, period
):
    now = datetime(2026, 10, 11, 2, tzinfo=UTC)  # Still October 10 in Pacific Time.

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz)

    monkeypatch.setattr(web, "datetime", FixedDatetime)
    activity = datetime(2026, 10, 10, 8, tzinfo=UTC)
    offsets = (0, 6, 7, 13, 14, 29, 30, 59, 60, 89, 90)
    with session_factory() as session:
        session.add_all(
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100 + offset,
                selling_started_at=activity - timedelta(days=offset),
                date_sold=activity - timedelta(days=offset),
                recipe_cost_at_sale=Decimal(200),
            )
            for offset in offsets
        )
        session.commit()

    response = client.get("/sales", params={} if period is None else {"chart_range": period})
    assert response.status_code == 200
    chart = response.text.split("<h2>Sales Over Time</h2>", maxsplit=1)[1]
    selected = period or "7"
    expected_offsets = [
        offset for offset in offsets if selected == "historical" or offset < int(selected)
    ]
    expected_dates = {
        (activity.astimezone(web.PACIFIC_TIME).date() - timedelta(days=offset)).isoformat()
        for offset in expected_offsets
    }
    assert set(re.findall(r"All Sales on ([\d-]+):", chart)) == expected_dates
    revenue = sum(100 + offset for offset in expected_offsets)
    cost = 200 * len(expected_offsets)
    assert f"<span>Total Sales</span><strong>{revenue:,}</strong>" in chart
    assert f"<span>Total Cost</span><strong>{cost:,}</strong>" in chart
    assert "<span>Sold Today</span><strong>100</strong>" in chart
    assert "<span>Profit Today</span><strong>-100</strong>" in chart
    assert "show today, 2026-10-10." in chart
    assert "Pacific" not in response.text
    if selected != "historical":
        daily_table = chart.split('class="sales-data-table"', maxsplit=1)[1].split("</table>")[0]
        dates = re.findall(r"<td>([\d-]+)</td>", daily_table)
        assert len(dates) == int(selected)
        assert dates[-1] == "2026-10-10"
        assert (
            dates[0]
            == (
                now.astimezone(web.PACIFIC_TIME).date() - timedelta(days=int(selected) - 1)
            ).isoformat()
        )
    navigation = chart.split('aria-label="Sales Over Time period"', maxsplit=1)[1].split("</nav>")[
        0
    ]
    ranges = re.findall(r'<a href="([^"]+)"([^>]*)>([^<]+)</a>', navigation)
    assert [label for _url, _attributes, label in ranges] == [
        "Last 7 days",
        "Last 14 days",
        "Last 30 days",
        "Last 60 days",
        "Last 90 days",
        "Historical",
    ]
    assert [
        parse_qs(urlparse(unescape(url)).query)["chart_range"][0]
        for url, attributes, _label in ranges
        if 'aria-current="page"' in attributes
    ] == [selected]


def test_chart_range_survives_filters_sorting_pagination_and_sale_edits(
    client, session_factory, catalog_item
):
    with session_factory() as session:
        listings = [
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100,
                selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
            )
            for _ in range(51)
        ]
        session.add_all(listings)
        session.commit()
        listing_uuid = listings[0].uuid

    parameters = {"chart_range": "60", "item_query": "Synthetic", "active_sort": "name"}
    response = client.get("/sales", params=parameters)
    assert response.status_code == 200
    assert 'name="chart_range" value="60"' in response.text
    assert 'href="/sales?chart_range=60">Clear filters</a>' in response.text
    links = [unescape(link) for link in re.findall(r'href="([^"]+)"', response.text)]
    links = [link for link in links if urlparse(link).fragment == "currently-selling"]
    assert any(parse_qs(urlparse(link).query).get("active_page") == ["2"] for link in links)
    for link in links:
        query = parse_qs(urlparse(link).query)
        assert query["chart_range"] == ["60"]
        assert query["item_query"] == ["Synthetic"]
    for link in re.findall(r'href="([^"]+#sales-over-time)"', response.text):
        query = parse_qs(urlparse(unescape(link)).query)
        assert query["item_query"] == ["Synthetic"]
        assert query["active_sort"] == ["name"]
    edited = client.post(
        f"/sales/{listing_uuid}/sold",
        params=parameters,
        follow_redirects=False,
    )
    assert edited.status_code == 303
    assert parse_qs(urlparse(edited.headers["location"]).query)["chart_range"] == ["60"]


def test_empty_range_keeps_longer_range_options(client, session_factory, catalog_item):
    with session_factory() as session:
        session.add(
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=100,
                selling_started_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()
    response = client.get("/sales")
    assert response.status_code == 200
    assert 'class="sales-chart"' not in response.text
    assert "No listing or sales activity in this period" in response.text
    assert ">Historical</a>" in response.text
    historical = client.get("/sales", params={"chart_range": "historical"})
    assert 'class="sales-chart"' in historical.text
    assert client.get("/sales", params={"chart_range": "8"}).status_code == 422


@pytest.mark.parametrize("days", [7, None])
def test_listed_line_breaks_on_empty_and_absent_calendar_dates(monkeypatch, days):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 11, 2, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(web, "datetime", FixedDatetime)
    # October 6 has no recorded activity; October 8 has sales but no listings.
    totals = [
        DailySalesTotal(
            activity_on=datetime(2026, 10, day).date(),
            total_listed_price=100 if day != 8 else 0,
            total_price=80,
            cost_covered_price=80,
            total_cost=Decimal(30),
            total_profit=Decimal(50),
            listed_count=int(day != 8),
            listed_priced_count=int(day != 8),
            sold_count=1,
            priced_count=1,
            costed_count=1,
            profit_count=1,
        )
        for day in (4, 5, 7, 8, 9, 10)
    ]
    chart = web._sales_chart(totals, current_listed_price=100, days=days)
    listed, sales, cost, profit = chart["series"]
    coordinates = {point["date"]: f"{point['x']},{point['y']}" for point in listed["points"]}
    assert listed["segments"] == [
        " ".join(coordinates[f"2026-10-{day:02}"] for day in group)
        for group in ((4, 5), (7,), (9, 10))
    ]
    assert chart["total_listed_price_label"] == "500"
    assert len(listed["points"]) == 5
    for series in (sales, cost, profit):
        assert len(series["segments"]) == 1
