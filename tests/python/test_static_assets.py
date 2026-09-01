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
    assert 'const initialDirection = header.getAttribute("aria-sort")' in script
    assert '["ascending", "descending"].includes(initialDirection)' in script
    assert "left.value === null" in script
    assert 'button.addEventListener("click"' in script


def test_recipe_calculator_preserves_shopping_list_sort_during_price_reload() -> None:
    script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/recipe-calculator.js")
        .read_text(encoding="utf-8")
    )

    assert '"dofus-recipe-calculator-shopping-list-sort-v2"' in script
    assert 'document.querySelector(".calculator-shopping-list-table")' in script
    assert 'header.getAttribute("aria-sort")' in script
    assert "saveRecipeCalculatorShoppingListSort();" in script
    assert "restoreRecipeCalculatorShoppingListSort();" in script
    assert 'header.getAttribute("aria-sort") === sortState.direction' in script
    assert 'header.getAttribute("aria-sort") !== sortState.direction' in script


def test_recipe_calculator_sale_submit_is_single_use_and_cleans_successful_cart_items() -> None:
    calculator_script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/recipe-calculator.js")
        .read_text(encoding="utf-8")
    )
    sales_script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/sales.js")
        .read_text(encoding="utf-8")
    )

    assert 'document.querySelector(".calculator-sales-form")' in calculator_script
    assert 'document.querySelector("#calculator-sale-select-all")' in calculator_script
    assert 'calculatorSalesForm.querySelectorAll(".calculator-sale-checkbox")' in (
        calculator_script
    )
    assert 'calculatorSaleSelectAll.addEventListener("change"' in calculator_script
    assert "checkbox.checked = calculatorSaleSelectAll.checked;" in calculator_script
    assert "calculatorSaleSelectAll.indeterminate" in calculator_script
    assert 'calculatorSalesForm.addEventListener("submit", (event)' in calculator_script
    assert 'calculatorSalesForm.dataset.submitting === "true"' in calculator_script
    assert "event.preventDefault();" in calculator_script
    assert "submitButton.disabled = true;" in calculator_script
    assert 'submitButton.textContent = "Adding to Sales…"' in calculator_script
    assert '"dofus-recipe-calculator-pending-sales-v1"' in calculator_script
    assert 'window.addEventListener("pageshow", (event)' in calculator_script
    assert "window.location.reload();" in calculator_script
    assert 'parameters.get("notice") !== "listings-added"' in sales_script
    assert "delete cart[itemUuid]" in sales_script
    assert "selection.filter((itemUuid) => !itemUuids.has(itemUuid))" in sales_script


def test_recipe_cart_uses_an_optional_validated_craft_quantity() -> None:
    script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/recipe-cart.js")
        .read_text(encoding="utf-8")
    )

    assert "Number(button.dataset.craftQuantity || 1)" in script
    assert "Number.isInteger(requestedQuantity)" in script
    assert "requestedQuantity >= 1" in script
    assert "requestedQuantity <= 1000" in script
    assert "? requestedQuantity" in script
    assert ": 1;" in script
    assert "craftQuantity.value = String(quantity)" in script


def test_recipe_cart_supports_opt_in_add_remove_toggles() -> None:
    script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/recipe-cart.js")
        .read_text(encoding="utf-8")
    )

    assert 'const isToggle = button.dataset.cartToggle === "true";' in script
    assert "button.disabled = isAdded && !isToggle;" in script
    assert 'button.setAttribute("aria-pressed", String(isAdded));' in script
    assert "? button.dataset.removeAriaLabel" in script
    assert ": button.dataset.addAriaLabel;" in script
    assert 'button.dataset.cartToggle === "true" && Object.hasOwn(cart, itemUuid)' in script
    assert "delete cart[itemUuid];" in script
    assert "selectedItems.delete(itemUuid);" in script


