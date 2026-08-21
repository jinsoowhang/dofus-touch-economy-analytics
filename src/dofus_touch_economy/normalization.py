ITEM_CATEGORY_SUFFIXES = {
    "amulet": "Amulet",
    "axe": "Axe",
    "belt": "Belt",
    "boots": "Boots",
    "bow": "Bow",
    "cape": "Cape",
    "cloak": "Cloak",
    "dagger": "Dagger",
    "daggers": "Dagger",
    "hammer": "Hammer",
    "hat": "Hat",
    "ring": "Ring",
    "shield": "Shield",
    "shovel": "Shovel",
    "staff": "Staff",
    "sword": "Sword",
    "wand": "Wand",
}


def format_item_display_name(raw: str) -> str:
    display_name = " ".join(raw.split())
    if not display_name:
        raise ValueError("item name must not be blank")
    return display_name.title()


def normalize_item_name(raw: str) -> str:
    normalized = " ".join(raw.split()).casefold()
    if not normalized:
        raise ValueError("item name must not be blank")
    return normalized


def infer_item_category(raw_name: str) -> str | None:
    normalized_name = normalize_item_name(raw_name)
    final_word = normalized_name.rsplit(" ", maxsplit=1)[-1]
    return ITEM_CATEGORY_SUFFIXES.get(final_word)
