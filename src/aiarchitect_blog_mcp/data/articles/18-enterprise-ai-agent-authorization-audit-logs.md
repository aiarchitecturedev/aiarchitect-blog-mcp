# Tistory 기술자료 초안

- 문서 ID: `BLOG-18`
- 상태: 공개 완료
- Tistory 상태: 2026-07-30 공개 게시 및 공개 페이지 검증 완료
- 분류: `엔터프라이즈 아키텍처`
- 공개 URL: https://aiarchitect.tistory.com/19
- 권장 제목: `엔터프라이즈 AI Agent 권한 설계: 사용자·테넌트·Tool 인가와 감사 로그`
- 검색 설명: `AI Agent가 기업 데이터를 조회하고 Tool을 실행할 때 사용자, 테넌트, 객체, 작업과 환경 속성을 결합해 권한을 판단하고 정책 결정부터 실제 실행 결과까지 감사 로그로 연결하는 아키텍처를 정리합니다.`
- 권장 태그: `AI Agent`, `MCP`, `Authorization`, `Multi-tenancy`, `ABAC`, `OPA`, `Audit Log`, `엔터프라이즈 아키텍처`
- 권장 대표 이미지: `portfolio/architecture-diagrams/04-mcp-enterprise-integration.svg`

---

# 엔터프라이즈 AI Agent 권한 설계: 사용자·테넌트·Tool 인가와 감사 로그

사용자가 AI Agent에게 요청합니다.

```text
“지난주 회의의 결정 사항을 찾아 줘.”
“이 회의의 후속 업무를 등록해 줘.”
“완료된 회의를 다른 조직으로 옮겨 줘.”
```

Agent는 자연어를 이해하고 회의 검색, 요약 조회, 업무 생성과 회의 이동 Tool을 선택합니다.

이때 “사용자가 로그인했다”는 사실만으로는 어느 요청도 실행할 수 없습니다.

```text
로그인됨
≠ 모든 Tenant 접근 가능
≠ 모든 Tool 실행 가능
≠ 모든 객체 변경 가능
≠ 현재 업무 상태에서 허용됨
```

더 어려운 문제는 실행 주체가 하나가 아니라는 점입니다.

```text
사용자
  → AI Client
    → Agent Runtime
      → MCP Server
        → Business API
          → Database
```

최종 Database 변경은 Service Account가 수행할 수 있지만, 업무 의도는 사용자에게서 시작됐습니다.

운영 시스템은 다음 질문에 답할 수 있어야 합니다.

- 누가 요청했는가?
- 어떤 Agent와 Service가 사용자를 대신해 실행했는가?
- 어느 Tenant의 어떤 객체에 접근했는가?
- 어떤 Tool과 작업이 허용됐는가?
- 어느 정책 Version이 허용 또는 거부했는가?
- 승인이 필요했다면 누가 무엇을 승인했는가?
- 실제 Side Effect (외부 상태 변화)는 성공했는가?
- 나중에 같은 결정을 재구성할 수 있는가?

이 글에서는 **사용자·테넌트·Tool·객체 단위 인가 (Authorization)를 하나의 정책 흐름으로 연결하고, 정책 결정과 실제 실행을 감사 로그 (Audit Log)로 증명하는 방법**을 정리합니다.

## 1. 인증, 인가, 승인과 감사는 서로 다른 통제다

네 개념을 먼저 분리합니다.

| 통제 | 질문 | 대표 결과 |
|---|---|---|
| 인증 (Authentication) | 요청자가 누구인가? | 검증된 Principal |
| 인가 (Authorization) | 이 작업을 이 대상에 수행할 수 있는가? | Allow·Deny·조건 |
| 승인 (Approval) | 사용자가 이 구체적 실행에 동의했는가? | 승인 Grant |
| 감사 (Audit) | 어떤 판단과 실행이 실제로 일어났는가? | 무단 변경·삭제를 방지한 증거 |

인증은 신원을 확인하지만 업무 권한을 결정하지 않습니다.

인가는 일반적인 실행 가능성을 판단하지만 위험한 작업의 현재 실행 의사까지 증명하지 않습니다.

승인은 특정 실행 의사를 확인하지만 원래 없는 권한을 만들어 주지 않습니다.

감사는 앞선 통제를 대신하지 않고, 결정과 실행이 정책대로 작동했는지 나중에 확인할 증거를 남깁니다.

```text
실행 허용
  = 인증된 신원
  ∩ Tenant 경계
  ∩ Tool·Action 권한
  ∩ 객체 권한
  ∩ 업무 상태 조건
  ∩ 필요한 경우 유효한 승인
```

## 2. 권한 검사는 한 번이 아니라 여러 경계에서 수행한다

각 계층은 서로 다른 질문을 담당합니다.

```text
Security Gateway
  └─ 이 사용자가 AI 기능에 접근할 수 있는가?

Agent Runtime
  └─ 이 Workflow에서 이 Tool을 후보로 제공할 수 있는가?

MCP Server
  └─ 이 Principal이 이 Tool Action을 호출할 수 있는가?

Business Service
  └─ 이 Principal이 이 Tenant의 이 객체에 작업할 수 있는가?

Database·Storage
  └─ 잘못된 Tenant 접근을 마지막으로 제한할 수 있는가?
```

Gateway에서 인증과 Scope 검사를 통과했다고 하위 서비스가 권한 검사를 생략하면 안 됩니다.

모델이 생성한 객체 ID, Tool 인자와 이전 대화의 권한 판단은 현재 실행의 권한 증명이 아닙니다.

