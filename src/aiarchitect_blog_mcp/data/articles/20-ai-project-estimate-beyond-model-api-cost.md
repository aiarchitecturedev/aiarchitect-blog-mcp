# AI 프로젝트 견적이 모델 API 비용만으로 정해지지 않는 이유: 10개 산정 항목

AI 프로젝트 견적을 요청하면 가장 먼저 모델 가격표를 확인하기 쉽습니다.

```text
평균 입력 Token × 입력 단가
+ 평균 출력 Token × 출력 단가
= AI 프로젝트 비용?
```

이 계산은 **모델 사용료의 일부**를 추정할 때는 필요합니다.

하지만 프로젝트 전체 견적은 아닙니다.

실제 AI 서비스에는 모델 앞뒤로 많은 시스템이 필요합니다.

```text
업무 정의
  → 데이터 수집·정제·권한
    → 검색·Prompt·Model
      → 업무 시스템 통합
        → 품질·보안·부하 시험
          → 배포·관측·복구
            → 운영·변경 관리
```

OpenAI의 공식 API 가격표만 보더라도 입력, Cached Input (캐시된 입력), 출력, Context 길이, 처리 등급, 음성·이미지와 Tool 사용의 과금 단위가 서로 다릅니다.

그런데 이것도 전체 시스템 중 한 공급자의 사용료 구조일 뿐입니다.

Google Cloud의 AI·ML 비용 최적화 지침은 Training, Inference, Storage와 Network 비용을 업무 가치와 연결하고, 데이터 거버넌스·MLOps·모니터링까지 수명주기 전반에서 관리하도록 설명합니다.

Azure Well-Architected Framework의 Cost Model (비용 모델)은 초기 비용, Run Rate (반복 운영 비용), 지속 비용과 예상 밖 지출의 완충을 함께 다루며, 관측·보안·거버넌스 같은 지원 서비스도 비용에 포함해야 한다고 설명합니다.

이 글에서는 AI 프로젝트 견적을 다음 다섯 층과 열 개 산정 항목으로 분해합니다.

```text
Build    구축 비용
Run      사용량 비용
Operate  운영 비용
Change   변경 비용
Risk     불확실성 비용
```

목표는 숫자를 크게 만드는 것이 아닙니다.

**무엇을 만들고, 어떤 가정으로 계산했으며, 무엇이 바뀌면 견적도 달라지는지를 설명할 수 있게 만드는 것**입니다.

## 1. 비용, 견적과 가격은 같은 말이 아니다

먼저 세 개념을 분리합니다.

| 개념 | 질문 | 포함 내용 |
|---|---|---|
| 비용 (Cost) | 만들고 운영하는 데 무엇이 드는가? | 인력, Cloud, License, 운영 |
| 견적 (Estimate) | 현재 정보로 얼마나 들 것으로 예상하는가? | 범위, 수량, 단가, 가정, 오차 |
| 제안 가격 (Quoted Price) | 어떤 조건으로 계약할 것인가? | 견적, 위험, 지원, 상업 조건 |

견적은 사실처럼 고정된 숫자가 아니라 현재까지 확인한 조건에 따른 예측입니다.

```text
견적
= 작업 패키지별 노력
+ 외부 서비스·License
+ 환경·운영 준비
+ 합의한 위험 완충
```

계약 가격에는 지급 조건, 보증 범위, 지원 기간과 계약상 위험 배분이 추가될 수 있습니다.

세금, 외부 플랫폼 수수료와 제3자 서비스 비용을 누가 부담하는지도 별도로 명시해야 합니다.

## 2. 다섯 층의 비용 모델로 시작한다

AI 프로젝트 비용을 한 줄로 합치기 전에 성격별로 나눕니다.

| 비용 층 | 의미 | 대표 항목 |
|---|---|---|
| 구축 비용 (Build Cost) | 최초 사용 가능한 시스템을 만드는 비용 | 설계, 개발, 데이터, 통합, 시험 |
| 사용량 비용 (Run Cost) | 실제 호출·처리에 비례하는 비용 | Model, STT, 검색, Storage, Network |
| 운영 비용 (Operating Cost) | 서비스를 유지하는 비용 | 모니터링, Incident, 재평가, 지원 |
| 변경 비용 (Change Cost) | 업무·데이터·Model 변화 대응 비용 | 회귀 시험, Migration, 재배포 |
| 불확실성 비용 (Risk Allowance) | 아직 확인되지 않은 위험의 범위 | 미확정 API, 데이터 품질, 규제 검토 |

구축비가 낮아도 매월 높은 사람 검토 비용과 장애 대응 비용이 발생할 수 있습니다.

반대로 초기 자동화 비용을 더 투자해 반복 운영비를 낮출 수도 있습니다.

따라서 초기 견적과 총소유비용 (Total Cost of Ownership, TCO)을 함께 봅니다.

