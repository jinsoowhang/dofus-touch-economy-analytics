import hashlib
from importlib import resources


def test_vendored_htmx_has_reviewed_digest() -> None:
    data = resources.files("dofus_touch_economy").joinpath("static/htmx.min.js").read_bytes()

    assert (
        hashlib.sha256(data).hexdigest()
        == "71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de"
    )


def test_vendored_htmx_license_has_reviewed_digest() -> None:
    data = resources.files("dofus_touch_economy").joinpath("static/htmx-LICENSE").read_bytes()

    assert (
        hashlib.sha256(data).hexdigest()
        == "d3d2456f76414f2456104660ebd65aff1c04cd7966b942bdabd63f3cdb316a38"
    )


def test_base_template_uses_only_local_assets() -> None:
    template = (
        resources.files("dofus_touch_economy")
        .joinpath("templates/base.html")
        .read_text(encoding="utf-8")
    )

    assert "/static/app.css" in template
    assert "/static/htmx.min.js" in template
    assert "/static/table-sort.js" in template
    assert "https://" not in template


def test_client_table_sorter_supports_typed_columns_and_missing_values() -> None:
    script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/table-sort.js")
        .read_text(encoding="utf-8")
    )

    assert 'document.querySelectorAll("table[data-sortable-table]")' in script
    assert 'type === "number"' in script
    assert 'type === "date"' in script
    assert 'header.setAttribute("aria-sort", direction)' in script
    assert "left.value === null" in script
    assert 'button.addEventListener("click"' in script


def test_recipe_calculator_preserves_shopping_list_sort_during_price_reload() -> None:
    script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/recipe-calculator.js")
        .read_text(encoding="utf-8")
    )

    assert '"dofus-recipe-calculator-shopping-list-sort"' in script
    assert 'document.querySelector(".calculator-shopping-list-table")' in script
    assert 'header.getAttribute("aria-sort")' in script
    assert "saveRecipeCalculatorShoppingListSort();" in script
    assert "restoreRecipeCalculatorShoppingListSort();" in script
    assert 'sortState.direction === "descending"' in script


def test_every_web_table_has_client_or_server_sorting() -> None:
    templates = resources.files("dofus_touch_economy").joinpath("templates")
    expected_server_sorted = {
        "best_sellers.html": 0,
        "fragments/item_results.html": 1,
        "item_detail.html": 0,
        "fragments/price_panel.html": 0,
        "out_of_stock_items.html": 0,
        "recipe_calculator.html": 0,
        "recipes.html": 1,
        "sales.html": 2,
    }

    for relative_path, server_sorted_count in expected_server_sorted.items():
        template = templates.joinpath(relative_path).read_text(encoding="utf-8")
        table_count = template.count("<table")
        client_sorted_count = template.count("data-sortable-table")

        assert table_count == client_sorted_count + server_sorted_count
        if server_sorted_count:
            assert 'class="sort-header"' in template


def test_bulk_sale_buttons_share_text_button_geometry() -> None:
    stylesheet = (
        resources.files("dofus_touch_economy")
        .joinpath("static/app.css")
        .read_text(encoding="utf-8")
    )

    bulk_button_rule = stylesheet.split(".bulk-actions button {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    assert "align-items: center;" in bulk_button_rule
    assert "font-size: inherit;" in bulk_button_rule
    assert "line-height: inherit;" in bulk_button_rule
    assert "min-height: 2.6rem;" in bulk_button_rule
    assert "padding: 0.55rem 0.7rem;" in bulk_button_rule


def test_out_of_stock_table_restores_cell_spacing() -> None:
    stylesheet = (
        resources.files("dofus_touch_economy")
        .joinpath("static/app.css")
        .read_text(encoding="utf-8")
    )

    out_of_stock_rule = stylesheet.split(".out-of-stock-table td {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    assert "padding: 0.75rem;" in out_of_stock_rule


def test_item_navigation_dropdown_supports_hover_click_and_focus() -> None:
    stylesheet = (
        resources.files("dofus_touch_economy")
        .joinpath("static/app.css")
        .read_text(encoding="utf-8")
    )
    template = (
        resources.files("dofus_touch_economy")
        .joinpath("templates/base.html")
        .read_text(encoding="utf-8")
    )

    assert '<details class="site-menu">' in template
    assert ".site-menu[open] .site-submenu" in stylesheet
    assert ".site-menu:hover .site-submenu" in stylesheet
    assert ".site-menu:focus-within .site-submenu" in stylesheet
