# Tistory 기술자료 초안

- 문서 ID: `BLOG-03`
- 상태: 공개 완료
- 공개 URL: https://aiarchitect.tistory.com/3
- 분류: `AI Agent · MCP`
- 작성 기준: MCP `2026-07-28` 사양
- 권장 제목: `기업용 MCP Tool 설계 원칙: 이름, 설명, 입력 스키마와 권한 경계`
- 검색 설명: `기업용 MCP Tool을 모델이 정확히 선택하고 서버가 안전하게 실행하도록 만드는 이름, 설명, JSON Schema, 권한, 승인, 출력과 오류 설계 원칙을 예제로 정리합니다.`
- 권장 태그: `MCP`, `Model Context Protocol`, `Tool Calling`, `JSON Schema`, `AI Agent`, `권한 설계`, `엔터프라이즈 AI`

---

# 기업용 MCP Tool 설계 원칙: 이름, 설명, 입력 스키마와 권한 경계

MCP Server에 Tool을 많이 등록한다고 AI Agent의 업무 수행 능력이 자동으로 좋아지지는 않습니다.

모델이 비슷한 Tool 사이에서 잘못된 기능을 선택하거나, 필수 인자를 빠뜨리거나, 조회 요청에 변경 Tool을 호출한다면 Tool 개수는 오히려 혼란을 키웁니다. 반대로 Tool의 이름과 설명, 입력·출력 스키마, 권한 경계가 명확하면 비교적 단순한 Agent도 안정적으로 업무 기능을 사용할 수 있습니다.

MCP Tool은 단순한 API 래퍼가 아닙니다. 모델에게는 선택 가능한 행동의 계약이고, 사용자에게는 실제 시스템에 영향을 주는 실행 경계이며, 서버에게는 반드시 검증해야 하는 외부 입력입니다.

이번 글에서는 기업용 MCP Tool을 설계할 때 실무에서 먼저 정해야 할 기준을 살펴보겠습니다.

## Tool 개수보다 업무 경계가 먼저다

기존 REST API의 엔드포인트를 그대로 Tool로 옮기는 방식은 시작하기 쉽습니다. 그러나 API가 개발자 관점에서 나뉘어 있고 실제 사용자 업무와 경계가 다르다면 모델은 어떤 Tool을 언제 호출해야 하는지 판단하기 어렵습니다.

다음과 같은 Tool 하나에 여러 동작을 넣는 경우가 대표적입니다.

```json
{
  "name": "manage_data",
  "description": "데이터를 관리합니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "action": { "type": "string" },
      "target": { "type": "string" },
      "value": {}
    }
  }
}
```

이 정의에는 세 가지 문제가 있습니다.

1. 이름만 보고 대상 업무와 위험도를 알 수 없습니다.
2. `action`, `target`, `value`의 가능한 조합이 지나치게 많습니다.
3. 조회, 수정, 삭제에 같은 권한과 승인 정책이 적용되기 쉽습니다.

Tool은 모델이 이해할 수 있는 업무 단위로 나누는 편이 좋습니다.

```text
meetings_search
meeting_get
meeting_summary_get
issue_create
issue_status_update
meeting_delete
```

이렇게 나누면 모델의 선택지가 명확해지고, Tool별로 권한·승인·감사 정책을 다르게 적용할 수 있습니다. 다만 하나의 사용자 작업을 수행하는 데 지나치게 많은 저수준 Tool이 필요하다면 반대 문제가 생깁니다. 좋은 경계는 “API 한 번”이 아니라 “사용자가 의미 있게 요청하는 한 단계의 업무”를 기준으로 정합니다.

## 1. 이름은 도메인과 동작을 함께 표현한다

MCP `2026-07-28` 사양에서 Tool 이름은 1자 이상 128자 이하이며, 영문자·숫자·밑줄·하이픈·마침표를 사용할 수 있습니다. 이름은 대소문자를 구분하고 Server 안에서 고유해야 합니다.

형식 제약을 지키는 것만으로 충분하지는 않습니다. `get`, `search`, `execute`처럼 일반적인 단어 하나보다 도메인과 동작을 함께 드러내는 이름이 좋습니다.

