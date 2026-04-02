"""Structured metric emission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from scribe.exceptions import ValidationError
from scribe.metrics.models import MetricEmission
from scribe.results import BatchCaptureResult, CaptureResult, PayloadFamily
from scribe.runtime.builders import build_metric_record
from scribe.runtime.dispatch import dispatch_record
from scribe.utils import iso_utc_now

if TYPE_CHECKING:
    from scribe.runtime.session import RuntimeSession


def emit_metric(
    runtime: RuntimeSession,
    *,
    key: str,
    value: int | float,
    unit: str | None = None,
    aggregation_scope: str = "step",
    tags: Mapping[str, str] | None = None,
    summary_basis: str = "raw_observation",
) -> CaptureResult:
    """Emit a structured metric."""
    runtime.require_run()

    if not key.strip():
        raise ValidationError("key must not be empty.")

    observed_at = iso_utc_now()
    record = build_metric_record(
        runtime,
        key=key,
        value=value,
        unit=unit,
        aggregation_scope=aggregation_scope,
        tags=tags,
        summary_basis=summary_basis,
        observed_at=observed_at,
    )
    return dispatch_record(runtime, record)


def emit_metrics(
    runtime: RuntimeSession,
    emissions: Sequence[MetricEmission],
) -> BatchCaptureResult:
    """Emit multiple structured metrics in the active context."""
    results = [
        emit_metric(
            runtime,
            key=emission.key,
            value=emission.value,
            unit=emission.unit,
            aggregation_scope=emission.aggregation_scope,
            tags=emission.tags,
            summary_basis=emission.summary_basis,
        )
        for emission in emissions
    ]
    return BatchCaptureResult.from_results(PayloadFamily.RECORD, results)
