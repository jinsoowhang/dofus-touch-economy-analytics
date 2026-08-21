def normalize_item_name(raw: str) -> str:
    normalized = " ".join(raw.split()).casefold()
    if not normalized:
        raise ValueError("item name must not be blank")
    return normalized
