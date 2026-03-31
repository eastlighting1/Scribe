# 아티팩트

[사용자 가이드 홈](../USER_GUIDE.ko.md)

팀이 처음 `Scribe`를 instrumentation할 때는 보통 event와 metric부터 시작합니다. 하지만
금방 또 다른 질문이 생깁니다:

"워크플로가 실행되는 동안 관찰한 사실만이 아니라, 실제로 만들어낸 output은 어떻게
캡처하지?"

이 페이지는 그 질문에 답하기 위해 존재합니다.

`Scribe`에서 artifact capture는 곁다리 기능이나 단순한 file-path helper로 취급되지
않습니다. output이 어디에 있는지만이 아니라, 그것이 어떤 종류의 output인지, 어떤
verification policy가 적용되었는지, binding이 얼마나 완전했는지, 그 output이 어떤
execution context에 속하는지까지 기록하는 구조화된 binding flow입니다.

이 페이지의 목표는 다음과 같습니다:

1. 왜 artifact capture가 `Scribe` 안에서 별도의 패턴인지 설명하기,
2. `register_artifact(...)` 동안 무슨 일이 일어나는지 보여주기,
3. successful artifact binding과 degraded artifact binding의 차이를 설명하기,
4. event에 path만 기록하는 대신 언제 artifact capture를 써야 하는지 판단하게 돕기.

이 페이지를 읽고 나면 artifact registration을 `Path`에 얇게 덧씌운 편의 wrapper가
아니라 구조화된 capture flow로 이해할 수 있어야 합니다.

## 왜 Artifact는 별도의 Capture Shape인가

처음 보면 artifact는 다음 어떤 방식으로든 표현할 수 있을 것처럼 보입니다:

- file path를 담은 message가 있는 event,
- output file을 가리키는 metric tag,
- observability capture 바깥 어딘가에 따로 저장된 plain file path,
- 전용 artifact registration 호출.

`Scribe`는 의도적으로 네 번째를 선택합니다.

그 선택이 중요한 이유는 checkpoint, evaluation report, exported dataset 같은 durable
output이 단순한 runtime occurrence가 아니기 때문입니다. 실행이 끝난 뒤에도 남아 있고,
나중에 설명되어야 하는 result입니다.

실제 워크플로에서는 금방 이런 질문이 생깁니다:

- 어느 run이 이 checkpoint를 만들었는가,
- 어느 stage가 이 evaluation report를 만들었는가,
- registration 시점에 파일이 실제로 존재했는가,
- hash는 계산되었는가,
- artifact는 완전히 bound되었는가 아니면 일부만 알려져 있었는가,
- 파일이 없을 때 hard fail해야 하는가 아니면 degraded evidence로 남겨야 하는가.

단순한 path string 하나로는 이런 질문에 잘 답할 수 없습니다. `Scribe`의 artifact
capture는 이런 질문이 끝까지 답 가능하도록 존재합니다.

## 핵심 아이디어: Logging이 아니라 Binding

가장 중요한 점은 `Scribe`가 artifact registration을 "파일 위치를 payload에 적기"로
보지 않는다는 것입니다. 이것은 다음 사이의 binding operation입니다:

- artifact identity,
- source location,
- verification policy,
- canonical artifact manifest,
- active execution context.

그래서 public method가 다음과 같습니다:

```python
run.register_artifact(...)
```

다음 같은 이름이 아닌 이유도 여기에 있습니다:

```python
run.log_file(...)
```

핵심은 단순히 어떤 파일이 존재했다는 사실을 기억하는 것이 아닙니다. output에 대해
구조화된 claim을 남기고, registration 시점에 그 output이 얼마나 강하게 binding되었는지
함께 캡처하는 것입니다.

## Public Artifact Capture Flow

top-level에서 artifact capture는 이렇게 보입니다:

```python
from pathlib import Path

stage.register_artifact(
    "checkpoint",
    Path("./artifacts/model.ckpt"),
    compute_hash=True,
)
```

이것은 가장 단순한 public form일 뿐이고, 내부에서는 여러 단계가 일어납니다:

