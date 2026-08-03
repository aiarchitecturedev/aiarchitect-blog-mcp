# AI Agent 승인 정책 설계: 읽기·쓰기·중요·파괴 작업을 구분하는 방법

AI Agent에게 “지난 회의를 찾아 요약해 줘”라고 요청했습니다.

Agent는 회의 목록을 조회하고, 대상 회의를 찾은 뒤 요약 작업을 요청할 수 있습니다. 여기까지는 비교적 자연스럽습니다.

그런데 요청이 “다른 조직으로 옮겨 줘”, “외부 담당자에게 전송해 줘”, “이 회의를 영구 삭제해 줘”라면 이야기가 달라집니다.

모두 같은 Tool Call이지만 결과의 영향은 같지 않습니다.

```text
조회 실패
  → 다시 확인할 수 있음

생성 중복
  → 데이터 정리와 비용 발생

잘못된 전송
  → 외부 노출과 업무 사고

영구 삭제
  → 복구 불가능할 수 있음
```

모델이 사용자의 의도를 잘 이해했다는 사실은 실행 권한을 얻었다는 뜻이 아닙니다.

운영 가능한 AI Agent에는 다음 네 질문에 각각 답하는 통제가 필요합니다.

```text
인증 (Authentication)
  누가 요청했는가?

인가 (Authorization)
  이 사용자가 이 대상에 이 작업을 할 수 있는가?

승인 (Approval)
  지금 이 구체적인 실행을 사용자가 허용했는가?

실행 안전성 (Execution Safety)
  중복·변경·실패가 발생해도 안전하게 처리할 수 있는가?
```

이 글에서는 Tool을 읽기·쓰기·중요·파괴 작업으로 분류하고, 사용자 승인 (Human-in-the-loop Approval)을 권한·미리보기·만료·재시도·감사와 연결하는 방법을 정리합니다.

## 1. 승인 화면 하나로는 실행을 안전하게 만들 수 없다

다음과 같은 구현은 얼핏 안전해 보입니다.

```json
{
  "tool": "meeting.delete",
  "arguments": {
    "meetingId": "meeting_fixture_001"
  },
  "confirm": true
}
```

하지만 `confirm: true`만으로는 중요한 질문에 답할 수 없습니다.

- 누가 승인했는가?
- 어떤 Tenant에서 승인했는가?
- 어느 회의를 삭제하도록 승인했는가?
- 승인 후 입력이 바뀌지 않았는가?
- 얼마나 오래 유효한 승인인가?
- 한 번만 사용할 수 있는가?
- 승인 당시와 실행 당시의 권한이 같은가?
- Timeout 후 같은 승인을 다시 사용해도 되는가?

더 큰 문제는 이 값을 Agent가 스스로 생성할 수 있다는 점입니다. 모델이 Tool 인자에 `confirm: true`를 넣는 것과 사용자가 실제 승인한 것은 전혀 다른 사건입니다.

```text
모델이 생성한 Boolean
≠ 인증된 사용자의 승인 Event
```

승인은 대화 문구가 아니라 신뢰할 수 있는 실행 계층이 발급하고 검증하는 제한된 권한이어야 합니다.

## 2. 인증·인가·승인을 분리해야 하는 이유

세 통제는 서로를 대체하지 않습니다.

| 통제 | 핵심 질문 | 대표 근거 |
|---|---|---|
| 인증 (Authentication) | 요청자가 누구인가? | Session, Access Token |
| 인가 (Authorization) | 이 작업이 허용되는가? | Role, Scope, 객체 권한 |
| 승인 (Approval) | 이 구체적 실행에 동의했는가? | 사용자 승인 Event |

예를 들어 사용자가 회의 삭제 권한을 보유하더라도 모든 삭제 요청을 자동 실행할 이유는 없습니다. 반대로 사용자가 확인 버튼을 눌렀더라도 그 회의에 대한 삭제 권한이 없다면 실행해서는 안 됩니다.

```text
실행 허용
  = 유효한 인증
  ∩ 현재 시점의 인가
  ∩ 필요한 경우 유효한 승인
  ∩ 실행 안전 조건
```

OAuth 동의 (OAuth Consent)도 업무 작업 승인과 구분해야 합니다.

OAuth 동의는 Client가 어떤 Scope로 접근할 수 있는지를 정합니다. “이 Client가 회의 관리 Scope를 요청한다”는 동의가 “지금 이 회의 한 건을 영구 삭제한다”는 승인까지 의미하지는 않습니다.

```text
OAuth Consent
  → Client 접근 범위

Action Approval
  → 특정 사용자·작업·대상·입력의 실행 허용
```

## 3. 먼저 위협 모델을 정의한다

승인 정책은 모델의 실수만 막는 기능이 아닙니다.

운영 환경에서는 다음 원인이 같은 위험 작업을 만들 수 있습니다.

- 모델의 환각 (Hallucination)과 대상 선택 오류
- 사용자 요청의 모호성
- 문서·웹페이지·Tool 결과에 포함된 Prompt Injection
- 악의적인 MCP Server 또는 잘못된 Tool 설명
- 권한 변경 후 남아 있는 오래된 Session
- 승인 이후 대상이나 입력이 바뀌는 경쟁 상태
- Timeout 후 자동 재시도로 발생하는 중복 실행
- Sub-agent나 생성 코드가 승인 범위를 확장하는 문제
- 대량 작업이 한 번의 작은 요청처럼 보이는 문제

