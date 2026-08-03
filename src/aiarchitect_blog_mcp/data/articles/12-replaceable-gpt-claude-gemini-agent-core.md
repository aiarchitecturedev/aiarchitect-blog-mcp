# 멀티 LLM Agent Core 설계: GPT·Claude·Gemini를 교체 가능한 Provider로 연결하기

AI Agent를 처음 만들 때는 특정 모델의 SDK를 직접 호출하는 방식이 가장 빠릅니다.

```python
response = provider_sdk.generate(
    model=model_name,
    messages=messages,
    tools=tools,
)
```

문제는 두 번째 모델을 연결할 때 시작됩니다.

- System 지시를 넣는 위치가 다릅니다.
- Message와 콘텐츠 블록 (Content Block)의 구조가 다릅니다.
- 도구 호출 (Tool Call)과 도구 결과 (Tool Result)를 연결하는 ID가 다릅니다.
- 스트리밍 이벤트 (Streaming Event)의 시작·증분·완료 순서가 다릅니다.
- 정상 종료, 길이 제한, 안전 차단과 Tool 요청을 표현하는 값이 다릅니다.
- 토큰 사용량 (Token Usage)과 캐시 토큰 (Cache Token)의 항목이 다릅니다.
- 모델 제공자 (Provider)가 대화를 보관하는 방식과 무상태 (Stateless) 호출 방식이 다릅니다.

이 차이를 에이전트 실행 반복문 (Agent Loop) 곳곳의 `if provider == ...`로 처리하면 모델 교체가 쉬워지는 것이 아니라 Core 전체가 Provider별 분기문으로 변합니다.

교체 가능한 구조는 **모든 모델을 가장 작은 공통 기능으로 축소하는 것**도 아닙니다. 공통 계약 (Common Contract)은 안정적으로 유지하되, 모델별 고유 기능은 기능 행렬 (Capability Matrix)과 확장 영역 (Extension Field)으로 명시해야 합니다.

```text
User · REPL · TUI · API
          │
          ▼
      Agent Core
  ┌─────────────────────┐
  │ Session · Memory    │
  │ Tool · Permission   │
  │ Skill · Hook        │
  │ Sub-agent · Trace   │
  └──────────┬──────────┘
             │ Common Contract
      ┌──────┼──────────────┐
      ▼      ▼              ▼
   OpenAI  Anthropic      Google
   Adapter  Adapter       Adapter
      │      │              │
      ▼      ▼              ▼
     GPT   Claude         Gemini
```

## 1. “교체 가능”의 범위를 먼저 정의한다

모델 교체 가능성 (Model Portability)은 여러 단계로 나뉩니다.

| 단계 | 의미 | 예시 |
|---|---|---|
| 설정 교체 | 같은 Core에서 Provider와 Model 설정을 바꿈 | 개발 환경은 A, 검증 환경은 B |
| 기능 교체 | Text·Tool·Streaming 같은 공통 기능이 동작 | 같은 Tool Loop를 세 Provider에서 실행 |
| 결과 교체 | 품질·형식·안전 정책까지 같은 수준을 유지 | 고정 평가 세트 통과 |
| 운영 교체 | 비용·지연·Rate Limit·장애 대응을 포함 | 장애 시 승인된 Fallback 실행 |

첫 번째 단계만 구현하고 “모델을 자유롭게 바꿀 수 있다”고 말하면 부족합니다. SDK 객체를 교체할 수 있어도 Tool Call 결과 연결, Streaming 완료 판정과 재시도 정책이 다르면 Agent Workflow는 깨질 수 있습니다.

반대로 모든 Provider의 결과가 같은 문장을 생성하도록 만드는 것도 현실적인 목표가 아닙니다. 모델마다 Prompt 해석, Tool 선택과 안전 정책이 다릅니다.

따라서 목표를 다음처럼 정의하는 것이 좋습니다.

```text
같은 Agent 의도
  + 같은 Tool·Permission 정책
  + Provider별 검증된 변환
  → 같은 종류의 실행 결과와 관측 정보
```

여기서 “같은 종류”는 `최종 Text`, `Tool 요청`, `길이 제한`, `안전 차단`, `재시도 가능 오류`처럼 Application이 처리할 수 있는 공통 상태를 의미합니다.

## 2. Agent Core와 제공자 어댑터 (Provider Adapter)의 책임을 분리한다

제공자 어댑터 (Provider Adapter)는 모델 API의 번역 계층입니다. Agent의 업무 정책을 소유하지 않습니다.

| Agent Core 책임 | Provider Adapter 책임 |
|---|---|
| Session과 Memory | 공통 Message를 Provider 형식으로 변환 |
| Tool Registry와 실행 | Tool Schema를 Provider 형식으로 변환 |
| Permission과 사용자 승인 | Provider Tool Call을 공통 Tool Call로 변환 |
| Retry·Checkpoint | Streaming Event를 공통 Event로 변환 |
| Skill·Hook·Sub-agent | 중단 사유·사용량·오류 정규화 |
| 감사 Log와 Trace | Provider Request ID와 원본 Metadata 보존 |

