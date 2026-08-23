from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from math import ceil, floor, log10
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from dofus_touch_economy.app import get_bigquery_sync_manager, get_session, get_settings
from dofus_touch_economy.bigquery_sync import BigQuerySyncManager
from dofus_touch_economy.config import Settings
from dofus_touch_economy.normalization import normalize_item_name
from dofus_touch_economy.schemas import (
    InvalidationCreate,
    ItemCreate,
    ItemCurrentPriceUpdate,
    PriceObservationCreate,
    RecipeIngredientPriceUpdate,
    SaleBulkAction,
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
from dofus_touch_economy.services.recipes import (
    RecipeCalculatorSelectionError,
    RecipeCalculatorService,
    RecipeCatalogFilters,
    RecipeCatalogService,
    RecipeEconomicsFilter,
    RecipeSortDirection,
    RecipeSortField,
)
from dofus_touch_economy.services.sales import (
    DailySalesTotal,
    SaleItemNotFound,
    SaleListingConflict,
    SaleListingFilters,
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
SalesStatusFilter = Literal["all", "active", "sold"]


@dataclass(frozen=True)
class SalesFilterState:
    item_uuid: UUID | None = None
    item_query: str = ""
    category: str = ""
    status: SalesStatusFilter = "all"
    min_price: int | None = None
    max_price: int | None = None
    min_profit: Decimal | None = None
    max_profit: Decimal | None = None
    date_from: date | None = None
    date_to: date | None = None
    validation_errors: tuple[str, ...] = ()

    def parameters(self) -> dict[str, str]:
        parameters: dict[str, str] = {}
        if self.item_uuid is not None:
            parameters["item_uuid"] = str(self.item_uuid)
        if self.item_query:
            parameters["item_query"] = self.item_query
        if self.category:
            parameters["category"] = self.category
        if self.status != "all":
            parameters["status"] = self.status
        for name, value in (
            ("min_price", self.min_price),
            ("max_price", self.max_price),
            ("min_profit", self.min_profit),
            ("max_profit", self.max_profit),
        ):
            if value is not None:
                parameters[name] = str(value)
        if self.date_from is not None:
            parameters["date_from"] = self.date_from.isoformat()
        if self.date_to is not None:
            parameters["date_to"] = self.date_to.isoformat()
        return parameters

    def listing_filters(self) -> SaleListingFilters:
        return SaleListingFilters(
            item_uuid=self.item_uuid,
            item_query=self.item_query,
            category=self.category,
            minimum_price=self.min_price,
            maximum_price=self.max_price,
            minimum_profit=self.min_profit,
            maximum_profit=self.max_profit,
            date_from=self.date_from,
            date_to=self.date_to,
            display_timezone=PACIFIC_TIME,
        )

    def errors(self) -> list[str]:
        errors = list(self.validation_errors)
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            errors.append("Minimum price cannot be greater than maximum price.")
        if (
            self.min_profit is not None
            and self.max_profit is not None
            and self.min_profit > self.max_profit
        ):
            errors.append("Minimum profit cannot be greater than maximum profit.")
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            errors.append("From date cannot be after through date.")
        return errors


DEFAULT_SALES_FILTER_STATE = SalesFilterState()


@dataclass(frozen=True)
class RecipeFilterState:
    item_query: str = ""
    category: str = ""
    profession: str = ""
    minimum_level: int | None = None
    maximum_level: int | None = None
    economics: RecipeEconomicsFilter = "all"

    def parameters(self) -> dict[str, str]:
        parameters: dict[str, str] = {}
        if self.item_query:
            parameters["q"] = self.item_query
        if self.category:
            parameters["category"] = self.category
        if self.profession:
            parameters["profession"] = self.profession
        if self.minimum_level is not None:
            parameters["min_level"] = str(self.minimum_level)
        if self.maximum_level is not None:
            parameters["max_level"] = str(self.maximum_level)
        if self.economics != "all":
            parameters["economics"] = self.economics
        return parameters

    def catalog_filters(self) -> RecipeCatalogFilters:
        return RecipeCatalogFilters(
            item_query=self.item_query,
            category=self.category,
            profession=self.profession,
            minimum_level=self.minimum_level,
            maximum_level=self.maximum_level,
            economics=self.economics,
        )

    def errors(self) -> list[str]:
        if (
            self.minimum_level is not None
            and self.maximum_level is not None
            and self.minimum_level > self.maximum_level
        ):
            return ["Minimum level cannot be greater than maximum level."]
        return []


def _sales_sort_state(
    active_sort: Annotated[SaleSortField, Query()] = "started",
    active_direction: Annotated[SaleSortDirection, Query()] = "desc",
    sold_sort: Annotated[SaleSortField, Query()] = "sold",
    sold_direction: Annotated[SaleSortDirection, Query()] = "desc",
) -> SalesSortState:
    return SalesSortState(active_sort, active_direction, sold_sort, sold_direction)


def _sales_filter_state(
    item_uuid: Annotated[UUID | None, Query()] = None,
    item_query: Annotated[str, Query(max_length=200)] = "",
    category: Annotated[str, Query(max_length=200)] = "",
    status: Annotated[SalesStatusFilter, Query()] = "all",
    min_price: Annotated[str, Query(max_length=50)] = "",
    max_price: Annotated[str, Query(max_length=50)] = "",
    min_profit: Annotated[str, Query(max_length=50)] = "",
    max_profit: Annotated[str, Query(max_length=50)] = "",
    date_from: Annotated[str, Query(max_length=10)] = "",
    date_to: Annotated[str, Query(max_length=10)] = "",
) -> SalesFilterState:
    errors: list[str] = []
    return SalesFilterState(
        item_uuid=item_uuid,
        item_query=item_query.strip(),
        category=category.strip(),
        status=status,
        min_price=_optional_integer_filter(min_price, "Minimum price", errors),
        max_price=_optional_integer_filter(max_price, "Maximum price", errors),
        min_profit=_optional_decimal_filter(min_profit, "Minimum profit", errors),
        max_profit=_optional_decimal_filter(max_profit, "Maximum profit", errors),
        date_from=_optional_date_filter(date_from, "From date", errors),
        date_to=_optional_date_filter(date_to, "Through date", errors),
        validation_errors=tuple(errors),
    )


def _recipe_filter_state(
    q: Annotated[str, Query(max_length=200)] = "",
    category: Annotated[str, Query(max_length=200)] = "",
    profession: Annotated[str, Query(max_length=200)] = "",
    min_level: Annotated[int | None, Query(ge=1, le=1000)] = None,
    max_level: Annotated[int | None, Query(ge=1, le=1000)] = None,
    economics: Annotated[RecipeEconomicsFilter, Query()] = "all",
) -> RecipeFilterState:
    return RecipeFilterState(
        item_query=q.strip(),
        category=category.strip(),
        profession=profession.strip(),
        minimum_level=min_level,
        maximum_level=max_level,
        economics=economics,
    )


def _optional_integer_filter(value: str, label: str, errors: list[str]) -> int | None:
    stripped = value.strip().replace(",", "")
    if not stripped:
        return None
    try:
        parsed = int(stripped)
    except ValueError:
        errors.append(f"{label} must be a whole number.")
        return None
    if parsed < 0:
        errors.append(f"{label} cannot be negative.")
        return None
    return parsed


def _optional_decimal_filter(value: str, label: str, errors: list[str]) -> Decimal | None:
    stripped = value.strip().replace(",", "")
    if not stripped:
        return None
    try:
        parsed = Decimal(stripped)
    except InvalidOperation:
        errors.append(f"{label} must be a number.")
        return None
    if not parsed.is_finite():
        errors.append(f"{label} must be a finite number.")
        return None
    return parsed


def _optional_date_filter(value: str, label: str, errors: list[str]) -> date | None:
    if not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        errors.append(f"{label} must use YYYY-MM-DD format.")
        return None


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").casefold() == "true"


def _detail_context(
    detail,
    *,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
    recipe_errors: list[str] | None = None,
    recipe_form_values: dict[str, str] | None = None,
    notification: str | None = None,
    include_metrics_oob: bool = False,
) -> dict[str, object]:
    return {
        "detail": detail,
        "error": None,
        "active_tab": "items",
        "errors": errors or [],
        "form_values": form_values or {},
        "recipe_errors": recipe_errors or [],
        "recipe_form_values": recipe_form_values or {},
        "notification": notification,
        "include_metrics_oob": include_metrics_oob,
    }


def _search_context(
    catalog: CatalogService,
    query: str,
    market_context: str,
    *,
    sort_field: ItemSortField = "name",
    sort_direction: SortDirection = "asc",
    category: str = "",
    notification: str | None = None,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
) -> dict[str, object]:
    category_filter = normalize_item_name(category) if category.strip() else ""
    category_choices = catalog.category_choices()
    category_labels = {choice.key: choice.label for choice in category_choices}
    items = catalog.search(
        query,
        limit=None,
        sort_field=sort_field,
        sort_direction=sort_direction,
        category=category_filter,
    )
    suggestions = (
        catalog.suggest(query, limit=5, category=category_filter)
        if query.strip() and not items
        else []
    )
    proposed_display_name = catalog.format_display_name(query) if query.strip() else query
    recognized_category = category_labels.get(category_filter)
    if recognized_category is None and query.strip():
        recognized_category = catalog.infer_category(query)
    return {
        "query": query,
        "category_filter": category_filter,
        "category_choices": category_choices,
        "items": items,
        "active_tab": "items",
        "suggestions": suggestions,
        "proposed_display_name": proposed_display_name,
        "recognized_category": recognized_category,
        "market_context": market_context,
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "sort_columns": _sort_columns(
            query,
            category_filter,
            sort_field,
            sort_direction,
        ),
        "notification": notification,
        "errors": errors or [],
        "form_values": form_values or {},
    }


def _sort_columns(
    query: str,
    category: str,
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
        next_direction = "asc" if active and sort_direction == "desc" else "desc"
        parameters = {
            "q": query,
            "category": category,
            "sort": field,
            "direction": next_direction,
        }
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
    filter_state: SalesFilterState = DEFAULT_SALES_FILTER_STATE,
    notification: str | None = None,
    errors: list[str] | None = None,
    form_values: dict[str, str] | None = None,
) -> dict[str, object]:
    item_choices = service.item_choices()
    listing_filters = filter_state.listing_filters()
    show_active = filter_state.status in ("all", "active")
    show_sold = filter_state.status in ("all", "sold")
    active_sales = (
        service.active(
            sort_state.active_sort,
            sort_state.active_direction,
            listing_filters,
        )
        if show_active
        else []
    )
    sold_sales = (
        service.sold(
            sort_state.sold_sort,
            sort_state.sold_direction,
            listing_filters,
        )
        if show_sold
        else []
    )
    category_labels: dict[str, str] = {}
    for item in item_choices:
        if item.category_key:
            category_labels.setdefault(item.category_key, (item.category or "").title())
    daily_totals = service.daily_totals(PACIFIC_TIME, sold_sales)
    filter_parameters = filter_state.parameters()
    sales_parameters = {**sort_state.parameters(), **filter_parameters}
    filter_item_value = filter_state.item_query
    if filter_state.item_uuid is not None:
        matching_item = next(
            (item for item in item_choices if item.uuid == filter_state.item_uuid),
            None,
        )
        if matching_item is not None:
            filter_item_value = matching_item.display_name
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
        "active_sales": active_sales,
        "active_total_price": sum(sale.asking_price or 0 for sale in active_sales),
        "sold_sales": sold_sales,
        "active_sort_columns": _sales_sort_columns(
            "active",
            sort_state.active_sort,
            sort_state.active_direction,
            sort_state.sold_sort,
            sort_state.sold_direction,
            filter_parameters,
        ),
        "sold_sort_columns": _sales_sort_columns(
            "sold",
            sort_state.sold_sort,
            sort_state.sold_direction,
            sort_state.active_sort,
            sort_state.active_direction,
            filter_parameters,
        ),
        "sales_sort_query": urlencode(sales_parameters),
        "sort_state": sort_state,
        "filter_state": filter_state,
        "filter_item_value": filter_item_value,
        "has_sales_filters": bool(filter_parameters),
        "show_active": show_active,
        "show_sold": show_sold,
        "sales_chart": _sales_chart(daily_totals),
        "notification": notification,
        "errors": [*filter_state.errors(), *(errors or [])],
        "form_values": form_values or {},
    }


def _sales_redirect_url(
    sort_state: SalesSortState,
    notice: str,
    *,
    filter_state: SalesFilterState = DEFAULT_SALES_FILTER_STATE,
    anchor: str | None = None,
    count: int | None = None,
) -> str:
    parameters = {
        **sort_state.parameters(),
        **filter_state.parameters(),
        "notice": notice,
    }
    if count is not None:
        parameters["count"] = str(count)
    fragment = "" if anchor is None else f"#{anchor}"
    return f"/sales?{urlencode(parameters)}{fragment}"


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
    chart_values = [Decimal(point.total_price) for point in daily_totals]
    chart_values.extend(
        value
        for point in daily_totals
        for value in (point.total_cost, point.total_profit)
        if value is not None
    )
    minimum = min([Decimal(0), *chart_values])
    maximum = max([Decimal(0), *chart_values])
    tick_step = _nice_tick_step(max(1, ceil(maximum - minimum)))
    chart_min = floor(minimum / tick_step) * tick_step
    chart_max = ceil(maximum / tick_step) * tick_step
    if chart_min == chart_max:
        chart_max = chart_min + tick_step * 4
    chart_span = chart_max - chart_min

    base_points: list[dict[str, object]] = []
    for index, total in enumerate(daily_totals):
        x = (
            left + plot_width / 2
            if len(daily_totals) == 1
            else left + (plot_width * index / (len(daily_totals) - 1))
        )
        base_points.append(
            {
                "x": round(x, 2),
                "date": total.sold_on.isoformat(),
                "daily_total": total,
            }
        )

    series: list[dict[str, object]] = []
    for key, label, attribute, count_attribute in (
        ("sales", "Sales", "total_price", "sold_count"),
        ("cost", "Cost", "total_cost", "costed_count"),
        ("profit", "Profit", "total_profit", "profit_count"),
    ):
        points: list[dict[str, object]] = []
        segments: list[str] = []
        current_segment: list[str] = []
        for base_point in base_points:
            daily_total = base_point["daily_total"]
            value = getattr(daily_total, attribute)
            if value is None:
                if current_segment:
                    segments.append(" ".join(current_segment))
                    current_segment = []
                continue
            decimal_value = Decimal(value)
            y = top + plot_height * float(
                (Decimal(chart_max) - decimal_value) / Decimal(chart_span)
            )
            point = {
                "x": base_point["x"],
                "y": round(y, 2),
                "date": base_point["date"],
                "value_label": f"{decimal_value:,}",
                "item_count": getattr(daily_total, count_attribute),
            }
            points.append(point)
            current_segment.append(f"{point['x']},{point['y']}")
        if current_segment:
            segments.append(" ".join(current_segment))
        series.append(
            {
                "key": key,
                "label": label,
                "segments": segments,
                "points": points,
            }
        )

    label_indexes = _chart_label_indexes(len(base_points))
    total_price = sum(point.total_price for point in daily_totals)
    total_cost = sum(
        (point.total_cost for point in daily_totals if point.total_cost is not None),
        start=Decimal(0),
    )
    total_profit = sum(
        (point.total_profit for point in daily_totals if point.total_profit is not None),
        start=Decimal(0),
    )
    sold_count = sum(point.sold_count for point in daily_totals)
    priced_count = sum(point.priced_count for point in daily_totals)
    costed_count = sum(point.costed_count for point in daily_totals)
    profit_count = sum(point.profit_count for point in daily_totals)
    average_price = None if not priced_count else round(total_price / priced_count)
    return {
        "width": width,
        "height": height,
        "left": left,
        "right_x": width - right,
        "top": top,
        "bottom_y": height - bottom,
        "series": series,
        "x_labels": [base_points[index] for index in label_indexes],
        "y_ticks": [
            {
                "value": value,
                "label": f"{value:,}",
                "y": round(
                    top + plot_height * ((chart_max - value) / chart_span),
                    2,
                ),
            }
            for value in range(chart_min, chart_max + 1, tick_step)
        ],
        "total_price_label": f"{total_price:,}",
        "total_cost_label": "—" if not costed_count else f"{total_cost:,}",
        "total_profit_label": "—" if not profit_count else f"{total_profit:,}",
        "sold_count": sold_count,
        "cost_coverage_label": f"{costed_count} of {sold_count}",
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
    filter_parameters: dict[str, str],
) -> list[dict[str, object]]:
    columns = (
        (
            ("name", "Item", False),
            ("category", "Category", False),
            ("price", "Price", True),
            ("cost", "Cost", True),
            ("profit", "Profit", True),
            ("started", "Selling Since", False),
        )
        if table == "active"
        else (
            ("name", "Item", False),
            ("price", "Price", True),
            ("cost", "Cost", True),
            ("profit", "Profit", True),
            ("started", "Selling Started", False),
            ("sold", "Date Sold", False),
        )
    )
    result: list[dict[str, object]] = []
    for field, label, numeric in columns:
        active = field == sort_field
        next_direction = "asc" if active and sort_direction == "desc" else "desc"
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
        parameters.update(filter_parameters)
        result.append(
            {
                "field": field,
                "label": label,
                "numeric": numeric,
                "active": active,
                "direction": sort_direction if active else None,
                "next_direction": next_direction,
                "url": (
                    f"/sales?{urlencode(parameters)}#"
                    f"{'currently-selling' if table == 'active' else 'sold-history'}"
                ),
            }
        )
    return result


def _recipe_sort_columns(
    sort_field: RecipeSortField,
    sort_direction: RecipeSortDirection,
    filter_parameters: dict[str, str],
) -> list[dict[str, object]]:
    columns = (
        ("name", "Item", False),
        ("category", "Category", False),
        ("profession", "Profession", False),
        ("level", "Required Level", True),
        ("price", "Current Price", True),
        ("cost", "Recipe Cost", True),
        ("profit", "Profit", True),
        ("roi", "ROI", True),
    )
    result: list[dict[str, object]] = []
    for field, label, numeric in columns:
        active = field == sort_field
        next_direction = "asc" if active and sort_direction == "desc" else "desc"
        parameters = {
            **filter_parameters,
            "sort": field,
            "direction": next_direction,
        }
        result.append(
            {
                "field": field,
                "label": label,
                "numeric": numeric,
                "active": active,
                "direction": sort_direction if active else None,
                "next_direction": next_direction,
                "url": f"/recipes?{urlencode(parameters)}#recipe-catalog",
            }
        )
    return result


def _recipe_page_context(
    session: Session,
    market_context: str,
    filter_state: RecipeFilterState,
    sort_field: RecipeSortField,
    sort_direction: RecipeSortDirection,
    *,
    notification: str | None = None,
    price_errors: list[str] | None = None,
    price_item_uuid: UUID | None = None,
    price_form_value: str = "",
) -> dict[str, object]:
    result = RecipeCatalogService(session, market_context).browse(
        filter_state.catalog_filters(),
        sort_field,
        sort_direction,
    )
    minimum_level = filter_state.minimum_level or result.minimum_available_level
    maximum_level = filter_state.maximum_level or result.maximum_available_level
    filter_parameters = filter_state.parameters()
    view_parameters = {
        **filter_parameters,
        "sort": sort_field,
        "direction": sort_direction,
    }
    return {
        "active_tab": "recipes",
        "market_context": market_context,
        "recipes": result.rows,
        "recipe_total_count": result.total_count,
        "profession_choices": result.professions,
        "category_choices": result.categories,
        "minimum_available_level": result.minimum_available_level,
        "maximum_available_level": result.maximum_available_level,
        "selected_minimum_level": minimum_level,
        "selected_maximum_level": maximum_level,
        "filter_state": filter_state,
        "has_recipe_filters": bool(filter_parameters),
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "sort_columns": _recipe_sort_columns(
            sort_field,
            sort_direction,
            filter_parameters,
        ),
        "recipe_view_query": urlencode(view_parameters),
        "errors": filter_state.errors(),
        "notification": notification,
        "price_errors": price_errors or [],
        "price_item_uuid": price_item_uuid,
        "price_form_value": price_form_value,
    }


def _recipe_calculator_context(
    service: RecipeCalculatorService,
    *,
    selected_quantities: dict[UUID, int] | None = None,
    result=None,
    errors: list[str] | None = None,
) -> dict[str, object]:
    choices = service.choices()
    quantities = selected_quantities or {}
    return {
        "active_tab": "recipe_calculator",
        "choice_data": [
            {
                "item_uuid": str(choice.item_uuid),
                "display_name": choice.display_name,
                "category": choice.category,
                "icon_url": choice.icon_url,
                "profession": choice.profession,
                "profession_level": choice.profession_level,
            }
            for choice in choices
        ],
        "selected_choices": [choice for choice in choices if choice.item_uuid in quantities],
        "selected_quantities": quantities,
        "result": result,
        "errors": errors or [],
    }


def _parse_recipe_calculator_selections(form) -> tuple[dict[UUID, int], list[str]]:
    selected_values = form.getlist("selected_item_uuid")
    errors: list[str] = []
    if not selected_values:
        return {}, ["Select at least one craftable item."]
    if len(selected_values) > 100:
        return {}, ["Select no more than 100 craftable items."]

    selections: dict[UUID, int] = {}
    for raw_item_uuid in selected_values:
        if not isinstance(raw_item_uuid, str):
            errors.append("A selected item identifier is invalid.")
            continue
        try:
            item_uuid = UUID(raw_item_uuid)
        except ValueError:
            errors.append("A selected item identifier is invalid.")
            continue
        if item_uuid in selections:
            errors.append("A craftable item was selected more than once.")
            continue
        raw_quantity = form.get(f"quantity_{item_uuid}", "1")
        try:
            quantity = int(raw_quantity) if isinstance(raw_quantity, str) else 0
        except ValueError:
            quantity = 0
        if not 1 <= quantity <= 1000:
            errors.append("Each craft quantity must be between 1 and 1,000.")
            continue
        selections[item_uuid] = quantity
    return selections, errors


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


@router.get("/recipes", response_class=HTMLResponse)
def recipes_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    filter_state: Annotated[RecipeFilterState, Depends(_recipe_filter_state)],
    sort: Annotated[RecipeSortField, Query()] = "name",
    direction: Annotated[RecipeSortDirection, Query()] = "asc",
    updated: Annotated[UUID | None, Query()] = None,
) -> HTMLResponse:
    notification = None
    if updated is not None:
        try:
            updated_item = CatalogService(session, settings.market_context).detail(updated)
        except ItemNotFound:
            pass
        else:
            notification = f"{updated_item.display_name} price has been updated."
    return templates.TemplateResponse(
        request,
        "recipes.html",
        context=_recipe_page_context(
            session,
            settings.market_context,
            filter_state,
            sort,
            direction,
            notification=notification,
        ),
    )