따라서 승인 정책은 “모델을 신뢰할 것인가?”보다 다음 질문에서 시작해야 합니다.

```text
이 작업이 잘못 실행됐을 때
누구에게, 어떤 범위로, 얼마나 오래 영향을 주며,
되돌릴 수 있는가?
```

## 4. Tool을 네 가지 기본 등급으로 분류한다

가장 단순하고 실용적인 출발점은 부작용 (Side Effect)과 업무 영향을 기준으로 네 등급을 정의하는 것입니다.

| 등급 | 의미 | 예시 | 기본 정책 |
|---|---|---|---|
| 읽기 (Read) | 상태를 변경하지 않음 | 목록·상세·검색 | 권한 확인 후 제한적 자동 실행 |
| 쓰기 (Write) | 내부 상태를 생성·변경 | 생성·수정·재처리 | 범위가 작으면 조건부 자동 또는 묶음 승인 |
| 중요 작업 (Important Action) | 외부·조직·비용에 큰 영향 | 전송·공유·이관·승인 | 실행 전 명시적 확인 |
| 파괴 작업 (Destructive Action) | 삭제·취소처럼 복구가 어렵거나 불가 | 영구 삭제·키 폐기 | 대상별 최종 승인 |

가상의 회의 업무 Tool을 분류하면 다음과 같습니다.

```json
{
  "toolRiskCatalog": [
    {
      "tool": "identity.get",
      "riskClass": "READ"
    },
    {
      "tool": "meeting.list",
      "riskClass": "READ"
    },
    {
      "tool": "meeting.create",
      "riskClass": "WRITE"
    },
    {
      "tool": "meeting.summary.request",
      "riskClass": "WRITE"
    },
    {
      "tool": "meeting.transfer",
      "riskClass": "IMPORTANT"
    },
    {
      "tool": "meeting.delete",
      "riskClass": "DESTRUCTIVE"
    }
  ]
}
```

분류는 Tool 이름만 보고 결정하지 않습니다. `get_report`라는 이름의 Tool이 보고서를 생성하면서 외부로 전송할 수도 있고, `sync`가 수천 건을 덮어쓸 수도 있습니다.

## 5. 같은 읽기 작업도 민감도에 따라 달라진다

읽기는 상태를 바꾸지 않지만 항상 저위험인 것은 아닙니다.

개인정보, 인사 평가, 의료 정보와 Secret을 조회하는 작업은 데이터 유출 위험이 큽니다. 수만 건을 내보내는 Export도 단일 상세 조회와 같게 취급할 수 없습니다.

작업 등급에 다음 위험 속성을 함께 평가해야 합니다.

| 속성 | 확인할 질문 |
|---|---|
| 데이터 민감도 (Data Sensitivity) | 개인정보·기밀·Secret이 포함되는가? |
| 영향 범위 (Blast Radius) | 한 건인가, 조직 전체인가? |
| 가역성 (Reversibility) | 자동 또는 수동으로 되돌릴 수 있는가? |
| 외부 영향 (External Effect) | 외부 전송·게시·결제가 발생하는가? |
| 비용 (Cost) | Model·GPU·결제 비용이 큰가? |
| 빈도 (Frequency) | 반복 실행 시 위험이 누적되는가? |

```json
{
  "tool": "meeting.export",
  "baseRiskClass": "READ",
  "riskAttributes": {
    "dataSensitivity": "CONFIDENTIAL",
    "maxRecords": 5000,
    "externalEffect": true,
    "reversibility": "NOT_APPLICABLE"
  },
  "effectiveRiskClass": "IMPORTANT"
}
```

기본 등급은 출발점이고, 실제 요청의 대상·건수·민감도에 따라 유효 위험 등급 (Effective Risk Class)을 높일 수 있어야 합니다.

## 6. 위험 등급은 신뢰된 Registry에서 관리한다

MCP Tool은 이름, 설명, 입력 Schema와 Annotation을 제공할 수 있습니다. 이 정보는 Agent와 UI가 Tool을 이해하는 데 유용합니다.

그러나 외부 Server가 자신을 `readOnly`라고 표시했다는 이유만으로 자동 실행을 허용해서는 안 됩니다.

MCP 공식 사양도 신뢰되지 않은 Server의 Tool Annotation을 신뢰하면 안 된다고 설명합니다.

```text
MCP Tool Metadata
  → 발견과 사용자 설명을 위한 Hint

Trusted Tool Registry
  → 조직이 검토한 실제 정책 근거
```

운영 환경에서는 Tool Registry에 다음 정보를 별도로 관리합니다.

```json
{
  "tool": "meeting.delete",
  "provider": "approved_meeting_service",
  "riskClass": "DESTRUCTIVE",
  "requiredScopes": [
    "meeting.delete"
  ],
  "approvalMode": "PER_ACTION",
  "maxBatchSize": 1,
  "retryMode": "VERIFY_BEFORE_RETRY",
  "auditLevel": "FULL",
  "policyVersion": "tool-policy-2026-07"
}
```

