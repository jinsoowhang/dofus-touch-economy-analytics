from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from dofus_touch_economy.models import (
    ImportBatch,
    Item,
    Recipe,
    RecipeIngredient,
    SaleListing,
    SourceRecord,
)
from dofus_touch_economy.schemas import PriceObservationCreate
from dofus_touch_economy.services.pricing import PriceService
from dofus_touch_economy.services.recipes import (
    RecipeCalculatorSelectionError,
    RecipeCalculatorService,
    RecipeCatalogFilters,
    RecipeCatalogService,
    required_profession_level,
)


@pytest.mark.parametrize(
    ("ingredient_count", "expected_level"),
    [(0, None), (1, 1), (2, 1), (3, 10), (4, 20), (5, 40), (6, 60), (7, 80), (8, 100), (9, None)],
)
def test_required_profession_level_uses_recipe_slot_unlocks(
    ingredient_count,
    expected_level,
) -> None:
    assert required_profession_level(ingredient_count) == expected_level


def seed_recipe_catalog(session_factory) -> dict[str, Item]:
    with session_factory() as session:
        ingredient = Item(
            display_name="Synthetic Wood",
            normalized_name="synthetic wood",
            category="Wood",
            identity_category="wood",
            weight=2,
        )
        alpha = Item(
            display_name="Alpha Sword",
            normalized_name="alpha sword",
            category="Sword",
            identity_category="sword",
            icon_source_url="https://example.invalid/alpha.png",
        )
        beta = Item(
            display_name="Beta Ring",
            normalized_name="beta ring",
            category="Ring",
            identity_category="ring",
            icon_source_url="https://example.invalid/beta.png",
        )
        gamma = Item(
            display_name="Gamma Hat",
            normalized_name="gamma hat",
            category="Hat",
            identity_category="hat",
        )
        session.add_all([ingredient, alpha, beta, gamma])
        session.flush()
        batch = ImportBatch(
            dataset="synthetic_recipes",
            filename="synthetic.json",
            checksum="b" * 64,
            accepted_count=3,
            status="completed",
        )
        session.add(batch)
        for row_number, item, profession, ingredient_count, quantity in (
            (1, alpha, "Sword Smith", 4, 2),
            (2, beta, "Jeweller", 8, 5),
            (3, gamma, "Tailor", 0, 3),
        ):
            record = SourceRecord(
                import_batch=batch,
                row_number=row_number,
                raw_payload_json="{}",
                status="accepted",
            )
            recipe = Recipe(
                crafted_item=item,
                profession=profession,
                source_record=record,
            )
            for position in range(1, ingredient_count + 1):
                recipe.ingredients.append(
                    RecipeIngredient(
                        position=position,
                        item=ingredient,
                        raw_name=ingredient.display_name,
                        normalized_name=ingredient.normalized_name,
                        quantity=quantity,
                    )
                )
            session.add(recipe)
        session.commit()

        prices = PriceService(session, "Dodge")
        observed_at = datetime(2026, 8, 22, tzinfo=UTC)
        for item, price in ((ingredient, 10), (alpha, 100), (beta, 30)):
            prices.record(
                item.uuid,
                PriceObservationCreate(
                    lot_quantity=1,
                    total_price=price,
                    observed_at=observed_at,
                ),
            )
        return {
            "ingredient": ingredient,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
        }


def test_recipe_catalog_filters_and_calculates_current_economics(session_factory) -> None:
    seed_recipe_catalog(session_factory)

    with session_factory() as session:
        result = RecipeCatalogService(session, "Dodge").browse(
            RecipeCatalogFilters(
                categories=("sword", "ring"),
                professions=("Sword Smith", "Jeweller"),
                minimum_level=20,
                maximum_level=100,
            )
        )

    assert result.total_count == 3
    assert result.minimum_available_level == 20
    assert result.maximum_available_level == 100
    assert result.professions == ["Jeweller", "Sword Smith", "Tailor"]
    assert [(choice.key, choice.label) for choice in result.categories] == [
        ("hat", "Hat"),
        ("ring", "Ring"),
        ("sword", "Sword"),
    ]
    assert [row.display_name for row in result.rows] == ["Alpha Sword", "Beta Ring"]
    assert result.rows[0].current_price == 100
    assert result.rows[0].recipe_cost == 80
    assert result.rows[0].profit == 20
    assert result.rows[0].roi == Decimal("0.25")


