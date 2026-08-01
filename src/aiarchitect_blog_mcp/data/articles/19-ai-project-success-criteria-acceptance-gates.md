# Tistory 기술자료 초안

- 문서 ID: `BLOG-19`
- 상태: 공개 완료
- Tistory 상태: 2026-07-30 공개 게시 및 공개 페이지 검증 완료
- 분류: `기술 인사이트`
- 공개 URL: https://aiarchitect.tistory.com/20
- 권장 제목: `AI 프로젝트 성공 기준 8가지: 모델 정확도 전에 합의할 인수 기준`
- 검색 설명: `AI 프로젝트를 시작하기 전에 업무 가치, 사용자 성공, AI 품질, 안전, 신뢰성, 데이터, 비용과 운영 책임을 측정 가능한 인수 기준으로 정의하는 방법을 정리합니다.`
- 권장 태그: `AI 프로젝트`, `성공 기준`, `인수 기준`, `KPI`, `AI 평가`, `SLO`, `AI 거버넌스`, `MLOps`
- 권장 대표 이미지: `portfolio/architecture-diagrams/01-enterprise-ai-reference-architecture.svg`

---

# AI 프로젝트 성공 기준 8가지: 모델 정확도 전에 합의할 인수 기준

AI 프로젝트를 시작할 때 이런 표현을 자주 듣습니다.

```text
“답변을 잘하면 성공입니다.”
“정확도 90%를 목표로 하겠습니다.”
“사용자가 만족하면 운영으로 전환하겠습니다.”
```

방향은 맞지만 이 상태로는 프로젝트의 종료 여부를 판단할 수 없습니다.

무엇을 정확도라고 부르는지, 어떤 데이터로 평가하는지, 보안 위반 한 건을 높은 평균 점수가 상쇄할 수 있는지, 목표에 미달하면 누가 어떤 결정을 내리는지가 빠져 있기 때문입니다.

좋은 성공 기준은 홍보 문구가 아니라 **관찰 가능한 증거로 다음 행동을 결정하는 합의서**입니다.

```text
측정값 (Metric)
  → 목표 (Target)
    → 인수 기준 (Acceptance Gate)
      → 증거 (Evidence)
        → 결정과 조치 (Decision & Action)
```

이 글에서는 AI 프로젝트를 개발하기 전에 합의해야 할 성공 기준을 다음 여덟 영역으로 나눕니다.

1. 업무 가치 (Business Outcome)
2. 사용자 작업 성공 (Task Success)
3. AI 품질 (AI Quality)
4. 안전·보안·권한 (Safety, Security & Authorization)
5. 지연·가용성·복구 (Latency, Availability & Recovery)
6. 데이터·통합 준비도 (Data & Integration Readiness)
7. 비용·처리 용량 (Cost & Capacity)
8. 운영·거버넌스 책임 (Operations & Governance)

목표는 지표를 많이 만드는 것이 아닙니다.

**프로젝트가 성공했는지 같은 증거를 보고 같은 결론을 내릴 수 있게 만드는 것**입니다.

## 1. 데모 성공과 프로젝트 성공은 다르다

데모에서는 대표 질문 몇 개에 자연스러운 답변이 나오면 가능성을 확인할 수 있습니다.

프로젝트 성공은 더 넓은 질문에 답해야 합니다.

| 구분 | 데모에서 확인하는 것 | 프로젝트에서 확인해야 하는 것 |
|---|---|---|
| 기능 | 한 번 동작하는가? | 실제 업무 분포에서 반복 동작하는가? |
| 품질 | 답변이 그럴듯한가? | 근거가 있고 실패 유형이 허용 범위 안인가? |
| 사용자 | 관계자가 인상적이라고 느끼는가? | 대상 사용자가 업무를 더 잘 완료하는가? |
| 안전 | 눈에 띄는 문제가 없는가? | 금지된 데이터·권한·행동 경계를 지키는가? |
| 운영 | 개발자가 실행할 수 있는가? | 장애 감지·복구·변경 관리가 가능한가? |
| 경제성 | API 호출이 가능한가? | 성공한 업무 한 건의 총비용이 지속 가능한가? |

데모가 성공했다고 운영 전환이 자동으로 결정되는 것은 아닙니다.

반대로 모든 지표가 완벽해질 때까지 프로젝트를 계속하는 것도 올바른 기준은 아닙니다.

단계별로 필요한 증거와 허용할 위험을 정해야 합니다.

## 2. Metric, Target과 Gate를 구분한다

세 용어를 섞으면 회의 때마다 성공의 의미가 바뀝니다.

