# Tistory 기술자료 초안

- 문서 ID: `BLOG-22`
- 상태: 공개 완료
- Tistory 상태: 2026-07-30 공개 게시 및 공개 페이지 검증 완료
- 분류: `보안`
- 공개 URL: `https://aiarchitect.tistory.com/22`
- 권장 제목: `MCP Server 보안 체크리스트: OAuth·Scope·Origin·SSRF·Rate Limit`
- 검색 설명: `원격 MCP Server를 운영할 때 OAuth Token과 Audience, 최소 Scope, Origin과 DNS Rebinding, SSRF, Tool별 Rate Limit 및 상태 핸들 인가를 배포 전 시험 항목으로 정리합니다.`
- 권장 태그: `MCP 보안`, `MCP Server`, `OAuth 2.1`, `SSRF`, `Rate Limit`, `Origin`, `API Security`, `AI Agent 보안`
- 권장 대표 이미지: `portfolio/architecture-diagrams/04-mcp-enterprise-integration.svg`

---

# MCP Server 보안 체크리스트: OAuth·Scope·Origin·SSRF·Rate Limit

MCP Server가 `tools/list`와 `tools/call`에 정상 응답한다고 운영 준비가 끝난 것은 아닙니다.

원격 MCP Server는 AI Client와 기업 시스템 사이에서 다음 기능을 수행할 수 있습니다.

```text
사용자 대신 데이터 조회
문서·파일 다운로드
업무 객체 생성·변경
외부 시스템 호출
장시간 Workflow 실행
```

이 경계가 약하면 정상적인 Tool Call과 공격 요청이 같은 경로로 들어옵니다.

```text
유효하지 않은 Token
다른 Resource용 Token
과도한 Scope
다른 사용자의 객체 ID
악성 웹페이지의 Local Server 호출
내부 주소를 향한 URL Fetch
고비용 Tool의 반복·병렬 호출
```

MCP 보안은 “OAuth를 붙였다”는 한 문장으로 완성되지 않습니다.

다음 통제가 하나의 실행 경로에서 연결돼야 합니다.

```text
TLS·Origin
  → Token 검증
    → Scope
      → 사용자·Tenant·객체 인가
        → Tool 입력 검증
          → Egress·SSRF 통제
            → Rate·Concurrency·Cost 제한
              → 감사·탐지·복구
```

이 글은 MCP OAuth의 전체 인증 흐름을 다시 설명하기보다, **MCP Server 운영자가 배포 전에 확인할 설정·코드·실패 시험**을 정리합니다.

## 1. 기준 사양과 배포 유형을 먼저 고정한다

이 글은 2026년 7월 28일 공개된 MCP 사양을 기준으로 합니다.

이 버전의 Streamable HTTP는 다음 특징을 가집니다.

- 하나의 MCP Endpoint가 HTTP POST를 받음
- JSON-RPC 요청마다 새로운 HTTP POST 사용
- 응답은 JSON 객체 또는 요청 범위의 SSE Stream
- Protocol-level Session (프로토콜 수준 세션) 제거
- 요청 Metadata를 Body와 HTTP Header에 함께 전달 가능
- Header와 Body의 중요 값이 다르면 Server가 거부

보안 설계를 시작할 때 배포 유형을 구분합니다.

| 구분 | 로컬 `stdio` | 원격 Streamable HTTP |
|---|---|---|
| 실행 | Client가 Child Process 실행 | 독립 Server |
| 주요 경계 | OS 사용자·Process | Internet·Gateway·Server |
| Credential | 환경·Host의 안전한 저장소 | 요청별 Access Token |
| Origin 위험 | 일반적으로 해당 없음 | Browser·DNS Rebinding 고려 |
| Rate Limit | Process 자원 제한 중심 | 사용자·Client·Tool·비용 제한 |

MCP Authorization 사양은 Authorization 자체를 선택 사항으로 정의합니다.

그러나 사용자별 비공개 데이터, 기업 시스템과 쓰기 Tool을 인터넷 또는 공유 Network에 노출하는 Server라면 “선택 사항”이라는 문장을 무인증 허용으로 해석하면 안 됩니다.

업무 위험에 맞는 인증·인가가 필요합니다.

## 2. 먼저 신뢰 경계를 그린다

MCP Server를 단일 Box로 보면 통제가 빠집니다.

```text
MCP Client
  → CDN·WAF
    → Load Balancer·API Gateway
      → MCP Transport
        → Tool Router
          → Business Service
            → Database·Storage

                         └→ External API·URL Fetch
```

각 경계의 질문이 다릅니다.

| 경계 | 확인할 질문 |
|---|---|
| CDN·WAF | 비정상 Traffic과 큰 Payload를 줄이는가? |
| Gateway | TLS, Origin, 인증 Header와 기본 Rate를 처리하는가? |
| MCP Transport | Protocol Version, JSON-RPC와 Header·Body를 검증하는가? |
| Tool Router | Tool이 등록됐고 현재 Principal에게 허용됐는가? |
| Business Service | Tenant·객체·업무 상태 인가를 다시 수행하는가? |
| Egress | 허용된 목적지와 Protocol로만 나가는가? |
| Data Store | 최종 Tenant 격리와 최소 권한을 적용하는가? |

