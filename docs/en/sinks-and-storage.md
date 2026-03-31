# Sinks and Storage

[User Guide Home](../USER_GUIDE.en.md)

Once `Scribe` starts capturing runtime truth, one question appears immediately:

"Where does that captured truth actually go?"

This page explains the sink boundary that answers that question. It is not only a page about local
files. It is the page that explains how `Scribe` hands canonical payloads off to storage or
forwarding layers, how payload-family support affects outcomes, and why degraded capture can appear
even when some data was still preserved successfully.

The goals of this page are:

1. explain why sinks are a separate layer in `Scribe`,
2. show how payload family dispatch works,
3. explain the behavior of the built-in sinks,
4. show how to inspect local JSONL output without guessing.

After reading this page, you should be able to understand not only how to configure a sink, but
also how sink behavior changes the meaning of `CaptureResult`, why some deliveries are marked as
skipped or degraded, and how to inspect captured payloads on disk with confidence.

## Why Sinks Exist As A Separate Layer

`Scribe` is designed so that capture logic and storage logic are not the same concern.

That distinction is extremely important in practice.

At runtime, `Scribe` is responsible for:

- creating lifecycle context,
- building canonical payloads,
- validating and normalizing capture shape,
- recording degraded capture as structured evidence,
- dispatching payloads by family.

But `Scribe` is intentionally not responsible for:

- deciding the persistence layout of every backend,
- deciding how transport happens,
- deciding whether captured truth is stored locally, forwarded remotely, or held only in memory.

That second responsibility belongs to sinks.

If this separation did not exist, several problems would appear quickly:

- every capture call would need to know too much about persistence,
- local development and backend-connected production would be tightly coupled,
- degraded capture caused by one storage path would be much harder to report clearly,
- introducing new output targets would require changing the capture logic itself.

So the sink boundary is not only an implementation convenience. It is one of the core design
choices that keeps `Scribe` vendor-agnostic, local-first, and operationally explainable.

## How To Think About The Sink Boundary

The easiest way to think about it is this:

- `Scribe` builds truth,
- sinks decide what to do with that truth.

The high-level flow looks like:

```text
runtime code
  -> Scribe scope and capture API
    -> canonical payload
      -> payload family dispatch
        -> one or more sinks
          -> storage or forwarding behavior
```

That means a sink is not "the place where `Scribe` becomes valid." The payload is already a
meaningful canonical object before a sink sees it. A sink is the next boundary where that canonical
object is persisted, forwarded, or inspected.

## Payload Families Come First

One of the most important ideas in `Scribe` storage behavior is that sinks do not just receive
"some payload." They receive payloads grouped into one of four families:

- `context`
- `record`
- `artifact`
- `degradation`

This family split matters because sinks can support some families and not others.

Examples:

- a sink may support only `record`,
- another may support all families,
- a local inspection sink may want every family,
- a specialized downstream target may only care about artifacts.

So payload routing in `Scribe` is not "send everything to every sink blindly." It is "dispatch each
payload by its family, and let each sink declare what it supports."

## The Sink Interface

The sink interface is intentionally small.

The core abstract type is [`Sink`](../../src/scribe/sinks/base.py).

At a high level, a sink provides:

- `name`
- `supported_families`
- `capture(family=..., payload=...)`

That small interface is one of the reasons the sink layer stays easy to reason about. A sink does
not need to know how the runtime scope was entered or how the payload was created. It only needs to
declare which families it supports and what it does when one of those payloads arrives.

This is also why the same `Scribe` instrumentation can be reused across:

- local JSONL inspection,
- tests,
- composite dispatch,
- future custom adapters.

## What Dispatch Actually Does

Internally, `Scribe` dispatches payloads through family-specific helpers such as:

- `dispatch_context(...)`
- `dispatch_record(...)`
- `dispatch_artifact(...)`
- `dispatch_degradation(...)`

Those all funnel into the common dispatch path implemented in
[`runtime/dispatch.py`](../../src/scribe/runtime/dispatch.py).

That dispatch logic does several things in one pass:

1. iterate through configured sinks,
2. check whether each sink supports the payload family,
3. attempt delivery for eligible sinks,
4. record per-sink delivery status,
5. determine whether the final result is `success`, `degraded`, or `failure`,
6. optionally emit a degradation-family payload when fidelity dropped.

That means sink dispatch is not merely "call capture on every sink." It is also the place where
delivery outcomes become structured operational data.

## Why A Capture Can Become Degraded

The sink layer is one of the main reasons `CaptureResult.status` can become `degraded`.

Common cases include:

- one sink failed but another accepted the payload,
- no sink supports the current payload family,
- a payload carried pre-existing degradation reasons, such as a missing artifact source,
- the sink path itself introduced warnings or delivery gaps.

This is an important operational point:

`degraded` does not mean "nothing was stored."

At the sink boundary, degraded usually means:

- at least some truth survived,
- but the storage or forwarding path did not preserve it perfectly.

That is why `Scribe` records:

- per-sink delivery results,
- degradation reasons,
- warnings,
- and sometimes a dedicated degradation-family payload.

## Built-In Sinks

The built-in sink set exposed at the public package boundary is:

- `LocalJsonlSink`
- `InMemorySink`
- `CompositeSink`

These are not redundant with one another. They serve different usage situations.

## `LocalJsonlSink`

`LocalJsonlSink` is the most important built-in sink for first-time and local-first usage.

Its implementation lives in
[`adapters/local/jsonl.py`](../../src/scribe/adapters/local/jsonl.py).

The reason this sink matters so much is that it gives `Scribe` a durable local path without
requiring any external infrastructure. That makes it ideal for:

- early integration,
- debugging,
- local experimentation,
- contract inspection,
- offline workflows.

### What It Writes

`LocalJsonlSink` writes one append-friendly JSONL file per payload family:

- `contexts.jsonl`
- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

Each line is a single JSON object with:

- `captured_at`
- `family`
- `payload`

That structure matters because it keeps the local format:

- easy to append,
- easy to inspect line by line,
- easy to parse with standard tools,
- easy to partition by payload family.

### Why Family-Separated Files Help

At first glance, one file for everything might seem simpler. But in real local debugging, family
separation is much easier to work with.

For example:

- if you want to inspect only lifecycle and environment truth, read `contexts.jsonl`,
- if you want to inspect only events, metrics, and spans, read `records.jsonl`,
- if you want to inspect output capture, read `artifacts.jsonl`,
- if you want to debug reduced-fidelity capture, read `degradations.jsonl`.

This keeps inspection focused and avoids mixing execution context with every other kind of payload
in one giant local stream.

### What Serialization Looks Like In Practice

Before writing, the sink converts dataclasses, enums, paths, lists, tuples, and dicts into JSON-
ready values. This means the local file is not storing opaque Python objects. It is storing
structurally inspectable JSON payloads that are suitable for debugging and local tooling.

The important point is that local JSONL here is not the canonical source of truth for the whole
architecture. It is one concrete adapter behind the sink boundary. The canonical meaning still
comes from the payloads `Scribe` created before the sink received them.

## `InMemorySink`

`InMemorySink` is a very different kind of sink.

Its implementation lives in
[`sinks/memory.py`](../../src/scribe/sinks/memory.py).

This sink stores actions in memory as tuples of:

- payload family
- payload object

That makes it very useful for:

- tests,
- local experiments,
- assertions over emitted payloads,
- situations where you want to inspect objects directly rather than inspect serialized files.

In practice, `InMemorySink` is much more useful for testing behavior than for long-lived runtime
storage.

Examples of good fit:

- asserting that `run.started` was emitted,
- verifying that a metric record reached the sink,
- confirming that a degradation-family payload was emitted during partial failure.

## `CompositeSink`

`CompositeSink` exists for a different reason again.

Its implementation lives in
[`sinks/composite.py`](../../src/scribe/sinks/composite.py).

This sink forwards incoming payloads to multiple child sinks. In effect, it acts like a grouped
sink that combines child support sets.

It is useful when you want one capture action to feed several outputs together.

Examples:

- keep a local JSONL audit trail while also collecting payloads in memory,
- group multiple custom sinks under one named sink,
- share one logical sink object across setup code while still reaching many targets.

Operationally, it is helpful to remember that `CompositeSink` does not remove the need to think
about downstream child failures. It only groups the fan-out behavior.

## What Happens When A Sink Does Not Support A Family

This is an important `Scribe` behavior to understand early.

If a sink does not support a payload family:

- the sink is not called for that family,
- a `Delivery` entry is recorded with `status=skipped`,
- and if no configured sink supports that family at all, the capture result can become `degraded`.

That means unsupported family behavior is visible and explicit. It does not vanish silently.

This matters because otherwise users could assume capture succeeded normally even when no sink was
actually able to store the payload family in question.

For example:

- a record-only sink may accept metrics and events,
- but artifact capture may become degraded because no sink supports `artifact`.

In that case, the right interpretation is not "artifact capture succeeded." It is "artifact capture
completed with reduced fidelity because no configured sink could accept that family."

## What Happens When A Sink Raises An Error

If a sink raises during capture:

- that sink gets a `Delivery` with `status=failure`,
- the failure detail is recorded,
- a degradation reason such as `sink_failure:<name>` is added,
- and the overall capture result is recalculated from all deliveries.

This leads to one of the most practically useful `Scribe` behaviors:

- if one sink fails but another succeeds, the overall result is usually `degraded`,
- if all eligible sinks fail, `Scribe` raises `SinkDispatchError`.

This is a healthy boundary because it preserves two different truths clearly:

- some failures should still preserve surviving capture,
- complete storage failure should not be mistaken for a successful operation.

## Why Degradation Payloads Can Be Emitted Automatically

When a non-degradation payload becomes degraded and there is an active run, `Scribe` may also emit
a dedicated degradation-family payload.

This behavior matters because it turns reduced-fidelity capture into first-class observability data.

Instead of leaving degradation only in the returned result object, `Scribe` can store evidence of
the capture problem in the same system of truth.

That means later readers can distinguish:

- payloads that were captured cleanly,
- payloads that were captured partially,
- and the evidence records that explain why fidelity dropped.

In local JSONL terms, that often means a degraded action can leave evidence in
`degradations.jsonl` as well as in the family-specific file that received the original payload.

## How To Configure A First Local Sink

The easiest starting configuration is:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)
```

This is the best first configuration because:

- it is durable,
- it is easy to inspect,
- it supports every payload family,
- it keeps the early operational story simple.

If you are trying to understand `Scribe`, this setup usually teaches you more than starting with a
more abstract or highly customized sink configuration.

## How To Inspect Local Output

The easiest inspection path is to use the sink helper methods directly.

```python
from pathlib import Path

from scribe import LocalJsonlSink, PayloadFamily

sink = LocalJsonlSink(Path("./.scribe"))
entries = sink.read_family(PayloadFamily.RECORD)
```

This gives you a list of parsed JSON objects for that family.

That is usually enough to answer practical questions like:

- did my event really get written,
- what family was this payload stored under,
- did a degradation-family record appear,
- what did the serialized local payload actually look like.

You can also ask the sink for the exact on-disk file:

```python
from pathlib import Path

from scribe import LocalJsonlSink, PayloadFamily

sink = LocalJsonlSink(Path("./.scribe"))
print(sink.path_for(PayloadFamily.ARTIFACT))
```

That is often useful when you want to open the file in an editor or hand it to another local tool.

## What A Normal Local Capture Sequence Looks Like

Suppose you run a simple workflow with one local sink and one run:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)

with scribe.run("quick-check") as run:
    run.event("run.note", message="quick check started")
    run.metric("training.loss", 0.42, aggregation_scope="step")
```

In local storage, you should expect to see:

- context-family payloads in `contexts.jsonl`,
- record-family payloads in `records.jsonl`,
- and usually no artifact or degradation entries unless those were actually captured.

That means local output will often look repetitive at first. This is expected. `Scribe` records
both the explicit facts you emitted and the lifecycle truth that gives those facts meaning.

## How To Think About Local JSONL Repetition

