# 비동기 AI 요약 완료 상태 설계: Polling·Event와 Readiness Predicate

AI 요약 생성 API를 호출했습니다.

응답에는 `completed=false`가 들어 있지만 요약 본문은 이미 존재합니다.

이 요약을 사용자에게 보여 줘야 할까요?

반대로 `completed=true`, `summaryAvailable=true`인데 본문이 비어 있다면 완료로 처리해도 될까요?

```json
{
  "completed": false,
  "summaryAvailable": true,
  "summary": {
    "text": "결정 사항과 후속 작업이 포함된 기존 요약"
  }
}
```

이런 응답은 반드시 서버 오류라는 뜻은 아닙니다.

`completed`가 최신 재생성 작업을 나타내고, `summary`는 이전에 성공한 결과를 나타낸다면 두 값은 동시에 성립할 수 있습니다.

문제는 Client가 각 필드의 대상을 모른다는 점입니다.

```text
completed
  어떤 작업이 완료됐다는 뜻인가?

summaryAvailable
  어떤 Version의 결과가 존재한다는 뜻인가?

summary
  최신 입력과 정책으로 생성된 결과인가?
```

비동기 AI 기능의 완료 상태는 Boolean 하나로 결정할 수 없습니다.

이 글에서는 **작업 상태 (Job State)**와 **결과 준비 상태 (Result Readiness)**를 분리하고, Polling (주기적 조회)과 Event (이벤트 알림)가 같은 결론을 내리도록 API 계약을 설계하는 방법을 살펴보겠습니다.

## 1. `202 Accepted`는 완료 응답이 아니다

긴 요약 작업을 하나의 HTTP 연결에서 기다리게 하면 Client Timeout, Proxy Timeout과 불필요한 연결 점유가 발생할 수 있습니다.

그래서 서버는 요청을 접수하고 추적 가능한 작업 Resource를 반환할 수 있습니다.

```http
POST /v1/meetings/meeting_fixture_001/summaries
Idempotency-Key: summary_request_fixture_001
```

```http
HTTP/1.1 202 Accepted
Location: /v1/operations/operation_fixture_001
Content-Type: application/json
```

```json
{
  "operationId": "operation_fixture_001",
  "state": "QUEUED",
  "target": {
    "meetingId": "meeting_fixture_001",
    "transcriptVersion": 7
  }
}
```

RFC 9110의 `202 Accepted`는 요청이 처리 대상으로 받아들여졌지만 처리가 아직 끝나지 않았다는 의미입니다.

따라서 `202`를 받은 Client가 할 일은 “성공 화면 표시”가 아니라 다음 조회 위치와 상태 계약을 확인하는 것입니다.

```text
202 Accepted
  = 접수 성공

SUCCEEDED
  = 작업 실행 성공

READY
  = 사용할 수 있는 결과 준비
```

세 상태는 같지 않습니다.

## 2. 가장 먼저 작업과 결과를 다른 Resource로 본다

Google API Improvement Proposals의 Long-running Operations (장기 실행 작업) 패턴은 오래 걸리는 API가 최종 결과 대신 추적 가능한 Operation을 반환하도록 설명합니다.

이 관점을 AI 요약에 적용하면 다음 두 Resource를 분리할 수 있습니다.

```text
Summary Operation
  요약 생성 시도 한 번의 생명주기

Summary Result
  성공적으로 생성·검증·게시된 결과물
```

예를 들어 같은 회의에 여러 Operation이 존재할 수 있습니다.

```text
Meeting A
  ├─ Operation 101 → SUCCEEDED → Result Version 1
  ├─ Operation 102 → FAILED
  └─ Operation 103 → RUNNING
```

이때 사용 가능한 결과는 여전히 Version 1입니다.

최신 Operation 103이 실행 중이라는 이유로 Version 1을 무조건 숨길 필요는 없습니다.

반대로 Operation 102가 실패했다고 해서 “이 회의에는 요약이 없다”고 단정해서도 안 됩니다.

```text
Operation State
  최신 생성 시도가 어떻게 됐는가?

Result Readiness
  읽을 수 있는 결과가 존재하는가?
```

## 3. 완료 상태를 다섯 축으로 분리한다

AI 요약의 사용자 가용성을 판단하려면 최소한 다음 축을 구분해야 합니다.

| 축 | 질문 | 예시 |
|---|---|---|
| 작업 종료 (Terminal) | 생성 시도가 더 진행되는가? | `SUCCEEDED`, `FAILED` |
| 결과 존재 (Exists) | 결과 Record와 본문이 있는가? | `result != null` |
| 결과 검증 (Valid) | Schema·품질 검증을 통과했는가? | `validation=PASSED` |
| 최신성 (Current) | 현재 Transcript·정책 Version을 반영했는가? | Version 일치 |
| 접근 가능 (Accessible) | 현재 사용자가 읽을 권한이 있는가? | 객체 단위 인가 통과 |

이 축들을 하나의 `completed`에 넣으면 다음 상태를 표현할 수 없습니다.

- 최신 작업은 실패했지만 기존 결과는 사용 가능
- 결과는 존재하지만 과거 Transcript 기반
- 작업은 성공했지만 결과 검증 실패
- 결과는 정상이나 현재 사용자는 접근 불가
- 작업은 삭제됐지만 결과는 보존됨