OWASP API Security의 Broken Object Level Authorization (객체 수준 인가 실패)은 Client가 전달한 객체 식별자를 사용하는 모든 Endpoint가 로그인 사용자에게 해당 작업 권한이 있는지 확인해야 한다고 설명합니다.

최종 업무 Service가 매 요청마다 객체 단위 권한을 검사해야 하는 이유입니다.

## 3. Principal을 사용자 하나로 단순화하지 않는다

AI Agent 실행에는 여러 신원이 참여합니다.

| 역할 | 의미 | 예시 |
|---|---|---|
| Subject (주체) | 권한이 행사되는 사용자 | 요청한 사용자 |
| Actor (행위자) | 실제로 호출을 수행하는 주체 | Agent Runtime |
| Client (클라이언트) | 사용자가 이용한 Application | 사내 AI Portal |
| Executor (실행자) | Downstream에서 실행한 Service Identity | MCP Server Service Account |
| Approver (승인자) | 위험 작업을 승인한 사용자 | 요청자 또는 관리자 |

사용자가 직접 API를 호출하면 Subject와 Actor가 같을 수 있습니다.

Agent가 사용자를 대신해 호출하면 둘을 분리해야 합니다.

```json
{
  "principal": {
    "subjectId": "user_fixture_001",
    "actor": {
      "type": "AI_AGENT",
      "id": "agent_runtime_fixture_001"
    },
    "clientId": "client_fixture_001",
    "tenantId": "tenant_fixture_001"
  }
}
```

Service Account만 감사 로그에 남기면 어느 사용자의 요청인지 알 수 없습니다.

반대로 사용자만 남기면 어느 Agent·Service가 실제 실행했는지 알 수 없습니다.

## 4. 위임 (Delegation)과 가장 (Impersonation)을 구분한다

RFC 8693 OAuth 2.0 Token Exchange는 한 Service가 사용자를 대신해 Downstream Service를 호출할 때 Delegation (위임)과 Impersonation (가장)을 구분합니다.

```text
Delegation
  Agent A가 사용자 B를 대신해 행동
  A와 B의 신원이 모두 보임

Impersonation
  제한된 Context에서 Agent A가 사용자 B처럼 행동
  Downstream에는 B가 주체로 보일 수 있음
```

감사 가능성이 중요하다면 실행 Chain을 보존하는 위임 모델이 유리합니다.

```json
{
  "delegation": {
    "subject": "user_fixture_001",
    "actor": "agent_runtime_fixture_001",
    "executor": "mcp_server_fixture_001",
    "scope": [
      "meeting:read",
      "task:create"
    ],
    "expiresAt": "2026-07-29T12:30:00Z"
  }
}
```

외부 Access Token 전체를 Queue·Prompt·Tool 인자에 복사하지 않습니다.

Downstream Service에 필요한 좁은 Audience, Scope와 짧은 수명을 가진 Credential을 발급하거나, Service Identity와 검증된 Delegation Context를 결합합니다.

## 5. Tenant는 사용자가 입력하는 필드가 아니다

다음 Tool 입력은 위험합니다.

```json
{
  "tool": "meeting.search",
  "arguments": {
    "tenantId": "tenant_fixture_other",
    "keyword": "분기 계획"
  }
}
```

모델 또는 사용자가 `tenantId`를 자유롭게 선택할 수 있다면 다른 조직으로의 수평 권한 상승이 가능해질 수 있습니다.

Tenant Context (테넌트 문맥)는 검증된 인증과 조직 소속에서 결정합니다.

```text
Access Token·Session
  → Subject 확인
  → 허용 Tenant Membership 확인
  → 현재 Tenant 선택
  → 서버가 Execution Context에 주입
```

Tool 인자에 Tenant가 필요하더라도 Client 값과 서버가 확정한 Tenant를 비교하고 불일치하면 거부합니다.

```javascript
function resolveTenant(authContext, requestedTenantId) {
  const activeTenantId = authContext.activeTenantId;

  if (requestedTenantId && requestedTenantId !== activeTenantId) {
    throw new Error("TENANT_CONTEXT_MISMATCH");
  }

  return activeTenantId;
}
```

내부 Header도 외부 사용자가 주입할 수 없도록 Gateway가 제거하고 검증된 값으로 다시 구성합니다.

## 6. 테넌트 격리는 애플리케이션 Filter 하나로 끝나지 않는다

Multi-tenancy (멀티테넌시) 구조는 규모와 위험도에 따라 다를 수 있습니다.

| 방식 | 장점 | 주의점 |
|---|---|---|
| 공유 DB·공유 Schema | 운영 단순·비용 효율 | 모든 Query의 Tenant 조건 필요 |
| 공유 DB·Tenant별 Schema | 논리 격리 강화 | Migration·Connection 관리 |
| Tenant별 Database | 강한 격리 | 운영·비용 증가 |

어느 방식을 선택해도 다음 계층을 함께 검토합니다.

- API와 Tool의 Tenant Context 고정
- Repository의 Tenant 조건
- Database Row-level Security 또는 별도 계정
- Object Storage Prefix·Bucket Policy
- Search Index Namespace와 Filter
- Cache Key의 Tenant 포함
- Queue Message의 Tenant Context
- Audit Log 조회 권한

예를 들어 Cache Key에 Tenant가 빠지면 다른 조직의 결과가 재사용될 수 있습니다.

```text
잘못된 Cache Key
  summary:{meetingId}

권장 Cache Key
  summary:{tenantId}:{meetingId}:{version}
```

불투명한 UUID를 사용해도 Tenant 권한 검사는 생략할 수 없습니다.

