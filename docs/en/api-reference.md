# API Reference

[User Guide Home](../USER_GUIDE.en.md)

This page is the reference companion to the rest of the Scribe guide. The other pages explain how
to think about instrumentation, scope design, degraded capture, sinks, and artifact binding. This
page exists for the moment when you already know what you want to do and simply need to confirm the
public API surface.

In practice, that usually means one of five questions. Which symbols are exposed from
`import scribe`? Which symbols are exposed from public submodules such as `scribe.results` and
`scribe.config`? Which methods live on the `Scribe` session object? Which methods live on scope
objects? Which result, sink, and exception types are intended to be public? This reference is
organized around those questions.

If you are still deciding whether a piece of data should be modeled as an event, metric, span, or
artifact, start with [Capture Patterns](capture-patterns.md).
If you are trying to understand degraded outcomes or dispatch failures, read
[Degradation and Errors](degradation-and-errors.md)
alongside this page.

## Package Entry Point

The top-level package exports are collected in
[src/scribe/__init__.py](../../src/scribe/__init__.py). Public
submodule exports are collected in module-level `__init__.py` files such as
[src/scribe/config/__init__.py](../../src/scribe/config/__init__.py)
and [src/scribe/results/__init__.py](../../src/scribe/results/__init__.py).
Together, those files are the best definition of what the library treats as its supported import
surface.

Most users start with a very small import set:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe
```

When batch capture is needed, the common extension is:

```python
from scribe import EventEmission, MetricEmission, Scribe
```

When you need configuration, import it from the configuration module rather than the top-level
package:

```python
from scribe import LocalJsonlSink, Scribe
from scribe.config import ScribeConfig
```

The public surface naturally falls into seven groups:

- the `Scribe` session object,
- lifecycle scope objects returned by that session,
- public submodule entry points,
- batch input models,
- result and status models,
- artifact-related models,
- sink and exception types.

### Public Import Paths

These are the public import entry points that appear to be intentionally supported by the package:

- `scribe`
- `scribe.api`
- `scribe.config`
- `scribe.events`
- `scribe.metrics`
- `scribe.results`
- `scribe.artifacts`
- `scribe.sinks`

Not every internal package under `src/scribe` is a public API module. For example, `runtime`,
`context`, and `traces` exist as implementation packages, but they do not currently re-export a
documented public symbol set through their `__init__.py` files.

## Session API

The main SDK entry point lives in
[src/scribe/api/session.py](../../src/scribe/api/session.py).
`Scribe` is the object you construct once for a project or process and then use to create
run-scoped instrumentation.

`Scribe` is publicly importable both as `from scribe import Scribe` and as
`from scribe.api import Scribe`.

### `scribe.Scribe`

`Scribe(project_name, *, sinks=None, config=None)`

This is the top-level session object for local-first observability capture. It owns the runtime,
the configured sink set, and the default capture configuration for the process or workflow in which
it is used.

Parameters:

- `project_name`: logical project name attached to the session and its emitted payloads
- `sinks`: optional sequence of sink instances
- `config`: optional [`ScribeConfig`](../../src/scribe/config/models.py)

Typical usage:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="nova-vision",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)
```

The important point is that constructing `Scribe` does not begin a run by itself. It creates an
instrumentation session. A run begins only when you call `scribe.run(...)`.

### `scribe.Scribe.project_name`

`Scribe.project_name`

This property returns the configured project name for the session. It is mostly useful for
inspection, tests, and places where you want to confirm the logical project identity that the
runtime is attaching to emitted payloads.

Returns:

- `str`

### `scribe.Scribe.run`

`Scribe.run(name, *, run_id=None, tags=None, metadata=None, code_revision=None, config_snapshot=None, dataset_ref=None)`

This method creates a run scope. In practice, it is the method that opens the main instrumentation
boundary for a training run, evaluation pass, batch scoring job, ingestion workflow, or similar
unit of work.

Parameters:

- `name`: human-readable run name
- `run_id`: optional explicit run reference
- `tags`: optional run-level tags
- `metadata`: optional run-level metadata
- `code_revision`: optional reproducibility field for source revision identity
- `config_snapshot`: optional structured configuration snapshot
- `dataset_ref`: optional dataset reference for run provenance

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

The returned scope can be used as a context manager and is the normal starting point for stage and
operation instrumentation.

