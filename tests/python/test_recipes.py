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
        )
        beta = Item(
            display_name="Beta Ring",
            normalized_name="beta ring",
            category="Ring",
            identity_category="ring",
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
                item_query="alpha",
                category="sword",
                profession="Sword Smith",
                minimum_level=20,
                maximum_level=20,
                economics="profitable",
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
    assert [row.display_name for row in result.rows] == ["Alpha Sword"]
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

    assert [row.display_name for row in result.rows] == [
        "Alpha Sword",
        "Beta Ring",
        "Gamma Hat",
    ]
    assert [row.active_listing_count for row in result.rows] == [2, 1, 0]


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
    assert report.top_profit_item is newly_priced
    assert report.top_roi_item is newly_priced
    assert [item.display_name for item in not_selling_report.items] == ["Delta Shield"]
    assert not_selling_report.total_count == 1


def test_recipe_calculator_aggregates_duplicate_ingredients_and_costs(
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
    assert [item.display_name for item in result.selected_items] == [
        "Alpha Sword",
        "Beta Ring",
    ]
    assert [item.category for item in result.selected_items] == ["Sword", "Ring"]
    assert [item.craft_quantity for item in result.selected_items] == [2, 3]
    assert [item.recipe_unit_cost for item in result.selected_items] == [80, 400]
    assert [item.total_recipe_cost for item in result.selected_items] == [160, 1200]
    assert result.total_crafts == 5
    assert len(result.ingredients) == 1
    assert result.ingredients[0].display_name == "Synthetic Wood"
    assert result.ingredients[0].category == "Wood"
    assert result.ingredients[0].total_quantity == 136
    assert result.ingredients[0].unit_weight == 2
    assert result.ingredients[0].total_weight == 272
    assert result.ingredients[0].unit_price == 10
    assert result.ingredients[0].total_cost == 1360
    assert result.ingredients[0].price_age_days == 0
    assert result.ingredients[0].price_status == "Current price"
    assert result.ingredients[0].used_by == ("Alpha Sword", "Beta Ring")
    assert result.priced_ingredient_count == 1
    assert result.known_total_cost == 1360
    assert result.total_cost == 1360
    assert result.weighted_ingredient_count == 1
    assert result.known_total_weight == 272
    assert result.total_weight == 272


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
    assert suggestions[1].shared_ingredient_count == 1
    assert suggestions[1].ingredient_count == 2
    assert suggestions[1].overlap_percent == 50
    assert suggestions[1].matching_selected_item_count == 2


def test_recipe_calculator_rejects_noncraftable_selection(session_factory) -> None:
    items = seed_recipe_catalog(session_factory)

    with session_factory() as session:
        service = RecipeCalculatorService(session, "Dodge")
        with pytest.raises(RecipeCalculatorSelectionError, match="no longer has"):
            service.calculate({items["ingredient"].uuid: 1})