Server가 보낸 Metadata와 Registry가 충돌하면 더 보수적인 정책을 적용하거나 Tool을 격리해야 합니다.

## 7. 정책 입력은 주체·객체·작업·환경을 포함한다

속성 기반 접근 제어 (Attribute-Based Access Control, ABAC)는 주체, 객체, 작업과 환경 속성을 정책에 대입해 결정을 내립니다.

AI Agent 승인 정책에도 같은 구조를 사용할 수 있습니다.

```json
{
  "subject": {
    "principalId": "user_fixture_alpha",
    "tenantId": "tenant_fixture_alpha",
    "roles": [
      "meeting_manager"
    ],
    "authenticationLevel": "MFA"
  },
  "action": {
    "tool": "meeting.transfer",
    "operation": "TRANSFER",
    "riskClass": "IMPORTANT"
  },
  "object": {
    "resourceType": "meeting",
    "resourceId": "meeting_fixture_001",
    "ownerTenantId": "tenant_fixture_alpha",
    "revision": "rev_fixture_007",
    "sensitivity": "INTERNAL"
  },
  "environment": {
    "channel": "WEB",
    "sessionId": "session_fixture_001",
    "requestedAt": "2026-07-29T09:00:00Z"
  }
}
```

NIST SP 800-162의 ABAC 정의처럼 정책 결정은 단순한 Role 하나가 아니라 실행 맥락의 속성을 함께 평가할 수 있습니다.

## 8. 정책 결과는 허용과 거부 두 개보다 풍부해야 한다

실제 승인 흐름에서 `ALLOW`와 `DENY`만으로는 부족합니다.

다음과 같은 정책 결정 (Policy Decision)이 유용합니다.

| 결정 | 의미 |
|---|---|
| `ALLOW` | 추가 승인 없이 실행 가능 |
| `DENY` | 실행 금지 |
| `REQUIRE_PREVIEW` | 실행 결과 미리보기 필요 |
| `REQUIRE_CONFIRMATION` | 특정 작업에 사용자 승인 필요 |
| `REQUIRE_STEP_UP` | MFA 등 강화 인증 필요 |
| `ALLOW_WITH_LIMITS` | 건수·비용·대상 제한 안에서 허용 |

```json
{
  "decision": "REQUIRE_CONFIRMATION",
  "decisionId": "decision_fixture_001",
  "reasonCode": "EXTERNAL_TENANT_TRANSFER",
  "obligations": {
    "showPreview": true,
    "requireResourceRevision": true,
    "approvalTtlSeconds": 300,
    "maxUses": 1,
    "maxBatchSize": 1
  },
  "policyVersion": "agent-approval-2026-07"
}
```

정책 엔진은 결정을 내리고, 실행 계층은 `obligations`를 반드시 이행해야 합니다. 화면에서 경고만 보여 주고 Backend가 제약을 검사하지 않는다면 통제가 아닙니다.

## 9. 등급별 기본 승인 정책을 정한다

서비스마다 차이는 있지만 다음 표를 기본값으로 사용할 수 있습니다.

| 작업 | 기본 승인 | 추가 통제 |
|---|---|---|
| 일반 읽기 | 자동 실행 가능 | 객체 권한·결과 Masking |
| 민감 읽기 | 미리보기 또는 강화 인증 | 목적·건수·다운로드 제한 |
| 소규모 내부 쓰기 | 제한된 Session 승인 가능 | 멱등성·변경 Diff |
| 대량 쓰기 | 작업별 승인 | 건수·비용·대상 표시 |
| 외부 전송·공유 | 작업별 승인 | 수신자·공개 범위 표시 |
| 이관·권한 변경 | 작업별 승인 | 이전·이후 소유권 표시 |
| 영구 삭제 | 대상별 최종 승인 | 자동 재시도 금지·복구 가능성 표시 |

여기서 “자동 실행 가능”은 무조건 실행을 의미하지 않습니다. 권한 검사, 입력 검증, Rate Limit과 감사 기록은 그대로 적용됩니다.

## 10. 승인 전에 실행 미리보기를 만든다

사용자는 Tool 이름보다 결과의 변화를 이해해야 합니다.

나쁜 확인 문구는 다음과 같습니다.

```text
meeting.transfer를 실행할까요?
```

좋은 확인 문구는 대상과 영향을 보여 줍니다.

```text
회의 “분기 계획 검토” 1건을
현재 그룹에서 “외부 협업 그룹”으로 이동합니다.

이동 후 현재 그룹 구성원은 접근할 수 없을 수 있습니다.
되돌리려면 양쪽 그룹의 권한이 다시 필요합니다.

[취소] [이동 승인]
```

실행 미리보기 (Execution Preview)에는 최소한 다음 정보가 필요합니다.

```json
{
  "preview": {
    "actionLabel": "회의 이동",
    "resource": {
      "type": "meeting",
      "displayName": "분기 계획 검토",
      "revision": "rev_fixture_007"
    },
    "changes": {
      "fromGroup": "현재 그룹",
      "toGroup": "외부 협업 그룹"
    },
    "impact": {
      "externalBoundaryCrossing": true,
      "reversible": true,
      "estimatedCost": "NONE"
    },
    "warnings": [
      "기존 구성원의 접근 권한이 변경될 수 있습니다."
    ]
  }
}
```

