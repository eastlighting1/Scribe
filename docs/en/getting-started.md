# Getting Started

[User Guide Home](C:/Users/eastl/MLObservability/Scribe/docs/en/README.md)

This page is the most practical starting point for a first-time `Scribe` user. Its goals are four
things:

1. get `Scribe` importable in your local environment,
2. create a minimal `Scribe -> run -> event/metric` flow,
3. understand what `Scribe` captures automatically,
4. get an intuitive sense of what `CaptureResult` means in practice.

By the time you finish this page, you should be able to add `Scribe` to a small Python workflow,
record a first event and metric, and inspect the resulting local output.

## What Problem Scribe Solves

In most ML systems, observability logic starts out as a mix of ad hoc logs, metrics, and file
paths.

Examples:

- plain log lines for state transitions,
- metric emitters with inconsistent naming,
- artifact paths stored without execution context,
- traces that do not connect cleanly to run or stage identity.

That works for a while, but over time the same questions become harder:

- which run produced this metric,
- which stage created this artifact,
- did capture succeed completely or only partially,
- which environment was active when this run started,
- where should local-first capture go when no backend is configured yet.

`Scribe` reduces that ambiguity by giving runtime code one capture-side SDK that:

- opens explicit lifecycle scopes,
- emits canonical observability payloads,
- dispatches them to sinks,
- preserves degraded capture as structured evidence.

In short, `Scribe` is the library that says:

"capture runtime truth as structured observability data while the workflow is running, not as a
collection of unrelated side effects."

## What To Know Before You Start

At the beginning, you only need four ideas:

- create one `Scribe(...)` session,
- open a `run`,
- emit event and metric data inside that run,
- let a sink decide where the payloads go.

The smallest useful picture looks like this:

```text
Scribe
  -> run
    -> event / metric / span / artifact
      -> CaptureResult
        -> sink output
```

Once that picture is clear, the rest of the library becomes much easier to use.

## Installation And Local Execution

### Install In A Workspace Setup

`Scribe` depends on `Spine`, which provides the canonical contract models used behind the SDK.

For local development, the simplest setup is to install both repositories in editable mode:

```bash
pip install -e ../Spine -e .[dev]
```

This gives you:

- the local `scribe` package,
- the local `spine` package,
- development tools such as `pytest`, `ruff`, and `mypy`.

### Check Imports

After installation, it is a good idea to confirm that the local package resolves correctly:

```bash
python -c "import scribe; print(scribe.__file__)"
```

If this succeeds, your environment is importing the local `scribe` package rather than some stale
or missing installation.

## Basic Import Pattern

Most users can begin from the top-level `scribe` package.

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe
```

At the beginning, it is enough to remember:

- `Scribe` is the main SDK entrypoint,
- `LocalJsonlSink` is the easiest local-first sink,
- most everyday calls happen through the `Scribe` instance or the active scope returned by
  `run()`.

## Your First Scribe Session

The easiest starting point is a local JSONL sink.

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)
```

At this stage, only two constructor fields matter most:

- `project_name`: the logical project identity for this SDK session,
- `sinks`: where payloads should be dispatched.

Why `LocalJsonlSink` is the best first sink:

- it works without external infrastructure,
- it keeps payload families separated on disk,
- it is easy to inspect during local development,
- it gives you a durable path even before choosing a backend product.

## Your First Run

The most useful first capture flow is:

1. create `Scribe`,
2. enter a run scope,
3. emit one event,
4. emit one metric.

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)

with scribe.run("quick-check") as run:
    event_result = run.event("run.note", message="quick check started")
    metric_result = run.metric("training.loss", 0.42, aggregation_scope="step")

print(event_result.status)
print(metric_result.status)
```

This code already demonstrates the basic `Scribe` usage loop exactly as it is meant to be used:

1. create a session,
2. open a lifecycle scope,
3. capture runtime facts,
4. inspect structured results.

## What Happens Automatically

This is one of the most important things to understand early.

When a run starts, `Scribe` does more than just store the event or metric you explicitly emitted.
It also captures lifecycle and environment truth automatically.

At minimum, a normal run usually emits:

- `Project`
- `Run(status="running")`
- `EnvironmentSnapshot`
- `run.started`
- your explicit event and metric records
- `run.completed`
- `Run(status="completed")`

That means lifecycle truth does not depend on users remembering to emit every transition manually.

## What `CaptureResult` Means

Every single capture call returns a `CaptureResult`.

The most important field is `status`:

- `success`: capture completed normally
- `degraded`: some truth was captured, but fidelity dropped
- `failure`: all eligible sinks failed

In early local usage, the most common result is `success`.

But it is important to understand right away that `degraded` is not the same thing as "nothing
worked." In `Scribe`, degraded capture often means:

- one sink failed but another still accepted the payload,
- an artifact was allowed to register even though its file does not exist yet,
- capture completed with warnings that should still be preserved as evidence.

So `CaptureResult` is not decorative metadata. It is the operational status of the capture action.

## Minimal Artifact Example

Even though event and metric are the easiest first steps, artifact capture is a major part of
`Scribe`.

```python
from pathlib import Path

