# AI Agent 감사 로그 설계: 추적성·개인정보 Masking과 보존 기간

AI Agent에게 다음과 같이 요청했다고 가정해 보겠습니다.

```text
“지난 회의의 결정 사항을 찾아 후속 업무를 등록해 줘.”
```

Agent는 한 문장을 여러 단계로 실행할 수 있습니다.

```text
사용자 요청
  → 회의 검색
    → 녹취록·요약 조회
      → 업무 후보 생성
        → 사용자 승인
          → 업무 생성 Tool 호출
            → Database Commit
              → 외부 알림 발송
```

운영 중 문제가 생기면 단순한 Application Log만으로는 다음 질문에 답하기 어렵습니다.

- 실제 사용자는 누구였는가?
- 어느 Agent와 Service가 대신 실행했는가?
- 어떤 정책 Version이 Tool 호출을 허용했는가?
- 승인한 내용과 실제 실행 인자가 같았는가?
- Tool이 성공 응답만 반환했는가, 실제 업무 객체도 생성됐는가?
- 같은 비동기 작업이 Retry로 두 번 실행됐는가?
- 어느 Tenant의 어떤 데이터가 모델과 외부 시스템에 전달됐는가?
- Prompt·Tool Result를 기록하지 않고도 사건을 재구성할 수 있는가?
- 감사 로그 자체가 수정되거나 삭제되지는 않았는가?

AI Agent 감사는 “대화 내용을 모두 저장”하는 문제가 아닙니다.

오히려 원문을 무제한 저장하면 Prompt, 개인정보, 회사 기밀, Token과 Tool Result가 한곳에 모여 새로운 고위험 데이터 저장소가 됩니다.

안전한 감사 구조는 다음 두 목표를 동시에 만족해야 합니다.

```text
추적 가능성
  누가·무엇을·왜·어떤 정책으로·어떤 결과까지 실행했는가

데이터 최소화
  조사에 필요하지 않은 Prompt·본문·Credential·개인정보는 남기지 않는가
```

이 글은 이전 권한 설계 글의 인가 모델을 반복하기보다, **정책 결정·승인·Tool 실행·Side Effect를 조사 가능한 증거 사슬로 만들고 Masking·무결성·보존·탐지·사고 대응까지 운영하는 방법**에 집중합니다.

## 1. 감사 로그의 목적을 먼저 정의한다

“나중에 필요할 수 있으니 전부 기록한다”는 요구는 범위도 끝도 없습니다.

감사 목적을 질문 형태로 정의합니다.

| 목적 | 답해야 할 질문 |
|---|---|
| 책임 추적 | 누가 요청하고 누가 대신 실행했는가? |
| 정책 증명 | 어느 정책이 Allow·Deny했고 이유는 무엇인가? |
| 승인 증명 | 누가 어떤 대상·인자·위험을 승인했는가? |
| Side Effect 증명 | 실제 외부 상태는 어떻게 바뀌었는가? |
| 보안 탐지 | 비정상 Tool·Tenant·대량 조회·우회가 있었는가? |
| 사고 조사 | 사건 범위와 영향을 시간순으로 재구성할 수 있는가? |
| 규정·계약 | 필요한 Event를 요구 기간 동안 보호했는가? |
| 품질 개선 | 누락·중복·실패한 통제 지점은 어디인가? |

목적이 다르면 필요한 Event와 보존 기간도 달라집니다.

예를 들어 Model Latency Debug에는 상세 Trace가 유용하지만, 승인된 삭제 작업 증명에는 정책 결정·승인·대상 Revision·실제 삭제 결과가 더 중요합니다.

## 2. Application Log·Trace·Audit Event·Security Alert를 분리한다

네 신호는 연결되지만 목적이 다릅니다.

| 신호 | 주 목적 | 대표 내용 | Sampling |
|---|---|---|---|
| Application Log | 오류·운영 진단 | 예외·상태·재시도 | 가능 |
| Distributed Trace | 분산 실행 경로·지연 | Span·부모·기간 | 가능 |
| Audit Event | 책임·정책·실행 증거 | Actor·Decision·Side Effect | 필수 Event는 금지 |
| Security Alert | 대응이 필요한 탐지 결과 | Rule·Severity·Evidence | 탐지 결과 보존 |

Trace가 있다고 Audit Trail (감사 추적)이 완성되는 것은 아닙니다.

Trace는 비용과 성능을 위해 Sampling될 수 있고, Span이 누락되거나 Backend 보존 기간이 짧을 수 있습니다.

반대로 Audit Event에 Stack Trace와 모든 Prompt를 넣으면 개인정보와 운영 Noise가 급증합니다.

가장 실용적인 구조는 Audit Event에 `traceId`와 핵심 증거 ID를 넣고, 허가된 조사자가 필요한 기간 안에 상세 Trace로 이동하게 하는 것입니다.

## 3. AI Agent 감사 위협 모델을 세운다

감사 시스템도 공격 대상입니다.

```text
Agent가 실제 사용자를 숨기고 Service Account만 기록
모델이 "승인됨"이라고 생성한 Text를 승인 증거로 사용
ALLOW Event는 없지만 Tool Side Effect 발생
Tool 성공 응답과 실제 Database Commit 불일치
Retry Event 때문에 동일 작업이 여러 번 실행
Prompt·Tool Argument에 Access Token·개인정보 저장
공격 문자열의 줄바꿈으로 가짜 Log Entry 삽입
Local Log 삭제로 사건 흔적 제거
Audit Pipeline 장애를 이용한 위험 작업 실행
다른 Tenant의 감사 로그 검색
Retention 변경으로 사건 직전 로그 조기 삭제
관리자가 감사 조회·Export한 사실이 남지 않음
```

따라서 감사 설계에는 다음 보안 속성이 필요합니다.

- 완전성: 필수 단계가 빠지지 않음
- 정확성: 모델의 주장보다 신뢰 경계의 실제 판단을 기록
- 상관성: 분산 서비스의 Event를 같은 실행으로 연결
- 무결성: 무단 수정·삭제를 탐지하거나 제한
- 최소성: 조사에 불필요한 민감정보를 저장하지 않음
- 가용성: 사건 조사 기간 동안 검색 가능
- 격리성: Tenant·역할·목적별 조회 범위를 강제
- 적시성: 탐지와 대응에 필요한 시간 안에 수집

