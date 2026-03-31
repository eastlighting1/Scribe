# Artifacts

[User Guide Home](../USER_GUIDE.en.md)

When teams first instrument `Scribe`, they often begin with events and metrics. Very quickly,
however, another question appears:

"How do I capture the outputs my workflow produced, not just the facts it observed while running?"

This page exists to answer that question.

In `Scribe`, artifact capture is not treated as a side note or a plain file-path helper. It is a
structured binding flow that records not only where an output lives, but also what kind of output it
is, what verification policy was applied, how complete the binding was, and which execution context
the output belongs to.

The goals of this page are:

1. explain why artifact capture is its own pattern in `Scribe`,
2. show what happens during `register_artifact(...)`,
3. explain the difference between successful and degraded artifact binding,
4. help you decide when to use artifact capture rather than just record a path in an event.

After reading this page, you should be able to understand artifact registration as a structured
capture flow rather than a convenience wrapper around `Path`.

## Why Artifacts Are Their Own Capture Shape

At first glance, it can seem like an artifact could be represented any of the following ways:

- an event with a message containing a file path,
- a metric tag that points to an output file,
- a plain file path stored elsewhere outside observability capture,
- a dedicated artifact registration call.

`Scribe` chooses the fourth option deliberately.

That choice matters because a durable output such as a checkpoint, evaluation report, or exported
dataset is not just another runtime occurrence. It is a result that remains after execution and must
often be explained later.

Questions like these appear quickly in real workflows:

- which run produced this checkpoint,
- which stage generated this evaluation report,
- was the file actually present at registration time,
- was a hash computed,
- was the artifact fully bound or only partially known,
- should a missing file fail hard or remain as degraded evidence.

A plain path string does not answer those questions well. `Scribe` artifact capture exists so those
questions stay answerable.

## The Core Idea: Binding, Not Just Logging

The most important thing to understand is that `Scribe` does not treat artifact registration as
"write a file location into a payload." It treats it as a binding operation between:

- an artifact identity,
- a source location,
- a verification policy,
- a canonical artifact manifest,
- and the active execution context.

That is why the public method is:

```python
run.register_artifact(...)
```

rather than something like:

```python
run.log_file(...)
```

The point is not merely to remember that a file existed. The point is to capture a structured claim
about an output and how strongly that output was bound at registration time.

## The Public Artifact Capture Flow

At the top level, artifact capture looks like this:

```python
from pathlib import Path

stage.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    compute_hash=True,
)
```

This is the simplest public form, but several steps happen underneath it:

1. the active run context is required,
2. the source path is normalized,
3. source existence is checked,
4. a verification policy is created,
5. an artifact registration request is built,
6. an `ArtifactManifest` is built,
7. an `ArtifactBinding` is assembled,
8. the artifact-family payload is dispatched to sinks,
9. degraded capture may also emit a degradation-family payload if fidelity dropped.

That means artifact registration is one of the richest capture flows in `Scribe`. It carries both
output identity and capture-quality semantics.

## The Main Models Behind Artifact Capture

The artifact models live in
[`artifacts/models.py`](../../src/scribe/artifacts/models.py).

The most important ones are:

- `ArtifactSource`
- `ArtifactVerificationPolicy`
- `ArtifactRegistrationRequest`
- `ArtifactBinding`

And the canonical manifest is built through `Spine`-aligned payload construction.

The easiest way to think about those roles is:

- `ArtifactSource`: where the bytes currently come from
- `ArtifactVerificationPolicy`: what verification is expected
- `ArtifactRegistrationRequest`: what the caller asked to bind
- `ArtifactBinding`: the actual operational artifact-capture payload
- `ArtifactManifest`: the canonical output description attached inside the binding

So `Scribe` artifact capture is not one flat object. It is a layered representation of request,
source, canonical output, and resulting binding state.

## `ArtifactSource`

`ArtifactSource` expresses where artifact bytes currently come from.

At the moment, the main source kind in current `Scribe` usage is path-based registration.

Important source fields include:

- `kind`
- `uri`
- `exists`

This is useful because `Scribe` can distinguish between:

- an artifact that points to a path that already exists,
- an artifact that points to a path expected to exist later,
- and, conceptually, other source forms such as staged paths or URIs.

The important point is that source location is explicit and inspectable rather than buried inside a
human-readable message.

