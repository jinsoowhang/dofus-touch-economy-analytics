import pytest

from dofus_touch_economy.normalization import normalize_item_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Gobball   Wool ", "gobball wool"),
        ("ÉCAFLIP", "écaflip"),
        ("Iron\tOre", "iron ore"),
    ],
)
def test_normalize_item_name(raw: str, expected: str) -> None:
    assert normalize_item_name(raw) == expected


def test_normalize_item_name_rejects_blank() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_item_name("  ")
