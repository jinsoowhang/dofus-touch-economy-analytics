from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from dofus_touch_economy.models import Item, PriceObservation, SaleListing
from dofus_touch_economy.repositories.catalog import CatalogRepository
from dofus_touch_economy.repositories.sales import SalesRepository
from dofus_touch_economy.schemas import (
    SaleItemChoiceResponse,
    SaleListingCreate,
    SaleListingResponse,
    SalePriceUpdate,
)

SaleSortField = Literal["name", "category", "price", "started", "sold"]
SaleSortDirection = Literal["asc", "desc"]


class SaleItemNotFound(LookupError):
    pass


class SaleListingNotFound(LookupError):
    pass


class SaleListingConflict(RuntimeError):
    pass


class SalesService:
    def __init__(self, session: Session, market_context: str) -> None:
        self._session = session
        self._market_context = market_context
        self._catalog = CatalogRepository(session)
        self._sales = SalesRepository(session)

    def item_choices(self) -> list[SaleItemChoiceResponse]:
        return [
            SaleItemChoiceResponse(
                uuid=item.uuid,
                display_name=item.display_name,
                category=item.category,
                icon_url=_icon_url(item),
            )
            for item in self._catalog.search("", limit=None)
        ]

    def active(
        self,
        sort_field: SaleSortField = "started",
        sort_direction: SaleSortDirection = "desc",
    ) -> list[SaleListingResponse]:
        listings = [_response(listing) for listing in self._sales.active()]
        return _sort_listings(listings, sort_field, sort_direction)

    def sold(
        self,
        sort_field: SaleSortField = "sold",
        sort_direction: SaleSortDirection = "desc",
    ) -> list[SaleListingResponse]:
        listings = [_response(listing) for listing in self._sales.sold()]
        return _sort_listings(listings, sort_field, sort_direction)

    def start(self, command: SaleListingCreate) -> SaleListingResponse:
        item_id = self._session.scalar(select(Item.id).where(Item.uuid == command.item_uuid))
        if item_id is None:
            raise SaleItemNotFound(str(command.item_uuid))
        selling_started_at = datetime.now(UTC)
        observation = self._new_price_observation(
            item_id,
            command.asking_price,
            selling_started_at,
        )
        listing = SaleListing(
            item_id=item_id,
            price_observation_id=None if observation is None else observation.id,
            lot_quantity=1,
            asking_price=command.asking_price,
            selling_started_at=selling_started_at,
        )
        self._session.add(listing)
        self._session.commit()
        return _response(self._sales.get_by_uuid(listing.uuid) or listing)

    def duplicate(self, listing_uuid: UUID) -> SaleListingResponse:
        original = self._sales.get_by_uuid(listing_uuid)
        if original is None:
            raise SaleListingNotFound(str(listing_uuid))
        duplicate = SaleListing(
            item_id=original.item_id,
            lot_quantity=1,
            asking_price=original.asking_price,
            selling_started_at=datetime.now(UTC),
        )
        self._session.add(duplicate)
        self._session.commit()
        return _response(self._sales.get_by_uuid(duplicate.uuid) or duplicate)

    def delete(self, listing_uuid: UUID) -> SaleListingResponse:
        listing = self._sales.get_by_uuid(listing_uuid)
        if listing is None:
            raise SaleListingNotFound(str(listing_uuid))
        response = _response(listing)
        self._session.delete(listing)
        self._session.commit()
        return response

    def update_price(
        self,
        listing_uuid: UUID,
        command: SalePriceUpdate,
    ) -> SaleListingResponse:
        existing = self._sales.get_by_uuid(listing_uuid)
        if existing is None:
            raise SaleListingNotFound(str(listing_uuid))
        observation = self._new_price_observation(
            existing.item_id,
            command.asking_price,
            datetime.now(UTC),
        )
        if observation is None:  # pragma: no cover - update prices are always present
            raise ValueError("sale price is required")
        if not self._sales.update_price(
            listing_uuid,
            command.asking_price,
            observation.id,
        ):
            self._session.rollback()
            raise SaleListingConflict(str(listing_uuid))
        self._session.commit()
        listing = self._sales.get_by_uuid(listing_uuid)
        if listing is None:  # pragma: no cover - protected by successful update
            raise SaleListingNotFound(str(listing_uuid))
        return _response(listing)

    def _new_price_observation(
        self,
        item_id: int,
        total_price: int | None,
        observed_at: datetime,
    ) -> PriceObservation | None:
        if total_price is None:
            return None
        observation = PriceObservation(
            item_id=item_id,
            lot_quantity=1,
            total_price=total_price,
            observed_at=observed_at,
            market_context=self._market_context,
        )
        self._session.add(observation)
        self._session.flush()
        return observation

    def mark_sold(self, listing_uuid: UUID) -> SaleListingResponse:
        if not self._sales.mark_sold(listing_uuid, datetime.now(UTC)):
            self._session.rollback()
            existing = self._sales.get_by_uuid(listing_uuid)
            if existing is None:
                raise SaleListingNotFound(str(listing_uuid))
            raise SaleListingConflict(str(listing_uuid))
        self._session.commit()
        listing = self._sales.get_by_uuid(listing_uuid)
        if listing is None:  # pragma: no cover - protected by successful update
            raise SaleListingNotFound(str(listing_uuid))
        return _response(listing)


def _response(listing: SaleListing) -> SaleListingResponse:
    return SaleListingResponse(
        uuid=listing.uuid,
        item_uuid=listing.item.uuid,
        display_name=listing.item.display_name,
        category=listing.item.category,
        icon_url=_icon_url(listing.item),
        asking_price=listing.asking_price,
        selling_started_at=_as_utc(listing.selling_started_at),
        date_sold=None if listing.date_sold is None else _as_utc(listing.date_sold),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _icon_url(item: Item) -> str | None:
    return None if item.icon_source_url is None else f"/item-icons/{item.uuid}.png"


def _sort_listings(
    listings: list[SaleListingResponse],
    sort_field: SaleSortField,
    sort_direction: SaleSortDirection,
) -> list[SaleListingResponse]:
    def value(listing: SaleListingResponse):
        if sort_field == "name":
            return listing.display_name.casefold()
        if sort_field == "category":
            return None if listing.category is None else listing.category.casefold()
        if sort_field == "price":
            return listing.asking_price
        if sort_field == "started":
            return listing.selling_started_at
        return listing.date_sold

    with_value = [listing for listing in listings if value(listing) is not None]
    without_value = [listing for listing in listings if value(listing) is None]
    with_value.sort(key=lambda listing: listing.display_name.casefold())
    with_value.sort(key=value, reverse=sort_direction == "desc")
    without_value.sort(key=lambda listing: listing.display_name.casefold())
    return [*with_value, *without_value]
