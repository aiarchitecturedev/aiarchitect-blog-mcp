# 메시지 버스 기반 멀티 에이전트 협업: 에이전트별 MCP·RAG 권한 분리

하나의 거대한 AI Agent (AI 에이전트)에게 회의록 검색, 웹 조사, 초안 작성, 사실 검증, 최종 편집을 모두 시키면 초기 개발은 빠릅니다.

문제는 이 에이전트에게 붙는 권한이 시간이 지날수록 계속 늘어난다는 점입니다.

```text
단일 거대 에이전트가 갖게 되는 권한
  → 회의 지식베이스 읽기
  → 웹 지식베이스 읽기
  → 외부 검색 도구 호출
  → 파일 업로드·삭제 도구 호출
  → 요약 재생성·저장 도구 호출
  → 그리고 위 모든 것을 하나의 System Prompt로 통제
```

권한이 한곳에 모이면 두 가지가 동시에 나빠집니다. 첫째, 프롬프트 한 줄이 오작동하면 그 파급 범위 (Blast Radius)가 모든 도구와 모든 지식베이스로 번집니다. 둘째, "이 작업에는 이 도구가 정말 필요한가"를 판단할 수 있는 경계가 사라집니다.

이 글은 이 문제를, 필자가 개발·상용화 검증 단계에서 설계·구현한 Python 멀티 에이전트 오케스트레이터를 기준으로 정리합니다. 이 오케스트레이터는 여러 AI Agent가 **Message Bus (메시지 버스)** 로 협업하고, 각 에이전트가 사용하는 MCP 서버·RAG 컬렉션·동료 에이전트 호출 권한을 **Allowlist (허용 목록)** 로 제한합니다.