### `scribe.Scribe.current_run`

`Scribe.current_run()`

This method returns the current active run scope. It is useful when helper functions or framework
callbacks need to emit data without receiving the scope object directly.

Returns:

- `RunScope`

Raises:

- `ContextError`: when there is no active run scope in the current execution context

### `scribe.Scribe.current_stage`

`Scribe.current_stage()`

This method returns the current active stage scope.

Returns:

- `StageScope`

Raises:

- `ContextError`: when there is no active stage scope

### `scribe.Scribe.current_operation`

`Scribe.current_operation()`

This method returns the current active operation scope.

Returns:

- `OperationScope`

Raises:

- `ContextError`: when there is no active operation scope

### `scribe.Scribe.event`

`Scribe.event(key, *, message, level="info", attributes=None, tags=None)`

This emits a structured event in the currently active context. It is the top-level convenience form
of event capture and is most useful when a helper function already knows that the correct lifecycle
scope is active.

Parameters:

- `key`: machine-readable event key
- `message`: human-readable message
- `level`: event severity level
- `attributes`: optional structured event detail
- `tags`: optional event tags

Returns:

- `CaptureResult`

Raises:

- `ContextError`: when no active lifecycle context is available
- `ValidationError`: when the event payload is invalid
- `SinkDispatchError`: when every eligible sink fails for the dispatch

### `scribe.Scribe.emit_events`

`Scribe.emit_events(emissions)`

This emits multiple events in the current context. It is the batch form of `event(...)` and is
useful when instrumentation already exists as a sequence of structured inputs.

Parameters:

- `emissions`: sequence of `EventEmission`

Returns:

- `BatchCaptureResult`

### `scribe.Scribe.metric`

`Scribe.metric(key, value, *, unit=None, aggregation_scope="point", tags=None, summary_basis="raw_observation")`

This emits a structured metric in the currently active context.

Parameters:

- `key`: metric name
- `value`: numeric value
- `unit`: optional unit string
- `aggregation_scope`: declared aggregation level for the metric value
- `tags`: optional metric tags
- `summary_basis`: optional description of how the value was summarized

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

### `scribe.Scribe.emit_metrics`

`Scribe.emit_metrics(emissions)`

This emits multiple metrics in the current context.

Parameters:

- `emissions`: sequence of `MetricEmission`

Returns:

- `BatchCaptureResult`

### `scribe.Scribe.span`

`Scribe.span(name, *, started_at=None, ended_at=None, status="ok", span_kind="operation", attributes=None, linked_refs=None, parent_span_id=None)`

This emits a trace-like span record in the active context. Use it when the duration and status of a
specific unit of work matter more than a single scalar measurement.

Parameters:

- `name`: span name
- `started_at`: optional explicit start timestamp
- `ended_at`: optional explicit end timestamp
- `status`: span status
- `span_kind`: span category
- `attributes`: optional structured span attributes
- `linked_refs`: optional related references
- `parent_span_id`: optional parent span identifier

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

### `scribe.Scribe.register_artifact`

`Scribe.register_artifact(artifact_kind, path, *, artifact_ref=None, attributes=None, compute_hash=True, allow_missing=False)`

This registers an artifact against the current lifecycle context. It is the top-level convenience
form of artifact binding and is commonly used for checkpoints, predictions, evaluation reports, or
other outputs that need durable identity rather than a plain event message.

Parameters:

- `artifact_kind`: logical artifact category
- `path`: artifact source path
- `artifact_ref`: optional explicit artifact reference
- `attributes`: optional artifact metadata
- `compute_hash`: whether the runtime should compute a source hash when possible
- `allow_missing`: whether a missing source should degrade instead of failing

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

## Scope API

The lifecycle scope types live in
[src/scribe/runtime/scopes.py](../../src/scribe/runtime/scopes.py).
In day-to-day usage, these scope objects are the API surface most developers work with directly,
because they make the lifecycle boundary explicit and keep instrumentation colocated with the work
being performed.

All scope types share a few public identity fields:

- `scope_kind`
- `ref`
- `name`

They also share context-manager behavior. Entering a scope makes it active for nested work. Exiting
the `with` block closes it automatically, using `"failed"` if the block exits with an exception and
`"completed"` otherwise.

### `scribe.RunScope`