## 4. Event Taxonomy를 먼저 고정한다

자유 형식 Message만 남기면 Service마다 다른 이름을 쓰고 탐지 Query가 깨집니다.

AI Agent Lifecycle의 Event Type을 표준화합니다.

```text
agent.request.accepted
agent.workflow.started
agent.model.invocation.completed
agent.tool.proposed
agent.authorization.decided
agent.approval.requested
agent.approval.decided
agent.tool.execution.started
agent.tool.execution.completed
agent.side_effect.confirmed
agent.data_egress.decided
agent.workflow.completed
agent.workflow.failed
agent.policy.changed
agent.audit.accessed
agent.audit.exported
agent.audit.retention_changed
```

모든 내부 단계가 반드시 Audit 대상인 것은 아닙니다.

다음처럼 위험과 책임 경계가 바뀌는 지점을 우선합니다.

- 신원과 Tenant가 확정될 때
- Tool·Resource 인가가 결정될 때
- 사용자 승인이 생성·거부·취소될 때
- 외부 상태 변경을 시도할 때
- 실제 Side Effect가 확인될 때
- 외부 데이터 전송이 결정될 때
- 정책·감사 설정이 변경될 때
- 감사 데이터 자체를 조회·Export·삭제할 때

## 5. 공통 Audit Event Envelope을 정의한다

Event마다 내용은 달라도 공통 Envelope이 있어야 검색과 검증이 가능합니다.

```json
{
  "eventId": "evt_opaque_id",
  "eventType": "agent.tool.execution.completed",
  "eventSchemaVersion": "1.0",
  "occurredAt": "2026-07-29T16:14:22.481Z",
  "observedAt": "2026-07-29T16:14:22.530Z",
  "severity": "INFO",
  "environment": "production",
  "service": {
    "name": "agent-runtime",
    "version": "fixture_release_v1",
    "instanceId": "ins_opaque_id"
  },
  "identity": {
    "subjectId": "usr_opaque_id",
    "actorId": "agt_opaque_id",
    "clientId": "cli_opaque_id",
    "executorId": "svc_opaque_id",
    "tenantId": "ten_opaque_id"
  },
  "correlation": {
    "workflowId": "wfl_opaque_id",
    "runId": "run_opaque_id",
    "traceId": "0123456789abcdef0123456789abcdef",
    "spanId": "0123456789abcdef",
    "toolCallId": "tcl_opaque_id",
    "decisionId": "dec_opaque_id",
    "approvalId": "apr_opaque_id"
  },
  "action": {
    "toolName": "task.create",
    "riskClass": "WRITE",
    "resourceType": "task",
    "resourceId": "tsk_opaque_id"
  },
  "outcome": {
    "status": "SUCCEEDED",
    "reasonCode": "TOOL_EXECUTION_COMMITTED"
  },
  "dataPolicyVersion": "audit_data_fixture_v3"
}
```

OpenTelemetry Logs Data Model도 Event 시각과 관측 시각, Trace ID, Span ID, Severity, Resource, Attributes와 Event Name 같은 공통 Field를 제공합니다.

내부 Audit Schema는 이 구조와 쉽게 Mapping할 수 있게 만들되, 책임 증명에 필요한 `subjectId`, `decisionId`, `approvalId`, `sideEffect` 같은 업무 Field를 별도로 정의합니다.

## 6. Subject·Actor·Executor·Approver를 모두 구분한다

최종 API 호출자는 Service Account일 수 있지만 업무 책임의 출발점은 사용자입니다.

```text
Subject
  권한이 행사되는 사용자

Actor
  Agent Runtime·Sub-agent처럼 대신 행동한 주체

Client
  사용자가 요청한 Application

Executor
  MCP Server·Worker·Business Service Identity

Approver
  구체적 실행을 승인한 사용자 또는 승인 시스템
```

```json
{
  "subject": {
    "type": "USER",
    "id": "usr_opaque_id"
  },
  "actor": {
    "type": "AI_AGENT",
    "id": "agt_opaque_id",
    "version": "agent_fixture_v4"
  },
  "client": {
    "id": "cli_opaque_id"
  },
  "executor": {
    "type": "WORKLOAD",
    "id": "svc_opaque_id"
  },
  "approver": {
    "type": "USER",
    "id": "usr_opaque_id"
  },
  "tenantId": "ten_opaque_id"
}
```

`service-account-01이 실행했다`만 남기면 사용자를 찾을 수 없습니다.

반대로 사용자 ID만 남기면 어느 Agent Version과 Workload가 실제 실행했는지 알 수 없습니다.

## 7. 하나의 ID로 모든 문제를 해결하지 않는다

각 ID는 다른 범위와 수명을 가집니다.

| ID | 범위 |
|---|---|
| Conversation ID | 사용자 대화 Thread |
| Workflow ID | 논리적 업무 흐름 |
| Run ID | 한 번의 실행 또는 재개 |
| Trace ID | 분산 요청 경로 |
| Span ID | 한 Component Operation |
| Tool Call ID | 모델 제안과 Tool Result 연결 |
| Decision ID | 인가 판단 증거 |
| Approval ID | 승인 증거 |
| Idempotency Key | 중복 Side Effect 방지 |
| Job·Operation ID | 비동기 작업 |
| Audit Event ID | 개별 감사 Record |

Conversation ID 하나만 사용하면 Retry, 재생성, 재개와 여러 Tool 호출이 뒤섞입니다.

Audit Event는 여러 ID를 연결해 다음 방향으로 탐색할 수 있어야 합니다.

```text
사용자 → Workflow → Tool → Resource
Resource → Side Effect → Decision → 사용자
Alert → Event → Trace → Downstream Commit
Approval → 실행 인자 Digest → 실제 Side Effect
```

## 8. Trace Context에는 개인정보를 넣지 않는다