Provider Adapter가 “이 Tool은 위험하므로 실행해도 되는가”를 결정하면 같은 업무가 Provider에 따라 다른 권한 정책을 갖게 됩니다.

반대로 Agent Core가 Provider의 세부 Event 이름까지 알아야 한다면 새 API 버전을 연결할 때 Core를 수정해야 합니다.

권장 Interface(인터페이스)는 작게 시작합니다.

```python
from collections.abc import AsyncIterator
from typing import Protocol


class ModelProvider(Protocol):
    def capabilities(self) -> "ProviderCapabilities":
        ...

    async def complete(self, request: "ModelRequest") -> "ModelResponse":
        ...

    async def stream(
        self,
        request: "ModelRequest",
    ) -> AsyncIterator["ModelEvent"]:
        ...

    async def count_tokens(
        self,
        request: "ModelRequest",
    ) -> "TokenEstimate":
        ...
```

`complete()`와 `stream()`은 입력 의미가 같아야 합니다. Streaming 경로만 별도 Tool 처리나 안전 정책을 갖게 만들면 같은 요청이 호출 방식에 따라 달라집니다.

## 3. 공통 Message는 문자열 배열보다 Content Part로 설계한다

Text만 지원하는 초기 구조는 보통 다음과 같습니다.

```json
{
  "role": "user",
  "content": "이 문서를 요약해줘"
}
```

이미지, 파일, Tool 결과와 Provider 고유 Part를 연결하면 `content`를 문자열 하나로 유지하기 어렵습니다. 공통 Message를 역할 (Role)과 콘텐츠 조각 (Content Part)의 목록으로 설계합니다.

```json
{
  "id": "msg_opaque_001",
  "role": "user",
  "parts": [
    {
      "type": "text",
      "text": "첨부 문서의 핵심 위험을 정리해줘"
    },
    {
      "type": "file_ref",
      "fileId": "file_opaque_001",
      "mediaType": "application/pdf"
    }
  ],
  "metadata": {
    "source": "user"
  }
}
```

공통 Part의 예시는 다음과 같습니다.

| Part | 용도 |
|---|---|
| `text` | 일반 Text |
| `image_ref` | 권한이 통제된 이미지 참조 |
| `file_ref` | 업로드된 파일 참조 |
| `tool_call` | 모델이 요청한 Tool 실행 |
| `tool_result` | Tool 실행 결과 |
| `refusal` | 안전 정책 등에 따른 거절 |
| `provider_extension` | 공통화하지 않은 Provider 고유 데이터 |

Provider의 원본 응답을 그대로 Session DB에 저장하는 방식은 빠르지만 Provider 교체와 장기 Migration에 취약합니다. 공통 Message를 주 저장 형식으로 두고, 진단과 재현에 필요한 원본 응답은 별도 암호화·보존 정책 아래 저장하는 편이 좋습니다.

## 4. System 지시와 사용자 대화를 분리한다

Provider마다 상위 지시를 전달하는 필드와 Role의 의미가 같지 않을 수 있습니다. Application의 System Policy(시스템 정책)를 단순히 첫 번째 Message 문자열로 취급하지 않습니다.

```json
{
  "instructions": {
    "systemPolicy": "권한이 확인된 Tool만 호출한다.",
    "agentInstruction": "요청을 분석하고 필요한 Tool을 선택한다.",
    "responseStyle": "결론을 먼저 한국어로 설명한다."
  },
  "messages": [
    {
      "role": "user",
      "parts": [
        {
          "type": "text",
          "text": "내 회의 목록을 보여줘"
        }
      ]
    }
  ]
}
```

Adapter는 이 구조를 Provider가 지원하는 `instructions`, `system` 또는 해당 API의 Message 형식으로 변환합니다.

중요한 점은 지시 우선순위 (Instruction Precedence)를 Core에서 정의하는 것입니다.

```text
Platform Security Policy
  > Tenant Policy
    > Agent Instruction
      > Skill Instruction
        > User Message
          > Retrieved Content
```

검색 문서와 Tool 결과는 명령이 아니라 비신뢰 데이터 (Untrusted Data)로 표시합니다. Provider를 교체해도 Prompt Injection 방어 경계가 유지돼야 합니다.

## 5. Provider별 API 세대를 설정에 포함한다

같은 회사 안에서도 API 세대가 달라질 수 있습니다.

- OpenAI는 새 프로젝트에 Responses API를 권장하면서 Chat Completions도 계속 지원합니다.
- Google Gemini API 문서는 Agentic Workflow(에이전트형 워크플로)를 위한 Interactions를 권장하고, `generateContent`와 `streamGenerateContent`도 제공합니다.
- Anthropic Messages API는 Message Content Block과 `stop_reason`을 중심으로 Tool Loop를 구성합니다.

따라서 `provider=openai`만 저장하면 재현 정보가 부족합니다.

```json
{
  "provider": "openai",
  "apiFamily": "responses",
  "modelAlias": "agent-default",
  "resolvedModel": "provider-model-version",
  "adapterVersion": "openai-responses-v3",
  "promptProfile": "agent-core-v5",
  "toolSchemaVersion": "tool-contract-v4"
}
```

