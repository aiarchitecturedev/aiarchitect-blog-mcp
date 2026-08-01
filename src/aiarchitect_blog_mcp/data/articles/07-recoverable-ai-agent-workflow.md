# Tistory 기술자료 초안

- 문서 ID: `BLOG-07`
- 상태: 공개 완료
- 공개 URL: https://aiarchitect.tistory.com/7
- Tistory 상태: 공개 게시·공개 페이지 검증 완료
- 분류: `엔터프라이즈 아키텍처`
- 권장 제목: `운영 가능한 AI Agent 만들기: Checkpoint, Retry, Idempotency와 Outbox`
- 검색 설명: `LLM과 외부 Tool이 포함된 긴 AI Agent Workflow를 실패 후 안전하게 재개하기 위한 Checkpoint(상태 저장), Retry(재시도), Idempotency(멱등성), Outbox(메시지 발행)와 승인 경계를 정리합니다.`
- 권장 태그: `AI Agent`, `LangGraph`, `Checkpoint`, `Retry`, `Idempotency`, `Outbox`, `엔터프라이즈 아키텍처`
- 권장 대표 이미지: `portfolio/architecture-diagrams/01-enterprise-ai-reference-architecture.svg`

---

# 운영 가능한 AI Agent 만들기: Checkpoint, Retry, Idempotency와 Outbox

AI Agent 데모는 질문을 받고 LLM을 호출한 뒤 Tool 결과를 보여 주면 완성된 것처럼 보입니다. 운영 환경에서는 그 사이에 훨씬 많은 일이 생깁니다.

- 모델 응답이 늦어집니다.
- 외부 API가 `429` 또는 `503`을 반환합니다.
- Tool 호출은 성공했지만 응답을 받기 전에 연결이 끊깁니다.
- Worker가 재시작됩니다.
- 사용자의 승인이 몇 시간 뒤 도착합니다.
- 재개된 Workflow가 같은 업무를 다시 실행합니다.
- 데이터 저장은 성공했지만 후속 이벤트 발행은 실패합니다.

이 문제를 단순한 `try/catch`와 무제한 재시도로 처리하면 중복 이슈, 중복 알림, 이중 결제와 잘못된 상태 전이가 발생할 수 있습니다.

운영 가능한 AI Agent는 “실패하지 않는 Agent”가 아닙니다. **실패 위치를 알고, 안전한 지점에서 재개하며, 외부 부작용이 중복되지 않도록 설계된 Agent**입니다.

운영 가능한 AI Agent를 만들기 위해서는 **Checkpoint(상태 저장), Retry(재시도), Idempotency(멱등성), 그리고 Outbox(메시지 발행)**를 서로 다른 복구 장치로 설계해야 합니다.

기준 구조는 다음과 같습니다.

```text
User Request
     │
     ▼
Workflow Instance ───── Checkpoint Store
     │                   상태 · 버전 · 재개 지점
     ├─ LLM Node
     ├─ Retrieval Node
     ├─ Approval Interrupt
     └─ Tool Execution ── Idempotency Store
              │           실행 결과 · 요청 지문
              ▼
       Business Transaction
              ├─ Domain State
              └─ Outbox Event
                       │
                       ▼
                 Event Relay
                       │
                       ▼
               Downstream Consumer
```

Checkpoint(상태 저장), Retry(재시도), Idempotency(멱등성)와 Outbox(메시지 발행)는 각각 다른 실패를 해결합니다. 하나를 적용했다고 나머지가 자동으로 해결되는 것은 아닙니다.

## 1. 먼저 실행 단위를 세 가지로 구분한다

복구 구조를 설계할 때 요청, Workflow와 외부 효과를 하나의 ID로 표현하면 의미가 섞입니다.

