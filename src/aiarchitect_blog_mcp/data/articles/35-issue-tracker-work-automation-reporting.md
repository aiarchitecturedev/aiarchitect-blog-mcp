# 이슈 트래커 업무 자동화 리포팅: MCP 수집·사용자 매핑·범위 검증·민감정보 처리

많은 조직이 이슈 트래커 (Issue Tracker)에 매일의 업무 흔적을 남깁니다. 이슈가 생성되고, 상태가 바뀌고, 담당자가 배정되고, 코멘트와 작업 시간이 기록됩니다. 그런데 정작 "지난 한 주 동안 우리 팀이 무엇을 했는가"를 한 장으로 정리하려고 하면, 사람이 화면을 열어 필터를 걸고 숫자를 손으로 옮겨 적습니다. 매일 반복되는 이 작업은 지루할 뿐 아니라, 사람마다 집계 방식이 달라 숫자가 미묘하게 어긋납니다.

이 글은 이슈 트래커를 MCP (Model Context Protocol) 호환 브리지로 AI Agent에 연결하고, 활동 데이터를 수집·집계해 **신뢰할 수 있는 운영/경영 리포트**를 자동 생성한 경험을 일반화해 정리합니다. 핵심은 "API를 호출해 데이터를 긁어오는 것"이 아니라, **그 숫자를 의사결정에 써도 되는가**를 보장하는 일입니다. 그리고 그 신뢰의 기준은 "빈 날짜가 없는 리포트"가 아니라, **고정된 원본 시점(as-of)과 수집 대사(reconciliation) 증거를 가진 리포트**입니다. 이슈는 사후에 수정되고 작업 시간은 소급 등록되므로, 같은 스코프라도 "언제 본 데이터인가"를 고정하지 않으면 같은 숫자가 재현되지 않습니다. 단, `as_of`를 적어 두는 것만으로 재현이 되는 것은 아니고, **원본 시스템이 그 시점의 데이터를 실제로 보존·재조회할 수 있어야** 성립합니다(11절 참조). 그래서 이 글의 절반은 수집이 아니라 지표 정의·검증·매핑·민감정보 처리에 할애합니다.

본문의 프로젝트·계정·수치·업무 시스템 URL은 **합성 예시**입니다. 특정 고객사·회사·실제 사용자·실제 이슈 번호를 가리키지 않으며, 예시 URL은 `example.com`을 사용합니다. 단, 상호 참조와 공식 참고 자료 링크에는 공개 웹사이트의 실제 URL을 사용합니다. 또한 이 글의 이벤트 건수 지표는 **운영 신호일 뿐 개인 성과평가 지표가 아닙니다**(5.1절 참조).

## 1. 문제 정의: "데이터가 있다"와 "리포트를 믿는다"의 간극

이슈 트래커에는 이미 데이터가 있습니다. 그러나 원본 데이터를 그대로 긁어와 표로 만든다고 해서 그것이 리포트가 되지는 않습니다. 다음 세 가지 질문에 답할 수 없다면, 그 표는 참고 자료일 뿐 근거가 되지 못합니다.

```text
1) 이 수치는 어느 프로젝트·어느 기간·어느 사람의 활동만 담고 있는가? (범위)
2) 그 범위 안의 활동을, 원본과 대사(reconciliation)해 빠짐없이 담았음을
   증거로 보일 수 있는가?                                       (수집 대사)
3) 어느 시점의 원본을 본 것인지 고정하고, 그 시점·규칙·수집기
   버전으로 같은 숫자를 다시 만들 수 있는가?                     (as-of 재현성)
```

이 세 가지가 보장되지 않으면, 리포트를 본 관리자는 결국 원본 화면을 다시 열어 직접 확인합니다. 그 순간 자동화의 가치는 사라집니다. 자동 리포팅의 목표는 "빠르게 만드는 것"이 아니라 **"사람이 다시 확인하지 않아도 되는 것"** 입니다.

| 구분 | 단순 API 스크립트 | 신뢰 가능한 자동 리포트 |
| --- | --- | --- |
| 관심사 | 데이터를 가져오는가 | 원본과 대사되고 as-of로 재현 가능한가 |
| 범위 | 쿼리에 걸린 대로 | 프로젝트·기간·명단(roster)으로 명시 고정 |
| 원본 시점 | 실행할 때마다 다른 "지금" | 고정된 `as_of` 스냅샷/워터마크로 못 박음 |
| 결측 처리 | 조용히 누락 | 원본 총건수와 대사해 결측을 탐지·표기 |
| 개인정보 | 원문 그대로 노출 | 목적에 맞게 요약·마스킹, 외부용은 가명처리 |
| 결과물 | 콘솔·임시 CSV | 독립 실행형 HTML(이스케이프 적용), 감사 매니페스트 포함 |
| 재실행 | 매번 결과가 다를 수 있음 | 최신본은 멱등 갱신, 감사본은 실행별 불변 보존 |

## 2. 전체 아키텍처 개요

리포팅 파이프라인은 사전조건 `(0)`을 고정한 뒤 크게 다섯 단계 `(1)~(5)`로 나뉩니다. 각 단계는 앞 단계의 출력이 유효할 때만 다음으로 넘어가는 게이트 구조입니다.

```text
[이슈 트래커 API]
   ▲
   │  인가 경계 B: 브리지 → 이슈 트래커 (업스트림 자격 증명)
   │  읽기 전용 최소 권한. OAuth 토큰이거나 API 키일 수 있음
   │  트래커(리소스) 대상으로만 발급·사용
   │
[MCP 브리지 = MCP Server]  ──  Tool: list_projects / list_issues / list_journals ...
   ▲
   │  인가 경계 A: MCP Client → MCP Server (MCP 인가, HTTP 전송 시)
   │  이 MCP 서버(리소스) 대상으로 발급된 토큰만 사용
   │  (JSON-RPC 2.0. Tool 결과 페이지네이션은 트래커 API 페이지네이션과 별개 계약)
   │
[AI Agent 오케스트레이터 = MCP Client 포함]
   ├─ (0) 원본 시점 고정: as_of / 수집 워터마크 / 수집기 버전
   ├─ (1) 범위 정의: 프로젝트 ID + 기간 + 명단(버전)
   ├─ (2) 수집: 페이지네이션 + 저널/변경 이력 + 원본 총건수 대사
   ├─ (3) 매핑: 계정 → 표시 이름, 명단 밖 제외(건수 보존)
   ├─ (4) 검증: 수집 대사(control total) + TZ 경계 + as-of 재현성
   ├─ (5) 민감정보: 사전 마스킹 → 요약 → 사후 마스킹 → 가명처리
   ▼
[산출물]  독립 실행형 UTF-8 HTML 리포트(이스케이프·CSP 적용, 오프라인·인쇄)
   +  실행 매니페스트(as_of·스냅샷 해시·대사 수치) / 감사 로그
```

두 인가 경계(A: MCP Client→Server, B: 브리지→이슈 트래커)는 **경계별로 분리된 자격 증명**을 씁니다. 반드시 서로 다른 인가 서버일 필요는 없고(동일 IdP가 두 리소스용 토큰을 각각 발급할 수도 있으며, 경계 B는 API 키일 수도 있음), 핵심은 **각 토큰이 서로 다른 리소스(audience)에 바인딩**되고 **어느 한쪽 토큰을 다른 쪽으로 그대로 흘려보내지 않는 것**입니다(토큰 패스스루 금지, 4절 참조).

MCP는 LLM 애플리케이션과 외부 데이터·도구를 연결하는 개방형 프로토콜로, `Host`(LLM 애플리케이션), `Client`(호스트 내부 커넥터), `Server`(도구·데이터를 제공하는 서비스)의 3자 구조와 JSON-RPC 2.0 메시지를 씁니다. 서버는 `Resources`(맥락·데이터), `Prompts`(템플릿), `Tools`(모델이 실행하는 함수)를 노출합니다. 이 글에서 이슈 트래커는 MCP `Server`가 노출한 `Tools`를 통해 접근됩니다.

Tool 설계의 일반 원칙과 MCP를 엔터프라이즈 표준으로 다루는 논의는 별도 글에서 다뤘으므로 여기서는 재설명하지 않고 리포팅 특화 관점에 집중합니다(끝의 상호 참조 참고).

## 3. 연결: MCP 브리지와 읽기 전용 최소 권한

이 절이 다루는 것은 **인가 경계 B**, 즉 MCP 브리지가 업스트림 이슈 트래커 API에 접속할 때 쓰는 자격 증명입니다(MCP Client→MCP Server 인가는 4절). 리포팅용 연결에서 첫 번째 원칙은 **최소 권한(least privilege)** 입니다. 리포트를 만드는 데는 조회 권한만 있으면 되고, 이슈를 생성·수정·삭제할 권한은 필요 없습니다. 브리지가 이슈 트래커에 쓰는 자격 증명은 다음 조건을 만족해야 합니다.

- 읽기 전용(read-only) 스코프. 쓰기·삭제 Tool은 아예 노출하지 않거나 allowlist에서 제외
- 리포팅 대상 프로젝트로 좁힌 접근. 조직 전체를 볼 수 있는 관리자 계정은 지양
- 만료·회전이 가능한 토큰. 장수명 개인 토큰보다 짧은 수명의 액세스 토큰 선호

```text
권장 스코프 (예시)
  projects:read      프로젝트 메타데이터 조회
  issues:read        이슈 목록·상세 조회
  journals:read      변경 이력·코멘트 조회
  users:read         사용자 표시 이름 매핑
  (issues:write, admin, delete 는 미부여)
```

