"""Metric batch input models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(slots=True)
class MetricEmission:
    """Structured input for batch metric capture."""

    key: str
    value: int | float
    unit: str | None = None
    aggregation_scope: str = "point"
    tags: Mapping[str, str] = field(default_factory=dict)
    summary_basis: str = "raw_observation"
