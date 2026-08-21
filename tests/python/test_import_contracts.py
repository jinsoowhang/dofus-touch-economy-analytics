import csv
from pathlib import Path

import pytest

from dofus_touch_economy.importers.contracts import (
    ContractError,
    validate_cost_csv,
    validate_recipe_csv,
)

RECIPE_HEADERS = [
    "recipe_item",
    "profession",
    *[
        field
        for position in range(1, 9)
        for field in (
            f"raw_material_{position}",
            f"quantity_{position}",
            f"cost_{position}",
        )
    ],
    "total_cost",
    "profit",
    "ROI",
]


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def write_recipe_fixture(tmp_path: Path, **overrides: str) -> Path:
    if "material_1" in overrides:
        overrides["raw_material_1"] = overrides.pop("material_1")
    row = dict.fromkeys(RECIPE_HEADERS, "")
    row.update(
        {
            "recipe_item": "Synthetic Widget",
            "profession": "Crafting",
            "raw_material_1": "Synthetic Ore",
            "quantity_1": "2",
            "cost_1": "20",
            **overrides,
        }
    )
    path = tmp_path / "recipe.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECIPE_HEADERS)
        writer.writeheader()
        writer.writerow(row)
    return path


def test_validates_cost_rows(fixture_dir: Path) -> None:
    result = validate_cost_csv(fixture_dir / "item_cost_valid.csv")

    assert result.rejected == []
    assert [row.raw_material for row in result.accepted] == [
        "Synthetic Ore",
        "Synthetic Fiber",
    ]
    assert result.accepted[0].row_number == 2
    assert result.accepted[0].raw_payload["price"] == "1,000"


def test_flattens_populated_recipe_ingredients(fixture_dir: Path) -> None:
    result = validate_recipe_csv(fixture_dir / "item_recipes_valid.csv")

    assert result.rejected == []
    recipe = result.accepted[0]
    assert [(part.position, part.raw_name, part.quantity) for part in recipe.ingredients] == [
        (1, "Synthetic Ore", 2),
        (2, "Synthetic Fiber", 3),
    ]
    assert recipe.total_cost == "50"
    assert recipe.profit == "25"
    assert recipe.roi == "50%"


def test_rejects_mismatched_material_and_quantity(tmp_path: Path) -> None:
    path = write_recipe_fixture(tmp_path, material_1="Synthetic Ore", quantity_1="")
    result = validate_recipe_csv(path)

    assert result.accepted == []
    assert result.rejected[0].messages == (
        "raw_material_1 and quantity_1 must be populated together",
    )


def test_rejects_nonpositive_or_noninteger_quantities(tmp_path: Path) -> None:
    path = write_recipe_fixture(tmp_path, quantity_1="1.5")

    result = validate_recipe_csv(path)

    assert result.accepted == []
    assert result.rejected[0].messages == ("quantity_1 must be a positive integer",)


def test_rejects_an_incorrect_header(tmp_path: Path) -> None:
    path = tmp_path / "cost.csv"
    path.write_text("material,category,price\nSynthetic Ore,Ore,100\n", encoding="utf-8")

    with pytest.raises(ContractError, match="exact header"):
        validate_cost_csv(path)