| 실행 단위 | 질문 | 권장 식별자 |
|---|---|---|
| 사용자 요청 | 같은 시작 요청이 다시 들어왔는가 | `requestId`, `requestIdempotencyKey` |
| Workflow 실행 | 어떤 상태 흐름을 이어서 실행하는가 | `workflowId`, `runId`, `checkpointId` |
| 외부 효과 | 같은 업무 변경을 이미 수행했는가 | `operationId`, `idempotencyKey`, `eventId` |

하나의 Workflow는 재개되면서 여러 `runId`를 가질 수 있습니다. 반대로 같은 사용자 시작 요청은 하나의 `workflowId`만 생성해야 할 수 있습니다. Workflow 안의 여러 Tool 호출은 각각 독립된 외부 효과 ID가 필요합니다.

다음처럼 식별자를 분리하면 로그와 저장소의 의미가 명확해집니다.

```json
{
  "requestId": "opaque-request-id",
  "workflowId": "opaque-workflow-id",
  "runId": "opaque-run-id",
  "stepId": "create-task",
  "attempt": 2,
  "operationId": "opaque-operation-id",
  "traceId": "opaque-trace-id"
}
```

식별자는 권한이 아닙니다. Workflow를 조회하거나 재개할 때마다 현재 사용자, 테넌트와 대상 업무의 접근 권한을 다시 확인해야 합니다.

## 2. Workflow를 명시적인 상태 머신으로 만든다

Agent의 상태를 `실행 중`, `완료`, `실패` 세 가지로만 표현하면 승인 대기와 재시도 가능 여부를 구분하기 어렵습니다.

```text
RECEIVED
  → PLANNING
  → READY_FOR_EXECUTION
  → WAITING_APPROVAL
  → EXECUTING
  → COMPLETED

실패 분기
  → RETRY_SCHEDULED
  → FAILED_RETRYABLE
  → FAILED_PERMANENT
  → CANCELLED
  → COMPENSATION_REQUIRED
```

상태에는 결과뿐 아니라 다음 행동을 판단할 정보가 필요합니다.

- 현재 단계와 상태 버전
- 다음 실행 가능한 시각
- 재시도 횟수와 최대 횟수
- 오류 분류와 마지막 실패 단계
- 승인 대상, 승인 만료 시각과 승인 결과
- 외부 실행의 `operationId`
- 생성된 결과와 후속 이벤트
- 취소 또는 보상 가능 여부

여러 Worker가 같은 Workflow를 동시에 재개하지 않도록 상태 버전, Lease 또는 낙관적 잠금을 사용합니다. `WHERE version = :expectedVersion`과 같은 조건부 갱신이 실패하면 다른 실행자가 상태를 먼저 변경한 것으로 보고 다시 읽어야 합니다.

## 3. Checkpoint는 재개 지점이지 외부 부작용의 보증서가 아니다

Checkpoint는 Workflow의 상태 Snapshot을 저장해 Worker 재시작, 사용자 승인 대기와 일시적 오류 뒤에 이전 지점부터 계속할 수 있게 합니다.

LangGraph의 Checkpointer는 Thread 단위 Graph 상태를 저장하며, Human-in-the-loop, 시간 이동과 장애 복구에 사용할 수 있습니다. 운영에서는 메모리 기반 Saver가 아니라 Process 재시작 후에도 남는 지속성 저장소가 필요합니다.

Checkpoint에 포함할 항목은 다음과 같습니다.

- Workflow 입력의 정규화된 형태
- 현재 Node와 다음 Node
- Node별 출력과 오류 분류
- Tool 실행 계획과 승인 상태
- Prompt·모델·Tool 계약 버전
- 재시도 횟수와 다음 실행 시각
- 외부 효과의 `operationId`와 결과 참조

반면 다음 값은 그대로 저장하지 않는 편이 안전합니다.

- Access Token, API Key와 장기 자격 증명
- 직렬화할 수 없는 Client·Socket 객체
- 불필요한 원문 파일과 대형 Binary
- 보존할 이유가 없는 전체 Prompt와 민감한 검색 원문
- 최신 권한을 대신하는 과거 승인·권한 Snapshot

