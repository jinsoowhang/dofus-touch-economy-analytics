from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from dofus_touch_economy.app import get_session, get_settings
from dofus_touch_economy.config import Settings
from dofus_touch_economy.services.catalog import CatalogService
from dofus_touch_economy.services.pricing import ItemNotFound

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/items", status_code=307)


@router.get("/items", response_class=HTMLResponse)
def search_items(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = Query(default=""),
) -> HTMLResponse:
    results = CatalogService(session, settings.market_context).search(q, limit=50)
    context = {"query": q, "items": results, "market_context": settings.market_context}
    if request.headers.get("HX-Request", "").casefold() == "true":
        return templates.TemplateResponse(request, "fragments/item_results.html", context=context)
    return templates.TemplateResponse(request, "items.html", context=context)


@router.get("/items/{item_uuid}", response_class=HTMLResponse)
def item_detail(
    request: Request,
    item_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    try:
        detail = CatalogService(session, settings.market_context).detail(item_uuid)
    except ItemNotFound:
        return templates.TemplateResponse(
            request,
            "item_detail.html",
            context={"detail": None, "error": "Item not found"},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "item_detail.html",
        context={"detail": detail, "error": None},
    )
