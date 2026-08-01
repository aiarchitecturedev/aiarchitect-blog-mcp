# Tistory 기술자료 초안

- 문서 ID: `BLOG-14`
- 상태: 공개 완료
- Tistory 상태: 공개 게시·공개 페이지 검증 완료
- 공개 URL: https://aiarchitect.tistory.com/15
- 분류: `기술 인사이트`
- 권장 제목: `AI PoC가 운영 단계에서 멈추는 이유: 인증, 권한, 복구와 관측성`
- 검색 설명: `AI 개념 검증이 데모에서는 성공했지만 운영 전환에서 멈추는 이유를 성공 기준, 인증·권한, 위험 작업 승인, 장애 복구, 품질 평가, 관측성, 비용과 배포 책임의 관점에서 정리합니다.`
- 권장 태그: `AI PoC`, `Production Readiness`, `AI Agent`, `MLOps`, `Observability`, `SLO`, `엔터프라이즈 AI`
- 권장 대표 이미지: `portfolio/architecture-diagrams/01-enterprise-ai-reference-architecture.svg`

---

# AI PoC가 운영 단계에서 멈추는 이유: 인증, 권한, 복구와 관측성

회의 파일을 올리면 녹취록과 요약이 생성됩니다. 질문을 입력하면 사내 문서를 검색하고, AI Agent가 업무 Tool까지 호출합니다.

개념 검증 (Proof of Concept, PoC) 시연은 성공했습니다.

하지만 운영 전환 회의에서는 새로운 질문이 쏟아집니다.

- 누가 어떤 데이터까지 볼 수 있는가?
- AI가 잘못된 대상을 변경하면 어떻게 막는가?
- 처리 중 서버가 재시작되면 어디서 다시 시작하는가?
- 답변 품질이 나빠졌다는 사실을 어떻게 감지하는가?
- 모델 API가 느리거나 중단되면 무엇을 보여 주는가?
- 사용자 한 명과 천 명의 비용 차이는 얼마인가?
- 장애가 발생했을 때 누가 판단하고 복구하는가?

이 질문들은 PoC의 부가 기능이 아닙니다. 실제 사용자가 있는 서비스라면 처음부터 존재했던 요구사항입니다. 다만 제한된 데이터와 성공 경로만 보여 주는 동안 보이지 않았을 뿐입니다.

```text
PoC 질문
  “핵심 기술이 가능한가?”

운영 질문
  “누가, 어떤 조건에서, 얼마나 안정적으로,
   얼마의 비용으로, 실패 후 어떻게 복구하며 사용하는가?”
```

AI PoC가 운영 단계에서 멈추는 핵심 원인은 모델 성능 하나가 아닙니다. **기술 가능성은 검증했지만 운영 계약 (Operational Contract)은 정의하지 않았기 때문**입니다.

## 1. PoC와 운영 시스템은 성공의 단위가 다르다

PoC는 가장 큰 불확실성을 짧게 검증하는 활동입니다.

예를 들어 다음 질문에 답할 수 있습니다.

- 이 음질의 한국어 회의를 원하는 수준으로 인식할 수 있는가?
- 보유 문서에서 관련 Chunk를 검색할 수 있는가?
- 자연어 요청을 업무 API의 Tool Call로 변환할 수 있는가?
- 목표 GPU에서 실시간보다 빠르게 추론할 수 있는가?

반면 운영 시스템은 반복 가능한 서비스 결과를 만들어야 합니다.

| 구분 | PoC | 운영 시스템 |
|---|---|---|
| 목표 | 핵심 가설과 위험 검증 | 지속적인 업무 가치 제공 |
| 사용자 | 개발자·평가자 중심 | 실제 사용자·관리자·운영자 |
| 데이터 | 선별된 Sample | 권한·오류·중복이 있는 실제 분포 |
| 실행 경로 | 정상 경로 중심 | 실패·취소·재시도·복구 포함 |
| 품질 | 몇 개 결과의 육안 확인 | 기준 Dataset과 지속 평가 |
| 인프라 | 고정된 시험 환경 | 확장·배포·Rollback·장애 대응 |
| 책임 | 만든 사람이 직접 확인 | 역할·Runbook·Escalation |

