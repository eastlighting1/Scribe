"""JSON-compatible serialization helpers for sink payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from scribe.spine_bridge import StableRef


def to_json_ready(value: Any) -> Any:
    """Convert supported payload objects into JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StableRef):
        return str(value)
    if is_dataclass(value):
        return {
            field.name: to_json_ready(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): to_json_ready(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_ready(item) for item in value]
    raise TypeError(f"Unsupported payload type for JSON serialization: {type(value).__name__}")