## 7. RBAC만으로 부족한 조건은 ABAC로 보완한다

Role-based Access Control (역할 기반 접근 제어, RBAC)은 역할별 기본 권한을 관리하기 쉽습니다.

```text
VIEWER
  회의 조회

EDITOR
  회의 수정·요약 재생성

MANAGER
  구성원·정책 관리
```

하지만 실제 업무 권한은 역할만으로 결정되지 않을 수 있습니다.

- 사용자가 해당 Group의 구성원인가?
- 객체의 보안 등급은 무엇인가?
- 대상 회의가 보존 잠금 상태인가?
- 외부 전송 목적지가 허용 Domain인가?
- 업무 시간이거나 관리형 Device인가?
- 요청 수량과 비용이 정책 범위 안인가?

NIST SP 800-162의 Attribute-based Access Control (속성 기반 접근 제어, ABAC)은 Subject, Object, Operation과 Environment 속성을 정책과 비교해 허용 작업을 결정하는 방식입니다.

```text
Decision =
  Policy(
    Subject Attributes,
    Object Attributes,
    Action,
    Environment Attributes
  )
```

RBAC를 버리고 ABAC로 교체한다는 뜻은 아닙니다.

역할은 Subject Attribute 중 하나로 사용하고, 객체 관계와 환경 조건을 추가합니다.

## 8. 권한 판단 입력을 구조화한다

Policy Engine이 Tool 이름만 받으면 충분한 결정을 내릴 수 없습니다.

```json
{
  "subject": {
    "id": "user_fixture_001",
    "tenantId": "tenant_fixture_001",
    "roles": [
      "EDITOR"
    ],
    "groupIds": [
      "group_fixture_001"
    ]
  },
  "actor": {
    "type": "AI_AGENT",
    "id": "agent_runtime_fixture_001",
    "clientId": "client_fixture_001"
  },
  "action": {
    "tool": "meeting.transfer",
    "operation": "TRANSFER"
  },
  "resource": {
    "type": "MEETING",
    "id": "meeting_fixture_001",
    "tenantId": "tenant_fixture_001",
    "groupId": "group_fixture_001",
    "classification": "INTERNAL",
    "state": "COMPLETE"
  },
  "environment": {
    "channel": "AI_AGENT",
    "requestTime": "2026-07-29T12:00:00Z",
    "managedDevice": true
  }
}
```

정책 입력에는 필요한 최소 속성만 전달합니다.

회의 제목, 전체 녹취록, Access Token과 Prompt 원문을 넣지 않습니다.

## 9. Tool 권한과 객체 권한을 분리한다

두 검사는 서로 다른 질문입니다.

```text
Tool 권한
  이 Principal이 meeting.transfer 기능을 사용할 수 있는가?

객체 권한
  이 Principal이 meeting_fixture_001을 옮길 수 있는가?
```

`meeting:transfer` Scope가 있어도 모든 회의를 옮길 수 있는 것은 아닙니다.

반대로 객체 Owner라도 Client에 해당 Tool Capability가 허용되지 않았다면 Agent를 통한 실행은 거부할 수 있습니다.

| 계층 | 확인 항목 |
|---|---|
| OAuth Scope | Client가 어떤 Capability를 요청했는가 |
| Agent Policy | 이 Workflow에서 Tool이 허용되는가 |
| Tool Policy | Principal이 이 Action을 실행할 수 있는가 |
| Object Policy | 대상 Tenant·Group·Owner 관계가 허용되는가 |
| Domain Rule | 현재 상태에서 이동 가능한가 |

MCP Authorization 문서는 최소 권한 Scope를 사용하고 가능하면 Tool 또는 Capability별로 접근을 나누도록 안내합니다.

하지만 OAuth Scope는 거친 권한 경계입니다.

최종 객체와 업무 상태 검사는 Resource Server가 수행합니다.

## 10. Tool 목록 필터링은 보안 경계가 아니다

사용자별로 허용된 Tool만 목록에 보여 주면 Model의 잘못된 선택을 줄일 수 있습니다.

```text
VIEWER
  meeting.search
  meeting.summary.get

EDITOR
  + meeting.summary.request
  + task.create
```

하지만 목록에서 숨겼다고 호출이 불가능한 것은 아닙니다.

공격자 또는 잘못된 Client가 `tools/call`을 직접 구성할 수 있기 때문입니다.

```text
Tool Discovery Filter
  사용성과 노출 최소화

Tool Execution Authorization
  실제 보안 경계
```

실행 Endpoint가 매 호출을 다시 인가해야 합니다.

MCP Tool Annotation도 위험도와 동작을 설명하는 Hint (힌트)일 뿐, 신뢰할 수 있는 서버에서 온 경우가 아니면 보안 정책으로 사용해서는 안 됩니다.

## 11. 정책 결정과 정책 집행을 분리한다

Policy Decision Point (정책 결정 지점, PDP)와 Policy Enforcement Point (정책 집행 지점, PEP)를 분리합니다.

```text
Agent Runtime
  │ Tool Intent
  ▼
Policy Enforcement Point
  │ Subject·Actor·Action·Resource·Environment
  ▼
Policy Decision Point
  │ Allow·Deny + Obligations + Decision ID
  ▼
MCP Tool Adapter
  │ Enforce Obligations
  ▼
Business Service
  │ Object-level Reauthorization
  ▼
Side Effect
```

보조 구성요소는 다음과 같습니다.