PoC를 작은 운영 시스템으로 만들 필요는 없습니다. 대신 **PoC 범위와 운영 전환에 필요한 후속 범위를 분명히 구분**해야 합니다.

```text
PoC 완료
≠ 제품 완료
≠ 운영 준비 완료
```

## 2. 첫 번째 공백: 성공 기준이 “시연 성공”으로 끝난다

“답변이 잘 나온다”, “요약 품질이 좋다”와 같은 기준은 시작점일 뿐입니다.

운영 전환에는 최소한 세 종류의 성공 기준이 필요합니다.

| 기준 | 질문 | 예시 |
|---|---|---|
| 업무 기준 | 실제 업무를 개선하는가? | 검토 시간, 완료율, 재작업률 |
| AI 품질 기준 | 결과가 충분히 정확하고 안전한가? | 검색 적중, 근거성, 오류 유형 |
| 운영 기준 | 서비스로 유지할 수 있는가? | 가용성, 지연, 복구, 비용 |

서비스 수준 목표 (Service Level Objective, SLO)는 기술 지표를 사용자 경험과 연결합니다.

```json
{
  "service": "meeting-summary",
  "businessOutcome": {
    "metric": "review_completed",
    "measurementWindow": "weekly"
  },
  "qualityObjectives": {
    "requiredFactsRecall": {
      "target": 0.95,
      "dataset": "approved_eval_set_v3"
    },
    "unsupportedClaimRate": {
      "target": 0.01,
      "direction": "maximum"
    }
  },
  "serviceObjectives": {
    "requestSuccessRate": {
      "target": 0.99
    },
    "p95CompletionSeconds": {
      "target": 120
    }
  }
}
```

수치는 업무 중요도와 관측 자료를 바탕으로 정해야 합니다. 근거 없이 `99.9%`를 붙이는 것이 목표 정의는 아닙니다.

Google SRE 자료의 실패 예산 (Error Budget)은 신뢰성과 변경 속도의 균형을 정하는 방법입니다. 목표를 지키지 못할 때 기능 개발을 계속할지, 안정화 작업으로 전환할지를 사전에 합의합니다.

## 3. 두 번째 공백: 선별된 Sample이 실제 데이터 분포를 대표하지 않는다

PoC에서는 잘 정리된 문서, 잡음이 적은 음성, 짧은 질문과 명확한 업무 요청을 선택하기 쉽습니다.

운영 데이터에는 다음 문제가 함께 들어옵니다.

- 빈 파일과 손상된 파일
- 지나치게 긴 문서와 중복 문서
- 오래되거나 서로 충돌하는 규정
- 여러 언어와 전문 용어
- 침묵·잡음·겹침 발화
- 권한이 섞인 검색 결과
- 애매한 지시와 Prompt Injection
- 처리 도중 변경·삭제된 원본

따라서 평가 Dataset은 “좋은 예시 모음”이 아니라 실제 위험을 대표해야 합니다.

```text
정상 사례
  + 경계값
  + 빈 결과
  + 권한 거부
  + 악성·비신뢰 입력
  + 외부 의존성 실패
  + 과거 장애 재현 사례
```

운영에서 발견한 실패를 익명화해 회귀 평가 세트에 추가해야 같은 문제가 다음 배포에서 반복되는지 알 수 있습니다.

## 4. 세 번째 공백: 로그인은 있지만 권한 경계가 없다

PoC는 공용 계정이나 고정된 테스트 사용자로 진행할 수 있습니다. 운영에서는 사용자 주체 (Principal), 조직, Tenant, 역할과 객체 소유권이 모두 실행 결과에 영향을 줍니다.

