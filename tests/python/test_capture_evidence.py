from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from PIL import Image

from dofus_touch_economy.capture_evidence import (
    EvidenceRetentionCandidate,
    EvidenceStore,
    EvidenceValidationError,
    create_integrity_checked_backup,
    purge_expired_evidence,
)
from dofus_touch_economy.database import create_engine_for_url

CAPTURE_UUID = UUID("00000000-0000-0000-0000-000000000123")


def _image_bytes(image_format: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(10, 20, 30)).save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("image_format", "mime_type", "suffix"),
    [
        ("PNG", "image/png", ".png"),
        ("JPEG", "image/jpeg", ".jpg"),
        ("WEBP", "image/webp", ".webp"),
    ],
)
def test_evidence_store_streams_valid_images_to_a_hash_named_path(
    tmp_path: Path,
    image_format: str,
    mime_type: str,
    suffix: str,
) -> None:
    payload = _image_bytes(image_format)
    store = EvidenceStore(tmp_path / "evidence", maximum_image_bytes=1024)

    stored = store.store(
        capture_uuid=CAPTURE_UUID,
        attachment_order=1,
        declared_mime_type=mime_type,
        chunks=(payload[:5], payload[5:]),
    )

    assert stored.absolute_path.is_file()
    assert stored.absolute_path.suffix == suffix
    assert stored.byte_size == len(payload)
    assert len(stored.sha256) == 64
    assert stored.mime_type == mime_type
    assert not any(path.suffix == ".tmp" for path in tmp_path.rglob("*"))


def test_evidence_store_rejects_oversize_and_mime_mismatch_without_residue(
    tmp_path: Path,
) -> None:
    payload = _image_bytes("PNG")
    evidence_root = tmp_path / "evidence"

    with pytest.raises(EvidenceValidationError, match="20 bytes"):
        EvidenceStore(evidence_root, maximum_image_bytes=20).store(
            capture_uuid=CAPTURE_UUID,
            attachment_order=1,
            declared_mime_type="image/png",
            chunks=(payload,),
        )
    with pytest.raises(EvidenceValidationError, match="does not match"):
        EvidenceStore(evidence_root, maximum_image_bytes=1024).store(
            capture_uuid=CAPTURE_UUID,
            attachment_order=1,
            declared_mime_type="image/jpeg",
            chunks=(payload,),
        )

    assert not any(path.is_file() for path in evidence_root.rglob("*"))


def test_evidence_retention_purges_only_old_terminal_files(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    root.mkdir()
    old_terminal = root / "old-terminal.png"
    old_review = root / "old-review.png"
    recent_terminal = root / "recent-terminal.png"
    for path in (old_terminal, old_review, recent_terminal):
        path.write_bytes(b"synthetic")
    now = datetime(2026, 8, 29, tzinfo=UTC)

    purged = purge_expired_evidence(
        root,
        (
            EvidenceRetentionCandidate(
                relative_path=old_terminal.name,
                terminal=True,
                completed_at=now - timedelta(days=91),
            ),
            EvidenceRetentionCandidate(
                relative_path=old_review.name,
                terminal=False,
                completed_at=now - timedelta(days=100),
            ),
            EvidenceRetentionCandidate(
                relative_path=recent_terminal.name,
                terminal=True,
                completed_at=now - timedelta(days=89),
            ),
        ),
        now=now,
        retention_days=90,
    )

    assert purged == (old_terminal,)
    assert not old_terminal.exists()
    assert old_review.exists()
    assert recent_terminal.exists()


def test_online_backup_is_consistent_for_a_live_wal_database(tmp_path: Path) -> None:
    database_path = tmp_path / "application.sqlite3"
    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE events (id INTEGER PRIMARY KEY, value TEXT)")
        connection.exec_driver_sql("INSERT INTO events (value) VALUES ('before')")

    backup_path = create_integrity_checked_backup(
        database_path,
        tmp_path / "backups",
        label="before-slack-capture",
        now=datetime(2026, 8, 29, 20, 0, tzinfo=UTC),
    )
    engine.dispose()

    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT value FROM events").fetchall() == [("before",)]