| 항목 | 의미 | 예시 |
|---|---|---|
| 측정값 (Metric) | 관찰할 수 있는 값과 계산 방법 | 업무 완료율 |
| 기준선 (Baseline) | AI 적용 전 또는 기존 방식의 값 | 기존 완료율 |
| 목표 (Target) | 개선하려는 바람직한 수준 | 기준선보다 개선 |
| 차단 기준 (Blocking Gate) | 미달하면 다른 점수와 무관하게 진행 중단 | Tenant 간 데이터 노출 0건 |
| 최적화 기준 (Optimization Metric) | 여러 목표 사이의 균형을 조정할 지표 | 응답 지연과 비용 |
| 증거 (Evidence) | 값을 재현할 평가 결과와 기록 | Version이 고정된 평가 보고서 |
| 조치 (Action) | 통과·미달 시 수행할 결정 | Pilot 확대·범위 축소·재평가 |

예를 들어 “정확도 90%”는 다음 질문 없이는 인수 기준이 아닙니다.

```text
정확도는 어떤 공식인가?
어떤 업무 유형을 포함하는가?
평가 데이터 Version은 무엇인가?
중요한 오류와 가벼운 오류의 가중치는 같은가?
평가자는 누구이며 불일치는 어떻게 해결하는가?
90% 미달이면 배포를 중단하는가, 제한 배포하는가?
```

## 3. 성공 기준은 가설과 평가 단위에서 시작한다

지표를 고르기 전에 프로젝트의 가설을 한 문장으로 씁니다.

```text
대상 사용자:
고객 상담 품질 관리 담당자

현재 문제:
긴 상담 기록에서 필수 확인 항목을 수작업으로 찾느라 시간이 오래 걸리고
검토자별 누락 편차가 크다.

AI 적용:
근거 구간과 함께 필수 확인 항목 후보를 제시한다.

기대 결과:
필수 항목의 누락을 늘리지 않으면서 검토 완료 시간을 줄인다.

평가 단위:
상담 기록 1건의 검토 업무
```

마지막의 평가 단위가 중요합니다.

문장 하나, LLM 호출 한 번, 화면 Session 한 번과 실제 업무 완료 한 건은 서로 다른 단위입니다.

업무 가치와 비용을 같은 단위로 연결하려면 “성공한 업무 결과 한 건”이 무엇인지 먼저 정의해야 합니다.

## 4. 성공 기준 1: 업무 가치 (Business Outcome)

첫 번째 기준은 모델이 아니라 업무 결과입니다.

대표 지표는 다음과 같습니다.

- 업무 완료 시간 (Time to Completion)
- 업무 완료율 (Completion Rate)
- 재작업률 (Rework Rate)
- 누락·오처리율 (Omission or Error Rate)
- 처리 대기 시간 (Lead Time)
- 수작업 단계 수 (Manual Steps)
- 서비스 전환·유지·해결률과 같은 업무별 결과

업무 완료율은 다음처럼 평가 단위를 명시해 계산합니다.

```text
업무 완료율
= 성공 조건을 충족한 업무 건수
÷ 평가 대상 업무 시도 건수
```

단순 사용량은 업무 가치의 대리 지표일 뿐입니다.

사용자가 AI 기능을 많이 열었다고 업무가 더 정확하고 빨라졌다고 단정할 수 없습니다.

가능하면 기존 방식의 기준선과 비교합니다.

```text
AI 적용 전 기준선
  ↕ 같은 업무 정의와 관찰 기간으로 비교
AI 적용 후 결과
```

비교 집단이나 순차적 Pilot을 사용할 수 없다면 최소한 계절성, 업무 난이도, 사용자 숙련도와 정책 변경이 결과에 미친 영향을 함께 기록합니다.

## 5. 성공 기준 2: 사용자 작업 성공 (Task Success)

좋은 답변이 나와도 사용자가 업무를 완료하지 못하면 제품은 성공하지 못합니다.

사용자 작업 성공은 AI 출력만이 아니라 전체 흐름을 평가합니다.

```text
질문 입력
  → 자료 선택
    → AI 결과 검토
      → 근거 확인
        → 수정·승인
          → 업무 시스템 반영
```

측정할 수 있는 지표는 다음과 같습니다.

| 지표 | 확인하려는 질문 |
|---|---|
| End-to-End 완료율 | 사용자가 의도한 업무를 끝냈는가? |
| 최초 시도 성공률 | 추가 안내 없이 한 번에 완료했는가? |
| 사람 개입률 (Human Intervention Rate) | 운영자·전문가의 도움이 얼마나 필요했는가? |
| 수정률 (Edit Rate) | 사용자가 결과를 얼마나 고쳐야 했는가? |
| 포기율 (Abandonment Rate) | 어느 단계에서 흐름을 중단했는가? |
| 근거 확인률 | 중요한 판단 전에 출처를 확인할 수 있었는가? |
| 업무 완료 시간 | 기존 방식보다 실제 시간이 줄었는가? |

사람 개입률은 무조건 낮을수록 좋은 값이 아닙니다.

법률, 의료, 금융, 인사 또는 파괴적 작업처럼 사람이 반드시 확인해야 하는 업무에서는 적절한 개입이 안전 통제입니다.

목표는 “사람 제거”가 아니라 **필요한 판단은 남기고 불필요한 반복 작업을 줄이는 것**입니다.

## 6. 성공 기준 3: AI 품질 (AI Quality)

