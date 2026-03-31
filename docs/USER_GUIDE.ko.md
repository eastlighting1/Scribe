# Scribe 사용자 가이드 (KO)

Scribe 문서는 새로운 사용자가 모든 API를 하나씩 외우기 전에, "이 라이브러리를 실제 Python ML 워크플로에 어떻게 붙여야 하는가?"에 먼저 답할 수 있도록 구성되어 있습니다. 처음 들어왔다면 아래 순서로 읽는 것이 가장 빠릅니다.

- [시작하기](ko/getting-started.md)
- [핵심 개념](ko/core-concepts.md)
- [캡처 패턴](ko/capture-patterns.md)
- [싱크와 저장소](ko/sinks-and-storage.md)
- [아티팩트](ko/artifacts.md)
- [Degradation과 오류](ko/degradation-and-errors.md)
- [API 레퍼런스](ko/api-reference.md)
- [예제](ko/examples.md)

권장 읽기 순서:

1. 바로 `Scribe`를 import해서 첫 event나 metric을 남기고 싶다면 [시작하기](ko/getting-started.md)부터 읽으세요.
2. `run -> stage -> operation` 구조와 payload family의 의미를 이해하고 싶다면 [핵심 개념](ko/core-concepts.md)을 읽으세요.
3. event, metric, span, artifact를 언제 어떻게 써야 할지 실전 감각이 필요하면 [캡처 패턴](ko/capture-patterns.md)과 [아티팩트](ko/artifacts.md)를 보세요.
4. 로컬 JSONL 출력, sink 동작, degraded capture 해석이 궁금하면 [싱크와 저장소](ko/sinks-and-storage.md)와 [Degradation과 오류](ko/degradation-and-errors.md)를 보세요.
5. 메서드나 결과 타입을 빠르게 찾고 싶다면 [API 레퍼런스](ko/api-reference.md)를 참고하세요.

처음 접한다면 보통 `시작하기`, `핵심 개념`, `Degradation과 오류` 세 문서만 먼저 읽어도 전체 흐름을 이해하기에 충분합니다.

## 이 문서가 중점을 두는 부분

`Scribe`는 스키마만 정의하는 라이브러리가 아니라, 실행 중인 Python 워크플로 안에서 관측 사실을 캡처하는 capture-side SDK입니다. 그래서 문서도 단순한 타입 목록보다 다음 질문에 답하는 데 초점을 맞춥니다.

- 어디에서 `run`을 열어야 하는가
- 언제 `stage`와 `operation`을 나눠야 하는가
- 언제 event, metric, span, artifact로 기록해야 하는가
- `CaptureResult`와 degraded capture를 어떻게 해석해야 하는가
- sink가 로컬 저장과 전달 경로에 어떤 영향을 주는가

즉, Scribe 문서는 "필드가 무엇인가"보다 "런타임에서 무엇을 언제 어떻게 남길 것인가"를 먼저 설명합니다.

## Scribe가 하는 일

큰 흐름에서 `Scribe`는 코드가 다음 다섯 가지를 하도록 돕습니다.

- ML 실행을 위한 명시적인 lifecycle scope를 연다
- 런타임 사실을 canonical observability payload로 변환한다
- 실행 컨텍스트를 자동으로 붙인다
- capability-based sink로 payload를 보낸다
- degraded capture를 숨기지 않고 구조화된 증거로 남긴다

일반적인 사용 흐름은 아래와 같습니다.

```text
create Scribe session
  -> enter run
    -> optionally enter stage and operation scopes
      -> emit event / metric / span / artifact
        -> inspect CaptureResult
          -> let sinks persist or forward payloads
```

이 가이드는 이 흐름이 자연스럽게 느껴지도록 만드는 것을 목표로 합니다.

## 문서 구성 방식

문서는 내부 모듈 구조가 아니라 사용자가 하려는 작업 기준으로 나뉘어 있습니다.

- `시작하기`: 가장 빠른 첫 성공 경로
- `핵심 개념`: mental model과 scope 구조
- `캡처 패턴`: 어떤 런타임 사실에 어떤 capture primitive를 써야 하는지
- `싱크와 저장소`: payload가 어디로 가고 어떻게 확인하는지
- `아티팩트`: binding 중심의 출력 캡처
- `Degradation과 오류`: reduced-fidelity capture와 운영 실패 해석
- `API 레퍼런스`: 공개 메서드와 결과 모델 빠르게 찾기
- `예제`: 전체 워크플로 레퍼런스

이 구조는 의도적입니다. 실제로는 "어떤 필드가 있나"보다 "어느 지점에서 캡처해야 하나" 때문에 더 자주 헷갈리기 때문입니다.

## 시간이 없을 때 먼저 읽을 문서

몇 분밖에 없다면 아래 세 문서를 먼저 읽으세요.

1. [시작하기](ko/getting-started.md)
2. [핵심 개념](ko/core-concepts.md)
3. [Degradation과 오류](ko/degradation-and-errors.md)

이 세 문서만으로도 아래를 이해할 수 있습니다.

- `Scribe`의 기본 런타임 구조
- record가 어느 위치에서 생겨야 하는지
- success, degraded, failure가 각각 무엇을 의미하는지

## Spine과의 관계

`Scribe`는 `Spine`과 밀접하게 연결되어 있지만 역할은 다릅니다.

- `Spine`은 canonical contract를 정의하고 검증합니다.
- `Scribe`는 런타임의 실제 데이터를 캡처하고 sink를 통해 전달합니다.

모델 시맨틱, 계약 구조, 검증 규칙이 궁금하면 `Spine` 쪽을 보면 되고, Python 워크플로를 계측하고 capture 결과를 해석하는 방법이 궁금하면 `Scribe` 쪽을 보면 됩니다.

## 관련 파일

- 영어 사용자 가이드: [docs/USER_GUIDE.en.md](USER_GUIDE.en.md)
- 패키지 엔트리포인트: [src/scribe/__init__.py](../src/scribe/__init__.py)
- 퍼블릭 세션 API: [src/scribe/api/session.py](../src/scribe/api/session.py)
- 학습 예제: [examples/training_workflow.py](../examples/training_workflow.py)
- 평가 예제: [examples/evaluation_workflow.py](../examples/evaluation_workflow.py)
- 아티팩트 바인딩 예제: [examples/artifact_binding_workflow.py](../examples/artifact_binding_workflow.py)
