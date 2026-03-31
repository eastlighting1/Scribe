# 핵심 개념

[사용자 가이드 홈](../USER_GUIDE.ko.md)

사람들이 처음 `Scribe`를 보면, 보통 첫 질문은 "어떤 필드가 있지?"가 아니라 "내
워크플로의 어디에 이 라이브러리를 넣어야 하고, 정확히 무엇을 캡처해 주는 거지?"
입니다. 이 페이지는 그 질문에 답하는 개념 가이드입니다.

이 문서의 목표는 다음과 같습니다:

1. `Scribe`의 런타임 형태를 설명하기,
2. 왜 `run`, `stage`, `operation`이 별개의 scope인지 보여주기,
3. `Scribe`가 dispatch하는 네 가지 payload family를 설명하기,
4. capture result를 운영 관점에서 어떻게 해석해야 하는지 명확히 하기,
5. `Scribe`가 끝나는 지점과 `Spine`이 시작되는 지점을 보여주기.

이 페이지를 읽고 나면, `Scribe`를 막연한 logging helper처럼 다루지 않고 실제
Python 워크플로 안에 배치할 수 있어야 합니다.

## Scribe를 이해할 때의 핵심 질문

`Scribe`에서 가장 중요한 질문은 "무엇을 emit했는가"만이 아니라 "어떤 runtime
context 안에서 emit했는가, 그리고 라이브러리가 어떤 truth를 자동으로 보존했는가"
입니다.

그래서 `Scribe`는 다음을 중심으로 구성됩니다:

- 명시적인 lifecycle scope,
- canonical payload family,
- 구조화된 capture outcome,
- sink dispatch,
- reproducibility를 고려한 context.

이 다섯 가지를 머리에 두면, 나머지 API도 훨씬 읽기 쉬워집니다.

## Scribe가 실제로 하는 일

높은 수준에서 보면 `Scribe`는 이 스택의 capture-side SDK입니다.

`Scribe`는 코드가 다음을 할 수 있게 도와줍니다:

- 실행 중인 워크플로를 위한 lifecycle boundary를 만들고,
- runtime fact를 canonical object로 바꾸고,
- execution context를 자동으로 붙이고,
- 그 object를 하나 이상의 sink로 dispatch하고,
- degraded capture를 숨기지 않고 증거로 남깁니다.

전형적인 흐름은 이렇게 생겼습니다:

```text
create Scribe session
  -> enter run
    -> optionally enter stage
      -> optionally enter operation
        -> emit event / metric / span / artifact
          -> receive CaptureResult
            -> let sinks persist or forward payloads
```

즉 `Scribe`는 느슨한 logging utility보다는 "runtime capture orchestration"에 훨씬
가깝습니다.

## 왜 Lifecycle Scope가 존재하는가

모든 observability 호출이 명시적인 scope 없이 emit된다면 데이터는 여전히 생기겠지만,
다음 질문에 답하기가 훨씬 어려워집니다:

- 이 metric은 어느 run에 속하는가,
- 이 event는 training에서 일어났는가 evaluation에서 일어났는가,
- 어떤 step이나 request가 이 span을 만들었는가,
- 어떤 artifact가 어떤 execution context에 속하는가.

그래서 `Scribe`는 capture context를 명시적으로 모델링합니다.

## Lifecycle Scope

`Scribe`는 세 개의 중첩 scope를 사용합니다:

- `run`: 하나의 논리적 실행
- `stage`: run 내부의 큰 phase
- `operation`: active context 안의 더 작은 work unit

전형적인 중첩은 다음과 같습니다:

```python
with scribe.run("baseline-train") as run:
    with run.stage("prepare-data") as stage:
        stage.metric("data.rows", 128_000, aggregation_scope="dataset")

    with run.stage("train") as stage:
        with stage.operation("step-1") as operation:
            operation.metric("training.loss", 0.42, aggregation_scope="step")
            operation.span("model.forward", span_kind="model_call")
```

