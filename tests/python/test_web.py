from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item, SaleListing
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
    assert "Dofus Touch Economy" in response.text
    assert catalog_item.display_name in response.text
    assert str(catalog_item.uuid) in response.text


def test_item_search_has_active_top_navigation_tab(client) -> None:
    response = client.get("/items")

    assert response.status_code == 200
    assert 'aria-label="Primary navigation"' in response.text
    assert 'class="site-tab is-active"' in response.text
    assert 'aria-current="page"' in response.text
    assert ">Item Search</a>" in response.text
    assert 'href="/sales"' in response.text


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
    assert 'input.addEventListener("blur", savePrice)' in script.text


def test_sales_page_adds_and_completes_a_listing(client, session_factory, catalog_item) -> None:
    created = client.post(
        "/sales",
        data={
            "item_uuid": str(catalog_item.uuid),
            "asking_price": "50000",
        },
        follow_redirects=False,
    )

    assert created.status_code == 303
    assert created.headers["location"] == f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-added"
    active_page = client.get(created.headers["location"])
    assert "Sale listing has been added." in active_page.text
    assert catalog_item.display_name in active_page.text
    assert 'value="50000"' in active_page.text
    assert "Mark sold" in active_page.text
    assert "Duplicate" in active_page.text
    assert active_page.text.count('class="collapsible-section" open') == 4
    assert '<button type="submit">Update</button>' not in active_page.text
    assert 'data-initial-value="50000"' in active_page.text
    assert "Press Enter or leave the field to save." in active_page.text
    assert "Lot quantity" not in active_page.text
    assert 'name="lot_quantity"' not in active_page.text
    assert "Delete this sales row? This cannot be undone." in active_page.text
    assert f'aria-label="Delete sale row for {catalog_item.display_name}"' in active_page.text

    with session_factory() as session:
        listing = session.scalar(select(SaleListing))
        assert listing is not None
        assert listing.price_observation is not None
        assert listing.price_observation.total_price == 50_000
        assert listing.price_observation.market_context == "Dodge"
        listing_uuid = listing.uuid
    item_page = client.get(f"/items/{catalog_item.uuid}")
    assert "Current Price: 50000 kama" in item_page.text
    assert "· 50000 kama" in item_page.text
    completed = client.post(
        f"/sales/{listing_uuid}/sold",
        follow_redirects=False,
    )

    assert completed.status_code == 303
    assert completed.headers["location"] == f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-sold"
    sold_page = client.get(completed.headers["location"])
    assert "Item has been marked as sold." in sold_page.text
    assert "0 active" in sold_page.text
    assert "1 sold" in sold_page.text
    assert "Date Sold" in sold_page.text


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


def test_recorded_item_price_appears_as_an_active_sale(client, catalog_item) -> None:
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
    assert catalog_item.display_name in sales.text
    assert 'value="125000"' in sales.text
    assert "1 active" in sales.text


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
        data={"asking_price": "45000"},
        follow_redirects=False,
    )

    assert repriced.status_code == 303
    assert repriced.headers["location"] == (
        f"/sales?{DEFAULT_SALES_QUERY}&notice=listing-price-updated"
    )
    page = client.get(repriced.headers["location"])
    assert "Sale price has been updated." in page.text
    assert 'value="50000"' in page.text
    assert 'value="45000"' in page.text
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
        "active_sort=price&amp;active_direction=asc&amp;sold_sort=name&amp;sold_direction=asc"
    ) in response.text
    assert (
        "active_sort=price&amp;active_direction=desc&amp;sold_sort=sold&amp;sold_direction=asc"
    ) in response.text
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
    assert "2026-08-21: 100 total across 1 item" in response.text
    assert "2026-08-23: 200 total across 1 item" in response.text
    assert "Daily sales totals by date sold" in response.text
    assert "Date Sold (Pacific Time)" in response.text
    assert "<strong>300</strong>" in response.text
    assert "<strong>2</strong>" in response.text


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
    assert "/items?q=synthetic&amp;sort=price&amp;direction=asc" in response.text
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
    assert "<summary><h2>Price Observations</h2></summary>" in detail.text
    assert "<summary><h2>Crafting Metrics</h2></summary>" in detail.text


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
            "total_price": "125",
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "Manual check",
        },
    )

    assert response.status_code == 204
    assert response.headers["hx-redirect"] == f"/items?updated={crafted_uuid}"

    with session_factory() as session:
        detail = CatalogService(session, "Dodge").detail(crafted_uuid)
    assert detail.current_price is not None
    assert detail.current_price.total_price == 125
    assert detail.current_price.lot_quantity == 1


def test_html_validation_is_inline_and_preserves_safe_values(client, catalog_item) -> None:
    response = client.post(
        f"/items/{catalog_item.uuid}/price-observations",
        headers={"HX-Request": "true"},
        data={
            "total_price": "-1",
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "Keep this note",
        },
    )

    assert response.status_code == 422
    assert "Input should be greater than 0" in response.text
    assert 'value="-1"' in response.text
    assert 'name="lot_quantity"' not in response.text
    assert "Keep this note" in response.text


def test_non_htmx_price_create_redirects_to_search_with_notification(client, catalog_item) -> None:
    response = client.post(
        f"/items/{catalog_item.uuid}/price-observations",
        data={
            "total_price": "125",
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
    assert 'class="notification" role="status"' in search.text


def test_htmx_invalidation_restores_previous_price(client, priced_item) -> None:
    response = client.post(
        f"/price-observations/{priced_item.current_uuid}/invalidation",
        headers={"HX-Request": "true"},
        data={"reason": "Mistyped price"},
    )

    assert response.status_code == 200
    assert "Current Price: 100" in response.text
    assert 'hx-swap-oob="true"' in response.text