이 글은 교체 가능한 [멀티 LLM Provider Core](https://aiarchitect.tistory.com/13)나 [자연어→도구 호출 통합 테스트](https://aiarchitect.tistory.com/14)를 다시 설명하지 않습니다. 회의 지식베이스 구축 방식은 [회의 RAG 파이프라인](https://aiarchitect.tistory.com/4)을 전제로 합니다. 이 글의 범위는 오직 **에이전트 사이의 협업 방식과 에이전트별 권한 분리**입니다.

```text
User · FastAPI/SSE UI
        │
        ▼
   Orchestrator
 ┌───────────────────────────────────────┐
 │  Message Bus (Command · Reply/Event)   │
 │  Delegation · Trace                    │
 │  Budget · Depth · Fan-out Guard        │
 └──┬───────┬───────────┬────────────┬────┘
    ▼       ▼           ▼            ▼
Researcher Writer  Source Verifier  External Fact
   │        │           │           Verifier
   │        │           │              │
   │ MCP·RAG│ MCP·RAG   │ MCP·RAG      │ MCP·RAG
   │ allow. │ allow.    │ allow.       │ allow.
   ▼        ▼           ▼              ▼
회의 KB   초안 도구   회의 KB(읽기전용) 웹 KB
웹 KB                 ·출처 검증        ·사실 검증
```

## 1. 이 글이 다루는 것과 다루지 않는 것

먼저 범위를 못 박아 두겠습니다.

| 구분 | 이 글의 범위 | 참고 글 |
|---|---|---|
| 모델 교체 (GPT·Claude·Gemini) | 다루지 않음 | https://aiarchitect.tistory.com/13 |
| 자연어→도구 호출 통합 테스트 | 다루지 않음 | https://aiarchitect.tistory.com/14 |
| 회의 오디오→RAG 색인 | 전제로만 참조 | https://aiarchitect.tistory.com/4 |
| 에이전트 간 협업·위임 | 다룸 | 이 글 |
| 에이전트별 권한 분리 | 다룸 | 이 글 |

즉 "여러 모델을 어떻게 붙일까"가 아니라, **"여러 에이전트를 어떻게 안전하게 협업시킬까"** 가 주제입니다. 각 에이전트가 내부적으로 어떤 모델을 쓰는지는 Provider Core가 흡수한다고 가정합니다.

## 2. 왜 멀티 에이전트인가: 단일 거대 에이전트의 한계

단일 에이전트를 여러 에이전트로 나누는 것은 언제나 옳은 선택이 아닙니다. 멀티 에이전트 구조는 지연 시간 (Latency), 비용, 유지보수 복잡도를 대부분 증가시키므로, 과제가 정말로 그 구조를 요구할 때만 도입해야 합니다.

그럼에도 다음 신호가 겹치면 분리를 검토할 가치가 있습니다.

| 신호 | 단일 에이전트에서의 증상 | 분리로 얻는 것 |
|---|---|---|
| System Prompt 비대화 | 하나의 지시문에 역할·규칙·도구 사용법이 뒤엉킴 | 역할별로 짧고 검증 가능한 지시문 |
| 권한 집중 | 한 에이전트가 모든 도구·KB 접근 | 역할별 최소 권한 |
| 검증 부재 | 작성자가 자기 출력을 스스로 검증 | 검증자 (Verifier)가 독립적으로 재검토 |
| 컨텍스트 오염 | 조사 자료와 초안이 같은 문맥에 섞임 | 단계별 컨텍스트 격리 |
| 관측성 부족 | "왜 이렇게 했는지" 추적 곤란 | 위임 단위로 추적 가능 |

핵심은 "더 똑똑한 하나"가 아니라 **"책임이 분리된 여러 개"** 라는 점입니다. 사람 조직에서 조사·작성·검토를 나누는 이유와 같습니다.

## 3. 역할 분리: 리서처·작성자·검증자

필자가 구현한 오케스트레이터는 역할 기반 (Role-based) 전략을 씁니다. 대표 역할은 다음과 같습니다.

| 역할 | 책임 | 대표 권한 | 대표 금지 |
|---|---|---|---|
| Researcher (리서처) | 회의·웹 지식베이스에서 근거 수집 | 회의 KB·웹 KB 읽기, 검색 도구 | 초안 저장·파일 삭제 |
| Writer (작성자) | 수집된 근거로 초안 생성 | 초안 생성·수정 도구, 리서처 결과 참조 | 지식베이스 직접 검색, 회의·웹 KB 쓰기, 외부 게시·삭제 도구 |
| Source Verifier (출처 검증자) | 초안이 인용한 회의 청크의 내용·출처·버전 대조 | 회의 KB 읽기(전용), 출처 검증 도구 | 초안 수정·저장, 웹 검색 |
| External Fact Verifier (외부 사실 검증자) | 초안의 외부(기술·시장·정책) 주장 검증 | 웹 KB 읽기, 사실 검증 도구 | 초안 수정·저장, 회의 KB 접근 |
| Orchestrator (오케스트레이터) | 위임 결정·상태 관리 | Message Bus, 위임 도구 | 도메인 도구 직접 실행 |

이 표에서 중요한 것은 "권한" 열보다 **"금지" 열** 입니다. 각 역할은 필요한 일만 할 수 있고, 다른 역할의 권한을 빌려 쓸 수 없습니다. 이것이 뒤에서 설명할 Allowlist의 목적입니다.

역할 구성은 고정된 정답이 없습니다. 공개 연구와 프레임워크에서도 일반적으로 통용되는 패턴은 다음 흐름입니다.

```text
Orchestrator → Researcher → Writer → Source Verifier ─┐
             (근거 수집)   (초안)   (회의 청크 대조)   ├→ Orchestrator
                                    External Fact Verifier ┘  (최종 판단)
                                    (외부 주장 검증)
```

검증을 하나의 역할로 두지 않고 두 갈래로 나눈 이유는 8절과 20절에서 설명합니다. 회의 청크 대조(Source Verifier)와 외부 사실 검증(External Fact Verifier)은 접근하는 지식베이스도 목적도 다르기 때문입니다.

## 4. 협업 방식 1: 직접 호출 vs 메시지 버스

에이전트가 서로 협업하는 방법은 크게 두 가지입니다.

**직접 호출 (Direct Call)** 은 한 에이전트가 다른 에이전트를 함수처럼 동기 호출합니다. 구현이 단순하지만 호출자가 피호출자를 알아야 하고, 호출 그래프가 코드에 하드코딩됩니다.

**Message Bus (메시지 버스)** 는 에이전트가 서로의 구체적인 인스턴스·엔드포인트를 알지 않고, 중앙 버스에 메시지를 발행 (Publish)하고 버스가 이를 대상 역할로 전달합니다. 이는 발행-구독 (Publish-Subscribe, Pub/Sub)의 느슨한 결합을 빌려오되, 실제로는 **지정 대상 Command와 Reply/Event를 함께 쓰는 메시지 브로커 기반 오케스트레이션** 입니다. 즉 순수 Pub/Sub 이벤트가 아니라, 위임 요청은 대상 역할을 지정하는 Command이고 그 결과는 Reply(또는 완료 Event)로 돌아옵니다.

버스를 흐르는 메시지는 성격이 다릅니다.

| 메시지 | 성격 | 예 |
|---|---|---|
| `task.delegation.request` | Command (지정 대상 명령) | 오케스트레이터 → 리서처 위임 |
| `task.delegation.result` | Reply / 완료 Event | 리서처 → 오케스트레이터 결과 반환 |
| `agent.status`, `run.terminated` | Event (상태 방송) | 진행·종료 알림 |

Pub/Sub 순수형의 "발행자는 처리자를 전혀 모른다"는 성질은 상태 방송 Event에는 맞지만, 위임 Command에는 맞지 않습니다. 위임에서 발행자는 **논리 역할** (`researcher`)은 알지만 그 역할을 담당하는 **구체적 인스턴스·엔드포인트** 는 모릅니다. 또한 Pub/Sub에서 응답을 받으려면 별도 응답 채널을 쓰는 Request-Reply가 필요하며, 이는 공식 패턴과도 일치합니다.

아래 비교는 **직접 호출의 전형적인 단순 구현** 을 기준으로 합니다. 직접 호출도 공통 Gateway·Middleware를 두면 권한·예산·Trace를 한곳에서 통제할 수 있으므로, 아래 차이는 필연이 아니라 기본 구현의 경향입니다.

| 항목 | 직접 호출 (단순 구현 기준) | Message Bus |
|---|---|---|
| 결합도 (Coupling) | 높음 (호출자↔피호출자) | 낮음 (버스가 중개) |
| 동기/비동기 | 주로 동기 | 비동기 가능 |
| 관측성 | 호출 스택에 흩어짐 | 이벤트 스트림으로 중앙화 |
| 권한 통제 지점 | 각 호출부(공통 미들웨어로 모을 수는 있음) | 버스의 발행·구독 정책 한 곳 |
| 루프 방지 | 스택 깊이로만 | 상관관계 ID·홉 수로 명시 |

필자가 구현한 오케스트레이터가 Message Bus를 택한 결정적 이유는 결합도가 아니라 **통제 지점의 단일화** 입니다. 모든 위임과 도구 호출이 버스를 통과하므로, 권한·예산·추적을 한곳에서 강제할 수 있습니다.

## 5. 협업 방식 2: 이벤트·토픽·위임 흐름

버스 위에서 협업은 이벤트 (Event)와 토픽 (Topic)으로 표현됩니다.

```text
Topic: task.delegation.request   (위임 요청)
Topic: task.delegation.result    (위임 결과)
Topic: tool.call.request         (도구 호출 요청)
Topic: tool.call.result          (도구 호출 결과)
Topic: agent.status              (진행 상태 알림)
Topic: run.terminated            (실행 종료·중단)
```

위임 (Delegation) 흐름은 다음과 같이 진행됩니다.

```text
1. Orchestrator가 task.delegation.request 발행
     to = "researcher", intent = "회의 근거 수집"
2. Researcher가 구독 → 자신의 allowlist 안에서만 도구 호출
3. Researcher가 task.delegation.result 발행 (근거 + 출처)
4. Orchestrator가 결과를 Writer에게 위임
5. Writer 초안 → Source Verifier(회의 인용 대조)
              → External Fact Verifier(외부 주장 검증)
              → Orchestrator 최종 판단
```

여기서 발행자는 대상 역할(`researcher`)은 지정하되, 그 역할을 담당하는 구체적 인스턴스는 몰라도 됩니다. 버스가 대상 역할 구독 정보에 따라 전달합니다. 다만 에이전트 협업에서는 이 느슨함이 곧 위험이 되므로, 다음 절부터의 권한 분리가 반드시 함께 가야 합니다.

## 6. 에이전트별 권한 분리 1: 왜 Allowlist인가

권한을 다루는 방법은 두 가지입니다. 하나는 "위험한 것만 막는" 차단 목록 (Denylist), 다른 하나는 "허용한 것만 되는" 허용 목록 (Allowlist)입니다.

에이전트 권한에서는 Allowlist가 원칙입니다. 이유는 최소 권한 (Least Privilege) 원칙과 같습니다. 새로운 도구·컬렉션·에이전트가 추가될 때, Denylist는 "막는 것을 잊으면" 곧바로 노출되지만, Allowlist는 "허용을 잊으면" 접근이 안 될 뿐입니다. 실패의 방향이 안전한 쪽입니다.

MCP 사양은 도구가 임의 코드 실행 경로가 될 수 있음을 강조하고, 신뢰된 서버에서 오지 않은 도구 설명은 신뢰하지 말 것과, 구현체가 견고한 인가·접근 통제를 갖출 것을 요구합니다. 즉 명시적 동의와 적절한 접근 통제로 승인된 동작만 허용해야 합니다. 에이전트별 Tool Allowlist는 이 요구를 오케스트레이터 수준에서 구현한 설계 선택입니다.

다만 뒤(9절, 실효 권한 논리곱)에서 다시 짚듯, 에이전트 Allowlist는 사용자·리소스 인가를 **대체하지 않습니다.** MCP의 전송 계층 인가는 HTTP 기반 구현에서는 선택 사항이지만, 사용하는 경우 서버가 매 요청의 토큰과 대상 audience를 검증해야 하며, 이 사용자·리소스 인가는 에이전트 Allowlist와 별개로 반드시 함께 성립해야 합니다.

## 7. 에이전트별 권한 분리 2: MCP 서버 Allowlist

각 에이전트는 자신이 호출할 수 있는 MCP 서버·도구를 명시적으로 허용받습니다.

```json
{
  "agent": "researcher",
  "mcp_servers": {
    "meeting-knowledge": {
      "tools": ["search_meeting_kb", "get_source_by_id"]
    },
    "web-knowledge": {
      "tools": ["search_web_kb"]
    }
  }
}
```

작성자(Writer)의 Allowlist는 훨씬 좁습니다.

```json
{
  "agent": "writer",
  "mcp_servers": {
    "draft-tools": {
      "tools": ["create_draft", "revise_draft"]
    }
  }
}
```

작성자에게는 지식베이스 검색 도구가 아예 없습니다. 작성자가 근거가 필요하면 리서처의 결과를 받아 쓰거나, 결과에 `needs_more_research` 상태를 실어 반환합니다. 이를 받은 오케스트레이터가 리서처 재위임 여부를 판단합니다(작성자는 동료를 직접 부르지 않고, 다음 절의 delegation matrix에서 호출 대상이 빈 배열입니다). 이렇게 하면 "작성자가 임의로 검색해 문맥을 오염시키는" 경로가 구조적으로 막힙니다.

Allowlist는 서버 단위가 아니라 **도구 단위** 로 내려가야 실효가 있습니다. 같은 MCP 서버라도 읽기 도구와 쓰기 도구는 권한이 다릅니다.

| 에이전트 | 허용 MCP 도구 | 서버 단위만 허용했을 때의 위험 |
|---|---|---|
| Researcher | 읽기·검색만 | 같은 서버의 삭제 도구까지 노출 |
| Writer | 초안 생성·수정 | 지식베이스 검색 오남용 |
| Source Verifier | 회의 KB 읽기·출처 검증 | 초안 저장 권한 획득 |
| External Fact Verifier | 웹 KB 읽기·사실 검증 | 초안 저장 권한 획득 |

## 8. 에이전트별 권한 분리 3: RAG 컬렉션 접근 범위

RAG (검색 증강 생성, Retrieval-Augmented Generation) 지식베이스도 에이전트별로 접근 범위를 나눕니다. 필자가 구현한 오케스트레이터는 두 도메인을 명확히 분리합니다.

| 컬렉션 | 내용 | 접근 가능 에이전트 |
|---|---|---|
| 회의 KB (Meeting KB) | 회의 요약·녹취 청크, 다국어 임베딩 | Researcher, Source Verifier |
| 웹 KB (Web KB) | 수집·정제된 웹 지식 청크 | Researcher, External Fact Verifier |

신뢰 도메인별 컬렉션 분리는 운영상 유용한 방어층입니다. 다만 컬렉션을 나누는 것만으로 보안 경계가 되지는 않습니다. 같은 DB 자격증명으로 모든 컬렉션에 접근할 수 있다면 강한 격리가 아니기 때문입니다. 실제 보안 경계는 검색 서비스의 **서버 측 인가** 로 강제합니다. 즉 검색 진입점에서 서버가 에이전트의 Allowlist에 따라 대상 컬렉션과 필수 필터를 중앙에서 생성하고, 별도 자격증명·네임스페이스와 객체 수준 재인가로 우회를 막습니다. 이 조건이 갖춰지면 메타데이터 필터도 유효한 방어층이 될 수 있지만, 서버가 필터 생성을 클라이언트에 맡기고 필터 한 줄이 빠지면 전 컬렉션이 노출되므로 에이전트 경계로는 약합니다.

```json
{
  "agent": "external-fact-verifier",
  "rag_collections": ["web-knowledge"],
  "note": "회의 KB 접근 불가 — 외부 주장 검증 근거는 공개 웹 지식으로 한정"
}
```

External Fact Verifier가 회의 KB에 접근하지 못하게 하는 것은 제약이 아니라 설계 의도입니다. 외부(기술·시장·정책) 주장 검증은 초안이 아니라 **독립된 외부 근거** 로 이뤄져야 하므로, 초안이 참조한 것과 같은 회의 원문에 다시 의존하지 않게 합니다.

반대로 회의 내부 결정 사항은 공개 웹에서 확인할 수 없습니다. 그래서 Source Verifier는 회의 KB를 **읽기 전용** 으로 다시 조회해, Writer가 인용한 회의 청크의 내용·출처·버전이 초안과 일치하는지 대조합니다. 여기서 "독립 검증"은 반드시 다른 출처를 쓴다는 뜻이 아니라, **작성자와 분리된 주체가 권위 있는 원문을 독립적으로 재조회한다** 는 뜻입니다. 다만 역할이 분리됐다고 오류가 통계적으로 독립되지는 않습니다. 같은 모델·프롬프트 계열·검색 서비스에 의존하면 같은 오류를 반복할 수 있습니다. 또한 회의 KB의 녹취 청크는 원본 음성이 아니라 STT 파생물일 수 있으므로, Source Verifier가 보장하는 것은 우선 **초안과 색인된 녹취·출처·버전의 일치** 이지 실제 발언의 완전한 진실성까지는 아닙니다. 중요한 인용은 타임코드·원본 음성 대조로 한 겹 더 확인하는 편이 안전합니다.

## 9. 에이전트별 권한 분리 4: 동료 에이전트 호출 Allowlist

세 번째 축은 "어떤 에이전트가 어떤 에이전트를 호출할 수 있는가"입니다.

```json
{
  "delegation_matrix": {
    "orchestrator": ["researcher", "writer", "source-verifier", "external-fact-verifier"],
    "researcher": [],
    "writer": [],
    "source-verifier": [],
    "external-fact-verifier": []
  }
}
```

이 예시에서 위임은 오케스트레이터에서만 나갑니다. 리서처·작성자·검증자(Source/External)는 서로를 직접 부를 수 없습니다. 이는 오케스트레이터 중심(Supervisor) 패턴에 해당하며, 위임 결정이 한곳에 모여 라우팅이 명확해지고 추적이 쉬워집니다.

동료 호출을 넓게 허용한 자유로운 협업(Swarm) 구조는 지연이 줄어들 수 있지만, 위임 경로가 폭발하고 루프가 생기기 쉽습니다. 엔터프라이즈 검증 단계에서는 **호출 경로를 좁게 고정** 하는 편이 감사와 안정성에 유리합니다. 참고로 LangGraph 같은 프레임워크도 Supervisor 패턴을 제공하되, 최근에는 별도 라이브러리보다 **도구 기반 직접 구현** 을 권장하는데, 이는 위임 라우팅과 컨텍스트를 오케스트레이터가 더 직접 통제하려는 같은 동기에서 나옵니다.

세 가지 Allowlist를 종합하면 한 에이전트의 실효 권한은 여러 조건이 모두 참일 때만 허용되는 **조건의 논리곱** 으로 정의됩니다. MCP 도구·RAG 컬렉션·동료 에이전트·숫자 예산은 서로 다른 종류의 원소라 수학적 교집합으로 묶기 어렵기 때문에, 다음처럼 AND 조건으로 표현하는 편이 정확합니다.

```text
allow =
      agent_capability(tool)      # 에이전트가 이 도구/역량을 가졌는가
  AND topic_acl                   # 이 토픽에 발행·구독할 수 있는가
  AND principal_scope             # 실행 주체(사용자)의 권한 범위 안인가
  AND tenant_object_policy        # 테넌트·객체 수준 데이터 접근 정책을 만족하는가
  AND run_budget_available        # 현재 Run의 예산·깊이 한도가 남아 있는가
  AND approval_satisfied          # 필요한 사람 승인을 받았는가
```

이 논리곱은 에이전트 Allowlist(앞의 세 축)만으로 인가가 완성되지 않음을 보여줍니다. 사용자·테넌트·객체 권한이 함께 참이어야 최종 접근이 허용됩니다.

한 가지 더 있습니다. 역할별 Allowlist는 그 역할이 **가질 수 있는 최대 권한**일 뿐, 요청별 최소 권한은 아닙니다. 예를 들어 리서처의 역할 Allowlist에는 회의 KB와 웹 KB가 모두 있지만, "지난 회의 결정 사항 정리" 작업에는 웹 KB가 필요 없을 수 있습니다. 그래서 실제 실행 권한은 역할 상한을 현재 Run이 발급한 Task Grant로 한 번 더 좁힙니다.

```text
실행 권한 = 역할별 최대 Allowlist ∩ 현재 Run의 Task Grant
```

역할 정책은 상한을 정하고, Task Grant는 이번 작업에 실제 필요한 도구·컬렉션만 남깁니다. 이렇게 해야 "역할은 넓게 열어 두되 매 작업은 좁게"라는 최소 권한이 성립합니다.

## 10. 컨텍스트/메시지 계약 1: 다른 에이전트의 출력은 검증 대상이다

멀티 에이전트에서 가장 흔한 오해는 "같은 시스템 안의 에이전트가 보낸 메시지는 믿을 수 있다"는 것입니다.

그렇지 않습니다. 리서처가 수집한 웹 근거에는 간접 프롬프트 주입 (Indirect Prompt Injection) 문장이 섞여 있을 수 있습니다. 그 문장이 리서처의 결과 메시지를 타고 작성자·오케스트레이터로 넘어가면, "내부 메시지"라는 이유로 신뢰되는 순간 공격이 전파됩니다.

공개 연구에서도 다중 에이전트 시스템의 대표 위험으로 에이전트 간 통신 오염과, 한 에이전트의 잘못된 판단이 하류로 빠르게 번지는 연쇄 실패 (Cascading Failure)를 지적합니다.

그래서 메시지 계약 (Message Contract)의 원칙은 다음과 같습니다.

```text
다른 에이전트의 출력 = 외부 데이터로 취급
  → 신뢰 표식(출처·신뢰 수준)을 함께 전달
  → 명령이 아니라 데이터로만 소비
  → 실행(도구 호출) 직전에 원래 사용자 의도와 대조
```

프롬프트 주입 자체의 방어 기법은 별도 글(Prompt Injection 방어)의 범위이므로, 여기서는 "내부 메시지도 신뢰 경계를 넘는다"는 원칙만 강조합니다.

## 11. 컨텍스트/메시지 계약 2: 메시지 스키마와 신뢰 표식

메시지는 자유 텍스트가 아니라 구조화된 계약이어야 합니다. 여기서 결정적으로 중요한 것은 **누가 어떤 필드를 만드는가** 입니다. 에이전트가 채운 payload와, 신뢰된 런타임(Dispatcher·Broker·Policy Engine)이 생성·검증하는 봉투(envelope)를 분리해야 합니다.

```json
{
  "envelope": {
    "_comment": "신뢰된 런타임이 생성·서명·검증 — 에이전트가 임의로 못 바꿈",
    "message_id": "msg-EXAMPLE-001",
    "schema_version": "1.2.0",
    "message_type": "delegation.result",
    "run_id": "run-EXAMPLE-001",
    "correlation_id": "corr-EXAMPLE-001",
    "causation_id": "msg-EXAMPLE-000",
    "parent_message_id": "msg-EXAMPLE-000",
    "from_agent": "researcher",
    "to_agent": "orchestrator",
    "intent_hash": "sha256:EXAMPLE-intent-a1b2c3",
    "subject": "user-EXAMPLE",
    "tenant": "tenant-EXAMPLE",
    "to_topic": "task.delegation.result",
    "hop": 2,
    "trust": "internal-retrieved",
    "deadline": "2026-07-30T00:00:07Z",
    "attempt": 1,
    "idempotency_key": "idem-EXAMPLE-001",
    "step_id": "step-EXAMPLE-003",
    "branch_id": "branch-EXAMPLE-A",
    "expected_state_version": 4,
    "budget_snapshot": {
      "remaining_tool_calls": 7,
      "remaining_depth": 2
    }
  },
  "payload": {
    "_comment": "에이전트가 채움 — 외부 데이터로 취급, 실행 전 검증 대상",
    "findings": [
      {
        "text": "요점 요약 텍스트(설명용)",
        "source": "meeting-kb://EXAMPLE/chunk-12",
        "source_version": "rev-2026-07-01",
        "distance": 0.17,
        "metric": "cosine",
        "retrieval_score": 0.83,
        "score_transform_version": "v1"
      }
    ]
  }
}
```

핵심 원칙: **에이전트가 자기 신뢰 수준·깊이·예산을 스스로 선언한다고 신뢰가 생기지 않습니다.** 리서처가 payload에 `trust="internal-retrieved"`를 넣어도, 손상된 에이전트는 이를 임의로 조작할 수 있습니다. 따라서 다음 필드는 에이전트 payload가 아니라 **신뢰된 런타임이 생성하거나 검증** 해야 합니다.

| 필드 | 생성·검증 주체 | 목적 |
|---|---|---|
| `run_id` | 런타임 | 하나의 사용자 요청 단위 식별 |
| `correlation_id`·`causation_id`·`parent_message_id` | 런타임 | 위임 체인·인과관계 추적, 루프 탐지 |
| `from_agent`·`to_agent` | 런타임(인증된 발신자로 확정, 대상 역할 라우팅) | 발신 주체 위조 방지, 위임 대상 확정 |
| `intent_hash` | 런타임(payload의 `intent`를 정규화해 해시) | 순환 탐지용 정규화 의도 — 원문 `intent`는 payload에 둠 |
| `subject`·`tenant` | 런타임 | 실행 주체·테넌트 인가 |
| `hop` | 런타임(증가) | 위임 깊이 — 한도 초과 시 거부 |
| `trust` | 런타임(출처에 근거해 부여) | 데이터 신뢰 수준 표식 |
| `schema_version`·`message_type` | 런타임 | 스키마 진화·하위 호환 |
| `deadline`·`attempt`·`idempotency_key` | 런타임 | 만료·재시도·중복 제거 |
| `step_id`·`branch_id`·`expected_state_version` | 런타임 | 병렬 분기별 순서 역전·stale 결과 폐기 |
| `budget_snapshot` | 런타임(권위 상태는 Run 저장소) | 참고용 스냅샷 — 차감은 저장소에서 |

예산은 메시지를 따라 복사해 차감하지 않습니다. 병렬 팬아웃과 재전송에서 초과 사용을 막으려면 **Run 상태 저장소에서 원자적으로 차감** 하고, 메시지의 `budget_snapshot`은 표시·디버깅용 사본으로만 취급합니다.

payload의 `source`와 검색 점수를 함께 실어 나르는 것은 여전히 중요합니다. 최종 산출물에서 "이 문장은 어느 청크에서 왔고 근접도가 얼마였는지"를 그대로 인용할 수 있어야 검증과 감사가 성립합니다. 다만 검색 점수 표현은 주의가 필요합니다. ChromaDB는 통상 **거리(distance)** 를 반환하고 값이 낮을수록 더 가까운 결과이며, 기본 공간은 L2, cosine을 써도 반환값은 보통 cosine distance입니다. 따라서 `0.83` 같은 숫자를 무조건 "높은 유사도"로 해석할 수 없습니다. 반환 계약에는 원 거리(`distance`)와 거리 지표(`metric`)를 함께 싣고, 사람이 읽기 쉬운 `retrieval_score`를 제공한다면 거리에서 변환한 방식과 버전(`score_transform_version`)을 밝혀야 합니다. 또한 검색 점수는 근거의 진실성·신뢰도가 아니라 **질의와 청크의 근접도** 일 뿐이며, 임계값은 모델·청킹·도메인별 평가셋으로 보정해야 합니다.

## 12. 컨텍스트/메시지 계약 3: 루프·폭주 방지

에이전트가 서로 위임하다 보면 A→B→A→B 같은 순환이나, 하나의 요청이 수십 개의 하위 위임으로 폭발하는 팬아웃 (Fan-out)이 생길 수 있습니다.

방지 장치는 예산 (Budget)과 깊이 (Depth) 제한, 그리고 경로 기반 순환 탐지로 구현합니다.

주의할 점은 **`correlation_id`만으로 순환을 판단하면 안 된다** 는 것입니다. 같은 위임 체인은 정상적으로 동일한 `correlation_id`를 공유하므로, 그것이 반복된다는 이유로 거부하면 정상 단계까지 막힙니다. 순환은 "같은 (from, to, 정규화된 의도)가 **현재 인과 경로** 안에서 되풀이되는가"로 판단하고, 이와 별개로 **Run 전체 반복 횟수** 는 별도 카운터로 상한을 둡니다. 이렇게 나누면 Writer 재작성처럼 의도 해시가 같아도 인과 경로가 다른 정상 재위임은 통과하되, 무한 순환과 과도한 반복은 각각 막힙니다.

또한 검사와 차감이 따로 놀면 병렬 팬아웃에서 경쟁 상태가 생깁니다. 그래서 깊이·반복·팬아웃 검사, 위임 예산 차감, 방문 간선 등록을 **하나의 원자적 예약(reserve) 연산** 으로 묶습니다. 위임 예산은 도구 호출 예산과 종류가 다르므로 `remaining_delegations`로 별도 관리합니다.

```python
# 개념 코드 (실행용 아님) — 예산의 권위 상태는 Run 저장소에 있고,
# guard는 신뢰된 런타임이 확정한 envelope 값만 읽는다.

def guard_delegation(env, run_state, limits):
    # 1) 깊이 한도: 런타임이 증가시킨 hop만 신뢰.
    #    추가 위임을 실행하기 전 검사이므로 >= 로 상한을 막는다.
    if env["hop"] >= limits["max_depth"]:
        raise DelegationRejected("depth exceeded")

    # 2) 검사·차감·등록을 단일 원자 연산으로 수행(경쟁 상태 방지).
    #    - 위임 예산(remaining_delegations) 차감 — 도구 호출 예산과 별개
    #    - 현재 인과 경로의 (from, to, intent_hash) 반복 → cycle
    #    - Run 전체 반복 횟수 상한(max_repeat)
    #    - Run 팬아웃 상한(max_fanout)
    #    intent 원문은 payload에 있고, 런타임이 정규화한 intent_hash만 봉투에서 읽는다.
    edge = (
        env["run_id"],
        env["from_agent"],
        env["to_agent"],
        env["intent_hash"],
    )
    decision = run_state.reserve_delegation(
        run_id=env["run_id"],
        parent_message_id=env["parent_message_id"],  # 현재 인과 경로 식별
        edge=edge,
        limits=limits,  # max_repeat, max_fanout, delegation_budget
    )
    if not decision.allowed:
        raise DelegationRejected(decision.reason)  # depth/budget/cycle/fan-out

    return True
```

| 통제 | 값(설명용 Fixture) | 초과 시 |
|---|---|---|
| 최대 위임 깊이 | 예: 3 (`hop >= max_depth`) | 위임 거부·상위로 반환 |
| Run당 위임 예산 | 예: 유한한 상한 (reserve 시 원자적 차감) | 추가 위임 차단 |
| Run당 도구 호출 예산 | 예: 유한한 상한 (Run 저장소에서 차감) | 도구 호출 차단 |
| Run당 벽시계 시간 | 예: 상한 초 | Run 중단 |
| 최대 팬아웃 | 예: Run당 하위 위임 상한 | 추가 위임 거부 |
| 현재 경로 순환 | `(run_id, from, to, intent_hash)`가 인과 경로에서 재출현 | 순환 차단 |
| Run 전체 반복 | 동일 간선의 Run 누적 횟수 > `max_repeat` | 반복 차단 |

이 값들은 정답이 아니라 운영 환경에서 조정할 대상입니다. 중요한 것은 "무한히 돌 수 없다"는 성질을 **버스 계층에서 강제** 한다는 점입니다.

## 13. 컨텍스트/메시지 계약 4: 전달 보장·중복·순서·DLQ

제목이 "메시지 버스 기반"인 만큼 짚어야 할 것이 있습니다. **메시지 버스는 순서·무중복 전달을 자동으로 보장하지 않습니다.** 많은 내구성 메시지 브로커는 at-least-once 전달을 기본 또는 주요 옵션으로 제공하지만, 실제 보장(at-most-once·at-least-once·제한적 exactly-once)은 제품·토픽·구독 설정에 따라 다릅니다. 이 설계에서는 at-least-once를 운영 전제로 두므로, 같은 메시지가 두 번 이상 도착하거나 순서가 뒤바뀔 수 있고, 소비자가 이를 스스로 처리해야 합니다. 공식 패턴도 전달 보장, 중복, 순서, DLQ, 스키마 진화, Backpressure를 각각 별도 설계 항목으로 다룹니다.

에이전트 협업에서는 이 성질이 곧 정확성 문제로 이어집니다. 위임 결과가 중복 도착하면 초안이 두 번 생성되거나 예산이 이중 차감될 수 있고, 결과가 순서를 어겨 도착하면 오래된 결과가 최신 상태를 덮어쓸 수 있습니다.

| 항목 | 위험 | 대응 |
|---|---|---|
| 전달 보장 | at-most-once면 유실, at-least-once면 중복 | at-least-once 전제 + 멱등 소비자 |
| 중복 (Duplicate) | 같은 위임 결과가 두 번 처리 | `message_id`·`idempotency_key`로 중복 제거 |
| 순서 역전 (Out-of-order) | 오래된 결과가 최신 상태를 덮어씀 | `step_id`별 `expected_state_version` 검증 |
| 만료 (Expiry) | 지난 결과를 뒤늦게 반영 | `deadline`·TTL 초과 결과 폐기 |
| Poison Message | 반복 실패 메시지가 큐를 막음 | 재시도 한도 후 DLQ로 격리 |
| Backpressure | 소비자 지연 시 큐 적체·팬아웃 폭주 | 큐 상한·팬아웃 제한·소비 제어 |
| 스키마 진화 | 필드 추가/변경 시 소비자 파손 | `schema_version`·하위 호환 정책 |

멱등 소비자(Idempotent Consumer)의 원칙은 단순합니다. 소비자는 처리하기 전에 `idempotency_key`(또는 `message_id`)를 **원자적으로 선점(claim)** 한 뒤에만 부수 효과를 실행합니다. 단순한 `seen → handle → record` 순서는 두 소비자가 동시에 `seen=False`를 보고 둘 다 처리하는 경쟁 상태를 남깁니다. 그래서 고유 키 삽입(또는 트랜잭션 Inbox)으로 선점에 성공한 소비자만 처리하고, 선점에 실패하면 이미 처리 중·완료된 결과를 반환합니다. 외부 시스템에 쓰는 경우 같은 `idempotency_key`를 하류까지 전달해 하류에서도 중복이 제거되게 합니다.

```text
on_message(env, payload):
  if now() > env.deadline:                     # 만료 → 폐기
      dead_letter(env, reason="expired")
      return
  # 순서 역전 → 폐기. Run 전체 generation이 아니라
  # step_id/branch_id 단위의 expected_state_version으로 비교(병렬 분기 안전).
  if env.expected_state_version < run_state.version(env.run_id, env.step_id):
      drop(env, reason="stale version")
      return
  claim = store.claim(env.idempotency_key)     # 고유 키 원자적 선점
  if not claim.acquired:                        # 이미 선점됨 → 재처리 금지
      return store.result_of(env.idempotency_key)
  result = handle(payload)                      # 실제 처리(부수 효과)
  store.record(env.idempotency_key, result)     # 결과 기록 후 재사용
  return result
```

여기서 순서 역전 폐기는 Run 전체의 단일 generation이 아니라, `step_id`/`branch_id` 단위의 `expected_state_version`으로 비교합니다. Run 전체 하나의 카운터로 비교하면 병렬 분기가 서로의 버전을 덮어써 정상 결과까지 stale로 오판할 수 있기 때문입니다. 이 필드들도 봉투에 실려 신뢰된 런타임이 부여합니다. 또한 Run이 종료·취소된 뒤 도착한 늦은 결과가 상태를 덮어쓰지 못하도록, 소비 시점에 해당 step의 version을 함께 검증합니다. 이 규칙들이 없으면 "메시지 버스로 협업한다"는 설계는 규모가 커질수록 조용히 어긋납니다.

## 14. 오케스트레이션 상태 1: SSE로 위임·도구 호출 실시간 표시

필자가 구현한 오케스트레이터는 FastAPI (파이썬 웹 프레임워크)와 SSE (Server-Sent Events, 서버 전송 이벤트)로, 위임과 도구 호출 흐름을 실시간 UI에 표시합니다.

```text
[SSE stream]
id: 1024
event: delegation
data: {"from":"orchestrator","to":"researcher","intent":"근거 수집"}

id: 1025
event: tool_call
data: {"agent":"researcher","tool":"search_meeting_kb","status":"running"}

id: 1026
event: tool_result
data: {"agent":"researcher","tool":"search_meeting_kb","hits":5}

id: 1027
event: delegation
data: {"from":"orchestrator","to":"writer","intent":"초안 작성"}
```

SSE를 택한 이유는 단순합니다. 위임과 도구 호출은 **서버에서 클라이언트로 흐르는 단방향 이벤트** 이고, 진행 상황을 계속 밀어내면 되므로 양방향 연결이 필요 없습니다. 사용자는 어떤 에이전트가 지금 무엇을 하는지, 어떤 도구를 부르고 있는지 실시간으로 봅니다.

운영에서는 몇 가지를 함께 챙깁니다. 위 예시처럼 각 이벤트에 `id:`를 부여해야 브라우저가 재연결 시 마지막으로 받은 값을 `Last-Event-ID` 헤더로 보낼 수 있습니다. 다만 `Last-Event-ID`는 재전송을 자동 보장하지 않으므로, 서버가 이벤트를 보관해 두었다가 해당 ID 이후의 이벤트를 재생(replay)하는 로직을 직접 두어야 합니다. 유휴 연결이 프록시에서 끊기지 않도록 heartbeat 이벤트도 주기적으로 보냅니다. 리버스 프록시의 응답 버퍼링을 끄지 않으면 이벤트가 몰아서 도착하므로 스트리밍 설정을 확인해야 합니다. 그리고 이벤트 payload에는 회의 원문·자격증명 같은 민감정보를 그대로 싣지 않고, 식별자와 상태 위주로 마스킹해 흘려보냅니다.

## 15. 오케스트레이션 상태 2: 위임 추적·실패·재시도

각 위임과 도구 호출은 상태 기계 (State Machine)로 관리됩니다.

```text
PENDING → RUNNING → SUCCEEDED
                  → FAILED → (재시도 가능?) → RETRYING → RUNNING
                                            → GAVE_UP → 상위로 반환
```

| 상태 | 의미 | UI 표시 |
|---|---|---|
| PENDING | 위임 대기 | 대기 아이콘 |
| RUNNING | 실행 중 | 진행 표시 |
| SUCCEEDED | 정상 완료 | 완료 |
| FAILED | 실패 | 경고 |
| RETRYING | 재시도 중 | 재시도 표시 |
| GAVE_UP | 재시도 소진 | 실패 확정 |

재시도는 무한하지 않으며, 앞 절의 예산에서 차감됩니다. 도구 호출이 실패했다고 무조건 재시도하지 않고, 실패 유형을 구분합니다.

```text
재시도 가능(조건부):  일시적 네트워크·타임아웃
                     └ 단, 작업이 멱등하거나 동일 idempotency key로
                        중복 실행이 제거되는 경우에만 자동 재시도
재시도 금지:          권한 거부(allowlist 위반) · 입력 검증 실패
상위 판단:            검증 실패(인용 불일치·근거 약함) → 검증자가 반려, 재작성 위임
```

여기서 중요한 단서가 있습니다. **"네트워크·타임아웃은 재시도 가능"은 읽기 작업에만 안전하고, 쓰기 작업에는 위험합니다.** 타임아웃 전에 서버에서 부수 효과가 이미 발생했을 수 있기 때문입니다. 그래서 네트워크 오류·타임아웃은 작업이 멱등하거나 동일한 idempotency key로 중복 실행이 제거되는 경우에만 자동 재시도하고, 결과가 불명확한 쓰기는 재시도 전에 **상태 조회나 조정(Reconciliation)** 을 먼저 수행합니다.

권한 거부는 재시도해도 결과가 같으므로 즉시 실패로 확정하고 감사 로그에 남깁니다.

## 16. 오케스트레이션 상태 3: 관측성과 Trace

위임 체인 전체를 하나의 Trace (추적)로 묶습니다. `run_id` 아래에 위임과 도구 호출이 Span (구간)으로 매달립니다.

```text
run_id: run-EXAMPLE-001
└─ span: orchestrator.plan
   ├─ span: delegate → researcher
   │  ├─ span: tool search_meeting_kb (5 hits)
   │  └─ span: tool search_web_kb (3 hits)
   ├─ span: delegate → writer
   │  └─ span: tool create_draft
   ├─ span: delegate → source-verifier
   │  └─ span: tool verify_source_chunks (1 mismatch)
   └─ span: delegate → external-fact-verifier
      └─ span: tool verify_external_claims (2 flagged)
```

Trace는 디버깅과 관측을 위한 것이며, 규제·책임 재구성을 위한 감사 로그 (Audit Log)와는 목적이 다릅니다. Trace는 샘플링·유실될 수 있으므로 감사의 대체물로 쓰지 않습니다. 감사 설계는 별도 주제입니다.

관측성에서 반드시 답할 수 있어야 하는 질문은 다음과 같습니다.

- 어떤 사용자 요청이 어떤 위임 체인을 만들었는가?
- 각 에이전트는 자신의 Allowlist 안에서만 도구를 호출했는가?
- 최종 산출물의 각 주장은 어느 근거·출처에서 왔는가?
- 어디서 재시도·실패·중단이 발생했는가?

## 17. 지식베이스 분리 1: 회의 KB vs 웹 KB 도메인 분리

지식베이스는 도메인별로 분리합니다.

| 지식베이스 | 소스 | 신뢰 성격 | 대표 사용 역할 |
|---|---|---|---|
| 회의 KB | 회의 요약·녹취 | 내부·조직 소유 | Researcher·Source Verifier |
| 웹 KB | 수집·정제된 웹 문서 | 외부·검증 대상 | Researcher·External Fact Verifier |

도메인을 나누는 이유는 저장 효율이 아니라 **신뢰 성격이 다르기** 때문입니다. 회의 KB는 조직 내부 데이터이고, 웹 KB는 외부 출처라 간접 주입 위험이 상대적으로 높습니다. 같은 컬렉션에 섞어도 메타데이터로 신뢰 도메인을 표시할 수는 있지만, 컬렉션을 나눠 두면 기본 격리와 오검색(cross-domain leak) 방지가 구조적으로 쉬워집니다.

## 18. 지식베이스 분리 2: 회의록 인제스터와 멱등 Upsert

회의 KB는 회의록 인제스터 (Ingester)가 채웁니다. 흐름은 다음과 같습니다.

```text
회의 요약·녹취
  → 청크 분할(Chunking)
  → 다국어 임베딩(Multilingual Embedding)
  → 멱등 Upsert(Idempotent Upsert) → ChromaDB
```

멱등 (Idempotent)이 핵심입니다. 같은 회의를 다시 인제스트해도 청크가 중복 저장되지 않도록, 결정적 (Deterministic) ID로 Upsert합니다. 다만 ID에 무엇을 넣느냐가 중요합니다. `chunk_index`만 쓰면 청크 수가 줄었을 때 이전의 뒤쪽 청크가 남고, chunker 버전이 바뀌면 같은 index가 다른 의미가 됩니다. 그래서 source revision과 chunker 버전, 그리고 내용 digest를 함께 넣습니다.

```python
# 개념 코드 (실행용 아님) — ID 구성 요소와 정리 흐름을 보이기 위한 예시

def chunk_id(minutes_id, file_id, source_rev, chunker_ver, chunk_index, text):
    content_digest = sha256(text.encode()).hexdigest()[:16]
    basis = f"{minutes_id}:{file_id}:{source_rev}:{chunker_ver}:{chunk_index}:{content_digest}"
    return sha256(basis.encode()).hexdigest()

generation = f"{minutes_id}:{file_id}:{source_rev}:{chunker_ver}"
new_ids = [chunk_id(m, f, source_rev, chunker_ver, i, t) for i, t in enumerate(chunks)]
collection.upsert(
    ids=new_ids,
    documents=chunks,
    embeddings=embeddings,
    metadatas=[{**md, "generation": generation} for md in metadatas],
)
# Chroma의 Upsert는 같은 ID를 갱신하거나 새 ID를 만들 뿐,
# 이번 실행에서 사라진 이전 청크를 자동 삭제하지 않는다.
# → 새 generation을 활성화한 뒤, 같은 (minutes_id, file_id) 범위에서
#   이번 generation에 속하지 않는 stale 청크만 정리한다.
# 광범위한 $ne 삭제보다 확정된 stale ID 목록 삭제가 안전하다.
existing = collection.get(
    where={"$and": [{"minutes_id": m}, {"file_id": f}]}
)
stale_ids = [i for i in existing["ids"] if i not in set(new_ids)]
if stale_ids:
    collection.delete(ids=stale_ids)
```

즉 결정적 ID만으로는 완전한 멱등 색인이 되지 않습니다. 최소한 (1) source revision, (2) chunker/version, (3) chunk ordinal 또는 content digest를 ID·메타데이터에 반영하고, (4) 새 generation을 활성화한 뒤 (5) 같은 `(minutes_id, file_id)` 범위에서 이번 generation에 속하지 않는 stale 청크만 정리해야 합니다. 정리 범위에서 `file_id`가 빠지면 한 회의의 다른 파일 청크까지 지울 수 있으므로 주의합니다. 멱등 색인의 상세 설계(중복 청크 방지, 재색인, 부분 갱신)는 별도 글의 주제이므로 여기서는 "리서처가 검색하는 회의 KB가 중복 없이 안정적으로 채워진다"는 전제만 확인합니다.

## 19. 지식베이스 분리 3: 출처·거리/점수를 포함한 검색

검색 결과는 텍스트만 반환하지 않고, 출처와 근접도 점수를 함께 반환합니다. 여기서 점수 표현에 주의해야 합니다. ChromaDB는 통상 **거리(distance)** 를 반환하고 값이 낮을수록 더 가까운 결과이며, 기본 공간은 L2입니다. cosine을 쓰더라도 반환값은 보통 cosine distance이므로, `0.86` 같은 숫자를 무조건 "높은 유사도"로 읽을 수 없습니다. 그래서 반환 계약에는 원 거리(`distance`)와 지표(`metric`)를 함께 싣고, 사람이 읽기 쉬운 `retrieval_score`를 제공할 때는 변환 방식·버전(`score_transform_version`)을 밝힙니다.

```json
{
  "query": "지난 회의 결정 사항",
  "collection": "meeting-knowledge",
  "metric": "cosine",
  "score_transform_version": "v1",
  "results": [
    {
      "text": "결정 사항 요약(설명용)",
      "source": "meeting-kb://EXAMPLE/chunk-12",
      "distance": 0.14,
      "retrieval_score": 0.86
    },
    {
      "text": "관련 논의(설명용)",
      "source": "meeting-kb://EXAMPLE/chunk-27",
      "distance": 0.29,
      "retrieval_score": 0.71
    }
  ]
}
```

거리·점수를 함께 흘려보내면 두 가지가 가능해집니다. 첫째, 임계값 (Threshold) 정책을 세워 근접도가 낮은 결과는 근거로 채택하지 않을 수 있습니다. 다만 임계값은 절대적인 값이 아니라 모델·청킹·도메인별 평가셋으로 보정해야 합니다. 둘째, 검증자가 "이 주장은 근접도가 약한 근거에만 의존한다"처럼 근거의 약함을 지적할 수 있습니다. 단, 검색 점수는 근거의 진실성이나 신뢰도가 아니라 **질의와 청크의 근접도** 일 뿐임을 잊지 말아야 합니다.

## 20. 협업 예시: 회의 근거 기반 문서 작성

세 축의 권한 분리가 실제 협업에서 어떻게 동작하는지 하나의 시나리오로 정리합니다.

```text
사용자: "지난 회의 결정 사항을 정리해 공유 문서 초안을 만들어줘."

1. Orchestrator
   - delegation_matrix로 researcher 호출 허용 확인
   - task.delegation.request → researcher

2. Researcher
   - RAG allowlist: 회의 KB·웹 KB 읽기만 가능
   - search_meeting_kb 호출(출처·거리/점수 포함)
   - findings 발행 (trust는 런타임이 출처에 근거해 부여)

3. Orchestrator → Writer 위임
   - Writer는 KB 검색 도구 없음 → researcher findings만 사용
   - create_draft 호출 (인용한 회의 청크의 source·source_version 표기)

4. Orchestrator → Source Verifier 위임
   - 회의 KB만 접근 → 초안이 인용한 회의 청크의
     내용·출처·버전이 실제와 일치하는지 읽기 전용으로 대조
   - 인용 불일치 1건 flag

5. Orchestrator → External Fact Verifier 위임
   - 웹 KB만 접근 → 초안 안의 외부(기술·시장·정책) 주장만 대조
   - 근거 약한 외부 주장 2건 flag

6. Orchestrator
   - flag된 주장(인용 불일치·근거 약함) 재작성을 Writer에 위임(예산 차감)
   - 최종 초안 사용자에게 반환
```

이 흐름에서 어느 에이전트도 자신의 Allowlist를 벗어나지 못합니다. 작성자가 회의 KB를 다시 뒤지고 싶어도 도구가 없고, 검증자가 초안을 직접 고치고 싶어도 저장 도구가 없습니다. 특히 회의 내부 결정 사항은 공개 웹에서 확인할 수 없으므로, 회의 인용의 정확성은 Source Verifier가 회의 원문을 재조회해 대조하고, 외부 주장만 External Fact Verifier가 웹 근거로 검증합니다.

## 21. 운영 고려 1: 승인이 필요한 쓰기·위험 작업

읽기·조사·작성은 자동으로 흘러가도, 외부 상태를 바꾸는 작업은 다릅니다. 회의록 삭제, 요약 저장, 다른 그룹으로의 이동 같은 부수 효과 (Side Effect)가 있는 작업은 사람 승인 (Human Approval)을 거치도록 게이트를 둡니다. 위험 등급은 이름이 아니라 **실제 복구·보상 가능성** 으로 정해야 합니다. 버전 관리가 없는 덮어쓰기는 되돌리기 어렵고, 반대로 휴지통·soft delete가 있는 삭제나 재이동 가능한 그룹 이동은 복구 여지가 있습니다.

```text
작업 분류 (실제 복구·보상 가능성 기준)
  READ_ONLY   : 검색·조회 → 자동 실행
  LOW_RISK    : 초안 저장 등 → 정책에 따라 자동/승인
  HIGH_RISK   : 그룹 이동 등 → 승인 권장
  DESTRUCTIVE : 복구 불가 삭제·외부 전송 → 승인 필수
```

승인 정책의 상세(무엇을 승인 대상으로 볼지, 승인 UX, 승인 감사)는 별도 글의 범위입니다. 이 글에서는 "에이전트가 아무리 자율적이어도 위험 작업의 마지막 판단은 오케스트레이터와 사람에게 남는다"는 원칙만 둡니다.

## 22. 운영 고려 2: 감사와 권한 위반 기록

권한 분리는 "위반을 기록할 수 있을 때" 완성됩니다. Allowlist를 벗어난 도구·컬렉션·동료 호출 시도는 차단하는 것으로 끝나지 않고, 감사 이벤트로 남겨야 합니다.

| 이벤트 | 기록 항목 |
|---|---|
| ALLOW | 어떤 에이전트가 어떤 도구를 어떤 Run에서 호출 |
| DENY | 차단된 도구·컬렉션·동료 호출과 사유 |
| APPROVAL | 승인 요청·승인자·결과 |
| SIDE_EFFECT | 실제 바뀐 외부 상태 |

특히 DENY 이벤트가 중요합니다. 정상 운영에서 DENY가 잦다면 Allowlist가 실제 필요와 어긋났다는 신호이고, 특정 에이전트에서 DENY가 갑자기 튀면 오작동이나 공격의 신호일 수 있습니다.

마지막으로 강조할 원칙이 있습니다. **에이전트 Allowlist는 필요조건이지, 사용자·테넌트·객체 인가의 대체물이 아닙니다.** 세 축의 Allowlist를 모두 통과해도, 그 요청을 낸 사용자(subject)가 해당 테넌트·객체에 접근할 권한이 없다면 접근은 거부되어야 합니다(9절의 실효 권한 논리곱). 이를 구조적으로 보장하려면 다음도 함께 강제해야 합니다.

| 통제 | 목적 |
|---|---|
| 버스 ACL | 어떤 실행 주체가 어떤 토픽에 발행·구독할 수 있는지 제한 |
| 우회 경로 차단 | 에이전트가 버스를 거치지 않고 MCP·검색에 직접 접속하지 못하도록 네트워크·자격증명 계층에서 강제 |
| Tool 변경 통제 | 서버·도구 이름 외에 서버 신원, 스키마 버전 또는 정책 버전을 고정해 도구가 조용히 바뀌는 것을 탐지 |
| 사용자·테넌트·객체 인가 | 에이전트 권한과 별개로 실행 주체의 데이터 접근 권한을 매 요청 검증 |

## 23. 운영 고려 3: 테스트 전략

멀티 에이전트 협업은 다음 층위로 나눠 시험합니다.

| 층위 | 시험 대상 | 예시 |
|---|---|---|
| 권한 단위 | Allowlist 강제 | 리서처가 삭제 도구 호출 시도 → 반드시 DENY |
| 계약 단위 | 메시지 스키마·봉투 검증 | payload가 자기 `trust`·`hop`을 위조 → 런타임이 무시·거부 |
| 전달 단위 | 중복·순서·만료 | 같은 `idempotency_key` 재도착 → 재처리 없이 동일 결과, stale version 결과 폐기 |
| 흐름 단위 | 위임·루프·예산 | 순환 위임 → 차단, 깊이·팬아웃 초과 → 거부 |
| 시나리오 단위 | 역할 협업 결과 | 회의 인용 불일치 → Source Verifier flag, 근거 약한 외부 주장 → External Fact Verifier flag |
| 적대적 단위 | 간접 주입·연쇄 실패 | 오염된 웹 근거 → 실행 계층에서 거부 |

특히 **권한 단위 Negative Test (부정 시험)** 가 핵심입니다. "허용된 일을 잘한다"보다 "금지된 일을 반드시 못 한다"를 회귀 테스트로 고정해야, 도구·에이전트를 추가할 때 권한 경계가 조용히 무너지는 것을 잡을 수 있습니다.

## 24. 안티패턴 정리

마지막으로, 멀티 에이전트 협업에서 반복적으로 관찰되는 안티패턴을 정리합니다.

| 안티패턴 | 문제 | 대안 |
|---|---|---|
| 공용 슈퍼 권한 | 모든 에이전트가 같은 도구·KB 접근 | 역할별 Allowlist |
| 서버 단위만 허용 | 같은 서버의 위험 도구 노출 | 도구 단위 Allowlist |
| 내부 메시지 무조건 신뢰 | 간접 주입 전파 | 다른 에이전트 출력=검증 대상 |
| 에이전트가 신뢰·예산 자체 선언 | 손상 에이전트가 `trust`·`budget` 위조 | 봉투는 신뢰된 런타임이 생성·검증, 예산은 Run 저장소에서 차감 |
| 전달 보장 가정 | 중복·순서 역전·늦은 결과가 상태 훼손 | 멱등 소비자·step별 version 검증·DLQ |
| 웹 KB로 회의 인용 검증 | 사내 결정은 공개 웹에 없음 | Source/External 검증자 분리 |
| Allowlist를 인가 전체로 착각 | 사용자·테넌트·객체 권한 누락 | 실효 권한 논리곱, 사용자·객체 인가 병행 |
| 무제한 위임 | 루프·팬아웃·비용 폭발 | 깊이·예산·순환 탐지 |
| 자유로운 동료 호출 | 추적 불가·경로 폭발 | Supervisor 중심 위임 매트릭스 |
| 승인 없는 위험 작업 | 되돌릴 수 없는 부수 효과 | 위험 등급별 승인 게이트 |
| Trace를 감사로 사용 | 유실·샘플링으로 책임 재구성 실패 | 감사 로그 별도 설계 |

## 25. 마무리

멀티 에이전트 협업의 목표는 "더 똑똑한 하나"를 만드는 것이 아닙니다.

**책임과 권한이 분리된 여러 에이전트를, 통제 가능한 하나의 흐름으로 협업시키는 것** 입니다.

이를 위한 핵심 원칙을 정리합니다.

1. 멀티 에이전트는 과제가 정말 요구할 때만 도입하고, 역할(리서처·작성자·출처 검증자·외부 사실 검증자)로 책임을 나눕니다.
2. 협업은 지정 대상 Command와 Reply/Event를 함께 쓰는 Message Bus 기반 오케스트레이션으로 하고, 모든 위임·도구 호출이 버스를 통과하게 해 통제 지점을 단일화합니다.
3. 에이전트별로 MCP 도구·RAG 컬렉션·동료 호출을 Allowlist로 최소화하되, 실효 권한은 사용자·테넌트·객체 인가까지 포함한 조건의 논리곱으로 정의합니다. Allowlist는 인가의 필요조건이지 대체물이 아닙니다.
4. 다른 에이전트의 출력도 신뢰 경계를 넘는 데이터로 보고, 신뢰 표식·깊이·예산 같은 봉투 필드는 에이전트가 아니라 신뢰된 런타임이 생성·검증합니다.
5. 깊이·예산·팬아웃·경로 기반 순환 탐지로 루프와 폭주를 버스 계층에서 막고, 중복·순서 역전·늦은 결과는 멱등 소비자와 step별 version 검증으로 처리합니다.
6. SSE로 위임·도구 호출을 실시간 표시하고, Run 단위 Trace로 관측합니다(감사는 별도).
7. 회의 KB와 웹 KB를 신뢰 성격에 따라 분리하고, 출처와 함께 거리·지표를 명시한 검색 점수를 실어 나릅니다. 회의 인용은 Source Verifier가, 외부 주장은 External Fact Verifier가 검증합니다.
8. 위험·되돌릴 수 없는 작업은 사람 승인 게이트를 두고, 권한 위반(DENY)을 감사로 남깁니다.
9. "금지된 일을 반드시 못 한다"를 부정 시험으로 고정합니다.

에이전트를 더 많이 붙일수록, 각 에이전트가 **할 수 없는 일** 의 목록이 시스템의 신뢰성을 결정합니다.

## 참고 자료

- [Model Context Protocol: Security Best Practices (2026-07-28)](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [Model Context Protocol: Authorization Specification (2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
- [Model Context Protocol: Specification (2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/)
- [OWASP Top 10 for Agentic Applications (2026)](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [Microsoft Azure Architecture Center: Publisher-Subscriber Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/publisher-subscriber)
- [Google Cloud: Event-driven Architecture with Pub/Sub](https://docs.cloud.google.com/solutions/event-driven-architecture-pubsub)
- [LangGraph: Multi-Agent Workflows (Supervisor 패턴 개념 문서)](https://www.langchain.com/blog/langgraph-multi-agent-workflows)
- [LangGraph Multi-Agent Supervisor (패키지 레퍼런스, 최신 안내는 도구 기반 직접 구현 권장)](https://reference.langchain.com/python/langgraph-supervisor)
- [Multi-Agent Collaboration Mechanisms: A Survey of LLMs (arXiv)](https://arxiv.org/pdf/2501.06322)
- [ChromaDB: Configure Collections (거리 지표)](https://docs.trychroma.com/docs/collections/configure)
- [ChromaDB: Upsert Records](https://docs.trychroma.com/reference/chroma-api/record/upsert-records)
- [ChromaDB: Metadata Filtering (`$and` 등)](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [WHATWG HTML: Server-Sent Events (`id:`·`Last-Event-ID`)](https://html.spec.whatwg.org/dev/server-sent-events.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

> 이 글은 2026년 7월 30일 기준 MCP, OWASP GenAI Security Project, Microsoft·Google의 공개 아키텍처 패턴, LangGraph 및 공개 연구 자료와, 필자가 개발·상용화 검증 단계에서 설계·구현한 Python 멀티 에이전트 오케스트레이터 경험을 바탕으로 작성했습니다. 예시 ID, 토픽 이름, Allowlist 항목, 예산·깊이 값, 메시지 스키마, 검색 결과와 거리·점수 값은 설명용 Fixture이며 실제 고객·조직·사용자·계정·회의·Prompt·Tool Result·내부 시스템 정보가 아닙니다. 실제 적용 시 조직의 역할 정의, MCP·RAG 접근 정책, 승인·감사 구조, 위임 예산과 운영 위험을 검토하고, 특히 "금지된 동작을 반드시 수행하지 못한다"는 권한 경계를 부정 시험(Negative Test)으로 검증해야 합니다.
