# Tistory 기술자료 초안

- 문서 ID: `BLOG-09`
- 상태: 공개 완료
- Tistory 상태: 공개
- 공개 URL: `https://aiarchitect.tistory.com/11`
- 분류: `AI Agent · MCP`
- 권장 제목: `MCP OAuth 2.1 인증 구조: Discovery, PKCE와 Resource Server 경계`
- 검색 설명: `원격 MCP Server 인증에서 Protected Resource Metadata(보호 리소스 메타데이터), Authorization Server Discovery(인증 서버 탐색), PKCE(인증 코드 보호), Resource Indicator(대상 리소스 지정)와 Scope(권한 범위)를 연결하는 구조를 정리합니다.`
- 권장 태그: `MCP`, `OAuth 2.1`, `PKCE`, `Resource Server`, `인증`, `권한 설계`, `AI Agent`
- 권장 대표 이미지: `portfolio/architecture-diagrams/04-mcp-enterprise-integration.svg`

---

# MCP OAuth 2.1 인증 구조: Discovery, PKCE와 Resource Server 경계

원격 MCP Server가 사용자별 문서, 회의, 업무 시스템이나 관리자 기능에 접근한다면 “로그인 화면을 붙였다”는 것만으로 인증 설계가 끝나지 않습니다.

MCP Client는 다음 질문에 답할 수 있어야 합니다.

1. 이 MCP Server는 어떤 Authorization Server(인증 서버)를 사용하는가
2. 어떤 Endpoint와 기능을 지원하는가
3. Client ID는 어떤 방식으로 등록하는가
4. Authorization Code(인증 코드)를 어떻게 안전하게 교환하는가
5. 발급된 Token이 이 MCP Server를 위한 것인지 어떻게 확인하는가
6. 현재 Tool에 필요한 Scope(권한 범위)는 무엇인가

MCP Authorization은 이 과정을 하나의 전용 인증 방식으로 다시 만들지 않습니다. OAuth 2.1과 여러 OAuth 표준을 조합해 원격 MCP Server를 보호합니다.

다만 2026년 7월 29일 기준 OAuth 2.1은 아직 IETF Draft(인터넷 초안)입니다. 이 글에서 “OAuth 2.1”은 MCP Authorization 사양이 참조하는 `draft-ietf-oauth-v2-1-13`과 관련 보안 RFC를 의미합니다.

## 1. 세 역할의 경계를 먼저 구분한다

MCP Authorization에는 세 가지 핵심 역할이 있습니다.

| 역할 | MCP에서의 주체 | 주요 책임 |
|---|---|---|
| OAuth Client | MCP Client·Host | 사용자 인증 시작, PKCE 생성, Token 보관과 MCP 요청 |
| Resource Server | 원격 MCP Server | Access Token 검증, Scope·사용자·업무 권한 검사 |
| Authorization Server | OAuth·OIDC 서버 | 사용자 로그인·동의, Client 검증, Token 발급 |

```text
User
  │ 로그인·동의
  ▼
Authorization Server
  ▲             │ Authorization Code · Token
  │             ▼
MCP Client ───▶ MCP Server
 OAuth Client    Resource Server
```

MCP Server가 Authorization Server와 같은 Application에 배포될 수는 있습니다. 하지만 논리적인 책임은 분리해야 합니다.

- Authorization Server는 사용자를 인증하고 Token을 발급합니다.
- MCP Server는 받은 Token이 자신의 Resource용인지 확인합니다.
- 업무 데이터에 대한 최종 권한은 MCP Server가 직접 검사합니다.

Token이 유효하다는 사실과 특정 회의·문서·프로젝트에 접근할 수 있다는 사실은 같은 의미가 아닙니다.

## 2. 로컬 `stdio`와 원격 HTTP 인증은 출발점이 다르다

로컬 `stdio` MCP Server는 Host가 실행한 Child Process(하위 프로세스)일 수 있습니다. 이 경우 운영체제 자격 증명, 환경 기반 Credential(자격 증명)이나 Host가 제공하는 인증 문맥을 사용할 수 있습니다.

원격 Streamable HTTP MCP Server는 네트워크를 통해 여러 Client와 사용자가 접근하므로 OAuth 기반 Authorization이 중요합니다.

