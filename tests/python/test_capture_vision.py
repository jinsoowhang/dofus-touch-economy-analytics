from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dofus_touch_economy.capture_schemas import (
    CaptureAction,
    CaptureExtraction,
    CaptureOccurrence,
    ScreenKind,
)
from dofus_touch_economy.capture_vision import (
    MARKET_LAYOUT_VALIDATED,
    CodexCliExecutionError,
    CodexCliUnavailableError,
    CodexCliVisionAdapter,
    VisionImage,
    VisionResponseError,
    extractions_agree,
)


def _extraction(name: str = "Synthetic Hat") -> CaptureExtraction:
    return CaptureExtraction(
        screen_kind=ScreenKind.SOLD_NOTIFICATION,
        occurrences=(
            CaptureOccurrence(
                raw_item_name=name,
                displayed_price_kamas=47_000,
                image_number=1,
                row_number=1,
            ),
        ),
    )


class _FakeRunner:
    def __init__(
        self,
        extraction: CaptureExtraction | None = None,
        *,
        returncode: int = 0,
        login_status: str = "Logged in using ChatGPT",
        stderr: str = "private provider output",
    ) -> None:
        self.extraction = extraction
        self.returncode = returncode
        self.login_status = login_status
        self.stderr = stderr
        self.calls: list[tuple[list[str], dict[str, object]]] = []
        self.schema: dict[str, object] | None = None

    def __call__(self, command, **kwargs):
        command_values = list(command)
        self.calls.append((command_values, kwargs))
        if command_values[1:] == ["login", "status"]:
            return subprocess.CompletedProcess(
                command_values,
                self.returncode,
                stdout=self.login_status,
                stderr="",
            )
        schema_path = Path(command_values[command_values.index("--output-schema") + 1])
        self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if self.extraction is not None and self.returncode == 0:
            output_path = Path(command_values[command_values.index("--output-last-message") + 1])
            output_path.write_text(self.extraction.model_dump_json(), encoding="utf-8")
        return subprocess.CompletedProcess(
            command_values,
            self.returncode,
            stdout="",
            stderr=self.stderr,
        )


def test_codex_cli_adapter_uses_hardened_ephemeral_structured_image_run(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"synthetic-image-bytes")
    runner = _FakeRunner(_extraction())
    adapter = CodexCliVisionAdapter(
        model="gpt-test",
        runner=runner,
        environment={
            "HOME": "/home/tester",
            "PATH": "/usr/bin",
            "DOFUS_SLACK_BOT_TOKEN": "bot-secret",
            "OPENAI_API_KEY": "api-secret",
        },
    )

    result = adapter.extract(
        CaptureAction.SOLD,
        (VisionImage(path=image_path, mime_type="image/png", image_number=1),),
    )

    assert result.extraction == _extraction()
    assert result.response_id is None
    assert result.model == "gpt-test"
    assert result.prompt_version == "sold-notification-v1"
    command, options = runner.calls[0]
    assert command[:3] == ["codex", "exec", "-"]
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert command.count("--disable") == 2
    assert "shell_tool" in command
    assert "multi_agent" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "shell_environment_policy.inherit=none" in command
    assert "tools.view_image=false" in command
    assert 'web_search="disabled"' in command
    assert command[command.index("--model") + 1] == "gpt-test"
    assert command[command.index("--image") + 1] == str(image_path.resolve())
    assert options["cwd"] != tmp_path
    assert options["env"] == {"HOME": "/home/tester", "PATH": "/usr/bin"}
    assert "Synthetic Hat" not in str(options["input"])
    assert runner.schema is not None
    assert runner.schema["additionalProperties"] is False
    assert runner.schema["required"] == ["screen_kind", "occurrences", "warnings"]
    assert "default" not in runner.schema["properties"]["warnings"]


def test_codex_cli_adapter_requires_a_valid_structured_result(tmp_path: Path) -> None:
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"synthetic-image-bytes")

    with pytest.raises(VisionResponseError, match="structured extraction"):
        CodexCliVisionAdapter(runner=_FakeRunner()).extract(
            CaptureAction.SOLD,
            (VisionImage(path=image_path, mime_type="image/png", image_number=1),),
        )


def test_codex_cli_adapter_classifies_nonzero_execution_as_transient(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"synthetic-image-bytes")

    with pytest.raises(CodexCliExecutionError, match="exit code 1"):
        CodexCliVisionAdapter(runner=_FakeRunner(returncode=1)).extract(
            CaptureAction.SOLD,
            (VisionImage(path=image_path, mime_type="image/png", image_number=1),),
        )


def test_codex_cli_adapter_classifies_invalid_request_as_permanent(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"synthetic-image-bytes")
    runner = _FakeRunner(
        returncode=1,
        stderr='{"type": "invalid_request_error", "code": "invalid_json_schema"}',
    )

    with pytest.raises(VisionResponseError, match="rejected"):
        CodexCliVisionAdapter(runner=runner).extract(
            CaptureAction.SOLD,
            (VisionImage(path=image_path, mime_type="image/png", image_number=1),),
        )


def test_codex_cli_adapter_records_reported_model(tmp_path: Path) -> None:
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"synthetic-image-bytes")
    runner = _FakeRunner(_extraction(), stderr="header\nmodel: gpt-observed-1\nfooter")

    result = CodexCliVisionAdapter(runner=runner).extract(
        CaptureAction.SOLD,
        (VisionImage(path=image_path, mime_type="image/png", image_number=1),),
    )

    assert result.model == "gpt-observed-1"


def test_codex_cli_readiness_requires_chatgpt_authentication() -> None:
    CodexCliVisionAdapter(runner=_FakeRunner()).check_ready()

    with pytest.raises(CodexCliUnavailableError, match="authenticated with ChatGPT"):
        CodexCliVisionAdapter(
            runner=_FakeRunner(login_status="Logged in using an API key")
        ).check_ready()


def test_verification_prompt_is_independent_and_exact_agreement_is_ordered(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"synthetic-image-bytes")
    primary = _extraction()
    runner = _FakeRunner(primary)

    result = CodexCliVisionAdapter(runner=runner).extract(
        CaptureAction.SOLD,
        (VisionImage(path=image_path, mime_type="image/png", image_number=1),),
        verification=True,
    )
    changed = _extraction("Other Hat")

    assert result.prompt_version == "sold-notification-verify-v1"
    assert extractions_agree(primary, result.extraction)
    assert not extractions_agree(primary, changed)


def test_market_prompt_remains_live_disabled_until_private_layout_is_labeled() -> None:
    assert MARKET_LAYOUT_VALIDATED is False
