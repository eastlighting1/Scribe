# 예제

[사용자 가이드 홈](../USER_GUIDE.ko.md)

`Scribe`를 가장 빨리 이해하는 방법 중 하나는 몇 개의 작은 워크플로가 scope,
capture primitive, artifact registration, local storage를 함께 어떻게 조립하는지
보는 것입니다. 이 페이지는 저장소에 포함된 example 파일을 설명하고, 더 중요한 것은
그 파일을 어떻게 읽어야 하는지 설명합니다.

이 페이지의 목적은 단순히 파일 목록을 나열하는 것이 아닙니다. 다음 질문에 답하도록
돕는 것입니다:

- 어떤 예제를 먼저 읽어야 하는가,
- 각 예제에서 무엇을 눈여겨봐야 하는가,
- 이 예제들이 다른 문서와 어떻게 연결되는가,
- 각 예제가 어떤 종류의 실제 워크플로를 나타내려는가.

이미 `시작하기`를 읽었다면, 이 페이지는 작은 도입용 snippet과 더 현실적인 코드
조립 감각 사이를 이어주는 다리 역할을 합니다.

## 왜 예제가 중요한가

대부분의 문서는 `Scribe`를 개념별 혹은 집중된 단위로 설명합니다:

- scope가 어떻게 동작하는지,
- event와 metric을 언제 써야 하는지,
- sink가 어떻게 동작하는지,
- artifact가 어떻게 degrade되는지.

예제는 그 아이디어가 한 흐름 안에 함께 등장하는 자리입니다.

이것이 중요한 이유는 실제 사용에서는:

- metric만 단독으로 캡처하지 않고,
- artifact만 단독으로 등록하지 않으며,
- 하나의 고립된 scope만 들어가지 않기 때문입니다.

실제 코드는 보통 하나의 실행 안에서 이런 일을 여러 개 함께 합니다. 예제는 처음부터
큰 코드베이스에 들어가지 않고도 그 결합된 흐름이 어떤 느낌인지 보여주기 위해
존재합니다.

## 포함된 워크플로

현재 저장소에는 다음 example 파일이 포함되어 있습니다:

- [Training workflow](../../examples/training_workflow.py)
- [Evaluation workflow](../../examples/evaluation_workflow.py)
- [Artifact binding workflow](../../examples/artifact_binding_workflow.py)

이 예제들은 의도적으로 작게 유지되어 있습니다. 목적은 완전한 production system을
흉내 내는 것이 아니라, 핵심 instrumentation pattern을 쉽게 보이게 만드는 데 있습니다.

## 권장 읽기 순서

가장 유용한 읽기 순서는 다음과 같습니다:

1. [Training workflow](../../examples/training_workflow.py)
2. [Evaluation workflow](../../examples/evaluation_workflow.py)
3. [Artifact binding workflow](../../examples/artifact_binding_workflow.py)

이 순서는 임의가 아닙니다.

가장 넓고 대표적인 end-to-end 흐름에서 시작해, 좀 더 특정한 evaluation 형태로
옮겨가고, 마지막에는 `Scribe`의 가장 특징적인 아이디어 중 하나인 imperfect
condition 아래의 artifact binding을 따로 떼어 보여줍니다.

## 예제 1: Training Workflow

파일:

- [examples/training_workflow.py](../../examples/training_workflow.py)

이 예제는 한 곳에서 가장 완전한 정상 `Scribe` 사용 단면을 보여주기 때문에 첫 예제로
가장 좋습니다.

### 무엇을 보여주는가

이 예제는 다음을 보여줍니다:

- `LocalJsonlSink`를 사용하는 `Scribe` 세션 생성
- run 열기
- 여러 stage scope 진입
- 세밀한 작업을 위한 operation scope 사용
- dataset level과 step level에서 metric emit
- batch event emit
- operation 내부에서 span emit
- artifact 등록

