# 크로스플랫폼 SDK 공통 계약: API·오류·상태·이벤트와 적합성 테스트

Java·Kotlin·Swift·JavaScript SDK가 같은 API를 각자 다르게 해석하면 플랫폼마다 다른 버그가 됩니다. 공통 계약은 공통 구현이 아니라 의미를 하나로 고정하는 일입니다. 이 글은 계약 저장소와 Version을 진실의 원천으로 두고 Operation 의미·오류·상태·이벤트 모델과 타입 변환 경계를 정의한 뒤, Golden Vector 적합성 테스트로 네 플랫폼을 검증하는 방법을 정리합니다.

![공통 API·오류·상태·이벤트 의미 계약이 네 플랫폼 SDK로 투영되고 적합성 매트릭스와 통합 증거로 검증되는 크로스플랫폼 SDK 아키텍처 이미지](assets/blog-45-cross-platform-sdk-contract-hero.png)

> **목차**
>
> 1. [공통 계약은 공통 구현이 아니다](#ai-section-1)
> 2. [계약 저장소와 Version을 진실의 원천으로 둔다](#ai-section-2)
> 3. [Operation 의미와 플랫폼별 API 투영을 함께 고정한다](#ai-section-3)
> 4. [JSON과 언어 Type의 경계를 명시한다](#ai-section-4)
> 5. [Schema와 실행 가능한 의미 규칙을 함께 관리한다](#ai-section-5)
> 6. [안정적인 오류 Code와 원본 정보를 보존한다](#ai-section-6)
> 7. [상태를 Boolean이 아닌 전이 규칙으로 정의한다](#ai-section-7)
> 8. [Event 전달과 Snapshot 재연결 계약을 연결한다](#ai-section-8)
> 9. [Cursor와 관측 문맥을 불투명하게 유지한다](#ai-section-9)
> 10. [변경 가능성과 호환성 정책을 계약에 포함한다](#ai-section-10)
> 11. [Golden Vector는 합의된 명세에서 만든다](#ai-section-11)
> 12. [같은 Fixture를 네 SDK에 독립 실행한다](#ai-section-12)
> 13. [Consumer Contract와 Provider 적합성을 함께 쓴다](#ai-section-13)
> 14. [CI에서 호환성과 적합성을 Release 조건으로 만든다](#ai-section-14)
> 15. [계약 변경의 소유자와 완료 기준을 정한다](#ai-section-15)
> 16. [구현·운영 체크리스트](#ai-section-16)
> 17. [마무리와 참고 자료](#ai-section-17)

같은 서비스를 Java Server SDK, Android Kotlin SDK, iOS Swift SDK와 React JavaScript SDK로 제공하면 네 개의 구현이 생깁니다. 그러나 고객에게 전달해야 할 업무 의미까지 네 개가 되어서는 안 됩니다.

예를 들어 서버는 상태 코드를 정상적으로 반환했는데 Android에서는 재시도하고 iOS에서는 즉시 실패한다면, 또는 Web SDK만 큰 숫자 ID를 다른 값으로 읽는다면 각 SDK의 코드는 동작해도 제품 계약은 깨진 것입니다.

![공통 Contract Repository의 API·오류·상태·이벤트 의미가 Java·Kotlin·Swift·JavaScript의 자연스러운 Public API로 투영되는 구조](assets/blog-45-semantic-contract-projections.png)

공통 계약의 목적은 모든 언어에서 똑같은 Class와 Method 이름을 강제하는 것이 아닙니다. Java에는 Java다운 API를, Kotlin에는 Coroutine과 Flow를, Swift에는 `async/await`과 `AsyncSequence`를, JavaScript에는 Promise와 구독 API를 제공하되 **입력·결과·오류·상태 변화의 의미는 같게 유지하는 것**입니다.

이 글에서는 특정 고객·제품·내부 Endpoint를 제외한 합성 예시로 크로스플랫폼 SDK 계약과 적합성 테스트(Conformance Test)를 설계합니다. 스키마·식별자·오류 Code 값은 전부 **공개용 합성 값**입니다. 다만 본문에서 **"필자"라고 밝힌 단락은 실제 정합성 검증·표면 확장 경험**에서 회사·제품·저장소·Endpoint 경로와 실제 API·도메인 수처럼 운영 규모를 드러내는 정보를 제거해 재구성한 것입니다.

<h2 id="ai-section-1" style="scroll-margin-top: 72px;">1. 공통 계약은 공통 구현이 아니다</h2>

멀티플랫폼 SDK에서 재사용해야 하는 것은 소스 코드보다 결정 규칙입니다.

| 공통이어야 하는 것 | 플랫폼별로 달라도 되는 것 |
|---|---|
| 업무 Operation과 필수 입력 | Method 이름의 언어 관례 |
| 성공·실패의 의미 | 동기·비동기 표현 방식 |
| 안정적인 오류 Code | Exception·Result Type 구조 |
| 상태 전이와 종료 조건 | UI Framework 연결 방식 |
| 이벤트 중복·순서·재연결 규칙 | Stream·Callback·Publisher 표현 |
| 호환성·폐기 정책 | Package와 Build Tool |

네 SDK가 하나의 공통 Runtime을 억지로 공유하면 언어별 수명과 오류 처리 관례를 해칠 수 있습니다. 반대로 명세만 있고 실행 가능한 검증이 없으면 시간이 지날수록 구현마다 의미가 달라집니다.

따라서 공통 계약은 다음 네 층으로 관리합니다.

- **의미 계약(Semantic Contract)은** 업무적으로 무엇을 뜻하는지 정의합니다.
- **Wire 계약**은 HTTP Body, Header와 Event Payload의 전송 형식을 정의합니다.
- **플랫폼 투영(Platform Projection)은** 같은 의미를 각 언어에 자연스럽게 노출합니다.
- **적합성 Suite**는 구현이 계약을 지키는지 반복해서 증명합니다.

OpenAPI 문서 하나만으로 네 층이 모두 해결되지는 않습니다. Schema는 필드 형식을 잘 설명하지만 취소가 서버 작업도 중단하는지, 이벤트 중복을 어떻게 처리하는지, 알 수 없는 Enum을 보존해야 하는지까지 자동으로 결정하지는 못합니다.

<h2 id="ai-section-2" style="scroll-margin-top: 72px;">2. 계약 저장소와 Version을 진실의 원천으로 둔다</h2>

공통 계약을 각 SDK Repository의 Wiki나 README에 복사해 두면 어느 문서가 최신인지 알 수 없습니다. 계약 원본과 실행 가능한 Fixture를 한곳에 두고, 각 SDK Build가 명시적인 계약 Version을 가져가도록 합니다.

```text
contract/
├── manifest.yaml
├── openapi.yaml
├── asyncapi.yaml
├── schemas/
│   ├── session.schema.json
│   ├── problem.schema.json
│   └── event.schema.json
├── scenarios/
│   ├── create-session.yaml
│   ├── cancel-request.yaml
│   └── resume-events.yaml
└── vectors/
    ├── valid/
    └── invalid/
```

`manifest.yaml`에는 최소한 다음 정보를 둡니다.

```yaml
contractId: example-sdk-contract
contractVersion: 2026-07
openapi: ./openapi.yaml
asyncapi: ./asyncapi.yaml
defaultTimeZone: UTC
identifierEncoding: opaque-string
unknownOutputFieldPolicy: ignore
extensionFieldPolicy: preserve-only-in-designated-extension-container
unknownInputFieldPolicy: reject
unknownEnumPolicy: preserve-raw-value
eventDelivery: at-least-once
```

계약 Version은 SDK Package Version과 같은 개념이 아닙니다. 하나의 계약 Version을 Java `4.x`, Kotlin `3.x`, Swift `2.x`, JavaScript `5.x`가 각각 구현할 수 있습니다. 어떤 SDK Version이 어떤 계약을 구현하는지는 별도 호환성 표로 추적합니다.


### 계약 저장소가 없을 때 무엇이 대신 진실의 원천이 되는가

위 구조는 계약 저장소가 **먼저** 있다는 전제에서 출발합니다. 필자가 **정합성 검증과 API 표면 확장 작업에 참여한** 두 SDK — 브라우저에서 동작하는 소비자 SDK와 고객사 서버에 심는 중계 SDK — 사이에는 그 저장소가 없었습니다. 각자 자기 호출 목록을 자기 코드에 들고 있었습니다.

이때 정한 것은 **표면의 진실 원천을 소비자 쪽 코드로 둔다**였습니다. 그리고 판정 기준을 "양쪽 일치"가 아니라 **"중계 쪽이 소비자 쪽의 상위집합"** 으로 잡았습니다. 방향이 비대칭인 이유는 두 방향의 결과가 다르기 때문입니다.

| 차이의 방향 | 의미 | 이 검사의 판정 |
|---|---|---|
| 소비자가 호출하는데 중계에 없다 | 해당 호출은 실행 시 실패한다 | 🔴 차단 |
| 중계에만 있다 | 미사용 표면·의도된 비노출·죽은 표면일 수 있다 | ⚪ 통과 — 필요성은 별도 검토 |

두 번째 줄이 "정상"이 아니라 "이 검사는 통과"인 점이 중요합니다. 상위집합 판정은 실행 경로가 끊기지 않았다는 것만 말하고, 그 표면이 있어야 하는지는 답하지 않습니다.

📌 계약 저장소가 있으면 양쪽 모두를 저장소와 대조하므로 판정이 대칭이 됩니다. 저장소가 없으면 **실제로 호출하는 쪽이 사실상의 계약**이 되고, 그 순간 판정은 한쪽 방향으로만 엄격해집니다. 이 상태는 동작하지만 계약을 코드에서 역산해야 하므로, 계약 저장소를 두는 편이 낫다는 이 절의 권고를 대체하지 않습니다. 다만 저장소를 만들기 전에도 **판정 방향만 먼저 정해 두면** 대조를 시작할 수 있습니다.

<h2 id="ai-section-3" style="scroll-margin-top: 72px;">3. Operation 의미와 플랫폼별 API 투영을 함께 고정한다</h2>

Operation마다 Method와 Path만 기록하지 말고 입력 전제조건, 성공 조건과 Side Effect를 함께 정의합니다.

예를 들어 `createSession`의 계약은 다음과 같이 쓸 수 있습니다.

| 항목 | 계약 |
|---|---|
| 입력 | `title`, 선택적인 고객 정의 Metadata |
| 성공 | 새로운 Session과 안정적인 `sessionId` 반환 |
| 멱등성 | 같은 Idempotency Key와 같은 입력은 같은 업무 결과 |
| 취소 | 호출자 대기 취소와 이미 시작된 서버 업무 취소는 별도 Operation |
| Timeout | 결과를 모른다는 뜻이며 업무 실패를 단정하지 않음 |
| 오류 | 안정적인 `code`, 재시도 가능 여부, 추적용 `requestId` 반환 |
| 이벤트 | 생성 완료 후 상태 변경 Event가 중복 전달될 수 있음 |

Wire Envelope도 공통으로 정할 수 있습니다.

```json
{
  "contractVersion": "2026-07",
  "requestId": "req-example-001",
  "tenantId": "tenant-example",
  "locale": "ko-KR",
  "payload": {
    "title": "합성 예시"
  }
}
```

여기서 `tenantId`가 Body에 있다고 해서 신뢰 가능한 권한 근거가 되는 것은 아닙니다. Mobile·Web에서 넘어온 Tenant와 Actor 정보는 서버의 인증 Context에서 다시 확인해야 합니다. Body 필드는 업무 Routing Hint일 수 있지만 인가의 진실의 원천은 아닙니다.

### 언어별 API 모양과 업무 의미를 분리한다

같은 단일 결과 Operation도 언어마다 자연스러운 비동기 표현이 다릅니다.

| 공통 의미 | Java Server | Kotlin | Swift | JavaScript |
|---|---|---|---|---|
| 단일 결과 | `CompletionStage<T>` 또는 동기 Facade | `suspend fun(): T` | `async throws -> T` | `Promise<T>` |
| 지속 이벤트 | `Flow.Publisher<T>` | `Flow<T>` | `AsyncSequence<T>` | `subscribe()` 또는 `AsyncIterable<T>` |
| 호출자 취소 | `Future.cancel`·Scope 정책 | Coroutine 취소 | `Task` 취소 | `AbortSignal` |
| 오류 | `SdkException` | Exception·Sealed Result | `SDKError` | `WebSdkError` |
| 자원 종료 | `close()` | `close()`·Scope 종료 | 명시적 종료·수명 소유자 | `close()`·Unsubscribe |

중요한 것은 네 API가 같은 철자를 갖는지가 아니라 다음 질문에 같은 답을 하는지입니다.

- 입력 검증은 어느 시점에 실패하는가?
- 취소가 로컬 대기만 끝내는가, 서버 업무도 중단하는가?
- Timeout 후 같은 요청을 안전하게 다시 보낼 수 있는가?
- 성공 응답의 알 수 없는 필드를 버려도 되는가?
- 같은 오류 Code를 네 SDK가 같은 분류로 노출하는가?

<h2 id="ai-section-4" style="scroll-margin-top: 72px;">4. JSON과 언어 Type의 경계를 명시한다</h2>

플랫폼 차이에서 가장 자주 생기는 장애는 복잡한 Algorithm보다 평범한 타입 변환입니다.

### 큰 정수와 소수

Java·Kotlin의 `Long`과 Swift의 `Int64`는 64bit 정수를 표현할 수 있지만 JavaScript `Number`는 모든 64bit 정수를 정확하게 표현하지 못합니다. 따라서 다음 값은 숫자가 아니라 불투명한 문자열로 정의하는 편이 안전합니다.

- 업무 ID와 Revision
- Event Sequence
- 64bit 범위의 Counter
- 반올림이 허용되지 않는 금액·고정밀 소수

```json
{
  "sessionId": "session-example",
  "sequence": "9007199254740993",
  "amount": "1234567890.123456"
}
```

SDK가 편의를 위해 문자열 ID를 숫자로 바꾸거나 앞의 `0`을 제거해서는 안 됩니다. ID는 계산 대상이 아니라 비교·전달 대상입니다.

### 누락과 null

다음 두 JSON은 같은 뜻이 아닐 수 있습니다.

```json
{
  "displayName": null
}
```

```json
{}
```

특히 PATCH에서는 세 상태가 필요합니다.

| Wire 상태 | 의미 예 |
|---|---|
| 필드 누락 | 기존 값을 변경하지 않음 |
| 명시적 `null` | 기존 값을 제거 |
| 값 존재 | 새 값으로 변경 |

Java의 `Optional<T>` 하나나 Kotlin·Swift의 Nullable Type 하나만으로는 “누락”과 “명시적 null”을 동시에 표현하기 어렵습니다. `Absent | Null | Value<T>` 형태의 Patch 전용 Type을 두는 편이 명확합니다.

### Enum과 미래 값

서버가 Enum 값을 추가하는 것은 Schema 관점에서 작은 변경처럼 보여도, 생성된 Client의 Exhaustive Switch를 깨뜨릴 수 있습니다.

```text
Known(READY)
Known(FAILED)
Unknown("PAUSED_BY_POLICY")
```

알 수 없는 값을 즉시 Parsing Error로 만들기보다 Raw Value를 보존하는 `Unknown` 경로를 마련합니다. 단, 보안상 허용 목록 외 값을 거부해야 하는 입력 Enum과 미래 호환성을 위한 출력 Enum은 정책을 분리해야 합니다.

이 권고는 **타입에 미지 값의 자리를 만들어 두는 일**을 전제합니다. 자리가 없으면 값은 어딘가에서 접힙니다. 필자가 만든 SDK 들에서 그 접힘이 세 형태로 나타났습니다. 세 코드에서 공통으로 확인되는 결과는 **원문을 표현할 수 없는 더 좁은 타입으로 옮길 때 미지 값을 독립적으로 보존하지 못한다**는 점이었습니다.

아래 예제의 숫자는 모두 **공개용 합성 값**입니다.

**첫째, 닫힌 리터럴 Union.** 허용 목록 밖 값을 정적으로 막으려고 리터럴로 닫으면, 그 타입을 쓰는 검사 범위에서는 목록 밖의 값을 **별도 처리 없이 표현할 수 없습니다.**

```typescript
// 공개용 합성 값. 오타는 정적으로 막히지만 목록 밖 값을 담을 자리가 없다.
export type ExampleErrorCode = 7101 | 7102 | 7103
```

TypeScript 타입은 런타임에 사라지므로 이 선언 자체가 서버 응답을 검증하지는 않습니다. 막아 주는 것은 **우리 코드가 그 타입으로 값을 다룰 때**입니다.

**둘째, Nullable 로 접기.** Wire 값에서 Enum 으로 되돌리는 함수가 미지 값에 `null` 을 돌려주면, 호출자는 그 반환값만으로는 "값이 없음"과 "모르는 값"을 구분할 수 없고, 원본 문자열은 반환값에 남지 않습니다.

```dart
/// 미지 값이면 null. 원본 문자열은 보존되지 않는다.
static SocialType? fromValue(String? value) {
  if (value == null) return null;
  for (final v in SocialType.values) {
    if (v.value == value) return v;
  }
  return null;
}
```

이 함수는 값을 **거부**하는 것이 아니라 `null` 을 돌려줄 뿐입니다. 거부로 만들려면 호출자가 `null` 을 검증 오류로 해석해야 하고, 그 규칙은 함수 밖에 있습니다.

**셋째, 센티넬로 접기.** 문자열로 오는 결과 코드를 정수로 좁히면서 실패 시 고정값을 쓰면, 서로 다른 원문이 한 값으로 합쳐집니다.

```dart
// 공개용 합성 센티넬. 파싱 불가 입력이 하나의 값으로 합쳐진다.
const int unparsedResultCode = -900;

throw ApiException(
  statusCode: statusCode,
  code: int.tryParse(resultCode ?? '') ?? unparsedResultCode,
  message: message,
);
```

여기서 정확히 짚을 것이 있습니다. **새로 추가된 코드가 숫자 문자열이면 그대로 보존됩니다.** 센티넬로 합쳐지는 것은 값이 누락됐거나 빈 문자열이거나 정수로 읽을 수 없는 형식일 때입니다. 즉 위험은 "새 코드를 못 받는다"가 아니라 **"서로 다른 이유의 실패가 같은 값으로 보고된다"** 는 쪽입니다. 업무 성공·실패를 HTTP 상태가 아니라 본문의 결과 코드로 판정하는 API 라면 이 좁힘이 실패 분류의 핵심 경로가 되므로 더 눈에 띕니다.

📌 세 사례가 가리키는 결론은 이 절이 이미 말한 두 가지 — **출력의 미지 값은 원문과 함께 보존하고, 입력과 출력의 정책을 분리한다** — 와 같습니다. 새로 덧붙일 것은 **변환 함수를 방향별로 나눠 두라**는 실행 지침입니다. 하나로 합쳐 두면 방향마다 반대인 정답 중 한쪽이 손해를 보고, 정책을 바꿀 때 양쪽이 함께 움직입니다.

ℹ️ 위 사례는 **개별 SDK 의 코드**에서 가져온 것이고, 이 글이 설명하는 네 SDK 공통 계약이 구현·검증됐다는 증거는 아닙니다.

### 시간·Binary·Unicode

| 항목 | 권장 계약 |
|---|---|
| 시각 | RFC 3339 형식, UTC, Fractional Second 정책 명시 |
| 기간 | 단위가 붙은 정수 필드, 예: `timeoutMs` |
| Binary | Base64 또는 Base64url을 이름과 Schema에 명시 |
| Unicode | 비교·서명 시 정규화 여부를 별도 명시 |
| Map 순서 | 의미 없음. Hash·서명 입력일 때만 Canonicalization |

일반 API 응답 비교에 JSON 문자열의 공백·Key 순서까지 요구하면 테스트가 취약해집니다. JSON을 Parsing한 뒤 의미적으로 비교하고, Hash나 전자서명처럼 Byte 일치가 필요한 경계에서만 Canonical JSON을 적용해야 합니다.

<h2 id="ai-section-5" style="scroll-margin-top: 72px;">5. Schema와 실행 가능한 의미 규칙을 함께 관리한다</h2>

OpenAPI 3.1은 JSON Schema 기반으로 Request·Response 형식을 기술하는 데 유용합니다. 그러나 `readOnly`, `nullable`, `format` 같은 표기만 보고 각 Code Generator가 완전히 같은 Runtime 검증을 제공한다고 가정해서는 안 됩니다.

```yaml
components:
  schemas:
    Session:
      type: object
      additionalProperties: false
      required:
        - sessionId
        - status
        - createdAt
      properties:
        sessionId:
          type: string
          minLength: 1
        status:
          type: string
          enum: [PENDING, READY, FAILED]
        createdAt:
          type: string
          format: date-time
        displayName:
          type:
            - string
            - "null"
```

이 Schema 옆에는 실행 가능한 의미 규칙이 있어야 합니다.

```yaml
scenario: create-session-success
given:
  title: "합성 예시"
when:
  operation: createSession
then:
  result:
    status: PENDING
  invariants:
    - sessionId-is-opaque
    - createdAt-is-utc
    - request-id-is-propagated
```

Schema 통과는 계약 검증의 시작이지 끝이 아닙니다. 예를 들어 날짜 문자열이 형식상 유효해도 UTC로 정규화해야 한다는 규칙이나, Timeout이 업무 실패를 의미하지 않는다는 규칙은 별도의 Scenario가 검증해야 합니다.

<h2 id="ai-section-6" style="scroll-margin-top: 72px;">6. 안정적인 오류 Code와 원본 정보를 보존한다</h2>

HTTP 상태는 전송 계층의 큰 분류입니다. 고객사 업무 로직이 `400`이나 사람이 읽는 `detail` 문자열을 Parsing해 분기하면 서버 문구 변경만으로 Application이 깨집니다.

RFC 9457의 Problem Details 형식을 기반으로 안정적인 확장 필드를 둘 수 있습니다. HTTP 응답의 `Content-Type`은 `application/problem+json`으로 명시하고, `type` URI는 오류 유형을 식별하는 값으로 다룹니다.

```json
{
  "type": "https://errors.example.com/problems/invalid-argument",
  "title": "Request is invalid",
  "status": 400,
  "detail": "One or more fields are invalid",
  "instance": "/requests/req-example-001",
  "code": "INVALID_ARGUMENT",
  "retryable": false,
  "requestId": "req-example-001",
  "violations": [
    {
      "field": "/title",
      "code": "REQUIRED"
    }
  ]
}
```

각 필드의 역할을 분리합니다.

| 필드 | 용도 | Client 분기 사용 |
|---|---|---|
| `type` | 오류 유형 문서의 URI 식별자 | 가능 |
| `title` | 유형의 짧은 설명 | 표시 보조 |
| `status` | HTTP 상태 복사 | 큰 분류 |
| `detail` | 이번 발생의 사람이 읽는 설명 | 금지 |
| `instance` | 이번 발생 식별 | 추적 |
| `code` | SDK의 안정적인 업무 오류 Code | 권장 |
| `retryable` | 현재 응답 기준 재시도 Hint | 정책 입력 |
| `requestId` | 지원·Log 상관관계 | 추적 |
| `violations` | 필드별 검증 오류 | Form 연결 |

`detail`에는 Secret, Token, 내부 Host, Query 원문, Stack Trace를 넣지 않습니다. 또한 `retryable: true`라고 해서 SDK가 무조건 재시도해서는 안 됩니다. Method의 멱등성, Retry Budget, `Retry-After`, 호출 Deadline을 함께 확인해야 합니다.

### 모든 플랫폼이 원래 오류 정보를 보존한다

Wire 오류를 언어별 Exception으로 바꾸더라도 공통 정보가 사라지면 안 됩니다.

![Wire Envelope의 ID·Patch·Enum·오류를 공통 의미로 정규화한 뒤 Java·Kotlin·Swift·JavaScript Type으로 투영하면서 Raw 정보를 보존하는 구조](assets/blog-45-cross-platform-value-error-contract.png)

공통 오류 Model은 최소한 다음을 보존합니다.

- 안정적인 `code`
- HTTP 상태와 Response Header
- `retryable` Hint
- `requestId` 또는 Correlation ID
- 필드별 `violations`
- 알 수 없는 Extension
- 안전하게 정제된 원인 정보

다만 네 언어의 Public Type을 억지로 동일하게 만들 필요는 없습니다.

```text
Java       SdkException(code, status, requestId, retryable)
Kotlin     SdkException + ErrorCode.Known/Unknown
Swift      SDKError.service(ServiceProblem)
JavaScript WebSdkError extends Error
```

Network 단절, Caller 취소, Timeout, Protocol Parsing 실패, Service 오류도 구분합니다. 특히 Timeout은 “서버가 처리하지 않았다”는 증거가 아닙니다. Side Effect가 있는 Operation은 상태 조회 또는 같은 Idempotency Key를 이용한 재확인 경로가 필요합니다.


### 도메인별로 Code 대역을 나눈 뒤 겹치게 두면 컴파일러는 잡지 않는다

이 절의 권고를 따라 오류를 도메인별 타입으로 나누고 각 타입에 숫자 대역을 주는 구조는 흔합니다. 그런데 그 구조에는 **분리만 있고 결합이 없는** 상태가 쉽게 남습니다. 도메인별 Code 타입이 서로 독립되어 있으면, 서로 다른 도메인이 같은 숫자를 쓰거나 Key의 의미와 Message가 어긋나도 **각 선언은 정상적으로 컴파일됩니다.**

아래는 그 구조적 위험을 보여 주는 **공개용 합성 예시**입니다.

```typescript
// 공개용 합성 값. 두 선언이 같은 숫자를 서로 다른 뜻으로 쓴다.
export type UploadErrorCode = 8201 | 8202 | 8203
export type SessionErrorCode = 8201 | 8202
```

타입이 다르므로 이것은 **타입 오류가 아닙니다.** 예외 클래스로 갈라 받는 코드는 정상 동작합니다. 깨지는 곳은 **숫자만 남는 자리**입니다.

- Log나 지표가 도메인 없이 `code`만 저장한다면 서로 다른 두 오류가 한 칸에 합쳐질 수 있습니다.
- 지원 창구에서 "오류 8201"이라는 말이 두 가지를 뜻할 수 있습니다.
- Client가 `code` 숫자만으로 재시도를 판단하면 두 도메인의 정책이 섞입니다.

한 겹이 더 있습니다. Key·Code·Message를 **세 개의 독립 선언**으로 두는 형태입니다.

```typescript
// 공개용 합성 예시. 세 선언을 묶어 주는 것이 없다.
export enum UploadErrorMessage { SIZE_EXCEEDED = 'File size exceeds the limit' }
export type UploadErrorKey = 'SIZE_EXCEEDED'
export type UploadErrorCode = 8201
```

세 선언을 서로 묶어 주는 장치가 없으므로 **짝이 어긋나도 컴파일이 통과합니다.** 값을 복사해 새 도메인을 만들 때 문구만 이전 도메인의 것으로 남는 사고가 이 형태에서 나옵니다. 세 선언이 각각 문법적으로 옳고 **조합만 틀린** 상태이므로, **TypeScript 컴파일러만으로는 잡을 수 없습니다.** 중앙 Registry에서 타입을 파생하거나, 정적 검사와 Test로 유일성·일대일 대응을 검증해야 합니다.

📌 분리 자체는 옳습니다. 다만 **분리에는 결합 장치가 따라와야 합니다.** 실행 지침은 두 가지입니다.

1. **대역을 코드 한 곳이 소유합니다.** 도메인별 선언이 각자 숫자를 고르면 겹침은 시간문제입니다. 대역 배정표를 한 파일에 두고 각 도메인이 그 안에서만 고르게 합니다. 겹침 자체를 Test로 검사하려면 배정표가 먼저 있어야 합니다.
2. **`(Key, Code, Message)` 목록을 Vector로 고정합니다.** [11절](#ai-section-11)의 Golden Vector는 요청·응답에만 쓰는 것이 아닙니다. 다만 목록을 Vector로 두는 것만으로는 부족하고, **Code의 전역 유일성과 세 값의 일대일 대응을 검사하는 Assertion**을 Release Gate에 함께 둬야 빨간불이 켜집니다.

<h2 id="ai-section-7" style="scroll-margin-top: 72px;">7. 상태를 Boolean이 아닌 전이 규칙으로 정의한다</h2>

`isLoading`, `hasData`, `hasError`, `isClosed` Boolean을 독립적으로 두면 불가능한 조합이 생깁니다. 공통 상태 계약은 Discriminated State와 전이 규칙으로 정의합니다.

```text
Idle
Loading(previous?)
Ready(value, revision)
Failed(problem, previous?)
Closed(reason)
```

다음 정책도 함께 고정해야 합니다.

- 새로 고치는 동안 이전 값을 유지하는가?
- 실패 시 이전 성공 값을 함께 노출하는가?
- `Closed` 뒤 재사용이 가능한가?
- 같은 Revision Event를 다시 받으면 상태를 갱신하는가?
- Local Cache가 오래됐음을 어떤 필드로 표현하는가?

초기 Loading이 취소되면 `Idle`로 돌아갈 수 있지만, 이전 값이 있는 Refresh가 취소되면 그 값을 가진 `Ready`로 돌아갑니다. Kotlin `StateFlow`, Swift Observable Model, React Store가 서로 다른 UI 수명을 갖더라도 같은 입력 Sequence에 대해 같은 논리 상태로 끝나야 합니다.

<h2 id="ai-section-8" style="scroll-margin-top: 72px;">8. Event 전달과 Snapshot 재연결 계약을 연결한다</h2>

이벤트의 JSON 모양만 공유하고 전달 보장을 정의하지 않으면 SDK마다 다른 동작을 하게 됩니다.

AsyncAPI 3.x는 Message 중심 API의 Channel, Operation과 Message를 기술하는 데 사용할 수 있습니다. CloudEvents 형식을 활용하면 Event의 공통 Metadata를 일관되게 구성할 수 있습니다.

```json
{
  "specversion": "1.0",
  "id": "evt-example-001",
  "source": "/sessions",
  "type": "com.example.session.status-changed.v1",
  "subject": "sessions/session-example",
  "time": "2026-07-31T03:00:00Z",
  "datacontenttype": "application/json",
  "dataschema": "https://schemas.example.com/session-status-v1.json",
  "sequence": "42",
  "aggregateRevision": "7",
  "data": {
    "status": "READY"
  }
}
```

CloudEvents의 필수 Context Attribute인 `id`, `source`, `specversion`, `type`을 사용하고, 업무상 필요한 `sequence`와 `aggregateRevision`은 Extension으로 명시합니다. 큰 숫자의 플랫폼 차이를 피하기 위해 Sequence도 문자열로 전송합니다.

이벤트 계약에는 다음 항목이 반드시 들어가야 합니다.

| 항목 | 결정 예 |
|---|---|
| 전달 보장 | At-least-once |
| 중복 판별 | `source + id` |
| 순서 보장 범위 | 같은 `subject` 안에서만 |
| 누락 탐지 | `aggregateRevision` 증가 |
| 재연결 | 마지막 확인 Cursor부터 재개 |
| 보존 기간 | 서버 정책으로 명시 |
| 오래된 Cursor | Snapshot 재조회 후 새 Cursor 발급 |
| 느린 소비자 | Buffer 한도와 Overflow 정책 |

### 재연결은 Snapshot과 Event를 연결해야 한다

Mobile App은 Background 진입, Network 전환과 절전 때문에 연결이 끊깁니다. Browser도 Tab 수명과 Proxy Timeout의 영향을 받습니다. 단순히 “자동 재연결”한다고 쓰는 것만으로는 충분하지 않습니다.

![Snapshot의 상태·Revision·Cursor를 Event Stream과 연결하고 중복 제거·Revision Gap 탐지 후 상태 갱신 또는 Snapshot 재조회로 복구하는 흐름](assets/blog-45-state-event-recovery.png)

안전한 재연결 흐름은 다음과 같습니다.

1. Snapshot과 재개 Cursor를 함께 받습니다.
2. Cursor 이후 Event를 구독합니다.
3. `source + id` 또는 계약된 Key로 중복을 제거합니다.
4. Revision Gap을 발견하면 Snapshot을 다시 조회합니다.
5. 너무 오래된 Cursor가 거부되면 처음부터 복구 절차를 수행합니다.

중복 제거 기록은 무한히 쌓지 않고 Event 보존 기간·Cursor 수명·Revision 정책에 맞춘 유한 Window로 관리합니다. Window 밖의 정합성은 Snapshot Revision으로 다시 확인합니다.

SDK가 Event를 영구 저장소처럼 취급해서는 안 됩니다. 최종 상태의 진실의 원천은 조회 API이며, Event는 상태 변화의 신속한 전달 수단입니다.

<h2 id="ai-section-9" style="scroll-margin-top: 72px;">9. Cursor와 관측 문맥을 불투명하게 유지한다</h2>

Pagination Cursor를 Base64로 보이는 Offset 정도로 간주해 Client가 Parsing하면 서버 구현을 바꿀 수 없습니다.

```json
{
  "items": [
    {
      "sessionId": "session-example"
    }
  ],
  "nextCursor": "cursor-example-opaque",
  "hasMore": true
}
```

Cursor 계약은 다음처럼 단순해야 합니다.

- SDK와 고객 Application은 Cursor를 Parsing·수정하지 않습니다.
- Cursor는 요청 조건과 연결될 수 있으므로 다른 Filter에 재사용하지 않습니다.
- 만료될 수 있으며, 만료 오류는 안정적인 Code로 반환합니다.
- `nextCursor` 누락, `null`, 빈 문자열 중 하나의 종료 표현만 선택합니다.
- Page Size는 서버가 상한을 적용할 수 있습니다.

네 SDK가 Pagination Helper를 제공하더라도 자동으로 모든 Page를 Memory에 모으는 방식만 제공해서는 안 됩니다. Server는 Iterator·Publisher, Mobile은 Flow·AsyncSequence, Web은 Async Iterable처럼 점진 소비 경로를 제공할 수 있습니다.

### Request ID와 분산 추적 Context를 혼동하지 않는다

운영 문제를 네 SDK에서 같은 사건으로 추적하려면 상관관계 계약이 필요합니다.

| 값 | 역할 | 생성·신뢰 |
|---|---|---|
| `requestId` | 고객 지원과 Application Log 상관관계 | Edge에서 검증·생성 |
| `traceparent` | W3C Trace Context 전파 | 신뢰 경계에서 정책 적용 |
| `tracestate` | Vendor별 Trace 정보 | 크기·허용 정책 필요 |
| `idempotencyKey` | Side Effect 중복 방지 | Operation Scope |
| `event.id` | Event 중복 판별 | Event Producer |

W3C Trace Context의 `traceparent`와 `tracestate`는 서비스 간 Trace를 연결하는 표준 Header입니다. 그러나 외부에서 받은 값에 무제한 신뢰를 부여하거나 이를 Tenant·Actor 인가 근거로 사용해서는 안 됩니다. 신뢰 경계에서 길이·형식을 검증하고 Sampling·전파 정책을 적용합니다.

<h2 id="ai-section-10" style="scroll-margin-top: 72px;">10. 변경 가능성과 호환성 정책을 계약에 포함한다</h2>

“필드를 추가했을 뿐”이라는 설명은 소비자에게 항상 호환 변경을 뜻하지 않습니다.

| 변경 | 잠재 영향 | 기본 판단 |
|---|---|---|
| 선택 출력 필드 추가 | 알 수 없는 필드를 거부하는 Client | 조건부 호환 |
| 필수 입력 필드 추가 | 기존 Client가 값을 보낼 수 없음 | Breaking |
| 출력 Enum 값 추가 | Exhaustive Switch 실패 | 조건부 호환 |
| 숫자에서 문자열로 변경 | Parser와 Model 변경 | Breaking |
| `null` 허용 추가 | Non-null Model 실패 | Breaking 가능 |
| 오류 Code 추가 | Unknown 처리 없으면 실패 | 조건부 호환 |
| Event 필수 필드 제거 | 소비자 Parsing 실패 | Breaking |
| Event Type v2 추가 | 별도 구독·병행 가능 | 병행 정책 필요 |

Forward Compatibility를 위해 SDK는 기본적으로 알 수 없는 **출력 필드**를 무시할 수 있어야 합니다. 반면 사용자가 보내는 **입력 필드**는 오타와 보안 문제를 발견하기 위해 엄격하게 검증할 수 있습니다.

Event의 의미가 바뀌면 기존 `type`을 조용히 재정의하지 않고 새 Version의 Type이나 Schema를 병행합니다. 구체적인 SemVer, 폐기 기간과 Package Release Gate는 다음 글에서 다룹니다.

<h2 id="ai-section-11" style="scroll-margin-top: 72px;">11. Golden Vector는 합의된 명세에서 만든다</h2>

Java 구현의 Serialization 결과를 저장하고 나머지 SDK가 그대로 따라가게 하면 Java의 우연한 동작이 계약이 됩니다. Golden Vector는 구현이 아니라 합의된 명세에서 생성·검토해야 합니다.

```text
vectors/
├── valid/
│   ├── session-minimal.json
│   ├── session-null-display-name.json
│   ├── unknown-output-enum.json
│   ├── event-large-sequence.json
│   └── problem-invalid-argument.json
└── invalid/
    ├── missing-required-id.json
    ├── numeric-sequence.json
    ├── invalid-rfc3339-time.json
    └── malformed-problem.json
```

경계 Vector에는 다음을 포함합니다.

- JavaScript의 안전한 정수 범위를 넘는 Sequence 문자열
- 필드 누락과 명시적 `null`
- 빈 문자열과 공백만 있는 문자열
- 알려지지 않은 출력 Enum과 오류 Code
- UTC Offset과 Fractional Second 경계
- Unicode 조합 문자와 Emoji
- 중복 Event와 Revision Gap
- 정의되지 않은 추가 입력 필드
- 잘못된 Problem Details와 Content Type
- 취소 직전·직후 도착한 성공 응답

일반 JSON Vector는 Key 순서나 공백이 아니라 Parsing 후 의미 값으로 비교합니다. 반면 서명·Hash 입력처럼 Byte가 계약인 경우에는 별도의 Canonicalization 규칙과 Byte Vector를 사용합니다.

앞선 [폴리글랏 보안 계약 검증 글](https://aiarchitect.tistory.com/34)은 Java와 Python 사이의 서명·Canonical Byte 일치를 다뤘습니다. 이번 글의 Golden Vector는 그보다 넓은 공개 SDK 의미 적합성을 다루며, 모든 JSON에 Byte 일치를 강제하지 않는다는 점이 다릅니다.

<h2 id="ai-section-12" style="scroll-margin-top: 72px;">12. 같은 Fixture를 네 SDK에 독립 실행한다</h2>

적합성 테스트의 핵심은 하나의 Runner로 네 SDK를 흉내 내는 것이 아닙니다. 각 언어의 실제 Public API와 실제 Serializer를 사용해 같은 Contract Fixture를 실행하는 것입니다.

![Contract Manifest와 Provider Test Server가 같은 Schema·Scenario·Golden Vector를 Java·Kotlin·Swift·JavaScript Runner에 독립 실행하고 통합 적합성 Report를 만드는 구조](assets/blog-45-conformance-matrix.png)

Test Server는 단순 Mock 응답만 제공하지 않고 계약된 실패 상황을 재현해야 합니다.

| Test 계층 | 검증 내용 |
|---|---|
| Schema Validation | Request·Response·Event가 Schema와 일치 |
| Codec Test | JSON과 언어 Model 간 변환 |
| Semantic Scenario | 같은 입력에서 같은 상태·오류 의미 |
| Transport Fault | Timeout·단절·잘못된 Content Type |
| Cancellation | 호출자 취소와 늦은 응답 Race |
| Event Recovery | 중복·순서 역전·Gap·재연결 |
| Negative Test | 잘못된 입력과 알 수 없는 값 |
| Package Smoke | 실제 배포 Artifact에서 Public API 사용 |

Kotlin Test가 JVM의 Java Model을 직접 호출하거나 Swift Test가 미리 변환한 Fixture만 읽으면 실제 경계를 검증하지 못합니다. 각 SDK가 Wire Fixture를 직접 읽고 자신의 Public Model로 변환해야 합니다.

<h2 id="ai-section-13" style="scroll-margin-top: 72px;">13. Consumer Contract와 Provider 적합성을 함께 쓴다</h2>

Contract Testing은 하나의 도구로 끝나지 않습니다.

- 정적 Schema 검사는 구조적 Breaking Change를 빠르게 발견합니다.
- SDK 적합성 테스트는 네 언어의 해석 차이를 찾습니다.
- Pact 같은 Consumer-driven Contract Test는 실제 소비자가 의존하는 요청·응답 예를 Provider가 만족하는지 확인합니다.
- Provider Test는 실제 Service가 공식 계약을 구현하는지 검증합니다.
- End-to-End Test는 인증, Gateway, 배포 설정과 Network까지 확인합니다.

Consumer-driven Contract는 전체 OpenAPI의 모든 조합을 증명하지 않으며, E2E Test도 모든 경계 Vector를 빠르게 검증하기 어렵습니다. 서로 대체하기보다 실패를 찾는 층을 나눕니다.


### 집합 비교가 내는 것은 차이가 아니라 차이 후보다

필자는 앞서 말한 두 SDK 사이에서 위 층 중 가장 값싼 것부터 돌려 본 일이 있습니다. 소비자 SDK의 **경로 상수 파일**에서 `(HTTP Method, 경로)` 를 추출해, 중계 SDK의 **표면 목록 문서**와 대조했습니다. 경로의 파라미터 이름을 지운 뒤 집합으로 비교하는, 스크립트 몇 줄짜리 대조입니다.

검증 문서에는 당시 예상도 함께 남겼습니다 — **"차이는 없을 것 같다."** 예상을 적어 두지 않으면 결과가 나온 뒤에 "그럴 줄 알았다"와 "운이 좋았다"를 구별할 수 없습니다.

집합 비교는 표면 차이 후보를 냈고, 호출 지점을 확인하니 **실행 경로 GAP 관점에서는 모두 오탐**이었습니다. 원인은 두 가지였습니다.

| 오탐의 원인 | 실제 코드 | 왜 집합 비교가 잡았나 |
|---|---|---|
| Helper 함수가 경로를 조립한다 | 상수에는 **기본 경로만** 두고, 실제 경로는 같은 파일의 Helper가 파라미터를 붙여 만든다 | 스크립트는 상수 문자열만 읽으므로 실제 호출 경로와 정규화된 짝이 맞지 않는다 |
| 죽은 상수가 남아 있다 | 정의는 있지만 **호출처가 없다** | 호출되지 않는 표면도 상수 목록에는 들어 있다 |

두 원인 모두 **스크립트가 상수를 읽는 데서 끝났기 때문에** 생겼습니다. Helper가 무엇을 조립하는지, 상수가 실제로 호출되는지는 스크립트가 답하지 못했고, 사람이 호출처를 열어 확인했습니다.

실행 경로가 끊긴 자리는 없었고 예상이 맞았습니다. 다만 후보 중 하나는 소비자 SDK 내부의 **미사용 상수 정리 후보**였으므로, "오탐"이 곧 "코드에 아무 문제도 없었다"는 뜻은 아닙니다.

📌 여기서 얻은 것은 "대조가 무의미하다"가 아니라 **판정 단계를 분리해야 한다**는 것입니다. 집합 비교는 확인해야 할 자리를 몇 곳으로 좁혀 줬습니다. 그 자리들이 실제 차이인지는 **호출 지점을 열어야** 알 수 있었고, 그 판정은 자동화되지 않았습니다. 이 절이 층을 나누라고 말하는 이유가 같습니다 — 값싼 층은 후보를 좁히고, 비싼 층은 판정합니다. 값싼 층의 출력을 결론으로 읽으면 없는 결함을 고치게 됩니다.

부수 소득도 있었습니다. 양쪽 대조가 계기가 되어 소비자 SDK 내부의 **미사용 상수 후보**도 확인했습니다. 이것은 교차 비교 자체가 증명한 결과라기보다, 후보의 호출처를 추적하는 추가 점검에서 나온 부수 발견입니다 — 같은 상수는 그 SDK 하나만 검색해도 찾을 수 있습니다. 📌 값싼 대조의 진짜 소득은 **어디를 열어 볼지 정해 준다**는 데 있습니다.

<h2 id="ai-section-14" style="scroll-margin-top: 72px;">14. CI에서 호환성과 적합성을 Release 조건으로 만든다</h2>

계약 문서를 검토했어도 Package Release가 이를 우회하면 의미가 없습니다. 계약 변경과 SDK Release를 CI Gate로 연결합니다.

![계약·SDK 변경이 Spec Lint와 호환성 Diff, Golden Vector·네 SDK Runner·Provider·Consumer·실제 Package Smoke를 거쳐 Release 또는 Block으로 분기되는 증거 Gate](assets/blog-45-contract-release-gate.png)

권장 Release Gate는 다음 순서입니다.

1. OpenAPI·AsyncAPI·JSON Schema 문법과 Lint를 검사합니다.
2. 이전 계약 Version과 Diff해 Breaking 후보를 분류합니다.
3. 모든 Positive·Negative Golden Vector를 검증합니다.
4. Java·Kotlin·Swift·JavaScript Runner를 독립 실행합니다.
5. Provider가 같은 계약을 구현하는지 확인합니다.
6. 실제 JAR·AAR·Swift Package·npm Tarball로 Smoke Test를 수행합니다.
7. 호환성 표와 변경 내역이 갱신된 경우에만 Release합니다.

OS나 Toolchain 제약으로 모든 Runner를 한 Build Machine에서 실행하기 어렵다면 결과를 Contract Version과 Commit SHA로 묶어 집계합니다. 일부 플랫폼이 실패하거나 실행되지 않은 상태를 전체 성공으로 표시해서는 안 됩니다.


### 실행 실패는 빨간불로 보이지만 검사기의 사각지대는 초록불로 보인다

위 Gate와 그 뒤 문단의 핵심은 **실패와 미실행을 성공으로 세지 않는 것**입니다. 다만 그 앞에 한 칸이 더 있습니다 — **검사기가 무엇을 보지 못하는지**입니다. 실행되지 않은 Runner는 목록에서 비어 보이지만, 검사기가 인식하지 못하는 패턴은 **통과로 보입니다.**

필자가 두 SDK의 표면을 대조할 때 쓴 1차 추출 스크립트는 소비자 SDK의 **경로 상수만** 읽었습니다. 같은 파일의 Helper 함수는 스크립트가 해석하지 않고, 차이 후보가 나온 뒤 호출처를 열어 사람이 확인했습니다.

그래서 서비스 계층이 URL 문자열을 직접 박아 호출하는 코드가 있으면 그 호출은 소비자 쪽 추출에서 빠집니다. 🔴 다만 여기서 정확히 짚을 것이 있습니다 — **빠졌다고 곧바로 "차이 없음"이 되지는 않습니다.** 중계 쪽 표면 목록에 대응 항목이 있으면 그것이 "중계에만 있는 후보"로 잡힙니다. 결과가 조용히 통과로 보이는 것은 **양쪽 추출에서 모두 빠질 때**입니다. 이 한계는 검증 문서에도 적어 뒀습니다.

같은 문서에 제외 범위도 적었습니다.

| 제외한 것 | 그때의 사유 | 사유의 유효 조건 |
|---|---|---|
| 요청 본문의 필드 단위 대조 | 별도 작업 규모 | ⚠️ 별도 검증 과제로 추적되고 Release 결과에 미검증 영역으로 표시되는 동안만 |
| 응답 Schema 대조 | 중계 SDK가 응답을 해석하지 않고 통과시키므로 영향이 적다 | 🔴 **그 SDK가 통과 계층인 동안만** |

📌 두 번째 줄이 중요합니다. 제외 사유가 **구현 구조에 의존**하고 있습니다. 그 SDK에 강타입 응답 Model을 도입하는 순간 "해석하지 않으므로 영향이 적다"는 근거가 사라지고, 응답 Schema 대조는 제외가 아니라 누락이 됩니다. 그런데 제외 결정만 적어 두면 그 전환 시점에 아무 신호도 울리지 않습니다.

그래서 제외 항목에는 사유만이 아니라 **사유가 무효가 되는 조건**을 함께 적는 편이 낫습니다. Release Gate의 결과표에 "검사하지 않은 영역"을 한 칸으로 항상 표시하면, 초록불이 "전부 통과"가 아니라 "정의된 범위 안에서 통과"로 읽힙니다.

<h2 id="ai-section-15" style="scroll-margin-top: 72px;">15. 계약 변경의 소유자와 완료 기준을 정한다</h2>

공통 계약은 문서 파일이 아니라 여러 팀의 변경 경계입니다.

| 역할 | 책임 |
|---|---|
| Contract Owner | 의미·호환성 판단과 최종 승인 |
| API Provider Owner | 실제 Service 적합성 |
| SDK Owner | 플랫폼 투영과 Package 품질 |
| Consumer Representative | 실제 사용 시나리오와 Migration 검증 |
| Release Manager | Matrix·Artifact·공지 일치 확인 |

계약 변경 Pull Request에는 최소한 다음이 포함돼야 합니다.

- 변경 이유와 영향받는 Operation
- 이전·새 Schema Diff
- 호환성 판정과 근거
- 추가·수정된 Positive·Negative Vector
- 네 SDK와 Provider 적합성 결과
- Migration 또는 Deprecation 계획
- 보안·개인정보·관측성 영향

“모든 SDK Build 성공”만으로는 완료가 아닙니다. 고객사가 사용 중인 계약 Version과 새 SDK의 조합이 호환성 표에 기록되고, 실제 배포 Package로 검증돼야 합니다.


### 계약 저장소가 없던 당시, "완료"의 정의는 체크리스트에 있었다

필자는 앞서 말한 두 SDK — 소비자 쪽과 중계 쪽 — 에 한 계약 변경을 **짝으로** 반영하는 일을 반복한 적이 있습니다. 계약 저장소가 없었으므로 어느 한쪽만 바뀌면 그 순간 표면이 어긋났습니다. 그래서 도메인을 추가할 때 따라야 할 절차를 문서에 순서대로 적고, 그것을 **문서상 완료 확인 기준**으로 뒀습니다.

절차는 이런 모양이었습니다.

1. 중계 쪽에 Service를 추가하고, 요청 본문이 있으면 요청 Model도 추가한다.
2. **컴파일을 통과시킨다.**
3. 중계 쪽 표면 목록 문서를 갱신한다.
4. 소비자 쪽에 경로 상수와 Service를 추가하고, 요청 Model·내부 입력 Model·의존성 등록·재노출 Index의 **필요 여부를 각각 확인해** 반영한다.
5. 두 저장소를 **한 쌍으로** 커밋한다.
6. 보류 카탈로그에서 해당 항목을 지우거나 도입 완료로 표시한다.

목록 자체는 특별하지 않습니다. 값을 한 것은 **4번의 범위**였습니다. 원본 체크리스트의 4번은 **새 도메인을 소비자 SDK에 노출할 때 확인할 여섯 종류의 자리**였습니다. 여기서 "여섯"은 **매번 고쳐야 하는 자리의 수가 아니라 필요 여부를 확인해야 하는 자리의 수**입니다. 기존 도메인에 호출 하나를 보탤 때는 경로 상수와 Service만 바뀌는 경우도 있었고, 새 도메인이라도 요청 본문이 없으면 요청 Model과 내부 입력 Model은 필요하지 않았습니다. 반면 의존성 등록과 재노출 경로는 새 도메인이면 거의 매번 확인해야 했습니다.

그리고 일부 누락은 **패키지 자체 컴파일만으로는 드러나지 않습니다.** 의존성 등록 누락은 실행 시점에, 재노출 누락은 소비자 쪽 빌드나 사용 시점에 발견될 수 있습니다.

이 목록은 처음부터 있었던 것이 아닙니다. 도메인을 여러 차례 추가한 **뒤에** 적었습니다. 반복해 보고서야 빠뜨리기 쉬운 자리가 어디인지 드러났고, 그다음에 순서로 굳었습니다.

📌 여기서 두 가지가 남았습니다.

- **완료 기준이 절차 문서로만 존재하면 그 절차의 준수 여부는 검증되지 않습니다.** 당시 이 체크리스트는 두 저장소를 함께 검증하는 CI Gate가 아니라 사람이 확인하는 절차였습니다. 이 절이 말하는 "완료 기준"은 문서에 적히는 것으로 끝나지 않고 [14절](#ai-section-14)의 Gate로 옮겨져야 합니다.
- **한 계약 변경이 손대야 하는 자리의 종류와 수가 설계 지표입니다.** 새 도메인이 여러 층을 함께 고쳐야 한다면 그 층마다 불일치 지점이 생길 수 있습니다. 계약에서 코드를 생성하는 쪽으로 가면 이 수가 줄고, 절차 문서가 필요한 이유도 함께 줄어듭니다.

⚪ 남겨 둔 항목도 함께 카탈로그에 적었습니다. 노출하지 않기로 한 표면을 **보류 사유와 함께** 목록으로 두면, 나중에 같은 표면을 다시 검토할 때 "왜 없는가"를 처음부터 조사하지 않아도 됩니다. 계약 저장소가 없는 상태에서 그 카탈로그가 사실상 **비목표 선언**의 역할을 했습니다.

<h2 id="ai-section-16" style="scroll-margin-top: 72px;">16. 구현·운영 체크리스트</h2>

### 공통 의미와 타입

- [ ] 공통 계약과 공통 구현을 구분했는가
- [ ] Operation의 성공·Side Effect·취소·Timeout 의미가 문서화됐는가
- [ ] ID·Revision·Sequence를 불투명한 문자열로 다루는가
- [ ] 필드 누락과 명시적 `null`을 구분하는가
- [ ] 알 수 없는 출력 Enum과 오류 Code를 보존하는가
- [ ] 시간대·정밀도·Binary Encoding·Unicode 정책이 명시됐는가
- [ ] 일반 JSON 의미 비교와 Canonical Byte 비교를 구분했는가

### 오류·상태·이벤트

- [ ] 고객 로직이 오류 `detail` 문자열로 분기하지 않는가
- [ ] Service 오류, Network, Timeout, 취소와 Parsing 오류를 구분하는가
- [ ] 상태를 Boolean 조합이 아닌 유효한 전이로 정의했는가
- [ ] Event 전달 보장·중복 Key·순서 범위가 문서화됐는가
- [ ] Snapshot·Cursor·재연결·Revision Gap 복구가 연결됐는가
- [ ] 느린 소비자와 Buffer Overflow 정책이 있는가
- [ ] Request ID와 Trace Context, Idempotency Key를 구분하는가

### 적합성 테스트와 Release

- [ ] 계약 원본과 Fixture의 진실의 원천이 하나인가
- [ ] 각 SDK가 자신의 실제 Public API와 Codec으로 Vector를 실행하는가
- [ ] Positive·Negative·경계 Vector가 함께 있는가
- [ ] Test Server가 지연·중복·잘못된 응답을 재현하는가
- [ ] Provider와 Consumer Contract 검증을 함께 수행하는가
- [ ] 실제 배포 Package Smoke Test가 있는가
- [ ] 호환성 Diff와 네 SDK 적합성 결과가 Release Gate인가
- [ ] 계약 Version과 SDK Version의 호환성 표를 관리하는가

<h2 id="ai-section-17" style="scroll-margin-top: 72px;">17. 마무리와 참고 자료</h2>

크로스플랫폼 SDK의 품질은 네 언어의 Method 이름을 얼마나 비슷하게 만들었는지로 결정되지 않습니다. **같은 입력과 같은 사건을 네 SDK가 같은 업무 의미로 해석하고, 그 사실을 반복 가능한 테스트로 증명하는가**가 핵심입니다.

이를 위해서는 다음 원칙이 필요합니다.

1. 의미 계약, Wire 계약, 플랫폼 투영과 적합성 Suite를 분리합니다.
2. 큰 숫자, 누락과 `null`, 미래 Enum, 시간과 Binary의 타입 경계를 명시합니다.
3. 오류는 안정적인 Code로 분기하고 원래 Problem 정보를 보존합니다.
4. 상태는 전이 규칙으로, Event는 중복·순서·재연결 의미까지 정의합니다.
5. Golden Vector는 특정 SDK의 우연한 출력을 정답으로 삼지 않습니다.
6. 네 SDK와 Provider가 같은 Fixture를 실제 Public API로 독립 실행합니다.
7. 호환성 Diff, 적합성 Report와 실제 Package 검증을 Release 조건으로 둡니다.

이 구조가 자리 잡으면 Java Server, Kotlin Android, Swift iOS와 React JavaScript가 각 플랫폼의 장점을 유지하면서도 하나의 서비스 계약으로 움직일 수 있습니다. 고객사는 원하는 UI와 Application 구조를 선택하고, 제공자는 프라이빗 API의 의미와 운영 품질을 플랫폼 전체에서 일관되게 지킬 수 있습니다.

---

### 함께 읽기

- [폴리글랏 보안 계약 검증: Java↔Python Golden Vector와 Canonical Byte](https://aiarchitect.tistory.com/34)
- [프라이빗 API를 보호하는 멀티플랫폼 SDK 아키텍처](https://aiarchitect.tistory.com/40)
- [프라이빗 API를 연결하는 Java Server SDK 설계](https://aiarchitect.tistory.com/41)
- [고객 맞춤형 Android 앱을 위한 Kotlin SDK](https://aiarchitect.tistory.com/42)
- [고객 맞춤형 iOS 앱을 위한 Swift SDK](https://aiarchitect.tistory.com/43)
- [고객 맞춤형 웹을 위한 React JavaScript SDK](https://aiarchitect.tistory.com/44)

### 공식 참고 자료

- OpenAPI Initiative, [OpenAPI Specification 3.1.0](https://spec.openapis.org/oas/v3.1.0)
- JSON Schema, [Draft 2020-12](https://json-schema.org/draft/2020-12)
- IETF, [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- AsyncAPI Initiative, [AsyncAPI Specification 3.0.0](https://www.asyncapi.com/docs/reference/specification/v3.0.0)
- Cloud Native Computing Foundation, [CloudEvents Specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md)
- W3C, [Trace Context](https://www.w3.org/TR/trace-context/)
- IETF, [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)
- Pact, [Introduction](https://docs.pact.io/)
- Pact, [Pact Specification](https://docs.pact.io/implementation_guides/pact_specification)

> 이 글은 공식 사양을 기반으로 한 일반화된 설계 예시입니다.
> 실제 적용 시에는 사용하는 OpenAPI·AsyncAPI·JSON Schema Version,
> 각 언어의 Serializer·Code Generator·Runtime, 고객사 API와 Event 전달 정책에 맞춘 별도 검증이 필요합니다.
