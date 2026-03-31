# Core Concepts

[User Guide Home](C:/Users/eastl/MLObservability/Scribe/docs/en/README.md)

When people first see `Scribe`, the first question is usually not "what fields exist," but "where
in my workflow should I put this library, and what exactly will it capture for me." This page is
the conceptual guide that answers that question.

The goals of this document are:

1. explain the runtime shape of `Scribe`,
2. show why `run`, `stage`, and `operation` are separate scopes,
3. explain the four payload families that `Scribe` dispatches,
4. clarify how capture results should be interpreted operationally,
5. show where `Scribe` ends and `Spine` begins.

After reading this page, you should be able to place `Scribe` into a real Python workflow without
treating it like a generic logging helper.

## The Core Question For Understanding Scribe

The most important question in `Scribe` is not only "what did we emit," but "inside which runtime
context was it emitted, and what truth did the library preserve automatically."

That is why `Scribe` is organized around:

- explicit lifecycle scopes,
- canonical payload families,
- structured capture outcomes,
- sink dispatch,
- reproducibility-aware context.

If you keep those five ideas in mind, the rest of the API becomes much easier to read.

## What Scribe Actually Does

At a high level, `Scribe` is the capture-side SDK of the stack.

It helps your code:

- create lifecycle boundaries for a running workflow,
- convert runtime facts into canonical objects,
- attach execution context automatically,
- dispatch those objects to one or more sinks,
- preserve degraded capture as evidence rather than hiding it.

The typical flow looks like this:

```text
create Scribe session
  -> enter run
    -> optionally enter stage
      -> optionally enter operation
        -> emit event / metric / span / artifact
          -> receive CaptureResult
            -> let sinks persist or forward payloads
```

This means `Scribe` is much closer to "runtime capture orchestration" than to "a loose logging
utility."

## Why Lifecycle Scopes Exist

If all observability calls were emitted with no explicit scope, the data would still exist, but it
would become much harder to answer questions like:

- which run did this metric belong to,
- did this event happen in training or evaluation,
- which step or request produced this span,
- which artifact belongs to which execution context.

That is why `Scribe` models capture context explicitly.

## Lifecycle Scopes

`Scribe` uses three nested scopes:

- `run`: one logical execution
- `stage`: a major phase inside a run
- `operation`: a smaller unit of work inside the active context

Typical nesting:

```python
with scribe.run("baseline-train") as run:
    with run.stage("prepare-data") as stage:
        stage.metric("data.rows", 128_000, aggregation_scope="dataset")

    with run.stage("train") as stage:
        with stage.operation("step-1") as operation:
            operation.metric("training.loss", 0.42, aggregation_scope="step")
            operation.span("model.forward", span_kind="model_call")
```

### How To Think About `run`

`run` is the top-level execution unit.

Examples:

- one training job
- one evaluation pass
- one batch processing execution
- one longer-lived serving session

If you need a single answer to "what execution does this belong to," the answer is usually the run.

### How To Think About `stage`

`stage` is a major phase inside a run.

Examples:

- `prepare-data`
- `train`
- `evaluate`
- `register`

You do not always need stages, but once your workflow has meaningful internal phases, stage-level
capture makes later debugging and analysis much easier.

### How To Think About `operation`

`operation` is a finer-grained unit of work.

Examples:

- one training step
- one batch
- one request
- one model call

This level matters when metrics or traces become dense enough that run-level or stage-level context
is too coarse.

## Why The Scope Levels Are Separate

The separation exists for the same reason in every real system:

- if you model too coarsely, you lose operational detail
- if you model too finely, you lose the larger execution picture
- most observability analysis needs both

In that sense, `Scribe` scopes are really a way of splitting runtime meaning:

- `run`: execution scope
- `stage`: phase scope
- `operation`: fine-grained work-unit scope

## What Happens Automatically When You Enter Scopes

This is one of the most important concepts in the whole library.

`Scribe` does not only capture what you emit manually. It also captures lifecycle truth
automatically.

Entering and exiting scopes causes `Scribe` to emit:

- `Project`
- `Run`
- `StageExecution`
- `OperationContext`
- lifecycle records such as `run.started`, `stage.completed`, and `operation.failed`
- `EnvironmentSnapshot` at run start when enabled

So a `run` is not just a context manager convenience. It is a trigger for structured lifecycle
capture.

## Payload Families

Every capture action dispatches one of four payload families:

- `context`
- `record`
- `artifact`
- `degradation`

These families are important because sink support is defined at this level.

## What Each Payload Family Means

### `context`

Context payloads describe execution background.

Examples:

- `Project`
- `Run`
- `StageExecution`
- `OperationContext`
- `EnvironmentSnapshot`

These answer "where did this happen."

### `record`

Record payloads describe observed runtime facts.

Examples:

- structured events
- metrics
- spans
- lifecycle event records

These answer "what happened."

### `artifact`

Artifact payloads describe durable outputs or output bindings.

Examples:

- checkpoints
- evaluation reports
- exported files

These answer "what execution output was produced or registered."

### `degradation`

Degradation payloads preserve reduced-fidelity capture as explicit evidence.

Examples:

- one sink failed but another accepted the payload
- an artifact was registered before the file existed
- a capture family had no supporting sink

These answer "what quality loss happened during capture."

## Why Payload Families Are Separate

Without this boundary, sink behavior becomes harder to reason about.

For example, a sink may:

- support records and artifacts,
- skip context,
- fully ignore degradation payloads.

By keeping the families explicit, `Scribe` can express:

- what kind of truth was produced,
- which sinks were eligible to receive it,
- whether reduced support caused degraded capture.