## `ArtifactVerificationPolicy`

One of the more important ideas in this artifact system is that verification expectations are part
of the request.

Current key fields:

- `compute_hash`
- `require_existing_source`

This matters because operational behavior changes depending on what the caller requested.

For example:

- some workflows want strong verification and should fail immediately if the file is missing,
- some workflows know the logical artifact before the file exists and want a degraded binding
  instead of a hard failure,
- some workflows want to skip hashing for speed or cost reasons.

Without an explicit verification policy, those differences would be hidden in ad hoc calling
conventions. `Scribe` makes them part of the structured capture contract.

## `ArtifactRegistrationRequest`

This model represents what the user asked `Scribe` to bind.

Its important fields include:

- `artifact_ref`
- `artifact_kind`
- `source`
- `verification_policy`
- `attributes`

This request object matters because it preserves caller intent distinctly from final binding
outcome.

That distinction is useful operationally. The request says:

- what artifact kind the caller intended,
- what source they pointed to,
- how strict verification was supposed to be,
- what extra metadata was supplied.

The final binding, by contrast, says how that request actually turned out in runtime conditions.

## `ArtifactBinding`

`ArtifactBinding` is the central output of `Scribe` artifact capture.

It contains:

- the original request,
- the canonical manifest,
- the source,
- project and operation context fields,
- binding status,
- completeness and degradation markers,
- artifact-level attributes.

This is why artifact capture in `Scribe` is best understood as a binding process. The final payload
preserves both:

- what was being bound,
- and how complete or degraded that binding was.

### Binding Status

Current binding statuses include:

- `BOUND`
- `PENDING`
- `DEGRADED`

In the current implementation, the most common statuses you will observe are:

- `BOUND` when the artifact was captured cleanly,
- `DEGRADED` when fidelity dropped, such as when the path was missing at registration time.

Even if your workflow does not use every binding state yet, the model is intentionally richer than a
simple success/failure boolean because artifact capture often exists in partially-known states.

## `ArtifactManifest`

The binding carries an `ArtifactManifest` that comes from the canonical contract layer.

Practically, that manifest gives the artifact a structured identity inside the active execution
context.

Important fields include:

- artifact ref
- artifact kind
- created time
- producer ref
- run ref
- stage execution ref when available
- location ref
- hash value
- size bytes
- attributes

That means an artifact in `Scribe` is not just "a path on disk." It is a canonical output object
connected to the run and stage in which it was registered.

## A Simple Successful Artifact Binding

The most straightforward artifact path is a file that already exists.

```python
from pathlib import Path

with scribe.run("training") as run:
    result = run.register_artifact(
        "checkpoint",
        Path("./artifacts/model.ckpt"),
        compute_hash=True,
    )
```

If the file exists and hashing succeeds, the usual result is:

- `CaptureResult.status == "success"`
- `ArtifactBinding.binding_status == "bound"`
- `hash_value` is present
- `size_bytes` is present

This is the cleanest artifact path because the logical artifact, the source file, and the canonical
manifest all line up without loss.

## Why `artifact_kind` Matters

`artifact_kind` is one of the most important inputs to artifact capture.

Examples:

- `checkpoint`
- `evaluation-report`
- `dataset`
- `feature-snapshot`

This value is more than a label. It is the primary statement of what kind of output the artifact
represents.

In practice, it is usually best to keep this vocabulary stable and relatively small. If the same
kind of output is referred to as `checkpoint`, `model_checkpoint`, `ckpt`, and `trained-model`
across the same system, consumers will have to reconstruct shared meaning later in much messier
ways.

A healthy pattern is:

- keep `artifact_kind` narrow and stable,
- put finer distinctions into attributes,
- introduce a new kind only when it really signals a different class of output.

## When To Use `attributes`

Artifact attributes are the right place for metadata that is useful but not part of the core binding
shape.

Examples:

- framework
- dtype
- split
- export format
- internal output category

That makes attributes a good place for output-local details, while the top-level artifact fields
should keep the universally important structure.

In other words:

- top-level fields should answer what every consumer needs to know,
- attributes should answer what some consumers may want to inspect later.

## `compute_hash=True`

Hashing is one of the major verification decisions in artifact registration.

When `compute_hash=True`:

- `Scribe` attempts to calculate a file hash,
- a successful hash becomes part of the manifest,
- and the artifact becomes much easier to compare and verify later.

