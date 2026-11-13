# AI Agent 관측성 설계: LLM·RAG·MCP Tool 호출을 하나의 Trace로 연결하기

AI Agent 장애는 로그를 모아 놓아도 원인이 잘 보이지 않습니다. 한 요청이 Gateway와 Orchestrator, RAG 검색, LLM 추론, MCP Tool 실행을 지나는데 구간별 기록이 서로 이어지지 않기 때문입니다. 이 글은 OpenTelemetry GenAI·MCP 규약과 W3C Trace Context로 하나의 Trace를 만들고, Span·Metric·평가·감사 분리, 민감정보 최소화, Sampling과 회귀 평가 피드백 루프까지 정리합니다.

![AI Agent 요청 경로의 Trace와 운영·품질·감사 신호가 평가 및 안전한 배포 피드백 루프로 연결되는 관측성 아키텍처](assets/blog-72-ai-agent-observability-trace-hero.png)

<blockquote id="aiarchitect-toc" data-ke-style="box" style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;">
<p style="color: #263746; font-weight: 700;"><b>목차</b></p>
<ol style="list-style-type: decimal; font-weight: 400;" data-ke-list-type="decimal">
<li><a href="#ai-section-1">관측성은 “로그를 많이 남기는 것”이 아니다</a></li>
<li><a href="#ai-section-2">하나의 요청을 Trace Tree로 먼저 그린다</a></li>
<li><a href="#ai-section-3">Trace Context와 업무 식별자를 구분한다</a></li>
<li><a href="#ai-section-4">Java Gateway에서 Python Agent까지 Context를 전파한다</a></li>
<li><a href="#ai-section-5">MCP Tool 호출은 _meta로 Trace를 이어 간다</a></li>
<li><a href="#ai-section-6">Agent Span은 계획·검색·모델·Tool을 분리한다</a></li>
<li><a href="#ai-section-7">RAG는 “검색 성공”과 “답변 근거 충분”을 구분한다</a></li>
<li><a href="#ai-section-8">Model 호출은 요청·응답 Version과 비용 신호를 남긴다</a></li>
<li><a href="#ai-section-9">“실행 오류”와 “품질 실패”를 같은 ERROR로 표시하지 않는다</a></li>
<li><a href="#ai-section-10">Trace와 Audit Trail을 연결하되 대체하지 않는다</a></li>
<li><a href="#ai-section-11">민감정보는 “수집 후 Masking”보다 “기본 미수집”이 우선이다</a></li>
<li><a href="#ai-section-12">Baggage에는 권한과 개인정보를 싣지 않는다</a></li>
<li><a href="#ai-section-13">Sampling은 무작위 비율 하나로 끝내지 않는다</a></li>
<li><a href="#ai-section-14">Metric은 지연·행동·품질·안전을 분리한다</a></li>
<li><a href="#ai-section-15">운영 Trace를 회귀 평가로 되돌리는 폐쇄 루프를 만든다</a></li>
<li><a href="#ai-section-16">합성 장애 사례로 Trace를 읽어 본다</a></li>
<li><a href="#ai-section-17">단계적으로 도입한다</a></li>
<li><a href="#ai-section-18">흔한 안티패턴</a></li>
<li><a href="#ai-section-19">운영 체크리스트</a></li>
<li><a href="#ai-section-20">마무리</a></li>
<li><a href="#ai-section-21">공식 참고자료</a></li>
</ol>
</blockquote>

사용자가 AI Agent에게 요청합니다.

```text
“지난주 회의에서 결정된 후속 업무를 찾아 티켓으로 등록해 줘.”
```

Agent는 문서를 검색하고, LLM으로 다음 행동을 판단하고, 사용자 권한을 확인한 뒤 MCP Tool을 호출합니다. 최종 응답만 보면 한 문장처럼 보이지만 내부 실행은 여러 서비스와 신뢰 경계를 통과합니다.

```text
사용자 요청
  → Java Security Gateway
    → Python AI Orchestrator
      → RAG Retrieval
      → LLM Planning
      → 승인·인가
      → MCP Client
        → MCP Server
          → Business API·Database
```

이때 “가끔 틀린 답을 한다”, “처리가 느리다”, “티켓이 생성되지 않았다”는 신고만으로는 원인을 찾기 어렵습니다.

- 검색 결과가 비어 있었는가?
- 올바른 문서를 찾았지만 LLM이 Tool을 잘못 선택했는가?
- Tool 이름은 맞지만 인자가 이전 검색 결과에서 유래하지 않았는가?
- 권한 정책이 거부했는가, 외부 API가 실패했는가?
- 재시도 중 같은 쓰기 작업이 두 번 실행됐는가?
- 모델·Prompt·검색 Index·Tool Schema 중 무엇이 바뀌었는가?

평문 Log 몇 줄과 최종 응답만으로는 이 질문에 답할 수 없습니다. 한 요청의 **인과 경로를 Trace로 연결**하고, 단계별 운영 상태를 Metric으로 집계하며, 품질 판정을 Evaluation으로 남기고, 중요 행위는 별도의 Audit Trail로 증명해야 합니다.

