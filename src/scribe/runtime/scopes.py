"""Lifecycle scope objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from scribe.artifacts.service import register_artifact
from scribe.events import EventEmission
from scribe.events.service import emit_event, emit_events
from scribe.exceptions import ClosedScopeError
from scribe.metrics import MetricEmission
from scribe.metrics.service import emit_metric, emit_metrics
from scribe.results import BatchCaptureResult, CaptureResult
from scribe.traces.service import emit_span

if TYPE_CHECKING:
    from scribe.runtime.session import RuntimeSession


class BaseScope:
    """Common behavior for lifecycle scopes."""

    def __init__(self, runtime: RuntimeSession, *, scope_kind: str, ref: str, name: str) -> None:
        self._runtime = runtime
        self.scope_kind = scope_kind
        self.ref = ref
        self.name = name
        self._closed = False
        self.started_at: str | None = None

    def _ensure_open(self) -> None:
        if self._closed:
            raise ClosedScopeError(f"{self.scope_kind} scope `{self.name}` is already closed.")

    def close(self, *, status: str = "completed") -> None:
        """Close the active scope."""
        self._ensure_open()
        self._runtime.close_scope(self, status=status)
        self._closed = True

    def event(
        self,
        key: str,
        *,
        message: str,
        level: str = "info",
        attributes: Mapping[str, Any] | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> CaptureResult:
        """Emit a structured event in this scope."""
        self._ensure_open()
        return emit_event(
            self._runtime,
            key=key,
            message=message,
            level=level,
            attributes=attributes,
            tags=tags,
        )

    def emit_events(self, emissions: Sequence[EventEmission]) -> BatchCaptureResult:
        """Emit multiple structured events in this scope."""
        self._ensure_open()
        return emit_events(self._runtime, emissions)

    def metric(
        self,
        key: str,
        value: int | float,
        *,
        unit: str | None = None,
        aggregation_scope: str = "point",
        tags: Mapping[str, str] | None = None,
        summary_basis: str = "raw_observation",
    ) -> CaptureResult:
        """Emit a metric in this scope."""
        self._ensure_open()
        return emit_metric(
            self._runtime,
            key=key,
            value=value,
            unit=unit,
            aggregation_scope=aggregation_scope,
            tags=tags,
            summary_basis=summary_basis,
        )

    def emit_metrics(self, emissions: Sequence[MetricEmission]) -> BatchCaptureResult:
        """Emit multiple structured metrics in this scope."""
        self._ensure_open()
        return emit_metrics(self._runtime, emissions)

    def span(
        self,
        name: str,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
        status: str = "ok",
        span_kind: str = "operation",
        attributes: Mapping[str, Any] | None = None,
        linked_refs: Sequence[str] | None = None,
        parent_span_id: str | None = None,
    ) -> CaptureResult:
        """Emit a trace-like span in this scope."""
        self._ensure_open()
        return emit_span(
            self._runtime,
            name=name,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            span_kind=span_kind,
            attributes=attributes,
            linked_refs=linked_refs,
            parent_span_id=parent_span_id,
        )

    def register_artifact(
        self,
        artifact_kind: str,
        path: str | Path,
        *,
        artifact_ref: str | None = None,
        attributes: Mapping[str, Any] | None = None,
        compute_hash: bool = True,
        allow_missing: bool = False,
    ) -> CaptureResult:
        """Register an artifact in this scope."""
        self._ensure_open()
        return register_artifact(
            self._runtime,
            artifact_kind=artifact_kind,
            path=path,
            artifact_ref=artifact_ref,
            attributes=attributes,
            compute_hash=compute_hash,
            allow_missing=allow_missing,
        )


class RunScope(BaseScope):
    """Run lifecycle scope."""

    def __init__(
        self,
        runtime: RuntimeSession,
        *,
        scope_kind: str,
        ref: str,
        name: str,
        code_revision: str | None = None,
        config_snapshot_ref: str | None = None,
        config_snapshot: Mapping[str, Any] | None = None,
        dataset_ref: str | None = None,
        tags: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(runtime, scope_kind=scope_kind, ref=ref, name=name)
        self.code_revision = code_revision
        self.config_snapshot_ref = config_snapshot_ref
        self.config_snapshot = dict(config_snapshot) if config_snapshot is not None else None
        self.dataset_ref = dataset_ref
        self.tags = dict(tags or {})
        self.metadata = dict(metadata or {})

    def __enter__(self) -> RunScope:
        self._runtime.enter_scope(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, tb
        self.close(status="failed" if exc is not None else "completed")

    def stage(
        self,
        name: str,
        *,
        stage_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> StageScope:
        """Create a stage scope under this run."""
        self._ensure_open()
        return self._runtime.start_stage(name=name, stage_ref=stage_ref, metadata=metadata)


class StageScope(BaseScope):
    """Stage lifecycle scope."""

    def __init__(
        self,
        runtime: RuntimeSession,
        *,
        scope_kind: str,
        ref: str,
        name: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(runtime, scope_kind=scope_kind, ref=ref, name=name)
        self.order_index: int | None = None
        self.metadata = dict(metadata or {})

    def __enter__(self) -> StageScope:
        self._runtime.enter_scope(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, tb
        self.close(status="failed" if exc is not None else "completed")

    def operation(
        self,
        name: str,
        *,
        operation_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> OperationScope:
        """Create an operation scope under this stage."""
        self._ensure_open()
        return self._runtime.start_operation(
            name=name,
            operation_ref=operation_ref,
            metadata=metadata,
        )


class OperationScope(BaseScope):
    """Fine-grained operation lifecycle scope."""

    def __init__(
        self,
        runtime: RuntimeSession,
        *,
        scope_kind: str,
        ref: str,
        name: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(runtime, scope_kind=scope_kind, ref=ref, name=name)
        self.observed_at: str | None = None
        self.metadata = dict(metadata or {})

    def __enter__(self) -> OperationScope:
        self._runtime.enter_scope(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, tb
        self.close(status="failed" if exc is not None else "completed")