Checkpoint에서 재개됐다고 이미 실행한 Node가 절대 다시 실행되지 않는 것은 아닙니다. Framework의 재개 경계, 저장 시점과 장애 시점을 이해해야 합니다.

```text
Tool 실행 성공
    │
    ├─ 결과 Checkpoint 저장 성공 → 다음 단계로 안전하게 진행
    │
    └─ 결과 Checkpoint 저장 전 Worker 종료
             ↓
       재개 시 Tool Node가 다시 실행될 수 있음
```

따라서 외부 부작용이 있는 Node는 Checkpoint와 별개로 멱등하게 설계해야 합니다.

## 4. 재실행될 수 있는 Node의 구조를 바꾼다

LLM 호출이나 검색은 다시 실행해도 업무 데이터가 변경되지 않을 수 있습니다. 하지만 비용, 결과 변동과 지연은 발생합니다. 이슈 생성, 결제, 메시지 발송과 상태 변경은 중복 실행 자체가 업무 오류가 됩니다.

Node를 다음 세 단계로 분리하면 복구가 쉬워집니다.

```text
Prepare
  입력 검증 · 권한 확인 · 요청 정규화 · operationId 결정
       ↓
Execute
  외부 Tool 호출 · 업무 변경
       ↓
Record
  결과 저장 · Checkpoint 갱신 · 후속 이벤트 준비
```

`Execute` 전에 안정된 `operationId`를 만들고 외부 시스템에 전달합니다. 외부 시스템이 멱등성 키를 지원하지 않는다면 내부 실행 기록, 결정적 업무 키 또는 실행 전 조회로 중복 가능성을 줄여야 합니다.

Node 안에서 승인 대기를 시작하기 전에 외부 변경을 수행하는 구조도 주의해야 합니다. 승인 Interrupt로 Node가 다시 시작될 수 있다면 Interrupt 앞의 부작용이 재실행될 수 있습니다. 가능하면 승인과 실행을 서로 다른 Node로 분리합니다.

## 5. Retry는 오류 분류 뒤에 적용한다

모든 오류가 재시도 대상은 아닙니다.

| 오류 유형 | 예시 | 기본 대응 |
|---|---|---|
| 일시적 네트워크 | 연결 초기화, 짧은 Timeout | 제한된 재시도 |
| 과부하·제한 | `429`, 일부 `503` | 서버 힌트와 Backoff 적용 |
| 인증·권한 | 만료된 자격 증명, `401`, `403` | 자격 갱신 또는 영구 실패 |
| 입력 오류 | Schema 오류, 존재하지 않는 대상 | 수정 전까지 재시도하지 않음 |
| 업무 충돌 | 이미 완료된 상태, 버전 충돌 | 최신 상태를 읽고 재판단 |
| 결과 불명 | 요청 전송 후 응답 유실 | 결과 조회 또는 멱등 키로 확인 |
| 모델 품질 | 형식 위반, 근거 부족 | 제한된 보정·재생성 후 중단 |

Timeout은 요청이 실패했다는 뜻이 아니라 **클라이언트가 결과를 알지 못한다는 뜻**일 수 있습니다. 외부 시스템이 이미 처리를 완료했는데 같은 변경을 새 요청으로 보내면 중복이 발생합니다.

재시도 정책에는 최소한 다음 값이 필요합니다.

- 연결 Timeout과 전체 요청 Timeout
- 최대 시도 횟수
- 지수 Backoff
- 동시 재시도가 몰리지 않도록 Jitter
- `Retry-After` 같은 서버 힌트
- Workflow 전체 Retry Budget
- 더 이상 자동 복구하지 않을 종료 조건

```text
delay = min(maxDelay, baseDelay × 2^attempt) + randomJitter
```