W3C Trace Context는 분산 시스템에서 요청을 연결하기 위한 `traceparent`와 `tracestate` 형식을 정의합니다.

W3C는 이 Field에 개인정보나 민감정보를 넣지 말아야 한다고 명시합니다.

다음 방식은 피합니다.

```text
traceId = 사용자 이메일
tracestate = tenant_name=user_name
Span Name = 실제 Prompt 원문
Baggage = Access Token·문서 제목·주민 식별번호
```

Trace ID는 불투명하고 충분히 무작위인 식별자로 생성합니다.

Tenant·Subject 같은 감사 속성은 신뢰할 수 있는 Server Context에서 별도 Field로 기록하고, 외부 Trust Boundary를 넘을 때 전파 범위를 제한합니다.

## 9. Event 시각과 관측 시각을 분리한다

비동기 시스템에서는 Event가 발생한 시각과 중앙 수집기가 본 시각이 다릅니다.

```text
occurredAt
  원래 Component에서 사건이 발생한 시간

observedAt
  Collector가 Event를 관측한 시간

ingestedAt
  중앙 저장소에 Commit된 시간
```

OpenTelemetry Logs Data Model도 `Timestamp`와 `ObservedTimestamp`를 구분합니다.

추가로 다음 값을 기록합니다.

- Component Instance ID
- Queue Event Time
- Attempt 번호
- Workflow Sequence
- Resource Revision
- Clock Synchronization 상태

공동 Event Logging 지침은 일관된 시간 형식과 신뢰할 수 있는 시간 원천을 사용해 여러 시스템의 Event를 연결하도록 권고합니다.

시계가 틀린 Event를 조용히 재작성하지 말고 원래 시각과 관측 시각을 함께 보존합니다.

## 10. 정책 결정은 결과와 근거 Version을 함께 기록한다

`authorized=true` 하나만으로는 나중에 같은 판단을 설명할 수 없습니다.

```json
{
  "eventType": "agent.authorization.decided",
  "decisionId": "dec_opaque_id",
  "subjectId": "usr_opaque_id",
  "actorId": "agt_opaque_id",
  "tenantId": "ten_opaque_id",
  "action": "task.create",
  "resource": {
    "type": "meeting",
    "id": "mtg_opaque_id",
    "revision": 12
  },
  "decision": "ALLOW",
  "reasonCodes": [
    "TENANT_MATCH",
    "TOOL_SCOPE_ALLOWED",
    "OBJECT_ACCESS_ALLOWED"
  ],
  "obligations": [
    "REQUIRE_USER_APPROVAL"
  ],
  "policy": {
    "bundleVersion": "authz_fixture_v8",
    "ruleId": "agent_write_fixture"
  },
  "occurredAt": "2026-07-29T16:14:20.110Z"
}
```

기록할 핵심은 다음과 같습니다.

- Allow·Deny·조건부 결과
- 안정적인 Reason Code
- Policy·Bundle·Rule Version
- 평가한 Subject·Action·Resource·Environment
- Obligation
- Resource Revision
- Decision ID

정책 Engine의 Debug 원문 전체를 Audit Log에 넣기보다 재현에 필요한 최소 Projection을 사용합니다.

## 11. 승인 증거를 실행 인자와 결속한다

사용자가 “삭제 승인” 버튼을 눌렀다는 사실만 기록하면 어떤 대상을 승인했는지 모릅니다.

승인 증거는 다음 값에 결속합니다.

```json
{
  "eventType": "agent.approval.decided",
  "approvalId": "apr_opaque_id",
  "approverId": "usr_opaque_id",
  "decision": "APPROVED",
  "preview": {
    "action": "task.create",
    "targetType": "meeting",
    "targetId": "mtg_opaque_id",
    "targetRevision": 12,
    "inputProjection": {
      "taskCount": 3,
      "assigneeScope": "same_tenant"
    },
    "canonicalInputDigest": "sha256_fixture_input_digest"
  },
  "expiresAt": "2026-07-29T16:19:20Z",
  "occurredAt": "2026-07-29T16:14:20.950Z"
}
```

실행 직전에 대상 Revision과 Canonical Input Digest를 다시 비교합니다.

승인 후 Model이 인자를 바꾸거나 Resource가 수정됐다면 같은 Approval ID를 재사용하지 않습니다.

## 12. Tool 요청·응답과 실제 Side Effect를 분리한다

Tool이 `success=true`를 반환해도 실제 외부 상태 변경이 Commit됐다는 보장은 없습니다.

```text
Tool Call Started
  → Business API Accepted
    → Database Commit
      → Outbox Event
        → External Notification
```

각 단계를 구분합니다.

```json
{
  "eventType": "agent.side_effect.confirmed",
  "toolCallId": "tcl_opaque_id",
  "decisionId": "dec_opaque_id",
  "approvalId": "apr_opaque_id",
  "idempotencyKeyDigest": "sha256_fixture_idempotency_digest",
  "sideEffect": {
    "system": "business-service",
    "operation": "task.created",
    "resourceType": "task",
    "resourceIds": [
      "tsk_opaque_id"
    ],
    "commitRevision": 44,
    "outboxEventIds": [
      "obx_opaque_id"
    ]
  },
  "outcome": "COMMITTED",
  "occurredAt": "2026-07-29T16:14:22.430Z"
}
```

감사 관점에서 중요한 불일치는 다음과 같습니다.

```text
ALLOW Decision은 있는데 실행 없음
실행 시작은 있는데 완료 없음
Tool 성공은 있는데 Commit 없음
ALLOW Decision 없이 Side Effect 발생
하나의 Approval로 서로 다른 Side Effect 발생
동일 Idempotency Key로 여러 Resource 생성
```

## 13. 비동기 작업은 접수와 완료를 별도 Event로 남긴다

HTTP `202 Accepted`는 요청 접수이지 완료가 아닙니다.

Queue·Worker 기반 Agent Workflow는 다음 Event를 연결합니다.

```text
job.requested
job.enqueued
job.started
job.attempted
job.completed | job.failed | job.cancelled
result.committed
result.delivered
```

Job 메시지에는 원문 Credential 대신 다음 재인가 Context를 넣습니다.

