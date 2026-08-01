# Tistory 기술자료 초안

- 문서 ID: `BLOG-24`
- 상태: 공개 완료
- Tistory 상태: 2026-07-30 공개 게시 및 공개 페이지 검증 완료
- 분류: `보안`
- 공개 URL: `https://aiarchitect.tistory.com/24`
- 권장 제목: `AI Agent 자격 증명 관리: 단기 Token·Credential Broker·Secret Masking`
- 검색 설명: `AI Agent의 Token과 API Key를 모델 Context에서 분리하고, Credential Broker를 통해 Downstream별 단기 자격 증명을 발급·주입·회전·폐기하며 Prompt·Tool·Log에서 Secret을 제거하는 운영 설계를 정리합니다.`
- 권장 태그: `AI Agent 보안`, `Credential Broker`, `Short-lived Token`, `Secret Manager`, `Secret Masking`, `OAuth Token Exchange`, `MCP 보안`, `자격 증명 관리`
- 권장 대표 이미지: `portfolio/architecture-diagrams/01-enterprise-ai-reference-architecture.svg`

---

# AI Agent 자격 증명 관리: 단기 Token·Credential Broker·Secret Masking

AI Agent가 업무를 수행하려면 여러 시스템에 접근해야 합니다.

```text
MCP Server
문서 저장소
Database
업무 API
Object Storage
외부 SaaS
Cloud Service
```

이때 가장 단순한 구현은 하나의 API Key나 Access Token을 Agent Process에 넣고 모든 Tool이 공유하게 만드는 것입니다.

개발 환경에서는 빨리 동작할 수 있지만 운영에서는 다음 문제가 생깁니다.

```text
모델 Context에 Token 노출
Prompt·Tool 인자·Error·Trace로 Secret 복제
모든 Downstream에 같은 Credential 재사용
과도한 Scope와 여러 Audience
Queue에 만료되지 않는 Token 저장
누가 어떤 권한으로 호출했는지 추적 불가
한 번 유출된 Key의 긴 악용 시간
회전 시 전체 Agent 중단
```

AI Agent의 Credential (자격 증명)은 모델이 추론에 사용하는 데이터가 아닙니다.

모델은 **무슨 작업이 필요한지 제안**하고, 신뢰할 수 있는 Application 계층이 **누가·어느 Resource에·어떤 Scope로·얼마 동안 접근할지 결정한 뒤 Credential을 주입**해야 합니다.

```text
Model·Planner
  → Tool Call Proposal
    → Tool Broker
      → Policy·Approval 검증
        → Credential Broker
          → 목적지 전용 단기 Credential
            → Downstream 호출
```

이 글은 OAuth 로그인 흐름이나 MCP Resource Server 검증을 반복하기보다, Agent의 실행 경로에서 Credential을 발급·전달·저장·회전·폐기·감사하는 운영 설계를 다룹니다.

## 1. 먼저 Credential과 Secret을 구분한다

Secret (비밀정보)은 노출되면 보호 속성이 깨지는 값입니다.

Credential은 Identity (신원) 또는 권한을 증명하는 수단입니다.

| 유형 | 예시 | 특징 |
|---|---|---|
| Access Token | OAuth Access Token | Resource·Scope·수명 제한 가능 |
| Refresh Token | Access Token 재발급 수단 | Access Token보다 오래 살 수 있어 더 강하게 보호 |
| API Key | 외부 SaaS Key | 정적·장기·넓은 권한인 경우가 많음 |
| Client Secret | OAuth Client 인증 값 | Application Identity 증명 |
| Private Key | 서명·mTLS·DPoP Key | Token보다 강한 Root Material이 될 수 있음 |
| Database Credential | 사용자명·Password·Certificate | Data Store 접근 권한 |
| Workload Identity | X.509-SVID·JWT-SVID 등 | 실행 Workload에 결속된 신원 |
| Presigned URL | 제한된 Object 접근 URL | URL 자체가 Bearer Credential이 될 수 있음 |

모든 Secret이 OAuth Token인 것은 아니고, 모든 Token이 같은 위험을 갖는 것도 아닙니다.

관리 정책에는 최소한 다음 속성이 필요합니다.

```text
Owner
Consumer
Purpose
Resource·Audience
Scope·Role
Environment
Issued At
Expires At
Rotation Method
Revocation Method
Storage Location
Audit Owner
```

값 자체보다 Metadata와 수명주기를 관리해야 합니다.

## 2. Credential 위험은 권한·재사용성·수명으로 평가한다

Credential이 유출됐을 때의 Blast Radius (피해 범위)는 다음 요소의 곱으로 볼 수 있습니다.

```text
피해 범위
  ≈ 접근 가능한 Resource 수
  × 허용 Action 수
  × 접근 가능한 데이터 범위
  × 사용할 수 있는 시간
  × 다른 위치에서 재사용할 수 있는 정도
```

같은 Token이라도 위험은 다릅니다.

| Credential | 위험 |
|---|---|
| 한 Resource의 읽기 전용·단기 Token | 비교적 제한적 |
| 여러 API에서 쓸 수 있는 장기 Bearer Token | 큼 |
| 전체 Tenant 관리자 API Key | 매우 큼 |
| Token 발급용 Client Secret·Private Key | 반복 발급 가능해 매우 큼 |

따라서 “암호화해서 저장했다”는 사실만으로 충분하지 않습니다.

도난 후 사용할 수 있는 권한, 목적지, 시간과 발신자를 함께 제한해야 합니다.

## 3. 모델은 Credential을 볼 필요가 없다

모델이 알아야 할 것은 Credential 값이 아니라 사용 가능한 Capability (기능)입니다.