```text
기간 T의 총소유비용
= 최초 구축 비용
+ T 기간의 사용량 비용
+ T 기간의 운영 비용
+ 예상 변경 비용
+ 잔여 위험 비용
```

## 3. 견적의 첫 번째 입력은 Model이 아니라 업무 범위다

“사내 문서 챗봇”이라는 한 문장으로는 견적을 만들 수 없습니다.

다음 두 프로젝트는 같은 모델을 사용해도 범위가 전혀 다릅니다.

| 질문 | 제한된 내부 검색 | 기업 업무 Agent |
|---|---|---|
| 사용자 | 소규모 Pilot | 여러 조직·Tenant |
| 데이터 | 승인된 정적 문서 | 문서·회의·업무 시스템 |
| 기능 | 검색과 답변 | 조회·생성·수정·승인 |
| 권한 | 단일 Role | 사용자·객체·Tool 단위 |
| 지연 | 비동기 허용 | 일부 실시간 |
| 장애 영향 | 다시 질문 | 업무 Side Effect 가능 |
| 감사 | 기본 사용 기록 | 결정·승인·실행 추적 |

견적 전에 다음 범위를 한 문장으로 고정합니다.

```text
대상 사용자:
무슨 업무를:
어떤 데이터와 시스템으로:
어디까지 자동화하고:
어떤 사람이 최종 책임을 지며:
어떤 품질·보안·SLO로:
언제까지 검증할 것인가:
```

이 정의가 바뀌면 단순 화면 변경이 아니라 데이터, 권한, 시험과 운영 범위가 함께 바뀔 수 있습니다.

## 4. 산정 항목 1: Discovery와 성공 기준

Discovery (사전 진단)는 개발 전 무료 대화가 아니라 불확실성을 줄이는 기술 작업입니다.

주요 작업은 다음과 같습니다.

- 업무 흐름과 대상 사용자 인터뷰
- 현재 방식의 기준선 측정
- AI가 필요한 문제인지 검토
- 데이터·시스템·권한 현황 조사
- 성공 기준과 Acceptance Gate (인수 기준) 정의
- 위험·의존성·제외 범위 식별
- 기준 아키텍처와 단계별 구현 계획 작성

Discovery가 빠지면 개발 단계에서 다음 질문이 반복됩니다.

```text
무엇이 정답인가?
누가 이 데이터에 접근할 수 있는가?
어느 시스템이 원본인가?
실패하면 사람이 어떻게 처리하는가?
어떤 수치면 완료인가?
```

초기 견적이 낮아 보일 수 있지만 뒤에서 재작업과 변경 요청으로 돌아옵니다.

Discovery 산출물은 회의록이 아니라 범위 명세, 가정 목록, 데이터 지도, 위험 목록, 평가 계획과 단계별 견적 기준이어야 합니다.

## 5. 산정 항목 2: 데이터 준비와 거버넌스

RAG 또는 AI 분석 프로젝트에서 “문서가 있다”와 “운영에 사용할 수 있는 데이터가 준비됐다”는 다릅니다.

데이터 작업에는 다음 항목이 포함될 수 있습니다.

- 데이터 Source 조사와 접근 권한
- 추출·변환·정제
- Encoding, OCR, 표와 첨부 처리
- 중복·삭제·최신성 관리
- Chunking, Metadata와 Embedding
- 문서·사용자별 ACL (접근 제어 목록)
- 개인정보 탐지·Masking
- 평가용 정답과 실패 Fixture 제작
- Lineage (데이터 계보), 보존과 삭제
- 증분 수집·재처리·복구

비용 동인은 파일 개수 하나가 아닙니다.

```text
파일 수
× 형식 다양성
× 평균·상위 크기
× 변경 빈도
× 권한 복잡도
× 품질 문제
× 보존·삭제 요구
```

샘플 PDF 열 개로 만든 PoC 견적을 실제 권한이 다른 수십만 문서의 운영 인덱싱에 그대로 적용할 수 없습니다.

## 6. 산정 항목 3: AI·RAG·Agent 핵심 로직

모델 호출 외에도 답변을 만들기 위한 Application Logic (응용 로직)이 필요합니다.

- Model 후보 비교와 Routing
- System Prompt와 업무별 Prompt
- Structured Output (구조화 출력) 검증
- Query 변환과 Hybrid Retrieval (혼합 검색)
- Reranking (재순위화)
- Context 조립과 인용
- Tool 선택·인자 검증
- Multi-step Workflow (다단계 흐름)
- Retry (재시도), Fallback (대체 경로)과 Timeout
- Checkpoint (상태 저장)와 Idempotency (멱등성)
- Model·Prompt·Index Version 관리

같은 요청도 실행 경로가 다를 수 있습니다.

```text
단순 질문
  → 검색 1회
  → Model 1회

복합 질문
  → 질문 분해
  → 검색 여러 회
  → Tool 조회
  → 중간 판단
  → 최종 Model 호출
```

