# Tistory 기술자료 초안

- 문서 ID: `BLOG-05`
- 상태: 공개 완료
- 공개 URL: https://aiarchitect.tistory.com/5
- Tistory 상태: 공개 게시·공개 페이지 검증 완료
- 분류: `엔터프라이즈 아키텍처`
- 권장 제목: `기업용 AI 백엔드 설계: Java Security Gateway와 Python AI Orchestrator의 책임 분리`
- 검색 설명: `기업용 AI 백엔드에서 Java Security Gateway와 Python AI Orchestrator를 분리하는 기준, 내부 토큰 계약, REST·SSE·파일 전달 경계와 권한 재검증 원칙을 정리합니다.`
- 권장 태그: `엔터프라이즈 아키텍처`, `Java`, `Spring Boot`, `Python`, `FastAPI`, `AI Agent`, `Security Gateway`
- 권장 대표 이미지: `portfolio/architecture-diagrams/01-enterprise-ai-reference-architecture.svg`

---

# 기업용 AI 백엔드 설계: Java Security Gateway와 Python AI Orchestrator의 책임 분리

기업용 AI 서비스를 설계할 때 자주 나오는 질문이 있습니다.

> 기존 Java 백엔드 안에 AI 기능을 넣어야 할까, Python 서비스를 따로 만들어야 할까?

이 질문을 언어 선택 문제로만 보면 답을 찾기 어렵습니다. 중요한 것은 Java와 Python 중 어느 쪽이 더 좋은지가 아니라, **외부 요청을 통제하는 책임과 AI 실행을 조율하는 책임을 어디에서 나눌 것인가**입니다.

인증, 테넌트 정책과 기존 업무 API는 안정성과 일관성이 중요합니다. 반면 Agent, RAG, 모델 SDK와 Prompt는 상대적으로 빠르게 바뀝니다. 두 영역을 하나의 배포 단위에 넣으면 시작은 단순하지만, 시간이 지날수록 보안 변경과 AI 실험의 배포 주기가 서로 얽힐 수 있습니다.

책임을 분리한 기준 구조는 다음과 같습니다.

```text
Web · Mobile · Business Channel
                 │
                 ▼
      Java Security Gateway
  인증 · 테넌트 · 정책 · 요청 통제
                 │
       제한된 내부 실행 계약
                 │
                 ▼
      Python AI Orchestrator
  Agent · RAG · 모델 · 승인 · 재개
          │        │        │
          ▼        ▼        ▼
     Knowledge   MCP Tool   LLM·STT
       Search    Servers    Providers
```

이 구조는 모든 기업용 AI 시스템의 정답이 아닙니다. 다만 기존 Java 서비스와 Python AI 생태계를 함께 사용하고, 여러 채널과 업무 시스템을 하나의 보안 경계로 통제해야 할 때 유용한 출발점이 됩니다.

## 1. 경계는 프로그래밍 언어가 아니라 책임으로 나눈다

`Java는 보안`, `Python은 AI`처럼 언어만으로 역할을 정하면 책임이 쉽게 흐려집니다. 먼저 각 계층이 최종적으로 책임질 항목을 정의해야 합니다.

| 영역 | Java Security Gateway | Python AI Orchestrator |
|---|---|---|
| 외부 인증 | Access Token 검증과 인증 실패 응답 | 외부 Token을 직접 신뢰하지 않음 |
| 테넌트 | 요청 사용자의 조직 범위 확정 | 전달받은 범위 안에서 Workflow 실행 |
| API 정책 | Route, 요청 크기, 속도 제한, CORS | AI 입력 길이, 모델·Tool 실행 예산 |
| AI 실행 | 실행 요청 접수와 결과 중계 | Agent, RAG, Prompt, 모델 Adapter |
| 승인 | 사용자 승인 상태와 정책 입구 | Workflow 중단·재개와 승인 대상 보존 |
| 업무 변경 | 공개 API 계약과 1차 인가 | Tool 호출 계획과 결과 연결 |
| 최종 인가 | 요청 수준의 통제 | Tool Server와 업무 시스템이 대상별 재검증 |
| 관측성 | 외부 요청 ID와 인증 결과 | Workflow·모델·검색·Tool Span |