```text
모델이 보는 것
  document_read(documentId)
  issue_create(projectId, title, body)

모델이 보지 않는 것
  Authorization Header
  API Key
  Client Secret
  Refresh Token
  Private Key
  Database Password
```

MCP Client Best Practices는 Host가 Token과 Credential을 보관하고, 생성된 Code에는 Typed Function만 노출한 뒤 Host가 Server 호출 시 인증 정보를 추가하는 구조를 설명합니다.

다음 위치에 Credential을 넣지 않습니다.

- System·Developer Prompt
- 사용자 Message와 Model Context
- Tool Description과 예시
- Tool Input Schema의 일반 Field
- RAG 문서와 Embedding
- Agent Memory
- 모델이 생성하는 Code·Shell Script
- Error Message와 Tool Result
- Log·Trace·Metric Label

모델이 Credential을 직접 다루지 않으면 Prompt Injection이 성공해도 Secret 원문을 읽어 출력하는 경로를 줄일 수 있습니다.

## 4. 신뢰 경계를 네 영역으로 나눈다

Agent Credential 흐름을 다음 네 영역으로 분리합니다.

```text
Untrusted Reasoning Zone
  Model·Prompt·Retrieved Content·Generated Code

Trusted Execution Zone
  Tool Broker·Policy Enforcement·Approval Verification

Credential Zone
  Credential Broker·Secret Manager·STS·KMS·HSM

Resource Zone
  MCP Server·업무 API·Database·Storage·외부 SaaS
```

각 영역의 책임이 다릅니다.

| 영역 | 허용 | 금지 |
|---|---|---|
| Reasoning | Tool과 인자 제안 | Secret 조회·Header 구성 |
| Execution | 인가·정책·승인·호출 | Credential 장기 저장 |
| Credential | 발급·교환·주입·회전·폐기 | 업무 내용 추론 |
| Resource | Token 검증·객체 권한·업무 실행 | 다른 Audience Token 수락 |

Credential Zone의 API는 “Secret 값을 달라”보다 “이 검증된 작업에 사용할 제한 Credential로 호출하라”에 가까워야 합니다.

## 5. Credential Broker의 책임을 명확히 한다

Credential Broker (자격 증명 중개자)는 Agent와 Downstream Credential 사이의 정책 집행 계층입니다.

주요 책임은 다음과 같습니다.

1. 호출 Workload와 사용자·Tenant Context 인증
2. 요청된 Tool·Resource·Scope·목적 검증
3. 승인과 정책 Version 확인
4. Secret Manager 또는 Security Token Service (STS, 보안 토큰 서비스) 호출
5. 목적지 전용 단기 Credential 발급·교환
6. Tool 실행 직전에 Header·Connection에 주입
7. Credential 원문을 모델·업무 Log에서 차단
8. 발급·사용·실패·폐기 Event 기록
9. Cache·만료·회전·장애 정책 적용

Broker 입력은 Credential 값이 아니라 Credential Request (자격 증명 요청)입니다.

```json
{
  "requestId": "crq_opaque_id",
  "subject": {
    "userId": "usr_opaque_id",
    "tenantId": "ten_opaque_id"
  },
  "actor": {
    "workloadId": "wld_tool_broker",
    "agentRunId": "run_opaque_id"
  },
  "action": {
    "tool": "document_read",
    "resource": "https://documents.example.com",
    "scopes": [
      "documents.read"
    ],
    "objectIds": [
      "doc_opaque_id"
    ]
  },
  "constraints": {
    "maxLifetimeSeconds": "POLICY_VALUE",
    "externalEgress": false
  },
  "policyVersion": "credential_policy_fixture_v1"
}
```

`maxLifetimeSeconds`는 모델이 정하는 값이 아니라 Server 정책의 상한 안에서 적용됩니다.

## 6. Secret Manager와 Credential Broker를 구분한다

Secret Manager (비밀정보 관리자)는 Secret의 안전한 저장, 접근 제어, Version, 회전과 감사에 초점을 둡니다.

Credential Broker는 현재 Agent 작업에 어떤 Credential을 어떻게 사용할지 결정합니다.

```text
Secret Manager
  장기 Root Secret·Private Key·Legacy API Key 보관

STS·Identity Provider
  단기 Token·동적 Credential 발급

Credential Broker
  작업 Context 검증·발급 요청·주입·사용 감사

Tool Broker
  Tool 인자 검증·실제 업무 API 호출
```

작은 시스템에서는 한 Component가 여러 역할을 수행할 수 있습니다.

그래도 논리적 책임을 분리해야 다음 질문에 답할 수 있습니다.

- 누가 Root Secret을 읽을 수 있는가?
- 누가 단기 Credential 발급을 요청할 수 있는가?
- 누가 Tool 호출을 승인했는가?
- Credential 값이 어느 Process Memory에 존재했는가?
- 어떤 Downstream에서 실제 사용됐는가?

## 7. 장기 Secret은 단기 Credential 발급에만 사용한다

Legacy API가 정적 Key만 지원하는 경우가 있습니다.

이때 장기 Key를 모든 Agent Worker에 배포하지 않습니다.

```text
장기 Root Secret
  → Secret Manager 또는 HSM에 보관
    → 제한된 Broker만 접근
      → 가능하면 Downstream 전용 동적 Credential 발급
        → Tool 호출 직전에 사용
```

동적 Credential을 지원하지 않는 API라면 Broker 또는 Egress Proxy가 Key를 주입하고 Agent Process에는 원문을 제공하지 않는 구조를 사용합니다.

장기 Secret에는 다음 제한이 필요합니다.

