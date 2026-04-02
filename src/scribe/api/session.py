"""Public session API for Scribe."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scribe.artifacts.service import register_artifact
from scribe.config import ScribeConfig
from scribe.events import EventEmission
from scribe.events.service import emit_event, emit_events
from scribe.exceptions import ContextError
from scribe.metrics import MetricEmission
from scribe.metrics.service import emit_metric, emit_metrics
from scribe.results import BatchCaptureResult, CaptureResult
from scribe.runtime.scopes import OperationScope, RunScope, StageScope
from scribe.runtime.session import RuntimeSession
from scribe.sinks import Sink
from scribe.traces.service import emit_span


class Scribe:
    """High-level SDK entry point for local-first observability capture."""

    def __init__(
        self,
        project_name: str,
        *,
        sinks: Sequence[Sink] | None = None,
        config: ScribeConfig | None = None,
    ) -> None:
        self._runtime = RuntimeSession(
            project_name=project_name,
            sinks=list(sinks or []),
            config=config or ScribeConfig(),
        )

    @property
    def project_name(self) -> str:
        """Return the configured project name."""
        return self._runtime.project_name

    def run(
        self,
        name: str,
        *,
        run_id: str | None = None,
        tags: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        code_revision: str | None = None,
        config_snapshot: Mapping[str, Any] | None = None,
        dataset_ref: str | None = None,
    ) -> RunScope:
        """Create a run scope."""
        return self._runtime.start_run(
            name=name,
            run_id=run_id,
            tags=tags,
            metadata=metadata,
            code_revision=code_revision,
            config_snapshot=config_snapshot,
            dataset_ref=dataset_ref,
        )

    def current_run(self) -> RunScope:
        """Return the current run scope."""
        run_scope = self._runtime.current_run_scope()
        if run_scope is None:
            raise ContextError("No active run scope is available.")
        return run_scope

    def current_stage(self) -> StageScope:
        """Return the current stage scope."""
        stage_scope = self._runtime.current_stage_scope()
        if stage_scope is None:
            raise ContextError("No active stage scope is available.")
        return stage_scope

    def current_operation(self) -> OperationScope:
        """Return the current operation scope."""
        operation_scope = self._runtime.current_operation_scope()
        if operation_scope is None:
            raise ContextError("No active operation scope is available.")
        return operation_scope

    def event(
        self,
        key: str,
        *,
        message: str,
        level: str = "info",
        attributes: Mapping[str, Any] | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> CaptureResult:
        """Emit a structured event in the active context."""
        return emit_event(
            self._runtime,
            key=key,
            message=message,
            level=level,
            attributes=attributes,
            tags=tags,
        )

    def emit_events(self, emissions: Sequence[EventEmission]) -> BatchCaptureResult:
        """Emit multiple structured events in the active context."""
        return emit_events(self._runtime, emissions)

    def metric(
        self,
        key: str,
        value: int | float,
        *,
        unit: str | None = None,
        aggregation_scope: str = "step",
        tags: Mapping[str, str] | None = None,
        summary_basis: str = "raw_observation",
    ) -> CaptureResult:
        """Emit a structured metric in the active context."""
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
        """Emit multiple structured metrics in the active context."""
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
        """Emit a trace-like span in the active context."""
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
        """Register an artifact in the active context."""
        return register_artifact(
            self._runtime,
            artifact_kind=artifact_kind,
            path=path,
            artifact_ref=artifact_ref,
            attributes=attributes,
            compute_hash=compute_hash,
            allow_missing=allow_missing,
        )