Gateway에서 Token을 확인했다고 MCP Server와 업무 Service가 인가를 생략하면 안 됩니다.

## 3. 기본 정책은 Deny by Default다

Deny by Default (기본 거부)는 알려진 허용 조건이 모두 충족된 요청만 실행하는 원칙입니다.

```text
등록되지 않은 Client
알 수 없는 Origin
지원하지 않는 Protocol Version
검증되지 않은 Token
알 수 없는 Tool
정의되지 않은 Scope
권한이 없는 객체
허용되지 않은 Egress
한도를 초과한 실행
  → 기본 거부
```

다음과 같은 편의 기능은 운영 기본값으로 두지 않습니다.

- 개발용 무인증 Mode 자동 활성화
- 모든 Origin 허용
- Scope 누락 시 전체 권한 부여
- 알 수 없는 Tool을 동적 Import
- URL Scheme 제한 없이 Fetch
- Rate Limit 저장소 장애 시 무제한 실행
- 인증 실패 시 상세 Token Claim 반환

개발 예외가 필요하다면 Profile, Network와 Credential을 운영에서 분리하고 시작 Log에 명확하게 표시합니다.

## 4. TLS와 Reverse Proxy 경계를 확인한다

원격 MCP Endpoint는 HTTPS로 보호합니다.

TLS가 Load Balancer에서 종료된다면 MCP Server는 다음을 알아야 합니다.

- 어느 Proxy가 신뢰할 수 있는가
- 원래 Scheme과 Host를 어떤 Header로 전달하는가
- 외부 Client가 같은 Header를 위조할 수 없는가
- Canonical MCP Resource URI를 어떻게 계산하는가
- Redirect·Metadata URL이 외부 주소와 일치하는가

모든 `Forwarded` 또는 `X-Forwarded-*` 값을 신뢰하면 외부 사용자가 Host와 Scheme을 바꿔 잘못된 Resource Metadata 또는 Redirect를 만들 수 있습니다.

```text
Internet 요청의 전달 Header 제거
  → 신뢰 Proxy가 검증된 값으로 다시 설정
    → Application은 지정된 Proxy에서 온 값만 사용
```

Health Check와 Metrics Endpoint는 MCP Endpoint와 분리하고 민감한 설정, Tool 목록과 Build 정보를 과도하게 노출하지 않습니다.

## 5. Origin 검증은 CORS 설정과 다르다

2026-07-28 MCP Streamable HTTP 사양은 들어오는 연결의 `Origin` Header를 검증하도록 요구합니다.

목적은 DNS Rebinding (DNS 재결속) 공격을 줄이는 것입니다.

악성 웹페이지가 사용자의 Browser를 이용해 Local 또는 내부 MCP Server에 요청을 보내는 상황을 생각해 볼 수 있습니다.

```text
악성 Website
  → 사용자의 Browser
    → Local·내부 MCP Endpoint
      → Tool 실행
```

Origin은 `scheme://host:port`의 정확한 조합입니다.

다음 세 주소는 서로 다른 Origin입니다.

```text
https://client.example.com
https://client.example.com:8443
http://client.example.com
```

검증 규칙은 다음처럼 구성합니다.

- 허용 Origin을 정확한 문자열 목록으로 관리
- Scheme, Host와 Port를 모두 비교
- `*` Wildcard를 Credential 요청에 사용하지 않음
- `null` Origin의 허용 여부를 명시적으로 결정
- 여러 값이나 비정상 형식을 거부
- `Origin`이 존재하지만 허용 목록과 다르면 HTTP 403
- 변경은 Code Review와 배포 이력에 기록

CORS (교차 출처 리소스 공유)는 Browser가 응답을 읽을 수 있는지를 제어하는 Mechanism입니다.

MCP의 Origin 검증은 Server가 요청 자체를 허용할지 결정하는 통제입니다.

```text
Access-Control-Allow-Origin 설정
≠ MCP 요청 Origin 인가
≠ 사용자 인증
```

일반적인 Server-to-Server Client는 `Origin`을 보내지 않을 수 있습니다.

그래서 Header 부재 정책은 배포 유형에 맞게 정합니다. Browser Client만 허용하는 Endpoint라면 요구할 수 있고, 비Browser Client도 사용하는 Endpoint라면 Token과 Client 정책으로 별도 통제합니다.

## 6. Local Server는 Loopback에만 Binding한다

Local Streamable HTTP Server가 모든 Network Interface에 Binding되면 같은 Network의 다른 장치가 접근할 수 있습니다.

MCP 사양은 Local Server가 Loopback Interface에만 Binding하도록 권고합니다.

```text
개발 편의를 위한 전체 Interface Binding
  → 같은 LAN에서 접근 가능
  → Firewall·Router 설정에 따라 외부 노출
```

확인할 항목은 다음과 같습니다.

- Local Mode의 기본 Binding이 Loopback인가?
- Remote Mode는 별도 Profile과 인증을 요구하는가?
- Container Port가 의도치 않게 Host 전체에 Publish되지 않는가?
- Service Discovery에 Local 관리 Endpoint가 등록되지 않는가?
- DNS Rebinding 방지를 위해 Origin도 검사하는가?

Loopback Binding만으로 인증이 완성되는 것은 아닙니다.