def test_recipe_catalog_filters_profitability_and_sorts_missing_values_last(
    session_factory,
) -> None:
    seed_recipe_catalog(session_factory)

    with session_factory() as session:
        service = RecipeCatalogService(session, "Dodge")
        non_profitable = service.browse(RecipeCatalogFilters(economics="non_profitable"))
        unknown = service.browse(RecipeCatalogFilters(economics="unknown"))
        ordered = service.browse(sort_field="profit", sort_direction="desc")

    assert [row.display_name for row in non_profitable.rows] == ["Beta Ring"]
    assert [row.display_name for row in unknown.rows] == ["Gamma Hat"]
    assert [row.display_name for row in ordered.rows] == [
        "Alpha Sword",
        "Beta Ring",
        "Gamma Hat",
    ]


def test_recipe_catalog_paginates_after_filtering_and_sorting(session_factory) -> None:
    seed_recipe_catalog(session_factory)

    with session_factory() as session:
        result = RecipeCatalogService(session, "Dodge").browse(
            sort_field="name",
            sort_direction="asc",
            page=2,
            page_size=2,
        )

    assert result.total_count == 3
    assert result.filtered_count == 3
    assert result.page == 2
    assert result.page_count == 2
    assert [row.display_name for row in result.rows] == ["Gamma Hat"]


def test_recipe_catalog_excludes_confirmed_non_touch_crafted_item(session_factory) -> None:
    items = seed_recipe_catalog(session_factory)
    with session_factory() as session:
        excluded_item = session.get(Item, items["alpha"].id)
        assert excluded_item is not None
        excluded_item.display_name = "Violet Arrow Helmet"
        excluded_item.normalized_name = "violet arrow helmet"
        excluded_item.category = "Hat"
        excluded_item.identity_category = "hat"
        excluded_item.touch_catalog_status = "excluded"
        session.commit()

        result = RecipeCatalogService(session, "Dodge").browse()

    assert result.total_count == 2
    assert [row.display_name for row in result.rows] == ["Beta Ring", "Gamma Hat"]


def test_recipe_catalog_excludes_recipe_with_non_touch_ingredient(session_factory) -> None:
    items = seed_recipe_catalog(session_factory)
    with session_factory() as session:
        excluded_ingredient = session.get(Item, items["ingredient"].id)
        assert excluded_ingredient is not None
        excluded_ingredient.touch_catalog_status = "excluded"
        session.commit()

        result = RecipeCatalogService(session, "Dodge").browse()

    assert result.total_count == 1
    assert [row.display_name for row in result.rows] == ["Gamma Hat"]


def test_recipe_catalog_counts_and_sorts_active_listings(session_factory) -> None:
    items = seed_recipe_catalog(session_factory)
    with session_factory() as session:
        session.add_all(
            [
                SaleListing(
                    item_id=items["alpha"].id,
                    lot_quantity=1,
                    asking_price=100,
                ),
                SaleListing(
                    item_id=items["alpha"].id,
                    lot_quantity=1,
                    asking_price=110,
                ),
                SaleListing(
                    item_id=items["beta"].id,
                    lot_quantity=1,
                    asking_price=30,
                ),
            ]
        )
        session.commit()

        result = RecipeCatalogService(session, "Dodge").browse(
            sort_field="active",
            sort_direction="desc",
        )
        not_selling = RecipeCatalogService(session, "Dodge").browse(
            RecipeCatalogFilters(not_currently_selling=True)
        )

    assert [row.display_name for row in result.rows] == [
        "Alpha Sword",
        "Beta Ring",
        "Gamma Hat",
    ]
    assert [row.active_listing_count for row in result.rows] == [2, 1, 0]
    assert [row.display_name for row in not_selling.rows] == ["Gamma Hat"]
    assert not_selling.filtered_count == 1