| 구분 | 로컬 `stdio` | 원격 HTTP |
|---|---|---|
| 실행 위치 | 사용자 장치의 Process | 원격 서비스·Container |
| 주요 신뢰 경계 | Host와 Process | Client, Internet, Gateway, Server |
| 대표 인증 | 로컬 Credential·Host 전달 | OAuth Access Token |
| 사용자 구분 | Host 문맥에 의존 가능 | 요청별 Token으로 확인 |
| Transport 보안 | Process·OS 경계 | HTTPS 필수 |

원격 Server가 `Mcp-Session-Id`나 연결 상태를 사용자 인증으로 사용해서는 안 됩니다. 세션 ID는 요청 연결을 돕는 식별자이지 신원 증거가 아닙니다.

## 3. 인증 흐름은 401 Challenge에서 시작한다

Token 없이 보호된 MCP Endpoint를 호출하면 Server는 `401 Unauthorized`와 `WWW-Authenticate` Challenge(인증 요구 정보)를 반환합니다.

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer
  resource_metadata="https://mcp.example.net/.well-known/oauth-protected-resource",
  scope="meetings:read"
```

두 값의 역할은 다릅니다.

- `resource_metadata`: 이 Resource의 인증 정보를 찾을 위치
- `scope`: 현재 요청을 수행하는 데 필요한 권한

MCP Authorization 초안은 Client가 초기 Scope를 선택할 때 Challenge의 `scope`를 우선 사용하도록 안내합니다. `scopes_supported` 전체를 항상 요청하는 방식보다 Least Privilege(최소 권한)에 가깝습니다.

```text
MCP Request without Token
  → 401 + WWW-Authenticate
  → Protected Resource Metadata 조회
  → Authorization Server Metadata 조회
  → Client 등록 정보 결정
  → Authorization Code + PKCE
  → Access Token 발급
  → 인증된 MCP Request 재시도
```

## 4. Protected Resource Metadata로 Resource를 발견한다

Protected Resource Metadata(보호 리소스 메타데이터)는 RFC 9728이 정의한 JSON 문서입니다.

```json
{
  "resource": "https://mcp.example.net/mcp",
  "authorization_servers": [
    "https://auth.example.net"
  ],
  "scopes_supported": [
    "meetings:read",
    "meetings:create"
  ],
  "bearer_methods_supported": [
    "header"
  ]
}
```

Client는 여기서 다음 정보를 확인합니다.

- 정확한 Resource Identifier(리소스 식별자)
- 사용할 수 있는 Authorization Server
- Resource가 지원하는 Scope
- Bearer Token 전달 방식

RFC 9728은 Metadata를 Resource Identifier에서 결정적으로 만들어지는 `.well-known` 위치에 게시하도록 규정합니다.

```text
Resource
https://mcp.example.net/mcp