따라서 내부와 API 계약에서 각 질문의 답을 따로 관리합니다.

## 4. Job State는 상호 배타적인 생명주기를 표현한다

Job State (작업 상태)는 한 시점에 하나만 선택되는 Lifecycle (생명주기) 값입니다.

```text
QUEUED
  → RUNNING
      ├─ SUCCEEDED
      ├─ FAILED
      └─ CANCELLED
```

필요하다면 다음 상태를 추가할 수 있습니다.

```text
WAITING_INPUT
RETRY_SCHEDULED
TIMED_OUT
SUPERSEDED
```

하지만 내부 구현 상태를 모두 외부에 공개할 필요는 없습니다.

Google AIP-216은 API State를 일관된 Enum으로 표현하고, 진행 중인 상태에는 `RUNNING` 같은 현재분사를, 완료된 Terminal State (종료 상태)에는 `SUCCEEDED`, `FAILED`, `CANCELLED` 같은 과거분사를 사용하는 기준을 제시합니다.

외부 Client에게 의미 있는 최소 상태는 다음 정도일 수 있습니다.

| 상태 | Terminal | 의미 |
|---|---:|---|
| `QUEUED` | 아니요 | 접수됐지만 실행 전 |
| `RUNNING` | 아니요 | Worker가 처리 중 |
| `SUCCEEDED` | 예 | 이 Operation의 실행 성공 |
| `FAILED` | 예 | 이 Operation의 실행 실패 |
| `CANCELLED` | 예 | 취소돼 더 진행하지 않음 |
| `SUPERSEDED` | 예 | 더 최신 Operation으로 대체됨 |

새 상태가 추가될 가능성도 계약에 포함합니다.

Client가 `state !== RUNNING`이면 모두 성공이라고 가정하지 않도록 Terminal 여부와 성공 여부를 명시적으로 판정해야 합니다.

## 5. Result는 생명주기보다 Version과 Condition이 중요하다

결과 Resource는 “생성 중”인 Job과 다른 질문에 답해야 합니다.

```json
{
  "summaryId": "summary_fixture_003",
  "version": 3,
  "source": {
    "transcriptVersion": 7,
    "promptVersion": "summary_prompt_v5",
    "modelPolicyVersion": "model_policy_v4"
  },
  "conditions": [
    {
      "type": "Validated",
      "status": "True",
      "reason": "SchemaAndContentChecksPassed"
    },
    {
      "type": "Published",
      "status": "True",
      "reason": "ResultCommitted"
    }
  ],
  "body": {
    "text": "결정 사항과 후속 업무를 포함한 요약"
  }
}
```

Kubernetes의 Condition (조건) 모델은 하나의 Phase만으로 전체 상황을 표현하지 않고, 여러 측면의 상태를 `type`, `status`, `reason`, `message`, `lastTransitionTime` 등으로 나누는 예를 보여 줍니다.

AI 요약에도 같은 사고방식을 적용할 수 있습니다.

```text
Validated=True
Published=True
Current=False
```

이 결과는 사용할 수 있지만 최신 Transcript를 반영하지 않은 결과일 수 있습니다.

상태가 상호 배타적이라면 Enum을 사용하고, 동시에 여러 사실이 성립할 수 있다면 Condition을 사용합니다.

## 6. 준비 상태 판정식 (Readiness Predicate)을 코드로 명시한다

“요약이 준비됐다”는 문장을 자연어로만 남기면 화면, Agent와 Batch Job이 서로 다른 기준을 구현합니다.

도메인별 Readiness Predicate (준비 상태 판정식)를 하나의 함수로 정의합니다.

```javascript
function isUsableSummary(result) {
  if (!result) {
    return false;
  }

  const validated = result.conditions
    .some(condition =>
      condition.type === "Validated"
      && condition.status === "True"
    );

  const published = result.conditions
    .some(condition =>
      condition.type === "Published"
      && condition.status === "True"
    );

  return validated
    && published
    && typeof result.body?.text === "string"
    && result.body.text.trim().length > 0;
}
```

중요한 점은 Job State를 이 함수에 넣지 않았다는 것입니다.

기존 결과를 사용할 수 있는지 판정하는 함수와 최신 작업의 완료 여부는 별도입니다.

```javascript
function isTerminalOperation(operation) {
  return [
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "SUPERSEDED"
  ].includes(operation.state);
}
```

최신성도 별도 함수로 판정합니다.

```javascript
function isCurrentSummary(result, desired) {
  return result.source.transcriptVersion === desired.transcriptVersion
    && result.source.promptVersion === desired.promptVersion
    && result.source.modelPolicyVersion === desired.modelPolicyVersion;
}
```

이렇게 나누면 “사용 가능하지만 최신은 아님”을 표현할 수 있습니다.

## 7. `usable`, `current`, `generating`을 동시에 계산한다

Client가 실제로 필요한 값은 단순한 완료 여부가 아닙니다.

```json
{
  "readiness": {
    "usable": true,
    "current": false,
    "generating": true
  }
}
```

각 값의 의미는 다음과 같습니다.

| 필드 | 의미 |
|---|---|
| `usable` | 지금 화면이나 Agent 응답에 사용할 결과가 있음 |
| `current` | 현재 Transcript·Prompt·Model 정책을 반영함 |
| `generating` | 더 최신 결과를 만드는 Operation이 진행 중 |

