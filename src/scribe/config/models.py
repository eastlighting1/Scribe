"""Configuration models for the Scribe runtime."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ScribeConfig:
    """Minimal runtime configuration."""

    producer_ref: str = "sdk.python.local"
    schema_version: str = "1.0.0"
    capture_environment: bool = True
    capture_installed_packages: bool = True
    environment_variable_allowlist: tuple[str, ...] = field(default_factory=tuple)
