from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from dofus_touch_economy.capture_evidence import create_integrity_checked_backup
from dofus_touch_economy.capture_schemas import (
    CaptureAction,
    CaptureExtraction,
    CaptureOccurrence,
    CapturePlan,
    CapturePlanChange,
    CapturePlanRow,
    ScreenKind,
)
from dofus_touch_economy.models import (
    Item,
    Recipe,
    SaleCaptureListingAction,
    SaleListing,
)
from dofus_touch_economy.normalization import normalize_item_name
from dofus_touch_economy.repositories.catalog import CatalogRepository
from dofus_touch_economy.repositories.sale_captures import SaleCaptureRepository
from dofus_touch_economy.repositories.sales import SalesRepository
from dofus_touch_economy.schemas import SaleListingCreate
from dofus_touch_economy.services.sales import SalesService


class CaptureStateConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class CaptureCommitResult:
    plan: CapturePlan
    backup_path: Path | None


@dataclass(frozen=True)
class _ResolvedOccurrence:
    occurrence: CaptureOccurrence
    row_index: int
    item: Item
    recipe: Recipe


class SaleCaptureService:
    def __init__(
        self,
        session: Session,
        market_context: str,
        *,
        approved_professions: tuple[str, ...],
    ) -> None:
        self._session = session
        self._market_context = market_context
        self._approved_professions = frozenset(approved_professions)
        self._catalog = CatalogRepository(session)
        self._sales = SalesRepository(session)

    def plan(
        self,
        action: CaptureAction,
        extraction: CaptureExtraction,
        *,
        observed_at: datetime,
    ) -> CapturePlan:
        issues: list[str] = []
        expected_screen = {
            CaptureAction.SOLD: ScreenKind.SOLD_NOTIFICATION,
            CaptureAction.MARKET: ScreenKind.OWN_MARKET_LISTINGS,
        }[action]
        if extraction.screen_kind != expected_screen:
            issues.append(
                f"requested action {action.value} does not match screen kind "
                f"{extraction.screen_kind.value}"
            )
        issues.extend(f"extraction warning: {warning}" for warning in extraction.warnings)
        if not extraction.occurrences:
            issues.append("screenshot contains no visible listing occurrences")

        normalized_names = {
            normalize_item_name(occurrence.raw_item_name) for occurrence in extraction.occurrences
        }
        items_by_name = self._catalog.find_active_by_normalized_names(normalized_names)
        unique_items = {
            candidates[0].id: candidates[0]
            for candidates in items_by_name.values()
            if len(candidates) == 1
        }
        latest_recipes = self._catalog.latest_recipes_for_item_ids(set(unique_items))

        rows: list[CapturePlanRow | None] = [None] * len(extraction.occurrences)
        resolved: list[_ResolvedOccurrence] = []
        for index, occurrence in enumerate(extraction.occurrences):
            normalized_name = normalize_item_name(occurrence.raw_item_name)
            candidates = items_by_name.get(normalized_name, [])
            if not candidates:
                issue = f"row {occurrence.row_number}: no exact active catalog item"
                issues.append(issue)
                rows[index] = _row(
                    occurrence,
                    normalized_name,
                    disposition="error",
                    detail=issue,
                )
                continue
            if len(candidates) != 1:
                issue = f"row {occurrence.row_number}: exact item name is ambiguous"
                issues.append(issue)
                rows[index] = _row(
                    occurrence,
                    normalized_name,
                    disposition="error",
                    detail=issue,
                )
                continue
            item = candidates[0]
            recipe = latest_recipes.get(item.id)
            if recipe is None or recipe.profession not in self._approved_professions:
                detail = (
                    "out of scope: no latest recipe"
                    if recipe is None
                    else f"out of scope profession: {recipe.profession}"
                )
                rows[index] = _row(
                    occurrence,
                    normalized_name,
                    item=item,
                    recipe=recipe,
                    disposition="out_of_scope",
                    detail=detail,
                )
                continue
            resolved.append(
                _ResolvedOccurrence(
                    occurrence=occurrence,
                    row_index=index,
                    item=item,
                    recipe=recipe,
                )
            )

        active = self._sales.active_for_item_ids({value.item.id for value in resolved})
        changes: list[CapturePlanChange] = []
        if action == CaptureAction.SOLD:
            self._plan_sold(resolved, active, rows, changes, issues, observed_at)
        else:
            self._plan_market(resolved, active, rows, changes, issues)

        finalized_rows = tuple(row for row in rows if row is not None)
        if len(finalized_rows) != len(extraction.occurrences):  # pragma: no cover - invariant
            raise RuntimeError("capture planner did not classify every occurrence")
        return CapturePlan(
            requested_action=action,
            screen_kind=extraction.screen_kind,
            observed_at=_as_utc(observed_at),
            rows=finalized_rows,
            changes=tuple(changes),
            issues=tuple(dict.fromkeys(issues)),
        )

    def commit_batch(
        self,
        batch_uuid: UUID,
        *,
        database_path: Path,
        backup_directory: Path,
        now: datetime,
        backup_creator: Callable[..., Path] = create_integrity_checked_backup,
    ) -> CaptureCommitResult:
        self._session.rollback()
        backup_path: Path | None = None
        with self._session.begin():
            capture_repository = SaleCaptureRepository(self._session)
            batch = capture_repository.get_by_uuid(batch_uuid)
            if batch is None:
                raise CaptureStateConflict(f"unknown capture batch: {batch_uuid}")
            if batch.status != "committing":
                raise CaptureStateConflict(f"capture batch must be committing, not {batch.status}")
            if batch.requested_action is None or batch.extraction_json is None:
                raise CaptureStateConflict("capture batch lacks an action or extraction")

            action = CaptureAction(batch.requested_action)
            extraction = CaptureExtraction.model_validate_json(batch.extraction_json)
            plan = self.plan(action, extraction, observed_at=batch.observed_at)
            batch.validation_json = plan.model_dump_json()
            batch.lease_expires_at = None
            if not plan.can_commit:
                batch.status = "needs_review"
                batch.receipt_status = "pending"
                return CaptureCommitResult(plan=plan, backup_path=None)

            if plan.changes:
                backup_path = backup_creator(
                    database_path,
                    backup_directory,
                    label=f"before-slack-{action.value}-{batch.uuid}",
                    now=_as_utc(now),
                )
                self._apply_changes(batch, plan)
            batch.status = "committed"
            batch.completed_at = _as_utc(now)
            batch.receipt_status = "pending"
        return CaptureCommitResult(plan=plan, backup_path=backup_path)

    def _plan_sold(
        self,
        resolved: list[_ResolvedOccurrence],
        active: list[SaleListing],
        rows: list[CapturePlanRow | None],
        changes: list[CapturePlanChange],
        issues: list[str],
        observed_at: datetime,
    ) -> None:
        candidates: dict[tuple[int, int], deque[SaleListing]] = defaultdict(deque)
        for listing in active:
            if listing.asking_price is not None:
                candidates[(listing.item_id, listing.asking_price)].append(listing)
        resolved_observed_at = _as_utc(observed_at)
        for value in resolved:
            occurrence = value.occurrence
            normalized_name = normalize_item_name(occurrence.raw_item_name)
            listing_candidates = candidates[(value.item.id, occurrence.displayed_price_kamas)]
            if not listing_candidates:
                issue = f"row {occurrence.row_number}: no active exact item-and-price listing"
                issues.append(issue)
                rows[value.row_index] = _row(
                    occurrence,
                    normalized_name,
                    item=value.item,
                    recipe=value.recipe,
                    disposition="error",
                    detail=issue,
                )
                continue
            listing = listing_candidates.popleft()
            if resolved_observed_at < _as_utc(listing.selling_started_at):
                issue = f"row {occurrence.row_number}: sale time is before listing start"
                issues.append(issue)
                rows[value.row_index] = _row(
                    occurrence,
                    normalized_name,
                    item=value.item,
                    recipe=value.recipe,
                    disposition="error",
                    detail=issue,
                )
                continue
            rows[value.row_index] = _row(
                occurrence,
                normalized_name,
                item=value.item,
                recipe=value.recipe,
                disposition="actionable",
                detail="mark oldest exact active listing sold",
            )
            changes.append(
                CapturePlanChange(
                    action="marked_sold",
                    item_uuid=value.item.uuid,
                    display_name=value.item.display_name,
                    asking_price=occurrence.displayed_price_kamas,
                    listing_uuid=listing.uuid,
                )
            )

    def _plan_market(
        self,
        resolved: list[_ResolvedOccurrence],
        active: list[SaleListing],
        rows: list[CapturePlanRow | None],
        changes: list[CapturePlanChange],
        issues: list[str],
    ) -> None:
        visible_prices_by_item: dict[int, set[int]] = defaultdict(set)
        grouped: dict[tuple[int, int], list[_ResolvedOccurrence]] = defaultdict(list)
        for value in resolved:
            price = value.occurrence.displayed_price_kamas
            visible_prices_by_item[value.item.id].add(price)
            grouped[(value.item.id, price)].append(value)

        active_by_key: dict[tuple[int, int], list[SaleListing]] = defaultdict(list)
        conflicting_item_ids: set[int] = set()
        for listing in active:
            price = listing.asking_price
            if price is not None:
                active_by_key[(listing.item_id, price)].append(listing)
            if price not in visible_prices_by_item.get(listing.item_id, set()):
                conflicting_item_ids.add(listing.item_id)

        for item_id in sorted(conflicting_item_ids):
            item = next(value.item for value in resolved if value.item.id == item_id)
            issues.append(
                f"{item.display_name}: Web UI has a different active price requiring review"
            )

        for key, occurrences in grouped.items():
            item_id, price = key
            has_conflict = item_id in conflicting_item_ids
            exact_count = len(active_by_key[key])
            for occurrence_index, value in enumerate(occurrences):
                occurrence = value.occurrence
                normalized_name = normalize_item_name(occurrence.raw_item_name)
                if has_conflict:
                    rows[value.row_index] = _row(
                        occurrence,
                        normalized_name,
                        item=value.item,
                        recipe=value.recipe,
                        disposition="error",
                        detail="different active Web UI price requires review",
                    )
                elif occurrence_index < exact_count:
                    rows[value.row_index] = _row(
                        occurrence,
                        normalized_name,
                        item=value.item,
                        recipe=value.recipe,
                        disposition="already_present",
                        detail="exact active listing already exists",
                    )
                else:
                    rows[value.row_index] = _row(
                        occurrence,
                        normalized_name,
                        item=value.item,
                        recipe=value.recipe,
                        disposition="actionable",
                        detail="create missing exact active listing",
                    )
                    changes.append(
                        CapturePlanChange(
                            action="created",
                            item_uuid=value.item.uuid,
                            display_name=value.item.display_name,
                            asking_price=price,
                        )
                    )

    def _apply_changes(self, batch, plan: CapturePlan) -> None:
        sales_service = SalesService(self._session, self._market_context)
        if plan.requested_action == CaptureAction.MARKET:
            listings = sales_service.create_listings_at(
                [
                    SaleListingCreate(
                        item_uuid=change.item_uuid,
                        asking_price=change.asking_price,
                    )
                    for change in plan.changes
                ],
                selling_started_at=plan.observed_at,
                source="slack_market_capture",
                capture_uuid=batch.uuid,
            )
        else:
            listing_uuids = [
                change.listing_uuid for change in plan.changes if change.listing_uuid is not None
            ]
            if len(listing_uuids) != len(plan.changes):  # pragma: no cover - plan invariant
                raise RuntimeError("sold capture change lacks a listing UUID")
            listings = sales_service.mark_listings_sold_at(
                listing_uuids,
                sold_at=plan.observed_at,
                source="slack_sold_capture",
                capture_uuid=batch.uuid,
            )

        for listing, change in zip(listings, plan.changes, strict=True):
            self._session.add(
                SaleCaptureListingAction(
                    capture_batch=batch,
                    sale_listing=listing,
                    action=change.action,
                    effective_at=plan.observed_at,
                    asking_price=change.asking_price,
                )
            )
        self._session.flush()


def _row(
    occurrence: CaptureOccurrence,
    normalized_name: str,
    *,
    disposition: str,
    detail: str,
    item: Item | None = None,
    recipe: Recipe | None = None,
) -> CapturePlanRow:
    return CapturePlanRow(
        image_number=occurrence.image_number,
        row_number=occurrence.row_number,
        raw_item_name=occurrence.raw_item_name,
        normalized_name=normalized_name,
        displayed_price_kamas=occurrence.displayed_price_kamas,
        display_name=None if item is None else item.display_name,
        profession=None if recipe is None else recipe.profession,
        disposition=disposition,
        detail=detail,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