Tool을 노출할 때도 리포팅 파이프라인에는 조회 계열만 등록합니다. Agent가 오작동하거나 프롬프트 주입에 노출되더라도, 애초에 쓰기 Tool이 없으면 데이터가 변형될 위험이 사라집니다. Tool allowlist와 신뢰 경계에 대한 상세 논의는 보안 시리즈를 참고하십시오.

## 4. OAuth 인가 호환성 문제 진단(일반화)

이 절은 **인가 경계 A**, 즉 MCP Client와 MCP Server(브리지) 사이의 인가를 다룹니다. 연결 초기에 가장 흔히 겪는 벽이 여기이며, 원인을 좁혀 나가며 해결했습니다. 3절의 업스트림 자격 증명(경계 B)과는 **별개의 자격 증명·별개의 대상(리소스)** 이라는 점을 먼저 못 박아 둡니다(반드시 서로 다른 인가 서버일 필요는 없고, 동일 IdP가 각 리소스용 토큰을 따로 발급할 수도 있습니다).

먼저 적용 조건입니다. MCP 인가는 **선택 사항(OPTIONAL)** 이며, 공식 인가 사양은 **HTTP 기반 전송**에 적용됩니다. STDIO 전송은 이 OAuth 흐름을 따르지 않고(SHOULD NOT) 환경(예: 환경 변수)에서 자격 증명을 얻습니다. 따라서 아래 설명은 "브리지를 HTTP 기반 인가로 노출할 때"를 전제로 합니다. 이 조건에서 MCP 서버는 보호 리소스로서 RFC 9728(OAuth 2.0 Protected Resource Metadata)을 구현해 인가 서버 위치를 알리고, 클라이언트는 이를 통해 인가 서버를 발견합니다. 기반 사양은 OAuth 2.1 IETF draft이며, 공개(public) 클라이언트가 많으므로 PKCE(`S256`)는 필수입니다. 세부 흐름(Discovery, PKCE, Resource Server 검증)은 MCP OAuth 2.1 글에서 별도로 다뤘습니다.

한 가지 핵심 요구사항을 못 박아 둡니다. 현재 공식 버전인 MCP 2026-07-28에서 클라이언트는 **RFC 8707(Resource Indicators)의 `resource` 파라미터를, 인가 요청과 토큰 요청 양쪽 모두에 포함해야(MUST)** 하며, 이 값은 토큰을 쓸 대상 MCP 서버의 정규 URI여야 합니다. 이 요구는 인가 서버가 해당 기능을 지원하는지와 무관하게 클라이언트가 항상 보내야 합니다. 그래야 발급된 토큰이 특정 리소스에 바인딩되어, 다른 서비스로 오용되거나 그대로 전달(패스스루)되는 것을 막을 수 있습니다.

메타데이터 발견 방식은 하나로 고정돼 있지 않습니다. 서버는 (1) 401 응답의 `WWW-Authenticate` 헤더에 `resource_metadata`를 담거나, (2) well-known URI(`/.well-known/oauth-protected-resource`)로 메타데이터를 제공합니다. 클라이언트는 헤더가 있으면 그 값을 쓰고, **없으면 well-known URI로 폴백**합니다. 즉 `WWW-Authenticate` 헤더가 항상 존재한다고 단정해서는 안 됩니다.

| 증상 | 흔한 원인 | 진단 포인트 |
| --- | --- | --- |
| 401 반복 | 토큰 만료·스코프 부족 | `WWW-Authenticate`가 있으면 `resource_metadata`, 없으면 well-known URI |
| 인가 서버를 못 찾음 | Protected Resource Metadata 미게시/오설정 | `/.well-known/oauth-protected-resource` 응답 검사 |
| 토큰은 발급되는데 거부됨 | audience(대상) 불일치 | 토큰이 이 MCP 서버(리소스)를 대상으로 발급됐는지(아래 참조) |
| 리다이렉트 실패 | redirect_uri 불일치·PKCE 누락 | 등록된 redirect_uri와 code_challenge 확인 |
| 간헐적 실패 | 시계 오차·토큰 캐시 | 서버·클라이언트 NTP, 토큰 만료 여유(clock skew) |

토큰 대상(audience) 검증은 JWT를 전제하지 않습니다. 액세스 토큰은 불투명(opaque) 토큰일 수 있으므로, "이 MCP 리소스를 대상으로 발급된 토큰인가"를 **`aud` 클레임 확인 또는 토큰 인트로스펙션 등 서버가 지원하는 방식**으로 검증합니다. 핵심은 MCP 서버가 자기 자신을 대상으로 발급된 토큰만 받고, 다른 리소스용 토큰을 받거나 그대로 흘려보내지(패스스루) 않는 것입니다.

진단할 때 유용했던 원칙은 "성공 응답이 아니라 실패 응답을 자세히 읽는다"였습니다. 401 응답에 `WWW-Authenticate` 헤더가 있으면 그 안의 `resource_metadata`로 인가 서버 발견을 시작할 수 있습니다. 다만 앞서 짚었듯 이 헤더가 항상 있는 것은 아니므로, 없으면 곧바로 well-known URI로 폴백해 같은 메타데이터를 조회합니다.

```text
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource",
                         scope="issues:read journals:read"
```

## 5. 데이터 모델 이해: 이슈, 저널, 변경 이력

리포트의 신뢰성은 데이터 모델을 정확히 이해하는 데서 시작합니다. 이슈 트래커의 활동은 크게 두 층위로 존재합니다.

```text
이슈(Issue)        현재 상태의 스냅샷
  ├─ 상태, 담당자, 우선순위, 마감일 ...
  └─ 최종 수정 시각 (updated_at)

저널(Journal)      이슈에 대한 "변경 이벤트"의 시계열
  ├─ 언제, 누가, 무엇을 바꿨는가 (상태 A→B, 담당자 변경 등)
  ├─ 코멘트 본문
  └─ 작업 시간(worklog) 기록 (있는 경우)
```

여기서 흔한 함정은 **이슈만 보고 활동을 세는 것**입니다. 이슈의 `updated_at`만으로 "이 사람이 오늘 무엇을 했는가"를 계산하면 부정확합니다. 하루에 한 이슈를 열 번 수정해도 `updated_at`은 하나이고, 마지막 수정자만 남으며, 트래커에 따라 "마지막 수정자"조차 저장하지 않습니다. 그래서 활동을 정확히 세려면 **지표별로 원천 이벤트를 먼저 정의하고, 변경 이력·코멘트·작업 시간 등을 필요한 범위에서 결합**해야 합니다. "저널만 세면 된다"는 단정은 위험한데, 제품마다 데이터 모델이 다르고 코멘트·작업시간·이슈 생성·첨부가 별도 엔드포인트인 트래커도 있기 때문입니다. 따라서 리포팅 수집은 이슈 목록뿐 아니라 각 지표의 원천 이벤트를 함께 가져오는 것을 전제로 설계합니다.

### 5.1 무엇을 "활동 1건"으로 정의하는가

리포트의 모든 숫자는 결국 "무엇을 1건으로 셌는가"에 달려 있습니다. 이 정의를 코드보다 먼저 표로 못 박아야, 뒤따르는 수집·집계·검증이 흔들리지 않습니다. 아래는 일반화한 지표 정의 예시입니다(제품에 맞게 조정).

| 지표 | 정의 | 제외 대상 | 중복 제거 키 |
| --- | --- | --- | --- |
| 상태 변경 | 사람이 상태를 실제로 변경한 이벤트 | 자동화·마이그레이션·대량 수정 | 시스템 ID + 이벤트 ID |
| 코멘트 | 비어 있지 않은 사용자 코멘트 등록 | 봇·서비스 계정·시스템 메시지 | 코멘트 ID |
| 작업 시간 | 승인된 작업시간 기록 | 취소·삭제·소급 무효 기록 | worklog ID |
| 완료 이슈 | 기간 중 완료 상태로 최초 진입 | 재오픈 후 중복 완료 | 이슈 ID + 상태 전이 |

여기서 두 가지를 함께 정한다는 점이 중요합니다. 첫째, **제외 대상**을 명시해 봇·서비스 계정·마이그레이션·대량 수정 이벤트가 사람의 활동으로 섞여 들지 않게 합니다(예: `import-bot` 계정, 일괄 상태 전이). 둘째, **중복 제거 키**를 정해 재시도로 같은 이벤트를 두 번 받아도 한 건으로 세도록 합니다.

그리고 이 숫자의 성격을 분명히 해 둡니다. **이벤트 건수는 운영 신호일 뿐, 생산성이나 개인 성과평가 지표가 아닙니다.** 상태를 여러 번 뒤집은 사람이 실제 성과가 큰 사람보다 높은 숫자를 얻을 수 있습니다. 리포트 본문과 각주에 이 경고를 함께 실어, 이벤트 건수가 인사 평가 근거로 단독 사용되지 않도록 합니다.

## 6. 범위 정의: 프로젝트·기간·명단의 3축 고정

신뢰할 수 있는 리포트의 출발점은 범위를 **명시적으로, 코드로** 고정하는 것입니다. "우리 팀"이나 "이번 주" 같은 말은 사람마다 다르게 해석되므로 반드시 식별자로 못 박습니다.