@router.get("/recipe-calculator", response_class=HTMLResponse)
def recipe_calculator_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    service = RecipeCalculatorService(session, settings.market_context)
    return templates.TemplateResponse(
        request,
        "recipe_calculator.html",
        context=_recipe_calculator_context(service),
    )


@router.post("/recipe-calculator", response_class=HTMLResponse)
async def calculate_recipes(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    form = await request.form()
    selections, errors = _parse_recipe_calculator_selections(form)
    service = RecipeCalculatorService(session, settings.market_context)
    result = None
    if not errors:
        try:
            result = service.calculate(selections)
        except RecipeCalculatorSelectionError as error:
            errors.append(str(error))
    return templates.TemplateResponse(
        request,
        "recipe_calculator.html",
        context=_recipe_calculator_context(
            service,
            selected_quantities=selections,
            result=result,
            errors=errors,
        ),
        status_code=422 if errors else 200,
    )


@router.get("/bigquery-sync", response_class=HTMLResponse)
def bigquery_sync_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    manager: Annotated[BigQuerySyncManager, Depends(get_bigquery_sync_manager)],
    notice: str | None = Query(default=None),
) -> HTMLResponse:
    notifications = {
        "started": "BigQuery snapshot publication has started.",
        "already-running": "A BigQuery snapshot publication is already running.",
    }
    return templates.TemplateResponse(
        request,
        "bigquery_sync.html",
        context={
            "active_tab": "bigquery_sync",
            "settings": settings,
            "sync": manager.snapshot(),
            "notification": notifications.get(notice),
        },
    )