| 구성요소 | 역할 |
|---|---|
| Policy Administration Point (PAP) | 정책 작성·승인·Version 관리 |
| Policy Information Point (PIP) | 사용자·조직·객체 속성 제공 |
| Policy Decision Point (PDP) | 정책 평가 |
| Policy Enforcement Point (PEP) | 결정과 의무 사항 집행 |

PDP가 허용했더라도 PEP가 승인 확인, 입력 Masking과 Rate Limit 같은 Obligation (의무 사항)을 적용하지 못하면 실행하지 않습니다.

## 12. 정책 결과는 Boolean보다 풍부해야 한다

단순 `allow=true`는 실행 조건을 전달할 수 없습니다.

```json
{
  "decisionId": "decision_fixture_001",
  "allowed": true,
  "policyVersion": "agent_authz_2026_07_29_v3",
  "reasonCodes": [
    "SUBJECT_IS_GROUP_MEMBER",
    "TOOL_SCOPE_ALLOWED"
  ],
  "obligations": {
    "approvalRequired": true,
    "maskFields": [
      "participantEmail"
    ],
    "maxRecords": 1,
    "reauthorizeBeforeCommit": true
  },
  "expiresAt": "2026-07-29T12:05:00Z"
}
```

거부도 구조화합니다.

```json
{
  "decisionId": "decision_fixture_002",
  "allowed": false,
  "policyVersion": "agent_authz_2026_07_29_v3",
  "reasonCodes": [
    "TARGET_TENANT_MISMATCH"
  ],
  "safeMessage": "요청한 대상에 대한 권한이 없습니다."
}
```

사용자 응답에는 내부 정책 구조를 과도하게 노출하지 않고, 상세 Reason Code는 감사와 운영 진단에 사용합니다.

## 13. OPA 정책 예시: 역할·Tenant·객체 관계를 함께 본다

Open Policy Agent (오픈 정책 에이전트, OPA)를 사용한다면 정책을 실행 코드와 분리할 수 있습니다.

```rego
package agent.authz

default allow := false

allow if {
  input.subject.tenantId == input.resource.tenantId
  input.action.tool == "meeting.summary.get"
  input.subject.roles[_] in {"VIEWER", "EDITOR", "MANAGER"}
  input.resource.groupId in input.subject.groupIds
}

allow if {
  input.subject.tenantId == input.resource.tenantId
  input.action.tool == "task.create"
  input.subject.roles[_] in {"EDITOR", "MANAGER"}
  input.resource.groupId in input.subject.groupIds
}
```

설명용 정책은 단순화되어 있습니다.

운영 정책에는 Null·Unknown 속성 처리, Default Deny (기본 거부), 정책 Version, Test와 배포 승인 절차가 필요합니다.

## 14. 객체 권한은 모든 상세·변경 Endpoint에서 재검사한다

목록 조회에서 권한 Filter를 적용했다고 상세 API가 안전해지는 것은 아닙니다.

공격자는 다른 경로에서 얻은 식별자를 직접 넣을 수 있습니다.

```text
GET /meetings
  → Tenant Filter 적용

GET /meetings/{meetingId}
  → 다시 객체 권한 확인

POST /meetings/{meetingId}/transfer
  → 다시 객체·Action·상태 확인
```

Repository 수준에서도 Tenant 조건을 강제합니다.

```sql
SELECT meeting_id, title, state
FROM meeting
WHERE tenant_id = :tenant_id
  AND meeting_id = :meeting_id;
```

`meeting_id`만으로 조회한 뒤 Application에서 Tenant를 비교하는 방식은 실수로 데이터가 노출될 여지를 늘립니다.

가능하면 Query 자체가 Tenant 경계를 포함하도록 만듭니다.

## 15. 업무 상태도 인가 입력이다

권한이 있는 사용자라도 모든 상태 전이를 수행할 수 있는 것은 아닙니다.

```text
DRAFT → COMPLETE
COMPLETE → ARCHIVED
ARCHIVED → 삭제 제한
LEGAL_HOLD → 이동·삭제 금지
```

인가와 업무 검증을 다음처럼 구분할 수 있습니다.

```text
Authorization
  이 Principal이 TRANSFER Action을 수행할 수 있는가?

Domain Validation
  현재 Resource State에서 TRANSFER가 가능한가?
```

둘 다 통과해야 실행합니다.

감사 로그에는 거부 주체를 구분합니다.

```text
AUTHZ_DENIED
DOMAIN_PRECONDITION_FAILED
APPROVAL_REQUIRED
EXECUTION_FAILED
```

모두 “권한 없음”으로 합치면 정책 문제와 업무 상태 문제를 구분할 수 없습니다.

## 16. 장시간 Workflow는 실행 직전에 다시 인가한다

AI Workflow가 승인 대기, Queue와 재시도를 거치면 최초 판단 후 시간이 흐릅니다.

그 사이 다음 값이 바뀔 수 있습니다.

- 사용자 역할
- Group 소속
- Tenant 상태
- 객체 Owner와 보안 등급
- Tool 정책
- 승인 유효기간
- 대상 객체 Version

```text
요청 시점
  Policy Decision = Allow

3시간 후 실행 시점
  사용자 Group 탈퇴
  Resource가 Legal Hold 상태로 전환
```

최초 결정을 그대로 재사용하지 않고 Side Effect 직전에 현재 상태로 다시 인가합니다.

```json
{
  "reauthorization": {
    "previousDecisionId": "decision_fixture_001",
    "newDecisionId": "decision_fixture_003",
    "resourceVersion": 18,
    "allowed": false,
    "reasonCodes": [
      "SUBJECT_NO_LONGER_GROUP_MEMBER"
    ]
  }
}
```

