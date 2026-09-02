from __future__ import annotations

import html
import json
import logging
import time
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import URLError
from uuid import UUID

from slack_sdk.errors import SlackApiError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dofus_touch_economy.capture_config import CaptureWorkerSettings
from dofus_touch_economy.capture_evidence import (
    EvidenceStore,
    EvidenceValidationError,
    purge_expired_evidence,
)
from dofus_touch_economy.capture_schemas import (
    CaptureAction,
    CaptureFileInput,
    CaptureIntake,
    CapturePlan,
    requested_action_from_caption,
)
from dofus_touch_economy.capture_vision import (
    MARKET_LAYOUT_VALIDATED,
    CodexCliExecutionError,
    VisionAdapter,
    VisionImage,
    VisionResponseError,
    extractions_agree,
)
from dofus_touch_economy.models import SaleCaptureBatch, SaleListing
from dofus_touch_economy.repositories.sale_captures import SaleCaptureRepository
from dofus_touch_economy.services.sale_captures import SaleCaptureService

ACTION_CHOOSE_SOLD = "dofus_capture_choose_sold"
ACTION_CHOOSE_MARKET = "dofus_capture_choose_market"
ACTION_CONFIRM = "dofus_capture_confirm"
ACTION_REJECT = "dofus_capture_reject"
MAX_PROCESSING_ATTEMPTS = 5
LOGGER = logging.getLogger(__name__)

TransientWorkerErrors = (
    CodexCliExecutionError,
    SlackApiError,
    URLError,
)