```text
Authentication(인증)
  “누구인가?”

Authorization(인가)
  “이 사용자가 이 객체에 이 작업을 할 수 있는가?”
```

AI 시스템에서 권한은 입구 한 곳에서만 검사하면 안 됩니다.

| 지점 | 필요한 검증 |
|---|---|
| API Gateway | Token, Audience, 만료와 Tenant |
| RAG 수집 | 원본 문서 ACL과 보존 범위 |
| Retrieval | 사용자별 Filter와 객체 권한 |
| Tool 호출 | Tool·Action·Resource 단위 권한 |
| 비동기 Worker | 원 요청자의 권한 Context |
| 결과 저장 | Tenant·소유자·민감도 |
| 감사 Log | 누가 무엇을 요청하고 실행했는지 |

특히 검색 후 생성 (Retrieval-Augmented Generation, RAG)은 검색 품질보다 먼저 권한 필터를 보장해야 합니다. 권한 없는 Chunk가 Prompt에 들어간 뒤 최종 답변에서 가리는 방식은 이미 데이터가 경계를 넘은 것입니다.

## 5. 네 번째 공백: AI의 답변과 업무 실행을 같은 위험으로 본다

AI가 문장을 잘못 생성한 경우와 데이터를 삭제한 경우의 영향은 다릅니다.

Tool은 결과의 부작용을 기준으로 분류합니다.

| 등급 | 예시 | 운영 통제 |
|---|---|---|
| 읽기 (Read) | 목록·상세·검색 | 권한 확인과 민감정보 최소화 |
| 쓰기 (Write) | 생성·수정·요약 재실행 | 입력 검증과 중복 방지 |
| 중요 작업 (Important Action) | 전송·공유·승인 | 대상·영향 재확인 |
| 파괴 작업 (Destructive Action) | 영구 삭제 | 명시적 최종 승인 |

승인은 단순한 `confirm: true`가 아닙니다.

```json
{
  "approval": {
    "principalId": "user_fixture_alpha",
    "tenantId": "tenant_fixture_alpha",
    "action": "meeting.delete",
    "resourceId": "meeting_fixture_001",
    "requestFingerprint": "sha256:fixture_hash",
    "approvedAt": "2026-07-29T09:00:00Z",
    "expiresAt": "2026-07-29T09:05:00Z"
  }
}
```

승인은 사용자, 작업, 대상, 입력과 만료 시간에 묶여야 합니다. 다른 회의나 변경된 요청에 이전 승인을 재사용하면 안 됩니다.

## 6. 다섯 번째 공백: Timeout을 실패로 단정하고 다시 실행한다

분산 시스템에서 응답을 받지 못했다는 사실은 실행되지 않았다는 뜻이 아닙니다.

```text
Agent ── 생성 요청 ──▶ 업무 시스템
Agent ◀── Timeout ───── Network
              │
              └─ 업무 시스템에서는 생성 완료
```

이 상황에서 같은 요청을 반복하면 중복 레코드, 중복 결제, 중복 메시지가 생길 수 있습니다.

운영 전환에는 다음이 필요합니다.

- 멱등성 (Idempotency)
- 재시도 (Retry) 분류와 횟수 예산
- Timeout과 취소 전파
- 결과 조회와 중복 실행 방지
- 보상 작업 (Compensation)
- 중복 Message 소비 방지

```text
읽기 Timeout
  → 제한된 Backoff 재시도 가능

쓰기 응답 유실
  → 멱등성 Key로 기존 결과 확인

삭제 응답 유실
  → 자동 반복 금지, 상태 확인과 운영자 판단
```

PoC에서는 “다시 실행하면 된다”가 해결책일 수 있지만 운영에서는 재실행 자체가 새로운 장애가 될 수 있습니다.

## 7. 여섯 번째 공백: 긴 작업의 상태가 메모리에만 있다