- Subject·Actor·Tenant
- Purpose
- 대상 Resource ID·Revision
- Decision·Approval Reference
- Policy Version
- Idempotency Key
- Trace·Workflow·Run ID

오래 실행된 작업은 Side Effect 직전에 현재 권한과 승인을 다시 확인하고 새 Decision Event를 연결합니다.

## 14. Prompt·Tool 입력은 원문 대신 Projection과 Digest를 우선한다

Prompt와 Tool Argument 전체를 저장하면 조사에는 편하지만 개인정보와 기밀정보 위험이 큽니다.

```text
원문 전체
  → 높은 조사 편의
  → 높은 노출·보존·접근 위험

안전한 Projection + Digest + Resource Reference
  → 필요한 판단 증거 유지
  → 원문 노출 최소화
```

예시는 다음과 같습니다.

```json
{
  "inputEvidence": {
    "purpose": "meeting_followup_generation",
    "sourceResourceIds": [
      "mtg_opaque_id"
    ],
    "sourceRevisions": [
      12
    ],
    "inputProjection": {
      "meetingCount": 1,
      "requestedAction": "task.create",
      "requestedTaskCount": 3,
      "destinationClass": "internal"
    },
    "canonicalInputDigest": "sha256_fixture_input_digest",
    "contentStored": false
  }
}
```

Digest는 나중에 제출된 원문이 당시 입력과 같은지 비교하는 데 도움을 주지만, 원문의 의미를 설명하거나 진위를 단독으로 증명하지는 않습니다.

## 15. Model Content 기록은 기본 비활성화하고 별도 통제로 연다

OpenTelemetry GenAI 속성 지침은 Input Message, Output Message, Retrieval Query, Tool Argument와 Result가 민감정보를 포함할 수 있다고 경고합니다.

따라서 다음 내용은 기본 Audit Event에서 제외합니다.

- System Prompt 원문
- 사용자 Prompt 원문
- Conversation 전체
- Retrieved Chunk 본문
- Tool Argument·Result 전체
- Model Response 전체
- Chain-of-thought 또는 내부 추론
- 첨부 File 본문

디버깅이나 사건 대응을 위해 Content Capture가 꼭 필요하면 다음을 별도 적용합니다.

```text
명시적 목적
  + 제한된 대상·기간
    + 승인된 사용자·Tenant
      + 별도 암호화·접근 권한
        + 짧은 Retention
          + 모든 조회 감사
            + 자동 종료
```

Content Capture 설정 변경 자체도 Audit Event입니다.

## 16. Field별 데이터 처리 정책을 만든다

Masking은 `password`라는 이름의 Field만 별표로 바꾸는 작업이 아닙니다.

| 데이터 | 기본 처리 |
|---|---|
| Access·Refresh Token | 저장 금지 |
| Password·API Key·Secret | 저장 금지 |
| Session ID | 필요 시 Keyed Pseudonym |
| 사용자 내부 ID | 목적과 조회 권한에 따라 Tokenize |
| 이름·Email·전화번호 | 제거·부분 Mask·Tokenize |
| 건강·금융·정부 식별정보 | 기본 제거·별도 승인 |
| Prompt·Tool 원문 | 기본 제거 |
| Resource ID | 불투명 ID 또는 감사용 Alias |
| IP·Device ID | 목적별 축소·Mask·짧은 보존 |
| File Path·내부 Host | 필요 최소화·분류 |
| Policy·Reason Code | 원문 민감정보 없이 보존 |
| Digest | 원문 추측 가능성·Key 사용 검토 |

OWASP Logging Cheat Sheet는 Access Token, Password, Encryption Key, 민감한 PII, Connection String과 높은 보안 등급 정보를 직접 기록하지 말고 제거·Mask·Sanitize·Hash·암호화 등을 고려하도록 안내합니다.

정책은 Event Type·Field Path·데이터 분류·목적·환경별로 Versioning합니다.

## 17. Masking·Tokenization·Pseudonymization을 구분한다

각 기법의 목적이 다릅니다.

| 기법 | 예 | 복원 | 주요 용도 |
|---|---|---|---|
| 제거 | Field 자체 미저장 | 불가 | 불필요한 Secret·원문 |
| 부분 Mask | `***-****-1234` | 불가 | 사람이 일부 확인 |
| Tokenization | Vault의 Alias | 통제된 복원 | 사건 조사·권리 요청 |
| Keyed Pseudonym | HMAC 기반 Alias | 직접 복원 불가 | 기간 내 동일 주체 상관 |
| 암호화 | Field Encryption | Key로 복원 | 제한된 원문 증거 |
| 일반 Hash | Digest | 불가 | 무결성 비교, 낮은 Entropy 주의 |

Email·전화번호처럼 가능한 값 공간이 작은 데이터에 단순 SHA-256을 적용하면 사전 대입으로 원문을 추측할 수 있습니다.

상관 분석이 필요하면 별도 Key와 Rotation 정책을 가진 Keyed Pseudonym을 고려합니다.

NIST SP 800-188은 단순 Masking Tool이 충분한 De-identification 기능을 제공한다고 가정하면 안 된다고 설명합니다.

가명처리된 데이터도 다른 정보와 결합해 재식별될 수 있으므로 무조건 익명 데이터로 취급하지 않습니다.

## 18. 수집 전에 Allowlist Redaction을 적용한다

민감정보가 중앙 Backend에 도착한 뒤 Dashboard에서 가리는 것만으로는 늦습니다.

```text
Application Event 생성
  → Schema Allowlist
    → Field Classification
      → Redaction·Tokenization
        → Log Injection Sanitization
          → Collector
            → Audit Store·SIEM
```

OpenTelemetry의 민감정보 처리 지침은 허용된 Attribute만 남기는 Redaction Processor와 Transform Processor 같은 수집 단계 통제를 설명합니다.

두 단계 방어가 유용합니다.

```text
Producer
  Domain을 이해하므로 Tool Argument·Resource Field를 정확히 최소화

Collector
  공통 Secret Pattern·허용 Attribute·목적지별 정책을 추가 적용
```

