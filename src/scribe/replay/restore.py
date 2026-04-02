"""Restore typed payload objects from durable outbox entries."""

from __future__ import annotations

from typing import Any

from scribe.artifacts.models import (
    ArtifactBinding,
    ArtifactBindingStatus,
    ArtifactRegistrationRequest,
    ArtifactSource,
    ArtifactSourceKind,
    ArtifactVerificationPolicy,
)
from scribe.spine_bridge import (
    ArtifactManifest,
    CorrelationRefs,
    EnvironmentSnapshot,
    ExtensionFieldSet,
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
)


def _ref(value: str | None) -> StableRef | None:
    if value is None:
        return None
    return StableRef.parse(value)


def _extensions(raw: list[dict[str, Any]] | None) -> tuple[ExtensionFieldSet, ...]:
    entries = raw or []
    return tuple(
        ExtensionFieldSet(namespace=entry["namespace"], fields=dict(entry.get("fields", {})))
        for entry in entries
    )


def _project(payload: dict[str, Any]) -> Project:
    return Project(
        project_ref=StableRef.parse(payload["project_ref"]),
        name=payload["name"],
        created_at=payload["created_at"],
        description=payload.get("description"),
        tags=dict(payload.get("tags", {})),
        schema_version=payload["schema_version"],
        extensions=_extensions(payload.get("extensions")),
    )


def _run(payload: dict[str, Any]) -> Run:
    return Run(
        run_ref=StableRef.parse(payload["run_ref"]),
        project_ref=StableRef.parse(payload["project_ref"]),
        name=payload["name"],
        status=payload["status"],
        started_at=payload["started_at"],
        ended_at=payload.get("ended_at"),
        description=payload.get("description"),
        schema_version=payload["schema_version"],
        extensions=_extensions(payload.get("extensions")),
    )


def _stage(payload: dict[str, Any]) -> StageExecution:
    return StageExecution(
        stage_execution_ref=StableRef.parse(payload["stage_execution_ref"]),
        run_ref=StableRef.parse(payload["run_ref"]),
        stage_name=payload["stage_name"],
        status=payload["status"],
        started_at=payload["started_at"],
        ended_at=payload.get("ended_at"),
        order_index=payload.get("order_index"),
        schema_version=payload["schema_version"],
        extensions=_extensions(payload.get("extensions")),
    )


def _operation(payload: dict[str, Any]) -> OperationContext:
    return OperationContext(
        operation_context_ref=StableRef.parse(payload["operation_context_ref"]),
        run_ref=StableRef.parse(payload["run_ref"]),
        stage_execution_ref=_ref(payload.get("stage_execution_ref")),
        operation_name=payload["operation_name"],
        observed_at=payload["observed_at"],
        schema_version=payload["schema_version"],
        extensions=_extensions(payload.get("extensions")),
    )


def _environment(payload: dict[str, Any]) -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        environment_snapshot_ref=StableRef.parse(payload["environment_snapshot_ref"]),
        run_ref=StableRef.parse(payload["run_ref"]),
        captured_at=payload["captured_at"],
        python_version=payload["python_version"],
        platform=payload["platform"],
        packages=dict(payload.get("packages", {})),
        environment_variables=dict(payload.get("environment_variables", {})),
        schema_version=payload["schema_version"],
        extensions=_extensions(payload.get("extensions")),
    )


def _artifact_manifest(payload: dict[str, Any]) -> ArtifactManifest:
    return ArtifactManifest(
        artifact_ref=StableRef.parse(payload["artifact_ref"]),
        artifact_kind=payload["artifact_kind"],
        created_at=payload["created_at"],
        producer_ref=payload["producer_ref"],
        run_ref=StableRef.parse(payload["run_ref"]),
        stage_execution_ref=_ref(payload.get("stage_execution_ref")),
        location_ref=payload["location_ref"],
        hash_value=payload.get("hash_value"),
        size_bytes=payload.get("size_bytes"),
        attributes=dict(payload.get("attributes", {})),
        schema_version=payload["schema_version"],
        extensions=_extensions(payload.get("extensions")),
    )


def _correlation_refs(payload: dict[str, Any]) -> CorrelationRefs:
    return CorrelationRefs(
        trace_id=payload.get("trace_id"),
        session_id=payload.get("session_id"),
    )