즉 대부분의 사용자가 결국 필요로 하게 되는 정상적인 "context -> observation ->
output" 흐름을 보여줍니다.

### 왜 이 예제가 첫 번째인가

이 파일이 첫 예제로 좋은 이유는 지나치게 많은 edge case에 들어가지 않으면서도 여러
capture type이 함께 공존하는 모습을 볼 수 있게 해주기 때문입니다.

이 예제는 다음을 줍니다:

- 하나의 run-level note event,
- 하나의 preparation stage와 dataset-scale metric,
- 하나의 training stage와 step-level metric, span,
- 하나의 artifact registration,
- 지속적인 확인을 위한 local sink 하나.

즉 가장 흔한 첫 production 질문을 그대로 비춥니다:

"복잡한 backend 없이 training-like workflow에 `Scribe`를 어떻게 붙이지?"

### 읽으면서 무엇을 볼 것인가

눈여겨볼 만한 중요한 패턴이 몇 가지 있습니다.

#### 1. sink는 한 번만 설정된다

세션은 맨 위에서 한 번만 만들어지고, 이후의 모든 capture action은 그 설정을 재사용합니다.

이것이 애플리케이션 코드에서 `Scribe`가 의도하는 느낌입니다. 세션 하나를 만들고,
그 다음에는 active scope가 runtime context를 운반하게 둡니다.

#### 2. stage마다 다른 capture style을 쓴다

`prepare-data` stage는 dataset scale의 batch metric을 emit합니다.
`train` stage는 다음을 emit합니다:

- operation 내부의 per-step metric,
- model-forward 작업을 위한 span,
- batched epoch event,
- 그리고 output artifact.

이것은 `Scribe`의 중요한 아이디어를 보여줍니다. 적절한 capture shape는 runtime fact에
따라 달라지지, 항상 같은 primitive만 쓰는 습관으로 결정되지 않습니다.

#### 3. operation scope는 의미가 생길 때만 사용된다

이 예제는 모든 줄을 `operation`으로 감싸지 않습니다.

이것은 건강한 패턴입니다.

operation scope는 보통 work unit 자체가 나중에 중요할 때 가장 유용합니다. 예를 들면:

- training step,
- batch,
- request,
- tool call.

training example은 정말 도움이 되는 곳에만 이 레벨을 사용합니다.

#### 4. artifact registration이 같은 워크플로의 일부다

checkpoint registration은 metric과 event와 같은 흐름 안에서 캡처됩니다. 이것은
`Scribe`의 가장 강한 설계 선택 중 하나를 반영합니다. output도 runtime fact와 같은
observability truth model 안에 속한다는 것입니다.

### 실행 후 이 예제를 어떻게 해석할까

`LocalJsonlSink`와 함께 실행하면, 로컬 `.scribe` 디렉터리에는 다음이 보여야 합니다:

- `Project`, `Run`, `StageExecution` 같은 context payload
- lifecycle event, training event, metric, span 같은 record payload
- checkpoint용 artifact payload
- 예제가 `allow_missing=True`를 쓰기 때문에 경우에 따라 degradation evidence

마지막 포인트가 중요합니다. 이 예제는 happy path만 보여주지 않습니다. output
materialization이 부분적일 때도 artifact capture가 어떻게 유용하게 남는지 보여줍니다.

### 이 예제가 강화해 주는 문서

training example은 특히 다음 문서와 강하게 연결됩니다:

- [시작하기](getting-started.md)
- [핵심 개념](core-concepts.md)
- [캡처 패턴](capture-patterns.md)
- [아티팩트](artifacts.md)

## 예제 2: Evaluation Workflow

파일:

- [examples/evaluation_workflow.py](../../examples/evaluation_workflow.py)

이 예제는 training workflow보다 더 좁은 범위를 다루며, 바로 그 점 때문에 유용합니다.

이 예제는 워크플로가 다음을 중심으로 조직될 때 `Scribe`가 어떤 모습인지 보여줍니다:

- 기존 artifact 로드,
- dataset against evaluation,
- aggregate metric 기록,
- evaluation result artifact emit.

### 무엇을 보여주는가

이 예제는 다음을 보여줍니다:

- evaluation 전에 stage-level artifact registration
- evaluation metric에 대한 batch metric capture
- `BatchCaptureResult`를 바탕으로 한 event emit
- evaluation report를 위한 output artifact registration

즉 촘촘한 operation-level training flow보다 stage-shaped pipeline work를 강조합니다.

### 왜 이 예제가 중요한가

많은 팀은 촘촘한 request-level tracing보다 evaluation이나 reporting flow가 더 명확합니다.

이 예제는 `Scribe`가 step-heavy training semantics가 없어도 유용하다는 점을 보여줍니다.
다음과 같은 워크플로에도 자연스럽게 맞습니다:

- 중요한 measurement가 dataset aggregate일 때,
- 핵심 output이 report일 때,
- 운영 구조가 request-oriented보다 phase-oriented일 때.

### 읽으면서 무엇을 볼 것인가

#### 1. main evaluation stage 전에 artifact registration이 일어날 수 있다

`load-checkpoint` stage는 evaluation metric이 캡처되기 전에 checkpoint artifact를
등록합니다.

이것은 중요한 아이디어를 강화합니다:

`Scribe`에서 artifact capture는 새로 생성된 output만을 다루는 것이 아닙니다. 현재
워크플로가 소비하거나 binding하는 중요한 output object도 설명할 수 있습니다.

#### 2. 여기서는 batch metric이 자연스럽다

evaluation metric은 하나의 grouped action으로 함께 emit됩니다:

- accuracy
- loss

이것은 `emit_metrics(...)`가 여러 개의 고립된 호출보다 더 낫다는 좋은 예입니다.
워크플로 자체가 evaluation result를 하나의 grouped observation set로 생각하기 때문입니다.

#### 3. event는 batch result를 사람이 읽을 수 있게 설명한다

metric emit 후 이 예제는 다음을 emit합니다:

- batch status를 message 안에 담은 event 하나.

이것은 아주 건강한 패턴입니다. 다음 역할 분담을 지켜줍니다:

- 값은 metric으로,
- phase outcome의 사람이 읽는 해석은 event로.

### 이 예제가 Training Example과 다른 점

training example과 비교하면, 이 예제는:

- operation-level scope를 덜 사용하고,
- step-level metric보다 dataset-level metric을 강조하며,
- artifact handling을 phase transition의 일부로 다루고,
- stage가 grouped metric capture를 어떻게 요약하는지 보여줍니다.

그래서 특히 다음을 instrumentation하려는 팀에 유용합니다:

- batch evaluation pipeline,
- report-generation workflow,
- offline validation 혹은 scoring job.

### 이 예제가 강화해 주는 문서

이 예제는 특히 다음 문서와 강하게 연결됩니다:

- [캡처 패턴](capture-patterns.md)
- [아티팩트](artifacts.md)
- [Degradation과 오류](degradation-and-errors.md)

## 예제 3: Artifact Binding Workflow

파일:

- [examples/artifact_binding_workflow.py](../../examples/artifact_binding_workflow.py)

이 예제는 집합 안에서 가장 특화된 예제이고, 그럴 만한 이유가 있습니다. artifact
binding은 `Scribe`에서 가장 특징적인 부분 중 하나이며, 따로 떼어서 보여줄 가치가
있습니다.

### 무엇을 보여주는가

이 예제는 다음을 보여줍니다:

- run-level reproducibility metadata
- `compute_hash=True`와 함께하는 artifact registration
- `allow_missing=True`와 함께하는 artifact registration
- binding result를 명시적으로 보고하는 event capture

이 파일은 작지만 개념적으로는 밀도가 높습니다.

### 왜 이 예제가 중요한가