다음 조합도 모두 유효합니다.

| usable | current | generating | 사용자 해석 |
|---:|---:|---:|---|
| `false` | `false` | `false` | 요약 없음 |
| `false` | `false` | `true` | 첫 요약 생성 중 |
| `true` | `true` | `false` | 최신 요약 사용 가능 |
| `true` | `false` | `true` | 기존 요약 표시·새 요약 생성 중 |
| `true` | `false` | `false` | 과거 Version 결과만 존재 |
| `true` | `true` | `true` | 정책상 동일 입력으로 재생성 중일 수 있음 |

Boolean 세 개를 무분별하게 늘리자는 뜻은 아닙니다.

서버 내부의 Source of Truth (기준 데이터)는 Operation과 Result Resource이며, 위 필드는 Client 편의를 위한 파생 값으로 계산해야 합니다.

## 8. `completed=false`, 결과 있음 상태를 정확히 해석한다

실제 연동 환경에서는 다음과 같은 응답을 만날 수 있습니다.

```json
{
  "completed": false,
  "summaryAvailable": true,
  "originalSummary": {
    "text": "사용 가능한 요약"
  }
}
```

이 응답만으로는 다음 중 무엇인지 알 수 없습니다.

```text
가설 A
  최신 Operation은 실행 중
  기존 Summary Result는 사용 가능

가설 B
  completed Flag 갱신이 지연됨
  본문은 최신 결과

가설 C
  서로 다른 Operation과 Result를
  하나의 응답에서 잘못 조합함
```

단기적인 Client 대응은 다음 판정이 될 수 있습니다.

```text
usableSummary =
  summaryAvailable == true
  AND originalSummary exists
  AND originalSummary.text is not blank
```

하지만 장기적으로는 다음 필드가 필요합니다.

- `operationId`
- `operation.state`
- `operation.targetTranscriptVersion`
- `result.summaryId`
- `result.sourceTranscriptVersion`
- `result.available`
- `result.validated`
- `result.createdAt`

어떤 Flag가 어떤 Resource와 Version을 설명하는지 명확해야 합니다.

## 9. 상태 조합표가 API 계약의 중심이다

상태 이름만 정의하고 조합별 행동을 정하지 않으면 Client마다 결과가 달라집니다.

| 최신 Job | 기존 결과 | 최신성 | 기대 화면 |
|---|---|---:|---|
| 없음 | 없음 | - | 요약 생성 가능 |
| `QUEUED` | 없음 | - | 요약 대기 중 |
| `RUNNING` | 없음 | - | 첫 요약 생성 중 |
| `SUCCEEDED` | 최신 결과 있음 | 예 | 최신 요약 표시 |
| `FAILED` | 없음 | - | 실패 원인·재시도 안내 |
| `FAILED` | 기존 결과 있음 | 아니요 | 기존 결과 표시·최신 생성 실패 안내 |
| `RUNNING` | 기존 결과 있음 | 아니요 | 기존 결과 표시·새 요약 생성 중 |
| `CANCELLED` | 기존 결과 있음 | 조건부 | 기존 결과 표시·재생성 취소 안내 |
| `SUPERSEDED` | 기존 결과 있음 | 조건부 | 더 최신 Operation 상태 조회 |
| `SUCCEEDED` | 결과 없음 | - | 상태 불일치 오류 |

마지막 조합은 정상 완료가 아닙니다.

```text
Operation = SUCCEEDED
Result = 없음
```

이 상태는 `RESULT_MISSING_AFTER_SUCCESS` 같은 일관성 오류로 기록하고 재조정 작업 (Reconciliation Job)의 대상에 넣습니다.

## 10. 최신성을 시간만으로 판단하지 않는다

`createdAt`이 가장 최근인 결과가 항상 최신 입력을 반영하는 것은 아닙니다.

분산 시스템에서는 Event 지연, 재처리와 Clock Skew (시계 오차)가 발생할 수 있습니다.

최신성을 판정할 때 생성 시간보다 입력 Version을 비교합니다.

```text
Summary Result
  transcriptVersion = 7
  promptVersion = v5
  modelPolicyVersion = v4

Desired State
  transcriptVersion = 8
  promptVersion = v5
  modelPolicyVersion = v4
```

이 결과는 가장 최근에 저장됐더라도 현재 Transcript Version 8을 반영하지 않았습니다.

Kubernetes의 `observedGeneration`은 상태가 어느 Generation의 Desired State를 관찰한 결과인지 연결하는 예입니다.

AI 요약에서도 비슷한 필드를 사용할 수 있습니다.

```json
{
  "desiredGeneration": 12,
  "observedGeneration": 11,
  "current": false
}
```

정확한 필드명보다 중요한 것은 **결과가 어떤 입력과 정책 Version을 관찰했는지 기록하는 것**입니다.

## 11. 재생성은 기존 결과를 덮어쓰지 않고 새 Version으로 만든다

사용자가 요약 재생성을 요청했다고 기존 결과를 즉시 삭제하면 새 작업이 실패했을 때 아무 결과도 남지 않습니다.

권장 흐름은 다음과 같습니다.

```text
Summary Version 3 = PUBLISHED

Regeneration Operation 104 = RUNNING
  └─ Target Summary Version 4

Version 4 검증·Commit 성공
  → Current Pointer를 Version 4로 전환
  → Version 3은 이력으로 보존
```