1. active run context가 필요하고,
2. source path가 normalize되며,
3. source existence를 확인하고,
4. verification policy를 만들고,
5. artifact registration request를 만들고,
6. `ArtifactManifest`를 만들고,
7. `ArtifactBinding`을 조립하고,
8. artifact-family payload를 sink로 dispatch하고,
9. fidelity가 떨어졌다면 degradation-family payload도 emit될 수 있습니다.

즉 artifact registration은 `Scribe`에서 가장 풍부한 capture flow 중 하나입니다. output
identity와 capture-quality semantics를 모두 함께 운반합니다.

## Artifact Capture 뒤의 주요 모델

artifact model은
[artifacts/models.py](../../src/scribe/artifacts/models.py)에
있습니다.

가장 중요한 것은 다음입니다:

- `ArtifactSource`
- `ArtifactVerificationPolicy`
- `ArtifactRegistrationRequest`
- `ArtifactBinding`

그리고 canonical manifest는 `Spine`과 정렬된 payload construction을 통해 만들어집니다.

이 역할을 가장 쉽게 생각하는 방법은 다음과 같습니다:

- `ArtifactSource`: 현재 bytes가 어디서 오는가
- `ArtifactVerificationPolicy`: 어떤 verification이 기대되는가
- `ArtifactRegistrationRequest`: caller가 무엇을 bind해 달라고 요청했는가
- `ArtifactBinding`: 실제 operational artifact-capture payload
- `ArtifactManifest`: binding 내부에 붙는 canonical output description

즉 `Scribe`의 artifact capture는 하나의 평평한 object가 아닙니다. request, source,
canonical output, resulting binding state가 층을 이루는 표현입니다.

## `ArtifactSource`

`ArtifactSource`는 artifact bytes가 현재 어디서 오는지를 표현합니다.

현재 `Scribe` 사용에서 가장 주된 source kind는 path-based registration입니다.

중요한 source field는 다음과 같습니다:

- `kind`
- `uri`
- `exists`

이 덕분에 `Scribe`는 다음을 구분할 수 있습니다:

- 이미 존재하는 path를 가리키는 artifact,
- 나중에 존재할 것으로 기대되는 path를 가리키는 artifact,
- 개념적으로 staged path나 URI 같은 다른 source form.

중요한 점은 source location이 사람이 읽는 message 안에 묻혀 있는 것이 아니라
명시적이고 검사 가능하다는 것입니다.

## `ArtifactVerificationPolicy`

이 artifact system에서 더 중요한 아이디어 중 하나는 verification expectation이 request의
일부라는 점입니다.

현재 핵심 field:

- `compute_hash`
- `require_existing_source`

이것이 중요한 이유는 caller가 무엇을 요구했는지에 따라 운영 동작이 달라지기 때문입니다.

예:

- 어떤 워크플로는 강한 verification을 원하고 파일이 없으면 즉시 실패해야 하며,
- 어떤 워크플로는 파일이 생기기 전에 logical artifact를 알고 있어 degraded binding을
  원할 수 있고,
- 어떤 워크플로는 속도나 비용 때문에 hashing을 건너뛰고 싶어할 수 있습니다.

명시적인 verification policy가 없다면 이런 차이는 임시 호출 관례 안에 숨어버립니다.
`Scribe`는 이것을 구조화된 capture contract의 일부로 만듭니다.

## `ArtifactRegistrationRequest`

이 model은 사용자가 `Scribe`에게 무엇을 bind해 달라고 요청했는지를 나타냅니다.

중요한 field는 다음을 포함합니다:

- `artifact_ref`
- `artifact_kind`
- `source`
- `verification_policy`
- `attributes`

이 request object가 중요한 이유는 caller intent를 final binding outcome과 분리해서
보존하기 때문입니다.

이 구분은 운영적으로 유용합니다. request는 이렇게 말합니다:

- caller가 어떤 artifact kind를 의도했는지,
- 어떤 source를 가리켰는지,
- verification이 얼마나 엄격해야 했는지,
- 어떤 추가 metadata를 넣었는지.

반면 final binding은 런타임 조건 안에서 그 request가 실제로 어떻게 끝났는지를
말해줍니다.

## `ArtifactBinding`

`ArtifactBinding`은 `Scribe` artifact capture의 중심 output입니다.

이것은 다음을 포함합니다:

- 원래 request,
- canonical manifest,
- source,
- project와 operation context field,
- binding status,
- completeness와 degradation marker,
- artifact-level attribute.

그래서 `Scribe`의 artifact capture는 binding process로 이해하는 것이 가장 좋습니다.
최종 payload는 다음 둘 다를 보존합니다:

- 무엇을 bind하려 했는가,
- 그 binding이 얼마나 완전했고 혹은 degraded했는가.

### Binding Status

현재 binding status는 다음을 포함합니다:

- `BOUND`
- `PENDING`
- `DEGRADED`

현재 구현에서 가장 자주 보게 되는 status는 다음과 같습니다:

- artifact가 깨끗하게 캡처됐을 때 `BOUND`,
- registration 시점에 path가 없었던 것처럼 fidelity가 떨어졌을 때 `DEGRADED`.

워크플로가 모든 binding state를 아직 다 쓰지 않더라도, model이 단순한 success/failure
boolean보다 더 풍부한 것은 artifact capture가 종종 partially-known state에 있기 때문입니다.

## `ArtifactManifest`

binding은 canonical contract layer에서 오는 `ArtifactManifest`를 함께 들고 있습니다.

실무적으로 이 manifest는 active execution context 안에서 artifact에 구조화된 identity를
부여합니다.

중요한 field는 다음을 포함합니다:

- artifact ref
- artifact kind
- created time
- producer ref
- run ref
- 있을 경우 stage execution ref
- location ref
- hash value
- size bytes
- attributes

즉 `Scribe`에서 artifact는 단순한 "디스크 위의 path"가 아닙니다. 등록된 run과 stage에
연결된 canonical output object입니다.

## 단순한 Successful Artifact Binding

가장 곧은 artifact path는 파일이 이미 존재하는 경우입니다.

```python
from pathlib import Path

with scribe.run("training") as run:
    result = run.register_artifact(
        "checkpoint",
        Path("./artifacts/model.ckpt"),
        compute_hash=True,
    )
```

파일이 존재하고 hashing도 성공하면, 보통 결과는 다음과 같습니다:

- `CaptureResult.status == "success"`
- `ArtifactBinding.binding_status == "bound"`
- `hash_value`가 존재함
- `size_bytes`가 존재함

이것이 가장 깨끗한 artifact path입니다. logical artifact, source file, canonical manifest가
손실 없이 정렬되기 때문입니다.

## 왜 `artifact_kind`가 중요한가

`artifact_kind`는 artifact capture에서 가장 중요한 입력 중 하나입니다.

예:

- `checkpoint`
- `evaluation-report`
- `dataset`
- `feature-snapshot`

이 값은 단순한 label 이상입니다. artifact가 어떤 종류의 output인지를 말하는 가장
주된 선언입니다.

실무에서는 이 vocabulary를 안정적이고 비교적 작게 유지하는 것이 보통 가장 좋습니다.
같은 종류의 output을 `checkpoint`, `model_checkpoint`, `ckpt`, `trained-model`처럼 한
시스템 안에서 제각각 부르면, consumer는 훨씬 지저분한 방식으로 shared meaning을
다시 조립해야 합니다.

건강한 패턴은 이렇습니다:

- `artifact_kind`는 좁고 안정적으로 유지하고,
- 더 세밀한 차이는 attribute에 넣고,
- 정말 다른 종류의 output일 때만 새로운 kind를 도입하기.

## 언제 `attributes`를 쓸까

artifact attribute는 유용하지만 core binding shape에는 속하지 않는 metadata를 담는
올바른 자리입니다.

예:

- framework
- dtype
- split
- export format
- 내부 output category

즉 attributes는 output-local detail에 적합하고, top-level artifact field는 모두에게
중요한 구조를 유지하는 데 집중해야 합니다.

다르게 말하면:

- top-level field는 모든 consumer가 알아야 할 것에 답하고,
- attribute는 일부 consumer가 나중에 보고 싶어 할 것에 답합니다.

## `compute_hash=True`

hashing은 artifact registration에서 가장 큰 verification decision 중 하나입니다.

`compute_hash=True`일 때:

- `Scribe`는 file hash를 계산하려 시도하고,
- 성공한 hash는 manifest의 일부가 되며,
- artifact는 나중에 비교와 검증이 훨씬 쉬워집니다.

이것이 유용한 이유는 file path만으로는 강한 identity가 아니기 때문입니다. 같은 path가
시간에 따라 다른 bytes를 가리킬 수 있고, 다른 path가 같은 content를 가리킬 수도
있습니다.

hashing은 다음 질문에 답하는 데 도움을 줍니다:

- 이것이 정말 예전과 같은 checkpoint인가,
- path는 같아도 output 내용은 바뀌었는가,
- storage 이동을 거친 뒤에도 이 artifact를 비교할 수 있는가.

### Hashing이 Degraded가 될 수 있는 경우

파일은 존재하지만 `OSError` 때문에 hashing이 실패하면, `Scribe`는 artifact가 완전히
bound되었다고 가장하지 않습니다. 대신 degradation reason과 warning을 기록합니다.

이것도 artifact flow가 단순한 편의 wrapper보다 풍부하다는 좋은 예입니다. output
integrity는 capture quality의 실제 일부로 취급됩니다.

## `allow_missing=True`

이 옵션은 artifact API에서 실무적으로 가장 중요한 부분 중 하나입니다.

예:

```python
from pathlib import Path

with scribe.run("training") as run:
    result = run.register_artifact(
        "checkpoint",
        Path("./artifacts/model.ckpt"),
        allow_missing=True,
    )
```

파일이 없고 `allow_missing=False`면 registration은 `ValidationError`로 실패합니다.

파일이 없지만 `allow_missing=True`면 `Scribe`는 여전히 다음을 할 수 있습니다:

- request를 만들고,
- manifest를 만들고,
- artifact binding을 emit하고,
- binding을 degraded로 표시하고,
- degradation evidence를 emit합니다.

이것은 output이 완전히 써지기 전에 logical artifact가 이미 알려져 있는 실제 워크플로에서
매우 유용합니다.

예:

- training worker가 파일을 flush하기 전에 checkpoint path가 먼저 정해질 수 있고,
- generation이 끝나기 전에 report path를 예약할 수 있으며,
- downstream stage가 file body가 늦더라도 expected output identity를 보존하고 싶을 수 있습니다.

즉 `allow_missing=True`는 sloppy한 지름길이 아닙니다. partial truth를 버리지 않고
보존하려는 의도적인 선택입니다.

## Degraded Artifact Binding은 무엇을 의미하는가

artifact capture는 `degraded` status가 가장 직관적으로 이해되는 자리 중 하나입니다.

caller가 다음을 안다고 가정해 봅시다:

- artifact kind가 무엇인지,
- 어떤 path가 그것을 담아야 하는지,
- 어떤 execution context에 속하는지.

하지만 파일은 아직 존재하지 않습니다.

이것은 "아무것도 알려진 게 없다"와는 다릅니다. 여전히 의미 있는 truth의 일부가
존재합니다. `Scribe`는 다음을 기록함으로써 그것을 보존합니다:

- artifact request intent,
- 목표로 했던 path,
- 그 path가 아직 존재하지 않는다는 사실,
- degraded binding status,
- degradation reason과 warning.

즉 degraded artifact capture는 이렇게 읽어야 합니다:

"output은 알려져 있었고 등록되었지만, binding fidelity는 부분적이었다."

이것은 다음 두 극단보다 훨씬 더 많은 정보를 줍니다:

- artifact가 완전히 존재한 척하기,
- artifact capture를 통째로 버리기.

## Artifact Capture와 Degradation Evidence

artifact registration이 degraded가 되면, `Scribe`는 degradation-family payload도 emit할
수 있습니다.

이것이 중요한 이유는 reduced-fidelity condition이 반환된 `CaptureResult` 안에만 머물지
않고, persisted observability truth의 일부가 될 수 있기 때문입니다.

실제 local-first 관점에서 보면 이는 보통 다음을 뜻합니다:

- artifact binding은 `artifacts.jsonl`에 나타나고,
- degradation evidence는 `degradations.jsonl`에 나타난다.

실제 워크플로를 디버깅할 때 이것은 매우 유용합니다. artifact가 등록되었다는 사실뿐
아니라, 왜 clean binding이 아니었는지까지 직접 볼 수 있기 때문입니다.