Collector Redaction이 Producer의 무제한 원문 Logging을 정당화하지는 않습니다.

## 19. Log Injection과 Schema Poisoning을 막는다

Prompt·Tool Result·File Name은 공격자가 제어할 수 있습니다.

줄바꿈과 구분자를 그대로 Text Log에 넣으면 가짜 Event처럼 보이게 할 수 있습니다.

```text
normal value
2026-07-29 ALLOW admin action
```

OWASP는 CR, LF와 Delimiter를 포함한 Event Data를 Sanitize하고 출력 형식에 맞게 Encode하도록 권고합니다.

다음 통제를 적용합니다.

- 구조화된 JSON Event
- Event Type과 Field Allowlist
- String 길이·배열 수·중첩 깊이 제한
- CR·LF·제어 문자 처리
- Enum·ID·Timestamp 형식 검증
- 사용자 입력을 Event Name·Field Name으로 사용 금지
- 높은 Cardinality Field 제한
- Parser 실패 Event와 원본 격리
- Schema Registry와 Compatibility Test

검증 실패 시 전체 Logging을 중단하기보다 안전한 최소 Error Event를 남기고 운영 Alert를 발생시킵니다.

## 20. Audit Schema와 Policy Version을 함께 관리한다

Event Field가 바뀌면 저장소 Query와 탐지 Rule이 깨질 수 있습니다.

```json
{
  "eventType": "agent.tool.execution.completed",
  "eventSchemaVersion": "1.1",
  "auditPolicyVersion": "audit_policy_fixture_v5",
  "dataPolicyVersion": "audit_data_fixture_v3",
  "producerVersion": "agent_runtime_fixture_v7",
  "compatibility": {
    "minimumConsumerVersion": "1.0"
  }
}
```

변경 시 확인할 항목은 다음과 같습니다.

- 필수 Field 추가·삭제
- Enum 의미 변경
- ID 범위와 Cardinality
- 민감정보 분류 변경
- Masking 방식 변경
- 탐지 Rule과 Dashboard 영향
- 보존·Index 영향
- 기존 Event Migration 필요성

Schema·Masking·Retention 변경도 관리자 Audit Event로 남깁니다.

## 21. 업무 Commit과 감사 Event 사이의 원자성을 설계한다

다음 순서는 감사 누락을 만들 수 있습니다.

```text
Database Commit 성공
  → Audit Backend 전송 실패
    → Side Effect는 있지만 Event 없음
```

반대 순서는 거짓 성공을 만들 수 있습니다.

```text
Audit "COMMITTED" 기록
  → Database Commit 실패
    → Event는 성공인데 실제 변경 없음
```

가능한 경우 업무 Transaction과 Outbox Record를 함께 Commit합니다.

```text
Business Transaction
  ├─ Resource 변경
  └─ Side Effect Audit Outbox

Outbox Publisher
  → 중앙 Audit Store
    → Delivery 확인
```

외부 시스템처럼 같은 Transaction을 사용할 수 없으면 `REQUESTED`, `ACCEPTED`, `COMMITTED`, `DELIVERY_CONFIRMED`를 구분하고 Reconciliation합니다.

## 22. Audit Pipeline 장애 정책을 작업 위험별로 정한다

Audit Backend 장애가 모든 서비스 장애로 번지면 가용성이 낮아집니다.

반대로 항상 Fail Open하면 공격자가 Logging을 막고 위험 작업을 실행할 수 있습니다.

| 작업 등급 | 예시 정책 |
|---|---|
| 일반 조회 | 제한된 Local Durable Queue 후 실행 |
| 민감 조회·Export | 감사 수집 확인 또는 축소된 기능 |
| 업무 생성·변경 | Transactional Outbox 필수 |
| 중요 외부 전송 | Durable Audit 없으면 보류 |
| 파괴·권한 변경 | 감사 증거 저장 실패 시 차단 |

NIST SP 800-53의 AU 계열 통제는 Audit Processing 실패 대응과 대체 Logging Capability를 다룹니다.

필요한 운영 상태는 다음과 같습니다.

```text
HEALTHY
DEGRADED
BUFFERING
BACKPRESSURE
FAILED_CLOSED
RECOVERING
```

Queue가 가득 찼을 때 Event를 조용히 버리지 말고 Drop 수, 가장 오래된 Event Age, 예상 복구 시간과 차단된 작업을 Alert합니다.

## 23. 감사 저장소를 Application과 분리하고 변조를 탐지한다

Application 관리자 권한으로 감사 기록을 수정·삭제할 수 있으면 사건 증거를 신뢰하기 어렵습니다.

```text
Producer
  Append 권한만

Audit Ingestion
  Schema·Redaction·Origin 검증

Hot Search
  제한된 기간·Role 기반 조회

Immutable Archive
  장기 보존·변조 방지

Security Analytics
  복제된 최소 Field로 탐지
```

NIST SP 800-53 AU-9는 Audit Information과 Logging Tool을 무단 접근·수정·삭제로부터 보호하는 통제를 제공합니다.

공동 Event Logging 지침도 중앙화, 분리된 저장, 무단 수정·삭제 방지, 암호학적 검증과 접근 제한을 권고합니다.

추가 통제 예시는 다음과 같습니다.

- 별도 Account·Project·Network Segment
- Producer와 Reader·Administrator·Retention Manager 권한 분리
- Append-only 또는 WORM 지원 저장소
- Versioning·Object Lock·Backup
- 전송 TLS와 Origin 인증
- Batch Hash·Signed Checkpoint
- 독립된 무결성 검증 Job
- 감사 저장소 접근 자체의 감사

Hash Chain만으로 Event 생성자의 신뢰성과 누락을 모두 증명할 수는 없습니다.

신뢰할 수 있는 Ingestion, 순서, 외부 Checkpoint와 완전성 검사까지 함께 필요합니다.

## 24. 감사 조회·Export도 감사한다

Audit Store에는 사용자 행동, Resource ID, 거부 이유와 보안 탐지 정보가 모입니다.

조회 권한을 `admin` 하나로 통합하지 않습니다.

