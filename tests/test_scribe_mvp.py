from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scribe import (
    ArtifactBindingStatus,
    ArtifactSourceKind,
    ContextError,
    DeliveryStatus,
    EventEmission,
    InMemorySink,
    LocalJsonlSink,
    MetricEmission,
    PayloadFamily,
    Scribe,
    SinkDispatchError,
    ValidationError,
)
from scribe.sinks import Sink
from scribe.spine_bridge import (
    ArtifactManifest,
    EnvironmentSnapshot,
    MetricRecord,
    OperationContext,
    Project,
    Run,
    StageExecution,
    StructuredEventRecord,
    TraceSpanRecord,
)


class FailingSink(Sink):
    name = "failing"
    supported_families = frozenset(PayloadFamily)

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        raise RuntimeError(f"cannot store {family}")


class RecordOnlySink(Sink):
    name = "record-only"
    supported_families = frozenset({PayloadFamily.RECORD})

    def __init__(self) -> None:
        self.actions: list[tuple[PayloadFamily, Any]] = []

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        self.actions.append((family, payload))


def test_lifecycle_golden_flow_sequence(tmp_path: Path) -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run("training") as run:
        with run.stage("train") as stage:
            with stage.operation("forward") as operation:
                operation.event("operation.note", message="forward step captured")
            stage.metric("training.loss", 0.42, aggregation_scope="step")
            stage.register_artifact("checkpoint", artifact_path)

    action_sequence = [
        (
            family.value,
            type(payload).__name__,
            payload.payload.event_key if isinstance(payload, StructuredEventRecord) else None,
        )
        for family, payload in sink.actions
    ]
    assert action_sequence == [
        ("context", "Project", None),
        ("context", "Run", None),
        ("context", "EnvironmentSnapshot", None),
        ("record", "StructuredEventRecord", "run.started"),
        ("context", "StageExecution", None),
        ("record", "StructuredEventRecord", "stage.started"),
        ("context", "OperationContext", None),
        ("record", "StructuredEventRecord", "operation.started"),
        ("record", "StructuredEventRecord", "operation.note"),
        ("record", "StructuredEventRecord", "operation.completed"),
        ("record", "MetricRecord", None),
        ("artifact", "ArtifactBinding", None),
        ("record", "StructuredEventRecord", "stage.completed"),
        ("context", "StageExecution", None),
        ("record", "StructuredEventRecord", "run.completed"),
        ("context", "Run", None),
    ]


def test_run_stage_operation_capture_flow(tmp_path: Path) -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run("training") as run:
        event_result = run.event("run.started", message="Training run started.")
        with run.stage("train") as stage:
            metric_result = stage.metric("training.loss", 0.42, aggregation_scope="step")
            with stage.operation("forward") as operation:
                span_result = operation.span("model.forward", span_kind="model_call")
            artifact_result = stage.register_artifact("checkpoint", artifact_path)

    assert event_result.status == DeliveryStatus.SUCCESS
    assert metric_result.status == DeliveryStatus.SUCCESS
    assert span_result.status == DeliveryStatus.SUCCESS
    assert artifact_result.status == DeliveryStatus.SUCCESS
    assert len(sink.actions) == 17

    context_payloads = [
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.CONTEXT
    ]
    record_payloads = [
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD
    ]
    artifact_payloads = [
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.ARTIFACT
    ]

    assert any(isinstance(payload, Project) for payload in context_payloads)
    assert any(isinstance(payload, EnvironmentSnapshot) for payload in context_payloads)
    assert sum(isinstance(payload, Run) for payload in context_payloads) == 2
    assert sum(isinstance(payload, StageExecution) for payload in context_payloads) == 2
    assert any(isinstance(payload, OperationContext) for payload in context_payloads)
    assert len(artifact_payloads) == 1

    metric_records = [payload for payload in record_payloads if isinstance(payload, MetricRecord)]
    assert len(metric_records) == 1
    record = metric_records[0]
    assert isinstance(record, MetricRecord)
    assert record.envelope.record_type == "metric"
    assert str(record.envelope.run_ref).startswith("run:")
    assert record.envelope.stage_execution_ref is not None

    lifecycle_keys = {
        payload.payload.event_key
        for payload in record_payloads
        if isinstance(payload, StructuredEventRecord)
    }
    assert {
        "run.started",
        "run.completed",
        "stage.started",
        "stage.completed",
        "operation.started",
        "operation.completed",
    } <= lifecycle_keys


def test_emit_without_run_raises_context_error() -> None:
    scribe = Scribe(project_name="demo-project")

    with pytest.raises(ContextError):
        scribe.event("orphan.event", message="This should fail.")