```json
{
  "report_scope": {
    "projects": ["PRJ-ALPHA", "PRJ-BETA"],
    "date_range": {
      "timezone": "Asia/Seoul",
      "start_inclusive": "2026-06-29T00:00:00+09:00",
      "end_exclusive": "2026-07-06T00:00:00+09:00",
      "iso_week": "2026-W27"
    },
    "roster_version": "roster-v8",
    "roster_interval_semantics": "[effective_from, effective_to)",
    "roster": [
      {"account": "u_1001", "effective_from": "2026-01-01", "effective_to": null},
      {"account": "u_1002", "effective_from": "2026-05-01", "effective_to": null},
      {"account": "u_1003", "effective_from": "2025-03-01", "effective_to": "2026-06-29"},
      {"account": "u_1004", "effective_from": "2026-01-01", "effective_to": null}
    ],
    "roster_policy": "fixed",
    "roster_members_total": 4,
    "roster_members_effective_in_range": 3,
    "out_of_scope_action": "exclude_and_log",

    "as_of": "2026-07-06T00:30:00+09:00",
    "as_of_reproducibility": "requires_source_point_in_time_read",
    "source_snapshot_hash": "sha256:… (예시)",
    "collector_version": "2.4.1",
    "metric_rule_version": "metrics-v3"
  }
}
```

- **프로젝트(projects)**: 프로젝트 표시 이름이 아니라 변하지 않는 식별자로 지정합니다. 표시 이름은 언제든 바뀔 수 있습니다.
- **기간(date_range)**: 시간대와 함께, 경계를 **반열림 구간 `[start_inclusive, end_exclusive)`** 로 명시합니다. 종료를 `23:59:59` 같은 닫힌 값으로 쓰지 않고 다음 날 `00:00:00`을 여는 값으로 둡니다. `interval` 문자열보다 시작·끝을 별도 필드로 두는 편이 기계 처리에 안전합니다(9절 참조). 위 예시는 ISO 주차 `2026-W27`(월~일: `[2026-06-29, 2026-07-06)`)에 정확히 대응합니다.
- **명단(roster)**: 현재 명단 하나가 아니라 **유효기간(`effective_from`/`effective_to`)이 있는 버전**으로 관리합니다. 유효기간도 날짜 경계와 마찬가지로 **반열림 구간 `[effective_from, effective_to)`** 로 해석합니다(즉 `effective_to` 당일부터는 명단 밖). 위 예시에서 `u_1003`은 `effective_to`가 `2026-06-29`이므로 리포트 기간(`[2026-06-29, 2026-07-06)`) 전체에서 대상이 아닙니다. 따라서 **명단에 4명이 있어도 이 기간의 유효 대상은 3명**입니다. 과거 기간을 리포트로 만들 때 "그때 명단"으로 대상 인원을 판정해야 하기 때문입니다(7~8절 참조). 명단 밖의 활동은 조용히 버리지 않고 "제외했음"을 건수와 함께 로그로 남깁니다.
- **원본 시점(as_of)·스냅샷·버전**: 같은 스코프라도 이슈가 사후 수정되면 원본이 달라지므로, "언제 본 데이터인가(`as_of` 또는 수집 워터마크)"와 원본 스냅샷 해시, 수집기 버전, 지표 규칙 버전을 함께 고정합니다. 다만 `as_of`를 적어 둔다고 데이터가 저절로 동결되지는 않습니다. 재현성은 이 시점·버전 집합에 더해, **원본이 그 시점 데이터를 실제로 보존·재조회할 수 있는 조건**(불변 export 보관, temporal/time-travel 조회, append-only 변경 로그·CDC 등)이 갖춰졌을 때 성립합니다(11절 참조).

이 스코프 객체는 리포트 상단과 실행 매니페스트에 그대로 인쇄됩니다. 리포트를 보는 사람이 "이 숫자가 어느 시점의 무엇을 담고 있는지"를 별도 설명 없이 알 수 있어야 하기 때문입니다.

## 7. 사용자·프로젝트 매핑: 계정에서 표시 이름으로

수집한 원본 데이터에는 사람 이름이 아니라 계정 식별자(예: `u_1002`)가 들어 있습니다. 리포트에는 사람이 읽을 수 있는 표시 이름이 필요하므로 매핑 테이블을 만듭니다. 이 매핑은 리포트의 "얼굴"이자, 잘못되면 가장 눈에 띄는 오류를 만드는 지점입니다.

| 계정 ID | 표시 이름(리포트용) | 상태 | 비고 |
| --- | --- | --- | --- |
| `u_1001` | 담당자 A | active | |
| `u_1002` | 담당자 B | active | |
| `u_1003` | 담당자 C | inactive | 이력 데이터에만 존재 |
| `u_1004` | 담당자 D | active | 이름 표기 중복 주의 |

매핑을 만들 때 지켜야 할 원칙은 다음과 같습니다.

- **계정 식별자를 키로 삼는다.** 이름은 중복·변경될 수 있으므로 표시 이름을 조인 키로 쓰지 않습니다.
- **표시 이름은 매핑 시점에 스냅샷한다.** 나중에 이름이 바뀌어도 과거 리포트의 표시가 흔들리지 않도록 합니다.
- **매핑에 없는 계정을 만나면 실패시키거나 명시적으로 표기한다.** 조용히 "알 수 없음"으로 뭉개면 집계가 왜곡됩니다.

## 8. 중복·퇴사자·명단 밖 활동 처리

실무에서 매핑을 어렵게 만드는 세 가지 현실이 있습니다.

### 8.1 동명이인·중복 표기

표시 이름이 같은 두 사람이 있을 수 있습니다. 리포트에서 이름만 보이면 활동이 뒤섞입니다. 계정 ID를 키로 유지하고, 표시 이름이 충돌하면 접미어(예: `담당자 D (팀1)`)로 구분합니다.

### 8.2 퇴사자·비활성 계정

과거 기간을 리포트로 만들면, 지금은 비활성인 계정의 활동이 데이터에 남아 있습니다. 이들을 어떻게 처리할지 정책을 정합니다.

```text
정책 예시
  - 과거 리포트: inactive 계정도 이력 표시 이름으로 노출 (활동은 실제로 있었으므로)
  - 현재 스냅샷 리포트(예: 열린 이슈 담당자): inactive 계정은 별도 "재배정 필요" 섹션으로
```

### 8.3 명단(roster) 밖 활동

고정 명단 밖의 계정이 대상 프로젝트에 활동을 남겼을 수 있습니다(외부 협력자, 다른 팀, 봇·서비스 계정 등). 이를 **조용히 버리면 어느 합계를 분모로 삼느냐에 따라 숫자가 어긋나** 리포트 신뢰성이 무너집니다. 그래서 하나의 합계로 뭉개지 않고, **수신 → 전송 중복 제거 → 지표 정책 제외 → 명단 내/밖 → 최종 보고**로 이어지는 대사(reconciliation) 수치를 **단계별로 상호 배타적으로** 남깁니다. 특히 봇·서비스 계정은 지표 정의(5.1절)의 "지표 정책 제외" 단계에서 한 번만 빠지며, 그 뒤의 `out_of_roster`에 다시 포함되지 않습니다.

```json
{
  "scope_reconciliation": {
    "raw_received_count": 149,
    "transport_duplicates": 7,
    "unique_source_count": 142,
    "metric_policy_exclusions": 7,
    "eligible_count": 135,
    "in_roster_count": 128,
    "out_of_roster_count": 7,
    "report_policy_exclusions": 0,
    "reported_count": 128,
    "out_of_roster_action": "excluded",
    "identities": {
      "note": "봇·서비스 계정은 metric_policy_exclusions에서 제외되며 out_of_roster에 중복 포함되지 않음",
      "example_bot_accounts": ["import-bot", "svc-sync"]
    },
    "note": "모든 수치는 합성 예시. 아래 대사식이 각주에 그대로 인쇄됨"
  }
}
```

위 수치는 모두 **합성 예시**입니다. 핵심은 각 단계를 서로 겹치지 않게 따로 세어 리포트 각주에 남기는 것이며, 사슬은 다음처럼 맞아떨어집니다.

```text
raw_received(149) - transport_duplicates(7) = unique_source(142)
unique_source(142) - metric_policy_exclusions(7) = eligible(135)
eligible(135) = in_roster(128) + out_of_roster(7)
reported(128) = in_roster(128) - report_policy_exclusions(0)
```

`raw_received_count`(재시도 중복 포함 수신량)와 `unique_source_count`(전송 중복 제거 후 논리적 원본 총량)를 구분하는 것이 중요합니다. 서버가 보고하는 `total`과 대사할 값은 후자입니다. 이렇게 단계를 분리해 두면 "왜 저 사람 활동이 안 보이지?"라는 질문에, 어느 단계에서 몇 건이 빠졌는지 즉시 답할 수 있습니다.

## 9. 날짜 범위 완전성과 시간대(TZ) 경계

리포팅에서 가장 조용하고 위험한 오류는 **경계에서 새는 데이터**입니다.

### 9.1 시간대 경계

이슈 트래커가 저장하는 타임스탬프는 대개 UTC입니다. 그러나 리포트의 "하루"는 사용자 시간대(예: `Asia/Seoul`) 기준입니다. 이 둘을 혼동하면 자정 근처의 활동이 엉뚱한 날짜에 잡힙니다.

```python
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # 고정 오프셋 대신 IANA 시간대(DST·오프셋 변경까지 반영)

SEOUL = ZoneInfo("Asia/Seoul")

def local_day_bounds(date_str: str):
    """지역 시간대 기준 하루의 [시작, 끝) 경계를 UTC로 변환해 반환."""
    start_local = datetime.fromisoformat(date_str + "T00:00:00").replace(tzinfo=SEOUL)
    end_local = start_local + timedelta(days=1)
    # 트래커 API에는 UTC 경계로 질의한다
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

# 예: Asia/Seoul 2026-07-01 하루 → UTC 2026-06-30T15:00 ~ 2026-07-01T15:00
start_utc, end_utc = local_day_bounds("2026-07-01")
```