Gateway가 LLM Prompt를 이해하기 시작하거나, Orchestrator가 OAuth Callback과 외부 세션을 직접 처리하기 시작하면 분리 효과가 줄어듭니다. 각 계층이 상대 영역의 세부 구현보다 **안정된 계약**에 의존하도록 설계해야 합니다.

## 2. Security Gateway는 외부 요청의 신뢰 경계를 책임진다

Security Gateway는 단순한 Reverse Proxy가 아닙니다. 외부에서 들어온 요청을 내부 AI 실행이 사용할 수 있는 제한된 요청으로 바꾸는 정책 집행 지점입니다.

주요 책임은 다음과 같습니다.

1. Access Token의 서명과 `issuer`, `audience`, 만료 시각을 검증합니다.
2. 사용자와 테넌트, 역할과 Scope를 확인합니다.
3. 요청 경로, 본문 크기, 파일 형식과 속도 제한을 적용합니다.
4. 외부 Header를 그대로 통과시키지 않고 허용된 값만 정규화합니다.
5. 내부 서비스가 검증할 수 있는 짧은 수명의 실행 Context를 발급합니다.
6. 사용자 응답 규격, 오류 형식과 Stream 연결 정책을 유지합니다.
7. 요청 ID와 감사에 필요한 최소 정보를 기록합니다.

Spring Security Resource Server는 JWT 서명과 `exp`, `nbf`, `iss` 검증을 지원하고, 별도의 설정으로 `aud`도 검증할 수 있습니다. 여기서 중요한 점은 Framework 기능을 켜는 것보다 어떤 발급자와 대상 서비스의 Token만 신뢰할지 명시하는 것입니다.

Spring Cloud Gateway의 Token Relay는 인증된 사용자의 Access Token을 Downstream 요청에 전달할 수 있습니다. 하지만 모든 구조에서 외부 Token을 그대로 전달하는 것이 최선은 아닙니다. Downstream 서비스가 외부 발급자의 Token과 넓은 Scope를 알아야 하고, 원래 Token의 수명이 AI Workflow보다 길거나 짧을 수 있기 때문입니다.

내부 서비스에 더 좁은 권한과 Audience를 가진 Token이 필요하다면 OAuth 2.0 Token Exchange 같은 표준 방식을 검토할 수 있습니다. 자체 서명 Header를 임의로 만드는 방식보다 발급자, Audience, Scope, 만료와 위임 관계가 명확한 Token 계약이 안전합니다.

## 3. AI Orchestrator는 실행 순서와 상태를 책임진다

AI Orchestrator의 핵심 역할은 모델 API를 한 번 호출하는 것이 아닙니다. 사용자 요청을 여러 단계의 실행 계획으로 바꾸고, 검색·모델·Tool 호출의 상태를 연결하는 것입니다.

```text
요청 수신
  ↓
실행 Context 검증
  ↓
Workflow 생성 또는 재개
  ↓
RAG 검색 · 모델 호출 · Tool 후보 생성
  ↓
필요 시 사용자 승인 대기
  ↓
Tool Server 재인가 후 실행
  ↓
결과 구조화 · 출처 연결 · 상태 저장
```

Orchestrator가 담당할 항목은 다음과 같습니다.

- Agent 상태와 단계별 실행 순서
- Prompt와 모델 Adapter
- RAG 검색, 재정렬과 출처 연결
- MCP Tool 목록 선택과 입력·출력 검증
- 실행 시간, Token 사용량과 Tool 호출 횟수 예산
- 승인 대기, Checkpoint와 Workflow 재개
- 모델·검색·외부 API 오류의 분류와 재시도
- 사용자에게 전달할 진행 Event와 최종 결과

