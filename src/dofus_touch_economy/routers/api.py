from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from dofus_touch_economy.app import get_session, get_settings
from dofus_touch_economy.config import Settings
from dofus_touch_economy.schemas import ItemDetailResponse, ItemSummaryResponse
from dofus_touch_economy.services.catalog import CatalogService
from dofus_touch_economy.services.pricing import ItemNotFound

router = APIRouter()


@router.get("/items", response_model=list[ItemSummaryResponse])
def search_items(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = Query(default=""),
) -> list[ItemSummaryResponse]:
    del request
    return CatalogService(session, settings.market_context).search(q, limit=50)


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
