"""Price units at the HTML boundary; domain commands always use whole kamas."""

import re
from decimal import Decimal

_PRICE_FIELDS = {
    "asking_price",
    "current_price",
    "unit_price",
    "total_price",
    "min_price",
    "max_price",
}
_THOUSANDS = re.compile(r"[+]?(?:\d{1,15}|\d{1,3}(?:,\d{3}){1,4})(?:\.\d{1,3})?")


def price_thousands(value: Decimal | int | None) -> str:
    if value is None:
        return ""
    return (
        format(Decimal(value) / 1000, "f").rstrip("0").rstrip(".")
        if Decimal(value) % 1000
        else str(int(Decimal(value) / 1000))
    )


def price_command_values(form, values: dict[str, str]) -> dict[str, str]:
    """Only explicitly marked HTML forms use thousands, including calculator batches."""
    if form.get("price_unit") != "thousands":
        return values
    converted = values.copy()
    for field, value in values.items():
        if field not in _PRICE_FIELDS:
            continue
        stripped = value.strip()
        converted[field] = (
            str(int(Decimal(stripped.replace(",", "")) * 1000))
            if _THOUSANDS.fullmatch(stripped)
            else ("Invalid price in thousands" if stripped else "")
        )
    return converted