`RunScope` is the top-level lifecycle scope returned by `Scribe.run(...)`. It represents the main
unit of work for a workflow execution.

Public fields commonly inspected in tests or debugging:

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

Public methods:

- `stage(name, *, stage_ref=None, metadata=None)`
- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

#### `scribe.RunScope.stage`

`RunScope.stage(name, *, stage_ref=None, metadata=None)`

This creates a stage scope under the current run.

Parameters:

- `name`: stage name
- `stage_ref`: optional explicit stage reference
- `metadata`: optional stage metadata

Returns:

- `StageScope`

Raises:

- `ClosedScopeError`: when the run has already been closed
- `ContextError`: when lifecycle state is inconsistent

### `scribe.StageScope`

`StageScope` represents a major phase inside a run, such as training, evaluation, preprocessing, or
serving setup.

Public fields commonly inspected in tests or debugging:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `order_index`
- `metadata`

Public methods:

- `operation(name, *, operation_ref=None, metadata=None)`
- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

#### `scribe.StageScope.operation`

`StageScope.operation(name, *, operation_ref=None, metadata=None)`

This creates an operation scope under the current stage.

Parameters:

- `name`: operation name
- `operation_ref`: optional explicit operation reference
- `metadata`: optional operation metadata

Returns:

- `OperationScope`

Raises:

- `ClosedScopeError`
- `ContextError`

### `scribe.OperationScope`

`OperationScope` is the fine-grained scope for a request, batch, iteration, or other small unit of
observable work.

Public fields commonly inspected in tests or debugging:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `observed_at`
- `metadata`

Public methods:

- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

### Shared Scope Capture Methods

`RunScope`, `StageScope`, and `OperationScope` share the same capture-style methods, and the
signatures match the top-level session methods:

- `event(key, *, message, level="info", attributes=None, tags=None)`
- `emit_events(emissions)`
- `metric(key, value, *, unit=None, aggregation_scope="point", tags=None, summary_basis="raw_observation")`
- `emit_metrics(emissions)`
- `span(name, *, started_at=None, ended_at=None, status="ok", span_kind="operation", attributes=None, linked_refs=None, parent_span_id=None)`
- `register_artifact(artifact_kind, path, *, artifact_ref=None, attributes=None, compute_hash=True, allow_missing=False)`
- `close(status="completed")`

The difference is not in the payload shape. The difference is in how explicit the call site is. A
scope method makes the lifecycle relationship visible at the point of capture, while a top-level
session call relies on the currently active context.

## Configuration

The runtime configuration model lives in
[src/scribe/config/models.py](../../src/scribe/config/models.py)
and is imported from `scribe.config`.

### `scribe.config.ScribeConfig`

`ScribeConfig(producer_ref="sdk.python.local", schema_version="1.0.0", capture_environment=True, capture_installed_packages=True, environment_variable_allowlist=())`

This dataclass configures session-wide runtime behavior. Most users do not need to override it
immediately, but it becomes important when you want to control environment capture or stamp a custom
producer identity into emitted payloads.

Parameters:

- `producer_ref`: producer identity attached to emitted payloads
- `schema_version`: schema version marker
- `capture_environment`: whether environment context should be captured at run start
- `capture_installed_packages`: whether installed packages should be included in environment capture
- `environment_variable_allowlist`: environment variable names allowed into the snapshot

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

## Batch Input Models

The batch input models exist so that event and metric capture can be prepared ahead of time and then
emitted in one call. They are small dataclasses rather than complex builders.

### `scribe.EventEmission`

`EventEmission(key, message, level="info", attributes={}, tags={})`

This model is the structured input for `emit_events(...)`.

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

### `scribe.MetricEmission`

`MetricEmission(key, value, unit=None, aggregation_scope="point", tags={}, summary_basis="raw_observation")`

This model is the structured input for `emit_metrics(...)`.

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

## Result Models

The result models live in
[src/scribe/results/models.py](../../src/scribe/results/models.py).
They are the main reason capture calls in Scribe feel different from plain logging calls. Instead of
returning `None`, the SDK returns structured outcomes that explain what family was emitted, whether
delivery succeeded, and whether any degradation occurred.

These models are publicly importable from `scribe.results`. A subset is also re-exported from the
top-level `scribe` package.

### `scribe.PayloadFamily`

`PayloadFamily`