Model 별칭 (Model Alias)은 운영 정책이 선택하는 논리 이름이고, 실제 호출한 Model ID와 Adapter Version(어댑터 버전)은 실행 기록에 남깁니다.

Provider SDK의 Major Version(주 버전), API Header와 Beta 기능도 결과 형식에 영향을 줄 수 있습니다. 재현에 필요한 값은 Secret을 제외하고 Trace Metadata에 기록합니다.

## 6. Tool 정의는 Provider Schema의 합집합이 아니라 검증된 부분집합을 사용한다

세 Provider 모두 Function 또는 Tool 정의를 구조화된 Schema로 전달할 수 있지만 지원하는 JSON Schema 범위와 Strict Mode(엄격 모드)는 같지 않습니다.

공통 Tool Contract(도구 계약)는 실제로 세 Adapter가 검증한 부분집합으로 제한합니다.

```json
{
  "name": "meeting.list",
  "description": "현재 사용자가 접근할 수 있는 회의 목록을 조회합니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keyword": {
        "type": ["string", "null"],
        "description": "선택 검색어"
      },
      "mine": {
        "type": "boolean",
        "description": "내 회의만 조회할지 여부"
      }
    },
    "required": ["keyword", "mine"],
    "additionalProperties": false
  },
  "risk": "read",
  "timeoutMs": 10000
}
```

OpenAI Function Calling 공식 문서는 Strict Mode에서 Object의 `additionalProperties`를 `false`로 두고 모든 Property를 `required`에 포함하도록 안내합니다. 선택값은 `null`을 허용하는 방식으로 표현할 수 있습니다.

Gemini Function Calling 문서는 OpenAPI Schema의 일부만 지원한다고 명시합니다. 따라서 한 Provider가 지원하는 복잡한 조합 Schema를 공통 Tool에 그대로 사용하면 다른 Provider에서 Request 자체가 거절될 수 있습니다.

권장 절차는 다음과 같습니다.

1. 내부 Canonical Schema(정규 도구 스키마)를 검증합니다.
2. Adapter가 Provider Schema로 변환합니다.
3. Provider가 지원하지 않는 Keyword를 발견하면 조용히 제거하지 않고 배포 단계에서 실패시킵니다.
4. 실제 모델 호출 뒤에도 Tool Arguments를 내부 Schema로 다시 검증합니다.
5. Schema 통과 뒤 업무 규칙과 Permission을 별도로 검증합니다.

모델이 생성한 JSON은 신뢰할 수 있는 실행 명령이 아닙니다.

## 7. Tool Call ID는 반드시 끝까지 보존한다

Tool 이름과 Arguments만 저장하면 병렬 호출 결과를 정확히 연결할 수 없습니다.

```text
Model Response
  ├─ tool call A: callId=opaque_a
  └─ tool call B: callId=opaque_b
         │
         ▼
Permission · Execution
         │
         ▼
Tool Results
  ├─ result for opaque_a
  └─ result for opaque_b
```

공통 Tool Call은 다음처럼 표현할 수 있습니다.

```json
{
  "type": "tool_call",
  "callId": "call_opaque_a",
  "providerCallId": "provider_call_opaque_a",
  "name": "meeting.list",
  "arguments": {
    "keyword": null,
    "mine": true
  },
  "status": "ready"
}
```

Provider별 연결 방식은 다릅니다.

| Provider API | 호출 표현 | 결과 연결 |
|---|---|---|
| OpenAI Responses | Function Call과 `call_id` | Function Call Output에 같은 `call_id` |
| Anthropic Messages | `tool_use` Content Block의 `id` | `tool_result`의 `tool_use_id` |
| Gemini Function Calling | `functionCall`의 `id` 또는 API별 Call ID | `functionResponse`에 대응 ID 보존 |

Anthropic 공식 문서는 `stop_reason`이 `tool_use`이면 하나 이상의 `tool_use` Block을 실행하고, 각각의 ID와 연결된 `tool_result`를 다음 User Message에 전달하는 흐름을 설명합니다.

Gemini 공식 문서는 지원 모델에서 `functionCall`의 고유 ID를 대응 `functionResponse`에 그대로 포함해야 정확히 연결할 수 있다고 안내합니다.

Provider가 ID를 제공하지 않는 구형 경로를 지원해야 한다면 Adapter가 위치 기반으로 추측하지 말고 명시적인 호환 정책을 둡니다. 병렬 Tool을 비활성화하거나, Adapter가 생성한 ID와 원본 순서를 함께 기록하고 해당 한계를 기능 행렬에 표시합니다.

## 8. Tool Loop는 Provider Adapter 밖에 둔다

Tool 실행 반복은 Agent Core의 책임입니다.

```python
async def run_agent(request, provider, tool_executor):
    response = await provider.complete(request)

    while response.status == "tool_required":
        results = []

        for call in response.tool_calls:
            authorized = await authorize(call)
            if not authorized:
                results.append(tool_denied_result(call))
                continue

            results.append(await tool_executor.execute(call))

        request = continue_with_tool_results(
            request=request,
            response=response,
            results=results,
        )
        response = await provider.complete(request)

    return response
```