Secret, Token과 내부 식별자를 그대로 노출하지 말고 사람이 식별할 수 있는 안전한 표시 이름을 사용합니다.

## 11. 승인 바인딩은 정확한 요청에 묶는다

승인 바인딩 (Approval Binding)은 한 번 받은 승인이 다른 요청으로 번지는 것을 막습니다.

승인 Grant에는 다음 요소가 필요합니다.

- 승인 사용자와 Tenant
- Session과 Client
- Tool과 업무 Action
- 대상 Resource와 Version
- 정규화된 입력의 지문
- 정책 Version
- 승인 시각과 만료 시각
- 사용 가능 횟수

```json
{
  "approvalGrant": {
    "grantId": "grant_fixture_001",
    "principalId": "user_fixture_alpha",
    "tenantId": "tenant_fixture_alpha",
    "sessionId": "session_fixture_001",
    "tool": "meeting.transfer",
    "action": "TRANSFER",
    "resourceId": "meeting_fixture_001",
    "resourceRevision": "rev_fixture_007",
    "requestFingerprint": "sha256:fixture_request_hash",
    "policyVersion": "agent-approval-2026-07",
    "approvedAt": "2026-07-29T09:00:00Z",
    "expiresAt": "2026-07-29T09:05:00Z",
    "maxUses": 1
  }
}
```

Grant는 Model이 수정할 수 없는 불투명 Handle 또는 서명된 구조로 전달합니다. 실행 Service는 신뢰할 수 있는 저장소나 서명을 통해 진위를 검증해야 합니다.

## 12. 입력 지문은 정규화 후 계산한다

같은 의미의 JSON은 Key 순서나 공백이 다를 수 있습니다. 원문 문자열에 단순 Hash를 계산하면 안정적인 비교가 어렵습니다.

요청 지문 (Request Fingerprint)은 다음 흐름으로 생성합니다.

```text
Tool Name
  + 정책에 포함할 인자 선택
  + JSON 정규화 (Canonicalization)
  + 사용자·Tenant·대상 Version
  + 정책 Version
  → SHA-256
```

예를 들어 다음 두 입력은 같은 의미로 정규화돼야 합니다.

```json
{
  "meetingId": "meeting_fixture_001",
  "targetGroupId": "group_fixture_beta"
}
```

```json
{
  "targetGroupId": "group_fixture_beta",
  "meetingId": "meeting_fixture_001"
}
```

반면 대상 그룹, 공유 범위, 삭제 방식과 수신자가 바뀌면 새로운 승인을 받아야 합니다.

## 13. 승인 후 대상이 바뀌는 문제를 막는다

확인 시점 검사와 실행 시점 사용 사이의 변경 (Time-of-check to Time-of-use, TOCTOU)은 승인 설계의 핵심 위험입니다.

```text
09:00 승인 화면
  회의 Revision = 7
  대상 그룹 = A

09:01 다른 사용자가 회의를 변경
  회의 Revision = 8

09:02 Agent 실행
  오래된 승인으로 변경 시도
```

실행 직전에 다음을 다시 확인합니다.

1. 사용자 Session과 인증 상태
2. 현재 객체 권한
3. Resource Revision 또는 ETag
4. 정규화된 입력 지문
5. 승인 만료와 사용 횟수
6. 현재 정책 Version과 긴급 차단 규칙

```json
{
  "executionPreconditions": {
    "expectedResourceRevision": "rev_fixture_007",
    "expectedRequestFingerprint": "sha256:fixture_request_hash",
    "approvalGrantState": "UNUSED",
    "authorizationRecheck": true
  }
}
```

Revision이 달라지면 자동으로 최신 상태에 적용하지 말고 새 미리보기와 승인을 요청합니다.

## 14. 자연어 확인은 인증된 승인 Event로 변환한다

사용자는 “응”, “진행해”, “그거 삭제해”처럼 짧게 답할 수 있습니다.

대화형 Agent는 이 응답을 승인 후보로 해석할 수 있지만, 어떤 실행을 가리키는지 Backend가 확인해야 합니다.

```text
Agent가 마지막으로 제시한 승인 요청
  + 현재 대화 Session
  + 인증된 사용자 Event
  + 만료되지 않은 Preview
  + 변경되지 않은 요청 지문
  → Approval Grant 발급
```

다음 경우에는 다시 물어야 합니다.

- 동시에 여러 승인 요청이 열려 있음
- 사용자가 대상을 바꿔 말함
- 승인 요청이 만료됨
- 다른 Device나 Session에서 응답함
- Tool 인자가 Preview 이후 변경됨
- “알아서 해”, “적당히 처리해”처럼 범위가 불명확함

모델 자신의 출력이나 외부 문서의 “승인합니다”라는 문자열을 사용자 승인으로 처리해서는 안 됩니다.

## 15. Session 승인은 좁은 범위에서만 허용한다

반복적인 저위험 쓰기마다 확인을 요구하면 사용자는 내용을 읽지 않고 승인하게 됩니다. 이를 승인 피로 (Approval Fatigue)라고 합니다.

