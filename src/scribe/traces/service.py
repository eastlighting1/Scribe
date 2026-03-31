"""Trace-like span emission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from scribe.exceptions import ValidationError
from scribe.results import CaptureResult
from scribe.runtime.builders import build_trace_record
from scribe.runtime.dispatch import dispatch_record
from scribe.utils import iso_utc_now

if TYPE_CHECKING:
    from scribe.runtime.session import RuntimeSession


def emit_span(
    runtime: RuntimeSession,
    *,
    name: str,
    started_at: str | None = None,
    ended_at: str | None = None,
    status: str = "ok",
    span_kind: str = "operation",
    attributes: Mapping[str, Any] | None = None,
    linked_refs: Sequence[str] | None = None,
    parent_span_id: str | None = None,
) -> CaptureResult:
    """Emit a trace-like span record."""
    runtime.require_run()

    if not name.strip():
        raise ValidationError("name must not be empty.")

    now = iso_utc_now()
    record = build_trace_record(
        runtime,
        name=name,
        started_at=started_at or now,
        ended_at=ended_at or now,
        status=status,
        span_kind=span_kind,
        attributes=attributes,
        linked_refs=linked_refs,
        parent_span_id=parent_span_id,
    )
    return dispatch_record(runtime, record)
