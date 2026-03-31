# 싱크와 저장소

[사용자 가이드 홈](C:/Users/eastl/MLObservability/Scribe/docs/ko/README.md)

`Scribe`가 runtime truth를 캡처하기 시작하면, 바로 다음 질문이 나옵니다:

"그렇게 캡처된 truth는 실제로 어디로 가는가?"

이 페이지는 그 질문에 답하는 sink boundary를 설명합니다. 단순히 로컬 파일에 대한
문서가 아닙니다. `Scribe`가 canonical payload를 어떻게 storage나 forwarding layer에
넘기는지, payload-family support가 결과에 어떤 영향을 주는지, 일부 데이터가 여전히
보존된 상황에서도 왜 degraded capture가 나타날 수 있는지를 설명하는 페이지입니다.

이 페이지의 목표는 다음과 같습니다:

1. 왜 sink가 `Scribe` 안에서 별도의 레이어인지 설명하기,
2. payload family dispatch가 어떻게 동작하는지 보여주기,
3. built-in sink의 동작을 설명하기,
4. 추측 없이 local JSONL output을 확인하는 방법을 보여주기.

이 페이지를 읽고 나면 sink를 어떻게 설정하는지뿐 아니라, sink 동작이
`CaptureResult`의 의미를 어떻게 바꾸는지, 왜 어떤 delivery는 skipped나 degraded로
표시되는지, 디스크 위의 captured payload를 어떻게 자신 있게 해석해야 하는지도
이해할 수 있어야 합니다.

## 왜 Sink는 별도 레이어로 존재하는가

`Scribe`는 capture logic과 storage logic이 같은 관심사가 아니도록 설계되어 있습니다.

실무에서는 이 구분이 아주 중요합니다.

런타임에서 `Scribe`가 책임지는 것은 다음입니다:

- lifecycle context 생성,
- canonical payload 구성,
- capture shape의 validation과 normalization,
- degraded capture를 구조화된 증거로 기록하기,
- payload를 family별로 dispatch하기.

반대로 `Scribe`가 의도적으로 책임지지 않는 것은 다음입니다:

- 각 backend의 persistence layout 결정,
- transport가 어떻게 일어날지 결정,
- 캡처된 truth를 로컬에 저장할지, 원격으로 전달할지, 메모리에만 둘지 결정.

두 번째 책임은 sink의 영역입니다.

이 분리가 없다면 금방 여러 문제가 생깁니다:

- 모든 capture call이 persistence를 지나치게 많이 알아야 하고,
- 로컬 개발과 backend-connected production이 강하게 결합되며,
- 하나의 storage path 때문에 생긴 degraded capture를 명확하게 보고하기 어려워지고,
- 새로운 output target을 추가할 때 capture logic 자체를 바꿔야 하기 때문입니다.

즉 sink boundary는 단순한 구현 편의가 아닙니다. `Scribe`를 vendor-agnostic하고,
local-first이며, 운영적으로 설명 가능한 상태로 유지하는 핵심 설계 선택 중 하나입니다.

## Sink Boundary를 어떻게 생각할까

가장 쉬운 생각법은 이렇습니다:

- `Scribe`가 truth를 만들고,
- sink가 그 truth를 어떻게 다룰지 결정합니다.

상위 수준 흐름은 이렇게 생겼습니다:

```text
runtime code
  -> Scribe scope and capture API
    -> canonical payload
      -> payload family dispatch
        -> one or more sinks
          -> storage or forwarding behavior
```

즉 sink는 "`Scribe`가 유효해지는 장소"가 아닙니다. payload는 sink가 보기 전부터 이미
의미 있는 canonical object입니다. sink는 그 canonical object가 저장되거나, 전달되거나,
검사되는 다음 경계입니다.

## Payload Family가 먼저다

`Scribe` 저장 동작에서 가장 중요한 아이디어 중 하나는 sink가 단순히 "어떤 payload"
를 받는 것이 아니라는 점입니다. payload는 다음 네 가지 family 중 하나로 묶여서
전달됩니다:

- `context`
- `record`
- `artifact`
- `degradation`

이 family 분리는 sink가 어떤 family는 지원하고 어떤 family는 지원하지 않을 수 있기
때문에 중요합니다.

예:

- 어떤 sink는 `record`만 지원할 수 있고,
- 다른 sink는 모든 family를 지원할 수 있으며,
- 로컬 inspection sink는 모든 family를 원할 수 있고,
- 어떤 specialized downstream target은 artifact에만 관심이 있을 수 있습니다.

즉 `Scribe`의 payload routing은 "모든 것을 모든 sink에 맹목적으로 보내기"가 아닙니다.
"각 payload를 family별로 dispatch하고, 각 sink가 자신이 무엇을 지원하는지 선언하게
두기"입니다.

## Sink Interface

sink interface는 의도적으로 작습니다.

핵심 abstract type은 [Sink](C:/Users/eastl/MLObservability/Scribe/src/scribe/sinks/base.py)
입니다.

높은 수준에서 sink는 다음을 제공합니다:

- `name`
- `supported_families`
- `capture(family=..., payload=...)`

이 작은 interface 덕분에 sink layer는 이해하기 쉬운 상태를 유지합니다. sink는 runtime
scope가 어떻게 열렸는지나 payload가 어떻게 생성되었는지를 알 필요가 없습니다. 자신이
어떤 family를 지원하는지, 그리고 그런 payload가 도착했을 때 무엇을 할지만 알면 됩니다.

이것이 같은 `Scribe` instrumentation이 다음 환경에서 그대로 재사용될 수 있는 이유이기도
합니다:

- local JSONL inspection,
- 테스트,
- composite dispatch,
- 미래의 custom adapter.

## Dispatch가 실제로 하는 일

내부적으로 `Scribe`는 다음과 같은 family-specific helper를 통해 payload를 dispatch합니다:

- `dispatch_context(...)`
- `dispatch_record(...)`
- `dispatch_artifact(...)`
- `dispatch_degradation(...)`

이 helper는 모두
[runtime/dispatch.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/dispatch.py)에
구현된 공통 dispatch path로 모입니다.

이 dispatch logic은 한 번에 여러 일을 합니다:

1. 설정된 sink를 순회하고,
2. 각 sink가 해당 payload family를 지원하는지 확인하고,
3. eligible sink에 delivery를 시도하고,
4. sink별 delivery status를 기록하고,
5. 최종 결과가 `success`, `degraded`, `failure` 중 무엇인지 결정하고,
6. fidelity가 떨어졌다면 선택적으로 degradation-family payload를 emit합니다.

즉 sink dispatch는 단순히 "모든 sink에 capture를 호출한다"가 아닙니다. delivery outcome이
구조화된 운영 데이터가 되는 자리이기도 합니다.

## 왜 Capture가 Degraded가 될 수 있는가

sink layer는 `CaptureResult.status`가 `degraded`가 되는 가장 큰 이유 중 하나입니다.

흔한 경우는 다음과 같습니다:

- 한 sink는 실패했지만 다른 sink가 payload를 받아들였다,
- 현재 payload family를 지원하는 sink가 없다,
- payload 자체가 이미 missing artifact source 같은 degradation reason을 갖고 있었다,
- sink path가 warning이나 delivery gap을 만들어냈다.

이것은 중요한 운영 포인트입니다:

`degraded`는 "아무것도 저장되지 않았다"는 뜻이 아닙니다.

sink boundary에서 degraded는 보통 다음 뜻입니다:

- 적어도 일부 truth는 살아남았지만,
- storage나 forwarding path가 그것을 완벽하게 보존하지는 못했다.

그래서 `Scribe`는 다음을 기록합니다:

- sink별 delivery result,
- degradation reason,
- warning,
- 때로는 전용 degradation-family payload.

## Built-In Sink

public package boundary에서 노출되는 built-in sink 집합은 다음과 같습니다:

- `LocalJsonlSink`
- `InMemorySink`
- `CompositeSink`