Browser를 통한 DNS Rebinding과 Local Process의 접근을 고려해야 합니다.

## 7. Protected Resource Metadata를 정확히 게시한다

보호된 MCP Server는 OAuth 2.0 Protected Resource Metadata (보호 리소스 메타데이터)를 제공합니다.

설명용 예시는 다음과 같습니다.

```json
{
  "resource": "https://mcp.example.com/mcp",
  "authorization_servers": [
    "https://auth.example.com"
  ],
  "scopes_supported": [
    "meeting:read"
  ],
  "bearer_methods_supported": [
    "header"
  ]
}
```

확인할 항목은 다음과 같습니다.

- `resource`가 실제 Canonical MCP URI와 일치하는가?
- HTTPS를 사용하는가?
- 승인된 Authorization Server만 포함하는가?
- 기본 기능에 필요한 최소 Scope만 공개하는가?
- 운영·검증 환경 Metadata가 섞이지 않는가?
- Cache 갱신과 변경 Rollout이 계획돼 있는가?

`scopes_supported`는 Client가 모두 요청해야 하는 권한 목록이 아닙니다.

RFC 9728과 MCP 사양은 현재 작업에 필요한 최소 Scope를 선택하도록 안내합니다.

## 8. Token을 매 요청 독립적으로 검증한다

MCP Server는 OAuth Resource Server (리소스 서버)입니다.

Access Token 검증에는 다음 항목이 포함됩니다.

| 항목 | 확인 내용 |
|---|---|
| Signature | 신뢰하는 Key와 Algorithm으로 서명됐는가? |
| Issuer | 신뢰하는 Authorization Server가 발급했는가? |
| Audience·Resource | 이 MCP Server를 위해 발급됐는가? |
| Expiration | 만료되지 않았는가? |
| Not Before | 아직 사용할 수 없는 Token이 아닌가? |
| Scope | 현재 Tool 작업에 필요한 권한이 있는가? |
| Revocation·Status | 조직 정책상 폐기 여부를 확인해야 하는가? |
| Subject·Client | 사용자와 호출 Client를 식별할 수 있는가? |

Streamable HTTP 요청마다 `Authorization` Header를 검증합니다.

이전 요청이 인증됐다는 사실, 같은 TCP 연결이라는 사실과 과거 Handle을 알고 있다는 사실은 현재 요청의 인증 증거가 아닙니다.

```text
Connection 재사용
≠ 인증 재사용 허용

State Handle 보유
≠ 사용자 권한
```

Token이 없거나 유효하지 않거나 만료됐다면 HTTP 401을 반환합니다.

## 9. Audience 검증과 Token Passthrough를 분리한다

Token Passthrough (토큰 전달)는 MCP Client가 준 Token을 MCP Server가 자신의 Token인지 확인하지 않고 Downstream API로 그대로 넘기는 구조입니다.

2026-07-28 MCP Authorization 사양은 다음을 요구합니다.

```text
MCP Server
  → 자신을 위해 발급된 Token만 수락
  → 다른 Token을 수락하거나 전달하지 않음
```

잘못된 구조는 다음과 같습니다.

```text
Client Token for Service A
  → MCP Server가 Audience 미검증
    → Service B에 그대로 전달
```

Downstream 호출이 필요하면 다음 중 조직의 위임 모델에 맞는 방식을 사용합니다.

- MCP Server의 제한된 Service Credential
- 검증된 사용자 Context와 Server Credential 조합
- OAuth Token Exchange (토큰 교환)
- Downstream 전용 Audience와 최소 Scope를 가진 Token

어떤 방식을 사용하든 Subject (사용자), Actor (MCP Server)와 대상 Resource를 감사할 수 있어야 합니다.

## 10. Scope는 Tool Catalog가 아니라 작업 Capability다

다음 Scope는 단순하지만 지나치게 넓습니다.

```text
mcp:full-access
admin
all
*
```

권장 구조는 업무 Capability (수행 능력)를 표현합니다.

```text
meeting:read
meeting:create
meeting:transfer
meeting:delete
summary:generate
```

Scope 설계 원칙은 다음과 같습니다.

- 읽기와 쓰기를 분리
- 일반 쓰기와 파괴 작업 분리
- 서로 관련 없는 Domain 권한 분리
- 기본 Scope는 저위험 읽기 중심
- 필요한 시점에 Step-up Authorization (단계적 권한 상승)
- Scope 의미가 바뀌면 Version과 Migration 관리
- Wildcard·Omnibus Scope 사용 억제

`tools/list`에 Tool이 보인다는 사실과 그 Tool을 실행할 권한은 다릅니다.

목록은 UX를 위해 Filter할 수 있지만 `tools/call` 시점에 실제 Scope와 업무 권한을 다시 검사해야 합니다.

## 11. 401과 403을 구분하고 최소 Scope만 Challenge한다

오류 의미를 정확히 구분합니다.

| 상태 | 의미 | Server 동작 |
|---|---|---|
| 401 Unauthorized | Token 없음·만료·유효하지 않음 | 인증 Metadata와 Challenge 제공 |
| 403 Forbidden | Token은 유효하지만 Scope·업무 권한 부족 | 필요한 최소 Scope 또는 거부 이유 |
| 400 Bad Request | 인증 요청·Protocol 형식 오류 | 안전한 Validation 오류 |

