# API Reference

[User Guide Home](../USER_GUIDE.en.md)

This page is a single reference document that collects the public API exposed through `import scribe`
and its documented public submodules in one place.

## Package Entry Points

The public import surface is defined by
[src/scribe/__init__.py](../../src/scribe/__init__.py)
and public submodule `__init__.py` files such as
[src/scribe/config/__init__.py](../../src/scribe/config/__init__.py),
[src/scribe/results/__init__.py](../../src/scribe/results/__init__.py),
[src/scribe/artifacts/__init__.py](../../src/scribe/artifacts/__init__.py),
and [src/scribe/sinks/__init__.py](../../src/scribe/sinks/__init__.py).

Public import paths:

- `scribe`
- `scribe.api`
- `scribe.config`
- `scribe.events`
- `scribe.metrics`
- `scribe.results`
- `scribe.artifacts`
- `scribe.sinks`

Not every internal package under `src/scribe` is a public API module. Packages such as `runtime`,
`context`, and `traces` are implementation packages rather than documented import surfaces.

## Session API

### `scribe.Scribe`

`Scribe(project_name, *, sinks=None, config=None)`

Top-level SDK entry point for local-first observability capture.

Parameters:

- `project_name`: logical project name attached to emitted payloads
- `sinks`: optional sequence of sink instances
- `config`: optional `ScribeConfig`

Returns:

- `Scribe`

Example:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="nova-vision",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)
```

See also:

- `scribe.Scribe.run`
- `scribe.config.ScribeConfig`
- `scribe.LocalJsonlSink`

### `scribe.Scribe.project_name`

`Scribe.project_name`

Configured project name for the session.

Returns:

- `str`

### `scribe.Scribe.run`

`Scribe.run(name, *, run_id=None, tags=None, metadata=None, code_revision=None, config_snapshot=None, dataset_ref=None)`

Create a run scope.

Parameters:

- `name`: human-readable run name
- `run_id`: optional explicit run reference
- `tags`: optional run-level tags
- `metadata`: optional run-level metadata
- `code_revision`: optional source revision identifier
- `config_snapshot`: optional structured configuration snapshot
- `dataset_ref`: optional dataset reference

Returns:

- `RunScope`

Example:

```python
with scribe.run(
    "baseline-train",
    code_revision="commit-123",
    dataset_ref="imagenet-v1",
    tags={"suite": "baseline"},
) as run:
    ...