def test_partial_sink_failure_is_reported_as_degraded() -> None:
    memory = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[memory, FailingSink()])

    with scribe.run("training") as run:
        result = run.event("run.started", message="Training run started.")

    assert result.status == DeliveryStatus.DEGRADED
    assert result.family == PayloadFamily.RECORD
    assert result.succeeded is True
    assert result.degradation_emitted is True
    assert any(reason.startswith("sink_failure:failing") for reason in result.degradation_reasons)
    assert any(isinstance(payload, StructuredEventRecord) for _, payload in memory.actions)
    assert any(
        family == PayloadFamily.DEGRADATION and isinstance(payload, StructuredEventRecord)
        for family, payload in memory.actions
    )


def test_all_sink_failures_raise_dispatch_error() -> None:
    scribe = Scribe(project_name="demo-project", sinks=[FailingSink()])

    with pytest.raises(SinkDispatchError):
        with scribe.run("training"):
            pass


def test_missing_artifact_can_be_registered_as_degraded(tmp_path: Path) -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    missing_path = tmp_path / "missing.ckpt"

    with scribe.run("training") as run:
        result = run.register_artifact("checkpoint", missing_path, allow_missing=True)

    assert result.status == DeliveryStatus.DEGRADED
    family, binding = next(
        (family, payload)
        for family, payload in sink.actions
        if family == PayloadFamily.ARTIFACT
    )
    assert family == PayloadFamily.ARTIFACT
    assert isinstance(binding.manifest, ArtifactManifest)
    assert binding.degradation_marker == "degraded"
    assert binding.manifest.artifact_kind == "checkpoint"
    assert binding.request.source.kind == ArtifactSourceKind.PATH
    assert binding.request.verification_policy.require_existing_source is False
    assert binding.binding_status == ArtifactBindingStatus.DEGRADED
    assert result.degradation_emitted is True


def test_degradation_family_record_is_emitted_for_artifact_gap(tmp_path: Path) -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    missing_path = tmp_path / "missing.ckpt"

    with scribe.run("training") as run:
        result = run.register_artifact("checkpoint", missing_path, allow_missing=True)

    assert result.status == DeliveryStatus.DEGRADED
    degradation_records = [
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.DEGRADATION
    ]
    assert len(degradation_records) == 1
    degradation_record = degradation_records[0]
    assert isinstance(degradation_record, StructuredEventRecord)
    assert degradation_record.payload.event_key == "capture.degraded"


def test_unsupported_family_degradation_is_written_to_local_sink(tmp_path: Path) -> None:
    sink = LocalJsonlSink(tmp_path / "scribe-store")
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    missing_path = tmp_path / "missing.ckpt"

    with scribe.run("training") as run:
        result = run.register_artifact("checkpoint", missing_path, allow_missing=True)

    assert result.status == DeliveryStatus.DEGRADED
    degradation_entries = sink.read_family(PayloadFamily.DEGRADATION)
    assert len(degradation_entries) == 1
    assert degradation_entries[0]["payload"]["payload"]["event_key"] == "capture.degraded"


def test_artifact_binding_exposes_vendor_agnostic_request_fields(tmp_path: Path) -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run("training") as run:
        result = run.register_artifact("checkpoint", artifact_path, compute_hash=False)

    assert result.status == DeliveryStatus.SUCCESS
    _, binding = next(
        (family, payload)
        for family, payload in sink.actions
        if family == PayloadFamily.ARTIFACT
    )
    assert binding.request.artifact_kind == "checkpoint"
    assert binding.request.source.kind == ArtifactSourceKind.PATH
    assert binding.request.verification_policy.compute_hash is False
    assert binding.binding_status == ArtifactBindingStatus.BOUND


def test_record_and_artifact_contract_shapes_are_stable(tmp_path: Path) -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "report.json"
    artifact_path.write_text('{"ok": true}', encoding="utf-8")

    with scribe.run(
        "evaluation",
        code_revision="commit-123",
        config_snapshot={"threshold": 0.8},
        dataset_ref="validation-split",
    ) as run:
        event_result = run.event("evaluation.started", message="evaluation started")
        metric_result = run.metric("eval.accuracy", 0.91, aggregation_scope="dataset")
        span_result = run.span("evaluator.forward", span_kind="model_call")
        artifact_result = run.register_artifact("evaluation-report", artifact_path)

    assert event_result.status == DeliveryStatus.SUCCESS
    assert metric_result.status == DeliveryStatus.SUCCESS
    assert span_result.status == DeliveryStatus.SUCCESS
    assert artifact_result.status == DeliveryStatus.SUCCESS

    event_record = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD
        and isinstance(payload, StructuredEventRecord)
        and payload.payload.event_key == "evaluation.started"
    )
    metric_record = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD and isinstance(payload, MetricRecord)
    )
    span_record = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD and isinstance(payload, TraceSpanRecord)
    )
    _, binding = next(
        (family, payload)
        for family, payload in sink.actions
        if family == PayloadFamily.ARTIFACT
    )

    assert event_record.envelope.record_type == "structured_event"
    assert event_record.payload.subject_ref == "run:" + str(event_record.envelope.run_ref.value)
    assert metric_record.payload.aggregation_scope == "dataset"
    assert metric_record.payload.value_type == "float"
    assert span_record.envelope.correlation_refs.trace_id is not None
    assert binding.request.artifact_kind == "evaluation-report"
    assert binding.request.source.kind == ArtifactSourceKind.PATH
    assert binding.manifest.hash_value is not None
    assert binding.manifest.size_bytes is not None