Metadata
https://mcp.example.net/.well-known/oauth-protected-resource/mcp
```

경로가 없는 Resource라면 기본 위치는 다음과 같습니다.

```text
https://mcp.example.net/.well-known/oauth-protected-resource
```

Client는 Metadata의 `resource` 값이 자신이 접근하려던 Resource Identifier와 정확히 일치하는지 검증해야 합니다. 이 검증을 생략하면 공격자가 다른 Resource의 Metadata를 대신 제공할 수 있습니다.

## 5. Authorization Server Metadata에서 Endpoint를 찾는다

Protected Resource Metadata에서 Authorization Server의 Issuer(발급자 식별자)를 찾은 뒤 Client는 Server Metadata를 조회합니다.

MCP Client는 다음 두 Discovery(탐색) 방식을 지원해야 합니다.

- RFC 8414 OAuth Authorization Server Metadata
- OpenID Connect Discovery

대표적인 Metadata는 다음과 같습니다.

```json
{
  "issuer": "https://auth.example.net",
  "authorization_endpoint": "https://auth.example.net/oauth2/authorize",
  "token_endpoint": "https://auth.example.net/oauth2/token",
  "registration_endpoint": "https://auth.example.net/oauth2/register",
  "code_challenge_methods_supported": [
    "S256"
  ],
  "scopes_supported": [
    "meetings:read",
    "meetings:create"
  ]
}
```

Client는 발견한 URL을 그대로 신뢰하지 않고 다음을 확인합니다.

- Metadata를 HTTPS로 조회했는가
- 조회에 사용한 Issuer와 응답의 `issuer`가 정확히 일치하는가
- Authorization·Token Endpoint가 기대한 Server에 속하는가
- PKCE `S256`을 지원하는가
- 필요한 Grant Type과 Client 등록 방식을 지원하는가

RFC 8414는 Metadata 요청에 사용한 Issuer와 응답의 `issuer`를 정확히 비교하도록 요구합니다. 비슷해 보이는 Host, 다른 Realm이나 경로를 같은 것으로 처리하지 않습니다.

## 6. Client 등록은 세 가지 방식을 구분한다

Authorization Flow를 시작하려면 MCP Client에 Client ID가 필요합니다.

현재 MCP Authorization 초안은 다음 세 가지 방식을 구분합니다.

1. Client ID Metadata Document(클라이언트 메타데이터 문서)
2. 사전 등록된 Client ID
3. Dynamic Client Registration(동적 클라이언트 등록)

Client ID Metadata Document는 Client 자체를 설명하는 HTTPS URL을 Client ID로 사용하는 방식입니다. 현재 MCP 초안은 Client와 Authorization Server가 이 방식을 지원하도록 권장합니다.

사전 등록은 기업 환경에서 관리자가 승인한 Redirect URI와 Client 정책을 미리 설정할 때 적합합니다.

Dynamic Client Registration은 범용 Client가 새로운 Authorization Server에 연결할 때 유용하지만, 현재 MCP 초안에서는 하위 호환을 위해 유지되는 방식으로 설명됩니다.

| 방식 | 장점 | 운영 시 주의점 |
|---|---|---|
| Client ID Metadata | 분산 Client 정보, 별도 등록 API 의존 감소 | Metadata Host 신뢰 정책 필요 |
| 사전 등록 | 가장 강한 관리 통제 | Client가 늘어날수록 운영 부담 |
| Dynamic Registration | 자동 연결 편의성 | Trusted Host·Rate Limit·등록 감사 필요 |

등록 방식과 관계없이 Redirect URI는 정확하게 제한해야 합니다. Wildcard(와일드카드)나 부분 문자열 비교는 Authorization Code가 공격자에게 전달될 가능성을 높입니다.

## 7. PKCE는 Authorization Code 탈취를 막는다

PKCE(Proof Key for Code Exchange, 인증 코드 교환 증명)는 Authorization Code를 가로챈 공격자가 Token으로 교환하지 못하도록 합니다.

Client는 매 인증 요청마다 충분히 무작위인 `code_verifier`를 생성합니다.

```text
code_verifier = cryptographically random value
code_challenge = BASE64URL(SHA256(code_verifier))
```

Authorization Request에는 Challenge만 보냅니다.

```http
GET /oauth2/authorize?
  response_type=code&
  client_id=https%3A%2F%2Fclient.example.net%2Fmetadata.json&
  redirect_uri=https%3A%2F%2Fclient.example.net%2Fcallback&
  code_challenge=<challenge>&
  code_challenge_method=S256&
  resource=https%3A%2F%2Fmcp.example.net%2Fmcp&
  scope=meetings%3Aread&
  state=<opaque-state>
```

Token Request에서는 원래의 Verifier를 보냅니다.

```http
POST /oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=<authorization-code>&
redirect_uri=https%3A%2F%2Fclient.example.net%2Fcallback&
client_id=https%3A%2F%2Fclient.example.net%2Fmetadata.json&
code_verifier=<original-verifier>&
resource=https%3A%2F%2Fmcp.example.net%2Fmcp
```

Authorization Server는 Verifier로 다시 계산한 값이 처음 받은 Challenge와 같은지 확인합니다.

```text
BASE64URL(SHA256(code_verifier)) == stored_code_challenge
```

새 구현에서는 `plain`으로 Downgrade(보안 수준 하향)하지 않고 `S256`을 사용합니다. RFC 7636은 Client가 `S256` 실패 뒤 `plain`으로 낮추지 말아야 한다고 설명합니다.

## 8. PKCE만으로 모든 OAuth 공격을 막을 수는 없다

PKCE는 Authorization Code 탈취 방어의 핵심이지만 다음 검증을 대체하지 않습니다.

- `state`를 요청별로 생성하고 Callback에서 일치 여부 확인
- Redirect URI 정확한 일치
- Authorization Response의 `iss` 검증
- Metadata에서 확인한 Issuer와 Endpoint Binding(결속)
- Client Credential을 발급한 Issuer에 Binding
- Open Redirect(임의 주소 이동) 차단

MCP `2026-07-28` Authorization 변경에는 RFC 9207에 따른 `iss` 검증이 포함됐습니다. 하나의 MCP Client가 여러 Server·Issuer에 연결할 때 Authorization Response Mix-Up(인증 응답 혼동) 위험을 줄이기 위한 조치입니다.

```text
인증 시작 시 저장
issuer + state + code_verifier + redirect_uri + resource

