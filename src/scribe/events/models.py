"""Event batch input models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EventEmission:
    """Structured input for batch event capture."""

    key: str
    message: str
    level: str = "info"
    attributes: Mapping[str, Any] = field(default_factory=dict)
    tags: Mapping[str, str] = field(default_factory=dict)