One of the first things people notice is that the local files may look repetitive.

For example, one run can produce:

- a `Run(status="running")` context payload,
- a `run.started` lifecycle record,
- your explicit event,
- your explicit metric,
- a `run.completed` lifecycle record,
- a `Run(status="completed")` context payload.

That repetition is not accidental duplication. It reflects different kinds of truth:

- context snapshots,
- lifecycle records,
- explicit user capture.

So local JSONL should be read as append-only operational truth, not as a deduplicated reporting
view.

## Storage Interpretation By Family

It helps to think about each family differently.

### `context`

This family tells you where execution happened.

Typical payloads:

- `Project`
- `Run`
- `StageExecution`
- `OperationContext`
- `EnvironmentSnapshot`

### `record`

This family tells you what happened or what was observed.

Typical payloads:

- structured events
- metrics
- spans
- lifecycle records

### `artifact`

This family tells you which durable outputs were registered.

Typical payloads:

- artifact bindings and manifests

### `degradation`

This family tells you where capture fidelity dropped.

Typical payloads:

- degradation evidence records

Once you read the local files through those meanings rather than just through filenames, the sink
layout becomes much easier to interpret.

## Good Sink Usage Patterns

The following patterns are usually healthy.

### Start With One Sink That Supports Everything

For first integration, `LocalJsonlSink` is almost always the safest choice.

### Use `InMemorySink` For Tests And Assertions

If the goal is to inspect emitted payload objects directly, in-memory capture is usually better than
reading files.

### Use Composite Behavior Deliberately

If you want to fan out capture to multiple child sinks, make sure you still reason about delivery
outcomes and failure interpretation clearly.

### Inspect Deliveries Instead Of Assuming Success

When debugging sink behavior, `CaptureResult.deliveries` is often more informative than only looking
at the top-level status.

## Common Sink Mistakes

### 1. Treating Sinks As If They Define Meaning

The sink does not decide what the payload means. It decides what happens to an already meaningful
payload.

### 2. Assuming Unsupported Families Are Harmless

If no sink supports a family, that is an operational signal. It often means the capture result
should be read as degraded, not as normally persisted.

### 3. Ignoring `degradations.jsonl`

When local debugging reduced-fidelity behavior, the degradation-family file is often the most
informative file in the directory.

### 4. Using Only A Record-Oriented View Of The Output

If you inspect only `records.jsonl`, you can miss the context and degradation data that explains how
to interpret those records.

### 5. Confusing Local Storage With The Whole Architecture

`LocalJsonlSink` is a concrete local adapter, not the definition of the overall `Scribe`
architecture.

## The Core Intuition To Keep From This Page

In very short form:

- `Scribe` builds canonical truth first and hands it to sinks afterward,
- sinks operate by payload family rather than by one undifferentiated stream,
- delivery results shape `CaptureResult`,
- local JSONL output is an inspection-friendly operational view of captured payloads,
- degraded capture at the sink boundary is explicit and inspectable rather than hidden.

The most important sentence to keep is this:

`Scribe` owns capture meaning, while sinks own what happens to that meaning once it leaves the
capture path.

## What To Read Next

If this page made sense, the most useful next pages are usually:

1. [Degradation and Errors](degradation-and-errors.md)
   if you want a deeper understanding of how sink failures and reduced fidelity are reported.
2. [Artifacts](artifacts.md) if you want to
   understand a family where degraded capture is especially common in practice.
3. [Examples](examples.md) if you want to see sink
   usage inside larger end-to-end flows.

## Related Files

- Sink interface: [src/scribe/sinks/base.py](../../src/scribe/sinks/base.py)
- Composite sink: [src/scribe/sinks/composite.py](../../src/scribe/sinks/composite.py)
- In-memory sink: [src/scribe/sinks/memory.py](../../src/scribe/sinks/memory.py)
- Local JSONL sink: [src/scribe/adapters/local/jsonl.py](../../src/scribe/adapters/local/jsonl.py)
- Dispatch logic: [src/scribe/runtime/dispatch.py](../../src/scribe/runtime/dispatch.py)
