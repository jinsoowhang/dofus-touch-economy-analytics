from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from dofus_touch_economy.capture_schemas import (
    CaptureAction,
    CaptureExtraction,
    CaptureOccurrence,
    ScreenKind,
    requested_action_from_caption,
)
from dofus_touch_economy.models import (
    ImportBatch,
    Item,
    PriceObservation,
    Recipe,
    SaleCaptureBatch,
    SaleCaptureListingAction,
    SaleListing,
    SourceRecord,
)
from dofus_touch_economy.normalization import normalize_item_name
from dofus_touch_economy.schemas import SaleListingCreate
from dofus_touch_economy.services.sale_captures import SaleCaptureService
from dofus_touch_economy.services.sales import SalesService

OBSERVED_AT = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)


def _craftable_item(session, name: str, profession: str = "Tailor") -> Item:
    item = Item(
        display_name=name,
        normalized_name=normalize_item_name(name),
        category="Hat",
        identity_category=f"hat-{name.casefold()}",
    )
    batch = ImportBatch(
        dataset=f"recipe-{name}",
        filename="synthetic.csv",
        checksum=(name.encode().hex() + "0" * 64)[:64],
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
    Recipe(
        crafted_item=item,
        profession=profession,
        source_record=record,
        created_at=OBSERVED_AT - timedelta(days=1),
    )
    session.add_all([item, batch])
    session.flush()
    return item


def _extraction(
    screen_kind: ScreenKind,
    rows: list[tuple[str, int]],
    *,
    warnings: tuple[str, ...] = (),
) -> CaptureExtraction:
    return CaptureExtraction(
        screen_kind=screen_kind,
        occurrences=tuple(
            CaptureOccurrence(
                raw_item_name=name,
                displayed_price_kamas=price,
                image_number=1,
                row_number=index,
            )
            for index, (name, price) in enumerate(rows, start=1)
        ),
        warnings=warnings,
    )


def test_caption_action_is_explicit_and_never_inferred() -> None:
    assert requested_action_from_caption("sold\nnightly sales") == CaptureAction.SOLD
    assert requested_action_from_caption("  MARKET  ") == CaptureAction.MARKET
    assert requested_action_from_caption("please mark these sold") is None
    assert requested_action_from_caption(None) is None


def test_sold_plan_uses_oldest_exact_matches_and_reports_out_of_scope(session) -> None:
    item = _craftable_item(session, "Synthetic Hat")
    resource = Item(
        display_name="Synthetic Bark",
        normalized_name="synthetic bark",
        category="Resource",
        identity_category="resource",
    )
    session.add(resource)
    older = SaleListing(
        item=item,
        lot_quantity=1,
        asking_price=47_000,
        selling_started_at=OBSERVED_AT - timedelta(days=2),
    )
    newer = SaleListing(
        item=item,
        lot_quantity=1,
        asking_price=47_000,
        selling_started_at=OBSERVED_AT - timedelta(days=1),
    )
    session.add_all([newer, older])
    session.commit()

    plan = SaleCaptureService(
        session,
        "Dodge",
        approved_professions=("Tailor", "Shoemaker", "Jeweller"),
    ).plan(
        CaptureAction.SOLD,
        _extraction(
            ScreenKind.SOLD_NOTIFICATION,
            [
                ("Synthetic Hat", 47_000),
                ("Synthetic Hat", 47_000),
                ("Synthetic Bark", 1_517),
            ],
        ),
        observed_at=OBSERVED_AT,
    )

    assert plan.can_commit
    assert [change.listing_uuid for change in plan.changes] == [older.uuid, newer.uuid]
    assert [row.disposition for row in plan.rows] == [
        "actionable",
        "actionable",
        "out_of_scope",
    ]


def test_sold_plan_blocks_entire_batch_on_missing_exact_match_or_warning(session) -> None:
    _craftable_item(session, "Synthetic Hat")
    session.commit()

    plan = SaleCaptureService(session, "Dodge", approved_professions=("Tailor",)).plan(
        CaptureAction.SOLD,
        _extraction(
            ScreenKind.SOLD_NOTIFICATION,
            [("Synthetic Hat", 47_000)],
            warnings=("bottom row is partially visible",),
        ),
        observed_at=OBSERVED_AT,
    )

    assert not plan.can_commit
    assert plan.changes == ()
    assert any("no active exact" in issue for issue in plan.issues)
    assert any("partially visible" in issue for issue in plan.issues)


def test_market_plan_adds_only_missing_exact_occurrences(session) -> None:
    item = _craftable_item(session, "Synthetic Hat")
    session.add(
        SaleListing(
            item=item,
            lot_quantity=1,
            asking_price=50_000,
            selling_started_at=OBSERVED_AT - timedelta(days=1),
        )
    )
    session.commit()

    plan = SaleCaptureService(session, "Dodge", approved_professions=("Tailor",)).plan(
        CaptureAction.MARKET,
        _extraction(
            ScreenKind.OWN_MARKET_LISTINGS,
            [("Synthetic Hat", 50_000), ("Synthetic Hat", 50_000)],
        ),
        observed_at=OBSERVED_AT,
    )

    assert plan.can_commit
    assert [row.disposition for row in plan.rows] == ["already_present", "actionable"]
    assert len(plan.changes) == 1
    assert plan.changes[0].action == "created"
    assert plan.changes[0].item_uuid == item.uuid
    assert plan.changes[0].asking_price == 50_000


def test_market_plan_blocks_different_active_price_and_leaves_extras_alone(session) -> None:
    item = _craftable_item(session, "Synthetic Hat")
    session.add_all(
        [
            SaleListing(
                item=item,
                lot_quantity=1,
                asking_price=49_000,
                selling_started_at=OBSERVED_AT - timedelta(days=2),
            ),
            SaleListing(
                item=item,
                lot_quantity=1,
                asking_price=50_000,
                selling_started_at=OBSERVED_AT - timedelta(days=1),
            ),
        ]
    )
    session.commit()
    service = SaleCaptureService(session, "Dodge", approved_professions=("Tailor",))

    conflict = service.plan(
        CaptureAction.MARKET,
        _extraction(ScreenKind.OWN_MARKET_LISTINGS, [("Synthetic Hat", 50_000)]),
        observed_at=OBSERVED_AT,
    )
    all_prices_visible = service.plan(
        CaptureAction.MARKET,
        _extraction(
            ScreenKind.OWN_MARKET_LISTINGS,
            [("Synthetic Hat", 49_000), ("Synthetic Hat", 50_000)],
        ),
        observed_at=OBSERVED_AT,
    )

    assert not conflict.can_commit
    assert any("different active price" in issue for issue in conflict.issues)
    assert all_prices_visible.is_noop


def test_action_screen_mismatch_and_ambiguous_name_require_review(session) -> None:
    session.add_all(
        [
            Item(
                display_name="Twin Hat",
                normalized_name="twin hat",
                category="Hat",
                identity_category="hat-a",
            ),
            Item(
                display_name="Twin Hat",
                normalized_name="twin hat",
                category="Hat",
                identity_category="hat-b",
            ),
        ]
    )
    session.commit()

    plan = SaleCaptureService(session, "Dodge", approved_professions=("Tailor",)).plan(
        CaptureAction.SOLD,
        _extraction(ScreenKind.OWN_MARKET_LISTINGS, [("Twin Hat", 10_000)]),
        observed_at=OBSERVED_AT,
    )

    assert not plan.can_commit
    assert any("does not match" in issue for issue in plan.issues)
    assert any("ambiguous" in issue for issue in plan.issues)


def test_confirmed_market_batch_commits_listing_observation_action_and_receipt_state(
    session,
    tmp_path: Path,
) -> None:
    item = _craftable_item(session, "Synthetic Hat")
    extraction = _extraction(
        ScreenKind.OWN_MARKET_LISTINGS,
        [("Synthetic Hat", 50_000)],
    )
    batch = SaleCaptureBatch(
        workspace_id="T123",
        channel_id="C123",
        parent_message_ts="1788058800.000001",
        requester_user_id="U123",
        requested_action="market",
        status="committing",
        observed_at=OBSERVED_AT,
        extraction_json=extraction.model_dump_json(),
    )
    session.add(batch)
    session.commit()
    backup_path = tmp_path / "synthetic-backup.sqlite3"

    result = SaleCaptureService(
        session,
        "Dodge",
        approved_professions=("Tailor",),
    ).commit_batch(
        batch.uuid,
        database_path=tmp_path / "unused.sqlite3",
        backup_directory=tmp_path,
        now=OBSERVED_AT + timedelta(minutes=1),
        backup_creator=lambda *_args, **_kwargs: backup_path,
    )

    assert result.plan.can_commit
    assert result.backup_path == backup_path
    persisted_batch = session.get(SaleCaptureBatch, batch.id)
    assert persisted_batch is not None
    assert persisted_batch.status == "committed"
    assert persisted_batch.receipt_status == "pending"
    listing = session.scalar(select(SaleListing).where(SaleListing.item_id == item.id))
    assert listing is not None
    assert listing.asking_price == 50_000
    assert listing.listing_source == "slack_market_capture"
    assert listing.listing_capture_uuid == batch.uuid
    assert session.scalar(select(func.count(PriceObservation.id))) == 1
    action = session.scalar(select(SaleCaptureListingAction))
    assert action is not None
    assert action.action == "created"
    assert action.sale_listing_id == listing.id


def test_commit_revalidates_stale_sold_state_and_writes_nothing_partial(
    session,
    tmp_path: Path,
) -> None:
    item = _craftable_item(session, "Synthetic Hat")
    listing = SalesService(session, "Dodge").start(
        SaleListingCreate(item_uuid=item.uuid, asking_price=47_000)
    )
    extraction = _extraction(
        ScreenKind.SOLD_NOTIFICATION,
        [("Synthetic Hat", 47_000)],
    )
    batch = SaleCaptureBatch(
        workspace_id="T123",
        channel_id="C123",
        parent_message_ts="1788058800.000002",
        requester_user_id="U123",
        requested_action="sold",
        status="committing",
        observed_at=datetime.now(UTC) + timedelta(seconds=1),
        extraction_json=extraction.model_dump_json(),
    )
    session.add(batch)
    session.commit()
    SalesService(session, "Dodge").mark_sold(listing.uuid)

    result = SaleCaptureService(
        session,
        "Dodge",
        approved_professions=("Tailor",),
    ).commit_batch(
        batch.uuid,
        database_path=tmp_path / "unused.sqlite3",
        backup_directory=tmp_path,
        now=datetime.now(UTC),
        backup_creator=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no backup is made for invalid state")
        ),
    )

    assert not result.plan.can_commit
    assert result.backup_path is None
    session.refresh(batch)
    assert batch.status == "needs_review"
    assert session.scalar(select(func.count(SaleCaptureListingAction.id))) == 0