새 결과 게시 전까지 기존 Version을 제공할 수 있습니다.

```json
{
  "currentResult": {
    "version": 3,
    "usable": true,
    "current": false
  },
  "latestOperation": {
    "operationId": "operation_fixture_104",
    "state": "RUNNING",
    "targetVersion": 4
  }
}
```

전환은 하나의 Transaction 또는 원자적인 Pointer 변경으로 수행합니다.

## 12. 동시에 여러 재생성 요청이 들어오면 목표 Version을 고정한다

같은 회의에 재생성 요청이 동시에 들어올 수 있습니다.

```text
Operation A
  transcriptVersion = 7
  promptVersion = v5

Operation B
  transcriptVersion = 8
  promptVersion = v5
```

Operation A가 늦게 끝났다고 Current Result를 Version 7 기반 결과로 되돌리면 안 됩니다.

Commit 조건에 목표 Version을 포함합니다.

```sql
UPDATE meeting_summary_pointer
SET current_summary_id = 'summary_fixture_b',
    current_generation = 8
WHERE meeting_id = 'meeting_fixture_001'
  AND current_generation < 8;
```

영향받은 Row가 없다면 더 최신 결과가 이미 게시된 것입니다.

이 경우 늦게 도착한 결과를 이력으로 보존하거나 `SUPERSEDED`로 표시할 수 있지만 Current Pointer를 덮어쓰지 않습니다.

Timestamp보다 Generation·Version과 조건부 갱신을 사용해야 합니다.

## 13. Polling API는 Operation Resource를 조회한다

Polling (주기적 조회)은 구현이 단순하고 방화벽·Client 환경의 제약이 적습니다.

Client는 최종 Summary API를 무작정 반복하지 않고 Operation Resource를 조회합니다.

```http
GET /v1/operations/operation_fixture_001
```

처리 중 응답은 다음과 같습니다.

```json
{
  "operationId": "operation_fixture_001",
  "state": "RUNNING",
  "terminal": false,
  "metadata": {
    "stage": "MODEL_INFERENCE",
    "progressPercent": 70
  },
  "nextPollAfterMs": 3000
}
```

완료 응답은 결과 참조를 포함합니다.

```json
{
  "operationId": "operation_fixture_001",
  "state": "SUCCEEDED",
  "terminal": true,
  "resultRef": {
    "summaryId": "summary_fixture_004",
    "uri": "/v1/summaries/summary_fixture_004"
  }
}
```

실패 응답은 구조화된 오류를 포함합니다.

```json
{
  "operationId": "operation_fixture_001",
  "state": "FAILED",
  "terminal": true,
  "error": {
    "code": "CONTEXT_EXCEEDED",
    "retryable": false,
    "safeMessage": "요약 입력이 현재 처리 범위를 초과했습니다."
  }
}
```

Google의 Long-running Operations 패턴도 완료된 Operation이 성공 결과 또는 실행 오류를 구분해 제공하도록 정의합니다.

## 14. Polling 간격은 Client마다 추측하게 두지 않는다

모든 Client가 500ms마다 조회하면 실제 요약 처리보다 상태 조회가 더 큰 부하를 만들 수 있습니다.

서버가 권장 간격을 제공합니다.

```http
HTTP/1.1 200 OK
Retry-After: 3
ETag: "operation-revision-7"
```

또는 응답 본문에 명시할 수 있습니다.

```json
{
  "state": "RUNNING",
  "nextPollAfterMs": 3000
}
```

Client는 다음 원칙을 적용합니다.

- 서버의 권장 간격을 우선함
- 권장값이 없으면 Exponential Backoff (지수 백오프) 사용
- Jitter (무작위 지연)를 추가해 동시 Polling 집중 방지
- 최대 간격을 제한해 사용자 경험 유지
- Terminal State에 도달하면 Polling 종료
- 전체 Deadline을 넘으면 UI만 대기 종료하고 Operation은 별도 확인

```javascript
async function waitForOperation(operationId) {
  let delayMs = 1000;

  while (true) {
    const operation = await getOperation(operationId);

    if (operation.terminal) {
      return operation;
    }

    const serverDelay = operation.nextPollAfterMs;
    const baseDelay = serverDelay ?? delayMs;
    const jitter = Math.floor(Math.random() * 250);

    await sleep(baseDelay + jitter);
    delayMs = Math.min(delayMs * 2, 10000);
  }
}
```

실제 서비스에서는 사용자 취소, Client Deadline과 Network 오류 처리도 추가합니다.

## 15. ETag와 조건부 GET으로 변경이 없을 때 본문을 줄인다

Operation 상태가 몇 분 동안 바뀌지 않을 수 있습니다.

서버가 Revision 기반 ETag를 제공하면 Client는 조건부 GET을 사용할 수 있습니다.

```http
GET /v1/operations/operation_fixture_001
If-None-Match: "operation-revision-7"
```

상태가 변하지 않았다면 다음처럼 응답할 수 있습니다.

```http
HTTP/1.1 304 Not Modified
ETag: "operation-revision-7"
```

RFC 9110은 ETag를 Representation Validator (표현 검증자)로 정의하며, 조건부 GET은 변경되지 않은 표현의 전송을 줄이는 데 사용할 수 있습니다.