Provider SDK가 제공하는 자동 Tool Runner(도구 실행기)는 빠른 검증에는 유용합니다. 하지만 다음 요구가 있다면 Core가 Loop를 소유하는 편이 명확합니다.

- 위험도별 사용자 승인
- Tool별 Timeout과 Retry
- 테넌트와 사용자 권한 검사
- 실행 전후 Hook
- Checkpoint와 재개
- Tool Result Masking(도구 결과 마스킹)
- 감사 Log와 비용 연결
- 여러 Provider에서 같은 정책 적용

Server-side Tool(제공자 서버 도구)을 사용할 때도 내부 Tool과 구분합니다. Provider가 실행한 Web Search와 Application이 실행한 고객 데이터 조회는 권한, 비용과 감사 범위가 다릅니다.

## 9. Streaming은 Text 조각이 아니라 수명주기 Event로 정규화한다

세 Provider 모두 Streaming을 지원하지만 Event 이름과 계층은 다릅니다.

OpenAI Responses Streaming은 대표적으로 `response.created`, `response.output_text.delta`, `response.completed`, `error` Event를 제공합니다.

Anthropic Streaming은 `message_start`, Content Block별 `content_block_start`·`content_block_delta`·`content_block_stop`, 상위 `message_delta`, 마지막 `message_stop` 순서를 사용합니다. Tool Arguments는 `input_json_delta`의 부분 JSON 문자열로 전달될 수 있습니다.

Gemini는 API 세대에 따라 Incremental `GenerateContentResponse` 또는 Interactions의 `step.delta` 같은 Event를 제공합니다. Function Arguments가 조각으로 전달되면 완료 전까지 누적해야 합니다.

공통 Event는 다음처럼 정의할 수 있습니다.

```json
{
  "eventId": "evt_opaque_010",
  "sequence": 10,
  "type": "tool_call.arguments.delta",
  "responseId": "resp_opaque_001",
  "itemId": "call_opaque_a",
  "delta": "{\"mine\":",
  "provider": {
    "name": "provider-name",
    "eventType": "provider-event-type"
  }
}
```

권장 공통 Event Type은 다음과 같습니다.

| Event | 의미 |
|---|---|
| `response.started` | 요청이 수락되고 응답 생성 시작 |
| `content.started` | Text·Tool·Refusal Item 시작 |
| `text.delta` | 표시 가능한 Text 증분 |
| `tool_call.started` | Tool Call 식별자와 이름 확인 |
| `tool_call.arguments.delta` | 아직 완성되지 않은 Arguments 조각 |
| `tool_call.completed` | Arguments 누적·JSON Parse·Schema 검증 가능 |
| `content.completed` | 개별 Content Item 완료 |
| `usage.updated` | 누적 또는 최종 사용량 |
| `response.completed` | 전체 응답 정상 완료 |
| `response.failed` | Stream 안의 오류 또는 비정상 종료 |

`text.delta`를 받았다고 Session의 Final Message로 즉시 저장하지 않습니다. 연결이 끊기거나 안전 차단이 뒤늦게 확인될 수 있습니다. Partial Buffer(부분 버퍼)와 Final Commit(최종 확정)을 분리합니다.

## 10. 부분 JSON은 완료 전 실행하지 않는다

Streaming Tool Arguments는 다음처럼 나뉘어 올 수 있습니다.

```text
{"key
word":"
quarterly
 report"}
```

각 Delta는 독립적인 JSON이 아닙니다. 문자열을 순서대로 누적한 뒤 Tool Call 완료 Event에서 Parse합니다.

```python
class ToolArgumentAssembler:
    def __init__(self) -> None:
        self._buffers: dict[str, list[str]] = {}

    def append(self, call_id: str, delta: str) -> None:
        self._buffers.setdefault(call_id, []).append(delta)

    def complete(self, call_id: str) -> dict:
        raw = "".join(self._buffers.pop(call_id, []))
        parsed = json.loads(raw)
        validate_tool_arguments(parsed)
        return parsed
```

다음 안전 규칙이 필요합니다.

- `callId`별로 Buffer를 분리합니다.
- Event `sequence` 역전과 중복을 탐지합니다.
- 최대 Arguments Byte를 제한합니다.
- UTF-8 경계와 문자열 Escape를 임의로 수정하지 않습니다.
- 완료 전 JSON처럼 보이더라도 Tool을 실행하지 않습니다.
- Parse와 Schema 검증 실패를 모델에 Tool Error로 돌려줄지 실행을 중단할지 정책화합니다.

화면에는 Tool 이름과 준비 상태를 먼저 표시할 수 있지만, 미완성 Arguments를 승인 화면의 확정값처럼 보여주면 안 됩니다.

## 11. 중단 사유를 하나의 `finish_reason` 문자열로 축소하지 않는다

Provider의 종료 값은 서로 일대일 대응하지 않습니다.