이 셋은 서로 중복되지 않습니다. 각각 다른 사용 상황을 위한 도구입니다.

## `LocalJsonlSink`

`LocalJsonlSink`는 처음 쓰는 사람과 local-first usage에서 가장 중요한 built-in sink입니다.

구현은
[adapters/local/jsonl.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/adapters/local/jsonl.py)
에 있습니다.

이 sink가 중요한 이유는 외부 인프라 없이도 `Scribe`에 지속적인 로컬 경로를 주기
때문입니다. 그래서 다음 상황에 매우 잘 맞습니다:

- 초기 통합,
- 디버깅,
- 로컬 실험,
- contract inspection,
- offline workflow.

### 무엇을 쓰는가

`LocalJsonlSink`는 payload family별로 append-friendly한 JSONL 파일 하나씩을 씁니다:

- `contexts.jsonl`
- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

각 줄은 다음 필드를 가진 하나의 JSON object입니다:

- `captured_at`
- `family`
- `payload`

이 구조가 중요한 이유는 로컬 포맷을 다음처럼 유지해 주기 때문입니다:

- append하기 쉽고,
- 줄 단위로 검사하기 쉽고,
- 표준 도구로 parse하기 쉽고,
- payload family별로 분리하기 쉽습니다.

### 왜 Family별 파일 분리가 도움이 되는가

처음 보면 모든 것을 하나의 파일에 넣는 편이 더 단순해 보일 수 있습니다. 하지만
실제 로컬 디버깅에서는 family 분리가 훨씬 다루기 쉽습니다.

예:

- lifecycle과 environment truth만 보고 싶다면 `contexts.jsonl`을 읽고,
- event, metric, span만 보고 싶다면 `records.jsonl`을 읽고,
- output capture만 보고 싶다면 `artifacts.jsonl`을 읽고,
- reduced-fidelity capture를 디버깅하고 싶다면 `degradations.jsonl`을 읽으면 됩니다.

이렇게 하면 하나의 거대한 로컬 stream 안에서 execution context와 다른 모든 payload가
뒤섞이지 않아 inspection이 훨씬 집중됩니다.

### 실제 Serialization 모습

쓰기 전에 sink는 dataclass, enum, path, list, tuple, dict를 JSON-ready value로 변환합니다.
즉 로컬 파일은 불투명한 Python object를 저장하는 것이 아니라, 디버깅과 로컬 툴링에
적합한 구조적으로 검사 가능한 JSON payload를 저장합니다.

중요한 점은 여기의 local JSONL이 전체 아키텍처의 canonical source of truth는 아니라는
것입니다. 이것은 sink boundary 뒤에 있는 하나의 구체적인 adapter입니다. canonical
meaning은 여전히 sink가 받기 전에 `Scribe`가 만든 payload에서 나옵니다.

## `InMemorySink`

`InMemorySink`는 성격이 꽤 다른 sink입니다.

구현은
[sinks/memory.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/sinks/memory.py)에 있습니다.

이 sink는 action을 메모리 안에 다음 tuple 형태로 저장합니다:

- payload family
- payload object

그래서 다음 상황에 매우 유용합니다:

- 테스트,
- 로컬 실험,
- emit된 payload에 대한 assertion,
- 직렬화된 파일 대신 object를 직접 보고 싶은 상황.

실무적으로 `InMemorySink`는 장기 저장보다는 동작 테스트에 훨씬 더 유용합니다.

잘 맞는 예:

- `run.started`가 emit되었는지 확인하기,
- metric record가 sink에 도달했는지 검증하기,
- partial failure 중 degradation-family payload가 emit되었는지 확인하기.

## `CompositeSink`

`CompositeSink`는 또 다른 이유로 존재합니다.

구현은
[sinks/composite.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/sinks/composite.py)에
있습니다.

이 sink는 들어오는 payload를 여러 child sink에 전달합니다. 사실상 child support set을
합친 grouped sink처럼 동작합니다.

