# 캡처 패턴

[사용자 가이드 홈](C:/Users/eastl/MLObservability/Scribe/docs/ko/README.md)

사람들이 `Scribe`를 쓰기 시작하면, 가장 먼저 나오는 실전 질문은 대개 "어떤 API가
있지?"가 아니라 "어떤 종류의 runtime fact를 어떤 primitive로 캡처해야 하지?"입니다.
이 페이지는 그 질문에 답하기 위해 존재합니다.

이 페이지의 핵심 목표는 다음과 같습니다:

1. 언제 event, metric, span, artifact를 써야 하는지 설명하기,
2. 같은 capture 호출도 scope level에 따라 의미가 달라짐을 보여주기,
3. 언제 batch capture가 더 잘 맞는지 설명하기,
4. 초기에 흔한 capture-shape 실수를 피하게 돕기.

이 페이지를 읽고 나면 다음 판단을 훨씬 빨리 할 수 있어야 합니다:

- 어떤 것이 event, metric, span, artifact 중 무엇인지,
- 그것이 run, stage, operation 중 어디에 속하는지,
- 하나씩 emit할지 batch API를 쓸지,
- 하나의 워크플로 안에서 여러 capture type을 어떻게 자연스럽게 조합할지.

## 왜 캡처 패턴에 별도 페이지가 필요한가

겉으로 보기에는 `Scribe`가 단순해 보일 수 있습니다:

- `event(...)`
- `metric(...)`
- `span(...)`
- `register_artifact(...)`

하지만 실제 instrumentation 작업에서 문제는 단순히 "이 메서드를 어떻게 부르지"가
아닙니다. 더 어려운 질문은 "이 runtime fact를 나중에 어떤 해석으로 읽고 싶지"입니다.

예를 들어:

- epoch boundary를 기록할 수 있고,
- loss를 기록할 수 있고,
- model forward pass를 기록할 수 있고,
- checkpoint를 기록할 수 있습니다.

이 네 가지는 모두 같은 워크플로에 대한 참인 문장이지만, 같은 종류의 truth는
아닙니다. capture shape를 잘못 고르면 나중의 search, aggregation, troubleshooting이
훨씬 어려워집니다.

그래서 이 페이지는 public method 자체보다 interpretation pattern을 중심으로
구성되어 있습니다.

## 가장 빠른 요령

아주 짧은 가이드는 이렇습니다:

- "무슨 일이 일어났는가"가 가장 중요하면 event를 쓰고,
- "값이 얼마였는가"가 가장 중요하면 metric을 쓰고,
- "얼마나 걸렸는가"나 "어떤 실행 경로를 탔는가"가 가장 중요하면 span을 쓰고,
- "어떤 durable output이 남았는가"가 가장 중요하면 artifact를 씁니다.

이건 첫 번째 지름길일 뿐입니다. 실제 시스템에서는 네 가지를 같은 run 안에서
함께 쓰는 경우가 많습니다.

## 캡처 의미보다 Scope가 먼저다

event, metric, span 중 무엇을 고르기 전에, 그 fact가 어디에 속하는지부터 정하는 것이
도움이 됩니다.

- `run`: 최상위 execution fact
- `stage`: 큰 workflow phase의 fact
- `operation`: 더 세밀한 work-unit fact

같은 capture primitive도 scope에 따라 뜻이 달라질 수 있습니다.

예:

- `run.event(...)`는 보통 run-level milestone을 뜻하고,
- `stage.metric(...)`는 보통 phase-level aggregate를 뜻하며,
- `operation.span(...)`는 보통 세밀한 latency나 execution segment를 뜻합니다.

즉 실제 판단은 대개 두 단계입니다:

1. 이 fact는 어느 scope에 속하는가,
2. 어떤 capture shape가 그것을 가장 잘 표현하는가.

## Event

event는 가장 중요한 질문이 다음일 때 맞습니다:

"무슨 일이 일어났는가?"

전형적인 예:

- run이 시작되었거나 끝났다,
- evaluation stage가 끝났다,
- warning condition이 감지되었다,
- deployment registration step이 실패했다,
- 사람이 읽을 수 있는 중요한 전이가 남아야 한다.

예:

```python
run.event(
    "evaluation.completed",
    message="evaluation finished",
    tags={"phase": "evaluation"},
    attributes={"dataset": "validation"},
)
```

### Event가 맞는 경우

- lifecycle에 인접한 milestone
- warning과 error
- operator가 읽기 좋은 status change
- event key로 검색할 가치가 있는 state transition