재시도 계층도 하나로 통제해야 합니다. Client SDK, Gateway, Worker와 Tool Client가 각각 세 번씩 재시도하면 한 번의 사용자 요청이 예상보다 훨씬 많은 호출로 증폭될 수 있습니다.

## 6. Idempotency Key는 같은 업무 의도를 식별해야 한다

HTTP 표준에서 멱등성은 같은 요청을 여러 번 보냈을 때 서버의 의도된 효과가 한 번 보낸 것과 같다는 의미입니다. 하지만 Agent의 쓰기 Tool은 대부분 `POST` 형태이므로 애플리케이션 수준의 멱등성 계약이 필요합니다.

좋은 멱등성 키는 단순한 호출 시각이나 매 시도마다 새로 생성한 UUID가 아닙니다. **재시도 사이에서 변하지 않는 하나의 업무 의도**를 나타내야 합니다.

```text
workflowId + stepId + normalizedBusinessTarget + operationVersion
```

예를 들어 동일 Workflow에서 동일한 업무 항목 생성 단계가 재실행된다면 같은 키를 사용합니다. 사용자가 승인 후 내용을 수정해 새로운 실행을 요청했다면 `operationVersion`을 올리거나 새 키를 발급합니다.

서버는 키만 저장해서는 안 됩니다.

```json
{
  "idempotencyKeyHash": "opaque-key-hash",
  "requestFingerprint": "canonical-request-hash",
  "status": "SUCCEEDED",
  "resourceId": "opaque-resource-id",
  "responseRef": "stored-result-reference",
  "createdAt": "2026-07-29T07:00:00Z",
  "expiresAt": "2026-08-05T07:00:00Z"
}
```

같은 키와 같은 요청 지문이 들어오면 저장된 결과를 반환할 수 있습니다. 같은 키에 다른 요청 본문이 들어오면 키 재사용 오류로 거부해야 합니다. 키의 보존 기간, 결과 저장 범위와 개인정보 처리 기준도 정해야 합니다.

## 7. 멱등 처리 기록과 업무 변경을 가능한 한 함께 저장한다

다음 순서는 경쟁 조건을 만들 수 있습니다.

```text
1. 멱등성 키 조회 → 없음
2. 업무 레코드 생성
3. 멱등성 결과 저장
```

두 Worker가 동시에 1번을 통과하거나, 2번 성공 후 3번 전에 Process가 종료될 수 있기 때문입니다.

가능하면 하나의 Database Transaction 안에서 멱등성 키 예약, 업무 변경과 결과 참조를 함께 저장합니다.

```sql
BEGIN;

INSERT INTO idempotency_record (
  key_hash, request_fingerprint, status
) VALUES (
  :key_hash, :request_fingerprint, 'IN_PROGRESS'
);

INSERT INTO business_task (
  task_id, title, status
) VALUES (
  :task_id, :title, 'OPEN'
);

UPDATE idempotency_record
SET status = 'SUCCEEDED',
    resource_id = :task_id
WHERE key_hash = :key_hash;

COMMIT;
```

`key_hash`에는 Unique Constraint가 필요합니다. 같은 키가 동시에 들어오면 한 요청만 생성 권한을 얻고, 다른 요청은 기존 레코드 상태에 따라 대기하거나 저장된 결과를 반환합니다.

외부 SaaS처럼 같은 Transaction에 넣을 수 없는 시스템은 해당 API의 멱등성 기능을 사용하거나, `operationId` 조회 API와 내부 실행 기록을 조합합니다.

## 8. Outbox는 데이터 저장과 이벤트 발행 사이의 틈을 줄인다

Workflow가 업무 상태를 바꾼 뒤 메시지 브로커에 이벤트를 발행하는 경우를 생각해 보겠습니다.

```text
업무 DB Commit 성공
        ↓
Event Publish 실패
```

업무 상태는 바뀌었지만 후속 서비스는 변경 사실을 모르게 됩니다. 순서를 반대로 바꾸면 이벤트는 발행됐는데 업무 Transaction이 Rollback되는 반대 불일치가 생길 수 있습니다.