일부 작업은 범주형 승인 (Categorical Approval)으로 묶을 수 있습니다.

```json
{
  "sessionGrant": {
    "principalId": "user_fixture_alpha",
    "sessionId": "session_fixture_001",
    "allowedTools": [
      "meeting.summary.request"
    ],
    "resourceScope": {
      "groupId": "group_fixture_alpha"
    },
    "limits": {
      "maxActions": 10,
      "maxEstimatedCost": 5
    },
    "expiresAt": "2026-07-29T09:30:00Z"
  }
}
```

다음 작업은 Session 승인에서 제외하는 편이 안전합니다.

- 영구 삭제
- 외부 게시·전송
- 권한과 소유권 변경
- 결제·계약·법적 효력이 있는 작업
- Secret 발급·폐기
- 영향 범위를 사전에 계산할 수 없는 대량 변경

MCP Client 보안 지침에서도 Script 실행을 승인했다고 해서 Script가 호출하는 모든 Tool을 무제한 승인한 것으로 보면 안 된다고 설명합니다. 범주형 승인을 사용하더라도 Broker가 각 호출을 Grant 범위와 비교해야 합니다.

## 16. 일괄 작업은 숨은 범위 확장을 막아야 한다

“지난달 회의 정리해 줘”라는 요청이 회의 2건인지 2천 건인지에 따라 위험이 달라집니다.

일괄 승인에는 다음 정보를 포함합니다.

```json
{
  "batchApproval": {
    "action": "ARCHIVE",
    "selectionRule": {
      "groupId": "group_fixture_alpha",
      "createdBefore": "2026-07-01T00:00:00Z"
    },
    "resolvedCount": 42,
    "sampleDisplayNames": [
      "주간 회의 A",
      "주간 회의 B",
      "외 40건"
    ],
    "limits": {
      "maximumCount": 50,
      "allowSelectionExpansion": false
    }
  }
}
```

승인 후 새로 조건에 들어온 객체를 자동 포함하면 안 됩니다. 승인 시점의 대상 목록 Snapshot이나 최대 건수·Selection Version을 바인딩합니다.

일부 항목이 권한 검사를 통과하지 못하면 성공 건수와 거부 건수를 분리해 보여 줍니다. 전체가 성공한 것처럼 요약하면 안 됩니다.

## 17. Sub-agent와 생성 코드에도 같은 정책을 적용한다

하나의 Agent가 다른 Agent를 호출하거나 Sandbox에서 코드를 생성해 실행할 수 있습니다.

이때 상위 Agent의 승인을 하위 실행에 포괄적으로 넘기면 권한이 예상보다 확장됩니다.

```text
User
  → Parent Agent
      → Sub-agent
          → Generated Script
              → Tool Broker
                  → Policy Check
```

Tool Broker는 호출 출처와 관계없이 모든 실제 Tool Call을 검사해야 합니다.

```json
{
  "executionContext": {
    "principalId": "user_fixture_alpha",
    "initiator": "parent_agent",
    "executor": "sandbox_script",
    "delegationDepth": 2,
    "approvalGrantId": "grant_fixture_001"
  }
}
```

하위 실행이 Tool, 대상, 건수 또는 비용 범위를 넓히면 새 승인이 필요합니다. “이 Script 실행 승인”은 “Script가 원하는 모든 외부 작업 승인”이 아닙니다.

## 18. Host 승인과 업무 시스템 권한을 함께 검사한다

승인 Dialog를 보여 주는 MCP Host만 믿어서는 안 됩니다.

다운스트림 업무 시스템도 매 요청에서 권한을 검사해야 합니다. OWASP는 이를 완전한 중재 (Complete Mediation) 원칙으로 설명하며, Model이 권한 검사를 대신하도록 두지 말 것을 권고합니다.

```text
MCP Host
  - 사용자에게 Tool과 영향 표시
  - 승인 Grant 발급
  - 호출 전 정책 검사

MCP Server
  - Token과 Audience 검증
  - Tool 입력 검증
  - Grant와 Context 검증

Business Service
  - 사용자·Tenant·객체 권한 재검사
  - 업무 규칙과 동시성 검사
  - 감사 Event 기록
```

한 계층이 우회되더라도 다른 계층이 위험 실행을 차단할 수 있어야 합니다.

## 19. 승인과 멱등성은 서로 다른 문제를 해결한다

승인은 “실행해도 되는가?”를 결정합니다.

멱등성 (Idempotency)은 “같은 요청이 반복돼도 부작용이 한 번만 발생하는가?”를 다룹니다.

```text
Approval
  → 권한과 사용자 의도

Idempotency
  → 중복 실행 통제
```

RFC 9110은 멱등 메서드를 같은 요청을 여러 번 적용해도 의도한 효과가 한 번 적용한 것과 같은 요청으로 설명합니다. 또한 비멱등 요청은 원 요청이 적용되지 않았다는 사실을 알거나 의미상 멱등하다고 보장할 수 없는 한 자동 재시도하면 안 된다고 설명합니다.

쓰기 작업에는 승인 Grant와 별도로 멱등성 Key를 사용합니다.

