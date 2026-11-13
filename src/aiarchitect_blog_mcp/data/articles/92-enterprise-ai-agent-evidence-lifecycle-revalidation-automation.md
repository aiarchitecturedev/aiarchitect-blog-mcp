# 기업 AI Agent 증거 수명주기 설계: Freshness·Expiry·Revocation·Revalidation 자동화

평가 보고서가 저장소에 남아 있다는 사실이 그 결과가 지금도 유효하다는 뜻은 아닙니다. Model과 Prompt, Tool, Policy가 바뀌면 어떤 증거는 그대로 쓸 수 있고 어떤 증거는 즉시 무효가 되는데, 이를 구분하지 못하면 전체 재평가와 무검증 배포 사이에서 매번 선택하게 됩니다. 이 글은 증거를 Release와 Claim에 바인딩하고 Freshness·Expiry·Revocation을 관리하며 변경 영향 그래프로 최소 재검증만 자동 실행하는 설계를 정리합니다.

![기업 AI Agent의 Release·Model·Prompt·Tool·Dataset·Policy 증거가 시간과 변경에 따라 활성·노후·철회 상태로 전이되고 영향받은 주장만 선택적으로 재검증되는 증거 수명주기 아키텍처](assets/blog-92-ai-agent-evidence-lifecycle-revalidation-hero.png)

<blockquote id="aiarchitect-toc" data-ke-style="box" style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;" data-mce-style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;">
<p style="color: #263746; font-weight: 700;" data-mce-style="color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 700;"><b>목차</b></p>
<ol style="list-style-type: decimal; color: #555555; font-weight: 400;" data-mce-style="list-style-type: decimal; color: #555555; font-weight: 400;" data-ke-list-type="decimal">
<li><a href="#ai-section-1" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">평가 보고서는 남아 있어도 승인 근거는 낡을 수 있다</a></li>
<li><a href="#ai-section-2" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">BLOG-91의 Evidence Graph를 운영 수명주기로 확장한다</a></li>
<li><a href="#ai-section-3" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Evidence·Claim·Decision의 수명주기를 분리한다</a></li>
<li><a href="#ai-section-4" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">증거를 불변 Subject와 Context에 바인딩한다</a></li>
<li><a href="#ai-section-5" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">상태 머신으로 증거의 사용 가능성을 관리한다</a></li>
<li><a href="#ai-section-6" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">STALE·EXPIRED·REVOKED·SUPERSEDED를 구분한다</a></li>
<li><a href="#ai-section-7" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Evidence Record에 판정에 필요한 최소 필드를 둔다</a></li>
<li><a href="#ai-section-8" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Freshness는 고정 TTL이 아니라 위험 기반 정책이다</a></li>
<li><a href="#ai-section-9" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">출처·무결성·내용 타당성을 세 단계로 검증한다</a></li>
<li><a href="#ai-section-10" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">변경 이벤트를 정규화해 누락 없이 수집한다</a></li>
<li><a href="#ai-section-11" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">의존 그래프로 변경 영향 범위를 계산한다</a></li>
<li><a href="#ai-section-12" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">무효화 규칙은 Event·Edge·Predicate로 작성한다</a></li>
<li><a href="#ai-section-13" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">최소 재검증은 영향받은 Claim의 공백만 채운다</a></li>
<li><a href="#ai-section-14" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">기존 증거 재사용에는 명시적인 안전 조건이 필요하다</a></li>
<li><a href="#ai-section-15" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Evidence Pipeline을 Release Gate에 연결한다</a></li>
<li><a href="#ai-section-16" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">동시 변경과 중복 이벤트에도 판정이 흔들리지 않게 한다</a></li>
<li><a href="#ai-section-17" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Runtime Drift와 Incident가 즉시 Claim에 도달하게 한다</a></li>
<li><a href="#ai-section-18" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">보존·삭제·Legal Hold를 유효성과 분리한다</a></li>
<li><a href="#ai-section-19" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">운영 지표는 증거 수보다 판정 지연과 공백을 본다</a></li>
<li><a href="#ai-section-20" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">합성 사례로 Prompt 변경의 최소 재검증을 계산한다</a></li>
<li><a href="#ai-section-21" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">실패하기 쉬운 Evidence Lifecycle 안티패턴을 피한다</a></li>
<li><a href="#ai-section-22" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">네 단계로 증거 수명주기를 도입한다</a></li>
<li><a href="#ai-section-23" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">마무리 — 지속 검증은 전체 재시험이 아니라 근거의 연속성이다</a></li>
<li><a href="#ai-section-24" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">공식 참고자료</a></li>
</ol>
</blockquote>

지난주에 통과한 AI Agent 평가 보고서가 오늘도 저장소에 있습니다. 파일의 Hash와 전자서명도 정상입니다. 그렇다면 이 보고서는 오늘 배포할 Release의 승인 근거로 쓸 수 있을까요?

답은 조건부입니다. 보고서가 평가한 Model·Prompt·Tool Schema·Dataset·Policy와 오늘의 Release가 같아야 합니다. 평가 환경과 운영 Context도 허용 범위 안에 있어야 합니다. 그 사이 새로운 취약점, 운영 Drift, 사고, 정책 변경, 평가기 결함이 발견되지 않았어야 합니다. 유효기간과 Coverage도 현재 Claim을 만족해야 합니다.

즉 **파일이 존재한다는 사실**, **파일이 변조되지 않았다는 사실**, **현재 승인 판단에 사용할 수 있다는 사실**은 서로 다릅니다. 기업 AI Agent의 증거는 정적 문서가 아니라 대상·시간·변경·반증에 따라 상태가 바뀌는 운영 객체로 관리해야 합니다.