Callback 시 검증
response issuer == stored issuer
response state == stored state
```

인증 요청별 값을 하나의 Transaction Record(거래 기록)에 묶고, 짧은 수명과 단일 사용 정책을 적용합니다.

## 9. `resource`와 `audience`로 Token의 목적지를 제한한다

Scope는 “무엇을 할 수 있는가”를 나타냅니다. Resource Indicator(대상 리소스 지정)는 “어느 Server에서 사용할 Token인가”를 나타냅니다.

```text
scope    = meetings:read
resource = https://mcp.example.net/mcp
```

Client는 Authorization Request와 Token Request에 RFC 8707의 `resource` Parameter를 포함합니다.

Authorization Server는 이 값에 맞는 Audience-restricted Token(대상 제한 토큰)을 발급합니다.

```json
{
  "iss": "https://auth.example.net",
  "sub": "usr_opaque_id",
  "aud": "https://mcp.example.net/mcp",
  "scope": "meetings:read",
  "exp": 1785315600
}
```

MCP Server는 `aud`가 자신의 Resource Identifier와 일치하는지 검사합니다.

```text
Token A
aud = https://mcp-a.example.net/mcp

MCP Server B
resource = https://mcp-b.example.net/mcp

결과: 거부
```

이 경계를 지키면 한 MCP Server에서 얻은 Token이 다른 MCP Server에서 재사용되는 위험을 줄일 수 있습니다. 여러 Audience를 가진 하나의 Bearer Token보다 Resource별 Token이 권한과 사고 범위를 관리하기 쉽습니다.

## 10. Resource Server가 매 요청을 최종 검증한다

원격 MCP Server는 Gateway가 Token을 확인했다는 이유만으로 요청을 신뢰하지 않습니다.

요청마다 최소한 다음을 검증합니다.

| 검증 | 확인 내용 |
|---|---|
| 서명·상태 | 서명 또는 Introspection 결과가 유효한가 |
| Issuer | 허용한 Authorization Server가 발급했는가 |
| Audience | 현재 MCP Resource를 위한 Token인가 |
| 시간 | `exp`, `nbf`와 필요 시 `iat`가 유효한가 |
| Scope | 현재 Tool에 필요한 Scope가 있는가 |
| 사용자 | `sub`가 활성 사용자와 연결되는가 |
| 테넌트 | Token과 요청 대상의 테넌트가 일치하는가 |
| 업무 권한 | 현재 문서·그룹·프로젝트에 접근할 수 있는가 |

다음 값은 권한 증거가 아닙니다.

- Client가 보낸 사용자 ID
- Tool 인자의 테넌트 ID
- `Mcp-Session-Id`
- 이전 요청의 인증 결과
- 모델이 생성한 `"authorized": true`

Token 검증이 성공해도 Server는 Tool 인자와 현재 업무 권한을 다시 확인해야 합니다.

## 11. Scope는 Tool과 위험도에 맞게 나눈다

`mcp:full-access` 같은 하나의 Scope는 구현은 쉽지만 Token 탈취나 잘못된 Tool 호출의 피해 범위를 키웁니다.

```text
meetings:read
meetings:create
meetings:transfer
meetings:delete
summaries:request
```

초기 연결에서는 읽기 Scope만 요청하고, 사용자가 실제로 쓰기 작업을 시도할 때 Step-Up Authorization(단계적 권한 승격)을 요청할 수 있습니다.

```http
HTTP/1.1 403 Forbidden
WWW-Authenticate: Bearer
  error="insufficient_scope",
  scope="meetings:create"
