import pytest

from dofus_touch_economy.normalization import (
    format_item_display_name,
    infer_item_category,
    normalize_item_name,
)


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


def test_format_item_display_name_collapses_whitespace_and_uses_title_case() -> None:
    assert format_item_display_name("  chouquish   belt ") == "Chouquish Belt"


def test_format_item_display_name_only_capitalizes_after_spaces() -> None:
    assert format_item_display_name("daggero's red necklace") == "Daggero's Red Necklace"


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("chouquish belt", "Belt"),
        ("royal gobball hat", "Hat"),
        ("synthetic daggers", "Dagger"),
        ("belt leather", None),
        ("ringed fabric", None),
    ],
)
def test_infer_item_category_uses_only_known_final_words(
    raw_name: str, expected: str | None
) -> None:
    assert infer_item_category(raw_name) == expected