`timezone(timedelta(hours=9))` 같은 고정 오프셋 대신 `ZoneInfo("Asia/Seoul")`를 쓰는 이유는, 서머타임이나 과거 오프셋 변경이 있는 지역에서도 날짜 경계가 올바르게 잡히도록 하기 위함입니다. 서울은 현재 DST가 없지만, 코드가 다른 지역으로 재사용될 때를 대비해 IANA 시간대를 기본으로 둡니다.

경계는 반드시 **반열림 구간 `[start, end)`** 로 다룹니다. `<= end`(닫힌 구간)를 쓰면 자정 정각 이벤트가 두 날에 중복 집계될 수 있습니다.

### 9.2 수집 대사: "빈 날짜 검사"는 완전성 증명이 아니다

수집이 도중에 끊기거나 페이지 하나를 빠뜨리면, 특정 날짜의 데이터가 통째로 비거나 일부만 담겨 리포트가 조용히 축소됩니다. 흔히 "날짜별 0건 검사"로 이걸 잡으려 하지만, **그것은 완전성 증명이 아닙니다.** 0건 검사는 빈 날짜만 볼 뿐, 데이터가 절반만 수집된 날과 진짜 무활동일을 구분하지 못하고, 수집 함수가 스스로 세운 "완료 플래그"는 자기 자신을 증명하지 못하는 독립적이지 않은 증거이기 때문입니다.

빈 날짜 표시는 리포트 표시상 여전히 유용하므로 유지하되, **이름을 "완전성 검증"이라 부르지 않습니다.** 이것은 대사(reconciliation)의 한 입력일 뿐입니다.

```python
def summarize_by_day(requested_days, collected_by_day):
    """날짜 축을 채워 표시용 요약을 만든다. (완전성 증명이 아니라 표시 보조)"""
    rows = []
    for day in requested_days:
        count = len(collected_by_day.get(day, []))
        rows.append({"date": day, "events": count, "empty": count == 0})
    return rows
```

완전성은 **명시된 원본 API 계약 범위 안에서** 서로 다른 통제값끼리 대사(control total)해 판단합니다. 여기서 한계를 정직하게 짚어 둡니다. 서버가 보고한 `total`과 페이지 사슬은 수집 결과보다 강한 통제값이지만, **동일한 가변 API 응답에서 얻은 값이라면 완전히 독립적인 증거는 아닙니다.** 이미 삭제된 이벤트, 권한 때문에 애초에 보이지 않는 데이터, 원본이 잘못 계산한 `total` 자체는 이 대사로 탐지되지 않습니다. 그래서 이것은 "절대적 완전성 증명"이 아니라 **"명시된 원본 계약 범위에서의 대사 검증"** 입니다.

```python
def reconcile_endpoint(collected, server_total, page_chain):
    """단일 엔드포인트의 수집 결과를 그 엔드포인트가 보고한 총량·페이지 사슬과 대사.
    (완전성 '증명'이 아니라, 명시된 API 계약 범위 안의 대사 검증)"""
    checks = {
        # 1) API가 보고한 total vs 실제 수집·중복 제거 수
        "server_total": server_total,
        "raw_received_count": len(collected),
        "unique_source_count": len({e["id"] for e in collected}),
        # 2) 커서 체인이 처음~끝까지 끊김 없이 이어졌는가(외부 관찰)
        "pages_expected": page_chain["expected"],
        "pages_seen": page_chain["seen"],
        "cursor_chain_intact": page_chain["intact"],
    }
    checks["count_reconciled"] = checks["unique_source_count"] == server_total
    checks["chain_ok"] = (page_chain["seen"] == page_chain["expected"]
                          and page_chain["intact"])
    # 이름을 'verified'가 아니라 'count_reconciled'로 낮춰 부른다(한계 명시)
    checks["reconciled"] = checks["count_reconciled"] and checks["chain_ok"]
    return checks
```

이슈·코멘트·작업시간이 서로 다른 엔드포인트로 나뉜 트래커라면 **단일 `server_total`은 성립하지 않습니다.** 엔드포인트·지표별로 각각 대사한 뒤(위 `reconcile_endpoint`), 8.3절의 단계별 사슬로 합산해 전체를 맞춰야 합니다. 즉 다음을 서로 맞춰봅니다.

- 각 엔드포인트가 보고한 `total`, 페이지 수, 커서 체인 — 수집기 밖에서 관찰한 값
- 수신 → 전송 중복 제거 → 지표 정책 제외 → 명단 내/밖 → 최종 보고의 사슬(8.3절)
- 가능하면 별도 count API나 시간 구간별 control total(같은 응답에 의존하지 않는 두 번째 관측)
- 동일 `as_of` 스냅샷 또는 안정적인 고수위 워터마크(수집 중 원본이 움직여도 기준이 흔들리지 않도록)

빈 날짜가 나오면 그것이 **진짜로 활동이 없었던 날**인지, 아니면 **수집이 실패한 날**인지는 위 대사 결과로 갈립니다. `reconciled`가 아니면 "지난주 금요일에 아무 일도 안 했다"는 잘못된 결론을 내리는 대신 리포트 생성을 중단합니다.

## 10. 페이지네이션과 안정적 수집

이슈·저널은 한 번의 응답에 다 담기지 않으므로 페이지네이션으로 나눠 가져옵니다. 먼저 층위를 구분해야 합니다. **MCP 계층의 페이지네이션(MCP Client↔Server)과 이슈 트래커 API의 페이지네이션(브리지↔트래커)은 서로 다른 계약**입니다. 한 가지 오해를 바로잡아 둡니다. MCP 표준의 커서 페이지네이션은 `tools/list`·`resources/list`·`resources/templates/list`·`prompts/list` 같은 **목록(list) 연산**에만 정의됩니다. `tools/call`(즉 Tool 호출)의 결과를 페이지로 나누는 것은 표준 기능이 아니라 **그 Tool의 입출력 스키마가 별도로 정하는 애플리케이션 계약**입니다. 즉 "MCP Tool 페이지네이션"이 표준으로 보장되는 것처럼 다루면 안 됩니다. 그 뒤의 트래커 API는 오프셋 기반일 수도, 커서 기반일 수도 있습니다. 대사는 결국 원본을 쥔 트래커 API의 총건수를 기준으로 삼아야 하므로, 두 층위 중 어느 쪽 `total`·커서를 보고 있는지 항상 의식합니다.

흔한 함정과 대응은 다음과 같습니다.

- **오프셋 이동 중 데이터 변경**: 수집하는 동안 원본이 바뀌면 오프셋 기반 페이지네이션은 항목을 건너뛰거나 중복시킵니다. 가능하면 커서(cursor) 기반이나 안정 정렬 키(생성 시각 + ID)를 씁니다.
- **부분 수집을 완료로 착각**: 마지막 페이지까지 받았는지 명확히 확인하지 않으면 일부만 담긴 채 리포트가 만들어집니다. 그래서 "커서 소진"만이 아니라 **서버가 보고한 `total`과 실제 건수를 대사**합니다.
- **재시도 중 중복 응답**: 타임아웃 후 재시도하면 같은 페이지가 두 번 들어올 수 있으므로, ID 기준으로 **멱등하게 중복을 제거**합니다.
- **커서 만료**: 커서에는 수명이 있어, 중간에 만료되면 처음부터 다시 받아야 할 수 있습니다. 만료를 감지해 `reconciled=False`로 되돌립니다.
- **레이트 리밋**: `429` 응답의 `Retry-After`를 존중하고, 지수 백오프에 지터(jitter)를 더하며, 최대 재시도 횟수를 둡니다.

```python
def collect_all(fetch_page, scope, *, max_pages=10_000):
    """페이지네이션을 끝까지 소진하며 대사에 필요한 근거를 함께 기록(개념 코드).
    수집기는 스스로 'verified'를 세우지 않는다. 반환값은 대사 단계에서 판정한다."""
    by_id, cursor, pages = {}, None, 0
    seen_cursors = set()                          # 커서 순환 감지
    server_total = None
    total_stable = True                           # total이 페이지마다 흔들렸는지
    content_conflicts = 0                         # 같은 ID의 내용이 페이지마다 다른지
    while True:
        page = fetch_page(scope, cursor=cursor)   # 재시도·백오프는 fetch_page가 담당
        if page.get("cursor_expired"):            # 커서 만료 → 불완전으로 판정
            return {"items": [], "reconciled": False, "reason": "cursor_expired"}
        # total은 '있을 때만' 채택하고, 값이 바뀌면 불안정으로 기록(마지막 값으로 덮지 않음)
        page_total = page.get("total")
        if page_total is not None:
            if server_total is not None and page_total != server_total:
                total_stable = False
            server_total = server_total if server_total is not None else page_total
        for item in page["items"]:
            prev = by_id.get(item["id"])
            if prev is not None and prev != item:
                content_conflicts += 1            # 같은 ID인데 내용이 다름(원본 변동 신호)
            by_id[item["id"]] = item              # 재시도 중복은 ID로 흡수(멱등)
        pages += 1
        cursor = page.get("next_cursor")
        if not cursor:                            # 마지막 페이지 도달
            break
        if cursor in seen_cursors or pages >= max_pages:
            return {"items": [], "reconciled": False, "reason": "cursor_cycle_or_overrun"}
        seen_cursors.add(cursor)
    items = list(by_id.values())
    # 아래는 '대사 후보' 신호일 뿐. 최종 판정은 reconcile_endpoint()가 한다.
    count_reconciled = server_total is not None and len(items) == server_total
    return {
        "items": items,
        "pages_fetched": pages,
        "server_total": server_total,
        "raw_received_count": None,               # 재시도 중복 포함 수는 fetch_page 계층에서 집계
        "unique_source_count": len(items),
        "count_reconciled": count_reconciled,
        "total_stable": total_stable,             # False면 스냅샷 일관성 의심
        "content_conflicts": content_conflicts,   # >0이면 수집 중 원본이 움직였을 수 있음
    }
```