- 환경별 분리
- Consumer별 분리
- 목적·Resource별 분리
- Secret 접근 가능 Workload 제한
- 자동 회전과 이전 Version 중단
- 사용량·위치 이상 탐지
- 비상 폐기 절차

하나의 관리자 API Key를 개발·검증·운영과 여러 Tool이 공유하면 유출 경로와 사고 범위를 구분하기 어렵습니다.

## 8. 단기 Token의 수명은 위험과 복구 능력으로 정한다

Short-lived Token (단기 토큰)은 유출된 Credential을 사용할 수 있는 시간을 줄입니다.

그러나 모든 시스템에 적용할 하나의 정답 수명은 없습니다.

다음 요소를 함께 봅니다.

| 요소 | 수명에 미치는 영향 |
|---|---|
| 쓰기·삭제·관리 권한 | 더 짧게 |
| 민감 데이터 접근 | 더 짧게 |
| Sender Constraint 적용 | Replay 위험 감소 |
| 즉시 폐기 지원 | 사고 대응 개선 |
| 재발급 지연·가용성 | 너무 짧으면 운영 부담 |
| 장시간 Workflow | 실행 단위 재발급 필요 |
| Offline 사용 | 별도 강한 정책 필요 |

Token 수명은 업무 시간보다 “한 번의 검증된 실행 구간”에 맞춥니다.

```text
나쁜 구조
  24시간 Workflow를 위해 24시간 Token 발급

권장 구조
  Workflow 상태 저장
  → Step 실행 직전 권한 재검증
  → 해당 Step용 단기 Token 발급
  → 실행 완료·만료
```

단기 Token은 최소 Scope, 단일 Audience, 폐기·탐지와 결합해야 효과가 있습니다.

## 9. Audience와 Resource를 Downstream별로 좁힌다

Scope는 “무엇을 할 수 있는가”를 나타내고, Audience·Resource는 “어디에서 사용할 수 있는가”를 제한합니다.

```text
Token A
  aud = document service
  scope = documents.read

Token B
  aud = issue service
  scope = issues.create
```

RFC 8707 Resource Indicators (대상 Resource 지정)는 Client가 접근하려는 Resource를 Token 요청에 명시하고 Authorization Server가 Audience-restricted Token (대상 제한 토큰)을 발급할 수 있게 합니다.

MCP 2026-07-28 Authorization도 Resource Parameter 사용과 현재 MCP Server Audience 검증을 요구합니다.

다음 구조를 피합니다.

```text
하나의 Bearer Token
  aud = 여러 Service
  scope = read write admin
  lifetime = 장기
```

한 Downstream에서 Token이 노출돼도 다른 Service에서 재사용할 수 없도록 Resource별 Credential을 사용합니다.

## 10. Token Passthrough 대신 교환·재발급한다

Token Passthrough (토큰 전달)는 Client가 MCP Server에 보낸 Token을 Server가 Downstream API로 그대로 넘기는 Anti-pattern (안티패턴)입니다.

MCP Security Best Practices는 MCP Server를 위해 발급되지 않은 Token의 수락과 Passthrough를 명시적으로 금지합니다.

권장 흐름은 다음과 같습니다.

```text
MCP Client Token
  aud = MCP Server
  scope = tool.request
        ↓ 검증
MCP Server·Credential Broker
        ↓ 교환 또는 별도 발급
Downstream Token
  aud = Document API
  scope = documents.read
  actor = MCP Tool Broker
  subject = verified user
```

이 구조는 다음을 분리합니다.

- MCP Client가 MCP Server를 호출할 권한
- MCP Server가 Downstream을 호출할 Workload Identity
- 사용자를 대신하는 Delegation Context
- Downstream 업무 객체에 대한 최종 권한

## 11. Delegation과 Impersonation을 구분한다

Delegation (위임)은 Agent 또는 Service가 사용자를 대신해 행동하되 Actor (행위자)도 식별되는 구조입니다.

Impersonation (가장)은 제한된 권한 Context에서 Service가 사용자처럼 취급되는 구조입니다.

RFC 8693 OAuth 2.0 Token Exchange는 `subject_token`, `actor_token`과 `act` Claim을 이용해 두 의미를 표현할 수 있게 합니다.

Agent 시스템에서는 가능하면 다음 정보를 모두 보존합니다.

```text
Subject
  업무 권한의 원래 사용자

Actor
  실제로 호출한 Agent·Tool Broker·Service

Client
  사용자가 이용한 MCP Host·Application

Tenant
  데이터·정책 경계

Purpose
  어떤 사용자 의도를 위해 호출했는가
```

Credential Manifest (자격 증명 명세) 예시는 다음과 같습니다.

```json
{
  "credentialId": "cred_opaque_id",
  "subjectId": "usr_opaque_id",
  "actorId": "wld_tool_broker",
  "clientId": "client_opaque_id",
  "tenantId": "ten_opaque_id",
  "resource": "https://documents.example.com",
  "scopes": [
    "documents.read"
  ],
  "purpose": "summarize_document",
  "issuedAt": "2026-07-29T13:00:00Z",
  "expiresAt": "2026-07-29T13:05:00Z",
  "tokenValueStored": false
}
```

감사 Log에는 Token 원문 대신 이 Metadata와 불투명한 `credentialId`를 사용합니다.

## 12. Workload Identity로 Broker 자체를 인증한다

Credential Broker에게 단기 Token을 요청하는 Component도 신원을 증명해야 합니다.

정적 Password를 Container Image나 환경 변수에 넣는 대신 Runtime의 Workload Identity (작업 부하 신원)를 사용할 수 있습니다.