def test_item_detail_scripts_do_not_redeclare_recipe_cart_storage_constants() -> None:
    static_assets = resources.files("dofus_touch_economy").joinpath("static")
    sales_script = static_assets.joinpath("sales.js").read_text(encoding="utf-8")
    cart_script = static_assets.joinpath("recipe-cart.js").read_text(encoding="utf-8")

    assert "const salesRecipeCartStorageKey" in sales_script
    assert "const salesRecipeSelectionStorageKey" in sales_script
    assert "const recipeCartStorageKey" not in sales_script
    assert "const recipeSelectionStorageKey" not in sales_script
    assert "const recipeCartStorageKey" in cart_script
    assert "const recipeSelectionStorageKey" in cart_script


def test_every_web_table_has_client_or_server_sorting() -> None:
    templates = resources.files("dofus_touch_economy").joinpath("templates")
    expected_server_sorted = {
        "best_sellers.html": 0,
        "fragments/item_results.html": 1,
        "item_detail.html": 0,
        "fragments/price_panel.html": 0,
        "out_of_stock_items.html": 0,
        "profit_opportunities.html": 0,
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


def test_multiselect_options_are_compact_non_reflowing_popovers() -> None:
    stylesheet = (
        resources.files("dofus_touch_economy")
        .joinpath("static/app.css")
        .read_text(encoding="utf-8")
    )

    options_rule = stylesheet.split(".filter-multiselect-options {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    checkbox_rule = stylesheet.split(
        '.filter-multiselect-options input[type="checkbox"] {', maxsplit=1
    )[1].split("}", maxsplit=1)[0]
    assert "position: absolute;" in options_rule
    assert "font-size: 0.9rem;" in options_rule
    assert "max-height: 14rem;" in options_rule
    assert "min-height: 0;" in checkbox_rule


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


def test_best_sellers_uses_compact_table_with_accessible_row_details() -> None:
    stylesheet = (
        resources.files("dofus_touch_economy")
        .joinpath("static/app.css")
        .read_text(encoding="utf-8")
    )
    template = (
        resources.files("dofus_touch_economy")
        .joinpath("templates/best_sellers.html")
        .read_text(encoding="utf-8")
    )

    best_sellers_rule = stylesheet.split(".best-sellers-table {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    assert "min-width: 64rem;" in best_sellers_rule
    assert '<details class="row-details">' in template
    assert "Average Sale Price" in template
    assert "Average Days to Sell" in template


def test_calculator_sales_form_uses_full_width_block_layout() -> None:
    stylesheet = (
        resources.files("dofus_touch_economy")
        .joinpath("static/app.css")
        .read_text(encoding="utf-8")
    )

    sales_form_rule = stylesheet.split(".calculator-sales-form {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    sales_actions_rule = stylesheet.split(
        ".calculator-sales-form .calculator-submit-actions {", maxsplit=1
    )[1].split("}", maxsplit=1)[0]

    assert "display: block;" in sales_form_rule
    assert "margin-block-start: 0.75rem;" in sales_actions_rule


def test_navigation_dropdowns_are_alphabetized_and_close_exclusively() -> None:
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
    script = (
        resources.files("dofus_touch_economy")
        .joinpath("static/site-navigation.js")
        .read_text(encoding="utf-8")
    )

    assert '<details class="site-menu">' in template
    assert ".site-menu[open] .site-submenu" in stylesheet
    assert ".site-menu:hover .site-submenu" not in stylesheet
    assert ".site-menu:focus-within .site-submenu" not in stylesheet
    assert '<script src="/static/site-navigation.js" defer></script>' in template
    assert 'menu.addEventListener("toggle"' in script
    assert "closeSiteMenus(menu)" in script
    assert 'document.addEventListener("pointerdown"' in script
    assert 'document.addEventListener("focusin"' in script
    assert 'event.key !== "Escape"' in script

    item_menu, sales_menu = template.split('aria-label="Sales navigation"', maxsplit=1)
    assert (
        item_menu.index(">Item Search</a>")
        < item_menu.index(">Recipe Calculator</a>")
        < item_menu.index(">Recipes</a>")
    )
    assert (
        sales_menu.index(">Activity</a>")
        < sales_menu.index(">Best Sellers</a>")
        < sales_menu.index(">Out of Stock Items</a>")
        < sales_menu.index(">Profit Opportunities</a>")
    )