@router.post("/bigquery-sync", response_model=None)
def start_bigquery_sync(
    manager: Annotated[BigQuerySyncManager, Depends(get_bigquery_sync_manager)],
) -> RedirectResponse:
    notice = "started" if manager.start() else "already-running"
    return RedirectResponse(url=f"/bigquery-sync?notice={notice}", status_code=303)


@router.get("/bigquery-sync/status", response_class=JSONResponse)
def bigquery_sync_status(
    manager: Annotated[BigQuerySyncManager, Depends(get_bigquery_sync_manager)],
) -> JSONResponse:
    return JSONResponse(manager.snapshot().to_dict())


@router.post(
    "/recipes/{item_uuid}/price",
    response_class=HTMLResponse,
    response_model=None,
)
async def update_recipe_item_current_price(
    request: Request,
    item_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    filter_state: Annotated[RecipeFilterState, Depends(_recipe_filter_state)],
    sort: Annotated[RecipeSortField, Query()] = "name",
    direction: Annotated[RecipeSortDirection, Query()] = "asc",
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    values = _form_values(form, ("current_price",))
    try:
        command = ItemCurrentPriceUpdate.model_validate(values)
    except ValidationError as error:
        return templates.TemplateResponse(
            request,
            "recipes.html",
            context=_recipe_page_context(
                session,
                settings.market_context,
                filter_state,
                sort,
                direction,
                price_errors=_validation_messages(error),
                price_item_uuid=item_uuid,
                price_form_value=values["current_price"],
            ),
            status_code=422,
        )

    try:
        PriceService(session, settings.market_context).record(
            item_uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=command.current_price,
                observed_at=datetime.now(UTC),
                note="Recipe catalog current price update",
            ),
        )
    except ItemNotFound:
        return _error_response(request, "Item not found", 404)

    parameters = {
        **filter_state.parameters(),
        "sort": sort,
        "direction": direction,
        "updated": str(item_uuid),
    }
    return RedirectResponse(
        url=f"/recipes?{urlencode(parameters)}#recipe-catalog",
        status_code=303,
    )