```

Client는 현재 Challenge의 Scope를 기준으로 추가 동의를 요청하고, 기존에 필요한 Scope가 사라지지 않도록 누적 정책을 적용합니다.

Scope가 있어도 다음 업무 규칙은 별도로 확인해야 합니다.

- 사용자가 대상 Project의 Member인가
- 생성과 삭제 권한이 분리돼 있는가
- 다른 테넌트로 이동할 수 있는가
- 현재 시간·위치·기기 정책을 만족하는가
- 위험 작업의 사용자 승인이 있는가

## 12. 401과 403을 구분해 Client가 복구할 수 있게 한다

| 상태 | 의미 | Client의 일반적인 대응 |
|---|---|---|
| `401 Unauthorized` | Token 없음·만료·유효하지 않음 | 인증 또는 갱신 후 재시도 |
| `403 Forbidden` | Token은 유효하지만 Scope·업무 권한 부족 | Step-Up 또는 사용자에게 권한 부족 안내 |
| `400 Bad Request` | Authorization Request 형식 오류 | 요청 수정, 자동 반복 금지 |

`401` 응답에는 필요한 경우 `resource_metadata`와 현재 작업의 `scope`를 포함합니다.

`403`을 모두 `401`로 바꾸면 Client가 불필요하게 로그인을 반복할 수 있습니다. 반대로 만료 Token을 `403`으로 반환하면 Client가 Token 갱신 시점을 판단하기 어렵습니다.

오류 응답에는 Token, 내부 Realm, Policy Expression이나 Stack Trace를 노출하지 않습니다. 내부 로그에는 Correlation ID(상관관계 식별자)로 상세 원인을 연결합니다.

## 13. Refresh Token과 `offline_access`는 분리해 생각한다

Access Token을 짧게 유지하면 탈취 피해 시간을 줄일 수 있지만 사용자가 자주 다시 로그인할 수 있습니다. Refresh Token(갱신 토큰)은 새 Access Token을 발급받을 때 사용합니다.

MCP Client는 다음 원칙을 적용합니다.

- Refresh Token을 암호화된 저장소에 보관
- 로그·Prompt·Tool 인자에 넣지 않음
- Client·Issuer·사용자와 Binding
- 만료·폐기·회전 정책 적용
- 발급을 당연하게 가정하지 않음

`offline_access`는 Resource가 요구하는 Scope가 아니라 Client가 장기간 접근을 요청하는 의미에 가깝습니다. MCP Authorization 초안은 MCP Server가 `WWW-Authenticate`나 Protected Resource Metadata의 `scopes_supported`에 `offline_access`를 Resource 요구사항처럼 넣지 않도록 안내합니다.

## 14. Token을 Model Context에 노출하지 않는다

Agent가 Tool을 호출할 때 모델이 Access Token을 직접 볼 이유가 없습니다.

```text
Model
  │ tool name + validated arguments
  ▼
MCP Host · Credential Broker
  │ Authorization: Bearer <token>
  ▼