class SlackSalesCaptureWorker:
    def __init__(
        self,
        settings: CaptureWorkerSettings,
        session_factory: sessionmaker[Session],
        slack_client: Any,
        vision_adapter: VisionAdapter,
        *,
        evidence_store: EvidenceStore | None = None,
        file_downloader: Callable[[str, str], Iterable[bytes]] | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._slack = slack_client
        self._vision = vision_adapter
        self._evidence = evidence_store or EvidenceStore(
            settings.evidence_path,
            maximum_image_bytes=settings.maximum_image_bytes,
        )
        self._file_downloader = file_downloader or _download_private_file

    def intake_event(
        self,
        body: dict[str, Any],
        event: dict[str, Any],
        ack: Callable[[], None],
    ) -> None:
        if not self._is_authorized_top_level_image(body, event):
            ack()
            return
        intake = self._intake_from_message(body, event)
        with self._session_factory() as session:
            batch, created = SaleCaptureRepository(session).get_or_create(intake)
            if created and batch.status == "awaiting_action":
                batch.receipt_status = "pending"
            session.commit()
        ack()

    def choose_action(
        self,
        batch_uuid: UUID,
        *,
        user_id: str,
        action: str,
    ) -> bool:
        if user_id != self._settings.slack_owner_user_id:
            return False
        if action not in (CaptureAction.SOLD, CaptureAction.MARKET):
            return False
        with self._session_factory() as session:
            changed = SaleCaptureRepository(session).set_requested_action(
                batch_uuid,
                action=str(action),
            )
            session.commit()
            return changed

    def decide(
        self,
        batch_uuid: UUID,
        *,
        user_id: str,
        approve: bool,
    ) -> bool:
        if user_id != self._settings.slack_owner_user_id:
            return False
        with self._session_factory() as session:
            changed = SaleCaptureRepository(session).decide(
                batch_uuid,
                owner_user_id=user_id,
                approve=approve,
                decided_at=datetime.now(UTC),
            )
            session.commit()
        if changed:
            self._replace_preview_actions(batch_uuid, approve=approve)
        return changed

    def process_once(self) -> bool:
        with self._session_factory() as session:
            committing = SaleCaptureRepository(session).next_committing()
            committing_uuid = None if committing is None else committing.uuid
        if committing_uuid is not None:
            self._commit_batch(committing_uuid)
            self.send_one_receipt()
            return True

        with self._session_factory() as session:
            repository = SaleCaptureRepository(session)
            batch = repository.claim_next(
                now=datetime.now(UTC),
                lease_for=timedelta(minutes=5),
            )
            if batch is None:
                return self.send_one_receipt()
            batch_uuid = batch.uuid
            session.commit()

        try:
            self._process_claimed(batch_uuid)
        except (EvidenceValidationError, VisionResponseError) as error:
            self._mark_review(batch_uuid, error_code=type(error).__name__)
        except TransientWorkerErrors as error:
            self._schedule_retry(batch_uuid, error_code=type(error).__name__)
        self._commit_if_ready(batch_uuid)
        self.send_one_receipt()
        return True

    def send_one_receipt(self) -> bool:
        with self._session_factory() as session:
            repository = SaleCaptureRepository(session)
            batch = repository.next_pending_receipt()
            if batch is None:
                return False
            batch_uuid = batch.uuid
            channel_id = batch.channel_id
            parent_message_ts = batch.parent_message_ts
            preview_message_ts = batch.preview_message_ts
            is_preview = batch.status == "awaiting_confirmation"
            active_item_ids = _active_item_ids_after_capture(session, batch)
            text, blocks = _receipt(batch, active_item_ids=active_item_ids)

        try:
            if preview_message_ts is not None and not is_preview:
                response = self._slack.chat_update(
                    channel=channel_id,
                    ts=preview_message_ts,
                    text=text,
                    blocks=blocks,
                )
            else:
                response = self._slack.chat_postMessage(
                    channel=channel_id,
                    thread_ts=parent_message_ts,
                    text=text,
                    blocks=blocks,
                )
            receipt_ts = str(response["ts"])
        except (SlackApiError, KeyError, TypeError):
            with self._session_factory() as session:
                SaleCaptureRepository(session).mark_receipt_retry(
                    batch_uuid,
                    failed=False,
                )
                session.commit()
            return False

        with self._session_factory() as session:
            SaleCaptureRepository(session).mark_receipt_sent(
                batch_uuid,
                receipt_ts,
                is_preview=is_preview,
            )
            session.commit()
        return True

    def _replace_preview_actions(self, batch_uuid: UUID, *, approve: bool) -> None:
        with self._session_factory() as session:
            batch = SaleCaptureRepository(session).get_by_uuid(batch_uuid)
            if batch is None or batch.preview_message_ts is None:
                return
            channel_id = batch.channel_id
            preview_message_ts = batch.preview_message_ts
        text = (
            "Confirmation received; processing capture."
            if approve
            else "Capture rejected; no Sales data changed."
        )
        try:
            self._slack.chat_update(
                channel=channel_id,
                ts=preview_message_ts,
                text=text,
                blocks=[_section(text)],
            )
        except (SlackApiError, TypeError):
            LOGGER.warning("could not remove capture preview actions after owner decision")

    def catch_up(self) -> int:
        with self._session_factory() as session:
            oldest = SaleCaptureRepository(session).latest_parent_message_ts()
        messages: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            arguments: dict[str, Any] = {
                "channel": self._settings.slack_channel_id,
                "limit": 200,
                "inclusive": True,
            }
            if oldest is not None:
                arguments["oldest"] = oldest
            if cursor:
                arguments["cursor"] = cursor
            response = self._slack.conversations_history(**arguments)
            messages.extend(response.get("messages", []))
            cursor = response.get("response_metadata", {}).get("next_cursor") or None
            if not cursor:
                break

        created_count = 0
        body = {"team_id": self._settings.slack_workspace_id, "event_id": None}
        for message in sorted(messages, key=lambda value: Decimal(str(value["ts"]))):
            before = self._batch_count()
            self.intake_event(body, message, lambda: None)
            created_count += int(self._batch_count() > before)
        return created_count

    def purge_evidence(self, *, now: datetime | None = None) -> int:
        purged_at = now or datetime.now(UTC)
        with self._session_factory() as session:
            repository = SaleCaptureRepository(session)
            records = repository.evidence_retention_candidates()
        purged_paths = purge_expired_evidence(
            self._settings.evidence_path,
            (record.candidate for record in records),
            now=purged_at,
            retention_days=self._settings.evidence_retention_days,
        )
        evidence_root = self._settings.evidence_path.resolve()
        purged_relative_paths = {
            path.relative_to(evidence_root).as_posix() for path in purged_paths
        }
        purged_file_ids = tuple(
            record.file_id
            for record in records
            if record.candidate.relative_path in purged_relative_paths
        )
        with self._session_factory() as session:
            purged_count = SaleCaptureRepository(session).mark_evidence_purged(
                purged_file_ids,
                purged_at=purged_at,
            )
            session.commit()
        return purged_count

    def _process_claimed(self, batch_uuid: UUID) -> None:
        with self._session_factory() as session:
            repository = SaleCaptureRepository(session)
            batch = repository.get_by_uuid(batch_uuid)
            if batch is None or batch.status != "extracting":
                return
            self._download_pending_files(session, batch)
            hashes = tuple(file.sha256 for file in batch.files if file.sha256 is not None)
            if len(hashes) != len(batch.files) or not hashes:
                raise EvidenceValidationError("capture does not have a complete image hash set")
            overlap = repository.hash_overlap(batch.id, hashes)
            if overlap == "exact":
                batch.status = "committed"
                batch.completed_at = datetime.now(UTC)
                batch.validation_json = json.dumps(
                    {"result": "duplicate_noop"}, separators=(",", ":")
                )
                batch.receipt_status = "pending"
                batch.lease_expires_at = None
                session.commit()
                return
            if overlap == "partial":
                batch.status = "needs_review"
                batch.error_code = "partial_duplicate"
                batch.error_message = "Some, but not all, image hashes overlap a prior batch."
                batch.receipt_status = "pending"
                batch.lease_expires_at = None
                session.commit()
                return

            action = CaptureAction(batch.requested_action)
            if action == CaptureAction.MARKET and not MARKET_LAYOUT_VALIDATED:
                batch.status = "needs_review"
                batch.error_code = "market_layout_not_validated"
                batch.error_message = (
                    "A private labeled marketplace screenshot is required before live extraction."
                )
                batch.receipt_status = "pending"
                batch.lease_expires_at = None
                session.commit()
                return

            images = tuple(
                VisionImage(
                    path=self._resolved_evidence_path(file.local_relative_path),
                    mime_type=file.mime_type,
                    image_number=file.attachment_order,
                )
                for file in batch.files
                if file.local_relative_path is not None
            )
            primary = self._vision.extract(action, images)
            batch.model = primary.model
            batch.prompt_version = primary.prompt_version
            batch.schema_version = "capture-extraction-v1"
            batch.primary_response_id = primary.response_id
            batch.extraction_json = primary.extraction.model_dump_json()

            plan = SaleCaptureService(
                session,
                self._settings.market_context,
                approved_professions=self._settings.approved_professions,
            ).plan(action, primary.extraction, observed_at=batch.observed_at)
            batch.validation_json = plan.model_dump_json()
            if not plan.can_commit:
                batch.status = "needs_review"
                batch.receipt_status = "pending"
                batch.lease_expires_at = None
                session.commit()
                return

            auto_commit = (
                self._settings.sold_auto_commit
                if action == CaptureAction.SOLD
                else self._settings.market_auto_commit
            )
            if auto_commit:
                verification = self._vision.extract(action, images, verification=True)
                batch.verification_prompt_version = verification.prompt_version
                batch.verification_response_id = verification.response_id
                batch.verification_json = verification.extraction.model_dump_json()
                if not extractions_agree(primary.extraction, verification.extraction):
                    batch.status = "needs_review"
                    batch.error_code = "verification_disagreement"
                    batch.error_message = "Independent extraction did not agree exactly."
                    batch.receipt_status = "pending"
                else:
                    batch.status = "committing"
            else:
                batch.status = "awaiting_confirmation"
                batch.receipt_status = "pending"
            batch.lease_expires_at = None
            session.commit()

    def _resolved_evidence_path(self, relative_path: str | None) -> Path:
        if relative_path is None:
            raise EvidenceValidationError("capture file has no local evidence path")
        evidence_root = self._settings.evidence_path.resolve()
        path = (evidence_root / relative_path).resolve()
        if not path.is_relative_to(evidence_root):
            raise EvidenceValidationError("evidence path escapes the configured root")
        return path

    def _download_pending_files(self, session: Session, batch) -> None:
        for file in batch.files:
            if file.status == "downloaded":
                continue
            response = self._slack.files_info(file=file.provider_file_id)
            private_url = str(response["file"]["url_private_download"])
            try:
                stored = self._evidence.store(
                    capture_uuid=batch.uuid,
                    attachment_order=file.attachment_order,
                    declared_mime_type=file.mime_type,
                    chunks=self._file_downloader(
                        private_url,
                        self._settings.slack_bot_token,
                    ),
                )
            except EvidenceValidationError:
                file.status = "invalid"
                session.commit()
                raise
            file.sha256 = stored.sha256
            file.byte_size = stored.byte_size
            file.mime_type = stored.mime_type
            file.local_relative_path = stored.relative_path
            file.status = "downloaded"
            file.downloaded_at = datetime.now(UTC)
            session.commit()

    def _commit_if_ready(self, batch_uuid: UUID) -> None:
        with self._session_factory() as session:
            batch = SaleCaptureRepository(session).get_by_uuid(batch_uuid)
            ready = batch is not None and batch.status == "committing"
        if ready:
            self._commit_batch(batch_uuid)

    def _commit_batch(self, batch_uuid: UUID) -> None:
        with self._session_factory() as session:
            SaleCaptureService(
                session,
                self._settings.market_context,
                approved_professions=self._settings.approved_professions,
            ).commit_batch(
                batch_uuid,
                database_path=self._settings.database_path,
                backup_directory=self._settings.project_root / "data/app/backups",
                now=datetime.now(UTC),
            )

    def _mark_review(self, batch_uuid: UUID, *, error_code: str) -> None:
        with self._session_factory() as session:
            SaleCaptureRepository(session).transition(
                batch_uuid,
                from_statuses=("extracting",),
                to_status="needs_review",
                values={
                    "error_code": error_code,
                    "error_message": "Capture input requires owner review.",
                    "receipt_status": "pending",
                },
            )
            session.commit()

    def _schedule_retry(self, batch_uuid: UUID, *, error_code: str) -> None:
        with self._session_factory() as session:
            repository = SaleCaptureRepository(session)
            batch = repository.get_by_uuid(batch_uuid)
            if batch is None or batch.status != "extracting":
                return
            failed = batch.attempt_count >= MAX_PROCESSING_ATTEMPTS
            delay_seconds = min(2**batch.attempt_count, 300)
            batch.status = "failed" if failed else "retry_wait"
            batch.next_attempt_at = (
                None if failed else datetime.now(UTC) + timedelta(seconds=delay_seconds)
            )
            batch.lease_expires_at = None
            batch.error_code = error_code
            batch.error_message = "Transient provider operation failed."
            if failed:
                batch.completed_at = datetime.now(UTC)
                batch.receipt_status = "pending"
            session.commit()

    def _is_authorized_top_level_image(
        self,
        body: dict[str, Any],
        event: dict[str, Any],
    ) -> bool:
        if body.get("team_id") != self._settings.slack_workspace_id:
            return False
        if event.get("channel") != self._settings.slack_channel_id:
            return False
        if event.get("user") != self._settings.slack_owner_user_id:
            return False
        if event.get("bot_id") or event.get("thread_ts"):
            return False
        if event.get("subtype") not in (None, "file_share"):
            return False
        files = event.get("files")
        return isinstance(files, list) and bool(files)

    def _intake_from_message(
        self,
        body: dict[str, Any],
        event: dict[str, Any],
    ) -> CaptureIntake:
        message_ts = str(event["ts"])
        try:
            observed_at = datetime.fromtimestamp(float(Decimal(message_ts)), UTC)
        except (InvalidOperation, ValueError) as error:
            raise ValueError("Slack message timestamp is invalid") from error
        caption = event.get("text")
        caption_value = None if caption is None else str(caption)
        requested_action = requested_action_from_caption(caption_value)
        files = tuple(
            CaptureFileInput(
                provider_file_id=str(file["id"]),
                mime_type=str(file.get("mimetype") or "application/octet-stream"),
                byte_size=int(file.get("size") or 0),
            )
            for file in event["files"]
        )
        return CaptureIntake(
            provider="slack",
            workspace_id=str(body["team_id"]),
            channel_id=str(event["channel"]),
            parent_message_ts=message_ts,
            event_id=None if body.get("event_id") is None else str(body["event_id"]),
            requester_user_id=str(event["user"]),
            caption=caption_value,
            requested_action=None if requested_action is None else requested_action.value,
            observed_at=observed_at,
            files=files,
        )

    def _batch_count(self) -> int:
        with self._session_factory() as session:
            from sqlalchemy import func, select

            from dofus_touch_economy.models import SaleCaptureBatch

            return int(session.scalar(select(func.count(SaleCaptureBatch.id))) or 0)


def _receipt(
    batch: SaleCaptureBatch,
    *,
    active_item_ids: frozenset[int] = frozenset(),
) -> tuple[str, list[dict[str, Any]]]:
    capture_uuid = str(batch.uuid)
    if batch.status == "awaiting_action":
        text = "Choose sold or market for this screenshot batch."
        return text, [
            _section(text),
            {
                "type": "actions",
                "elements": [
                    _button("Sold", ACTION_CHOOSE_SOLD, capture_uuid, style="primary"),
                    _button("Market", ACTION_CHOOSE_MARKET, capture_uuid),
                ],
            },
        ]
    if batch.status == "awaiting_confirmation" and batch.validation_json:
        plan = CapturePlan.model_validate_json(batch.validation_json)
        proposed_changes = iter(plan.changes)
        lines = [
            f"*{plan.requested_action.value.title()} preview* — "
            f"{len(plan.changes)} proposed change(s)"
        ]
        for row in plan.rows[:25]:
            name = html.escape(row.display_name or row.raw_item_name)
            price = f"{row.displayed_price_kamas:,}"
            disposition = row.disposition.replace("_", " ")
            if row.disposition == "actionable":
                change = next(proposed_changes)
                if change.action == "marked_sold" and (
                    change.previous_asking_price is not None
                    and change.previous_asking_price != change.asking_price
                ):
                    price = f"{change.previous_asking_price:,} → {change.asking_price:,}"
                    disposition = "reprice and mark sold"
            lines.append(f"• {name} — {price} — {html.escape(disposition)}")
        if len(plan.rows) > 25:
            lines.append(f"• … {len(plan.rows) - 25} more row(s)")
        text = "\n".join(lines)
        return text, [
            _section(text),
            {
                "type": "actions",
                "elements": [
                    _button("Confirm", ACTION_CONFIRM, capture_uuid, style="primary"),
                    _button("Reject", ACTION_REJECT, capture_uuid, style="danger"),
                ],
            },
        ]
    if batch.status == "committed" and batch.requested_action == CaptureAction.SOLD:
        return _sold_commit_receipt(batch, active_item_ids=active_item_ids)
    if batch.status == "committed":
        action_count = len(batch.listing_actions)
        text = f"Capture committed successfully: {action_count} listing change(s)."
    elif batch.status == "rejected":
        text = "Capture rejected; no Sales data changed."
    elif batch.status in ("needs_review", "failed"):
        text = "Capture needs review; no Sales data changed."
        if batch.error_code:
            text += f" Reason: {html.escape(batch.error_code)}."
    else:
        text = f"Capture status: {html.escape(batch.status)}."
    return text, [_section(text)]


def _active_item_ids_after_capture(
    session: Session,
    batch: SaleCaptureBatch,
) -> frozenset[int]:
    if batch.status != "committed" or batch.requested_action != CaptureAction.SOLD:
        return frozenset()
    affected_item_ids = {
        action.sale_listing.item_id
        for action in batch.listing_actions
        if action.action == "marked_sold"
    }
    if not affected_item_ids:
        return frozenset()
    return frozenset(
        session.scalars(
            select(SaleListing.item_id).where(
                SaleListing.item_id.in_(affected_item_ids),
                SaleListing.date_sold.is_(None),
            )
        )
    )


def _sold_commit_receipt(
    batch: SaleCaptureBatch,
    *,
    active_item_ids: frozenset[int],
) -> tuple[str, list[dict[str, Any]]]:
    actions = tuple(action for action in batch.listing_actions if action.action == "marked_sold")
    sold_count = len(actions)
    revenue = sum(action.asking_price for action in actions)
    costed_actions = tuple(
        action for action in actions if action.sale_listing.recipe_cost_at_sale is not None
    )
    total_cost = sum(
        (Decimal(action.sale_listing.recipe_cost_at_sale) for action in costed_actions),
        Decimal(0),
    )
    total_profit = sum(
        (
            Decimal(action.asking_price) - Decimal(action.sale_listing.recipe_cost_at_sale)
            for action in costed_actions
            if action.sale_listing.recipe_cost_at_sale is not None
        ),
        Decimal(0),
    )

    out_of_stock_items = {
        action.sale_listing.item_id: action.sale_listing.item.display_name
        for action in actions
        if action.sale_listing.item_id not in active_item_ids
    }
    out_of_scope_names: list[str] = []
    if batch.validation_json:
        plan = CapturePlan.model_validate_json(batch.validation_json)
        out_of_scope_names = [
            row.display_name or row.raw_item_name
            for row in plan.rows
            if row.disposition == "out_of_scope"
        ]

    sold_label = "listing" if sold_count == 1 else "listings"
    lines = [
        f"*Sold capture committed* — {sold_count} {sold_label} sold",
        f"• Total recorded sales revenue: {_format_kamas(revenue)} kama",
        "• Total known cost: " + (f"{_format_kamas(total_cost)} kama" if costed_actions else "—"),
        "• Total known profit: "
        + (f"{_format_kamas(total_profit)} kama" if costed_actions else "—"),
    ]
    if sold_count:
        coverage_label = "listing" if sold_count == 1 else "listings"
        lines.append(
            f"• Cost coverage: {len(costed_actions)} of {sold_count} sold {coverage_label}"
        )
    else:
        lines.append("• Cost coverage: not applicable (no listings sold)")

    out_of_stock_count = len(out_of_stock_items)
    out_of_stock_label = "item" if out_of_stock_count == 1 else "items"
    out_of_stock_line = f"• Newly out of stock: {out_of_stock_count} {out_of_stock_label}"
    if out_of_stock_items:
        out_of_stock_line += f" — {_summarize_names(out_of_stock_items.values())}"
    lines.append(out_of_stock_line)

    out_of_scope_count = len(out_of_scope_names)
    out_of_scope_label = "row" if out_of_scope_count == 1 else "rows"
    out_of_scope_line = (
        f"• Out of scope: {out_of_scope_count} screenshot {out_of_scope_label} excluded"
    )
    if out_of_scope_names:
        out_of_scope_line += f" — {_summarize_names(out_of_scope_names)}"
    lines.append(out_of_scope_line)

    text = "\n".join(lines)
    return text, [_section(text)]


def _format_kamas(value: int | Decimal) -> str:
    resolved = Decimal(value)
    if resolved == resolved.to_integral():
        return f"{int(resolved):,}"
    return f"{resolved.normalize():,f}"


def _summarize_names(names: Iterable[str], *, limit: int = 8) -> str:
    counts = Counter(name.strip() for name in names)
    entries: list[str] = []
    for name, count in sorted(counts.items(), key=lambda value: value[0].casefold())[:limit]:
        visible_name = name if len(name) <= 80 else f"{name[:79]}…"
        entry = _escape_slack_text(visible_name)
        if count > 1:
            entry += f" ×{count}"
        entries.append(entry)
    omitted_count = len(counts) - len(entries)
    if omitted_count:
        entries.append(f"… {omitted_count} more")
    return ", ".join(entries)


def _escape_slack_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _section(text: str) -> dict[str, Any]:
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": text[:3000]},
    }


