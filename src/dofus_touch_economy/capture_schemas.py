from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaptureAction(StrEnum):
    SOLD = "sold"
    MARKET = "market"


class ScreenKind(StrEnum):
    SOLD_NOTIFICATION = "sold_notification"
    OWN_MARKET_LISTINGS = "own_market_listings"
    OTHER = "other"
    UNCERTAIN = "uncertain"


class CaptureOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    raw_item_name: str = Field(min_length=1)
    displayed_price_kamas: int = Field(gt=0)
    image_number: int = Field(gt=0)
    row_number: int = Field(gt=0)

    @field_validator("raw_item_name")
    @classmethod
    def require_visible_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("raw item name must contain visible text")
        return value


class CaptureExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    screen_kind: ScreenKind
    occurrences: tuple[CaptureOccurrence, ...]
    warnings: tuple[str, ...] = ()


class CapturePlanRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_number: int
    row_number: int
    raw_item_name: str
    normalized_name: str
    displayed_price_kamas: int
    display_name: str | None = None
    profession: str | None = None
    disposition: Literal["actionable", "already_present", "out_of_scope", "error"]
    detail: str


class CapturePlanChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["created", "marked_sold"]
    item_uuid: UUID
    display_name: str
    asking_price: int
    previous_asking_price: int | None = None
    listing_uuid: UUID | None = None


class CapturePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_action: CaptureAction
    screen_kind: ScreenKind
    observed_at: datetime
    rows: tuple[CapturePlanRow, ...]
    changes: tuple[CapturePlanChange, ...]
    issues: tuple[str, ...]

    @property
    def can_commit(self) -> bool:
        return not self.issues

    @property
    def is_noop(self) -> bool:
        return self.can_commit and not self.changes


@dataclass(frozen=True)
class CaptureFileInput:
    provider_file_id: str
    mime_type: str
    byte_size: int


@dataclass(frozen=True)
class CaptureIntake:
    provider: Literal["slack"]
    workspace_id: str
    channel_id: str
    parent_message_ts: str
    event_id: str | None
    requester_user_id: str
    caption: str | None
    requested_action: Literal["sold", "market"] | None
    observed_at: datetime
    files: tuple[CaptureFileInput, ...]


def requested_action_from_caption(caption: str | None) -> CaptureAction | None:
    if caption is None:
        return None
    first_nonempty = next((line.strip() for line in caption.splitlines() if line.strip()), "")
    action = first_nonempty.casefold()
    if action == CaptureAction.SOLD:
        return CaptureAction.SOLD
    if action == CaptureAction.MARKET:
        return CaptureAction.MARKET
    return None