Remote MCP Server
```

MCP Host가 Token을 안전하게 보관하고 요청 직전에 Header를 추가합니다.

다음 위치에 Token을 기록하지 않습니다.

- System Prompt와 Conversation
- Tool Description과 Tool Result
- 생성된 Code와 Sandbox Output
- Application Log와 Trace Attribute
- URL Query String
- 오류 메시지와 Screenshot

MCP Authorization은 Access Token을 `Authorization: Bearer` Header로 매 HTTP 요청에 포함하고 URI Query String에는 넣지 않도록 요구합니다.

## 15. 흔한 장애를 인증 단계별로 진단한다

| 증상 | 가능성이 높은 원인 | 먼저 확인할 항목 |
|---|---|---|
| 401 뒤 로그인 화면이 열리지 않음 | Challenge·PRM 오류 | `resource_metadata`, HTTPS, `resource` 일치 |
| Metadata 조회 실패 | `.well-known` 경로 계산 오류 | Resource에 Path가 있는지 확인 |
| Client 등록 거부 | 등록 정책·Trusted Host | 등록 방식, Redirect URI, Application Type |
| Callback 거부 | Redirect URI 불일치 | Scheme·Host·Path·Port 정책 |
| Code 교환 실패 | PKCE·일회성 Code 문제 | `code_verifier`, `S256`, Code 재사용 |
| Token은 발급됐지만 MCP가 401 | Issuer·Audience·서명 오류 | `iss`, `aud`, Key·Introspection |
| 일부 Tool만 403 | Scope·업무 권한 부족 | Tool 요구 Scope와 Server Policy |
| 다른 계정으로 연결됨 | 기존 Authorization Server Session | 현재 로그인 사용자와 연결 해제·재인증 |
| 갱신 후 Scope가 사라짐 | Step-Up 누적 오류 | 기존·추가 Scope 결합 정책 |
| 재시작 뒤 인증 반복 | Token 저장·Refresh 정책 오류 | 안전한 저장소, 만료, 회전 |

인증 문제는 “OAuth가 안 된다”로 묶기보다 다음 단계로 분리해야 원인을 빠르게 찾을 수 있습니다.

```text
Resource Discovery
→ Authorization Server Discovery
→ Client Registration
→ User Authorization
→ Callback Validation
→ Token Exchange
→ Token Validation
→ Scope Authorization
→ Business Authorization
```

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| 역할 | Client, Resource Server와 Authorization Server 책임이 분리돼 있는가 |
| Transport | 원격 MCP Endpoint가 HTTPS만 허용하는가 |
| Challenge | 401에 올바른 `resource_metadata`와 필요한 Scope가 있는가 |
| PRM | RFC 9728 Metadata와 실제 Resource Identifier가 일치하는가 |
| AS Discovery | Issuer와 Metadata 응답의 `issuer`를 정확히 비교하는가 |
| Client 등록 | Client ID Metadata·사전 등록·DCR 정책을 구분하는가 |
| Redirect | 등록 URI를 정확한 문자열로 검증하는가 |
| PKCE | 요청별 Verifier와 `S256`을 사용하고 Downgrade를 막는가 |
| Callback | `state`와 Authorization Response의 `iss`를 검증하는가 |
| Resource | Authorization·Token Request에 정확한 `resource`를 보내는가 |
| Audience | MCP Server가 자신의 `aud`만 허용하는가 |
| Token | 서명·Issuer·Audience·시간·Scope를 매 요청 확인하는가 |
| 업무 권한 | Token 이후 사용자·테넌트·대상 권한을 다시 검사하는가 |
| Scope | 읽기·쓰기·삭제를 나누고 필요한 시점에만 승격하는가 |
| 오류 | 401·403·400의 의미와 Client 복구가 일치하는가 |
| Refresh | Token을 안전하게 저장하고 만료·회전·폐기를 처리하는가 |
| 비밀정보 | Token·Code·Verifier를 Prompt·URL·로그에 기록하지 않는가 |
| 감사 | 로그인·동의·승격·거부를 Correlation ID로 추적하는가 |

## 마무리

MCP OAuth 인증은 Token 하나를 발급받는 기능이 아닙니다. **Resource를 발견하고, 올바른 Authorization Server와 Client를 연결하며, Token의 목적지와 권한을 Resource Server가 끝까지 검증하는 계약**입니다.

운영 환경에서는 다음 경계를 함께 지켜야 합니다.

1. MCP Client, Resource Server와 Authorization Server의 책임을 분리합니다.
2. `401` Challenge에서 Protected Resource Metadata를 발견합니다.
3. Authorization Server Metadata와 Issuer를 정확히 검증합니다.
4. 환경에 맞는 Client 등록 방식을 선택합니다.
5. Authorization Code Flow에 PKCE `S256`을 적용합니다.
6. `state`, `iss`, Redirect URI로 Callback을 검증합니다.
7. `resource`와 `aud`로 Token의 목적지를 제한합니다.
8. Resource Server가 Scope와 실제 업무 권한을 매 요청 확인합니다.
9. Token을 Model Context와 로그에서 분리합니다.
10. Discovery부터 업무 권한까지 단계별로 관측하고 진단합니다.

다음 글에서는 실시간 STT Pipeline에서 48kHz 입력을 모델 입력 형식으로 변환하고 Partial(중간 결과)·Final(확정 결과) 자막과 무음 환각을 관리하는 방법을 살펴보겠습니다.

---

## 참고 자료

- [MCP Draft: Authorization](https://modelcontextprotocol.io/specification/draft/basic/authorization)
- [MCP 2026-07-28: Understanding Authorization](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization)
- [MCP 2026-07-28: Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)
- [MCP 2026-07-28 Specification Release Candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
- [IETF OAuth 2.1 Draft 13](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13)
- [RFC 9728: OAuth 2.0 Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728)
- [RFC 8414: OAuth 2.0 Authorization Server Metadata](https://datatracker.ietf.org/doc/html/rfc8414)
- [RFC 7636: Proof Key for Code Exchange](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 8707: Resource Indicators for OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc8707)
- [RFC 9207: OAuth 2.0 Authorization Server Issuer Identification](https://datatracker.ietf.org/doc/html/rfc9207)
- [RFC 9700: Best Current Practice for OAuth 2.0 Security](https://datatracker.ietf.org/doc/html/rfc9700)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0.html)

> 이 글은 2026년 7월 29일 기준 MCP Authorization 초안과 공개 OAuth·OpenID Connect 표준을 바탕으로 작성했습니다. OAuth 2.1과 MCP Authorization은 발전 중이므로 구현 전 사용 중인 MCP SDK, Authorization Server와 공식 사양의 최신 버전을 다시 확인해야 합니다.
