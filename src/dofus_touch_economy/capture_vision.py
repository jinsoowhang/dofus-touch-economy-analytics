from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from dofus_touch_economy.capture_schemas import CaptureAction, CaptureExtraction

MARKET_LAYOUT_VALIDATED = False
DEFAULT_CODEX_TIMEOUT_SECONDS = 180
DEFAULT_CODEX_MODEL_LABEL = "codex-cli-subscription-default"

_COMMON_INSTRUCTIONS = """
You transcribe Dofus Touch screenshots into a strict structured record. Read pixels
only. Do not use tools, the shell, the network, or files other than the attached
images. Do not correct an item name from memory, resolve it to a catalog, infer
missing text, choose a business action, or invent a row. Preserve every raw item name
as it appears. Convert a visibly complete kama price to a positive whole integer
without separators. Number images from one in the supplied order and rows from one
from top to bottom within each image. Include repeated identical rows separately.
Omit a partially visible row and add a precise warning. Use other or uncertain
screen_kind whenever the screen is not clearly the requested Dofus Touch layout.
Return only the JSON object required by the supplied schema.
""".strip()

_SOLD_PROMPT = """
The requested layout is a Dofus Touch sold-notification/chat screen. A qualifying row
is a complete sale message such as a bank credit followed by '(sale of 1 ITEM while
offline)'. Extract the credited kama amount as displayed_price_kamas and only the ITEM
text as raw_item_name. Ignore unrelated chat, energy, login, and informational lines.
Set screen_kind to sold_notification only when this layout is clearly present.
""".strip()

_SOLD_VERIFICATION_PROMPT = """
Independently audit a Dofus Touch sold-notification screenshot. Start from the bottom
of each image and work upward, then return occurrences in normal top-to-bottom order.
Transcribe only complete bank-credit sale lines, preserving item spelling and the
visible whole-kama amount. Do not rely on any prior extraction.
""".strip()

_MARKET_PROMPT = """
The requested layout is the player's own active marketplace-listings screen in Dofus
Touch. Extract one occurrence for each complete visible owned-listing row, preserving
its item name and exact whole-kama asking price. Do not treat catalog search results,
other players' listings, inventory rows, suggested prices, totals, or partly visible
rows as owned active listings. Set screen_kind to own_market_listings only when that
ownership context is explicit. This prompt remains disabled for live market writes
until a private example of the actual layout is labeled and evaluated.
""".strip()

_MARKET_VERIFICATION_PROMPT = """
Independently audit the player's own active Dofus Touch marketplace screen. Recount
each complete owned-listing row and transcribe the exact item text and whole-kama
asking price in visible order. Do not rely on any prior extraction.
""".strip()

_CODEX_ENVIRONMENT_NAMES = (
    "CODEX_HOME",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TMPDIR",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
)
_CODEX_MODEL_PATTERN = re.compile(
    r"^model:\s*([a-z0-9][a-z0-9._-]*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_PERMANENT_CODEX_ERROR_CODES = (
    '"code": "invalid_json_schema"',
    '"type": "invalid_request_error"',
    '"code": "model_not_found"',
)


class VisionResponseError(RuntimeError):
    """The model output could not be used safely."""


class CodexCliUnavailableError(VisionResponseError):
    """The local Codex CLI or its ChatGPT authentication is unavailable."""


class CodexCliExecutionError(RuntimeError):
    """A potentially transient Codex CLI invocation failed."""


@dataclass(frozen=True)
class VisionImage:
    path: Path
    mime_type: str
    image_number: int


@dataclass(frozen=True)
class VisionExtractionResult:
    extraction: CaptureExtraction
    response_id: str | None
    model: str
    prompt_version: str


class VisionAdapter(Protocol):
    def extract(
        self,
        action: CaptureAction,
        images: tuple[VisionImage, ...],
        *,
        verification: bool = False,
    ) -> VisionExtractionResult: ...