def test_unsupported_family_is_skipped_without_forcing_failure(tmp_path: Path) -> None:
    sink = RecordOnlySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run("training") as run:
        result = run.register_artifact("checkpoint", artifact_path)

    assert result.status == DeliveryStatus.DEGRADED
    assert result.family == PayloadFamily.ARTIFACT
    assert any(
        reason.startswith("no_sink_support_for_family:artifact")
        for reason in result.degradation_reasons
    )
    assert all(family != PayloadFamily.ARTIFACT for family, _ in sink.actions)
    assert any(delivery.status == DeliveryStatus.SKIPPED for delivery in result.deliveries)


def test_span_emits_spine_trace_record() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        with run.stage("train") as stage:
            result = stage.span("model.forward", span_kind="model_call")

    assert result.status == DeliveryStatus.SUCCESS
    family, payload = next(
        (family, payload)
        for family, payload in sink.actions
        if isinstance(payload, TraceSpanRecord)
    )
    assert family == PayloadFamily.RECORD
    assert isinstance(payload, TraceSpanRecord)
    assert payload.envelope.record_type == "trace_span"


def test_local_jsonl_sink_persists_families_to_disk(tmp_path: Path) -> None:
    sink = LocalJsonlSink(tmp_path / "scribe-store")
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run("training") as run:
        run.event("run.started", message="Training run started.")
        run.register_artifact("checkpoint", artifact_path)

    context_entries = sink.read_family(PayloadFamily.CONTEXT)
    record_entries = sink.read_family(PayloadFamily.RECORD)
    artifact_entries = sink.read_family(PayloadFamily.ARTIFACT)

    assert context_entries
    assert record_entries
    assert artifact_entries
    assert sink.path_for(PayloadFamily.CONTEXT).exists()
    assert sink.path_for(PayloadFamily.RECORD).exists()
    assert sink.path_for(PayloadFamily.ARTIFACT).exists()
    assert context_entries[0]["family"] == "context"


def test_local_jsonl_sink_supports_reopen_and_readback(tmp_path: Path) -> None:
    storage_root = tmp_path / "scribe-store"
    sink = LocalJsonlSink(storage_root)
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        run.event("run.note", message="first capture")

    reopened = LocalJsonlSink(storage_root)
    record_entries = reopened.read_family(PayloadFamily.RECORD)

    assert record_entries
    assert any(
        entry["payload"]["payload"]["event_key"] == "run.note"
        for entry in record_entries
    )


def test_batch_event_capture_returns_aggregated_success() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        result = run.emit_events(
            [
                EventEmission("batch.first", "first event"),
                EventEmission("batch.second", "second event", level="warning"),
            ]
        )

    assert result.status == DeliveryStatus.SUCCESS
    assert result.total_count == 2
    assert result.success_count == 2
    assert result.degraded_count == 0
    event_keys = [
        payload.payload.event_key
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD and isinstance(payload, StructuredEventRecord)
    ]
    assert "batch.first" in event_keys
    assert "batch.second" in event_keys


def test_batch_metric_capture_reports_partial_success() -> None:
    memory = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[memory, FailingSink()])

    with scribe.run("training") as run:
        result = run.emit_metrics(
            [
                MetricEmission("training.loss", 0.42, aggregation_scope="step"),
                MetricEmission("training.accuracy", 0.91, aggregation_scope="epoch"),
            ]
        )

    assert result.status == DeliveryStatus.DEGRADED
    assert result.total_count == 2
    assert result.success_count == 0
    assert result.degraded_count == 2
    assert result.failure_count == 0
    metric_records = [
        payload
        for family, payload in memory.actions
        if family == PayloadFamily.RECORD and isinstance(payload, MetricRecord)
    ]
    assert len(metric_records) == 2