## Scope와 Artifact 의미

다른 `Scribe` capture pattern과 마찬가지로, artifact registration도 scope에 따라
의미가 달라집니다.

### Run-level artifact

artifact가 whole-run output이나 run-level result를 나타낼 때 사용합니다.

예:

- final summary report
- run-level packaged export

### Stage-level artifact

artifact가 큰 phase에 분명하게 속할 때 사용합니다.

예:

- training checkpoint
- evaluation report
- prepared dataset snapshot

### Operation-level artifact

artifact가 더 세밀한 work unit에 속하고, 나중에도 그 구분이 필요할 때 사용합니다.

예:

- request-level debug bundle
- one-step intermediate output

실무에서는 stage-level artifact capture가 가장 흔한 운영 패턴입니다. 많은 ML workflow가
artifact를 train이나 evaluate 같은 phase의 output으로 자연스럽게 보기 때문입니다.

## Event Capture와 비교한 Artifact Capture

이 차이는 매우 중요합니다.

다음 같은 event는:

```python
run.event(
    "checkpoint.saved",
    message="checkpoint saved to ./artifacts/model.ckpt",
)
```

유용할 수는 있지만, artifact registration의 대체물이 아닙니다.

event는 어떤 occurrence가 있었음을 말합니다.
artifact binding은 다음을 말해줍니다:

- artifact가 무엇인지,
- 어떤 source를 가리키는지,
- 어떤 verification policy가 적용되었는지,
- binding status가 무엇이었는지,
- 어떤 canonical manifest가 구성되었는지,
- 어떤 run이나 stage에 속하는지.

즉 event와 artifact는 함께 쓰일 때가 많지만, 역할이 다릅니다.

event가 답하는 질문:

"어떤 일이 일어났는가?"

artifact가 답하는 질문:

"어떤 output object가 binding되었고, 얼마나 완전했는가?"

## 현실적인 Artifact Flow

[artifact_binding_workflow.py](../../examples/artifact_binding_workflow.py)
예제는 좋은 현실적 패턴을 보여줍니다.

이 run은:

- reproducibility metadata를 들고,
- `allow_missing=True`로 artifact를 등록하고,
- 그 다음 artifact binding result를 설명하는 event를 emit합니다.

실무에서는 이것이 매우 건강한 패턴입니다:

1. output을 구조적으로 등록하고,
2. 결과를 확인하고,
3. 선택적으로 무슨 일이 있었는지 사람이 읽을 수 있는 event를 emit하기.

이렇게 하면 artifact 자체는 구조적으로 유지하면서도, 운영 outcome은 event stream에서
읽기 쉽게 만들 수 있습니다.

## Artifact Capture와 Reproducibility Context

`Scribe`에서 artifact registration의 중요한 강점 중 하나는 active run context가
artifact manifest 안으로 흘러들어간다는 점입니다.

즉 다음 값들이:

- `code_revision`
- `config_snapshot`
- `dataset_ref`

output에 붙는 reproducibility extension의 일부가 될 수 있습니다.

이것이 중요한 이유는 output이 나중에 팀이 가장 많이 설명해야 하는 대상인 경우가
많기 때문입니다:

- 어떤 code revision이 이 report를 만들었는가,
- 어떤 dataset이 활성화된 상태에서 이 checkpoint가 등록되었는가,
- 어떤 configuration snapshot이 이 output에 속하는가.

artifact capture는 execution과 output의 연결을 보존하기에 가장 자연스러운 자리 중
하나입니다.

## Artifact Capture가 맞는 경우

artifact capture는 다음 경우에 맞습니다:

- 캡처하려는 것이 durable output이거나 expected output일 때,
- execution context가 그 output에 계속 붙어 있어야 할 때,
- file integrity나 source existence가 중요할 때,
- degraded output binding도 여전히 보존할 가치가 있을 때,
- 나중의 consumer가 그 output을 독립된 entity로 비교, 검사, 라우팅해야 할 수 있을 때.

좋은 예:

- checkpoint
- model package
- evaluation report
- feature snapshot
- exported dataset
- generated manifest

## Artifact Capture가 맞지 않는 경우