@router.get("/sales", response_class=HTMLResponse)
def sales_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
    notice: str | None = Query(default=None),
    count: int | None = Query(default=None, ge=1, le=500),
) -> HTMLResponse:
    notifications = {
        "listing-added": "Sale listing has been added.",
        "listing-duplicated": "Sale listing has been duplicated.",
        "listing-price-updated": "Sale price has been updated.",
        "listing-sold": "Item has been marked as sold.",
        "listing-reopened": "Item has been returned to Currently Selling.",
        "listing-deleted": "Sale listing has been deleted.",
        "listings-sold": (
            f"{count} selected {'item has' if count == 1 else 'items have'} been marked as sold."
            if count is not None
            else "Selected items have been marked as sold."
        ),
        "listings-deleted": (
            f"{count} selected {'listing has' if count == 1 else 'listings have'} been deleted."
            if count is not None
            else "Selected listings have been deleted."
        ),
    }
    context = _sales_context(
        SalesService(session, settings.market_context),
        sort_state=sort_state,
        filter_state=filter_state,
        notification=notifications.get(notice),
    )
    return templates.TemplateResponse(request, "sales.html", context=context)


@router.post("/sales", response_class=HTMLResponse, response_model=None)
async def start_sale(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
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
                filter_state=filter_state,
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
                filter_state=filter_state,
                errors=["Item not found."],
                form_values=values,
            ),
            status_code=404,
        )
    return RedirectResponse(
        url=_sales_redirect_url(
            sort_state,
            "listing-added",
            filter_state=filter_state,
        ),
        status_code=303,
    )


