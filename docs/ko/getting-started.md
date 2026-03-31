# 시작하기

[사용자 가이드 홈](../USER_GUIDE.ko.md)

이 페이지는 처음 `Scribe`를 쓰는 사람에게 가장 실용적인 출발점입니다. 목표는 네
가지입니다:

1. 로컬 환경에서 `Scribe`를 import 가능하게 만들기,
2. 최소한의 `Scribe -> run -> event/metric` 흐름을 만들기,
3. `Scribe`가 무엇을 자동으로 캡처하는지 이해하기,
4. 실제로 `CaptureResult`가 무엇을 뜻하는지 직관을 얻기.

이 페이지를 끝낼 때쯤이면 작은 Python 워크플로에 `Scribe`를 붙이고, 첫 event와
metric을 기록하고, 그 결과로 생성된 로컬 출력을 직접 확인할 수 있어야 합니다.

## Scribe가 해결하는 문제

대부분의 ML 시스템에서 observability 로직은 처음에는 임시 로그, 메트릭, 파일
경로가 뒤섞인 형태로 시작합니다.

예를 들면:

- 상태 전이를 남기는 평범한 로그 라인,
- 이름 규칙이 제각각인 metric emitter,
- 실행 컨텍스트 없이 저장된 artifact path,
- run이나 stage identity와 깔끔하게 연결되지 않는 trace.

한동안은 이 방식도 돌아가지만, 시간이 지나면 같은 질문들이 점점 더 어려워집니다:

- 이 metric은 어느 run이 만들었는가,
- 이 artifact는 어느 stage가 만들었는가,
- capture는 완전히 성공했는가 아니면 부분적으로만 보존됐는가,
- 이 run이 시작될 때 어떤 environment가 활성화되어 있었는가,
- 아직 backend가 없을 때 local-first capture는 어디로 가야 하는가.

`Scribe`는 런타임 코드에 하나의 capture-side SDK를 제공해서 그 모호함을 줄여줍니다.
이 SDK는:

- 명시적인 lifecycle scope를 열고,
- canonical observability payload를 만들고,
- 이를 sink로 dispatch하고,
- degraded capture를 구조화된 증거로 남깁니다.

짧게 말하면, `Scribe`는 이렇게 말하는 라이브러리입니다:

"워크플로가 실행되는 동안 런타임 truth를 구조화된 observability data로 캡처하라.
서로 무관한 side effect 모음으로 남기지 말고."

## 시작 전에 알면 좋은 것

처음에는 네 가지 아이디어만 알면 충분합니다:

- `Scribe(...)` 세션 하나를 만든다,
- `run`을 연다,
- 그 run 안에서 event와 metric 데이터를 emit한다,
- payload가 어디로 갈지는 sink가 결정하게 둔다.

가장 작은 유용한 그림은 이렇게 생겼습니다:

```text
Scribe
  -> run
    -> event / metric / span / artifact
      -> CaptureResult
        -> sink output
```

이 그림만 명확하면, 나머지 라이브러리도 훨씬 쉽게 이해됩니다.

## 설치와 로컬 실행

### 워크스페이스 환경에서 설치하기

`Scribe`는 SDK 뒤에서 사용되는 canonical contract model을 제공하는 `Spine`에 의존합니다.

로컬 개발에서는 두 저장소를 editable mode로 함께 설치하는 것이 가장 간단합니다:

```bash
pip install -e ../Spine -e .[dev]
```

이렇게 하면 다음이 한 번에 준비됩니다:

- 로컬 `scribe` 패키지,
- 로컬 `spine` 패키지,
- `pytest`, `ruff`, `mypy` 같은 개발 도구.

### Import 확인하기

설치 후에는 로컬 패키지가 올바르게 해석되는지 확인하는 것이 좋습니다:

```bash
python -c "import scribe; print(scribe.__file__)"
```

이 명령이 성공하면, 환경이 오래된 설치본이나 누락된 설치본이 아니라 로컬 `scribe`
패키지를 import하고 있다는 뜻입니다.

## 기본 import 패턴

