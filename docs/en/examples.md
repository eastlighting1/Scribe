# Examples

[User Guide Home](../USER_GUIDE.en.md)

One of the fastest ways to understand `Scribe` is to see how a few small workflows assemble scope,
capture primitives, artifact registration, and local storage together. This page explains the
example files included in the repository and, more importantly, how to read them.

The goal of this page is not only to list files. It is to help you answer questions like:

- which example should I read first,
- what should I pay attention to in each one,
- how do these examples map to the rest of the documentation,
- what kind of real workflow is each example trying to represent.

If you already read `Getting Started`, this page is the bridge between the small introductory
snippets and a more realistic feel for how `Scribe` is assembled in code.

## Why The Examples Matter

Most of the documentation explains `Scribe` in conceptual or focused slices:

- how scopes work,
- when to use an event or metric,
- how sinks behave,
- how artifacts degrade.

Examples are where those ideas appear together in one flow.

That matters because in real usage:

- you do not capture only a metric,
- you do not register only an artifact,
- you do not enter only one isolated scope.

Real code usually does several of these things in one execution. The examples exist to show what
that combined flow feels like without forcing you into a large codebase first.

## Included Workflows

The repository currently includes these example files:

- [Training workflow](../../examples/training_workflow.py)
- [Evaluation workflow](../../examples/evaluation_workflow.py)
- [Artifact binding workflow](../../examples/artifact_binding_workflow.py)

These examples are intentionally small. Their job is not to simulate a full production system. Their
job is to make the core instrumentation patterns easy to see.

## Recommended Reading Order

The most useful reading order is:

1. [Training workflow](../../examples/training_workflow.py)
2. [Evaluation workflow](../../examples/evaluation_workflow.py)
3. [Artifact binding workflow](../../examples/artifact_binding_workflow.py)

That order is not arbitrary.

It starts with the broadest and most representative end-to-end flow, then moves into a more
specific evaluation shape, and finally isolates one of `Scribe`'s most distinctive ideas: artifact
binding under imperfect conditions.

## Example 1: Training Workflow

File:

- [examples/training_workflow.py](../../examples/training_workflow.py)

This is the best first example because it shows the most complete cross-section of normal `Scribe`
usage in one place.

### What It Demonstrates

This example shows:

- creating a `Scribe` session with `LocalJsonlSink`
- opening a run
- entering multiple stage scopes
- using operation scopes for fine-grained work
- emitting metrics at dataset and step level
- emitting events in batch
- emitting spans inside operations
- registering an artifact

In other words, it shows the normal "context -> observation -> output" flow that most users will
eventually need.

### Why This Example Comes First

This file is the best first example because it lets you see how several capture types coexist
without forcing you into too many edge cases.

It gives you:

- one run-level note event,
- one preparation stage with dataset-scale metrics,
- one training stage with step-level metrics and spans,
- one artifact registration,
- one local sink for durable inspection.

That means it mirrors the most common first production question:

"How do I add `Scribe` to a training-like workflow without introducing a complicated backend?"

### What To Notice While Reading

There are several important patterns to notice.

#### 1. The sink is configured only once

The session is created once at the top, and every later capture action reuses that configuration.

This is how `Scribe` is intended to feel in application code: create one session, then let the
active scopes carry the runtime context.

#### 2. Different stages use different capture styles

The `prepare-data` stage emits batch metrics at dataset scale.
The `train` stage emits:

- per-step metrics inside operations,
- spans for model-forward work,
- batched epoch events,
- and an output artifact.

This demonstrates an important `Scribe` idea: the right capture shape depends on the runtime fact,
not on a fixed habit of always using one primitive.

#### 3. Operation scopes are used only where they add meaning

The example does not wrap every line in an `operation`.

That is a healthy pattern.

Operation scopes are most useful when the work unit itself matters later, such as:

- a training step,
- a batch,
- a request,
- a tool call.

The training example uses that level only where it really helps.

#### 4. Artifact registration is part of the same workflow, not an afterthought

The checkpoint registration is captured in the same flow as metrics and events. That reflects one of
`Scribe`'s strongest design choices: outputs belong in the same observability truth model as runtime
facts.

### How To Interpret This Example After Running It

If you run it with `LocalJsonlSink`, the local `.scribe` directory should show:

- context payloads such as `Project`, `Run`, and `StageExecution`
- record payloads such as lifecycle events, training events, metrics, and spans
- an artifact payload for the checkpoint
- possibly degradation evidence because the example uses `allow_missing=True`

That last point matters. The example is not only a happy-path illustration. It also shows how
artifact capture can stay useful even when output materialization is partial.

### Which Documentation This Example Reinforces

The training example connects most strongly to:

- [Getting Started](getting-started.md)
- [Core Concepts](core-concepts.md)
- [Capture Patterns](capture-patterns.md)
- [Artifacts](artifacts.md)

## Example 2: Evaluation Workflow

File:

- [examples/evaluation_workflow.py](../../examples/evaluation_workflow.py)

This example is narrower than the training workflow, and that is exactly why it is useful.

It shows what `Scribe` looks like when the workflow is organized around:

- loading an existing artifact,
- evaluating against a dataset,
- recording aggregate metrics,
- and emitting an evaluation result artifact.

### What It Demonstrates

This example shows:

- stage-level artifact registration before evaluation
- batch metric capture for evaluation metrics
- event emission based on `BatchCaptureResult`
- output artifact registration for the evaluation report

So instead of emphasizing dense operation-level training flow, it emphasizes stage-shaped pipeline
work.

### Why This Example Matters

Many teams have clearer evaluation or reporting flows than they do dense request-level tracing.

This example demonstrates that `Scribe` does not require step-heavy training semantics to be useful.
It also works naturally for workflows where:

- the important measurements are dataset aggregates,
- the key outputs are reports,
- and the operational structure is phase-oriented rather than request-oriented.

### What To Notice While Reading

#### 1. Artifact registration can happen before the main evaluation stage

The `load-checkpoint` stage registers the checkpoint artifact before the evaluation metrics are
captured.

That reinforces an important idea:

artifact capture in `Scribe` is not only about newly created outputs. It can also describe relevant
output objects that the current workflow consumes or binds against.

#### 2. Batch metrics are the natural fit here

Evaluation metrics are emitted together as one grouped action:

- accuracy
- loss

This is a good example of when `emit_metrics(...)` is better than many isolated calls. The workflow
already thinks of the evaluation result as one grouped observation set.

#### 3. The event explains the batch result in human-readable form

After metric emission, the example emits:

- an event with the batch status embedded in the message.

That is a very healthy pattern. It uses:

- metrics for the values,
- events for the human-readable interpretation of the phase outcome.

### How This Example Differs From The Training Example

Compared to the training example, this one:

- uses fewer operation-level scopes,
- emphasizes dataset-level metrics over step-level metrics,
- treats artifact handling as part of phase transitions,
- and shows how a stage can summarize grouped metric capture.

That makes it especially useful for teams instrumenting:

- batch evaluation pipelines,
- report-generation workflows,
- offline validation or scoring jobs.

### Which Documentation This Example Reinforces

This example connects most strongly to:

- [Capture Patterns](capture-patterns.md)
- [Artifacts](artifacts.md)
- [Degradation and Errors](degradation-and-errors.md)

## Example 3: Artifact Binding Workflow

File:

- [examples/artifact_binding_workflow.py](../../examples/artifact_binding_workflow.py)

This is the most specialized example in the set, and it exists for a good reason. Artifact binding
is one of the most distinctive parts of `Scribe`, and it benefits from being shown in isolation.

### What It Demonstrates

This example shows:

- run-level reproducibility metadata
- artifact registration with `compute_hash=True`
- artifact registration with `allow_missing=True`
- event capture that reports the binding result explicitly

This file is small, but conceptually dense.

### Why This Example Matters

A lot of observability SDKs can emit an event or metric. Fewer libraries make artifact registration
and degraded binding a first-class part of runtime capture.

This example isolates that behavior so the reader can focus on questions like:

- what happens when the file is missing,
- what information still survives,
- how should the capture result be interpreted,
- how can artifact binding be paired with a human-readable event.

### What To Notice While Reading

#### 1. Reproducibility context is set at run creation

The example supplies:

- `code_revision`
- `config_snapshot`
- `dataset_ref`

This is important because artifact capture is one of the most natural places where those run-level
reproducibility fields become valuable later.

The artifact is not just "some report." It becomes an output connected to a particular code
revision, configuration snapshot, and dataset reference.