이 코드는 `count_reconciled`(건수 대사) 외에 **`total_stable`(페이지마다 `total`이 흔들리지 않았는가)** 와 **`content_conflicts`(같은 ID 내용이 페이지 간에 달라졌는가)** 를 별도 신호로 남깁니다. 커서가 스냅샷 일관성을 보장한다는 API 계약이 없으면 건수가 맞아도 완전성을 단정할 수 없기 때문입니다. 스냅샷 일관성·커서 연속성·`total` 불변성은 서로 다른 필드로 두고, 최종 판정은 대사 단계에서 종합합니다.

아래는 `requests`/`httpx` 계열(응답의 `.status_code`, 예외는 `RequestException`)을 전제로 한 **개념 코드**입니다. 실제로는 사용하는 HTTP 라이브러리의 속성·예외 타입에 맞춰야 합니다.

```python
import email.utils
import random
import time

# 일시적(재시도 가능) 상태 코드. 4xx 중 429/408만 재시도, 나머지 4xx는 재시도 안 함.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _parse_retry_after(value):
    """Retry-After는 정수 '초' 또는 HTTP-date 둘 다 가능. 둘 다 처리."""
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    parsed = email.utils.parsedate_to_datetime(value)   # HTTP-date 형식
    if parsed is None:
        return None
    delay = parsed.timestamp() - time.time()
    return max(0.0, delay)


def fetch_with_backoff(call, *, max_attempts=5, base=0.5, cap=30.0):
    """일시 오류·네트워크 예외에 Retry-After 존중 + 지터 백오프.
    max_attempts는 '총 시도 횟수'(최초 1회 포함). 성공은 그대로 반환."""
    for attempt in range(max_attempts):          # attempt: 0 .. max_attempts-1
        try:
            resp = call()
        except RequestException:                 # 네트워크 예외도 재시도 대상
            if attempt == max_attempts - 1:
                raise
            time.sleep(min(cap, base * (2 ** attempt)) * (0.5 + random.random()))
            continue
        if resp.status_code not in RETRYABLE_STATUS:
            return resp                           # 2xx뿐 아니라 401/403/404 등도 그대로 반환(상위 판단)
        if attempt == max_attempts - 1:
            break
        delay = _parse_retry_after(resp.headers.get("Retry-After"))
        if delay is None:
            delay = min(cap, base * (2 ** attempt)) * (0.5 + random.random())
        time.sleep(min(cap, delay))
    raise RuntimeError("max_attempts_exceeded")   # 상위에서 리포트 생성 중단 처리
```

수집 결과의 `count_reconciled`(및 `total_stable`·`content_conflicts`)는 수집기가 스스로 세우는 자기 선언이 아니라 **서버 `total`·페이지 사슬과 대사한 결과**입니다. 검증 단계는 이들이 모두 만족되지 않으면(또는 커서 스냅샷 일관성 계약이 없으면) 리포트 생성을 중단합니다. **불완전한 리포트를 만드느니 만들지 않는 편**이 낫습니다.

## 11. 집계와 멱등·결정론·재현성

이 세 단어는 자주 뒤섞여 쓰이지만 서로 다른 성질이며, 리포팅에서는 셋을 구분해야 논리가 무너지지 않습니다.

- **멱등성(idempotence)**: 같은 실행을 반복해도 중복 부작용(중복 파일, 중복 알림)이 생기지 않는다.
- **결정론(determinism)**: 동일한 입력이면 동일한 출력이 나온다. 이벤트 정렬·타이브레이크로 **표시 순서**를 고정하는 것이 여기에 해당한다.
- **재현성(reproducibility)**: 같은 **원본 스냅샷·규칙 버전·수집기 버전**으로 결과를 다시 만들 수 있다. 단 이는 **원본이 그 시점 데이터를 실제로 보존·재조회할 수 있을 때**에 한한다(아래 참조).

주의할 점은, 정렬을 결정론적으로 만든다고 해서 단순 건수 집계의 **재현성**이 저절로 보장되지는 않는다는 것입니다. 이슈가 사후 수정되거나 작업 시간이 소급 등록되면 같은 기간의 원본이 달라지므로, 스코프만으로는 같은 숫자가 나오지 않습니다. 그래서 재현성은 6절의 `as_of`·스냅샷 해시·`collector_version`·`metric_rule_version`에 고정합니다. "지금"에 의존하지 않는다는 원칙(예: `to` 경계를 넘긴 데이터는 항상 제외)도 이 고정의 일부입니다.

다만 여기서 과장하지 않는 것이 중요합니다. **`as_of`와 스냅샷 해시만으로는 재현이 보장되지 않습니다.** `as_of`는 "언제 기준으로 조회했는가"를 기록할 뿐, 원본 시스템이 과거시점 조회를 지원하지 않으면 데이터를 동결하지 못합니다. 해시는 이미 보관 중인 스냅샷의 무결성을 확인할 뿐, 해시만으로 원본을 복원할 수는 없습니다. 커서·고수위 워터마크도 삭제·수정·소급 등록이 가능한 원본에서는 자동으로 스냅샷 의미를 갖지 않습니다. 따라서 재현성은 다음 중 하나가 갖춰졌을 때 **그 조건 아래에서** 성립한다고 표현해야 정확합니다.

- 불변 원본 export를 실제로 보관하거나
- temporal/time-travel 조회를 지원하는 원본이거나
- append-only 변경 로그 또는 CDC로 시점 복원이 가능하거나
- 스냅샷 일관성을 보장하는 API 계약과 고정 워터마크가 있을 때

```python
from datetime import date, datetime


def _parse_ts(value: str) -> datetime:
    """ISO 8601 문자열을 aware datetime으로 파싱.
    문자열을 그대로 정렬하면 오프셋 표기가 섞일 때 실제 시간순과 어긋난다."""
    dt = datetime.fromisoformat(value)           # 예: "2026-07-02T09:30:00+09:00"
    if dt.tzinfo is None:
        raise ValueError(f"naive timestamp not allowed: {value}")
    return dt


def _effective_on(entry: dict, when: date) -> bool:
    """반열림 구간 [effective_from, effective_to)로 명단 유효 여부 판정."""
    ef = date.fromisoformat(entry["effective_from"])
    et = entry["effective_to"]
    if when < ef:
        return False
    if et is not None and when >= date.fromisoformat(et):   # effective_to 당일부터 제외
        return False
    return True


def aggregate(events, roster):
    """계정별 활동 이벤트 수를 '표시 순서 결정론적으로' 집계(개념 코드).
    - roster는 {account, effective_from, effective_to} 객체의 '목록'이다.
    - 재현성 자체는 as_of 스냅샷·규칙 버전·원본 보존 조건으로 성립한다(본문 참조)."""
    order = [r["account"] for r in roster]        # 표시 순서(명단 순서) 고정
    by_account = {r["account"]: r for r in roster}
    counts = {acct: 0 for acct in order}
    seen = set()
    # 시각→ID 순으로 결정론적 정렬(문자열이 아니라 파싱한 datetime으로)
    for e in sorted(events, key=lambda x: (_parse_ts(x["ts"]), x["id"])):
        # 여러 이벤트 종류에서 ID가 충돌할 수 있으므로 복합 키로 중복 제거
        key = (e["source"], e["event_type"], e["id"])
        if key in seen:
            continue
        seen.add(key)
        entry = by_account.get(e["actor"])
        if entry is None:                         # 명단 밖은 제외(별도 집계)
            continue
        # 이벤트 발생 '당시' 명단에 유효했는지 확인(그때 명단으로 판정)
        if not _effective_on(entry, _parse_ts(e["ts"]).date()):
            continue
        counts[e["actor"]] += 1
    return counts
```

산출물 관리에서는 **멱등 갱신과 감사 보존을 분리**합니다. 재실행 시 같은 파일을 덮어쓰기만 하면 감사 추적과 충돌하기 때문입니다.

- **사용자용 최신본**: 안정적 별칭(예: `report_PRJ-ALPHA_2026-W27_latest.html`)으로 멱등하게 갱신하되, **검증(대사)에 성공한 산출물만 원자적으로 교체**합니다(임시 파일에 쓴 뒤 rename). 대사에 실패하면 기존 `latest`를 그대로 두지 않고, 최신본에 `data_as_of`와 신선도 상태(예: `stale`/`failed`)를 함께 표기해 **낡은 리포트가 최신처럼 보이지 않게** 합니다.
- **감사용 불변본**: 실행마다 `as_of`·매니페스트·스냅샷 해시를 포함한 **버전별 파일**로 보존하고 덮어쓰지 않습니다. 파일명에 `as_of`만 넣으면 **동일 스냅샷 재실행 시 이름이 충돌**하므로, `run_id`나 매니페스트 해시를 함께 넣습니다(예: `report_..._asof-20260706T0030_run-7f3a9c.html`).
- 이전 실행 대비 산출 수치가 달라졌다면 그 차이를 감지해 감사 로그에 남깁니다.

