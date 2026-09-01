from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import UUID

from PIL import Image
from sqlalchemy import func, select

from dofus_touch_economy.capture_config import CaptureWorkerSettings
from dofus_touch_economy.capture_schemas import (
    CaptureAction,
    CaptureExtraction,
    CaptureOccurrence,
    CapturePlan,
    CapturePlanChange,
    CapturePlanRow,
    ScreenKind,
)
from dofus_touch_economy.capture_vision import VisionExtractionResult
from dofus_touch_economy.models import (
    ImportBatch,
    Item,
    Recipe,
    SaleCaptureBatch,
    SaleCaptureListingAction,
    SaleListing,
    SourceRecord,
)
from dofus_touch_economy.normalization import normalize_item_name
from dofus_touch_economy.slack_sales_worker import SlackSalesCaptureWorker

OBSERVED_AT = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)
MESSAGE_TS = f"{OBSERVED_AT.timestamp():.6f}"


class _FakeSlackClient:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.updates: list[dict[str, object]] = []
        self.history_pages: list[dict[str, object]] = []
        self.file_urls: dict[str, str] = {}

    def chat_postMessage(self, **kwargs):
        self.messages.append(kwargs)
        return {"ok": True, "ts": f"receipt-{len(self.messages)}"}

    def chat_update(self, **kwargs):
        self.updates.append(kwargs)
        return {"ok": True, "ts": kwargs["ts"]}

    def files_info(self, *, file: str):
        return {"ok": True, "file": {"url_private_download": self.file_urls[file]}}

    def conversations_history(self, **_kwargs):
        return self.history_pages.pop(0)


class _FakeVision:
    def __init__(self, extraction: CaptureExtraction) -> None:
        self.extraction = extraction
        self.calls = 0

    def extract(self, _action, _images, *, verification: bool = False):
        self.calls += 1
        return VisionExtractionResult(
            extraction=self.extraction,
            response_id=f"resp-{self.calls}",
            model="gpt-5.6-terra-test",
            prompt_version=("verify-v1" if verification else "primary-v1"),
        )


def _settings(tmp_path: Path, session_factory) -> CaptureWorkerSettings:
    database_path = Path(session_factory.kw["bind"].url.database)
    return CaptureWorkerSettings(
        project_root=tmp_path,
        database_path=database_path,
        market_context="Dodge",
        evidence_path=tmp_path / "evidence",
        slack_bot_token="bot-secret",
        slack_app_token="app-secret",
        slack_workspace_id="T123",
        slack_channel_id="C123",
        slack_owner_user_id="U123",
        approved_professions=("Tailor", "Shoemaker", "Jeweller"),
    )


def _event(*, action: str = "sold", user: str = "U123") -> tuple[dict, dict]:
    return (
        {"team_id": "T123", "event_id": "Ev123"},
        {
            "type": "message",
            "channel": "C123",
            "user": user,
            "ts": MESSAGE_TS,
            "text": action,
            "files": [
                {
                    "id": "F1",
                    "mimetype": "image/png",
                    "size": 100,
                }
            ],
        },
    )


def _craftable_item(session, name: str = "Synthetic Hat") -> Item:
    item = Item(
        display_name=name,
        normalized_name=normalize_item_name(name),
        category="Hat",
        identity_category="hat",
    )
    batch = ImportBatch(
        dataset="worker-recipe",
        filename="synthetic.csv",
        checksum="a" * 64,
        accepted_count=1,
        rejected_count=0,
        warning_count=0,
        status="succeeded",
    )
    record = SourceRecord(
        import_batch=batch,
        row_number=1,
        raw_payload_json="{}",
        status="accepted",
        validation_messages_json="[]",
    )
    recipe = Recipe(
        crafted_item=item,
        profession="Tailor",
        source_record=record,
        created_at=OBSERVED_AT - timedelta(days=2),
    )
    session.add_all([item, batch, recipe])
    session.flush()
    return item


def _sold_extraction() -> CaptureExtraction:
    return CaptureExtraction(
        screen_kind=ScreenKind.SOLD_NOTIFICATION,
        occurrences=(
            CaptureOccurrence(
                raw_item_name="Synthetic Hat",
                displayed_price_kamas=47_000,
                image_number=1,
                row_number=1,
            ),
        ),
    )


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _mark_file_downloaded(session, batch_uuid: UUID, root: Path) -> None:
    batch = session.scalar(select(SaleCaptureBatch).where(SaleCaptureBatch.uuid == batch_uuid))
    assert batch is not None
    file = batch.files[0]
    capture_directory = root / str(batch.uuid)
    capture_directory.mkdir(parents=True, exist_ok=True)
    path = capture_directory / "01-synthetic.png"
    path.write_bytes(b"synthetic")
    file.local_relative_path = path.relative_to(root).as_posix()
    file.sha256 = "a" * 64
    file.status = "downloaded"
    file.downloaded_at = OBSERVED_AT
    session.commit()


