"""Builders for Spine-backed canonical payloads."""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from scribe.exceptions import ValidationError
from scribe.spine_bridge import (
    ArtifactManifest,
    CorrelationRefs,
    EnvironmentSnapshot,
    ExtensionFieldSet,
    METRIC_AGGREGATION_SCOPES,
    MetricPayload,
    MetricRecord,
    OperationContext,
    Project,
    RecordEnvelope,
    Run,
    StableRef,
    StageExecution,
    StructuredEventPayload,
    StructuredEventRecord,
    TraceSpanPayload,
    TraceSpanRecord,
    normalize_timestamp,
    validate_artifact_manifest,
    validate_environment_snapshot,
    validate_metric_record,
    validate_operation_context,
    validate_project,
    validate_run,
    validate_stage_execution,
    validate_structured_event_record,
    validate_trace_span_record,
)
from scribe.utils import iso_utc_now, new_ref, stable_value

if TYPE_CHECKING:
    from scribe.runtime.session import RuntimeSession


_ALLOWED_COMPLETENESS_MARKERS = frozenset({"complete", "partial", "unknown"})
_ALLOWED_DEGRADATION_MARKERS = frozenset(
    {"none", "partial_failure", "capture_gap", "compatibility_upgrade"}
)


def _require_valid(report: Any, label: str) -> None:
    if not report.valid:
        issues = ", ".join(f"{issue.path}: {issue.message}" for issue in report.issues)
        raise ValidationError(f"{label} is invalid: {issues}")