하나의 capture action이 여러 output으로 동시에 흘러가야 할 때 유용합니다.

예:

- 로컬 JSONL audit trail을 남기면서 동시에 memory에도 payload를 수집하기,
- 여러 custom sink를 하나의 named sink 아래 묶기,
- setup code에서는 하나의 logical sink object만 다루되 실제로는 여러 target에 도달하기.

운영적으로 기억할 점은, `CompositeSink`가 downstream child failure에 대해 생각할 필요를
없애주지는 않는다는 것입니다. fan-out behavior를 묶어 줄 뿐입니다.

## Sink가 Family를 지원하지 않을 때 무슨 일이 일어나는가

이것은 초기에 꼭 이해해야 하는 중요한 `Scribe` 동작입니다.

sink가 어떤 payload family를 지원하지 않으면:

- 그 family에 대해서는 sink가 호출되지 않고,
- `status=skipped`인 `Delivery` entry가 기록되며,
- 설정된 sink 중 그 family를 지원하는 것이 하나도 없으면 capture result가
  `degraded`가 될 수 있습니다.

즉 unsupported family behavior는 눈에 보이고 명시적입니다. 조용히 사라지지 않습니다.

이것이 중요한 이유는, 그렇지 않으면 사용자가 실제로는 어떤 sink도 그 payload family를
저장하지 못했는데도 capture가 정상적으로 성공했다고 오해할 수 있기 때문입니다.

예:

- record-only sink는 metric과 event는 받아들일 수 있지만,
- artifact는 어떤 sink도 지원하지 않아 degraded가 될 수 있습니다.

그 경우 올바른 해석은 "artifact capture가 성공했다"가 아닙니다. "설정된 어떤 sink도
그 family를 받을 수 없어서 reduced fidelity로 끝났다"입니다.

## Sink가 Error를 Raise하면 무슨 일이 일어나는가

capture 중 sink가 raise하면:

- 그 sink에는 `status=failure`인 `Delivery`가 붙고,
- failure detail이 기록되며,
- `sink_failure:<name>` 같은 degradation reason이 추가되고,
- 전체 capture result는 모든 delivery를 바탕으로 다시 계산됩니다.

이것은 실무적으로 매우 유용한 `Scribe` 동작으로 이어집니다:

- 한 sink는 실패했지만 다른 sink가 성공하면 전체 결과는 대개 `degraded`가 되고,
- eligible sink가 모두 실패하면 `Scribe`는 `SinkDispatchError`를 raise합니다.

이 경계가 건강한 이유는 다음 두 truth를 분명히 구분해 주기 때문입니다:

- 어떤 실패는 살아남은 capture를 그대로 보존해야 하고,
- 완전한 storage failure는 성공으로 오해되면 안 됩니다.

## 왜 Degradation Payload가 자동으로 Emit될 수 있는가

degradation family가 아닌 payload가 degraded가 되었고 active run이 있을 때, `Scribe`는
전용 degradation-family payload도 함께 emit할 수 있습니다.

이 동작이 중요한 이유는 reduced-fidelity capture를 first-class observability data로
바꾸기 때문입니다.

degradation을 단순히 반환된 result object 안에만 남겨두는 대신, `Scribe`는 capture
문제의 증거를 같은 truth system 안에 저장할 수 있습니다.

즉 나중에 읽는 사람은 다음을 구분할 수 있습니다:

- 깨끗하게 캡처된 payload,
- 부분적으로 캡처된 payload,
- 왜 fidelity가 떨어졌는지 설명하는 evidence record.

local JSONL 관점에서 보면, degraded action 하나가 원래 family 파일뿐 아니라
`degradations.jsonl`에도 흔적을 남길 수 있다는 뜻이기도 합니다.

## 첫 로컬 Sink를 어떻게 설정할까