@router.post("/sales/bulk", response_class=HTMLResponse, response_model=None)
async def bulk_active_sales(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    service = SalesService(session, settings.market_context)
    try:
        command = SaleBulkAction.model_validate(
            {
                "action": form.get("action"),
                "listing_uuids": form.getlist("listing_uuid"),
            }
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                filter_state=filter_state,
                errors=["Select at least one Currently Selling row and choose a bulk action."],
            ),
            status_code=422,
        )

    try:
        if command.action == "mark_sold":
            changed = service.mark_sold_many(command.listing_uuids)
            notice = "listings-sold"
        else:
            changed = service.delete_active_many(command.listing_uuids)
            notice = "listings-deleted"
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                filter_state=filter_state,
                errors=["One or more selected sale listings could not be found."],
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
                filter_state=filter_state,
                errors=["One or more selected listings are no longer Currently Selling."],
            ),
            status_code=409,
        )

    return RedirectResponse(
        url=_sales_redirect_url(
            sort_state,
            notice,
            filter_state=filter_state,
            anchor="currently-selling",
            count=len(changed),
        ),
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
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
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
                filter_state=filter_state,
                errors=["Sale listing not found."],
            ),
            status_code=404,
        )
    return RedirectResponse(
        url=_sales_redirect_url(
            sort_state,
            "listing-duplicated",
            filter_state=filter_state,
        ),
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
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
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
                filter_state=filter_state,
                errors=["Sale listing not found."],
            ),
            status_code=404,
        )
    return RedirectResponse(
        url=_sales_redirect_url(
            sort_state,
            "listing-deleted",
            filter_state=filter_state,
        ),
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
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
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
                filter_state=filter_state,
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
                filter_state=filter_state,
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
                filter_state=filter_state,
                errors=["A sold listing cannot be repriced."],
            ),
            status_code=409,
        )
    return RedirectResponse(
        url=_sales_redirect_url(
            sort_state,
            "listing-price-updated",
            filter_state=filter_state,
        ),
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
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
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
                filter_state=filter_state,
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
                filter_state=filter_state,
                errors=["Item has already been marked as sold."],
            ),
            status_code=409,
        )
    return RedirectResponse(
        url=_sales_redirect_url(
            sort_state,
            "listing-sold",
            filter_state=filter_state,
            anchor="currently-selling",
        ),
        status_code=303,
    )