```text
Platform Attestation
  → Workload Identity 발급
    → Broker가 Workload·Namespace·Service Account 검증
      → 허용된 Credential Policy만 적용
```

NIST SP 800-207A는 Cloud-native 환경에서 Application과 Service Identity를 기반으로 한 접근 제어 모델을 설명합니다.

SPIFFE의 SVID (SPIFFE Verifiable Identity Document)는 Workload에 짧은 수명의 X.509 또는 JWT Identity를 제공하고 자동 회전을 지원합니다.

중요한 원칙은 제품 선택보다 다음입니다.

- 배포 시점이 아니라 Runtime에 Workload 신원 확인
- Environment·Cluster·Namespace·Service와 결속
- 짧은 수명과 자동 회전
- Private Key를 일반 Application Code에 노출하지 않음
- Workload 변경·삭제 시 권한 중단

Workload Identity는 사용자 위임 권한을 자동으로 의미하지 않습니다. Broker는 Workload와 사용자 Context를 함께 검증합니다.

## 13. Sender-constrained Token으로 Replay를 줄인다

Bearer Token (소지자 토큰)은 값을 가진 누구나 사용할 수 있습니다.

Sender-constrained Token (발신자 제한 토큰)은 Token 외에 특정 Key의 소유도 증명해야 합니다.

OAuth Security BCP인 RFC 9700은 Access Token Replay를 줄이기 위해 Audience 제한과 Sender Constraint를 권고합니다.

대표 방식은 다음과 같습니다.

| 방식 | 핵심 |
|---|---|
| mTLS Certificate-bound Token | Client Certificate에 Token 결속 |
| DPoP | Application 계층에서 Public Key와 Request Proof에 결속 |

RFC 9449 DPoP는 Access Token을 Public Key에 결속하고, Client가 해당 Private Key를 소유했음을 Request마다 증명하도록 합니다.

다만 Token과 Private Key가 함께 탈취되면 보호가 약해집니다.

따라서 다음을 함께 적용합니다.

- Key를 HSM·OS Key Store·격리된 Sidecar 등에서 보호
- Proof의 URI·HTTP Method·시간·Nonce 검증
- Replay Cache와 짧은 Proof 유효 시간
- TLS Server Identity 검증
- Token Audience·Scope·만료와 최종 인가

모든 연동이 Sender Constraint를 지원하지는 않으므로 위험도가 높은 Credential부터 적용합니다.

## 14. Broker는 Secret Handle을 Capability로 오해하지 않는다

Agent와 Tool Broker 사이에는 Token 원문 대신 Credential Handle (자격 증명 핸들)을 사용할 수 있습니다.

```json
{
  "credentialHandle": "ch_opaque_id",
  "resource": "https://documents.example.com",
  "scopeSetId": "scope_documents_read",
  "subjectId": "usr_opaque_id",
  "actorId": "wld_tool_broker",
  "expiresAt": "2026-07-29T13:05:00Z"
}
```

Handle은 Secret 원문 노출을 줄이지만 그 자체만으로 권한 증거가 아닙니다.

Broker는 사용할 때마다 다음을 확인합니다.

- 요청 Workload가 Handle의 Actor인가?
- 사용자·Tenant·Run이 일치하는가?
- Resource와 Scope가 현재 Tool Call과 일치하는가?
- 만료·폐기·정책 변경이 없는가?
- 승인과 원래 사용자 의도가 유효한가?

Handle을 추측하기 어렵게 만드는 것과 Server-side Authorization (서버 측 인가)은 서로 다른 통제입니다.

## 15. Credential을 Tool 실행 직전에 주입한다

Credential은 가능한 한 늦게 획득하고 빨리 폐기합니다.

```text
Tool Call Proposal
  → Input Schema·업무 규칙
    → 사용자·Tenant·객체 권한
      → 승인·정책·예산
        → Credential 요청
          → HTTP Header·Connection에 주입
            → Downstream 호출
              → 응답 정제
                → Credential Memory 제거
```

모델이 만든 Tool 인자에 `authorization`, `apiKey`, `cookie`, `clientSecret` 같은 Field를 허용하지 않습니다.

Tool Input Schema는 추가 Field를 기본 거부합니다.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "documentId": {
      "type": "string",
      "pattern": "^doc_[a-z0-9_]+$"
    }
  },
  "required": [
    "documentId"
  ],
  "additionalProperties": false
}
```

Credential 주입은 Typed Client, Proxy, Sidecar 또는 Broker 내부에서 수행합니다.

## 16. Queue에는 Token이 아니라 재검증 가능한 Context를 저장한다

비동기 Agent Workflow가 Queue에서 오랜 시간 대기할 수 있습니다.

다음 Message는 위험합니다.

```text
userAccessToken
refreshToken
apiKey
databasePassword
presignedUrl
```

Queue에는 실행을 재구성할 최소 Context만 저장합니다.

```json
{
  "jobId": "job_opaque_id",
  "subjectId": "usr_opaque_id",
  "tenantId": "ten_opaque_id",
  "actorPolicy": "summary_worker",
  "intentId": "int_opaque_id",
  "tool": "document_read",
  "resourceId": "doc_opaque_id",
  "requiredScopes": [
    "documents.read"
  ],
  "approvalId": null,
  "policyVersion": "credential_policy_fixture_v1",
  "notAfter": "2026-07-29T14:00:00Z"
}
```

Worker는 실행 직전에 다음 순서로 처리합니다.

```text
Job 만료 확인
  → 사용자·Tenant·객체 권한 재검증
    → 승인·정책 변경 확인
      → Workload Identity 검증
        → 새 단기 Credential 발급
          → Step 실행