많은 observability SDK는 event나 metric은 emit할 수 있습니다. 하지만 artifact
registration과 degraded binding을 runtime capture의 first-class 요소로 다루는 라이브러리는
훨씬 드뭅니다.

이 예제는 그 동작을 분리해서 보여주기 때문에, 독자는 다음 질문에 집중할 수 있습니다:

- 파일이 없으면 무슨 일이 일어나는가,
- 그럼에도 어떤 정보가 살아남는가,
- capture result는 어떻게 해석해야 하는가,
- artifact binding을 사람이 읽는 event와 어떻게 짝지을 수 있는가.

### 읽으면서 무엇을 볼 것인가

#### 1. reproducibility context는 run 생성 시 설정된다

이 예제는 다음을 전달합니다:

- `code_revision`
- `config_snapshot`
- `dataset_ref`

이것이 중요한 이유는 artifact capture가 나중에 이 run-level reproducibility field를
가장 가치 있게 만드는 자리 중 하나이기 때문입니다.

artifact는 단순한 report가 아니라, 특정 code revision, configuration snapshot,
dataset reference와 연결된 output이 됩니다.

#### 2. artifact 호출은 의도적으로 degrade될 수 있게 설계되어 있다

파일이 아직 없을 수 있지만, 예제는 여전히 artifact를 등록합니다.

이것은 sloppy instrumentation이 아닙니다. `Scribe`의 핵심 아이디어 중 하나를 의도적으로
보여주는 것입니다:

partial truth는 종종 버리지 말고 보존해야 합니다.

#### 3. event는 대체물이 아니라 해석 역할을 한다

artifact registration 후 이 예제는 다음을 요약하는 event를 emit합니다:

- artifact family,
- 결과가 degrade되었는지 여부.

이것은 매우 강한 패턴입니다. 왜냐하면 다음 두 가지를:

- 구조화된 artifact binding,
- 사람이 읽는 운영 메모,

서로 보완적인 별도 record로 유지하기 때문입니다.

### 이 예제가 강화해 주는 문서

이 예제는 특히 다음 문서와 강하게 연결됩니다:

- [아티팩트](artifacts.md)
- [Degradation과 오류](degradation-and-errors.md)
- [싱크와 저장소](sinks-and-storage.md)

## 예제를 잘 활용하는 법

이 example 파일을 사용하는 방식은 적어도 세 가지가 있습니다.

### 1. 실행하기 전에 먼저 읽기

assembly order와 capture shape를 먼저 이해하고 싶을 때 유용합니다.

읽으면서 다음을 물어보세요:

- run은 어디서 시작되는가,
- stage는 어디서 시작하고 끝나는가,
- 어떤 capture primitive가 왜 선택되었는가,
- 어떤 호출이 grouped result를 반환하는가,
- 어떤 output이 degrade될 것으로 예상되는가.

### 2. Local JSONL storage와 함께 실행하기

코드와 실제 emitted payload를 연결하고 싶을 때 유용합니다.

실행 후에는 다음을 확인해 보세요:

- `contexts.jsonl`
- `records.jsonl`
- `artifacts.jsonl`
- `degradations.jsonl`

이렇게 하면 예제가 훨씬 더 유익해집니다. instrumentation code뿐 아니라, 그 코드에서
실제로 만들어진 stored truth까지 함께 볼 수 있기 때문입니다.

### 3. 발판으로 사용하기

실무적으로는 이 방식이 가장 유용한 경우가 많습니다.

한 줄씩 복사하기보다 다음을 위한 template로 사용하세요:

- training instrumentation,
- evaluation job,
- output registration flow.

빈 파일에서 시작하는 것보다 이 편이 대개 더 낫습니다. 이미 건강한 `Scribe` 패턴이
반영되어 있기 때문입니다.

## 이 예제들이 의도적으로 다루지 않는 것