ETag는 Job State만이 아니라 Client가 받는 전체 표현의 Revision을 나타내야 합니다.

```text
state
progress
error
resultRef
updatedAt
```

이 중 하나가 바뀌면 새 ETag를 반환합니다.

## 16. Polling 종료 조건을 명확히 한다

Client가 언제 Polling을 끝낼지 정의하지 않으면 무한 조회가 발생합니다.

정상 종료 조건은 다음과 같습니다.

```text
operation.terminal == true
```

그리고 Terminal State별 다음 행동을 정합니다.

| 상태 | Polling | 다음 행동 |
|---|---|---|
| `SUCCEEDED` | 종료 | `resultRef` 조회·Readiness 검증 |
| `FAILED` | 종료 | 오류 표시·정책에 따라 재시도 |
| `CANCELLED` | 종료 | 취소 표시 |
| `SUPERSEDED` | 종료 | `supersededBy` Operation 조회 |

Client Deadline 도달은 Operation 실패와 다릅니다.

```text
Client Wait Timeout
  화면이 더 이상 기다리지 않음

Operation Timeout
  서버 작업이 종료 상태로 전환됨
```

사용자가 화면을 닫았다고 서버 작업을 자동 취소할지도 별도 계약입니다.

## 17. Event는 상태 변경 알림이고 결과의 기준 데이터가 아니다

Polling 대신 Webhook, Message Broker 또는 Server-Sent Events로 상태 변경을 전달할 수 있습니다.

Event에는 최소한 다음 정보가 필요합니다.

```json
{
  "specversion": "1.0",
  "id": "event_fixture_001",
  "source": "/summary-service",
  "type": "com.example.summary.operation.changed.v1",
  "subject": "operations/operation_fixture_001",
  "time": "2026-07-29T11:20:00Z",
  "datacontenttype": "application/json",
  "data": {
    "operationId": "operation_fixture_001",
    "state": "SUCCEEDED",
    "operationRevision": 8,
    "resultRef": "/v1/summaries/summary_fixture_004"
  }
}
```

CloudEvents는 Event의 `id`, `source`, `type`, `subject`, `time`과 Data 같은 Context를 공통 형식으로 표현하는 사양을 제공합니다.

하지만 CloudEvents 형식을 사용한다고 전달 순서, Exactly-once (정확히 한 번 처리) 또는 업무 결과의 일관성이 자동으로 보장되지는 않습니다.

Event는 “상태가 바뀌었을 수 있다”는 알림으로 사용하고, Consumer는 필요하면 Source of Truth API를 다시 조회합니다.

```text
Event 수신
  → source + eventId 중복 확인
  → operationRevision 비교
  → GET Operation
  → GET Result
  → Readiness Predicate 적용
```

## 18. 중복·역순 Event를 전제로 Consumer를 만든다

다음 순서로 Event가 생성됐다고 가정합니다.

```text
Revision 7: RUNNING
Revision 8: SUCCEEDED
```

Network와 Broker 상황에 따라 Consumer가 다음 순서로 받을 수 있습니다.

```text
SUCCEEDED revision 8
RUNNING revision 7
```

마지막으로 도착한 Event를 무조건 적용하면 상태가 완료에서 실행 중으로 되돌아갑니다.

Consumer는 Operation Revision을 비교합니다.

```javascript
function shouldApplyEvent(currentRevision, event) {
  return event.operationRevision > currentRevision;
}
```

동일 Event의 재전달은 `event.source + event.id` 조합으로 제거합니다.

```text
eventSource + eventId
  전달 중복 제거

operationRevision
  같은 Operation의 순서 판정

targetGeneration
  서로 다른 Operation 결과의 최신성 판정
```

세 값은 역할이 다릅니다.

## 19. Polling과 Event를 함께 사용하는 것이 현실적이다

Event만 사용하면 Client가 잠시 연결되지 않았을 때 상태 변경을 놓칠 수 있습니다.

Polling만 사용하면 불필요한 지연과 조회 부하가 생길 수 있습니다.

실무에서는 두 방식을 결합할 수 있습니다.

```text
1. POST Summary
2. Operation ID 저장
3. Event 구독 또는 SSE 연결
4. Event 수신 시 Operation 즉시 조회
5. Event가 없어도 낮은 빈도로 Polling
6. 재연결 시 마지막 Operation 상태 재조회
```

Event는 Wake-up Signal (깨우기 신호), Operation API는 Source of Truth로 사용합니다.

Client가 Event를 놓쳐도 Polling으로 수렴하고, Event를 받으면 불필요한 대기 없이 갱신할 수 있습니다.

## 20. UI에는 작업 상태와 결과 상태를 함께 보여 준다

사용자 화면 문구도 상태 조합표를 따라야 합니다.

| 상태 조합 | 권장 표시 |
|---|---|
| 결과 없음 + `QUEUED` | “요약 작업이 대기 중입니다.” |
| 결과 없음 + `RUNNING` | “AI 요약을 생성하고 있습니다.” |
| 최신 결과 있음 + Job 없음 | 최신 요약 표시 |
| 기존 결과 있음 + `RUNNING` | 기존 요약 표시 + “새 요약 생성 중” |
| 기존 결과 있음 + `FAILED` | 기존 요약 표시 + “최신 요약 생성 실패” |
| 결과 없음 + `FAILED` | 안전한 오류 설명 + 재시도 조건 |
| `SUCCEEDED` + 결과 없음 | “결과 확인 중” + 운영 오류 기록 |
| 과거 Version 결과만 있음 | 생성 기준 Version·갱신 안내 |