Transactional Outbox는 업무 변경과 발행할 이벤트를 같은 Database Transaction에 기록합니다.

```sql
BEGIN;

UPDATE workflow
SET status = 'COMPLETED',
    version = version + 1
WHERE workflow_id = :workflow_id
  AND version = :expected_version;

INSERT INTO outbox_event (
  event_id,
  aggregate_type,
  aggregate_id,
  event_type,
  payload,
  occurred_at
) VALUES (
  :event_id,
  'Workflow',
  :workflow_id,
  'WorkflowCompleted',
  :payload,
  CURRENT_TIMESTAMP
);

COMMIT;
```

별도 Relay 또는 CDC가 Outbox 레코드를 읽어 Broker로 전달합니다. Debezium Outbox Event Router는 Outbox Table의 변경을 포착하고 Event ID와 Aggregate Key를 이용해 메시지를 전달할 수 있습니다.

Outbox도 자동으로 정확히 한 번 전달을 보장하는 마법은 아닙니다. Relay가 발행 후 처리 완료 표시 전에 종료되면 같은 Event가 다시 전달될 수 있습니다. Consumer는 `eventId`를 기준으로 중복을 제거하거나 Inbox 기록을 사용해야 합니다.

## 9. 승인 대기는 Checkpoint와 실행 권한을 함께 설계한다

위험한 Tool 실행 전에 사용자 승인을 받는 Workflow는 수 초가 아니라 수 시간 또는 수 일이 걸릴 수 있습니다. Worker가 연결을 유지한 채 기다리는 대신 상태를 저장하고 `WAITING_APPROVAL`로 전환해야 합니다.

승인 화면에는 모델의 자연어 설명만 보여 주지 않습니다.

- 실행할 Tool과 작업 유형
- 대상 업무와 변경 전·후 값
- 중요 입력값과 요청 지문
- 요청 사용자와 승인자
- 권한·정책 검증 결과
- 승인 만료 시각
- 승인 후 사용할 `operationId`

승인은 특정 실행 내용에 묶여야 합니다.

```text
approvalFingerprint =
  hash(toolName + normalizedArguments + target + policyVersion)
```

승인 뒤 Tool 입력이나 대상이 바뀌면 기존 승인을 재사용하지 않고 다시 승인받아야 합니다. 승인과 실행 사이에 시간이 지났다면 사용자 권한, 대상 레코드의 현재 상태와 정책을 실행 시점에 다시 확인합니다.

LangGraph Interrupt는 Graph 상태를 Checkpoint에 저장하고 외부 입력이 올 때까지 중단한 뒤 같은 Thread를 재개하는 Human-in-the-loop 흐름을 지원합니다. 다만 Interrupt 이전에 실행된 외부 부작용은 재실행 가능성을 고려해 멱등하게 만들어야 합니다.

## 10. 취소와 보상은 Retry의 반대말이 아니다

이미 실행된 외부 효과를 취소할 때 단순히 이전 Checkpoint로 돌아가면 데이터가 원상 복구되는 것은 아닙니다.

```text
Checkpoint 되돌림
≠
외부 시스템 변경 되돌림
```

외부 효과를 되돌릴 수 있다면 별도의 보상 작업으로 모델링합니다.

| 원래 작업 | 가능한 보상 | 주의점 |
|---|---|---|
| 임시 예약 생성 | 예약 취소 | 취소 기한과 수수료 확인 |
| 업무 항목 생성 | 상태를 취소로 변경 | 삭제보다 감사 이력 보존 |
| 알림 발송 | 정정 알림 | 이미 읽은 메시지는 회수 불가 |
| 접근 권한 부여 | 권한 회수 | 회수 전 접근 행위는 되돌릴 수 없음 |
| 외부 결제 | 환불 요청 | 결제 취소와 환불은 다른 상태일 수 있음 |