[BLOG-91](https://aiarchitect.tistory.com/91)에서 만든 Evidence Graph는 승인 시점을 찍은 정지 화면입니다. 이 글은 그 그래프에 시간을 넣습니다. 증거마다 유효 기간과 무효화 조건을 붙이고, Prompt·Model·Tool·Policy가 바뀔 때 어떤 Claim이 흔들리는지 의존 그래프로 계산해, **다시 검증해야 할 최소 범위만 자동으로 뽑아내는 것**이 목표입니다.

이 글의 Agent, 회사, Release, Digest, 평가 수치와 Policy는 모두 교육용 합성 예시입니다. `ACTIVE`, `STALE`, `REVOKED` 같은 상태 이름과 TTL 예시는 이 글이 제안하는 구현 모델이며 W3C PROV, in-toto, SLSA, OSCAL이 정한 공통 상태 열거형이 아닙니다. 이 글의 TTL과 임계값을 그대로 옮겨 쓰지 마십시오. 실제 값은 Claim이 틀렸을 때의 업무 영향, 보안·개인정보·법무 정책, 산업 규제와 계약, 그리고 실제 평가·운영 데이터에서 역산해야 합니다.

<a id="ai-section-1"></a>

## 1. 평가 보고서는 남아 있어도 승인 근거는 낡을 수 있다

Evidence가 낡는 원인은 시간만이 아닙니다.

```text
Release 변경     Model·Prompt·Tool·Knowledge·Policy Digest 변경
환경 변경         권한·Region·Tenant·Dependency·Runtime 설정 변경
평가 기반 변경    Dataset·Evaluator·Threshold·Sampling Policy 변경
운영 관측         Drift·오류율 상승·새로운 실패 Slice 발견
반증 발견         Red Team Finding·Incident·취약점·평가기 결함 발견
시간 경과         정한 Freshness Window 또는 승인 유효기간 초과
```

예를 들어 Prompt만 수정했더라도 Tool 선택 순서와 입력 인자, 거부 문구, 사람 승인 요청 시점이 바뀔 수 있습니다. 반대로 Logging Agent의 Dashboard 색상 변경은 개인정보 보존 통제 Claim에 영향을 주지 않을 수 있습니다. 두 변경을 모두 “전체 회귀 평가”로 처리하면 비용이 폭증하고, 모두 “경미한 변경”으로 처리하면 필요한 재검증을 놓칩니다.

따라서 필요한 것은 단순한 만료 알림이 아니라 다음 네 기능입니다.

1. 어떤 증거가 어떤 Subject·Claim·Decision을 지지하거나 반박하는지 추적합니다.
2. 변경과 사고가 발생하면 영향받은 Evidence와 Claim을 계산합니다.
3. 현재 Coverage의 공백을 채우는 최소 재검증 계획을 만듭니다.
4. 재검증이 끝날 때까지 Release Gate와 운영 범위를 보수적으로 조정합니다.

<a id="ai-section-2"></a>

## 2. BLOG-91의 Evidence Graph를 운영 수명주기로 확장한다

Evidence Lifecycle은 새 저장소를 하나 더 만드는 일이 아닙니다. 기존 거버넌스 산출물을 하나의 변경 전파 경로로 연결하는 일입니다.

| 연결 글 | 이미 확보한 산출물 | BLOG-92에서 추가할 연결 |
|---|---|---|
| [AI Agent 평가 아키텍처](https://aiarchitect.tistory.com/74) | Dataset·Evaluator·Metric·회귀 평가 | 실행 결과의 Freshness·Coverage·재실행 계획 |
| [AI Agent Control Plane](https://aiarchitect.tistory.com/76) | Desired·Effective·Observed State, Policy·Kill Switch | 증거 상태에 따른 허용 범위 축소·차단 |
| [AI Agent Release Governance](https://aiarchitect.tistory.com/87) | 불변 Release Bundle·Progressive Delivery·Release Ledger | 변경 이벤트·재검증 Gate·승인 유효기간 |
| [AI Agent Sandbox](https://aiarchitect.tistory.com/89) | 격리 평가·Synthetic Data·Tool Simulation | 재검증 실행 환경과 Evidence Producer |
| [Red Teaming과 Continuous Assurance](https://aiarchitect.tistory.com/90) | Finding·Counter-evidence·Runtime Assurance | Finding 발생 시 Claim 무효화·재검증 Trigger |
| [Assurance Case와 Evidence Graph](https://aiarchitect.tistory.com/91) | Claim·Argument·Evidence·Decision | Evidence 상태 전이·변경 영향·최소 재검증 |

핵심 경로는 다음과 같습니다.

```text
Release Bundle 변경
  → Change Event
  → Subject·Evidence·Claim Graph 탐색
  → Evidence 상태 전이
  → Coverage 공백 계산
  → 최소 재검증 실행
  → Assurance Decision 재판정
  → Release Gate 또는 Runtime Policy 반영
```

<a id="ai-section-3"></a>

## 3. Evidence·Claim·Decision의 수명주기를 분리한다

세 객체를 하나의 `PASS/FAIL` 상태로 합치면 변경 영향이 과도하게 전파되거나 위험하게 누락됩니다.

| 객체 | 의미 | 상태 예 | 바뀌는 대표 원인 |
|---|---|---|---|
| Evidence | 관찰·시험·문서·Attestation 산출물 | ACTIVE·STALE·REVOKED | Subject 변경, 시간 경과, 평가기 결함 |
| Claim | 특정 범위에서 받아들이려는 주장 | UNKNOWN·SUPPORTED·PARTIAL·UNSUPPORTED·DEFEATED | 지지 Evidence 공백, Counter-evidence 발생 |
| Decision | 운영 범위에 대한 승인 판단 | APPROVED·CONDITIONAL·HOLD·REJECTED | Claim 상태, Risk Tolerance, 승인 만료 |

`Evidence=ACTIVE`는 그 증거를 현재 판정에 사용할 수 있다는 뜻이지 결과가 성공이라는 뜻이 아닙니다. 활성 상태의 Red Team Finding은 Claim을 반박할 수 있습니다. 반대로 `Evidence=STALE`도 내용이 거짓이라는 뜻은 아닙니다. 현재 Release에 적용 가능한지 다시 확인해야 한다는 뜻입니다.

이 분리가 있어야 다음과 같은 판단이 가능합니다.

```text
평가 결과 Evidence: ACTIVE, verdict=FAIL
Claim: DEFEATED
Decision: HOLD
```

상태와 결과를 분리하지 않으면 실패 보고서를 `inactive`로 숨겨 승인 근거에서 사라지게 만드는 심각한 오류가 생길 수 있습니다.

<a id="ai-section-4"></a>

## 4. 증거를 불변 Subject와 Context에 바인딩한다

`agent-prod`, `latest-model`, `current-policy` 같은 별칭은 사람이 보기에는 편하지만 증거 대상 식별자로는 부족합니다. Evidence에는 평가 시점의 불변 Subject가 들어가야 합니다.

```yaml
subject:
  agent_release_digest: sha256:8c31...
  model_route_digest: sha256:2a90...
  prompt_bundle_digest: sha256:18b2...
  tool_contract_digest: sha256:6d0a...
  knowledge_snapshot_digest: sha256:a422...
  policy_bundle_digest: sha256:991f...
context:
  tenant_class: internal-pilot
  region: kr
  data_classification: confidential
  identity_profile: employee-standard
  tool_scope: [calendar.read, ticket.draft]
  runtime_profile_digest: sha256:b113...
```

Model API처럼 공급자가 내부 Weight Digest를 제공하지 않는 경우에는 사용할 수 없는 식별자를 꾸며내면 안 됩니다. Provider, Model ID, Version 또는 Snapshot ID, Region, API Parameter, Routing Policy, 호출 시각과 응답 메타데이터처럼 실제로 관찰 가능한 식별자를 남깁니다. Provider가 Alias만 제공한다면 그 불확실성을 Claim의 Assumption과 Freshness Policy에 반영합니다.

Context가 달라지면 같은 Artifact도 다른 위험을 가집니다. 사내 읽기 전용 Pilot에서 얻은 증거는 외부 메일 발송 권한이 있는 운영 Context를 자동으로 지지하지 않습니다.

<a id="ai-section-5"></a>

## 5. 상태 머신으로 증거의 사용 가능성을 관리한다

<img src="assets/blog-92-evidence-state-machine.png" alt="AI Agent Evidence가 수집·격리·검증·활성화된 뒤 변경과 시간 경과에 따라 노후·만료·철회·대체되고 재검증을 통해 다시 활성화되는 상태 머신" width="450" />

이 글의 권장 상태 모델은 다음과 같습니다.

| 상태 | 의미 | Gate 사용 |
|---|---|---|
| `COLLECTED` | Producer에서 수집됐지만 아직 신뢰 검증 전 | 불가 |
| `QUARANTINED` | Schema·Digest·서명·Issuer 검증 대기 | 불가 |
| `VERIFIED` | 기본 무결성과 출처 검증 통과 | Claim 연결 전에는 불가 |
| `ACTIVE` | 특정 Subject·Claim·Context에서 현재 사용 가능 | 가능 |
| `STALE` | 변경·Drift·Freshness 초과로 적용 가능성 재확인 필요 | 기본 불가 또는 제한적 |
| `EXPIRED` | 명시된 `valid_until` 종료 | 불가 |
| `REVOKED` | 오류·사고·발행자 철회로 사용 금지 | 불가 |
| `SUPERSEDED` | 더 새로운 증거가 역할을 대체 | 과거 감사용만 |
| `REJECTED` | 수집 또는 검증 실패 | 불가 |
| `REVALIDATING` | 영향 범위가 정해져 재검증 진행 중 | 정책에 따라 HOLD·제한 운용 |

상태 전이는 원인, 행위자, 시각과 이전 상태를 Append-only Event로 남깁니다. 관리자가 DB 값을 `ACTIVE`에서 `REVOKED`로 직접 바꾸고 이유를 덮어쓰는 방식은 감사 가능성을 잃습니다.

```json
{
  "event_id": "EVT-EVIDENCE-20260819-0042",
  "evidence_id": "EVD-TOOL-0088",
  "from": "ACTIVE",
  "to": "STALE",
  "reason_code": "PROMPT_SUBJECT_CHANGED",
  "caused_by": "CHG-20260819-017",
  "occurred_at": "2026-08-19T06:20:00Z",
  "actor": "evidence-invalidation-engine"
}
```

<a id="ai-section-6"></a>

## 6. STALE·EXPIRED·REVOKED·SUPERSEDED를 구분한다

네 상태를 모두 `invalid=true`로 합치면 운영자가 무엇을 해야 하는지 알 수 없습니다.

| 상태 | 핵심 질문 | 필요한 조치 | 과거 감사 보존 |
|---|---|---|---|
| STALE | 현재 대상에도 적용되는가 | 영향 분석·재검증 | 예 |
| EXPIRED | 정한 유효기간이 끝났는가 | 새 평가 또는 승인 갱신 | 예 |
| REVOKED | 사용하면 안 되는 명시적 이유가 있는가 | 즉시 Gate 차단·영향 Decision 재판정 | 예 |
| SUPERSEDED | 새 증거가 같은 역할을 대체했는가 | 새 Evidence를 기본 선택 | 예 |

예를 들어 Dataset에 Label Leakage가 발견됐다면 해당 Dataset으로 만든 평가 결과는 `REVOKED`가 적절합니다. 단순히 30일이 지났다면 `EXPIRED`입니다. Prompt가 바뀌어 적용 여부가 불명확해졌다면 `STALE`입니다. 동일 조건에서 더 큰 Sample로 재평가해 기존 결과를 대체했다면 이전 결과는 `SUPERSEDED`로 남깁니다.

삭제는 상태가 아닙니다. `REVOKED` Evidence도 왜 과거 승인이 잘못됐는지 조사하려면 보존해야 합니다.

<a id="ai-section-7"></a>

## 7. Evidence Record에 판정에 필요한 최소 필드를 둔다

파일 URL과 생성일만으로는 자동 판정할 수 없습니다. 다음은 구현 예시입니다.

```yaml
evidence:
  id: EVD-TOOL-0088
  type: evaluation-result
  predicate: tool-policy-conformance/v2
  verdict: pass
  status: ACTIVE
  subject:
    agent_release_digest: sha256:8c31...
    prompt_bundle_digest: sha256:18b2...
    tool_contract_digest: sha256:6d0a...
    policy_bundle_digest: sha256:991f...
  producer:
    issuer: spiffe://assurance.example/evaluator/tool-policy
    evaluator_digest: sha256:51ce...
    execution_environment_digest: sha256:99da...
  artifact:
    uri: s3://evidence/2026/08/EVD-TOOL-0088.json
    digest: sha256:aa72...
    signature_bundle_uri: s3://evidence/2026/08/EVD-TOOL-0088.bundle
  coverage:
    scenario_set: critical-tools-v7
    required_slices: 12
    covered_slices: 12
    sample_count: 2400
  time:
    observed_from: 2026-08-18T00:00:00Z
    observed_until: 2026-08-18T04:12:00Z
    issued_at: 2026-08-18T04:13:10Z
    valid_until: 2026-09-01T00:00:00Z
  claims:
    supports: [CLM-TOOL-01, CLM-TOOL-02]
    contradicts: []
  lifecycle:
    freshness_policy: FP-CRITICAL-TOOL-01
    invalidation_rule_set: IRS-TOOL-03
    supersedes: null
```

여기서 `predicate`는 무엇을 측정했는지, `verdict`는 그 결과가 무엇인지, `status`는 지금 사용할 수 있는지를 분리합니다. `coverage`가 없으면 전체 평균이 Critical Slice의 공백을 숨길 수 있습니다.

<a id="ai-section-8"></a>

## 8. Freshness는 고정 TTL이 아니라 위험 기반 정책이다

모든 Evidence에 일괄적으로 30일 TTL을 주는 것은 단순하지만 정확하지 않습니다. Freshness Window는 최소한 다음 요소로 결정합니다.

```text
Freshness Window = f(
  업무 영향,
  Subject 변동성,
  운영 노출,
  탐지 가능성,
  변경 빈도,
  평가 비용,
  법규·계약·내부 정책
)
```

| Evidence 예 | 변동성·영향 | 예시 정책 | 반드시 Event Trigger도 필요한가 |
|---|---|---|---|
| Critical Tool 권한·Side Effect 평가 | 높음 | 짧은 유효기간 + Release마다 | 예 |
| Prompt Injection 회귀 평가 | 높음 | Prompt·Model·RAG 변경 시 | 예 |
| 운영 Drift 통계 | 매우 높음 | Rolling Window로 지속 갱신 | 예 |
| 조직 역할·승인자 지정 | 중간 | 분기 검토 + 인사 변경 시 | 예 |
| 정적 아키텍처 설명 | 낮음 | 반기 검토 | 예 |

표의 기간은 보편적 표준값이 아니라 설계 예시입니다. 높은 위험 Evidence는 시간 TTL만으로 보호할 수 없습니다. 평가 직후 Critical Tool 권한이 바뀌었다면 30일이 남았어도 즉시 `STALE` 또는 `REVOKED`로 전이해야 합니다.

권장 판정은 다음과 같습니다.

```text
usable(evidence, now, release) =
  status == ACTIVE
  AND now < valid_until
  AND subject_matches(release)
  AND context_covers(target_context)
  AND required_coverage_met
  AND no_active_revocation
  AND issuer_is_trusted
```

<a id="ai-section-9"></a>

## 9. 출처·무결성·내용 타당성을 세 단계로 검증한다

Evidence 검증은 한 번의 서명 확인으로 끝나지 않습니다.

### 1단계: Artifact 무결성

- Digest가 실제 Artifact와 일치하는가
- Schema와 필수 필드가 유효한가
- 서명된 Payload와 표시된 내용이 같은가

### 2단계: Provenance와 Issuer 신뢰

- 누가 어떤 Activity로 만들었는가
- 사용한 Dataset·Evaluator·Environment가 무엇인가
- Issuer가 해당 Predicate를 발행할 권한과 독립성을 가졌는가

### 3단계: Claim 적용 가능성과 충분성

- Evidence의 Subject가 현재 Release와 일치하는가
- Context와 Coverage가 Claim 범위를 덮는가
- Threshold와 평가 방법이 승인된 Policy인가
- 반대 Evidence와 미해결 Finding이 있는가

W3C PROV-O의 Entity·Activity·Agent 관계는 생성·사용·파생·무효화 이력을 표현하는 데 유용합니다. in-toto Attestation은 Subject와 Predicate를 Statement에 담고 Envelope로 인증하는 구조를 제공합니다. SLSA Provenance는 Software Artifact가 어디서·언제·어떻게 만들어졌는지 추적하는 구체적 형식입니다.

하지만 서명은 발행자와 Payload 무결성을 검증할 뿐, 평가 결론의 진실성이나 현재 유효성을 보장하지 않습니다. SLSA도 Software Build Supply Chain을 직접 대상으로 하므로 AI 품질·안전 판단에는 Prompt·Tool·Dataset·Evaluator용 Custom Predicate와 별도의 Claim 논리가 필요합니다.

<a id="ai-section-10"></a>

## 10. 변경 이벤트를 정규화해 누락 없이 수집한다

Evidence Lifecycle의 입력은 Git Commit만이 아닙니다.

| Event Class | 예 | 주요 Source |
|---|---|---|
| Release | Code·Prompt·Model Route·Tool·Knowledge·Policy 변경 | CI/CD·Release Ledger |
| Runtime | 권한·Feature Flag·Region·Dependency 설정 변경 | Control Plane·CMDB |
| Evaluation | Dataset·Label·Evaluator·Threshold 변경 | Evaluation Registry |
| Security | 취약점·Credential 노출·Red Team Finding | Scanner·SIEM·Finding System |
| Operations | Drift·오류율·Override 증가·Incident | Telemetry·Incident System |
| Governance | 법규·내부 Policy·Risk Tolerance·승인자 변경 | GRC·Policy Registry |

정규 Event Envelope은 Producer마다 다른 형식을 Graph가 이해할 수 있는 공통 표현으로 바꿉니다.

```json
{
  "event_id": "CHG-20260819-017",
  "event_type": "PROMPT_BUNDLE_CHANGED",
  "subject_type": "prompt-bundle",
  "before_digest": "sha256:18b2...",
  "after_digest": "sha256:7f44...",
  "release_before": "sha256:8c31...",
  "release_after": "sha256:cc09...",
  "changed_paths": ["prompts/tool-selection.yaml"],
  "occurred_at": "2026-08-19T06:15:00Z",
  "source": "release-ledger",
  "correlation_id": "REL-20260819-04"
}
```

변경 설명을 자유 텍스트로만 남기면 자동 영향 분석이 어렵습니다. `before/after digest`, 변경 Subject Type, Release, 발생 시각과 상관관계 ID를 구조화합니다.

<a id="ai-section-11"></a>

## 11. 의존 그래프로 변경 영향 범위를 계산한다

<img src="assets/blog-92-change-impact-revalidation-graph.png" alt="Prompt 변경 이벤트가 Subject Graph와 Predicate를 거쳐 금지 행동·도구 선택 Claim에만 재검증을 요구하고 데이터 보존 Claim의 기존 증거는 재사용하는 변경 영향 분석 그래프" width="470" />

영향 분석은 파일 경로 목록이 아니라 의미 관계를 따라야 합니다.

```text
Release CONTAINS Prompt Bundle
Evidence EVALUATED Prompt Bundle
Evidence USED Dataset
Evidence PRODUCED_BY Evaluator
Evidence SUPPORTS Claim
Claim REQUIRED_BY Decision
Finding CONTRADICTS Claim
Decision AUTHORIZES Runtime Scope
```

Prompt Digest가 바뀌면 다음 순서로 탐색합니다.

1. 이전 Prompt를 직접 평가한 Evidence를 찾습니다.
2. 그 Evidence가 지지·반박하는 Claim을 찾습니다.
3. 변경된 Prompt 영역과 Evidence Predicate의 관련성을 규칙으로 확인합니다.
4. 영향 Claim의 유효한 대체 Evidence와 Coverage를 다시 계산합니다.
5. Claim을 요구하는 Decision과 현재 Runtime Scope를 찾습니다.
6. 재검증이 끝날 때까지 Decision을 `HOLD` 또는 더 좁은 조건부 범위로 전이합니다.

Graph Traversal의 깊이를 무한히 늘리면 모든 변경이 모든 Claim에 도달합니다. Edge Type, Predicate, Context, Release Lineage와 Stop Rule을 사용해 전파 경계를 명확히 해야 합니다.

<a id="ai-section-12"></a>

## 12. 무효화 규칙은 Event·Edge·Predicate로 작성한다

좋은 규칙은 “무언가 바뀌면 다시 테스트”가 아니라 어떤 변경이 어떤 Evidence에 왜 영향을 주는지 설명합니다.

```yaml
rule_id: IRS-PROMPT-TOOL-01
when:
  event_type: PROMPT_BUNDLE_CHANGED
  changed_path_matches:
    - prompts/tool-selection/**
traverse:
  subject_edges: [EVALUATED, USED_BY]
affects_predicates:
  - tool-selection-accuracy/*
  - prohibited-effect-control/*
  - human-approval-routing/*
transition:
  evidence_status: STALE
  claim_status: PARTIAL
gate_action: HOLD_IF_NO_ACTIVE_ALTERNATIVE
required_revalidation:
  - suite: tool-trajectory-regression
  - suite: prohibited-effect-red-team
```

대표 규칙은 다음처럼 시작할 수 있습니다.

| 변경 또는 발견 | 기본 영향 | 예외 조건 |
|---|---|---|
| Subject Digest 변경 | 그 Subject를 평가한 Evidence → STALE | Predicate가 변경 영역과 무관하다고 증명 |
| Evaluator 결함 발견 | 해당 Evaluator가 만든 결과 → REVOKED | 결함 발생 전·후 범위가 명확히 분리됨 |
| Dataset Label 수정 | 해당 Version을 사용한 결과 → STALE 또는 REVOKED | 수정 Slice가 Claim Coverage 밖임 |
| Critical Finding 확인 | 반박 Claim → DEFEATED 가능 | 승인된 완화가 효과 Evidence로 검증됨 |
| Policy Threshold 강화 | 새 기준 미평가 Claim → PARTIAL | 원시 결과로 새 기준을 재계산 가능하고 방법이 동등함 |
| `valid_until` 도달 | Evidence → EXPIRED | 없음, 새 승인 또는 재검증 필요 |

자동 규칙에는 버전, 승인자, 발효 시각, 테스트 Fixture와 Rollback이 필요합니다. 잘못된 규칙 하나가 모든 Evidence를 만료시키거나 필요한 전파를 막을 수 있기 때문입니다.

<a id="ai-section-13"></a>

## 13. 최소 재검증은 영향받은 Claim의 공백만 채운다

최소 재검증의 목적은 테스트 수를 줄이는 것이 아니라 **현재 Assurance Case의 공백을 가장 작은 신뢰 가능한 평가 집합으로 채우는 것**입니다.

먼저 각 Claim의 Evidence Requirement를 정의합니다.

```yaml
claim_id: CLM-TOOL-01
requirements:
  - predicate: prohibited-effect-control/v2
    minimum_coverage:
      critical_tools: 100%
      tenant_slices: [pilot-kr-01, pilot-kr-02]
      identity_profiles: [employee-standard, contractor-limited]
    maximum_age: P14D
    independent_issuer_required: true
  - predicate: runtime-side-effect-monitoring/v1
    observation_window: P7D
```

그다음 `ACTIVE` Evidence로 충족되는 부분을 빼고 남은 공백을 계산합니다.

```text
Required Coverage
  − Active Applicable Evidence Coverage
  + Contradiction Resolution
  + Mandatory Regression Set
  = Revalidation Plan
```

최소화하면 안 되는 영역도 있습니다.

- 법규·계약·내부 Policy가 매 Release 또는 정기 평가를 요구하는 항목
- 피해 영향이 크고 변경과의 독립성을 증명하기 어려운 Critical Control
- Evaluator 자체가 바뀌어 결과의 동등성을 확인할 수 없는 경우
- Incident 원인이 아직 규명되지 않은 범위
- Model Provider가 Snapshot을 식별하지 않아 변경 범위를 좁힐 수 없는 경우

이때는 전체 또는 넓은 회귀 평가가 합리적입니다. “최소”는 비용 최적화 목표가 아니라 증거 충분성을 만족하는 하한입니다.

<a id="ai-section-14"></a>

## 14. 기존 증거 재사용에는 명시적인 안전 조건이 필요하다

재사용은 기본값이 아니라 다음 조건을 모두 확인한 결과여야 합니다.

- Evidence Subject가 변경되지 않았거나, 변경과 Predicate의 독립성이 입증됐습니다.
- Target Context가 기존 Coverage 안에 포함됩니다.
- Freshness와 `valid_until`이 남아 있습니다.
- Issuer와 Evaluator가 여전히 신뢰 상태입니다.
- 활성 Revocation과 미해결 Counter-evidence가 없습니다.
- 평가 방법·Threshold·Policy가 현재 요구사항과 동등합니다.
- 재사용 판단의 규칙 ID와 이유가 Decision Log에 남습니다.

```yaml
reuse_decision:
  evidence_id: EVD-RETENTION-0031
  target_release: sha256:cc09...
  result: REUSED
  reason: >
    변경은 Prompt의 tool-selection 영역에 한정되며,
    본 Evidence의 Predicate는 storage-retention-control/v1이고
    Storage Config·Policy·Runtime Digest가 이전 Release와 동일하다.
  rule_id: REUSE-INDEPENDENT-SUBJECT-02
  decided_at: 2026-08-19T06:24:00Z
```

“코드가 조금만 바뀌었다”는 재사용 근거가 아닙니다. 무엇이 동일하고 왜 해당 Claim에 영향을 주지 않는지를 기계와 사람이 함께 검토할 수 있어야 합니다.

<a id="ai-section-15"></a>

## 15. Evidence Pipeline을 Release Gate에 연결한다

<img src="assets/blog-92-continuous-evidence-pipeline.png" alt="평가·Scanner·Monitor가 만든 Evidence를 격리 검증하고 Registry와 Claim Graph에 연결한 뒤 Release Gate와 Runtime Monitor가 변경 영향과 재검증을 순환시키는 지속 증거 파이프라인" width="330" />

권장 Pipeline은 다음 책임을 분리합니다.

| 구성요소 | 책임 | 실패 시 기본 동작 |
|---|---|---|
| Evidence Producer | 평가·Scan·관측 결과 생성 | 결과 없음으로 처리, 성공 추정 금지 |
| Ingestion·Quarantine | Schema·Digest·중복·Malware 검사 | 격리 |
| Trust Verifier | 서명·Issuer·Attestation 검증 | `REJECTED` |
| Evidence Registry | Artifact·Metadata·상태 Event 보존 | Gate는 보수적 실패 |
| Claim Graph | 적용 가능성·Coverage·상충 계산 | 해당 Claim `UNKNOWN/PARTIAL` |
| Invalidation Engine | 변경·사고·만료 Event 전파 | 영향 Decision 재판정 |
| Revalidation Planner | 부족 Predicate·Slice를 실행 계획으로 변환 | 자동 실행 또는 Owner 할당 |
| Decision Service | Risk Policy와 Claim으로 Gate 판정 | `HOLD` 기본 |

Release Gate는 단순히 모든 평가 Job의 종료 코드만 보지 않습니다.

```text
APPROVE only if
  required_claims == SUPPORTED
  AND no unresolved critical defeater
  AND evidence_coverage >= policy threshold
  AND all required evidence is usable
  AND residual_risk_acceptance is active
  AND approval.valid_until > planned_exposure_end
```

Pipeline 장애가 곧 Agent 서비스 장애를 의미할 필요는 없습니다. 다만 새로운 배포 승인을 멈추고, 현재 운영은 마지막 유효 Decision의 범위와 만료 조건 안에서만 지속해야 합니다.

<a id="ai-section-16"></a>

## 16. 동시 변경과 중복 이벤트에도 판정이 흔들리지 않게 한다

현실에서는 Prompt 변경 직후 Policy 변경과 Incident가 동시에 들어올 수 있습니다. 다음 제어가 없으면 늦게 끝난 평가가 더 새로운 변경을 덮어쓰는 Race Condition이 생깁니다.

- **Idempotency Key**: 같은 Event를 여러 번 받아도 상태 전이는 한 번만 적용합니다.
- **Monotonic Revision**: Decision은 자신이 평가한 Graph Revision보다 오래된 상태에 기록할 수 없습니다.
- **Subject Digest Lock**: 재검증 결과는 계획에 고정된 Subject Digest에만 연결합니다.
- **Optimistic Concurrency**: 상태 변경 시 이전 Version이 같을 때만 Commit합니다.
- **Event-time 처리**: 수신 순서가 아니라 발생 시각과 Causality를 함께 봅니다.
- **Debounce Window**: 연속 변경을 하나의 Release Candidate로 묶되 Critical Revocation은 지연하지 않습니다.

```text
Plan subject = Release R12
평가 중 Release R13 생성
R12 평가 완료
  → R13의 Evidence로 승격 금지
  → R12 전용 Evidence로 등록
  → R13은 별도 Impact Analysis 수행
```

`latest`에 평가 결과를 붙이는 구현은 금지해야 합니다. 결과가 생성된 순간 `latest`가 다른 Release일 수 있습니다.

<a id="ai-section-17"></a>

## 17. Runtime Drift와 Incident가 즉시 Claim에 도달하게 한다

NIST AI RMF Playbook은 운영 중 기능과 행동을 모니터링하고, 운영 Metric이 배포 전 시험과 어떻게 달라지는지 문서화하는 방안을 제시합니다. 이는 자발적 실무 지침이며 현재 AI RMF 1.0은 개정 중입니다. NIST AI 600-1도 Generative AI의 배포 중 역량·한계 관찰과 Incident 관련 관행을 다룹니다.

운영 Signal을 Dashboard에만 남기지 말고 Evidence와 Trigger로 승격합니다.

| Runtime Signal | Evidence | Trigger 예 |
|---|---|---|
| 승인 우회 시도 증가 | Trajectory·Policy Decision Log | Critical Threshold 초과 시 Claim PARTIAL |
| Tool Side Effect 불일치 | Effect Ledger·Reconciliation | 1건이라도 확인 시 즉시 HOLD |
| RAG Source 분포 변화 | Retrieval Trace·Corpus Drift | 승인 Corpus Coverage 이탈 시 STALE |
| Human Override 증가 | Decision·Override Log | Rolling Baseline 대비 상승 시 재평가 |
| 새로운 Prompt Injection 유형 | Finding·Reproduction Artifact | 관련 Red Team Evidence REVOKED/STALE |

EU AI Act의 Article 72는 고위험 AI System Provider에게 수명주기 동안 성능 관련 데이터를 적극적·체계적으로 수집·문서화·분석하는 사후 모니터링 체계를 요구합니다. Article 12는 고위험 AI의 자동 Log 기록 역량을 다룹니다. 적용 대상과 의무는 System 역할·위험 분류·관할과 시행 시점에 따라 달라지므로, 이 글의 Pipeline을 법적 적합성의 충분조건으로 해석하면 안 됩니다.

<a id="ai-section-18"></a>

## 18. 보존·삭제·Legal Hold를 유효성과 분리한다

`valid_until`이 지났다고 Artifact를 삭제하면 과거 Decision을 재구성할 수 없습니다. 반대로 보존 기간이 남았다고 현재 Gate에 사용할 수 있는 것도 아닙니다.

| 시간 개념 | 질문 | 예시 |
|---|---|---|
| Freshness Window | 지금 Claim 판정에 충분히 최근인가 | 운영 Drift Evidence 24시간 |
| Validity | 언제까지 사용 가능하다고 승인했는가 | `valid_until` 14일 |
| Retention | 감사·계약·분쟁 대응을 위해 얼마나 보존하는가 | 1년·3년 등 조직 정책 |
| Legal Hold | 정상 삭제를 중단해야 하는가 | 사고 조사·소송 보존 |

개인정보나 기밀 입력이 Evidence Artifact에 포함된다면 무기한 보존도 위험합니다. 원본 Payload와 판정 Metadata를 분리하고, 최소 수집·암호화·접근 통제·지역성·삭제 증명을 설계합니다. 필요한 경우 원문 대신 Digest, 비식별화된 Sample, 재현 가능한 Query와 접근 승인 기록을 보존합니다.

NIST OSCAL Assessment Results는 Assessment의 범위·시각·활동·관찰·Finding·Risk와 관련 Evidence를 기계 판독 가능한 구조로 표현하고, 결과 만료도 모델링할 수 있는 패턴을 제공합니다. 다만 OSCAL은 보안·개인정보 통제 평가를 주된 범위로 하므로 AI Assurance 전체를 대신하는 표준은 아닙니다.

<a id="ai-section-19"></a>

## 19. 운영 지표는 증거 수보다 판정 지연과 공백을 본다

Evidence 파일 수가 많다는 것은 통제가 강하다는 뜻이 아닙니다. 다음 지표가 운영 품질을 더 잘 보여줍니다.

| 지표 | 계산 예 | 의미 |
|---|---|---|
| Active Coverage Ratio | 충족된 필수 Predicate·Slice / 전체 필수 Predicate·Slice | 현재 Claim의 증거 공백 |
| Invalidation Latency | 변경 발생 → 관련 Evidence 상태 전이 | 위험 노출 시간 |
| Revalidation Lead Time | 재검증 요청 → Decision 재판정 | 변경 처리 속도 |
| Reuse Ratio | 안전하게 재사용한 Requirement / 전체 Requirement | 선택적 재검증 효율 |
| False Invalidation Rate | 검토 결과 영향 없음 / 전체 무효화 | 규칙의 과대 전파 |
| Missed Impact Count | Incident 후 뒤늦게 발견된 미전파 Claim | 규칙의 치명적 누락 |
| Expired-in-Use Count | 만료 Evidence를 참조한 활성 Decision | Gate 결함 |
| Revocation Propagation Time | 철회 → 모든 Decision 반영 | Counter-evidence 대응력 |

`Reuse Ratio`만 높이면 위험합니다. `Missed Impact Count`와 함께 봐야 합니다. 또한 평균 Revalidation 시간보다 Critical Claim의 상위 백분위 지연이 중요합니다.

권장 SLO 예시는 다음과 같지만 실제 수치는 업무 영향과 운영 역량으로 정합니다.

```text
Critical Revocation의 Decision 반영: 수분 단위
Critical Release 변경의 Impact Analysis: CI Gate 안에서 완료
Expired-in-Use Count: 0
모든 활성 Decision의 Evidence Coverage 조회 가능: 100%
```

<a id="ai-section-20"></a>

## 20. 합성 사례로 Prompt 변경의 최소 재검증을 계산한다

회의 후속조치 Agent `R12`가 다음 Claim으로 Pilot 승인을 받았다고 가정합니다.

| Claim | 내용 | 주요 Evidence |
|---|---|---|
| C1 | 외부 전송은 사람의 단건 승인 없이는 실행되지 않는다 | Policy Test·Effect Ledger |
| C2 | 허용된 Tool을 정확한 순서와 인자로 호출한다 | Trajectory·Tool Evaluation |
| C3 | 회의 원문은 30일 후 삭제되고 Audit Metadata만 보존한다 | Storage Config·Deletion Test |
| C4 | 회의 참석자 Tenant 밖의 지식을 검색하지 않는다 | RAG Isolation Test |

`R13`에서 `prompts/tool-selection.yaml`만 변경됐습니다. Model Route, Tool Contract, Storage, RAG Corpus, Policy Digest는 같습니다.

### 1단계: 직접 영향

- Prompt를 Subject로 평가한 C2 Evidence → `STALE`
- Prompt와 Policy 상호작용을 시험한 C1의 일부 Evidence → `STALE`
- Storage와 RAG의 불변 Subject만 평가한 C3·C4 Evidence → 재사용 후보

### 2단계: Coverage 공백

- C1: 승인 우회·금지 Side Effect Scenario가 비었습니다.
- C2: Tool 선택·인자·순서 전체 Slice가 비었습니다.
- C3·C4: Subject·Context·Freshness가 동일하고 활성 Evidence가 남습니다.

### 3단계: 재검증 계획

```yaml
target_release: R13
run:
  - prohibited-effect-red-team
  - human-approval-routing-regression
  - tool-trajectory-critical-slices
reuse:
  - storage-retention-control: EVD-RETENTION-0031
  - rag-tenant-isolation: EVD-RAG-0142
gate:
  hold_claims: [C1, C2]
  provisional_reuse: [C3, C4]
  decision: HOLD
```

### 4단계: 재판정

새 평가가 C1·C2의 필수 Coverage를 충족하고 Critical Finding이 없으면 R13의 Evidence를 `ACTIVE`로 연결합니다. R12 Evidence를 R13으로 옮겨 붙이지 않습니다. C3·C4는 재사용 Decision과 독립성 근거를 남깁니다. 최종 Decision은 R13 Digest, Pilot 범위, 만료일을 새로 기록합니다.

이 방식은 전체 회귀 평가보다 작지만, 단순한 Changed-file Test보다 강합니다. 변경 파일이 아니라 Claim과 Predicate의 공백을 기준으로 범위를 정했기 때문입니다.

<a id="ai-section-21"></a>

## 21. 실패하기 쉬운 Evidence Lifecycle 안티패턴을 피한다

| 안티패턴 | 문제 | 개선 |
|---|---|---|
| 모든 증거 30일 TTL | 위험·변동성 차이를 무시 | 위험 기반 TTL + Event Trigger |
| 서명 검증 통과 = 신뢰 | 내용 타당성·현재 적용성을 혼동 | 무결성·Provenance·충분성 분리 |
| 변경마다 전체 재평가 | 비용·Lead Time 폭증 | Claim Graph 기반 최소 재검증 |
| Git Diff만으로 영향 분석 | Model·Policy·운영 Drift 누락 | 다중 Event Source와 의미 Edge |
| PASS 결과만 Registry에 저장 | 반증과 Inconclusive 은폐 | Verdict와 상태를 분리해 모두 보존 |
| 오래된 증거를 삭제 | 과거 Decision 재구성 불가 | 유효성과 Retention 분리 |
| 최신 Evidence로 자동 교체 | Context·Coverage가 다른 결과 혼합 | 명시적 `SUPERSEDES` 조건 |
| 평가 중 `latest` Release 참조 | 결과가 다른 Subject에 연결 | 계획 시 Digest 고정 |
| Pipeline 장애 시 자동 승인 | 증거 부재를 성공으로 오인 | Fail-closed Gate·제한 운용 |
| Confidence 점수 하나로 승인 | Coverage·상충·Risk Acceptance 은폐 | Claim별 Evidence와 Decision 분리 |

가장 위험한 안티패턴은 “평가가 실행됐다”를 “현재 Release가 입증됐다”로 바꾸는 것입니다. Job 성공은 Evidence Producer의 실행 상태일 뿐 Assurance 결론이 아닙니다.

<a id="ai-section-22"></a>


**실제 사례 — 이 블로그에서 겪은 재현 실패 (2026년 9월)**

2026년 9월 1일, 이 블로그 글 94편이 서로 겹치는지 TF-IDF 유사도로 재고 "통합할 대상 없음"으로 판정했습니다. 요약표에는 최대 0.402가 적혔고, 가장 비슷한 쌍으로 [/63](https://aiarchitect.tistory.com/63)↔[/68](https://aiarchitect.tistory.com/68)(0.332)을 검토했습니다. 그런데 그 측정을 수행한 스크립트를 남기지 않았습니다.

3주 뒤 결론이 유효한지 확인하려고 측정을 다시 만들었습니다. /63↔/68은 0.327로 기록과 사실상 같았지만, **가장 비슷한 쌍은 [/42](https://aiarchitect.tistory.com/42)↔[/43](https://aiarchitect.tistory.com/43)의 0.382였고 /63↔/68은 5위였습니다.** 0.402를 만든 전처리는 끝내 특정하지 못했습니다.

결론 자체는 유지됐습니다. 4,371쌍의 중앙값이 0.061이고, 최고 쌍도 같은 주제를 Android와 iOS로 나눠 쓴 의도된 연작이었기 때문입니다. 그러나 **결론이 유지되는 것과 근거를 재구성할 수 있는 것은 다릅니다.** 재생성이 안 되면 무엇이 달라졌는지 비교할 기준이 없습니다.

그래서 이후 측정은 결과가 아니라 스크립트로 남깁니다. **Evidence Lifecycle의 첫 조건은 TTL이 아니라 재생성 가능성입니다.**

## 22. 네 단계로 증거 수명주기를 도입한다

### 1단계: Inventory와 수명 필드 정리

- Critical Claim과 현재 Evidence를 연결합니다.
- Subject Digest, Issuer, Coverage, `issued_at`, `valid_until`을 채웁니다.
- `verdict`와 `status`를 분리합니다.
- 만료됐거나 대상을 식별할 수 없는 Evidence를 먼저 찾습니다.

### 2단계: Release 변경 Trigger 자동화

- Code·Prompt·Model·Tool·Knowledge·Policy 변경 Event를 수집합니다.
- Critical Subject 변경에 대한 보수적 무효화 규칙부터 시작합니다.
- Release Gate가 `STALE/EXPIRED/REVOKED` Evidence를 거부하게 합니다.

### 3단계: Graph 기반 선택 재검증

- Evidence Requirement와 Coverage Slice를 구조화합니다.
- 영향받은 Claim과 부족 Predicate를 계산합니다.
- 재사용 Decision과 최소 재검증 계획을 감사 로그로 남깁니다.
- False Invalidation과 Missed Impact를 검토해 규칙을 개선합니다.

### 4단계: Runtime Continuous Assurance

- Drift·Finding·Incident·Policy Event를 같은 경로로 연결합니다.
- Revocation이 활성 Decision과 Control Plane에 즉시 전파되게 합니다.
- Decision 만료·조건부 승인·Kill Switch를 자동화합니다.
- 정기 Tabletop Exercise로 누락과 Race Condition을 검증합니다.

처음부터 전사 Evidence Graph를 만들 필요는 없습니다. 피해 영향이 큰 두세 개 Claim과 하나의 Agent Release Line부터 시작해, 실제 변경과 사고를 통해 Edge와 규칙을 검증하는 편이 안전합니다.

<a id="ai-section-23"></a>

## 23. 마무리 — 지속 검증은 전체 재시험이 아니라 근거의 연속성이다

AI Agent는 Code만 바뀌는 Software가 아닙니다. Model Route, Prompt, Tool, RAG Corpus, Memory, Policy, Identity와 운영 환경이 독립적으로 변합니다. 따라서 한 번 만든 평가 보고서와 승인 문서는 빠르게 현실과 멀어질 수 있습니다.

Evidence Lifecycle의 핵심은 세 문장으로 정리할 수 있습니다.

1. Evidence를 불변 Subject·Context·Claim·Decision에 바인딩합니다.
2. 시간·변경·Drift·Incident·반증을 명시적 상태 전이로 전파합니다.
3. 영향받은 Claim의 Coverage 공백만 신뢰 가능한 방법으로 다시 검증합니다.

좋은 Continuous Assurance는 모든 테스트를 매번 다시 돌리는 시스템이 아닙니다. **어떤 근거가 왜 낡았고, 무엇은 아직 재사용할 수 있으며, 어떤 재검증이 끝나야 어느 범위의 운영을 승인할 수 있는지**를 끊김 없이 설명하는 시스템입니다.

<a id="ai-section-24"></a>

## 24. 공식 참고자료

- [W3C PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Entity·Activity·Agent와 생성·사용·파생·무효화 관계를 표현하는 W3C Recommendation
- [in-toto Attestation Framework Specification](https://github.com/in-toto/attestation/blob/main/spec/README.md) — Predicate·Statement·Envelope·Bundle로 Attestation을 구성하는 공식 사양
- [in-toto Attestation v1.2 Envelope](https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md) — Statement Payload의 직렬화와 인증·서명 Envelope
- [SLSA Specification 1.2](https://slsa.dev/spec/v1.2/) — Software Supply Chain Integrity의 Track·Level·Attestation Format
- [SLSA Provenance](https://slsa.dev/spec/v1.2/provenance) — Artifact가 어디서·언제·어떻게 생성됐는지 표현하는 Provenance 형식
- [NIST OSCAL Assessment Results](https://pages.nist.gov/OSCAL/learn/concepts/layer/assessment/assessment-results/) — Assessment 범위·활동·관찰·Finding·Risk·Evidence를 구조화하는 공식 개념 설명
- [NIST OSCAL 1.2.3 Assessment Results JSON Reference](https://pages.nist.gov/OSCAL-Reference/models/v1.2.3/assessment-results/json-reference/) — Assessment Results 모델의 최신 공개 기계 판독 Reference
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) — AI RMF 1.0과 현재 개정 상태를 안내하는 공식 페이지
- [NIST AI RMF Playbook](https://airc.nist.gov/airmf-resources/playbook/) — Govern·Map·Measure·Manage Outcome을 위한 자발적 Suggested Action
- [NIST AI RMF Playbook — Manage](https://airc.nist.gov/airmf-resources/playbook/manage/) — 배포·운영·모니터링과 Risk 대응 관련 Suggested Action
- [NIST AI 600-1: Generative Artificial Intelligence Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) — Generative AI Risk 관리와 배포 중 TEVV·Incident 관련 공식 Profile
- [ISO/IEC 42001:2023](https://www.iso.org/standard/42001) — AI Management System의 수립·구현·유지·지속 개선 요구사항
- [ISO/IEC 42005:2025](https://www.iso.org/standard/44545.html) — AI System Impact Assessment의 수행과 문서화를 위한 국제표준
- [Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=en) — 고위험 AI의 Record-keeping, Post-market Monitoring과 Serious Incident Reporting을 포함하는 EU 공식 법령 원문

---

*이 글은 기업 AI Agent 아키텍처 설계를 위한 기술 자료입니다. 특정 시스템의 안전성·법적 적합성·인증을 보장하지 않으며, 실제 적용 시 조직의 Risk Tolerance와 관할 법규, 계약, 보안·개인정보 정책 및 독립 검증 결과를 함께 검토해야 합니다.*