AI 품질은 하나의 정확도로 압축하지 않습니다.

업무에 필요한 품질을 오류 유형별로 분리합니다.

회의 요약을 예로 들면 다음 지표가 서로 다릅니다.

- 필수 결정 사항 재현율 (Required Decision Recall)
- 존재하지 않는 결정 생성률 (Unsupported Decision Rate)
- 담당자·기한 추출 정확도
- 근거 인용 정확도 (Citation Precision)
- 근거 포함률 (Citation Coverage)
- 출력 Schema 유효률
- 금지 표현·민감정보 생성률

지원되지 않는 중요 주장 비율은 다음처럼 정의할 수 있습니다.

```text
지원되지 않는 중요 주장 비율
= 근거에서 확인할 수 없는 중요 주장을 포함한 출력 건수
÷ 평가한 출력 건수
```

전체 평균만 보면 드문 중요 실패가 가려집니다.

따라서 다음 Slice (세부 집단)를 별도로 확인합니다.

```text
짧은 기록 / 긴 기록
깨끗한 음성 / 소음이 많은 음성
단일 화자 / 다중 화자
한국어 / 혼합 언어
정상 입력 / 빈 입력 / 손상된 입력
일반 정보 / 민감정보 포함 자료
다수 업무 유형 / 낮은 빈도의 중요 업무
```

Google의 생성형 AI 평가 문서는 집계 지표와 개별 평가 사례를 함께 확인하는 방식을 제공합니다.

평균 점수는 경향을 보여 주고, 사례별 결과는 실패의 형태를 보여 줍니다.

둘 중 하나만으로는 인수 판단이 충분하지 않습니다.

## 7. 사람 평가와 AI Judge를 함께 설계한다

생성형 AI 출력은 정답 문자열 하나로 평가하기 어려울 때가 많습니다.

이때 Human Evaluation (사람 평가)과 AI Judge (AI 평가 모델)를 사용할 수 있습니다.

사람 평가에는 다음 계약이 필요합니다.

- 평가 Rubric (채점 기준)
- 좋은·나쁜 출력의 예시
- 평가자 교육 방식
- 평가자 간 불일치 처리
- 모호한 사례의 판정 책임자
- 평가 Dataset과 Rubric Version

AI Judge는 자동화에 유용하지만 그 자체가 정답은 아닙니다.

Google의 Judge 모델 평가 지침처럼 대상 업무의 사람 평가와 비교해 보정하고, 불일치가 큰 유형을 확인해야 합니다.

```text
대표 사례의 사람 평가
  → AI Judge 결과와 비교
    → 편향·불일치 Slice 확인
      → Rubric·Prompt·Judge Version 고정
        → 주기적 재보정
```

모델이 자기 출력을 평가하는 구조, 평가 모델 Version이 조용히 변경되는 구조, 설명 없이 점수만 남기는 구조는 피합니다.

## 8. 성공 기준 4: 안전·보안·권한 (Safety, Security & Authorization)

일부 기준은 평균 점수로 상쇄할 수 없습니다.

예를 들어 응답 만족도가 높아도 다음 사건이 발생했다면 그대로 운영 승인할 수 없습니다.

```text
다른 Tenant의 데이터 노출
권한 없는 문서 조회
승인 없는 파괴적 Tool 실행
비밀·자격 증명의 Prompt 또는 Log 노출
Prompt Injection으로 인한 정책 우회
감사 기록 없이 발생한 중요 Side Effect
```

이런 항목은 Blocking Gate (필수 통과 기준)로 둡니다.

| 안전 기준 예시 | 판단 방식 |
|---|---|
| Tenant 간 데이터 노출 | 시험 시나리오에서 0건, 발견 시 배포 차단 |
| 권한 없는 Tool 실행 | 0건, 정책·실행 계층 모두 검사 |
| 중요 작업의 승인 우회 | 0건, 승인과 실행 대상 Binding 확인 |
| 민감정보 출력 | 데이터 등급별 허용 기준과 차단 조치 |
| Prompt Injection | 공격 Fixture별 정책 경계 유지 여부 |
| 감사 누락 | 중요 작업의 결정·승인·실행 Event 연결 여부 |

“발견된 위반 0건”은 시스템에 취약점이 전혀 없다는 뜻이 아닙니다.

평가한 공격 시나리오, 도구, 데이터 범위와 관찰 기간 안에서 발견되지 않았다는 뜻입니다.

그래서 안전 기준에는 시험 범위와 잔여 위험 (Residual Risk)을 함께 기록해야 합니다.

NIST AI Risk Management Framework (AI 위험 관리 프레임워크)는 Govern, Map, Measure와 Manage를 수명주기 전반의 지속적인 기능으로 둡니다.

한 번의 출시 검사로 안전이 끝나지 않는 이유입니다.

## 9. 성공 기준 5: 지연·가용성·복구 (Latency, Availability & Recovery)

사용자가 경험하는 신뢰성을 측정하려면 먼저 SLI와 SLO를 구분합니다.