### `run`을 어떻게 이해할까

`run`은 최상위 execution unit입니다.

예:

- 하나의 training job
- 하나의 evaluation pass
- 하나의 batch processing 실행
- 더 오래 지속되는 serving session 하나

"이건 어느 실행에 속하지?"라는 질문에 하나의 답을 줘야 한다면, 보통 그 답은 run입니다.

### `stage`를 어떻게 이해할까

`stage`는 run 내부의 큰 phase입니다.

예:

- `prepare-data`
- `train`
- `evaluate`
- `register`

항상 stage가 필요한 것은 아니지만, 워크플로 안에 의미 있는 내부 phase가 생기면
stage-level capture가 이후 디버깅과 분석을 훨씬 쉽게 만들어 줍니다.

### `operation`을 어떻게 이해할까

`operation`은 더 세밀한 work unit입니다.

예:

- 하나의 training step
- 하나의 batch
- 하나의 request
- 하나의 model call

metric이나 trace가 충분히 촘촘해져서 run-level이나 stage-level context가 너무 거칠게
느껴질 때 이 레벨이 중요해집니다.

## 왜 Scope 레벨이 분리되어 있는가

이 분리는 실제 시스템에서 늘 같은 이유로 필요합니다:

- 너무 거칠게 모델링하면 운영 세부사항을 잃고
- 너무 세밀하게 모델링하면 큰 실행 그림을 잃고
- 대부분의 observability 분석은 둘 다 필요합니다

그 의미에서 `Scribe`의 scope는 runtime meaning을 나누는 방식입니다:

- `run`: execution scope
- `stage`: phase scope
- `operation`: fine-grained work-unit scope

## Scope에 들어가면 자동으로 일어나는 일

이것은 라이브러리 전체에서 가장 중요한 개념 중 하나입니다.

`Scribe`는 사용자가 직접 emit한 것만 캡처하지 않습니다. lifecycle truth도
자동으로 캡처합니다.

scope에 진입하고 종료하면 `Scribe`는 다음을 emit합니다:

- `Project`
- `Run`
- `StageExecution`
- `OperationContext`
- `run.started`, `stage.completed`, `operation.failed` 같은 lifecycle record
- 활성화된 경우 run 시작 시 `EnvironmentSnapshot`

즉 `run`은 단순한 context manager 편의 기능이 아닙니다. 구조화된 lifecycle capture를
트리거하는 장치입니다.

## Payload Family

모든 capture action은 다음 네 가지 payload family 중 하나를 dispatch합니다:

- `context`
- `record`
- `artifact`
- `degradation`

이 family는 sink support가 이 레벨에서 정의되기 때문에 중요합니다.

## 각 Payload Family의 의미

### `context`

context payload는 실행 배경을 설명합니다.

예:

- `Project`
- `Run`
- `StageExecution`
- `OperationContext`
- `EnvironmentSnapshot`

이 family는 "어디에서 일어났는가"에 답합니다.

### `record`

record payload는 관측된 runtime fact를 설명합니다.

예:

- 구조화된 event
- metric
- span
- lifecycle event record

이 family는 "무슨 일이 일어났는가"에 답합니다.

### `artifact`

artifact payload는 durable output이나 output binding을 설명합니다.

예:

- checkpoint
- evaluation report
- exported file

이 family는 "어떤 execution output이 생성되거나 등록되었는가"에 답합니다.

### `degradation`

degradation payload는 fidelity가 떨어진 capture를 명시적인 증거로 보존합니다.

예:

- 한 sink는 실패했지만 다른 sink는 payload를 받아들였다
- 파일이 존재하기 전에 artifact가 등록되었다
- 어떤 capture family를 지원하는 sink가 없었다

이 family는 "capture 중 어떤 품질 저하가 일어났는가"에 답합니다.

## 왜 Payload Family가 분리되어 있는가