| 피해야 할 이름 | 권장 이름 | 이유 |
|---|---|---|
| `get` | `meeting_summary_get` | 무엇을 조회하는지 명확함 |
| `search` | `meetings_search` | 검색 대상이 드러남 |
| `update` | `issue_status_update` | 변경 범위를 상태로 제한함 |
| `execute_action` | `report_export_request` | 실행 결과와 업무 목적을 알 수 있음 |

프로젝트 안에서는 `domain_action` 또는 `action_domain` 중 하나를 선택해 일관되게 사용해야 합니다. 여기서는 목록에서 같은 도메인의 Tool이 모이도록 `domain_action` 형식을 사용했습니다.

여러 MCP Server의 Tool을 한 Host에서 합치는 경우에는 이름 충돌도 고려해야 합니다. Server 내부에서 고유하더라도 서로 다른 Server가 같은 이름을 제공할 수 있으므로 Host가 Server 식별자를 포함해 구분하거나 충돌 해결 규칙을 가져야 합니다.

## 2. Description은 모델을 위한 선택 기준이다

Tool 설명은 사람에게 보여 주는 API 주석에 그치지 않습니다. 모델이 사용자 의도와 Tool을 연결할 때 사용하는 핵심 정보입니다.

좋은 설명에는 최소한 다음 내용이 포함돼야 합니다.

- 무엇을 하는가
- 언제 사용해야 하는가
- 비슷한 Tool 대신 언제 사용하지 말아야 하는가
- 데이터 변경이나 외부 전송 같은 부수 효과가 있는가
- 필요한 권한이나 사용자 확인은 무엇인가
- 성공 결과와 주요 실패 조건은 무엇인가

예를 들어 “회의 정보를 조회합니다”보다 다음 설명이 선택 기준을 더 분명하게 제공합니다.

```text
지정한 회의의 승인된 AI 요약을 조회합니다.
원문 녹취록이 필요하면 meeting_transcript_get을 사용하세요.
데이터를 변경하지 않는 읽기 전용 Tool이며,
사용자가 접근할 수 있는 조직과 회의인지 서버에서 다시 검증합니다.
```

설명이 길다고 항상 좋은 것은 아닙니다. 모델이 선택에 필요한 차이와 중요한 제약을 빠르게 찾을 수 있도록 문장을 짧고 구체적으로 유지해야 합니다. 실제로 강제해야 하는 보안 규칙은 설명에만 의존하지 않고 서버 코드와 정책 계층에서 적용해야 합니다.

## 3. Input Schema는 가능한 값을 좁혀야 한다

최신 MCP Tool 사양은 입력 스키마의 기본 dialect로 JSON Schema `2020-12`를 사용합니다. `inputSchema`는 유효한 객체 스키마여야 하며 `null`일 수 없습니다.

입력이 없는 Tool도 빈 객체를 명시하는 방식이 권장됩니다.

```json
{
  "type": "object",
  "additionalProperties": false
}
```

입력이 있다면 자유 형식 문자열을 넓게 받기보다 실제 업무 규칙을 스키마에 표현합니다.

```json
{
  "type": "object",
  "properties": {
    "meetingId": {
      "type": "string",
      "minLength": 1,
      "description": "조회할 회의의 불투명 식별자"
    },
    "language": {
      "type": "string",
      "enum": ["ko", "en"],
      "default": "ko",
      "description": "요약 결과 언어"
    }
  },
  "required": ["meetingId"],
  "additionalProperties": false
}
```

실무에서는 다음 항목을 점검합니다.

- 정말 필요한 값만 `required`로 지정했는가
- 고정 선택지는 `enum`으로 제한했는가
- 문자열 길이와 숫자 범위에 상한이 있는가
- 날짜·시간·식별자의 형식이 명확한가
- 의미 없는 추가 필드를 허용하지 않는가
- 기본값이 사용자의 의도를 바꾸지 않는가

JSON Schema 검증을 통과했다고 업무 요청이 유효한 것은 아닙니다. 존재하지 않는 레코드, 허용되지 않은 상태 전이, 다른 조직의 식별자, 마감된 업무의 변경처럼 데이터와 권한을 확인해야 알 수 있는 조건은 별도의 업무 규칙으로 검증해야 합니다.

모델이 생성한 Tool 인자는 신뢰할 수 없는 외부 입력으로 취급하는 것이 안전합니다.

## 4. 조회·변경·위험 작업을 분리한다