| 공통 상태 | 의미 | 후속 동작 |
|---|---|---|
| `completed` | 자연스럽게 응답 완료 | 결과 사용 |
| `tool_required` | Application Tool 실행 필요 | Permission·Tool Loop |
| `length_limited` | 출력 또는 Context 한도 | 계속 생성·요약·설정 조정 |
| `content_filtered` | 안전 또는 정책 차단 | 사용자 안내·정책 처리 |
| `refused` | 모델이 요청을 거절 | 이유 표시·허용된 Fallback 검토 |
| `paused` | Provider 내부 장기 작업 중단 | Provider 규칙에 따라 재개 |
| `malformed_tool_call` | Tool Arguments 생성 실패 | 재요청·Tool 비활성화 |
| `failed` | 호출 또는 Stream 실패 | 오류 분류에 따라 Retry |

원본 종료 사유도 함께 보존합니다.

```json
{
  "status": "tool_required",
  "providerFinish": {
    "provider": "anthropic",
    "rawReason": "tool_use",
    "rawDetails": null
  },
  "toolCallCount": 2
}
```

Anthropic Messages의 `stop_reason`에는 `end_turn`, `max_tokens`, `tool_use`, `pause_turn`, `refusal`, `model_context_window_exceeded` 등이 있습니다.

Gemini `GenerateContentResponse`의 Candidate에는 `finishReason`과 Safety Rating이 있고, `MALFORMED_FUNCTION_CALL`처럼 Tool 호출 자체가 잘못된 경우도 구분합니다.

중단 사유를 단순히 `stop`과 `length` 두 값으로 줄이면 안전 차단과 Tool 요청을 정상 완료로 오해할 수 있습니다.

## 12. 사용량은 공통 합계와 Provider 상세를 함께 저장한다

공통 Usage(사용량)는 비용과 Context 관리에 필요한 최소 항목을 제공합니다.

```json
{
  "inputTokens": 1250,
  "outputTokens": 320,
  "totalTokens": 1570,
  "cachedInputTokens": 800,
  "reasoningTokens": null,
  "providerDetails": {
    "name": "provider-name",
    "rawUsage": {
      "input_units": 1250,
      "output_units": 320
    }
  }
}
```

모든 Provider가 같은 세부 항목을 제공한다고 가정하지 않습니다. 없는 값은 `0`으로 만들어 의미를 바꾸기보다 `null` 또는 미지원 상태로 남깁니다.

Streaming에서는 Usage가 중간 Event에 누적값으로 오거나 마지막 응답에만 포함될 수 있습니다.

- 중간값과 최종값을 구분합니다.
- 누적값을 매 Event마다 합산해 이중 계산하지 않습니다.
- 실제 청구 단위는 Provider Billing 자료와 대조합니다.
- Model Alias가 아니라 실제 호출 Model ID와 가격표 버전을 연결합니다.
- Tool 호출 비용, 검색 비용과 Model Token 비용을 별도 항목으로 둡니다.

비용 계산은 Adapter 안에 하드코딩하지 않습니다. 가격표가 바뀌어도 과거 실행 비용을 재현할 수 있도록 유효 기간이 있는 Pricing Registry(가격 레지스트리)를 사용합니다.

## 13. 오류는 재시도 가능성보다 먼저 부작용 여부를 본다

HTTP `429`나 `5xx`는 일반적으로 재시도 후보이지만 Agent에서는 요청이 어느 단계까지 실행됐는지가 더 중요합니다.

```text
Model 요청 실패
  └─ Tool 실행 전       → 안전한 Provider Retry 후보

Tool 실행 성공
  └─ 후속 Model 요청 실패 → Tool을 다시 실행하면 안 됨

응답 완료
  └─ Client 수신 실패   → 저장된 결과 조회 후 판정
```

공통 오류는 다음 정보를 가져야 합니다.

```json
{
  "category": "rate_limited",
  "retryable": true,
  "retryAfterMs": 2000,
  "providerRequestId": "req_opaque_001",
  "httpStatus": 429,
  "attempt": 2,
  "sideEffectState": "none",
  "safeMessage": "요청이 일시적으로 제한되었습니다.",
  "providerCode": "provider-rate-limit-code"
}
```

권장 오류 분류는 다음과 같습니다.

| 분류 | 예시 | 기본 처리 |
|---|---|---|
| `invalid_request` | Schema·Parameter 오류 | 재시도 금지, Adapter 수정 |
| `authentication` | Key·Token 오류 | Credential 갱신 또는 운영자 조치 |
| `permission_denied` | Model·Project 권한 부족 | 다른 Credential로 자동 우회 금지 |
| `rate_limited` | 요청·Token 제한 | `Retry-After`와 Backoff |
| `overloaded` | Provider 과부하 | 제한된 Retry 또는 승인된 Fallback |
| `timeout` | 연결·응답 Timeout | 실행 단계 확인 후 Retry |
| `content_filtered` | 안전 차단 | 사용자 안전 응답 |
| `context_exceeded` | Context 한도 | 압축·요약·입력 축소 |
| `stream_interrupted` | SSE·Socket 중단 | Checkpoint와 Provider 상태 확인 |