좋은 예:

- `run.note`
- `evaluation.completed`
- `dataset.load.failed`
- `checkpoint.registration.started`

### 각 Event 필드에 무엇을 넣을까

#### `key`

event key는 machine-readable classification으로 사용합니다.

좋은 스타일:

- 안정적이고
- 검색 가능하며
- filter하기에 충분히 구체적이어야 합니다

#### `message`

message는 사람이 읽는 설명으로 사용합니다.

#### `attributes`

attributes는 event-local detail에 사용합니다.

예:

```python
attributes={"dataset": "validation", "epoch": 3}
```

#### `tags`

tags는 event 자체에 가벼운 capture metadata를 붙이고 싶을 때 사용합니다.

### Event가 최선이 아닌 경우

다음과 같은 경우 event는 대개 잘 맞지 않습니다:

- 핵심 의미가 나중에 aggregate할 numeric value일 때,
- 주된 질문이 duration이나 parent-child execution flow일 때,
- 그 fact가 실제로는 runtime occurrence가 아니라 output object일 때.

좋지 않은 패턴:

```text
"training loss is 0.42"
```

이 값이 나중에 charting, thresholding, averaging의 대상이라면, 보통 metric이어야 합니다.

## Metric

metric은 가장 중요한 질문이 다음일 때 맞습니다:

"측정된 값이 무엇이었는가?"

예:

```python
stage.metric("eval.accuracy", 0.91, aggregation_scope="dataset")
```

### Metric이 맞는 경우

- loss, accuracy, latency summary, throughput
- evaluation score
- resource usage
- queue depth
- count, ratio, aggregate

좋은 예:

- `training.loss`
- `eval.accuracy`
- `gpu.memory.used`
- `inference.requests_per_second`

### Aggregation Scope가 중요하다

`Scribe`에서 metric은 단순한 숫자가 아닙니다. aggregation scope도 함께 가집니다.

지원되는 aggregation scope:

- `point`
- `step`
- `batch`
- `epoch`
- `dataset`
- `run`
- `operation`

이 scope는 metric에서 가장 중요한 의미 필드 중 하나입니다.

예:

- `step`: 하나의 training step observation
- `epoch`: 하나의 epoch 전체 aggregate
- `dataset`: 하나의 evaluation dataset 전체 aggregate
- `run`: 하나의 run-level summary

즉 metric scope를 고를 때의 실전 질문은 이것입니다:

"이 값은 어떤 단위를 기준으로 해석되어야 하는가?"

### Metric의 Scope 패턴

#### Run-level metric

값이 전체 실행을 요약할 때 사용합니다.

예:

```python
run.metric("training.best_accuracy", 0.94, aggregation_scope="run")
```

#### Stage-level metric

값이 하나의 phase를 요약할 때 사용합니다.

예:

```python
stage.metric("eval.accuracy", 0.91, aggregation_scope="dataset")
```

#### Operation-level metric

값이 step, batch, request에 속할 때 사용합니다.

예:

```python
operation.metric("training.loss", 0.42, aggregation_scope="step")
```

### Metric이 최선이 아닌 경우

다음과 같은 경우 metric은 대개 잘 맞지 않습니다:

- 정보가 실제로는 state transition일 때,
- operator가 이것을 measurement보다 occurrence로 읽게 될 때,
- duration과 nesting structure가 숫자 자체보다 더 중요할 때.

좋지 않은 패턴:

```text
training.epoch.started = 1
```

이것은 의미상 event에 훨씬 가깝습니다.

## Span

span은 가장 중요한 질문이 다음일 때 맞습니다:

"이 작업은 얼마나 걸렸고, 주변 실행과 어떻게 연결되는가?"

예:

```python
operation.span("model.forward", span_kind="model_call")
```

### Span이 맞는 경우

- model call latency
- external API call
- feature lookup segment
- request execution interval
- parent-child flow가 중요한 nested work

좋은 예:

- `model.forward`
- `feature.lookup`
- `predict.request`
- `vector.search`

### Span이 단순한 Metric이 아닌 이유

`inference.latency=152ms` 같은 latency metric도 유용하지만, span은 훨씬 더 많은 것을
보존합니다:

- start time
- end time
- status
- parent linkage
- trace identity
- linked refs

즉 실무적 차이는 이렇습니다:

- metric은 "latency 값이 얼마였는가"를 말하고
- span은 "그 latency를 만든 execution interval이 어떤 trace context 아래 있었는가"를 말합니다

### 고민할 만한 Span 필드

- `span_kind`: 이 span이 어떤 종류의 작업을 나타내는지
- `attributes`: span에 붙는 구조화된 context
- `linked_refs`: artifact나 다른 entity와 연결하는 데 도움 되는 related ref
- `parent_span_id`: 가능한 경우 명시적인 parent-child linkage

### Span이 최선이 아닌 경우

다음과 같은 경우 span은 대개 잘 맞지 않습니다:

- 그 fact가 구간이 아니라 이산적인 milestone일 때,
- 단순한 numeric aggregate면 충분할 때,
- 보존할 만한 meaningful duration이나 execution segment가 없을 때.

좋지 않은 패턴:

- 단순한 phase-completed notification을 span으로 emit하는 것

그 경우는 event로 표현하는 편이 더 낫습니다.

## Artifact

artifact는 가장 중요한 질문이 다음일 때 맞습니다:

"이 실행이 어떤 durable output이나 file-like result를 만들었거나 참조했는가?"

예:

```python
from pathlib import Path

stage.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    compute_hash=True,
)
```

### Artifact가 맞는 경우

- checkpoint
- evaluation report
- exported dataset
- feature snapshot
- generated manifest나 packaged output

### Artifact가 단순한 File Path가 아닌 이유

`Scribe`에서 artifact capture는 binding-aware합니다. registration에는 다음이 포함됩니다:

- artifact kind
- source path
- verification policy
- binding status
- active run이나 stage의 execution context

즉 artifact capture는 단순히 "이 path를 기억하라"가 아닙니다. "이 output을 구조화된
execution result로 기록하라"에 가깝습니다.

### `allow_missing=True`

이 옵션은 실제 워크플로에서 특히 중요합니다.

예:

```python
stage.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    allow_missing=True,
)
```

이 설정을 쓰면, 파일이 아직 없을 때 hard failure 대신 결과가 `degraded`가 될 수
있습니다. file body가 완전히 materialize되기 전에 logical artifact identity는 이미
알려져 있는 워크플로에서 매우 유용합니다.

## Event, Metric, Span, Artifact는 경쟁 관계가 아니다

실제 워크플로에서는 여러 capture type이 함께 필요한 경우가 많습니다.

예를 들어 하나의 training stage 안에서:

- epoch start는 event이고,
- training loss는 metric이며,
- `model.forward`는 span이고,
- checkpoint는 artifact입니다.

즉 이들은 서로 대체재가 아닙니다. 나중에 서로 다른 질문에 답합니다.

더 직접적으로 말하면:

- event는 무슨 일이 일어났는지 말하고,
- metric은 값이 얼마였는지 말하며,
- span은 작업 구간이 어떻게 동작했는지 말하고,
- artifact는 어떤 durable result가 남았는지 말합니다.

## Batch Capture

batch API는 코드가 자연스럽게 여러 item을 함께 만들 때 유용합니다.

예:

- 하나의 stage가 여러 관련 metric을 한 번에 emit할 때,
- 하나의 phase가 여러 completion event를 함께 emit할 때,
- batch result가 이미 메모리에서 그룹으로 묶여 있을 때.

예:

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

### Batch Capture가 더 잘 맞는 경우

- 코드가 이미 measurement나 event의 list를 가지고 있을 때
- 하나의 aggregated `BatchCaptureResult`가 필요할 때
- capture site가 hot path라서 하나씩 orchestration하면 너무 시끄러울 때

### `BatchCaptureResult`가 주는 것