## 17. 감사 로그는 일반 Application Log와 목적이 다르다

Application Log는 장애 진단과 성능 분석을 위해 상세한 내부 상태를 기록할 수 있습니다.

Audit Log는 책임 추적과 정책 준수 증거를 위해 보존합니다.

| 구분 | Application Log | Audit Log |
|---|---|---|
| 목적 | 장애·성능 진단 | 보안·업무 책임 추적 |
| 내용 | Exception, 내부 단계 | Actor, Action, Resource, Decision, Outcome |
| 보존 | 운영 필요에 따라 짧을 수 있음 | 정책·규제에 따라 별도 정의 |
| 접근 | 개발·운영자 | 제한된 감사·보안 역할 |
| 변경 | 운영 편의를 위해 Rotation | 무단 변경·삭제 방지 필요 |

Trace도 Audit Log를 대신하지 않습니다.

Sampling된 Trace가 누락될 수 있고, Trace Retention이 감사 요구보다 짧을 수 있기 때문입니다.

대신 `traceId`를 Audit Event에 넣어 상세 진단으로 연결합니다.

## 18. 감사 이벤트는 “누가·어디서·무엇을·왜·어떻게 됐는가”를 담는다

OWASP Logging Cheat Sheet는 Application Log가 사건의 `when`, `where`, `who`, `what`을 기록해야 한다고 설명합니다.

NIST SP 800-53의 AU-3도 사건 유형, 시각, 위치, Source, Outcome과 관련 Subject·Object의 식별을 감사 Record의 핵심으로 제시합니다.

AI Agent 실행에는 다음 필드를 추가합니다.

```json
{
  "eventId": "audit_event_fixture_001",
  "eventType": "AI_TOOL_AUTHORIZATION_DECIDED",
  "occurredAt": "2026-07-29T12:00:00Z",
  "recordedAt": "2026-07-29T12:00:00.120Z",
  "tenantId": "tenant_fixture_001",
  "subject": {
    "type": "USER",
    "id": "user_fixture_001"
  },
  "actor": {
    "type": "AI_AGENT",
    "id": "agent_runtime_fixture_001"
  },
  "clientId": "client_fixture_001",
  "action": {
    "tool": "meeting.transfer",
    "operation": "TRANSFER"
  },
  "resource": {
    "type": "MEETING",
    "id": "meeting_fixture_001",
    "version": 17
  },
  "decision": {
    "id": "decision_fixture_001",
    "allowed": false,
    "policyVersion": "agent_authz_2026_07_29_v3",
    "reasonCodes": [
      "TARGET_TENANT_MISMATCH"
    ]
  },
  "correlation": {
    "requestId": "request_fixture_001",
    "workflowId": "workflow_fixture_001",
    "toolCallId": "tool_call_fixture_001",
    "traceId": "trace_fixture_001"
  }
}
```

이벤트 본문에는 원본 Prompt, Access Token과 전체 회의 내용을 넣지 않습니다.

## 19. 정책 결정과 실제 실행을 다른 이벤트로 남긴다

허용 결정이 내려졌다고 실제 실행이 성공한 것은 아닙니다.

```text
Authorization Decision = ALLOW
Tool Execution = FAILED
Side Effect = 없음
```

반대의 이상 상태도 탐지해야 합니다.

```text
Authorization Decision = DENY
Tool Execution = SUCCEEDED
```

권장 Event Chain은 다음과 같습니다.

```text
AI_RUN_STARTED
  → TOOL_PROPOSED
  → AUTHORIZATION_DECIDED
  → APPROVAL_REQUESTED
  → APPROVAL_GRANTED
  → TOOL_EXECUTION_STARTED
  → TOOL_EXECUTION_COMPLETED
  → SIDE_EFFECT_CONFIRMED
```

모든 Tool이 승인 이벤트를 필요로 하지는 않습니다.

하지만 정책 결정과 실행 결과는 분리해 기록합니다.

## 20. 실행 감사 이벤트에는 결과 상태와 Side Effect를 구분한다

Tool Adapter의 HTTP `200`만으로 업무 변경을 확정할 수 없습니다.

```json
{
  "eventId": "audit_event_fixture_002",
  "eventType": "AI_TOOL_EXECUTION_COMPLETED",
  "occurredAt": "2026-07-29T12:00:02Z",
  "tenantId": "tenant_fixture_001",
  "subjectId": "user_fixture_001",
  "actorId": "agent_runtime_fixture_001",
  "tool": "task.create",
  "resource": {
    "type": "MEETING",
    "id": "meeting_fixture_001"
  },
  "execution": {
    "operationId": "operation_fixture_001",
    "status": "SUCCEEDED",
    "sideEffect": "TASK_CREATED",
    "affectedObject": {
      "type": "TASK",
      "id": "task_fixture_001",
      "version": 1
    }
  },
  "authorizationDecisionId": "decision_fixture_004",
  "approvalId": null,
  "traceId": "trace_fixture_001"
}
```

비동기 Tool이면 접수와 최종 Side Effect를 다른 이벤트로 남깁니다.

```text
TOOL_REQUEST_ACCEPTED
  → OPERATION_SUCCEEDED
  → SIDE_EFFECT_CONFIRMED
```

## 21. 전체 Tool 인자 대신 Canonical Digest를 기록한다

감사를 위해 Tool 인자를 모두 저장하면 개인정보와 Credential이 감사 저장소로 확산될 수 있습니다.

대신 필요한 공개 가능한 요약 필드와 Canonical Request Digest (정규 요청 요약값)를 저장합니다.