이 경계가 없으면 sink 동작을 이해하기가 훨씬 어려워집니다.

예를 들면 어떤 sink는:

- record와 artifact는 지원하고,
- context는 건너뛰고,
- degradation payload는 완전히 무시할 수 있습니다.

family를 명시적으로 나눠두면 `Scribe`는 다음을 표현할 수 있습니다:

- 어떤 종류의 truth가 만들어졌는지,
- 어떤 sink가 그것을 받을 자격이 있었는지,
- 지원 부족 때문에 degraded capture가 생겼는지.

이것이 `Scribe`가 vendor-agnostic함을 유지하면서도 운영적으로 유용한 이유 중
하나입니다.

## Public API 형태

top-level `Scribe` object는 public capture entrypoint를 노출합니다:

- `Scribe.run(...)`
- `Scribe.event(...)`
- `Scribe.metric(...)`
- `Scribe.span(...)`
- `Scribe.register_artifact(...)`
- `Scribe.emit_events(...)`
- `Scribe.emit_metrics(...)`

scope object도 active context 안에서 같은 capture primitive를 노출합니다:

- `RunScope.stage(...)`
- `StageScope.operation(...)`
- `scope.event(...)`
- `scope.metric(...)`
- `scope.span(...)`
- `scope.register_artifact(...)`
- `scope.emit_events(...)`
- `scope.emit_metrics(...)`

즉 API는 아주 단순하게 이렇게 생각하면 됩니다:

- top-level 호출은 현재 active scope를 사용하고
- scope-level 호출은 그 context를 코드에 명시합니다

## Capture Outcome

단일 item capture는 `CaptureResult`를 반환합니다.
batch capture는 `BatchCaptureResult`를 반환합니다.

가장 중요한 status 값은 다음과 같습니다:

- `success`
- `degraded`
- `failure`

그리고 per-delivery status model에는 `skipped`도 포함됩니다.

## `CaptureResult`를 읽는 법

`CaptureResult`는 단순한 success flag가 아닙니다. capture 중 무엇이 일어났는지
설명하는 구조화된 결과입니다.

중요한 필드:

- `family`
- `status`
- `deliveries`
- `warnings`
- `degradation_reasons`
- `payload`
- `degradation_emitted`

편의 property도 중요합니다:

- `succeeded`
- `degraded`

가장 중요한 운영 아이디어는 이것입니다:

- `success`는 eligible sink가 payload를 완전히 받아들였다는 뜻이고
- `degraded`는 일부 truth는 보존됐지만 fidelity가 떨어졌다는 뜻이며
- `failure`는 모든 eligible sink가 실패했다는 뜻입니다

즉 degraded capture는 전체 실패와 같지 않습니다.

## `BatchCaptureResult`를 읽는 법

batch capture는 여러 개별 capture의 outcome을 요약합니다.

중요한 필드와 property:

- `status`
- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`
- `results`

이 때문에 batch capture는 hot path에서도 구조화된 운영 피드백이 필요할 때 유용합니다.

## Reproducibility Context

run scope는 다음 reproducibility field를 가질 수 있습니다:

- `code_revision`
- `config_snapshot`
- `dataset_ref`

이 값들은 downstream consumer를 위해 canonical payload extension에 붙습니다.

실무에서는 이 층이 runtime observability와 reproducibility, audit 질문을 연결해 줍니다.

예를 들면:

```python
with scribe.run(
    "training",
    code_revision="abc123def",
    config_snapshot={"lr": 0.001, "batch_size": 32},
    dataset_ref="imagenet-v1",
) as run:
    run.metric("training.loss", 0.42, aggregation_scope="step")