- 서비스 수준 지표 (Service Level Indicator, SLI): 실제 측정값
- 서비스 수준 목표 (Service Level Objective, SLO): 목표 수준

평균 응답 시간만으로는 느린 상위 구간을 볼 수 없습니다.

동기 요청은 p50, p95와 p99 지연을 함께 보고, 비동기 작업은 접수 시간과 최종 완료 시간을 분리합니다.

```text
API 접수 지연
≠ Queue 대기 시간
≠ Worker 처리 시간
≠ 결과 사용 가능 시간
```

평가할 항목은 다음과 같습니다.

- 동기 응답 p95 지연
- 비동기 완료 p95 시간
- 성공 요청 비율
- 결과 사용 가능 비율
- 장애 감지 시간
- 복구 시간 목표 (Recovery Time Objective, RTO)
- 재처리 후 중복 Side Effect 발생 여부
- 의존 서비스 장애 시 Graceful Degradation (점진적 기능 저하)

Google SRE는 SLO를 이해관계자가 합의한 신뢰성 목표로 보고, SLO 미달 시 어떤 행동을 할지 Error Budget Policy (오류 예산 정책)에 연결합니다.

예를 들어 설명용 정책은 다음과 같습니다.

```text
오류 예산이 소진되면
  → 신규 기능 확대를 일시 중단
  → 상위 실패 원인과 취약 Slice를 수정
  → 회귀 평가와 부하 시험을 다시 실행
  → 승인권자가 재개 여부를 결정
```

99.9% 같은 숫자를 먼저 선택하지 않습니다.

사용자 요구, 기존 기준선, 의존 서비스의 SLO, 비용과 실패 영향을 바탕으로 정합니다.

## 10. 성공 기준 6: 데이터·통합 준비도 (Data & Integration Readiness)

모델 품질이 좋아도 실제 데이터와 시스템에 연결되지 않으면 프로젝트는 멈춥니다.

데이터 준비도는 파일 수가 아니라 다음 질문으로 평가합니다.

- 대상 업무를 대표하는 데이터가 있는가?
- 데이터 사용 권한과 보존 목적이 확인됐는가?
- 문서별 접근 권한을 Retrieval과 결과에 적용할 수 있는가?
- 최신성, 누락, 중복과 삭제를 처리할 수 있는가?
- 원본에서 Chunk·Embedding·응답까지 계보 (Lineage)를 추적할 수 있는가?
- 빈 값, 손상 파일, 긴 문서와 혼합 언어를 처리하는가?
- 평가 Dataset이 운영 분포를 충분히 포함하는가?

통합 준비도는 API가 존재하는지만 보지 않습니다.

```text
인증·인가 계약
오류·Timeout 계약
Rate Limit과 용량
Idempotency (멱등성)
비동기 상태와 재시도
Schema Version 호환성
감사·추적 식별자
Sandbox·운영 환경 차이
```

Mock API에서 성공한 통합은 운영 권한, 실제 데이터 크기와 제한 조건에서 다시 검증해야 합니다.

## 11. 성공 기준 7: 비용·처리 용량 (Cost & Capacity)

AI 프로젝트 비용은 Token 가격만이 아닙니다.

검색, 저장소, Queue, 음성 처리, 재시도, 관측, 사람 검토와 운영 인력이 함께 들어갑니다.

성공 기준에서는 상세 견적보다 비용의 측정 단위를 먼저 정합니다.

```text
성공한 업무 결과당 비용
= 평가 범위의 전체 관련 비용
÷ 성공 조건을 충족한 업무 결과 수
```

API 호출당 비용이 낮아도 실패·재시도가 많고 사람이 대부분 다시 작업하면 업무 결과당 비용은 높아집니다.

최소한 다음 항목을 봅니다.

- 사용자·Tenant·업무 유형별 비용
- 성공·실패·재시도별 비용
- 평균과 상위 백분위 요청 비용
- 동시 요청과 Queue 적체 시 처리 용량
- Budget 초과 경보와 차단·저하 정책
- 사용량 증가 시 단위 비용 변화

비용 목표도 품질과 분리해 최적화하지 않습니다.

Prompt를 무조건 줄여 중요한 Context가 빠지거나 저가 모델로 변경해 중요 오류가 늘면 총업무비용이 오를 수 있습니다.

구체적인 견적 구성과 비용 추정 방법은 다음 글에서 별도로 다룹니다.

## 12. 성공 기준 8: 운영·거버넌스 책임 (Operations & Governance)

운영 준비는 문서가 존재하는지가 아니라 책임자가 실제로 행동할 수 있는지로 판단합니다.

| 항목 | 확인할 내용 |
|---|---|
| 소유권 (Ownership) | 업무, 모델, 데이터, 보안과 운영 책임자가 누구인가? |
| Runbook (운영 절차서) | 장애·품질 저하·비용 급증 때 무엇을 하는가? |
| Version 관리 | Model, Prompt, Retrieval, Tool, Dataset을 재현할 수 있는가? |
| 변경 승인 | 어떤 변경이 재평가와 승인을 요구하는가? |
| Rollback (되돌리기) | 안전한 이전 Version으로 돌아갈 수 있는가? |
| Incident 대응 | 누가 탐지·분류·통지·복구하는가? |
| 데이터 수명주기 | 수집, 보존, 삭제와 평가 재사용 정책이 있는가? |
| 재평가 주기 | 성능·위험·Drift를 언제 다시 측정하는가? |