```

사용자가 퇴사하거나 권한이 철회됐다면 Queue에 Job이 남아 있어도 실행하지 않습니다.

## 17. Token Cache Key를 보안 Context 전체로 만든다

매 호출마다 Token을 발급하면 Authorization Server 부하와 지연이 커질 수 있어 짧은 Cache를 사용할 수 있습니다.

Cache Key를 `resource` 하나로 만들면 다른 사용자·Tenant·Scope Token이 섞일 수 있습니다.

```text
Credential Cache Key
  subjectId
  actorId
  tenantId
  clientId
  resource
  normalizedScopes
  senderKeyId
  policyVersion
  authorizationContextVersion
```

Cache Entry는 다음 Metadata만 노출합니다.

```json
{
  "cacheEntryId": "cec_opaque_id",
  "credentialId": "cred_opaque_id",
  "contextDigest": "sha256_fixture_value",
  "resource": "https://documents.example.com",
  "scopeSetId": "scope_documents_read",
  "expiresAt": "2026-07-29T13:05:00Z",
  "refreshAfter": "POLICY_VALUE",
  "revocationVersion": 4
}
```

Token 원문은 암호화된 Process Memory 또는 전용 Credential Store에 두고 일반 Cache 조회 결과와 Log에 반환하지 않습니다.

Cache Hit에서도 현재 정책, 승인, 객체 권한과 폐기 Version을 다시 확인합니다.

## 18. Refresh Token은 Access Token보다 강하게 보호한다

Access Token이 짧아도 Refresh Token이 오래 살고 쉽게 복제된다면 공격자는 새 Token을 계속 만들 수 있습니다.

Refresh Token 정책에는 다음이 필요합니다.

- 안전한 전용 저장소
- Client·Sender 결속
- Refresh Token Rotation (재발급 토큰 회전)
- 재사용 탐지
- 사용자·Client·Session 종료 시 폐기
- Idle·Absolute Lifetime 분리
- Scope·Resource 확대 금지

Model, Tool Worker와 일반 Business Service가 Refresh Token을 직접 읽지 않게 합니다.

가능하면 Credential Broker만 Refresh Token을 다루거나, Platform Identity로 STS에서 새 Access Token을 발급받습니다.

RFC 9700은 Public Client의 Refresh Token에 Sender Constraint 또는 Rotation을 요구합니다.

## 19. 실패 정책은 위험 등급별로 정한다

Credential Broker나 Secret Manager가 실패했을 때 이전 Token을 무기한 재사용하면 단기 수명과 폐기 정책이 무력화됩니다.

| 작업 | Broker 장애 시 권장 기본값 |
|---|---|
| 공개 데이터 읽기 | 제한된 Cache·Grace 정책 검토 가능 |
| 내부 읽기 | 유효한 Cache와 정책 조건에서만 제한적으로 |
| 민감 데이터 | Fail Closed (실패 시 거부) |
| 외부 전송·쓰기 | Fail Closed |
| 삭제·권한 변경·관리 | Fail Closed |

Grace Period (유예 시간)을 사용한다면 다음을 명시합니다.

- 어떤 Tool과 Scope에 적용하는가
- 최대 시간과 횟수
- 정책·폐기 Cache가 얼마나 최신이어야 하는가
- Sender Constraint가 필요한가
- 어떤 Alert와 감사 Event를 남기는가

Expired Token을 Clock Skew 이상의 시간 동안 허용하는 방식으로 구현하면 안 됩니다.

## 20. Rotation은 새 값 발급보다 전체 전환 과정이다

Credential Rotation (자격 증명 회전)은 새 Secret을 만드는 한 단계가 아닙니다.

```text
새 Version 생성
  → Consumer 배포
    → 새 Version 동작 검증
      → Traffic 전환
        → 이전 Version 사용 탐지
          → 이전 Version 폐기
            → 복구 가능성 확인
```

회전 전략을 Credential 유형별로 구분합니다.

| 유형 | 회전 방식 |
|---|---|
| 단기 Access Token | 만료 후 재발급 |
| Refresh Token | 사용 시 회전·재사용 탐지 |
| API Key | Dual Key 또는 Version 전환 후 이전 Key 폐기 |
| Database Password | 동적 계정 또는 단계적 Password 전환 |
| Certificate | 새 Certificate 배포·Trust 중첩·이전 폐기 |
| Signing Key | `kid` Version·검증 Key 중첩·서명 Key 전환 |

회전 시험에는 오래된 Worker, Cache, Queue, Retry와 Disaster Recovery 환경이 이전 Credential을 계속 사용하는지 포함합니다.

## 21. Revocation은 발급 시스템과 실행 시스템을 연결한다

짧은 수명은 Revocation (폐기)을 대신하지 않습니다.

다음 사건은 즉시 폐기가 필요할 수 있습니다.

- 사용자 권한 철회·퇴사
- Workload 손상·배포 취소
- Client·Agent 비활성화
- Secret 노출 탐지
- 정책·Tenant 관계 변경
- 비정상 사용 위치·빈도

폐기 Event는 다음 Component에 전달돼야 합니다.

```text
Authorization Server
Credential Broker
Token·Secret Cache
Tool Broker
Queue Worker
API Gateway
Downstream Resource Server
Detection·Incident Response
```

Self-contained JWT는 발급 후 만료 전까지 독립 검증될 수 있으므로 매우 빠른 권한 철회가 필요한 작업에는 짧은 수명, Introspection, Revocation Version 또는 별도 정책 확인을 조합합니다.

## 22. Secret Masking은 생성 지점에서 시작한다

Secret Masking (비밀정보 가림 처리)은 중앙 Log 저장소에 들어간 뒤 적용하는 마지막 단계가 아닙니다.

```text
HTTP Client
  → Application Logger
    → Agent Trace
      → APM Collector
        → Message Queue
          → SIEM·Dashboard