```text
Tenant Auditor
  자신의 Tenant Event만

Application Operator
  Content 없이 기술 상태·Correlation 조회

Security Analyst
  승인된 사건·기간·Field 조회

Privacy Officer
  PII 처리와 권리 요청 범위

Audit Administrator
  Storage 운영, 원문 업무 데이터 접근은 별도
```

다음 행위를 기록합니다.

- 검색 Query의 안전한 Projection
- 조회 Tenant·기간·Event Type
- 결과 수와 Export Byte
- Export 목적·승인·Ticket
- 복호화·Token 재식별
- Retention·Legal Hold 변경
- Detection Rule 변경
- 관리자 Break-glass 사용

Export File에도 암호화, 만료, Watermark 또는 Case ID, Download 제한과 삭제 증거를 적용합니다.

## 25. 보존 기간은 Event 목적과 위험으로 정한다

모든 Event를 같은 기간 보존하거나 영구 보존하지 않습니다.

OWASP는 요구된 기간보다 일찍 삭제하지 말고, 그 기간을 넘어 불필요하게 보관하지 않도록 안내합니다.

공동 Event Logging 지침은 기본 Retention이 조사에 부족할 수 있으며 시스템 위험, 규정과 사건 발견 가능성을 고려해 기간을 정하도록 권고합니다.

보존 Policy 입력은 다음과 같습니다.

- 법률·규제·계약 의무
- 감사·보안 탐지 목적
- 예상 사건 발견·조사 기간
- 데이터 민감도와 개인정보 위험
- Resource 수명
- Event의 증거 가치
- 저장·검색 비용
- Tenant 계약과 지역
- 삭제·보존 잠금 요구

```json
{
  "retentionPolicyVersion": "retention_fixture_v4",
  "eventClass": "HIGH_RISK_SIDE_EFFECT",
  "classification": "CONFIDENTIAL_METADATA",
  "tiers": {
    "hotDays": 30,
    "warmDays": 180,
    "coldDays": 730
  },
  "legalHoldEligible": true,
  "disposal": "CRYPTOGRAPHIC_ERASURE_AND_INDEX_DELETE"
}
```

기간은 설명용 Fixture이며 실제 조직 정책이 아닙니다.

## 26. Hot·Warm·Cold Tier와 Legal Hold를 분리한다

보존과 즉시 검색 가능성은 같은 요구가 아닙니다.

| Tier | 용도 | 특성 |
|---|---|---|
| Hot | 실시간 탐지·최근 조사 | 빠른 검색·높은 비용 |
| Warm | 정기 감사·중기 조사 | 제한된 Index |
| Cold | 장기 증거·규정 | 복원 절차·낮은 비용 |
| Legal Hold | 사건·소송 보존 | 일반 삭제 정책 일시 중지 |

Cold Storage로 이동해도 다음이 가능해야 합니다.

- Case별 복원
- Hash·Signature 검증
- Schema Version 해석
- 접근 승인과 조회 감사
- 복원본 자동 만료

삭제 시 Primary Store만 지우고 Search Index, Cache, Export, Backup과 임시 조사 Workspace를 남기지 않습니다.

Legal Hold는 모든 Log를 무기한 보존하는 기능이 아니라 대상, 사유, 승인자, 시작·종료와 검토 주기를 가진 별도 상태입니다.

## 27. 중앙 수집과 정규화로 탐지 가능한 품질을 만든다

공동 Event Logging 지침은 구조화된 형식, 중앙 수집, 정규화, 안전한 저장과 SIEM·XDR 분석을 권고합니다.

중앙화만 하면 자동으로 좋은 Event가 되는 것은 아닙니다.

다음 품질을 측정합니다.

- 필수 Event Coverage
- Schema Parse 성공률
- 필수 Correlation ID 존재율
- Event 발생부터 Ingest까지 지연
- Clock Skew
- Duplicate·Out-of-order 비율
- Unknown Event Type
- Redaction 위반
- Tenant 누락
- Side Effect 대비 Audit Event 비율
- Producer Version별 품질

OpenTelemetry Event는 Event Name, Timestamp, Trace ID, Span ID, Severity, Resource와 Attributes를 공통 구조로 표현할 수 있습니다.

내부 도메인 Event를 표준 Signal로 내보낼 때 의미를 잃지 않도록 Mapping Contract를 Test합니다.

## 28. 탐지 규칙은 Decision과 Side Effect의 불일치를 본다

AI Agent 특화 탐지는 단순 Error Count보다 통제 간 불일치가 중요합니다.

| 탐지 | 의미 |
|---|---|
| ALLOW 없이 Side Effect | 인가 우회·감사 누락 |
| Approval 없이 중요 Tool 실행 | 승인 우회 |
| Approval Digest와 실행 Digest 불일치 | TOCTOU·인자 변경 |
| DENY 뒤 인자만 바꾼 반복 호출 | 정책 탐색·우회 시도 |
| 한 Subject의 여러 Tenant 접근 | Tenant 경계 이상 |
| Agent Version 변경 후 Tool 급증 | 배포 이상·오용 |
| Read Tool의 비정상 대량 결과 | 데이터 수집 |
| 외부 Egress Destination 변화 | 유출 가능성 |
| 동일 Idempotency Key의 다중 Resource | 중복 Side Effect |
| Audit Event Drop·Lag 증가 | 탐지 회피·장애 |
| Logging·Retention 설정 변경 | 증거 약화 시도 |
| Audit Export 급증 | 내부자·계정 탈취 |

예시 탐지 Query는 다음과 같습니다.

```sql
SELECT s.tool_call_id, s.resource_id, s.occurred_at
FROM side_effect_event s
LEFT JOIN authorization_event a
  ON a.decision_id = s.decision_id
 AND a.decision = 'ALLOW'
WHERE s.occurred_at >= :window_start
  AND a.decision_id IS NULL;
```

Hard Rule과 Baseline을 함께 사용합니다.

`ALLOW 없는 Side Effect`는 즉시 조사할 수 있지만, “평소보다 Tool 호출이 많음”은 사용자 역할·시기·업무량 Context가 필요합니다.

