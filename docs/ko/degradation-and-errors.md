# Degradation과 오류

[사용자 가이드 홈](C:/Users/eastl/MLObservability/Scribe/docs/ko/README.md)

`Scribe`를 이해할 때 가장 중요한 부분 중 하나는, 뭔가 잘못되었을 때 이 라이브러리가
그 상황을 어떻게 말하는지 배우는 것입니다.

대부분의 instrumentation 라이브러리는 실패를 하나의 흐릿한 개념으로 뭉개 버립니다:

- 사용자는 아무것도 못 보거나,
- 호출이 raise되거나,
- warning이 로그 어딘가에 묻혀 사라집니다.

`Scribe`는 좀 더 구조적인 접근을 취합니다.

모든 불완전한 capture outcome을 같은 사건으로 취급하는 대신, 몇 가지 상황을 분리합니다:

- capture가 정상적으로 성공했는가,
- 일부 truth는 보존됐지만 fidelity가 떨어졌는가,
- eligible sink boundary에서 완전히 실패했는가,
- capture가 시작되기도 전에 usage 자체가 invalid했는가.

이 페이지는 그 차이를 설명합니다.

이 페이지의 목표는 다음과 같습니다:

1. `success`, `degraded`, `failure`가 실제로 무엇을 뜻하는지 설명하기,
2. `CaptureResult`와 `BatchCaptureResult`를 운영적으로 어떻게 읽어야 하는지 보여주기,
3. 언제 `Scribe`가 예외를 raise하고, 언제 partial truth를 대신 보존하는지 설명하기,
4. 가장 흔한 실패 및 reduced-fidelity path를 디버깅하도록 돕기.

이 페이지를 읽고 나면 다음을 구분할 수 있어야 합니다:

- 깨끗한 capture,
- 부분적으로 보존된 capture,
- 완전한 sink dispatch failure,
- 애초에 valid runtime context가 없어서 성립할 수 없었던 invalid call.

## 왜 Degradation이 아예 존재하는가

처음 보면 모든 불완전한 capture를 failure로 취급하는 편이 더 단순해 보일 수 있습니다.

하지만 실제 ML workflow에서는 그것이 지나치게 무딥니다.

예를 들어:

- 한 sink는 실패했지만 다른 sink는 payload를 보존했을 수 있고,
- file body가 존재하기 전에 artifact의 논리적 identity가 먼저 알려질 수 있으며,
- 파일은 존재하지만 hash 계산이 실패할 수 있고,
- 어떤 payload family를 지원하는 sink가 하나도 없을 수 있습니다.

이런 경우들에서는 여전히 truth의 일부가 존재합니다.

시스템이 이런 모든 경우를 generic failure 하나 아래로 던져 버리면, 나중의 분석은
훨씬 약해집니다. 다음 차이를 잃어버리기 때문입니다:

- "아무것도 보존되지 않았다"
- "전체는 아니지만 일부 truth는 보존되었다"

`Scribe`는 degradation semantics를 통해 이 차이를 명시적으로 유지합니다.

그래서 이 페이지가 중요합니다. `degraded`를 잘못 이해하면, 라이브러리의 핵심 운영
동작 중 하나를 잘못 이해하게 됩니다.

## 세 가지 주요 Capture Outcome

상위 수준에서 대부분의 단일 capture call은 다음 세 outcome 중 하나를 만듭니다:

- `success`
- `degraded`
- `failure`

이것들은
[results/models.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/results/models.py)의
`DeliveryStatus`를 통해 표현됩니다.

### `success`

`success`는 다음을 뜻합니다:

- 적어도 하나의 eligible sink가 payload를 받아들였고,
- 그 capture path에 degradation reason이 붙지 않았다.

이것이 가장 깨끗한 경로입니다.

### `degraded`

`degraded`는 다음을 뜻합니다:

- 일부 truth는 캡처되었지만,
- 어떤 이유로 fidelity가 떨어졌다.

이것은 장식용 label이 아닙니다. capture를 여전히 사용해야 하지만, 좀 더 주의해서
해석해야 한다는 구조화된 선언입니다.

### `failure`

`failure`는 다음을 뜻합니다:

- 어떤 eligible sink도 payload를 성공적으로 캡처하지 못했고,
- dispatch 관점에서 그 capture를 success나 degraded result로 보존할 수 없었다.

현재 구현에서는 eligible sink가 모두 실패하면 `SinkDispatchError`를 raise합니다.

즉 실무에서는 전체 실패가 조용히 반환되는 `CaptureResult(status="failure")`보다 예외로
더 자주 나타납니다.