기존 결과가 있는데 화면 전체를 Spinner로 덮는 방식은 사용자 가치를 불필요하게 숨깁니다.

반대로 과거 결과를 최신이라고 표시하면 잘못된 의사결정을 만들 수 있습니다.

결과 Version 또는 생성 기준을 사용자가 이해할 수 있는 수준으로 표시합니다.

```text
현재 요약: 10:20 생성
새 녹취 반영 요약: 생성 중
```

## 21. Agent와 MCP Tool도 같은 Readiness Predicate를 사용한다

AI Agent가 요약 조회 Tool을 호출했을 때 `completed=false`만 보고 “요약이 없습니다”라고 답하면 이미 사용 가능한 결과를 놓칩니다.

Tool Result는 작업과 결과를 분리해 반환합니다.

```json
{
  "operation": {
    "operationId": "operation_fixture_001",
    "state": "RUNNING",
    "targetTranscriptVersion": 8
  },
  "result": {
    "summaryId": "summary_fixture_003",
    "sourceTranscriptVersion": 7,
    "available": true,
    "text": "기존 요약 본문"
  },
  "readiness": {
    "usable": true,
    "current": false,
    "generating": true
  }
}
```

Agent의 기대 답변은 다음과 같습니다.

```text
“현재 사용 가능한 기존 요약을 보여드립니다.
 최신 녹취록을 반영한 새 요약은 생성 중입니다.”
```

요약 본문이 없고 `usable=false`라면 그때 처리 중 또는 실패 상태를 설명합니다.

조회 요청이 곧 재생성 요청은 아닙니다.

Agent가 결과가 없다는 이유로 쓰기 작업인 `summary.request`를 자동 호출하지 않도록 Tool 권한과 사용자 의도를 별도로 확인해야 합니다.

## 22. 접근 권한은 Readiness와 별도로 매 요청 확인한다

결과가 기술적으로 준비됐다고 모든 사용자가 읽을 수 있는 것은 아닙니다.

```text
Ready
  결과가 생성·검증·게시됨

Accessible
  현재 Principal이 이 결과를 읽을 수 있음
```

`accessible=true`를 결과 Record에 영구 저장하면 사용자 역할과 회의 소속이 바뀌었을 때 오래된 판단을 재사용할 수 있습니다.

접근 가능 여부는 요청 시점의 Principal, Tenant, Group과 Object 권한으로 다시 판단합니다.

권한이 없을 때 결과 존재 여부까지 노출하지 않는 정책도 필요합니다.

```text
404 Not Found
  존재 여부 은닉 정책

403 Forbidden
  존재는 공개하지만 접근은 거부하는 정책
```

어느 방식을 사용할지는 보안 정책으로 일관되게 정합니다.

Polling·Event Channel도 같은 객체 단위 인가를 적용해야 합니다.

## 23. Operation과 Result의 보존 기간을 분리한다

작업 추적 정보와 업무 결과는 보존 목적이 다릅니다.

```text
Operation
  실행 진단·오류·Attempt·Trace

Summary Result
  사용자가 조회하는 업무 결과
```

Google의 Long-running Operations 지침도 완료된 Operation Resource가 일정 기간 후 만료될 수 있음을 설명합니다.

Operation이 만료됐다고 Summary Result까지 삭제할 필요는 없습니다.

반대로 개인정보 보존 정책에 따라 Summary Result는 삭제됐지만 감사용 Operation Metadata 일부만 남을 수도 있습니다.

API는 만료와 삭제를 구분합니다.

```json
{
  "operationId": "operation_fixture_001",
  "state": "EXPIRED",
  "resultRef": "/v1/summaries/summary_fixture_004"
}
```

실제 계약에서는 `EXPIRED`를 State로 노출할지, Operation 조회에 `404` 또는 `410`을 사용할지 명확히 정합니다.

## 24. 상태와 결과를 같은 Transaction 또는 복구 가능한 흐름으로 저장한다

정상 계약을 정의해도 저장 순서가 잘못되면 불일치가 생깁니다.

```text
Operation을 SUCCEEDED로 저장
→ Result 저장 실패
```

가능하다면 Result와 Operation Terminal State를 같은 Transaction에 Commit합니다.

```sql
BEGIN;

INSERT INTO summary_result (
  summary_id,
  operation_id,
  transcript_version,
  body_json
) VALUES (
  'summary_fixture_004',
  'operation_fixture_001',
  8,
  '{"text":"fixture summary"}'
);

UPDATE summary_operation
SET state = 'SUCCEEDED',
    result_id = 'summary_fixture_004',
    revision = revision + 1
WHERE operation_id = 'operation_fixture_001'
  AND state = 'RUNNING';

COMMIT;
```

Event 발행은 Transactional Outbox (트랜잭션 아웃박스)로 연결하고, Consumer는 Event 중복을 처리합니다.

저장소가 분리돼 원자적 Commit이 어렵다면 Reconciliation Job이 다음 불일치를 찾아야 합니다.

- `SUCCEEDED`인데 Result 없음
- Result가 있는데 Operation은 계속 `RUNNING`
- Current Pointer가 삭제된 Result를 가리킴
- Result의 Source Version이 Operation Target과 다름