## 12. 집계 근거와 감사 추적

리포트의 숫자 옆에는 항상 **근거로 되돌아갈 수 있는 실마리**가 있어야 합니다. "담당자 B: 12건"이라는 숫자를 보고 관리자가 "어떤 12건이냐"고 물을 때, 원본 이슈 목록으로 즉시 연결되어야 합니다.

```json
{
  "aggregate": {
    "actor": "u_1002",
    "display_name": "담당자 B",
    "event_count": 12,
    "evidence": {
      "issue_ids": ["I-3011", "I-3012", "I-3020"],
      "journal_ids": ["J-88", "J-91", "J-104"],
      "note": "예시 식별자. 실제 값은 내부 감사 저장소에만 보관"
    }
  }
}
```

위 식별자는 모두 **합성 예시**입니다. 실무에서는 근거가 되는 원본 식별자를 리포트 본문에 노출하지 않고, 별도 감사 저장소에 두고 링크나 참조 키로만 연결하는 편이 안전합니다. 리포트 본문에는 집계 수치와 그 산출 기준(스코프·시간대·정렬 규칙)만 담고, 원본으로의 추적은 통제된 경로로 제공합니다. 감사 추적과 개인정보 최소화의 균형에 대한 상세 논의는 감사 로그 시리즈를 참고하십시오.

개별 집계뿐 아니라 **실행 전체**에 대한 근거도 하나의 매니페스트로 남깁니다. 이 매니페스트가 있으면 "이 리포트는 어느 시점의 원본을, 어떤 수집기·규칙 버전으로, 몇 건을 받아 몇 건을 보고했는가"에 한 번에 답할 수 있습니다.

```json
{
  "report_id": "weekly-2026-W27",
  "run_id": "run-7f3a9c",
  "scope_version": "scope-v3",
  "roster_version": "roster-v8",
  "metric_rule_version": "metrics-v3",
  "template_version": "tmpl-v5",
  "schema_version": "schema-v2",
  "renderer_version": "renderer-1.9.0",
  "as_of": "2026-07-06T00:30:00+09:00",
  "collector_version": "2.4.1",
  "raw_received_count": 149,
  "unique_source_count": 142,
  "metric_policy_exclusions": 7,
  "eligible_count": 135,
  "in_roster_count": 128,
  "out_of_roster_count": 7,
  "reported_count": 128,
  "snapshot_hash": "sha256:… (예시)",
  "artifact_hash": "sha256:… (예시)",
  "reconciliation_status": "count_reconciled",
  "reproducibility": "conditional_on_source_point_in_time_read"
}
```

위 수치는 모두 **합성 예시**입니다. `raw_received → unique_source → eligible → (in_roster + out_of_roster) → reported`의 사슬과 `as_of`·`snapshot_hash`·`artifact_hash`가 함께 있으므로, 같은 리포트를 나중에 (원본 보존 조건 아래) 재현하거나 감사할 때 이 매니페스트 하나가 기준점이 됩니다. 상태는 "완전성 검증됨(verified)"이 아니라 **`count_reconciled`(명시된 API 계약 범위에서 건수가 대사됨)** 로 정직하게 표기하고, 재현성도 원본의 과거시점 조회 조건에 걸린 조건부임을 명시합니다. 원본 데이터 버전뿐 아니라 `template_version`·`schema_version`·`renderer_version`과 산출물 해시(`artifact_hash`)까지 함께 남겨야, 렌더러·의존성이 바뀌어 표시가 달라진 경우도 구분됩니다.

## 13. 민감정보 처리: 무엇을 남기고 무엇을 지울까

이슈 트래커의 데이터에는 개인정보와 기밀이 섞여 있습니다. 이슈 제목에 고객사명·계약 조건이 들어 있고, 코멘트에 사람 이름과 연락처가 있으며, 담당자 필드 자체가 개인정보입니다. 리포트를 자동 생성한다는 것은 **이 민감정보가 새 저장소로 복제된다**는 뜻이므로, 목적에 맞게 최소화해야 합니다.

기본 원칙은 **목적 기반 최소 노출**입니다. 리포트의 목적이 "누가 얼마나 활동했는가"라면 이슈 제목 전문이나 코멘트 본문은 대개 필요하지 않습니다.

| 데이터 | 내부용 리포트 | 외부 공유용 리포트 |
| --- | --- | --- |
| 담당자 표시 이름 | 표시 | 가명처리(담당자 A/B/C) |
| 이슈 제목 | 요약/일부 표시 | 카테고리·유형만 표시 |
| 코멘트 본문 | 미포함(건수만) | 미포함 |
| 작업 시간(worklog) | 합계 표시 | 합계·구간만 |
| 고객사·계약 정보 | 마스킹 | 완전 제거 |

리포트를 만들기 전에 **처리 목적·법적 근거·열람 대상·보관 기간**을 먼저 정합니다. 특히 개인별 활동 리포트는 성격상 직원 모니터링에 해당할 수 있으므로, 직원 활동 데이터를 처리하는 **법적 근거**(예: 정당한 이익 또는 근로계약·내부 규정), 조직의 개인정보 처리방침과 근로자 감시 관련 내부 규정에 부합하는지 확인하고, 5.1절의 "이벤트 건수는 성과평가 지표가 아니다"라는 한계도 함께 명시합니다. 또한 외부 요약 모델·클라우드에 데이터를 넘긴다면 **위탁·제3자 제공·국외 이전 여부와 그 근거**, 그리고 **모델 제공자의 저장·학습·보존 정책**(입력이 학습에 쓰이는지, 보존 기간은 얼마인지)까지 사전에 검토합니다. 목적에 필요 없는 필드는 애초에 수집·복제하지 않는 것이 가장 안전한 최소화입니다.

## 14. 요약·마스킹·가명처리 기법

민감정보 처리는 세 가지 층위로 나눠 적용하되, **순서**가 중요합니다. 특히 외부 모델(LLM)로 원문을 보내는 경우, 마스킹은 모델 투입 **전에** 이뤄져야 합니다. 요약 뒤에만 마스킹하면 원문 개인정보가 이미 모델 제공자에게 전달된 뒤이기 때문입니다.

```text
데이터 처리 경계(권장 순서)
  원문 → 사전 DLP/마스킹 → 승인된 모델·폐쇄형 실행 → 구조화 요약
       → 사후 DLP/마스킹 → 외부 공유 전 재식별 위험 검증
```

즉 외부·비승인 모델에는 원문을 보내지 않고, 사전 마스킹을 통과한 텍스트만 넘깁니다. 조직 정책상 원문을 모델에 보낼 수 없다면 규칙 기반 요약(라벨·카테고리 필드)만으로 처리하고 자유 텍스트는 건수만 남깁니다.

### 14.1 마스킹(masking)

값의 형태는 유지하되 식별력을 제거합니다. 이메일·전화·계정처럼 패턴이 뚜렷한 값에 적합합니다.

```python
import re

def mask_obvious_pii(text: str) -> str:
    """패턴이 뚜렷한 일부 PII만 가리는 보조 수단(개념 코드).
    이 정규식만으로 '빠짐없이' 가릴 수 없다 — 아래 한계 참조."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    text = re.sub(r"01[016789]-?\d{3,4}-?\d{4}", "[phone-kr-mobile]", text)
    return text

# "문의: user@example.com / 010-0000-0000"  (예시는 명백한 비실재 값)
#  → "문의: [email] / [phone-kr-mobile]"
```

이런 정규식은 **완전한 방어가 아닙니다.** 위 패턴은 국제전화(`+82`), 공백·점 구분 번호, 일반전화, 국제화 이메일, 그리고 이름·회사명·주소 같은 비정형 식별자를 잡지 못합니다. 따라서 "마스킹이 이메일·전화·계정을 빠짐없이 가린다"고 단정하지 않으며, 정규식은 어디까지나 보조 수단으로 두고 승인된 DLP/검증 단계를 함께 씁니다.

### 14.2 요약(summarization)

원문 대신 유형·범주만 남깁니다. 이슈 제목 "A고객사 결제 오류 긴급 대응"은 리포트에서 "결제/장애 대응"으로 범주화됩니다. 요약은 규칙 기반(라벨·카테고리 필드 활용)을 우선하고, 자유 텍스트에만 승인된 모델 요약을 보조로 씁니다. 모델 요약을 쓸 때도 위 처리 경계대로 **사전 마스킹 → 모델 → 사후 마스킹**을 지켜, 요약 결과에 개인정보가 되살아나지 않도록 합니다.

### 14.3 가명처리(pseudonymisation)

외부 공유용에서는 표시 이름을 안정적 가명으로 치환합니다. 같은 사람은 항상 같은 가명이 되도록 매핑을 고정하되, 그 역매핑 테이블은 리포트와 분리해 별도 통제 구역에 둡니다.

```json
{
  "pseudonymisation_map": {
    "u_1001": "담당자 A",
    "u_1002": "담당자 B"
  },
  "storage_note": "역매핑은 리포트와 분리, 접근 통제 구역에만 보관(예시)"
}
```