STT, 문서 Parsing, Embedding, 대규모 요약과 외부 시스템 연동은 한 HTTP 요청 안에 끝나지 않을 수 있습니다.

운영 시스템은 비동기 상태를 명시적으로 관리해야 합니다.

```json
{
  "jobId": "job_fixture_001",
  "state": "SUMMARIZING",
  "attempt": 2,
  "progress": {
    "completedSteps": [
      "UPLOAD_VERIFIED",
      "TRANSCRIPTION_COMPLETED"
    ],
    "currentStep": "SUMMARIZING"
  },
  "lastCheckpointAt": "2026-07-29T09:10:00Z",
  "nextAction": "RETRY_WITH_BACKOFF"
}
```

체크포인트 (Checkpoint)는 단순한 진행률 저장이 아닙니다.

- 어떤 입력과 버전으로 실행했는가?
- 어떤 단계까지 부작용이 확정됐는가?
- 어떤 결과를 다시 사용할 수 있는가?
- 재시작할 때 무엇을 반복하면 안 되는가?
- 사용자 승인 상태가 아직 유효한가?

상태가 Worker 메모리에만 있으면 배포, 재시작과 장애가 곧 업무 유실로 이어집니다.

## 8. 일곱 번째 공백: AI 품질 평가를 다시 실행할 수 없다

PoC 평가는 보통 개발자가 몇 개 질문을 직접 입력하고 결과를 눈으로 확인합니다.

운영 전환에는 재현 가능한 평가 계약이 필요합니다.

| 평가 자산 | 기록 내용 |
|---|---|
| 입력 Dataset | 질문·문서·음성의 승인된 Version |
| 기대 결과 | 필수 사실, 금지 사실, 허용 범위 |
| Prompt | System·Agent·Tool Description Version |
| Model | Provider, Model과 주요 설정 |
| Retrieval | Index Revision, Filter와 Top K |
| Tool Trace | 선택 Tool, 인자, 순서와 결과 |
| 평가 결과 | 품질 지표, 오류 유형과 검토자 |

문장 전체의 일치보다 업무 불변 조건을 검사합니다.

- 답변의 필수 사실이 근거에 존재하는가?
- 인용한 Source가 실제 검색 결과인가?
- 권한 없는 Source를 사용하지 않았는가?
- Tool ID가 앞 호출 결과에서 유래했는가?
- 승인 없이 변경 작업을 실행하지 않았는가?
- 모호한 요청에서 임의로 대상을 선택하지 않았는가?

Model, Prompt, Embedding과 Index가 바뀔 때 같은 평가를 실행해야 품질 개선인지 회귀인지 판단할 수 있습니다.

## 9. 여덟 번째 공백: Log는 있지만 관측성이 없다

관측성 (Observability)은 Log 파일이 존재한다는 뜻이 아닙니다.

OpenTelemetry는 분산 시스템을 관측하는 주요 신호로 Trace, Metric과 Log를 설명합니다.

| 신호 | AI 시스템에서 확인할 내용 |
|---|---|
| 추적 (Trace) | 사용자 요청→검색→Model→Tool→외부 API 경로 |
| 지표 (Metric) | 성공률, 지연, Token, GPU, Queue, 품질 |
| 로그 (Log) | 상태 전이, 오류, 승인과 정책 결정 |

AI 서비스는 네 층을 함께 관찰해야 합니다.

```text
Infrastructure
  CPU · GPU · Memory · Network · Queue

Application
  Request · Error · Latency · Saturation

AI Pipeline
  Retrieval · Token · Model · Tool · Evaluation

Business
  Task Completion · User Correction · Escalation
```

요청 하나를 연결하는 식별자도 필요합니다.

