from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dofus_touch_economy.app import get_session, get_settings
from dofus_touch_economy.config import Settings
from dofus_touch_economy.schemas import (
    InvalidationCreate,
    ItemCreate,
    ItemDetailResponse,
    ItemSummaryResponse,
    PriceObservationCreate,
)
from dofus_touch_economy.services.catalog import CatalogItemConflict, CatalogService
from dofus_touch_economy.services.pricing import (
    ItemNotFound,
    ObservationConflict,
    ObservationNotFound,
    PriceService,
)

router = APIRouter()


@router.get("/items", response_model=list[ItemSummaryResponse])
def search_items(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = Query(default=""),
) -> list[ItemSummaryResponse]:
    return CatalogService(session, settings.market_context).search(q, limit=50)


@router.post(
    "/items",
    response_model=ItemDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    command: ItemCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemDetailResponse:
    try:
        return CatalogService(session, settings.market_context).create_manual(command)
    except CatalogItemConflict as error:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "catalog item identity already exists",
                "candidates": [candidate.model_dump(mode="json") for candidate in error.candidates],
            },
        ) from error


@router.get("/items/{item_uuid}", response_model=ItemDetailResponse)
def item_detail(
    item_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemDetailResponse:
    try:
        return CatalogService(session, settings.market_context).detail(item_uuid)
    except ItemNotFound as error:
        raise HTTPException(status_code=404, detail="item not found") from error


@router.post(
    "/items/{item_uuid}/price-observations",
    response_model=ItemDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_price(
    item_uuid: UUID,
    command: PriceObservationCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemDetailResponse:
    try:
        PriceService(session, settings.market_context).record(item_uuid, command)
        return CatalogService(session, settings.market_context).detail(item_uuid)
    except ItemNotFound as error:
        raise HTTPException(status_code=404, detail="item not found") from error


@router.post(
    "/price-observations/{observation_uuid}/invalidation",
    response_model=ItemDetailResponse,
)
def invalidate_price(
    observation_uuid: UUID,
    command: InvalidationCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemDetailResponse:
    service = PriceService(session, settings.market_context)
    try:
        observation = service.invalidate(observation_uuid, command.reason)
        return CatalogService(session, settings.market_context).detail(observation.item_uuid)
    except ObservationNotFound as error:
        raise HTTPException(status_code=404, detail="observation not found") from error
    except ObservationConflict as error:
        raise HTTPException(status_code=409, detail="observation already invalidated") from error