```json
{
  "execution": {
    "approvalGrantId": "grant_fixture_001",
    "idempotencyKey": "idem_fixture_001",
    "requestFingerprint": "sha256:fixture_request_hash",
    "retryPolicy": "LOOKUP_BEFORE_RETRY"
  }
}
```

동일한 멱등성 Key에 다른 입력 지문이 들어오면 거부해야 합니다.

## 20. Timeout 뒤에는 승인부터 다시 묻지 않는다

응답을 받지 못했다고 실행이 실패한 것은 아닙니다.

```text
Agent ── 삭제 요청 ──▶ Service
Agent ◀── Timeout ───── Network
              │
              └─ Service에서는 삭제 완료
```

이때 바로 새 승인을 받아 다시 삭제하면 상황이 더 복잡해집니다.

권장 순서는 다음과 같습니다.

```text
1. 멱등성 Key 또는 Operation ID로 결과 조회
2. 실행 완료면 기존 결과 반환
3. 처리 중이면 Polling 또는 Event 대기
4. 실행되지 않았음이 확인되면 승인 유효성 재검사
5. Grant가 만료됐거나 대상이 바뀌었으면 재승인
```

특히 삭제·결제·외부 전송은 “Timeout이므로 재시도”를 기본값으로 두지 않습니다.

## 21. 비동기 작업은 승인과 작업 상태를 분리한다

요약 생성처럼 요청을 접수한 뒤 Queue에서 처리하는 Tool이 있습니다.

승인 Grant가 5분 후 만료되더라도 유효한 승인으로 이미 접수된 작업을 무조건 중단해야 하는 것은 아닙니다. 대신 접수 시점과 실행 상태를 명확하게 구분합니다.

```json
{
  "operation": {
    "operationId": "operation_fixture_001",
    "action": "SUMMARY_GENERATION",
    "acceptedAt": "2026-07-29T09:01:00Z",
    "approvalDecisionId": "decision_fixture_001",
    "state": "QUEUED",
    "cancellable": true
  }
}
```

반대로 Worker가 실제 외부 전송 직전에 최신 수신자 권한을 확인해야 하는 업무라면 실행 시점 재검사가 필요합니다.

정책에는 다음 시점을 구분해 기록합니다.

- 요청 승인 시점
- 업무 접수 시점
- 실제 부작용 발생 시점
- 완료 또는 실패 시점
- 취소 가능 시점

## 22. 정책 결정과 실행을 분리한다

정책 결정 지점 (Policy Decision Point, PDP)과 정책 집행 지점 (Policy Enforcement Point, PEP)을 분리하면 규칙을 일관되게 관리할 수 있습니다.

```text
Agent / MCP Host
       │ Tool Call Intent
       ▼
Policy Enforcement Point
       │ Structured Input
       ▼
Policy Decision Point
       │ Decision + Obligations
       ▼
Preview / Approval / Deny / Execute
       │
       ▼
Business Service
```

Open Policy Agent (OPA)는 정책 결정을 애플리케이션 실행 코드에서 분리하고 구조화된 JSON 입력과 결과로 연동할 수 있는 선택지입니다.

중요한 것은 특정 제품이 아니라 경계입니다.

```text
Model
  → 실행 의도와 인자 제안

Policy Engine
  → 허용·거부·승인 필요 여부 결정

Execution Service
  → 정책 의무사항을 검증하고 실행
```

Model에게 “이 작업이 안전한지 스스로 판단해”라고 Prompt만 추가하는 것은 정책 엔진이 아닙니다.

## 23. 정책 규칙은 코드와 함께 검증 가능해야 한다

다음은 개념을 보여 주기 위한 간단한 Rego 예시입니다.

```rego
package agent.approval

default decision := {
  "result": "DENY",
  "reason": "NO_MATCHING_POLICY"
}

decision := {
  "result": "ALLOW",
  "reason": "AUTHORIZED_READ"
} if {
  input.action.riskClass == "READ"
  input.authorization.allowed == true
  input.object.sensitivity != "RESTRICTED"
}

decision := {
  "result": "REQUIRE_CONFIRMATION",
  "reason": "IMPORTANT_ACTION"
} if {
  input.action.riskClass == "IMPORTANT"
  input.authorization.allowed == true
}

decision := {
  "result": "REQUIRE_CONFIRMATION",
  "reason": "DESTRUCTIVE_ACTION",
  "obligations": {
    "maxUses": 1,
    "approvalTtlSeconds": 300
  }
} if {
  input.action.riskClass == "DESTRUCTIVE"
  input.authorization.allowed == true
}
```

실제 정책에는 Tenant 경계, 객체 소유권, 강화 인증, 업무 시간, 대량 작업 제한과 긴급 차단 조건이 추가됩니다.

정책 변경도 Application 변경처럼 Version 관리, Review, Test와 Rollback이 필요합니다.

## 24. 감사 로그는 의도·결정·승인·실행을 연결한다

“누가 삭제 API를 호출했다”는 Log만으로는 Agent 실행을 재구성하기 어렵습니다.

다음 Event를 하나의 Trace로 연결합니다.

```text
User Request
  → Model Tool Intent
  → Policy Decision
  → Preview
  → User Approval
  → Authorization Recheck
  → Tool Execution
  → Business Result
```

