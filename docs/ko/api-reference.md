# API 레퍼런스

[사용자 가이드 홈](../USER_GUIDE.ko.md)

이 페이지는 나머지 `Scribe` 가이드의 레퍼런스 companion입니다. 다른 페이지들은
instrumentation을 어떻게 생각해야 하는지, scope를 어떻게 설계해야 하는지, degraded
capture와 sink, artifact binding을 어떻게 이해해야 하는지를 설명합니다. 이 페이지는
이미 무엇을 하고 싶은지는 알고 있고, public API surface만 빠르게 확인하고 싶을 때를
위해 존재합니다.

실무에서는 보통 다음 다섯 질문 중 하나로 이어집니다. `import scribe`에서는 어떤 symbol이
노출되는가? `scribe.results`, `scribe.config` 같은 public submodule에서는 어떤 symbol이
노출되는가? `Scribe` session object에는 어떤 method가 있는가? scope object에는 어떤
method가 있는가? 어떤 result, sink, exception type이 public으로 간주되는가? 이
레퍼런스는 바로 그 질문들에 맞춰 구성되어 있습니다.

어떤 데이터가 event, metric, span, artifact 중 무엇으로 모델링되어야 할지 아직 고민
중이라면 먼저 [캡처 패턴](capture-patterns.md)
부터 읽는 편이 좋습니다. degraded outcome이나 dispatch failure를 이해하려는 중이라면
[Degradation과 오류](degradation-and-errors.md)
와 함께 이 페이지를 읽는 것이 가장 좋습니다.

## 패키지 진입점

top-level package export는
[src/scribe/__init__.py](../../src/scribe/__init__.py)에
모여 있습니다. public submodule export는
[src/scribe/config/__init__.py](../../src/scribe/config/__init__.py)
와
[src/scribe/results/__init__.py](../../src/scribe/results/__init__.py)
같은 모듈 단위 `__init__.py` 파일에 모여 있습니다. 이 파일들을 함께 보는 것이
라이브러리가 무엇을 supported import surface로 취급하는지 판단하는 가장 좋은 기준입니다.

대부분의 사용자는 아주 작은 import 집합으로 시작합니다:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe
```

batch capture가 필요할 때 흔히 여기에 이것이 추가됩니다:

```python
from scribe import EventEmission, MetricEmission, Scribe
```

configuration이 필요할 때는 top-level package가 아니라 configuration module에서 import하는
것이 맞습니다:

```python
from scribe import LocalJsonlSink, Scribe
from scribe.config import ScribeConfig
```

public surface는 자연스럽게 일곱 그룹으로 나뉩니다:

- `Scribe` session object,
- 그 session이 반환하는 lifecycle scope object,
- public submodule entry point,
- batch input model,
- result와 status model,
- artifact-related model,
- sink와 exception type.

### Public Import Path

의도적으로 지원되는 public import entry point는 다음과 같습니다:

- `scribe`
- `scribe.api`
- `scribe.config`
- `scribe.events`
- `scribe.metrics`
- `scribe.results`
- `scribe.artifacts`
- `scribe.sinks`

`src/scribe` 아래의 모든 internal package가 public API module은 아닙니다. 예를 들어
`runtime`, `context`, `traces`는 구현 패키지로 존재하지만, 현재는 `__init__.py`를
통해 문서화된 public symbol set을 재수출하지 않습니다.

## Session API

메인 SDK entry point는
[src/scribe/api/session.py](../../src/scribe/api/session.py)
에 있습니다. `Scribe`는 프로젝트나 프로세스 단위로 한 번 만들고, 그 위에서
run-scoped instrumentation을 여는 object입니다.

`Scribe`는 `from scribe import Scribe`와 `from scribe.api import Scribe` 두 방식 모두로
public import할 수 있습니다.

### `scribe.Scribe`

`Scribe(project_name, *, sinks=None, config=None)`

이것은 local-first observability capture를 위한 top-level session object입니다. runtime,
configured sink 집합, 그리고 프로세스나 workflow 전체에 적용되는 기본 capture
configuration을 소유합니다.

Parameters:

- `project_name`: 세션과 emitted payload에 붙는 논리적 project name
- `sinks`: sink instance의 optional sequence
- `config`: optional [`ScribeConfig`](../../src/scribe/config/models.py)

Typical usage:

```python
from pathlib import Path