```

각 단계에서 Secret이 복제될 수 있습니다.

가장 안전한 방법은 Secret 원문을 Log Event에 처음부터 넣지 않는 것입니다.

다음 값은 기본 기록 금지 목록으로 둡니다.

- `Authorization`·`Proxy-Authorization`
- Access·Refresh·ID Token
- Cookie·Session ID
- API Key·Client Secret
- Password·Connection String
- Private Key·Signing Key
- Presigned URL의 Signature·Query
- OAuth Authorization Code
- DPoP Proof·Client Certificate Private Key

OWASP Logging Cheat Sheet도 Access Token, Password, Database Connection String, Encryption Key와 주요 Secret을 직접 기록하지 말고 제거·Mask·Hash·암호화하도록 안내합니다.

## 23. Field 이름과 값 형태를 함께 검사한다

Structured Log (구조화 로그)에서는 민감 Field 이름을 먼저 차단합니다.

```json
{
  "eventType": "tool_call_completed",
  "credential": {
    "credentialId": "cred_opaque_id",
    "resource": "https://documents.example.com",
    "scopeSetId": "scope_documents_read",
    "status": "used"
  },
  "http": {
    "method": "GET",
    "statusCode": 200
  },
  "secretFieldsPresent": false
}
```

다음 Field는 재귀적으로 제거하거나 고정 문자열로 대체합니다.

```text
authorization
token
access_token
refresh_token
api_key
client_secret
password
cookie
private_key
connection_string
signature
```

하지만 공격자는 Secret을 `message`, `debug`, `payload` 같은 Field에 넣을 수 있습니다.

그래서 값 형태 Detector도 추가합니다.

- 알려진 Token Prefix
- JWT와 유사한 구조
- PEM Header
- Cloud·SaaS Key Pattern
- Credential이 포함된 URL Query
- 고엔트로피 문자열

형태 탐지는 오탐과 누락이 있으므로 원문 미기록 설계를 대체하지 않습니다.

## 24. Prompt·Trace·Error·Tool Result를 별도로 검사한다

일반 Application Log만 Masking하면 Agent 전용 저장소에 Secret이 남을 수 있습니다.

| 경로 | 확인할 내용 |
|---|---|
| Prompt Trace | System·User·Tool Message 안의 Credential |
| Model Output | Token·Key·Connection String 생성·반사 |
| Tool Input | 모델이 Secret Field를 추가했는지 |
| Tool Result | Downstream이 Header·Cookie·Debug 정보 반환 |
| Error | HTTP Client·SDK가 Request Header를 Dump |
| APM Span | URL Query·Header·Baggage·Attribute |
| Evaluation Dataset | 운영 Prompt와 Secret이 Fixture로 복사 |
| Support Export | 관리자 Download에 민감 Field 포함 |

Error Adapter는 Downstream 원문 Error를 모델에 그대로 반환하지 않습니다.

```text
내부 Error
  인증 Header·Host·Stack·SDK Detail 포함 가능
        ↓
Sanitize·Classify
        ↓
모델용 Error
  code = DOWNSTREAM_AUTH_FAILED
  retryable = false
  correlationId = err_opaque_id
```

운영자가 상세 원인을 볼 수 있는 보안 저장소와 모델·사용자에게 보여줄 Error를 분리합니다.

## 25. Secret 값 대신 Digest와 Metadata를 감사한다

감사 목적은 Token 원문을 복원하는 것이 아니라 다음 질문에 답하는 것입니다.

- 누가 발급을 요청했는가?
- 어떤 Actor와 Run이 사용했는가?
- 어느 Resource·Scope·객체를 위한 Credential인가?
- 언제 발급·사용·만료·폐기됐는가?
- 어떤 정책과 승인이 적용됐는가?
- 성공·거부·실패·재사용 시도가 있었는가?

Credential Audit Event 예시는 다음과 같습니다.

```json
{
  "eventType": "credential_issued",
  "credentialId": "cred_opaque_id",
  "credentialFingerprint": "sha256_fixture_digest",
  "subjectId": "usr_opaque_id",
  "actorId": "wld_tool_broker",
  "tenantId": "ten_opaque_id",
  "resource": "https://documents.example.com",
  "scopeSetId": "scope_documents_read",
  "intentId": "int_opaque_id",
  "policyVersion": "credential_policy_fixture_v1",
  "issuedAt": "2026-07-29T13:00:00Z",
  "expiresAt": "2026-07-29T13:05:00Z",
  "tokenValueLogged": false
}
```

Fingerprint는 조직이 관리하는 Key를 이용한 HMAC 등 목적에 맞는 방식으로 만들 수 있습니다.

단순 Hash는 Token의 Entropy와 접근 가능한 후보에 따라 위험할 수 있으므로 설계 검토가 필요합니다.

## 26. Secret 노출을 Source부터 Runtime까지 검사한다

Secret Detection (비밀정보 탐지)은 Repository 검사 하나로 끝나지 않습니다.

```text
개발자 입력
  → Source·Commit History
    → Build Log·Artifact·Container Layer
      → Deployment Manifest
        → Runtime Environment·Memory
          → Prompt·Tool·Trace
            → 중앙 Log·Backup·Support Export