```json
{
  "traceId": "trace_fixture_001",
  "requestId": "request_fixture_001",
  "workflowId": "workflow_fixture_001",
  "principalRef": "principal_hash_alpha",
  "tenantRef": "tenant_hash_alpha",
  "model": "provider_model_alias",
  "promptVersion": "agent_prompt_v7",
  "toolCatalogVersion": "tool_catalog_v4",
  "retrievalRevision": "index_revision_v12"
}
```

개인정보, Token, 원문 녹취록과 전체 Prompt를 무조건 Log에 남기면 안 됩니다. 재현에 필요한 Metadata와 보안상 저장하면 안 되는 본문을 구분해야 합니다.

## 10. 아홉 번째 공백: 평균 지연과 API 단가만 계산한다

AI 비용은 모델 입력·출력 Token만으로 결정되지 않습니다.

```text
Total Cost
  = Model API
  + Embedding
  + Vector Search
  + STT · GPU
  + Storage
  + Network
  + Queue · Worker
  + Observability
  + Human Review
  + Failure · Retry
```

평균값만 보면 긴 문서, 반복 Tool Call과 재시도 폭증을 놓칠 수 있습니다.

운영 검증에서는 다음을 분포로 측정합니다.

- 요청당 입력·출력 Token의 P50·P95
- 업무 완료당 Model·Tool 호출 수
- Cache 적중률
- Queue 대기와 처리 시간
- GPU 사용률과 유휴 시간
- 실패·재시도에 사용된 비용
- Tenant·기능·Model별 비용
- 사용자 수정과 수동 검토 비율

부하 테스트도 “동시에 몇 명”보다 실제 작업 형태를 반영해야 합니다. 짧은 질문 백 개와 두 시간짜리 음성 백 개는 같은 동시 요청 수가 아닙니다.

## 11. 열 번째 공백: Model 장애가 곧 전체 서비스 장애다

운영에서는 외부 Model API, Vector DB, 업무 API와 GPU가 각각 실패할 수 있습니다.

축소 운영 (Graceful Degradation)은 모든 기능이 완벽하지 않아도 핵심 기능을 안전하게 유지하는 전략입니다.

| 장애 | 가능한 축소 동작 |
|---|---|
| 주 Model Timeout | 승인된 대체 Model 또는 재시도 안내 |
| Vector Search 장애 | 검색 필요 답변 중단, 일반 안내만 제공 |
| 요약 Worker 포화 | 접수 후 예상 대기 상태 제공 |
| Tool Server 장애 | 읽기 전용 안내, 변경 작업 차단 |
| 품질 Gate 실패 | 자동 실행 대신 사용자 검토로 전환 |

Fallback은 결과만 바꾸는 설정이 아닙니다.

- 대체 Model이 같은 Tool Schema를 지원하는가?
- 안전 정책과 데이터 지역 요구를 만족하는가?
- 이미 부작용이 발생한 Tool을 다시 실행하지 않는가?
- 품질이 낮아진 상태를 사용자에게 표시하는가?
- 원래 경로로 복귀하는 조건이 있는가?

Google Cloud의 AI·ML 신뢰성 지침도 확장성, 느슨한 결합, 자동화된 Pipeline, 데이터·Model Governance와 전체 관측성을 함께 다룹니다. 신뢰성은 Model Endpoint 하나의 가용성만으로 만들어지지 않습니다.

## 12. 열한 번째 공백: 배포는 있지만 Rollback이 없다

AI 시스템의 변경 단위는 Application 코드만이 아닙니다.

```text
Code
Prompt
Model
Tool Schema
Retrieval Policy
Embedding Model
Index Revision
Safety Policy
Evaluation Dataset
```

이 구성요소 중 하나만 바뀌어도 결과가 달라질 수 있습니다.

운영 배포에는 다음 정보가 함께 묶여야 합니다.

- 변경된 구성요소와 Version
- 자동 평가 결과
- 승인자와 배포 시간
- 점진 배포 (Canary Deployment) 비율
- 중단 기준과 Rollback 기준
- 이전 호환 Version
- 데이터 Migration과 복구 방법