#### 2. The artifact call is intentionally allowed to degrade

The file may not exist yet, but the example still registers the artifact.

This is not sloppy instrumentation. It is an intentional demonstration of one of `Scribe`'s core
ideas:

partial truth should often be preserved rather than discarded.

#### 3. The event is used as interpretation, not replacement

After artifact registration, the example emits an event summarizing:

- the artifact family,
- whether the result degraded.

This is a very strong pattern because it keeps:

- the structured artifact binding,
- and a human-readable operational note,

as separate but complementary records.

### Which Documentation This Example Reinforces

This example connects most strongly to:

- [Artifacts](artifacts.md)
- [Degradation and Errors](degradation-and-errors.md)
- [Sinks and Storage](sinks-and-storage.md)

## How To Use The Examples Well

There are at least three different ways to use these example files.

### 1. Read Them Before Running Them

This is useful when you want to understand assembly order and capture shape first.

While reading, ask:

- where does the run begin,
- where do stages begin and end,
- which capture primitives are chosen and why,
- which calls return grouped results,
- which outputs are expected to degrade.

### 2. Run Them With Local JSONL Storage

This is useful when you want to connect code to actual emitted payloads.

After running, inspect:

- `contexts.jsonl`
- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

This makes the examples much more informative because you can see not only the instrumentation code,
but also the stored truth that resulted from it.

### 3. Use Them As Scaffolding

This is often the most practical approach.

Instead of copying them line by line, use them as templates for:

- training instrumentation,
- evaluation jobs,
- output registration flows.

That is usually better than starting from a blank file because the examples already reflect healthy
`Scribe` patterns.

## What The Examples Intentionally Do Not Cover

These examples are deliberately small, so they do not try to show every advanced path.

They do not try to cover all of the following at once:

- custom sink implementations
- complex multi-sink topologies
- highly concurrent instrumentation
- large-scale lineage or external backend integration

That omission is intentional. The examples are designed to teach the core assembly pattern first:

- create context,
- capture runtime facts,
- register outputs,
- inspect results.

Once that is clear, more advanced integrations become much easier to build on top of it.

## What To Compare Across The Three Examples

If you want to get the most learning out of the set, compare them along these axes.

### Scope depth

- training: run -> stage -> operation
- evaluation: run -> stage
- artifact binding: mostly run-level

### Dominant capture type

- training: mixed metrics, spans, events, and artifacts
- evaluation: aggregate metrics plus artifacts
- artifact binding: artifact-centric with one explanatory event

### Typical degradation path

- training: artifact may degrade if the checkpoint does not exist yet
- evaluation: checkpoint or report artifact may degrade
- artifact binding: degradation is the main instructional focus

This comparison is useful because it helps you see that `Scribe` is not tied to one single workflow
shape. The same core SDK can support several different capture patterns depending on what the system
needs to express.

## A Good Progression For New Users

If you are introducing `Scribe` into a real project, the healthiest progression usually looks like
this:

1. Read and run the training example to understand the full shape.
2. Read and run the evaluation example to see a stage-oriented aggregate flow.
3. Read and run the artifact binding example to understand degraded output capture.
4. Then go back to your own code and imitate only the parts that match your workflow.

This is a better approach than trying to import every pattern at once.

## The Core Intuition To Keep From This Page

In very short form:

- the examples are intentionally small but structurally representative,
- each example teaches a different emphasis rather than duplicating the others,
- the best way to use them is to connect code shape, capture result, and local sink output together,
- they are templates for instrumentation patterns, not scripts you must copy exactly.

The most important sentence to keep is this:

The example set is designed to teach how `Scribe` assembles capture flow in real code, not just how
individual methods look in isolation.

## What To Read Next

If this page made sense, the most useful next pages are usually:

1. [API Reference](api-reference.md) if you want a
   compact lookup while reading or adapting the examples.
2. [Artifacts](artifacts.md) if the artifact-centric
   example raised new questions.
3. [Sinks and Storage](sinks-and-storage.md) if you
   want to inspect the example output more deeply.

## Related Files

- Training example: [examples/training_workflow.py](../../examples/training_workflow.py)
- Evaluation example: [examples/evaluation_workflow.py](../../examples/evaluation_workflow.py)
- Artifact binding example: [examples/artifact_binding_workflow.py](../../examples/artifact_binding_workflow.py)