대부분의 사용자는 top-level `scribe` 패키지에서 시작하면 충분합니다.

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe
```

처음에는 이것만 기억해도 됩니다:

- `Scribe`는 메인 SDK entrypoint이고,
- `LocalJsonlSink`는 가장 쉬운 local-first sink이며,
- 일상적인 호출 대부분은 `Scribe` 인스턴스나 `run()`이 반환한 active scope에서 일어납니다.

## 첫 Scribe 세션

가장 쉬운 시작점은 로컬 JSONL sink입니다.

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)
```

이 단계에서 가장 중요한 생성자 필드는 둘입니다:

- `project_name`: 이 SDK 세션의 논리적 project identity,
- `sinks`: payload를 어디로 dispatch할지.

왜 `LocalJsonlSink`가 첫 sink로 가장 좋은가:

- 외부 인프라 없이 동작하고,
- payload family를 디스크에서 분리해 보관하고,
- 로컬 개발 중 확인하기 쉽고,
- backend 제품을 고르기 전에도 지속적인 저장 경로를 제공하기 때문입니다.

## 첫 Run

가장 유용한 첫 capture 흐름은 다음과 같습니다:

1. `Scribe`를 만든다,
2. run scope에 들어간다,
3. event 하나를 emit한다,
4. metric 하나를 emit한다.

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

이 코드는 `Scribe`가 의도한 기본 사용 루프를 그대로 보여줍니다:

1. 세션을 만들고,
2. lifecycle scope를 열고,
3. runtime fact를 캡처하고,
4. 구조화된 결과를 확인합니다.

## 자동으로 일어나는 일

이 부분은 아주 초기에 꼭 이해해야 합니다.

run이 시작되면, `Scribe`는 사용자가 명시적으로 emit한 event나 metric만 저장하는 것이
아닙니다. lifecycle과 environment truth도 자동으로 캡처합니다.

최소한 정상적인 run은 보통 다음을 emit합니다:

- `Project`
- `Run(status="running")`
- `EnvironmentSnapshot`
- `run.started`
- 사용자가 명시적으로 emit한 event와 metric record
- `run.completed`
- `Run(status="completed")`

즉 lifecycle truth는 사용자가 모든 전이를 손으로 emit하는지에 의존하지 않습니다.

## `CaptureResult`가 의미하는 것

각 capture 호출은 모두 `CaptureResult`를 반환합니다.

가장 중요한 필드는 `status`입니다:

- `success`: capture가 정상적으로 끝남
- `degraded`: 일부 truth는 캡처됐지만 fidelity가 떨어짐
- `failure`: 모든 eligible sink가 실패함

초기 로컬 사용에서 가장 흔한 결과는 `success`입니다.

하지만 아주 초기에 바로 이해해야 할 것은, `degraded`가 "아무것도 안 됐다"와
같은 뜻이 아니라는 점입니다. `Scribe`에서 degraded capture는 보통 이런 의미입니다:

- 한 sink는 실패했지만 다른 sink가 payload를 받아들였다,
- 파일이 아직 없더라도 artifact를 등록하도록 허용했다,
- 경고와 함께 capture가 끝났지만 그 경고 자체는 증거로 남겨야 한다.

즉 `CaptureResult`는 장식용 메타데이터가 아닙니다. capture action의 운영 상태입니다.

## 최소 Artifact 예제

event와 metric이 첫 단계로 가장 쉽기는 하지만, artifact capture도 `Scribe`의 큰
축입니다.

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

파일이 없고 `allow_missing=True`라면, 결과는 hard failure가 아니라 `degraded`가 될 수
있습니다. 이것은 의도된 동작입니다. `Scribe`는 partial truth를 지우기보다 보존하도록
설계되어 있습니다.

## 최소 Stage와 Operation 예제

첫 페이지에서 완전한 중첩을 다 이해할 필요는 없지만, 형태는 한 번 봐두는 것이
좋습니다.

```python
with scribe.run("baseline-train") as run:
    with run.stage("train") as stage:
        with stage.operation("step-1") as operation:
            operation.metric("training.loss", 0.42, aggregation_scope="step")
            operation.span("model.forward", span_kind="model_call")
```