```

단계별 검사를 연결합니다.

- Pre-commit·Pull Request Secret Scan
- Build Log와 Artifact 검사
- Image·Package·Infrastructure Template 검사
- 배포 전 Secret Reference 검증
- Runtime Egress·Log Detector
- Prompt·Tool Result DLP 검사
- 중앙 저장소 사후 탐지와 Alert
- 과거 Backup·Export 접근 통제

탐지된 Secret은 “파일에서 문자열 삭제”로 처리하지 않습니다.

이미 노출된 것으로 가정하고 폐기·회전·사용 이력 조사까지 수행합니다.

## 27. Credential 정책을 기계적으로 검사한다

Credential Policy Manifest (자격 증명 정책 명세)를 Version 관리하면 배포 전에 위험한 변경을 찾을 수 있습니다.

```json
{
  "policyId": "agent_credential_policy",
  "version": "credential_policy_fixture_v1",
  "defaults": {
    "decision": "deny",
    "tokenPassthrough": "forbidden",
    "rawSecretToModel": "forbidden",
    "rawSecretLogging": "forbidden",
    "queueTokenStorage": "forbidden"
  },
  "issuance": {
    "singleAudienceRequired": true,
    "minimumScopesRequired": true,
    "maxLifetimeSeconds": "POLICY_VALUE",
    "senderConstraint": "risk_based"
  },
  "storage": {
    "secretManagerRequired": true,
    "encryptionRequired": true,
    "cacheContextBindingRequired": true
  },
  "operations": {
    "rotationAutomated": true,
    "revocationSupported": true,
    "auditMetadataRequired": true
  }
}
```

CI Policy는 다음 변경을 차단하거나 보안 검토로 보냅니다.

- Token 수명 증가
- Wildcard Scope 추가
- Audience 다중화
- 새로운 Raw Secret 접근 Consumer
- Token Passthrough 허용
- Queue·Log·Trace 저장 허용
- Rotation·Revocation 비활성화
- Production에서 정적 관리자 Key 사용

## 28. Negative Test로 유출과 재사용을 검증한다

정상 Tool 호출만 성공하는지 확인하면 Credential 경계는 검증되지 않습니다.

| 시험 | 기대 결과 |
|---|---|
| 모델이 `authorization` 인자 추가 | Schema 거부·Credential 미발급 |
| 다른 Audience Token 사용 | Resource Server 거부 |
| 넓은 Scope 요청 | Broker 축소 또는 거부 |
| 만료 Token 재사용 | 거부·재발급 정책 적용 |
| 폐기된 Credential 사용 | 거부·보안 Event |
| 다른 Tenant의 Handle 사용 | 거부·Downstream 미호출 |
| Queue Message에 Token 삽입 | Producer·Consumer Validation 거부 |
| Tool Error에 Authorization Header 포함 | 모델·Log 전달 전 제거 |
| Presigned URL 전체 Logging | Query Signature 제거 |
| Prompt Injection으로 Secret 조회 | Tool 없음·Broker 거부 |
| Cache Key에서 Subject 제거 | 격리 Test 실패·배포 차단 |
| 이전 Key 회전 후 재사용 | 거부·사용 위치 Alert |
| Token만 탈취해 다른 Client에서 사용 | Sender Constraint 적용 경로에서 거부 |
| Broker 장애 중 쓰기 요청 | Fail Closed |

검증 시 “응답에 Secret이 보이지 않는다”만 보지 않습니다.

APM, Trace, Queue, Dead Letter Queue, Retry Log, Metric Label과 Support Export까지 검색합니다.

## 29. Credential 노출 사고 대응 절차를 준비한다

Secret이 노출됐을 가능성이 있으면 실제 악용 증거가 없더라도 대응을 시작합니다.

1. Credential 유형·Owner·Resource·Scope 확인
2. 노출 위치와 최초·최종 노출 시간 확인
3. Credential 즉시 폐기 또는 회전
4. 관련 Token·Session·Cache·Presigned URL 무효화
5. 발급 가능한 상위 Root Secret 노출 여부 확인
6. 사용 Log에서 비정상 Resource·Actor·위치·시간 조사
7. Queue·Prompt·Trace·Log·Backup의 복제본 식별
8. 노출된 값을 안전하게 제거하되 감사 무결성 보존
9. Downstream Side Effect와 데이터 접근 범위 확인
10. 탐지 규칙·정책·회귀 Test 보강

Root Secret이 노출됐다면 그 Secret으로 발급된 모든 하위 Credential과 서명된 Artifact의 신뢰도 검토해야 합니다.

회전 전에 새 Secret을 같은 취약한 경로에 다시 배포하면 사고가 반복됩니다.

## 30. 운영 전 체크리스트

### 구조·권한

- [ ] Model·Prompt·Generated Code에서 Credential 원문을 분리한다.
- [ ] Tool Broker와 Credential Broker의 책임을 정의한다.
- [ ] Secret Manager·STS·KMS·HSM의 역할을 구분한다.
- [ ] Workload Identity와 사용자 Delegation Context를 함께 검증한다.
- [ ] Tool 실행 직전에만 Credential을 획득·주입한다.
- [ ] Tool Input Schema에서 Secret Field와 추가 Field를 거부한다.

### Token·발급

- [ ] Downstream별 단일 Audience와 최소 Scope를 사용한다.
- [ ] Token Passthrough를 금지하고 교환·재발급한다.
- [ ] Subject·Actor·Client·Tenant·Purpose를 보존한다.
- [ ] 위험에 맞는 단기 수명과 재발급 정책이 있다.
- [ ] 고위험 연동에 Sender Constraint 적용을 검토한다.
- [ ] Refresh Token을 별도 강한 저장·회전·폐기 정책으로 보호한다.

### 저장·Queue·Cache

- [ ] 장기 Secret은 중앙 Secret Manager에 보관한다.
- [ ] 환경·Consumer·Resource별 Secret을 분리한다.
- [ ] Queue·Checkpoint·Memory에 Token 원문을 저장하지 않는다.
- [ ] 비동기 Step 실행 전 권한을 재검증하고 새 Token을 발급한다.
- [ ] Cache Key에 Subject·Actor·Tenant·Resource·Scope·정책 Version을 포함한다.
- [ ] Cache Hit에서도 만료·폐기·권한·승인을 다시 확인한다.

### Masking·감사

- [ ] Prompt·Tool·Error·Log·Trace·Metric에서 Secret을 제거한다.
- [ ] Header·Field 이름과 Secret 값 형태를 함께 검사한다.
- [ ] Presigned URL과 Query Signature를 직접 기록하지 않는다.
- [ ] Credential 원문 대신 ID·Fingerprint·Resource·Scope·수명만 감사한다.
- [ ] 발급·사용·거부·만료·폐기·재사용 시도를 기록한다.
- [ ] Log·Trace·Support Export의 조회 권한과 보존 정책을 제한한다.

### 운영·검증

- [ ] Rotation·Revocation을 자동화하고 실제 전환을 시험한다.
- [ ] Broker·Secret Manager 장애의 위험 등급별 Fail 정책이 있다.
- [ ] Source·Build·Artifact·Runtime·Prompt·Log에 Secret Scan을 적용한다.
- [ ] Credential 경계 Negative Test를 배포 Gate에서 실행한다.
- [ ] Kill Switch와 Credential 대량 폐기 절차가 있다.
- [ ] 노출 시 하위 Credential·Side Effect·복제 저장소를 조사한다.

## 마무리

AI Agent의 Credential 관리 원칙은 다음 흐름으로 정리할 수 있습니다.

```text
Model은 작업만 제안
  → Tool Broker가 인자·권한·승인 검증
    → Credential Broker가 사용자·Workload·목적 검증
      → Resource·Scope·수명이 좁은 Credential 발급
        → 실행 직전에 주입
          → Resource Server가 다시 검증
            → 결과에서 Secret 제거
              → Metadata만 감사
                → 만료·회전·폐기·탐지