보상도 실패할 수 있으므로 `COMPENSATION_REQUIRED`, `COMPENSATING`, `COMPENSATED`, `COMPENSATION_FAILED` 같은 상태와 별도 멱등성 키가 필요합니다.

되돌릴 수 없는 작업은 실행 전 승인과 검증을 더 강하게 적용하고, 자동 Retry 범위를 좁혀야 합니다.

## 11. 상태 Schema와 실행 계약도 버전 관리한다

장기간 대기한 Workflow가 새 코드 배포 뒤 재개될 수 있습니다. 과거 Checkpoint의 상태 구조와 현재 Node 코드가 다르면 재개 과정에서 오류가 발생하거나 잘못된 Tool 입력이 만들어질 수 있습니다.

다음 버전을 Checkpoint에 기록합니다.

- Workflow Definition Version
- State Schema Version
- Prompt Version
- Model과 주요 Parameter
- Tool 이름과 Input Schema Version
- Policy Version
- Serializer Version

배포 시에는 이전 상태를 새 Schema로 변환하는 Migration, 구버전 Worker로 재개하는 방법 또는 안전한 종료 정책 중 하나를 준비합니다.

Tool 계약이 바뀌었다면 저장된 인자를 무조건 새 Tool에 전달하지 않습니다. Schema 재검증, 업무 규칙 검증과 승인 지문 재확인이 필요합니다.

## 12. 관측성은 시도 횟수가 아니라 인과관계를 보여 줘야 한다

하나의 사용자 요청이 여러 Worker, LLM, 검색 시스템과 Tool Server를 거치면 서비스별 로그만으로 전체 흐름을 맞추기 어렵습니다.

다음 Context를 연결합니다.

```text
requestId
  └─ workflowId
      ├─ runId
      │   ├─ stepId + attempt
      │   └─ traceId + spanId
      ├─ operationId
      └─ eventId
```

권장 지표는 다음과 같습니다.

- Workflow 완료·실패·취소 비율
- 단계별 처리 시간과 대기 시간
- 오류 유형별 Retry 횟수
- Retry Budget 소진 비율
- 승인 대기 시간과 만료 비율
- 멱등성 중복 적중과 키 충돌 건수
- Outbox 미발행 건수와 가장 오래된 Event 나이
- 보상 작업 성공·실패 건수
- LLM·Tool별 Timeout, 비용과 품질 실패

OpenTelemetry Trace Context를 HTTP, Queue와 Worker 경계에서 전파하면 하나의 논리 작업을 서비스 간 Span으로 연결할 수 있습니다. 다만 Baggage와 로그에 Token, Prompt 원문, 개인정보나 업무 비밀을 넣지 않아야 합니다.

## 13. 장애 주입으로 복구 계약을 검증한다

정상 경로 테스트만으로는 복구 구조를 확인할 수 없습니다. 다음 시점에 의도적으로 장애를 발생시켜 봅니다.

1. LLM 응답 전 Timeout
2. Tool 요청 전송 직후 연결 종료
3. Tool 성공 후 Checkpoint 저장 전 Worker 종료
4. 승인 대기 중 배포와 Process 재시작
5. 같은 Workflow를 두 Worker가 동시에 재개
6. 업무 DB Commit 후 Event Relay 중단
7. Event 발행 후 Consumer 처리 전 재시작
8. 보상 작업 실행 중 외부 API 실패

각 시험에서 다음 결과를 확인합니다.