가장 쉬운 시작 설정은 다음과 같습니다:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)
```

이 설정이 가장 좋은 첫 선택인 이유는:

- 지속적이고,
- 확인하기 쉽고,
- 모든 payload family를 지원하고,
- 초기 운영 이야기를 단순하게 유지해 주기 때문입니다.

`Scribe`를 이해하려고 한다면, 지나치게 추상적이거나 고도로 커스터마이즈된 sink
설정보다 이 구성이 훨씬 더 많은 것을 가르쳐 줍니다.

## 로컬 출력은 어떻게 확인할까

가장 쉬운 inspection path는 sink helper method를 직접 사용하는 것입니다.

```python
from pathlib import Path

from scribe import LocalJsonlSink, PayloadFamily

sink = LocalJsonlSink(Path("./.scribe"))
entries = sink.read_family(PayloadFamily.RECORD)
```

이렇게 하면 해당 family에 대한 parse된 JSON object list를 얻습니다.

이 정도면 보통 다음 질문에 답하기 충분합니다:

- 내 event가 정말로 써졌는가,
- 이 payload는 어떤 family 아래 저장되었는가,
- degradation-family record가 생겼는가,
- 직렬화된 로컬 payload는 실제로 어떤 모양이었는가.

정확한 on-disk file 경로도 sink에게 물을 수 있습니다:

```python
from pathlib import Path

from scribe import LocalJsonlSink, PayloadFamily