def test_profit_opportunities_include_improving_and_newly_priced_unsold_recipes(
    session_factory,
) -> None:
    items = seed_recipe_catalog(session_factory)
    with session_factory() as session:
        batch = session.scalar(select(ImportBatch))
        assert batch is not None
        fresh_material = Item(
            display_name="Fresh Material",
            normalized_name="fresh material",
            category="Resource",
            identity_category="resource",
        )
        delta = Item(
            display_name="Delta Shield",
            normalized_name="delta shield",
            category="Shield",
            identity_category="shield",
        )
        session.add_all([fresh_material, delta])
        session.flush()
        record = SourceRecord(
            import_batch=batch,
            row_number=4,
            raw_payload_json="{}",
            status="accepted",
        )
        recipe = Recipe(
            crafted_item=delta,
            profession="Shield Smith",
            source_record=record,
        )
        recipe.ingredients.append(
            RecipeIngredient(
                position=1,
                item=fresh_material,
                raw_name=fresh_material.display_name,
                normalized_name=fresh_material.normalized_name,
                quantity=1,
            )
        )
        session.add(recipe)
        session.commit()

        prices = PriceService(session, "Dodge")
        prices.record(
            items["ingredient"].uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=5,
                observed_at=datetime(2026, 8, 23, tzinfo=UTC),
            ),
        )
        prices.record(
            fresh_material.uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=20,
                observed_at=datetime(2026, 8, 23, tzinfo=UTC),
            ),
        )
        prices.record(
            delta.uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=100,
                observed_at=datetime(2026, 8, 23, tzinfo=UTC),
            ),
        )
        session.add(
            SaleListing(
                item_id=items["alpha"].id,
                lot_quantity=1,
                asking_price=100,
            )
        )
        session.commit()

        report = RecipeCatalogService(session, "Dodge").profit_opportunities()
        not_selling_report = RecipeCatalogService(session, "Dodge").profit_opportunities(
            not_currently_selling=True
        )
        shield_report = RecipeCatalogService(session, "Dodge").profit_opportunities(
            professions=("shield smith",)
        )

    assert [item.display_name for item in report.items] == [
        "Alpha Sword",
        "Delta Shield",
    ]
    improving, newly_priced = report.items
    assert improving.signal == "Improving"
    assert improving.recipe_cost == 40
    assert improving.profit == 60
    assert improving.roi == Decimal("1.5")
    assert improving.previous_recipe_cost == 80
    assert improving.previous_roi == Decimal("0.25")
    assert improving.roi_change == Decimal("1.25")
    assert improving.active_listing_count == 1
    assert improving.completed_sale_count == 0
    assert newly_priced.signal == "Newly priced"
    assert newly_priced.recipe_cost == 20
    assert newly_priced.profit == 80
    assert newly_priced.roi == 4
    assert newly_priced.previous_recipe_cost is None
    assert newly_priced.previous_roi is None
    assert newly_priced.active_listing_count == 0
    assert newly_priced.completed_sale_count == 0
    assert report.total_count == 2
    assert report.improving_count == 1
    assert report.newly_priced_count == 1
    assert report.professions == ("Jeweller", "Shield Smith", "Sword Smith", "Tailor")
    assert report.top_profit_item is newly_priced
    assert report.top_roi_item is newly_priced
    assert [item.display_name for item in not_selling_report.items] == ["Delta Shield"]
    assert not_selling_report.total_count == 1
    assert [item.display_name for item in shield_report.items] == ["Delta Shield"]
    assert shield_report.total_count == 1


