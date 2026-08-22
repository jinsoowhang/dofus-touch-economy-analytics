from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dofus_touch_economy.icon_fetcher import (
    TOUCH_CONFIG_URL,
    JsonFetcher,
    _fetch_json,
    _trusted_config_url,
)
from dofus_touch_economy.models import (
    ImportBatch,
    Item,
    Recipe,
    RecipeIngredient,
    SourceItemName,
    SourceRecord,
)
from dofus_touch_economy.normalization import normalize_item_name

DATASET = "dofus_touch_live_recipes"
SOURCE_FILENAME = "ankama-live-recipes-en.json"


@dataclass(frozen=True)
class RecipeSyncSummary:
    source_count: int
    recipe_count: int
    ingredient_count: int
    created_batch: bool
    checksum: str


@dataclass(frozen=True)
class _IngredientCandidate:
    item_id: int
    display_name: str
    normalized_name: str
    category: str
    quantity: int


@dataclass(frozen=True)
class _RecipeCandidate:
    result_id: int
    display_name: str
    normalized_name: str
    category: str
    profession: str
    ingredients: tuple[_IngredientCandidate, ...]
    raw_payload: dict[str, Any]


def sync_touch_recipes(
    session_factory: sessionmaker[Session],
    *,
    json_fetcher: JsonFetcher | None = None,
) -> RecipeSyncSummary:
    fetch_json = json_fetcher or _fetch_json
    config = fetch_json(TOUCH_CONFIG_URL, None)
    data_url = _trusted_config_url(config, "dataUrl", ".ankama-games.com")
    endpoint = f"{data_url.rstrip('/')}/data/map"
    items_payload = fetch_json(endpoint, {"class": "Items", "lang": "en"})
    types_payload = fetch_json(endpoint, {"class": "ItemTypes", "lang": "en"})
    recipes_payload = fetch_json(endpoint, {"class": "Recipes", "lang": "en"})
    candidates = _recipe_candidates(items_payload, types_payload, recipes_payload)
    checksum = _candidate_checksum(candidates)
    ingredient_count = sum(len(candidate.ingredients) for candidate in candidates)

    with session_factory() as session:
        existing_batch = session.scalar(
            select(ImportBatch).where(
                ImportBatch.dataset == DATASET,
                ImportBatch.checksum == checksum,
                ImportBatch.status == "completed",
            )
        )
        if existing_batch is not None:
            return RecipeSyncSummary(
                source_count=len(candidates),
                recipe_count=0,
                ingredient_count=0,
                created_batch=False,
                checksum=checksum,
            )

        resolved = _resolve_candidates(session, candidates)
        batch = ImportBatch(
            dataset=DATASET,
            filename=SOURCE_FILENAME,
            checksum=checksum,
            accepted_count=len(candidates),
            rejected_count=0,
            warning_count=0,
            status="started",
        )
        session.add(batch)

        for row_number, (candidate, crafted_item, ingredient_items) in enumerate(resolved, start=1):
            record = SourceRecord(
                import_batch=batch,
                row_number=row_number,
                raw_payload_json=json.dumps(
                    candidate.raw_payload, ensure_ascii=False, sort_keys=True
                ),
                status="accepted",
                validation_messages_json="[]",
            )
            recipe = Recipe(
                crafted_item=crafted_item,
                profession=candidate.profession,
                source_record=record,
            )
            record.source_item_names.append(
                SourceItemName(
                    source_field="recipe_item",
                    position=0,
                    raw_name=candidate.display_name,
                    normalized_name=candidate.normalized_name,
                    item=crafted_item,
                    resolution_status="matched",
                )
            )
            for position, (ingredient, ingredient_item) in enumerate(
                zip(candidate.ingredients, ingredient_items, strict=True), start=1
            ):
                record.source_item_names.append(
                    SourceItemName(
                        source_field=f"raw_material_{position}",
                        position=position,
                        raw_name=ingredient.display_name,
                        normalized_name=ingredient.normalized_name,
                        item=ingredient_item,
                        resolution_status="matched",
                    )
                )
                recipe.ingredients.append(
                    RecipeIngredient(
                        position=position,
                        item=ingredient_item,
                        raw_name=ingredient.display_name,
                        normalized_name=ingredient.normalized_name,
                        quantity=ingredient.quantity,
                    )
                )
            session.add(record)

        batch.status = "completed"
        batch.completed_at = datetime.now(UTC)
        session.commit()

    return RecipeSyncSummary(
        source_count=len(candidates),
        recipe_count=len(candidates),
        ingredient_count=ingredient_count,
        created_batch=True,
        checksum=checksum,
    )