sink = LocalJsonlSink(Path("./.scribe"))
print(sink.path_for(PayloadFamily.ARTIFACT))
```

이것은 에디터에서 파일을 직접 열거나 다른 로컬 도구에 넘길 때 자주 유용합니다.

## 정상적인 로컬 Capture Sequence는 어떤 모습인가

하나의 local sink와 하나의 run이 있는 단순 워크플로를 실행한다고 가정해 봅시다:

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

로컬 저장소에서는 보통 다음을 보게 됩니다:

- `contexts.jsonl` 안의 context-family payload,
- `records.jsonl` 안의 record-family payload,
- 실제로 캡처하지 않았다면 artifact나 degradation entry는 대개 없음.

즉 로컬 출력은 처음엔 다소 반복적으로 보일 수 있습니다. 이것은 정상입니다. `Scribe`는
사용자가 명시적으로 emit한 fact와, 그 fact에 의미를 주는 lifecycle truth를 둘 다
기록하기 때문입니다.

## Local JSONL의 반복을 어떻게 생각할까

많은 사람이 가장 먼저 눈치채는 것은 로컬 파일이 꽤 반복적으로 보일 수 있다는 점입니다.

예를 들어 하나의 run은 다음을 만들 수 있습니다:

- `Run(status="running")` context payload,
- `run.started` lifecycle record,
- 사용자가 명시적으로 emit한 event,
- 사용자가 명시적으로 emit한 metric,
- `run.completed` lifecycle record,
- `Run(status="completed")` context payload.

이 반복은 우발적인 중복이 아닙니다. 서로 다른 truth 종류를 반영합니다:

- context snapshot,
- lifecycle record,
- explicit user capture.

즉 local JSONL은 deduplicated reporting view가 아니라 append-only operational truth로
읽어야 합니다.

## Family별 저장 해석

각 family를 다르게 생각하면 도움이 됩니다.

### `context`

이 family는 실행이 어디서 일어났는지를 알려줍니다.

전형적인 payload:

- `Project`
- `Run`
- `StageExecution`
- `OperationContext`
- `EnvironmentSnapshot`

### `record`

이 family는 무엇이 일어났거나 무엇이 관측되었는지를 알려줍니다.

전형적인 payload:

- 구조화된 event
- metric
- span
- lifecycle record

### `artifact`

이 family는 어떤 durable output이 등록되었는지를 알려줍니다.

전형적인 payload:

- artifact binding과 manifest

### `degradation`

이 family는 capture fidelity가 어디서 떨어졌는지를 알려줍니다.

전형적인 payload:

- degradation evidence record

단순히 파일 이름으로만 보지 말고 이런 의미를 기준으로 로컬 파일을 읽기 시작하면,
sink layout은 훨씬 해석하기 쉬워집니다.

## 좋은 Sink 사용 패턴

다음 패턴은 대체로 건강합니다.

### 모든 것을 지원하는 Sink 하나로 시작하기

초기 통합에서는 `LocalJsonlSink`가 거의 항상 가장 안전한 선택입니다.

### 테스트와 Assertion에는 `InMemorySink` 쓰기

emit된 payload object를 직접 보고 싶다면, 파일을 읽는 것보다 in-memory capture가 대개
더 낫습니다.

### Composite Behavior는 의도적으로 쓰기

capture를 여러 child sink로 fan-out하고 싶다면, delivery outcome과 failure 해석을
여전히 명확하게 사고하고 있어야 합니다.

### 성공을 가정하지 말고 Delivery를 확인하기

sink 동작을 디버깅할 때는 top-level status만 보는 것보다 `CaptureResult.deliveries`가
훨씬 더 많은 정보를 주는 경우가 많습니다.

## 흔한 Sink 실수

### 1. Sink가 의미를 정의한다고 생각하기

sink는 payload가 무엇을 의미하는지를 결정하지 않습니다. 이미 의미 있는 payload에
무슨 일이 일어날지를 결정할 뿐입니다.

### 2. Unsupported Family를 무해하다고 생각하기

어떤 family도 지원하지 않는 sink 구성은 운영 신호입니다. 보통 그 capture result는
정상 저장이 아니라 degraded로 읽어야 합니다.

### 3. `degradations.jsonl`을 무시하기

reduced-fidelity behavior를 로컬에서 디버깅할 때, degradation-family 파일이 디렉터리에서
가장 많은 정보를 주는 경우가 많습니다.

### 4. Output을 Record 중심으로만 보기

`records.jsonl`만 보면, 그 record를 어떻게 해석해야 하는지 설명해 주는 context와
degradation data를 놓칠 수 있습니다.

### 5. Local Storage를 전체 아키텍처와 혼동하기

`LocalJsonlSink`는 하나의 구체적인 로컬 adapter이지, 전체 `Scribe` 아키텍처의 정의가
아닙니다.

## 이 페이지에서 가져가야 할 핵심 직관

아주 짧게 정리하면:

- `Scribe`는 먼저 canonical truth를 만들고 그다음 sink에 넘기며,
- sink는 하나의 미분화된 stream이 아니라 payload family 단위로 동작하고,
- delivery result가 `CaptureResult`를 형성하며,
- local JSONL output은 captured payload를 확인하기 쉬운 operational view이고,
- sink boundary에서의 degraded capture는 숨겨지지 않고 명시적으로 확인 가능합니다.

가장 중요한 문장은 이것입니다:

`Scribe`가 capture meaning을 담당하고, sink는 그 meaning이 capture path를 벗어난 뒤
무슨 일을 겪는지를 담당합니다.

## 다음에 읽을 문서

이 페이지가 이해됐다면, 다음 문서들이 보통 가장 유용합니다:

1. [Degradation과 오류](C:/Users/eastl/MLObservability/Scribe/docs/ko/degradation-and-errors.md):
   sink failure와 reduced fidelity가 어떻게 보고되는지 더 깊이 보고 싶을 때
2. [아티팩트](C:/Users/eastl/MLObservability/Scribe/docs/ko/artifacts.md):
   degraded capture가 실제로 자주 생기는 family를 보고 싶을 때
3. [예제](C:/Users/eastl/MLObservability/Scribe/docs/ko/examples.md):
   더 큰 end-to-end 흐름 안에서 sink usage를 보고 싶을 때

## 관련 파일

- Sink interface: [src/scribe/sinks/base.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/sinks/base.py)
- Composite sink: [src/scribe/sinks/composite.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/sinks/composite.py)
- In-memory sink: [src/scribe/sinks/memory.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/sinks/memory.py)
- Local JSONL sink: [src/scribe/adapters/local/jsonl.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/adapters/local/jsonl.py)
- Dispatch logic: [src/scribe/runtime/dispatch.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/dispatch.py)
