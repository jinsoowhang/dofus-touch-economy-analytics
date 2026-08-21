from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from dofus_touch_economy.models import Item, SaleListing
from dofus_touch_economy.repositories.catalog import CatalogRepository
from dofus_touch_economy.repositories.sales import SalesRepository
from dofus_touch_economy.schemas import (
    SaleItemChoiceResponse,
    SaleListingCreate,
    SaleListingResponse,
)


class SaleItemNotFound(LookupError):
    pass


class SaleListingNotFound(LookupError):
    pass


class SaleListingConflict(RuntimeError):
    pass


class SalesService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._catalog = CatalogRepository(session)
        self._sales = SalesRepository(session)

    def item_choices(self) -> list[SaleItemChoiceResponse]:
        return [
            SaleItemChoiceResponse(
                uuid=item.uuid,
                display_name=item.display_name,
                category=item.category,
            )
            for item in self._catalog.search("", limit=None)
        ]

    def active(self) -> list[SaleListingResponse]:
        return [_response(listing) for listing in self._sales.active()]

    def sold(self) -> list[SaleListingResponse]:
        return [_response(listing) for listing in self._sales.sold()]

    def start(self, command: SaleListingCreate) -> SaleListingResponse:
        item_id = self._session.scalar(select(Item.id).where(Item.uuid == command.item_uuid))
        if item_id is None:
            raise SaleItemNotFound(str(command.item_uuid))
        listing = SaleListing(
            item_id=item_id,
            lot_quantity=command.lot_quantity,
            selling_started_at=datetime.now(UTC),
        )
        self._session.add(listing)
        self._session.commit()
        return _response(self._sales.get_by_uuid(listing.uuid) or listing)

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
    observation = listing.price_observation
    return SaleListingResponse(
        uuid=listing.uuid,
        item_uuid=listing.item.uuid,
        display_name=listing.item.display_name,
        category=listing.item.category,
        lot_quantity=listing.lot_quantity,
        total_price=None if observation is None else observation.total_price,
        selling_started_at=_as_utc(listing.selling_started_at),
        date_sold=None if listing.date_sold is None else _as_utc(listing.date_sold),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