def test_authorized_top_level_event_is_durable_before_ack_and_idempotent(
    session_factory,
    tmp_path: Path,
) -> None:
    slack = _FakeSlackClient()
    worker = SlackSalesCaptureWorker(
        _settings(tmp_path, session_factory),
        session_factory,
        slack,
        _FakeVision(_sold_extraction()),
    )
    body, event = _event()
    acknowledgements: list[str] = []

    worker.intake_event(body, event, lambda: acknowledgements.append("acked"))
    worker.intake_event(body, event, lambda: acknowledgements.append("acked-again"))

    with session_factory() as session:
        batches = list(session.scalars(select(SaleCaptureBatch)))
        assert len(batches) == 1
        assert batches[0].status == "queued"
        assert batches[0].requested_action == "sold"
        assert [file.provider_file_id for file in batches[0].files] == ["F1"]
    assert acknowledgements == ["acked", "acked-again"]
    assert slack.messages == []


def test_unauthorized_thread_and_bot_messages_are_ignored(session_factory, tmp_path: Path) -> None:
    worker = SlackSalesCaptureWorker(
        _settings(tmp_path, session_factory),
        session_factory,
        _FakeSlackClient(),
        _FakeVision(_sold_extraction()),
    )
    body, unauthorized = _event(user="U999")
    _, threaded = _event()
    threaded["thread_ts"] = "parent"
    _, bot = _event()
    bot["bot_id"] = "B123"

    worker.intake_event(body, unauthorized, lambda: None)
    worker.intake_event(body, threaded, lambda: None)
    worker.intake_event(body, bot, lambda: None)

    with session_factory() as session:
        assert session.scalar(select(func.count(SaleCaptureBatch.id))) == 0


def test_missing_caption_requires_owner_action_selection(session_factory, tmp_path: Path) -> None:
    slack = _FakeSlackClient()
    worker = SlackSalesCaptureWorker(
        _settings(tmp_path, session_factory),
        session_factory,
        slack,
        _FakeVision(_sold_extraction()),
    )
    body, event = _event(action="please process")
    worker.intake_event(body, event, lambda: None)
    worker.send_one_receipt()
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        assert batch.status == "awaiting_action"
        batch_uuid = batch.uuid

    assert slack.messages
    assert worker.choose_action(batch_uuid, user_id="U999", action="sold") is False
    assert worker.choose_action(batch_uuid, user_id="U123", action="sold") is True
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        assert batch.status == "queued"
        assert batch.requested_action == "sold"


def test_sold_capture_previews_then_commits_only_after_owner_confirmation(
    session_factory,
    tmp_path: Path,
) -> None:
    with session_factory() as session:
        item = _craftable_item(session)
        session.add(
            SaleListing(
                item=item,
                lot_quantity=1,
                asking_price=47_000,
                selling_started_at=OBSERVED_AT - timedelta(days=1),
            )
        )
        session.commit()
    slack = _FakeSlackClient()
    vision = _FakeVision(_sold_extraction())
    settings = _settings(tmp_path, session_factory)
    worker = SlackSalesCaptureWorker(settings, session_factory, slack, vision)
    body, event = _event()
    worker.intake_event(body, event, lambda: None)
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        batch_uuid = batch.uuid
        _mark_file_downloaded(session, batch_uuid, settings.evidence_path)

    assert worker.process_once()
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        listing = session.scalar(select(SaleListing))
        assert batch is not None
        assert batch.status == "awaiting_confirmation"
        assert batch.preview_message_ts == "receipt-1"
        assert listing is not None
        assert listing.date_sold is None
    assert slack.messages
    assert any(block["type"] == "actions" for block in slack.messages[-1]["blocks"])
    assert "Synthetic Hat" in str(slack.messages[-1])
    assert "47,000" in str(slack.messages[-1])
    assert worker.decide(batch_uuid, user_id="U999", approve=True) is False
    assert worker.decide(batch_uuid, user_id="U123", approve=True) is True
    assert "processing capture" in str(slack.updates[-1])
    assert all(block["type"] != "actions" for block in slack.updates[-1]["blocks"])

    assert worker.process_once()
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        listing = session.scalar(select(SaleListing))
        assert batch is not None
        assert batch.status == "committed"
        assert listing is not None
        assert listing.date_sold is not None
        assert listing.sale_source == "slack_sold_capture"
    assert len(slack.messages) == 1
    assert "Sold capture committed" in str(slack.updates[-1])
    assert all(block["type"] != "actions" for block in slack.updates[-1]["blocks"])
    assert list((tmp_path / "data/app/backups").glob("*.sqlite3"))