Scope가 부족할 때의 설명용 응답은 다음과 같습니다.

```http
HTTP/1.1 403 Forbidden
WWW-Authenticate: Bearer
  error="insufficient_scope",
  scope="meeting:transfer",
  resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"
```

전체 Scope Catalog를 매번 반환하지 않습니다.

현재 작업에 필요한 Scope를 한 번에 제시하고, Client의 무한 Step-up 반복을 막기 위해 재인가 재시도 횟수도 제한합니다.

## 12. Scope 이후에 객체·Tenant 인가를 다시 수행한다

Scope는 “회의 읽기 기능을 사용할 수 있다”는 Capability입니다.

다음 권한까지 자동으로 증명하지 않습니다.

```text
meeting:read Scope
≠ 모든 Tenant 회의 읽기
≠ 모든 Group 회의 읽기
≠ 입력한 임의 meetingId 읽기
```

Tool 실행 허용은 다음 교집합입니다.

```text
유효한 Token
∩ 현재 Tool Scope
∩ Tenant Membership
∩ 객체 접근 권한
∩ 업무 상태 조건
∩ 필요한 경우 Action Approval
```

Tool 인자의 `tenantId`, `userId`, `meetingId`를 신뢰하지 않습니다.

Tenant는 검증된 인증 Context에서 확정하고, 객체는 현재 Principal이 수행하려는 Action에 대해 Server 측에서 조회·인가합니다.

OWASP BOLA (객체 수준 인가 실패) 지침도 Client가 전달한 객체 ID를 사용하는 모든 기능에서 로그인 사용자의 해당 작업 권한을 확인하도록 권고합니다.

## 13. 2026-07-28 사양에서는 암묵적 Session을 기대하지 않는다

2026-07-28 Streamable HTTP에는 Protocol-level Session이 없습니다.

여러 요청에 걸친 상태가 필요하면 Server가 명시적 State Handle (상태 핸들)을 발급할 수 있습니다.

```json
{
  "workflowHandle": "workflow_fixture_022",
  "expiresAt": "2026-07-29T12:00:00Z",
  "nextAllowedActions": [
    "review",
    "cancel"
  ]
}
```

Handle은 이름이지 권한이 아닙니다.

Server 저장소에서는 다음 Context와 결속합니다.

```text
Handle
  + Subject
  + Tenant
  + Client
  + Workflow Type
  + Expiration
  + Current State
```

매 호출에서 Token의 Subject와 Handle Owner를 비교하고, Tenant·Action·만료·상태를 다시 확인합니다.

충분히 추측하기 어려운 불투명 식별자를 사용하더라도 인가 검사는 생략하지 않습니다.

## 14. Tool 입력은 JSON Schema 이후에도 검증한다

MCP Tool의 `inputSchema`는 중요한 첫 번째 경계입니다.

```json
{
  "name": "meeting.search",
  "inputSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "keyword": {
        "type": "string",
        "minLength": 1,
        "maxLength": 200
      },
      "limit": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50
      }
    },
    "required": [
      "keyword"
    ]
  }
}
```

Schema 이후에도 업무 Validation이 필요합니다.

- 문자열 길이·배열 개수·중첩 깊이
- 날짜·시간 범위
- Page Size와 Result Size
- 허용 File 유형·크기
- URL Scheme·Host
- SQL·Path·Command 같은 위험 입력
- 현재 사용자의 업무 상태
- 중복 실행과 Idempotency Key

2026-07-28 MCP Tool 사양은 Server가 Tool 입력을 검증하고 접근 통제와 Rate Limit을 구현하며 Tool 출력을 정제하도록 요구합니다.

외부 `$ref`를 자동으로 가져오지 않고 Schema 깊이와 검증 시간을 제한합니다.

## 15. Header와 Body가 다르면 요청을 거부한다

2026-07-28 Streamable HTTP는 일부 MCP Metadata와 Tool 인자를 HTTP Header에 Mirror할 수 있습니다.

이때 Proxy는 Header로 Routing하고 Server는 Body로 실행하면 해석 차이가 생길 수 있습니다.

```text
Header: low-risk Tool
Body: destructive Tool
```

Server가 Body를 처리한다면 다음 값을 비교합니다.

- `Mcp-Method`
- `Mcp-Name`
- Schema에서 `x-mcp-header`로 지정한 인자
- Body의 대응 Method·Name·Argument

불일치하면 HTTP 400과 `HeaderMismatch` JSON-RPC 오류로 거부합니다.

Header 이름은 대소문자를 구분하지 않지만 Method·Tool 이름과 같은 값은 사양에 따라 정확하게 비교합니다.

Rate Limit과 Authorization을 적용하는 Gateway도 Header만 보고 최종 실행 권한을 결정하지 않습니다.

## 16. Tool Output도 신뢰하지 않는 데이터다

Downstream API와 Database 응답이 안전하다고 가정하지 않습니다.

Tool 출력에는 다음 정보가 섞일 수 있습니다.

- Access Token·Cookie·API Key
- 내부 URL·Host·Stack Trace
- 다른 Tenant의 Field
- 불필요한 개인정보
- Prompt Injection 문자열
- 과도하게 큰 Payload
- HTML·Script·제어 문자

