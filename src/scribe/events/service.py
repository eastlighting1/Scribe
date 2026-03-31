"""Structured event emission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from scribe.events.models import EventEmission
from scribe.exceptions import ValidationError
from scribe.results import BatchCaptureResult, CaptureResult, PayloadFamily
from scribe.runtime.builders import build_event_record
from scribe.runtime.dispatch import dispatch_record
from scribe.utils import iso_utc_now

if TYPE_CHECKING:
    from scribe.runtime.session import RuntimeSession


def emit_event(
    runtime: RuntimeSession,
    *,
    key: str,
    message: str,
    level: str = "info",
    attributes: Mapping[str, Any] | None = None,
    tags: Mapping[str, str] | None = None,
) -> CaptureResult:
    """Emit a structured event."""
    runtime.require_run()

    if not key.strip():
        raise ValidationError("key must not be empty.")
    if not message.strip():
        raise ValidationError("message must not be empty.")

    observed_at = iso_utc_now()
    record = build_event_record(
        runtime,
        key=key,
        message=message,
        level=level,
        attributes=attributes,
        tags=tags,
        observed_at=observed_at,
    )
    return dispatch_record(runtime, record)


def emit_events(
    runtime: RuntimeSession,
    emissions: Sequence[EventEmission],
) -> BatchCaptureResult:
    """Emit multiple structured events in the active context."""
    results = [
        emit_event(
            runtime,
            key=emission.key,
            message=emission.message,
            level=emission.level,
            attributes=emission.attributes,
            tags=emission.tags,
        )
        for emission in emissions
    ]
    return BatchCaptureResult.from_results(PayloadFamily.RECORD, results)