```javascript
function auditProjection(toolInput) {
  return {
    meetingId: toolInput.meetingId,
    targetGroupId: toolInput.targetGroupId,
    requestedAction: "TRANSFER"
  };
}
```

```text
requestDigest =
  SHA-256(
    canonicalJson(
      tool,
      tenantId,
      resourceId,
      resourceVersion,
      allowedBusinessArguments
    )
  )
```

Digest는 원문을 복구하는 암호화가 아닙니다.

입력 후보가 제한적이면 Hash를 추측할 수 있으므로 민감한 값의 비밀성을 보장하는 수단으로 사용해서는 안 됩니다.

## 22. 허용뿐 아니라 거부와 실패를 기록한다

보안 사고의 초기 신호는 성공보다 거부 이벤트에 나타날 수 있습니다.

권장 감사 대상은 다음과 같습니다.

- 인증 성공·실패
- Tenant Context 불일치
- Tool Scope 부족
- 객체 권한 거부
- 승인 요청·승인·거부·만료
- Domain Precondition 실패
- Tool 실행 시작·성공·실패
- 비동기 재시도·취소
- 외부 전송과 대량 조회
- 정책·역할·Group Membership 변경
- Audit Pipeline 실패

다만 모든 내부 Debug Event를 감사 저장소에 넣으면 중요한 사건이 묻힙니다.

위험도와 조사 목적에 맞는 Event Vocabulary (이벤트 어휘)를 정의합니다.

## 23. Decision ID로 정책 판단을 재구성한다

OPA Decision Logs는 Policy Query의 Input, Result, Bundle Metadata와 `decision_id`를 기록해 감사와 Offline Debugging에 사용할 수 있도록 합니다.

AI Agent 권한 결정에도 고유 Decision ID를 사용합니다.

```text
decisionId
  → 정책 Version
  → 입력 속성 Snapshot 또는 안전한 Projection
  → 결과
  → Reason Codes
  → Obligations
```

나중에 정책이 바뀌더라도 당시 어떤 Version이 어떤 입력으로 결정했는지 확인할 수 있어야 합니다.

```json
{
  "decisionId": "decision_fixture_004",
  "policy": {
    "bundleRevision": "authz_bundle_fixture_031",
    "entrypoint": "agent/authz/decision"
  },
  "inputDigest": "sha256:fixture_input_digest",
  "result": {
    "allowed": true,
    "approvalRequired": false
  }
}
```

## 24. 감사 로그의 민감정보를 별도 정책으로 Masking한다

OPA 문서는 Decision Log의 Input과 Result에 사용자명, Password 같은 민감정보가 포함될 수 있으므로 업로드 전에 Mask 또는 제거하는 정책을 제공합니다.

감사 Event에도 Field별 처리 정책을 적용합니다.

| 데이터 | 기본 처리 |
|---|---|
| Access Token·API Key·Cookie | 기록 금지 |
| Password·인증 Code | 기록 금지 |
| Prompt·녹취록·문서 원문 | 기본 기록 금지 |
| 사용자 ID | 업무상 필요 시 불투명 ID |
| 이메일·전화번호 | Mask 또는 별도 보호 저장소 |
| 객체 ID | 감사 조사에 필요한 범위에서 기록 |
| Tool 입력 | 안전한 Projection과 Digest |
| 오류 | Stack·내부 경로 제거 후 분류 Code |

OpenTelemetry Baggage (수하물)는 Downstream으로 전파되므로 민감한 사용자 정보와 Token을 넣지 않습니다.

`tenantId`, `workflowId`도 외부 Provider 호출까지 자동 전파하지 않고 신뢰 경계별 Allowlist를 적용합니다.

## 25. 감사 로그 자체를 보호한다

감사 저장소를 일반 Application 관리자 누구나 수정할 수 있다면 증거 가치가 약해집니다.

NIST SP 800-53의 AU-9는 Audit Information과 Logging Tool을 무단 접근, 수정과 삭제로부터 보호하고 이상 접근을 탐지하도록 요구합니다.

실무 통제는 다음과 같습니다.

- Application 계정은 Append 또는 제한된 전송만 가능
- 감사 조회 역할과 운영 역할 분리
- 삭제·Retention 변경은 별도 승인
- 전송 구간 암호화
- 저장 시 암호화와 Key 접근 통제
- Event Sequence·Batch Hash·서명 등 무결성 검증
- 중앙 시간 동기화와 UTC Timestamp
- 저장 실패·지연·누락 Alert
- Backup과 복구 시험

특정 규제에서 요구하지 않는 한 모든 로그를 영구 보존하지 않습니다.

보존 기간은 업무 목적, 법적 근거, 개인정보 위험과 저장 비용을 함께 평가해 정합니다.

## 26. 감사 Pipeline 실패 시 행동을 위험 등급별로 정한다

감사 저장소가 잠시 응답하지 않을 때 모든 업무를 중단하면 가용성이 낮아집니다.

반대로 위험 작업을 기록 없이 계속 실행하면 책임 추적이 사라집니다.

| 작업 | 감사 실패 시 기본 정책 예시 |
|---|---|
| 공개 정보 조회 | Buffer 후 실행 가능 |
| 내부 문서 조회 | 제한된 Local Queue에 보존 후 실행 |
| 업무 생성·변경 | Durable Audit Event 저장 후 실행 |
| 외부 전송·권한 변경 | 감사 증거 저장 실패 시 실행 차단 |
| 영구 삭제 | 감사·승인 증거 없으면 실행 차단 |

