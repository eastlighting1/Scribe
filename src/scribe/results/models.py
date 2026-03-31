"""Capture result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PayloadFamily(StrEnum):
    """Vendor-agnostic truth families produced by Scribe."""

    CONTEXT = "context"
    RECORD = "record"
    ARTIFACT = "artifact"
    DEGRADATION = "degradation"


class DeliveryStatus(StrEnum):
    """Normalized capture delivery status."""

    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass(slots=True)
class Delivery:
    """Per-sink delivery information."""

    sink_name: str
    family: PayloadFamily
    status: DeliveryStatus
    detail: str = ""


@dataclass(slots=True)
class CaptureResult:
    """Structured outcome for any capture action."""

    family: PayloadFamily
    status: DeliveryStatus
    deliveries: list[Delivery] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    degradation_reasons: list[str] = field(default_factory=list)
    payload: Any | None = None
    degradation_emitted: bool = False
    degradation_payload: Any | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether at least one sink accepted the payload."""
        return self.status in (DeliveryStatus.SUCCESS, DeliveryStatus.DEGRADED)

    @property
    def degraded(self) -> bool:
        """Return whether capture finished with reduced fidelity."""
        return self.status == DeliveryStatus.DEGRADED


@dataclass(slots=True)
class BatchCaptureResult:
    """Aggregated outcome for batch capture operations."""

    family: PayloadFamily
    status: DeliveryStatus
    results: list[CaptureResult] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        """Return the number of attempted captures."""
        return len(self.results)

    @property
    def success_count(self) -> int:
        """Return the number of fully successful captures."""
        return sum(result.status == DeliveryStatus.SUCCESS for result in self.results)

    @property
    def degraded_count(self) -> int:
        """Return the number of degraded captures."""
        return sum(result.status == DeliveryStatus.DEGRADED for result in self.results)

    @property
    def failure_count(self) -> int:
        """Return the number of failed captures."""
        return sum(result.status == DeliveryStatus.FAILURE for result in self.results)

    @property
    def succeeded(self) -> bool:
        """Return whether at least one batch item succeeded."""
        return self.status in (DeliveryStatus.SUCCESS, DeliveryStatus.DEGRADED)

    @property
    def degraded(self) -> bool:
        """Return whether the batch finished with reduced fidelity."""
        return self.status == DeliveryStatus.DEGRADED

    @classmethod
    def from_results(
        cls,
        family: PayloadFamily,
        results: list[CaptureResult],
    ) -> BatchCaptureResult:
        """Build a normalized batch outcome from individual results."""
        if not results:
            return cls(family=family, status=DeliveryStatus.SUCCESS, results=[])

        statuses = {result.status for result in results}
        if statuses == {DeliveryStatus.SUCCESS}:
            status = DeliveryStatus.SUCCESS
        elif statuses == {DeliveryStatus.FAILURE}:
            status = DeliveryStatus.FAILURE
        else:
            status = DeliveryStatus.DEGRADED
        return cls(family=family, status=status, results=results)