Python과 FastAPI는 비동기 API, AI SDK와 데이터 처리 Library를 조합하기 편리합니다. FastAPI는 `async def`와 `await`를 지원하고 문자열이나 Binary Chunk를 `StreamingResponse`로 보낼 수 있습니다.

하지만 CPU·GPU를 오래 점유하거나 여러 서버에서 처리해야 하는 작업을 Web Process의 간단한 Background Task에만 맡기면 복구와 확장이 어려워질 수 있습니다. FastAPI 공식 문서도 무거운 Background 계산은 별도 Process와 Queue를 사용하는 더 큰 도구가 적합할 수 있다고 안내합니다. 긴 AI Workflow는 상태 저장과 재실행이 가능한 Worker 구조로 분리하는 편이 안전합니다.

## 4. Java와 Python 사이에는 최소 실행 Context만 전달한다

Gateway가 인증했다고 해서 Orchestrator에 외부 Token 전체와 모든 사용자 정보를 넘길 필요는 없습니다. 내부 호출에 필요한 최소 정보만 구조화합니다.

예를 들면 다음과 같습니다.

```json
{
  "subject": "opaque-user-id",
  "tenant": "opaque-tenant-id",
  "audience": "ai-orchestrator",
  "scopes": [
    "ai.workflow.start",
    "knowledge.read"
  ],
  "policy": {
    "allowedToolGroups": [
      "meeting.read"
    ],
    "maxExecutionSeconds": 120
  },
  "requestId": "opaque-request-id",
  "issuedAt": 1785300000,
  "expiresAt": 1785300300
}
```

실제 내부 JWT라면 이 JSON 외에 다음 조건이 필요합니다.

- Gateway 또는 신뢰된 Authorization Server의 서명
- Orchestrator 전용 `audience`
- 짧은 만료 시간
- 재사용 범위를 제한하는 Scope
- Key 회전을 고려한 JWKS 검증
- Server 간 암호화 통신
- 필요한 경우 Token Exchange의 위임 관계

`X-User-Id`, `X-Tenant-Id` 같은 Header를 외부 요청에서 받아 그대로 신뢰하면 공격자가 값을 바꿀 수 있습니다. Gateway는 외부에서 들어온 동일 이름의 Header를 제거하고, 검증된 인증 결과로 내부 Context를 새로 구성해야 합니다. Orchestrator도 Gateway를 거쳤다는 네트워크 위치만 믿지 말고 내부 Token의 서명, Audience와 만료를 검증해야 합니다.

## 5. REST, SSE와 파일 전달은 서로 다른 계약으로 설계한다

AI 요청은 처리 시간이 짧은 조회, 수 분이 걸리는 Workflow, 대용량 파일처럼 성격이 다릅니다. 하나의 HTTP 요청 방식으로 모두 처리하려고 하면 Timeout과 재시도 정책이 불명확해집니다.

| 흐름 | 권장 계약 | 주의점 |
|---|---|---|
| 짧은 조회 | 동기 REST | 명확한 Timeout과 응답 크기 제한 |
| 긴 AI 작업 시작 | `POST` 후 `202 Accepted` | `workflowId`와 상태 조회 URL 반환 |
| 진행 상태·부분 결과 | SSE | Event ID, 재연결과 최종 상태 정의 |
| 사용자 승인 | 별도 REST 명령 | 승인 대상·버전·만료를 함께 확인 |
| 파일 업로드 | Streaming 또는 Upload Ticket | 크기·형식·무결성·악성 파일 검사 |
| 최종 결과 | 상태 조회 또는 완료 Event | 부분 출력과 확정 결과를 구분 |

SSE는 Server가 Web Page로 Event를 Push할 수 있는 단방향 연결입니다. AI 진행 상태와 Text Chunk 전달에 적합하지만, 사용자의 취소·승인·수정은 별도의 REST 요청으로 보내는 편이 계약을 명확하게 합니다.

Gateway는 Orchestrator의 Stream을 중계할 때 Provider 고유 Event를 그대로 외부에 노출하지 않아야 합니다. 공개 Event Type을 안정적으로 정의하고, 연결이 끊겼을 때 `Last-Event-ID` 또는 상태 조회로 복구할 수 있어야 합니다.

