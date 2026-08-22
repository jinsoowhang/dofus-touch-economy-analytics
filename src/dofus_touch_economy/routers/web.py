from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil, floor, log10
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID
from zoneinfo import ZoneInfo

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
    DailySalesTotal,
    SaleItemNotFound,
    SaleListingConflict,
    SaleListingNotFound,
    SaleSortDirection,
    SaleSortField,
    SalesService,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
PACIFIC_TIME = ZoneInfo("America/Los_Angeles")


def _pacific_time(value: datetime) -> datetime:
    return value.astimezone(PACIFIC_TIME)


templates.env.filters["pacific_time"] = _pacific_time


@dataclass(frozen=True)
class SalesSortState:
    active_sort: SaleSortField = "started"
    active_direction: SaleSortDirection = "desc"
    sold_sort: SaleSortField = "sold"
    sold_direction: SaleSortDirection = "desc"

    def parameters(self) -> dict[str, str]:
        return {
            "active_sort": self.active_sort,
            "active_direction": self.active_direction,
            "sold_sort": self.sold_sort,
            "sold_direction": self.sold_direction,
        }


DEFAULT_SALES_SORT_STATE = SalesSortState()


def _sales_sort_state(
    active_sort: Annotated[SaleSortField, Query()] = "started",
    active_direction: Annotated[SaleSortDirection, Query()] = "desc",
    sold_sort: Annotated[SaleSortField, Query()] = "sold",
    sold_direction: Annotated[SaleSortDirection, Query()] = "desc",
) -> SalesSortState:
    return SalesSortState(active_sort, active_direction, sold_sort, sold_direction)


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
        ("name", "Item Name", False),
        ("category", "Category", False),
        ("price", "Current Price", True),
        ("observed", "Last Observed", False),
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
    sort_state: SalesSortState = DEFAULT_SALES_SORT_STATE,
    notification: str | None = None,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
) -> dict[str, object]:
    item_choices = service.item_choices()
    category_labels: dict[str, str] = {}
    for item in item_choices:
        if item.category_key:
            category_labels.setdefault(item.category_key, (item.category or "").title())
    daily_totals = service.daily_totals(PACIFIC_TIME)
    return {
        "active_tab": "sales",
        "item_choices": item_choices,
        "category_choices": [
            {"key": key, "label": label}
            for key, label in sorted(
                category_labels.items(),
                key=lambda entry: entry[1].casefold(),
            )
        ],
        "active_sales": service.active(
            sort_state.active_sort,
            sort_state.active_direction,
        ),
        "sold_sales": service.sold(sort_state.sold_sort, sort_state.sold_direction),
        "active_sort_columns": _sales_sort_columns(
            "active",
            sort_state.active_sort,
            sort_state.active_direction,
            sort_state.sold_sort,
            sort_state.sold_direction,
        ),
        "sold_sort_columns": _sales_sort_columns(
            "sold",
            sort_state.sold_sort,
            sort_state.sold_direction,
            sort_state.active_sort,
            sort_state.active_direction,
        ),
        "sales_sort_query": urlencode(sort_state.parameters()),
        "sales_chart": _sales_chart(daily_totals),
        "notification": notification,
        "errors": errors or [],
        "form_values": form_values or {},
    }


def _sales_redirect_url(sort_state: SalesSortState, notice: str) -> str:
    parameters = {**sort_state.parameters(), "notice": notice}
    return f"/sales?{urlencode(parameters)}"


