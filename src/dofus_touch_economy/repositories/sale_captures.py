from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from dofus_touch_economy.capture_evidence import EvidenceRetentionCandidate
from dofus_touch_economy.capture_schemas import CaptureIntake
from dofus_touch_economy.models import (
    SaleCaptureBatch,
    SaleCaptureFile,
    SaleCaptureListingAction,
    SaleListing,
)

HashOverlap = Literal["none", "partial", "exact"]
TERMINAL_CAPTURE_STATUSES = frozenset(("committed", "rejected", "failed"))


@dataclass(frozen=True)
class CaptureEvidenceRetentionRecord:
    file_id: int
    candidate: EvidenceRetentionCandidate


class SaleCaptureRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, intake: CaptureIntake) -> tuple[SaleCaptureBatch, bool]:
        existing = self._session.scalar(
            select(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.provider == intake.provider,
                SaleCaptureBatch.workspace_id == intake.workspace_id,
                SaleCaptureBatch.channel_id == intake.channel_id,
                SaleCaptureBatch.parent_message_ts == intake.parent_message_ts,
            )
            .options(selectinload(SaleCaptureBatch.files))
        )
        if existing is not None:
            return existing, False

        batch = SaleCaptureBatch(
            provider=intake.provider,
            workspace_id=intake.workspace_id,
            channel_id=intake.channel_id,
            parent_message_ts=intake.parent_message_ts,
            event_id=intake.event_id,
            requester_user_id=intake.requester_user_id,
            caption=intake.caption,
            requested_action=intake.requested_action,
            status="queued" if intake.requested_action is not None else "awaiting_action",
            observed_at=intake.observed_at,
        )
        batch.files.extend(
            SaleCaptureFile(
                attachment_order=index,
                provider_file_id=file.provider_file_id,
                mime_type=file.mime_type,
                byte_size=file.byte_size,
                status="pending",
            )
            for index, file in enumerate(intake.files, start=1)
        )
        self._session.add(batch)
        self._session.flush()
        return batch, True

    def get_by_uuid(self, batch_uuid: UUID) -> SaleCaptureBatch | None:
        return self._session.scalar(
            select(SaleCaptureBatch)
            .where(SaleCaptureBatch.uuid == batch_uuid)
            .options(
                selectinload(SaleCaptureBatch.files),
                selectinload(SaleCaptureBatch.listing_actions)
                .selectinload(SaleCaptureListingAction.sale_listing)
                .selectinload(SaleListing.item),
            )
        )

    def get_by_parent_message(
        self,
        *,
        provider: str,
        workspace_id: str,
        channel_id: str,
        parent_message_ts: str,
    ) -> SaleCaptureBatch | None:
        return self._session.scalar(
            select(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.provider == provider,
                SaleCaptureBatch.workspace_id == workspace_id,
                SaleCaptureBatch.channel_id == channel_id,
                SaleCaptureBatch.parent_message_ts == parent_message_ts,
            )
            .options(selectinload(SaleCaptureBatch.files))
        )

    def latest_parent_message_ts(self) -> str | None:
        return self._session.scalar(select(func.max(SaleCaptureBatch.parent_message_ts)))

    def next_committing(self) -> SaleCaptureBatch | None:
        return self._session.scalar(
            select(SaleCaptureBatch)
            .where(SaleCaptureBatch.status == "committing")
            .order_by(SaleCaptureBatch.decided_at, SaleCaptureBatch.id)
            .limit(1)
        )

    def next_pending_receipt(self) -> SaleCaptureBatch | None:
        return self._session.scalar(
            select(SaleCaptureBatch)
            .where(SaleCaptureBatch.receipt_status.in_(("pending", "retry_wait")))
            .order_by(SaleCaptureBatch.completed_at, SaleCaptureBatch.id)
            .limit(1)
            .options(
                selectinload(SaleCaptureBatch.files),
                selectinload(SaleCaptureBatch.listing_actions)
                .selectinload(SaleCaptureListingAction.sale_listing)
                .selectinload(SaleListing.item),
            )
        )

    def set_requested_action(
        self,
        batch_uuid: UUID,
        *,
        action: str,
    ) -> bool:
        result = self._session.execute(
            update(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.uuid == batch_uuid,
                SaleCaptureBatch.status == "awaiting_action",
                SaleCaptureBatch.requested_action.is_(None),
            )
            .values(
                requested_action=action,
                status="queued",
                receipt_status="none",
            )
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def hash_overlap(self, current_batch_id: int, hashes: tuple[str, ...]) -> HashOverlap:
        requested = Counter(hashes)
        if not requested:
            return "none"
        prior_batches = self._session.scalars(
            select(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.id != current_batch_id,
                SaleCaptureBatch.status == "committed",
            )
            .options(selectinload(SaleCaptureBatch.files))
        ).all()
        partial = False
        for batch in prior_batches:
            prior = Counter(file.sha256 for file in batch.files if file.sha256 is not None)
            if prior == requested:
                return "exact"
            if prior.keys() & requested.keys():
                partial = True
        return "partial" if partial else "none"

    def claim_next(
        self,
        *,
        now: datetime,
        lease_for: timedelta,
    ) -> SaleCaptureBatch | None:
        eligible = self._eligible_clause(now)
        candidate_id = self._session.scalar(
            select(SaleCaptureBatch.id)
            .where(eligible)
            .order_by(SaleCaptureBatch.received_at, SaleCaptureBatch.id)
            .limit(1)
        )
        if candidate_id is None:
            return None
        result = self._session.execute(
            update(SaleCaptureBatch)
            .where(SaleCaptureBatch.id == candidate_id, self._eligible_clause(now))
            .values(
                status="extracting",
                attempt_count=SaleCaptureBatch.attempt_count + 1,
                lease_expires_at=now + lease_for,
                next_attempt_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            return None
        return self._session.scalar(
            select(SaleCaptureBatch)
            .where(SaleCaptureBatch.id == candidate_id)
            .options(selectinload(SaleCaptureBatch.files))
            .execution_options(populate_existing=True)
        )

    def transition(
        self,
        batch_uuid: UUID,
        *,
        from_statuses: tuple[str, ...],
        to_status: str,
        values: dict[str, object] | None = None,
    ) -> bool:
        updates = {"status": to_status, **(values or {})}
        if to_status != "extracting":
            updates.setdefault("lease_expires_at", None)
        result = self._session.execute(
            update(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.uuid == batch_uuid,
                SaleCaptureBatch.status.in_(from_statuses),
            )
            .values(**updates)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def decide(
        self,
        batch_uuid: UUID,
        *,
        owner_user_id: str,
        approve: bool,
        decided_at: datetime,
    ) -> bool:
        result = self._session.execute(
            update(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.uuid == batch_uuid,
                SaleCaptureBatch.status == "awaiting_confirmation",
                SaleCaptureBatch.decided_at.is_(None),
            )
            .values(
                status="committing" if approve else "rejected",
                decided_by_user_id=owner_user_id,
                decided_at=decided_at,
                completed_at=None if approve else decided_at,
                receipt_status="none" if approve else "pending",
            )
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def mark_receipt_sent(
        self,
        batch_uuid: UUID,
        receipt_message_ts: str,
        *,
        is_preview: bool = False,
    ) -> bool:
        values: dict[str, object] = {
            "receipt_status": "sent",
            "receipt_message_ts": receipt_message_ts,
        }
        if is_preview:
            values["preview_message_ts"] = receipt_message_ts
        result = self._session.execute(
            update(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.uuid == batch_uuid,
                SaleCaptureBatch.receipt_status.in_(("pending", "retry_wait")),
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def mark_receipt_retry(
        self,
        batch_uuid: UUID,
        *,
        failed: bool,
    ) -> bool:
        result = self._session.execute(
            update(SaleCaptureBatch)
            .where(
                SaleCaptureBatch.uuid == batch_uuid,
                SaleCaptureBatch.receipt_status.in_(("pending", "retry_wait")),
            )
            .values(receipt_status="failed" if failed else "retry_wait")
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def evidence_retention_candidates(self) -> tuple[CaptureEvidenceRetentionRecord, ...]:
        rows = self._session.execute(
            select(
                SaleCaptureFile.id,
                SaleCaptureFile.local_relative_path,
                SaleCaptureBatch.status,
                SaleCaptureBatch.completed_at,
            )
            .join(SaleCaptureBatch, SaleCaptureFile.capture_batch_id == SaleCaptureBatch.id)
            .where(
                SaleCaptureFile.status == "downloaded",
                SaleCaptureFile.local_relative_path.is_not(None),
            )
        ).all()
        return tuple(
            CaptureEvidenceRetentionRecord(
                file_id=file_id,
                candidate=EvidenceRetentionCandidate(
                    relative_path=relative_path,
                    terminal=status in TERMINAL_CAPTURE_STATUSES,
                    completed_at=completed_at,
                ),
            )
            for file_id, relative_path, status, completed_at in rows
        )

    def mark_evidence_purged(self, file_ids: tuple[int, ...], *, purged_at: datetime) -> int:
        if not file_ids:
            return 0
        result = self._session.execute(
            update(SaleCaptureFile)
            .where(
                SaleCaptureFile.id.in_(file_ids),
                SaleCaptureFile.status == "downloaded",
            )
            .values(status="purged", purged_at=purged_at)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount

    @staticmethod
    def _eligible_clause(now: datetime):
        return and_(
            SaleCaptureBatch.status.in_(("queued", "retry_wait", "extracting")),
            or_(
                SaleCaptureBatch.next_attempt_at.is_(None),
                SaleCaptureBatch.next_attempt_at <= now,
            ),
            or_(
                SaleCaptureBatch.lease_expires_at.is_(None),
                SaleCaptureBatch.lease_expires_at <= now,
            ),
        )