Server는 최소 Field만 Projection (선별)하고 `outputSchema`를 검증합니다.

```text
Downstream 원본
  → Tenant·Field 권한 Filter
    → Secret·PII Masking
      → 크기 제한
        → Output Schema 검증
          → MCP Tool Result
```

Error에도 내부 Stack, SQL, Token Claim 전체와 Downstream 응답 원문을 넣지 않습니다.

## 17. SSRF 진입점을 먼저 목록화한다

SSRF (Server-Side Request Forgery, 서버 측 요청 위조)는 공격자가 Server 또는 Server-side Client로 하여금 의도하지 않은 주소에 요청하도록 만드는 공격입니다.

MCP 환경의 진입점은 하나가 아닙니다.

- URL을 가져오는 Tool
- Webhook·Callback 등록 Tool
- 외부 File Import
- Image·Document Preview
- OAuth Protected Resource Metadata 조회
- Authorization Server Metadata 조회
- Client ID Metadata Document 조회
- Redirect 자동 추적

MCP 공식 보안 지침은 OAuth Discovery URL이 내부 Network, Cloud Metadata, Loopback 또는 Redirect Chain을 향할 수 있는 위험을 설명합니다.

순수 MCP Resource Server는 Client처럼 OAuth Metadata를 가져오지 않을 수 있습니다.

하지만 하나의 Application이 MCP Server, OAuth Proxy 또는 Authorization Server 역할을 함께 하거나 URL Fetch Tool을 제공한다면 같은 SSRF 통제가 필요합니다.

## 18. URL 문자열 검사만으로 SSRF를 막지 않는다

다음 검사는 충분하지 않습니다.

```text
문자열에 "localhost"가 없으면 허용
문자열이 "https://"로 시작하면 허용
처음 DNS 결과가 Public이면 허용
첫 Redirect URL만 검사
```

권장 Validation Pipeline은 다음과 같습니다.

```text
URL Parse
  → 허용 Scheme 확인
    → Userinfo·Fragment·비정상 Port 거부
      → Host Allowlist 또는 정책 확인
        → DNS Resolution
          → Private·Loopback·Link-local·Reserved 목적지 거부
            → Egress Policy 적용
              → Redirect마다 다시 검증
                → Timeout·크기·Content Type 제한
```

추가 원칙은 다음과 같습니다.

- 가능하면 목적지 Allowlist 사용
- Production OAuth URL은 HTTPS만 허용
- 자동 Redirect를 끄거나 각 Hop을 재검증
- DNS 검증과 실제 연결 사이 TOCTOU를 고려
- 표준 IP·URL Parser 사용
- IPv4·IPv6·Encoding 우회 처리
- Egress Proxy와 Network Policy로 2차 차단
- 내부 응답을 Error에 반사하지 않음

Application 검사와 Network Egress 통제를 함께 사용합니다.

## 19. Tool마다 Egress Capability를 선언한다

모든 Tool이 인터넷에 접근할 이유는 없습니다.

| Tool 유형 | Egress 정책 예시 |
|---|---|
| Database 조회 | Database Network만 허용 |
| 사내 API | 승인된 Service Host만 허용 |
| 공개 Web 검색 | 전용 Egress Proxy 사용 |
| File Import | 승인 Storage·Scanner 경유 |
| Webhook 등록 | 검증된 Domain·Port만 허용 |
| 내부 계산 | Network 접근 금지 |

Tool 실행 Process의 Network 권한을 분리하면 Prompt 또는 입력 검증이 실패해도 피해 범위를 줄일 수 있습니다.

DNS, Proxy와 Firewall Log를 Tool Call ID와 연결하되 민감 Payload 전체를 기록하지 않습니다.

## 20. Rate Limit은 요청 횟수 하나가 아니다

일반적인 분당 요청 수 제한만으로 비싼 Tool의 자원 소모를 제어할 수 없습니다.

다음 Dimension (차원)을 함께 봅니다.

- Source IP
- 인증 Subject
- OAuth Client
- Tenant
- Tool·Action
- 동시 실행 수
- 입력·출력 크기
- CPU·Memory·실행 시간
- Downstream 호출 수
- Model Token·음성 시간
- 일·월 Budget

설명용 정책은 다음과 같습니다.

```json
{
  "policyId": "mcp-rate-policy-fixture-022",
  "dimensions": [
    "subject",
    "client",
    "tenant",
    "tool"
  ],
  "classes": {
    "READ_LIGHT": {
      "requestLimit": "higher",
      "concurrencyLimit": "moderate"
    },
    "WRITE": {
      "requestLimit": "lower",
      "concurrencyLimit": "low"
    },
    "EXPENSIVE": {
      "requestLimit": "strict",
      "concurrencyLimit": "very-low",
      "budgetCheck": true
    }
  }
}
```

실제 수치는 부하 시험, SLO와 Downstream 제한을 기준으로 정합니다.

IP만 기준으로 제한하면 여러 사용자가 같은 NAT를 공유할 때 오탐이 발생하고, 공격자는 IP를 분산할 수 있습니다.

사용자·Client·Tenant·Tool과 비용 단위를 결합합니다.

## 21. Rate뿐 아니라 Concurrency·Queue·Budget을 제한한다