Model만 이전 Version으로 되돌렸는데 Prompt와 Tool Schema는 그대로라면 진정한 Rollback이 아닐 수 있습니다.

## 13. 열두 번째 공백: 운영 책임자가 정해지지 않았다

PoC에서는 개발자가 직접 Log를 열어 보고 문제를 해결합니다. 운영에서는 장애가 언제 발생할지 알 수 없습니다.

최소한 다음 책임이 정해져야 합니다.

| 상황 | 결정해야 할 책임 |
|---|---|
| Model 품질 저하 | 평가·Prompt·Model 담당 |
| 개인정보 노출 의심 | 보안·개인정보 대응 책임 |
| 외부 API 장애 | 서비스 운영과 연동 담당 |
| 비용 급증 | 제품·기술·FinOps 의사결정 |
| 데이터 삭제 요청 | 원본·Index·Cache 삭제 책임 |
| SLO 위반 | 배포 중단·안정화 우선순위 |

운영 준비 검토 (Production Readiness Review, PRR)는 “개발이 끝났는가”를 확인하는 회의가 아닙니다.

- 누가 알림을 받는가?
- 어떤 상태에서 사용자를 차단하거나 축소 운영하는가?
- Runbook은 실제로 실행해 봤는가?
- 복구와 Rollback에 필요한 권한이 있는가?
- 주 담당자가 없어도 대응할 수 있는가?

Google SRE 자료도 Production Readiness Review와 명확한 Application 소유권, 공동 목표와 Runbook을 운영 준비의 핵심 활동으로 다룹니다.

## 14. PoC 종료 보고서에 반드시 들어가야 할 것

좋은 PoC 결과는 “성공” 또는 “실패” 두 단어로 끝나지 않습니다.

| 항목 | 기록 내용 |
|---|---|
| 검증 가설 | 무엇을 확인하려 했는가? |
| Dataset·환경 | 어떤 조건에서 시험했는가? |
| 성공 기준 | 어떤 지표와 Threshold를 사용했는가? |
| 결과 | 통과·미통과·판단 보류 |
| 한계 | 검증하지 않은 데이터·기능·규모 |
| 발견 위험 | 권한, 비용, 성능, 품질과 연동 문제 |
| 운영 Gap | 추가 설계·개발·검증 항목 |
| 다음 결정 | 중단·추가 PoC·단계 구축·본 개발 |

특히 “검증하지 않은 것”을 명시해야 PoC 결과가 과도하게 확대 해석되지 않습니다.

```text
검증 완료
  한국어 회의 파일의 STT 가능성

검증하지 않음
  실시간 동시 처리 용량
  사용자·Tenant 권한
  장애 후 재개
  장기 비용
  운영 품질 변화
```

이 구분은 실패를 숨기는 문구가 아니라 올바른 투자 결정을 위한 기술 정보입니다.

## 15. 운영 준비도 행렬을 사용한다

운영 준비도 (Production Readiness)를 한 점수로만 표현하면 높은 기능 점수가 낮은 보안 점수를 가릴 수 있습니다.

영역별 상태를 분리합니다.

| 영역 | PoC 통과 조건 | 운영 전환 조건 |
|---|---|---|
| 업무 가치 | 핵심 Use Case 가능 | 담당자·업무 KPI·운영 절차 |
| AI 품질 | 대표 Sample 통과 | Versioned Eval·회귀 Gate |
| 데이터 | 시험 데이터 처리 | ACL·보존·삭제·Lineage |
| 보안 | 시험 인증 | Tenant·객체 권한·감사 |
| 실행 안전 | Tool 호출 가능 | 승인·멱등성·중복 방지 |
| 신뢰성 | 정상 경로 성공 | Timeout·복구·축소 운영 |
| 관측성 | 개발 Log | Trace·Metric·Alert·Masking |
| 성능 | 단일 요청 충족 | 부하·Queue·용량·P95 |
| 비용 | 단일 실행 추정 | Tenant·업무별 예산과 경보 |
| 배포 | 시험 환경 실행 | CI/CD·Canary·Rollback |
| 운영 | 개발자 대응 | Owner·Runbook·Escalation |