@router.post(
    "/sales/{listing_uuid}/reopen",
    response_class=HTMLResponse,
    response_model=None,
)
def reopen_sale(
    request: Request,
    listing_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    sort_state: Annotated[SalesSortState, Depends(_sales_sort_state)],
    filter_state: Annotated[SalesFilterState, Depends(_sales_filter_state)],
) -> HTMLResponse | RedirectResponse:
    service = SalesService(session, settings.market_context)
    try:
        service.reopen(listing_uuid)
    except SaleListingNotFound:
        return templates.TemplateResponse(
            request,
            "sales.html",
            context=_sales_context(
                service,
                sort_state=sort_state,
                filter_state=filter_state,
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
                filter_state=filter_state,
                errors=["Only a sold listing can be returned to Currently Selling."],
            ),
            status_code=409,
        )
    return RedirectResponse(
        url=_sales_redirect_url(
            sort_state,
            "listing-reopened",
            filter_state=filter_state,
        ),
        status_code=303,
    )


@router.get("/items", response_class=HTMLResponse)
def search_items(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = Query(default=""),
    category: str = Query(default=""),
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
        category=category,
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
    updated: Annotated[UUID | None, Query()] = None,
    notice: str | None = Query(default=None),
) -> HTMLResponse:
    catalog = CatalogService(session, settings.market_context)
    try:
        detail = catalog.detail(item_uuid)
    except ItemNotFound:
        return _error_response(request, "Item not found", 404)
    notifications = {
        "price-history-deleted": "Price history row has been deleted.",
        "price-history-already-deleted": "Price history row was already deleted.",
    }
    notification = notifications.get(notice)
    if notification is None and updated is not None:
        try:
            updated_item = catalog.detail(updated)
        except ItemNotFound:
            pass
        else:
            notification = f"{updated_item.display_name} price has been updated."
    return templates.TemplateResponse(
        request,
        "item_detail.html",
        context=_detail_context(detail, notification=notification),
    )


