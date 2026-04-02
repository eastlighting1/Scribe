"""Configuration models for the Scribe runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scribe.exceptions import ValidationError


@dataclass(slots=True)
class ScribeConfig:
    """Minimal runtime configuration."""

    producer_ref: str = "sdk.python.local"
    schema_version: str = "1.0.0"
    capture_environment: bool = True
    capture_installed_packages: bool = True
    environment_variable_allowlist: tuple[str, ...] = field(default_factory=tuple)
    retry_attempts: int = 0
    retry_backoff_seconds: float = 0.0
    outbox_root: str | Path | None = None

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0":
            raise ValidationError(
                "schema_version is fixed by the active Spine contract and must remain '1.0.0'."
            )
        if self.retry_attempts < 0:
            raise ValidationError("retry_attempts must be >= 0.")
        if self.retry_backoff_seconds < 0:
            raise ValidationError("retry_backoff_seconds must be >= 0.")