```text
event: workflow.progress
id: event-0042
data: {"workflowId":"opaque-workflow-id","stage":"retrieval","progress":40}

event: workflow.completed
id: event-0088
data: {"workflowId":"opaque-workflow-id","resultVersion":3}
```

대용량 파일은 JSON 안에 Base64로 넣어 Java와 Python을 반복 통과시키기보다, Gateway가 업로드 권한과 Metadata를 검증한 뒤 Object Storage나 격리된 저장소의 불투명 참조를 Orchestrator에 전달하는 방식이 효율적입니다. Orchestrator는 사용자가 제출한 로컬 경로나 임의 URL을 직접 읽지 않고, 승인된 저장소와 현재 Tenant 범위 안의 참조만 사용해야 합니다.

## 6. Gateway의 인증은 Tool 실행 권한을 대신하지 않는다

사용자가 Gateway를 통과했다는 사실은 로그인됐음을 의미할 뿐, 모든 데이터와 Tool을 사용할 수 있다는 뜻은 아닙니다.

권한 검사는 여러 경계에서 서로 다른 목적으로 수행합니다.

```text
Security Gateway
  └─ 이 사용자가 AI 기능에 접근할 수 있는가
      └─ AI Orchestrator
          └─ 이 Workflow에서 이 Tool 후보가 허용되는가
              └─ MCP Tool Server
                  └─ 이 사용자가 이 레코드에 이 작업을 할 수 있는가
                      └─ 업무 시스템
                          └─ 현재 상태에서 변경이 가능한가
```

Gateway는 Route와 기능 Scope 같은 비교적 거친 권한을 통제합니다. Orchestrator는 Workflow 정책과 Tool Group을 제한합니다. 최종 Tool Server와 업무 시스템은 대상 레코드, 현재 상태와 실제 사용자 권한을 실행 시점에 다시 검사합니다.

모델이 만든 Tool 인자, 검색 결과에 포함된 식별자, 이전 대화에서 확인한 권한은 현재 실행의 권한 증명이 아닙니다. 특히 삭제, 외부 전송, 결제와 상태 확정 같은 작업은 사용자의 명시적 승인과 실행 직전 재인가가 모두 필요합니다.

## 7. 비동기 상태와 오류를 공개 API 계약에 포함한다

긴 Workflow를 동기 요청 하나로 감추면 사용자는 작업이 진행 중인지 실패했는지 알기 어렵습니다. Gateway와 Orchestrator 사이의 응답에 최소한 다음 상태를 포함하는 것이 좋습니다.

```json
{
  "workflowId": "opaque-workflow-id",
  "status": "accepted",
  "statusUrl": "/ai/workflows/opaque-workflow-id",
  "streamUrl": "/ai/workflows/opaque-workflow-id/events",
  "requestId": "opaque-request-id"
}
```

상태는 시스템이 구분할 수 있는 값으로 관리합니다.

```text
ACCEPTED
RUNNING
WAITING_FOR_APPROVAL
COMPLETED
FAILED_RETRYABLE
FAILED_FINAL
CANCELED
```

HTTP Timeout이 발생했다고 Workflow까지 실패한 것은 아닐 수 있습니다. Client가 같은 요청을 다시 보낼 때 중복 Workflow가 생기지 않도록 `idempotencyKey`를 사용하고, 상태 조회와 취소 요청도 동일한 사용자·테넌트 범위에서 검증해야 합니다.

외부 오류 응답에는 사용자가 다음 행동을 결정할 수 있는 오류 코드와 `requestId`를 제공합니다. 내부 Stack Trace, Prompt 전체, Token, 모델 Provider의 민감한 오류 본문은 노출하지 않습니다.

## 8. 두 Runtime을 하나의 Trace로 연결한다

서비스를 분리하면 장애 원인을 찾기 어려워질 수 있습니다. Browser 요청, Java Gateway, Python Orchestrator, 검색, 모델과 Tool 호출을 하나의 Trace로 연결해야 합니다.