기업 시스템에서는 같은 도메인이라도 작업의 영향도에 따라 Tool을 나누는 것이 중요합니다.

| 구분 | 예시 | 기본 통제 |
|---|---|---|
| 조회 | `meetings_search`, `meeting_summary_get` | 접근 권한 확인, 결과 범위 제한 |
| 생성 | `issue_create` | 입력 검증, 중복 방지, 감사 |
| 변경 | `issue_status_update` | 현재 상태 확인, 사용자 확인, 멱등 처리 |
| 위험 작업 | `meeting_delete` | 명시적 승인, 실행 직전 재인가, 복구 정책 |

모델이 “필요 없어진 회의를 정리해 줘”라는 문장을 해석했다고 해서 곧바로 삭제를 실행해서는 안 됩니다. 삭제 대상과 영향 범위를 사용자에게 보여 주고 확인을 받은 다음, Server가 실행 시점의 권한을 다시 검사해야 합니다.

MCP 사양도 Tool이 모델에 의해 선택될 수 있다는 점을 전제로, 애플리케이션이 사용자에게 사용 가능한 Tool을 명확히 보여 주고 실행 표시와 확인 절차를 제공하도록 권고합니다. 특히 실제 데이터나 외부 시스템에 영향을 주는 작업은 Human-in-the-loop를 제품 흐름의 일부로 설계해야 합니다.

## 5. Tool 목록과 실행 권한은 별개의 경계다

권한이 없는 Tool을 처음부터 모델에 노출하지 않으면 잘못된 선택과 정보 노출을 줄일 수 있습니다. MCP 사양에서는 요청별 인가 상태에 따라 `tools/list` 결과가 달라질 수 있습니다.

예를 들어 조회 권한만 있는 사용자에게는 조회 Tool만 제공하고, 관리자에게만 삭제 Tool을 노출할 수 있습니다. 하지만 목록 필터링만으로 인가가 끝나는 것은 아닙니다.

모든 `tools/call` 요청에서 다음 항목을 다시 검증해야 합니다.

```text
요청 사용자
  └─ 소속 조직 또는 테넌트
      └─ Tool 실행 권한
          └─ 대상 레코드 접근 권한
              └─ 현재 상태에서 허용된 동작
```

모델이 알고 있는 레코드 ID나 앞선 대화에서 받은 값은 권한 증명이 아닙니다. 식별자는 가능하면 의미를 추측하기 어려운 불투명 값으로 사용하고, Server가 매 호출마다 사용자·테넌트·대상 데이터의 관계를 확인해야 합니다.

Tool annotations로 읽기 전용 여부나 파괴적 작업 여부 같은 힌트를 전달할 수 있지만, 이 값은 UI와 모델의 판단을 돕는 메타데이터입니다. 실제 권한과 승인 정책은 Server와 Host의 신뢰 경계 안에서 강제해야 합니다.

## 6. 출력은 사람과 프로그램이 함께 사용할 수 있어야 한다

Tool 결과를 긴 자연어 문장 하나로만 반환하면 모델은 읽을 수 있지만, 후속 Tool 호출이나 UI 렌더링에서 필요한 값을 다시 추출해야 합니다. 반대로 구조화 데이터만 반환하면 이를 지원하지 않는 Client에서 활용하기 어려울 수 있습니다.

MCP Tool은 `outputSchema`와 `structuredContent`를 통해 구조화된 결과를 정의할 수 있습니다. 호환성을 위해 같은 핵심 내용을 텍스트 형태로도 제공하는 방식을 고려할 수 있습니다.

```json
{
  "structuredContent": {
    "meetingId": "opaque-meeting-id",
    "status": "ready",
    "summary": "결정사항과 후속 업무가 포함된 요약"
  },
  "content": [
    {
      "type": "text",
      "text": "요약 준비가 완료되었습니다."
    }
  ]
}
```

출력 필드는 이름과 의미를 안정적으로 유지하고, Server는 선언한 `outputSchema`에 결과가 맞는지 검사해야 합니다. 대량 목록이나 원문 전체를 한 번에 반환하기보다 페이지 크기와 결과 수를 제한하고, 다음 조회에 필요한 커서나 식별자를 제공하는 편이 안전합니다.

민감정보는 모델이 필요로 하는 범위만 반환합니다. 내부 URL, 접근 토큰, 저장소 경로, 원본 시스템의 불필요한 메타데이터가 Tool 결과에 포함되지 않도록 출력 단계에서도 필터링이 필요합니다.