보안 경계 위반, 데이터 삭제 불가와 승인 없는 파괴 작업처럼 상쇄할 수 없는 항목은 차단 조건으로 관리합니다.

```json
{
  "goLiveDecision": {
    "blockingConditions": {
      "crossTenantExposure": 0,
      "destructiveActionWithoutApproval": 0,
      "unrecoverableDataDeletion": 0
    },
    "requiredEvidence": [
      "evaluation_report",
      "load_test_report",
      "rollback_drill",
      "permission_test",
      "incident_runbook"
    ],
    "decision": "CONDITIONAL"
  }
}
```

## 16. PoC를 어떻게 설계해야 다시 만들지 않는가

PoC에 운영 기능을 모두 구현하자는 뜻은 아닙니다.

다음 순서가 현실적입니다.

```text
1. 업무 문제와 사용자 결정 확인
2. 가장 큰 기술·데이터 위험 선택
3. PoC 범위와 제외 범위 기록
4. 운영 목표 구조의 최소 수직 경로 구현
5. 결과와 한계를 평가
6. 운영 Gap의 비용·순서·책임 산정
7. 단계 구축 또는 중단 결정
```

여기서 “운영 목표 구조의 최소 수직 경로”가 중요합니다.

예를 들어 공용 개발 계정으로 모든 문서를 검색하는 대신, 두 개의 가상 Tenant와 최소 권한 Filter를 가진 작은 경로를 만듭니다. 전체 권한 시스템을 완성하지 않더라도 구조적으로 권한을 나중에 붙일 수 있는지 확인할 수 있습니다.

또한 Notebook 안에서만 Model을 호출하는 대신 다음 최소 경로를 검증합니다.

```text
Client
  → Authentication Boundary
  → AI Orchestrator
  → Retrieval or Tool
  → Model
  → Trace and Result
```

PoC 코드를 그대로 상용화하는 것이 목표가 아니라, 운영 구조를 불가능하게 만드는 가정을 조기에 발견하는 것이 목표입니다.

## 17. NIST AI RMF 관점으로 운영 전환을 다시 본다

NIST AI 위험관리 프레임워크 (AI Risk Management Framework, AI RMF)는 AI 위험관리를 다음 네 기능으로 구성합니다.

```text
거버넌스 (Govern)
  역할·정책·책임

맥락 정의 (Map)
  사용자·영향·위험과 사용 조건

측정 (Measure)
  품질·안전·성능·불확실성 평가

관리 (Manage)
  우선순위·대응·복구·지속 개선
```

이 구조는 운영 전환이 Model 평가 하나로 끝날 수 없는 이유를 잘 보여 줍니다.

- `Govern`이 없으면 장애와 위험의 책임자가 없습니다.
- `Map`이 없으면 누구에게 어떤 피해가 생길지 모릅니다.
- `Measure`가 없으면 품질 저하와 통제 실패를 감지할 수 없습니다.
- `Manage`가 없으면 감지한 문제를 중단·복구·개선으로 연결하지 못합니다.

NIST는 이러한 활동을 일회성 승인보다 AI 생명주기 전반의 지속 활동으로 설명합니다. 생성형 AI Profile도 AI RMF를 생성형 AI의 특성과 위험에 적용하는 보조 자료입니다.

## 18. 운영 전환 전 최종 체크리스트

### 목표와 범위

- [ ] PoC 가설과 운영 목표가 구분돼 있는가?
- [ ] 업무·AI 품질·운영 성공 기준이 각각 있는가?
- [ ] 검증하지 않은 데이터와 기능을 기록했는가?
- [ ] Go-live 차단 조건과 승인자가 정해져 있는가?