## 29. Alert에서 사고 대응 증거 Package까지 연결한다

Alert는 결론이 아니라 조사 시작점입니다.

```json
{
  "alertId": "alt_opaque_id",
  "ruleId": "agent_side_effect_without_allow",
  "ruleVersion": "rule_fixture_v2",
  "severity": "HIGH",
  "detectedAt": "2026-07-29T16:15:00Z",
  "evidence": {
    "eventIds": [
      "evt_opaque_id"
    ],
    "workflowIds": [
      "wfl_opaque_id"
    ],
    "traceIds": [
      "0123456789abcdef0123456789abcdef"
    ],
    "resourceIds": [
      "tsk_opaque_id"
    ]
  },
  "recommendedPlaybook": "agent_unauthorized_side_effect_fixture"
}
```

사고 대응 흐름은 다음과 같습니다.

```text
Detect
  → Triage
    → Preserve Evidence
      → Scope Subject·Agent·Tool·Tenant·Resource
        → Contain Token·Agent·Tool·Egress
          → Eradicate 원인
            → Recover·Reconcile Side Effect
              → Notify·Report
                → Lessons Learned·Rule Update
```

NIST SP 800-61 Rev. 3은 Incident Response를 Cybersecurity Risk Management 전반에 통합해 탐지·대응·복구의 효과를 높이는 지침을 제공합니다.

Evidence Package에는 다음을 포함합니다.

- Case ID와 조사 목적
- Event Query 조건·시간 범위
- Event·Trace·Decision·Approval·Resource ID
- Export 시각·담당자·승인
- File·Batch Hash와 Signature
- Schema·Policy·Rule Version
- Time Source와 알려진 Clock Skew
- 누락·Drop·Pipeline 장애
- Chain of Custody
- 보존 잠금과 종료 조건

원문 Prompt가 없어도 정책과 Side Effect를 재구성할 수 있는지를 평소에 시험합니다.

## 30. 운영 전 체크리스트와 Negative Test

### Event·Identity

- [ ] Application Log, Trace, Audit Event와 Security Alert 목적을 분리한다.
- [ ] 필수 Audit Event는 Trace Sampling과 무관하게 남긴다.
- [ ] Event Taxonomy와 Schema Version을 중앙 관리한다.
- [ ] Subject·Actor·Client·Executor·Approver·Tenant를 구분한다.
- [ ] Workflow·Run·Trace·Tool Call·Decision·Approval·Job·Event ID를 연결한다.
- [ ] Trace Context에 PII·Tenant 이름·Credential을 넣지 않는다.
- [ ] occurredAt·observedAt·ingestedAt과 Clock 상태를 추적한다.

### Decision·Approval·Side Effect

- [ ] Allow·Deny, Reason, Policy Version, Resource Revision을 기록한다.
- [ ] 승인 증거를 대상·Revision·Canonical Input Digest와 결속한다.
- [ ] Tool 요청·응답과 실제 Business Commit을 구분한다.
- [ ] Side Effect Event가 Decision·Approval·Idempotency Key를 참조한다.
- [ ] 비동기 접수·시도·완료·결과 Commit을 별도 Event로 남긴다.
- [ ] 오래 실행된 Workflow는 Side Effect 직전에 다시 인가한다.
- [ ] 업무 Commit과 Audit Outbox를 가능한 한 같은 Transaction에 둔다.

### 개인정보·Content

- [ ] Prompt·System Instruction·Retrieved Chunk·Tool 원문을 기본 저장하지 않는다.
- [ ] Access Token·Password·API Key·Secret·Connection String을 저장 금지한다.
- [ ] 원문 대신 Resource Reference·안전한 Projection·Digest를 우선한다.
- [ ] Mask·Tokenization·Keyed Pseudonym·암호화의 목적을 구분한다.
- [ ] Producer와 Collector 양쪽에서 Allowlist Redaction을 수행한다.
- [ ] Log Injection을 막도록 CR·LF·Delimiter·길이·Schema를 검증한다.
- [ ] Content Capture는 목적·승인·대상·기간·조회 감사와 자동 종료를 가진다.

### 저장·접근·보존

- [ ] Application 권한과 분리된 중앙 Audit Store를 사용한다.
- [ ] Producer는 Append 중심 최소 권한만 가진다.
- [ ] 전송·저장 암호화와 Origin 검증을 적용한다.
- [ ] 무단 수정·삭제를 제한하고 Hash·Checkpoint로 탐지한다.
- [ ] Audit 조회·Export·재식별·Retention 변경도 감사한다.
- [ ] Tenant·운영·보안·개인정보 역할별 조회 범위를 분리한다.
- [ ] Event 목적·위험·법규에 따라 Hot·Warm·Cold 보존을 정한다.
- [ ] Legal Hold에 대상·사유·승인·검토·종료 조건을 둔다.
- [ ] 만료 시 Index·Cache·Export·Backup·복원본 삭제를 추적한다.

### 탐지·대응·검증

- [ ] ALLOW·Approval·Side Effect 불일치 탐지 Rule이 있다.
- [ ] Tenant 우회·대량 조회·Egress 변화·Audit 설정 변경을 탐지한다.
- [ ] Audit Drop·Lag·Parse Error·Redaction 위반을 운영 Metric으로 본다.
- [ ] Alert가 Event·Trace·Decision·Resource와 대응 Playbook을 참조한다.
- [ ] Incident Evidence Export와 Chain of Custody 절차를 시험한다.
- [ ] 감사 Pipeline 장애 시 위험 등급별 Buffer·Degrade·Fail Closed 정책을 시험한다.

Negative Test에는 다음을 포함합니다.