그래서 “사용자 질문 한 건”과 “Model 호출 한 번”을 같은 단위로 계산하면 안 됩니다.

## 7. 산정 항목 4: 기존 시스템 통합

기업 AI 프로젝트는 새 화면보다 기존 시스템과의 경계에서 시간이 많이 들 수 있습니다.

통합 항목은 다음과 같습니다.

- SSO, OAuth·OIDC와 Service Account
- 사용자·조직·Tenant Context
- 기존 REST·GraphQL·Database·Message Queue
- MCP Tool·Resource 계약
- 파일 업로드·다운로드
- 동기·비동기 상태와 Webhook
- Rate Limit, Timeout과 재시도
- Schema Version과 하위 호환성
- 개발·검증·운영 환경 연결
- 실제 장애 코드와 예외 처리

API 문서가 존재한다고 통합이 끝난 것은 아닙니다.

Sandbox와 운영의 인증 방식이 다르거나, 테스트 데이터가 없거나, 호출 권한 승인에 시간이 걸리거나, API가 비동기인데 완료 상태 계약이 없을 수 있습니다.

견적에는 개발 노력뿐 아니라 외부 팀 의존성과 대기 조건을 가정으로 남깁니다.

## 8. 산정 항목 5: 사용자 경험과 사람의 검토 흐름

AI 출력이 좋은 것과 사용자가 안전하게 업무를 완료하는 것은 다릅니다.

필요한 UX는 Chat 입력창 하나보다 넓을 수 있습니다.

- Source와 근거 구간 확인
- 생성 중·완료·실패 상태
- 결과 수정·재생성
- 신뢰도와 제한 사항 표시
- 위험 작업 Preview (실행 전 보기)
- 승인·거부·취소
- 실패 후 재시도와 수동 처리
- 접근 권한 부족 안내
- 사용자 Feedback과 이의 제기
- 접근성·다국어·Mobile 대응

사람 검토가 필요한 업무라면 Human-in-the-loop (사람 참여형 검토)의 시간도 TCO에 포함합니다.

```text
월간 사람 검토 비용
= 대상 업무 건수
× 건당 평균 검토 시간
× 검토자의 시간 단가
```

AI API 비용이 낮더라도 대부분의 결과를 처음부터 다시 작성하면 총비용은 높습니다.

## 9. 산정 항목 6: 보안·개인정보·규제 대응

보안은 출시 직전 점검표 한 장이 아니라 설계·구현·검증 작업입니다.

- Threat Modeling (위협 모델링)
- 인증·인가와 Least Privilege (최소 권한)
- Tenant·객체·Tool 단위 접근 통제
- Secret과 Token 관리
- Encryption과 Key 관리
- Prompt Injection 시험
- 데이터 유출·과도한 Agency 시험
- 감사 Event와 보존
- 개인정보 처리와 삭제
- 공급자·지역·데이터 처리 조건 검토
- Incident 대응과 통지 절차

NIST AI RMF는 Govern, Map, Measure와 Manage를 전체 수명주기에서 계속 수행하도록 설명하며, 시험·평가·검증·확인 (Testing, Evaluation, Verification and Validation, TEVV)을 문서화하도록 권고합니다.

보안·안전 요구가 높은 업무는 더 많은 설계, 독립 검토, 공격 시험과 증거가 필요합니다.

그 비용을 빼면 위험이 사라지는 것이 아니라 견적 밖으로 숨겨집니다.

## 10. 산정 항목 7: 품질 평가와 회귀 시험

“Prompt를 몇 번 조정한다”는 평가 계획이 아닙니다.

다음 작업이 필요할 수 있습니다.

- 대표 Dataset과 Slice 설계
- 정답·Rubric (채점 기준) 작성
- 도메인 전문가 평가
- 평가자 간 불일치 조정
- AI Judge (AI 평가 모델) 보정
- 정확성·근거성·안전성 평가
- Model·Prompt·Retrieval 조합 실험
- 회귀 시험 자동화
- 부하·장애·보안 시험
- 인수 증거 보고서

평가 비용은 다음 변수에 민감합니다.

```text
평가 사례 수
× 평가 Version 수
× 비교할 구성 수
× 사람 평가 시간
× 재검토 비율
```

Google의 MLOps 지침은 일반 Software Test 외에 데이터 검증, Model 품질 평가와 Model 검증이 필요하다고 설명합니다.

NIST AI RMF도 배포 전과 운영 중의 반복 평가, 대표적인 조건, 불확실성과 문서화를 강조합니다.

평가를 생략하면 비용을 절약한 것이 아니라 품질 실패를 운영 사용자에게 이전한 것입니다.

## 11. 산정 항목 8: Platform·환경·신뢰성

Model API가 관리형이어도 Application Runtime과 데이터 계층은 필요합니다.

