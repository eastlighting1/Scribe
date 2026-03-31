# Degradation and Errors

[User Guide Home](C:/Users/eastl/MLObservability/Scribe/docs/en/README.md)

One of the most important parts of understanding `Scribe` is learning how it talks about things
going wrong.

Most instrumentation libraries collapse failure into a single vague idea:

- either the user sees nothing,
- or a call raises,
- or a warning is lost inside logs.

`Scribe` takes a more structured approach.

Instead of treating every imperfect capture outcome as the same event, it separates several
different situations:

- capture succeeded normally,
- capture preserved some truth but fidelity dropped,
- capture failed completely at the eligible sink boundary,
- usage was invalid before capture could even begin.

This page explains those differences.

The goals of this page are:

1. explain what `success`, `degraded`, and `failure` really mean,
2. show how `CaptureResult` and `BatchCaptureResult` should be interpreted operationally,
3. explain when `Scribe` raises exceptions and when it preserves partial truth instead,
4. help you debug the most common failure and reduced-fidelity paths.

After reading this page, you should be able to distinguish:

- a clean capture,
- a partially preserved capture,
- a total sink dispatch failure,
- and an invalid call that never had valid runtime context in the first place.

## Why Degradation Exists At All

At first glance, it may seem simpler to treat all imperfect capture as failure.

But in real ML workflows, that is often too blunt.

For example:

- one sink may fail while another sink still preserves the payload,
- an artifact may be logically known before its file body exists,
- a file may exist but hash computation may fail,
- no configured sink may support one payload family even though others are working normally.

In each of those cases, some truth still exists.

If the system throws all of that away under one generic failure state, later analysis becomes much
weaker. You lose the difference between:

- "nothing was preserved"
- and "the system preserved part of the truth, but not all of it."

`Scribe` keeps that difference explicit through degradation semantics.

That is why this page matters so much. If you misunderstand `degraded`, you misunderstand one of the
core operational behaviors of the library.

## The Three Main Capture Outcomes

At the top level, most single capture calls produce one of three outcomes:

- `success`
- `degraded`
- `failure`

These are represented through `DeliveryStatus` in
[`results/models.py`](C:/Users/eastl/MLObservability/Scribe/src/scribe/results/models.py).

### `success`

`success` means:

- at least one eligible sink accepted the payload,
- and no degradation reasons were attached to that capture path.

This is the clean path.

### `degraded`

`degraded` means:

- some truth was captured,
- but fidelity dropped for some reason.

This is not just a cosmetic label. It is a structured statement that the capture should still be
used, but interpreted with more care.

### `failure`

`failure` means:

- no eligible sink successfully captured the payload,
- and from the dispatch point of view, the capture could not be preserved as a successful or
  degraded result.

In the current implementation, all-eligible-sink failure raises `SinkDispatchError`.

So in practice, total failure often appears as an exception rather than as a quietly returned
`CaptureResult(status="failure")`.

## Why `degraded` Is Not A Soft Version Of Failure

This is the most important distinction in the whole page.

`degraded` is not "almost failed."

It is closer to:

"the system still has meaningful truth, but the capture was not complete or clean enough to call a
fully successful delivery."

That difference matters because degraded capture is often still operationally valuable.

Examples:

- a metric reached a local sink even though a secondary sink failed,
- an artifact binding preserved output identity and path even though the file was missing,
- a degradation record itself was emitted so that the reduced-fidelity event can be inspected later.

If you treat degraded capture as disposable, you often throw away the exact evidence that explains a
partial operational incident.

## How `CaptureResult` Should Be Read

Every single-item capture returns a `CaptureResult`.

Important fields include:

- `family`
- `status`
- `deliveries`
- `warnings`
- `degradation_reasons`
- `payload`
- `degradation_emitted`
- `degradation_payload`

This means a capture result is not only "did the method work." It is a compact operational report of
what happened at the dispatch boundary.

### `status`

This is the first field you should inspect.

It answers:

- was the capture clean,
- partially preserved,
- or unable to survive eligible dispatch.

### `deliveries`

This is often the most informative field during debugging.

Each `Delivery` tells you:

- which sink was considered,
- which family was being delivered,
- whether that sink marked the payload as success, failure, or skipped,
- and an optional detail string.

So if you are trying to understand "why did this capture degrade," `deliveries` often tells the
story more precisely than the top-level status alone.

### `warnings`

Warnings are human-readable messages that explain reduced fidelity or sink-side problems.

They are especially useful when:

- a sink raised,
- a family had no supporting sink,
- artifact verification dropped fidelity.

### `degradation_reasons`

This field is the structured machine-readable explanation of why fidelity dropped.

Typical reasons include:

- `sink_failure:<name>`
- `no_sinks_configured:<family>`
- `no_sink_support_for_family:<family>`
- `artifact_missing_at_registration`
- `artifact_hash_unavailable`

These values matter because they make degradation queryable and classifiable later.

### `degradation_emitted`

This field tells you whether a dedicated degradation-family payload was also emitted.

That matters because reduced-fidelity capture is not only returned to the caller. It can also
become part of the persisted truth model.