def _button(
    text: str,
    action_id: str,
    value: str,
    *,
    style: str | None = None,
) -> dict[str, str]:
    button = {
        "type": "button",
        "text": {"type": "plain_text", "text": text},
        "action_id": action_id,
        "value": value,
    }
    if style is not None:
        button["style"] = style
    return button


def _download_private_file(url: str, token: str) -> Iterable[bytes]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        while chunk := response.read(64 * 1024):
            yield chunk


def build_bolt_app(
    settings: CaptureWorkerSettings,
    worker: SlackSalesCaptureWorker,
):
    from slack_bolt import App

    app = App(token=settings.slack_bot_token)

    @app.event("message")
    def handle_message(body, event, ack):
        worker.intake_event(body, event, ack)

    def action_payload(body) -> tuple[UUID | None, str]:
        user_id = str(body.get("user", {}).get("id", ""))
        try:
            batch_uuid = UUID(str(body["actions"][0]["value"]))
        except (KeyError, IndexError, TypeError, ValueError):
            batch_uuid = None
        return batch_uuid, user_id

    @app.action(ACTION_CHOOSE_SOLD)
    def choose_sold(body, ack):
        ack()
        batch_uuid, user_id = action_payload(body)
        if batch_uuid is not None:
            worker.choose_action(batch_uuid, user_id=user_id, action="sold")

    @app.action(ACTION_CHOOSE_MARKET)
    def choose_market(body, ack):
        ack()
        batch_uuid, user_id = action_payload(body)
        if batch_uuid is not None:
            worker.choose_action(batch_uuid, user_id=user_id, action="market")

    @app.action(ACTION_CONFIRM)
    def confirm(body, ack):
        ack()
        batch_uuid, user_id = action_payload(body)
        if batch_uuid is not None:
            worker.decide(batch_uuid, user_id=user_id, approve=True)

    @app.action(ACTION_REJECT)
    def reject(body, ack):
        ack()
        batch_uuid, user_id = action_payload(body)
        if batch_uuid is not None:
            worker.decide(batch_uuid, user_id=user_id, approve=False)

    return app


def run_processor_loop(
    worker: SlackSalesCaptureWorker,
    *,
    should_stop: Callable[[], bool],
    idle_seconds: float = 1.0,
) -> None:
    while not should_stop():
        try:
            did_work = worker.process_once()
        except Exception as error:  # pragma: no cover - process supervisor safeguard
            LOGGER.error("capture processor failed: %s", type(error).__name__)
            did_work = False
        if not did_work:
            time.sleep(idle_seconds)
