import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from dofus_touch_economy.bigquery_sync import BigQuerySyncManager
from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item, Recipe, SaleListing
from dofus_touch_economy.schemas import PriceObservationCreate
from dofus_touch_economy.services.catalog import CatalogService
from dofus_touch_economy.services.pricing import PriceService

DEFAULT_SALES_QUERY = "active_sort=started&active_direction=desc&sold_sort=sold&sold_direction=desc"


def test_root_redirects_to_items(client) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/items"


def test_rejects_untrusted_host(client) -> None:
    response = client.get("/items", headers={"host": "example.com"})

    assert response.status_code == 400


def test_item_search_renders_matching_synthetic_item(client, catalog_item) -> None:
    response = client.get("/items", params={"q": "ore"})

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert "Dofus Touch Economy" in response.text
    assert catalog_item.display_name in response.text
    assert str(catalog_item.uuid) in response.text


def test_item_search_has_active_item_navigation(client) -> None:
    response = client.get("/items")

    assert response.status_code == 200
    assert 'aria-label="Primary navigation"' in response.text
    assert '<details class="site-menu">' in response.text
    assert "<span>Item</span>" in response.text
    assert 'class="site-submenu" role="group" aria-label="Item navigation"' in (response.text)
    assert 'class="site-submenu-link is-active"' in response.text
    assert 'aria-current="page"' in response.text
    assert ">Item Search</a>" in response.text
    assert 'href="/sales"' in response.text
    assert 'href="/recipes"' in response.text


def test_sales_page_has_active_tab_and_alphabetical_item_choices(
    client, session_factory, catalog_item
) -> None:
    with session_factory() as session:
        session.add(
            Item(
                display_name="Alpha Item",
                normalized_name="alpha item",
                category="hat",
                identity_category="",
            )
        )
        session.commit()

    response = client.get("/sales")

    assert response.status_code == 200
    assert ">Sales</a>" in response.text
    assert 'class="site-tab is-active"' in response.text
    assert 'aria-current="page"' in response.text
    assert "Currently Selling" in response.text
    assert "Sold History" in response.text
    assert "Alpha Item — Hat" in response.text
    assert response.text.index("Alpha Item") < response.text.index(catalog_item.display_name)


def test_sales_category_filter_marks_item_options_and_loads_local_script(
    client,
    session_factory,
) -> None:
    with session_factory() as session:
        session.add_all(
            [
                Item(
                    display_name="Alpha Ring",
                    normalized_name="alpha ring",
                    category="Ring",
                    identity_category="ring",
                ),
                Item(
                    display_name="Zeta Hat",
                    normalized_name="zeta hat",
                    category="Hat",
                    identity_category="hat",
                ),
            ]
        )
        session.commit()

    response = client.get("/sales")
    script = client.get("/static/sales.js")

    assert response.status_code == 200
    assert '<label for="sale-category">Category (Optional)</label>' in response.text
    assert 'value="ring"' in response.text
    assert 'data-category="ring"' in response.text
    assert 'data-category="hat"' in response.text
    assert '<script src="/static/sales.js" defer></script>' in response.text
    assert script.status_code == 200
    assert 'categorySelect.addEventListener("change", filterItems)' in script.text
    assert "moveItemToTop(matchingItem)" in script.text
    assert "updateSalePriceSuggestion(true)" in script.text
    assert "salePriceInput.value = suggestedPrice" in script.text
    assert "No completed sales for this item yet." in script.text
    assert 'input.addEventListener("blur", savePrice)' in script.text
    assert 'activeSalesSelectAll.addEventListener("change"' in script.text
    assert "window.sessionStorage.setItem(salesScrollStorageKey" in script.text
    assert "window.scrollTo(0, scrollPosition)" in script.text
    assert "Delete the selected sales rows? This cannot be undone." in script.text