- 개발·검증·운영 환경
- API Gateway와 Backend
- Database·Object Storage·Vector Store
- Queue·Worker·Scheduler
- Cache와 Session
- Network·DNS·Certificate
- Backup·Restore
- Autoscaling과 용량 제한
- CI/CD·Infrastructure as Code
- Rollback과 Disaster Recovery

신뢰성 목표가 높아질수록 중복 구성, 자동 복구, 시험과 운영 복잡성이 커질 수 있습니다.

```text
높은 SLO
  → 다중 Instance·Zone
  → 더 강한 Queue·재처리
  → Backup·복구 시험
  → 더 많은 관측과 On-call
```

Azure 비용 모델 지침도 성능, 확장성, 관측, Backup과 Disaster Recovery 요구가 비용에 영향을 준다고 설명합니다.

## 12. 산정 항목 9: 관측성과 비용 통제

운영에서 비용을 알기 위해서도 먼저 측정 기능을 만들어야 합니다.

- 요청·Workflow·Tool별 Trace
- 성공률·지연·Queue·오류 Metric
- 입력·출력·Cached Token 사용량
- Model·업무·Tenant별 비용 Attribution (귀속)
- Log 수집·Masking·보존
- 품질 Drift와 안전 신호
- Budget·Quota·Anomaly Alert
- Dashboard와 정기 보고

Google Cloud는 AI·ML 비용을 Project, Team, Environment, Model, Dataset과 Use Case 단위로 귀속할 수 있는 Label과 Billing Data를 권장합니다.

태그와 식별자가 없다면 월말 청구서는 확인할 수 있어도 어느 업무가 비용을 만들었는지 설명하기 어렵습니다.

관측 데이터 자체도 저장·조회·보존 비용이 발생합니다.

모든 Prompt와 결과 전문을 무기한 저장하는 대신 재현성과 개인정보 보호를 함께 고려한 수집 범위를 정합니다.

## 13. 산정 항목 10: 운영 인수·교육·변경 관리

운영은 배포 버튼을 누르는 것으로 시작하지 않습니다.

- Runbook (운영 절차서)
- 장애 등급과 연락 체계
- 운영자·사용자 교육
- 권한 신청·회수 절차
- Model·Prompt 변경 승인
- 품질·비용 정기 Review
- Incident 대응과 사후 분석
- 데이터 재인덱싱·재평가
- 공급자 장애·가격·정책 변경 대응
- Warranty (보증)와 유지보수 범위

운영 담당자가 누구인지, 업무 시간 외 대응이 필요한지, 월간 변경량이 어느 정도인지에 따라 반복 비용이 달라집니다.

Google과 AWS의 AI·ML 비용 지침이 비용 최적화를 PoC부터 운영까지 계속되는 수명주기 활동으로 보는 이유입니다.

## 14. Model API 비용도 한 줄 곱셈으로 끝나지 않는다

Model 비용 자체도 요청 경로와 과금 단위로 계산해야 합니다.

설명용 수식은 다음과 같습니다.

```text
월간 Model 비용
= Σ 실행 경로별 요청 건수
   × (
       평균 입력 Token × 입력 단가
       + 평균 Cached Input Token × Cached Input 단가
       + 평균 출력 Token × 출력 단가
       + Tool·Search·Container 사용료
     )
   × 재시도·Fallback 계수
```

Multimodal (다중 Modal) 시스템은 추가 단위를 가질 수 있습니다.

```text
음성 처리 시간
+ 이미지·영상 처리량
+ Embedding Token
+ Vector·File Storage 기간
+ Search·Tool 호출
+ Network 전송
```

최신 가격표는 바뀔 수 있으므로 견적서에 가격 기준일, Provider, Region, 처리 등급, Model과 통화를 기록합니다.

단가를 문서에 고정해 두기보다 계산 입력으로 분리하는 편이 안전합니다.

## 15. 평균 하나보다 실행 경로의 분포를 사용한다

모든 요청이 같은 Token과 Tool 수를 사용하지 않습니다.

| 실행 경로 | 예시 | 비용 특성 |
|---|---|---|
| 단순 (Simple) | 짧은 질문, 검색 1회 | 낮은 Context·호출 수 |
| 일반 (Standard) | 검색·근거·구조화 출력 | 대표 경로 |
| 복합 (Complex) | 여러 Source·Tool·단계 | 긴 Context·다중 호출 |
| 실패 (Failure) | Timeout·재시도·Fallback | 결과 없이 비용 발생 |
| 평가 (Evaluation) | 후보 여러 개와 Judge | 운영 외 추가 호출 |

월간 비용은 실행 경로 비중을 사용해 계산합니다.

```text
월간 사용량 비용
= 월간 업무 건수
× Σ(실행 경로 비중 × 경로당 평균 비용)
```

평균뿐 아니라 p95 입력 크기, 출력 길이, Tool 호출 수와 지연도 확인합니다.