def test_committed_sold_receipt_reports_financial_coverage_stockouts_and_scope(
    session_factory,
    tmp_path: Path,
) -> None:
    with session_factory() as session:
        stockout_item = Item(
            display_name="Daggero's Red Necklace",
            normalized_name="daggero's red necklace",
            category="Amulet",
            identity_category="amulet",
        )
        remaining_item = Item(
            display_name="Synthetic Boots",
            normalized_name="synthetic boots",
            category="Boots",
            identity_category="boots",
        )
        sold_with_cost = SaleListing(
            item=stockout_item,
            lot_quantity=1,
            asking_price=47_000,
            selling_started_at=OBSERVED_AT - timedelta(days=2),
            date_sold=OBSERVED_AT,
            recipe_cost_at_sale=Decimal("12000"),
        )
        sold_without_cost = SaleListing(
            item=remaining_item,
            lot_quantity=1,
            asking_price=53_000,
            selling_started_at=OBSERVED_AT - timedelta(days=2),
            date_sold=OBSERVED_AT,
        )
        active_listing = SaleListing(
            item=remaining_item,
            lot_quantity=1,
            asking_price=55_000,
            selling_started_at=OBSERVED_AT - timedelta(days=1),
        )
        session.add_all((sold_with_cost, sold_without_cost, active_listing))
        session.flush()
        plan = CapturePlan(
            requested_action=CaptureAction.SOLD,
            screen_kind=ScreenKind.SOLD_NOTIFICATION,
            observed_at=OBSERVED_AT,
            rows=(
                CapturePlanRow(
                    image_number=1,
                    row_number=1,
                    raw_item_name=stockout_item.display_name,
                    normalized_name=stockout_item.normalized_name,
                    displayed_price_kamas=47_000,
                    display_name=stockout_item.display_name,
                    profession="Jeweller",
                    disposition="actionable",
                    detail="mark oldest exact active listing sold",
                ),
                CapturePlanRow(
                    image_number=1,
                    row_number=2,
                    raw_item_name=remaining_item.display_name,
                    normalized_name=remaining_item.normalized_name,
                    displayed_price_kamas=53_000,
                    display_name=remaining_item.display_name,
                    profession="Shoemaker",
                    disposition="actionable",
                    detail="mark oldest exact active listing sold",
                ),
                CapturePlanRow(
                    image_number=1,
                    row_number=3,
                    raw_item_name="Water Larva",
                    normalized_name="water larva",
                    displayed_price_kamas=1,
                    disposition="out_of_scope",
                    detail="out of scope: no latest recipe",
                ),
                CapturePlanRow(
                    image_number=1,
                    row_number=4,
                    raw_item_name="Water Larva",
                    normalized_name="water larva",
                    displayed_price_kamas=1,
                    disposition="out_of_scope",
                    detail="out of scope: no latest recipe",
                ),
            ),
            changes=(
                CapturePlanChange(
                    action="marked_sold",
                    item_uuid=stockout_item.uuid,
                    display_name=stockout_item.display_name,
                    asking_price=47_000,
                    listing_uuid=sold_with_cost.uuid,
                ),
                CapturePlanChange(
                    action="marked_sold",
                    item_uuid=remaining_item.uuid,
                    display_name=remaining_item.display_name,
                    asking_price=53_000,
                    listing_uuid=sold_without_cost.uuid,
                ),
            ),
            issues=(),
        )
        batch = SaleCaptureBatch(
            workspace_id="T123",
            channel_id="C123",
            parent_message_ts=MESSAGE_TS,
            requester_user_id="U123",
            requested_action="sold",
            status="committed",
            observed_at=OBSERVED_AT,
            completed_at=OBSERVED_AT + timedelta(minutes=1),
            validation_json=plan.model_dump_json(),
            receipt_status="pending",
        )
        batch.listing_actions.extend(
            (
                SaleCaptureListingAction(
                    sale_listing=sold_with_cost,
                    action="marked_sold",
                    effective_at=OBSERVED_AT,
                    asking_price=47_000,
                ),
                SaleCaptureListingAction(
                    sale_listing=sold_without_cost,
                    action="marked_sold",
                    effective_at=OBSERVED_AT,
                    asking_price=53_000,
                ),
            )
        )
        session.add(batch)
        session.commit()

    slack = _FakeSlackClient()
    worker = SlackSalesCaptureWorker(
        _settings(tmp_path, session_factory),
        session_factory,
        slack,
        _FakeVision(_sold_extraction()),
    )

    assert worker.send_one_receipt()

    receipt = str(slack.messages[-1]["text"])
    assert "*Sold capture committed* — 2 listings sold" in receipt
    assert "Total recorded sales revenue: 100,000 kama" in receipt
    assert "Total known cost: 12,000 kama" in receipt
    assert "Total known profit: 35,000 kama" in receipt
    assert "Cost coverage: 1 of 2 sold listings" in receipt
    assert "Newly out of stock: 1 item — Daggero's Red Necklace" in receipt
    assert "Daggero&#x27;s" not in receipt
    assert "Out of scope: 2 screenshot rows excluded — Water Larva ×2" in receipt
    assert all(block["type"] != "actions" for block in slack.messages[-1]["blocks"])


