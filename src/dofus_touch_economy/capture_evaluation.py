from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from dofus_touch_economy.capture_schemas import CaptureAction, CaptureExtraction
from dofus_touch_economy.capture_vision import VisionAdapter, VisionImage


class EvaluationImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    mime_type: str


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    action: CaptureAction
    images: tuple[EvaluationImage, ...] = Field(min_length=1)
    expected: CaptureExtraction


class EvaluationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: tuple[EvaluationCase, ...] = Field(min_length=1)


@dataclass(frozen=True)
class CaptureEvaluationSummary:
    total_count: int
    passed_count: int
    false_positive_count: int


def evaluate_capture_manifest(
    manifest_path: Path,
    adapter: VisionAdapter,
    *,
    emit: Callable[[str], None] = print,
) -> CaptureEvaluationSummary:
    resolved_manifest = manifest_path.resolve()
    manifest = EvaluationManifest.model_validate_json(resolved_manifest.read_text(encoding="utf-8"))
    counts: dict[CaptureAction, list[int]] = defaultdict(lambda: [0, 0, 0])
    for case in manifest.cases:
        images = tuple(
            VisionImage(
                path=(resolved_manifest.parent / image.path).resolve(),
                mime_type=image.mime_type,
                image_number=index,
            )
            for index, image in enumerate(case.images, start=1)
        )
        actual = adapter.extract(case.action, images).extraction
        action_counts = counts[case.action]
        action_counts[0] += 1
        if actual == case.expected:
            action_counts[1] += 1
        action_counts[2] += _false_positive_count(case.expected, actual)

    for action in sorted(counts, key=lambda value: value.value):
        total, passed, false_positives = counts[action]
        emit(
            f"action={action.value} passed={passed} total={total} false_positives={false_positives}"
        )
    return CaptureEvaluationSummary(
        total_count=sum(value[0] for value in counts.values()),
        passed_count=sum(value[1] for value in counts.values()),
        false_positive_count=sum(value[2] for value in counts.values()),
    )


def _false_positive_count(
    expected: CaptureExtraction,
    actual: CaptureExtraction,
) -> int:
    expected_rows = Counter(
        (
            value.raw_item_name,
            value.displayed_price_kamas,
            value.image_number,
            value.row_number,
        )
        for value in expected.occurrences
    )
    actual_rows = Counter(
        (
            value.raw_item_name,
            value.displayed_price_kamas,
            value.image_number,
            value.row_number,
        )
        for value in actual.occurrences
    )
    return sum((actual_rows - expected_rows).values())