정책은 조직의 위험 수용 기준에 따라 달라집니다.

핵심은 Fail-open (장애 시 허용) 또는 Fail-closed (장애 시 차단)를 우연히 결정하지 않고 작업 등급별로 명시하는 것입니다.

## 27. Tenant별 감사 조회 권한도 분리한다

감사 로그에는 누가 어떤 회의와 문서를 조회했는지가 들어 있어 그 자체가 민감정보입니다.

```text
Tenant Admin
  자신의 Tenant 이벤트만 조회

Security Auditor
  승인된 범위의 다중 Tenant 사건 조사

Application Operator
  본문 없이 기술 상태와 Correlation ID 조회
```

검색 Query에도 Tenant 조건을 강제합니다.

```sql
SELECT event_id, event_type, occurred_at, outcome
FROM audit_event
WHERE tenant_id = :authorized_tenant_id
  AND occurred_at >= :from_time
  AND occurred_at < :to_time
ORDER BY occurred_at;
```

감사 관리자 역할이 모든 고객 데이터 원문을 볼 수 있게 설계하지 않습니다.

## 28. 탐지 규칙은 권한 결정과 실행 이벤트를 함께 본다

구조화된 Event가 있으면 다음 패턴을 탐지할 수 있습니다.

```text
같은 Subject의 반복 Tenant 불일치
같은 Agent의 짧은 시간 내 대량 객체 조회
평소 사용하지 않던 Tool의 실행 증가
DENY 뒤 인자를 바꾼 반복 호출
승인되지 않은 외부 전송
ALLOW Decision 없이 발생한 Side Effect
낮은 위험 Tool에서 갑작스러운 대량 결과
정책 Version 변경 직후 거부율 급증
```

예시 Query는 다음과 같습니다.

```sql
SELECT actor_id, tool_name, COUNT(*) AS denied_count
FROM audit_event
WHERE event_type = 'AI_TOOL_AUTHORIZATION_DECIDED'
  AND decision_allowed = FALSE
  AND occurred_at >= :window_start
GROUP BY actor_id, tool_name
HAVING COUNT(*) >= :threshold;
```

임계값은 설명용 Parameter이며 실제 Traffic과 오탐 기준으로 조정합니다.

## 29. 권한 정책 변경도 감사 대상이다

누가 Tool 권한을 실행했는지만 기록하고 누가 정책을 바꿨는지 남기지 않으면 원인을 찾을 수 없습니다.

다음 변경을 감사합니다.

- Role과 Permission 변경
- Tenant Membership 변경
- Tool Scope Mapping 변경
- Policy Bundle 배포·Rollback
- Approval Rule 변경
- Audit Masking·Retention 변경
- Break-glass (긴급 권한) 발급·사용·회수

```json
{
  "eventType": "AUTHORIZATION_POLICY_DEPLOYED",
  "occurredAt": "2026-07-29T13:00:00Z",
  "actor": {
    "type": "ADMIN_USER",
    "id": "admin_fixture_001"
  },
  "change": {
    "fromVersion": "authz_bundle_fixture_030",
    "toVersion": "authz_bundle_fixture_031",
    "changeRequestId": "change_fixture_001"
  },
  "outcome": "SUCCEEDED"
}
```

Policy 변경 전후의 Test 결과와 승인 기록도 연결합니다.

## 30. 권한 테스트는 역할보다 전체 Context 조합을 검증한다

`MANAGER는 허용`, `VIEWER는 거부` 두 가지로는 부족합니다.

| Subject | Tenant | 객체 관계 | Tool | 상태 | 기대 결과 |
|---|---|---|---|---|---|
| Viewer | 동일 | Group 구성원 | 조회 | Complete | 허용 |
| Viewer | 동일 | 비구성원 | 조회 | Complete | 거부 |
| Editor | 동일 | Group 구성원 | 요약 재생성 | Complete | 허용 |
| Editor | 다른 Tenant | 구성원 아님 | 조회 | Complete | 거부 |
| Manager | 동일 | 비구성원 | 이동 | Complete | 정책에 따라 거부 |
| Manager | 동일 | 구성원 | 삭제 | Legal Hold | 업무 조건 거부 |
| Service Actor | 동일 | 사용자 위임 없음 | 변경 | Complete | 거부 |
| Agent Actor | 동일 | 유효한 위임 | 변경 | Complete | 승인 정책 적용 |

각 Case에서 다음을 함께 확인합니다.

- 실제 API 결과
- Policy Decision과 Reason Code
- Audit Event 생성
- 민감정보 Masking
- Side Effect 존재 여부
- Trace·Decision·Tool Call ID 연결

## 31. 공격·오류 시나리오로 검증한다

1. Tool 인자의 Tenant ID를 다른 조직으로 변경
2. 다른 Tenant에서 얻은 객체 ID를 상세 Tool에 직접 입력
3. 읽기 Scope Token으로 쓰기 Tool 호출
4. Tool 목록에 없던 Tool을 `tools/call`로 직접 호출
5. 만료된 위임 Token으로 비동기 Workflow 재개
6. Group 탈퇴 후 이전 Allow Decision 재사용
7. 승인 후 대상 객체 Version 변경
8. Audit Pipeline 중단 중 위험 작업 실행 시도
9. Audit Event에 Access Token이 포함되는지 검사
10. ALLOW Decision Event 없이 Side Effect 생성
11. 오래된 Policy Bundle을 사용하는 Worker 실행
12. 감사 조회 API에서 Tenant Filter 제거 시도

정상적으로 거부되는지만 보지 않고 거부 Event와 실제 Side Effect 부재를 함께 검증합니다.