최대 Context만 모든 요청에 적용하면 과대 추정할 수 있고, 짧은 대표 질문만 사용하면 긴 문서와 복합 업무 비용을 놓칠 수 있습니다.

## 16. 실패와 평가 Traffic을 별도로 계산한다

성공 요청만 계산하면 실제 비용이 낮게 보입니다.

다음 호출도 비용을 만듭니다.

- Timeout 후 재시도
- Rate Limit 후 Backoff
- Provider 장애 시 Fallback
- 출력 Schema 실패 후 재생성
- 사용자의 재생성 요청
- 정기 품질 평가
- 배포 전 회귀 평가
- Shadow Traffic (사용자에게 보이지 않는 병렬 검증)
- 공격·Red Team 시험

```text
실효 호출 배수
= 1
+ 재시도율 × 평균 추가 호출 수
+ Fallback 비율 × 평균 대체 호출 수
+ 평가 Traffic 비율
```

재시도가 중복 업무 처리나 비용 폭주로 이어지지 않도록 Budget과 Idempotency도 함께 설계합니다.

## 17. Fixed Cost와 Variable Cost를 분리한다

월간 비용은 고정비와 변동비로 나눕니다.

| 유형 | 예시 |
|---|---|
| 고정 비용 (Fixed Cost) | 최소 Runtime, 운영 도구, 기본 지원, License |
| 단계 비용 (Step Cost) | 특정 용량 구간을 넘을 때 추가 Worker·Shard |
| 변동 비용 (Variable Cost) | Token, 음성 시간, Storage, 호출·전송량 |
| 사건 비용 (Event Cost) | 재인덱싱, Migration, 장애 대응, 대규모 평가 |

사용자가 0명이어도 발생하는 비용과 사용량에 비례하는 비용을 섞지 않습니다.

또한 Serverless, 예약 용량, 전용 Endpoint와 자체 GPU는 비용 구조가 다릅니다.

평균 사용량뿐 아니라 Peak (최대 부하), 동시성, Cold Start와 Quota를 함께 봅니다.

## 18. 세 가지 Scenario로 운영비를 제시한다

단일 월간 비용보다 Scenario (시나리오) 범위가 의사결정에 유용합니다.

```text
Low
  제한 Pilot, 낮은 사용량, 비동기 중심

Expected
  합의한 사용자와 대표 업무 분포

High
  높은 Adoption, 긴 입력, 복합 Tool, 재시도 증가
```

각 Scenario에서 바뀌는 입력을 명시합니다.

| Driver (비용 동인) | Low | Expected | High |
|---|---|---|---|
| 월간 업무 건수 | Fixture 입력 | Fixture 입력 | Fixture 입력 |
| 복합 경로 비율 | 낮음 | 기준 | 높음 |
| 입력 길이 | 짧음 | 관측 평균 | 상위 구간 |
| 재시도율 | 정상 | 기준 | 장애 포함 |
| 사람 검토율 | 제한 | 기준 | 품질 저하 포함 |
| 동시성 | Pilot | 운영 예상 | Peak |

High Scenario는 공포를 위한 숫자가 아니라 Budget, Quota와 Degradation Policy (기능 저하 정책)를 결정하는 입력입니다.

## 19. 가정 목록 (Assumption Register)이 견적의 핵심이다

정확한 견적보다 먼저 정확한 가정을 만듭니다.

```json
{
  "estimateId": "estimate-fixture-020",
  "asOfDate": "2026-07-29",
  "currency": "CONTRACT_CURRENCY",
  "scope": {
    "users": "pilot-user-group",
    "useCases": [
      "meeting-summary-review",
      "follow-up-action-candidate"
    ],
    "environments": [
      "development",
      "staging",
      "production"
    ]
  },
  "assumptions": [
    {
      "id": "A-01",
      "statement": "Source API와 Test Credential은 착수 시 제공된다.",
      "ownerRole": "Customer Integration Owner",
      "impactIfFalse": "통합 일정과 개발 노력을 재산정한다."
    },
    {
      "id": "A-02",
      "statement": "운영 데이터의 사용 목적과 보존 정책은 승인됐다.",
      "ownerRole": "Data Owner",
      "impactIfFalse": "데이터 작업을 중단하고 정책 확정 후 재개한다."
    }
  ],
  "exclusions": [
    "기존 원천 시스템의 신규 API 개발",
    "법률 의견서와 규제 인증",
    "24x7 운영 대응"
  ]
}
```

가정에는 Owner (책임자), 확인 기한과 틀렸을 때 영향을 연결합니다.

가정이 사실로 확인되면 위험이 줄고, 틀리면 범위·일정·가격을 재산정합니다.

## 20. Work Breakdown Structure로 견적을 재현한다

Work Breakdown Structure (작업 분해 구조, WBS)는 기능 목록을 실제 산출물과 작업으로 나눕니다.