```json
{
  "auditEvent": {
    "traceId": "trace_fixture_001",
    "decisionId": "decision_fixture_001",
    "approvalGrantId": "grant_fixture_001",
    "principalId": "user_fixture_alpha",
    "tenantId": "tenant_fixture_alpha",
    "tool": "meeting.transfer",
    "resourceType": "meeting",
    "resourceIdHash": "sha256:fixture_resource_hash",
    "requestFingerprint": "sha256:fixture_request_hash",
    "policyVersion": "agent-approval-2026-07",
    "decision": "ALLOW",
    "result": "SUCCESS",
    "occurredAt": "2026-07-29T09:02:00Z"
  }
}
```

Open Policy Agent의 Decision Log도 정책 Query, 입력, 결과, Decision ID와 Bundle Revision을 기록할 수 있습니다.

다만 감사 가능성을 이유로 Prompt 전문, Access Token, 개인정보와 Tool 결과 전체를 무조건 저장해서는 안 됩니다. 민감 Field를 지우거나 Masking하고, 보존 기간과 접근 권한을 별도로 정합니다.

## 25. 거부와 오류를 구분해 사용자에게 보여 준다

실패가 모두 같은 실패는 아닙니다.

| 종류 | 예시 | 사용자 처리 |
|---|---|---|
| 인증 실패 | Session 만료 | 재로그인 안내 |
| 인가 거부 | 대상 객체 권한 없음 | 권한 요청 또는 대상 변경 |
| 승인 필요 | 중요 작업 | Preview와 승인 요청 |
| 승인 무효 | 입력·Revision 변경 | 새 Preview와 재승인 |
| 정책 거부 | 파괴 작업 금지 시간 | 사유와 허용 조건 안내 |
| 업무 오류 | 대상 상태 충돌 | 최신 상태와 해결 방법 안내 |
| 시스템 오류 | Timeout·의존성 장애 | 결과 조회 후 안전한 재시도 |

MCP에서는 Protocol 자체의 오류와 Tool 실행 결과의 업무 오류도 구분합니다. Agent가 오류 유형을 알아야 잘못된 자동 재시도를 피할 수 있습니다.

거부 사유는 사용자가 다음 행동을 선택할 만큼 명확해야 하지만, 내부 정책 구조나 민감한 Resource 존재 여부를 과도하게 노출해서는 안 됩니다.

## 26. 승인 정책 테스트는 우회와 재사용을 중심으로 만든다

정상 승인 한 건만 통과시키는 테스트로는 부족합니다.

| 테스트 | 기대 결과 |
|---|---|
| 승인 없이 중요 작업 호출 | 차단 |
| 다른 사용자의 Grant 재사용 | 차단 |
| 다른 Tenant에서 Grant 재사용 | 차단 |
| Tool 이름 변경 | 차단 |
| 대상 Resource 변경 | 차단 |
| 인자 하나 변경 | 새 승인 요구 |
| Grant 만료 후 실행 | 새 승인 요구 |
| 이미 사용한 1회성 Grant Replay | 차단 |
| 승인 후 객체 Revision 변경 | 새 Preview 요구 |
| 승인 후 사용자 권한 회수 | 차단 |
| Batch 건수 상한 초과 | 차단 또는 범위 축소 |
| Timeout 후 동일 멱등성 Key 재호출 | 기존 결과 반환 |
| 동일 멱등성 Key에 다른 입력 | 차단 |
| Sub-agent가 승인 범위 확장 | 차단 |
| Tool Annotation이 위험도를 낮춰 보고 | Registry 정책 유지 |

정책 테스트에는 정상 Case뿐 아니라 우회 Case, 경쟁 상태와 과거 Incident 재현을 포함합니다.

## 27. 운영 도입은 Shadow Mode부터 시작한다

기존 Agent에 강한 승인 정책을 한 번에 적용하면 업무가 과도하게 중단될 수 있습니다.

다음 순서로 도입할 수 있습니다.

```text
1. Tool Inventory와 Owner 확인
2. 위험 등급과 속성 분류
3. 기존 호출을 Shadow Policy로 평가
4. 실제 결정과 예상 결정 비교
5. 파괴 작업부터 강제 차단
6. 중요 작업에 Preview와 승인 적용
7. 저위험 반복 작업의 제한적 Session Grant 도입
8. 오탐·승인 피로·우회 시도를 지속 측정
```

Shadow Mode에서는 정책 결정을 기록하되 기존 호출을 차단하지 않습니다. 이 자료로 어떤 Tool이 예상보다 많이 실행되고, 어떤 규칙이 정상 업무를 방해하는지 확인합니다.

운영 지표는 다음과 같습니다.

- 위험 등급별 Tool 호출 수
- 승인 요청·승인·거부 비율
- 승인 후 입력 변경 비율
- 만료·Replay 차단 수
- 승인에서 실행까지 걸린 시간
- 사용자별 반복 승인 빈도
- 정책 거부 후 우회 시도
- 중복 실행 방지 건수
- 권한 재검사 실패 건수

승인율이 높다는 사실만으로 정책이 좋은 것은 아닙니다. 사용자가 내용을 읽지 않고 습관적으로 승인하는지 함께 살펴야 합니다.

