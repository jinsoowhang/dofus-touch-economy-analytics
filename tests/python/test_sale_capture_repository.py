from datetime import UTC, datetime, timedelta

from dofus_touch_economy.capture_schemas import CaptureFileInput, CaptureIntake
from dofus_touch_economy.repositories.sale_captures import SaleCaptureRepository

NOW = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)


def _intake(*, message_ts: str = "1788058800.000001") -> CaptureIntake:
    return CaptureIntake(
        provider="slack",
        workspace_id="T123",
        channel_id="C123",
        parent_message_ts=message_ts,
        event_id="Ev123",
        requester_user_id="U123",
        caption="market\nplease sync",
        requested_action="market",
        observed_at=NOW,
        files=(
            CaptureFileInput(
                provider_file_id="F1",
                mime_type="image/png",
                byte_size=100,
            ),
            CaptureFileInput(
                provider_file_id="F2",
                mime_type="image/jpeg",
                byte_size=200,
            ),
        ),
    )


def test_intake_is_idempotent_by_parent_message(session) -> None:
    repository = SaleCaptureRepository(session)

    first, first_created = repository.get_or_create(_intake())
    session.commit()
    second, second_created = repository.get_or_create(_intake())

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert first.status == "queued"
    assert [file.provider_file_id for file in first.files] == ["F1", "F2"]
    assert all(file.sha256 is None for file in first.files)


def test_intake_without_action_waits_for_owner_selection(session) -> None:
    intake = _intake()
    intake = CaptureIntake(
        **{**intake.__dict__, "requested_action": None, "caption": "please process"}
    )

    batch, _ = SaleCaptureRepository(session).get_or_create(intake)

    assert batch.status == "awaiting_action"


def test_hash_overlap_distinguishes_exact_and_partial_completed_batches(session) -> None:
    repository = SaleCaptureRepository(session)
    prior, _ = repository.get_or_create(_intake())
    for file, digest in zip(prior.files, ("a" * 64, "b" * 64), strict=True):
        file.sha256 = digest
        file.status = "downloaded"
    prior.status = "committed"
    current, _ = repository.get_or_create(_intake(message_ts="1788058801.000001"))
    session.flush()

    assert repository.hash_overlap(current.id, ("a" * 64, "b" * 64)) == "exact"
    assert repository.hash_overlap(current.id, ("a" * 64, "c" * 64)) == "partial"
    assert repository.hash_overlap(current.id, ("c" * 64, "d" * 64)) == "none"


def test_claim_next_uses_persisted_lease_and_recovers_expired_work(session) -> None:
    repository = SaleCaptureRepository(session)
    first, _ = repository.get_or_create(_intake())
    second, _ = repository.get_or_create(_intake(message_ts="1788058801.000001"))
    first.received_at = NOW - timedelta(minutes=2)
    second.received_at = NOW - timedelta(minutes=1)
    session.commit()

    claimed = repository.claim_next(now=NOW, lease_for=timedelta(minutes=5))
    session.commit()
    next_claimed = repository.claim_next(now=NOW, lease_for=timedelta(minutes=5))

    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == "extracting"
    assert claimed.attempt_count == 1
    assert next_claimed is not None
    assert next_claimed.id == second.id
    assert repository.claim_next(now=NOW, lease_for=timedelta(minutes=5)) is None

    first.status = "queued"
    first.lease_expires_at = NOW - timedelta(seconds=1)
    session.commit()

    recovered = repository.claim_next(now=NOW, lease_for=timedelta(minutes=5))

    assert recovered is not None
    assert recovered.id == first.id
    assert recovered.attempt_count == 2


def test_conditional_transitions_and_decisions_are_idempotent(session) -> None:
    repository = SaleCaptureRepository(session)
    batch, _ = repository.get_or_create(_intake())
    session.commit()

    assert repository.transition(
        batch.uuid,
        from_statuses=("queued",),
        to_status="awaiting_confirmation",
    )
    assert not repository.transition(
        batch.uuid,
        from_statuses=("queued",),
        to_status="awaiting_confirmation",
    )
    assert repository.decide(
        batch.uuid,
        owner_user_id="U123",
        approve=True,
        decided_at=NOW,
    )
    assert not repository.decide(
        batch.uuid,
        owner_user_id="U123",
        approve=True,
        decided_at=NOW,
    )
    session.refresh(batch)
    assert batch.status == "committing"
    assert batch.decided_by_user_id == "U123"
    assert batch.decided_at == NOW.replace(tzinfo=None)


def test_receipt_status_is_independent_of_domain_status(session) -> None:
    repository = SaleCaptureRepository(session)
    batch, _ = repository.get_or_create(_intake())
    batch.status = "committed"
    batch.receipt_status = "pending"
    session.commit()

    assert repository.mark_receipt_sent(batch.uuid, "1788058810.000001")
    session.refresh(batch)

    assert batch.status == "committed"
    assert batch.receipt_status == "sent"
    assert batch.receipt_message_ts == "1788058810.000001"