여기서 중요한 것은 아직 모든 메서드를 외우는 것이 아닙니다. 다음 구조를 보는
것입니다:

- `run`은 최상위 execution scope이고,
- `stage`는 run 내부의 큰 phase이며,
- `operation`은 active context 안의 더 작은 work unit입니다.

## 로컬 출력 확인하는 법

`LocalJsonlSink`를 쓰면 payload는 family별로 저장됩니다:

- `contexts.jsonl`
- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

sink API로 다시 읽어올 수도 있습니다:

```python
from pathlib import Path

from scribe import LocalJsonlSink, PayloadFamily

sink = LocalJsonlSink(Path("./.scribe"))
record_entries = sink.read_family(PayloadFamily.RECORD)
print(len(record_entries))
```

이 방법은 `Scribe`가 실제로 무엇을 emit하는지 감을 잡는 가장 쉬운 길 중 하나입니다.

## 조금 더 현실적인 예제

아래 예제는 여전히 작지만, 실제 워크플로에 더 가깝게 보이기 시작합니다.

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

이 예제는 `Scribe`의 핵심 조립 원리를 보여줍니다:

1. 먼저 execution context를 만들고,
2. 그 context 안에서 event와 metric을 캡처하고,
3. artifact 같은 출력을 붙이고,
4. sink가 결과를 저장하게 둡니다.

## 처음 자주 하는 실수

### 1. active run 없이 emit하기

이 경우 `ContextError`가 발생합니다.

좋지 않은 패턴:

```python
scribe.metric("training.loss", 0.42)
```

좋은 패턴:

```python
with scribe.run("training") as run:
    run.metric("training.loss", 0.42, aggregation_scope="step")
```

### 2. `degraded`를 전체 실패처럼 다루기

`Scribe`에서 degraded capture는 "일부 truth가 보존됐다"는 뜻인 경우가 많습니다.
무시하지 말고 확인해야 합니다.

### 3. 처음부터 너무 많은 scope를 열기

처음에는 `run`만으로 시작해도 괜찮고, 실제 워크플로가 필요로 할 때 `stage`와
`operation`을 추가하면 됩니다.

### 4. 로컬 확인을 건너뛰기

`Scribe`를 가장 빨리 이해하는 길은 로컬 sink가 실제로 무엇을 썼는지 보는 것입니다.

## 이 페이지에서 가져가야 할 핵심 직관

아주 짧게 정리하면:

- `Scribe`는 `run`을 열고 그 안에서 몇 가지 runtime fact를 캡처하는 방식으로 도입되고,
- payload가 어디로 갈지는 sink가 결정하며,
- lifecycle과 environment capture는 자동으로 일어나고,
- `CaptureResult`는 capture가 success, degraded, failure 중 무엇이었는지 알려주고,
- 로컬 JSONL 출력이 가장 쉬운 첫 확인 경로입니다.

한 문장으로 줄이면:

"로컬 sink 하나, run 하나, event 하나, metric 하나로 시작하고, scope나 복잡도를 더하기
전에 먼저 결과를 직접 확인하라."

## 다음에 읽을 문서

이 페이지가 이해됐다면, 다음 문서들이 보통 가장 유용합니다:

1. [핵심 개념](core-concepts.md):
   scope, payload family, result type의 mental model이 필요할 때
2. [캡처 패턴](capture-patterns.md):
   event, metric, span, batch API를 언제 써야 하는지 실전 가이드가 필요할 때
3. [싱크와 저장소](sinks-and-storage.md):
   로컬 JSONL 출력과 sink 동작을 이해하고 싶을 때
4. [Degradation과 오류](degradation-and-errors.md):
   reduced-fidelity capture와 운영 실패 모드를 이해하고 싶을 때

## 관련 파일

- Public SDK entrypoint: [src/scribe/api/session.py](../../src/scribe/api/session.py)
- Result models: [src/scribe/results/models.py](../../src/scribe/results/models.py)
- Built-in sinks: [src/scribe/sinks/__init__.py](../../src/scribe/sinks/__init__.py)
- Training example: [examples/training_workflow.py](../../examples/training_workflow.py)