느리고 비싼 Tool은 낮은 요청 빈도에서도 자원을 고갈시킬 수 있습니다.

```text
긴 실행 1개 × 많은 동시성
  → Worker 고갈
  → Queue 적체
  → Timeout·재시도
  → 더 큰 부하와 비용
```

따라서 다음 통제가 필요합니다.

- Tool별 동시 실행 수
- Tenant별 Queue 깊이
- 최대 실행 시간
- 최대 재시도 횟수
- Batch 항목 수
- 검색 Result·파일 크기
- Model·외부 API Budget
- Circuit Breaker (회로 차단기)
- Backpressure (역압)
- 전체 시스템 Emergency Limit

OWASP API4 Unrestricted Resource Consumption (제한 없는 자원 소비)은 실행 시간, Memory, Payload, 작업 수, 호출 빈도와 외부 서비스 지출 한도를 함께 제한하도록 권고합니다.

## 22. 한도 초과 응답은 재시도 폭주를 막아야 한다

일반적인 Rate 초과에는 HTTP 429 `Too Many Requests`를 사용할 수 있습니다.

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
Content-Type: application/json
```

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "요청 한도를 초과했습니다.",
    "retryable": true,
    "retryAfterSeconds": 30,
    "requestId": "request_fixture_022"
  }
}
```

RFC 6585는 429 응답에 조건 설명과 선택적인 `Retry-After`를 포함할 수 있다고 정의합니다.

Client는 다음을 지켜야 합니다.

- `Retry-After` 준수
- Exponential Backoff (지수형 대기)
- Jitter (무작위 지연)
- 최대 재시도 횟수
- Non-idempotent Tool 자동 재시도 금지
- 권한 오류를 Rate 오류로 오인하지 않음

공격 중에는 429 응답 자체도 자원을 사용할 수 있으므로 Gateway 차단, 연결 종료와 Network 통제를 함께 고려합니다.

## 23. Rate Limit 저장소 장애 정책을 정한다

분산 Rate Limit은 Counter 저장소나 Gateway에 의존할 수 있습니다.

그 저장소가 실패했을 때의 정책이 필요합니다.

| Tool 위험 | 권장 방향 |
|---|---|
| 저비용 Public 읽기 | 제한된 Fail-open 검토 가능 |
| Tenant 비공개 읽기 | 보수적 한도·인증 유지 |
| 쓰기·외부 전송 | Fail-closed 또는 매우 낮은 비상 한도 |
| 파괴·고비용 작업 | Fail-closed |

Fail-open (장애 시 허용) 또는 Fail-closed (장애 시 거부)를 전역 Boolean 하나로 결정하지 않습니다.

Tool 위험, 비용, 가역성과 업무 중요도에 따라 분리합니다.

## 24. Timeout과 취소를 자원 회수까지 연결한다

Client가 SSE 응답 Stream을 닫으면 2026-07-28 Streamable HTTP에서 요청 취소 신호가 됩니다.

Server는 Connection 종료만 감지하고 Downstream 작업을 계속 방치하면 안 됩니다.

```text
Client 취소
  → Request Context 취소
    → Downstream HTTP·Database 취소
      → Worker·Lease 정리
        → 필요 시 보상·상태 기록
```

Side Effect가 이미 Commit됐다면 단순 취소로 되돌아간 것처럼 응답하지 않습니다.

최종 상태를 조회할 Operation 또는 명시적 보상 절차를 제공합니다.

Timeout은 다음 계층별로 둡니다.

- Gateway
- MCP 요청
- Tool
- Downstream API
- Database
- Model
- Queue 작업

상위 Timeout보다 하위 작업이 무한히 오래 실행되지 않도록 Budget을 전파합니다.

## 25. 오류 응답이 공격자에게 내부 구조를 알려주지 않게 한다

Client가 행동을 결정할 수 있는 정보는 제공하되 내부 구현은 숨깁니다.

| 포함 가능 | 외부 응답에서 제외 |
|---|---|
| 안전한 오류 코드 | Stack Trace |
| Retry 가능 여부 | SQL·내부 Query |
| 필요한 최소 Scope | Token 전체와 Claim Dump |
| 입력 Field 오류 | 내부 Host·Port |
| Request ID | Policy Expression |
| 사용자 조치 | Downstream 원문 |

인증이 필요한 객체의 존재 여부 자체가 민감하다면 403과 404 표현 정책을 일관되게 정합니다.

로그에는 상세 원인을 연결하되 Token, Secret, 원본 Prompt와 전체 Tool 결과를 남기지 않습니다.

## 26. Secret을 Prompt와 Tool 인자에서 분리한다

Model이 Credential을 볼 이유는 없습니다.

```text
Model
  → Tool 이름과 업무 인자 생성

Trusted Tool Broker
  → 현재 사용자·정책 확인
  → Secret Manager에서 Credential 획득
  → Downstream 요청에 주입
```

다음 위치에 Secret을 넣지 않습니다.

- System Prompt
- Tool Description
- Tool 입력·출력
- Resource 본문
- State Handle
- URL Query
- 일반 Log·Trace Attribute
- Error Message

Credential은 목적지·Scope·수명과 환경을 제한하고 회전·폐기할 수 있어야 합니다.

## 27. 감사 Log는 결정과 실행을 분리한다