def _sales_chart(daily_totals: list[DailySalesTotal]) -> dict[str, object] | None:
    if not daily_totals:
        return None
    width = 900
    height = 320
    left = 78
    right = 24
    top = 24
    bottom = 58
    plot_width = width - left - right
    plot_height = height - top - bottom
    tick_step = _nice_tick_step(max(point.total_price for point in daily_totals))
    chart_max = tick_step * 4
    points: list[dict[str, object]] = []
    for index, total in enumerate(daily_totals):
        x = (
            left + plot_width / 2
            if len(daily_totals) == 1
            else left + (plot_width * index / (len(daily_totals) - 1))
        )
        y = top + plot_height * (1 - total.total_price / chart_max)
        points.append(
            {
                "x": round(x, 2),
                "y": round(y, 2),
                "date": total.sold_on.isoformat(),
                "total_price": total.total_price,
                "total_price_label": f"{total.total_price:,}",
                "sold_count": total.sold_count,
            }
        )
    label_indexes = _chart_label_indexes(len(points))
    total_price = sum(point.total_price for point in daily_totals)
    sold_count = sum(point.sold_count for point in daily_totals)
    priced_count = sum(point.priced_count for point in daily_totals)
    average_price = None if not priced_count else round(total_price / priced_count)
    return {
        "width": width,
        "height": height,
        "left": left,
        "right_x": width - right,
        "top": top,
        "bottom_y": height - bottom,
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in points),
        "points": points,
        "x_labels": [points[index] for index in label_indexes],
        "y_ticks": [
            {
                "value": value,
                "label": f"{value:,}",
                "y": round(top + plot_height * (1 - value / chart_max), 2),
            }
            for value in range(0, chart_max + 1, tick_step)
        ],
        "total_price_label": f"{total_price:,}",
        "sold_count": sold_count,
        "average_price_label": "—" if average_price is None else f"{average_price:,}",
        "daily_totals": daily_totals,
    }


def _nice_tick_step(maximum: int) -> int:
    if maximum <= 4:
        return 1
    rough_step = maximum / 4
    magnitude = 10 ** floor(log10(rough_step))
    normalized = rough_step / magnitude
    factor = next(candidate for candidate in (1, 2, 5, 10) if candidate >= normalized)
    return ceil(factor * magnitude)


def _chart_label_indexes(point_count: int) -> list[int]:
    if point_count <= 7:
        return list(range(point_count))
    return sorted({round(index * (point_count - 1) / 6) for index in range(7)})


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
            ("started", "Selling Since", False),
        )
        if table == "active"
        else (
            ("name", "Item", False),
            ("price", "Price", True),
            ("started", "Selling Started", False),
            ("sold", "Date Sold", False),
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
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
    notice: str | None = Query(default=None),
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
        sort_state=sort_state,
        notification=notifications.get(notice),
    )
    return templates.TemplateResponse(request, "sales.html", context=context)


@router.post("/sales", response_class=HTMLResponse, response_model=None)
async def start_sale(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    values = _form_values(form, ("category", "item_uuid", "asking_price"))
    service = SalesService(session, settings.market_context)
    try:
        command = SaleListingCreate.model_validate(values)
    except ValidationError as error:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
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
                sort_state=sort_state,
                errors=["Item not found."],
                form_values=values,
            ),
            status_code=404,
        )
    return RedirectResponse(
        url=_sales_redirect_url(sort_state, "listing-added"),
        status_code=303,
    )


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
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
) -> HTMLResponse | RedirectResponse:
    service = SalesService(session, settings.market_context)
    try:
        service.duplicate(listing_uuid)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                errors=["Sale listing not found."],
            ),
            status_code=404,
        )
    return RedirectResponse(
        url=_sales_redirect_url(sort_state, "listing-duplicated"),
        status_code=303,
    )


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
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
) -> HTMLResponse | RedirectResponse:
    service = SalesService(session, settings.market_context)
    try:
        service.delete(listing_uuid)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                errors=["Sale listing not found."],
            ),
            status_code=404,
        )
    return RedirectResponse(
        url=_sales_redirect_url(sort_state, "listing-deleted"),
        status_code=303,
    )


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
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
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
            context=_sales_context(
                service,
                sort_state=sort_state,
                errors=_validation_messages(error),
            ),
            status_code=422,
        )
    try:
        service.update_price(listing_uuid, command)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                errors=["Sale listing not found."],
            ),
            status_code=404,
        )
    except SaleListingConflict:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                errors=["A sold listing cannot be repriced."],
            ),
            status_code=409,
        )
    return RedirectResponse(
        url=_sales_redirect_url(sort_state, "listing-price-updated"),
        status_code=303,
    )


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
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
) -> HTMLResponse | RedirectResponse:
    service = SalesService(session, settings.market_context)
    try:
        service.mark_sold(listing_uuid)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                errors=["Sale listing not found."],
            ),
            status_code=404,
        )
    except SaleListingConflict:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                errors=["Item has already been marked as sold."],
            ),
            status_code=409,
        )
    return RedirectResponse(
        url=_sales_redirect_url(sort_state, "listing-sold"),
        status_code=303,
    )


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