def _recipe_candidates(
    items_payload: Any,
    types_payload: Any,
    recipes_payload: Any,
) -> list[_RecipeCandidate]:
    if not isinstance(items_payload, dict) or not isinstance(types_payload, dict):
        raise ValueError("Dofus Touch item payloads must be objects")
    if not isinstance(recipes_payload, dict):
        raise ValueError("Dofus Touch recipe payload must be an object")

    item_types = {
        value["id"]: value["nameId"].strip()
        for value in types_payload.values()
        if isinstance(value, dict)
        and isinstance(value.get("id"), int)
        and isinstance(value.get("nameId"), str)
        and value["nameId"].strip()
    }
    items = {
        value["id"]: value
        for value in items_payload.values()
        if isinstance(value, dict) and isinstance(value.get("id"), int)
    }
    candidates: list[_RecipeCandidate] = []
    seen_result_ids: set[int] = set()
    for value in recipes_payload.values():
        if not isinstance(value, dict):
            raise ValueError("Dofus Touch recipe rows must be objects")
        result_id = value.get("resultId")
        result = items.get(result_id) if isinstance(result_id, int) else None
        if result is None:
            raise ValueError(f"recipe result item is missing: {result_id!r}")
        if result.get("exchangeable") is not True:
            continue
        if result_id in seen_result_ids:
            raise ValueError(f"duplicate recipe result item: {result_id}")
        seen_result_ids.add(result_id)

        display_name, normalized_name, category = _item_identity(result, item_types)
        profession = value.get("jobName")
        ingredient_ids = value.get("ingredientIds")
        quantities = value.get("quantities")
        if not isinstance(profession, str) or not profession.strip():
            raise ValueError(f"recipe profession is missing for item {result_id}")
        if (
            not isinstance(ingredient_ids, list)
            or not isinstance(quantities, list)
            or len(ingredient_ids) != len(quantities)
            or not 1 <= len(ingredient_ids) <= 8
        ):
            raise ValueError(f"recipe ingredients are invalid for item {result_id}")

        ingredients: list[_IngredientCandidate] = []
        for ingredient_id, quantity in zip(ingredient_ids, quantities, strict=True):
            ingredient = items.get(ingredient_id) if isinstance(ingredient_id, int) else None
            if ingredient is None or not isinstance(quantity, int) or quantity <= 0:
                raise ValueError(f"recipe ingredient is invalid for item {result_id}")
            ingredient_name, ingredient_normalized_name, ingredient_category = _item_identity(
                ingredient, item_types
            )
            ingredients.append(
                _IngredientCandidate(
                    item_id=ingredient_id,
                    display_name=ingredient_name,
                    normalized_name=ingredient_normalized_name,
                    category=ingredient_category,
                    quantity=quantity,
                )
            )

        candidates.append(
            _RecipeCandidate(
                result_id=result_id,
                display_name=display_name,
                normalized_name=normalized_name,
                category=category,
                profession=profession.strip(),
                ingredients=tuple(ingredients),
                raw_payload=value,
            )
        )
    return sorted(candidates, key=lambda candidate: candidate.result_id)


def _item_identity(item: dict[str, Any], item_types: dict[int, str]) -> tuple[str, str, str]:
    display_name = item.get("nameId")
    category = item_types.get(item.get("typeId"))
    if not isinstance(display_name, str) or not display_name.strip() or category is None:
        raise ValueError(f"item identity is incomplete: {item.get('id')!r}")
    clean_name = display_name.strip()
    return clean_name, normalize_item_name(clean_name), normalize_item_name(category)


def _candidate_checksum(candidates: list[_RecipeCandidate]) -> str:
    payload = [asdict(candidate) for candidate in candidates]
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(serialized).hexdigest()


def _resolve_candidates(
    session: Session,
    candidates: list[_RecipeCandidate],
) -> list[tuple[_RecipeCandidate, Item, tuple[Item, ...]]]:
    items = list(session.scalars(select(Item).order_by(Item.id)))
    by_identity = {(item.normalized_name, item.identity_category): item for item in items}
    by_name: defaultdict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_name[item.normalized_name].append(item)

    def resolve(normalized_name: str, category: str) -> Item | None:
        exact = by_identity.get((normalized_name, category))
        if exact is not None:
            return exact
        matches = by_name[normalized_name]
        return matches[0] if len(matches) == 1 else None

    resolved: list[tuple[_RecipeCandidate, Item, tuple[Item, ...]]] = []
    unresolved: set[str] = set()
    for candidate in candidates:
        crafted_item = resolve(candidate.normalized_name, candidate.category)
        ingredient_items = tuple(
            resolve(ingredient.normalized_name, ingredient.category)
            for ingredient in candidate.ingredients
        )
        if crafted_item is None:
            unresolved.add(candidate.display_name)
        unresolved.update(
            ingredient.display_name
            for ingredient, item in zip(candidate.ingredients, ingredient_items, strict=True)
            if item is None
        )
        if crafted_item is not None and all(item is not None for item in ingredient_items):
            resolved.append(
                (
                    candidate,
                    crafted_item,
                    tuple(item for item in ingredient_items if item is not None),
                )
            )
    if unresolved:
        sample = ", ".join(sorted(unresolved)[:10])
        raise ValueError(
            f"{len(unresolved)} recipe item names are not in the local catalog; "
            f"run dofus-sync-catalog first (sample: {sample})"
        )
    return resolved