class CodexCliVisionAdapter:
    def __init__(
        self,
        *,
        binary: str = "codex",
        model: str | None = None,
        timeout_seconds: int = DEFAULT_CODEX_TIMEOUT_SECONDS,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if not binary.strip():
            raise ValueError("Codex CLI binary must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("Codex CLI timeout must be positive")
        self._binary = binary
        self._model = model.strip() if model and model.strip() else None
        self._timeout_seconds = timeout_seconds
        self._runner = runner
        self._environment = _codex_environment(environment or os.environ)

    @property
    def model_label(self) -> str:
        return self._model or DEFAULT_CODEX_MODEL_LABEL

    def check_ready(self) -> None:
        try:
            result = self._runner(
                [self._binary, "login", "status"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                env=self._environment,
            )
        except (FileNotFoundError, PermissionError) as error:
            raise CodexCliUnavailableError(
                "Codex CLI is unavailable; install it and run 'codex login'."
            ) from error
        except subprocess.TimeoutExpired as error:
            raise CodexCliUnavailableError("Codex CLI login status timed out.") from error
        status_text = f"{result.stdout}\n{result.stderr}".casefold()
        if result.returncode != 0 or "chatgpt" not in status_text:
            raise CodexCliUnavailableError(
                "Codex CLI must be authenticated with ChatGPT; run 'codex login'."
            )

    def extract(
        self,
        action: CaptureAction,
        images: tuple[VisionImage, ...],
        *,
        verification: bool = False,
    ) -> VisionExtractionResult:
        _validate_images(images)
        prompt, prompt_version = _prompt(action, verification=verification)
        full_prompt = f"{_COMMON_INSTRUCTIONS}\n\n{prompt}"

        with tempfile.TemporaryDirectory(prefix="dofus-codex-") as temporary_directory:
            work_path = Path(temporary_directory)
            schema_path = work_path / "capture-extraction-schema.json"
            output_path = work_path / "capture-extraction.json"
            schema_path.write_text(
                json.dumps(_capture_output_schema(), separators=(",", ":")),
                encoding="utf-8",
            )
            command = self._command(
                schema_path=schema_path,
                output_path=output_path,
                images=images,
            )
            try:
                result = self._runner(
                    command,
                    input=full_prompt,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self._timeout_seconds,
                    check=False,
                    cwd=work_path,
                    env=self._environment,
                )
            except (FileNotFoundError, PermissionError) as error:
                raise CodexCliUnavailableError(
                    "Codex CLI became unavailable; run the worker readiness check."
                ) from error
            except subprocess.TimeoutExpired as error:
                raise CodexCliExecutionError("Codex CLI extraction timed out.") from error
            if result.returncode != 0:
                if _is_permanent_codex_error(result.stderr):
                    raise VisionResponseError("Codex CLI rejected the extraction request.")
                raise CodexCliExecutionError(
                    f"Codex CLI extraction failed with exit code {result.returncode}."
                )
            try:
                extraction = CaptureExtraction.model_validate_json(
                    output_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as error:
                raise VisionResponseError(
                    "Codex CLI returned no valid structured extraction."
                ) from error

        return VisionExtractionResult(
            extraction=extraction,
            response_id=None,
            model=_reported_codex_model(result.stderr) or self.model_label,
            prompt_version=prompt_version,
        )

    def _command(
        self,
        *,
        schema_path: Path,
        output_path: Path,
        images: tuple[VisionImage, ...],
    ) -> list[str]:
        command = [
            self._binary,
            "exec",
            "-",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--disable",
            "shell_tool",
            "--disable",
            "multi_agent",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--config",
            "shell_environment_policy.inherit=none",
            "--config",
            "tools.view_image=false",
            "--config",
            'web_search="disabled"',
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
        ]
        if self._model is not None:
            command.extend(("--model", self._model))
        for image in images:
            command.extend(("--image", str(image.path.resolve())))
        return command


def extractions_agree(
    primary: CaptureExtraction,
    verification: CaptureExtraction,
) -> bool:
    return (
        primary.screen_kind == verification.screen_kind
        and primary.occurrences == verification.occurrences
    )


def _validate_images(images: tuple[VisionImage, ...]) -> None:
    if not images:
        raise ValueError("at least one image is required")
    expected_numbers = tuple(range(1, len(images) + 1))
    if tuple(image.image_number for image in images) != expected_numbers:
        raise ValueError("image numbers must be consecutive and start at one")
    for image in images:
        if image.mime_type not in ("image/png", "image/jpeg", "image/webp"):
            raise ValueError(f"unsupported image MIME type: {image.mime_type}")
        if not image.path.is_file():
            raise ValueError("image path must identify a file")


def _codex_environment(source: Mapping[str, str]) -> dict[str, str]:
    return {name: source[name] for name in _CODEX_ENVIRONMENT_NAMES if source.get(name)}


def _capture_output_schema() -> dict[str, object]:
    schema = CaptureExtraction.model_json_schema()
    properties = schema["properties"]
    schema["required"] = list(properties)
    properties["warnings"].pop("default", None)
    return schema


def _is_permanent_codex_error(stderr: str | None) -> bool:
    error_text = (stderr or "").casefold()
    return any(code in error_text for code in _PERMANENT_CODEX_ERROR_CODES)


def _reported_codex_model(stderr: str | None) -> str | None:
    match = _CODEX_MODEL_PATTERN.search(stderr or "")
    return None if match is None else match.group(1)


def _prompt(action: CaptureAction, *, verification: bool) -> tuple[str, str]:
    if action == CaptureAction.SOLD:
        return (
            (_SOLD_VERIFICATION_PROMPT, "sold-notification-verify-v1")
            if verification
            else (_SOLD_PROMPT, "sold-notification-v1")
        )
    return (
        (_MARKET_VERIFICATION_PROMPT, "market-listings-verify-v0-unvalidated")
        if verification
        else (_MARKET_PROMPT, "market-listings-v0-unvalidated")
    )