artifact capture는 보통 다음 경우에는 맞지 않습니다:

- 그 fact가 일시적인 occurrence일 뿐 output object가 아닐 때,
- 보존할 만한 meaningful output identity가 없을 때,
- 그 정보가 실제로는 warning, note, numeric observation일 때.

예:

- "checkpoint save started"는 event가 더 낫고,
- "checkpoint write took 2.3s"는 metric이나 span이 더 낫고,
- "training loss is 0.42"는 metric이 더 낫습니다.

## 흔한 Artifact 실수

### 1. Artifact Registration을 단순한 Path Logging처럼 다루기

이렇게 하면 binding status, verification policy, canonical manifest context의 핵심 의미를
놓치게 됩니다.

### 2. 모든 Missing Output에서 Hard Fail하기

때로는 이것이 맞지만, 많은 실제 워크플로에서는 degraded capture로 보존할 수 있었던
유용한 partial truth를 지워버립니다.

### 3. Event Message만으로 Artifact를 기록하기

이렇게 하면 output은 사람이 읽기에는 쉽지만, 나중에 구조적으로 해석하기는 훨씬
어려워집니다.

### 4. `artifact_kind`가 불필요하게 흔들리게 두기

kind vocabulary가 통제되지 않으면 consumer가 shared meaning을 수동으로 다시 복원해야
합니다.

### 5. 반환된 `CaptureResult`를 무시하기

artifact capture는 fire-and-forget helper보다 훨씬 풍부합니다. binding이 full이었는지,
degraded였는지, 실패했는지에 대한 가장 중요한 정보가 result 안에 있는 경우가 많습니다.

## 실전 의사결정 가이드

artifact에 대한 빠른 판단이 필요하다면 다음 질문을 해보면 됩니다:

### 1. 이 output은 실행이 끝난 뒤에도 중요할 정도로 durable한가

그렇다면 artifact capture를 고려할 가치가 있습니다.

### 2. 이 output에 execution context가 붙어 있어야 하는가

그렇다면 artifact capture가 보통 맞습니다.

### 3. missing-source behavior는 hard fail해야 하는가, 아니면 degraded truth로 남아야 하는가

이에 따라 `allow_missing`을 고르세요.

### 4. file body가 verification되어야 하는가, 아니면 reference만 있어도 되는가

이에 따라 `compute_hash`를 고르세요.

### 5. consumer가 안정적인 output category를 필요로 하는가

그렇다면 안정적인 `artifact_kind`를 정의하세요.

## 이 페이지에서 가져가야 할 핵심 직관

아주 짧게 정리하면:

- `Scribe`의 artifact capture는 path logging이 아니라 binding flow이고,
- registration request와 final binding outcome은 의도적으로 분리되어 있으며,
- degraded artifact capture도 종종 의미 있고 보존할 가치가 있으며,
- verification policy는 구조화된 artifact contract의 일부이고,
- artifact registration은 output을 execution context와 연결하는 올바른 자리입니다.

가장 중요한 한 문장은 이것입니다:

`Scribe`의 artifact는 plain file reference가 아니라, output과 그 binding quality에 대한
구조화된 claim으로 모델링됩니다.

## 다음에 읽을 문서

이 페이지가 이해됐다면, 다음 문서들이 보통 가장 유용합니다:

1. [Degradation과 오류](degradation-and-errors.md):
   degraded artifact capture를 더 운영적으로 이해하고 싶을 때
2. [싱크와 저장소](sinks-and-storage.md):
   artifact binding과 degradation evidence가 어디에 저장되는지 보고 싶을 때
3. [예제](examples.md):
   전체 워크플로 안에서 artifact registration을 보고 싶을 때

## 관련 파일

- Artifact models: [src/scribe/artifacts/models.py](../../src/scribe/artifacts/models.py)
- Artifact registration service: [src/scribe/artifacts/service.py](../../src/scribe/artifacts/service.py)
- Artifact binding example: [examples/artifact_binding_workflow.py](../../examples/artifact_binding_workflow.py)
- Artifact-related tests: [tests/test_scribe_mvp.py](C:/Users/eastl/MLObservability/Scribe/tests/test_scribe_mvp.py)