This is one of the reasons `Scribe` stays vendor-agnostic while still being operationally useful.

## The Public API Shape

The top-level `Scribe` object exposes the public capture entrypoints:

- `Scribe.run(...)`
- `Scribe.event(...)`
- `Scribe.metric(...)`
- `Scribe.span(...)`
- `Scribe.register_artifact(...)`
- `Scribe.emit_events(...)`
- `Scribe.emit_metrics(...)`

Scope objects expose the same capture primitives in the active context:

- `RunScope.stage(...)`
- `StageScope.operation(...)`
- `scope.event(...)`
- `scope.metric(...)`
- `scope.span(...)`
- `scope.register_artifact(...)`
- `scope.emit_events(...)`
- `scope.emit_metrics(...)`

This means you can think about the API in a very simple way:

- top-level calls use the current active scope
- scope-level calls make that context explicit in the code

## Capture Outcomes

Single-item capture returns `CaptureResult`.
Batch capture returns `BatchCaptureResult`.

The most important status values are:

- `success`
- `degraded`
- `failure`

There is also a per-delivery status model that includes `skipped`.

## How To Read `CaptureResult`

`CaptureResult` is not just a success flag. It is a structured explanation of what happened during
capture.

Important fields:

- `family`
- `status`
- `deliveries`
- `warnings`
- `degradation_reasons`
- `payload`
- `degradation_emitted`

The convenience properties matter too:

- `succeeded`
- `degraded`

The most important operational idea is this:

- `success` means the payload was fully accepted by eligible sinks
- `degraded` means some truth was preserved, but fidelity dropped
- `failure` means all eligible sinks failed

So degraded capture is not the same thing as total failure.

## How To Read `BatchCaptureResult`

Batch capture summarizes the outcomes of multiple individual captures.

Important fields and properties:

- `status`
- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`
- `results`

This makes batch capture useful in hot paths where you still need structured operational feedback.

## Reproducibility Context

Run scopes can carry reproducibility fields:

- `code_revision`
- `config_snapshot`
- `dataset_ref`

These values are attached to canonical payload extensions for downstream consumers.

In practice, this is the layer that helps connect runtime observability to reproducibility and audit
questions.

For example:

```python
with scribe.run(
    "training",
    code_revision="abc123def",
    config_snapshot={"lr": 0.001, "batch_size": 32},
    dataset_ref="imagenet-v1",
) as run:
    run.metric("training.loss", 0.42, aggregation_scope="step")
```

`Scribe` can also preserve:

- run-level `tags`
- run-level `metadata`
- stage-level `metadata`
- operation-level `metadata`
- event-level `tags`

So reproducibility and capture metadata are not an afterthought. They are part of the active
runtime context.

## What `current_run`, `current_stage`, And `current_operation` Mean

`Scribe` exposes:

- `current_run()`
- `current_stage()`
- `current_operation()`

These methods return the currently active task-local scope when it exists.

They are useful when helper code needs to emit capture without explicitly receiving the scope
object as a parameter. But the important thing to remember is that these methods only make sense
inside an active lifecycle context. Outside that context, `ContextError` is the expected result.

## Where Scribe Ends And Spine Begins

This boundary is important.

`Scribe` and `Spine` are aligned, but they are not the same library.

`Scribe` owns:

- lifecycle orchestration
- runtime capture flow
- sink dispatch
- degraded capture handling
- high-level SDK ergonomics

`Spine` owns:

- canonical object models
- validation rules
- serialization semantics
- compatibility and migration logic

So if you are asking:

- "where should I open a run"
- "what gets emitted automatically"
- "how should I interpret degraded capture"

that is `Scribe`.

If you are asking:

- "what exactly does this canonical object mean"
- "how is this payload validated"
- "how is legacy schema upgraded"

that is `Spine`.

## Common Conceptual Mistakes

### 1. Treating `Scribe` as a generic logger

It can emit event-like records, but its real value is contextual capture, lifecycle automation, and
structured sink dispatch.

### 2. Opening too few scopes

If everything is captured at the run level, stage- and operation-level interpretation becomes much
harder later.

### 3. Opening too many scopes

If every tiny internal function call becomes an operation, the signal can become noisy quickly.

### 4. Treating `degraded` as equivalent to failure

This hides an important operational distinction. Degraded capture often still preserves useful truth
and can emit explicit degradation evidence.

### 5. Assuming `Scribe` replaces `Spine`

`Scribe` is the capture SDK, not the schema-definition library. They work together, but they solve
different problems.

## The Core Intuition To Keep From This Page

In very short form:

- `Scribe` structures runtime capture around `run`, `stage`, and `operation`
- every capture action produces one of four payload families
- capture results explain not only success or failure, but also degraded fidelity
- `Scribe` owns runtime orchestration, while `Spine` owns the canonical contract

If you keep those four points in mind, the rest of the `Scribe` documentation becomes much easier
to navigate.

## What To Read After This Page

If this page explained "how the runtime is shaped," the next pages explain "how to choose the
right capture primitive" and "how that capture behaves operationally."

- event, metric, span, and batch guidance:
  [Capture Patterns](C:/Users/eastl/MLObservability/Scribe/docs/en/capture-patterns.md)
- sink behavior and local inspection:
  [Sinks and Storage](C:/Users/eastl/MLObservability/Scribe/docs/en/sinks-and-storage.md)
- reduced-fidelity capture and error interpretation:
  [Degradation and Errors](C:/Users/eastl/MLObservability/Scribe/docs/en/degradation-and-errors.md)

The most natural next page is usually
[Capture Patterns](C:/Users/eastl/MLObservability/Scribe/docs/en/capture-patterns.md).