def stable_ref(kind: str, value: str) -> StableRef:
    """Build a Spine stable ref."""
    try:
        return StableRef(kind=kind, value=value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _subject_ref_for_context(runtime: RuntimeSession) -> str | None:
    context = runtime.resolve_context()
    if context.operation_context_ref is not None:
        return str(stable_ref("op", context.operation_context_ref))
    if context.stage_execution_ref is not None:
        return str(stable_ref("stage", context.stage_execution_ref))
    if context.run_ref is not None:
        return str(stable_ref("run", context.run_ref))
    return None


def _reproducibility_extensions(
    *,
    code_revision: str | None,
    config_snapshot_ref: str | None,
    dataset_ref: str | None,
    config_snapshot: Mapping[str, Any] | None = None,
) -> tuple[ExtensionFieldSet, ...]:
    extension_sets: list[ExtensionFieldSet] = []

    reproducibility_fields = {
        key: value
        for key, value in {
            "code_revision": code_revision,
            "config_snapshot_ref": config_snapshot_ref,
            "dataset_ref": dataset_ref,
        }.items()
        if value is not None
    }
    if reproducibility_fields:
        extension_sets.append(
            ExtensionFieldSet(
                namespace="scribe.reproducibility",
                fields=reproducibility_fields,
            )
        )
    if config_snapshot:
        extension_sets.append(
            ExtensionFieldSet(
                namespace="scribe.config_snapshot",
                fields={"snapshot": dict(config_snapshot)},
            )
        )
    return tuple(extension_sets)


def _capture_extensions(
    *,
    tags: Mapping[str, str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[ExtensionFieldSet, ...]:
    extension_sets: list[ExtensionFieldSet] = []
    if tags:
        extension_sets.append(
            ExtensionFieldSet(
                namespace="scribe.capture.tags",
                fields={str(key): value for key, value in tags.items()},
            )
        )
    if metadata:
        extension_sets.append(
            ExtensionFieldSet(
                namespace="scribe.capture.metadata",
                fields=dict(metadata),
            )
        )
    return tuple(extension_sets)


def _combine_extensions(
    *extension_groups: tuple[ExtensionFieldSet, ...],
) -> tuple[ExtensionFieldSet, ...]:
    combined: list[ExtensionFieldSet] = []
    for group in extension_groups:
        combined.extend(group)
    return tuple(combined)


def _context_extensions(runtime: RuntimeSession) -> tuple[ExtensionFieldSet, ...]:
    context = runtime.resolve_context()
    return _reproducibility_extensions(
        code_revision=context.code_revision,
        config_snapshot_ref=context.config_snapshot_ref,
        dataset_ref=context.dataset_ref,
    )


def _normalize_linked_refs(
    runtime: RuntimeSession,
    linked_refs: Sequence[str] | None,
) -> tuple[str, ...]:
    ordered: list[str] = []
    subject_ref = _subject_ref_for_context(runtime)
    if subject_ref is not None:
        ordered.append(subject_ref)
    for linked_ref in linked_refs or ():
        if linked_ref not in ordered:
            ordered.append(linked_ref)
    return tuple(ordered)


def build_envelope(
    runtime: RuntimeSession,
    *,
    record_type: str,
    observed_at: str,
    completeness_marker: str = "complete",
    degradation_marker: str = "none",
    trace_id: str | None = None,
    extensions: tuple[ExtensionFieldSet, ...] | None = None,
) -> RecordEnvelope:
    context = runtime.resolve_context()
    run_ref = context.run_ref
    if run_ref is None:
        raise ValidationError("An active run is required to build a record envelope.")
    if completeness_marker not in _ALLOWED_COMPLETENESS_MARKERS:
        raise ValidationError(f"Unsupported completeness_marker: {completeness_marker}")
    if degradation_marker not in _ALLOWED_DEGRADATION_MARKERS:
        raise ValidationError(f"Unsupported degradation_marker: {degradation_marker}")

    return RecordEnvelope(
        record_ref=stable_ref("record", new_ref("record")),
        record_type=record_type,
        recorded_at=normalize_timestamp(iso_utc_now()),
        observed_at=normalize_timestamp(observed_at),
        producer_ref=runtime.config.producer_ref,
        run_ref=stable_ref("run", run_ref),
        stage_execution_ref=(
            stable_ref("stage", context.stage_execution_ref)
            if context.stage_execution_ref is not None
            else None
        ),
        operation_context_ref=(
            stable_ref("op", context.operation_context_ref)
            if context.operation_context_ref is not None
            else None
        ),
        correlation_refs=CorrelationRefs(
            trace_id=trace_id or context.trace_id,
            session_id=context.session_id,
        ),
        completeness_marker=completeness_marker,
        degradation_marker=degradation_marker,
        extensions=extensions if extensions is not None else _context_extensions(runtime),
    )


def build_event_record(
    runtime: RuntimeSession,
    *,
    key: str,
    message: str,
    level: str,
    attributes: Mapping[str, Any] | None,
    tags: Mapping[str, str] | None,
    observed_at: str,
    completeness_marker: str = "complete",
    degradation_marker: str = "none",
) -> StructuredEventRecord:
    record = StructuredEventRecord(
        envelope=build_envelope(
            runtime,
            record_type="structured_event",
            observed_at=observed_at,
            completeness_marker=completeness_marker,
            degradation_marker=degradation_marker,
            extensions=_combine_extensions(
                _context_extensions(runtime),
                _capture_extensions(tags=tags),
            ),
        ),
        payload=StructuredEventPayload(
            event_key=key,
            level=level,
            message=message,
            subject_ref=_subject_ref_for_context(runtime),
            attributes=dict(attributes or {}),
        ),
    )
    _require_valid(validate_structured_event_record(record), "structured_event_record")
    return record


def build_degradation_record(
    runtime: RuntimeSession,
    *,
    source_family: str,
    degradation_reasons: Sequence[str],
    warnings: Sequence[str],
    observed_at: str,
) -> StructuredEventRecord:
    return build_event_record(
        runtime,
        key="capture.degraded",
        message=f"Capture degraded for {source_family}.",
        level="warning",
        attributes={
            "source_family": source_family,
            "degradation_reasons": list(degradation_reasons),
            "warnings": list(warnings),
        },
        tags=None,
        observed_at=observed_at,
        completeness_marker="partial",
        degradation_marker="partial_failure",
    )


def build_metric_record(
    runtime: RuntimeSession,
    *,
    key: str,
    value: int | float,
    unit: str | None,
    aggregation_scope: str,
    tags: Mapping[str, str] | None,
    summary_basis: str,
    observed_at: str,
) -> MetricRecord:
    if aggregation_scope not in METRIC_AGGREGATION_SCOPES:
        raise ValidationError(f"Unsupported aggregation_scope: {aggregation_scope}")
    value_type = "integer" if isinstance(value, int) else "float"
    record = MetricRecord(
        envelope=build_envelope(
            runtime,
            record_type="metric",
            observed_at=observed_at,
        ),
        payload=MetricPayload(
            metric_key=key,
            value=value,
            value_type=value_type,
            unit=unit,
            aggregation_scope=aggregation_scope,
            subject_ref=_subject_ref_for_context(runtime),
            tags=dict(tags or {}),
            summary_basis=summary_basis,
        ),
    )
    _require_valid(validate_metric_record(record), "metric_record")
    return record


def build_trace_record(
    runtime: RuntimeSession,
    *,
    name: str,
    started_at: str,
    ended_at: str,
    status: str,
    span_kind: str,
    attributes: Mapping[str, Any] | None,
    linked_refs: Sequence[str] | None,
    parent_span_id: str | None = None,
) -> TraceSpanRecord:
    context = runtime.resolve_context()
    trace_id = (
        context.trace_id
        or context.operation_context_ref
        or context.stage_execution_ref
        or context.run_ref
        or new_ref("trace")
    )
    record = TraceSpanRecord(
        envelope=build_envelope(
            runtime,
            record_type="trace_span",
            observed_at=ended_at,
            trace_id=trace_id,
        ),
        payload=TraceSpanPayload(
            span_id=new_ref("span"),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            span_name=name,
            started_at=normalize_timestamp(started_at),
            ended_at=normalize_timestamp(ended_at),
            status=status,
            span_kind=span_kind,
            attributes=dict(attributes or {}),
            linked_refs=_normalize_linked_refs(runtime, linked_refs),
        ),
    )
    _require_valid(validate_trace_span_record(record), "trace_span_record")
    return record


def build_artifact_manifest(
    runtime: RuntimeSession,
    *,
    artifact_ref: str,
    artifact_kind: str,
    location_ref: str,
    hash_value: str | None,
    size_bytes: int | None,
    attributes: Mapping[str, Any] | None,
    created_at: str,
) -> ArtifactManifest:
    context = runtime.resolve_context()
    run_ref = context.run_ref
    if run_ref is None:
        raise ValidationError("An active run is required to build an artifact manifest.")

    manifest = ArtifactManifest(
        artifact_ref=stable_ref("artifact", artifact_ref),
        artifact_kind=artifact_kind,
        created_at=normalize_timestamp(created_at),
        producer_ref=runtime.config.producer_ref,
        run_ref=stable_ref("run", run_ref),
        stage_execution_ref=(
            stable_ref("stage", context.stage_execution_ref)
            if context.stage_execution_ref is not None
            else None
        ),
        location_ref=location_ref,
        hash_value=hash_value,
        size_bytes=size_bytes,
        attributes=dict(attributes or {}),
        extensions=_context_extensions(runtime),
    )
    _require_valid(validate_artifact_manifest(manifest), "artifact_manifest")
    return manifest


def build_project(*, project_name: str, created_at: str) -> Project:
    project = Project(
        project_ref=stable_ref("project", stable_value(project_name)),
        name=project_name,
        created_at=normalize_timestamp(created_at),
    )
    _require_valid(validate_project(project), "project")
    return project


def build_run(
    *,
    project_name: str,
    run_ref: str,
    name: str,
    status: str,
    started_at: str,
    ended_at: str | None,
    code_revision: str | None = None,
    config_snapshot_ref: str | None = None,
    dataset_ref: str | None = None,
    config_snapshot: Mapping[str, Any] | None = None,
    tags: Mapping[str, str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Run:
    run = Run(
        run_ref=stable_ref("run", run_ref),
        project_ref=stable_ref("project", stable_value(project_name)),
        name=name,
        status=status,
        started_at=normalize_timestamp(started_at),
        ended_at=normalize_timestamp(ended_at) if ended_at is not None else None,
        extensions=_combine_extensions(
            _reproducibility_extensions(
                code_revision=code_revision,
                config_snapshot_ref=config_snapshot_ref,
                dataset_ref=dataset_ref,
                config_snapshot=config_snapshot,
            ),
            _capture_extensions(tags=tags, metadata=metadata),
        ),
    )
    _require_valid(validate_run(run), "run")
    return run


def build_stage(
    *,
    run_ref: str,
    stage_ref: str,
    stage_name: str,
    status: str,
    started_at: str,
    ended_at: str | None,
    order_index: int | None,
    metadata: Mapping[str, Any] | None = None,
) -> StageExecution:
    stage = StageExecution(
        stage_execution_ref=stable_ref("stage", stage_ref),
        run_ref=stable_ref("run", run_ref),
        stage_name=stage_name,
        status=status,
        started_at=normalize_timestamp(started_at),
        ended_at=normalize_timestamp(ended_at) if ended_at is not None else None,
        order_index=order_index,
        extensions=_capture_extensions(metadata=metadata),
    )
    _require_valid(validate_stage_execution(stage), "stage_execution")
    return stage


def build_operation(
    *,
    run_ref: str,
    stage_execution_ref: str | None,
    operation_ref: str,
    operation_name: str,
    observed_at: str,
    metadata: Mapping[str, Any] | None = None,
) -> OperationContext:
    operation = OperationContext(
        operation_context_ref=stable_ref("op", operation_ref),
        run_ref=stable_ref("run", run_ref),
        stage_execution_ref=(
            stable_ref("stage", stage_execution_ref)
            if stage_execution_ref is not None
            else None
        ),
        operation_name=operation_name,
        observed_at=normalize_timestamp(observed_at),
        extensions=_capture_extensions(metadata=metadata),
    )
    _require_valid(validate_operation_context(operation), "operation_context")
    return operation


def build_environment_snapshot(
    *,
    run_ref: str,
    captured_at: str,
    capture_installed_packages: bool,
    environment_variable_allowlist: Sequence[str],
    code_revision: str | None = None,
    config_snapshot_ref: str | None = None,
    dataset_ref: str | None = None,
) -> EnvironmentSnapshot:
    packages: dict[str, str] = {}
    if capture_installed_packages:
        try:
            from importlib import metadata as importlib_metadata

            for dist in importlib_metadata.distributions():
                try:
                    name = dist.metadata["Name"]
                except KeyError:
                    continue
                if name:
                    packages[name] = dist.version
        except Exception:
            packages = {}

    environment_variables = {
        key: os.environ[key]
        for key in environment_variable_allowlist
        if key in os.environ
    }

    snapshot = EnvironmentSnapshot(
        environment_snapshot_ref=stable_ref("env", new_ref("env")),
        run_ref=stable_ref("run", run_ref),
        captured_at=normalize_timestamp(captured_at),
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        packages=packages,
        environment_variables=environment_variables,
        extensions=_reproducibility_extensions(
            code_revision=code_revision,
            config_snapshot_ref=config_snapshot_ref,
            dataset_ref=dataset_ref,
        ),
    )
    _require_valid(validate_environment_snapshot(snapshot), "environment_snapshot")
    return snapshot