def test_reject_replaces_preview_without_interactive_buttons(
    session_factory,
    tmp_path: Path,
) -> None:
    with session_factory() as session:
        item = _craftable_item(session)
        session.add(
            SaleListing(
                item=item,
                lot_quantity=1,
                asking_price=47_000,
                selling_started_at=OBSERVED_AT - timedelta(days=1),
            )
        )
        session.commit()
    slack = _FakeSlackClient()
    settings = _settings(tmp_path, session_factory)
    worker = SlackSalesCaptureWorker(
        settings,
        session_factory,
        slack,
        _FakeVision(_sold_extraction()),
    )
    body, event = _event()
    worker.intake_event(body, event, lambda: None)
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        batch_uuid = batch.uuid
        _mark_file_downloaded(session, batch_uuid, settings.evidence_path)

    assert worker.process_once()
    assert worker.decide(batch_uuid, user_id="U123", approve=False) is True

    assert "rejected" in str(slack.updates[-1])
    assert all(block["type"] != "actions" for block in slack.updates[-1]["blocks"])
    assert worker.process_once()
    assert len(slack.messages) == 1
    assert "rejected" in str(slack.updates[-1])
    assert all(block["type"] != "actions" for block in slack.updates[-1]["blocks"])


def test_market_capture_is_review_only_until_private_layout_is_validated(
    session_factory,
    tmp_path: Path,
) -> None:
    slack = _FakeSlackClient()
    vision = _FakeVision(
        CaptureExtraction(screen_kind=ScreenKind.OWN_MARKET_LISTINGS, occurrences=())
    )
    settings = _settings(tmp_path, session_factory)
    worker = SlackSalesCaptureWorker(settings, session_factory, slack, vision)
    body, event = _event(action="market")
    worker.intake_event(body, event, lambda: None)
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        batch_uuid = batch.uuid
        _mark_file_downloaded(session, batch_uuid, settings.evidence_path)

    assert worker.process_once()

    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        assert batch.status == "needs_review"
    assert batch.error_code == "market_layout_not_validated"
    assert vision.calls == 0


def test_invalid_later_attachment_keeps_prior_download_durably_tracked(
    session_factory,
    tmp_path: Path,
) -> None:
    slack = _FakeSlackClient()
    slack.file_urls = {"F1": "private://valid", "F2": "private://invalid"}
    settings = _settings(tmp_path, session_factory)
    worker = SlackSalesCaptureWorker(
        settings,
        session_factory,
        slack,
        _FakeVision(_sold_extraction()),
        file_downloader=lambda url, _token: (
            (_png_bytes(),) if url == "private://valid" else (b"not-an-image",)
        ),
    )
    body, event = _event()
    event["files"].append({"id": "F2", "mimetype": "image/png", "size": len(b"not-an-image")})
    worker.intake_event(body, event, lambda: None)

    assert worker.process_once()

    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        assert batch.status == "needs_review"
        assert [file.status for file in batch.files] == ["downloaded", "invalid"]
        assert batch.files[0].local_relative_path is not None
        assert (settings.evidence_path / batch.files[0].local_relative_path).is_file()


def test_evidence_retention_marks_only_deleted_old_terminal_files_as_purged(
    session_factory,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, session_factory)
    worker = SlackSalesCaptureWorker(
        settings,
        session_factory,
        _FakeSlackClient(),
        _FakeVision(_sold_extraction()),
    )
    body, event = _event()
    worker.intake_event(body, event, lambda: None)
    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        batch_uuid = batch.uuid
        _mark_file_downloaded(session, batch_uuid, settings.evidence_path)
        batch.status = "rejected"
        batch.completed_at = OBSERVED_AT - timedelta(days=91)
        session.commit()
        evidence_path = settings.evidence_path / batch.files[0].local_relative_path

    assert worker.purge_evidence(now=OBSERVED_AT) == 1

    with session_factory() as session:
        batch = session.scalar(select(SaleCaptureBatch))
        assert batch is not None
        assert batch.files[0].status == "purged"
        assert batch.files[0].purged_at is not None
    assert not evidence_path.exists()