| 작업 패키지 | 산출물 | 수량 Driver | 완료 증거 |
|---|---|---|---|
| Discovery | 범위·가정·위험·아키텍처 | 업무·시스템 수 | 승인된 설계 문서 |
| Data | 수집·정제·Index Pipeline | Source·형식·권한 | 재처리 시험 |
| AI Core | Prompt·RAG·Workflow | Use Case·경로 | Version별 평가 |
| Integration | 인증·API·Tool | Endpoint·환경 | 계약·E2E 시험 |
| UX | 검토·승인·실패 흐름 | 사용자 Role | 사용자 Scenario |
| Security | Threat Model·권한·감사 | 위험·데이터 등급 | 보안 시험 결과 |
| Evaluation | Dataset·Rubric·회귀 | 사례·Slice·Version | 평가 보고서 |
| Platform | Runtime·Queue·Storage | SLO·용량·환경 | 부하·복구 시험 |
| Observability | Trace·Metric·Cost | Service·신호 | Dashboard·Alert |
| Handover | Runbook·교육·인수 | 운영 Role·절차 | 인수 기록 |

“AI 기능 개발 1식”처럼 묶으면 무엇이 빠졌는지, 변경이 어디에 영향을 주는지 알기 어렵습니다.

## 21. Three-point Estimate로 불확실성을 보인다

정보가 부족한 작업을 하나의 확정 숫자로 표현하지 않습니다.

Three-point Estimate (3점 추정)는 다음 세 값을 사용합니다.

```text
Optimistic   위험이 거의 발생하지 않는 경우
Most Likely  현재 가정에서 가장 가능성 높은 경우
Pessimistic  확인된 주요 위험이 발생하는 경우
```

PERT에서 자주 사용하는 가중 예시는 다음과 같습니다.

```text
기대 노력
= (Optimistic + 4 × Most Likely + Pessimistic) ÷ 6
```

이 공식이 불확실성을 없애는 것은 아닙니다.

작업별 범위와 위험을 숨기지 않고 비교할 수 있게 만드는 보조 수단입니다.

특히 다음 항목은 Range (범위)로 제시하는 편이 안전합니다.

- 문서 품질과 변환 난이도
- 외부 API·권한 준비 상태
- 평가 결과에 따른 반복 횟수
- 성능·동시성 최적화
- 보안·규제 검토 결과

## 22. Contingency는 근거 없는 비율이 아니다

Contingency (예비비)는 “AI니까 일단 추가”하는 금액이 아닙니다.

Risk Register (위험 목록)에서 계산 근거를 가져옵니다.

```text
위험 노출값
= 발생 가능성
× 발생 시 추가 비용 또는 노력
```

```json
{
  "riskId": "R-01",
  "description": "운영 API가 Sandbox와 다른 비동기 계약을 사용한다.",
  "probability": "MEDIUM",
  "impact": "Integration 재설계와 E2E 재시험",
  "response": "운영 계약을 Discovery 단계에 검증한다.",
  "estimateTreatment": "별도 Range와 변경 조건으로 반영"
}
```

위험을 완화하면 예비비를 줄일 수 있습니다.

반대로 데이터와 API를 보지 못한 상태에서 고정가를 요구하면 공급자는 위험을 가격에 크게 포함하거나, 낮은 가격 뒤에 많은 제외 범위를 둘 수밖에 없습니다.

## 23. 고정가·시간재료·단계 계약을 상황에 맞게 선택한다

| 방식 | 적합한 상황 | 주의점 |
|---|---|---|
| 고정가 (Fixed Price) | 범위·데이터·API·인수 기준이 안정적 | 변경 조건이 명확해야 함 |
| 시간재료 (Time & Materials) | 탐색·실험과 우선순위 변경이 많음 | Budget Cap과 정기 Review 필요 |
| 단계 계약 (Phased Contract) | 불확실성이 크고 순차 검증 가능 | 단계별 Go·No-go 기준 필요 |
| 상한형 (Capped T&M) | 탐색은 필요하지만 최대 예산이 있음 | 상한 도달 시 범위 조정 규칙 필요 |

AI 프로젝트는 초기 Dataset과 평가 결과에 따라 반복 횟수가 달라질 수 있습니다.

이때 다음 구조가 유용합니다.

```text
1단계: Discovery 고정 범위
  → 데이터·API·위험 확인

2단계: PoC 또는 Technical Spike
  → 품질 가능성과 비용 Driver 측정

3단계: Pilot 구축
  → 실제 사용자·권한·운영 조건 검증

4단계: 운영 확대
  → 용량·SLO·지원 범위 확정
```

단계마다 중단 가능한 산출물을 만들면 전체 위험을 한 번에 계약하지 않아도 됩니다.

## 24. Change Request는 기능 개수만 세지 않는다

변경 영향은 화면 수가 아니라 경계를 따라 계산합니다.

