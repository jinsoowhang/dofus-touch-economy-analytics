from sqlalchemy import func, select

from dofus_touch_economy.models import (
    ImportBatch,
    Item,
    Recipe,
    RecipeIngredient,
    SourceItemName,
    SourceRecord,
)
from dofus_touch_economy.recipe_sync import DATASET, sync_touch_recipes


def test_syncs_live_recipes_with_provenance_idempotently(session_factory) -> None:
    with session_factory() as session:
        items = [
            Item(
                display_name="Abyss Necklace",
                normalized_name="abyss necklace",
                category="Amulet",
                identity_category="amulet",
            ),
            Item(
                display_name="Iridescent Orb",
                normalized_name="iridescent orb",
                category="Resource",
                identity_category="resource",
            ),
            Item(
                display_name="Thermite Leg",
                normalized_name="thermite leg",
                category="Resource",
                identity_category="resource",
            ),
        ]
        session.add_all(items)
        session.commit()

    items_payload = {
        "16030": {
            "id": 16030,
            "nameId": "Abyss Necklace",
            "typeId": 1,
            "exchangeable": True,
        },
        "15748": {
            "id": 15748,
            "nameId": "Iridescent Orb",
            "typeId": 2,
            "exchangeable": True,
        },
        "13943": {
            "id": 13943,
            "nameId": "Thermite Leg",
            "typeId": 2,
            "exchangeable": True,
        },
    }
    types_payload = {
        "1": {"id": 1, "nameId": "Amulet"},
        "2": {"id": 2, "nameId": "Material"},
    }
    recipes_payload = {
        "16030": {
            "resultId": 16030,
            "resultLevel": 200,
            "ingredientIds": [15748, 13943],
            "quantities": [54, 76],
            "jobId": 16,
            "jobName": "Jeweller",
        }
    }

    def fetch_json(url, payload):
        if "config.json" in url:
            return {"dataUrl": "https://data.ankama-games.com"}
        if payload == {"class": "Items", "lang": "en"}:
            return items_payload
        if payload == {"class": "ItemTypes", "lang": "en"}:
            return types_payload
        if payload == {"class": "Recipes", "lang": "en"}:
            return recipes_payload
        raise AssertionError(f"unexpected request: {url} {payload}")

    summary = sync_touch_recipes(session_factory, json_fetcher=fetch_json)

    assert summary.source_count == 1
    assert summary.recipe_count == 1
    assert summary.ingredient_count == 2
    assert summary.created_batch is True
    with session_factory() as session:
        batch = session.scalar(select(ImportBatch).where(ImportBatch.dataset == DATASET))
        recipe = session.scalar(select(Recipe))
        ingredient_rows = list(
            session.scalars(select(RecipeIngredient).order_by(RecipeIngredient.position))
        )
        source_names = list(session.scalars(select(SourceItemName)))
        assert batch is not None
        assert batch.status == "completed"
        assert batch.accepted_count == 1
        assert recipe is not None
        assert recipe.crafted_item.display_name == "Abyss Necklace"
        assert recipe.profession == "Jeweller"
        assert [(row.raw_name, row.quantity) for row in ingredient_rows] == [
            ("Iridescent Orb", 54),
            ("Thermite Leg", 76),
        ]
        assert all(row.item_id is not None for row in ingredient_rows)
        assert len(source_names) == 3
        assert {row.resolution_status for row in source_names} == {"matched"}

    repeated = sync_touch_recipes(session_factory, json_fetcher=fetch_json)

    assert repeated.created_batch is False
    assert repeated.recipe_count == 0
    assert repeated.ingredient_count == 0
    with session_factory() as session:
        assert session.scalar(select(func.count(ImportBatch.id))) == 1
        assert session.scalar(select(func.count(SourceRecord.id))) == 1
        assert session.scalar(select(func.count(Recipe.id))) == 1
        assert session.scalar(select(func.count(RecipeIngredient.id))) == 2


def test_sync_requires_every_recipe_name_to_exist_in_catalog(session_factory, catalog_item) -> None:
    def fetch_json(url, payload):
        if "config.json" in url:
            return {"dataUrl": "https://data.ankama-games.com"}
        if payload == {"class": "Items", "lang": "en"}:
            return {
                "1": {
                    "id": 1,
                    "nameId": "Missing Product",
                    "typeId": 1,
                    "exchangeable": True,
                },
                "2": {
                    "id": 2,
                    "nameId": catalog_item.display_name,
                    "typeId": 1,
                    "exchangeable": True,
                },
            }
        if payload == {"class": "ItemTypes", "lang": "en"}:
            return {"1": {"id": 1, "nameId": "Ore"}}
        if payload == {"class": "Recipes", "lang": "en"}:
            return {
                "1": {
                    "resultId": 1,
                    "ingredientIds": [2],
                    "quantities": [1],
                    "jobName": "Miner",
                }
            }
        raise AssertionError(f"unexpected request: {url} {payload}")

    try:
        sync_touch_recipes(session_factory, json_fetcher=fetch_json)
    except ValueError as error:
        assert "run dofus-sync-catalog first" in str(error)
    else:
        raise AssertionError("expected missing catalog items to stop the sync")

    with session_factory() as session:
        assert session.scalar(select(func.count(ImportBatch.id))) == 0