def test_sales_item_choice_suggests_median_completed_sale_price(
    client,
    session_factory,
    catalog_item,
) -> None:
    with session_factory() as session:
        session.add_all(
            [
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=100_000,
                    selling_started_at=datetime(2026, 8, 18, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 19, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=300_000,
                    selling_started_at=datetime(2026, 8, 20, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 21, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=999_000,
                    selling_started_at=datetime(2026, 8, 21, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

    response = client.get("/sales")

    assert response.status_code == 200
    assert f'value="{catalog_item.uuid}"' in response.text
    assert 'data-suggested-price="200,000"' in response.text
    assert 'data-sold-count="2"' in response.text
    assert (
        '<p id="sale-price-suggestion" class="sale-price-suggestion" aria-live="polite" hidden></p>'
    ) in response.text


def test_sales_page_adds_and_completes_a_listing(client, session_factory, catalog_item) -> None:
    created = client.post(
        "/sales",
        data={
            "item_uuid": str(catalog_item.uuid),
            "asking_price": "50,000",
        },
        follow_redirects=False,
    )

    assert created.status_code == 303
    assert created.headers["location"] == f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-added"
    active_page = client.get(created.headers["location"])
    assert "Sale listing has been added." in active_page.text
    assert catalog_item.display_name in active_page.text
    assert 'value="50,000"' in active_page.text
    assert "1 active · Total Price: 50,000" in active_page.text
    assert f'aria-label="Duplicate sale row for {catalog_item.display_name}"' in active_page.text
    assert f'aria-label="Mark {catalog_item.display_name} as sold"' in active_page.text
    assert '<span aria-hidden="true">⧉</span>' in active_page.text
    assert '<span aria-hidden="true">✓</span>' in active_page.text
    assert ">Duplicate</button>" not in active_page.text
    assert ">Mark sold</button>" not in active_page.text
    assert active_page.text.count('class="collapsible-section" open') == 4
    assert active_page.text.index("Add an Item to Sell") < active_page.text.index("Filter Items")
    assert active_page.text.index("Filter Items") < active_page.text.index("Currently Selling")
    assert "Filter Sales" not in active_page.text
    filter_summary = active_page.text.split("<h2>Filter Items</h2>", maxsplit=1)[0]
    assert filter_summary.rsplit("<details", maxsplit=1)[1].startswith(
        ' class="collapsible-section">'
    )
    assert '<button type="submit">Update</button>' not in active_page.text
    assert 'data-initial-value="50,000"' in active_page.text
    assert "Press Enter or leave the field to save." in active_page.text
    assert "Lot quantity" not in active_page.text
    assert 'name="lot_quantity"' not in active_page.text
    assert "Delete this sales row? This cannot be undone." in active_page.text
    assert f'aria-label="Delete sale row for {catalog_item.display_name}"' in active_page.text
    assert 'id="active-sales-bulk-form"' in active_page.text
    assert 'id="select-all-active-sales"' in active_page.text

    with session_factory() as session:
        listing = session.scalar(select(SaleListing))
        assert listing is not None
        assert listing.price_observation is not None
        assert listing.price_observation.total_price == 50_000
        assert listing.price_observation.market_context == "Dodge"
        listing_uuid = listing.uuid
    assert f'value="{listing_uuid}"' in active_page.text
    item_page = client.get(f"/items/{catalog_item.uuid}")
    assert "<summary><h2>Current Price</h2></summary>" in item_page.text
    assert 'name="current_price"' in item_page.text
    assert 'value="50,000"' in item_page.text
    assert ">50,000</td>" in item_page.text
    completed = client.post(
        f"/sales/{listing_uuid}/sold",
        follow_redirects=False,
    )

    assert completed.status_code == 303
    assert completed.headers["location"] == (
        f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-sold#currently-selling"
    )
    sold_page = client.get(completed.headers["location"])
    assert "Item has been marked as sold." in sold_page.text
    assert "0 active" in sold_page.text
    assert "1 sold" in sold_page.text
    assert "Date Sold" in sold_page.text
    assert (
        f'action="/sales/{listing_uuid}/reopen?{DEFAULT_SALES_QUERY.replace("&", "&amp;")}"'
        in sold_page.text
    )
    assert f'aria-label="Return {catalog_item.display_name} to Currently Selling"' in sold_page.text
    assert ">↩</button>" in sold_page.text

    reopened = client.post(
        f"/sales/{listing_uuid}/reopen",
        follow_redirects=False,
    )

    assert reopened.status_code == 303
    assert reopened.headers["location"] == (f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-reopened")
    reopened_page = client.get(reopened.headers["location"])
    assert "Item has been returned to Currently Selling." in reopened_page.text
    assert "1 active" in reopened_page.text
    assert "0 sold" in reopened_page.text


def test_sales_page_requires_an_asking_price(client, catalog_item) -> None:
    response = client.post(
        "/sales",
        data={"item_uuid": str(catalog_item.uuid), "asking_price": ""},
    )

    assert response.status_code == 422
    assert "Input should be a valid integer" in response.text
    assert '<label for="sale-asking-price">Sale Price</label>' in response.text
    assert 'name="asking_price"' in response.text
    assert "required" in response.text


def test_recorded_item_price_does_not_appear_as_an_active_sale(client, catalog_item) -> None:
    response = client.post(
        f"/items/{catalog_item.uuid}/price-observations",
        data={
            "total_price": "125000",
            "observed_at": "2026-08-21T12:00:00Z",
            "note": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    sales = client.get("/sales")
    assert 'value="125,000"' not in sales.text
    assert "0 active" in sales.text


def test_sales_page_duplicates_and_reprices_a_listing(
    client,
    session_factory,
    catalog_item,
) -> None:
    client.post(
        "/sales",
        data={
            "item_uuid": str(catalog_item.uuid),
            "asking_price": "50000",
        },
    )
    with session_factory() as session:
        original_uuid = session.scalar(select(SaleListing.uuid))

    duplicated = client.post(
        f"/sales/{original_uuid}/duplicate",
        follow_redirects=False,
    )

    assert duplicated.status_code == 303
    assert duplicated.headers["location"] == (
        f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-duplicated"
    )
    with session_factory() as session:
        listings = list(session.scalars(select(SaleListing).order_by(SaleListing.id)))
    assert len(listings) == 2
    assert listings[0].asking_price == listings[1].asking_price == 50_000
    assert listings[0].lot_quantity == listings[1].lot_quantity == 1

    repriced = client.post(
        f"/sales/{listings[1].uuid}/price",
        data={"asking_price": "45,000"},
        follow_redirects=False,
    )

    assert repriced.status_code == 303
    assert repriced.headers["location"] == (
        f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-price-updated"
    )
    page = client.get(repriced.headers["location"])
    assert "Sale price has been updated." in page.text
    assert 'value="50,000"' in page.text
    assert 'value="45,000"' in page.text
    assert "2 active" in page.text


def test_sales_page_validates_repriced_value(client, session_factory, catalog_item) -> None:
    client.post(
        "/sales",
        data={
            "item_uuid": str(catalog_item.uuid),
            "asking_price": "1000",
        },
    )
    with session_factory() as session:
        listing_uuid = session.scalar(select(SaleListing.uuid))

    response = client.post(
        f"/sales/{listing_uuid}/price",
        data={"asking_price": "0"},
    )

    assert response.status_code == 422
    assert "Input should be greater than 0" in response.text


def test_sales_page_deletes_a_listing_after_confirmation(
    client,
    session_factory,
    catalog_item,
) -> None:
    client.post(
        "/sales",
        data={"item_uuid": str(catalog_item.uuid), "asking_price": "1000"},
    )
    with session_factory() as session:
        listing_uuid = session.scalar(select(SaleListing.uuid))

    page = client.get("/sales")
    escaped_query = DEFAULT_SALES_QUERY.replace("&", "&amp;")
    assert f'action="/sales/{listing_uuid}/delete?{escaped_query}"' in page.text
    assert "return window.confirm('Delete this sales row? This cannot be undone.')" in page.text

    response = client.post(
        f"/sales/{listing_uuid}/delete",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-deleted"
    deleted_page = client.get(response.headers["location"])
    assert "Sale listing has been deleted." in deleted_page.text
    assert "0 active" in deleted_page.text
    with session_factory() as session:
        assert session.scalar(select(SaleListing.id)) is None


def test_sales_page_bulk_marks_sold_and_deletes_selected_rows(
    client,
    session_factory,
    catalog_item,
) -> None:
    for asking_price in (1_000, 2_000, 3_000):
        client.post(
            "/sales",
            data={"item_uuid": str(catalog_item.uuid), "asking_price": str(asking_price)},
        )
    with session_factory() as session:
        listing_uuids = list(session.scalars(select(SaleListing.uuid).order_by(SaleListing.id)))

    page = client.get("/sales")
    escaped_query = DEFAULT_SALES_QUERY.replace("&", "&amp;")
    assert f'action="/sales/bulk?{escaped_query}"' in page.text
    assert page.text.count('class="active-sale-checkbox"') == 3
    assert 'aria-label="Select all currently selling rows"' in page.text
    assert "Mark selected sold" in page.text
    assert "Delete selected" in page.text
    assert page.text.count("data-preserve-scroll") == 13

    sold = client.post(
        "/sales/bulk",
        data={
            "action": "mark_sold",
            "listing_uuid": [str(listing_uuids[0]), str(listing_uuids[1])],
        },
        follow_redirects=False,
    )

    assert sold.status_code == 303
    assert sold.headers["location"] == (
        f"/sales?{DEFAULT_SALES_QUERY}&notice=listings-sold&count=2#currently-selling"
    )
    sold_page = client.get(sold.headers["location"])
    assert "2 selected items have been marked as sold." in sold_page.text
    assert "1 active" in sold_page.text
    assert "2 sold" in sold_page.text

    deleted = client.post(
        "/sales/bulk",
        data={"action": "delete", "listing_uuid": str(listing_uuids[2])},
        follow_redirects=False,
    )

    assert deleted.status_code == 303
    assert deleted.headers["location"] == (
        f"/sales?{DEFAULT_SALES_QUERY}&notice=listings-deleted&count=1#currently-selling"
    )
    deleted_page = client.get(deleted.headers["location"])
    assert "1 selected listing has been deleted." in deleted_page.text
    assert "0 active" in deleted_page.text
    assert "2 sold" in deleted_page.text


def test_sales_page_bulk_action_requires_a_selection(client, catalog_item) -> None:
    client.post(
        "/sales",
        data={"item_uuid": str(catalog_item.uuid), "asking_price": "1000"},
    )

    response = client.post("/sales/bulk", data={"action": "mark_sold"})

    assert response.status_code == 422
    assert "Select at least one Currently Selling row and choose a bulk action." in response.text
    assert "1 active" in response.text


def test_sales_tables_sort_independently_and_show_directions(
    client,
    session_factory,
    catalog_item,
) -> None:
    with session_factory() as session:
        alpha = Item(
            display_name="Alpha Hat",
            normalized_name="alpha hat",
            category="Hat",
            identity_category="hat",
        )
        session.add(alpha)
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
                    item_id=alpha.id,
                    lot_quantity=1,
                    asking_price=300,
                    selling_started_at=datetime(2026, 8, 21, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=400,
                    selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 23, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=alpha.id,
                    lot_quantity=1,
                    asking_price=200,
                    selling_started_at=datetime(2026, 8, 24, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 25, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

    response = client.get(
        "/sales",
        params={
            "active_sort": "price",
            "active_direction": "desc",
            "sold_sort": "name",
            "sold_direction": "asc",
        },
    )

    assert response.status_code == 200
    assert response.text.count('aria-sort="descending"') == 1
    assert response.text.count('aria-sort="ascending"') == 1
    assert '<span class="sort-arrow" aria-hidden="true">▼</span>' in response.text
    assert '<span class="sort-arrow" aria-hidden="true">▲</span>' in response.text
    assert (
        "active_sort=price&amp;active_direction=asc&amp;sold_sort=name&amp;"
        "sold_direction=asc#currently-selling"
    ) in response.text
    assert (
        "active_sort=price&amp;active_direction=desc&amp;sold_sort=sold&amp;"
        "sold_direction=desc#sold-history"
    ) in response.text
    assert '<details id="sold-history" class="collapsible-section" open>' in response.text
    active_section, sold_section = response.text.split("<h2>Sold History</h2>")
    active_section = active_section.split("<h2>Currently Selling</h2>", maxsplit=1)[1]
    assert active_section.index("Alpha Hat") < active_section.index(catalog_item.display_name)
    assert sold_section.index("Alpha Hat") < sold_section.index(catalog_item.display_name)


def test_sales_actions_preserve_both_table_sort_settings(client, catalog_item) -> None:
    sort_parameters = {
        "active_sort": "price",
        "active_direction": "asc",
        "sold_sort": "name",
        "sold_direction": "desc",
    }

    response = client.post(
        "/sales",
        params=sort_parameters,
        data={"item_uuid": str(catalog_item.uuid), "asking_price": "1000"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/sales?active_sort=price&active_direction=asc&sold_sort=name&"
        "sold_direction=desc&notice=listing-added"
    )
    page = client.get(response.headers["location"])
    assert (
        "active_sort=price&amp;active_direction=asc&amp;sold_sort=name&amp;sold_direction=desc"
    ) in page.text
    assert 'aria-sort="ascending"' in page.text


def test_sales_filters_render_matching_status_and_persist_in_links(
    client,
    session_factory,
    catalog_item,
) -> None:
    with session_factory() as session:
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
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=500,
                    selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 23, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

    parameters = {
        "item_query": "alpha",
        "category": "hat",
        "status": "active",
        "min_price": "100",
        "max_price": "200",
        "date_from": "2026-08-21",
        "date_to": "2026-08-21",
    }
    response = client.get("/sales", params=parameters)

    assert response.status_code == 200
    assert "Filters applied" in response.text
    assert 'name="item_query" value="alpha"' in response.text
    assert '<option value="hat" selected>Hat</option>' in response.text
    assert '<option value="active" selected>Currently Selling</option>' in response.text
    assert 'name="min_price" inputmode="numeric" value="100"' in response.text
    assert 'name="date_from" type="date" value="2026-08-21"' in response.text
    assert '<details id="sold-history"' not in response.text
    active_section = response.text.split("<h2>Currently Selling</h2>", maxsplit=1)[1]
    assert "Alpha Hat" in active_section
    assert "Beta Hat" not in active_section
    assert catalog_item.display_name not in active_section
    assert (
        "item_query=alpha&amp;category=hat&amp;status=active&amp;min_price=100&amp;"
        "max_price=200&amp;date_from=2026-08-21&amp;date_to=2026-08-21"
    ) in response.text


def test_sales_filters_preserve_values_through_mutation(client, catalog_item) -> None:
    filter_parameters = {
        "item_query": "synthetic",
        "status": "active",
        "min_price": "100",
    }

    response = client.post(
        "/sales",
        params=filter_parameters,
        data={"item_uuid": str(catalog_item.uuid), "asking_price": "1000"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/sales?{DEFAULT_SALES_QUERY}&item_query=synthetic&status=active&"
        "min_price=100&notice=listing-added"
    )


def test_sales_filter_validation_is_inline_and_blank_values_are_allowed(client) -> None:
    blank = client.get(
        "/sales",
        params={
            "min_price": "",
            "max_price": "",
            "min_profit": "",
            "max_profit": "",
            "date_from": "",
            "date_to": "",
        },
    )
    invalid = client.get(
        "/sales",
        params={
            "min_price": "200",
            "max_price": "100",
            "min_profit": "not-a-number",
            "date_from": "2026-08-23",
            "date_to": "2026-08-22",
        },
    )

    assert blank.status_code == 200
    assert invalid.status_code == 200
    assert "Minimum price cannot be greater than maximum price." in invalid.text
    assert "Minimum profit must be a number." in invalid.text
    assert "From date cannot be after through date." in invalid.text


def test_sales_dates_and_daily_chart_use_pacific_time(
    client,
    session_factory,
    catalog_item,
) -> None:
    with session_factory() as session:
        session.add_all(
            [
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=100,
                    selling_started_at=datetime(2026, 8, 22, 1, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 22, 2, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=200,
                    selling_started_at=datetime(2026, 8, 23, 7, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 23, 8, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

    response = client.get("/sales")

    assert response.status_code == 200
    assert 'datetime="2026-08-21T19:00:00-07:00"' in response.text
    assert "Sales on 2026-08-21: 100 across 1 item" in response.text
    assert "Sales on 2026-08-23: 200 across 1 item" in response.text
    assert "Daily sales, cost, and profit by date sold" in response.text
    assert "Date Sold (Pacific Time)" in response.text
    assert "<strong>300</strong>" in response.text
    assert "<strong>2</strong>" in response.text
    assert "<strong>0 of 2</strong>" in response.text


def test_sales_show_recipe_cost_profit_and_three_chart_series(
    client,
    session_factory,
    fixture_dir,
) -> None:
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    with session_factory() as session:
        widget = session.scalar(select(Item).where(Item.normalized_name == "synthetic widget"))
        assert widget is not None
        session.add_all(
            [
                SaleListing(
                    item_id=widget.id,
                    lot_quantity=1,
                    asking_price=4_000,
                    selling_started_at=datetime(2026, 8, 21, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=widget.id,
                    lot_quantity=1,
                    asking_price=5_000,
                    selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=widget.id,
                    lot_quantity=1,
                    asking_price=4_500,
                    selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 23, 8, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=widget.id,
                    lot_quantity=1,
                    asking_price=3_000,
                    selling_started_at=datetime(2026, 8, 23, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 24, 8, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

    response = client.get(
        "/sales",
        params={"active_sort": "profit", "active_direction": "desc"},
    )

    assert response.status_code == 200
    assert 'aria-label="Sort currently selling by Cost, descending"' in response.text
    assert 'aria-label="Sort currently selling by Profit, ascending"' in response.text
    assert 'aria-label="Sort sold history by Cost, descending"' in response.text
    assert 'aria-label="Sort sold history by Profit, descending"' in response.text
    assert 'name="recipe_cost"' not in response.text
    assert 'name="profit"' not in response.text
    active_section, sold_section = response.text.split("<h2>Sold History</h2>")
    active_section = active_section.split("<h2>Currently Selling</h2>", maxsplit=1)[1]
    assert active_section.index('value="5,000"') < active_section.index('value="4,000"')
    assert active_section.count(">3,500</td>") == 2
    assert ">1,500</td>" in active_section
    assert ">500</td>" in active_section
    assert ">3,500</td>" in sold_section
    assert ">1,000</td>" in sold_section
    for series in ("sales", "cost", "profit"):
        assert f'class="chart-series chart-series--{series}"' in response.text
        assert f'class="chart-point chart-point--{series}"' in response.text
    assert "Sales on 2026-08-23: 4,500 across 1 item" in response.text
    assert "Cost on 2026-08-23: 3,500 across 1 item" in response.text
    assert "Profit on 2026-08-23: 1,000 across 1 item" in response.text
    assert "Profit on 2026-08-24: -500 across 1 item" in response.text
    assert "<span>Total Cost</span><strong>7,000</strong>" in response.text
    assert "<span>Total Profit</span><strong>500</strong>" in response.text
    assert "<span>Cost Coverage</span><strong>2 of 2</strong>" in response.text

    filtered = client.get(
        "/sales",
        params={"status": "active", "min_profit": "1000"},
    )
    active_section = filtered.text.split("<h2>Currently Selling</h2>", maxsplit=1)[1]
    assert 'value="5,000"' in active_section
    assert 'value="4,000"' not in active_section


def test_recipes_page_filters_sorts_and_links_to_item_detail(
    client,
    session_factory,
    fixture_dir,
) -> None:
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    with session_factory() as session:
        recipe = session.scalar(select(Recipe))
        assert recipe is not None
        item_uuid = recipe.crafted_item.uuid

    response = client.get(
        "/recipes",
        params={
            "profession": "Crafting",
            "min_level": "1",
            "max_level": "1",
            "economics": "unknown",
            "sort": "level",
            "direction": "desc",
        },
    )
    script = client.get("/static/recipes.js")

    assert response.status_code == 200
    assert ">Recipes</a>" in response.text
    assert 'class="site-submenu-link is-active"' in response.text
    assert 'class="page-shell page-shell--wide"' in response.text
    assert "<span>Item</span>" in response.text
    assert '<option value="Crafting" selected>Crafting</option>' in response.text
    assert '<option value="unknown" selected>Profit unknown</option>' in response.text
    assert 'id="recipe-min-level"' in response.text
    assert 'name="min_level"' in response.text
    assert 'id="recipe-min-level-number"' in response.text
    assert 'aria-label="Minimum required profession level number"' in response.text
    assert 'id="recipe-max-level"' in response.text
    assert 'name="max_level"' in response.text
    assert 'id="recipe-max-level-number"' in response.text
    assert 'aria-label="Maximum required profession level number"' in response.text
    assert response.text.count('class="dual-range-track"') == 1
    assert 'class="dual-range-slider"' in response.text
    assert 'aria-label="Minimum required profession level"' in response.text
    assert 'aria-label="Maximum required profession level"' in response.text
    assert 'value="1"' in response.text
    assert "Synthetic Widget" in response.text
    assert f'href="/items/{item_uuid}#recipe"' in response.text
    assert (
        f'action="/recipes/{item_uuid}/price?profession=Crafting&amp;min_level=1&amp;'
        'max_level=1&amp;economics=unknown&amp;sort=level&amp;direction=desc"'
    ) in response.text
    assert 'name="current_price"' in response.text
    assert 'class="price-edit-form recipe-current-price-form"' in response.text
    assert 'class="recipe-cart-add secondary-button"' in response.text
    assert 'id="recipe-open-calculator"' in response.text
    assert 'aria-label="Sort recipes by Required Level, ascending"' in response.text
    assert (
        "profession=Crafting&amp;min_level=1&amp;max_level=1&amp;economics=unknown&amp;"
        "sort=name&amp;direction=desc#recipe-catalog"
    ) in response.text
    assert '<script src="/static/recipes.js" defer></script>' in response.text
    assert script.status_code == 200
    assert 'minimumLevel.addEventListener("input"' in script.text
    assert 'minimumLevelNumber.addEventListener("input"' in script.text
    assert 'levelRangeSlider.style.setProperty("--range-minimum-position"' in script.text
    assert 'levelRangeSlider.style.setProperty("--range-maximum-position"' in script.text
    assert 'document.querySelectorAll(".recipe-current-price-form")' in script.text
    assert 'input.addEventListener("blur", savePrice)' in script.text
    assert "window.sessionStorage.setItem(recipeScrollStorageKey" in script.text
    assert 'const recipeCartStorageKey = "dofus-recipe-calculator-cart-v1"' in script.text
    assert 'form.action = "/recipe-calculator"' in script.text


def test_recipe_current_price_edit_preserves_view_and_recalculates_economics(
    client,
    session_factory,
    fixture_dir,
) -> None:
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    with session_factory() as session:
        recipe = session.scalar(select(Recipe))
        assert recipe is not None
        item_uuid = recipe.crafted_item.uuid

    response = client.post(
        f"/recipes/{item_uuid}/price",
        params={
            "q": "widget",
            "profession": "Crafting",
            "sort": "profit",
            "direction": "desc",
        },
        data={"current_price": "4,000"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/recipes?q=widget&profession=Crafting&sort=profit&direction=desc&"
        f"updated={item_uuid}#recipe-catalog"
    )
    updated_page = client.get(response.headers["location"])
    assert "Synthetic Widget price has been updated." in updated_page.text
    assert 'value="4,000"' in updated_page.text
    assert ">3,500</a>" in updated_page.text
    assert ">500</a>" in updated_page.text

    with session_factory() as session:
        detail = CatalogService(session, "Dodge").detail(item_uuid)
        listing = session.scalar(select(SaleListing))
    assert detail.current_price is not None
    assert detail.current_price.total_price == 4_000
    assert detail.current_price.lot_quantity == 1
    assert listing is None


def test_recipe_current_price_edit_rejects_invalid_value_inline(
    client,
    session_factory,
    fixture_dir,
) -> None:
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    with session_factory() as session:
        recipe = session.scalar(select(Recipe))
        assert recipe is not None
        item_uuid = recipe.crafted_item.uuid

    response = client.post(
        f"/recipes/{item_uuid}/price",
        params={"sort": "price", "direction": "desc"},
        data={"current_price": "-1"},
    )

    assert response.status_code == 422
    assert "Could not save the current price:" in response.text
    assert "Input should be greater than 0" in response.text
    assert 'value="-1"' in response.text
    with session_factory() as session:
        detail = CatalogService(session, "Dodge").detail(item_uuid)
    assert detail.current_price is None


def test_recipes_page_shows_inline_reversed_level_error(client) -> None:
    response = client.get(
        "/recipes",
        params={"min_level": "100", "max_level": "20"},
    )

    assert response.status_code == 200
    assert "Minimum level cannot be greater than maximum level." in response.text


def test_recipe_calculator_selects_multiple_items_and_renders_shopping_list(
    client,
    session_factory,
    synthetic_files,
) -> None:
    synthetic_files.write_cost_rows([("Synthetic Wood", "Wood", "10")])
    synthetic_files.write_recipe(
        ingredient="Synthetic Wood",
        quantity="2",
        recipe_item="Alpha Sword",
    )
    importer = ImportService(session_factory, market_context="Dodge")
    importer.import_files(*synthetic_files.paths)
    synthetic_files.write_recipe(
        ingredient="Synthetic Wood",
        quantity="5",
        recipe_item="Beta Ring",
    )
    importer.import_files(*synthetic_files.paths)
    with session_factory() as session:
        items = {item.normalized_name: item for item in session.scalars(select(Item)).all()}

    page = client.get("/recipe-calculator")
    script = client.get("/static/recipe-calculator.js")

    assert page.status_code == 200
    assert "Recipe Calculator" in page.text
    assert 'class="site-submenu-link is-active"' in page.text
    assert 'id="calculator-choice-data"' in page.text
    assert str(items["alpha sword"].uuid) in page.text
    assert "Alpha Sword" in page.text
    assert script.status_code == 200
    assert 'calculatorSearch.addEventListener("input"' in script.text
    assert "const addChoice = (choice, craftQuantity = 1)" in script.text
    assert "calculatorSelectedItems.append(row)" in script.text
    assert "window.localStorage.setItem(recipeCartStorageKey" in script.text
    assert 'document.querySelectorAll(".calculator-ingredient-price-form")' in script.text
    assert "await fetch(form.action" in script.text
    assert "calculatorForm.requestSubmit()" in script.text

    response = client.post(
        "/recipe-calculator",
        data={
            "selected_item_uuid": [
                str(items["alpha sword"].uuid),
                str(items["beta ring"].uuid),
            ],
            f"quantity_{items['alpha sword'].uuid}": "2",
            f"quantity_{items['beta ring'].uuid}": "3",
        },
    )

    assert response.status_code == 200
    assert "Combined Shopping List" in response.text
    assert "Synthetic Wood" in response.text
    assert re.search(r"Total Quantity</th>.*?>19</td>", response.text, re.DOTALL)
    assert "190" in response.text
    assert "Alpha Sword, Beta Ring" in response.text
    assert "5" in response.text
    assert 'id="recipe-calculator-form"' in response.text
    assert (
        f'action="/recipe-calculator/ingredients/{items["synthetic wood"].uuid}/price"'
        in response.text
    )
    assert 'class="price-edit-form calculator-ingredient-price-form"' in response.text
    assert 'name="unit_price"' in response.text

    invalid_update = client.post(
        f"/recipe-calculator/ingredients/{items['synthetic wood'].uuid}/price",
        data={"unit_price": "0"},
        headers={"accept": "application/json"},
    )

    assert invalid_update.status_code == 422
    assert invalid_update.json()["errors"]

    update = client.post(
        f"/recipe-calculator/ingredients/{items['synthetic wood'].uuid}/price",
        data={"unit_price": "25"},
        headers={"accept": "application/json"},
    )

    assert update.status_code == 200
    assert update.json() == {
        "item_uuid": str(items["synthetic wood"].uuid),
        "unit_price": 25,
    }

    recalculated = client.post(
        "/recipe-calculator",
        params={"updated": str(items["synthetic wood"].uuid)},
        data={
            "selected_item_uuid": [
                str(items["alpha sword"].uuid),
                str(items["beta ring"].uuid),
            ],
            f"quantity_{items['alpha sword'].uuid}": "2",
            f"quantity_{items['beta ring'].uuid}": "3",
        },
    )

    assert recalculated.status_code == 200
    assert "Ingredient price updated and shopping list recalculated." in recalculated.text
    assert re.search(r"Total Quantity</th>.*?>19</td>", recalculated.text, re.DOTALL)
    assert "<strong>475</strong>" in recalculated.text
    assert 'value="25"' in recalculated.text
    with session_factory() as session:
        ingredient = session.scalar(select(Item).where(Item.normalized_name == "synthetic wood"))
        assert ingredient is not None
        current_price = PriceService(session, "Dodge").current_for_item(ingredient.id)
        history = PriceService(session, "Dodge").history_for_item(ingredient.id)
        assert current_price is not None
        assert current_price.lot_quantity == 1
        assert current_price.total_price == 25
        assert history[0].note == "Recipe calculator ingredient price update"
        assert session.scalar(select(SaleListing.id)) is None


def test_recipe_calculator_requires_a_valid_selection(client) -> None:
    response = client.post("/recipe-calculator", data={})

    assert response.status_code == 422
    assert "Select at least one craftable item." in response.text


def test_bigquery_sync_page_starts_fixed_job_and_streams_status(
    app,
    client,
    tmp_path,
) -> None:
    captured_arguments = []

    def runner(arguments, emit) -> int:
        captured_arguments.extend(arguments)
        emit("dataset=dofus_dev table=raw_items status=loading rows=3")
        emit("dataset=dofus_prod status=complete")
        return 0

    manager = BigQuerySyncManager(
        "claude-projects-489306",
        "US",
        ("dofus_dev", "dofus_prod"),
        tmp_path / "application.sqlite3",
        runner=runner,
    )
    app.state.bigquery_sync_manager = manager

    page = client.get("/bigquery-sync")
    script = client.get("/static/bigquery-sync.js")

    assert page.status_code == 200
    assert "BigQuery Sync" in page.text
    assert 'class="site-tab is-active"' in page.text
    assert "claude-projects-489306" in page.text
    assert "dofus_dev, dofus_prod" in page.text
    assert "Update BigQuery Now" in page.text
    assert "dbt build" in page.text
    assert script.status_code == 200
    assert 'window.fetch("/bigquery-sync/status"' in script.text

    started = client.post("/bigquery-sync", follow_redirects=False)
    assert started.status_code == 303
    assert started.headers["location"] == "/bigquery-sync?notice=started"
    completed = manager.wait(timeout=2)
    assert completed.status == "succeeded"
    assert "--project-id=claude-projects-489306" in captured_arguments
    assert "--dataset=dofus_dev" in captured_arguments
    assert "--dataset=dofus_prod" in captured_arguments

    status = client.get("/bigquery-sync/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "succeeded"
    assert payload["exit_code"] == 0
    assert any("raw_items" in line for line in payload["lines"])


def test_blank_search_lists_catalog_alphabetically(client, session_factory, catalog_item) -> None:
    with session_factory() as session:
        session.add_all(
            [
                Item(display_name="Zeta Item", normalized_name="zeta item", identity_category=""),
                Item(
                    display_name="Alpha Item",
                    normalized_name="alpha item",
                    category="hat",
                    identity_category="",
                ),
            ]
        )
        session.commit()

    response = client.get("/items")

    assert response.status_code == 200
    assert "Item Name" in response.text
    assert "Current Price" in response.text
    assert "Observed lot" not in response.text
    assert "Last Observed" in response.text
    assert "Hat" in response.text
    assert '<details class="collapsible-section" open>' in response.text
    assert response.text.index("Alpha Item") < response.text.index(catalog_item.display_name)
    assert response.text.index(catalog_item.display_name) < response.text.index("Zeta Item")


def test_blank_item_catalog_is_paginated(client, session_factory) -> None:
    with session_factory() as session:
        session.add_all(
            Item(
                display_name=f"Paged Item {index:03d}",
                normalized_name=f"paged item {index:03d}",
                identity_category="",
            )
            for index in range(105)
        )
        session.commit()

    first_page = client.get("/items")
    second_page = client.get("/items", params={"page": 2})

    assert first_page.status_code == 200
    assert first_page.text.count('class="item-row"') == 100
    assert "1–100 of 105 shown" in first_page.text
    assert "Page 1 of 2" in first_page.text
    assert "Paged Item 000" in first_page.text
    assert "Paged Item 100" not in first_page.text
    assert second_page.status_code == 200
    assert second_page.text.count('class="item-row"') == 5
    assert "101–105 of 105 shown" in second_page.text
    assert "Paged Item 100" in second_page.text


def test_search_field_reduces_catalog_table(client, session_factory, catalog_item) -> None:
    with session_factory() as session:
        session.add(
            Item(
                display_name="Synthetic Fiber",
                normalized_name="synthetic fiber",
                identity_category="fiber",
            )
        )
        session.commit()

    response = client.get("/items", params={"q": "ore"})

    assert response.status_code == 200
    assert catalog_item.display_name in response.text
    assert "Synthetic Fiber" not in response.text
    assert "1 shown" in response.text


def test_item_search_category_filter_reduces_results_and_persists_in_sorting(
    client,
    session_factory,
) -> None:
    with session_factory() as session:
        session.add_all(
            [
                Item(
                    display_name="Alpha Ring",
                    normalized_name="alpha ring",
                    category="Ring",
                    identity_category="ring",
                ),
                Item(
                    display_name="Alpha Hat",
                    normalized_name="alpha hat",
                    category="Hat",
                    identity_category="hat",
                ),
            ]
        )
        session.commit()

    response = client.get("/items", params={"q": "alpha", "category": "ring"})

    assert response.status_code == 200
    assert '<label for="item-category">Category (Optional)</label>' in response.text
    assert '<option value="ring" selected>Ring</option>' in response.text
    assert "Alpha Ring" in response.text
    assert "Alpha Hat" not in response.text
    assert "q=alpha&amp;category=ring&amp;sort=price&amp;direction=desc" in response.text
    assert 'aria-label="Sort by Current Price, descending"' in response.text


def test_item_headers_toggle_sort_and_show_active_direction(client, catalog_item) -> None:
    response = client.get(
        "/items",
        params={"q": "synthetic", "sort": "price", "direction": "desc"},
    )

    assert response.status_code == 200
    assert 'name="sort" value="price"' in response.text
    assert 'name="direction" value="desc"' in response.text
    assert 'aria-sort="descending"' in response.text
    assert '<span class="sort-arrow" aria-hidden="true">▼</span>' in response.text
    assert "/items?q=synthetic&amp;category=&amp;sort=price&amp;direction=asc" in response.text
    for field in ("name", "category", "price", "observed"):
        assert f"sort={field}" in response.text


def test_catalog_row_shows_current_price_and_opens_item_detail(client, priced_item) -> None:
    response = client.get("/items")
    item_url = f"/items/{priced_item.item_uuid}"

    assert response.status_code == 200
    assert 'class="item-table"' in response.text
    assert "120 kamas" not in response.text
    assert ">\n                120\n" in response.text
    assert "2026-08-20" in response.text
    assert "2026-08-20 00:00 UTC" not in response.text
    assert "Update Price" in response.text
    assert response.text.count(f'href="{item_url}"') == 5

    detail = client.get(item_url)
    assert detail.status_code == 200
    assert "<summary><h2>Current Price</h2></summary>" in detail.text
    assert "Price Observations" not in detail.text
    assert "<summary><h2>Crafting Metrics</h2></summary>" in detail.text


def test_item_detail_shows_active_and_sold_listing_counts(
    client,
    session_factory,
    catalog_item,
) -> None:
    client.post(
        "/sales",
        data={"item_uuid": str(catalog_item.uuid), "asking_price": "100"},
    )
    client.post(
        "/sales",
        data={"item_uuid": str(catalog_item.uuid), "asking_price": "200"},
    )
    with session_factory() as session:
        sold_uuid = session.scalar(select(SaleListing.uuid).order_by(SaleListing.id.desc()))
    client.post(f"/sales/{sold_uuid}/sold")

    response = client.get(f"/items/{catalog_item.uuid}")

    assert response.status_code == 200
    assert 'class="item-sales-counts"' in response.text
    assert "<span>Currently Selling</span><strong>1</strong>" in response.text
    assert "<span>Sold</span><strong>1</strong>" in response.text
    assert (
        f'href="/sales?item_uuid={catalog_item.uuid}&amp;status=active#currently-selling"'
        in response.text
    )
    assert (
        f'href="/sales?item_uuid={catalog_item.uuid}&amp;status=sold#sold-history"' in response.text
    )


def test_catalog_and_static_route_show_cached_item_icon(
    client,
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    icon_directory = tmp_path / "data" / "app" / "item_icons"
    icon_directory.mkdir(parents=True)
    icon_content = b"\x89PNG\r\n\x1a\nsynthetic"
    (icon_directory / f"{catalog_item.uuid}.png").write_bytes(icon_content)
    with session_factory() as session:
        item = session.scalar(select(Item).where(Item.uuid == catalog_item.uuid))
        item.icon_source_url = "https://example.invalid/item.png"
        session.commit()

    response = client.get("/items", params={"q": catalog_item.display_name})

    assert response.status_code == 200
    icon_url = f"/item-icons/{catalog_item.uuid}.png"
    assert f'src="{icon_url}"' in response.text
    icon_response = client.get(icon_url)
    assert icon_response.status_code == 200
    assert icon_response.content == icon_content


def test_htmx_search_returns_only_results_fragment(client, catalog_item) -> None:
    response = client.get("/items?q=ore", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert catalog_item.display_name in response.text
    assert "<html" not in response.text


def test_search_input_uses_delayed_htmx_updates(client) -> None:
    response = client.get("/items")

    assert 'hx-get="/items"' in response.text
    assert 'hx-trigger="input changed delay:250ms, search"' in response.text
    assert 'hx-target="#item-results"' in response.text
    assert (
        "hx-include=\"#item-category, input[name='sort'], input[name='direction']\""
        in response.text
    )
    assert 'id="item-category"' in response.text
    assert 'hx-trigger="change"' in response.text


def test_no_results_offers_typo_suggestion_and_manual_add_form(client, catalog_item) -> None:
    response = client.get("/items", params={"q": "syntheic ore"})

    assert response.status_code == 200
    assert "No items found" in response.text
    assert "Similar Items" in response.text
    assert catalog_item.display_name in response.text
    assert 'action="/items"' in response.text
    assert 'value="Syntheic Ore"' in response.text


def test_no_results_previews_title_case_and_recognized_category(client) -> None:
    response = client.get("/items", params={"q": "chouquish belt"})

    assert response.status_code == 200
    assert 'name="display_name"' in response.text
    assert 'value="Chouquish Belt"' in response.text
    assert 'name="category"' in response.text
    assert 'value="Belt"' in response.text


def test_no_results_title_case_does_not_capitalize_after_apostrophe(client) -> None:
    response = client.get("/items", params={"q": "daggero's red necklace"})

    assert response.status_code == 200
    assert 'value="Daggero&#39;s Red Necklace"' in response.text
    assert "Daggero'S Red Necklace" not in response.text


def test_html_creates_manual_item_and_redirects_to_detail(client) -> None:
    response = client.post(
        "/items",
        data={"display_name": "chouquish belt", "category": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/items/")
    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "Chouquish Belt" in detail.text
    assert "Belt · Market: Dodge" in detail.text
    assert "Catalog Source: Manual" in detail.text


def test_html_duplicate_manual_item_redirects_to_existing_item(client, catalog_item) -> None:
    response = client.post(
        "/items",
        data={"display_name": "Synthetic Ore", "category": "Ore"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/items/{catalog_item.uuid}"


def test_html_manual_item_validation_is_inline(client) -> None:
    response = client.post(
        "/items",
        data={"display_name": "   ", "category": "Keep Category"},
    )

    assert response.status_code == 422
    assert "item name must not be blank" in response.text
    assert 'value="Keep Category"' in response.text


def test_unknown_html_item_returns_404(client) -> None:
    response = client.get(f"/items/{uuid4()}")

    assert response.status_code == 404
    assert "Item not found" in response.text


def test_detail_labels_incomplete_recipe_cost(client, session_factory, synthetic_files) -> None:
    ImportService(session_factory).import_files(*synthetic_files.paths)
    with session_factory() as session:
        product_uuid = session.scalar(
            select(Item.uuid).where(Item.normalized_name == "synthetic product")
        )

    response = client.get(f"/items/{product_uuid}")

    assert response.status_code == 200
    assert "Recipe cost is incomplete" in response.text


def test_recipe_links_ingredient_name_and_shows_unit_and_total_prices(
    client, session_factory, fixture_dir
) -> None:
    ImportService(session_factory).import_files(
        fixture_dir / "item_cost_valid.csv", fixture_dir / "item_recipes_valid.csv"
    )
    with session_factory() as session:
        items = {item.normalized_name: item for item in session.scalars(select(Item)).all()}
        price_service = PriceService(session, "Dodge")
        price_service.record(
            items["synthetic ore"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=1_000,
                observed_at=datetime(2026, 8, 21, tzinfo=UTC),
            ),
        )
        price_service.record(
            items["synthetic fiber"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=500,
                observed_at=datetime(2026, 8, 21, tzinfo=UTC),
            ),
        )
        price_service.record(
            items["synthetic widget"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=4_000,
                observed_at=datetime(2026, 8, 21, tzinfo=UTC),
            ),
        )

    response = client.get(f"/items/{items['synthetic widget'].uuid}")

    assert response.status_code == 200
    assert "Recipe · Crafting ·" in response.text
    assert "Required Level 1" in response.text
    assert "2 ingredient slots" in response.text
    assert "Per Unit Price" in response.text
    assert "Total Cost" in response.text
    assert (
        f'<a class="recipe-item-link" href="/items/{items["synthetic ore"].uuid}">Synthetic Ore</a>'
    ) in response.text
    assert "View item" not in response.text
    assert 'name="unit_price"' in response.text
    assert 'value="1,000"' in response.text
    assert 'value="500"' in response.text
    assert '<script src="/static/sales.js" defer></script>' in response.text
    script = client.get("/static/sales.js")
    assert 'input[name="asking_price"], input[name="unit_price"]' in script.text
    assert 'input[name="current_price"]' in script.text
    assert 'class="crafting-metrics-grid"' in response.text
    assert response.text.count('class="crafting-metric"') == 3
    assert "Recipe Cost" in response.text
    assert "3,500 kama" in response.text
    assert "Profit" in response.text
    assert "500 kama" in response.text
    assert "14.29%" in response.text
    for value in ("2,000", "1,500"):
        assert re.search(rf'<td class="numeric">\s*{value}\s*</td>', response.text)


def test_recipe_unit_price_edit_updates_history_without_starting_sale(
    client, session_factory, fixture_dir
) -> None:
    ImportService(session_factory).import_files(
        fixture_dir / "item_cost_valid.csv", fixture_dir / "item_recipes_valid.csv"
    )
    with session_factory() as session:
        items = {item.normalized_name: item for item in session.scalars(select(Item)).all()}

    response = client.post(
        f"/items/{items['synthetic widget'].uuid}/recipe-ingredients/"
        f"{items['synthetic ore'].uuid}/price",
        data={"unit_price": "1,250"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/items/{items['synthetic widget'].uuid}?updated={items['synthetic ore'].uuid}#recipe"
    )
    updated_page = client.get(response.headers["location"])
    assert "Synthetic Ore price has been updated." in updated_page.text
    assert 'value="1,250"' in updated_page.text
    assert re.search(r'<td class="numeric">\s*2,500\s*</td>', updated_page.text)
    assert "Last Updated (Days)" in updated_page.text
    assert re.search(r'<td class="numeric">\s*0\s*</td>', updated_page.text)
    assert '<td class="status">Current price</td>' in updated_page.text
    assert "Price missing" not in updated_page.text
    assert ">Priced<" not in updated_page.text

    with session_factory() as session:
        detail = CatalogService(session, "Dodge").detail(items["synthetic widget"].uuid)
        listing = session.scalar(select(SaleListing))
    assert detail.recipe is not None
    assert detail.recipe.ingredients[0].current_price is not None
    assert detail.recipe.ingredients[0].current_price.total_price == 1_250
    assert detail.recipe.ingredients[0].extended_cost == 2_500
    assert listing is None


def test_recipe_price_edit_rejects_item_outside_current_recipe(
    client, session_factory, fixture_dir
) -> None:
    ImportService(session_factory).import_files(
        fixture_dir / "item_cost_valid.csv", fixture_dir / "item_recipes_valid.csv"
    )
    with session_factory() as session:
        product_uuid = session.scalar(
            select(Item.uuid).where(Item.normalized_name == "synthetic widget")
        )
        unrelated_item = Item(
            display_name="Unrelated Item",
            normalized_name="unrelated item",
            identity_category="",
        )
        session.add(unrelated_item)
        session.commit()

    response = client.post(
        f"/items/{product_uuid}/recipe-ingredients/{unrelated_item.uuid}/price",
        data={"unit_price": "1,000"},
    )

    assert response.status_code == 404
    assert "Recipe ingredient not found." in response.text
    with session_factory() as session:
        assert session.scalar(select(SaleListing.id)) is None


def test_htmx_price_create_redirects_to_item_search(client, session_factory, fixture_dir) -> None:
    ImportService(session_factory).import_files(
        fixture_dir / "item_cost_valid.csv", fixture_dir / "item_recipes_valid.csv"
    )
    with session_factory() as session:
        items = {item.normalized_name: item for item in session.scalars(select(Item)).all()}
        service = PriceService(session, "Dodge")
        service.record(
            items["synthetic ore"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=10,
                observed_at="2026-08-20T12:00:00Z",
            ),
        )
        service.record(
            items["synthetic fiber"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=20,
                observed_at="2026-08-20T12:00:00Z",
            ),
        )
        crafted_uuid = items["synthetic widget"].uuid

    response = client.post(
        f"/items/{crafted_uuid}/price-observations",
        headers={"HX-Request": "true"},
        data={
            "total_price": "125,000",
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "Manual check",
        },
    )

    assert response.status_code == 204
    assert response.headers["hx-redirect"] == f"/items?updated={crafted_uuid}"

    with session_factory() as session:
        detail = CatalogService(session, "Dodge").detail(crafted_uuid)
    assert detail.current_price is not None
    assert detail.current_price.total_price == 125_000
    assert detail.current_price.lot_quantity == 1


def test_item_current_price_validation_is_inline_and_hides_legacy_fields(
    client, catalog_item
) -> None:
    response = client.post(
        f"/items/{catalog_item.uuid}/price",
        data={"current_price": "-1"},
    )

    assert response.status_code == 422
    assert "Input should be greater than 0" in response.text
    assert 'value="-1"' in response.text
    for field_name in ("note", "total_price", "observed_at", "lot_quantity", "reason"):
        assert f'name="{field_name}"' not in response.text
    assert "Invalidate" not in response.text


def test_item_current_price_edit_appends_history_and_returns_to_item(
    client, session_factory, catalog_item
) -> None:
    initial_page = client.get(f"/items/{catalog_item.uuid}")

    assert initial_page.status_code == 200
    assert f'action="/items/{catalog_item.uuid}/price"' in initial_page.text
    assert 'name="current_price"' in initial_page.text
    assert 'placeholder="—"' in initial_page.text
    assert "Observed At" not in initial_page.text
    assert ">Note<" not in initial_page.text
    assert ">Total Price<" not in initial_page.text
    assert "Invalidation Reason" not in initial_page.text
    assert ">Invalidate</button>" not in initial_page.text

    response = client.post(
        f"/items/{catalog_item.uuid}/price",
        data={"current_price": "245,000"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/items/{catalog_item.uuid}?updated={catalog_item.uuid}#price-panel"
    )
    updated_page = client.get(response.headers["location"])
    assert f"{catalog_item.display_name} price has been updated." in updated_page.text
    assert 'value="245,000"' in updated_page.text
    assert ">245,000</td>" in updated_page.text
    with session_factory() as session:
        listing = session.scalar(select(SaleListing))
        detail = CatalogService(session, "Dodge").detail(catalog_item.uuid)
    assert listing is None
    assert detail.current_price is not None
    assert detail.current_price.total_price == 245_000
    assert len(detail.price_history) == 1


def test_price_history_is_a_table_with_confirmed_audit_safe_deletion(
    client,
    session_factory,
    priced_item,
) -> None:
    page = client.get(f"/items/{priced_item.item_uuid}")

    assert page.status_code == 200
    assert '<table class="price-history-table">' in page.text
    assert "<th>Date Observed</th>" in page.text
    assert '<th class="numeric">Price</th>' in page.text
    assert "<th>Action</th>" in page.text
    assert f'action="/price-observations/{priced_item.previous_uuid}/delete"' in page.text
    assert f'action="/price-observations/{priced_item.current_uuid}/delete"' in page.text
    assert "return window.confirm('Delete this price history row?')" in page.text
    assert 'title="Delete price history row"' in page.text
    assert 'name="reason"' not in page.text

    response = client.post(
        f"/price-observations/{priced_item.current_uuid}/delete",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/items/{priced_item.item_uuid}?notice=price-history-deleted#price-panel"
    )
    updated_page = client.get(response.headers["location"])
    assert "Price history row has been deleted." in updated_page.text
    assert 'value="100"' in updated_page.text
    assert ">100</td>" in updated_page.text
    assert ">120</td>" not in updated_page.text
    assert f'action="/price-observations/{priced_item.current_uuid}/delete"' not in (
        updated_page.text
    )
    with session_factory() as session:
        detail = CatalogService(session, "Dodge").detail(priced_item.item_uuid)
    observations = {
        observation.observation_uuid: observation for observation in detail.price_history
    }
    assert detail.current_price is not None
    assert detail.current_price.total_price == 100
    assert observations[priced_item.current_uuid].invalidated_at is not None
    assert (
        observations[priced_item.current_uuid].invalidation_reason
        == "Deleted from item price history"
    )


def test_non_htmx_price_create_redirects_to_search_with_notification(client, catalog_item) -> None:
    response = client.post(
        f"/items/{catalog_item.uuid}/price-observations",
        data={
            "total_price": "245,000",
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/items?updated={catalog_item.uuid}"

    search = client.get(response.headers["location"])
    assert search.status_code == 200
    assert f"{catalog_item.display_name} price has been updated." in search.text
    assert "245,000" in search.text
    assert 'class="notification" role="status"' in search.text


def test_htmx_invalidation_restores_previous_price(client, priced_item) -> None:
    response = client.post(
        f"/price-observations/{priced_item.current_uuid}/invalidation",
        headers={"HX-Request": "true"},
        data={"reason": "Mistyped price"},
    )

    assert response.status_code == 200
    assert 'name="current_price"' in response.text
    assert 'value="100"' in response.text
    assert "Invalidate" not in response.text
    assert 'hx-swap-oob="true"' in response.text