## How `BatchCaptureResult` Should Be Read

Batch capture returns `BatchCaptureResult`.

Important fields include:

- `status`
- `results`
- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`

This gives you a higher-level summary across many single-item captures.

The important point is that batch status is not independent of item results. It is derived from
them.

So if a batch is degraded, the right next question is usually:

"Which items were degraded and why?"

That means the normal debugging flow is:

1. inspect batch-level counts,
2. then inspect individual `CaptureResult` entries.

## Where Degradation Usually Comes From

In the current implementation, degradation usually comes from two broad sources:

- the dispatch/sink boundary,
- or the payload-specific capture logic.

Understanding that split makes debugging much faster.

## Sink-Side Degradation

The dispatch path in
[`runtime/dispatch.py`](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/dispatch.py)
is the main place where sink-related degradation is created.

Typical sink-side degraded cases:

### 1. One Sink Failed, Another Succeeded

Example situation:

- local JSONL sink accepts a record,
- a second sink raises an exception.

In that case:

- the payload still survived somewhere,
- but fidelity across configured sinks was reduced,
- so the result becomes `degraded`.

### 2. No Sinks Configured

If a session is created without sinks and capture proceeds, `Scribe` records:

- a degradation reason for missing sinks,
- warnings describing the situation,
- and a degraded result instead of pretending that persistence happened.

This is important because no-sink operation is still an explicit operational state. It is not the
same thing as successful storage.

### 3. No Sink Supports The Payload Family

Example:

- you configure a sink that supports only `record`,
- then try to register an artifact.

In that case:

- the sink is marked as `skipped` for `artifact`,
- no eligible sink supports that family,
- and the result becomes degraded.

This makes unsupported-family behavior visible instead of silently dropping the payload.

## Capture-Logic Degradation

Not all degradation comes from sinks.

Some degraded states originate earlier during payload-specific capture logic.

Artifact registration is the clearest example.

The artifact service in
[`artifacts/service.py`](C:/Users/eastl/MLObservability/Scribe/src/scribe/artifacts/service.py)
can attach degradation reasons before dispatch even begins.

Examples:

### 1. Artifact Missing At Registration

If a caller uses:

```python
run.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    allow_missing=True,
)
```

and the file does not exist, `Scribe` can still:

- preserve artifact identity,
- preserve target path,
- build the manifest and binding,
- and return a degraded result rather than a hard validation failure.

This is one of the strongest examples of `degraded` meaning "partial truth survived."

### 2. Artifact Hash Unavailable

If the file exists but hash computation fails, `Scribe` can preserve the artifact binding while
still recording that integrity verification was incomplete.

Again, the important point is that partial truth is not discarded.

## Why Degradation Payloads Can Be Emitted

When a non-degradation payload becomes degraded and there is an active run, `Scribe` may also emit a
degradation-family payload automatically.

This matters because it upgrades "reduced fidelity happened" from a returned result detail into a
first-class captured fact.

Practically, that means a degraded capture can leave two kinds of traces:

- the original payload under its own family,
- and a degradation-family record that explains the quality drop.

This is extremely useful for later inspection, especially when using `LocalJsonlSink`.

It also reveals an important design principle:

`Scribe` does not treat degradation as hidden implementation noise. It treats it as observability
truth about the capture process itself.

## How Exceptions Fit Into This Model

Not every problem becomes a degraded result.

Some problems are treated as invalid usage or complete dispatch failure and therefore raise
exceptions.

That separation is healthy because it keeps three different categories apart:

- invalid inputs or invalid context,
- partially preserved capture,
- total eligible-sink failure.

## `ValidationError`

`ValidationError` means invalid data was supplied to the SDK.

This happens before normal capture can proceed safely.

Examples:

- empty `project_name`
- empty metric or event keys
- unsupported metric aggregation scope
- empty artifact kind
- missing artifact path when strict existence is required

This kind of failure is not a degraded capture state. It is a contract problem at the caller
boundary.

In other words, `ValidationError` means:

"the SDK was asked to do something that did not satisfy basic capture rules."

## `ContextError`

`ContextError` means lifecycle state is missing or inconsistent.

The most common example is trying to capture something that requires an active run when no run is
active.

Examples:

- `scribe.event(...)` without a run
- `scribe.metric(...)` without a run
- creating a stage without an active run
- asking for `current_run()` when there is no active run scope

This is important because context is not optional in `Scribe`. The library is explicitly designed
around lifecycle state, so missing context is treated as a real error rather than a recoverable
guessing situation.

### `ClosedScopeError`

`ClosedScopeError` is a more specific lifecycle error.

It means a scope that has already been closed is being used again.

This is helpful because it prevents confusing silent capture after the lifecycle boundary has ended.

## `SinkDispatchError`

`SinkDispatchError` means all eligible sinks failed to capture the payload.

This is the main exception that corresponds to total dispatch failure.

The important word there is "eligible."

If a sink does not support the family, it is skipped.
If every sink that could have handled the family fails, dispatch raises.

So `SinkDispatchError` means:

"capture reached the storage/forwarding boundary, but nothing eligible preserved it."

That is very different from degraded capture, where at least some truth survived.

## A Useful Mental Model For Errors Versus Degradation

It helps to think in the following sequence:

### Before capture can begin

If the input or context is invalid:

- `ValidationError`
- `ContextError`
- `ClosedScopeError`

### During capture, while some truth can still survive

If capture loses fidelity but still preserves meaning:

- `CaptureResult.status == "degraded"`

### At the eligible dispatch boundary when nothing survives

If all eligible sinks fail:

- `SinkDispatchError`

This three-way split is one of the cleanest parts of the current `Scribe` design.

## What To Inspect First When Something Looks Wrong

When debugging capture behavior, the fastest inspection order is usually:

1. Did the call raise an exception
2. If not, what is `CaptureResult.status`
3. If degraded, what do `degradation_reasons` say
4. What do `warnings` say
5. What do per-sink `deliveries` show
6. Was a degradation payload emitted
7. If using `LocalJsonlSink`, what appears in `degradations.jsonl`

This order matters because it moves from:

- hard failure,
- to partial survival,
- to sink-specific explanation,
- to persisted evidence.

## How To Read `deliveries`

This field is easy to overlook, but it is often the most useful debugging surface.

A delivery can be:

- `success`
- `failure`
- `skipped`

That means you can distinguish:

- the sink that stored the payload,
- the sink that raised,
- and the sink that was never eligible for this family.

That is a much better operational story than a flat boolean result.

In practice, when you see `degraded`, `deliveries` is often where the true cause becomes obvious.

## What To Look For In Local JSONL

When using `LocalJsonlSink`, reduced-fidelity behavior often leaves a visible trace on disk.

The most important files are:

- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

Examples:

- a degraded artifact registration may still appear in `artifacts.jsonl`,
- while the degradation explanation appears in `degradations.jsonl`.

This is one of the reasons local JSONL inspection is so useful. It lets you verify not only that
capture was attempted, but also whether quality-loss evidence was preserved properly.

## Common Failure Stories And Their Meaning

### Story 1. "My artifact call returned degraded"

Most likely interpretations:

- the file was missing and `allow_missing=True`,
- hash computation failed,
- or sink-side fidelity dropped after the artifact payload was built.

The right response is not "artifact capture failed completely." The right response is "inspect the
degradation reasons and the binding state."

### Story 2. "My capture call raised immediately"

Most likely interpretations:

- invalid input
- invalid context
- or all eligible sinks failed

The right next step is to determine which exception class was raised before assuming this was a
degradation issue.

### Story 3. "Nothing appears in the expected storage path"

Most likely interpretations:

- no sink was configured,
- the sink did not support the payload family,
- or a sink dispatch failure occurred.

That is why storage debugging should begin with `deliveries` rather than only with filesystem
inspection.

## Common Mistakes

### 1. Treating `degraded` As If It Means "ignore this result"

In `Scribe`, degraded often contains exactly the information you need to explain partial operational
failure.

### 2. Looking Only At The Top-Level Status

If you skip `deliveries`, `warnings`, and `degradation_reasons`, you often miss the real cause.

### 3. Confusing Invalid Usage With Capture Degradation

An empty artifact kind or missing run context is not a degraded capture path. It is a contract or
lifecycle error.

### 4. Assuming A Sink Failure Always Means Total Failure

If another sink succeeded, the correct interpretation is often degradation, not total loss.

### 5. Forgetting To Inspect Degradation Evidence On Disk

When using local JSONL storage, the degradation-family file is often the clearest explanation of
what happened.

## The Core Intuition To Keep From This Page

In very short form:

- `Scribe` separates invalid usage, partial truth preservation, and total eligible-sink failure,
- `degraded` means fidelity dropped but meaningful capture survived,
- exceptions usually indicate invalid input/context or total dispatch failure,
- `CaptureResult` is an operational report, not just a success flag,
- degradation can become first-class persisted evidence.

The single most important sentence to keep is this:

In `Scribe`, reduced-fidelity capture is something to inspect and preserve, not something to blur
together with complete failure.

## What To Read Next

If this page made sense, the most useful next pages are usually:

1. [Sinks and Storage](C:/Users/eastl/MLObservability/Scribe/docs/en/sinks-and-storage.md) if you
   want to understand where degraded evidence and deliveries come from.
2. [Artifacts](C:/Users/eastl/MLObservability/Scribe/docs/en/artifacts.md) if you want to see the
   most common practical source of degraded capture.
3. [API Reference](C:/Users/eastl/MLObservability/Scribe/docs/en/api-reference.md) if you want a
   compact lookup of result models and exception types.

## Related Files

- Exceptions: [src/scribe/exceptions.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/exceptions.py)
- Result models: [src/scribe/results/models.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/results/models.py)
- Dispatch logic: [src/scribe/runtime/dispatch.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/dispatch.py)
- Artifact service: [src/scribe/artifacts/service.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/artifacts/service.py)
- Runtime session: [src/scribe/runtime/session.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/session.py)