다음 Event를 하나의 Correlation Chain (상관관계 연결)으로 남깁니다.

```text
REQUEST_RECEIVED
AUTHENTICATION_DECISION
AUTHORIZATION_DECISION
RATE_LIMIT_DECISION
TOOL_EXECUTION_STARTED
TOOL_EXECUTION_FINISHED
SIDE_EFFECT_COMMITTED
```

권장 Metadata는 다음과 같습니다.

- Timestamp
- Request·Trace·Tool Call ID
- Subject·Actor·Client·Tenant의 불투명 ID
- Tool·Action
- 정책 Decision과 Version
- 허용·거부 Reason Code
- Rate Class와 사용량
- 결과 상태와 지연
- Downstream Service의 안전한 식별자

Tool 입력 원문 대신 민감 Field를 제거한 Projection과 Digest를 고려합니다.

감사 Log 자체의 접근·수정·삭제 권한과 보존 기간도 분리합니다.

## 28. 배포 설정을 기계적으로 검사할 수 있게 만든다

운영 보안 설정을 Wiki 문장으로만 남기지 않습니다.

설명용 Manifest는 다음과 같습니다.

```json
{
  "securityProfile": "production-fixture",
  "transport": {
    "protocolVersion": "2026-07-28",
    "type": "streamable-http",
    "httpsRequired": true,
    "allowedOrigins": [
      "https://client.example.com"
    ],
    "maxBodyBytes": "DEPLOYMENT_VALUE"
  },
  "authorization": {
    "required": true,
    "resource": "https://mcp.example.com/mcp",
    "acceptedIssuers": [
      "https://auth.example.com"
    ],
    "audienceValidation": "required",
    "tokenPassthrough": "forbidden"
  },
  "egress": {
    "default": "deny",
    "redirectValidation": "every-hop",
    "privateDestinationAccess": "deny"
  },
  "limits": {
    "perSubject": true,
    "perTenant": true,
    "perTool": true,
    "concurrency": true,
    "costBudget": true
  }
}
```

CI·배포 Policy에서 다음을 검사할 수 있습니다.

- 운영에서 무인증 금지
- HTTPS 필수
- Wildcard Origin 금지
- Audience 검증 필수
- Token Passthrough 금지
- Egress 기본 거부
- Tool별 Rate·Concurrency 정의
- Debug Error와 민감 Log 금지

## 29. Negative Test Matrix를 운영 인수 조건으로 사용한다

정상 호출만 성공하는지 보지 않습니다.

| 시험 | 기대 결과 |
|---|---|
| Token 없이 호출 | 401, Tool 미실행 |
| 만료 Token | 401, Tool 미실행 |
| 다른 Audience Token | 401, Downstream 미호출 |
| 필요한 Scope 없음 | 403과 최소 Scope Challenge |
| 다른 Tenant 객체 ID | 거부, 데이터·존재 정보 미노출 |
| 등록되지 않은 Tool | Protocol 오류, 동적 실행 없음 |
| 허용되지 않은 Origin | 403, JSON-RPC 실행 전 차단 |
| Header의 Tool과 Body Tool 불일치 | 400 `HeaderMismatch` |
| 다른 사용자의 State Handle | 거부, 상태 미변경 |
| 내부·Loopback 목적지 URL | SSRF 차단, 응답 미반사 |
| Redirect가 금지 목적지로 변경 | 각 Hop 재검증 후 차단 |
| 큰 배열·깊은 Schema·큰 Payload | 입력 한도에서 거부 |
| 고비용 Tool 반복 호출 | Tool별 Rate·Budget 차단 |
| 동시 실행 한도 초과 | Queue·429·정책 응답 |
| Rate 저장소 장애 | Tool 위험별 Fail 정책 적용 |
| Client가 Stream 취소 | Downstream 자원 회수 |
| Tool Error에 Secret 포함 | Masking·출력 Schema에서 제거 |

거부 응답만 확인하지 않습니다.

```text
거부 Event가 기록됐는가?
Downstream 호출이 없었는가?
Side Effect가 발생하지 않았는가?
다른 Tenant 정보가 노출되지 않았는가?
재시도 폭주가 발생하지 않았는가?
```

## 30. 배포 전 체크리스트

### Transport·Network

- [ ] MCP Protocol Version과 호환 정책을 고정했다.
- [ ] 원격 Endpoint에 HTTPS를 적용했다.
- [ ] 신뢰 Proxy와 전달 Header 범위를 제한했다.
- [ ] Origin을 Scheme·Host·Port의 정확한 Allowlist로 검증한다.
- [ ] Local Mode는 Loopback에만 Binding한다.
- [ ] Health·Metrics·관리 Endpoint를 별도로 보호한다.

### OAuth·Authorization

- [ ] Protected Resource Metadata의 Resource·Issuer·Scope가 정확하다.
- [ ] Token의 Signature·Issuer·Audience·시간을 매 요청 검증한다.
- [ ] Access Token을 URL Query에 넣지 않는다.
- [ ] 다른 Resource용 Token과 Token Passthrough를 거부한다.
- [ ] 최소 Scope와 Step-up 정책을 사용한다.
- [ ] 401·403과 Scope Challenge 의미를 구분한다.
- [ ] Scope 이후 Tenant·객체·Action 권한을 다시 검사한다.

