from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

from dofus_touch_economy.models import Item, SaleListing
from dofus_touch_economy.repositories.sales import SalesRepository
from dofus_touch_economy.routers import web


@pytest.fixture
def rendered(client, monkeypatch):
    # GZip middleware omits Starlette's test-only template debug messages.
    contexts = []
    original = web.templates.TemplateResponse

    def capture(*args, **kwargs):
        response = original(*args, **kwargs)
        contexts.append(response.context)
        return response

    monkeypatch.setattr(web.templates, "TemplateResponse", capture)

    def request(method, url, **kwargs):
        contexts.clear()
        response = client.request(method, url, **kwargs)
        response.context = contexts[-1] if contexts else {}
        return response

    return request


@pytest.fixture
def activity_history(session_factory, catalog_item):
    with session_factory() as session:
        rows = [
            SaleListing(
                item_id=catalog_item.id,
                lot_quantity=1,
                asking_price=price,
                selling_started_at=datetime(2026, 8, 1, tzinfo=UTC),
                date_sold=datetime(2026, 8, 2, tzinfo=UTC) if sold else None,
                recipe_cost_at_sale=Decimal(10) if sold else None,
            )
            for sold in (False, True)
            for price in range(1, 112)
        ]
        session.add_all(rows)
        session.commit()
        return rows


def test_activity_pages_preserve_full_totals_and_sort_before_slicing(rendered, activity_history):
    first = rendered("GET", "/sales", params={"active_sort": "price", "sold_sort": "profit"})
    second = rendered(
        "GET",
        "/sales",
        params={
            "active_sort": "price",
            "sold_sort": "profit",
            "active_page": 2,
            "sold_page": 3,
        },
    )
    assert first.status_code == second.status_code == 200
    context = second.context
    assert context["active_count"] == context["sold_count"] == 111
    assert [row.asking_price for row in context["active_sales"]] == list(range(61, 11, -1))
    assert [row.profit for row in context["sold_sales"]] == list(range(1, -10, -1))
    assert context["active_total_price"] == sum(range(1, 112))
    assert context["sales_chart"] == first.context["sales_chart"]
    assert second.text.count('class="active-sale-checkbox"') == 50
    assert "Bulk selection applies to this page only." in second.text
    assert "101–111 of 111" in second.text
    active_section = second.text.split('id="currently-selling"', maxsplit=1)[1].split(
        'id="sold-history"', maxsplit=1
    )[0]
    assert active_section.count('aria-label="Currently Selling pages"') == 2
    footer = active_section.split("</table>", maxsplit=1)[1]
    assert "Page 2 of 3" in footer
    assert ">Previous</a>" in footer
    assert ">Next</a>" in footer
    for column in context["active_sort_columns"]:
        params = parse_qs(urlsplit(column["url"]).query)
        assert "active_page" not in params
        assert params["sold_page"] == ["3"]
    for column in context["sold_sort_columns"]:
        params = parse_qs(urlsplit(column["url"]).query)
        assert "sold_page" not in params
        assert params["active_page"] == ["2"]
    next_params = parse_qs(urlsplit(context["active_pagination"]["next"]).query)
    assert next_params["active_page"] == ["3"]
    assert next_params["sold_page"] == ["3"]


def test_activity_filters_precede_pagination_and_leave_chart_unchanged(rendered, activity_history):
    baseline = rendered("GET", "/sales")
    filtered = rendered(
        "GET",
        "/sales",
        params={
            "status": "sold",
            "min_profit": "50",
            "sold_sort": "profit",
            "sold_direction": "asc",
            "sold_page": 2,
        },
    )
    assert filtered.status_code == 200
    assert filtered.context["sold_count"] == 52
    assert [row.profit for row in filtered.context["sold_sales"]] == [100, 101]
    assert filtered.context["active_sales"] == []
    assert filtered.context["sales_chart"] == baseline.context["sales_chart"]
    assert "min_profit=50" in filtered.context["sold_pagination"]["previous"]


def test_activity_clamps_pages_and_preserves_view_on_mutation(rendered, activity_history):
    response = rendered("GET", "/sales?active_page=999&sold_page=999")
    assert response.context["sort_state"].active_page == 3
    assert response.context["sort_state"].sold_page == 3
    listing = response.context["active_sales"][0]
    changed = rendered(
        "POST",
        f"/sales/{listing.uuid}/delete?active_page=3&sold_page=2&active_sort=price",
        follow_redirects=False,
    )
    assert changed.status_code == 303
    parameters = parse_qs(urlsplit(changed.headers["location"]).query)
    assert parameters["active_page"] == ["3"]
    assert parameters["sold_page"] == ["2"]
    assert parameters["active_sort"] == ["price"]


@pytest.mark.parametrize("parameter", ["active_page", "sold_page"])
def test_activity_rejects_invalid_pages(rendered, parameter):
    assert rendered("GET", "/sales", params={parameter: 0}).status_code == 422
    empty = rendered("GET", "/sales", params={parameter: 99})
    assert empty.status_code == 200
    assert getattr(empty.context["sort_state"], parameter) == 1


def test_activity_reads_sold_history_only_once(rendered, activity_history):
    original = SalesRepository.sold
    calls = []

    def tracked(repository):
        calls.append(True)
        return original(repository)

    with patch.object(SalesRepository, "sold", tracked):
        assert rendered("GET", "/sales").status_code == 200
    assert len(calls) == 1


def test_item_choices_remain_bounded_and_activity_skips_picker_queries(
    rendered,
    session_factory,
    catalog_item,
):
    with session_factory() as session:
        session.add_all(
            [
                Item(
                    display_name=f"Alpha {index:03}",
                    normalized_name=f"alpha {index:03}",
                    category="Hat",
                    identity_category="hat",
                )
                for index in range(60)
            ]
        )
        session.add_all(
            [
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=price,
                    selling_started_at=datetime(2026, 8, 1, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 2, tzinfo=UTC) if sold else None,
                )
                for price, sold in [(100, True), (300, True), (999, False)]
            ]
        )
        session.commit()
    initial = rendered("GET", "/sales")
    assert "item_choices" not in initial.context
    assert "Add an Item to Sell" not in initial.text
    bounded = rendered("GET", "/sales/item-choices")
    assert len(bounded.context["item_choices"]) == 25
    choices = rendered("GET", "/sales/item-choices", params={"q": "synthetic", "category": "ore"})
    assert choices.status_code == 200
    assert [item.uuid for item in choices.context["item_choices"]] == [catalog_item.uuid]
    assert 'data-suggested-price="200"' in choices.text
    assert 'data-sold-count="2"' in choices.text
    assert "<html" not in choices.text
    mismatch = rendered("GET", "/sales/item-choices?q=synthetic&category=hat")
    assert mismatch.context["item_choices"] == []
    assert "No matching items" in mismatch.text
    invalid = rendered(
        "POST",
        "/sales",
        data={
            "q": "synthetic",
            "item_uuid": str(catalog_item.uuid),
            "asking_price": "oops",
        },
    )
    assert invalid.status_code == 422
    assert invalid.context["form_values"]["q"] == "synthetic"
    assert invalid.context["form_values"]["asking_price"] == "oops"
    outside = rendered(
        "POST", "/sales", data={"item_uuid": str(catalog_item.uuid), "asking_price": "0"}
    )
    assert outside.status_code == 422
    assert "item_choices" not in outside.context
    assert rendered("GET", "/sales/item-choices", params={"q": "x" * 201}).status_code == 422