```text
업무 규칙 변경
  → Prompt·Tool Schema
  → 평가 Dataset·Rubric
  → 권한 정책
  → API·UI
  → 회귀·보안·부하 시험
  → Runbook·교육
```

변경 요청에는 다음을 기록합니다.

- 변경 전·후 범위
- 요청 이유와 우선순위
- 영향받는 WBS와 산출물
- 데이터·보안·운영 영향
- 일정·비용·위험 변화
- 기존 범위에서 제거할 항목
- 승인자와 적용 Version

작은 문구 변경처럼 보여도 Structured Output, Tool 인자와 승인 정책을 바꾸면 전체 계약 시험이 필요할 수 있습니다.

## 25. Build와 Buy를 같은 요구사항으로 비교한다

관리형 AI 서비스는 개발 시간을 줄일 수 있지만 사용료, Lock-in, Region, 데이터 조건과 기능 제한을 가집니다.

직접 구축은 제어권을 높일 수 있지만 인프라, 보안, 업그레이드와 On-call 책임이 커집니다.

| 비교 항목 | Managed·Buy | Custom·Build |
|---|---|---|
| 초기 속도 | 빠를 수 있음 | 설계·개발 필요 |
| 기능 적합성 | 제품 기능 안에서 구성 | 업무에 맞게 구현 |
| 운영 책임 | 일부 공급자 담당 | 조직 책임 증가 |
| 단위 비용 | 사용량·제품 정책 의존 | 용량·운영 효율 의존 |
| 변경 통제 | Roadmap·제약 영향 | 직접 통제 가능 |
| 이전 비용 | Export·호환성 확인 | 자체 표준화 필요 |

같은 성공 기준, 데이터 조건, SLO와 보안 요구로 비교해야 합니다.

기능이 다른 두 대안을 월간 가격만으로 비교하면 의미가 없습니다.

## 26. “저렴한 Model”이 항상 저렴한 시스템은 아니다

Model 단가를 낮췄는데 전체 비용이 오를 수 있습니다.

```text
낮은 Model 단가
  → 품질 저하
    → 재생성 증가
      → 사람 검토 증가
        → 업무 완료 시간 증가
```

반대로 가장 비싼 Model을 모든 요청에 사용하는 것도 비효율적일 수 있습니다.

다음처럼 경로별 전략을 비교합니다.

- 간단한 분류·추출은 작은 Model
- 복합 추론은 강한 Model
- 반복 Prefix는 Cache 활용
- 지연 허용 작업은 Batch
- Retrieval로 필요한 Context만 제공
- 실패율이 높은 경로는 Prompt가 아니라 업무 흐름부터 개선

최적화 단위는 Token당 비용이 아니라 **성공한 업무 결과당 비용**입니다.

```text
성공한 업무 결과당 비용
= Model·Infrastructure·Operation·Human Review 전체 비용
÷ 인수 조건을 충족한 업무 결과 수
```

## 27. 견적서에 반드시 포함할 항목

좋은 견적서는 총액만 보여 주지 않습니다.

- 기준일과 유효 기간
- 목표·사용자·Use Case
- 포함 범위와 제외 범위
- WBS와 산출물
- 성공 기준과 인수 방법
- 데이터·API·환경 선행 조건
- 노력·License·Cloud·운영 비용 구분
- 사용량 Scenario와 비용 Driver
- 가정·의존성·위험
- 고객과 수행팀의 책임
- 일정과 의사결정 시한
- 변경 관리 절차
- 보증·유지보수·지원 범위
- 제3자 가격 변동 처리

다음 질문에 답할 수 있어야 합니다.

```text
무엇이 완료되면 인수하는가?
어떤 데이터와 API 제공을 전제로 하는가?
사용량이 두 배가 되면 무엇이 변하는가?
Model 가격이나 정책이 바뀌면 누가 부담하는가?
평가 미달 시 몇 번까지 개선하는가?
운영 장애와 신규 기능을 어떻게 구분하는가?
```

## 28. 자주 실패하는 견적 안티패턴

### 안티패턴 1: Token 단가만 계산한다

데이터, 통합, 평가, 보안과 운영 비용이 빠집니다.

### 안티패턴 2: “챗봇 1식”으로 견적한다

업무·권한·데이터·품질 수준이 보이지 않습니다.

### 안티패턴 3: PoC 비용을 운영 구축비로 사용한다

실제 사용자, SLO, 감사, 복구와 운영 인수가 빠집니다.

### 안티패턴 4: 사용량 평균 하나만 사용한다

복합 경로, Peak, 재시도와 평가 Traffic을 놓칩니다.

### 안티패턴 5: 사람 검토 비용을 제외한다

API 비용은 낮지만 업무 결과당 비용이 높아질 수 있습니다.

### 안티패턴 6: 가정과 제외 범위를 기록하지 않는다

같은 문장을 서로 다르게 해석해 변경 분쟁이 생깁니다.