다음 질문에 담당자 이름이나 역할로 답할 수 있어야 합니다.

```text
품질이 목표 아래로 떨어지면 누가 배포를 중단하는가?
보안 Blocking Gate 실패를 누가 판정하는가?
업무 정책 변경 시 누가 평가 Dataset을 갱신하는가?
모델 Version 변경을 누가 승인하는가?
장애 중 수동 운영으로 전환할 결정권자는 누구인가?
```

“개발팀이 알아서 대응한다”는 운영 책임 정의가 아닙니다.

## 13. Blocking Gate와 Optimization Metric을 섞지 않는다

모든 지표를 가중 평균한 종합 점수는 간단해 보이지만 위험할 수 있습니다.

```text
업무 가치 95점
사용자 만족 92점
응답 속도 90점
Tenant 격리 0점
----------------
평균 69.25점
```

이 경우 평균이 몇 점이든 출시하면 안 됩니다.

권장 구조는 두 단계입니다.

```text
1단계: 모든 Blocking Gate 통과
  - 법규·보안·권한·중요 안전 기준
  - 필수 기능·데이터 계약
  - 복구 불가능한 위험

2단계: Optimization Metric 검토
  - 품질·지연·비용의 균형
  - 개선 우선순위
  - 제한 Pilot 또는 확장 범위
```

종합 점수를 사용하더라도 각 필수 기준의 통과 여부를 숨기지 않습니다.

## 14. 기준선 없이 목표 숫자부터 정하지 않는다

목표는 다음 네 가지를 함께 보고 정합니다.

1. 현재 업무의 기준선
2. 사용자가 실제로 필요한 최소 수준
3. 실패가 초래하는 위험
4. 기술·비용·일정 제약

기준선이 없다면 Discovery (탐색) 단계의 첫 결과는 목표 달성이 아니라 기준선 측정일 수 있습니다.

```text
기존 업무 측정
  → 오류 유형과 분포 확인
    → AI 적용으로 개선 가능한 구간 식별
      → Pilot 목표 설정
        → 운영 SLO와 Gate 확정
```

설명용 수치를 계약서에 그대로 복사하지 않습니다.

“p95 10초”, “정확도 90%”, “비용 100원”은 업무와 시스템에 따라 의미가 완전히 달라집니다.

## 15. 대표 평가 Dataset과 실패 Slice를 Version으로 관리한다

좋은 평가 Dataset은 많이 모은 데이터가 아니라 의사결정에 필요한 분포를 가진 데이터입니다.

다음 구성을 권장합니다.

- 일반적인 정상 사례
- 빈도가 높고 가치가 큰 사례
- 빈도는 낮지만 실패 영향이 큰 사례
- 과거 장애·불만을 재현하는 사례
- 경계값·긴 입력·빈 입력·손상 입력
- 권한·Tenant·민감정보 공격 사례
- 새 정책·언어·고객군처럼 변화가 예상되는 사례

평가 결과에는 최소한 다음 Version을 연결합니다.

```json
{
  "evaluationId": "eval_fixture_019",
  "datasetVersion": "success-gate-fixture-v3",
  "rubricVersion": "rubric-fixture-v2",
  "modelVersion": "model-fixture-v1",
  "promptVersion": "prompt-fixture-v7",
  "retrievalVersion": "retrieval-fixture-v4",
  "toolRegistryVersion": "tools-fixture-v2",
  "evaluatedAt": "2026-07-29T09:00:00Z"
}
```

운영 데이터로 평가 Dataset을 갱신할 때 개인정보, 사용 목적, 보존 기간과 접근 권한을 함께 검토합니다.

## 16. Offline Evaluation과 Online Evaluation을 연결한다

Offline Evaluation (오프라인 평가)은 출시 전에 같은 조건을 반복 비교하기 좋습니다.

Online Evaluation (온라인 평가)은 실제 사용자, 실제 지연과 실제 데이터 분포에서만 나타나는 문제를 찾습니다.

| 평가 | 장점 | 놓치기 쉬운 것 |
|---|---|---|
| Offline | 재현 가능, Version 비교, 공격 시험 | 실제 사용 흐름·부하·행동 변화 |
| Shadow | 운영 입력 분포 관찰, 사용자 영향 제한 | 실제 상호작용과 후속 행동 |
| Limited Pilot | 실제 업무 가치와 안전 통제 확인 | 전체 조직·최대 부하 대표성 |
| Production Monitoring | Drift와 장기 성과 확인 | 출시 전 차단이 필요한 위험 |

둘은 대체 관계가 아닙니다.

