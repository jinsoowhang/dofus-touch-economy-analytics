from dataclasses import dataclass

from sqlalchemy import not_, or_
from sqlalchemy.sql.elements import ColumnElement


@dataclass(frozen=True)
class CatalogExclusion:
    normalized_name: str
    reason: str


CATALOG_EXCLUSIONS = (
    CatalogExclusion(
        normalized_name="violet arrow helmet",
        reason=(
            "Dofus-only item absent from Ankama's live Dofus Touch catalog; confirmed 2026-08-23."
        ),
    ),
)


def active_catalog_item_clause(item_model) -> ColumnElement[bool]:
    """Return the shared SQL predicate for items exposed as Dofus Touch catalog data."""
    excluded_names = or_(
        *(
            item_model.normalized_name == exclusion.normalized_name
            for exclusion in CATALOG_EXCLUSIONS
        )
    )
    return not_(excluded_names)


def catalog_exclusion_for_name(normalized_name: str) -> CatalogExclusion | None:
    return next(
        (
            exclusion
            for exclusion in CATALOG_EXCLUSIONS
            if exclusion.normalized_name == normalized_name
        ),
        None,
    )