여기서 용어를 정확히 씁니다. 역매핑 테이블을 보관한 채 `담당자 A`로 바꾸는 것은 **익명화가 아니라 가명처리(pseudonymisation)** 입니다. 한국 개인정보 보호법에서 **가명정보는 개인정보의 정의에 포함**되므로, "개인정보에 해당할 수 있다"가 아니라 **"개인정보에 해당한다"** 가 정확합니다. 따라서 가명정보는 익명화된 데이터처럼 다뤄서는 안 되며, 개인정보 보호법상 가명정보 처리 기준(목적 제한·안전조치·결합 제한 등)을 적용합니다. 또한 표시 이름을 단순히 `담당자 A/B`로 치환한다고 해서 법적 의미의 가명처리가 저절로 성립하는 것도 아닙니다. 특히 4명 규모의 작은 조직에서는 활동 패턴·순서만으로 쉽게 추론될 수 있습니다. 진짜 익명화는 **합리적으로 가용한 시간·비용·기술과 다른 정보의 결합 가능성까지 고려해도** 되돌릴 수 없어야 성립하며, "기술적으로 영원히 불가능"이라는 절대적 기준으로 판단하지 않습니다.

외부 공유 전에는 **재식별 위험을 한 번 더 검토**합니다. 가명을 붙였더라도 소수 집단은 조합만으로 특정될 수 있으므로, 셀 인원이 적은 집계는 억제(소수 셀 suppression)하거나 희귀 카테고리를 상위 범주로 통합하고, 근무 시간·특이 활동 패턴처럼 간접 식별 단서가 남지 않는지 확인합니다. 위 예시처럼 대상이 3~4명뿐이라면 개인별 표는 외부 공유에서 아예 억제하고 집단 합계만 남기는 편이 안전합니다.

## 15. 산출물: 독립 실행형 UTF-8 HTML 리포트

결과물은 **어디서나 열리고, 인쇄되며, 외부 의존이 없는** 단일 HTML 파일로 만듭니다. 이 선택에는 분명한 이유가 있습니다.

- **오프라인·이식성**: 사내망이든 개인 PC든 브라우저만 있으면 열립니다. 외부 CDN·스크립트에 의존하지 않으므로 폐쇄망에서도 동작합니다.
- **인쇄·보관**: CSS `@media print`로 종이·PDF 출력에 최적화하고, 그대로 아카이브합니다.
- **유출면 축소(보안의 전부는 아님)**: 외부 리소스 호출이 없으므로 데이터가 링크를 타고 나갈 여지는 줄어듭니다. 다만 **단일 HTML이라는 사실만으로 안전해지지는 않습니다.** 이슈 제목이나 표시 이름을 이스케이프하지 않으면, 원본에 심긴 마크업이 저장형 HTML/스크립트 주입으로 실행될 수 있습니다.

그래서 산출 단계에서 다음을 함께 적용합니다.

- **텍스트 노드 이스케이프**: 원본에서 온 모든 문자열(이슈 제목·표시 이름·코멘트 파생 값)은 `&`, `<`, `>`, `"`, `'`를 이스케이프해 텍스트로만 렌더링합니다.
- **active content 금지 + CSP**: 인라인 스크립트·이벤트 핸들러·외부 스크립트를 넣지 않고, `Content-Security-Policy` 메타로 스크립트를 차단합니다.
- **URL 스킴 allowlist**: 링크를 넣는다면 `https:`(또는 필요한 사내 스킴)만 허용하고 `javascript:` 등은 거부합니다.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;
                 base-uri 'none'; form-action 'none';">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>주간 활동 리포트 (예시)</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; color: #1a1a1a; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    caption { text-align: left; font-weight: 600; margin-bottom: 6px; }
    th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
    .scope { background: #f5f5f5; padding: 12px; border-radius: 6px; }
    @media print { body { margin: 0; } .no-print { display: none; } }
  </style>
</head>
<body>
  <h1>주간 활동 리포트 (예시)</h1>
  <div class="scope">
    범위: PRJ-ALPHA, PRJ-BETA · 기간: [2026-06-29, 2026-07-06) (Asia/Seoul, 2026-W27)
    · 명단 4명 중 유효 대상 3명
    · 수신 149건 → 중복 제거 142건 → 정책 제외 후 대상 135건
      → 명단 내 128건 보고(명단 밖 7건 제외) · as_of 2026-07-06T00:30:00+09:00
  </div>
  <table>
    <caption>담당자별 활동 (예시)</caption>
    <thead>
      <tr><th scope="col">담당자</th><th scope="col">활동 건수</th></tr>
    </thead>
    <tbody>
      <!-- 값은 서버 원본을 이스케이프한 뒤 삽입 -->
    </tbody>
  </table>
</body>
</html>
```

CSV는 보조 산출물로 함께 제공하되, 원본이 아니라 **집계 결과**를 담습니다. CSV에는 별도의 방어가 필요합니다.

- **수식 주입(CSV injection) 방어**: `=`, `+`, `-`, `@`(및 탭·캐리지리턴)로 시작하는 셀은 스프레드시트에서 수식으로 실행될 수 있으므로, 앞에 작은따옴표를 붙이는 등으로 무력화합니다.
- **인코딩**: BOM은 Excel에서 UTF-8을 올바로 열기 위한 호환 옵션일 뿐, 완전성·보안 대책이 아닙니다. 필요 시 Excel 호환을 위해 BOM을 붙이되 보안 대책과 혼동하지 않습니다.

## 16. 리포트 구성 요소와 레이아웃

리포트는 위에서 아래로 "무엇을 담았는지 → 요약 → 상세 → 각주"의 순서를 지킵니다.

```text
[머리말]  스코프 요약 (프로젝트·기간·시간대·인원·제외 건수)
[요약]    핵심 지표 카드 (총 활동, 완료, 진행 중 ...)
[개인별]  담당자별 활동 표 (표시 이름·건수·유형 분포)
[유형별]  카테고리별 분포 (규칙 기반 라벨)
[추이]    날짜별 활동 (빈 날짜는 명시)
[각주]    데이터 완전성·제외 정책·생성 시각·재현 조건
```

각 표는 "합계 행"을 두고, 개별 항목의 합이 합계와 일치함을 눈으로 확인할 수 있게 합니다. 다만 **개인별 합과 유형별 합은 정상적으로도 다를 수 있습니다.** 한 이벤트가 여러 카테고리에 걸치거나, 미분류가 있거나, 한 이슈에 복수 변경이 있으면 유형별 합이 개인별 합과 달라지는 것이 자연스럽습니다. 그러므로 "합이 다르면 곧 결함"이 아니라, **어느 축이 중복 집계(예: 다중 카테고리)를 허용하는지 각주에 명시**하고, 중복을 허용하지 않기로 한 축에서만 불일치를 결함 신호로 다룹니다. 신뢰의 기준이 되는 것은 8.3절의 단계별 대사 사슬(수신 → 중복 제거 → 정책 제외 → 명단 안팎 → 보고)입니다.

## 17. 자동화 오류 처리와 부분 실패

자동화는 성공보다 실패를 잘 다뤄야 오래갑니다. 리포팅 파이프라인에서 실패는 크게 세 종류입니다.

| 실패 유형 | 예시 | 대응 |
| --- | --- | --- |
| 연결 실패 | 인증 만료, 네트워크, `429` | `Retry-After` 존중·지터 백오프·최대 재시도, 초과 시 미생성·알림 |
| 부분 수집 | 페이지 누락, 커서 만료, TZ 경계 누락 | 수집 대사(control total) 불일치 시 차단, 원인 로깅 |
| 매핑 실패 | 매핑에 없는 계정 | 명시적 표기 또는 중단(정책에 따라) |

핵심 원칙은 **"조용히 잘못된 리포트를 내지 않는다"** 입니다. 부분 실패가 감지되면 그럴듯하지만 틀린 리포트를 만드는 대신, 실패 사실과 원인을 명확히 남기고 생성을 중단합니다. 잘못된 숫자가 회의 자료로 올라가는 것이 빈 리포트보다 훨씬 비쌉니다. 복구 가능한 Agent 워크플로우 설계는 관련 글에서 별도로 다룹니다.

## 18. 정기 스케줄과 운영

리포트는 매일/매주 정해진 시각에 자동 생성되도록 스케줄링합니다. 운영 관점의 체크리스트는 다음과 같습니다.

```text
스케줄 운영 체크리스트
  [ ] 실행 시각을 리포트 기간 종료 이후로 (예: 지역 시간 익일 오전)
  [ ] 실행마다 스코프·as_of·대사 수치·매니페스트를 로그로 남김
  [ ] 실패 시 담당자에게 알림 (성공은 조용히, 실패는 시끄럽게)
  [ ] 예정 시각에 산출물이 없으면 경보 (dead-man alert: 스케줄러 자체 미실행 탐지)
  [ ] 토큰 만료 임박 시 사전 경고 (경계 A·B 각각)
  [ ] 산출물 보관 기간·접근 통제 정책 적용 (최신본/감사본 분리)
  [ ] 스코프·명단 변경은 유효기간 있는 버전으로 관리
  [ ] 지연 입력·사후 정정에 대한 수정본 정책 (확정 마감 시점·재발행 규칙)
```

스케줄 실행에서 **최신본은 멱등하게 갱신**하되, **감사본은 실행별로 불변 보존**합니다. 같은 기간을 재실행해도 사용자용 별칭은 덮어쓰이고, 감사용 버전은 쌓이며 변경분이 감지되어야 합니다(11절).

작업시간이 뒤늦게 등록되거나 이슈가 사후 정정되는 일은 흔하므로, **수정본 정책**을 미리 정합니다. 각 리포트에 `revision` 번호와, 이전 리포트를 대체할 때 `supersedes_report_id`를 남기고, "이 시점 이후 입력은 다음 회차에 반영한다"는 **확정 마감(cut-off) 시점**을 명시합니다. 그래야 같은 주차 리포트가 여러 번 갱신돼도 어느 것이 최신 확정본인지 감사할 수 있습니다.

## 19. 통합 테스트: 리포트를 믿기 위한 검증

리포팅 파이프라인도 코드이므로 테스트가 필요합니다. 다만 일반 단위 테스트보다 **데이터 계약(data contract) 검증**의 성격이 강합니다.

```text
테스트 항목 (예시)
  1) 스코프 밖 데이터가 결과에 포함되지 않는가
  2) TZ 경계 근처 이벤트가 올바른 날짜에 집계되는가 (반열림 [start,end))
  3) 명단 밖 활동이 제외되고 단계별 대사 사슬(8.3절)이 각주에 남는가
  4) 같은 as_of 스냅샷·규칙 버전으로 두 번 실행 시,
     정규화된 산출물(생성 시각 등 비결정 필드 제외) 또는 핵심 지표가 동일한가
  5) 서버 total과 수집 건수를 어긋나게 주입하면(=대사 불일치) 차단되는가
  6) 재시도로 중복 응답을 주입해도 복합 키 기준으로 한 건으로 집계되는가
  7) 사전 마스킹을 통과하지 않은 원문이 외부 모델로 나가지 않는가
  8) 이슈 제목에 <script> 등 마크업을 넣어도 이스케이프되어 실행되지 않는가
  9) CSV 셀이 =,+,-,@ 로 시작할 때 수식으로 실행되지 않도록 무력화되는가
     (실제 대상 Excel/LibreOffice에서 회귀 확인)
 10) 소수 셀 억제가 적용되어 외부 공유본에서 재식별 단서가 남지 않는가
 11) 명단 유효기간을 벗어난 계정의 활동이 그 기간 집계에서 제외되는가
 12) API 스키마 변경·필드 누락·권한 축소를 데이터 계약 테스트가 탐지하는가
 13) 스케줄러 미실행(예정 산출물 부재)을 dead-man 경보가 잡는가
