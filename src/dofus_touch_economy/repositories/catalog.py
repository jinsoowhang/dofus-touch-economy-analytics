from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from dofus_touch_economy.models import Item, Recipe, RecipeIngredient
from dofus_touch_economy.normalization import normalize_item_name


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, limit: int | None = 50) -> list[Item]:
        statement = select(Item)
        if query.strip():
            normalized_query = normalize_item_name(query)
            statement = statement.where(
                Item.normalized_name.contains(normalized_query, autoescape=True)
            )
        statement = statement.order_by(
            Item.normalized_name,
            func.coalesce(Item.category, ""),
            Item.id,
        )
        if limit is not None:
            statement = statement.limit(limit)
        return list(self._session.scalars(statement))

    def find_by_identity(self, normalized_name: str, identity_category: str) -> Item | None:
        return self._session.scalar(
            select(Item).where(
                Item.normalized_name == normalized_name,
                Item.identity_category == identity_category,
            )
        )

    def find_by_normalized_name(self, normalized_name: str) -> list[Item]:
        statement = (
            select(Item)
            .where(Item.normalized_name == normalized_name)
            .order_by(func.coalesce(Item.category, ""), Item.id)
        )
        return list(self._session.scalars(statement))

    def suggestion_candidates(self) -> list[Item]:
        statement = select(Item).order_by(
            Item.normalized_name,
            func.coalesce(Item.category, ""),
            Item.id,
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