```

See also:

- `scribe.RunScope`
- `scribe.Scribe.current_run`

### `scribe.Scribe.current_run`

`Scribe.current_run()`

Return the current active run scope.

Returns:

- `RunScope`

Raises:

- `ContextError`: raised when no active run scope is available

### `scribe.Scribe.current_stage`

`Scribe.current_stage()`

Return the current active stage scope.

Returns:

- `StageScope`

Raises:

- `ContextError`: raised when no active stage scope is available

### `scribe.Scribe.current_operation`

`Scribe.current_operation()`

Return the current active operation scope.

Returns:

- `OperationScope`

Raises:

- `ContextError`: raised when no active operation scope is available

### `scribe.Scribe.event`

`Scribe.event(key, *, message, level="info", attributes=None, tags=None)`

Emit a structured event in the active context.

Parameters:

- `key`
- `message`
- `level`
- `attributes`
- `tags`

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

See also:

- `scribe.EventEmission`
- `scribe.RunScope`

### `scribe.Scribe.emit_events`

`Scribe.emit_events(emissions)`

Emit multiple structured events in the active context.

Parameters:

- `emissions`: sequence of `EventEmission`

Returns:

- `BatchCaptureResult`

### `scribe.Scribe.metric`

`Scribe.metric(key, value, *, unit=None, aggregation_scope="step", tags=None, summary_basis="raw_observation")`

Emit a structured metric in the active context.

Parameters:

- `key`
- `value`
- `unit`
- `aggregation_scope`
- `tags`
- `summary_basis`

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

See also:

- `scribe.MetricEmission`
- `scribe.BatchCaptureResult`

### `scribe.Scribe.emit_metrics`

`Scribe.emit_metrics(emissions)`

Emit multiple structured metrics in the active context.

Parameters:

- `emissions`: sequence of `MetricEmission`

Returns:

- `BatchCaptureResult`

### `scribe.Scribe.span`

`Scribe.span(name, *, started_at=None, ended_at=None, status="ok", span_kind="operation", attributes=None, linked_refs=None, parent_span_id=None)`

Emit a trace-like span record in the active context.

Parameters:

- `name`
- `started_at`
- `ended_at`
- `status`
- `span_kind`
- `attributes`
- `linked_refs`
- `parent_span_id`

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

### `scribe.Scribe.register_artifact`

`Scribe.register_artifact(artifact_kind, path, *, artifact_ref=None, attributes=None, compute_hash=True, allow_missing=False)`

Register an artifact in the active context.

Parameters:

- `artifact_kind`
- `path`
- `artifact_ref`
- `attributes`
- `compute_hash`
- `allow_missing`

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

## Scope Types

The lifecycle scope types live in
[src/scribe/runtime/scopes.py](../../src/scribe/runtime/scopes.py).

### `scribe.RunScope`

Top-level lifecycle scope returned by `Scribe.run(...)`.

Public fields:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `code_revision`
- `config_snapshot_ref`
- `config_snapshot`
- `dataset_ref`
- `tags`
- `metadata`

Methods:

- `stage(name, *, stage_ref=None, metadata=None)`
- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

See also:

- `scribe.StageScope`
- `scribe.Scribe.run`

### `scribe.RunScope.stage`

`RunScope.stage(name, *, stage_ref=None, metadata=None)`

Create a stage scope under the current run.

Parameters:

- `name`
- `stage_ref`
- `metadata`

Returns:

- `StageScope`

Raises:

- `ClosedScopeError`

### `scribe.StageScope`

Major phase inside a run, such as training or evaluation.

Public fields:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `order_index`
- `metadata`

Methods:

- `operation(name, *, operation_ref=None, metadata=None)`
- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

See also:

- `scribe.OperationScope`
- `scribe.RunScope`

### `scribe.StageScope.operation`

`StageScope.operation(name, *, operation_ref=None, metadata=None)`

Create an operation scope under the current stage.

Parameters:

- `name`
- `operation_ref`
- `metadata`

Returns:

- `OperationScope`

Raises:

- `ClosedScopeError`

### `scribe.OperationScope`

Fine-grained scope for a request, batch, iteration, or other small unit of work.

Public fields:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `observed_at`
- `metadata`

Methods:

- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

### Shared scope capture methods

`RunScope`, `StageScope`, and `OperationScope` share these methods:

- `event(key, *, message, level="info", attributes=None, tags=None)`
- `emit_events(emissions)`
- `metric(key, value, *, unit=None, aggregation_scope="step", tags=None, summary_basis="raw_observation")`
- `emit_metrics(emissions)`
- `span(name, *, started_at=None, ended_at=None, status="ok", span_kind="operation", attributes=None, linked_refs=None, parent_span_id=None)`
- `register_artifact(artifact_kind, path, *, artifact_ref=None, attributes=None, compute_hash=True, allow_missing=False)`
- `close(status="completed")`

## Configuration

### `scribe.config.ScribeConfig`

`ScribeConfig(producer_ref="sdk.python.local", schema_version="1.0.0", capture_environment=True, capture_installed_packages=True, environment_variable_allowlist=(), retry_attempts=0, retry_backoff_seconds=0.0, outbox_root=None)`

Session-wide runtime configuration dataclass.

Parameters:

- `producer_ref`
- `schema_version`
- `capture_environment`
- `capture_installed_packages`
- `environment_variable_allowlist`
- `retry_attempts`
- `retry_backoff_seconds`
- `outbox_root`

Returns:

- `ScribeConfig`

Example:

```python
from scribe import LocalJsonlSink, Scribe
from scribe.config import ScribeConfig

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(".scribe")],
    config=ScribeConfig(
        producer_ref="sdk.python.training",
        capture_environment=False,
    ),
)
```

See also:

- `scribe.Scribe`

## Batch Input Models

### `scribe.EventEmission`

`EventEmission(key, message, level="info", attributes={}, tags={})`

Structured input for `emit_events(...)`.

Fields:

- `key`
- `message`
- `level`
- `attributes`
- `tags`

Example:

```python
from scribe import EventEmission

