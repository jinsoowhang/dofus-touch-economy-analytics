from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from dofus_touch_economy.models import (
    Item,
    SaleCaptureBatch,
    SaleCaptureFile,
    SaleCaptureListingAction,
    SaleListing,
)


def _batch(*, message_ts: str = "1788058800.000001") -> SaleCaptureBatch:
    return SaleCaptureBatch(
        provider="slack",
        workspace_id="T123",
        channel_id="C123",
        parent_message_ts=message_ts,
        requester_user_id="U123",
        requested_action="market",
        status="received",
        observed_at=datetime(2026, 8, 29, 20, 0, tzinfo=UTC),
    )


def test_capture_models_preserve_ordered_files_and_listing_action_history(session) -> None:
    item = Item(
        display_name="Synthetic Hat",
        normalized_name="synthetic hat",
        category="Hat",
        identity_category="hat",
    )
    listing = SaleListing(
        item=item,
        lot_quantity=1,
        asking_price=12_000,
        selling_started_at=datetime(2026, 8, 29, 20, 0, tzinfo=UTC),
    )
    market_batch = _batch()
    market_batch.files.extend(
        [
            SaleCaptureFile(
                attachment_order=1,
                provider_file_id="F1",
                mime_type="image/png",
                byte_size=100,
                sha256="a" * 64,
                status="downloaded",
            ),
            SaleCaptureFile(
                attachment_order=2,
                provider_file_id="F2",
                mime_type="image/jpeg",
                byte_size=200,
                sha256="b" * 64,
                status="downloaded",
            ),
        ]
    )
    market_batch.listing_actions.append(
        SaleCaptureListingAction(
            sale_listing=listing,
            action="created",
            effective_at=datetime(2026, 8, 29, 20, 0, tzinfo=UTC),
            asking_price=12_000,
        )
    )
    sold_batch = _batch(message_ts="1788145200.000001")
    sold_batch.requested_action = "sold"
    sold_batch.listing_actions.append(
        SaleCaptureListingAction(
            sale_listing=listing,
            action="marked_sold",
            effective_at=datetime(2026, 8, 30, 20, 0, tzinfo=UTC),
            asking_price=12_000,
        )
    )
    session.add_all([market_batch, sold_batch])
    session.commit()

    assert [file.provider_file_id for file in market_batch.files] == ["F1", "F2"]
    assert [action.action for action in listing.capture_actions] == [
        "created",
        "marked_sold",
    ]


def test_capture_message_identity_is_unique(session) -> None:
    session.add(_batch())
    session.commit()
    session.add(_batch())

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "discord"),
        ("requested_action", "guess"),
        ("status", "surprise"),
        ("attempt_count", -1),
    ],
)
def test_capture_batch_rejects_invalid_state(session, field: str, value: object) -> None:
    batch = _batch()
    setattr(batch, field, value)
    session.add(batch)

    with pytest.raises(IntegrityError):
        session.commit()


def test_capture_file_rejects_invalid_positive_fields(session) -> None:
    batch = _batch()
    batch.files.append(
        SaleCaptureFile(
            attachment_order=0,
            provider_file_id="F1",
            mime_type="image/png",
            byte_size=0,
            sha256="a" * 64,
            status="downloaded",
        )
    )
    session.add(batch)

    with pytest.raises(IntegrityError):
        session.commit()