@router.post(
    "/price-observations/{observation_uuid}/delete",
    response_class=HTMLResponse,
    response_model=None,
)
def delete_price_history_row(
    request: Request,
    observation_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    service = PriceService(session, settings.market_context)
    try:
        item_uuid = service.item_uuid_for_observation(observation_uuid)
    except ObservationNotFound:
        return _error_response(request, "Price history row not found", 404)
    notice = "price-history-deleted"
    try:
        service.invalidate(observation_uuid, "Deleted from item price history")
    except ObservationConflict:
        notice = "price-history-already-deleted"
    redirect_url = f"/items/{item_uuid}?notice={notice}#price-panel"
    if _is_htmx(request):
        return Response(status_code=204, headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post(
    "/items/{item_uuid}/price",
    response_class=HTMLResponse,
    response_model=None,
)
async def update_item_current_price(
    request: Request,
    item_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    catalog = CatalogService(session, settings.market_context)
    try:
        detail = catalog.detail(item_uuid)
    except ItemNotFound:
        return _error_response(request, "Item not found", 404)

    form = await request.form()
    values = _form_values(form, ("current_price",))
    try:
        command = ItemCurrentPriceUpdate.model_validate(values)
    except ValidationError as error:
        return templates.TemplateResponse(
            request,
            "item_detail.html",
            context=_detail_context(
                detail,
                errors=_validation_messages(error),
                form_values=values,
            ),
            status_code=422,
        )

    PriceService(session, settings.market_context).record(
        item_uuid,
        PriceObservationCreate(
            lot_quantity=1,
            total_price=command.current_price,
            observed_at=datetime.now(UTC),
            note="Item current price update",
        ),
    )
    return RedirectResponse(
        url=f"/items/{item_uuid}?updated={item_uuid}#price-panel",
        status_code=303,
    )


@router.post(
    "/items/{item_uuid}/recipe-ingredients/{ingredient_uuid}/price",
    response_class=HTMLResponse,
    response_model=None,
)
async def update_recipe_ingredient_price(
    request: Request,
    item_uuid: UUID,
    ingredient_uuid: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse | RedirectResponse:
    catalog = CatalogService(session, settings.market_context)
    try:
        detail = catalog.detail(item_uuid)
    except ItemNotFound:
        return _error_response(request, "Item not found", 404)
    recipe_ingredient_uuids = {
        ingredient.item_uuid
        for ingredient in ([] if detail.recipe is None else detail.recipe.ingredients)
        if ingredient.item_uuid is not None
    }
    if ingredient_uuid not in recipe_ingredient_uuids:
        return templates.TemplateResponse(
            request,
            "item_detail.html",
            context=_detail_context(
                detail,
                recipe_errors=["Recipe ingredient not found."],
            ),
            status_code=404,
        )

    form = await request.form()
    values = _form_values(form, ("unit_price",))
    try:
        command = RecipeIngredientPriceUpdate.model_validate(values)
    except ValidationError as error:
        return templates.TemplateResponse(
            request,
            "item_detail.html",
            context=_detail_context(
                detail,
                recipe_errors=_validation_messages(error),
                recipe_form_values={
                    "ingredient_uuid": str(ingredient_uuid),
                    **values,
                },
            ),
            status_code=422,
        )

    PriceService(session, settings.market_context).record(
        ingredient_uuid,
        PriceObservationCreate(
            lot_quantity=1,
            total_price=command.unit_price,
            observed_at=datetime.now(UTC),
            note="Recipe ingredient price update",
        ),
    )
    return RedirectResponse(
        url=f"/items/{item_uuid}?updated={ingredient_uuid}#recipe",
        status_code=303,
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