Provider Error Message 전체를 사용자에게 전달하지 않습니다. 내부 Request ID는 진단에 보존하되 API Key, Prompt 원문과 고객 데이터는 일반 Log에서 제외합니다.

## 14. Fallback은 Provider 교체가 아니라 새 실행 정책이다

첫 Provider가 실패하면 두 번째 Provider를 자동 호출하는 코드는 간단합니다.

```python
try:
    return await primary.complete(request)
except RetryableProviderError:
    return await fallback.complete(request)
```

그러나 Tool 실행이 포함되면 이 방식은 위험합니다.

```text
Provider A → Tool Call → 결제 Tool 성공
Provider A → 최종 응답 생성 중 Timeout
Provider B → 같은 대화 재실행 → 결제 Tool 다시 요청
```

Fallback Policy(대체 실행 정책)는 다음 조건을 확인해야 합니다.

- 아직 외부 부작용이 발생하지 않았는가
- 같은 Tool Call 결과를 재사용할 수 있는가
- Provider B가 필요한 기능과 Context를 지원하는가
- 데이터 Residency(데이터 위치)와 계약상 전송이 허용되는가
- Prompt와 안전 정책이 Provider B에서 검증됐는가
- 사용자가 특정 Provider를 명시했는가

외부 부작용 뒤에는 새 Agent 실행보다 저장된 Checkpoint에서 후속 응답 생성만 재개하는 방식이 안전합니다.

```text
Checkpoint
  ├─ normalized messages
  ├─ completed tool calls
  ├─ tool results
  ├─ pending model step
  └─ side-effect ledger
```

Provider Fallback은 품질 평가와 보안 승인을 거친 명시적 Route만 허용합니다.

## 15. 기능 행렬 (Capability Matrix)로 손실을 숨기지 않는다

Provider별 기능을 Boolean 몇 개로만 표현하면 Model별 차이를 담기 어렵습니다.

```json
{
  "provider": "provider-name",
  "apiFamily": "provider-api-family",
  "model": "provider-model-version",
  "capabilities": {
    "text": {
      "supported": true
    },
    "visionInput": {
      "supported": true,
      "mediaTypes": ["image/png", "image/jpeg"]
    },
    "toolCalling": {
      "supported": true,
      "parallel": true,
      "strictSchema": "provider-specific"
    },
    "streaming": {
      "supported": true,
      "toolArgumentDelta": true
    },
    "serverState": {
      "supported": true,
      "mode": "provider-specific"
    }
  }
}
```

요청 전에 필요한 기능을 확인합니다.

```python
required = {
    "toolCalling": True,
    "streaming": True,
    "visionInput": False,
}

model = registry.resolve(
    alias="agent-default",
    required_capabilities=required,
)
```

미지원 기능을 조용히 제거하지 않습니다.

- Image 입력을 Text 설명으로 바꾸면 품질과 개인정보 범위가 달라집니다.
- Parallel Tool Call을 직렬 실행으로 바꾸면 순서와 지연이 달라집니다.
- Strict Schema를 Best Effort로 낮추면 Validation 책임이 커집니다.
- Server-side State를 Local History로 바꾸면 보존과 비용이 달라집니다.

호환 변환이 가능하더라도 Trace에 Degradation(기능 저하)을 기록합니다.

## 16. Session과 Memory를 Provider 대화 ID에 종속시키지 않는다

Provider가 Server-side Conversation State(서버 측 대화 상태)를 지원하면 구현이 간단해질 수 있습니다. OpenAI Responses API는 `previous_response_id`로 이전 응답의 Context를 연결할 수 있습니다.

하지만 Application Session의 유일한 상태를 Provider ID로 두면 다음 작업이 어려워집니다.

- 다른 Provider로 전환
- 대화 내역 Export와 삭제
- Tool Permission 감사
- 특정 Message를 Masking한 재실행
- 고정 Fixture를 이용한 회귀 Test
- Provider 장애 시 복구

권장 구조는 Application이 정규화된 Session을 소유하고 Provider State는 선택적 가속 정보로 취급하는 것입니다.

```text
Application Session
  ├─ normalized messages
  ├─ tool ledger
  ├─ permission decisions
  ├─ memory references
  └─ provider cursors
       ├─ OpenAI previous response ID
       ├─ Anthropic continuation metadata
       └─ Gemini interaction or history metadata
```

Provider Cursor(제공자 상태 포인터)가 만료되거나 해석되지 않으면 정규화된 Message History로 새 요청을 구성할 수 있어야 합니다.

대화 전체를 매번 전달하면 Token 비용이 커집니다. Summary, Retrieval Memory와 최근 Message Window를 조합하되, Tool 결과와 승인 기록을 임의로 요약해 의미를 잃지 않습니다.

## 17. Permission·Skill·Hook은 Model보다 바깥에 둔다

멀티 Provider Workbench에서 재사용 가치가 큰 부분은 Model 호출 자체보다 Agent Runtime(에이전트 실행 환경)입니다.

