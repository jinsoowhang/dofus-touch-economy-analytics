from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dofus_touch_economy.importers.contracts import (
    ContractError,
    CostRow,
    RecipeRow,
    RejectedRow,
    ValidationResult,
    validate_cost_csv,
    validate_recipe_csv,
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


@dataclass(frozen=True)
class ImportSummary:
    created_batches: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    conflicts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_batches": self.created_batches,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "warning_count": self.warning_count,
            "conflicts": self.conflicts,
        }


class ImportService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def import_files(self, cost_path: Path, recipe_path: Path) -> ImportSummary:
        cost_path = Path(cost_path)
        recipe_path = Path(recipe_path)

        cost_result = validate_cost_csv(cost_path)
        recipe_result = validate_recipe_csv(recipe_path)
        cost_checksum = _sha256(cost_path)
        recipe_checksum = _sha256(recipe_path)

        created_batches = 0
        accepted_count = 0
        rejected_count = 0
        conflicts: list[dict[str, Any]] = []
        with self._session_factory() as session, session.begin():
            if not self._completed_batch_exists(session, "item_cost", cost_checksum):
                self._import_costs(session, cost_path, cost_checksum, cost_result)
                created_batches += 1
                accepted_count += len(cost_result.accepted)
                rejected_count += len(cost_result.rejected)

            if not self._completed_batch_exists(session, "item_recipes", recipe_checksum):
                recipe_conflicts = self._import_recipes(
                    session, recipe_path, recipe_checksum, recipe_result
                )
                created_batches += 1
                accepted_count += len(recipe_result.accepted)
                rejected_count += len(recipe_result.rejected)
                conflicts.extend(recipe_conflicts)

        return ImportSummary(
            created_batches=created_batches,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            warning_count=len(conflicts),
            conflicts=conflicts,
        )

    @staticmethod
    def _completed_batch_exists(session: Session, dataset: str, checksum: str) -> bool:
        return (
            session.scalar(
                select(ImportBatch.id).where(
                    ImportBatch.dataset == dataset,
                    ImportBatch.checksum == checksum,
                    ImportBatch.status == "completed",
                )
            )
            is not None
        )

    def _import_costs(
        self,
        session: Session,
        path: Path,
        checksum: str,
        result: ValidationResult[CostRow],
    ) -> None:
        batch = self._create_batch(session, "item_cost", path, checksum, result)
        for row in result.accepted:
            self._store_record(session, batch, row.row_number, row.raw_payload, "accepted", ())
            self._get_or_create_cost_item(session, row)
        for row in result.rejected:
            self._store_rejection(session, batch, row)
        batch.status = "completed"
        batch.completed_at = datetime.now(UTC)

    def _import_recipes(
        self,
        session: Session,
        path: Path,
        checksum: str,
        result: ValidationResult[RecipeRow],
    ) -> list[dict[str, Any]]:
        batch = self._create_batch(session, "item_recipes", path, checksum, result)
        conflicts: list[dict[str, Any]] = []
        for row in result.accepted:
            record = self._store_record(
                session, batch, row.row_number, row.raw_payload, "accepted", ()
            )
            crafted_item, resolution_status = self._resolve_crafted_item(session, row.recipe_item)
            session.add(
                SourceItemName(
                    source_record_id=record.id,
                    source_field="recipe_item",
                    position=0,
                    raw_name=row.recipe_item,
                    normalized_name=normalize_item_name(row.recipe_item),
                    item_id=crafted_item.id,
                    resolution_status=resolution_status,
                )
            )
            recipe = Recipe(
                crafted_item_id=crafted_item.id,
                profession=row.profession,
                source_record_id=record.id,
            )
            session.add(recipe)
            session.flush()

            for part in row.ingredients:
                item, ingredient_status, candidate_count = self._resolve_ingredient(
                    session, part.raw_name
                )
                source_field = f"raw_material_{part.position}"
                session.add(
                    SourceItemName(
                        source_record_id=record.id,
                        source_field=source_field,
                        position=part.position,
                        raw_name=part.raw_name,
                        normalized_name=normalize_item_name(part.raw_name),
                        item_id=None if item is None else item.id,
                        resolution_status=ingredient_status,
                    )
                )
                session.add(
                    RecipeIngredient(
                        recipe_id=recipe.id,
                        position=part.position,
                        item_id=None if item is None else item.id,
                        raw_name=part.raw_name,
                        normalized_name=normalize_item_name(part.raw_name),
                        quantity=part.quantity,
                    )
                )
                if ingredient_status == "ambiguous":
                    conflicts.append(
                        {
                            "dataset": "item_recipes",
                            "row_number": row.row_number,
                            "source_field": source_field,
                            "normalized_name": normalize_item_name(part.raw_name),
                            "candidate_count": candidate_count,
                        }
                    )

        for row in result.rejected:
            self._store_rejection(session, batch, row)
        batch.warning_count = len(conflicts)
        batch.status = "completed"
        batch.completed_at = datetime.now(UTC)
        return conflicts

    @staticmethod
    def _create_batch(
        session: Session,
        dataset: str,
        path: Path,
        checksum: str,
        result: ValidationResult[Any],
    ) -> ImportBatch:
        batch = ImportBatch(
            dataset=dataset,
            filename=path.name,
            checksum=checksum,
            accepted_count=len(result.accepted),
            rejected_count=len(result.rejected),
            warning_count=0,
            status="started",
        )
        session.add(batch)
        session.flush()
        return batch

    @staticmethod
    def _store_record(
        session: Session,
        batch: ImportBatch,
        row_number: int,
        raw_payload: dict[str, str | None],
        status: str,
        messages: tuple[str, ...],
    ) -> SourceRecord:
        record = SourceRecord(
            import_batch_id=batch.id,
            row_number=row_number,
            raw_payload_json=json.dumps(raw_payload, ensure_ascii=False, sort_keys=True),
            status=status,
            validation_messages_json=json.dumps(messages, ensure_ascii=False),
        )
        session.add(record)
        session.flush()
        return record

    def _store_rejection(self, session: Session, batch: ImportBatch, rejected: RejectedRow) -> None:
        self._store_record(
            session,
            batch,
            rejected.row_number,
            rejected.raw_payload,
            "rejected",
            rejected.messages,
        )

    @staticmethod
    def _get_or_create_cost_item(session: Session, row: CostRow) -> Item:
        normalized_name = normalize_item_name(row.raw_material)
        identity_category = normalize_item_name(row.category)
        item = session.scalar(
            select(Item).where(
                Item.normalized_name == normalized_name,
                Item.identity_category == identity_category,
            )
        )
        if item is None:
            item = Item(
                display_name=row.raw_material.strip(),
                normalized_name=normalized_name,
                category=row.category.strip(),
                identity_category=identity_category,
            )
            session.add(item)
            session.flush()
        return item

    @staticmethod
    def _name_candidates(session: Session, normalized_name: str) -> list[Item]:
        return list(
            session.scalars(
                select(Item).where(Item.normalized_name == normalized_name).order_by(Item.id)
            )
        )

    def _resolve_crafted_item(self, session: Session, raw_name: str) -> tuple[Item, str]:
        normalized_name = normalize_item_name(raw_name)
        candidates = self._name_candidates(session, normalized_name)
        if len(candidates) == 1:
            return candidates[0], "matched"
        if len(candidates) > 1:
            category_empty = next(
                (candidate for candidate in candidates if candidate.identity_category == ""), None
            )
            if category_empty is not None:
                return category_empty, "matched"
        item = self._create_category_empty_item(session, raw_name, normalized_name)
        return item, "created"

    def _resolve_ingredient(self, session: Session, raw_name: str) -> tuple[Item | None, str, int]:
        normalized_name = normalize_item_name(raw_name)
        candidates = self._name_candidates(session, normalized_name)
        if len(candidates) == 1:
            return candidates[0], "matched", 1
        if len(candidates) > 1:
            return None, "ambiguous", len(candidates)
        return self._create_category_empty_item(session, raw_name, normalized_name), "created", 0

    @staticmethod
    def _create_category_empty_item(session: Session, raw_name: str, normalized_name: str) -> Item:
        item = Item(
            display_name=raw_name.strip(),
            normalized_name=normalized_name,
            category=None,
            identity_category="",
        )
        session.add(item)
        session.flush()
        return item


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ContractError(f"could not hash {path.name}: {error}") from error
    return digest.hexdigest()
