# Capture Patterns

[User Guide Home](../USER_GUIDE.en.md)

When people start using `Scribe`, one of the first practical questions is usually not "what API
exists," but "what kind of runtime fact should I capture with which primitive." This page exists to
answer that question.

The core goals of this page are:

1. explain when to use events, metrics, spans, and artifacts,
2. show how scope level changes the meaning of the same capture call,
3. explain when batch capture is the better fit,
4. help you avoid common capture-shape mistakes early.

After reading this page, you should be able to decide much more quickly:

- whether something is an event, metric, span, or artifact,
- whether it belongs at run, stage, or operation scope,
- whether to emit one item at a time or use a batch API,
- how to combine multiple capture types inside one workflow naturally.

## Why Capture Patterns Need Their Own Page

At first glance, `Scribe` can look simple:

- `event(...)`
- `metric(...)`
- `span(...)`
- `register_artifact(...)`

But in real instrumentation work, the problem is not just "how do I call the method." The harder
question is "what future interpretation do I want this runtime fact to support."

For example:

- an epoch boundary can be recorded,
- loss can be recorded,
- a model forward pass can be recorded,
- a checkpoint can be recorded.

All four are true statements about one workflow, but they are not the same kind of truth. If you
pick the wrong capture shape, later search, aggregation, or troubleshooting becomes much harder.

That is why this page is organized around interpretation patterns, not just public methods.

## The Fastest Rule Of Thumb

As a very short guide:

- if "what happened" matters most, use an event,
- if "what was the value" matters most, use a metric,
- if "how long did it take" or "what execution path did it follow" matters most, use a span,
- if "what durable output remained" matters most, use an artifact.

That is only the first shortcut. In real systems, all four are often used together inside the same
run.

## Scope Comes Before Capture Meaning

Before choosing event, metric, or span, it helps to decide where the fact belongs.

- `run`: top-level execution facts
- `stage`: major workflow-phase facts
- `operation`: finer-grained work-unit facts

The same capture primitive can mean different things depending on scope.

Examples:

- `run.event(...)` usually means a run-level milestone,
- `stage.metric(...)` usually means a phase-level aggregate,
- `operation.span(...)` usually means a fine-grained latency or execution segment.

So the real decision is often two-step:

1. which scope does this fact belong to,
2. which capture shape best represents it.

## Events

Events are the right fit when the most important question is:

"What happened?"

Typical examples:

- a run started or completed,
- an evaluation stage finished,
- a warning condition was detected,
- a deployment registration step failed,
- an important transition should remain readable to humans.

Example:

```python
run.event(
    "evaluation.completed",
    message="evaluation finished",
    tags={"phase": "evaluation"},
    attributes={"dataset": "validation"},
)
```

### When Event Is The Right Fit

- lifecycle-adjacent milestones
- warnings and errors
- operator-readable status changes
- state transitions worth searching by event key

Good examples:

- `run.note`
- `evaluation.completed`
- `dataset.load.failed`
- `checkpoint.registration.started`

### What To Put In Each Event Field

#### `key`

Use the event key as the machine-readable classification.

Good style:

- stable
- searchable
- specific enough to filter on

#### `message`

Use the message as the human-readable explanation.

#### `attributes`

Use attributes for event-local details.

Example:

```python
attributes={"dataset": "validation", "epoch": 3}
```

#### `tags`

Use tags when you want lightweight capture metadata attached to the event itself.

### When Event Is Not The Best Fit

Events are usually the wrong fit when:

- the core meaning is a numeric value you want to aggregate later,
- the main question is duration or parent-child execution flow,
- the fact is really an output object rather than a runtime occurrence.

Bad pattern:

```text
"training loss is 0.42"
```

If that value needs charting, thresholding, or averaging later, it should usually be a metric.

## Metrics

Metrics are the right fit when the most important question is:

"What was the measured value?"

Example:

```python
stage.metric("eval.accuracy", 0.91, aggregation_scope="dataset")
```

### When Metric Is The Right Fit

- loss, accuracy, latency summaries, throughput
- evaluation scores
- resource usage
- queue depth
- counts, ratios, and aggregates

Good examples:

- `training.loss`
- `eval.accuracy`
- `gpu.memory.used`
- `inference.requests_per_second`

### Aggregation Scope Matters

In `Scribe`, a metric is not just a number. It also carries an aggregation scope.