This is useful because a file path alone is not strong identity. The same path can point to
different bytes over time, and different paths can sometimes point to the same content.

Hashing helps answer questions like:

- is this really the same checkpoint as before,
- did the output change even if the path did not,
- can this artifact be compared across storage movement.

### When Hashing May Become Degraded

If the file exists but hashing fails due to an `OSError`, `Scribe` does not simply pretend the
artifact was fully bound. Instead it records degradation reasons and warnings.

This is another good example of the artifact flow being richer than a convenience wrapper. Output
integrity is treated as a real part of capture quality.

## `allow_missing=True`

This option is one of the most practically important parts of the artifact API.

Example:

```python
from pathlib import Path

with scribe.run("training") as run:
    result = run.register_artifact(
        "checkpoint",
        Path("./artifacts/model.ckpt"),
        allow_missing=True,
    )
```

If the file does not exist and `allow_missing=False`, registration fails with `ValidationError`.

If the file does not exist and `allow_missing=True`, `Scribe` can still:

- build a request,
- build a manifest,
- emit an artifact binding,
- mark the binding as degraded,
- emit degradation evidence.

This is extremely useful in real workflows where the logical artifact is known before the output is
fully written.

Examples:

- a checkpoint path is determined before the training worker flushes the file,
- a report path is reserved before generation finishes,
- a downstream stage wants to preserve the expected output identity even when the file body is late.

So `allow_missing=True` is not a sloppy shortcut. It is a deliberate choice to preserve partial
truth rather than throw it away.

## What Degraded Artifact Binding Means

Artifact capture is one of the places where `degraded` status makes the most intuitive sense.

Suppose the caller knows:

- what the artifact kind is,
- what path should hold it,
- what execution context it belongs to.

But the file does not exist yet.

That is not the same thing as "nothing is known." A meaningful part of the truth is still available.
`Scribe` preserves that by recording:

- artifact request intent,
- the path that was targeted,
- the fact that the path did not exist,
- a degraded binding status,
- degradation reasons and warnings.

So degraded artifact capture should be read as:

"the output was known and registered, but binding fidelity was partial."

That is much more informative than either of these extremes:

- pretending the artifact was fully present,
- discarding the artifact capture completely.

## Artifact Capture And Degradation Evidence

When artifact registration becomes degraded, `Scribe` may also emit a degradation-family payload.

That matters because the reduced-fidelity condition is not left only in the returned
`CaptureResult`. It can become part of the persisted observability truth as well.

In practical local-first terms, that often means:

- the artifact binding appears in `artifacts.jsonl`,
- and degradation evidence appears in `degradations.jsonl`.

This is very useful when debugging real workflows. You can inspect not only that an artifact was
registered, but also exactly why it was not a clean binding.

## Scope And Artifact Meaning

Like other `Scribe` capture patterns, artifact registration also changes meaning depending on scope.

### Run-level artifact

Use when the artifact represents a whole-run output or run-level result.

Examples:

- final summary report
- run-level packaged export

### Stage-level artifact

Use when the artifact belongs clearly to a major phase.

Examples:

- training checkpoint
- evaluation report
- prepared dataset snapshot

### Operation-level artifact

Use when the artifact belongs to a finer work unit and you need that distinction later.

Examples:

- request-level debug bundle
- one-step intermediate output

In practice, stage-level artifact capture is the most common operational pattern, because many ML
workflows naturally think of artifacts as outputs of phases such as train or evaluate.

## Artifact Capture Compared To Event Capture

This distinction matters a lot.

An event like:

```python
run.event(
    "checkpoint.saved",
    message="checkpoint saved to ./artifacts/model.ckpt",
)
```

can be useful, but it is not a replacement for artifact registration.

The event tells you an occurrence happened.
The artifact binding tells you:

- what the artifact is,
- what source it points to,
- what verification policy was applied,
- what the binding status was,
- what canonical manifest was constructed,
- what run or stage it belongs to.

So an event and an artifact often work well together, but they do different jobs.

The event answers:

"Did something happen?"

The artifact answers:

"What output object was bound, and how completely?"

## A Realistic Artifact Flow

The example workflow in
[`artifact_binding_workflow.py`](../../examples/artifact_binding_workflow.py)
shows a good realistic pattern.

The run:

- carries reproducibility metadata,
- registers an artifact with `allow_missing=True`,
- then emits an event describing the artifact binding result.

That is a very healthy pattern in practice:

1. register the output structurally,
2. inspect the result,
3. optionally emit a human-readable event about what happened.

This keeps the artifact itself structured, while still making the operational outcome easy to read
in event streams.

## Artifact Capture And Reproducibility Context

One of the important strengths of artifact registration in `Scribe` is that active run context flows
into the artifact manifest.

That means values such as:

- `code_revision`
- `config_snapshot`
- `dataset_ref`

can become part of the output's attached reproducibility extensions.

This matters because outputs are often the thing teams need to explain later:

- which code revision produced this report,
- which dataset was active when this checkpoint was registered,
- which configuration snapshot belongs to this output.

Artifact capture is one of the most natural places to preserve that execution-to-output connection.

## When Artifact Capture Is The Right Fit

Artifact capture is the right fit when:

- the thing being captured is a durable output or expected output,
- execution context should remain attached to that output,
- file integrity or source existence matters,
- degraded output binding is still worth preserving,
- later consumers may need to compare, inspect, or route the output as its own entity.

Good examples:

- checkpoints
- model packages
- evaluation reports
- feature snapshots
- exported datasets
- generated manifests

## When Artifact Capture Is Not The Right Fit

Artifact capture is usually not the right fit when:

- the fact is only a transient occurrence and not an output object,
- there is no meaningful output identity to preserve,
- the information is really just a warning, note, or numeric observation.

Examples:

- "checkpoint save started" is better as an event,
- "checkpoint write took 2.3s" is better as a metric or span,
- "training loss is 0.42" is better as a metric.

## Common Artifact Mistakes

### 1. Treating Artifact Registration As Just Path Logging

This misses the whole point of binding status, verification policy, and canonical manifest context.

### 2. Failing Hard On Every Missing Output

Sometimes this is correct, but in many real workflows it erases useful partial truth that could
have been preserved as degraded capture.

### 3. Using Event Messages As The Only Artifact Record

That keeps the output human-readable but much harder to interpret structurally later.

### 4. Letting `artifact_kind` Drift Unnecessarily

If kind vocabulary is uncontrolled, consumers end up reconstructing shared meaning manually.

### 5. Ignoring The Returned `CaptureResult`

Artifact capture is richer than a fire-and-forget helper. The result often contains the most
important information about whether the binding was full, degraded, or failed.

## Practical Decision Guide

If you want a quick decision process for artifacts, ask these questions:

### 1. Is this output durable enough to matter after execution finishes

If yes, artifact capture is worth considering.

### 2. Do I need execution context attached to that output

If yes, artifact capture is usually the right fit.

### 3. Is missing-source behavior supposed to fail hard or remain visible as degraded truth

Choose `allow_missing` accordingly.

### 4. Do I care whether the file body is verified or only referenced

Choose `compute_hash` accordingly.

### 5. Will consumers need a stable output category

If yes, define a stable `artifact_kind`.

## The Core Intuition To Keep From This Page

In very short form:

- artifact capture in `Scribe` is a binding flow, not just path logging,
- the registration request and final binding outcome are intentionally distinct,
- degraded artifact capture is often meaningful and worth preserving,
- verification policy is part of the structured artifact contract,
- artifact registration is the right place to connect outputs to execution context.

The single most important sentence to keep is this:

`Scribe` artifacts are modeled as structured claims about outputs and their binding quality, not as
plain file references.

## What To Read Next

If this page made sense, the most useful next pages are usually:

1. [Degradation and Errors](degradation-and-errors.md)
   if you want to understand degraded artifact capture in more operational detail.
2. [Sinks and Storage](sinks-and-storage.md) if you
   want to see where artifact bindings and degradation evidence are persisted.
3. [Examples](examples.md) if you want to see
   artifact registration inside full workflow examples.

## Related Files

- Artifact models: [src/scribe/artifacts/models.py](../../src/scribe/artifacts/models.py)
- Artifact registration service: [src/scribe/artifacts/service.py](../../src/scribe/artifacts/service.py)
- Artifact binding example: [examples/artifact_binding_workflow.py](../../examples/artifact_binding_workflow.py)
- Artifact-related tests: [tests/test_scribe_mvp.py](../../tests/test_scribe_mvp.py)