## 7. 오류는 모델이 다음 행동을 결정할 수 있게 만든다

MCP Tool 오류는 크게 두 종류로 구분할 수 있습니다.

- 알 수 없는 Tool, 잘못된 요청 형식 같은 프로토콜 오류
- 입력값, 권한, 업무 상태, 외부 API 실패 같은 Tool 실행 오류

사용자가 수정할 수 있는 입력 문제나 업무 규칙 위반은 `isError: true`인 Tool 실행 결과로 돌려주고, 모델이 다음 요청을 고칠 수 있는 정보를 제공하는 것이 좋습니다.

```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "현재 상태에서는 완료로 변경할 수 없습니다. 먼저 담당자를 지정하세요."
    }
  ]
}
```

“처리 실패”처럼 원인을 알 수 없는 문구보다 실패한 필드, 허용되는 값, 필요한 선행 작업을 알려 주는 오류가 Agent의 자기 교정에 유리합니다.

다만 상세 오류에 내부 스택, SQL, 비밀정보, 다른 사용자의 데이터가 포함돼서는 안 됩니다. 사용자에게 전달할 메시지와 운영자가 확인할 내부 로그를 분리하고, 양쪽을 연결할 추적 ID를 제공하는 방식이 적절합니다.

## 8. 재시도되는 쓰기 Tool은 멱등성을 고려한다

AI Agent의 Tool 호출은 네트워크 시간 초과, Client 재시도, Workflow 재개로 인해 같은 요청이 다시 전달될 수 있습니다. 생성이나 상태 변경 Tool이 요청마다 새 동작을 수행하면 중복 이슈, 중복 알림, 잘못된 상태 전이가 발생할 수 있습니다.

쓰기 Tool에는 필요에 따라 다음 값을 포함합니다.

- `idempotencyKey`: 같은 업무 요청의 중복 실행 방지
- `expectedVersion`: 조회 이후 다른 변경이 있었는지 확인
- `reason`: 변경 목적과 감사 근거
- `requestId`: 로그와 분산 추적 연결

예를 들어 상태 변경 Tool은 다음처럼 정의할 수 있습니다.

```json
{
  "name": "issue_status_update",
  "description": "지정한 업무의 상태만 변경합니다. 변경 전 사용자 확인이 필요하며 제목이나 본문은 수정하지 않습니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "issueId": {
        "type": "string",
        "minLength": 1
      },
      "targetStatus": {
        "type": "string",
        "enum": ["in_progress", "blocked", "completed"]
      },
      "expectedVersion": {
        "type": "integer",
        "minimum": 1
      },
      "reason": {
        "type": "string",
        "minLength": 1,
        "maxLength": 500
      },
      "idempotencyKey": {
        "type": "string",
        "minLength": 16,
        "maxLength": 128
      }
    },
    "required": [
      "issueId",
      "targetStatus",
      "expectedVersion",
      "reason",
      "idempotencyKey"
    ],
    "additionalProperties": false
  }
}
```

멱등성 키를 입력에 추가하는 것만으로 중복 방지가 완성되지는 않습니다. Server가 키와 요청 본문을 안전하게 저장하고, 같은 키에 다른 요청이 들어오는 경우 거부하며, 보존 기간과 재처리 정책을 정해야 합니다.

## 읽기 Tool 설계 예시

앞선 기준을 적용한 읽기 Tool은 다음처럼 구성할 수 있습니다.

```json
{
  "name": "meeting_summary_get",
  "title": "회의 AI 요약 조회",
  "description": "지정한 회의의 준비 완료된 AI 요약을 조회합니다. 원문 녹취록 조회에는 사용하지 않습니다. 데이터를 변경하지 않으며 서버가 사용자의 조직 및 회의 접근 권한을 검증합니다.",
  "inputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "meetingId": {
        "type": "string",
        "minLength": 1,
        "description": "조회할 회의의 불투명 식별자"
      }
    },
    "required": ["meetingId"],
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "meetingId": { "type": "string" },
      "status": {
        "type": "string",
        "enum": ["ready", "processing"]
      },
      "summary": { "type": "string" }
    },
    "required": ["meetingId", "status"],
    "additionalProperties": false
  },
  "annotations": {
    "readOnlyHint": true,
    "destructiveHint": false
  }
}
```