Supported aggregation scopes:

- `point`
- `step`
- `batch`
- `epoch`
- `dataset`
- `run`
- `operation`

That scope is one of the most important meaning fields in the metric.

Examples:

- `step`: one training step observation
- `epoch`: one aggregate across an epoch
- `dataset`: one aggregate across an evaluation dataset
- `run`: one run-level summary

So if you are choosing a metric scope, the practical question is:

"Over what unit should this value be interpreted?"

### Scope Patterns For Metrics

#### Run-level metric

Use when the value summarizes the entire execution.

Example:

```python
run.metric("training.best_accuracy", 0.94, aggregation_scope="run")
```

#### Stage-level metric

Use when the value summarizes one phase.

Example:

```python
stage.metric("eval.accuracy", 0.91, aggregation_scope="dataset")
```

#### Operation-level metric

Use when the value belongs to a step, batch, or request.

Example:

```python
operation.metric("training.loss", 0.42, aggregation_scope="step")
```

### When Metric Is Not The Best Fit

Metrics are usually the wrong fit when:

- the information is really a state transition,
- the operator will read it more like an occurrence than a measurement,
- duration and nesting structure matter more than the numeric value itself.

Bad pattern:

```text
training.epoch.started = 1
```

That is semantically much closer to an event.

## Spans

Spans are the right fit when the most important question is:

"How long did this work take, and how does it connect to the surrounding execution?"

Example:

```python
operation.span("model.forward", span_kind="model_call")
```

### When Span Is The Right Fit

- model call latency
- external API calls
- feature lookup segments
- request execution intervals
- nested work where parent-child flow matters

Good examples:

- `model.forward`
- `feature.lookup`
- `predict.request`
- `vector.search`

### Why A Span Is Not Just A Metric

A latency metric like `inference.latency=152ms` is useful, but a span preserves much more:

- start time
- end time
- status
- parent linkage
- trace identity
- linked refs

So the practical difference is:

- metric says "what was the latency value"
- span says "what execution interval produced that latency, under what trace context"

### Span Fields Worth Thinking About

- `span_kind`: what kind of work this span represents
- `attributes`: structured context for the span
- `linked_refs`: related refs that help connect the span to artifacts or other entities
- `parent_span_id`: explicit parent-child linkage when available

### When Span Is Not The Best Fit

Spans are usually the wrong fit when:

- the fact is a discrete milestone rather than an interval,
- a plain numeric aggregate is enough,
- there is no meaningful duration or execution segment to preserve.

Bad pattern:

- emitting a span for a simple phase-completed notification

That is better represented as an event.

## Artifacts

Artifacts are the right fit when the most important question is:

"What durable output or file-like result did this execution produce or refer to?"

Example:

```python
from pathlib import Path

stage.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    compute_hash=True,
)
```

### When Artifact Is The Right Fit

- checkpoints
- evaluation reports
- exported datasets
- feature snapshots
- generated manifests or packaged outputs

### Why Artifact Is Not Just A File Path

In `Scribe`, artifact capture is binding-aware. The registration includes:

- artifact kind
- source path
- verification policy
- binding status
- execution context from the active run or stage

So artifact capture is not just "remember this path." It is "record this output as a structured
execution result."

### `allow_missing=True`

This option is especially important in real workflows.

Example:

```python
stage.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    allow_missing=True,
)
```

With this setting, the result can become `degraded` instead of failing hard when the file does not
exist yet. That is useful when logical artifact identity is known before the file body is fully
materialized.

## Event, Metric, Span, And Artifact Are Not Competing Types

In practice, one workflow often needs several capture types together.

For example, inside one training stage:

- epoch start is an event,
- training loss is a metric,
- `model.forward` is a span,
- a checkpoint is an artifact.

So these are not substitutes. They answer different later questions.

Put more directly:

- event says what happened,
- metric says what the value was,
- span says how the work interval behaved,
- artifact says what durable result remained.

## Batch Capture

Batch APIs are useful when code naturally produces multiple items together.

Examples:

- a stage emits many related metrics at once,
- one phase emits several completion events together,
- a batch result is already grouped in memory.

Example:

```python
from scribe import EventEmission, MetricEmission

run.emit_events(
    [
        EventEmission("epoch.started", "epoch 1 started"),
        EventEmission("epoch.completed", "epoch 1 completed"),
    ]
)

run.emit_metrics(
    [
        MetricEmission("training.loss", 0.42, aggregation_scope="step"),
        MetricEmission("training.accuracy", 0.91, aggregation_scope="epoch"),
    ]
)
```

### When Batch Capture Is The Better Fit

- the code already has a list of measurements or events
- you want one aggregated `BatchCaptureResult`
- the capture site is a hot path and one-by-one orchestration would be noisy

### What `BatchCaptureResult` Gives You

- `status`
- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`

That makes it easier to reason about grouped capture outcomes than inspecting every item manually.

## Top-Level API vs Scope-Level API

`Scribe` supports both top-level and scope-level capture patterns.

Top-level:

```python
with scribe.run("training"):
    scribe.event("run.note", message="capture from active context")
```

Scope-level:

```python
with scribe.run("training") as run:
    run.event("run.note", message="capture from explicit scope")
```

In practice, scope-level usage is usually easier to reason about because the active context is more
obvious in the code.

Top-level capture can still be useful when:

- helper code should work against the current active scope,
- the surrounding control flow already manages scope entrance elsewhere.

## Pattern Combinations By Scenario

### Training pipeline

Common shape:

- run-level note event
- stage-level dataset metrics
- operation-level loss metric
- operation-level model-forward span
- stage-level checkpoint artifact

### Evaluation pipeline

Common shape:

- artifact registration for the loaded checkpoint
- dataset-level evaluation metrics
- completion event with summary status
- report artifact

### Online inference

Common shape:

- request-level operation context
- request event for an important state change
- latency span
- latency or token-count metric
- optional report or drift artifact

So even though the same APIs are available everywhere, the useful pattern changes by scenario.

## Common Capture Mistakes

### 1. Sending everything as events

This makes numeric analysis harder later.

Bad example:

```text
"training loss is 0.42"
```

### 2. Sending everything as metrics

This weakens state transition meaning.

Bad example:

```text
evaluation.completed = 1
```

### 3. Replacing spans with start and end events only

That loses interval structure and makes later trace-style analysis weaker.

### 4. Registering outputs only as plain paths outside capture flow

That drops the execution context and binding semantics `Scribe` is designed to preserve.

### 5. Capturing at the wrong scope

For example:

- recording one request-level fact at the run level,
- recording a dataset aggregate at the operation level,
- recording a whole-run summary inside one step operation.

Even if the payload itself is valid, interpretation becomes noisy later.

## Practical Decision Guide

If you want a quick decision process, ask these questions in order:

### 1. Is this fact mainly a runtime occurrence, a numeric value, an interval, or an output

- occurrence -> event
- value -> metric
- interval -> span
- output -> artifact

### 2. Which scope owns this fact

- whole execution -> run
- one major phase -> stage
- one step, batch, or request -> operation

### 3. Is this naturally one item or a group of items

- one item -> single capture call
- grouped items -> batch API

### 4. Will I need to inspect reduced-fidelity behavior later

If yes, pay attention to `CaptureResult` and do not treat degraded capture as invisible.

## The Core Intuition To Keep From This Page

In very short form:

- choose capture shape by future interpretation, not only by what is easiest to emit now,
- choose scope by where the fact belongs operationally,
- use batch APIs when the code already produces grouped values,
- use multiple capture types together when they answer different questions about the same workflow.

In one sentence:

"Model the runtime fact according to how you will want to read it later, then place it at the
scope where it naturally belongs."

## What To Read Next

If this page made sense, the most useful next pages are usually:

1. [Artifacts](artifacts.md) if you want deeper
   guidance on artifact registration and degraded bindings.
2. [Sinks and Storage](sinks-and-storage.md) if you
   want to understand where captured payloads go.
3. [Degradation and Errors](degradation-and-errors.md)
   if you want to understand operational interpretation when capture is partial or sinks fail.
4. [Examples](examples.md) if you want full workflow
   examples rather than isolated patterns.

## Related Files

- Scope APIs: [src/scribe/runtime/scopes.py](../../src/scribe/runtime/scopes.py)
- Trace capture service: [src/scribe/traces/service.py](../../src/scribe/traces/service.py)
- Artifact registration service: [src/scribe/artifacts/service.py](../../src/scribe/artifacts/service.py)
- Evaluation example: [examples/evaluation_workflow.py](../../examples/evaluation_workflow.py)