```text
Offline Gate 통과
  → Shadow·제한 Pilot
    → Online 지표와 Incident 관찰
      → 운영 확대 또는 Rollback
```

## 17. 성공 기준 문서는 계산식까지 명시한다

지표 이름만 적으면 팀마다 다른 SQL과 Dashboard가 만들어집니다.

Metric Specification (지표 명세)에 다음 필드를 둡니다.

```json
{
  "metricId": "task_success_rate",
  "displayName": "업무 완료율 (Task Success Rate)",
  "businessUnit": "검토 업무 1건",
  "population": "Pilot 기간 중 인수 조건을 충족한 대상 업무",
  "numerator": "성공 조건을 충족한 업무 건수",
  "denominator": "평가 대상 업무 시도 건수",
  "exclusions": [
    "사용자 요청으로 취소된 건",
    "사전에 합의한 외부 시스템 전체 장애 구간"
  ],
  "slices": [
    "업무 유형",
    "입력 길이",
    "사용자 역할"
  ],
  "source": "versioned-evaluation-result-fixture",
  "ownerRole": "AI Product Owner",
  "reviewCadence": "pilot-weekly"
}
```

분모, 제외 조건과 시간 범위를 바꾸면 같은 이름의 지표도 다른 결과가 됩니다.

변경 이력과 승인자를 남깁니다.

## 18. 성공 계약 (Success Contract) 예시

아래 값은 구조를 설명하기 위한 Fixture (예시 데이터)입니다.

실제 목표는 기준선, 업무 위험과 측정 결과로 교체해야 합니다.

```json
{
  "contractId": "success-contract-fixture-019",
  "useCase": "회의 후속 업무 후보 생성",
  "evaluationUnit": "최종 녹취록이 존재하는 회의 1건",
  "baselineVersion": "baseline-fixture-v1",
  "datasetVersion": "dataset-fixture-v3",
  "gates": [
    {
      "id": "business_task_time",
      "type": "OPTIMIZATION",
      "metric": "median_review_minutes",
      "target": {
        "operator": "IMPROVE_FROM_BASELINE",
        "value": 0.25,
        "unit": "ratio"
      },
      "evidence": "pilot-task-report"
    },
    {
      "id": "quality_required_action_recall",
      "type": "REQUIRED",
      "metric": "required_action_recall",
      "target": {
        "operator": "GTE",
        "value": 0.9,
        "unit": "ratio"
      },
      "evidence": "human-reviewed-evaluation"
    },
    {
      "id": "security_cross_tenant_exposure",
      "type": "BLOCKING",
      "metric": "cross_tenant_exposure_count",
      "target": {
        "operator": "EQ",
        "value": 0,
        "unit": "incident"
      },
      "evidence": "authorization-attack-suite"
    },
    {
      "id": "reliability_result_ready",
      "type": "REQUIRED",
      "metric": "result_ready_ratio",
      "target": {
        "operator": "GTE",
        "value": 0.99,
        "unit": "ratio"
      },
      "evidence": "load-and-recovery-test"
    }
  ],
  "decisionPolicy": {
    "blockingFailure": "FAIL",
    "requiredFailure": "CONDITIONAL_PASS_OR_FAIL_BY_APPROVER",
    "optimizationMiss": "IMPROVEMENT_PLAN_REQUIRED"
  },
  "approverRoles": [
    "Business Owner",
    "Service Owner",
    "Security Owner"
  ]
}
```

한 문서에서 업무, 품질, 안전과 운영 기준을 연결하면 특정 팀의 지표만 좋아졌을 때 전체 프로젝트가 성공했다고 오해하는 일을 줄일 수 있습니다.

## 19. 단계별 Acceptance Gate를 다르게 둔다

처음부터 운영 수준의 모든 기준을 요구하면 탐색이 불가능하고, PoC 기준을 그대로 운영에 적용하면 위험합니다.

| 단계 | 핵심 질문 | 필요한 증거 |
|---|---|---|
| Discovery 종료 | 해결할 가치가 있고 측정 가능한가? | 업무 가설, 기준선, 데이터·위험 지도 |
| PoC 종료 | 기술적으로 가능한가? | 대표 Dataset의 품질 결과, 주요 실패 유형 |
| Pilot 종료 | 실제 사용자가 안전하게 가치를 얻는가? | 업무 결과, 사용자 흐름, 보안·부하·비용 결과 |
| 운영 출시 | 지속적으로 운영하고 복구할 수 있는가? | SLO, Runbook, Owner, Rollback, 감사와 승인 |
| 확장 승인 | 더 많은 사용자·Tenant·업무에 적용 가능한가? | Slice별 성능, 용량, Incident와 비용 추세 |

단계가 바뀔 때 Dataset, 부하, 사용자 범위와 위험 수준도 함께 넓어져야 합니다.

## 20. 판정 상태를 네 가지로 고정한다

회의 결과를 “대체로 괜찮음”으로 남기지 않습니다.