def test_recipe_calculator_splits_shared_ingredients_by_craft_and_aggregates_slots(
    session_factory,
) -> None:
    items = seed_recipe_catalog(session_factory)

    with session_factory() as session:
        service = RecipeCalculatorService(
            session,
            "Dodge",
            as_of=datetime(2026, 8, 22, tzinfo=UTC),
        )
        choices = service.choices()
        result = service.calculate(
            {
                items["alpha"].uuid: 2,
                items["beta"].uuid: 3,
            }
        )

    assert {choice.display_name: choice.sale_price for choice in choices} == {
        "Alpha Sword": 100,
        "Beta Ring": 30,
        "Gamma Hat": None,
    }
    assert {choice.display_name: choice.recipe_cost for choice in choices} == {
        "Alpha Sword": 80,
        "Beta Ring": 400,
        "Gamma Hat": 0,
    }
    assert [item.display_name for item in result.selected_items] == [
        "Beta Ring",
        "Alpha Sword",
    ]
    assert [item.category for item in result.selected_items] == ["Ring", "Sword"]
    assert [item.craft_quantity for item in result.selected_items] == [3, 2]
    assert [item.recipe_unit_cost for item in result.selected_items] == [400, 80]
    assert [item.total_recipe_cost for item in result.selected_items] == [1200, 160]
    assert result.total_crafts == 5
    assert len(result.ingredients) == 2
    assert [ingredient.crafted_item_display_name for ingredient in result.ingredients] == [
        "Alpha Sword",
        "Beta Ring",
    ]
    assert [ingredient.crafted_item_uuid for ingredient in result.ingredients] == [
        items["alpha"].uuid,
        items["beta"].uuid,
    ]
    assert [ingredient.crafted_item_icon_url for ingredient in result.ingredients] == [
        f"/item-icons/{items['alpha'].uuid}.png",
        f"/item-icons/{items['beta'].uuid}.png",
    ]
    assert [ingredient.display_name for ingredient in result.ingredients] == [
        "Synthetic Wood",
        "Synthetic Wood",
    ]
    assert [ingredient.category for ingredient in result.ingredients] == ["Wood", "Wood"]
    assert [ingredient.total_quantity for ingredient in result.ingredients] == [16, 120]
    assert [ingredient.unit_weight for ingredient in result.ingredients] == [2, 2]
    assert [ingredient.total_weight for ingredient in result.ingredients] == [32, 240]
    assert [ingredient.unit_price for ingredient in result.ingredients] == [10, 10]
    assert [ingredient.total_cost for ingredient in result.ingredients] == [160, 1200]
    assert [ingredient.price_age_days for ingredient in result.ingredients] == [0, 0]
    assert [ingredient.price_status for ingredient in result.ingredients] == [
        "Current price",
        "Current price",
    ]
    assert result.unique_ingredient_count == 1
    assert result.priced_ingredient_count == 1
    assert result.known_total_cost == 1360
    assert result.total_cost == 1360
    assert result.weighted_ingredient_count == 1
    assert result.known_total_weight == 272
    assert result.total_weight == 272


def test_recipe_calculator_keeps_ingredients_in_source_order_within_each_craft(
    session_factory,
) -> None:
    items = seed_recipe_catalog(session_factory)
    with session_factory() as session:
        recipe = session.scalar(
            select(Recipe).join(Recipe.crafted_item).where(Item.uuid == items["alpha"].uuid)
        )
        assert recipe is not None
        ore = Item(
            display_name="Aardvark Ore",
            normalized_name="aardvark ore",
            category="Ore",
            identity_category="ore",
        )
        session.add(ore)
        session.flush()
        recipe.ingredients.append(
            RecipeIngredient(
                position=5,
                item=ore,
                raw_name=ore.display_name,
                normalized_name=ore.normalized_name,
                quantity=1,
            )
        )
        session.commit()
        PriceService(session, "Dodge").record(
            ore.uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=7,
                observed_at=datetime(2026, 8, 22, tzinfo=UTC),
            ),
        )

        result = RecipeCalculatorService(session, "Dodge").calculate({items["alpha"].uuid: 1})

    assert [ingredient.display_name for ingredient in result.ingredients] == [
        "Synthetic Wood",
        "Aardvark Ore",
    ]