```text
Skill
  → 작업 절차와 안전 규칙

Hook
  → 호출 전후 검사·관측·차단

Permission
  → Read·Write·Important·Destructive 승인

Memory
  → 사용자·Project·Session Context

Sub-agent
  → 위임 범위와 별도 Tool Allowlist
```

모델이 “이 작업은 안전하다”고 판단해도 Permission Engine(권한 엔진)의 결정을 우회할 수 없습니다.

| 위험도 | 예시 | 기본 정책 |
|---|---|---|
| Read | 목록·상세 조회 | 범위 내 자동 실행 가능 |
| Write | Note·설정 변경 | 정책에 따른 확인 |
| Important | 외부 게시·메시지 전송 | 명시적 사용자 의도 확인 |
| Destructive | 삭제·취소·영구 변경 | 정확한 대상 재확인 |

Sub-agent가 다른 Provider를 사용하더라도 부모 Agent보다 넓은 Tool 권한을 자동 상속하지 않습니다. 위임된 Task, Tool Allowlist(도구 허용 목록), Token·비용 Budget과 최대 실행 시간을 함께 전달합니다.

## 18. REPL과 TUI는 Adapter 검증 도구가 된다

대화형 명령줄 (Read-Eval-Print Loop, REPL)과 터미널 사용자 인터페이스 (Terminal User Interface, TUI)는 개발자용 편의 기능에 그치지 않습니다.

Provider별 같은 입력을 빠르게 비교할 수 있습니다.

```text
/provider openai
/model agent-default
/trace on
내 회의 목록을 보여줘

/provider anthropic
/replay last

/provider google
/replay last
```

화면에서 다음을 분리해 표시합니다.

- 사용자 입력과 정규화된 Message
- Provider Request 시작·종료
- Text Delta와 Tool Arguments Delta
- Tool Permission 요청
- Tool 실행 결과
- 공통 종료 상태와 원본 종료 사유
- Input·Output·Cache Token
- Model·Tool·전체 지연 시간

Raw Provider Response를 기본 화면에 그대로 노출하면 민감한 Metadata가 섞일 수 있습니다. 진단 모드와 일반 모드를 분리하고 Secret Masking을 적용합니다.

## 19. Contract Test와 Golden Fixture로 Provider 차이를 고정한다

실제 API만 호출하는 Test는 느리고 비용이 들며 Model 결과가 바뀔 수 있습니다. Adapter 단위에서는 고정된 Provider 응답 Fixture를 공통 Event와 Response로 변환하는 Contract Test(계약 테스트)가 필요합니다.

| Test | 검증 내용 |
|---|---|
| Text 완료 | 최종 Text와 `completed` 상태 |
| 단일 Tool | Call ID·이름·Arguments 변환 |
| 병렬 Tool | 각 Result가 정확한 Call에 연결 |
| Tool Arguments Streaming | Delta 누적 후 한 번만 실행 |
| 길이 제한 | `length_limited`로 정규화 |
| 안전 차단 | Text 완료로 오인하지 않음 |
| Stream 중 오류 | Partial과 Final 상태 분리 |
| Usage 누적 | 중간값 중복 합산 없음 |
| Unknown Event | 무시·보존·경고 정책 |
| Provider ID 만료 | Local Session History로 복구 |

Golden Fixture(고정 검증 자료)는 다음 두 계층으로 나눕니다.

```text
Provider Raw Fixture
  → Adapter
  → Normalized Event Fixture
  → Event Reducer
  → Normalized Response Fixture
```

실제 Model E2E Test에서는 문장 일치보다 행동을 검증합니다.

```text
사용자 요청
  → 허용된 Tool 선택
  → 필수 Arguments 포함
  → 읽기 Tool만 실행
  → 결과를 근거로 최종 응답
```

Provider SDK나 API Version을 올릴 때 Raw Fixture, Event 순서, 종료 상태와 Usage가 바뀌는지 먼저 확인합니다.

## 20. 관측성은 공통 Span과 Provider 원본 ID를 연결한다

하나의 Agent 실행은 여러 Provider와 Tool을 거칠 수 있습니다.

```text
agent.run
  ├─ model.request
  │    ├─ model.stream
  │    └─ model.response
  ├─ permission.check
  ├─ tool.execute
  └─ model.request
```

권장 공통 Attribute는 다음과 같습니다.

- `agentRunId`
- `sessionId`
- `provider`
- `apiFamily`
- `resolvedModel`
- `adapterVersion`
- `providerRequestId`
- `responseId`
- `toolCallId`
- `toolName`
- `finishStatus`
- `inputTokens`, `outputTokens`
- `firstTokenLatencyMs`, `totalLatencyMs`
- `retryCount`, `fallbackRoute`

Metric Label(지표 레이블)에 Prompt, Tool Arguments, 사용자 이름과 문서 제목을 넣지 않습니다. 고유값이 많은 식별자는 Trace에만 두고 Metric에는 Provider·Model Alias·상태 Code처럼 제한된 값을 사용합니다.