## 32. 운영 체크리스트

- [ ] Subject, Actor, Client, Executor와 Approver를 구분한다.
- [ ] Tenant Context를 검증된 인증·Membership에서 결정한다.
- [ ] 외부 Tenant Header와 Tool 인자를 그대로 신뢰하지 않는다.
- [ ] Cache, Queue, Search, Storage와 Audit에 Tenant 경계를 포함한다.
- [ ] RBAC에 객체·환경 속성 기반 ABAC를 결합한다.
- [ ] Tool 권한과 객체 권한을 분리해 검사한다.
- [ ] Tool 목록 필터링과 실제 실행 인가를 구분한다.
- [ ] Gateway 이후 MCP Server와 업무 Service가 다시 인가한다.
- [ ] PDP와 PEP를 분리하고 Obligation 집행 실패 시 실행하지 않는다.
- [ ] 정책 결과에 Decision ID, Version, Reason과 Obligation을 포함한다.
- [ ] 장시간 Workflow의 Side Effect 직전에 다시 인가한다.
- [ ] 정책 결정과 실제 Tool 실행 결과를 별도 감사 이벤트로 남긴다.
- [ ] 비동기 접수와 최종 Side Effect를 분리해 기록한다.
- [ ] Tool 입력 원문 대신 안전한 Projection과 Digest를 사용한다.
- [ ] 허용뿐 아니라 거부·실패·정책 변경을 기록한다.
- [ ] Access Token, Prompt 원문과 민감정보를 감사 로그에서 제거한다.
- [ ] 감사 저장소의 수정·삭제·조회 권한을 분리한다.
- [ ] 감사 Pipeline 장애 시 위험 등급별 Fail-open·Fail-closed 정책을 정한다.
- [ ] Tenant별 감사 조회 범위를 강제한다.
- [ ] Decision ID, Tool Call ID, Workflow ID와 Trace ID를 연결한다.
- [ ] 권한 Test Matrix와 공격 시나리오를 CI에서 실행한다.

## 마무리

엔터프라이즈 AI Agent의 권한은 “로그인한 사용자의 Token을 Tool에 전달하는 것”으로 완성되지 않습니다.

다음 경계를 차례로 통과해야 합니다.

```text
인증된 Subject
  → 검증된 Tenant Context
    → 허용된 Agent·Client
      → 허용된 Tool Action
        → 허용된 Resource
          → 허용된 업무 상태
            → 필요한 승인
              → 실행 시점 재인가
                → Side Effect
```

감사 로그는 같은 흐름을 반대 방향으로 재구성할 수 있어야 합니다.

```text
누가 요청했는가?
누가 대신 실행했는가?
어떤 정책이 허용했는가?
어떤 대상이 변경됐는가?
실제 결과는 무엇이었는가?
```

핵심 원칙은 다음과 같습니다.

1. Subject와 Actor를 분리합니다.
2. Tenant를 Client 입력이 아닌 신뢰할 수 있는 Context로 확정합니다.
3. Tool, 객체와 업무 상태를 각각 인가합니다.
4. 장시간 Workflow는 실행 직전에 다시 인가합니다.
5. Decision ID와 Policy Version으로 판단 근거를 남깁니다.
6. 정책 결정, 승인과 실제 Side Effect를 별도 감사 이벤트로 연결합니다.
7. 감사 로그의 민감정보와 무결성도 별도 보안 정책으로 보호합니다.

안전한 Agent는 권한을 많이 가진 Agent가 아닙니다.

**현재 사용자의 제한된 권한을 정확한 Tenant·Tool·객체에만 적용하고, 그 판단과 결과를 나중에 증명할 수 있는 Agent**입니다.

다음 글에서는 AI 프로젝트를 시작할 때 모델 정확도만 정하지 않고 업무 가치, 품질, 지연, 안전, 운영과 비용을 포함한 성공 기준을 어떻게 정의하는지 살펴보겠습니다.

## 참고 자료

- [NIST SP 800-162: Guide to Attribute Based Access Control](https://csrc.nist.gov/pubs/sp/800/162/upd2/final)
- [NIST SP 800-53 Rev. 5: Security and Privacy Controls](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)
- [NIST SP 800-92: Guide to Computer Security Log Management](https://csrc.nist.gov/pubs/sp/800/92/final)
- [OWASP API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [Open Policy Agent: Decision Logs](https://www.openpolicyagent.org/docs/management-decision-logs)
- [RFC 8693: OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693.html)
- [MCP: Understanding Authorization](https://modelcontextprotocol.io/docs/tutorials/security/authorization)
- [MCP: Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [MCP Draft: Tools](https://modelcontextprotocol.io/specification/draft/server/tools)
- [OpenTelemetry: Baggage](https://opentelemetry.io/docs/concepts/signals/baggage/)
- [OpenTelemetry: Trace Context in non-OTLP Log Formats](https://opentelemetry.io/docs/specs/otel/compatibility/logging_trace_context/)

---

> 이 글은 2026년 7월 29일 기준 NIST, OWASP, IETF, MCP, Open Policy Agent와 OpenTelemetry의 공식 공개 문서 및 공개 가능한 엔터프라이즈 AI·MCP 설계 경험을 바탕으로 작성했습니다. 예시 Policy, Scope, Role, Tenant 격리 방식, 감사 Event와 보존 정책은 설명용이며 실제 적용 시 조직의 Identity Provider, 데이터 분류, 위임 모델, 관련 법규, 감사 목적과 위험 수용 기준에 맞게 검토해야 합니다.
