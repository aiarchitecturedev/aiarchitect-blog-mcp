# 기업 AI Agent 변경 승인 자동화 설계: Risk Tier·Evidence Gate·Exception·Rollback 계약

AI Agent의 Prompt 한 줄을 바꾸는 일은 코드 배포처럼 보이지만 승인 절차는 그대로 적용되지 않습니다. 검증 결과가 좋다는 사실과 지금 이 변경을 배포해도 된다는 결정은 서로 다른 판단이고, 모든 변경에 같은 승인 단계를 요구하면 사람이 형식적으로 승인하기 시작합니다. 이 글은 변경을 불변 Change Set으로 고정하고 Risk Tier별 Evidence Gate, 자동·사람 승인, 기한부 예외, 단계적 배포와 Rollback 계약으로 연결하는 설계를 정리합니다.

![기업 AI Agent의 불변 Change Set이 Risk Tier와 Evidence Gate를 거쳐 자동·사람 승인으로 분기되고 단계적 배포 또는 Rollback으로 연결되는 변경 승인 자동화 아키텍처](assets/blog-93-ai-agent-change-approval-evidence-gate-hero.png)

<blockquote id="aiarchitect-toc" data-ke-style="box" style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;" data-mce-style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;">
<p style="color: #263746; font-weight: 700;" data-mce-style="color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 700;"><b>목차</b></p>
<ol style="list-style-type: decimal; color: #555555; font-weight: 400;" data-mce-style="list-style-type: decimal; color: #555555; font-weight: 400;" data-ke-list-type="decimal">
<li><a href="#ai-section-1" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">검증 통과와 변경 승인은 같은 판정이 아니다</a></li>
<li><a href="#ai-section-2" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">BLOG-91·92의 결과를 승인 입력으로 연결한다</a></li>
<li><a href="#ai-section-3" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">변경부터 Rollback까지 하나의 결정 흐름으로 만든다</a></li>
<li><a href="#ai-section-4" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Change Set을 불변 Subject로 고정한다</a></li>
<li><a href="#ai-section-5" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">변경 승인과 배포 Promotion을 분리한다</a></li>
<li><a href="#ai-section-6" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Risk Tier는 파일 종류가 아니라 업무 피해로 정한다</a></li>
<li><a href="#ai-section-7" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Impact·Likelihood·Exposure·Authority·Reversibility로 위험을 설명한다</a></li>
<li><a href="#ai-section-8" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Evidence Profile을 Tier별 계약으로 정의한다</a></li>
<li><a href="#ai-section-9" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">판정 입력을 하나의 Decision Snapshot으로 동결한다</a></li>
<li><a href="#ai-section-10" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Gate Result와 Approval Decision을 분리한다</a></li>
<li><a href="#ai-section-11" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Blocking Rule은 평균 점수로 상쇄하지 않는다</a></li>
<li><a href="#ai-section-12" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">자동 승인은 좁고 관찰 가능한 범위에만 허용한다</a></li>
<li><a href="#ai-section-13" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">사람 승인은 증거의 공백을 대신 채우지 않는다</a></li>
<li><a href="#ai-section-14" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">업무 분리와 이중 승인을 위험에 맞게 적용한다</a></li>
<li><a href="#ai-section-15" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Decision Record를 Artifact Digest에 바인딩한다</a></li>
<li><a href="#ai-section-16" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">승인에는 유효기간과 철회 조건이 필요하다</a></li>
<li><a href="#ai-section-17" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Exception은 영구 우회가 아니라 기한부 위험 수용이다</a></li>
<li><a href="#ai-section-18" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">긴급 변경은 통제를 생략하지 않고 순서를 바꾼다</a></li>
<li><a href="#ai-section-19" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Promotion Contract로 단계별 노출을 제한한다</a></li>
<li><a href="#ai-section-20" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">관찰 구간의 사후조건을 다음 승인의 증거로 만든다</a></li>
<li><a href="#ai-section-21" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Rollback은 실행 가능성과 업무 복구를 함께 계약한다</a></li>
<li><a href="#ai-section-22" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">승인 명령의 재전송과 경합을 멱등 계약으로 흡수한다</a></li>
<li><a href="#ai-section-23" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">운영 사고는 기존 승인을 즉시 재평가하게 한다</a></li>
<li><a href="#ai-section-24" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">합성 사례로 Prompt·Tool 변경 승인을 계산한다</a></li>
<li><a href="#ai-section-25" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">실패하기 쉬운 변경 승인 안티패턴을 피한다</a></li>
<li><a href="#ai-section-26" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">다섯 단계로 도입하고 결정 품질을 측정한다</a></li>
<li><a href="#ai-section-27" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">공식 참고자료</a></li>
</ol>
</blockquote>

AI Agent의 Prompt 회귀 평가가 통과했고, Tool Contract Test도 성공했으며, Red Team의 Critical Finding은 없습니다. 그렇다면 운영 배포를 자동 승인해도 될까요?

아직은 알 수 없습니다. 그 증거가 **현재 변경 대상과 정확히 결합됐는지**, 변경이 노출되는 Tenant와 권한 범위가 무엇인지, 실패했을 때 되돌릴 수 있는지, 남은 위험을 누가 어떤 기간 동안 수용하는지까지 확인해야 합니다. 평가 결과는 승인 판단의 입력이지 승인 자체가 아닙니다.

기업 AI Agent의 변경 승인은 단순한 CI 성공 조건보다 넓습니다. Model Route, Prompt, Tool Schema, 권한, Knowledge Snapshot, Runtime Policy 가운데 하나만 바뀌어도 Agent가 선택하는 행동과 실제 Side Effect가 달라질 수 있습니다. 반대로 문구 수정처럼 영향이 제한된 변경까지 매번 위원회에 올리면 승인 대기열이 길어지고, 운영팀은 통제를 우회하기 시작합니다.