from scribe import LocalJsonlSink, Scribe

scribe = Scribe(
    project_name="nova-vision",
    sinks=[LocalJsonlSink(Path("./.scribe"))],
)
```

중요한 점은 `Scribe`를 생성한다고 해서 run이 바로 시작되지는 않는다는 것입니다.
여기서는 instrumentation session만 만들어지고, run은 `scribe.run(...)`을 호출할 때
비로소 시작됩니다.

### `scribe.Scribe.project_name`

`Scribe.project_name`

이 property는 세션에 설정된 project name을 반환합니다. 주로 inspection, 테스트, 혹은
runtime이 emitted payload에 어떤 project identity를 붙이고 있는지 확인하고 싶을 때
유용합니다.

Returns:

- `str`

### `scribe.Scribe.run`

`Scribe.run(name, *, run_id=None, tags=None, metadata=None, code_revision=None, config_snapshot=None, dataset_ref=None)`

이 method는 run scope를 만듭니다. 실무에서는 training run, evaluation pass, batch
scoring job, ingestion workflow 같은 메인 instrumentation boundary를 여는 메서드라고
생각하면 됩니다.

Parameters:

- `name`: 사람이 읽는 run name
- `run_id`: optional explicit run reference
- `tags`: optional run-level tag
- `metadata`: optional run-level metadata
- `code_revision`: source revision identity를 위한 optional reproducibility field
- `config_snapshot`: optional structured configuration snapshot
- `dataset_ref`: run provenance를 위한 optional dataset reference

Returns:

- `RunScope`

Example:

```python
with scribe.run(
    "baseline-train",
    code_revision="commit-123",
    dataset_ref="imagenet-v1",
    tags={"suite": "baseline"},
) as run:
    ...