## 25. 기존 Boolean API를 단계적으로 개선한다

이미 다음 API를 운영 중일 수 있습니다.

```json
{
  "summarized": true,
  "completed": false,
  "summaryAvailable": true,
  "summary": {
    "text": "기존 요약"
  }
}
```

한 번에 기존 필드를 제거하면 Client가 깨질 수 있습니다.

다음 순서로 개선합니다.

### 1단계: 필드 의미를 문서화한다

```text
summarized
  요약 요청 이력이 있음

completed
  최신 Operation 종료 여부

summaryAvailable
  사용 가능한 Result 존재 여부
```

### 2단계: Operation과 Result 객체를 추가한다

```json
{
  "operation": {
    "id": "operation_fixture_001",
    "state": "RUNNING"
  },
  "result": {
    "id": "summary_fixture_003",
    "available": true,
    "version": 3
  }
}
```

### 3단계: 파생 Readiness를 추가한다

```json
{
  "readiness": {
    "usable": true,
    "current": false,
    "generating": true
  }
}
```

### 4단계: Client 전환을 측정한다

- 구형 필드 사용 Client 비율
- 신형 Operation API 호출 비율
- 상태 불일치 처리 오류

### 5단계: Versioned API에서 구형 필드를 제거한다

필드 추가만으로 끝내지 말고 의미와 전환 기한을 명시합니다.

## 26. 상태 계약 테스트는 모든 조합을 검증한다

Happy Path 하나만 테스트하면 상태 불일치를 놓칩니다.

최소 조합은 다음과 같습니다.

| Job | Result | Body | Current | 기대 결과 |
|---|---|---|---:|---|
| 없음 | 없음 | 없음 | - | 요약 없음 |
| `QUEUED` | 없음 | 없음 | - | 대기 중 |
| `RUNNING` | 없음 | 없음 | - | 생성 중 |
| `RUNNING` | 있음 | 있음 | 아니요 | 기존 결과 + 생성 중 |
| `SUCCEEDED` | 있음 | 있음 | 예 | 최신 결과 |
| `SUCCEEDED` | 있음 | 없음 | 예 | 불일치 오류 |
| `SUCCEEDED` | 없음 | 없음 | - | 불일치 오류 |
| `FAILED` | 없음 | 없음 | - | 실패 |
| `FAILED` | 있음 | 있음 | 아니요 | 기존 결과 + 최신 실패 |
| `CANCELLED` | 있음 | 있음 | 조건부 | 기존 결과 + 취소 |
| `SUPERSEDED` | 있음 | 있음 | 아니요 | 대체 Operation 확인 |

Condition 조합도 검사합니다.

| Validated | Published | Body | usable |
|---:|---:|---|---:|
| `True` | `True` | 있음 | `true` |
| `True` | `False` | 있음 | `false` |
| `False` | `True` | 있음 | `false` |
| `True` | `True` | 없음 | `false` + 불일치 기록 |
| `Unknown` | `True` | 있음 | 정책에 따라 대기 |

Client·Agent·Batch가 같은 Test Vector (테스트 벡터)를 공유하면 판정 로직의 차이를 줄일 수 있습니다.

## 27. Polling과 Event 계약을 실패 주입으로 검증한다

상태 값만 아니라 전달 과정도 테스트합니다.

- Event를 한 번 누락한 뒤 Polling으로 수렴하는가?
- 같은 Event를 여러 번 전달해도 결과가 같은가?
- Revision 8 뒤 Revision 7을 받아도 상태가 되돌아가지 않는가?
- Operation 조회가 일시적으로 `503`일 때 Backoff하는가?
- ETag가 같을 때 `304`를 올바르게 처리하는가?
- Client Deadline 뒤 다시 접속해 기존 Operation을 복구하는가?
- `SUPERSEDED`가 가리키는 새 Operation을 따라가는가?
- Operation은 만료됐지만 Result가 남아 있을 때 조회 가능한가?
- 권한 변경 뒤 Event·Polling 조회가 모두 거부되는가?

이 테스트는 비동기 기능의 API 계약 테스트입니다.

특정 Queue나 LLM Provider를 Mocking하는 것만으로는 충분하지 않습니다.

## 28. 운영 Metric은 결과 가용성을 기준으로 만든다

Operation 성공률만 보면 사용자가 실제로 결과를 받았는지 알 수 없습니다.

다음 Metric을 분리합니다.

| Metric | 의미 |
|---|---|
| `summary_operation_created_total` | 접수된 작업 |
| `summary_operation_terminal_total` | 종료된 작업 |
| `summary_operation_failed_total` | 실패한 작업 |
| `summary_result_usable_total` | 사용 가능한 결과 |
| `summary_result_current_total` | 최신 결과 |
| `summary_state_inconsistency_total` | 상태·결과 불일치 |
| `summary_regeneration_with_old_result_total` | 기존 결과 유지 중 재생성 |
| `summary_poll_request_total` | Polling 부하 |
| `summary_event_lag_seconds` | Event 전달 지연 |
| `summary_event_duplicate_total` | 중복 Event |

사용자 성공률은 다음에 가깝습니다.

```text
사용 가능한 요약 결과를 받은 요청
÷
유효한 요약 요청
```