이 Tool은 이름만으로 대상과 동작을 알 수 있고, 설명은 요약과 녹취록의 선택 기준을 제공합니다. 입력 범위는 하나의 식별자로 제한했으며, 출력도 후속 처리에 사용할 수 있도록 구조화했습니다.

실제 구현에서는 `meetingId`가 존재하는지뿐 아니라 현재 사용자가 해당 회의에 접근할 수 있는지를 확인해야 합니다. `readOnlyHint`가 있다고 해서 Server의 인가 검사가 생략되는 것은 아닙니다.

## 운영 전 점검 체크리스트

| 점검 항목 | 확인 질문 |
|---|---|
| 업무 경계 | Tool 하나가 사용자가 이해할 수 있는 한 단계의 업무를 수행하는가 |
| 이름 | 도메인과 동작이 드러나며 다른 Tool과 쉽게 구분되는가 |
| 설명 | 사용 시점, 제외 조건, 부수 효과와 주요 실패 조건이 있는가 |
| 입력 스키마 | 필수값, 선택값, 범위, 형식과 추가 필드 정책이 명확한가 |
| 업무 검증 | JSON Schema 밖의 상태·소유권·조직 규칙을 검사하는가 |
| 읽기·쓰기 분리 | 조회, 생성, 변경, 삭제의 권한과 승인이 분리됐는가 |
| 목록 필터링 | 사용자 권한에 맞는 Tool만 발견되도록 구성했는가 |
| 실행 인가 | 모든 호출에서 사용자·테넌트·대상 권한을 다시 확인하는가 |
| 출력 계약 | 구조화 결과가 안정적이며 불필요한 민감정보를 제거했는가 |
| 오류 | 모델이 수정하거나 다음 행동을 선택할 수 있는 메시지인가 |
| 재시도 | 쓰기 작업의 멱등성, 버전 충돌과 중복 실행을 처리하는가 |
| 감사 | 요청자, 승인, 대상, 결과와 추적 ID를 안전하게 기록하는가 |

## 마무리

기업용 MCP Tool의 품질은 Tool 개수보다 계약의 명확성과 실행 통제에서 결정됩니다.

핵심을 정리하면 다음과 같습니다.

1. Tool은 모호한 범용 기능이 아니라 의미 있는 업무 단위로 나눕니다.
2. 이름과 설명은 모델이 올바른 Tool을 선택할 수 있는 차이를 제공해야 합니다.
3. 입력은 JSON Schema로 좁히고, Server에서 업무 규칙과 권한을 다시 검증합니다.
4. 조회·변경·위험 작업을 분리하고 영향이 큰 작업에는 명시적 승인을 둡니다.
5. 출력과 오류는 모델의 다음 행동, UI, 감사와 운영 추적까지 고려해 설계합니다.
6. 재시도될 수 있는 쓰기 작업은 멱등성과 버전 충돌을 처리해야 합니다.

결국 좋은 MCP Tool은 AI에게 강력한 기능을 많이 주는 인터페이스가 아니라, 허용된 기능을 예측 가능하고 검증 가능한 방식으로 실행하게 만드는 인터페이스입니다.

다음 글에서는 회의 음성이 녹취록과 요약을 거쳐 검색 가능한 지식으로 바뀌고, 다시 업무 Tool Calling으로 연결되는 RAG 파이프라인을 살펴보겠습니다.

---

## 참고 자료

- [MCP 2026-07-28 Tools 사양](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [MCP 2026-07-28 아키텍처](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)
- [JSON Schema 2020-12 기본 dialect 명세](https://modelcontextprotocol.io/seps/1613-establish-json-schema-2020-12-as-default-dialect-f)
- [Tool 이름 형식 명세](https://modelcontextprotocol.io/seps/986-specify-format-for-tool-names)
- [입력 검증 오류 처리 명세](https://modelcontextprotocol.io/seps/1303-input-validation-errors-as-tool-execution-errors)
- [MCP 2026-07-28 릴리스 안내](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)

> 이 글은 2026년 7월 29일 기준 MCP `2026-07-28` 공식 사양을 바탕으로 작성했습니다. 실제 구현에서는 사용 중인 Host, Client와 SDK가 해당 사양의 기능을 지원하는지 함께 확인해야 합니다.
