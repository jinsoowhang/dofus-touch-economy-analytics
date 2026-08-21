from uuid import uuid4

from sqlalchemy import select

from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item
from dofus_touch_economy.schemas import PriceObservationCreate
from dofus_touch_economy.services.pricing import PriceService


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


def test_blank_search_lists_catalog_alphabetically(client, session_factory, catalog_item) -> None:
    with session_factory() as session:
        session.add_all(
            [
                Item(display_name="Zeta Item", normalized_name="zeta item", identity_category=""),
                Item(
                    display_name="Alpha Item",
                    normalized_name="alpha item",
                    identity_category="",
                ),
            ]
        )
        session.commit()

    response = client.get("/items")

    assert response.status_code == 200
    assert "Item name" in response.text
    assert "Current unit price" in response.text
    assert "Last observed" in response.text
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


def test_catalog_row_shows_current_price_and_opens_item_detail(client, priced_item) -> None:
    response = client.get("/items")
    item_url = f"/items/{priced_item.item_uuid}"

    assert response.status_code == 200
    assert 'class="item-table"' in response.text
    assert "120 kamas" in response.text
    assert "1 for 120 kamas" in response.text
    assert "Update price" in response.text
    assert response.text.count(f'href="{item_url}"') == 6


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
    assert "Similar items" in response.text
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
    assert "Catalog source: Manual" in detail.text


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


def test_htmx_price_create_returns_panel_and_recalculated_metrics(
    client, session_factory, fixture_dir
) -> None:
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
            "lot_quantity": "1",
            "total_price": "125",
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "Manual check",
        },
    )

    assert response.status_code == 200
    assert 'id="price-panel"' in response.text
    assert 'hx-swap-oob="true"' in response.text
    assert "Market: Dodge" in response.text
    assert "Recipe cost: 80" in response.text
    assert "Profit: 45" in response.text
    assert "<html" not in response.text


def test_html_validation_is_inline_and_preserves_safe_values(client, catalog_item) -> None:
    response = client.post(
        f"/items/{catalog_item.uuid}/price-observations",
        headers={"HX-Request": "true"},
        data={
            "lot_quantity": "-1",
            "total_price": "125",
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "Keep this note",
        },
    )

    assert response.status_code == 422
    assert "Input should be greater than 0" in response.text
    assert 'value="-1"' in response.text
    assert "Keep this note" in response.text


def test_non_htmx_price_create_redirects_to_detail(client, catalog_item) -> None:
    response = client.post(
        f"/items/{catalog_item.uuid}/price-observations",
        data={
            "lot_quantity": "1",
            "total_price": "125",
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/items/{catalog_item.uuid}"


def test_htmx_invalidation_restores_previous_price(client, priced_item) -> None:
    response = client.post(
        f"/price-observations/{priced_item.current_uuid}/invalidation",
        headers={"HX-Request": "true"},
        data={"reason": "Mistyped price"},
    )

    assert response.status_code == 200
    assert "Current unit price: 100" in response.text
    assert 'hx-swap-oob="true"' in response.text
