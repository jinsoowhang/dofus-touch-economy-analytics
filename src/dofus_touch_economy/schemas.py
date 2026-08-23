from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, field_validator

from dofus_touch_economy.normalization import format_item_display_name

DecimalString = Annotated[
    Decimal,
    PlainSerializer(lambda value: str(value), return_type=str, when_used="json"),
]
COMMA_SEPARATED_INTEGER = re.compile(r"[+-]?\d{1,3}(?:,\d{3})+")


def _parse_comma_separated_integer(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if "," not in stripped:
        return stripped
    if COMMA_SEPARATED_INTEGER.fullmatch(stripped):
        return stripped.replace(",", "")
    return value


class ItemCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=200)

    @field_validator("display_name")
    @classmethod
    def format_display_name(cls, value: str) -> str:
        return format_item_display_name(value)

    @field_validator("category")
    @classmethod
    def normalize_optional_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return None if not value.strip() else format_item_display_name(value)


class PriceObservationCreate(BaseModel):
    lot_quantity: int = Field(gt=0)
    total_price: int = Field(gt=0)
    observed_at: datetime
    note: str | None = Field(default=None, max_length=500)

    @field_validator("total_price", mode="before")
    @classmethod
    def parse_total_price(cls, value: object) -> object:
        return _parse_comma_separated_integer(value)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class InvalidationCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise ValueError("reason must not be blank")
        return reason


class SaleListingCreate(BaseModel):
    item_uuid: UUID
    asking_price: int = Field(gt=0)

    @field_validator("asking_price", mode="before")
    @classmethod
    def parse_asking_price(cls, value: object) -> object:
        return _parse_comma_separated_integer(value)


class SalePriceUpdate(BaseModel):
    asking_price: int = Field(gt=0)

    @field_validator("asking_price", mode="before")
    @classmethod
    def parse_asking_price(cls, value: object) -> object:
        return _parse_comma_separated_integer(value)


class SaleBulkAction(BaseModel):
    action: Literal["mark_sold", "delete"]
    listing_uuids: list[UUID] = Field(min_length=1, max_length=500)

    @field_validator("listing_uuids")
    @classmethod
    def deduplicate_listing_uuids(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))


class RecipeIngredientPriceUpdate(BaseModel):
    unit_price: int = Field(gt=0)

    @field_validator("unit_price", mode="before")
    @classmethod
    def parse_unit_price(cls, value: object) -> object:
        return _parse_comma_separated_integer(value)


class ItemCurrentPriceUpdate(BaseModel):
    current_price: int = Field(gt=0)

    @field_validator("current_price", mode="before")
    @classmethod
    def parse_current_price(cls, value: object) -> object:
        return _parse_comma_separated_integer(value)


class SaleItemChoiceResponse(BaseModel):
    uuid: UUID
    display_name: str
    category: str | None
    category_key: str
    icon_url: str | None
    suggested_price: int | None
    sold_count: int


class SaleListingResponse(BaseModel):
    uuid: UUID
    item_uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    asking_price: int | None
    recipe_cost: DecimalString | None
    profit: DecimalString | None
    selling_started_at: datetime
    date_sold: datetime | None


class ItemSummaryResponse(BaseModel):
    uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    created_source: Literal["imported", "manual"]
    current_price: CurrentPriceResponse | None = None


class CurrentPriceResponse(BaseModel):
    observation_uuid: UUID
    lot_quantity: int
    total_price: int
    unit_price: DecimalString
    observed_at: datetime
    recorded_at: datetime
    market_context: str


class PriceObservationResponse(CurrentPriceResponse):
    item_uuid: UUID
    note: str | None
    source: str
    invalidated_at: datetime | None
    invalidation_reason: str | None


class RecipeIngredientResponse(BaseModel):
    position: int
    item_uuid: UUID | None
    display_name: str
    icon_url: str | None
    raw_name: str
    quantity: int
    current_price: CurrentPriceResponse | None
    extended_cost: DecimalString | None
    is_resolved: bool
    price_age_days: int | None = Field(default=None, ge=0)
    price_status: Literal["Missing price", "Stale price", "Current price"] = "Missing price"


class RecipeResponse(BaseModel):
    uuid: UUID
    profession: str
    profession_level: int | None = Field(ge=1)
    ingredients: list[RecipeIngredientResponse]


class RecipeMetricsResponse(BaseModel):
    recipe_cost: DecimalString | None
    profit: DecimalString | None
    roi: DecimalString | None
    is_complete: bool


class ItemDetailResponse(BaseModel):
    uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    created_source: Literal["imported", "manual"]
    market_context: str
    active_sale_count: int = Field(ge=0)
    sold_sale_count: int = Field(ge=0)
    current_price: CurrentPriceResponse | None
    recipe: RecipeResponse | None
    metrics: RecipeMetricsResponse | None
    price_history: list[PriceObservationResponse]