Provider Raw Error와 Request·Response 본문은 접근 통제된 진단 저장소에 짧게 보존하거나 저장하지 않는 정책을 선택합니다.

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| Core 경계 | Session·Permission·Tool Loop가 Adapter 밖에 있는가 |
| Message | Text 외 Content Part를 표현할 수 있는가 |
| 지시 | System Policy와 사용자 Message가 분리돼 있는가 |
| API 세대 | Provider뿐 아니라 API Family와 Adapter Version을 기록하는가 |
| Tool Schema | 세 Provider가 검증한 JSON Schema 부분집합인가 |
| Arguments | Provider 응답 뒤 내부 Schema로 다시 검증하는가 |
| Call ID | Tool Call과 Result ID를 끝까지 보존하는가 |
| 병렬 호출 | 병렬 Tool별 Buffer와 Result 연결이 분리되는가 |
| Streaming | 시작·Delta·완료·오류 Event가 정규화되는가 |
| Partial JSON | Tool Call 완료 전 실행하지 않는가 |
| 종료 상태 | Tool·길이·차단·거절·일시중단을 구분하는가 |
| Usage | 누적값과 최종값을 이중 합산하지 않는가 |
| 비용 | 가격표와 실제 Model Version을 분리 관리하는가 |
| 오류 | Retry 가능성과 부작용 상태를 함께 판단하는가 |
| Fallback | 외부 부작용 후 전체 Agent를 다시 실행하지 않는가 |
| 기능 행렬 | 미지원 기능을 조용히 제거하지 않는가 |
| Session | Provider 대화 ID 없이도 복구 가능한가 |
| Permission | Provider가 바뀌어도 같은 승인 정책을 적용하는가 |
| Sub-agent | 위임된 권한과 비용 범위를 제한하는가 |
| Test | Raw→Event→Response Golden Fixture가 있는가 |
| 관측성 | 공통 Span과 Provider Request ID가 연결되는가 |
| 개인정보 | Prompt·Tool Arguments·Secret을 일반 Log에서 제외하는가 |

## 마무리

GPT·Claude·Gemini를 교체 가능한 Agent Core에 연결한다는 것은 SDK 세 개를 같은 Interface로 감싸는 작업보다 큽니다.

핵심은 다음과 같습니다.

1. Agent Core가 Session, Tool Loop, Permission, Skill, Hook과 Checkpoint를 소유합니다.
2. Provider Adapter는 Message, Tool, Streaming, Usage와 오류를 번역합니다.
3. 공통 Message는 Text 문자열이 아니라 Content Part 목록으로 설계합니다.
4. Tool Schema는 검증된 공통 부분집합을 사용하고 실행 전에 다시 검증합니다.
5. Tool Call ID와 Result 연결을 병렬 실행에서도 보존합니다.
6. Streaming을 Text Delta가 아닌 수명주기 Event로 정규화합니다.
7. 종료 상태를 Tool, 길이 제한, 안전 차단과 실패로 구분합니다.
8. Provider 고유 기능은 기능 행렬과 확장 영역으로 보존합니다.
9. Fallback 전에 Tool 부작용과 Checkpoint를 확인합니다.
10. Raw Fixture, 공통 Event와 최종 Response를 Contract Test로 고정합니다.

좋은 Provider Adapter는 차이를 숨기는 계층이 아닙니다. **Agent Core가 의존해야 할 안정적인 의미를 만들고, 숨기면 안 되는 차이는 명시적으로 드러내는 계층**입니다.

다음 글에서는 자연어 요청이 예상한 MCP Tool과 Arguments로 연결되는지, 목록→상세→파일→본문 같은 다단계 흐름과 권한 오류를 Golden Case(고정 성공 사례)로 검증하는 통합 테스트 방법을 살펴보겠습니다.

## 참고 자료

- [OpenAI: Migrate to the Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses)
- [OpenAI: Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI: Streaming API responses](https://developers.openai.com/api/docs/guides/streaming-responses)
- [OpenAI: Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [Anthropic: Messages API](https://platform.claude.com/docs/en/api/messages/create)
- [Anthropic: How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic: Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- [Anthropic: Streaming messages](https://platform.claude.com/docs/en/build-with-claude/streaming)
- [Anthropic: Stop reasons and fallback](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons)
- [Google: Gemini API reference](https://ai.google.dev/api)
- [Google: Function calling with the Gemini API](https://ai.google.dev/gemini-api/docs/function-calling)
- [Google: GenerateContentResponse](https://ai.google.dev/api/generate-content)
- [Google: Text generation and streaming](https://ai.google.dev/gemini-api/docs/text-generation)

> 이 글은 2026년 7월 29일 기준 OpenAI, Anthropic과 Google의 공개 공식 문서와, GPT·Claude·Gemini를 하나의 Agent Core에서 전환하고 MCP·Permission·Skill·Hook·Memory·Sub-agent·REPL·TUI를 검증한 공개 가능한 구현 경험을 바탕으로 작성했습니다. Provider API와 Model 기능은 계속 바뀔 수 있으므로 실제 적용 시 API Family, Model Version과 공식 문서를 다시 확인해야 합니다.