- 같은 업무 효과가 한 번만 발생하는가
- 재개 위치와 상태 전이가 예상과 일치하는가
- 재시도 불가능한 오류가 반복되지 않는가
- 승인 내용이 변경되지 않았는가
- 중복 Event를 Consumer가 안전하게 처리하는가
- 운영자가 Workflow와 외부 효과를 함께 추적할 수 있는가

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| 실행 단위 | 요청, Workflow, Run과 외부 효과 식별자가 분리돼 있는가 |
| 상태 머신 | 승인 대기, 재시도, 영구 실패와 보상을 구분하는가 |
| Checkpoint | Process 재시작 후에도 상태와 버전을 복구할 수 있는가 |
| 민감정보 | Checkpoint와 로그에 Token·비밀·불필요한 원문이 없는가 |
| Node 경계 | 외부 부작용과 Checkpoint 저장 사이의 실패를 고려했는가 |
| Retry | 오류를 분류하고 최대 횟수·Backoff·Jitter를 적용하는가 |
| Retry Budget | 여러 계층의 재시도가 호출을 증폭시키지 않는가 |
| 결과 불명 | Timeout 뒤 결과 조회 또는 멱등 재호출이 가능한가 |
| Idempotency | 같은 업무 의도에 안정된 키를 사용하는가 |
| 요청 지문 | 같은 키에 다른 입력이 들어오면 거부하는가 |
| 동시성 | Unique Constraint, 상태 버전 또는 Lease가 있는가 |
| Outbox | 업무 변경과 Event가 같은 Transaction에 저장되는가 |
| Consumer | 중복 Event를 `eventId`로 제거하는가 |
| 승인 | 승인 내용, 대상, 정책 버전과 만료를 고정하는가 |
| 재검증 | 승인 후 실행 시 현재 권한과 업무 상태를 다시 확인하는가 |
| 보상 | 되돌릴 수 있는 효과와 불가능한 효과를 구분하는가 |
| 버전 | 과거 Checkpoint를 새 코드에서 재개하는 정책이 있는가 |
| 관측성 | Request부터 Event까지 Trace와 업무 ID를 연결하는가 |
| 장애 시험 | Worker 종료, 응답 유실과 중복 전달을 재현했는가 |

## 마무리

운영 가능한 AI Agent의 핵심은 더 정교한 Prompt만이 아닙니다. 실패와 재개를 업무 계약의 일부로 만드는 것입니다.

1. 명시적인 상태 머신으로 현재 위치와 다음 행동을 표현합니다.
2. Checkpoint에 재개 가능한 상태와 실행 계약 버전을 저장합니다.
3. Retry 전에 오류를 분류하고 Backoff, Jitter와 전체 예산을 적용합니다.
4. 외부 부작용에는 안정된 Idempotency Key와 요청 지문을 사용합니다.
5. 업무 변경과 후속 Event 사이에는 Transactional Outbox를 적용합니다.
6. 승인 내용을 실행 입력에 묶고 재개 시 권한과 업무 상태를 다시 확인합니다.
7. 취소와 보상을 별도 Workflow로 관리합니다.
8. 장애 주입으로 실제 중복 실행과 복구 경계를 검증합니다.

Checkpoint만 추가하면 Agent는 다시 움직일 수 있습니다. Idempotency와 Outbox까지 함께 설계해야 다시 움직인 Agent가 같은 업무를 두 번 만들지 않습니다.

다음 글에서는 원격 MCP Server가 사용자의 로컬 파일 경로를 읽을 수 없는 이유와 Upload Ticket을 이용해 파일을 안전하게 전달하는 구조를 살펴보겠습니다.

---

## 참고 자료

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [AWS Builders' Library: Timeouts, retries and backoff with jitter](https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter)
- [AWS Builders' Library: Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- [RFC 9110: HTTP Semantics](https://datatracker.ietf.org/doc/html/rfc9110)
- [Stripe API: Idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [Debezium Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [OpenTelemetry Concepts](https://opentelemetry.io/docs/concepts/)

> 이 글은 2026년 7월 29일 기준 공개된 공식 문서와 공개 가능한 AI Orchestration 설계·검증 경험을 바탕으로 작성했습니다. 사용 중인 Workflow Engine, Database, Message Broker와 외부 Tool의 멱등성 지원 범위에 맞춰 Transaction 경계와 복구 정책을 검증해야 합니다.