def _envelope(payload: dict[str, Any]) -> RecordEnvelope:
    return RecordEnvelope(
        record_ref=StableRef.parse(payload["record_ref"]),
        record_type=payload["record_type"],
        recorded_at=payload["recorded_at"],
        observed_at=payload["observed_at"],
        producer_ref=payload["producer_ref"],
        run_ref=StableRef.parse(payload["run_ref"]),
        stage_execution_ref=_ref(payload.get("stage_execution_ref")),
        operation_context_ref=_ref(payload.get("operation_context_ref")),
        correlation_refs=_correlation_refs(payload.get("correlation_refs", {})),
        completeness_marker=payload.get("completeness_marker", "complete"),
        degradation_marker=payload.get("degradation_marker", "none"),
        schema_version=payload["schema_version"],
        extensions=_extensions(payload.get("extensions")),
    )


def _structured_event_record(payload: dict[str, Any]) -> StructuredEventRecord:
    body = payload["payload"]
    return StructuredEventRecord(
        envelope=_envelope(payload["envelope"]),
        payload=StructuredEventPayload(
            event_key=body["event_key"],
            level=body["level"],
            message=body["message"],
            subject_ref=body.get("subject_ref"),
            attributes=dict(body.get("attributes", {})),
            origin_marker=body.get("origin_marker", "explicit_capture"),
        ),
    )


def _metric_record(payload: dict[str, Any]) -> MetricRecord:
    body = payload["payload"]
    return MetricRecord(
        envelope=_envelope(payload["envelope"]),
        payload=MetricPayload(
            metric_key=body["metric_key"],
            value=body["value"],
            value_type=body["value_type"],
            unit=body.get("unit"),
            aggregation_scope=body.get("aggregation_scope", "step"),
            subject_ref=body.get("subject_ref"),
            slice_ref=body.get("slice_ref"),
            tags=dict(body.get("tags", {})),
            summary_basis=body.get("summary_basis"),
        ),
    )


def _trace_span_record(payload: dict[str, Any]) -> TraceSpanRecord:
    body = payload["payload"]
    return TraceSpanRecord(
        envelope=_envelope(payload["envelope"]),
        payload=TraceSpanPayload(
            span_id=body["span_id"],
            trace_id=body["trace_id"],
            parent_span_id=body.get("parent_span_id"),
            span_name=body["span_name"],
            started_at=body["started_at"],
            ended_at=body["ended_at"],
            status=body["status"],
            span_kind=body["span_kind"],
            attributes=dict(body.get("attributes", {})),
            linked_refs=tuple(body.get("linked_refs", ())),
        ),
    )


def _artifact_binding(payload: dict[str, Any]) -> ArtifactBinding:
    request = payload["request"]
    source = request["source"]
    verification_policy = request["verification_policy"]
    restored_source = ArtifactSource(
        kind=ArtifactSourceKind(source["kind"]),
        uri=source["uri"],
        exists=source["exists"],
    )
    return ArtifactBinding(
        request=ArtifactRegistrationRequest(
            artifact_ref=request["artifact_ref"],
            artifact_kind=request["artifact_kind"],
            source=restored_source,
            verification_policy=ArtifactVerificationPolicy(
                compute_hash=verification_policy["compute_hash"],
                require_existing_source=verification_policy["require_existing_source"],
            ),
            attributes=dict(request.get("attributes", {})),
        ),
        manifest=_artifact_manifest(payload["manifest"]),
        source=ArtifactSource(
            kind=ArtifactSourceKind(payload["source"]["kind"]),
            uri=payload["source"]["uri"],
            exists=payload["source"]["exists"],
        ),
        project_name=payload["project_name"],
        operation_context_ref=payload.get("operation_context_ref"),
        binding_status=ArtifactBindingStatus(payload["binding_status"]),
        completeness_marker=payload.get("completeness_marker", "complete"),
        degradation_marker=payload.get("degradation_marker", "none"),
        attributes=dict(payload.get("attributes", {})),
    )


_RESTORERS: dict[str, Any] = {
    "Project": _project,
    "Run": _run,
    "StageExecution": _stage,
    "OperationContext": _operation,
    "EnvironmentSnapshot": _environment,
    "StructuredEventRecord": _structured_event_record,
    "MetricRecord": _metric_record,
    "TraceSpanRecord": _trace_span_record,
    "ArtifactBinding": _artifact_binding,
    "ArtifactManifest": _artifact_manifest,
}


def restore_payload(payload_type: str, payload: dict[str, Any]) -> Any:
    """Restore a typed payload object from a json-ready outbox payload."""
    restorer = _RESTORERS.get(payload_type)
    if restorer is None:
        return payload
    return restorer(payload)