```

`Scribe`는 다음도 보존할 수 있습니다:

- run-level `tags`
- run-level `metadata`
- stage-level `metadata`
- operation-level `metadata`
- event-level `tags`

즉 reproducibility와 capture metadata는 나중에 덧붙인 요소가 아니라 active runtime
context의 일부입니다.

## `current_run`, `current_stage`, `current_operation`의 의미

`Scribe`는 다음 메서드를 제공합니다:

- `current_run()`
- `current_stage()`
- `current_operation()`

이 메서드들은 존재할 경우 현재 task-local active scope를 반환합니다.

이 메서드는 helper 코드가 scope object를 인자로 직접 받지 않고도 capture를 emit해야
할 때 유용합니다. 하지만 중요한 점은, 이 메서드가 의미를 가지는 것은 active
lifecycle context 안에서뿐이라는 점입니다. 그 밖에서는 `ContextError`가 정상적인
결과입니다.

## Scribe가 끝나고 Spine이 시작되는 지점

이 경계는 중요합니다.

`Scribe`와 `Spine`은 정렬되어 있지만, 같은 라이브러리는 아닙니다.

`Scribe`가 맡는 것:

- lifecycle orchestration
- runtime capture flow
- sink dispatch
- degraded capture handling
- high-level SDK ergonomics

`Spine`이 맡는 것:

- canonical object model
- validation rule
- serialization semantics
- compatibility와 migration logic

즉 다음 질문은:

- "어디서 run을 열어야 하지"
- "무엇이 자동으로 emit되지"
- "degraded capture를 어떻게 해석하지"

이건 `Scribe`의 영역입니다.

그리고 다음 질문은:

- "이 canonical object는 정확히 무엇을 의미하지"
- "이 payload는 어떻게 validation되지"
- "legacy schema는 어떻게 업그레이드되지"

이건 `Spine`의 영역입니다.

## 흔한 개념적 실수

### 1. `Scribe`를 범용 logger처럼 다루기

event 같은 record를 emit할 수는 있지만, 진짜 가치는 contextual capture, lifecycle
automation, 구조화된 sink dispatch에 있습니다.

### 2. Scope를 너무 적게 열기

모든 것이 run level에만 캡처되면 stage-level, operation-level 해석이 훨씬 어려워집니다.

### 3. Scope를 너무 많이 열기

아주 작은 내부 함수 호출마다 operation을 열면 신호가 금방 시끄러워질 수 있습니다.

### 4. `degraded`를 failure와 같다고 보기

이렇게 보면 중요한 운영 구분이 사라집니다. degraded capture는 유용한 truth를 여전히
보존하는 경우가 많고, 명시적인 degradation evidence도 emit할 수 있습니다.

### 5. `Scribe`가 `Spine`을 대체한다고 생각하기

`Scribe`는 capture SDK이지 schema-definition 라이브러리가 아닙니다. 둘은 함께
작동하지만 해결하는 문제는 다릅니다.

## 이 페이지에서 가져가야 할 핵심 직관

아주 짧게 정리하면:

- `Scribe`는 `run`, `stage`, `operation`을 중심으로 runtime capture를 구조화하고
- 모든 capture action은 네 가지 payload family 중 하나를 만들며
- capture result는 success나 failure뿐 아니라 degraded fidelity도 설명하고
- `Scribe`는 runtime orchestration을, `Spine`은 canonical contract를 담당합니다

이 네 가지를 기억하고 있으면 나머지 `Scribe` 문서도 훨씬 쉽게 탐색할 수 있습니다.

## 이 페이지 다음에 읽을 것

이 페이지가 "런타임이 어떻게 생겼는가"를 설명했다면, 다음 문서들은 "어떤 capture
primitive를 선택해야 하는가"와 "그 capture가 운영적으로 어떻게 동작하는가"를
설명합니다.

- event, metric, span, batch 가이드:
  [캡처 패턴](capture-patterns.md)
- sink 동작과 로컬 확인:
  [싱크와 저장소](sinks-and-storage.md)
- reduced-fidelity capture와 오류 해석:
  [Degradation과 오류](degradation-and-errors.md)

가장 자연스러운 다음 문서는 보통
[캡처 패턴](capture-patterns.md)입니다.