with scribe.run("training") as run:
    result = run.register_artifact(
        "checkpoint",
        Path("./artifacts/model.ckpt"),
        allow_missing=True,
    )

print(result.status)
```

If the file is missing and `allow_missing=True`, the result may be `degraded` instead of failing
hard. That is intentional. `Scribe` is designed to preserve partial truth rather than erase it.

## Minimal Stage And Operation Example

The first page does not require full nesting, but you should at least see the shape once.

```python
with scribe.run("baseline-train") as run:
    with run.stage("train") as stage:
        with stage.operation("step-1") as operation:
            operation.metric("training.loss", 0.42, aggregation_scope="step")
            operation.span("model.forward", span_kind="model_call")
```

The important point is not to memorize every method yet. It is to see that:

- `run` is the top-level execution scope,
- `stage` is a major phase inside a run,
- `operation` is a finer-grained work unit inside the active context.

## How To Inspect Local Output

With `LocalJsonlSink`, payloads are stored by family:

- `contexts.jsonl`
- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

You can read them back through the sink API:

```python
from pathlib import Path

from scribe import LocalJsonlSink, PayloadFamily

sink = LocalJsonlSink(Path("./.scribe"))
record_entries = sink.read_family(PayloadFamily.RECORD)
print(len(record_entries))
```

This is one of the easiest ways to build intuition for what `Scribe` is actually emitting.

## A Slightly More Realistic Example

The example below is still small, but it already resembles a real workflow more closely.

```python
from pathlib import Path

from scribe import EventEmission, LocalJsonlSink, MetricEmission, Scribe

scribe = Scribe(
    project_name="nova-vision",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)

with scribe.run("resnet50-baseline") as run:
    run.event("run.note", message="baseline training started")

    with run.stage("prepare-data") as stage:
        stage.emit_metrics(
            [
                MetricEmission("data.rows", 128_000, aggregation_scope="dataset"),
                MetricEmission("data.features", 512, aggregation_scope="dataset"),
            ]
        )

    with run.stage("train") as stage:
        stage.emit_events(
            [
                EventEmission("epoch.started", "epoch 1 started"),
                EventEmission("epoch.completed", "epoch 1 completed"),
            ]
        )
        stage.register_artifact("checkpoint", Path("./artifacts/model.ckpt"), allow_missing=True)
```

This shows the core `Scribe` assembly principle:

1. create execution context first,
2. capture events and metrics inside that context,
3. attach outputs such as artifacts,
4. let sinks persist the result.

## Common First-Time Mistakes

### 1. Emitting without an active run

This raises `ContextError`.

Bad pattern:

```python
scribe.metric("training.loss", 0.42)
```

Good pattern:

```python
with scribe.run("training") as run:
    run.metric("training.loss", 0.42, aggregation_scope="step")
```

### 2. Treating `degraded` like total failure

In `Scribe`, degraded capture often means "some truth was preserved." It should be inspected, not
ignored.

### 3. Starting with too many scopes

At the beginning, it is fine to start with only `run`, then add `stage` and `operation` when your
workflow actually needs them.

### 4. Skipping local inspection

The fastest way to understand `Scribe` is often to inspect what the local sink actually wrote.

## The Core Intuition To Keep From This Page

In very short form:

- `Scribe` is introduced by opening a `run` and capturing a few runtime facts inside it,
- sinks decide where payloads go,
- lifecycle and environment capture happen automatically,
- `CaptureResult` tells you whether capture succeeded, degraded, or failed,
- local JSONL output is the easiest first inspection path.

If you want to compress it into one sentence:

"Start with one local sink, one run, one event, and one metric, then inspect the result before
adding more scope or complexity."

## What To Read Next

If this page made sense, the next useful pages are usually:

1. [Core Concepts](C:/Users/eastl/MLObservability/Scribe/docs/en/core-concepts.md) if you want the
   mental model of scopes, payload families, and result types.
2. [Capture Patterns](C:/Users/eastl/MLObservability/Scribe/docs/en/capture-patterns.md) if you
   want practical guidance on when to use events, metrics, spans, and batch APIs.
3. [Sinks and Storage](C:/Users/eastl/MLObservability/Scribe/docs/en/sinks-and-storage.md) if you
   want to understand local JSONL output and sink behavior.
4. [Degradation and Errors](C:/Users/eastl/MLObservability/Scribe/docs/en/degradation-and-errors.md)
   if you want to understand reduced-fidelity capture and operational failure modes.

## Related Files

- Public SDK entrypoint: [src/scribe/api/session.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/api/session.py)
- Result models: [src/scribe/results/models.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/results/models.py)
- Built-in sinks: [src/scribe/sinks/__init__.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/sinks/__init__.py)
- Training example: [examples/training_workflow.py](C:/Users/eastl/MLObservability/Scribe/examples/training_workflow.py)