이 예제들은 의도적으로 작게 유지되기 때문에 모든 고급 경로를 한 번에 보여주지는
않습니다.

다음 모든 것을 한 번에 다루려고 하지는 않습니다:

- custom sink implementation
- complex multi-sink topology
- highly concurrent instrumentation
- large-scale lineage나 external backend integration

이런 생략은 의도적입니다. 예제의 목적은 먼저 핵심 assembly pattern을 가르치는 데
있기 때문입니다:

- context를 만들고,
- runtime fact를 캡처하고,
- output을 등록하고,
- 결과를 확인하는 것.

이 흐름이 명확해지면 더 고급 integration은 그 위에 훨씬 쉽게 쌓을 수 있습니다.

## 세 예제 사이에서 무엇을 비교할까

가장 많이 배우고 싶다면, 다음 축으로 서로 비교해 보면 좋습니다.

### Scope depth

- training: run -> stage -> operation
- evaluation: run -> stage
- artifact binding: mostly run-level

### 지배적인 capture type

- training: mixed metrics, spans, events, and artifacts
- evaluation: aggregate metrics plus artifacts
- artifact binding: artifact-centric with one explanatory event

### 전형적인 degradation path

- training: checkpoint가 아직 없으면 artifact가 degrade될 수 있음
- evaluation: checkpoint나 report artifact가 degrade될 수 있음
- artifact binding: degradation 자체가 main instructional focus

이 비교가 유용한 이유는, `Scribe`가 하나의 단일 workflow shape에 묶여 있지 않다는
점을 보게 해주기 때문입니다. 같은 core SDK가 시스템이 무엇을 표현해야 하느냐에 따라
여러 캡처 패턴을 지원할 수 있습니다.

## 새로운 사용자를 위한 좋은 진행 순서

실제 프로젝트에 `Scribe`를 도입한다면, 가장 건강한 진행 순서는 보통 이렇습니다:

1. training example을 읽고 실행해서 전체 형태를 이해한다.
2. evaluation example을 읽고 실행해서 stage-oriented aggregate flow를 본다.
3. artifact binding example을 읽고 실행해서 degraded output capture를 이해한다.
4. 그 다음 자기 코드로 돌아가, 자신의 워크플로와 맞는 부분만 흉내 낸다.

한 번에 모든 패턴을 가져오려 하는 것보다 이 편이 훨씬 낫습니다.

## 이 페이지에서 가져가야 할 핵심 직관

아주 짧게 정리하면:

- 예제는 의도적으로 작지만 구조적으로는 충분히 대표적이고,
- 각 예제는 서로를 복제하기보다 다른 강조점을 가르치며,
- 가장 좋은 활용법은 코드 형태, capture result, local sink output을 함께 보는 것이고,
- 이 예제들은 그대로 복사해야 할 스크립트가 아니라 instrumentation pattern의 template입니다.

가장 중요한 한 문장은 이것입니다:

이 예제 모음은 개별 메서드의 모양만 보여주기보다, 실제 코드 안에서 `Scribe`가 어떻게
capture flow를 조립하는지 가르치도록 설계되어 있습니다.

## 다음에 읽을 문서

이 페이지가 이해됐다면, 다음 문서들이 보통 가장 유용합니다:

1. [API 레퍼런스](api-reference.md):
   예제를 읽거나 수정할 때 곁에 둘 compact lookup이 필요할 때
2. [아티팩트](artifacts.md):
   artifact-centric example을 보고 새 질문이 생겼을 때
3. [싱크와 저장소](sinks-and-storage.md):
   예제 출력물을 더 깊게 확인하고 싶을 때

## 관련 파일

- Training example: [examples/training_workflow.py](../../examples/training_workflow.py)
- Evaluation example: [examples/evaluation_workflow.py](../../examples/evaluation_workflow.py)
- Artifact binding example: [examples/artifact_binding_workflow.py](../../examples/artifact_binding_workflow.py)