```

핵심 원칙은 다음과 같습니다.

1. 모델과 생성 Code에 Credential을 노출하지 않습니다.
2. 하나의 장기 Secret을 여러 Tool·환경·Resource가 공유하지 않습니다.
3. Downstream마다 Audience·Scope·수명이 좁은 Credential을 사용합니다.
4. Token Passthrough 대신 검증된 Delegation Context로 교환·재발급합니다.
5. Queue에는 Token이 아니라 실행 시점에 재검증할 권한 문맥을 저장합니다.
6. Rotation, Revocation과 Sender Constraint로 도난 후 사용 범위를 줄입니다.
7. Prompt·Tool·Error·Trace·Log에 Secret이 생성되지 않게 하고 전 경로를 검사합니다.
8. 정상 발급보다 유출·오용·폐기·장애 시험을 운영 Gate로 사용합니다.

Credential 보안은 “Secret Manager를 도입했다”는 제품 선택으로 끝나지 않습니다.

**누가 어떤 사용자 의도를 대신해 어느 Resource에 어떤 권한으로 얼마나 짧게 접근했는지 설명할 수 있고, Credential 원문 없이도 그 실행을 감사·폐기·복구할 수 있어야 합니다.**

다음 글에서는 Multi-tenant RAG (멀티테넌트 검색 증강 생성)의 수집 단계부터 문서 ACL, Retrieval Filter, Chunk 권한, Index 격리와 삭제 전파를 연결하는 방법을 살펴보겠습니다.

## 참고 자료

- [MCP 2026-07-28: Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
- [MCP Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [MCP Client Best Practices](https://modelcontextprotocol.io/docs/develop/clients/client-best-practices)
- [MCP OAuth Client Credentials Extension](https://modelcontextprotocol.io/extensions/auth/oauth-client-credentials)
- [RFC 9700: Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700.html)
- [RFC 8693: OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693.html)
- [RFC 8707: Resource Indicators for OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707.html)
- [RFC 9449: OAuth 2.0 Demonstrating Proof of Possession](https://www.rfc-editor.org/rfc/rfc9449.html)
- [RFC 8705: OAuth 2.0 Mutual-TLS Client Authentication and Certificate-Bound Access Tokens](https://www.rfc-editor.org/rfc/rfc8705.html)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [NIST SP 800-207A: Zero Trust Architecture Model for Cloud-Native Applications](https://csrc.nist.gov/pubs/sp/800/207/a/final)
- [SPIFFE Concepts](https://spiffe.io/docs/latest/spiffe/concepts/)
- [SPIFFE Workload API](https://spiffe.io/docs/latest/spiffe-specs/spiffe_workload_api/)

---

> 이 글은 2026년 7월 29일 기준 MCP, IETF OAuth RFC, OWASP, NIST와 SPIFFE의 공식 공개 자료 및 공개 가능한 엔터프라이즈 AI Agent 보안 설계 경험을 바탕으로 작성했습니다. 예시 ID, Domain, Scope, 정책, 수명, Hash와 Credential Metadata는 설명용 Fixture이며 실제 Token·Secret·Account·내부 주소가 아닙니다. 실제 적용 시 Identity Provider, Cloud·Container Platform, Secret Manager, Downstream API, 데이터 분류, SLO, 관련 법규와 조직의 사고 대응 능력에 맞게 검토하고 발급·유출·회전·폐기·장애 시험으로 검증해야 합니다.