`202 Accepted` 응답 수나 `completed=true` Flag 수를 성공률로 사용하면 실제 가용성을 과대평가할 수 있습니다.

불일치에는 즉시 Alert를 설정합니다.

```text
SUCCEEDED + Result 없음
Published=True + Body 없음
Current=True + Source Version 불일치
```

## 29. 구현 체크리스트

- [ ] 요약 Operation과 Summary Result를 별도 Resource로 모델링한다.
- [ ] `202 Accepted`를 접수 완료로만 해석한다.
- [ ] Job State의 Terminal 여부와 성공 여부를 구분한다.
- [ ] 사용 가능, 최신, 생성 중을 별도 파생 값으로 계산한다.
- [ ] Readiness Predicate를 공통 Library와 Test Vector로 관리한다.
- [ ] Result에 Transcript·Prompt·Model Policy Version을 기록한다.
- [ ] 생성 시간보다 Version·Generation으로 최신성을 판정한다.
- [ ] 재생성 중에도 기존 Result를 유지한다.
- [ ] 늦게 완료된 과거 Generation이 Current Pointer를 덮어쓰지 못하게 한다.
- [ ] Polling API에 Operation ID와 Terminal State를 제공한다.
- [ ] Polling 간격, Backoff, Jitter와 종료 조건을 정의한다.
- [ ] ETag와 조건부 GET으로 변경 없는 응답 비용을 줄인다.
- [ ] Event에 Event ID, Operation Revision과 Result Reference를 포함한다.
- [ ] Event 중복·역순·누락을 전제로 Consumer를 구현한다.
- [ ] Event는 알림, Operation API는 Source of Truth로 사용한다.
- [ ] 접근 권한을 결과 Readiness와 별도로 매 요청 검증한다.
- [ ] Operation과 Result의 보존 기간을 분리한다.
- [ ] 상태·결과 불일치를 탐지하는 Reconciliation Job과 Metric을 둔다.
- [ ] 구형 Boolean 필드의 의미와 폐기 계획을 문서화한다.

## 마무리

비동기 AI 요약에서 “완료됐는가?”는 하나의 질문이 아닙니다.

```text
작업은 끝났는가?
결과가 존재하는가?
결과는 검증됐는가?
현재 입력을 반영했는가?
현재 사용자가 읽을 수 있는가?
```

이 질문들을 분리하면 다음처럼 정확한 사용자 경험을 만들 수 있습니다.

```text
“현재 사용 가능한 기존 요약이 있습니다.
 최신 녹취록을 반영한 새 요약은 생성 중입니다.”
```

또는 다음 불일치를 운영 오류로 감지할 수 있습니다.

```text
Operation = SUCCEEDED
Result = 없음
```

핵심 원칙은 네 가지입니다.

1. Operation과 Result를 분리합니다.
2. Readiness Predicate를 명시적인 코드와 Test Vector로 관리합니다.
3. Version·Generation으로 최신성을 판단합니다.
4. Polling과 Event가 Source of Truth API로 같은 상태에 수렴하게 합니다.

좋은 비동기 API는 Client에게 “조금 더 기다려 보세요”라고만 말하지 않습니다.

지금 사용할 결과가 있는지, 더 최신 결과를 만들고 있는지, 실패했다면 기존 결과를 유지할 수 있는지를 구조화된 계약으로 설명합니다.

다음 글에서는 사용자, Tenant와 Tool 단위의 권한을 분리하고 AI Agent가 수행한 조회·변경·승인·실패를 감사 로그로 연결하는 방법을 살펴보겠습니다.

## 참고 자료

- [RFC 9110: HTTP Semantics — 202 Accepted](https://www.rfc-editor.org/rfc/rfc9110.html#name-202-accepted)
- [RFC 9110: HTTP Semantics — Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after)
- [RFC 9110: HTTP Semantics — Conditional Requests](https://www.rfc-editor.org/rfc/rfc9110.html#name-conditional-requests)
- [Google AIP-151: Long-running operations](https://google.aip.dev/151)
- [Google AIP-216: States](https://google.aip.dev/216)
- [Kubernetes: Pod Conditions](https://kubernetes.io/docs/concepts/workloads/pods/pod-condition/)
- [Kubernetes: Pods — observedGeneration](https://kubernetes.io/docs/concepts/workloads/pods/#pod-generation)
- [CloudEvents Specification](https://github.com/cloudevents/spec/blob/ce@stable/cloudevents/spec.md)
- [CloudEvents Primer](https://github.com/cloudevents/spec/blob/ce@stable/cloudevents/primer.md)
- [OpenTelemetry: Semantic conventions for messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/)

---

> 이 글은 2026년 7월 29일 기준 RFC 9110, Google API Improvement Proposals, Kubernetes API, CloudEvents와 OpenTelemetry 공식 문서 및 공개 가능한 비동기 AI 요약 연동 경험을 바탕으로 작성했습니다. `completed=false`와 사용 가능한 요약 본문이 동시에 존재하는 사례는 각 필드가 서로 다른 Operation·Result 또는 Version을 나타낼 수 있음을 보여 주는 출발점이며, 특정 제품의 모든 상태 의미를 일반화한 결론은 아닙니다. 실제 Field 의미, Terminal State, Polling 간격, Event 전달 보장과 보존 기간은 사용하는 API·Queue·Client 환경의 계약으로 다시 확인해야 합니다.