- `status`
- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`

이 덕분에 grouped capture outcome을 item 하나하나 수동으로 보지 않고도 훨씬 쉽게
이해할 수 있습니다.

## Top-Level API와 Scope-Level API

`Scribe`는 top-level capture 패턴과 scope-level capture 패턴을 둘 다 지원합니다.

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

실무에서는 scope-level 사용이 코드에서 active context가 더 분명하기 때문에 대개
이해하기 쉽습니다.

top-level capture도 다음과 같은 경우에는 여전히 유용합니다:

- helper 코드가 현재 active scope를 기준으로 동작해야 할 때,
- 바깥 control flow가 이미 다른 곳에서 scope entrance를 관리하고 있을 때.

## 시나리오별 패턴 조합

### Training pipeline

흔한 형태:

- run-level note event
- stage-level dataset metric
- operation-level loss metric
- operation-level model-forward span
- stage-level checkpoint artifact

### Evaluation pipeline

흔한 형태:

- load된 checkpoint에 대한 artifact registration
- dataset-level evaluation metric
- summary status를 담은 completion event
- report artifact

### Online inference

흔한 형태:

- request-level operation context
- 중요한 state change를 위한 request event
- latency span
- latency나 token-count metric
- 선택적인 report나 drift artifact

즉 같은 API가 어디서나 가능하더라도, 유용한 패턴은 시나리오마다 달라집니다.

## 흔한 캡처 실수

### 1. 모든 것을 event로 보내기

이렇게 하면 나중의 숫자 분석이 어려워집니다.

좋지 않은 예:

```text
"training loss is 0.42"
```

### 2. 모든 것을 metric으로 보내기

이렇게 하면 state transition의 의미가 약해집니다.

좋지 않은 예:

```text
evaluation.completed = 1
```

### 3. span을 start와 end event만으로 대체하기

이렇게 하면 interval structure를 잃고, 나중의 trace-style 분석이 약해집니다.

### 4. capture flow 밖에서 output을 plain path로만 등록하기

이렇게 하면 `Scribe`가 보존하려는 execution context와 binding semantics를 놓치게 됩니다.

### 5. 잘못된 scope에 캡처하기

예를 들면:

- request-level fact를 run level에 기록하거나,
- dataset aggregate를 operation level에 기록하거나,
- whole-run summary를 step operation 안에 기록하는 경우.

payload 자체는 유효해도 나중 해석이 시끄러워집니다.

## 실전 의사결정 가이드

빠른 결정 프로세스가 필요하다면, 다음 질문을 순서대로 해보면 됩니다:

### 1. 이 fact는 주로 runtime occurrence인가, numeric value인가, interval인가, output인가

- occurrence -> event
- value -> metric
- interval -> span
- output -> artifact

### 2. 이 fact를 소유하는 scope는 어디인가

- 전체 실행 -> run
- 하나의 큰 phase -> stage
- 하나의 step, batch, request -> operation

### 3. 이건 자연스럽게 item 하나인가, item들의 묶음인가

- item 하나 -> single capture call
- grouped item -> batch API

### 4. 나중에 reduced-fidelity behavior를 직접 확인해야 하는가

그렇다면 `CaptureResult`를 주의 깊게 보고, degraded capture를 보이지 않는 것으로
취급하지 마세요.

## 이 페이지에서 가져가야 할 핵심 직관

아주 짧게 정리하면:

- 지금 emit하기 쉬운 형태가 아니라, 나중에 어떻게 읽고 싶은지에 따라 capture shape를 고르고,
- 그 fact가 운영적으로 속하는 위치에 따라 scope를 고르고,
- 코드가 이미 grouped value를 만든다면 batch API를 쓰고,
- 같은 워크플로의 다른 질문에 답하려면 여러 capture type을 함께 사용하면 됩니다.

한 문장으로 줄이면:

"runtime fact를 나중에 읽고 싶은 방식에 맞춰 모델링하고, 그 fact가 자연스럽게 속하는
scope에 배치하라."

## 다음에 읽을 문서

이 페이지가 이해됐다면, 다음 문서들이 보통 가장 유용합니다:

1. [아티팩트](C:/Users/eastl/MLObservability/Scribe/docs/ko/artifacts.md):
   artifact registration과 degraded binding을 더 깊게 보고 싶을 때
2. [싱크와 저장소](C:/Users/eastl/MLObservability/Scribe/docs/ko/sinks-and-storage.md):
   캡처된 payload가 어디로 가는지 알고 싶을 때
3. [Degradation과 오류](C:/Users/eastl/MLObservability/Scribe/docs/ko/degradation-and-errors.md):
   capture가 부분적이거나 sink가 실패했을 때의 운영 해석을 알고 싶을 때
4. [예제](C:/Users/eastl/MLObservability/Scribe/docs/ko/examples.md):
   고립된 패턴보다 전체 워크플로 예제를 보고 싶을 때

## 관련 파일

- Scope APIs: [src/scribe/runtime/scopes.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/scopes.py)
- Trace capture service: [src/scribe/traces/service.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/traces/service.py)
- Artifact registration service: [src/scribe/artifacts/service.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/artifacts/service.py)
- Evaluation example: [examples/evaluation_workflow.py](C:/Users/eastl/MLObservability/Scribe/examples/evaluation_workflow.py)