```text
PASS
  모든 Blocking·Required Gate가 통과했고 증거가 유효함

CONDITIONAL_PASS
  Blocking Gate는 통과했지만 제한 범위·기한·보완 조치가 필요함

FAIL
  Blocking Gate 실패 또는 핵심 Required Gate 미달

NOT_EVALUATED
  데이터·도구·표본·환경 부족으로 아직 판단할 수 없음
```

`NOT_EVALUATED`를 실패와 구분해야 합니다.

측정하지 못한 항목을 0점으로 처리하면 기술 실패와 준비 부족이 섞이고, 공란으로 두면 통과한 것처럼 오해할 수 있습니다.

조건부 통과에는 반드시 제한 조건과 만료일을 둡니다.

```json
{
  "decision": "CONDITIONAL_PASS",
  "scope": "내부 Pilot 사용자 그룹",
  "conditions": [
    "쓰기 Tool 비활성화",
    "사람의 최종 승인 필수",
    "긴 입력 Slice 재평가"
  ],
  "expiresAt": "2026-08-31T15:00:00Z",
  "approverRole": "Service Owner"
}
```

## 21. 인수 증거 패키지 (Acceptance Evidence Package)

최종 회의의 발표 자료만 남기지 않습니다.

재현 가능한 증거 패키지에는 다음 항목을 포함합니다.

- 성공 기준과 변경 이력
- 기준선 측정 결과
- Version이 고정된 평가 Dataset과 Rubric
- 집계 지표와 사례별 평가 결과
- 실패 Slice와 미해결 위험
- 보안·권한·Prompt Injection 시험 결과
- 부하·장애·복구 시험 결과
- 비용·용량 보고서
- Runbook 실행 또는 Game Day 결과
- Model·Prompt·Retrieval·Tool Version
- 승인자, 판정, 조건과 후속 조치

증거를 재현할 수 없다면 다음 모델·Prompt 변경이 실제 개선인지 판단하기 어렵습니다.

## 22. 성공 기준에도 Owner와 Review Date가 필요하다

Google SRE의 SLO 문서는 작성자, 검토자, 승인자와 다음 검토 시점을 기록할 것을 권장합니다.

AI 프로젝트 성공 기준도 같은 방식이 유용합니다.

| 역할 | 책임 |
|---|---|
| Business Owner | 업무 가치와 허용 가능한 실패 영향 결정 |
| Product Owner | 사용자 범위와 작업 성공 기준 관리 |
| AI·ML Owner | 품질 평가, Dataset과 Model 변경 관리 |
| Data Owner | 데이터 사용 권한·품질·수명주기 결정 |
| Security Owner | Blocking Gate와 잔여 위험 승인 |
| Service Owner | SLO, 용량, Runbook과 Incident 대응 |
| Independent Reviewer | 평가 방법·증거·판정의 편향 검토 |

한 사람이 여러 역할을 맡을 수 있지만 책임 자체를 생략할 수는 없습니다.

성공 기준은 고정 문서가 아닙니다.

업무 정책, 데이터 분포, 모델, Tool 또는 위험이 바뀌면 검토해야 합니다.

## 23. 자주 실패하는 성공 기준 안티패턴

### 안티패턴 1: 정확도 하나로 전체 성공을 정의한다

사용자 업무, 안전, 지연과 비용을 볼 수 없습니다.

### 안티패턴 2: 기준선 없이 목표를 정한다

개선 여부와 목표의 현실성을 판단할 수 없습니다.

### 안티패턴 3: 평균만 보고 중요한 Slice를 보지 않는다

희귀하지만 영향이 큰 실패가 가려집니다.

### 안티패턴 4: 사용량을 업무 가치로 간주한다

반복 시도와 실패도 높은 사용량으로 보일 수 있습니다.

### 안티패턴 5: 모델 출력만 평가한다

Retrieval, 권한, UI, 후속 시스템 반영 실패를 놓칩니다.

### 안티패턴 6: 보안 점수를 다른 지표와 평균낸다

차단해야 할 위험이 높은 품질 점수로 상쇄됩니다.

### 안티패턴 7: 목표 미달 때 행동이 없다

Dashboard는 있지만 배포·축소·Rollback 결정으로 이어지지 않습니다.

### 안티패턴 8: 평가 조건과 Version을 남기지 않는다

결과를 재현하거나 변경 전후를 비교할 수 없습니다.

## 24. Kickoff에서 결정할 질문

프로젝트 착수 회의에서 다음 질문에 답합니다.

### 업무와 사용자

- [ ] 어떤 사용자의 어떤 업무를 개선하는가?
- [ ] 성공한 업무 한 건은 무엇인가?
- [ ] 기존 방식의 기준선은 무엇인가?
- [ ] AI를 사용하지 않는 편이 나은 범위는 어디인가?

### 품질과 안전

- [ ] 반드시 맞아야 하는 사실과 허용 가능한 오류는 무엇인가?
- [ ] 평균 외에 어떤 Slice를 별도로 평가하는가?
- [ ] 어떤 실패가 즉시 출시를 차단하는가?
- [ ] 사람이 반드시 검토·승인해야 하는 작업은 무엇인가?

