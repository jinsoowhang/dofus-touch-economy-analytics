from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from PIL import Image, UnidentifiedImageError

SUPPORTED_IMAGE_MIME_TYPES = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class EvidenceValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StoredEvidence:
    absolute_path: Path
    relative_path: str
    sha256: str
    byte_size: int
    mime_type: str


@dataclass(frozen=True)
class EvidenceRetentionCandidate:
    relative_path: str
    terminal: bool
    completed_at: datetime | None


class EvidenceStore:
    def __init__(self, root: Path, *, maximum_image_bytes: int) -> None:
        if maximum_image_bytes <= 0:
            raise ValueError("maximum image bytes must be positive")
        self._root = root.resolve()
        self._maximum_image_bytes = maximum_image_bytes

    def store(
        self,
        *,
        capture_uuid: UUID,
        attachment_order: int,
        declared_mime_type: str,
        chunks: Iterable[bytes],
    ) -> StoredEvidence:
        if attachment_order <= 0:
            raise ValueError("attachment order must be positive")
        if declared_mime_type not in {value[0] for value in SUPPORTED_IMAGE_MIME_TYPES.values()}:
            raise EvidenceValidationError("unsupported declared image MIME type")

        capture_directory = self._root / str(capture_uuid)
        capture_directory.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            digest = hashlib.sha256()
            byte_size = 0
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".tmp",
                prefix=f"{attachment_order:02d}-",
                dir=capture_directory,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                for chunk in chunks:
                    byte_size += len(chunk)
                    if byte_size > self._maximum_image_bytes:
                        raise EvidenceValidationError(
                            f"image exceeds the {self._maximum_image_bytes} bytes limit"
                        )
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())

            try:
                with Image.open(temporary_path) as image:
                    image.verify()
                    image_format = image.format
            except (OSError, UnidentifiedImageError) as error:
                raise EvidenceValidationError(
                    "attachment is not a valid supported image"
                ) from error
            if image_format not in SUPPORTED_IMAGE_MIME_TYPES:
                raise EvidenceValidationError("decoded image format is unsupported")
            actual_mime_type, suffix = SUPPORTED_IMAGE_MIME_TYPES[image_format]
            if actual_mime_type != declared_mime_type:
                raise EvidenceValidationError(
                    "declared image MIME type does not match decoded content"
                )

            sha256 = digest.hexdigest()
            destination = capture_directory / f"{attachment_order:02d}-{sha256[:16]}{suffix}"
            os.replace(temporary_path, destination)
            temporary_path = None
            return StoredEvidence(
                absolute_path=destination,
                relative_path=destination.relative_to(self._root).as_posix(),
                sha256=sha256,
                byte_size=byte_size,
                mime_type=actual_mime_type,
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def purge_expired_evidence(
    root: Path,
    candidates: Iterable[EvidenceRetentionCandidate],
    *,
    now: datetime,
    retention_days: int,
) -> tuple[Path, ...]:
    if retention_days <= 0:
        raise ValueError("retention days must be positive")
    resolved_root = root.resolve()
    cutoff = _as_utc(now) - timedelta(days=retention_days)
    purged: list[Path] = []
    for candidate in candidates:
        if (
            not candidate.terminal
            or candidate.completed_at is None
            or _as_utc(candidate.completed_at) > cutoff
        ):
            continue
        path = (resolved_root / candidate.relative_path).resolve()
        if not path.is_relative_to(resolved_root):
            raise EvidenceValidationError("evidence path escapes the configured root")
        if path.is_file():
            path.unlink()
            purged.append(path)
    return tuple(purged)


def create_integrity_checked_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    label: str,
    now: datetime,
) -> Path:
    source_path = database_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"application database does not exist: {source_path}")
    safe_label = re.sub(r"[^a-z0-9-]+", "-", label.casefold()).strip("-")
    if not safe_label:
        raise ValueError("backup label must contain letters or numbers")
    resolved_directory = backup_directory.resolve()
    resolved_directory.mkdir(parents=True, exist_ok=True)
    timestamp = _as_utc(now).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = resolved_directory / f"dofus-touch-{safe_label}-{timestamp}.sqlite3"

    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeError("SQLite backup failed its integrity check")
    except Exception:
        destination.close()
        source.close()
        backup_path.unlink(missing_ok=True)
        raise
    else:
        destination.close()
        source.close()
    return backup_path


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
