from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from dofus_touch_economy.database import Base, create_engine_for_url, create_session_factory
from dofus_touch_economy.models import (
    ImportBatch,
    Item,
    PriceObservation,
    Recipe,
    RecipeIngredient,
    SaleListing,
    SourceRecord,
)


@pytest.fixture
def session():
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as database_session:
        yield database_session
    engine.dispose()


def make_source_record(session) -> SourceRecord:
    batch = ImportBatch(
        dataset="item_recipes",
        filename="item_recipes.csv",
        checksum="a" * 64,
        status="completed",
    )
    session.add(batch)
    session.flush()
    record = SourceRecord(
        import_batch_id=batch.id,
        row_number=2,
        raw_payload_json="{}",
        status="accepted",
        validation_messages_json="[]",
    )
    session.add(record)
    session.flush()
    return record


def make_recipe(session) -> Recipe:
    item = Item(display_name="Sword", normalized_name="sword", identity_category="weapon")
    session.add(item)
    session.flush()
    recipe = Recipe(
        crafted_item_id=item.id,
        profession="Smith",
        source_record_id=make_source_record(session).id,
    )
    session.add(recipe)
    session.flush()
    return recipe


def test_price_observation_rejects_nonpositive_lot_quantity(session) -> None:
    item = Item(display_name="Iron", normalized_name="iron", identity_category="ore")
    session.add(item)
    session.flush()
    session.add(
        PriceObservation(
            item_id=item.id,
            lot_quantity=0,
            total_price=100,
            observed_at=datetime.now(UTC),
            market_context="Dodge",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_item_creation_source_is_constrained(session) -> None:
    session.add(
        Item(
            display_name="Iron",
            normalized_name="iron",
            identity_category="ore",
            created_source="unknown",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_sale_listing_rejects_nonpositive_lot_quantity(session) -> None:
    item = Item(display_name="Iron", normalized_name="iron", identity_category="ore")
    session.add(item)
    session.flush()
    session.add(SaleListing(item_id=item.id, lot_quantity=0))

    with pytest.raises(IntegrityError):
        session.commit()


def test_sale_listing_rejects_nonpositive_asking_price(session) -> None:
    item = Item(display_name="Iron", normalized_name="iron", identity_category="ore")
    session.add(item)
    session.flush()
    session.add(SaleListing(item_id=item.id, lot_quantity=1, asking_price=0))

    with pytest.raises(IntegrityError):
        session.commit()


def test_recipe_ingredient_position_is_unique(session) -> None:
    recipe = make_recipe(session)
    session.add_all(
        [
            RecipeIngredient(
                recipe_id=recipe.id,
                position=1,
                raw_name="A",
                normalized_name="a",
                quantity=1,
            ),
            RecipeIngredient(
                recipe_id=recipe.id,
                position=1,
                raw_name="B",
                normalized_name="b",
                quantity=1,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_invalidation_timestamp_and_reason_must_be_paired(session) -> None:
    item = Item(display_name="Iron", normalized_name="iron", identity_category="ore")
    session.add(item)
    session.flush()
    session.add(
        PriceObservation(
            item_id=item.id,
            lot_quantity=1,
            total_price=100,
            observed_at=datetime.now(UTC),
            market_context="Dodge",
            invalidation_reason="incorrect listing",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
