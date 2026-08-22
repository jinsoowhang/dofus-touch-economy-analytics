from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from dofus_touch_economy.app import get_session, get_settings
from dofus_touch_economy.config import Settings
from dofus_touch_economy.schemas import (
    InvalidationCreate,
    ItemCreate,
    PriceObservationCreate,
    SaleListingCreate,
    SalePriceUpdate,
)
from dofus_touch_economy.services.catalog import (
    CatalogItemConflict,
    CatalogService,
    ItemSortField,
    SortDirection,
)
from dofus_touch_economy.services.pricing import (
    ItemNotFound,
    ObservationConflict,
    ObservationNotFound,
    PriceService,
)
from dofus_touch_economy.services.sales import (
    SaleItemNotFound,
    SaleListingConflict,
    SaleListingNotFound,
    SaleSortDirection,
    SaleSortField,
    SalesService,
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
    sort_field: ItemSortField = "name",
    sort_direction: SortDirection = "asc",
    notification: str | None = None,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
) -> dict[str, object]:
    items = catalog.search(
        query,
        limit=None,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )
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
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "sort_columns": _sort_columns(query, sort_field, sort_direction),
        "notification": notification,
        "errors": errors or [],
        "form_values": form_values or {},
    }


def _sort_columns(
    query: str,
    sort_field: ItemSortField,
    sort_direction: SortDirection,
) -> list[dict[str, object]]:
    columns = (
        ("name", "Item name", False),
        ("category", "Category", False),
        ("price", "Current price", True),
        ("observed", "Last observed", False),
    )
    result: list[dict[str, object]] = []
    for field, label, numeric in columns:
        active = field == sort_field
        next_direction = "desc" if active and sort_direction == "asc" else "asc"
        parameters = {"q": query, "sort": field, "direction": next_direction}
        result.append(
            {
                "field": field,
                "label": label,
                "numeric": numeric,
                "active": active,
                "direction": sort_direction if active else None,
                "next_direction": next_direction,
                "url": f"/items?{urlencode(parameters)}",
            }
        )
    return result


def _error_response(request: Request, message: str, status_code: int) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "item_detail.html",
        context={"detail": None, "error": message, "active_tab": "items"},
        status_code=status_code,
    )


def _sales_context(
    service: SalesService,
    *,
    active_sort: SaleSortField = "started",
    active_direction: SaleSortDirection = "desc",
    sold_sort: SaleSortField = "sold",
    sold_direction: SaleSortDirection = "desc",
    notification: str | None = None,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "active_tab": "sales",
        "item_choices": service.item_choices(),
        "active_sales": service.active(active_sort, active_direction),
        "sold_sales": service.sold(sold_sort, sold_direction),
        "active_sort_columns": _sales_sort_columns(
            "active",
            active_sort,
            active_direction,
            sold_sort,
            sold_direction,
        ),
        "sold_sort_columns": _sales_sort_columns(
            "sold",
            sold_sort,
            sold_direction,
            active_sort,
            active_direction,
        ),
        "notification": notification,
        "errors": errors or [],
        "form_values": form_values or {},
    }


def _sales_sort_columns(
    table: Literal["active", "sold"],
    sort_field: SaleSortField,
    sort_direction: SaleSortDirection,
    other_sort: SaleSortField,
    other_direction: SaleSortDirection,
) -> list[dict[str, object]]:
    columns = (
        (
            ("name", "Item", False),
            ("category", "Category", False),
            ("price", "Price", True),
            ("started", "Selling since", False),
        )
        if table == "active"
        else (
            ("name", "Item", False),
            ("price", "Price", True),
            ("started", "Selling started", False),
            ("sold", "Date sold", False),
        )
    )
    result: list[dict[str, object]] = []
    for field, label, numeric in columns:
        active = field == sort_field
        next_direction = "desc" if active and sort_direction == "asc" else "asc"
        if table == "active":
            parameters = {
                "active_sort": field,
                "active_direction": next_direction,
                "sold_sort": other_sort,
                "sold_direction": other_direction,
            }
        else:
            parameters = {
                "active_sort": other_sort,
                "active_direction": other_direction,
                "sold_sort": field,
                "sold_direction": next_direction,
            }
        result.append(
            {
                "field": field,
                "label": label,
                "numeric": numeric,
                "active": active,
                "direction": sort_direction if active else None,
                "next_direction": next_direction,
                "url": f"/sales?{urlencode(parameters)}",
            }
        )
    return result


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