```

자연어 기반 MCP Tool 호출의 통합 테스트 방법론은 별도 글에서 상세히 다뤘으므로, 여기서는 리포트 특유의 검증 항목만 정리했습니다. 특히 (4) 재현성 테스트는 두 실행의 HTML을 정규화(생성 시각 등 비결정 필드 제외) 후 비교하거나 핵심 지표만 비교해 자동화합니다. "동일 산출물"을 통째로 비교하는 것이 아니라 **비결정 필드를 배제한 정규화본 또는 핵심 지표가 같은지**를 봅니다. 마스킹은 "빠짐없이 가린다"를 단정할 수 없으므로(14.1절), 테스트는 완전성 주장 대신 **알려진 케이스 목록에 대한 회귀 검증**과 위 (7)의 데이터 경계 검증으로 구성합니다. (12)~(13)은 코드 자체보다 **파이프라인이 놓인 환경**을 지키는 계약 테스트로, 원본 API가 조용히 바뀌거나 스케줄러가 실행되지 않아 낡은 리포트가 최신처럼 남는 사고를 막습니다.

## 20. 도입 판단 체크리스트(의사결정자용)

이 자동화를 조직에 도입할지 판단할 때 확인할 질문들입니다.

| 질문 | 확인 |
| --- | --- |
| 리포팅 자격 증명(경계 B)은 읽기 전용 최소 권한인가? | ⬜ |
| 활동 1건의 정의·제외 대상·복합 중복 키가 표로 고정되는가? | ⬜ |
| 스코프에 `as_of`·스냅샷 해시·수집기/규칙/템플릿 버전이 포함되는가? | ⬜ |
| 재현성 주장이 "원본 보존/과거시점 조회 조건"으로 제한되는가? | ⬜ |
| 명단이 반열림 유효기간(`[from,to)`) 버전으로 관리되는가? | ⬜ |
| 서버 total과의 수집 대사(control total)가 검증되고, 그 한계가 명시되는가? | ⬜ |
| 시간대 경계가 반열림 `[start,end)`으로 처리되는가? | ⬜ |
| 단계별 대사 사슬(수신→중복 제거→정책 제외→명단 안팎→보고)이 각주에 남는가? | ⬜ |
| 외부 모델 투입 전 사전 마스킹, 출력 후 재검사가 되는가? | ⬜ |
| 외부 모델의 저장·학습·보존 정책과 국외 이전 근거를 검토했는가? | ⬜ |
| 외부 공유용 가명처리·역매핑 분리·소수 셀 억제가 되는가? | ⬜ |
| HTML 이스케이프·CSP(`base-uri`/`form-action` 포함)·CSV 수식 주입 방어가 적용되는가? | ⬜ |
| 최신본은 검증 성공 시에만 원자적으로 교체되고 신선도가 표기되는가? | ⬜ |
| 감사본 파일명에 `run_id`/매니페스트 해시가 포함되어 충돌하지 않는가? | ⬜ |
| 부분 실패 시 조용히 틀린 리포트를 내지 않는가? | ⬜ |
| dead-man 경보와 지연 입력·수정본 정책이 있는가? | ⬜ |
| 이벤트 건수를 개인 성과평가 지표로 쓰지 않음을 명시하는가? | ⬜ |
| 직원 데이터 처리의 법적 근거·보관·접근 통제·모니터링 정책이 있는가? | ⬜ |

## 21. 마무리: 자동화의 가치는 "다시 확인하지 않아도 됨"에 있다

이슈 트래커를 MCP로 연결해 리포트를 자동 생성하는 일에서 어려운 부분은 데이터를 가져오는 코드가 아니었습니다. 진짜 노력은 **그 숫자를 믿을 수 있게 만드는 것** — 무엇을 1건으로 셀지 정의하고, 범위와 원본 시점을 못 박고, 원본과 대사(reconciliation)해 새지 않았음을 증거로 보이고, 명단 안팎을 정직하게 세고, 민감정보를 목적에 맞게 다루고, 같은 스냅샷·규칙 버전이면 같은 결과가 나오게 하는 것 — 에 들어갔습니다.

여기서 신뢰 모델을 다시 새깁니다. 신뢰할 수 있는 리포트는 "빈 날짜가 없는 리포트"가 아니라, **고정된 원본 시점(as-of)과 수집 대사 증거를 가진 리포트**입니다. 다만 `as_of`를 적는 것 자체가 재현을 보장하지는 않으며, **원본이 그 시점 데이터를 실제로 보존·재조회할 수 있는 조건**에서만 재현이 성립합니다. 또 대사는 "절대적 완전성 증명"이 아니라 명시된 API 계약 범위 안의 검증입니다. 빈 날짜는 대사 결과의 한 입력일 뿐이고, 정작 중요한 것은 "어느 시점의 원본을, 몇 건 받아, 몇 건 보고했는가"를 매니페스트로 되짚을 수 있느냐입니다.

자동 리포트의 성패는 "얼마나 빨리 만드는가"가 아니라 **"관리자가 원본 화면을 다시 열지 않는가"** 로 판가름 납니다. 그 신뢰를 확보한 순간, 매일 사람이 화면을 열어 숫자를 옮겨 적던 반복 업무가 사라지고, 사람은 숫자를 **해석하는 일**에 시간을 쓸 수 있게 됩니다. 단, 그 숫자는 **운영 신호이지 개인 성과평가 지표가 아니라는** 전제 위에서만 그렇습니다.

## 22. 상호 참조 및 공식 참고 자료

이 글은 리포팅 자동화 특화 내용에 집중했습니다. 아래 주제는 재설명하지 않았으니 연계 글을 참고하십시오.

- MCP Tool 설계 원칙: https://aiarchitect.tistory.com/3
- MCP OAuth 2.1 (Discovery·PKCE·Resource Server): https://aiarchitect.tistory.com/11
- MCP 통합 테스트(자연어 Tool 호출 검증): https://aiarchitect.tistory.com/14
- 민감정보·감사 로그 처리: https://aiarchitect.tistory.com/27

공식 참고 자료(확인 기준일: 2026-07-30). 현재 공식 프로토콜 버전은 `2026-07-28`이며, 이 글의 MCP 구조와 인가 요구사항도 이 버전을 기준으로 다시 확인했습니다. `2025-11-25` 이하 구현은 초기화·세션 방식 등 프로토콜 세대가 다르므로, 실제 연동 시 지원 버전과 하위 호환 경로를 별도로 확인해야 합니다.

- Model Context Protocol Specification (2026-07-28): https://modelcontextprotocol.io/specification/2026-07-28
- MCP Authorization Specification (2026-07-28): https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
- MCP Pagination (2026-07-28, 목록 연산 한정): https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination
- MCP 버전 정책: https://modelcontextprotocol.io/docs/learn/versioning
- RFC 9728 — OAuth 2.0 Protected Resource Metadata: https://datatracker.ietf.org/doc/html/rfc9728
- RFC 8414 — OAuth 2.0 Authorization Server Metadata: https://datatracker.ietf.org/doc/html/rfc8414
- RFC 8707 — Resource Indicators for OAuth 2.0: https://www.rfc-editor.org/rfc/rfc8707.html
- OAuth 2.1 — MCP 2026-07-28이 기준으로 삼은 판본은 draft-13: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13
- OAuth 2.1 — 현재 최신 초안은 draft-15(참고): https://datatracker.ietf.org/doc/draft-ietf-oauth-v2-1/
- RFC 7636 — PKCE (Proof Key for Code Exchange): https://datatracker.ietf.org/doc/html/rfc7636
- JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
- 가명처리와 익명화의 차이 (ICO): https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/pseudonymisation/
- 개인정보 보호법 제2조(정의): https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030669293
- 개인정보보호위원회 가명정보 처리 가이드라인: https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS289&mCode=D040070000&nttId=10433
