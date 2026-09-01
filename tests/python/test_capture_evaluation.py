import json
from pathlib import Path

from dofus_touch_economy.capture_evaluation import evaluate_capture_manifest
from dofus_touch_economy.capture_schemas import (
    CaptureExtraction,
    CaptureOccurrence,
    ScreenKind,
)
from dofus_touch_economy.capture_vision import VisionExtractionResult


class _FakeVision:
    def extract(self, action, images, *, verification=False):
        assert verification is False
        return VisionExtractionResult(
            extraction=CaptureExtraction(
                screen_kind=ScreenKind.SOLD_NOTIFICATION,
                occurrences=(
                    CaptureOccurrence(
                        raw_item_name="Synthetic Hat",
                        displayed_price_kamas=47_000,
                        image_number=1,
                        row_number=1,
                    ),
                ),
            ),
            response_id="resp-test",
            model="test-model",
            prompt_version=f"{action.value}-test",
        )


def test_private_capture_evaluation_reports_only_aggregate_exact_matches(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "sold.png"
    image_path.write_bytes(b"synthetic")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "sold-1",
                        "action": "sold",
                        "images": [{"path": "sold.png", "mime_type": "image/png"}],
                        "expected": {
                            "screen_kind": "sold_notification",
                            "occurrences": [
                                {
                                    "raw_item_name": "Synthetic Hat",
                                    "displayed_price_kamas": 47000,
                                    "image_number": 1,
                                    "row_number": 1,
                                }
                            ],
                            "warnings": [],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output: list[str] = []

    summary = evaluate_capture_manifest(manifest_path, _FakeVision(), emit=output.append)

    assert summary.total_count == 1
    assert summary.passed_count == 1
    assert summary.false_positive_count == 0
    assert output == ["action=sold passed=1 total=1 false_positives=0"]
    assert "Synthetic Hat" not in str(output)