```

반환된 scope는 context manager로 사용할 수 있고, stage와 operation instrumentation의
정상적인 시작점입니다.

### `scribe.Scribe.current_run`

`Scribe.current_run()`

이 method는 현재 active run scope를 반환합니다. helper function이나 framework callback이
scope object를 직접 인자로 받지 않고도 데이터를 emit해야 할 때 유용합니다.

Returns:

- `RunScope`

Raises:

- `ContextError`: 현재 execution context에 active run scope가 없을 때

### `scribe.Scribe.current_stage`

`Scribe.current_stage()`

이 method는 현재 active stage scope를 반환합니다.

Returns:

- `StageScope`

Raises:

- `ContextError`: active stage scope가 없을 때

### `scribe.Scribe.current_operation`

`Scribe.current_operation()`

이 method는 현재 active operation scope를 반환합니다.

Returns:

- `OperationScope`

Raises:

- `ContextError`: active operation scope가 없을 때

### `scribe.Scribe.event`

`Scribe.event(key, *, message, level="info", attributes=None, tags=None)`

이 method는 현재 active context 안에 구조화된 event를 emit합니다. helper function이
올바른 lifecycle scope가 이미 active하다는 사실을 알고 있을 때 쓰기 좋은 top-level
convenience form입니다.

Parameters:

- `key`: machine-readable event key
- `message`: 사람이 읽는 message
- `level`: event severity level
- `attributes`: optional structured event detail
- `tags`: optional event tag

Returns:

- `CaptureResult`

Raises:

- `ContextError`: active lifecycle context가 없을 때
- `ValidationError`: event payload가 invalid할 때
- `SinkDispatchError`: 모든 eligible sink가 dispatch에 실패했을 때

### `scribe.Scribe.emit_events`

`Scribe.emit_events(emissions)`

이 method는 현재 context에서 여러 event를 한 번에 emit합니다. `event(...)`의 batch
형태이며, instrumentation이 이미 structured input sequence로 준비되어 있을 때
유용합니다.

Parameters:

- `emissions`: `EventEmission`의 sequence

Returns:

- `BatchCaptureResult`

### `scribe.Scribe.metric`

`Scribe.metric(key, value, *, unit=None, aggregation_scope="step", tags=None, summary_basis="raw_observation")`

이 method는 현재 active context에 구조화된 metric을 emit합니다.

Parameters:

- `key`: metric name
- `value`: numeric value
- `unit`: optional unit string
- `aggregation_scope`: metric value가 어떤 aggregation level에서 해석되어야 하는지
- `tags`: optional metric tag
- `summary_basis`: 값이 어떻게 요약되었는지에 대한 optional 설명

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

### `scribe.Scribe.emit_metrics`

`Scribe.emit_metrics(emissions)`

이 method는 현재 context에서 여러 metric을 한 번에 emit합니다.

Parameters:

- `emissions`: `MetricEmission`의 sequence

Returns:

- `BatchCaptureResult`

### `scribe.Scribe.span`

`Scribe.span(name, *, started_at=None, ended_at=None, status="ok", span_kind="operation", attributes=None, linked_refs=None, parent_span_id=None)`

이 method는 active context 안에 trace-like span record를 emit합니다. 단일 scalar
measurement보다 특정 작업 단위의 duration과 status가 더 중요할 때 적합합니다.

Parameters:

- `name`: span name
- `started_at`: optional explicit start timestamp
- `ended_at`: optional explicit end timestamp
- `status`: span status
- `span_kind`: span category
- `attributes`: optional structured span attribute
- `linked_refs`: optional related reference
- `parent_span_id`: optional parent span identifier

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

### `scribe.Scribe.register_artifact`

`Scribe.register_artifact(artifact_kind, path, *, artifact_ref=None, attributes=None, compute_hash=True, allow_missing=False)`

이 method는 현재 lifecycle context에 artifact를 등록합니다. top-level convenience form이며,
checkpoint, prediction, evaluation report, 혹은 plain event message보다 durable identity가
필요한 output에서 자주 사용됩니다.

Parameters:

- `artifact_kind`: 논리적 artifact category
- `path`: artifact source path
- `artifact_ref`: optional explicit artifact reference
- `attributes`: optional artifact metadata
- `compute_hash`: 가능할 때 source hash를 계산할지 여부
- `allow_missing`: missing source를 failure 대신 degraded로 처리할지 여부

Returns:

- `CaptureResult`

Raises:

- `ContextError`
- `ValidationError`
- `SinkDispatchError`

## Scope API

lifecycle scope type은
[src/scribe/runtime/scopes.py](../../src/scribe/runtime/scopes.py)
에 있습니다. 일상적인 사용에서는 대부분의 개발자가 이 scope object를 직접 다룹니다.
lifecycle boundary가 명시적이고, instrumentation을 실제 작업과 같은 자리에서 표현할 수
있기 때문입니다.

모든 scope type은 몇 가지 public identity field를 공유합니다:

- `scope_kind`
- `ref`
- `name`

또한 모두 context-manager behavior를 공유합니다. scope에 들어가면 nested work를 위한
active context가 되고, `with` 블록을 나가면 자동으로 닫히며, 예외가 나왔으면
`"failed"`, 아니면 `"completed"` 상태로 닫힙니다.

### `scribe.RunScope`

`RunScope`는 `Scribe.run(...)`이 반환하는 top-level lifecycle scope입니다. 하나의
workflow execution 전체를 대표하는 main unit of work라고 보면 됩니다.

테스트나 디버깅에서 자주 보는 public field:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `code_revision`
- `config_snapshot_ref`
- `config_snapshot`
- `dataset_ref`
- `tags`
- `metadata`

Public method:

- `stage(name, *, stage_ref=None, metadata=None)`
- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

#### `scribe.RunScope.stage`

`RunScope.stage(name, *, stage_ref=None, metadata=None)`

이 method는 현재 run 아래에 stage scope를 만듭니다.

Parameters:

- `name`: stage name
- `stage_ref`: optional explicit stage reference
- `metadata`: optional stage metadata

Returns:

- `StageScope`

Raises:

- `ClosedScopeError`: run이 이미 닫혀 있을 때
- `ContextError`: lifecycle state가 일관되지 않을 때

### `scribe.StageScope`

`StageScope`는 training, evaluation, preprocessing, serving setup 같은 run 내부의 큰
phase를 나타냅니다.

테스트나 디버깅에서 자주 보는 public field:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `order_index`
- `metadata`

Public method:

- `operation(name, *, operation_ref=None, metadata=None)`
- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

#### `scribe.StageScope.operation`

`StageScope.operation(name, *, operation_ref=None, metadata=None)`

이 method는 현재 stage 아래에 operation scope를 만듭니다.

Parameters:

- `name`: operation name
- `operation_ref`: optional explicit operation reference
- `metadata`: optional operation metadata

Returns:

- `OperationScope`

Raises:

- `ClosedScopeError`
- `ContextError`

### `scribe.OperationScope`

`OperationScope`는 request, batch, iteration 같은 더 작은 observable work unit을 위한
fine-grained scope입니다.

테스트나 디버깅에서 자주 보는 public field:

- `scope_kind`
- `ref`
- `name`
- `started_at`
- `observed_at`
- `metadata`

Public method:

- `event(...)`
- `emit_events(...)`
- `metric(...)`
- `emit_metrics(...)`
- `span(...)`
- `register_artifact(...)`
- `close(status="completed")`

### Shared Scope Capture Methods

`RunScope`, `StageScope`, `OperationScope`는 모두 같은 capture-style method를 공유하며,
signature도 top-level session method와 같습니다:

- `event(key, *, message, level="info", attributes=None, tags=None)`
- `emit_events(emissions)`
- `metric(key, value, *, unit=None, aggregation_scope="step", tags=None, summary_basis="raw_observation")`
- `emit_metrics(emissions)`
- `span(name, *, started_at=None, ended_at=None, status="ok", span_kind="operation", attributes=None, linked_refs=None, parent_span_id=None)`
- `register_artifact(artifact_kind, path, *, artifact_ref=None, attributes=None, compute_hash=True, allow_missing=False)`
- `close(status="completed")`

차이는 payload shape가 아니라 call site의 명시성에 있습니다. scope method는 lifecycle
relationship을 코드 위치에 드러내고, top-level session call은 현재 active context에
의존합니다.

## Configuration

runtime configuration model은
[src/scribe/config/models.py](../../src/scribe/config/models.py)
에 있고, `scribe.config`에서 import합니다.

### `scribe.config.ScribeConfig`

`ScribeConfig(producer_ref="sdk.python.local", schema_version="1.0.0", capture_environment=True, capture_installed_packages=True, environment_variable_allowlist=(), retry_attempts=0, retry_backoff_seconds=0.0, outbox_root=None)`

이 dataclass는 session 전체에 적용되는 runtime behavior를 설정합니다. 대부분의 사용자는
초반에는 override할 필요가 없지만, environment capture를 제어하거나 custom producer
identity를 payload에 찍고 싶을 때 중요해집니다.

Parameters:

- `producer_ref`: emitted payload에 붙는 producer identity
- `schema_version`: 현재 `"1.0.0"`으로 고정된 schema version marker
- `capture_environment`: run 시작 시 environment context를 캡처할지 여부
- `capture_installed_packages`: installed package를 environment capture에 포함할지 여부
- `environment_variable_allowlist`: snapshot에 허용할 environment variable name
- `retry_attempts`: sink dispatch 실패 시 재시도 횟수
- `retry_backoff_seconds`: 재시도 사이의 기본 backoff 초 단위 값
- `outbox_root`: 실시간 전달 실패 payload를 durable하게 보존할 로컬 outbox 경로

Example:

```python
from scribe import LocalJsonlSink, Scribe
from scribe.config import ScribeConfig