1. ALLOW Decision 없이 Side Effect 생성 시도
2. 승인 Digest와 다른 Tool 인자 실행
3. 같은 Approval로 다른 Resource 변경
4. 동일 Idempotency Key로 중복 Resource 생성
5. 비동기 Worker에서 Subject·Tenant 누락
6. Trace Sampling 0%에서도 필수 Audit Event 생성
7. Prompt·Tool Argument에 Canary Token·Email·전화번호 삽입
8. CR·LF와 JSON 중첩으로 Log Injection 시도
9. 알 수 없는 Event Schema Version 전송
10. Audit Collector 연결 중단과 Queue 포화
11. Producer가 과거 Audit Event 수정·삭제 시도
12. 다른 Tenant의 Audit Query와 Export 시도
13. Retention 만료 후 Hot·Cold·Index·Export 잔존 검사
14. Legal Hold 대상의 자동 삭제 방지
15. 늦게 도착한 Event와 Clock Skew가 Timeline을 오염시키는지 검사
16. Audit 설정 변경과 Break-glass 사용 Event 누락 검사
17. Evidence Package Hash·Signature 변조 검사
18. Alert에서 실제 Side Effect까지 역추적

핵심 운영 지표는 다음과 같습니다.

```text
필수 Audit Event Coverage
Side Effect without ALLOW Count
Side Effect without Approval Count
Audit Ingestion Lag
Audit Event Drop·Parse Failure
Missing Correlation ID Rate
Sensitive Field Violation Count
Duplicate·Out-of-order Event Rate
Retention Disposal Completion
Audit Query·Export Anomaly
Mean Time to Scope Agent Incident
```

## 마무리

AI Agent 감사 흐름은 다음과 같이 정리할 수 있습니다.

```text
인증된 Subject·Tenant
  → Workflow·Run·Trace Context
    → 정책 Decision과 Version
      → 대상·인자에 결속된 Approval
        → Tool Execution Attempt
          → 실제 Side Effect Commit
            → 구조화된 Audit Event
              → 수집 전 Data Minimization·Masking
                → 중앙 무결성 보호 저장
                  → Risk 기반 Retention
                    → Decision·Side Effect 불일치 탐지
                      → Evidence Package·Incident Response
```

핵심 원칙은 다음과 같습니다.

1. Trace와 Application Log를 Audit Event의 대체물로 사용하지 않습니다.
2. 모델의 설명이 아니라 Policy Enforcement Point와 Business Service의 실제 판단·Commit을 기록합니다.
3. Subject·Actor·Executor·Approver와 Tenant를 분리해 책임 Chain을 보존합니다.
4. Decision·Approval·Tool Call·Side Effect를 ID와 Digest로 연결합니다.
5. Prompt·Tool Argument·Result 원문은 기본 저장하지 않고 Projection·Reference·Digest를 사용합니다.
6. 민감정보는 Backend 도착 전 Producer와 Collector에서 Allowlist 방식으로 제거합니다.
7. 감사 저장소의 수정·삭제·조회·Export 권한도 별도 통제하고 감사합니다.
8. 보존 기간은 “영구”가 아니라 Event 목적·위험·법규·개인정보를 기반으로 정합니다.
9. ALLOW·Approval·Side Effect 불일치를 탐지하고 즉시 대응 Playbook으로 연결합니다.
10. Audit Pipeline 장애·Sampling·중복·Clock Skew·Retention 삭제까지 Negative Test로 검증합니다.

AI Agent 감사의 목표는 “무슨 일이 있었는지 추측할 수 있는 많은 로그”가 아닙니다.

**필요한 개인정보를 최소화하면서도 누가 어떤 정책과 승인으로 무엇을 실행했고 실제 외부 상태가 어떻게 바뀌었는지를 신뢰할 수 있게 재구성하는 것**입니다.

이 글로 AI Agent·MCP·RAG·파일 처리와 보안 운영을 연결한 27편 기술자료 로드맵의 초안 작성을 마무리합니다.

## 참고 자료

- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [OWASP Logging Vocabulary Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html)
- [NIST Log Management Project](https://csrc.nist.gov/Projects/log-management)
- [NIST SP 800-92: Guide to Computer Security Log Management](https://csrc.nist.gov/pubs/sp/800/92/final)
- [NIST SP 800-53 Rev. 5: Security and Privacy Controls](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)
- [NIST SP 800-122: Protecting the Confidentiality of PII](https://csrc.nist.gov/pubs/sp/800/122/final)
- [NIST SP 800-188: De-Identifying Government Datasets](https://csrc.nist.gov/pubs/sp/800/188/final)
- [NIST SP 800-61 Rev. 3: Incident Response Recommendations](https://csrc.nist.gov/pubs/sp/800/61/r3/final)
- [Joint Guidance: Best Practices for Event Logging and Threat Detection](https://www.cyber.gov.au/business-government/detecting-responding-to-threats/event-logging/best-practices-for-event-logging-and-threat-detection)
- [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)
- [OpenTelemetry Semantic Conventions for Events](https://opentelemetry.io/docs/specs/semconv/general/events/)
- [OpenTelemetry GenAI Attributes and Sensitive Content Warnings](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
- [OpenTelemetry: Handling Sensitive Data](https://opentelemetry.io/docs/security/handling-sensitive-data/)
- [OpenTelemetry: Trace Context in non-OTLP Log Formats](https://opentelemetry.io/docs/specs/otel/compatibility/logging_trace_context/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [MCP Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [MCP Debugging: Structured Logging and Sensitive Data](https://modelcontextprotocol.io/docs/tools/debugging)

---

> 이 글은 2026년 7월 29일 기준 OWASP, NIST, CISA가 공동 참여한 Event Logging 지침, OpenTelemetry, W3C와 MCP의 공식 공개 자료 및 공개 가능한 엔터프라이즈 AI Agent 감사 설계 경험을 바탕으로 작성했습니다. 예시 ID, Event, Policy, Schema, Masking 방식, Hash, Retention 기간, Detection Rule과 Incident Playbook은 설명용 Fixture이며 실제 고객·Tenant·사용자·계정·Prompt·Tool Result·내부 시스템 정보가 아닙니다. 실제 적용 시 조직의 데이터 분류, 개인정보 처리 목적과 법적 근거, Tenant 계약, Identity·Authorization·Approval 구조, SIEM·Audit Storage, Incident Response 절차, 보존·삭제·Legal Hold 의무와 운영 위험을 검토하고 필수 Event Coverage·민감정보 Canary·Audit Pipeline 장애·변조·권한 우회·보존 만료 Negative Test로 검증해야 합니다.