def test_run_reproducibility_metadata_flows_into_context_record_and_artifact(
    tmp_path: Path,
) -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run(
        "training",
        code_revision="abc123def",
        config_snapshot={"lr": 0.001, "batch_size": 32},
        dataset_ref="imagenet-v1",
    ) as run:
        metric_result = run.metric("training.loss", 0.42, aggregation_scope="step")
        artifact_result = run.register_artifact("checkpoint", artifact_path)

    assert metric_result.status == DeliveryStatus.SUCCESS
    assert artifact_result.status == DeliveryStatus.SUCCESS

    run_payloads = [
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.CONTEXT and isinstance(payload, Run)
    ]
    assert run_payloads
    run_extensions = {
        extension.namespace: extension.fields
        for extension in run_payloads[0].extensions
    }
    assert run_extensions["scribe.reproducibility"]["code_revision"] == "abc123def"
    assert run_extensions["scribe.reproducibility"]["dataset_ref"] == "imagenet-v1"
    assert "config_snapshot_ref" in run_extensions["scribe.reproducibility"]
    assert run_extensions["scribe.config_snapshot"]["snapshot"] == {"batch_size": 32, "lr": 0.001}

    metric_record = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD and isinstance(payload, MetricRecord)
    )
    metric_extensions = {
        extension.namespace: extension.fields
        for extension in metric_record.envelope.extensions
    }
    assert metric_record.payload.subject_ref is not None
    assert metric_record.payload.subject_ref.startswith("run:")
    assert metric_extensions["scribe.reproducibility"]["code_revision"] == "abc123def"

    _, binding = next(
        (family, payload)
        for family, payload in sink.actions
        if family == PayloadFamily.ARTIFACT
    )
    artifact_extensions = {
        extension.namespace: extension.fields
        for extension in binding.manifest.extensions
    }
    assert artifact_extensions["scribe.reproducibility"]["dataset_ref"] == "imagenet-v1"


def test_run_tags_and_metadata_are_preserved_in_run_extensions() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run(
        "training",
        tags={"team": "ml-platform"},
        metadata={"owner": "scribe", "priority": 1},
    ):
        pass

    run_payload = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.CONTEXT and isinstance(payload, Run)
    )
    extensions = {extension.namespace: extension.fields for extension in run_payload.extensions}
    assert extensions["scribe.capture.tags"] == {"team": "ml-platform"}
    assert extensions["scribe.capture.metadata"] == {"owner": "scribe", "priority": 1}


def test_stage_and_operation_metadata_are_preserved_in_extensions() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        with run.stage("train", metadata={"dataset": "imagenet"}) as stage:
            with stage.operation("forward", metadata={"batch_size": 32}):
                pass

    stage_payload = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.CONTEXT and isinstance(payload, StageExecution)
    )
    operation_payload = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.CONTEXT and isinstance(payload, OperationContext)
    )
    stage_extensions = {
        extension.namespace: extension.fields for extension in stage_payload.extensions
    }
    operation_extensions = {
        extension.namespace: extension.fields for extension in operation_payload.extensions
    }
    assert stage_extensions["scribe.capture.metadata"] == {"dataset": "imagenet"}
    assert operation_extensions["scribe.capture.metadata"] == {"batch_size": 32}


def test_event_tags_are_preserved_in_record_envelope_extensions() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        run.event("run.note", message="captured", tags={"phase": "warmup"})

    event_record = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD
        and isinstance(payload, StructuredEventRecord)
        and payload.payload.event_key == "run.note"
    )
    extensions = {
        extension.namespace: extension.fields for extension in event_record.envelope.extensions
    }
    assert extensions["scribe.capture.tags"] == {"phase": "warmup"}


def test_current_scope_apis_follow_task_local_context() -> None:
    import asyncio

    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    observed: dict[str, str] = {}

    async def capture(label: str) -> None:
        with scribe.run(label) as run:
            await asyncio.sleep(0)
            observed[label] = scribe.current_run().name
            assert run is scribe.current_run()

    async def main() -> None:
        await asyncio.gather(capture("first"), capture("second"))

    asyncio.run(main())

    assert observed == {"first": "first", "second": "second"}


def test_invalid_metric_aggregation_scope_is_rejected() -> None:
    scribe = Scribe(project_name="demo-project", sinks=[InMemorySink()])

    with scribe.run("training") as run:
        with pytest.raises(ValidationError):
            run.metric("training.loss", 0.42, aggregation_scope="nonsense")


def test_span_allows_explicit_parent_and_context_linked_refs() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        with run.stage("train") as stage:
            result = stage.span(
                "model.forward",
                span_kind="model_call",
                parent_span_id="span_parent_123",
                linked_refs=["artifact:model.ckpt"],
            )

    assert result.status == DeliveryStatus.SUCCESS
    trace_record = next(
        payload
        for family, payload in sink.actions
        if family == PayloadFamily.RECORD and isinstance(payload, TraceSpanRecord)
    )
    assert trace_record.payload.parent_span_id == "span_parent_123"
    assert "artifact:model.ckpt" in trace_record.payload.linked_refs
    assert any(linked_ref.startswith("stage:") for linked_ref in trace_record.payload.linked_refs)