EventEmission(
    key="epoch.started",
    message="epoch 1 started",
    tags={"phase": "train"},
)
```

See also:

- `scribe.Scribe.emit_events`

### `scribe.MetricEmission`

`MetricEmission(key, value, unit=None, aggregation_scope="step", tags={}, summary_basis="raw_observation")`

Structured input for `emit_metrics(...)`.

Fields:

- `key`
- `value`
- `unit`
- `aggregation_scope`
- `tags`
- `summary_basis`

Example:

```python
from scribe import MetricEmission

MetricEmission(
    key="eval.accuracy",
    value=0.91,
    aggregation_scope="dataset",
    tags={"split": "validation"},
)
```

See also:

- `scribe.Scribe.emit_metrics`

## Result Models

### `scribe.PayloadFamily`

`PayloadFamily`

Enum identifying the emitted payload family.

Values:

- `PayloadFamily.CONTEXT`
- `PayloadFamily.RECORD`
- `PayloadFamily.ARTIFACT`
- `PayloadFamily.DEGRADATION`

### `scribe.DeliveryStatus`

`DeliveryStatus`

Enum identifying normalized delivery outcome.

Values:

- `DeliveryStatus.SUCCESS`
- `DeliveryStatus.DEGRADED`
- `DeliveryStatus.FAILURE`
- `DeliveryStatus.SKIPPED`

### `scribe.results.Delivery`

`Delivery(sink_name, family, status, detail="")`

Per-sink dispatch result item.

Fields:

- `sink_name`
- `family`
- `status`
- `detail`

### `scribe.CaptureResult`

`CaptureResult(family, status, deliveries=[], warnings=[], degradation_reasons=[], payload=None, degradation_emitted=False, degradation_payload=None, recovered_to_outbox=False, replay_refs=[])`

Structured outcome for a single capture action.

Fields:

- `family`
- `status`
- `deliveries`
- `warnings`
- `degradation_reasons`
- `payload`
- `degradation_emitted`
- `degradation_payload`
- `recovered_to_outbox`
- `replay_refs`

Properties:

- `succeeded`
- `degraded`

See also:

- `scribe.BatchCaptureResult`
- `scribe.results.Delivery`

### `scribe.BatchCaptureResult`

`BatchCaptureResult(family, status, results=[])`

Aggregated result for batch event or metric capture.

Fields:

- `family`
- `status`
- `results`

Properties:

- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`
- `succeeded`
- `degraded`

Class methods:

- `BatchCaptureResult.from_results(family, results)`

## Artifact Models

### `scribe.ArtifactSourceKind`

`ArtifactSourceKind`

Enum describing how artifact bytes are located.

Values:

- `ArtifactSourceKind.PATH`
- `ArtifactSourceKind.STAGED_PATH`
- `ArtifactSourceKind.URI`

### `scribe.ArtifactBindingStatus`

`ArtifactBindingStatus`

Enum describing binding state.

Values:

- `ArtifactBindingStatus.BOUND`
- `ArtifactBindingStatus.PENDING`
- `ArtifactBindingStatus.DEGRADED`

### `scribe.ArtifactSource`

`ArtifactSource(kind, uri, exists)`

Artifact source location record.

Fields:

- `kind`
- `uri`
- `exists`

### `scribe.ArtifactVerificationPolicy`

`ArtifactVerificationPolicy(compute_hash=True, require_existing_source=True)`

Verification expectations for artifact registration.

Fields:

- `compute_hash`
- `require_existing_source`

### `scribe.ArtifactRegistrationRequest`

`ArtifactRegistrationRequest(artifact_ref, artifact_kind, source, verification_policy, attributes={})`

Artifact registration request model.

Fields:

- `artifact_ref`
- `artifact_kind`
- `source`
- `verification_policy`
- `attributes`

### `scribe.ArtifactBinding`

`ArtifactBinding(request, manifest, source, project_name, operation_context_ref, binding_status="bound", completeness_marker="complete", degradation_marker="none", attributes={})`

Artifact-family payload emitted by Scribe.

Fields:

- `request`
- `manifest`
- `source`
- `project_name`
- `operation_context_ref`
- `binding_status`
- `completeness_marker`
- `degradation_marker`
- `attributes`

See also:

- [Artifacts](artifacts.md)

## Sink Types

### `scribe.Sink`

`Sink`

Abstract sink interface.

Members:

- `name`
- `supported_families`
- `supports(family)`
- `capture(family=..., payload=...)`

### `scribe.LocalJsonlSink`

`LocalJsonlSink(storage_root, *, name="local-jsonl")`

Built-in sink that writes one JSONL file per payload family.

Methods:

- `capture(...)`
- `path_for(family)`
- `read_family(family)`

Returns:

- `LocalJsonlSink`

### `scribe.InMemorySink`

`InMemorySink(*, name="memory")`

Built-in sink that stores capture actions in memory.

Fields:

- `actions`

Returns:

- `InMemorySink`

### `scribe.CompositeSink`

`CompositeSink(sinks, *, name="composite")`

Sink that forwards capture requests to multiple child sinks.

This type is deprecated in favor of passing multiple sinks directly to
`Scribe(..., sinks=[...])`, which preserves per-sink delivery reporting.

Parameters:

- `sinks`
- `name`

Returns:

- `CompositeSink`

See also:

- [Sinks and Storage](sinks-and-storage.md)

### `scribe.S3ObjectSink`

`S3ObjectSink(*, bucket, prefix="scribe", client=None, name="s3-object")`

Built-in sink that writes each payload as a standalone JSON object in S3-compatible storage.

### `scribe.KafkaSink`

`KafkaSink(*, producer=None, topic_prefix="scribe", delivery_timeout_seconds=10.0, name="kafka")`

Built-in sink that publishes payloads to Kafka topics grouped by payload family.

## Replay API

### `scribe.replay_outbox`

`replay_outbox(*, outbox_root, sinks, sink_name=None, acknowledge_successes=True, dead_letter_after_failures=None)`

Replay pending outbox entries to configured sinks.

### `scribe.ReplayEntryResult`

`ReplayEntryResult(replay_ref, family, target_sink, status, detail="")`

Per-entry replay result.

### `scribe.ReplayBatchResult`

`ReplayBatchResult(results=[])`

Aggregated replay result.

Properties:

- `total_count`
- `success_count`
- `failure_count`
- `skipped_total`

### CLI

`scribe-replay-outbox`

Command-line entry point for replaying durable outbox entries into `local-jsonl`, `s3`, or `kafka` sinks.

## Exceptions

### `scribe.ScribeError`

Base exception for the package.

See also:

- `scribe.ValidationError`
- `scribe.ContextError`
- `scribe.ClosedScopeError`
- `scribe.SinkDispatchError`

### `scribe.ValidationError`

Raised when invalid data is supplied to the SDK.

### `scribe.ContextError`

Raised when lifecycle state is missing or inconsistent.

### `scribe.ClosedScopeError`

Raised when a scope is used after it has already been closed.

### `scribe.SinkDispatchError`

Raised when every eligible sink fails for a dispatch.

## Related Files

- Package exports: [src/scribe/__init__.py](../../src/scribe/__init__.py)
- Session API: [src/scribe/api/session.py](../../src/scribe/api/session.py)
- Scope types: [src/scribe/runtime/scopes.py](../../src/scribe/runtime/scopes.py)
- Runtime config: [src/scribe/config/models.py](../../src/scribe/config/models.py)
- Result models: [src/scribe/results/models.py](../../src/scribe/results/models.py)
- Artifact models: [src/scribe/artifacts/models.py](../../src/scribe/artifacts/models.py)
- Exceptions: [src/scribe/exceptions.py](../../src/scribe/exceptions.py)
