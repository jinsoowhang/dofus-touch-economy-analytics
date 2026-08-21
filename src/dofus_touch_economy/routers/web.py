from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from dofus_touch_economy.app import get_session, get_settings
from dofus_touch_economy.config import Settings
from dofus_touch_economy.schemas import InvalidationCreate, ItemCreate, PriceObservationCreate
from dofus_touch_economy.services.catalog import CatalogItemConflict, CatalogService
from dofus_touch_economy.services.pricing import (
    ItemNotFound,
    ObservationConflict,
    ObservationNotFound,
    PriceService,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").casefold() == "true"


def _detail_context(
    detail,
    *,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
    include_metrics_oob: bool = False,
) -> dict[str, object]:
    return {
        "detail": detail,
        "error": None,
        "active_tab": "items",
        "errors": errors or [],
        "form_values": form_values or {},
        "default_observed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "include_metrics_oob": include_metrics_oob,
    }


def _search_context(
    catalog: CatalogService,
    query: str,
    market_context: str,
    *,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
) -> dict[str, object]:
    items = catalog.search(query, limit=None)
    suggestions = catalog.suggest(query, limit=5) if query.strip() and not items else []
    proposed_display_name = catalog.format_display_name(query) if query.strip() else query
    recognized_category = catalog.infer_category(query) if query.strip() else None
    return {
        "query": query,
        "items": items,
        "active_tab": "items",
        "suggestions": suggestions,
        "proposed_display_name": proposed_display_name,
        "recognized_category": recognized_category,
        "market_context": market_context,
        "errors": errors or [],
        "form_values": form_values or {},
    }


def _error_response(request: Request, message: str, status_code: int) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "item_detail.html",
        context={"detail": None, "error": message, "active_tab": "items"},
        status_code=status_code,
    )


def _form_values(form, fields: tuple[str, ...]) -> dict[str, str]:
    return {
        field: value if isinstance((value := form.get(field, "")), str) else "" for field in fields
    }


def _validation_messages(error: ValidationError) -> list[str]:
    return [entry["msg"] for entry in error.errors()]


def _mutation_response(
    request: Request,
    detail,
    *,
    status_code: int = 200,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
) -> HTMLResponse | RedirectResponse:
    if not _is_htmx(request) and status_code < 400:
        return RedirectResponse(url=f"/items/{detail.uuid}", status_code=303)
    template = "fragments/price_panel.html" if _is_htmx(request) else "item_detail.html"
    return templates.TemplateResponse(
        request,
        template,
        context=_detail_context(
            detail,
            errors=errors,
            form_values=form_values,
            include_metrics_oob=_is_htmx(request),
        ),
        status_code=status_code,
    )


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
    catalog = CatalogService(session, settings.market_context)
    context = _search_context(catalog, q, settings.market_context)
    if _is_htmx(request):
        return templates.TemplateResponse(request, "fragments/item_results.html", context=context)
    return templates.TemplateResponse(request, "items.html", context=context)


@router.post("/items", response_class=HTMLResponse, response_model=None)
async def create_item(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    values = _form_values(form, ("display_name", "category"))
    catalog = CatalogService(session, settings.market_context)
    try:
        command = ItemCreate.model_validate(values)
    except ValidationError as error:
        context = _search_context(
            catalog,
            values["display_name"],
            settings.market_context,
            errors=_validation_messages(error),
            form_values=values,
        )
        return templates.TemplateResponse(
            request,
            "items.html",
            context=context,
            status_code=422,
        )

    try:
        detail = catalog.create_manual(command)
    except CatalogItemConflict as error:
        if len(error.candidates) == 1:
            return RedirectResponse(url=f"/items/{error.candidates[0].uuid}", status_code=303)
        context = _search_context(
            catalog,
            command.display_name,
            settings.market_context,
            errors=["That name matches multiple existing items. Choose the correct category."],
            form_values=values,
        )
        return templates.TemplateResponse(
            request,
            "items.html",
            context=context,
            status_code=409,
        )
    return RedirectResponse(url=f"/items/{detail.uuid}", status_code=303)


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
        return _error_response(request, "Item not found", 404)
    return templates.TemplateResponse(
        request,
        "item_detail.html",
        context=_detail_context(detail),
    )


@router.post(
    "/items/{item_uuid}/price-observations",
    response_class=HTMLResponse,
    response_model=None,
)
async def record_price(
    request: Request,
    item_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    form = await request.form()
    values = _form_values(form, ("lot_quantity", "total_price", "observed_at", "note"))
    catalog = CatalogService(session, settings.market_context)
    try:
        detail = catalog.detail(item_uuid)
    except ItemNotFound:
        return _error_response(request, "Item not found", 404)
    try:
        command = PriceObservationCreate.model_validate(values)
    except ValidationError as error:
        return _mutation_response(
            request,
            detail,
            status_code=422,
            errors=_validation_messages(error),
            form_values=values,
        )

    PriceService(session, settings.market_context).record(item_uuid, command)
    return _mutation_response(request, catalog.detail(item_uuid))


@router.post(
    "/price-observations/{observation_uuid}/invalidation",
    response_class=HTMLResponse,
    response_model=None,
)
async def invalidate_price(
    request: Request,
    observation_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    form = await request.form()
    values = _form_values(form, ("reason",))
    service = PriceService(session, settings.market_context)
    try:
        item_uuid = service.item_uuid_for_observation(observation_uuid)
    except ObservationNotFound:
        return _error_response(request, "Observation not found", 404)
    detail = CatalogService(session, settings.market_context).detail(item_uuid)
    try:
        command = InvalidationCreate.model_validate(values)
    except ValidationError as error:
        return _mutation_response(
            request,
            detail,
            status_code=422,
            errors=_validation_messages(error),
        )
    try:
        service.invalidate(observation_uuid, command.reason)
    except ObservationConflict:
        return _mutation_response(
            request,
            detail,
            status_code=409,
            errors=["Observation has already been invalidated."],
        )
    return _mutation_response(
        request,
        CatalogService(session, settings.market_context).detail(item_uuid),
    )