## 28. 구현 체크리스트

### Tool 분류

- [ ] 모든 Tool에 Owner와 신뢰 수준이 있는가?
- [ ] 읽기·쓰기·중요·파괴 작업이 구분돼 있는가?
- [ ] 민감도·영향 범위·가역성·외부 효과를 평가하는가?
- [ ] 외부 Server의 Annotation을 정책 근거로 그대로 신뢰하지 않는가?
- [ ] Tool Metadata 변경을 감지하고 재검토하는가?

### 인증과 인가

- [ ] 실제 사용자 Principal과 Tenant가 모든 호출에 전달되는가?
- [ ] 사용자 Context에서 최소 권한으로 실행하는가?
- [ ] 객체 단위 권한을 실행 직전에 다시 검사하는가?
- [ ] OAuth 동의와 업무 작업 승인을 구분하는가?
- [ ] 다운스트림 업무 시스템도 권한을 검사하는가?

### 승인 경험

- [ ] 사용자가 Tool 이름이 아니라 실제 영향을 볼 수 있는가?
- [ ] 대상·건수·수신자·비용·가역성을 표시하는가?
- [ ] 승인과 취소 버튼이 명확한가?
- [ ] 자연어 승인이 하나의 열린 요청에 명확히 연결되는가?
- [ ] 파괴 작업에 포괄적 Session 승인을 허용하지 않는가?

### 승인 Grant

- [ ] 사용자·Tenant·Session·Tool·대상에 바인딩되는가?
- [ ] 정규화된 입력 지문과 Resource Revision을 포함하는가?
- [ ] 만료 시간과 최대 사용 횟수가 있는가?
- [ ] Model이 Grant를 생성하거나 수정할 수 없는가?
- [ ] 정책 Version 변경과 긴급 차단을 반영하는가?

### 실행 안전성

- [ ] 쓰기 작업에 멱등성 Key가 있는가?
- [ ] Timeout 후 기존 결과를 먼저 조회하는가?
- [ ] 비멱등 작업을 무조건 자동 재시도하지 않는가?
- [ ] 일괄 작업의 대상과 최대 건수를 고정하는가?
- [ ] 비동기 작업의 접수·실행·완료 상태를 구분하는가?

### 관측과 검증

- [ ] 의도·정책·승인·실행 Event가 Trace로 연결되는가?
- [ ] Decision ID와 Policy Version을 기록하는가?
- [ ] Log에서 Token·개인정보·민감 입력을 제거하는가?
- [ ] Replay·TOCTOU·Sub-agent·Batch 우회 테스트가 있는가?
- [ ] 승인 피로와 정책 오탐을 운영 지표로 보는가?

## 29. 마무리

AI Agent 승인 정책의 목표는 모든 Tool Call 앞에 확인 Dialog를 붙이는 것이 아닙니다.

위험이 낮은 작업은 불필요한 마찰 없이 실행하고, 영향이 큰 작업은 사용자가 결과를 이해한 상태에서 구체적으로 승인하며, 어떤 경우에도 현재 권한과 실행 안전 조건을 우회하지 못하게 만드는 것이 목표입니다.

```text
Safe Agent Action
  = Trusted Tool Classification
  + Current Authorization
  + Risk-based Approval
  + Approval Binding
  + Execution Preconditions
  + Idempotency and Recovery
  + Auditability
```

핵심 원칙은 다음 한 문장으로 정리할 수 있습니다.

> Agent는 실행을 제안할 수 있지만, 위험 작업을 승인하거나 권한을 부여할 수는 없습니다.

사용자의 짧은 “응, 진행해”를 안전한 실행으로 바꾸려면 대화 해석 뒤에 정책 결정, 실행 미리보기, 승인 바인딩, 권한 재검사와 중복 방지가 이어져야 합니다.

승인은 UX 요소이면서 동시에 보안·분산 시스템·감사의 계약입니다. 이 계약이 명확할수록 Agent는 더 많은 업무를 수행하면서도 사용자가 통제권을 유지할 수 있습니다.

---

## 참고 자료

- [Model Context Protocol 2026-07-28 - Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [Model Context Protocol - Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [Model Context Protocol - Client Security Best Practices](https://modelcontextprotocol.io/docs/develop/clients/client-best-practices)
- [OWASP LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
- [NIST SP 800-162 - Guide to Attribute Based Access Control](https://csrc.nist.gov/pubs/sp/800/162/upd2/final)
- [Open Policy Agent - Documentation](https://www.openpolicyagent.org/docs)
- [Open Policy Agent - Integrating OPA](https://www.openpolicyagent.org/docs/integration)
- [Open Policy Agent - Decision Logs](https://www.openpolicyagent.org/docs/management-decision-logs)
- [RFC 9110 - HTTP Semantics](https://datatracker.ietf.org/doc/html/rfc9110)
- [OpenTelemetry - Traces](https://opentelemetry.io/docs/concepts/signals/traces/)
- [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)

> 이 글은 특정 Policy Engine이나 Agent Framework를 필수 선택으로 제안하지 않습니다. 실제 승인 강도와 보존 정책은 업무 영향, 데이터 민감도, 규제, 복구 가능성과 조직의 책임 구조에 맞게 결정해야 합니다.