This enum identifies the broad truth family being emitted by the SDK.

Values:

- `PayloadFamily.CONTEXT`
- `PayloadFamily.RECORD`
- `PayloadFamily.ARTIFACT`
- `PayloadFamily.DEGRADATION`

### `scribe.DeliveryStatus`

`DeliveryStatus`

This enum normalizes the outcome of a capture or dispatch step.

Values:

- `DeliveryStatus.SUCCESS`
- `DeliveryStatus.DEGRADED`
- `DeliveryStatus.FAILURE`
- `DeliveryStatus.SKIPPED`

`SUCCESS` means the payload was accepted by at least one eligible sink without reduced fidelity.
`DEGRADED` means some truth was preserved, but not in the ideal form. `FAILURE` means the capture
did not succeed. `SKIPPED` is mainly relevant inside per-sink delivery details.

### `scribe.results.Delivery`

`Delivery(sink_name, family, status, detail="")`

This dataclass records the outcome for one sink during one dispatch attempt.

Fields:

- `sink_name`
- `family`
- `status`
- `detail`

`Delivery` is part of the public `scribe.results` module, even though it is not re-exported from the
top-level `scribe` package. It matters whenever you inspect `CaptureResult.deliveries` in tests or
operational tooling.

### `scribe.CaptureResult`

`CaptureResult(family, status, deliveries=[], warnings=[], degradation_reasons=[], payload=None, degradation_emitted=False, degradation_payload=None)`

This is the structured outcome for a single capture action.

Important fields:

- `family`: the payload family that was being captured
- `status`: the normalized overall outcome
- `deliveries`: per-sink delivery entries
- `warnings`: non-fatal warnings produced during capture
- `degradation_reasons`: human-readable reasons for degraded capture
- `payload`: the emitted payload, when available
- `degradation_emitted`: whether a degradation payload was emitted
- `degradation_payload`: the emitted degradation payload, when available

Important properties:

- `succeeded`: `True` for successful and degraded outcomes
- `degraded`: `True` only when the overall status is degraded

In practice, most application code only needs `status`, `succeeded`, `degraded`, and sometimes
`degradation_reasons`. Tests and operational tooling often inspect `deliveries` as well.

### `scribe.BatchCaptureResult`

`BatchCaptureResult(family, status, results=[])`

This is the aggregated outcome for batch event or metric capture.

Important fields:

- `family`
- `status`
- `results`

Important properties:

- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`
- `succeeded`
- `degraded`

Class methods:

- `BatchCaptureResult.from_results(family, results)`

The overall batch status is normalized from the item-level results. A batch is fully successful only
when every item succeeded. It is fully failed only when every item failed. Mixed outcomes produce a
degraded batch result.

## Artifact Models

The public artifact models live in
[src/scribe/artifacts/models.py](../../src/scribe/artifacts/models.py).
Most users do not instantiate all of them directly during normal instrumentation, because
`register_artifact(...)` handles the common path. They are still part of the public surface because
they define the binding model Scribe emits and they are useful in tests, extensions, and advanced
inspection code.

These models are publicly importable from both `scribe.artifacts` and, for convenience, the
top-level `scribe` package.

### `scribe.ArtifactSourceKind`

`ArtifactSourceKind`

This enum describes how artifact bytes are currently located.

Values:

- `ArtifactSourceKind.PATH`
- `ArtifactSourceKind.STAGED_PATH`
- `ArtifactSourceKind.URI`

### `scribe.ArtifactBindingStatus`

`ArtifactBindingStatus`

This enum describes the operational state of the artifact binding.

Values:

- `ArtifactBindingStatus.BOUND`
- `ArtifactBindingStatus.PENDING`
- `ArtifactBindingStatus.DEGRADED`

### `scribe.ArtifactSource`

`ArtifactSource(kind, uri, exists)`

This frozen dataclass records where the runtime believes the artifact source is and whether that
source currently exists.

Fields:

- `kind`
- `uri`
- `exists`

### `scribe.ArtifactVerificationPolicy`

`ArtifactVerificationPolicy(compute_hash=True, require_existing_source=True)`

This frozen dataclass records the verification expectations that accompany an artifact registration
request.

Fields:

- `compute_hash`
- `require_existing_source`

### `scribe.ArtifactRegistrationRequest`

`ArtifactRegistrationRequest(artifact_ref, artifact_kind, source, verification_policy, attributes={})`

This frozen dataclass represents the registration intent before that intent is turned into a bound
artifact payload.

Fields:

- `artifact_ref`
- `artifact_kind`
- `source`
- `verification_policy`
- `attributes`

### `scribe.ArtifactBinding`

`ArtifactBinding(request, manifest, source, project_name, operation_context_ref, binding_status="bound", completeness_marker="complete", degradation_marker="none", attributes={})`

This frozen dataclass is the artifact-family payload emitted by Scribe. It carries both the request
that was made and the binding state that was actually achieved.

Important fields:

- `request`
- `manifest`
- `source`
- `project_name`
- `operation_context_ref`
- `binding_status`
- `completeness_marker`
- `degradation_marker`
- `attributes`

If you are trying to understand when these fields degrade, or why artifact binding is modeled
separately from events, see
[Artifacts](artifacts.md).

## Sink Types

The built-in sinks are re-exported through
[src/scribe/sinks/__init__.py](../../src/scribe/sinks/__init__.py).
These are the delivery boundary between Scribe's structured runtime model and actual persistence or
inspection.

They are publicly importable from both `scribe.sinks` and the top-level `scribe` package.

### `scribe.Sink`

`Sink`

This is the abstract sink interface.

Important members:

- `name`
- `supported_families`
- `supports(family)`
- `capture(family=..., payload=...)`

Custom sinks should follow this contract.

### `scribe.LocalJsonlSink`

`LocalJsonlSink(storage_root, *, name="local-jsonl")`

This is the default persistence-oriented sink for local development and inspection. It writes one
JSONL file per payload family under the configured storage root.

Important methods:

- `capture(...)`
- `path_for(family)`
- `read_family(family)`

Returns:

- `LocalJsonlSink`

### `scribe.InMemorySink`

`InMemorySink(*, name="memory")`

This is the simplest inspection sink. It stores capture actions in memory and is primarily useful in
tests and lightweight runtime assertions.

Important fields:

- `actions`

Returns:

- `InMemorySink`

### `scribe.CompositeSink`

`CompositeSink(sinks, *, name="composite")`

This sink forwards the same capture request to multiple child sinks.

Parameters:

- `sinks`
- `name`

Returns:

- `CompositeSink`

For more operational detail about dispatch, family support, and local persistence layout, see
[Sinks and Storage](sinks-and-storage.md).

## Exceptions

The public exception types live in
[src/scribe/exceptions.py](../../src/scribe/exceptions.py). They
divide Scribe failures into a small number of categories so that callers can distinguish invalid
input, missing lifecycle state, closed scopes, and dispatch failure.

These exceptions are re-exported from the top-level `scribe` package.

### `scribe.ScribeError`

Base exception for the package.

### `scribe.ValidationError`

Raised when invalid data is supplied to the SDK.

Typical causes include invalid metric fields, unsupported aggregation scopes, invalid artifact
inputs, and other payload-shape problems that should be fixed at the call site.

### `scribe.ContextError`

Raised when lifecycle state is missing or inconsistent.

Typical causes include attempting capture without an active run, calling `current_run()` when no run
is active, or otherwise depending on lifecycle state that does not exist in the current execution
context.

### `scribe.ClosedScopeError`

Raised when a scope is used again after it has already been closed.

This exception subclasses `ContextError`, which reflects the fact that it is still a lifecycle-state
problem rather than a payload-validation problem.

### `scribe.SinkDispatchError`

Raised when every eligible sink fails for a dispatch.

This is the exception to catch when capture logic is valid but delivery infrastructure has failed in
a way that left no successful sink path.

## Related Files

- Package exports: [src/scribe/__init__.py](../../src/scribe/__init__.py)
- SDK session API: [src/scribe/api/session.py](../../src/scribe/api/session.py)
- Scope types: [src/scribe/runtime/scopes.py](../../src/scribe/runtime/scopes.py)
- Runtime config: [src/scribe/config/models.py](../../src/scribe/config/models.py)
- Result models: [src/scribe/results/models.py](../../src/scribe/results/models.py)
- Artifact models: [src/scribe/artifacts/models.py](../../src/scribe/artifacts/models.py)
- Exceptions: [src/scribe/exceptions.py](../../src/scribe/exceptions.py)