OpenTelemetry는 Context Propagation을 통해 서로 다른 Process에서 생성된 Span을 하나의 Trace로 조합할 수 있습니다. HTTP 경계에서는 표준 `traceparent`와 `tracestate`를 사용하고, 업무 추적을 위해 다음 식별자를 함께 관리할 수 있습니다.

- `requestId`: 외부 요청과 응답 연결
- `traceId`: 분산 호출 경로 연결
- `workflowId`: 장시간 AI 실행의 생명주기
- `idempotencyKey`: 중복 실행 방지
- `approvalId`: 승인 대상과 실행 연결
- `toolCallId`: Tool 요청과 결과 연결

단, Trace와 Log가 새로운 정보 유출 경로가 되지 않도록 해야 합니다. Access Token, 원본 Prompt, 전체 검색 문서, 파일 내용과 개인 식별정보를 기본 로그에 남기지 않고, 필요한 값은 Masking하거나 불투명 식별자로 기록합니다.

## 9. 분리 구조의 이점만큼 비용도 계산한다

Java Gateway와 Python Orchestrator를 분리하면 다음 이점이 있습니다.

- 보안 정책과 AI Library의 배포 주기를 분리할 수 있습니다.
- 인증·테넌트 정책을 여러 AI 기능에 일관되게 적용할 수 있습니다.
- Gateway는 외부 요청, Orchestrator는 AI 작업 특성에 맞게 확장할 수 있습니다.
- 모델, RAG와 Tool Adapter를 기존 업무 API에서 분리할 수 있습니다.
- AI Workflow 실패가 전체 인증 서비스로 확산되는 범위를 줄일 수 있습니다.

하지만 서비스가 하나 더 생기므로 비용도 늘어납니다.

- 네트워크 Hop과 직렬화 비용
- 내부 인증서·Token과 Secret 수명주기
- REST·SSE·파일 계약의 버전 관리
- 분산 Trace와 장애 분석
- 부분 실패, Timeout과 재시도 조합
- Java와 Python의 배포·운영 역량

분리의 효과를 유지하려면 API Schema와 고정 Fixture를 이용한 계약 테스트가 필요합니다. 필드 추가·삭제, Enum 변경, 오류 코드와 SSE Event 순서가 두 Runtime에서 같은 의미로 처리되는지 CI에서 확인해야 합니다.

## 10. 처음부터 분리하지 않아도 되는 경우

다음 조건에서는 하나의 서비스로 시작하는 편이 합리적일 수 있습니다.

- 사용자와 기능이 제한된 내부 검증 단계
- 외부 인증과 복잡한 테넌트 정책이 없는 경우
- AI 호출이 짧은 동기 작업 하나인 경우
- 운영팀이 두 Runtime과 분산 시스템을 관리하기 어려운 경우
- 독립 확장과 배포 주기가 아직 필요하지 않은 경우

이 경우에도 인증, AI 실행, 업무 Adapter를 Module 수준에서 분리해 두면 이후 서비스 경계를 옮기기 쉽습니다.

반대로 다음 신호가 반복되면 물리적 분리를 검토할 시점입니다.

