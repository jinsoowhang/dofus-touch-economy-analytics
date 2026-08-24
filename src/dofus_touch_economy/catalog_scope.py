from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

TOUCH_CATALOG_VERIFIED = "verified"
TOUCH_CATALOG_EXCLUDED = "excluded"
TOUCH_CATALOG_EXCLUSION_REASON = (
    "Normalized item name absent from Ankama's live Dofus Touch item catalog."
)


def active_catalog_item_clause(item_model) -> ColumnElement[bool]:
    """Return the shared SQL predicate for items exposed as Dofus Touch catalog data."""
    return or_(
        item_model.touch_catalog_status.is_(None),
        item_model.touch_catalog_status != TOUCH_CATALOG_EXCLUDED,
    )


def is_active_catalog_item(item) -> bool:
    return item.touch_catalog_status != TOUCH_CATALOG_EXCLUDED