### Tool·State

- [ ] Tool 목록 노출과 실행 인가를 분리한다.
- [ ] Tool 입력·출력 Schema와 업무 규칙을 검증한다.
- [ ] Header와 Body가 불일치하면 실행 전에 거부한다.
- [ ] State Handle을 Subject·Tenant·Client·만료에 결속한다.
- [ ] 쓰기 Tool에 승인·멱등성·실행 시점 재인가를 적용한다.
- [ ] Secret을 Prompt·인자·결과·Error에서 분리한다.

### SSRF·Egress

- [ ] URL을 가져오는 모든 기능을 목록화했다.
- [ ] 허용 Scheme·Host·Port와 목적지 정책이 있다.
- [ ] Private·Loopback·Link-local·Reserved 목적지를 차단한다.
- [ ] Redirect의 모든 Hop을 다시 검증한다.
- [ ] DNS TOCTOU와 Encoding 우회를 시험한다.
- [ ] Egress Proxy·Firewall·Network Policy를 함께 적용한다.
- [ ] 응답 크기·시간·Content Type을 제한한다.

### Availability·Operations

- [ ] Subject·Client·Tenant·Tool별 Rate Limit이 있다.
- [ ] Concurrency·Queue·Payload·실행 시간·Budget을 제한한다.
- [ ] 429와 `Retry-After`·Backoff 정책이 있다.
- [ ] Rate 저장소 장애 시 Tool 위험별 Fail 정책이 있다.
- [ ] 취소·Timeout이 Downstream 자원을 회수한다.
- [ ] 거부·한도·Tool 실행·Side Effect 감사 Event를 연결한다.
- [ ] Negative Test Matrix를 배포 Gate에서 실행한다.

## 마무리

안전한 MCP Server는 OAuth Login이 한 번 성공한 Server가 아닙니다.

각 Tool Call이 다음 경계를 모두 통과하는 Server입니다.

```text
허용된 Origin·Network
  → 이 Resource용 유효한 Token
    → 현재 Tool의 최소 Scope
      → 현재 사용자·Tenant·객체 권한
        → 검증된 입력·Header·State
          → 허용된 Egress
            → Rate·Concurrency·Budget
              → 감사 가능한 Side Effect
```

핵심 원칙은 다음과 같습니다.

1. 2026-07-28 Protocol Version과 배포 유형을 먼저 고정합니다.
2. Origin 검증, CORS와 인증을 서로 다른 통제로 다룹니다.
3. Token을 매 요청 검증하고 Audience와 Resource를 결속합니다.
4. Token Passthrough를 금지하고 Downstream Credential 경계를 분리합니다.
5. Scope를 최소 Capability로 설계하고 객체·Tenant 인가를 다시 수행합니다.
6. State Handle을 권한으로 사용하지 않고 사용자와 상태에 결속합니다.
7. URL 검증과 Network Egress를 결합해 SSRF를 방어합니다.
8. Rate뿐 아니라 동시성, Queue, 실행 시간과 비용 Budget을 제한합니다.
9. Tool 입력·출력과 Header·Body를 결정적 코드로 검증합니다.
10. 정상 시험보다 거부 후 Side Effect가 없음을 검증하는 Negative Test를 운영 Gate로 사용합니다.

MCP Server 보안 체크리스트의 목적은 항목에 체크 표시를 많이 남기는 것이 아닙니다.

**잘못된 Token, 악성 Origin, 다른 Tenant ID, 위험한 URL과 반복 호출이 들어와도 Tool이 실행되지 않았다는 증거를 만드는 것**입니다.

다음 글에서는 Prompt Injection을 직접·간접·다중 Modal 공격으로 나누고, 신뢰 경계·데이터 표식·Tool Allowlist와 실행 전 재검증으로 방어하는 방법을 살펴보겠습니다.

## 참고 자료

- [MCP 2026-07-28: Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
- [MCP 2026-07-28: Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [MCP 2026-07-28: Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [MCP 2026-07-28: Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)
- [RFC 9700: Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700.html)
- [RFC 9728: OAuth 2.0 Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728.html)
- [RFC 8707: Resource Indicators for OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707.html)
- [RFC 6750: OAuth 2.0 Bearer Token Usage](https://www.rfc-editor.org/rfc/rfc6750.html)
- [RFC 6454: The Web Origin Concept](https://www.rfc-editor.org/rfc/rfc6454.html)
- [RFC 6585: Additional HTTP Status Codes](https://www.rfc-editor.org/rfc/rfc6585.html)
- [OWASP Server-Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- [OWASP API4:2023 Unrestricted Resource Consumption](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/)

---

> 이 글은 2026년 7월 29일 기준 MCP 2026-07-28 사양, IETF OAuth·HTTP RFC와 OWASP의 공식 공개 자료 및 공개 가능한 엔터프라이즈 MCP Server 설계 경험을 바탕으로 작성했습니다. 예시 Domain, Scope, Handle, 정책, 한도와 시간은 설명용 Fixture이며 실제 적용 시 조직의 Identity Provider, Network, Tenant 모델, Tool 위험, 데이터 분류, SLO, 관련 법규와 보안 정책에 맞게 검토하고 침투·부하·장애 시험으로 검증해야 합니다.