### 안티패턴 7: 모든 불확실성을 고정가에 숨긴다

과도한 위험 Premium 또는 누락된 범위로 나타납니다.

### 안티패턴 8: 운영비를 Cloud 청구서로만 본다

재평가, Incident, 데이터 변경과 지원 인력이 빠집니다.

## 29. 사전 진단 체크리스트

### 업무·품질

- [ ] 대상 사용자와 성공한 업무 결과를 정의했는가?
- [ ] AI가 아닌 대안과 비교했는가?
- [ ] 인수 기준과 실패 시 조치를 합의했는가?
- [ ] 사람 검토가 필요한 범위와 시간을 측정했는가?

### 데이터·통합

- [ ] 실제 Source, 형식, 크기와 변경 빈도를 확인했는가?
- [ ] 접근 권한·보존·삭제 정책이 준비됐는가?
- [ ] 개발·검증·운영 API와 Credential 제공자를 정했는가?
- [ ] 외부 팀 의존성과 승인 Lead Time을 기록했는가?

### 기술·운영

- [ ] 단순·일반·복합·실패 실행 경로를 나눴는가?
- [ ] Model 외 Storage, Search, Queue, Network와 Tool 비용을 계산했는가?
- [ ] SLO, 동시성, Peak와 복구 요구를 확인했는가?
- [ ] 관측·Budget·Quota·비용 귀속 방법을 포함했는가?

### 계약·위험

- [ ] 포함·제외 범위와 가정 목록이 있는가?
- [ ] WBS별 산출물과 완료 증거가 있는가?
- [ ] 불확실한 작업을 Range와 Risk로 표시했는가?
- [ ] 변경 요청과 제3자 가격 변동 규칙이 있는가?
- [ ] 운영 인수·보증·유지보수 범위를 구분했는가?

## 마무리

AI 프로젝트 견적은 Model 가격표에 예상 Token을 곱하는 작업이 아닙니다.

다음 다섯 층을 함께 계산해야 합니다.

```text
Build
  설계·데이터·AI Core·통합·UX·시험

Run
  Model·음성·검색·Storage·Network·Tool

Operate
  관측·장애 대응·재평가·지원

Change
  업무·데이터·Model·Provider 변화

Risk
  미확정 API·데이터·규제·품질 위험
```

핵심 원칙은 다음과 같습니다.

1. 비용, 견적과 계약 가격을 구분합니다.
2. Model보다 업무·사용자·성공 기준을 먼저 정의합니다.
3. 구축·사용량·운영·변경·위험 비용을 분리합니다.
4. 열 개 WBS와 재현 가능한 산출물로 범위를 분해합니다.
5. 평균 호출이 아니라 실행 경로와 Low·Expected·High Scenario로 계산합니다.
6. 평가, 실패, 재시도, 사람 검토와 관측 비용을 포함합니다.
7. 가정·제외 범위·위험·변경 조건을 견적과 함께 관리합니다.
8. 최적화 단위를 Token이 아니라 성공한 업무 결과로 둡니다.

가장 신뢰할 수 있는 견적은 처음부터 가장 낮거나 정밀해 보이는 숫자가 아닙니다.

**현재 확인된 사실과 불확실성을 분리하고, 범위가 바뀔 때 비용이 어떻게 달라지는지 추적할 수 있는 견적**입니다.

다음 글에서는 MCP Server의 OAuth, Scope, Origin, SSRF와 Rate Limit을 운영 보안 체크리스트로 연결하는 방법을 살펴보겠습니다.

## 참고 자료

- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing)
- [Google Cloud: AI and ML Perspective — Cost Optimization](https://docs.cloud.google.com/architecture/framework/perspectives/ai-ml/cost-optimization)
- [Google Cloud: MLOps Continuous Delivery and Automation Pipelines](https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)
- [AWS Well-Architected Machine Learning Lens: Cost Optimization](https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/cost-optimization.html)
- [Azure Well-Architected Framework: Create and Maintain a Cost Model](https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/cost-model)
- [Azure Well-Architected Framework: Cost Optimization Design Principles](https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/principles)
- [NIST AI Risk Management Framework 1.0](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10)
- [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- [NIST AI 600-1: Generative Artificial Intelligence Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- [Google SRE Workbook: Implementing SLOs](https://sre.google/workbook/implementing-slos/)

---

> 이 글은 2026년 7월 29일 기준 OpenAI, Google Cloud, AWS, Microsoft Azure, NIST와 Google SRE의 공식 공개 문서 및 공개 가능한 엔터프라이즈 AI 프로젝트 산정 경험을 바탕으로 작성했습니다. 예시 ID, Scenario, 계약 구조, 계산식과 날짜는 설명용 Fixture이며 실제 견적은 최신 Provider 가격, 통화, 세금, 계약 조건, 업무 범위, 데이터 상태, 품질·보안·SLO와 운영 책임을 확인해 별도로 산정해야 합니다.
