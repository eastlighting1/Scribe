# Scribe 사용자 가이드

Scribe 문서는 새로운 사용자가 모든 API의 세부 사항을 파고들기 전에 "실제 Python ML 워크플로우에 이 라이브러리를 어떻게 추가해야 할까?"라는 질문에 답할 수 있도록 구성되어 있습니다. 이곳에 처음 오셨다면, 아래의 문서들을 순서대로 읽어보는 것이 가장 빠른 방법입니다.

- [시작하기](C:/Users/eastl/MLObservability/Scribe/docs/ko/getting-started.md)
- [핵심 개념](C:/Users/eastl/MLObservability/Scribe/docs/ko/core-concepts.md)
- [캡처 패턴](C:/Users/eastl/MLObservability/Scribe/docs/ko/capture-patterns.md)
- [싱크 및 스토리지](C:/Users/eastl/MLObservability/Scribe/docs/ko/sinks-and-storage.md)
- [아티팩트](C:/Users/eastl/MLObservability/Scribe/docs/ko/artifacts.md)
- [성능 저하 및 오류](C:/Users/eastl/MLObservability/Scribe/docs/ko/degradation-and-errors.md)
- [API 레퍼런스](C:/Users/eastl/MLObservability/Scribe/docs/ko/api-reference.md)
- [예제](C:/Users/eastl/MLObservability/Scribe/docs/ko/examples.md)

권장 읽기 순서:

1. 당장 `Scribe`를 임포트하여 첫 번째 이벤트나 메트릭을 기록해보고 싶다면, [시작하기](C:/Users/eastl/MLObservability/Scribe/docs/ko/getting-started.md)부터 읽어보세요.
2. `run -> stage -> operation`의 멘탈 모델과 4가지 페이로드 제품군을 이해하고 싶다면, [핵심 개념](C:/Users/eastl/MLObservability/Scribe/docs/ko/core-concepts.md)을 읽어보세요.
3. 언제 이벤트, 메트릭, 스팬, 아티팩트를 발생시켜야 하는지에 대한 실용적인 가이드가 필요하다면, [캡처 패턴](C:/Users/eastl/MLObservability/Scribe/docs/ko/capture-patterns.md)과 [아티팩트](C:/Users/eastl/MLObservability/Scribe/docs/ko/artifacts.md)를 읽어보세요.
4. 로컬 검사, 싱크 동작 및 캡처 성능 저하에 대해 이해하고 싶다면, [싱크 및 스토리지](C:/Users/eastl/MLObservability/Scribe/docs/ko/sinks-and-storage.md)와 [성능 저하 및 오류](C:/Users/eastl/MLObservability/Scribe/docs/ko/degradation-and-errors.md)를 읽어보세요.
5. 메서드와 결과 모델을 빠르게 찾아보고 싶다면, [API 레퍼런스](C:/Users/eastl/MLObservability/Scribe/docs/ko/api-reference.md)를 활용하세요.

`Scribe`가 처음이라면 `시작하기`, `핵심 개념`, 그리고 `성능 저하 및 오류`를 먼저 읽은 다음, 필요할 때만 특정 타입이나 운영 관련 페이지로 넘어가는 것이 보통 훨씬 효율적입니다.

## 이 문서가 중점을 두는 부분

`Scribe`는 근본적으로 스키마를 정의하는 라이브러리가 아닙니다. 실행 중인 Python 워크플로우 내부에 자리 잡는 캡처 측(capture-side) SDK입니다. 즉, 문서에서 다뤄야 할 가장 중요한 질문들은 대개 다음과 같습니다:

- 어디에서 `run`을 열어야 하는가
- 언제 `stage` 및 `operation` 스코프를 생성해야 하는가
- 언제 이벤트, 메트릭, 스팬 또는 아티팩트로 간주해야 하는가
- `CaptureResult`와 성능이 저하된(degraded) 캡처를 어떻게 해석해야 하는가
- 싱크가 로컬에 유지되거나 다운스트림으로 전달되는 데이터에 어떤 영향을 미치는가

이러한 이유로, Scribe 문서는 단순히 타입 정의뿐만 아니라 캡처 흐름과 운영적 해석을 중심으로 작성되었습니다.

## Scribe의 역할

큰 틀에서 볼 때, `Scribe`는 코드 레벨에서 다음 다섯 가지 작업을 수행하도록 돕습니다:

- ML 실행을 위한 명시적인 수명 주기 스코프 생성
- 런타임 팩트(facts)를 표준 옵저버빌리티 페이로드로 변환
- 실행 컨텍스트 자동 첨부
- 기능 기반(capability-based) 싱크로 페이로드 디스패치
- 성능이 저하된 캡처를 숨기지 않고 구조화된 증거로 보존

일반적인 사용 패턴은 다음과 같습니다:

```text
create Scribe session
  -> enter run
    -> optionally enter stage and operation scopes
      -> emit event / metric / span / artifact
        -> inspect CaptureResult
          -> let sinks persist or forward payloads
```

이 가이드는 모든 메서드를 암기하기 전에 이러한 흐름이 자연스럽게 느껴지도록 설계되었습니다.

## 문서 구성 방식

이 문서들은 내부 모듈 구조가 아닌 사용자 작업(task)을 기준으로 나뉘어 있습니다.

  - `시작하기`: 초기 성공을 위한 경로
  - `핵심 개념`: 멘탈 모델 및 스코프 구조
  - `캡처 패턴`: 특정 런타임 팩트에 적합한 캡처 기본 요소(primitive)
  - `싱크 및 스토리지`: 페이로드의 이동 경로 및 검사 방법
  - `아티팩트`: 바인딩 중심의 출력 캡처
  - `성능 저하 및 오류`: 충실도가 낮아진(reduced-fidelity) 캡처 및 운영 실패를 해석하는 방법
  - `API 레퍼런스`: 공개 메서드 및 결과 모델의 빠른 검색
  - `예제`: 전체 워크플로우 레퍼런스

이는 의도적인 구성입니다. `Scribe`를 사용할 때 겪는 대부분의 혼란은 "어떤 필드가 존재하는가"가 아니라 "워크플로우의 어느 부분에서 이를 캡처해야 하며, 나중에 운영상 어떤 식으로 동작할 것인가"에서 비롯되기 때문입니다.

## 시간이 부족할 때 읽어야 할 문서

시간이 몇 분밖에 없다면, 다음 세 페이지를 먼저 읽어보세요:

1.  [시작하기](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/docs/ko/getting-started.md)
2.  [핵심 개념](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/docs/ko/core-concepts.md)
3.  [성능 저하 및 오류](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/docs/ko/degradation-and-errors.md)

이 세 페이지만으로도 다음 내용을 이해하기에 충분합니다:

  - `Scribe`의 기본적인 런타임 형태
  - 레코드가 위치해야 할 곳
  - 성공, 성능 저하(degraded), 실패 상태가 의미하는 바

## Spine과의 관계

`Scribe`는 `Spine`과 밀접하게 연관되어 있지만, 두 라이브러리의 목적은 다릅니다.

  - `Spine`은 표준 규약(canonical contract)을 정의하고 검증합니다.
  - `Scribe`는 런타임의 실제 데이터를 캡처하여 싱크를 통해 전달합니다.

따라서 깊이 있는 모델 시맨틱, 스키마 추론 또는 호환성 세부 정보가 필요하다면 `Spine`을 살펴보는 것이 적합합니다. 반면, 실제 Python 코드를 계측(instrument)하는 방법과 캡처가 성공하거나 성능이 저하될 때 어떤 일이 발생하는지 알아야 한다면 `Scribe`가 적합합니다.

## 관련 파일

  - 한국어 문서 홈: [docs/ko/README.md](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/docs/ko/README.md)
  - 영어 사용자 가이드 항목: [docs/USER\_GUIDE.en.md](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/docs/USER_GUIDE.en.md)
  - 패키지 엔트리포인트: [src/scribe/**init**.py](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/src/scribe/__init__.py)
  - 퍼블릭 세션 API: [src/scribe/api/session.py](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/src/scribe/api/session.py)
  - 학습 예제: [examples/training\_workflow.py](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/examples/training_workflow.py)
  - 평가 예제: [examples/evaluation\_workflow.py](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/examples/evaluation_workflow.py)
  - 아티팩트 바인딩 예제: [examples/artifact\_binding\_workflow.py](https://www.google.com/search?q=C:/Users/eastl/MLObservability/Scribe/examples/artifact_binding_workflow.py)

<!-- end list -->