증거가 갖춰졌고([BLOG-91](https://aiarchitect.tistory.com/91)), 그 증거가 아직 살아 있다는 것까지 확인했다면([BLOG-92](https://aiarchitect.tistory.com/92)), 남은 질문은 하나입니다. **그래서 이 변경을 지금 내보낼 것인가.** 이 글은 배포 여부와 범위를 정하는 그 판정을 담당자의 임의적 재량에만 맡기지 않고 계약으로 만듭니다. Change Set을 불변 단위로 고정하고, Risk Tier마다 요구 증거를 미리 정해 두고, 자동 승인·사람 승인·기한부 예외·단계적 배포·Rollback을 하나의 결정 흐름으로 묶습니다.

이 글의 회사, Agent, 수치, Digest, Policy와 승인 기록은 모두 교육용 합성 예시입니다. `TIER-1`부터 `TIER-4`, `PASS`, `HOLD`, `APPROVED_WITH_EXCEPTION` 같은 이름은 이 글이 제안하는 구현 모델이며 NIST, ISO, W3C, in-toto 또는 SLSA가 정한 공통 열거형이 아닙니다. 이 글의 4단계 Tier는 출발점일 뿐입니다. 실제 Tier 경계와 승인 권한은 그 변경이 잘못됐을 때의 업무 피해와 복구 가능성을 먼저 보고, 조직이 따르는 보안·개인정보·법무 정책과 산업 규제·계약, 그리고 실제 운영 데이터를 함께 반영해 정해야 합니다.

<a id="ai-section-1"></a>

## 1. 검증 통과와 변경 승인은 같은 판정이 아니다

검증은 “정한 시험 조건에서 관찰한 결과가 기준을 만족했는가”를 묻습니다. 승인은 “남은 불확실성과 잔여 위험을 고려해 이 변경을 이 범위에 노출해도 되는가”를 묻습니다. 두 질문은 입력과 책임자가 다릅니다.

```text
Evaluation Result  = 특정 Dataset·Evaluator·Context에서 관찰한 결과
Gate Result        = 필수 Evidence와 Policy 조건의 충족 여부
Approval Decision  = 특정 Subject·Scope·기간에 대한 위험 수용 결정
Promotion Decision = 다음 노출 단계로 이동할지에 대한 운영 결정
```

예를 들어 정확도와 안전성 평가는 모두 통과했어도 Rollback이 검증되지 않은 파괴적 Tool 변경은 승인할 수 없습니다. 반대로 낮은 위험의 내부 검색 Prompt 변경은 자동화된 회귀 평가와 좁은 Canary 조건만으로 승인할 수 있습니다. 핵심은 시험 개수를 늘리는 것이 아니라 **변경 위험과 필요한 증거, 승인 권한, 배포 범위를 같은 계약으로 묶는 것**입니다.

NIST AI RMF 1.0은 위험 수준과 조직의 Risk Tolerance에 따라 관리 활동의 강도를 정하고, 의도한 목적 달성 여부와 개발·배포 진행 여부를 판단하도록 안내합니다. 변경 승인 자동화는 이 원칙을 Release Pipeline에서 실행 가능한 규칙으로 옮기는 작업입니다.

<a id="ai-section-2"></a>

## 2. BLOG-91·92의 결과를 승인 입력으로 연결한다

BLOG-93은 기존 평가와 거버넌스 기능을 다시 만들지 않습니다. 앞선 글이 생산한 산출물을 승인 결정의 입력으로 연결합니다.

| 연결 글 | 이미 확보한 산출물 | BLOG-93에서 사용하는 방식 |
|---|---|---|
| [AI Agent 승인 정책](https://aiarchitect.tistory.com/16) | 행동 위험 등급·사람 승인·실행 권한 | 변경 후 Agent가 행사할 수 있는 Authority 계산 |
| [기업 AI Agent 도입 로드맵](https://aiarchitect.tistory.com/65) | PoC·Pilot·운영 전환 단계 | 승인 Scope와 Stage 경계 정의 |
| [AI Agent 도입 준비도 진단](https://aiarchitect.tistory.com/69) | 데이터·API·권한·보안·인수 기준 | Evidence Profile의 조직 준비도 조건 |
| [AI Agent 적합도 판정](https://aiarchitect.tistory.com/70) | 업무 영향·가역성·예외 구조 | Risk Tier 입력과 자동화 상한 |
| [AI Agent 평가 아키텍처](https://aiarchitect.tistory.com/74) | Dataset·Evaluator·Regression Gate | 품질·안전 Evidence와 Blocking Rule |
| [AI Agent Release Governance](https://aiarchitect.tistory.com/87) | Release Bundle·Canary·Rollback | Promotion Contract와 Release Ledger |
| [Red Teaming과 Continuous Assurance](https://aiarchitect.tistory.com/90) | Attack Evidence·Finding·Runtime Signal | Critical Finding 차단과 운영 중 승인 철회 |
| [Assurance Case와 Evidence Graph](https://aiarchitect.tistory.com/91) | Claim·Argument·Evidence·Decision | 승인 논리와 Decision Provenance |
| [Evidence Lifecycle과 Revalidation](https://aiarchitect.tistory.com/92) | Freshness·Invalidation·최소 재검증 | 현재 유효한 Evidence Set과 Coverage Gap |

경계는 명확해야 합니다. BLOG-92의 Revalidation Engine은 어떤 증거가 낡았고 무엇을 다시 시험할지 계산합니다. BLOG-93의 Decision Engine은 재검증 결과를 포함한 현재 Evidence Set을 받아 **어떤 승인 경로와 배포 범위를 허용할지** 결정합니다.

<a id="ai-section-3"></a>

## 3. 변경부터 Rollback까지 하나의 결정 흐름으로 만든다

권장 흐름은 다음과 같습니다.

```text
Change Request
  → immutable Change Set
  → Impact Summary
  → Inherent Risk Tier
  → required Evidence Profile
  → Evidence Gate
  → Residual Risk
  → Approval Decision
  → signed Decision Record
  → staged Promotion
  → Observation Evidence
  → Retain / Hold / Rollback
```

<img src="assets/blog-93-change-approval-decision-pipeline.png" alt="기업 AI Agent의 Change Request가 불변 Change Set과 영향 분석, Inherent Risk Tier, Evidence Profile과 Gate를 거쳐 자동 승인, 사람 승인 또는 기한부 Risk Acceptance로 분기되고 서명된 Decision, 단계적 Promotion과 관찰 후 유지 또는 Rollback으로 이어지는 변경 승인 결정 파이프라인" width="660" />

각 화살표는 단순한 화면 전환이 아니라 입출력 계약입니다. 예를 들어 Risk Classifier는 `TIER-3`이라는 숫자만 반환하면 안 됩니다. 어떤 업무 피해와 권한 변화, 노출 범위, 비가역성이 그 결과를 만들었는지 Reason Code와 근거를 함께 반환해야 합니다.

결정 흐름에는 두 가지 폐쇄 루프가 있습니다.

1. **변경 전 루프**: 영향 분석과 Evidence Gate로 배포 자격을 판단합니다.
2. **변경 후 루프**: Canary 관찰 결과로 다음 Promotion 또는 Rollback을 판단합니다.

변경 전 시험이 운영의 모든 상호작용을 재현하지 못하므로 두 루프를 모두 가져야 합니다. 다만 “운영에서 보자”는 이유로 Critical Precondition을 Canary에 미루면 안 됩니다.

<a id="ai-section-4"></a>

## 4. Change Set을 불변 Subject로 고정한다

승인 대상은 Ticket 번호나 `release-candidate` 별칭이 아니라, 실제 배포할 Artifact 집합이어야 합니다.

```yaml
change_set:
  id: CHG-20260820-0041
  manifest_schema: change-set/v3
  canonicalization: canonical-json/v1
  digest: sha256:93a2...
  base_release_digest: sha256:81d0...
  candidate_release_digest: sha256:c719...
  components:
    prompt_bundle: sha256:11bc...
    model_route: sha256:79f4...
    tool_contract: sha256:206d...
    knowledge_snapshot: sha256:a510...
    policy_bundle: sha256:bf90...
    runtime_profile: sha256:ca80...
  requested_scope:
    environment: production
    tenant_cohort: kr-internal-pilot
    traffic_percent: 1
  requester: team://meeting-agent
  created_at: 2026-08-20T01:10:00Z
```

`digest`를 재현하려면 구성요소 목록뿐 아니라 Manifest Schema와 Canonicalization 규칙도 고정해야 합니다. 같은 논리 객체가 YAML Key 순서나 공백 차이 때문에 다른 Digest를 만들지 않도록, 조직이 정한 정규 직렬화 결과를 Hash 입력으로 사용합니다.

Change Set이 승인 후 수정되면 기존 Decision은 재사용할 수 없습니다. 구성요소 하나라도 Digest가 달라지는 순간 새로운 Subject입니다. 공급자 Model처럼 Weight Digest를 알 수 없다면 Provider, Model ID, Snapshot 또는 Version, Region, 주요 Parameter와 Routing Policy 등 실제 관찰 가능한 식별자를 기록합니다.

in-toto Attestation과 SLSA의 `subject`·Digest 결합은 Artifact와 Provenance가 다른 대상에 대체되는 것을 막는 데 유용한 패턴입니다. AI Agent에서는 Container뿐 아니라 Prompt·Tool·Policy·Knowledge와 운영 Profile까지 같은 Change Set에 묶어야 승인 대상을 재현할 수 있습니다.

<a id="ai-section-5"></a>

## 5. 변경 승인과 배포 Promotion을 분리한다

`APPROVED`를 곧바로 “전면 배포 완료”로 해석하면 승인 범위가 무제한으로 커집니다. 최소한 다음 결정을 분리합니다.

| 결정 | 질문 | 예시 결과 |
|---|---|---|
| Change Acceptance | 이 변경은 검토와 시험을 시작할 자격이 있는가 | ACCEPTED·REJECTED |
| Release Approval | 이 Candidate를 정한 초기 Scope에 배포해도 되는가 | APPROVED·APPROVED_CONDITIONAL·APPROVED_WITH_EXCEPTION·HOLD·REJECTED |
| Promotion Approval | 관찰 결과를 근거로 다음 Scope로 확대해도 되는가 | PROMOTE·RETAIN·ROLLBACK |
| Risk Acceptance | 특정 미충족 조건을 제한된 기간과 범위에서 수용하는가 | RISK_ACCEPTED·RISK_REJECTED |

예를 들어 Release Approval의 Scope가 `내부 Pilot 1%`라면 이를 근거로 전 고객 100% 배포를 할 수 없습니다. 5%, 25%, 100%는 각각 독립된 Promotion Decision이 필요합니다. 앞 단계의 관찰 Evidence가 다음 단계의 입력이 됩니다.

이 분리는 [BLOG-87 Release Governance](https://aiarchitect.tistory.com/87)의 Progressive Delivery를 승인 모델과 결합합니다. 배포 도구가 Traffic만 늘리는 것이 아니라, 정확한 Decision ID와 허용된 Scope를 확인한 뒤 다음 단계로 이동하게 합니다.

<a id="ai-section-6"></a>

## 6. Risk Tier는 파일 종류가 아니라 업무 피해로 정한다

`Prompt 변경은 낮은 위험`, `Model 변경은 높은 위험`처럼 파일 종류만으로 분류하면 실제 위험을 놓칩니다. 한 문장의 Prompt 수정이 결제 Tool 호출 조건을 바꿀 수 있고, Model Patch가 응답 형식에 영향을 주지 않을 수도 있습니다.

먼저 이 변경으로 가능한 업무 피해를 정의합니다.

| Tier 예 | 가능한 업무 영향 | 기본 승인 경로 |
|---|---|---|
| TIER-1 | 내부 표현·비기능 변경, Side Effect 없음 | 정책 조건 충족 시 자동 승인 |
| TIER-2 | 제한된 내부 영향, 읽기 또는 즉시 복구 가능한 Draft 쓰기 | 자동 승인 + Canary 또는 단일 사람 승인 |
| TIER-3 | 외부 전송·영구 쓰기·민감정보 또는 높은 업무 영향 | 독립 검토 + 사람 승인 + 단계적 배포 |
| TIER-4 | 안전·법적 권리·대규모 재무·파괴적 작업 영향 | 다중 승인, 엄격한 증거, 자동 승인 금지 |

Tier는 Agent 전체에 영구 부착되는 Label이 아닙니다. **특정 Change Set과 요청된 Scope의 조합**에 대한 판정입니다. 같은 Agent라도 내부 Shadow는 TIER-2, 외부 고객 100% Promotion은 TIER-3가 될 수 있습니다.

Inherent Risk Tier를 낮추려면 위험을 말로 축소하지 말고 요청 Scope를 실제로 줄여야 합니다. 예를 들어 외부 쓰기 Tool을 Scope에서 제외하고 Synthetic Data와 내부 Cohort 1%로 제한하면 Inherent Risk를 다시 계산할 수 있습니다. 반면 Kill Switch와 Rollback은 원래 위험을 없애는 것이 아니라 탐지·중지·복구 능력으로 Residual Risk를 낮추는 통제입니다.

<a id="ai-section-7"></a>

## 7. Impact·Likelihood·Exposure·Authority·Reversibility로 위험을 설명한다

숫자 하나만 저장하지 말고 최소 다섯 축을 보존합니다.

```text
Impact        실패했을 때 사람·조직·자산에 미치는 피해
Likelihood    현재 변경과 Context에서 실패가 발생할 가능성과 불확실성
Exposure      영향을 받을 사용자·Tenant·요청량·데이터 범위
Authority     Agent가 읽기·쓰기·전송·승인·삭제할 수 있는 권한
Reversibility 결과와 Side Effect를 탐지·중지·복구할 수 있는 정도
```

여기에 데이터 민감도, 변경 Novelty, 공급자 의존성, 탐지 지연을 보조 축으로 추가할 수 있습니다. 중요한 것은 단순 합산 점수보다 **상한 규칙**입니다.

```yaml
risk_classification:
  impact: high
  likelihood: possible
  evidence_uncertainty: medium
  exposure: limited
  authority: write-external
  reversibility: partial
  data_classification: confidential
  novelty: tool-contract-changed
  derived_tier: TIER-3
  floor_reasons:
    - EXTERNAL_SIDE_EFFECT
    - PARTIAL_REVERSIBILITY
```

예를 들어 `Authority=delete` 또는 `Impact=severe`이면 다른 축의 점수가 낮아도 최소 TIER-3로 올리는 식입니다. 평균값만 사용하면 높은 피해 가능성이 좁은 Exposure 점수에 상쇄될 수 있습니다.

이 단계에서 정하는 것은 통제 적용 전의 `Inherent Change Risk Tier`입니다. 이 Tier가 필요한 Evidence Profile과 승인 독립성의 하한을 선택합니다. Evidence Gate가 통제 효과와 실패 가능성을 확인한 뒤에는 미완화 위험을 `Residual Risk`로 다시 계산합니다. 최종 Approval Decision이 수용하는 대상은 Inherent Risk가 아니라 특정 Scope·기간에 남은 Residual Risk입니다.

[BLOG-70 AI Agent 적합도 판정](https://aiarchitect.tistory.com/70)의 가역성과 예외 구조, [BLOG-16 승인 정책](https://aiarchitect.tistory.com/16)의 행동 위험 등급을 이 분류기의 입력으로 재사용할 수 있습니다.

<a id="ai-section-8"></a>

## 8. Evidence Profile을 Tier별 계약으로 정의한다

Risk Tier가 정해지면 필요한 Evidence를 사람의 기억이 아니라 Versioned Profile에서 선택합니다.

| Evidence 범주 | TIER-1 | TIER-2 | TIER-3 | TIER-4 |
|---|---:|---:|---:|---:|
| Artifact Digest·Provenance | 필수 | 필수 | 필수 | 필수 |
| Schema·Contract Test | 해당 시 | 필수 | 필수 | 필수 |
| Regression Evaluation | 핵심 Slice | 확대 Slice | 전체 Critical Slice | 독립 재현 포함 |
| Security·Privacy Test | 기본 검사 | 변경 영향 검사 | 위협 기반 시험 | 독립 심층 검토 |
| Red Team Finding Closure | 해당 시 | High 이상 | High·Critical | 모든 지정 Scenario |
| Rollback Rehearsal | 선언 | 검증 | 필수 | 대체 복구 경로 포함 |
| Human Approval | 선택 | 정책 기반 | 필수 | 다중·독립 승인 |
| Observation Window | 짧음 | 필수 | 확대 | 보수적·단계별 |

<img src="assets/blog-93-risk-tier-approval-boundary.png" alt="Impact·Likelihood·Exposure·Authority·Reversibility로 분류한 TIER-1부터 TIER-4까지의 변경 위험이 각기 다른 Evidence 요구와 자동 승인, 조건부 승인, 독립 사람 승인, 다중 승인 경계로 연결되는 구조" width="600" />

Profile에는 Evidence Type만 적지 않습니다. Issuer 신뢰, Subject 일치, Freshness, Coverage, Threshold, 허용되는 재사용 조건, 실패 시 Blocking 여부를 함께 둡니다.

```yaml
evidence_profile:
  id: EPROF-TOOL-WRITE-T3-v4
  applies_when:
    minimum_tier: TIER-3
    change_kinds: [prompt, tool-contract, policy]
  requirements:
    - claim: CLM-TOOL-AUTHZ-01
      predicate_type: tool-authorization-conformance/v3
      trusted_issuers: [spiffe://assurance/evaluator/tool-authz]
      freshness: PT72H
      required_slices: [external-write, denied-scope, replay]
      blocking: true
    - claim: CLM-ROLLBACK-01
      predicate_type: rollback-rehearsal/v2
      freshness: P30D
      blocking: true
  approval_policy: AP-T3-v6
```

Profile이 바뀌면 Version을 올립니다. 과거 Decision은 당시 어떤 규칙으로 승인됐는지 재현할 수 있어야 합니다.

<a id="ai-section-9"></a>

## 9. 판정 입력을 하나의 Decision Snapshot으로 동결한다

Gate가 실행되는 동안 Evidence가 갱신되거나 Policy가 바뀌면 같은 요청이 서로 다른 결과를 만들 수 있습니다. 판정 시작 시 입력의 Version과 Digest를 동결합니다.

```yaml
decision_snapshot:
  id: DS-20260820-0041-02
  change_set_digest: sha256:93a2...
  impact_summary_digest: sha256:7731...
  risk_classifier_version: RC-v5
  inherent_risk_tier: TIER-3
  evidence_profile_digest: sha256:3b20...
  policy_bundle_digest: sha256:bf90...
  evidence_manifest_digest: sha256:5d71...
  requested_scope_digest: sha256:d611...
  evaluated_at: 2026-08-20T02:05:00Z
```

Snapshot 안의 Evidence는 [BLOG-92 Evidence Lifecycle](https://aiarchitect.tistory.com/92)이 `ACTIVE`로 판정한 현재 Set이어야 합니다. 다만 `ACTIVE`라는 상태만 믿지 말고 Subject·Context·Coverage가 현재 Claim과 일치하는지 Gate에서 다시 확인합니다.

평가 도중 새 Critical Finding이 들어오면 조용히 무시하지 않습니다. 현재 Snapshot을 `SUPERSEDED` 또는 `ABORTED`로 닫고 새 Snapshot에서 재판정합니다. 이는 결정을 느리게 만드는 중복이 아니라 서로 다른 시점의 사실을 섞지 않는 일관성 장치입니다.

<a id="ai-section-10"></a>

## 10. Gate Result와 Approval Decision을 분리한다

Gate는 요구 조건을 기계적으로 평가합니다. Approval은 Gate Result와 조직의 Risk Tolerance를 바탕으로 권한 있는 주체가 내리는 결정입니다.

```text
Gate Result
  PASS          모든 Blocking 조건 충족
  PASS_WITH_GAP Blocking 조건은 충족했지만 목표값 경고 또는 추가 관찰 필요
  EXCEPTION_REQUIRED 조직이 예외를 허용한 Requirement 미충족
  INCONCLUSIVE  표본·신뢰도·데이터 부족
  FAIL          하나 이상의 Blocking 조건 실패
  ERROR         판정 인프라 또는 입력 무결성 오류

Approval Decision
  APPROVED               요청 Scope 승인
  APPROVED_CONDITIONAL   더 좁은 Scope·추가 관찰 조건으로 승인
  APPROVED_WITH_EXCEPTION 명시적 기한부 위험 수용으로 승인
  HOLD                   보완 전까지 보류
  REJECTED               현재 Change Set 승인 거부
```

`Gate=PASS`라고 자동으로 `Decision=APPROVED`가 되는 것은 아닙니다. 예를 들어 TIER-4는 PASS여도 다중 사람 승인이 필요할 수 있습니다. `PASS_WITH_GAP`은 모든 Blocking 조건을 충족했지만 경고 구간이나 추가 관찰이 필요한 상태이므로 `APPROVED_CONDITIONAL`로 연결할 수 있습니다. Requirement 자체가 미충족됐지만 Policy가 예외를 허용한다면 `EXCEPTION_REQUIRED`로 분리합니다.

`APPROVED_CONDITIONAL`은 모든 Blocking Gate가 통과한 상태에서 더 좁은 Scope, 추가 관찰 또는 Capability 제한을 붙이는 결정입니다. `APPROVED_WITH_EXCEPTION`은 `EXCEPTION_REQUIRED`인 Requirement에 대해 별도의 `RISK_ACCEPTED` Record로 잔여 위험을 기한부 수용한 경우에만 사용합니다. 두 상태를 같은 의미로 섞지 않습니다.

`INCONCLUSIVE`와 `ERROR`를 실패가 아닌 통과로 처리해서는 안 됩니다. Evidence가 부족하거나 평가기가 고장 난 상태는 안전하다는 증거가 아닙니다. 기본 정책은 `HOLD`이며, 예외 승인을 허용하려면 별도의 Risk Acceptance 계약이 필요합니다.

<a id="ai-section-11"></a>

## 11. Blocking Rule은 평균 점수로 상쇄하지 않는다

AI Agent 평가에서는 좋은 평균이 위험한 Slice를 숨길 수 있습니다. 승인 Gate는 Threshold와 불변조건을 분리해야 합니다.

```yaml
gate_rules:
  invariants:
    - id: NO_UNAUTHORIZED_EXTERNAL_WRITE
      condition: unauthorized_external_write_count == 0
      blocking: true
    - id: NO_OPEN_CRITICAL_FINDING
      condition: open_critical_findings == 0
      blocking: true
    - id: SUBJECT_DIGEST_MATCH
      condition: evidence.subject == change_set.subject
      blocking: true
  thresholds:
    - id: TASK_SUCCESS_RATE
      condition: lower_confidence_bound >= 0.97
      blocking: true
    - id: P95_LATENCY_DELTA
      target: candidate_delta <= 0.05
      hard_limit: candidate_delta <= 0.10
      on_target_miss: PASS_WITH_GAP
      blocking: false
```

`unauthorized_external_write_count=1`을 높은 Task Success Rate로 상쇄할 수 없습니다. 보안, 개인정보, 권한, 파괴적 Side Effect, Critical Finding 같은 항목은 평균 점수와 별도의 불변조건으로 둡니다.

또한 Candidate 절대값뿐 아니라 Baseline 대비 변화, 표본 수, 신뢰 구간, Critical Slice별 최저값을 봅니다. 자세한 평가 구조는 [BLOG-74 AI Agent 평가 아키텍처](https://aiarchitect.tistory.com/74)에서 다룹니다.

<a id="ai-section-12"></a>

## 12. 자동 승인은 좁고 관찰 가능한 범위에만 허용한다

자동 승인의 목적은 사람을 없애는 것이 아니라 **반복 가능하고 낮은 위험의 판정을 일관되게 처리하는 것**입니다. 다음 조건을 모두 만족하는 범위부터 시작합니다.

1. Risk Tier가 조직의 자동 승인 상한 이하여야 합니다.
2. 모든 Blocking Evidence가 현재 Subject와 Context에 대해 유효해야 합니다.
3. Critical 또는 High 미해결 Finding이 없어야 합니다.
4. Requested Scope가 정책의 자동 승인 한도 안에 있어야 합니다.
5. 관찰 가능성, Kill Switch, Rollback 또는 안전한 Forward Fix가 검증돼야 합니다.
6. 요청자와 Policy·Evidence Producer의 신원이 검증돼야 합니다.
7. 동일 Change Set에 해결되지 않은 거부·철회·사고 기록이 없어야 합니다.

예시 Policy는 다음처럼 명시적이어야 합니다.

```text
IF tier <= TIER-2
AND gate_result == PASS
AND requested_scope.traffic_percent <= 1
AND authority NOT IN [external_write, delete, financial_commit]
AND rollback_rehearsal == PASS
AND open_high_findings == 0
THEN APPROVED_CONDITIONAL for internal-pilot / 24h
ELSE route_to_human_or_hold
```

자동 승인 Policy 자체도 Version·검토자·유효기간·변경 이력을 가진 통제 대상입니다. Rule을 바꾼 사람이 자신의 변경을 즉시 그 새 Rule로 승인할 수 없도록 업무 분리를 적용합니다.

<a id="ai-section-13"></a>

## 13. 사람 승인은 증거의 공백을 대신 채우지 않는다

사람 승인이 필요한 이유는 모든 판단을 자동화할 수 없기 때문입니다. 새로운 업무 피해, 모호한 법적·윤리적 영향, 잔여 위험 수용, 복구 불가능한 Side Effect처럼 조직 책임이 필요한 판단은 사람이 맡아야 합니다.

그러나 사람의 클릭은 Evidence 부족을 자동으로 해결하지 않습니다. 승인 화면에는 최소한 다음 정보가 보여야 합니다.

- 정확한 Change Set과 Baseline의 차이
- Risk Tier와 상향 Reason Code
- 충족·미충족·판정 불가 Gate 목록
- Evidence의 Subject·Issuer·Freshness·Coverage
- 요청된 사용자·Tenant·권한·Traffic Scope
- 남은 위험과 예상 업무 피해
- Rollback 가능 범위와 복구 한계
- 승인 유효기간과 철회 Trigger
- Exception이 있다면 보완 통제와 종료 조건

승인자가 원본 Evidence를 열어볼 수 있어야 하지만, 수십 개 파일을 읽어야만 핵심을 파악하는 UI도 실패입니다. Decision Summary에서 Claim → Rule → Evidence → 원본 Artifact로 내려갈 수 있게 설계합니다.

고위험 승인에서 LLM이 요약을 도울 수는 있지만, 최종 승인 책임자나 Policy Evaluator로 가장해서는 안 됩니다. 요약의 출처와 누락 가능성을 표시하고, 결정에 사용한 구조화 필드는 원본에서 검증합니다.

<a id="ai-section-14"></a>

## 14. 업무 분리와 이중 승인을 위험에 맞게 적용한다

모든 변경에 두 명의 서명을 요구하면 형식적인 승인만 늘어납니다. 반대로 요청자, 평가자, Policy 관리자, 승인자, 배포 실행자가 모두 같은 권한을 가지면 통제의 독립성이 사라집니다.

| 역할 | 허용 | 제한 |
|---|---|---|
| Change Author | Change Set 제출·설명 | 자신의 TIER-3 이상 최종 승인 금지 |
| Evidence Producer | 시험 실행·Attestation 발행 | 결과 수정·승인 결정 금지 |
| Policy Owner | Tier·Gate Rule 관리 | 새 Policy로 자신의 변경 즉시 승인 금지 |
| Risk Approver | 잔여 위험 수용·Scope 승인 | Artifact 교체·Evidence 재작성 금지 |
| Release Operator | 승인된 Scope 실행 | Decision Scope 초과 금지 |

TIER-1과 TIER-2는 자동화 또는 단일 승인, TIER-3는 독립 승인, TIER-4는 서로 다른 책임 영역의 다중 승인을 요구하는 식으로 강화할 수 있습니다. NIST SP 800-53의 Configuration Change Control은 변경 검토·승인·기록·감독과 영향 분석을 요구하며, 고위험 변경의 이중 승인 설계에 참고할 수 있습니다.

기계 Identity에도 같은 원칙을 적용합니다. Gate Service는 Evidence를 발행하지 않고, Deployment Controller는 임의 Decision을 만들 수 없으며, Policy Repository 변경은 서명된 Review를 거쳐야 합니다.

<a id="ai-section-15"></a>

## 15. Decision Record를 Artifact Digest에 바인딩한다

승인 화면의 최종 상태만 DB에 덮어쓰면 왜 승인했는지 재현할 수 없습니다. Decision은 Append-only Record로 남기고 이전 Decision을 수정하지 않습니다.

```yaml
decision:
  id: DEC-20260820-0041-03
  type: release-approval
  subject:
    change_set_digest: sha256:93a2...
    candidate_release_digest: sha256:c719...
  based_on:
    snapshot_digest: sha256:fe20...
    evidence_manifest_digest: sha256:5d71...
    policy_bundle_digest: sha256:bf90...
    risk_classifier_version: RC-v5
  residual_risk:
    assessment_digest: sha256:841c...
    level: medium
    unresolved_items: [P95_LATENCY_TARGET_MISS]
  result: APPROVED_CONDITIONAL
  authorized_scope:
    environment: production
    tenant_cohort: kr-internal-pilot
    traffic_percent_max: 1
    disabled_capabilities: [external_send]
  conditions:
    observation_window: PT6H
    minimum_requests: 5000
    next_action: promotion-review
  valid_from: 2026-08-20T02:30:00Z
  valid_until: 2026-08-21T02:30:00Z
  approvers:
    - identity: user://risk-owner-17
      role: service-risk-owner
  signature: sigstore-bundle://decisions/DEC-20260820-0041-03
```

W3C PROV-O의 Entity·Activity·Agent와 생성·사용·귀속 관계는 Change Set, Evaluation, Policy Evaluation, Human Approval의 Provenance를 교환하는 데 참고할 수 있습니다. 다만 저장 형식은 조직의 환경에 맞게 선택할 수 있습니다.

Deployment Controller는 `result`만 확인하지 않습니다. 요청한 Artifact Digest, Environment, Cohort, Traffic, Capability가 `authorized_scope` 안에 있는지 검증합니다. 하나라도 다르면 실행을 거부합니다.

<a id="ai-section-16"></a>

## 16. 승인에는 유효기간과 철회 조건이 필요하다

승인은 영구 자격이 아닙니다. 다음 중 하나가 발생하면 만료 또는 재판정해야 합니다.

```text
Artifact 변경       Change Set 또는 종속 Artifact Digest 변경
Scope 변경          Tenant·Region·권한·Traffic·업무 목적 확대
Evidence 변경       만료·철회·평가기 결함·Coverage Gap 발견
Policy 변경         Risk Tolerance·Threshold·규제·계약 변경
운영 반증           Incident·Drift·Critical Finding·SLO 위반
시간 경과           Decision valid_until 도달
```

`EXPIRED`와 `REVOKED`를 구분합니다. 만료는 정한 시간이 끝난 것이고, 철회는 사고나 반증처럼 더 이상 사용해서는 안 되는 이유가 생긴 것입니다. 기존 Record를 삭제하지 않고 새 Revocation Event를 연결합니다.

```json
{
  "event_id": "REV-20260820-0018",
  "decision_id": "DEC-20260820-0041-03",
  "status": "REVOKED",
  "reason_code": "CRITICAL_RUNTIME_FINDING",
  "evidence_id": "FND-20260820-0092",
  "effective_at": "2026-08-20T05:14:11Z",
  "required_action": "FREEZE_AND_ROLLBACK"
}
```

철회 전파는 비동기 알림에만 의존하지 않습니다. Deployment Controller와 Runtime Control Plane이 짧은 유효기간의 Capability Token이나 최신 Decision 상태를 확인하도록 설계해, 이미 철회된 승인이 계속 사용되는 시간을 제한합니다.

<a id="ai-section-17"></a>

## 17. Exception은 영구 우회가 아니라 기한부 위험 수용이다

현실에서는 Non-critical 평가 한 건이 지연되거나 외부 공급자 장애로 일부 Evidence를 만들지 못할 수 있습니다. 모든 경우를 즉시 거부하면 운영이 멈추지만, `skip_gate=true`를 허용하면 통제는 사라집니다.

Exception은 최소한 다음 필드를 가진 별도 객체여야 합니다.

```yaml
exception:
  id: EXC-20260820-0007
  subject:
    change_set_digest: sha256:93a2...
    candidate_release_digest: sha256:c719...
  based_on:
    decision_snapshot_digest: sha256:fe20...
    policy_bundle_digest: sha256:bf90...
    approval_request_id: APR-20260820-0041
  failed_or_missing_rule: EXTENDED_LATENCY_LOAD_TEST
  reason: external-evaluator-capacity-incident
  residual_risk: delayed response may increase user abandonment
  scope:
    tenant_cohort: kr-internal-pilot
    traffic_percent_max: 0.5
    capability_constraints: [read-only]
  compensating_controls:
    - tighter-runtime-latency-alert
    - manual-operator-on-call
    - automatic-stop-at-p95-3s
  owner: role://service-risk-owner
  approved_by: [user://risk-owner-17]
  result: RISK_ACCEPTED
  valid_until: 2026-08-20T12:00:00Z
  exit_criteria:
    - missing-evaluation-completed
    - latency-gate-pass
```

Exception도 승인 대상과 같은 불변 Subject, 판정에 사용한 Snapshot, Policy Version에 결합합니다. 그래야 한 Change Set의 예외를 다른 Release나 더 넓은 Scope에 재사용하는 것을 막을 수 있습니다.

다음 항목은 Exception으로 우회하지 않는 것이 안전합니다.

- Subject 또는 Signature 불일치
- 승인자 신원 검증 실패
- 미해결 Critical 권한 우회·데이터 유출·파괴적 Side Effect
- Rollback도 격리도 불가능한 고위험 변경
- 법률·계약·내부 Policy가 예외를 금지한 조건

Exception 만료 시 자동 연장하지 않습니다. 미충족 Rule이 해결되지 않았다면 `HOLD` 또는 Rollback으로 이동하고, 새 위험 수용이 필요하면 새로운 Exception과 승인을 만듭니다.

<a id="ai-section-18"></a>

## 18. 긴급 변경은 통제를 생략하지 않고 순서를 바꾼다

운영 사고 중에는 정상 승인 대기 시간이 더 큰 피해를 만들 수 있습니다. Break-glass 경로는 필요하지만, 자유로운 우회 계정이 되어서는 안 됩니다.

```text
Incident 선언
  → 긴급 변경 권한 활성화
  → 최소 안전 Gate 실행
  → 제한된 Scope 적용
  → 실시간 관찰
  → 사후 독립 검토
  → 정규 Evidence 보완
  → 유지·수정·Rollback 결정
```

긴급 변경에서도 Subject Digest, 요청자·승인자 Identity, 이유, Scope, 실행 시간, Rollback Plan과 감사 기록은 남깁니다. 생략 가능한 것은 정상 경로의 일부 대기와 비차단 Evidence이지, 대상 식별과 책임 기록이 아닙니다.

Break-glass 권한은 평상시 비활성화하고, Incident ID와 짧은 TTL에 결합하며, 사용 즉시 독립 채널로 알립니다. 사후 검토 기한을 넘기면 해당 변경을 유지하는 승인이 자동 만료되도록 합니다.

<a id="ai-section-19"></a>

## 19. Promotion Contract로 단계별 노출을 제한한다

초기 Release Approval 뒤에는 Stage별 Promotion Contract가 필요합니다.

| Stage | 대표 Scope | 진입 조건 | 다음 결정 |
|---|---|---|---|
| Shadow | 복제 Traffic, Side Effect 차단 | Pre-production Gate PASS | Pilot 진입 또는 HOLD |
| Internal Pilot | 내부 Cohort 0.5~1% | Shadow Evidence 충족 | Canary 확대 또는 RETAIN |
| Canary | 위험 기반 Tenant 1~5% | Pilot SLO·안전 조건 충족 | 25% Promotion 또는 Rollback |
| Limited GA | 허용 Cohort 25% | 최소 표본·관찰 시간 충족 | 100% Promotion 또는 유지 |
| GA | 승인된 전체 Scope | 모든 Promotion Decision 유효 | 지속 모니터링 |

<img src="assets/blog-93-promotion-rollback-state-machine.png" alt="승인된 현재 Scope에서 Shadow·Pilot·Canary·Limited GA를 단계적으로 진행하고 관찰 사후조건의 충족·불충분·위반에 따라 Promotion, Retain, 동결, Capability 차단, 이전 Release와 업무 효과 복구로 전이하는 상태 흐름" width="660" />

숫자는 예시일 뿐이며 서비스의 요청량과 피해 규모에 맞춰야 합니다. 요청량이 적다면 Traffic 비율보다 최소 Sample과 관찰 시간을 먼저 충족해야 합니다.

```yaml
promotion_contract:
  from: internal-pilot-1pct
  to: canary-5pct
  subject_digest: sha256:c719...
  preconditions:
    minimum_requests: 5000
    minimum_duration: PT6H
    critical_incidents: 0
    unauthorized_tool_effects: 0
    task_success_lcb: ">=0.97"
    error_budget_burn_rate: "<2"
  on_pass: PROMOTE
  on_inconclusive: RETAIN
  on_fail: ROLLBACK
```

`RETAIN`은 실패가 아닙니다. 최소 표본이 부족하면 현재 안전한 Scope를 유지하며 더 관찰할 수 있습니다. 반면 Critical 불변조건 위반은 표본을 더 모으지 않고 즉시 Rollback해야 합니다.

<a id="ai-section-20"></a>

## 20. 관찰 구간의 사후조건을 다음 승인의 증거로 만든다

Canary Dashboard를 사람이 잠깐 보고 “문제없음”이라고 판단하면 재현할 수 없습니다. 관찰 결과를 구조화된 Evidence로 발행합니다.

```yaml
observation_evidence:
  id: EVD-CANARY-20260820-0011
  subject_digest: sha256:c719...
  deployment_stage: internal-pilot-1pct
  window:
    from: 2026-08-20T03:00:00Z
    to: 2026-08-20T09:00:00Z
  population:
    tenant_cohort: kr-internal-pilot
    request_count: 6270
  results:
    critical_incidents: 0
    unauthorized_tool_effects: 0
    task_success_lcb: 0.978
    p95_latency_delta: 0.06
    human_override_rate_delta: 0.002
  telemetry_completeness: 0.998
  verdict: PASS
```

Metric 자체뿐 아니라 Telemetry Completeness도 확인해야 합니다. Logging Pipeline이 끊긴 동안 오류가 0건이었다는 관측은 안전의 증거가 아닙니다. 관측 공백이 크면 `INCONCLUSIVE`로 처리합니다.

업무 효과가 늦게 나타나는 경우 관찰 구간도 분리합니다. 즉시 권한 위반은 초 단위로 Rollback할 수 있지만, 잘못 생성한 계약 요약이 며칠 뒤 발견될 수 있다면 전면 Promotion 전에 지연 품질 표본과 사람 검토를 추가합니다.

<a id="ai-section-21"></a>

## 21. Rollback은 실행 가능성과 업무 복구를 함께 계약한다

이전 Container로 되돌릴 수 있다는 사실만으로 AI Agent의 Rollback이 완성되지는 않습니다. 이미 보낸 메일, 생성한 Ticket, 변경한 권한, 오염된 Memory, 갱신한 Knowledge Index는 Code Rollback으로 취소되지 않을 수 있습니다.

Rollback Contract는 네 층을 포함합니다.

| 층 | 질문 | 예시 |
|---|---|---|
| Release | 이전 Artifact로 전환 가능한가 | Model Route·Prompt·Policy 복원 |
| Capability | 위험한 기능을 즉시 중지할 수 있는가 | Tool write 차단·Kill Switch |
| State | 새 Schema·Memory·Index를 되돌릴 수 있는가 | Dual-write·Snapshot·Migration 보상 |
| Business Effect | 이미 발생한 외부 효과를 복구할 수 있는가 | 취소 API·사람 검토·고객 통지 |

```yaml
rollback_contract:
  id: RB-20260820-0041-v2
  subject:
    change_set_digest: sha256:93a2...
    candidate_release_digest: sha256:c719...
    authorized_scope_digest: sha256:d611...
  rollback_policy_version: RBP-v4
  target_release_digest: sha256:81d0...
  triggers:
    - "unauthorized_tool_effects > 0"
    - "critical_incidents > 0"
    - "task_success_lcb < 0.94"
  actions:
    - freeze_promotion
    - disable_capability: external_send
    - route_to_release: sha256:81d0...
    - quarantine_candidate_sessions
    - enqueue_business_effect_review
  recovery_objectives:
    detection: PT1M
    capability_stop: PT2M
    release_restore: PT10M
  verification:
    - effective_release_digest_matches_target
    - write_tool_denial_probe_passes
    - affected_effects_reconciled
```

Rollback Contract도 복원할 Target뿐 아니라 어떤 Candidate와 Change Set, 승인 Scope에 대한 계약인지 고정합니다. 비가역적 효과가 있다면 “Rollback 가능”이라고 표시하지 않습니다. `PARTIAL`로 분류하고, 보상 작업과 책임자, 허용 가능한 손실 범위를 Risk Tier에 반영합니다. 자세한 Progressive Delivery와 State 복구는 [BLOG-87](https://aiarchitect.tistory.com/87)에서 다룹니다.

<a id="ai-section-22"></a>

## 22. 승인 명령의 재전송과 경합을 멱등 계약으로 흡수한다

변경 승인 시스템도 분산 시스템입니다. 같은 Change Set의 중복 Event, 오래 걸리는 평가 중 새 Commit, 동시에 실행되는 Promotion과 Rollback을 처리해야 합니다.

권장 규칙은 다음과 같습니다.

- 모든 Event에 전역적으로 유일한 ID와 Subject Digest를 둡니다.
- 동일 `decision_request_id` 재처리는 같은 결과를 반환하도록 Idempotent하게 만듭니다.
- Decision은 기대한 Base Release와 현재 Effective Release가 같은지 Compare-and-Set으로 확인합니다.
- 새 Change Set이 생기면 이전 Snapshot과 미실행 Decision을 `SUPERSEDED`로 닫습니다.
- Rollback과 Promotion이 충돌하면 안전 우선순위로 Rollback이 이기게 합니다.
- 순서가 뒤바뀐 Event는 Event Time과 Version으로 탐지하고 재판정합니다.

```text
Safety priority:
REVOKE / ROLLBACK > FREEZE / HOLD > RETAIN > PROMOTE
```

이 우선순위가 “항상 Rollback이 정답”이라는 뜻은 아닙니다. 동일 Subject와 Stage에서 충돌하는 명령을 동시에 받았을 때 위험 확대보다 중지·축소를 먼저 적용한다는 뜻입니다.

장기 실행 Agent Task도 고려합니다. Task 시작 시 Release Digest와 Decision Scope를 고정하고, 중간 Promotion이 기존 Task의 Prompt·Tool을 섞지 않게 합니다. Critical Revocation이면 명시된 중단·격리 Policy에 따라 처리합니다.

<a id="ai-section-23"></a>

## 23. 운영 사고는 기존 승인을 즉시 재평가하게 한다

승인 후에도 새로운 반증이 들어옵니다. [BLOG-90 Continuous Assurance](https://aiarchitect.tistory.com/90)의 Finding, [BLOG-92](https://aiarchitect.tistory.com/92)의 Evidence Revocation, 운영 SLO와 Incident Event를 Decision Graph에 연결합니다.

```text
Runtime Signal / Incident / Finding
  → affected Subject·Claim·Evidence 탐색
  → Decision 영향 계산
  → Promotion 동결
  → Runtime Scope 축소 또는 Rollback
  → Evidence 재검증
  → 새 Decision 발행
```

Severity만으로 자동 Rollback을 결정하지 않습니다. Signal 신뢰도, 영향받은 Subject 일치, 현재 Scope, 탐지 지연과 오탐 비용을 함께 봅니다. 다만 권한 우회, 민감정보 외부 전송, 파괴적 Tool 오작동처럼 미리 정한 Critical Invariant는 즉시 Capability를 차단해야 합니다.

운영 중 조치는 기존 Record를 수정하지 않고 새 사건과 결정으로 연결합니다. 그래야 “왜 05:14에 5% Canary가 중지됐는가”를 Finding, Telemetry, Rule, Revocation, Rollback 실행까지 추적할 수 있습니다.

<a id="ai-section-24"></a>

## 24. 합성 사례로 Prompt·Tool 변경 승인을 계산한다

회의 후속조치 Agent가 회의록에서 담당자와 마감일을 추출해 Ticket 초안을 만듭니다. 이번 변경은 Prompt를 수정하고 `ticket.draft` Tool Schema에 `due_date` 필드를 추가합니다. 외부 전송은 하지 않지만 업무 시스템에 Draft를 쓰므로 단순 문구 변경은 아닙니다.

### 1단계: Change Set과 영향 분석

```text
변경                Prompt Bundle + Tool Contract
업무 영향            잘못된 담당자·마감일이 Draft에 기록될 수 있음
노출                 내부 Pilot Tenant 1%
권한                 ticket.draft 쓰기, publish 권한 없음
가역성               Draft 삭제 가능, 알림 발송 전
Risk Tier            TIER-2, 단 external publish 활성화 시 TIER-3
```

### 2단계: Evidence Profile 실행

| Gate | 결과 | 해석 |
|---|---|---|
| Subject·Provenance 일치 | PASS | Candidate Digest와 Evidence Subject 일치 |
| Tool Schema Contract | PASS | 신규 필드·거부 Case 검증 |
| Critical Slice Regression | PASS | 담당자·마감일·다국어 Slice 충족 |
| Unauthorized Publish | PASS | publish 호출 0건 |
| Rollback Rehearsal | PASS | 이전 Prompt·Schema Route 6분 내 복원 |
| P95 Latency Delta | PASS_WITH_GAP | 목표 +5%는 넘었지만 Non-blocking Hard Limit +10% 이내 |

### 3단계: 조건부 자동 승인

Policy는 TIER-2, 내부 1%, `ticket.draft`만 허용, 모든 Blocking Gate PASS, Rollback 검증을 확인해 6시간 조건부 승인을 발행합니다. Latency는 상한에 가까우므로 경고 Threshold를 강화합니다.

```text
Decision            APPROVED_CONDITIONAL
Authorized Scope    internal-pilot / 1% / ticket.draft only
Forbidden           ticket.publish, external notification
Observation         6시간 + 최소 5,000건
Promotion           사람 검토 후 5%
Rollback Trigger    unauthorized publish > 0 또는 task success LCB < 0.94
```

### 4단계: Scope 확대 요청

다음 요청이 `ticket.publish`를 활성화한다면 기존 승인을 재사용할 수 없습니다. Authority와 업무 피해가 달라져 새 Change Set·Risk Tier·Evidence Profile·사람 승인이 필요합니다. “Code가 같고 Feature Flag만 켰다”는 이유로 이전 Decision Scope를 확장해서는 안 됩니다.

이 사례의 핵심은 자동 승인 여부가 Prompt 변경이라는 이름에 의해 결정되지 않는다는 점입니다. 실제 권한, 노출, 가역성, Evidence, 관찰과 Scope 계약이 함께 결정합니다.

<a id="ai-section-25"></a>

## 25. 실패하기 쉬운 변경 승인 안티패턴을 피한다

### CI가 초록색이면 곧바로 전면 배포한다

시험 통과와 Risk Acceptance, 초기 배포와 다음 Promotion을 분리하지 않은 설계입니다. Gate Result, Approval Decision, Promotion Decision을 별도 Record로 만듭니다.

### Ticket 번호만 승인 대상에 연결한다

Ticket 내용은 수정될 수 있고 실제 Artifact를 식별하지 못합니다. Change Set과 모든 주요 구성요소 Digest를 Decision Subject로 사용합니다.

### 모든 변경에 같은 Checklist를 요구한다

낮은 위험에는 승인 병목을 만들고 높은 위험에는 증거가 부족합니다. Risk Tier와 Change Impact에 따라 Versioned Evidence Profile을 선택합니다.

### 평균 점수로 Critical 실패를 상쇄한다

권한 우회 한 건은 높은 평균 정확도로 없어지지 않습니다. Critical Invariant와 일반 Threshold를 분리합니다.

### 사람이 승인하면 Evidence Gap이 사라진다

사람은 잔여 위험을 수용할 수 있지만 존재하지 않는 시험 결과를 만들어내지는 못합니다. 미충족 항목, 이유, 보완 통제, Scope, 만료가 있는 Exception으로 기록합니다.

### Exception을 만료 없이 복사한다

예외가 정상 경로가 됩니다. 짧은 TTL, Owner, Exit Criteria를 두고 자동 연장을 금지합니다.

### Rollback을 이전 이미지 배포로만 정의한다

Tool Side Effect와 Memory·Knowledge·Schema 변경이 남습니다. Release·Capability·State·Business Effect 네 층을 검증합니다.

### 승인 Record를 현재 상태로 덮어쓴다

과거 판단의 근거와 철회 과정을 잃습니다. Decision, Exception, Revocation, Promotion, Rollback을 Append-only Event로 연결합니다.

### 자동 승인 Rule을 아무나 즉시 수정한다

Policy 변경이 가장 쉬운 우회 경로가 됩니다. Policy도 Review·서명·Version·업무 분리를 가진 Release 대상이어야 합니다.

<a id="ai-section-26"></a>

## 26. 다섯 단계로 도입하고 결정 품질을 측정한다

처음부터 모든 AI Agent와 모든 Gate를 통합할 필요는 없습니다.

### 1단계: 승인 대상을 고정한다

Release Bundle, Change Set, Environment, Tenant, Capability와 Traffic Scope를 구조화합니다. Decision에 Candidate Digest와 허용 Scope가 반드시 들어가게 합니다.

### 2단계: Risk Tier와 Blocking Gate를 최소화해 시작한다

가장 중요한 업무 피해와 Critical Invariant부터 정의합니다. 자동 승인 범위는 내부·읽기 중심·가역적 변경으로 제한합니다.

### 3단계: Evidence Profile과 Decision Record를 자동화한다

평가·보안·Provenance·Rollback Evidence를 Versioned Profile로 묶고, Snapshot과 Decision을 서명된 Append-only Record로 남깁니다.

### 4단계: Exception·Promotion·Rollback을 연결한다

기한부 예외, Canary Observation Evidence, 다음 Promotion, 승인 철회와 Rollback을 하나의 상태 흐름으로 운영합니다.

### 5단계: 운영 반증과 Policy 개선을 폐쇄 루프로 만든다

Incident·Finding·Drift가 영향받은 Decision을 재평가하게 하고, 오탐·승인 지연·Rollback 결과를 근거로 Tier와 Gate Rule을 조정합니다.

운영 지표는 승인 건수보다 결정의 품질을 보여야 합니다.

| 지표 | 의미 |
|---|---|
| Decision Lead Time | Change Set 고정부터 첫 승인까지 걸린 시간 |
| Evidence Wait Ratio | 전체 지연 중 Evidence 생성·갱신 대기 비율 |
| Auto-approval Eligibility Rate | 자동 승인 조건을 실제로 충족한 비율 |
| Human Override Rate | 기계 경로와 다른 사람 결정의 비율과 이유 |
| Exception Age·Renewal Rate | 예외가 정상 상태로 굳어지는지 여부 |
| Post-approval Incident Rate | 승인 후 동일 Claim에서 발생한 사고 비율 |
| Revocation Propagation Time | 반증 발견부터 실행 차단까지 걸린 시간 |
| Rollback Success·Recovery Time | 계약한 복구가 실제 수행됐는지 여부 |
| False Hold·False Approve Review | 과도한 차단과 위험한 통과를 사후 분석한 결과 |

자동 승인율 자체를 목표로 삼으면 Tier를 낮추거나 Gate를 약하게 만드는 잘못된 유인이 생깁니다. 목표는 **낮은 위험 변경의 대기 시간을 줄이면서 고위험 변경의 증거와 책임 경계를 강화하는 것**입니다.

마무리하면 기업 AI Agent의 변경 승인 자동화는 승인 버튼을 Workflow에 추가하는 일이 아닙니다. 정확한 Change Set, 설명 가능한 Risk Tier, 현재 유효한 Evidence Profile, 분리된 Gate와 Decision, 범위가 제한된 자동 승인, 책임 있는 사람 승인, 만료되는 Exception, 관찰 가능한 Promotion과 실행 가능한 Rollback을 하나의 계약으로 만드는 일입니다.

이 구조가 갖춰지면 팀은 두 질문에 동시에 답할 수 있습니다.

```text
왜 이 변경을 이 범위에 승인했는가?
어떤 조건이 깨지면 누가 언제 중지하고 복구하는가?
```

첫 번째 질문은 Assurance와 승인 책임을, 두 번째 질문은 운영 통제와 복구 가능성을 만듭니다. 두 답이 같은 Decision Graph에 연결될 때 변경 속도와 거버넌스는 서로의 반대말이 아니게 됩니다.

<a id="ai-section-27"></a>

## 27. 공식 참고자료

- NIST, [Artificial Intelligence Risk Management Framework (AI RMF 1.0)](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10)
- NIST, [AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- NIST, [AI RMF Playbook](https://www.nist.gov/itl/ai-risk-management-framework/nist-ai-rmf-playbook)
- NIST, [SP 800-53 Rev. 5: Security and Privacy Controls for Information Systems and Organizations](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)
- NIST, [SP 800-218: Secure Software Development Framework (SSDF) Version 1.1](https://csrc.nist.gov/pubs/sp/800/218/final)
- NIST, [SP 800-218A: Secure Software Development Practices for Generative AI and Dual-Use Foundation Models](https://csrc.nist.gov/pubs/sp/800/218/a/final)
- ISO, [ISO/IEC 42001:2023 — Artificial intelligence management system](https://www.iso.org/standard/42001)
- W3C, [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)
- in-toto, [Attestation Framework v1.2](https://github.com/in-toto/attestation/tree/v1.2.0/spec)
- SLSA, [Specification v1.2](https://slsa.dev/spec/v1.2/)
- SLSA, [Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts)
- SLSA, [Verification Summary Attestation](https://slsa.dev/spec/v1.2/verification_summary)

작성 시점인 2026년 8월 기준으로 NIST AI RMF 1.0은 개정 작업이 진행 중이며, NIST SP 800-218 Rev. 1의 SSDF 1.2는 Draft입니다. 이 글은 공개된 AI RMF 1.0과 최종본 SSDF 1.1을 기준선으로 사용합니다. 또한 이 글의 Risk Tier, Gate 상태, Policy 예시는 위 표준의 문구를 그대로 옮긴 규격이 아니라, 공식 원칙을 기업 AI Agent 변경 승인 흐름에 적용한 구현 제안입니다.