이 글은 앞선 [AI Agent 도입 아키텍처 진화](https://aiarchitect.tistory.com/71)의 “로그 → 관측성” 구간을 독립된 운영 설계로 확장합니다. 자연어와 Tool 호출의 테스트 방법은 [자연어에서 MCP Tool Call까지](https://aiarchitect.tistory.com/14), 인수 기준은 [AI 프로젝트 성공 기준 8가지](https://aiarchitect.tistory.com/20), 권한과 감사는 [엔터프라이즈 AI Agent 권한 설계](https://aiarchitect.tistory.com/19)와 [AI Agent 감사 로그 설계](https://aiarchitect.tistory.com/27)를 함께 참고할 수 있습니다.

> 이 글의 예시 시스템, 식별자, Trace와 수치는 교육용 합성 예시입니다. 다만 **"코드 점검에서 발견한 것"으로 표시한 대목**은 저자가 관리한 코드의 익명화된 구조를 근거로 하며, 런타임 설정·로그·운영 성과는 확인하지 않았습니다. 특정 고객·회사·제품·운영 환경이나 실제 성과를 나타내지 않습니다. OpenTelemetry의 GenAI·MCP Semantic Convention은 2026-08-09 현재 **Development 상태**이므로, 운영 적용 시 사용하는 SDK와 규약 버전을 고정하고 최신 공식 문서를 다시 확인해야 합니다.

## 1. 관측성은 “로그를 많이 남기는 것”이 아니다

Observability(관측성)는 시스템 외부에 드러나는 신호로 내부 상태를 설명할 수 있게 만드는 능력입니다. AI Agent에서는 전통적인 오류·지연뿐 아니라 검색 품질, Tool 선택, 인자 출처, 승인과 모델 변경까지 함께 봐야 합니다.

먼저 다섯 가지 기록의 목적을 분리합니다.

- **Trace**
  - 답하려는 질문: 한 요청이 어디를 거쳐 왜 느리거나 실패했는가?
  - 대표 데이터: Span, 부모·자식 관계, Link, Event
  - 보존·완전성: Sampling 가능
- **Metric**
  - 답하려는 질문: 시스템 전체에서 무엇이 얼마나 자주 발생하는가?
  - 대표 데이터: 지연 분포, 오류율, Token·Tool 호출 수
  - 보존·완전성: 집계 중심
- **Diagnostic Log**
  - 답하려는 질문: 특정 코드 경계에서 무슨 일이 있었는가?
  - 대표 데이터: 구조화 Event, 오류 Code
  - 보존·완전성: 필요 범위만 저장
- **Evaluation**
  - 답하려는 질문: 실행 결과와 경로가 업무 품질 기준을 충족했는가?
  - 대표 데이터: 점수, Label, Rubric·Dataset Version
  - 보존·완전성: 재현 가능한 평가 증거
- **Audit Trail**
  - 답하려는 질문: 누가 어떤 권한과 승인으로 무엇을 변경했는가?
  - 대표 데이터: 주체, 대상, 정책 결정, Side Effect
  - 보존·완전성: 위험 작업은 Sampling 금지

이들을 한 저장소와 한 수명주기로 합치면 문제가 생깁니다.

- Trace는 진단을 위해 풍부하지만 Sampling될 수 있습니다.
- Audit Trail은 중요 변경을 빠짐없이 증명해야 합니다.
- 평가 Dataset은 재현을 위해 오래 보존할 수 있지만 사용자 원문을 그대로 복제하면 안 됩니다.
- Metric Label은 집계를 위한 저 Cardinality 값이어야 합니다.

따라서 **Trace ID로 서로 참조하되 목적·접근 권한·보존 기간은 분리**합니다.

## 2. 하나의 요청을 Trace Tree로 먼저 그린다

관측성 구현은 SDK 설치보다 **경계 설계**가 먼저입니다. 합성 업무인 “회의 결정 사항 검색 후 티켓 생성”을 다음 Trace Tree로 표현할 수 있습니다.

```text
HTTP POST /agent/requests                         SERVER
└─ invoke_agent knowledge-action-agent           INTERNAL
   ├─ retrieval meeting-knowledge                CLIENT/INTERNAL
   ├─ chat model-fixture-v1                       CLIENT
   ├─ policy.evaluate ticket.create              INTERNAL
   ├─ approval.wait                               INTERNAL
   ├─ tools/call ticket.create                    CLIENT
   │  ├─ POST /mcp                                CLIENT (transport)
   │  └─ tools/call ticket.create                 SERVER (MCP Server)
   │     ├─ POST /tickets                         CLIENT
   │     └─ INSERT ticket                         CLIENT
   └─ chat model-fixture-v1                       CLIENT
```

여기서 중요한 것은 Span을 많이 만드는 것이 아니라 **실패를 서로 다른 책임 경계로 분리하는 것**입니다.

- Gateway Span은 인증·요청 수명과 전체 지연을 봅니다.
- Agent Span은 한 번의 업무 실행과 반복 횟수를 묶습니다.
- Retrieval Span은 검색 조건·Index Version·결과 수를 봅니다.
- Model Span은 Provider·요청 Model·응답 Model·Token과 지연을 봅니다.
- Policy·Approval Span은 판단과 대기 시간을 실행 시간과 분리합니다.
- MCP Client·Server Span은 Agent가 요청한 Tool과 Server가 실제 처리한 Tool을 연결합니다.
- Business API·Database Span은 실제 Side Effect가 어디까지 확정됐는지 봅니다.

HTTP, Database와 LLM SDK의 자동 계측이 이미 Span을 만들고 있다면 같은 경계를 수동으로 다시 만들지 않습니다. 자동 Span에는 부족한 Version·업무 상태만 보강하고, 자동 계측이 보지 못하는 Agent 계획·승인·검증 경계만 수동 Span이나 Event로 추가합니다.

## 3. Trace Context와 업무 식별자를 구분한다

W3C Trace Context는 HTTP에서 `traceparent`와 선택적인 `tracestate`로 분산 Trace의 위치를 전달합니다.

```text
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

이 값은 다음 요청으로 Trace를 이어 주는 기술 식별자입니다. 하지만 다음 식별자를 대신하지 않습니다.

- **`trace_id`**: 한 번의 분산 실행을 진단하며, 한 실행 또는 연결된 실행 구간 동안 유지합니다.
- **`workflow_id`**: 재시작·승인 대기를 포함한 업무 Workflow를 연결하며, 업무 완료·취소까지 유지합니다.
- **`operation_id`**: 외부 Side Effect 조회와 멱등 재호출을 연결하며, 작업 결과가 확정될 때까지 유지합니다.
- **`tool_call_id`**: 특정 Tool 호출과 응답을 연결하며, 한 Tool 호출 동안 유지합니다.
- **`decision_id`**: 권한 정책 판단과 실행 감사를 연결하며, 정책 결정 증거 수명 동안 유지합니다.
- **`evaluation_id`**: Trace를 어떤 Rubric으로 평가했는지 연결하며, 평가 Dataset 수명 동안 유지합니다.

장시간 Workflow가 승인 대기 후 재개되거나 Worker 재시작으로 새 실행을 시작하면 새 Trace가 더 자연스러울 수 있습니다. 이 경우 `workflow_id`는 유지하고 새 Trace에서 이전 실행 Span을 **Link**로 연결합니다. 모든 재개를 하나의 며칠짜리 Trace로 강제로 늘리면 Sampling, 보존과 조회 비용이 복잡해집니다.

```text
Trace A: 요청 → 계획 → 승인 대기
                   │
                   └─ workflow_id 유지
                              │ Span Link
Trace B: 승인 응답 → 실행 시점 재인가 → Tool 실행
```

Trace ID를 업무 ID나 사용자 ID로 생성해서도 안 됩니다. W3C 규약은 `traceparent`와 `tracestate`에 개인정보나 민감정보를 넣지 않도록 요구합니다.

## 4. Java Gateway에서 Python Agent까지 Context를 전파한다

Java Gateway와 Python Orchestrator가 HTTP로 통신하면 OpenTelemetry 자동 계측이 W3C Trace Context를 주입·추출하도록 구성할 수 있습니다.

```text
Browser
  → Java Gateway SERVER Span
    → Java HTTP CLIENT Span
      -- traceparent -->
        Python HTTP SERVER Span
          → Agent INTERNAL Span
```

자동 계측이 HTTP Server Span을 이미 만들었다면 새 Root Span을 만들지 않고 현재 Span에 공개 가능한 Version 속성을 보강합니다.

```java
import io.opentelemetry.api.trace.Span;

public AgentReceipt accept(AgentRequest request) {
    Span current = Span.current();
    current.setAttribute("app.agent.name", "knowledge-action-agent");
    current.setAttribute("app.agent.version", "agent-fixture-v3");
    current.setAttribute("app.prompt.version", "prompt-fixture-v7");
    current.setAttribute("app.policy.version", "policy-fixture-v4");

    // 인증 사용자·Tenant·Token·Prompt 원문은 Span 속성에 기록하지 않는다.
    return orchestratorClient.submit(request);
}
```

`app.*` 속성은 이 글의 **애플리케이션 전용 예시**이며 OpenTelemetry 표준 속성이 아닙니다. 조직 내부 Schema Registry에서 이름·형식·Cardinality·보존 정책을 별도로 관리해야 합니다.

비동기 Queue를 통과할 때는 Trace Context를 Message Header에 전달하되, 다음을 구분합니다.

- 즉시 소비되는 단일 작업은 전달받은 Context 아래에 Consumer Span을 둘 수 있습니다.
- Fan-out, Batch, 지연 실행과 재처리는 하나의 부모보다 여러 원인과 연결될 수 있으므로 Span Link가 더 적합할 수 있습니다.
- 외부에서 받은 `trace-flags`와 Baggage는 신뢰할 수 있는 권한 입력이 아닙니다.

## 5. MCP Tool 호출은 `_meta`로 Trace를 이어 간다

**코드 점검에서 발견한 것** — 제 구현이 MCP 서버를 호출할 때 실어 보내는 헤더는 콘텐츠 타입과 인증 키가 전부입니다. **Trace Context를 전파하지 않고 `_meta`도 쓰지 않습니다.**

🔴 여기에 착각하기 쉬운 지점이 있습니다. JSON-RPC에서 `id`는 요청과 응답을 대응시키기 위한 **프로토콜 식별자**입니다. 그런데 이 클라이언트는 응답의 `id`를 따로 검증하지 않고 `result`만 꺼내 씁니다. 값 자체도 프로세스 안에서 증가하는 카운터라, 재시작하거나 프로세스가 여러 개면 같은 값이 다시 나올 수 있고 다른 서비스의 로그로 전파되지도 않습니다. **분산 Trace 식별자가 아닙니다.**

이 기준으로 보면 제 구현은 이 글의 단계표 **1단계에 아직 진입하지 못했습니다.** 다음에 손댄다면 세부 AI Span을 쪼개기 전에, **서비스 경계에서 Trace Context를 만들어 넘기는 것**이 먼저입니다.

MCP SEP-414는 MCP 요청의 `_meta`에 W3C 형식의 `traceparent`, `tracestate`, `baggage`를 전달하는 규칙을 정의합니다. 이 세 Key는 일반적인 DNS Prefix 예외로 **Prefix 없이** 사용합니다.

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "ticket.create",
    "arguments": {
      "summary": "합성 예시 업무"
    },
    "_meta": {
      "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    }
  }
}
```

MCP Client는 `CLIENT` Span, MCP Server는 같은 Trace Context를 추출한 `SERVER` Span을 만듭니다. OpenTelemetry의 현재 MCP 규약은 Tool 호출 Span에 다음 형태를 제안합니다.

```text
Span name: tools/call ticket.create
Span kind: CLIENT 또는 SERVER

mcp.method.name = tools/call
gen_ai.operation.name = execute_tool
gen_ai.tool.name = ticket.create
error.type = timeout | invalid_argument | permission_denied | ...
```

`gen_ai.tool.call.arguments`와 `gen_ai.tool.call.result`는 민감정보를 포함할 수 있어 **Opt-In** 속성입니다. 운영 기본값으로 원문을 켜지 않습니다.

MCP 2026-07-28은 Stateless Core로 전환하고 Protocol Logging 기능을 폐기 수순에 두었습니다. 따라서 Agent 관측성을 MCP Logging 알림에 의존시키지 않습니다. Transport와 무관한 OpenTelemetry 계측을 애플리케이션 운영 경계로 사용하고, MCP Protocol Version은 사용하는 SDK와 함께 Version으로 고정합니다.

또한 `trace_id`는 보안 권한이 아닙니다. MCP Server는 Trace가 이어졌다는 이유로 요청을 신뢰하지 않고 인증·Tenant·Tool·객체 권한을 독립적으로 검증해야 합니다.

## 6. Agent Span은 계획·검색·모델·Tool을 분리한다

Python Orchestrator에서는 한 번의 Agent 실행을 상위 Span으로 묶고, 검색과 Tool 경계를 자식 Span으로 나눕니다. 다음 코드는 원리를 보여 주는 축약 예시입니다.

```python
import hashlib
import json
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

tracer = trace.get_tracer("example.agent")


def canonical_digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_agent(query: str) -> dict:
    with tracer.start_as_current_span("invoke_agent knowledge-action-agent") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        root.set_attribute("gen_ai.agent.name", "knowledge-action-agent")
        root.set_attribute("gen_ai.agent.version", "agent-fixture-v3")
        root.set_attribute("app.prompt.version", "prompt-fixture-v7")

        try:
            with tracer.start_as_current_span("retrieval meeting-knowledge") as span:
                span.set_attribute("gen_ai.operation.name", "retrieval")
                span.set_attribute("app.retrieval.index.version", "index-fixture-v5")
                documents = search_documents(query)
                span.set_attribute("app.retrieval.result.count", len(documents))

            plan = call_model(query, documents)  # Model SDK 자동 계측 사용 가능
            arguments = validate_and_bind(plan, documents)

            with tracer.start_as_current_span(
                "tools/call ticket.create",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("mcp.method.name", "tools/call")
                span.set_attribute("gen_ai.operation.name", "execute_tool")
                span.set_attribute("gen_ai.tool.name", "ticket.create")
                span.set_attribute(
                    "app.tool.arguments.digest",
                    canonical_digest(arguments),
                )
                result = mcp_call("ticket.create", arguments)

            return result
        except Exception as exc:
            root.record_exception(exc)
            root.set_status(Status(StatusCode.ERROR))
            raise
```

실제 구현에서는 다음을 보완합니다.

1. Model·MCP SDK가 자동 Span을 만드는지 먼저 확인해 중복 계측을 피합니다.
2. 예외 전체 Message를 `error.type`에 넣지 않고 낮은 Cardinality의 안정된 Error Code를 사용합니다.
3. `canonical_digest`는 동일 인자 비교용이지 익명화가 아닙니다. 값의 후보 공간이 작으면 Hash를 역추측할 수 있으므로 원문 보호 수단으로 사용하지 않습니다.
4. Tool 인자는 허용 Schema로 정규화하고, 민감 Field는 Digest 계산 전에도 최소화합니다.
5. Prompt·검색 Chunk·Model 응답 원문은 기본적으로 기록하지 않습니다.

## 7. RAG는 “검색 성공”과 “답변 근거 충분”을 구분한다

RAG 관측성에서 Vector 검색 API가 `200 OK`를 반환했다는 사실만으로 품질이 좋은 것은 아닙니다. 검색 Span에는 원문 대신 다음처럼 진단 가능한 구조를 남깁니다.

- **Index·Embedding Version**: 배포 전후 품질 변화를 비교합니다. 안정된 Version을 사용합니다.
- **검색 전략**: Keyword·Vector·Hybrid를 구분합니다. 낮은 Cardinality Enum으로 기록합니다.
- **`top_k`**: 요청한 후보 수를 확인합니다. Metric Label로 무분별하게 사용하지 않습니다.
- **결과 수**: Empty Retrieval을 탐지합니다. 결과 수 자체가 정답성을 의미하지는 않습니다.
- **Filter Policy Version**: Tenant·ACL Filter 변경을 추적합니다. 실제 Tenant ID는 기록하지 않습니다.
- **Re-ranking Version**: 순위 변경 원인을 추적합니다. Model Version과 분리합니다.
- **문서 참조 Digest**: 평가 시 같은 근거 집합인지 비교합니다. 원문이나 내부 경로를 대신하지 않습니다.

검색 점수도 해석에 주의합니다. Cosine Similarity, Distance와 Re-ranker Score는 척도와 방향이 다르고 Model Version이 바뀌면 분포도 달라질 수 있습니다. 서로 다른 Index·Model의 점수를 한 Dashboard에서 절대값으로 비교하지 않습니다.

```text
retrieval API 성공
  ≠ 관련 문서 검색 성공
  ≠ 충분한 근거 확보
  ≠ 최종 답변의 사실성 보장
```

온라인에서 결과 수·점수 분포·지연은 **Proxy Signal**로 사용할 수 있지만, Recall·근거 충실도·정답성은 Label과 Rubric이 있는 Evaluation으로 따로 판정해야 합니다.

## 8. Model 호출은 요청·응답 Version과 비용 신호를 남긴다

Model Span에는 Provider 이름 하나만 남겨서는 회귀 원인을 찾기 어렵습니다.

- 요청한 Model과 실제 응답한 Model
- Agent·Prompt·Tool Registry Version
- 입력·출력 Token 수
- 전체 지연과 Streaming Time to First Chunk
- Timeout·Rate Limit·Provider Error
- Fallback 적용 여부와 Fallback 대상

OpenTelemetry GenAI Metric 규약은 현재 다음과 같은 이름을 제안하고 있습니다.

```text
gen_ai.client.token.usage
gen_ai.client.operation.duration
gen_ai.client.operation.time_to_first_chunk
gen_ai.invoke_agent.duration
gen_ai.invoke_agent.inference_calls
gen_ai.invoke_agent.tool_calls
gen_ai.execute_tool.duration
```

이 이름들은 2026-08-09 현재 Development 상태입니다. Dashboard Query에 직접 흩어 넣기보다 내부 Metric Adapter와 Versioned Dashboard를 두어 규약 변경의 영향을 제한합니다.

비용은 Token 수만으로 끝나지 않습니다. Cache Hit, 재시도, Fallback, Tool 호출과 Retrieval 비용을 함께 봐야 합니다. 다만 가격표는 Provider와 계약에 따라 바뀌므로, Trace에 계산된 통화 비용을 영구 사실처럼 저장하기보다 **사용량과 적용한 가격표 Version**을 분리하는 편이 재계산에 유리합니다.

## 9. “실행 오류”와 “품질 실패”를 같은 ERROR로 표시하지 않는다

Span Status는 실행이 기술적으로 실패했는지를 나타냅니다.

- Timeout, 연결 실패, Protocol 오류와 처리하지 못한 예외는 `ERROR`가 될 수 있습니다.
- 정책이 정상적으로 `deny`를 반환했다면 예상된 업무 결과일 수 있습니다.
- 사용자가 승인을 거부했다면 시스템 장애가 아닙니다.
- Model 호출은 성공했지만 답변이 부정확했다면 Provider Span은 기술적으로 성공입니다.

품질 실패를 모두 `ERROR`로 만들면 운영 장애율과 AI 품질이 뒤섞입니다. 대신 Evaluation Event나 별도 평가 저장소에 남깁니다.

```json
{
  "evaluation_id": "eval-fixture-019",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "dataset_version": "agent-regression-fixture-v6",
  "rubric_version": "trajectory-rubric-fixture-v4",
  "evaluator_type": "deterministic_rule",
  "scores": {
    "tool_selection": 1,
    "source_binding": 0,
    "approval_compliance": 1
  },
  "label": "FAIL"
}
```

반대로 보안 불변식 위반은 평균 품질 점수로 상쇄하지 않습니다. 다른 Tenant 데이터 노출, 승인 없는 파괴 작업과 Secret 유출은 별도 Blocking Gate로 취급합니다.

## 10. Trace와 Audit Trail을 연결하되 대체하지 않는다

Trace와 Audit Trail은 일부 Field를 공유하지만 목적이 다릅니다.

- **Trace**
  - 주목적: 성능·오류·품질 원인 진단
  - 수집: Sampling 가능
  - 구조: Span Tree·Link·Event
  - 보존: 진단에 필요한 기간
  - 접근: 운영·개발 역할의 제한된 접근
  - 무결성: 관측 Backend 정책 적용
- **Audit Trail**
  - 주목적: 중요 행위의 책임과 결과 증명
  - 수집: 위험 작업은 완전 수집
  - 구조: 주체·정책·승인·대상·결과 Event Chain
  - 보존: 법규·계약·업무 정책에 따른 기간
  - 접근: 감사 역할과 Tenant 범위 분리
  - 무결성: Append-only·변조 방지 등 강화

Ticket 생성 같은 쓰기 작업은 다음 연결 고리를 갖습니다.

```text
Trace
  trace_id ─ tool_call_id ─ operation_id
                         │
                         ▼
Audit Trail
  decision_id ─ approval_id ─ side_effect_id ─ result
```

Audit Event에 `trace_id`를 참조로 넣을 수 있지만 Trace가 Sampling되거나 만료돼도 Audit 증거는 독립적으로 남아야 합니다. 반대로 Trace에 사용자·Tenant·전체 Tool 인자를 복제해 Audit 저장소처럼 만들지 않습니다.

## 11. 민감정보는 “수집 후 Masking”보다 “기본 미수집”이 우선이다

Agent Trace에는 다음 정보가 자연스럽게 흘러들 수 있습니다.

- 사용자 Prompt와 대화 이력
- 검색 Query·문서 Chunk·내부 URL
- Tool 인자·결과·파일명
- Access Token·Cookie·Authorization Header
- 사용자·Tenant·회의·업무 식별자
- System Instruction과 내부 정책

OpenTelemetry GenAI 규약도 Model 입력·출력, System Instruction, Retrieval Query와 Tool 인자·결과를 민감할 수 있는 Opt-In 정보로 다룹니다. 운영 기본 정책은 다음처럼 잡습니다.

```text
기본: 원문 미수집
  → 낮은 Cardinality Metadata만 수집
  → 진단 필요 시 승인된 환경·기간·대상에 한해 제한적 Capture
  → 별도 보호 저장소에 원문 저장 후 Trace에는 Reference만 기록
  → 만료 후 원문 삭제, 평가 Dataset에는 정제본만 승격
```

Collector의 Attribute·Filter·Redaction·Transform Processor는 두 번째 방어선으로 사용할 수 있습니다. 가장 안전한 방법은 민감정보를 애플리케이션에서 처음부터 Telemetry에 넣지 않는 것입니다.

Hash도 만능이 아닙니다. 사번, 순차 ID, 짧은 이메일 목록처럼 후보 공간이 작은 값은 Hash를 대입해 추측할 수 있습니다. 목적에 따라 무작위 Tokenization, 집계, 삭제와 별도 Mapping Vault를 검토합니다.

## 12. Baggage에는 권한과 개인정보를 싣지 않는다

OpenTelemetry Baggage는 서비스 경계를 넘어 Key·Value를 전파하고 Span이나 Log를 보강할 수 있습니다. 편리하지만 자동 계측이 Baggage를 제3자 API 요청까지 전달할 수 있고, 내장된 무결성 검사가 없습니다.

따라서 엔터프라이즈 Agent의 기본 정책은 보수적으로 잡습니다.

- Access Token, Email, 사용자 원본 ID와 Tenant ID를 넣지 않습니다.
- Baggage 값을 인가·승인·과금의 신뢰 입력으로 사용하지 않습니다.
- 외부 Provider 호출 전에 허용 목록 밖의 Baggage를 제거합니다.
- 꼭 필요한 값은 낮은 민감도·낮은 Cardinality의 기술 Metadata로 제한합니다.
- 신뢰 경계마다 전파·재시작 정책을 명시합니다.

```text
관측 Context가 전달됨
  ≠ 사용자 신원이 검증됨
  ≠ Tenant가 확정됨
  ≠ Tool 실행이 허용됨
```

인증·Tenant·권한은 검증된 Security Context에서 다시 확정하고, Trace Context는 진단 상관관계에만 사용합니다.

## 13. Sampling은 무작위 비율 하나로 끝내지 않는다

모든 Trace를 영구 저장하면 비용과 개인정보 노출 면적이 커집니다. 반대로 무작위 1%만 남기면 드물지만 위험한 실패를 놓칠 수 있습니다.

Head Sampling은 요청 시작 시 결정하므로 단순하고 비용을 빨리 줄이지만 결과를 보기 전에 선택합니다. Tail Sampling은 Trace가 끝난 뒤 오류·지연·속성을 보고 결정할 수 있지만 Collector가 Trace를 일정 시간 Buffering해야 합니다.

Agent에서는 다음 조합을 고려할 수 있습니다.

- 처리하지 못한 오류 Trace는 높은 우선순위로 보존
- Timeout·Fallback·Retry Exhaustion Trace 보존
- 승인 없는 위험 작업 시도는 Audit에서 100% 기록하고 관련 Trace 보존 우선순위 상향
- 비정상적으로 많은 Model·Tool 반복 호출 Trace 보존
- 느린 Trace 보존
- 품질 평가 FAIL Trace 보존
- 정상 Trace도 기준선 비교를 위해 일정 비율 무작위 보존

```text
오류·고위험·느린 Trace  ── 우선 보존
평가 FAIL Trace          ── 우선 보존
정상 Trace               ── 대표 표본 보존
Audit Event              ── Sampling 금지
```

주의할 점도 있습니다.

1. Tail Sampling 결정 전에 품질 평가 결과가 늦게 도착하면 같은 Pipeline에서 즉시 판정하기 어렵습니다. Trace ID 기반 후속 보존·Dataset 승격 정책을 따로 둘 수 있습니다.
2. 장시간 Workflow 전체를 한 Trace로 만들면 Tail Sampling 대기·Memory 요구가 커집니다. 실행 구간별 Trace와 Span Link가 더 적합할 수 있습니다.
3. 사용자 입력으로 Sampling Priority를 직접 올리게 하면 Telemetry 비용을 악용할 수 있습니다.
4. Sampling은 Audit 완전성을 대신하지 않습니다.

## 14. Metric은 지연·행동·품질·안전을 분리한다

Dashboard 하나에 모든 숫자를 섞기보다 네 영역으로 나눕니다.

### 실행 건강 상태

- Agent End-to-End 지연 분포
- Model·Retrieval·Tool 단계별 지연
- Timeout·Rate Limit·Protocol Error 비율
- Queue 대기·승인 대기·실행 시간을 분리한 분포
- 재시도·Fallback·Circuit Breaker 상태

### Agent 행동

- 한 Agent 실행당 Model 호출 수
- 한 Agent 실행당 Tool 호출 수
- Tool별 성공·거부·실패 분포
- 불필요 호출·반복 호출·최대 Step 초과
- 승인 요청·허용·거부·만료 분포

### 품질

- Task Success와 사용자 수정·재시도 비율
- Retrieval Empty·근거 부족 판정
- Tool 선택·인자 출처·호출 순서 평가
- 근거 충실도·정답성·형식 준수 평가
- Model·Prompt·Index·Tool Schema Version별 회귀

### 안전과 비용

- 권한 거부·교차 Tenant 접근 시도
- 승인 없는 중요 작업 실행 수 — 목표는 항상 0
- Secret·PII Canary 탐지
- 입력·출력 Token과 Cache 사용량
- Fallback·재시도로 증가한 호출량

Metric Label에는 원문 Query, Trace ID, 사용자·문서·Tool Call ID처럼 Cardinality가 큰 값을 넣지 않습니다. Version, 환경, 안정된 Tool 이름과 낮은 Cardinality Error Type 정도로 제한하고, 개별 실행은 Metric의 Exemplar나 Trace 링크로 이동합니다.

## 15. 운영 Trace를 회귀 평가로 되돌리는 폐쇄 루프를 만든다

관측성의 목적은 Dashboard를 보는 데서 끝나지 않습니다. 운영에서 발견한 실패를 재현 가능한 평가 자산으로 바꿔야 같은 문제가 다시 배포되지 않습니다.

![운영 Trace에서 실패·경계 사례를 선별하고 익명화·최소화를 거쳐 버전 평가 데이터셋으로 승격하는 흐름](assets/blog-72-trace-to-evaluation-dataset.png)

*그림 1. 운영 Trace를 안전한 평가 Dataset으로 승격하는 단계*

![버전 평가 데이터셋을 Offline Regression과 Release Gate, Shadow·Canary를 거쳐 운영 Trace로 되돌리는 폐쇄 루프](assets/blog-72-evaluation-release-feedback-loop.png)

*그림 2. 평가 Dataset을 Release Gate와 Shadow·Canary로 연결하는 단계*

평가기는 위험도에 따라 조합합니다.

- **결정적 규칙**: Tool 이름, 인자 Schema, 식별자 출처, 승인 순서, Tenant 경계
- **업무 검증 코드**: 실제 Side Effect 상태, 중복 생성, 멱등성
- **사람 평가**: 애매한 업무 품질, Rubric 보정, 고위험 사례
- **LLM-as-Judge**: 의미적 충실도와 설명 품질의 보조 평가

LLM Judge만으로 Release Gate를 만들면 Judge Model·Prompt의 변화가 판정을 흔들 수 있습니다. Dataset, Rubric, Evaluator, Model과 Prompt Version을 모두 기록하고 사람 평가와 결정적 Rule로 보정합니다.

운영 Trace를 Dataset으로 승격할 때는 원문을 그대로 복사하지 않습니다.

1. 수집 목적과 사용 권한을 확인합니다.
2. 개인정보·고객 데이터·내부 식별자를 제거하거나 합성값으로 치환합니다.
3. Tool을 Replay할 때 실제 쓰기 Side Effect를 차단합니다.
4. 실패를 재현하는 데 필요한 최소 Field만 남깁니다.
5. 원본 Trace와 정제 평가 Case의 접근 권한·보존 기간을 분리합니다.

## 16. 합성 장애 사례로 Trace를 읽어 본다

다음은 실제 운영 수치가 아닌 설명용 Trace입니다.

```text
invoke_agent knowledge-action-agent                         2.84s
├─ retrieval meeting-knowledge                             0.18s  OK
│    result.count=0, index.version=index-fixture-v5
├─ chat model-fixture-v1                                   1.21s  OK
├─ policy.evaluate ticket.create                           0.02s  OK
└─ tools/call ticket.create                                0.09s  ERROR
     error.type=invalid_source_binding
```

최종 현상은 “티켓 생성 실패”지만 Trace를 보면 원인이 더 구체적입니다.

1. Retrieval은 기술적으로 성공했지만 결과가 0건입니다.
2. Model은 근거가 없는 상태에서 `ticket.create`를 선택했습니다.
3. Policy는 사용자의 Tool 권한만 확인했기 때문에 통과했습니다.
4. Tool 입력 검증기가 Ticket의 근거 식별자가 검색 결과에서 유래하지 않았음을 발견해 실행을 차단했습니다.

이 실행에서 Model Span과 Retrieval Span을 모두 `ERROR`로 바꿀 필요는 없습니다. 대신 다음 조치를 연결합니다.

- `source_binding=FAIL` 평가 Label 추가
- Empty Retrieval에서 쓰기 Tool을 제안하지 않는 Negative Case 생성
- 검색 결과가 없을 때 사용자에게 추가 정보를 요청하는 정책 추가
- `invalid_source_binding` Trace 보존 우선순위 상향
- Regression Gate에서 승인 전 입력 출처 검증을 Zero-tolerance로 고정

Trace는 “어디서 실패했는가”를 보여 주고, Evaluation은 “업무적으로 무엇이 잘못됐는가”를 판정하며, Tool Validator는 Side Effect가 발생하기 전에 안전 경계를 강제합니다.

## 17. 단계적으로 도입한다

처음부터 모든 Prompt와 Span을 수집할 필요는 없습니다. 다음 순서가 현실적입니다.

### 1단계 — Trace 연결

- Gateway·Orchestrator·MCP Client·Server의 `traceparent` 전파
- `service.name`, 환경과 배포 Version 설정
- 오류·지연·Tool 이름만으로 기본 Trace Tree 확인

### 2단계 — AI 실행 경계

- Agent·Retrieval·Model·Policy·Approval·Tool Span 분리
- Agent·Prompt·Index·Tool Schema·Policy Version 기록
- 자동·수동 계측 중복 제거

### 3단계 — 데이터 최소화

- Prompt·Chunk·Tool 인자 기본 미수집
- Attribute Allowlist와 Collector Redaction
- Baggage·Header·Error Message 유출 Test
- 역할별 접근 권한과 보존 기간 적용

### 4단계 — Metric·SLO

- End-to-End와 단계별 지연 분포
- 오류·Fallback·반복 호출·Token·Tool 호출 수
- 안전 불변식과 비용 Guardrail

### 5단계 — 평가 피드백 루프

- 실패 Trace 선별·정제
- Dataset·Rubric·Evaluator Versioning
- Offline Regression과 Release Gate
- Shadow·Canary 후 운영 품질 비교

### 6단계 — Sampling·운영

- 오류·느린·고위험 Trace 중심 Tail Sampling
- Collector Drop·Queue·Export 실패 자체 관측
- Dashboard·Alert·Runbook Owner 지정
- 규약·SDK Version Upgrade Gate

## 18. 흔한 안티패턴

### 모든 Prompt와 결과를 기본 저장한다

진단은 쉬워 보이지만 개인정보·기밀·비용·접근 통제 문제가 커집니다. 기본 미수집 후 제한적 Opt-In을 사용합니다.

### 한 Agent 요청을 Span 하나로만 남긴다

전체 지연만 보이고 검색·모델·Tool·승인 중 어디가 문제인지 알 수 없습니다. 책임 경계별 Span으로 나눕니다.

### 자동 계측과 수동 계측을 겹친다

같은 HTTP·Model·MCP 호출이 두 번 보이고 지연·호출 수가 부풀려집니다. 자동 계측 Coverage를 확인한 뒤 부족한 경계만 추가합니다.

### Trace를 Audit Trail로 사용한다

Sampling·만료·접근 정책이 다릅니다. 위험 작업 감사 Event는 독립적으로 완전 수집합니다.

### Baggage의 Tenant ID로 권한을 결정한다

Baggage에는 내장 무결성 보장이 없고 외부로 전파될 수 있습니다. 검증된 Security Context에서 Tenant를 다시 확정합니다.

### 품질이 낮은 응답을 모두 Span ERROR로 만든다

기술 장애와 의미 품질을 섞습니다. 실행 Status와 Evaluation Score를 분리합니다.

### Metric Label에 Query와 사용자 ID를 넣는다

Cardinality와 개인정보 노출이 폭증합니다. 집계 축은 낮은 Cardinality Version·Operation·Tool·Error Type으로 제한합니다.

### 운영 Trace를 그대로 Replay한다

실제 Tool이 다시 호출돼 Ticket·전송·삭제가 중복 실행될 수 있습니다. Fixture Server, Read-only Mode, Mock Tool과 Side Effect 차단을 사용합니다.

### Development 규약을 영구 Schema로 가정한다

GenAI·MCP Semantic Convention은 바뀔 수 있습니다. 규약·SDK Version을 고정하고 Adapter와 Migration Test를 둡니다.

## 19. 운영 체크리스트

### Trace 모델

- [ ] Gateway→Orchestrator→MCP Client→Server의 Context가 끊기지 않는다.
- [ ] Agent·Retrieval·Model·Policy·Approval·Tool 경계가 구분된다.
- [ ] 장시간 승인·재개는 Workflow ID와 Span Link로 연결한다.
- [ ] 자동·수동 계측이 같은 호출을 중복 기록하지 않는다.
- [ ] Trace ID, Workflow ID, Operation ID와 Audit ID의 목적이 분리돼 있다.

### Version과 속성

- [ ] Agent·Prompt·Model·Index·Tool Schema·Policy Version을 기록한다.
- [ ] `error.type`은 안정된 낮은 Cardinality Code다.
- [ ] Metric Label에 사용자·문서·Trace ID와 원문 Query가 없다.
- [ ] 애플리케이션 전용 속성의 Schema·Owner·보존 정책이 있다.
- [ ] GenAI·MCP 규약과 SDK Version Upgrade Test가 있다.

### 데이터 보호

- [ ] Prompt·응답·검색 Chunk·Tool 인자 원문은 기본 미수집이다.
- [ ] Token·Cookie·Authorization Header·Secret을 기록하지 않는다.
- [ ] Baggage를 권한 입력으로 사용하지 않는다.
- [ ] Collector Allowlist·Redaction과 유출 Canary Test가 있다.
- [ ] Trace·평가 Dataset·Audit 저장소의 접근 권한과 보존 기간이 분리돼 있다.

### 운영과 평가

- [ ] 오류·느린·Fallback·고위험 Trace의 Sampling 정책이 있다.
- [ ] 정상 Trace도 기준선 비교를 위한 대표 표본을 남긴다.
- [ ] Audit Event는 Trace Sampling과 무관하게 완전 수집한다.
- [ ] 실행 오류와 품질 실패를 다른 신호로 판정한다.
- [ ] 실패 Trace를 정제한 회귀 Case로 되돌리는 절차가 있다.
- [ ] Replay 환경에서 쓰기 Side Effect가 차단된다.
- [ ] Dataset·Rubric·Evaluator·Model·Prompt Version이 평가 결과에 연결된다.

## 20. 마무리

AI Agent의 관측성은 LLM 호출 Log를 저장하는 기능이 아닙니다.

```text
한 번의 사용자 요청
  → 분산 Trace로 실행 경로 연결
  → Metric으로 전체 상태 집계
  → Evaluation으로 업무 품질 판정
  → Audit Trail로 중요 행위 증명
  → 실패 Trace를 회귀 Dataset으로 환류
```

좋은 Trace는 “모델이 무슨 생각을 했는가”를 무제한 저장하지 않습니다. **어떤 Version과 권한 아래에서 어떤 검색·모델·Tool 경계를 통과했고, 어디서 실패했으며, 실제 Side Effect는 무엇이었는지**를 최소한의 안전한 Metadata로 재구성하게 합니다.

핵심 원칙은 다음과 같습니다.

1. Trace, Metric, Evaluation과 Audit의 목적을 분리합니다.
2. Java Gateway에서 Python Agent와 MCP Server까지 W3C Trace Context를 연결합니다.
3. RAG·LLM·Policy·Approval·Tool을 책임 경계별 Span으로 나눕니다.
4. Prompt·검색 Chunk·Tool 인자 원문은 기본적으로 수집하지 않습니다.
5. 실행 오류와 품질 실패를 다른 신호로 기록합니다.
6. 오류·고위험 Trace를 우선 보존하되 Audit은 Sampling하지 않습니다.
7. 운영 실패를 정제된 평가 Dataset과 Release Gate로 되돌립니다.

운영 가능한 Agent는 좋은 답을 생성하는 것에서 끝나지 않습니다. **좋은 답과 나쁜 답, 안전한 실행과 차단된 실행, 느린 단계와 실패한 Side Effect를 나중에 설명하고 같은 문제의 재발을 막을 수 있어야 합니다.**

---

## 21. 공식 참고자료

- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OpenTelemetry Python Manual Instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [OpenTelemetry Baggage](https://opentelemetry.io/docs/concepts/signals/baggage/)
- [OpenTelemetry Handling Sensitive Data](https://opentelemetry.io/docs/security/handling-sensitive-data/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [OpenTelemetry Tail-based Sampling Example](https://opentelemetry.io/docs/demo/sample-configurations/tail-sampling-service-criticality/)
- [OpenTelemetry GenAI Semantic Conventions Repository](https://github.com/open-telemetry/semantic-conventions-genai)
- [OpenTelemetry GenAI Agent Spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- [OpenTelemetry GenAI Metrics](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md)
- [OpenTelemetry MCP Semantic Conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md)
- [MCP SEP-414: OpenTelemetry Trace Context Propagation](https://modelcontextprotocol.io/seps/414-request-meta)
- [MCP 2026-07-28 Specification Announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [LangSmith Evaluation Concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
- [NIST AI Resource Center: TEVV and AI RMF Resources](https://airc.nist.gov/)

> 이 글은 2026년 8월 9일 기준 W3C, OpenTelemetry, Model Context Protocol과 NIST의 공식 공개 문서를 바탕으로 작성했습니다. OpenTelemetry GenAI·MCP Semantic Convention과 일부 Collector Component는 Development·Alpha·Beta 상태가 섞여 있으며 변경될 수 있습니다. 실제 적용 시 사용하는 SDK, Collector Distribution, Semantic Convention과 MCP Protocol Version을 고정하고, 조직의 개인정보·보안·감사·보존 정책에 맞게 별도 검토해야 합니다.
