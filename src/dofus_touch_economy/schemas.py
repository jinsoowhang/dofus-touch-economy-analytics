from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, field_validator

DecimalString = Annotated[
    Decimal,
    PlainSerializer(lambda value: str(value), return_type=str, when_used="json"),
]


class ItemCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=200)

    @field_validator("display_name")
    @classmethod
    def normalize_display_whitespace(cls, value: str) -> str:
        display_name = " ".join(value.split())
        if not display_name:
            raise ValueError("item name must not be blank")
        return display_name

    @field_validator("category")
    @classmethod
    def normalize_optional_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        category = " ".join(value.split())
        return category or None


class PriceObservationCreate(BaseModel):
    lot_quantity: int = Field(gt=0)
    total_price: int = Field(gt=0)
    observed_at: datetime
    note: str | None = Field(default=None, max_length=500)

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


class ItemSummaryResponse(BaseModel):
    uuid: UUID
    display_name: str
    category: str | None
    created_source: Literal["imported", "manual"]


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
    raw_name: str
    quantity: int
    current_price: CurrentPriceResponse | None
    extended_cost: DecimalString | None
    is_resolved: bool


class RecipeResponse(BaseModel):
    uuid: UUID
    profession: str
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
    created_source: Literal["imported", "manual"]
    market_context: str
    current_price: CurrentPriceResponse | None
    recipe: RecipeResponse | None
    metrics: RecipeMetricsResponse | None
    price_history: list[PriceObservationResponse]