- AI Library 변경 때문에 핵심 업무 Backend를 자주 재배포합니다.
- 여러 채널이 각자 다른 방식으로 인증과 모델을 호출합니다.
- 긴 AI 작업이 일반 API의 Thread와 Connection을 점유합니다.
- GPU·모델·검색 작업과 업무 API의 확장 기준이 다릅니다.
- 쓰기 Tool의 승인과 감사 정책이 여러 곳에 흩어집니다.
- AI 장애가 로그인과 핵심 업무 API까지 영향을 줍니다.

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| 책임 | Gateway와 Orchestrator의 최종 책임자가 명확한가 |
| 외부 인증 | 서명, 발급자, 대상, 만료와 Scope를 검증하는가 |
| 내부 신뢰 | 내부 호출도 서명된 짧은 수명의 Context를 검증하는가 |
| Header | 외부 사용자가 내부 사용자·테넌트 Header를 주입할 수 없는가 |
| 권한 | Gateway 이후 Tool Server가 대상 레코드 권한을 재검증하는가 |
| 승인 | 위험 작업의 대상·버전·영향을 확인한 뒤 실행하는가 |
| REST | 동기 조회와 비동기 Workflow 시작이 구분돼 있는가 |
| SSE | Event ID, 재연결, 완료와 오류 상태가 정의돼 있는가 |
| 파일 | 크기·형식·무결성·보관·삭제 정책이 있는가 |
| 재시도 | Timeout 후 중복 실행을 막는 멱등성 기준이 있는가 |
| 계약 | Java와 Python 사이 Schema·오류·Event 계약을 테스트하는가 |
| 관측성 | 요청부터 모델·Tool까지 Trace를 연결할 수 있는가 |
| 로그 | Token·Prompt·문서·개인정보를 과도하게 기록하지 않는가 |
| 장애 격리 | Orchestrator 장애가 인증·핵심 API로 확산되지 않는가 |
| 운영 비용 | 두 Runtime과 분산 호출의 복잡성을 감당할 수 있는가 |

## 마무리

Java Security Gateway와 Python AI Orchestrator의 분리는 기술 취향이 아니라 **변화 속도와 신뢰 경계를 다루는 아키텍처 결정**입니다.

좋은 분리 구조는 다음 원칙을 지킵니다.

1. Gateway는 외부 인증, 테넌트와 요청 정책을 책임집니다.
2. Orchestrator는 Agent, RAG, 모델과 Workflow 상태를 책임집니다.
3. 두 서비스는 서명된 최소 실행 Context와 안정된 API 계약으로 연결됩니다.
4. Gateway 인증 이후에도 Tool Server와 업무 시스템이 최종 권한을 재검증합니다.
5. 긴 작업은 REST 시작, 상태 조회와 SSE Event로 분리합니다.
6. 요청·Workflow·Tool 실행을 하나의 Trace로 연결합니다.
7. 분리 비용이 이점보다 크다면 Module 경계부터 시작합니다.

핵심은 Java와 Python 중 하나를 선택하는 것이 아닙니다. 안정적으로 통제해야 하는 영역과 빠르게 진화하는 AI 실행 영역을 분리하고, 그 사이의 권한·상태·오류·관측성 계약을 명확하게 만드는 것입니다.

다음 글에서는 브라우저 WebRTC 연결이 실패할 때 ICE Candidate, mDNS, NAT와 TURN을 어떤 순서로 확인해야 하는지 살펴보겠습니다.

---

## 참고 자료

- [Spring Security OAuth 2.0 Resource Server JWT](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html)
- [Spring Cloud Gateway Token Relay](https://docs.spring.io/spring-cloud-gateway/docs/current/reference/html/index.html#the-tokenrelay-gatewayfilter-factory)
- [Spring Cloud Gateway RequestRateLimiter](https://docs.spring.io/spring-cloud-gateway/reference/spring-cloud-gateway-server-webflux/gatewayfilter-factories/requestratelimiter-factory.html)
- [FastAPI Concurrency and async/await](https://fastapi.tiangolo.com/async/)
- [FastAPI Stream Data](https://fastapi.tiangolo.com/advanced/stream-data/)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [RFC 8693 — OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/rfc8693/)
- [WHATWG HTML — Server-sent events](https://html.spec.whatwg.org/dev/server-sent-events.html)
- [OpenTelemetry Traces and Context Propagation](https://opentelemetry.io/docs/concepts/signals/traces/)

> 이 글은 2026년 7월 29일 기준 공개된 공식 문서와 공개 가능한 개발·상용화 검증 경험을 바탕으로 작성했습니다. 실제 구현에서는 조직의 인증 체계, 데이터 보안 등급, 운영 인력과 사용 중인 Framework 버전을 함께 확인해야 합니다.
