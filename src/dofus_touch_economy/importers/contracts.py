from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

COST_HEADERS = ("raw_material", "category", "price")
RECIPE_HEADERS = (
    "recipe_item",
    "profession",
    *(
        field
        for position in range(1, 9)
        for field in (
            f"raw_material_{position}",
            f"quantity_{position}",
            f"cost_{position}",
        )
    ),
    "total_cost",
    "profit",
    "ROI",
)

RawPayload = dict[str, str | None]


class ContractError(ValueError):
    """Raised when a source file cannot be validated row by row."""


@dataclass(frozen=True)
class CostRow:
    row_number: int
    raw_material: str
    category: str
    price: str
    raw_payload: RawPayload


@dataclass(frozen=True)
class IngredientRow:
    position: int
    raw_name: str
    quantity: int
    cost: str


@dataclass(frozen=True)
class RecipeRow:
    row_number: int
    recipe_item: str
    profession: str
    ingredients: tuple[IngredientRow, ...]
    total_cost: str
    profit: str
    roi: str
    raw_payload: RawPayload


@dataclass(frozen=True)
class RejectedRow:
    row_number: int
    raw_payload: RawPayload
    messages: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult[AcceptedRow]:
    accepted: list[AcceptedRow]
    rejected: list[RejectedRow]


def _read_rows(path: Path, expected_headers: tuple[str, ...]) -> list[tuple[int, RawPayload]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != expected_headers:
                raise ContractError(
                    f"{path.name} must use exact header: {','.join(expected_headers)}"
                )
            return [
                (row_number, {header: row.get(header) for header in expected_headers})
                for row_number, row in enumerate(reader, start=2)
            ]
    except ContractError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise ContractError(f"could not read {path.name}: {error}") from error


def _value(payload: RawPayload, field: str) -> str:
    return payload[field] or ""


def validate_cost_csv(path: Path) -> ValidationResult[CostRow]:
    accepted: list[CostRow] = []
    rejected: list[RejectedRow] = []
    for row_number, payload in _read_rows(path, COST_HEADERS):
        raw_material = _value(payload, "raw_material")
        category = _value(payload, "category")
        messages: list[str] = []
        if not raw_material.strip():
            messages.append("raw_material must not be blank")
        if not category.strip():
            messages.append("category must not be blank")

        if messages:
            rejected.append(RejectedRow(row_number, payload, tuple(messages)))
            continue
        accepted.append(
            CostRow(
                row_number=row_number,
                raw_material=raw_material,
                category=category,
                price=_value(payload, "price"),
                raw_payload=payload,
            )
        )
    return ValidationResult(accepted=accepted, rejected=rejected)


def _parse_quantity(raw: str) -> int | None:
    candidate = raw.replace(",", "").strip()
    if not re.fullmatch(r"[0-9]+", candidate):
        return None
    quantity = int(candidate, 10)
    return quantity if quantity > 0 else None


def validate_recipe_csv(path: Path) -> ValidationResult[RecipeRow]:
    accepted: list[RecipeRow] = []
    rejected: list[RejectedRow] = []
    for row_number, payload in _read_rows(path, RECIPE_HEADERS):
        recipe_item = _value(payload, "recipe_item")
        profession = _value(payload, "profession")
        messages: list[str] = []
        ingredients: list[IngredientRow] = []
        if not recipe_item.strip():
            messages.append("recipe_item must not be blank")
        if not profession.strip():
            messages.append("profession must not be blank")

        for position in range(1, 9):
            material_field = f"raw_material_{position}"
            quantity_field = f"quantity_{position}"
            raw_material = _value(payload, material_field)
            raw_quantity = _value(payload, quantity_field)
            has_material = bool(raw_material.strip())
            has_quantity = bool(raw_quantity.strip())
            if has_material != has_quantity:
                messages.append(f"{material_field} and {quantity_field} must be populated together")
                continue
            if not has_material:
                continue

            quantity = _parse_quantity(raw_quantity)
            if quantity is None:
                messages.append(f"{quantity_field} must be a positive integer")
                continue
            ingredients.append(
                IngredientRow(
                    position=position,
                    raw_name=raw_material,
                    quantity=quantity,
                    cost=_value(payload, f"cost_{position}"),
                )
            )

        if messages:
            rejected.append(RejectedRow(row_number, payload, tuple(messages)))
            continue
        accepted.append(
            RecipeRow(
                row_number=row_number,
                recipe_item=recipe_item,
                profession=profession,
                ingredients=tuple(ingredients),
                total_cost=_value(payload, "total_cost"),
                profit=_value(payload, "profit"),
                roi=_value(payload, "ROI"),
                raw_payload=payload,
            )
        )
    return ValidationResult(accepted=accepted, rejected=rejected)