## 왜 `degraded`는 Failure의 약한 버전이 아닌가

이것은 페이지 전체에서 가장 중요한 구분입니다.

`degraded`는 "거의 실패했다"가 아닙니다.

오히려 다음에 더 가깝습니다:

"시스템은 여전히 의미 있는 truth를 가지고 있지만, 그 capture가 완전하고 깨끗한
delivery라고 부르기에는 부족했다."

이 차이는 degraded capture가 여전히 운영적으로 가치 있는 경우가 많기 때문에 중요합니다.

예:

- secondary sink는 실패했지만 metric은 local sink에 도달했다,
- 파일이 없어도 artifact binding은 output identity와 path를 보존했다,
- reduced-fidelity 사건을 나중에 확인할 수 있도록 degradation record 자체가 emit되었다.

degraded capture를 버려도 되는 것으로 취급하면, 부분적인 운영 incident를 설명해 주는
바로 그 증거를 버리게 되는 경우가 많습니다.

## `CaptureResult`는 어떻게 읽어야 하는가

각 single-item capture는 `CaptureResult`를 반환합니다.

중요한 필드는 다음을 포함합니다:

- `family`
- `status`
- `deliveries`
- `warnings`
- `degradation_reasons`
- `payload`
- `degradation_emitted`
- `degradation_payload`

즉 capture result는 단순히 "메서드가 동작했는가"가 아닙니다. dispatch boundary에서
무슨 일이 있었는지에 대한 compact operational report입니다.

### `status`

가장 먼저 봐야 하는 필드입니다.

이 필드는 다음에 답합니다:

- capture가 깨끗했는가,
- 부분적으로 보존되었는가,
- eligible dispatch를 버티지 못했는가.

### `deliveries`

디버깅할 때 가장 정보량이 많은 필드인 경우가 많습니다.

각 `Delivery`는 다음을 말해줍니다:

- 어떤 sink가 고려되었는지,
- 어떤 family를 전달하고 있었는지,
- 그 sink가 success, failure, skipped 중 무엇으로 표시했는지,
- 선택적으로 어떤 detail string이 붙었는지.

즉 "왜 이 capture가 degraded가 되었지?"를 알고 싶다면, top-level status보다
`deliveries`가 더 정확한 이야기를 들려주는 경우가 많습니다.

### `warnings`

warning은 reduced fidelity나 sink-side problem을 설명하는 사람이 읽는 메시지입니다.

특히 다음 상황에서 유용합니다:

- sink가 raise했을 때,
- 어떤 family를 지원하는 sink가 없을 때,
- artifact verification 때문에 fidelity가 떨어졌을 때.

### `degradation_reasons`

이 필드는 왜 fidelity가 떨어졌는지를 설명하는 구조화된 machine-readable reason입니다.

전형적인 reason 예:

- `sink_failure:<name>`
- `no_sinks_configured:<family>`
- `no_sink_support_for_family:<family>`
- `artifact_missing_at_registration`
- `artifact_hash_unavailable`

이 값들이 중요한 이유는 degradation을 나중에 query하고 분류할 수 있게 해주기 때문입니다.

### `degradation_emitted`

이 필드는 전용 degradation-family payload도 함께 emit되었는지를 말해줍니다.

이것이 중요한 이유는 reduced-fidelity capture가 caller에게 반환만 되는 것이 아니라,
persisted truth model의 일부가 될 수도 있기 때문입니다.

## `BatchCaptureResult`는 어떻게 읽어야 하는가

batch capture는 `BatchCaptureResult`를 반환합니다.

중요한 필드는 다음을 포함합니다:

- `status`
- `results`
- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`

이것은 여러 single-item capture 전체를 가로지르는 상위 수준 요약을 줍니다.

중요한 점은 batch status가 item result와 독립적인 것이 아니라는 점입니다. 개별 result에서
유도됩니다.

즉 batch가 degraded라면, 다음 질문은 보통 이것이어야 합니다:

"어떤 item이 degraded였고 그 이유는 무엇인가?"

그래서 정상적인 디버깅 흐름은 다음과 같습니다:

1. batch-level count를 보고,
2. 그다음 individual `CaptureResult`를 본다.

## Degradation은 보통 어디서 오는가

현재 구현에서 degradation은 보통 두 가지 큰 근원에서 옵니다:

- dispatch/sink boundary,
- payload-specific capture logic.

이 구분을 이해하면 디버깅이 훨씬 빨라집니다.

## Sink-Side Degradation

[runtime/dispatch.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/dispatch.py)의
dispatch path는 sink-related degradation이 만들어지는 핵심 자리입니다.

전형적인 sink-side degraded case:

### 1. 한 Sink는 실패하고 다른 Sink는 성공했다

예시 상황:

- local JSONL sink는 record를 받아들였고,
- 두 번째 sink는 예외를 던졌다.

이 경우:

- payload는 어딘가에는 살아남았고,
- configured sink 전체를 기준으로 fidelity는 떨어졌으므로,
- 결과는 `degraded`가 됩니다.

### 2. Sink가 하나도 설정되지 않았다

sink 없이 세션을 만들고 capture가 진행되면, `Scribe`는 다음을 기록합니다:

- sink가 없다는 degradation reason,
- 상황을 설명하는 warning,
- persistence가 있었다고 가장하는 대신 degraded result.

이것이 중요한 이유는 no-sink operation도 명시적인 운영 상태이기 때문입니다. 성공적인
저장과 같은 것이 아닙니다.

### 3. Payload Family를 지원하는 Sink가 없다

예:

- `record`만 지원하는 sink를 설정하고,
- artifact registration을 시도한다.

이 경우:

- 그 sink는 `artifact`에 대해 `skipped`로 표시되고,
- 그 family를 지원하는 eligible sink가 없으며,
- 결과는 degraded가 됩니다.

이것은 unsupported-family behavior를 조용한 drop이 아니라 눈에 보이는 상태로 만들어 줍니다.

## Capture-Logic Degradation

모든 degradation이 sink에서 오는 것은 아닙니다.

일부 degraded state는 payload-specific capture logic 단계에서 더 일찍 생깁니다.

가장 분명한 예는 artifact registration입니다.

[artifacts/service.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/artifacts/service.py)의
artifact service는 dispatch가 시작되기 전부터 degradation reason을 붙일 수 있습니다.

예:

### 1. Registration 시점에 Artifact가 없다

caller가 다음을 쓴다고 가정합시다:

```python
run.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    allow_missing=True,
)
```

그리고 파일이 존재하지 않습니다. 그래도 `Scribe`는 다음을 할 수 있습니다:

- artifact identity를 보존하고,
- target path를 보존하고,
- manifest와 binding을 만들고,
- hard validation failure 대신 degraded result를 반환합니다.

이것은 `degraded`가 "partial truth survived"를 의미하는 가장 강한 예 중 하나입니다.

### 2. Artifact Hash를 사용할 수 없다

파일은 존재하지만 hash 계산이 실패하면, `Scribe`는 artifact binding을 보존하면서도
integrity verification이 불완전했다는 사실을 함께 기록할 수 있습니다.

여기서도 중요한 점은 partial truth가 버려지지 않는다는 것입니다.

## 왜 Degradation Payload가 Emit될 수 있는가

degradation family가 아닌 payload가 degraded가 되고 active run이 있을 때, `Scribe`는
degradation-family payload도 자동으로 emit할 수 있습니다.

이것이 중요한 이유는 "reduced fidelity가 일어났다"는 사실을 반환된 result detail에서
first-class captured fact로 승격시키기 때문입니다.

실무적으로 보면 degraded capture는 두 종류의 흔적을 남길 수 있습니다:

- 원래 family 아래의 original payload,
- quality drop을 설명하는 degradation-family record.

특히 `LocalJsonlSink`를 쓸 때 이것은 나중 inspection에 매우 유용합니다.

또 하나의 중요한 설계 원칙도 드러납니다:

`Scribe`는 degradation을 숨겨야 할 구현 노이즈로 보지 않습니다. capture process 자체에
대한 observability truth로 취급합니다.

## 예외는 이 모델 안에서 어디에 들어가는가

모든 문제가 degraded result가 되는 것은 아닙니다.

일부 문제는 invalid usage나 complete dispatch failure로 다뤄져서 예외를 raise합니다.

이 구분이 건강한 이유는 세 범주를 분명히 갈라주기 때문입니다:

- invalid input 또는 invalid context,
- 부분적으로 보존된 capture,
- eligible sink 전체 실패.

## `ValidationError`

`ValidationError`는 SDK에 invalid data가 전달되었음을 뜻합니다.

이 경우 정상 capture는 안전하게 진행될 수 없습니다.

예:

- 비어 있는 `project_name`
- 비어 있는 metric 혹은 event key
- 지원되지 않는 metric aggregation scope
- 비어 있는 artifact kind
- 엄격한 존재성 요구가 있는 상황에서 artifact path가 없음

이런 실패는 degraded capture state가 아닙니다. caller boundary에서의 contract 문제입니다.

즉 `ValidationError`는 이렇게 읽어야 합니다:

"SDK가 기본 capture rule을 만족하지 못하는 일을 요청받았다."

## `ContextError`

`ContextError`는 lifecycle state가 없거나 일관되지 않음을 뜻합니다.

가장 흔한 예는 active run이 없는데 active run이 필요한 capture를 시도하는 경우입니다.

예:

- run 없이 `scribe.event(...)`
- run 없이 `scribe.metric(...)`
- active run 없이 stage 생성
- active run scope가 없는데 `current_run()`을 호출

이것이 중요한 이유는 context가 `Scribe`에서 선택사항이 아니기 때문입니다. 라이브러리는
lifecycle state를 중심으로 설계되어 있으므로, context 부족은 복구 가능한 추정 상황이
아니라 실제 오류로 취급됩니다.

### `ClosedScopeError`

`ClosedScopeError`는 더 구체적인 lifecycle error입니다.

이미 닫힌 scope를 다시 사용하려 한다는 뜻입니다.

이 예외는 lifecycle boundary가 끝난 뒤에도 조용히 capture가 이어지는 혼란을 막아줍니다.

## `SinkDispatchError`

`SinkDispatchError`는 모든 eligible sink가 payload capture에 실패했다는 뜻입니다.

이것이 전체 dispatch failure에 대응하는 핵심 예외입니다.

여기서 중요한 단어는 "eligible"입니다.

sink가 family를 지원하지 않으면 skipped됩니다.
그 family를 처리할 수 있었던 sink가 모두 실패하면 dispatch가 raise합니다.

즉 `SinkDispatchError`는 이렇게 읽어야 합니다:

"capture는 storage/forwarding boundary까지 도달했지만, eligible한 어떤 경로도 그것을
보존하지 못했다."

이것은 적어도 일부 truth가 살아남는 degraded capture와 매우 다릅니다.

## 오류와 Degradation을 구분하는 유용한 Mental Model

다음 순서로 생각하면 도움이 됩니다:

### Capture가 시작되기 전

입력이나 context가 invalid하면:

- `ValidationError`
- `ContextError`
- `ClosedScopeError`

### Capture 도중, 일부 truth는 살아남을 수 있을 때

capture가 fidelity를 잃더라도 의미를 보존한다면:

- `CaptureResult.status == "degraded"`

### Eligible dispatch boundary에서 아무것도 살아남지 못할 때

eligible sink가 모두 실패하면:

- `SinkDispatchError`

이 세 갈래 구분은 현재 `Scribe` 설계에서 가장 깔끔한 부분 중 하나입니다.

## 뭔가 이상해 보일 때 먼저 무엇을 볼까

capture behavior를 디버깅할 때 가장 빠른 inspection 순서는 보통 다음과 같습니다:

1. 호출이 예외를 raise했는가
2. 아니라면 `CaptureResult.status`는 무엇인가
3. degraded라면 `degradation_reasons`는 무엇을 말하는가
4. `warnings`는 무엇을 말하는가
5. sink별 `deliveries`는 무엇을 보여주는가
6. degradation payload가 emit되었는가
7. `LocalJsonlSink`를 쓴다면 `degradations.jsonl`에 무엇이 나타나는가

이 순서가 중요한 이유는 다음 방향으로 이동하기 때문입니다:

- hard failure,
- partial survival,
- sink-specific explanation,
- persisted evidence.

## `deliveries`는 어떻게 읽어야 하는가

이 필드는 쉽게 지나치기 쉽지만, 디버깅에서 가장 유용한 표면인 경우가 많습니다.

delivery는 다음 중 하나일 수 있습니다:

- `success`
- `failure`
- `skipped`

즉 다음을 구분할 수 있습니다:

- payload를 저장한 sink,
- 예외를 던진 sink,
- 이 family에 대해 애초에 eligible하지 않았던 sink.

이것은 납작한 boolean result보다 훨씬 좋은 운영 설명입니다.

실무에서는 `degraded`를 봤을 때 진짜 원인이 `deliveries`에서 분명해지는 경우가 많습니다.

## Local JSONL에서는 무엇을 봐야 하는가

`LocalJsonlSink`를 쓸 때 reduced-fidelity behavior는 디스크 위에 눈에 보이는 흔적을
남기는 경우가 많습니다.

가장 중요한 파일은 다음입니다:

- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

예:

- degraded artifact registration은 `artifacts.jsonl`에 여전히 나타날 수 있고,
- degradation explanation은 `degradations.jsonl`에 나타날 수 있습니다.

local JSONL inspection이 유용한 큰 이유 중 하나가 바로 이것입니다. capture가 시도되었는지뿐
아니라 quality-loss evidence가 올바르게 보존되었는지도 직접 확인할 수 있기 때문입니다.

## 흔한 실패 스토리와 그 의미

### 이야기 1. "내 artifact call이 degraded를 반환했다"

가장 가능성 높은 해석:

- 파일이 없었고 `allow_missing=True`였다,
- hash 계산이 실패했다,
- 혹은 artifact payload가 만들어진 뒤 sink-side fidelity가 떨어졌다.

올바른 반응은 "artifact capture가 완전히 실패했네"가 아닙니다. "degradation reason과
binding state를 확인하자"입니다.

### 이야기 2. "내 capture call이 즉시 raise됐다"

가장 가능성 높은 해석:

- invalid input
- invalid context
- 혹은 eligible sink 전체 실패

올바른 다음 단계는 이것이 degradation issue라고 가정하기 전에, 어떤 예외 클래스가
raise됐는지부터 확인하는 것입니다.

### 이야기 3. "기대한 저장 경로에 아무것도 나타나지 않는다"

가장 가능성 높은 해석:

- sink가 설정되지 않았다,
- sink가 그 payload family를 지원하지 않았다,
- 혹은 sink dispatch failure가 발생했다.

그래서 storage debugging은 filesystem 확인만이 아니라 `deliveries` 확인부터 시작해야
합니다.

## 흔한 실수

### 1. `degraded`를 "무시해도 되는 결과"처럼 다루기

`Scribe`에서 degraded는 부분적인 운영 실패를 설명해 주는 정확한 정보 자체인 경우가
많습니다.

### 2. Top-Level Status만 보기

`deliveries`, `warnings`, `degradation_reasons`를 건너뛰면 진짜 원인을 놓치는 경우가
많습니다.

### 3. Invalid Usage와 Capture Degradation을 혼동하기

빈 artifact kind나 missing run context는 degraded capture path가 아닙니다. contract 또는
lifecycle error입니다.

### 4. Sink Failure는 항상 Total Failure라고 가정하기

다른 sink가 성공했다면, 올바른 해석은 total loss가 아니라 degradation인 경우가 많습니다.

### 5. 디스크 위의 Degradation Evidence를 확인하지 않기

local JSONL storage를 쓸 때 degradation-family 파일이 무슨 일이 일어났는지 가장 명확하게
설명해 주는 경우가 많습니다.

## 이 페이지에서 가져가야 할 핵심 직관

아주 짧게 정리하면:

- `Scribe`는 invalid usage, partial truth preservation, total eligible-sink failure를
  구분하고,
- `degraded`는 fidelity는 떨어졌지만 의미 있는 capture는 살아남았다는 뜻이며,
- 예외는 보통 invalid input/context 또는 total dispatch failure를 나타내고,
- `CaptureResult`는 단순한 success flag가 아니라 operational report이며,
- degradation은 first-class persisted evidence가 될 수 있습니다.

가장 중요한 한 문장은 이것입니다:

`Scribe`에서 reduced-fidelity capture는 complete failure와 뭉개 버릴 것이 아니라, 확인하고
보존해야 할 대상입니다.

## 다음에 읽을 문서

이 페이지가 이해됐다면, 다음 문서들이 보통 가장 유용합니다:

1. [싱크와 저장소](C:/Users/eastl/MLObservability/Scribe/docs/ko/sinks-and-storage.md):
   degraded evidence와 delivery가 어디서 오는지 알고 싶을 때
2. [아티팩트](C:/Users/eastl/MLObservability/Scribe/docs/ko/artifacts.md):
   degraded capture가 실제로 가장 자주 나오는 practical source를 보고 싶을 때
3. [API 레퍼런스](C:/Users/eastl/MLObservability/Scribe/docs/ko/api-reference.md):
   result model과 exception type을 compact하게 lookup하고 싶을 때

## 관련 파일

- Exceptions: [src/scribe/exceptions.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/exceptions.py)
- Result models: [src/scribe/results/models.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/results/models.py)
- Dispatch logic: [src/scribe/runtime/dispatch.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/dispatch.py)
- Artifact service: [src/scribe/artifacts/service.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/artifacts/service.py)
- Runtime session: [src/scribe/runtime/session.py](C:/Users/eastl/MLObservability/Scribe/src/scribe/runtime/session.py)