### 데이터와 권한

- [ ] 사용자·Tenant·객체 단위 권한을 모든 경로에서 검사하는가?
- [ ] RAG 검색 전에 ACL Filter가 적용되는가?
- [ ] 데이터 수집·보존·삭제·Index 반영 정책이 있는가?
- [ ] 운영 Log와 평가 Dataset에서 개인정보를 제거하는가?

### 실행과 복구

- [ ] 읽기·쓰기·중요·파괴 작업을 구분하는가?
- [ ] 승인이 사용자·작업·대상·입력·시간에 묶여 있는가?
- [ ] 쓰기 요청에 멱등성 Key가 있는가?
- [ ] Timeout 후 중복 실행 여부를 확인할 수 있는가?
- [ ] 비동기 상태와 Checkpoint가 영속화되는가?
- [ ] 외부 의존성 장애 시 축소 운영이 가능한가?

### 품질과 관측성

- [ ] Versioned 평가 Dataset과 회귀 Gate가 있는가?
- [ ] Model·Prompt·Tool·Index Version을 함께 기록하는가?
- [ ] Trace·Metric·Log가 요청 단위로 연결되는가?
- [ ] 품질·지연·오류·Token·비용 경보가 있는가?
- [ ] 민감정보를 저장하지 않는 관측 정책이 있는가?

### 배포와 운영

- [ ] 부하·권한·오류·복구 테스트를 실행했는가?
- [ ] Canary와 Rollback 기준이 있는가?
- [ ] 이전 Version으로 실제 복구해 봤는가?
- [ ] Owner, Runbook과 Escalation 경로가 있는가?
- [ ] SLO 위반 시 기능 개발과 안정화의 우선순위가 정해져 있는가?

## 19. 마무리

AI PoC는 필요합니다. 불확실한 기술과 데이터에 큰 비용을 투자하기 전에 가장 위험한 가설을 확인할 수 있기 때문입니다.

문제는 PoC가 아니라 PoC의 성공을 제품의 완성으로 해석하는 것입니다.

```text
PoC Success
  + Security Boundary
  + Data Governance
  + Safe Side Effects
  + Recovery
  + Evaluation
  + Observability
  + Cost and Capacity
  + Deployment and Ownership
  = Production Readiness
```

운영 전환은 모델 API 주변에 기능을 덧붙이는 마무리 단계가 아닙니다. 사용자·데이터·실행·실패와 책임을 하나의 서비스 계약으로 연결하는 별도의 Engineering 단계입니다.

PoC를 시작할 때부터 다음 두 문장을 함께 적으면 불필요한 재구축을 줄일 수 있습니다.

```text
이번 PoC에서 무엇을 검증할 것인가?
운영 전환 전에 무엇을 추가로 검증해야 하는가?
```

첫 문장은 기술 가능성을 명확하게 만들고, 두 번째 문장은 시연 성공과 운영 준비 사이의 숨은 비용을 드러냅니다.

---

## 참고 자료

- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST AI RMF Core - Govern, Map, Measure and Manage](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- [NIST AI 600-1 - Generative Artificial Intelligence Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- [Google Cloud - MLOps: Continuous Delivery and Automation Pipelines](https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)
- [Google Cloud Well-Architected Framework - AI and ML Reliability](https://docs.cloud.google.com/architecture/framework/perspectives/ai-ml/reliability)
- [Google SRE Workbook - Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Google SRE Workbook - SRE Engagement Model and Production Readiness](https://sre.google/workbook/engagement-model/)
- [OpenTelemetry - Signals](https://opentelemetry.io/docs/concepts/signals/)

> 이 글은 특정 Cloud나 AI Model을 필수 선택으로 제안하지 않습니다. 각 공식 자료의 운영 원칙을 일반화해 설명했으며, 실제 목표와 통제 수준은 업무 영향·규제·인프라·조직 책임에 맞게 결정해야 합니다.