scribe = Scribe(
    project_name="demo-project",
    sinks=[LocalJsonlSink(".scribe")],
    config=ScribeConfig(
        producer_ref="sdk.python.training",
        capture_environment=False,
    ),
)
```

## Batch Input Model

batch input model은 event와 metric capture를 미리 준비해 두었다가 한 번에 emit할 수
있도록 존재합니다. 복잡한 builder가 아니라 작은 dataclass입니다.

### `scribe.EventEmission`

`EventEmission(key, message, level="info", attributes={}, tags={})`

이 model은 `emit_events(...)`의 structured input입니다.

Fields:

- `key`
- `message`
- `level`
- `attributes`
- `tags`

Example:

```python
from scribe import EventEmission

EventEmission(
    key="epoch.started",
    message="epoch 1 started",
    tags={"phase": "train"},
)
```

### `scribe.MetricEmission`

`MetricEmission(key, value, unit=None, aggregation_scope="step", tags={}, summary_basis="raw_observation")`

이 model은 `emit_metrics(...)`의 structured input입니다.

Fields:

- `key`
- `value`
- `unit`
- `aggregation_scope`
- `tags`
- `summary_basis`

Example:

```python
from scribe import MetricEmission

MetricEmission(
    key="eval.accuracy",
    value=0.91,
    aggregation_scope="dataset",
    tags={"split": "validation"},
)
```

## Result Model

result model은
[src/scribe/results/models.py](../../src/scribe/results/models.py)
에 있습니다. `Scribe`의 capture call이 plain logging call과 다르게 느껴지는 가장 큰
이유가 바로 이것입니다. `None`을 반환하는 대신, SDK는 어떤 family가 emit되었는지,
delivery가 성공했는지, degradation이 있었는지 설명하는 구조화된 outcome을 반환합니다.

이 model은 `scribe.results`에서 public import할 수 있고, 일부는 top-level `scribe`
package에서도 재수출됩니다.

### `scribe.PayloadFamily`

`PayloadFamily`

이 enum은 SDK가 emit하는 넓은 truth family를 식별합니다.

Values:

- `PayloadFamily.CONTEXT`
- `PayloadFamily.RECORD`
- `PayloadFamily.ARTIFACT`
- `PayloadFamily.DEGRADATION`

### `scribe.DeliveryStatus`

`DeliveryStatus`

이 enum은 capture 또는 dispatch step의 outcome을 정규화합니다.

Values:

- `DeliveryStatus.SUCCESS`
- `DeliveryStatus.DEGRADED`
- `DeliveryStatus.FAILURE`
- `DeliveryStatus.SKIPPED`

`SUCCESS`는 적어도 하나의 eligible sink가 reduced fidelity 없이 payload를 받아들였다는
뜻입니다. `DEGRADED`는 일부 truth는 보존됐지만 ideal한 형태는 아니었다는 뜻입니다.
`FAILURE`는 capture가 성공하지 못했다는 뜻입니다. `SKIPPED`는 주로 sink별 delivery
detail 안에서 중요합니다.

### `scribe.results.Delivery`

`Delivery(sink_name, family, status, detail="")`

이 dataclass는 하나의 dispatch attempt 동안 하나의 sink에서 일어난 outcome을 기록합니다.

Fields:

- `sink_name`
- `family`
- `status`
- `detail`

`Delivery`는 top-level `scribe` package에서는 재수출되지 않지만, public
`scribe.results` module의 일부입니다. 테스트나 운영 툴링에서
`CaptureResult.deliveries`를 검사할 때 중요합니다.

### `scribe.CaptureResult`

`CaptureResult(family, status, deliveries=[], warnings=[], degradation_reasons=[], payload=None, degradation_emitted=False, degradation_payload=None, recovered_to_outbox=False, replay_refs=[])`

이것은 하나의 capture action에 대한 구조화된 outcome입니다.

Important fields:

- `family`: 캡처하려고 했던 payload family
- `status`: 정규화된 overall outcome
- `deliveries`: sink별 delivery entry
- `warnings`: capture 중 생긴 non-fatal warning
- `degradation_reasons`: degraded capture 이유를 설명하는 사람이 읽는 reason
- `payload`: 있을 경우 emit된 payload
- `degradation_emitted`: degradation payload도 emit되었는지 여부
- `degradation_payload`: 있을 경우 emit된 degradation payload
- `recovered_to_outbox`: 실시간 전달 실패 뒤 durable outbox 보존으로 복구되었는지 여부
- `replay_refs`: outbox replay나 추적에 사용할 delivery reference

Important properties:

- `succeeded`: success와 degraded outcome에서 `True`
- `degraded`: overall status가 degraded일 때만 `True`

실무에서는 대부분의 application code가 `status`, `succeeded`, `degraded`, 그리고 경우에
따라 `degradation_reasons` 정도만 보면 충분합니다. 테스트와 운영 툴링은 `deliveries`
까지 보는 일이 많습니다.

### `scribe.BatchCaptureResult`

`BatchCaptureResult(family, status, results=[])`

이것은 batch event나 batch metric capture의 aggregated outcome입니다.

Important fields:

- `family`
- `status`
- `results`

Important properties:

- `total_count`
- `success_count`
- `degraded_count`
- `failure_count`
- `succeeded`
- `degraded`

Class methods:

- `BatchCaptureResult.from_results(family, results)`

overall batch status는 item-level result에서 정규화됩니다. 모든 item이 성공했을 때만
완전한 success이고, 모든 item이 실패했을 때만 완전한 failure입니다. 섞인 outcome은
degraded batch result를 만듭니다.

## Artifact Model

public artifact model은
[src/scribe/artifacts/models.py](../../src/scribe/artifacts/models.py)
에 있습니다. 대부분의 사용자는 normal instrumentation 동안 이 model을 모두 직접
인스턴스화하지는 않습니다. `register_artifact(...)`가 common path를 처리하기 때문입니다.
그래도 이 model이 public surface인 이유는, `Scribe`가 emit하는 binding model 자체를
정의하고 있고, 테스트, extension, advanced inspection code에서 유용하기 때문입니다.

이 model은 `scribe.artifacts`와 convenience를 위한 top-level `scribe` 양쪽에서 public
import가 가능합니다.

### `scribe.ArtifactSourceKind`

`ArtifactSourceKind`

이 enum은 artifact byte가 현재 어디에 있는지를 설명합니다.

Values:

- `ArtifactSourceKind.PATH`
- `ArtifactSourceKind.STAGED_PATH`
- `ArtifactSourceKind.URI`

### `scribe.ArtifactBindingStatus`

`ArtifactBindingStatus`

이 enum은 artifact binding의 operational state를 설명합니다.

Values:

- `ArtifactBindingStatus.BOUND`
- `ArtifactBindingStatus.PENDING`
- `ArtifactBindingStatus.DEGRADED`

### `scribe.ArtifactSource`

`ArtifactSource(kind, uri, exists)`

이 frozen dataclass는 runtime이 artifact source를 어디로 보고 있는지, 그리고 그 source가
현재 존재하는지를 기록합니다.

Fields:

- `kind`
- `uri`
- `exists`

### `scribe.ArtifactVerificationPolicy`

`ArtifactVerificationPolicy(compute_hash=True, require_existing_source=True)`

이 frozen dataclass는 artifact registration request에 붙는 verification expectation을
기록합니다.

Fields:

- `compute_hash`
- `require_existing_source`

### `scribe.ArtifactRegistrationRequest`

`ArtifactRegistrationRequest(artifact_ref, artifact_kind, source, verification_policy, attributes={})`

이 frozen dataclass는 registration intent가 bound artifact payload로 바뀌기 전의 request를
표현합니다.

Fields:

- `artifact_ref`
- `artifact_kind`
- `source`
- `verification_policy`
- `attributes`

### `scribe.ArtifactBinding`

`ArtifactBinding(request, manifest, source, project_name, operation_context_ref, binding_status="bound", completeness_marker="complete", degradation_marker="none", attributes={})`

이 frozen dataclass는 `Scribe`가 emit하는 artifact-family payload입니다. request로 무엇을
원했는지와, 실제로 어떤 binding state가 성립했는지를 함께 들고 갑니다.

Important fields:

- `request`
- `manifest`
- `source`
- `project_name`
- `operation_context_ref`
- `binding_status`
- `completeness_marker`
- `degradation_marker`
- `attributes`

이 field가 언제 degrade되는지, 혹은 왜 artifact binding이 event와 분리된 model인지
이해하려면 [아티팩트](artifacts.md)를
함께 읽는 것이 좋습니다.

## Sink Type

built-in sink는
[src/scribe/sinks/__init__.py](../../src/scribe/sinks/__init__.py)
를 통해 재수출됩니다. 이것이 `Scribe`의 구조화된 runtime model과 실제 persistence 또는
inspection 사이의 delivery boundary입니다.

이 type은 `scribe.sinks`와 top-level `scribe` 양쪽에서 public import할 수 있습니다.

### `scribe.Sink`

`Sink`

이것은 abstract sink interface입니다.

Important members:

- `name`
- `supported_families`
- `supports(family)`
- `capture(family=..., payload=...)`

custom sink는 이 contract를 따라야 합니다.

### `scribe.LocalJsonlSink`

`LocalJsonlSink(storage_root, *, name="local-jsonl")`

이것은 로컬 개발과 inspection을 위한 기본 persistence-oriented sink입니다. configured
storage root 아래에 payload family별 JSONL 파일 하나씩을 씁니다.

Important methods:

- `capture(...)`
- `path_for(family)`
- `read_family(family)`

Returns:

- `LocalJsonlSink`

### `scribe.InMemorySink`

`InMemorySink(*, name="memory")`

이것은 가장 단순한 inspection sink입니다. capture action을 메모리에 저장하고, 테스트와
가벼운 runtime assertion에서 특히 유용합니다.

Important fields:

- `actions`

Returns:

- `InMemorySink`

### `scribe.S3ObjectSink`

`S3ObjectSink(client, bucket, *, prefix="scribe", name="s3-object")`

이 sink는 payload를 object-by-object 방식으로 S3에 기록합니다. append형 JSONL이 아니라 family/date/ref 기반 object key를 사용하므로, 원격 object storage와 더 잘 맞습니다.

Important parameters:

- `client`
- `bucket`
- `prefix`
- `name`

### `scribe.KafkaSink`

`KafkaSink(producer, *, topics=None, timeout_seconds=5.0, name="kafka")`

이 sink는 family별 topic으로 payload를 전송하고, producer ack를 동기적으로 확인합니다. delivery 실패는 dispatch retry나 outbox recovery와 자연스럽게 연결됩니다.

Important parameters:

- `producer`
- `topics`
- `timeout_seconds`
- `name`

### `scribe.CompositeSink`

`CompositeSink(sinks, *, name="composite")`

이 sink는 같은 capture request를 여러 child sink로 전달합니다.

Parameters:

- `sinks`
- `name`

Returns:

- `CompositeSink`

이 sink는 계속 제공되지만, 새 통합에서는 top-level `Scribe(..., sinks=[...])` fan-out이 더 권장됩니다. child sink 일부만 실패하는 상황을 더 직접적으로 해석할 수 있기 때문입니다.

dispatch, family support, local persistence layout 같은 운영 detail은
[싱크와 저장소](sinks-and-storage.md)를 함께
보는 것이 가장 좋습니다.

## Exception

public exception type은
[src/scribe/exceptions.py](../../src/scribe/exceptions.py)에
있습니다. 이것들은 `Scribe`의 failure를 몇 가지 작은 범주로 나눠서, caller가 invalid
input, missing lifecycle state, closed scope, dispatch failure를 구분할 수 있게 해줍니다.

이 exception은 top-level `scribe` package에서 재수출됩니다.

### `scribe.ScribeError`

패키지 전체의 base exception입니다.

### `scribe.ValidationError`

SDK에 invalid data가 전달되었을 때 raise됩니다.

전형적인 원인에는 invalid metric field, unsupported aggregation scope, invalid artifact
input, 그 밖의 payload-shape 문제가 포함됩니다. 이런 문제는 call site에서 고쳐야
합니다.

### `scribe.ContextError`

lifecycle state가 없거나 일관되지 않을 때 raise됩니다.

전형적인 원인에는 active run 없이 capture를 시도하는 경우, run이 active하지 않은데
`current_run()`을 호출하는 경우, 혹은 현재 execution context에 존재하지 않는 lifecycle
state를 전제로 코드를 작성한 경우가 포함됩니다.

### `scribe.ClosedScopeError`

이미 닫힌 scope를 다시 사용하려 할 때 raise됩니다.

이 예외는 `ContextError`의 subclass입니다. payload validation 문제가 아니라 여전히
lifecycle-state 문제라는 뜻입니다.

### `scribe.SinkDispatchError`

모든 eligible sink가 dispatch에 실패했을 때 raise됩니다.

capture logic은 유효했지만, delivery infrastructure가 실패해서 성공적인 sink path가
하나도 남지 않았을 때 잡아야 하는 예외가 이것입니다.

## 관련 파일

- Package exports: [src/scribe/__init__.py](../../src/scribe/__init__.py)
- SDK session API: [src/scribe/api/session.py](../../src/scribe/api/session.py)
- Scope types: [src/scribe/runtime/scopes.py](../../src/scribe/runtime/scopes.py)
- Runtime config: [src/scribe/config/models.py](../../src/scribe/config/models.py)
- Result models: [src/scribe/results/models.py](../../src/scribe/results/models.py)
- Artifact models: [src/scribe/artifacts/models.py](../../src/scribe/artifacts/models.py)
- Exceptions: [src/scribe/exceptions.py](../../src/scribe/exceptions.py)
