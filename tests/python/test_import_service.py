import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from dofus_touch_economy.importers.contracts import ContractError
from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import (
    ImportBatch,
    Item,
    PriceObservation,
    Recipe,
    RecipeIngredient,
    SaleListing,
    SourceItemName,
    SourceRecord,
)
from dofus_touch_economy.schemas import ItemCreate, PriceObservationCreate
from dofus_touch_economy.services.catalog import CatalogService
from dofus_touch_economy.services.pricing import PriceService


def test_import_is_idempotent(session_factory, fixture_dir: Path) -> None:
    service = ImportService(session_factory)
    first = service.import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    second = service.import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )

    assert first.created_batches == 2
    assert first.price_count == 2
    assert second.created_batches == 0
    assert second.price_count == 0
    with session_factory() as session:
        assert session.scalar(select(func.count(Item.id))) == 3
        assert session.scalar(select(func.count(Recipe.id))) == 1
        assert session.scalar(select(func.count(RecipeIngredient.id))) == 2
        assert session.scalar(select(func.count(PriceObservation.id))) == 2


def test_ambiguous_exact_name_remains_unresolved(session_factory, synthetic_files) -> None:
    synthetic_files.write_cost_rows([("Shared Name", "Ore", "1"), ("Shared Name", "Fiber", "2")])
    synthetic_files.write_recipe(ingredient="Shared Name", quantity="1")

    summary = ImportService(session_factory).import_files(*synthetic_files.paths)

    with session_factory() as session:
        ingredient = session.scalar(select(RecipeIngredient))
        source_name = session.scalar(
            select(SourceItemName).where(SourceItemName.source_field == "raw_material_1")
        )
        assert ingredient is not None
        assert source_name is not None
        assert ingredient.item_id is None
        assert source_name.resolution_status == "ambiguous"
    assert summary.warning_count == 1
    assert summary.conflicts[0]["candidate_count"] == 2


def test_preserves_source_rows_and_imports_valid_cost_prices(
    session_factory, synthetic_files
) -> None:
    synthetic_files.write_recipe(quantity="")

    summary = ImportService(session_factory).import_files(*synthetic_files.paths)

    assert summary.accepted_count == 1
    assert summary.rejected_count == 1
    assert summary.rejections == [
        {
            "dataset": "item_recipes",
            "row_number": 2,
            "messages": ["raw_material_1 and quantity_1 must be populated together"],
        }
    ]
    with session_factory() as session:
        records = session.scalars(select(SourceRecord).order_by(SourceRecord.id)).all()
        assert len(records) == 2
        assert json.loads(records[0].raw_payload_json)["price"] == "10"
        assert records[1].status == "rejected"
        assert json.loads(records[1].validation_messages_json)
        observation = session.scalar(select(PriceObservation))
        assert observation is not None
        assert observation.total_price == 10
        assert observation.lot_quantity == 1
        assert observation.source == "item_cost"
        assert observation.market_context == "unspecified"


def test_changed_checksum_creates_batch_without_duplicate_identity(
    session_factory, synthetic_files
) -> None:
    service = ImportService(session_factory)
    first = service.import_files(*synthetic_files.paths)
    synthetic_files.write_cost_rows([("Synthetic Ore", "Ore", "999")])
    second = service.import_files(*synthetic_files.paths)

    assert first.created_batches == 2
    assert second.created_batches == 1
    with session_factory() as session:
        assert session.scalar(select(func.count(ImportBatch.id))) == 3
        assert session.scalar(select(func.count(Item.id))) == 2
        prices = session.scalars(select(PriceObservation).order_by(PriceObservation.id)).all()
        assert [price.total_price for price in prices] == [10, 999]


def test_import_enriches_sole_uncategorized_manual_item_without_losing_price(
    session_factory, synthetic_files
) -> None:
    with session_factory() as session:
        manual = CatalogService(session, "Dodge").create_manual(ItemCreate(display_name="New Ore"))
    with session_factory() as session:
        PriceService(session, "Dodge").record(
            manual.uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=125,
                observed_at="2026-08-21T12:00:00Z",
            ),
        )
    synthetic_files.write_cost_rows([("New Ore", "Ore", "10")])
    synthetic_files.write_recipe(ingredient="New Ore")

    ImportService(session_factory).import_files(*synthetic_files.paths)

    with session_factory() as session:
        matching = session.scalars(select(Item).where(Item.normalized_name == "new ore")).all()
        assert len(matching) == 1
        assert matching[0].uuid == manual.uuid
        assert matching[0].category == "Ore"
        assert matching[0].identity_category == "ore"
        assert matching[0].created_source == "manual"
        assert (
            session.scalar(
                select(func.count(PriceObservation.id)).where(
                    PriceObservation.item_id == matching[0].id
                )
            )
            == 2
        )


def test_last_duplicate_cost_row_becomes_current_without_creating_sales(
    session_factory, synthetic_files
) -> None:
    synthetic_files.write_cost_rows(
        [
            ("Synthetic Ore", "Ore", "10"),
            ("Synthetic Ore", "Ore", "25"),
        ]
    )

    summary = ImportService(session_factory, "Dodge").import_files(*synthetic_files.paths)

    assert summary.price_count == 1
    with session_factory() as session:
        observations = session.scalars(select(PriceObservation)).all()
        assert len(observations) == 1
        assert observations[0].total_price == 25
        assert observations[0].market_context == "Dodge"
        assert session.scalar(select(func.count(SaleListing.id))) == 0


def test_file_contract_failure_happens_before_any_database_write(
    session_factory, synthetic_files
) -> None:
    synthetic_files.recipe_path.write_text("wrong,header\nvalue,value\n", encoding="utf-8")

    with pytest.raises(ContractError):
        ImportService(session_factory).import_files(*synthetic_files.paths)

    with session_factory() as session:
        assert session.scalar(select(func.count(ImportBatch.id))) == 0


def test_unexpected_failure_rolls_back_both_batches(
    monkeypatch, session_factory, synthetic_files
) -> None:
    service = ImportService(session_factory)

    def fail_recipe_import(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(service, "_import_recipes", fail_recipe_import)

    with pytest.raises(RuntimeError, match="synthetic failure"):
        service.import_files(*synthetic_files.paths)

    with session_factory() as session:
        assert session.scalar(select(func.count(ImportBatch.id))) == 0
        assert session.scalar(select(func.count(Item.id))) == 0
