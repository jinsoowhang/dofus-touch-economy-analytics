from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from dofus_touch_economy.models import Item, Recipe, RecipeIngredient
from dofus_touch_economy.normalization import normalize_item_name


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, limit: int = 50) -> list[Item]:
        if not query.strip():
            return []
        normalized_query = normalize_item_name(query)
        statement = (
            select(Item)
            .where(Item.normalized_name.contains(normalized_query, autoescape=True))
            .order_by(Item.normalized_name, func.coalesce(Item.category, ""), Item.id)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def get_by_uuid(self, item_uuid: UUID) -> Item | None:
        statement = (
            select(Item)
            .where(Item.uuid == item_uuid)
            .options(
                selectinload(Item.recipes)
                .selectinload(Recipe.ingredients)
                .selectinload(RecipeIngredient.item)
            )
        )
        return self._session.scalar(statement)
