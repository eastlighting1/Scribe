# Scribe User Guide (EN)

Scribe documentation is organized so that a new user can answer "how do I add this library to a
real Python ML workflow" before diving into every API surface in detail. If this is your first
time here, the fastest path is to read the pages below in order.

- [Getting Started](en/getting-started.md)
- [Core Concepts](en/core-concepts.md)
- [Capture Patterns](en/capture-patterns.md)
- [Sinks and Storage](en/sinks-and-storage.md)
- [Artifacts](en/artifacts.md)
- [Degradation and Errors](en/degradation-and-errors.md)
- [API Reference](en/api-reference.md)
- [Examples](en/examples.md)

Recommended reading order:

1. If you want to import `Scribe` right away and record your first event or metric, start with
   [Getting Started](en/getting-started.md).
2. If you want to understand the mental model of `run -> stage -> operation` and the four payload
   families, read [Core Concepts](en/core-concepts.md).
3. If you want practical guidance on when to emit events, metrics, spans, and artifacts, read
   [Capture Patterns](en/capture-patterns.md) and
   [Artifacts](en/artifacts.md).
4. If you want to understand local inspection, sink behavior, and degraded capture, read
   [Sinks and Storage](en/sinks-and-storage.md) and
   [Degradation and Errors](en/degradation-and-errors.md).
5. If you want to look up methods and result models quickly, use
   [API Reference](en/api-reference.md).

If you are new to `Scribe`, it is usually much more efficient to read `Getting Started`,
`Core Concepts`, and `Degradation and Errors` first, then jump into type-specific or operational
pages only when you need them.

## What This Documentation Optimizes For

`Scribe` is not primarily a schema-definition library. It is a capture-side SDK that sits inside
running Python workflows. That means the most important documentation questions are usually:

- where should I open a `run`
- when should I create `stage` and `operation` scopes
- when is something an event, a metric, a span, or an artifact
- how should I interpret `CaptureResult` and degraded capture
- how do sinks affect what is persisted locally or forwarded downstream

Because of that, the `Scribe` docs are written around capture flow and operational interpretation,
not only around type definitions.

## What Scribe Does

At a high level, `Scribe` helps code do five things:

- create explicit lifecycle scopes for ML execution
- turn runtime facts into canonical observability payloads
- attach execution context automatically
- dispatch payloads to capability-based sinks
- preserve degraded capture as structured evidence instead of hiding it

The normal usage pattern looks like this:

```text
create Scribe session
  -> enter run
    -> optionally enter stage and operation scopes
      -> emit event / metric / span / artifact
        -> inspect CaptureResult
          -> let sinks persist or forward payloads
```

This guide is designed to make that flow feel natural before you need to memorize every method.

## How The Pages Are Split

The pages are divided by user task rather than by internal module layout.

- `Getting Started`: first success path
- `Core Concepts`: mental model and scope structure
- `Capture Patterns`: which capture primitive fits which kind of runtime fact
- `Sinks and Storage`: where payloads go and how to inspect them
- `Artifacts`: binding-oriented output capture
- `Degradation and Errors`: how to read reduced-fidelity capture and operational failures
- `API Reference`: quick lookup for public methods and result models
- `Examples`: full workflow references

This is intentional. In `Scribe`, most confusion comes not from "what fields exist" but from
"where in the workflow should I capture this, and how will it behave operationally later."

## What To Read If You Are In A Hurry

If you only have a few minutes, read these three pages first:

1. [Getting Started](en/getting-started.md)
2. [Core Concepts](en/core-concepts.md)
3. [Degradation and Errors](en/degradation-and-errors.md)

Those three pages are enough to understand:

- the basic runtime shape of `Scribe`
- where records belong
- what success, degraded, and failure states mean

## Relationship To Spine

`Scribe` is closely aligned with `Spine`, but the two libraries serve different purposes.

- `Spine` defines and validates the canonical contract
- `Scribe` captures runtime truth and dispatches it through sinks

So if you need deep model semantics, schema reasoning, or compatibility details, the relevant place
to go is `Spine`. If you need to know how to instrument real Python code and understand what will
happen when capture succeeds or degrades, the relevant place is `Scribe`.

## Related Files

- Korean user guide entry: [docs/USER_GUIDE.ko.md](USER_GUIDE.ko.md)
- Package entrypoint: [src/scribe/__init__.py](../src/scribe/__init__.py)
- Public session API: [src/scribe/api/session.py](../src/scribe/api/session.py)
- Training example: [examples/training_workflow.py](../examples/training_workflow.py)
- Evaluation example: [examples/evaluation_workflow.py](../examples/evaluation_workflow.py)
- Artifact binding example: [examples/artifact_binding_workflow.py](../examples/artifact_binding_workflow.py)