@router.get("/sales", response_class=HTMLResponse)
def sales_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    notice: str | None = Query(default=None),
    active_sort: Annotated[SaleSortField, Query()] = "started",
    active_direction: Annotated[SaleSortDirection, Query()] = "desc",
    sold_sort: Annotated[SaleSortField, Query()] = "sold",
    sold_direction: Annotated[SaleSortDirection, Query()] = "desc",
) -> HTMLResponse:
    notifications = {
        "listing-added": "Sale listing has been added.",
        "listing-duplicated": "Sale listing has been duplicated.",
        "listing-price-updated": "Sale price has been updated.",
        "listing-sold": "Item has been marked as sold.",
        "listing-deleted": "Sale listing has been deleted.",
    }
    context = _sales_context(
        SalesService(session, settings.market_context),
        active_sort=active_sort,
        active_direction=active_direction,
        sold_sort=sold_sort,
        sold_direction=sold_direction,
        notification=notifications.get(notice),
    )
    return templates.TemplateResponse(request, "sales.html", context=context)


@router.post("/sales", response_class=HTMLResponse, response_model=None)
async def start_sale(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    values = _form_values(form, ("item_uuid", "asking_price"))
    service = SalesService(session, settings.market_context)
    try:
        command = SaleListingCreate.model_validate(values)
    except ValidationError as error:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                errors=_validation_messages(error),
                form_values=values,
            ),
            status_code=422,
        )
    try:
        service.start(command)
    except SaleItemNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                errors=["Item not found."],
                form_values=values,
            ),
            status_code=404,
        )
    return RedirectResponse(url="/sales?notice=listing-added", status_code=303)


@router.post(
    "/sales/{listing_uuid}/duplicate",
    response_class=HTMLResponse,
    response_model=None,
)
def duplicate_sale(
    request: Request,
    listing_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    service = SalesService(session, settings.market_context)
    try:
        service.duplicate(listing_uuid)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(service, errors=["Sale listing not found."]),
            status_code=404,
        )
    return RedirectResponse(url="/sales?notice=listing-duplicated", status_code=303)


@router.post(
    "/sales/{listing_uuid}/delete",
    response_class=HTMLResponse,
    response_model=None,
)
def delete_sale(
    request: Request,
    listing_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    service = SalesService(session, settings.market_context)
    try:
        service.delete(listing_uuid)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(service, errors=["Sale listing not found."]),
            status_code=404,
        )
    return RedirectResponse(url="/sales?notice=listing-deleted", status_code=303)


@router.post(
    "/sales/{listing_uuid}/price",
    response_class=HTMLResponse,
    response_model=None,
)
async def update_sale_price(
    request: Request,
    listing_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    values = _form_values(form, ("asking_price",))
    service = SalesService(session, settings.market_context)
    try:
        command = SalePriceUpdate.model_validate(values)
    except ValidationError as error:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(service, errors=_validation_messages(error)),
            status_code=422,
        )
    try:
        service.update_price(listing_uuid, command)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(service, errors=["Sale listing not found."]),
            status_code=404,
        )
    except SaleListingConflict:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(service, errors=["A sold listing cannot be repriced."]),
            status_code=409,
        )
    return RedirectResponse(url="/sales?notice=listing-price-updated", status_code=303)


@router.post(
    "/sales/{listing_uuid}/sold",
    response_class=HTMLResponse,
    response_model=None,
)
def mark_sale_sold(
    request: Request,
    listing_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    service = SalesService(session, settings.market_context)
    try:
        service.mark_sold(listing_uuid)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(service, errors=["Sale listing not found."]),
            status_code=404,
        )
    except SaleListingConflict:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(service, errors=["Item has already been marked as sold."]),
            status_code=409,
        )
    return RedirectResponse(url="/sales?notice=listing-sold", status_code=303)


@router.get("/items", response_class=HTMLResponse)
def search_items(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = Query(default=""),
    sort: Annotated[ItemSortField, Query()] = "name",
    direction: Annotated[SortDirection, Query()] = "asc",
    updated: Annotated[UUID | None, Query()] = None,
) -> HTMLResponse:
    catalog = CatalogService(session, settings.market_context)
    notification = None
    if updated is not None:
        try:
            updated_item = catalog.detail(updated)
        except ItemNotFound:
            pass
        else:
            notification = f"{updated_item.display_name} price has been updated."
    context = _search_context(
        catalog,
        q,
        settings.market_context,
        sort_field=sort,
        sort_direction=direction,
        notification=notification,
    )
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
    values = _form_values(form, ("total_price", "observed_at", "note"))
    values["lot_quantity"] = "1"
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
    redirect_url = f"/items?updated={item_uuid}"
    if _is_htmx(request):
        return Response(status_code=204, headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


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