### 시스템과 운영

- [ ] 사용자가 기다릴 수 있는 시간과 필요한 SLO는 무엇인가?
- [ ] 장애 시 어떤 기능으로 저하하거나 수동 절차로 전환하는가?
- [ ] 실제 데이터·권한·API 계약을 언제 검증하는가?
- [ ] 성공한 업무 결과당 비용과 최대 처리량을 어떻게 측정하는가?

### 판정과 책임

- [ ] 각 지표의 계산식, Dataset과 관찰 기간은 무엇인가?
- [ ] 증거를 누가 생성하고 검토하는가?
- [ ] PASS·CONDITIONAL_PASS·FAIL을 누가 승인하는가?
- [ ] 조건부 통과의 범위, 조치와 만료일은 무엇인가?

## 25. 운영 전 최종 체크리스트

- [ ] 업무 가설과 평가 단위를 한 문장으로 정의했다.
- [ ] AI 적용 전 기준선을 측정했다.
- [ ] 업무 가치와 사용자 작업 성공을 분리해 측정한다.
- [ ] AI 품질을 오류 유형과 Slice별로 평가한다.
- [ ] 사람 평가 Rubric과 AI Judge 보정 절차가 있다.
- [ ] 보안·권한·중요 안전 항목을 Blocking Gate로 분리했다.
- [ ] SLI, SLO와 오류 예산 소진 시 조치를 정했다.
- [ ] 실제 데이터의 권한·품질·최신성과 통합 계약을 검증했다.
- [ ] 성공한 업무 결과당 비용과 처리 용량을 측정한다.
- [ ] Model, Prompt, Retrieval, Tool과 Dataset Version을 기록한다.
- [ ] Offline Gate와 Online Pilot 지표를 연결했다.
- [ ] PASS·CONDITIONAL_PASS·FAIL·NOT_EVALUATED 상태를 사용한다.
- [ ] 각 기준에 Owner, Evidence, Review Date와 Action이 있다.
- [ ] 조건부 통과에 범위, 보완 조치와 만료일이 있다.
- [ ] 재현 가능한 인수 증거 패키지를 보존한다.

## 마무리

AI 프로젝트 성공 기준은 “모델이 얼마나 똑똑한가?”라는 질문만으로 만들 수 없습니다.

다음 여덟 영역이 함께 연결되어야 합니다.

```text
업무 가치
  + 사용자 작업 성공
  + AI 품질
  + 안전·보안·권한
  + 지연·가용성·복구
  + 데이터·통합 준비도
  + 비용·처리 용량
  + 운영·거버넌스 책임
```

핵심 원칙은 다음과 같습니다.

1. Metric, Target, Gate, Evidence와 Action을 구분합니다.
2. 업무 가설과 평가 단위를 먼저 정합니다.
3. 기준선과 대표 Dataset 없이 목표 숫자를 만들지 않습니다.
4. 평균뿐 아니라 중요한 실패 Slice를 봅니다.
5. 보안·권한과 중대한 안전 기준은 Blocking Gate로 관리합니다.
6. Offline 평가를 실제 사용자 Pilot과 운영 지표로 연결합니다.
7. 통과·조건부 통과·실패·미평가의 판정 규칙을 고정합니다.
8. 모든 기준에 책임자와 목표 미달 시 조치를 연결합니다.

좋은 성공 기준은 프로젝트가 잘될 것이라고 약속하지 않습니다.

대신 **어떤 조건에서 시작하고, 무엇을 측정하며, 어느 증거로 확대·보완·중단을 결정할지 명확하게 만듭니다.**

다음 글에서는 AI 프로젝트 비용을 모델 API 단가만으로 계산하면 왜 실제 견적과 달라지는지, 데이터·통합·평가·보안·운영 비용까지 포함해 살펴보겠습니다.

## 참고 자료

- [NIST AI Risk Management Framework 1.0](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- [NIST AI 600-1: Generative Artificial Intelligence Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- [Google SRE Workbook: Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Google SRE Workbook: Example Error Budget Policy](https://sre.google/workbook/error-budget-policy/)
- [Google SRE Workbook: SLOs for Data Processing Pipelines](https://sre.google/workbook/data-processing/)
- [Google Cloud: Evaluate Gen AI Models and Applications](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-overview)
- [Google Cloud: View and Interpret Evaluation Results](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/eval-python-sdk/view-evaluation)
- [Google Cloud: Evaluate a Gen AI Judge Model](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/evaluate-judge-model)

---

> 이 글은 2026년 7월 29일 기준 NIST와 Google의 공식 공개 문서 및 공개 가능한 엔터프라이즈 AI 프로젝트 설계 경험을 바탕으로 작성했습니다. 예시 목표값, Dataset, 계약, 평가 결과와 날짜는 구조 설명을 위한 Fixture이며 실제 적용 시 업무 기준선, 데이터 분포, 위험 등급, 관련 법규, 조직 정책, 비용과 사용자 요구에 맞게 다시 측정하고 승인해야 합니다.