def test_recipe_calculator_suggests_unselected_crafts_by_ingredient_overlap(
    session_factory,
) -> None:
    items = seed_recipe_catalog(session_factory)
    with session_factory() as session:
        batch = session.scalar(select(ImportBatch))
        wood = session.scalar(select(Item).where(Item.normalized_name == "synthetic wood"))
        assert batch is not None
        assert wood is not None
        ore = Item(
            display_name="Synthetic Ore",
            normalized_name="synthetic ore",
            category="Ore",
            identity_category="ore",
        )
        delta = Item(
            display_name="Delta Shield",
            normalized_name="delta shield",
            category="Shield",
            identity_category="shield",
        )
        epsilon = Item(
            display_name="Epsilon Boots",
            normalized_name="epsilon boots",
            category="Boots",
            identity_category="boots",
        )
        zeta = Item(
            display_name="Zeta Cloak",
            normalized_name="zeta cloak",
            category="Cloak",
            identity_category="cloak",
        )
        session.add_all([ore, delta, epsilon, zeta])
        session.flush()
        for row_number, crafted_item, recipe_ingredients in (
            (4, delta, (wood,)),
            (5, epsilon, (wood, ore)),
            (6, zeta, (ore,)),
        ):
            record = SourceRecord(
                import_batch=batch,
                row_number=row_number,
                raw_payload_json="{}",
                status="accepted",
            )
            recipe = Recipe(
                crafted_item=crafted_item,
                profession="Crafting",
                source_record=record,
            )
            for position, ingredient in enumerate(recipe_ingredients, start=1):
                recipe.ingredients.append(
                    RecipeIngredient(
                        position=position,
                        item=ingredient,
                        raw_name=ingredient.display_name,
                        normalized_name=ingredient.normalized_name,
                        quantity=1,
                    )
                )
            session.add(recipe)
        session.commit()
        session.add_all(
            [
                SaleListing(
                    item_id=delta.id,
                    lot_quantity=1,
                    asking_price=100,
                    selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=delta.id,
                    lot_quantity=1,
                    asking_price=100,
                    selling_started_at=datetime(2026, 8, 22, tzinfo=UTC),
                    date_sold=datetime(2026, 8, 23, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

    with session_factory() as session:
        service = RecipeCalculatorService(session, "Dodge")
        suggestions = service.suggest_similar((items["alpha"].uuid, items["beta"].uuid))
        with pytest.raises(RecipeCalculatorSelectionError, match="at least two"):
            service.suggest_similar((items["alpha"].uuid,))

    assert [suggestion.display_name for suggestion in suggestions] == [
        "Delta Shield",
        "Epsilon Boots",
    ]
    assert suggestions[0].shared_ingredient_count == 1
    assert suggestions[0].ingredient_count == 1
    assert suggestions[0].overlap_percent == 100
    assert suggestions[0].matching_selected_item_count == 2
    assert suggestions[0].active_listing_count == 1
    assert suggestions[0].completed_sale_count == 1
    assert suggestions[1].shared_ingredient_count == 1
    assert suggestions[1].ingredient_count == 2
    assert suggestions[1].overlap_percent == 50
    assert suggestions[1].matching_selected_item_count == 2
    assert suggestions[1].active_listing_count == 0
    assert suggestions[1].completed_sale_count == 0


def test_recipe_calculator_rejects_noncraftable_selection(session_factory) -> None:
    items = seed_recipe_catalog(session_factory)

    with session_factory() as session:
        service = RecipeCalculatorService(session, "Dodge")
        with pytest.raises(RecipeCalculatorSelectionError, match="no longer has"):
            service.calculate({items["ingredient"].uuid: 1})
