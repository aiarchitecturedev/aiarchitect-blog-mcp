# 기업 AI Agent 도입 검증 체크리스트: Assurance Case와 Evidence Graph 설계

기업 AI Agent 도입 심사에서 항목을 전부 통과했는데도 운영 승인을 내리기 어려울 때가 있습니다. 체크 표시는 누가 무엇을 근거로 판단했는지, 그 근거가 지금도 유효한지를 남기지 않기 때문입니다. 이 글은 AI 거버넌스 판정을 주장·논거·반증·증거로 구성하는 Assurance Case와 Evidence Graph의 Subject Digest·출처·서명·신선도·Coverage·독립성, 릴리스 Gate와 잔여 위험 승인 설계를 정리합니다.

![기업 AI Agent의 검증 주장과 평가·정책·출처·승인 증거가 그래프로 연결되고 반증이 발견되면 운영 승인을 중단하는 Assurance Case 아키텍처](assets/blog-91-ai-agent-assurance-case-evidence-graph-hero.png)

<blockquote id="aiarchitect-toc" data-ke-style="box" style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;" data-mce-style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;">
<p style="color: #263746; font-weight: 700;" data-mce-style="color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 700;"><b>목차</b></p>
<ol style="list-style-type: decimal; color: #555555; font-weight: 400;" data-mce-style="list-style-type: decimal; color: #555555; font-weight: 400;" data-ke-list-type="decimal">
<li><a href="#ai-section-1" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">체크리스트를 모두 채워도 운영 승인의 근거는 부족할 수 있다</a></li>
<li><a href="#ai-section-2" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Assurance Case·Risk Register·Compliance·Evidence Graph의 경계를 나눈다</a></li>
<li><a href="#ai-section-3" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">기존 거버넌스 글을 하나의 도입 검증 허브로 연결한다</a></li>
<li><a href="#ai-section-4" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">최상위 주장은 System·Release·Context·Time을 고정한다</a></li>
<li><a href="#ai-section-5" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">업무 피해와 불변식에서 하위 주장을 도출한다</a></li>
<li><a href="#ai-section-6" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Claim·Argument·Evidence·Decision을 분리한다</a></li>
<li><a href="#ai-section-7" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Context·Assumption·Justification을 숨기지 않는다</a></li>
<li><a href="#ai-section-8" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Defeater와 Counter-evidence를 정상 입력으로 취급한다</a></li>
<li><a href="#ai-section-9" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">좋은 Evidence의 일곱 가지 품질을 검증한다</a></li>
<li><a href="#ai-section-10" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Examine·Interview·Test의 역할과 한계를 구분한다</a></li>
<li><a href="#ai-section-11" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Evidence Graph는 표준 제품명이 아니라 구현 패턴이다</a></li>
<li><a href="#ai-section-12" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Evidence Node를 Subject·Predicate·Issuer에 바인딩한다</a></li>
<li><a href="#ai-section-13" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">W3C PROV로 Entity·Activity·Agent의 출처를 표현한다</a></li>
<li><a href="#ai-section-14" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Digest와 Attestation으로 증거 대상과 무결성을 확인한다</a></li>
<li><a href="#ai-section-15" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">서명은 진실이 아니라 발행자와 무결성을 증명한다</a></li>
<li><a href="#ai-section-16" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Freshness·Expiry·Revocation으로 증거 수명을 관리한다</a></li>
<li><a href="#ai-section-17" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Coverage와 Unsupported Claim을 PASS에서 분리한다</a></li>
<li><a href="#ai-section-18" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">충돌하는 증거를 평균으로 지우지 않는다</a></li>
<li><a href="#ai-section-19" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Confidence Score를 근거 없는 확률처럼 사용하지 않는다</a></li>
<li><a href="#ai-section-20" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Residual Risk Acceptance에 범위·책임·만료를 둔다</a></li>
<li><a href="#ai-section-21" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">그래프 질의로 누락·만료·영향 범위를 찾는다</a></li>
<li><a href="#ai-section-22" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">Assurance Decision을 Release Gate에 연결한다</a></li>
<li><a href="#ai-section-23" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">변경·사고·Drift가 영향을 받은 주장만 무효화한다</a></li>
<li><a href="#ai-section-24" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">표준·법규 매핑은 적합성 보증과 구분한다</a></li>
<li><a href="#ai-section-25" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">합성 사례로 회의 후속조치 Agent를 판정한다</a></li>
<li><a href="#ai-section-26" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">도입·Pilot·운영 승인 체크리스트를 Evidence에 묶는다</a></li>
<li><a href="#ai-section-27" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">자주 실패하는 Assurance 안티패턴을 피한다</a></li>
<li><a href="#ai-section-28" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">네 단계로 Assurance Case를 도입한다</a></li>
<li><a href="#ai-section-29" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">마무리 — 좋은 검증은 결론보다 추적 가능한 이유를 남긴다</a></li>
<li><a href="#ai-section-30" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">공식 참고자료</a></li>
</ol>
</blockquote>

도입 검토 문서에는 흔히 수십 개의 체크 항목이 있습니다. 데이터 준비, API 연결, 권한, 품질, 보안, 운영 조직을 모두 `완료`로 표시합니다. 그런데 승인 회의에서 다음 질문이 나오면 답이 끊깁니다.

```text
어느 Agent Release에 대한 결과인가?
평가 Dataset과 Policy가 바뀌어도 이 결론은 유효한가?
테스트가 실제 운영 권한과 Side Effect를 포함했는가?
상충하는 Red Team Finding은 왜 승인 판단에서 제외됐는가?
누가 어떤 근거로 잔여 위험을 수용했는가?
이 증거는 언제 만료되고 무엇이 바뀌면 재검증하는가?
```

체크리스트는 확인할 항목을 빠뜨리지 않는 데 유용하지만, 항목 사이의 논리와 증거의 유효성을 스스로 설명하지 않습니다. Evidence 파일이 많다고 결론이 강해지는 것도 아닙니다. 다른 Release를 시험한 결과, 만료된 정책 승인, 신뢰할 수 없는 검증기가 만든 보고서, 낮은 위험 Slice만 포함한 평균 점수는 현재 운영 승인을 지지하지 못합니다.

**Assurance Case**는 특정 주장이 왜 받아들여질 수 있는지를 논거와 증거, 명시적 가정으로 설명하는 감사 가능한 산출물입니다. **Evidence Graph**는 그 주장과 증거가 어떤 대상·활동·발행자·버전에 연결됐는지를 기계가 추적하도록 만든 구현 패턴입니다. 둘을 결합하면 “체크했는가”를 넘어 **무엇을, 어떤 조건에서, 어떤 증거로, 누가 승인했으며, 지금도 그 근거가 유효한가**를 판정할 수 있습니다.

이 글의 Agent, 회사, Release, Dataset, 수치, Identifier와 Policy는 모두 교육용 합성 예시입니다. 실제 도입 판단은 조직의 업무 영향, Risk Tolerance, 법무·보안·개인정보 정책, 산업 규제, 계약, 실제 평가와 운영 데이터를 기준으로 해야 합니다. 이 글은 법률 자문이나 인증 결과가 아닙니다.

<a id="ai-section-1"></a>

## 1. 체크리스트를 모두 채워도 운영 승인의 근거는 부족할 수 있다

체크리스트는 질문 목록입니다. Assurance Case는 결론까지 이어지는 이유의 구조입니다.

| 체크리스트가 알려주는 것 | Assurance Case가 추가로 설명할 것 |
|---|---|
| 평가 완료 | 어떤 Release·Dataset·Evaluator를 평가했는가 |
| 보안 검토 완료 | 어떤 위협·권한·Side Effect가 범위에 포함됐는가 |
| 승인 완료 | 승인자가 어떤 주장과 잔여 위험을 수용했는가 |
| 로그 수집 | 어떤 Claim을 지지하거나 반박하는 Evidence인가 |
| 운영 모니터링 | 어떤 Signal이 어느 Claim을 무효화하는가 |

예를 들어 `Tool 오용 테스트 통과`라는 체크는 다음 조건이 모두 확인돼야 운영 승인 근거가 됩니다.

- 시험 대상 Tool Contract Digest가 실제 Release와 일치합니다.
- 시험 Identity와 Credential Scope가 운영과 같은 권한 경계를 재현합니다.
- 금지된 Side Effect가 응답 문구가 아니라 실제 Effect Ledger에서 0건입니다.
- Scenario가 Critical Tool과 Tenant·사용자·위험 Slice를 충분히 덮습니다.
- 검증기와 Dataset Version, 실행 시각, 결과 Artifact Digest가 남습니다.
- 미해결 Finding과 Inconclusive Result가 숨겨지지 않습니다.
- 이 결과가 지지하는 Claim과 만료 조건이 명확합니다.

따라서 체크리스트를 버리는 것이 아니라, 각 항목을 **Claim 또는 Evidence Requirement**로 승격하고 실제 Evidence Node에 연결합니다.

<a id="ai-section-2"></a>

## 2. Assurance Case·Risk Register·Compliance·Evidence Graph의 경계를 나눈다

네 개는 서로 보완하지만 같은 산출물이 아닙니다.

| 산출물 | 핵심 질문 | 포함 내용 | 단독으로 보장하지 않는 것 |
|---|---|---|---|
| Assurance Case | 왜 이 주장을 받아들일 수 있는가 | Claim·Argument·Evidence·Context·Assumption·Defeater | 모든 법규 적합성·무사고 |
| Risk Register | 어떤 위험을 어떻게 처리하는가 | 원인·영향·가능성·통제·Owner·Residual Risk | 통제가 실제 효과적이라는 증명 |
| Compliance Mapping | 어떤 요구사항에 어떻게 대응하는가 | 법규·표준 조항과 통제·Evidence 연결 | 시스템이 안전하거나 목적에 적합함 |
| Evidence Graph | 증거가 어디서 왔고 무엇과 연결되는가 | Subject·Digest·Activity·Issuer·Claim·Decision Edge | 논거의 타당성·증거의 충분성 |

ISO/IEC/IEEE 15026-2:2022는 Assurance Case의 구조와 용어 요구사항을 다루며, 특정 그래픽 표기나 물리적 구현을 강제하지 않습니다. Goal Structuring Notation(GSN)은 Claim과 Strategy, Context, Solution을 시각화하는 한 가지 방법이지만 Assurance Case와 동의어는 아닙니다.

W3C PROV-O는 Entity·Activity·Agent와 생성·사용·파생·책임 관계를 표현합니다. PROV 관계가 있다는 사실은 출처 추적을 돕지만, 그 Entity의 내용이 참이거나 Claim을 충분히 입증한다는 뜻은 아닙니다.

<a id="ai-section-3"></a>

## 3. 기존 거버넌스 글을 하나의 도입 검증 허브로 연결한다

BLOG-91은 앞선 글의 결과를 대체하지 않고 하나의 승인 논리로 조립합니다.

| 단계 | 핵심 질문 | 연결 글 | Assurance Case에서의 역할 |
|---|---|---|---|
| 도입 경로 | 무엇을 어떤 Stage Gate로 검증할 것인가 | [기업 AI Agent 도입 로드맵](https://aiarchitect.tistory.com/65) | Lifecycle Context·Gate Strategy |
| 업무 적합성 | 이 업무에 Agent가 필요한가 | [AI Agent 자동화 적합도 판정](https://aiarchitect.tistory.com/70) | 업무 목적·자동화 방식 Claim |
| 준비도 | 데이터·API·권한·보안·인수가 준비됐는가 | [AI Agent 도입 준비도 진단](https://aiarchitect.tistory.com/69) | Readiness Evidence·Negative Test |
| 품질 검증 | Outcome·Trajectory·Tool·RAG가 기준을 만족하는가 | [AI Agent 평가 아키텍처](https://aiarchitect.tistory.com/74) | Evaluation Evidence |
| 배포 판단 | 실제 Release를 어떤 범위로 노출할 것인가 | [AI Agent Release Governance](https://aiarchitect.tistory.com/87) | Release Subject·Promotion Decision |
| 공격·지속 검증 | 공격과 변경 후에도 통제가 유효한가 | [Red Teaming과 Continuous Assurance](https://aiarchitect.tistory.com/90) | Counter-evidence·Freshness Trigger |

도입 로드맵의 각 Gate가 `승인`이라는 Boolean만 남기면 다음 Gate에서 이유를 재구성해야 합니다. 반대로 각 Gate가 Claim과 Evidence를 남기면, Pilot과 운영 승인은 앞 단계의 근거를 재사용하면서 변경된 부분만 재검증할 수 있습니다.

<a id="ai-section-4"></a>

## 4. 최상위 주장은 System·Release·Context·Time을 고정한다

`이 Agent는 안전하다`는 주장은 검증할 수 없습니다. 안전의 대상·범위·시점이 빠졌기 때문입니다.

```yaml
top_claim:
  claim_id: CLM-OPERATE-001
  statement: >
    meeting-action-agent release rel-20260819-03은
    승인된 사내 회의 후속조치 업무에서 읽기와 초안 생성만 수행하고,
    외부 전송과 Ticket 상태 변경은 사람의 단건 승인을 거치며,
    2026-09-18T00:00:00Z까지 정의된 운영 통제와 잔여 위험 조건 아래
    Pilot Cohort에서 운영 승인 가능하다.
  subject:
    agent_release_digest: sha256:8c31...
    prompt_bundle_digest: sha256:18b2...
    tool_contract_digest: sha256:6d0a...
    policy_bundle_digest: sha256:991f...
    knowledge_snapshot_digest: sha256:a422...
  context:
    tenants: [pilot-kr-01, pilot-kr-02]
    task_classes: [meeting-summary, action-draft]
    prohibited_effects: [external-send-without-approval, ticket-delete]
  valid_until: 2026-09-18T00:00:00Z
```

최상위 주장에는 최소한 다음 경계가 필요합니다.

- **System**: Agent만이 아니라 Model Route, RAG, Memory, MCP Tool, A2A Agent, Policy와 Runtime Dependency를 포함합니다.
- **Release**: Alias가 아니라 불변 Revision과 Digest를 사용합니다.
- **Context**: Tenant, 사용자, 업무, 데이터 등급, 지역, Channel과 권한 범위를 고정합니다.
- **Time**: Evidence와 승인의 유효 기간을 둡니다.
- **Decision**: 전면 안전 선언이 아니라 허용된 운영 범위와 조건을 명시합니다.

Release Digest가 달라지면 같은 이름의 Agent라도 다른 판정 대상입니다. Context가 바뀌면 같은 Release라도 기존 Claim이 자동으로 확장되지 않습니다.

<a id="ai-section-5"></a>

## 5. 업무 피해와 불변식에서 하위 주장을 도출한다

Framework 항목을 그대로 Claim으로 복사하기보다, 보호할 Outcome과 업무 피해에서 하위 주장을 도출합니다.

```text
업무 피해: 승인되지 않은 외부 수신자에게 회의 내용 전송
  ↓
불변식: 외부 전송은 사용자 승인 Grant와 정확히 같은 수신자·내용 Digest에만 허용
  ↓
Claim: 실행 Gateway는 유효한 단건 Grant가 없는 외부 전송을 거부한다
  ↓
Evidence Requirement:
  - Policy Negative Test
  - 승인 Grant 재사용·변조 Test
  - 실제 Effect Ledger 0건
  - Runtime Deny Trace
```

권장 Claim 영역은 다음과 같습니다.

1. **Purpose and Fitness**: Agent가 의도한 업무 목적에 맞고 자율성 수준이 정당합니다.
2. **Readiness**: 데이터·연동·권한·보안·인수 조건이 검증 가능합니다.
3. **Quality and Validity**: Outcome과 Trajectory가 Slice별 인수 기준을 만족합니다.
4. **Authority and Effect Integrity**: 위임 권한과 Side Effect가 정책 범위를 벗어나지 않습니다.
5. **Security and Privacy**: 공격자 통제 입력과 데이터 흐름이 보호 경계를 우회하지 않습니다.
6. **Reliability and Recovery**: 장애를 탐지·중단·조정하고 안전 상태로 복구합니다.
7. **Operations and Accountability**: Trace·Audit·Owner·Incident·Change 절차가 작동합니다.

각 영역의 통과가 다른 영역의 실패를 상쇄하지 않도록 Critical Claim은 독립 Blocking Gate로 둡니다.

<a id="ai-section-6"></a>

## 6. Claim·Argument·Evidence·Decision을 분리한다

네 요소를 하나의 문장이나 JSON 객체로 합치면 순환 논리가 생기기 쉽습니다.

```text
Claim    : 무엇이 참이라고 주장하는가
Argument : 왜 하위 Claim과 Evidence가 그 주장을 지지하는가
Evidence : 어떤 관찰·시험·문서·영수증이 실제로 존재하는가
Decision : 누가 어떤 범위·조건·만료로 주장을 받아들였는가
```

![최상위 운영 승인 주장을 업무 목적·권한과 Side Effect·실패 복구 논거로 분해하고 평가·인가·Red Team 증거와 반증을 함께 판정하는 Assurance Case 구조](assets/blog-91-assurance-case-argument-structure.png)

*Assurance Case 구조 — Evidence가 많아도 논거가 없으면 결론으로 이어지지 않으며, 반증과 미해결 가정은 판정의 정식 입력입니다.*

잘못된 순환 예시는 다음과 같습니다.

```text
Claim: 안전하다.
Evidence: 안전성 검토에서 통과했다.
검토 기준: Claim이 안전하다고 승인됐는지 확인한다.
```

검증 가능한 구조는 관찰 가능한 하위 Claim으로 분해합니다.

```text
Top Claim
  ← Argument: 금지 Effect가 예방되고 실패 시 제한된 시간 안에 복구됨
      ← Subclaim A: 승인 없는 외부 전송은 Gateway에서 거부됨
          ← Evidence: Policy Test + Effect Ledger + Deny Trace
      ← Subclaim B: 우회 시도를 5초 안에 탐지함
          ← Evidence: Red Team Replay + Alert Timestamp
      ← Subclaim C: 오염된 Task와 Credential을 철회함
          ← Evidence: Incident Exercise + Revocation Receipt
```

<a id="ai-section-7"></a>

## 7. Context·Assumption·Justification을 숨기지 않는다

Evidence는 Context 밖에서 자동으로 일반화되지 않습니다.

| 요소 | 예시 | 잘못 숨겼을 때 생기는 오류 |
|---|---|---|
| Context | Pilot Tenant·한국어 회의·읽기/초안 업무 | 전체 Tenant·언어·쓰기 업무로 과도하게 확장 |
| Assumption | IdP가 사용자와 Tenant를 정확히 인증 | Identity 장애를 Agent 통제가 해결한다고 오판 |
| Justification | 외부 전송은 영향이 커 Human Approval을 Blocking Gate로 선택 | 왜 사람 승인이 필요한지 추적 불가 |

Assumption은 사실처럼 쓰지 않고 검증 가능성과 Owner를 둡니다.

```yaml
assumption:
  assumption_id: ASM-IDP-01
  statement: IdP가 subject와 tenant claim을 조직 정책에 따라 발급한다.
  owner: identity-platform
  verification: quarterly-access-control-assessment
  evidence_ref: EVD-IDP-2026Q3
  invalidation_triggers:
    - idp-claim-schema-change
    - issuer-key-rotation-failure
    - tenant-mapping-incident
```

검증되지 않은 Assumption이 Critical Claim을 지탱한다면 그 Claim은 `SUPPORTED`가 아니라 `UNSUPPORTED` 또는 `CONTESTED`로 남겨야 합니다.

<a id="ai-section-8"></a>

## 8. Defeater와 Counter-evidence를 정상 입력으로 취급한다

Assurance Case는 찬성 자료만 모으는 제안서가 아닙니다. 결론을 무너뜨릴 수 있는 조건을 먼저 찾습니다.

```yaml
defeater:
  defeater_id: DFT-AUTHZ-04
  challenges: CLM-AUTHZ-02
  statement: 승인 Grant가 만료된 뒤 Queue에서 지연된 Task가 실행될 수 있다.
  status: OPEN
  evidence_refs:
    - EVD-QUEUE-DELAY-TEST-17
  required_resolution:
    - execution-time-grant-revalidation
    - delayed-task-regression-test
```

Counter-evidence는 기존 Claim과 충돌하는 실제 관찰입니다.

- 평균 평가 점수는 통과했지만 특정 언어 Slice에서 금지 Tool 호출이 발생했습니다.
- Contract Test는 통과했지만 운영 Trace에서 더 넓은 Credential Scope가 관찰됐습니다.
- Red Team에서 실제 Effect는 차단됐지만 Goal Hijack이 탐지되지 않았습니다.
- Recovery Test는 통과했지만 RTO가 승인된 상한을 초과했습니다.

Critical Defeater가 열려 있거나 Counter-evidence가 해결되지 않으면 `APPROVE`로 올리지 않습니다. `PAUSE`, 범위 축소, Control 추가, 재검증 중 하나로 해소합니다.

<a id="ai-section-9"></a>

## 9. 좋은 Evidence의 일곱 가지 품질을 검증한다

Evidence가 존재한다는 사실과 채택할 수 있다는 판단을 분리합니다.

| 품질 | 검증 질문 | 실패 예시 |
|---|---|---|
| Relevance | 이 Evidence가 해당 Claim을 직접 지지하는가 | 일반 LLM Benchmark로 업무 Side Effect 안전성 주장 |
| Validity | 측정·시험 방법이 의도한 속성을 측정하는가 | 응답 문구만 보고 실제 Tool 실행 여부 판정 |
| Integrity | Artifact와 Subject가 변경되지 않았는가 | Digest 없이 덮어쓴 CSV |
| Provenance | 누가·무엇으로·어떤 입력에서 만들었는가 | 검증기·Dataset Version이 없는 PASS 보고서 |
| Freshness | 현재 Release와 Context에 아직 유효한가 | Tool Schema 변경 전 Contract Test |
| Coverage | 필요한 업무·권한·위험 Slice를 덮는가 | 읽기 Tool만 시험하고 쓰기 안전성 승인 |
| Independence | 작성·검증·승인 역할이 위험에 맞게 분리됐는가 | Release 작성자가 자기 결과만으로 Critical 승인 |

재현성도 중요하지만 비결정적 Agent에서 byte-for-byte 같은 출력만을 뜻하지 않습니다. 고정된 Release·Dataset·Evaluator·Seed·Trial 계약으로 같은 분포와 Blocking Invariant를 다시 평가할 수 있어야 합니다.

<a id="ai-section-10"></a>

## 10. Examine·Interview·Test의 역할과 한계를 구분한다

NIST SP 800-53A와 OSCAL Assessment Model은 통제 평가 활동을 이해하는 데 유용한 세 가지 방법을 제공합니다. 이 구조는 보안·Privacy 통제 평가용이며 AI 전체 Assurance를 대신하지 않지만 Evidence Method를 구분하는 데 활용할 수 있습니다.

| 방법 | 무엇을 확인하는가 | AI Agent 예시 | 한계 |
|---|---|---|---|
| Examine | 문서·설정·Artifact를 검사 | Policy Bundle, Tool Allowlist, Dataset Manifest | 선언과 실제 동작이 다를 수 있음 |
| Interview | 역할·절차·의사결정을 확인 | Incident Owner, Human Approval 운영자 | 자기보고·기억 편향 가능 |
| Test | 지정 조건에서 실제 동작을 실행 | 권한 우회, 장애 주입, 회귀 평가 | 시험하지 않은 Context로 일반화 불가 |

Critical Claim은 한 종류의 Evidence만으로 끝내지 않습니다. 예를 들어 Kill Switch Claim은 다음을 함께 봅니다.

- Examine: Kill Switch Policy와 대상 범위가 선언돼 있습니다.
- Interview: On-call이 발동 권한과 절차를 이해합니다.
- Test: 합성 Incident에서 실제 Task·Credential·Queue가 중단됩니다.
- Observe: 운영 Telemetry가 중단 이후 새 Effect 0건을 보여줍니다.

<a id="ai-section-11"></a>

## 11. Evidence Graph는 표준 제품명이 아니라 구현 패턴이다

이 글에서 Evidence Graph는 특정 국제표준의 고유 스키마가 아닙니다. 다음 요구를 만족하기 위한 **도메인 구현 패턴**입니다.

- 하나의 Evidence가 어떤 불변 Subject Digest에 관한 것인지 찾습니다.
- Evidence를 생성한 Activity·Tool·Dataset·Identity를 추적합니다.
- Claim이 어떤 Evidence와 Argument에 의존하는지 찾습니다.
- 변경·만료·Incident가 어떤 Claim과 Decision에 영향을 주는지 계산합니다.
- 상충하는 Evidence와 열려 있는 Defeater를 보존합니다.
- 승인 범위·조건·만료와 승인자를 추적합니다.

구현은 Property Graph, RDF/OWL, 관계형 테이블+Edge Table, 문서 저장소+검색 Index 중 조직 환경에 맞게 선택할 수 있습니다. 중요한 것은 Graph Database 제품이 아니라 **ID·Edge Semantics·불변성·검증 규칙**입니다.

<a id="ai-section-12"></a>

## 12. Evidence Node를 Subject·Predicate·Issuer에 바인딩한다

Evidence Node는 파일 경로만 가리키지 않습니다.

```json
{
  "evidence_id": "EVD-EVAL-20260819-0042",
  "evidence_type": "evaluation-result",
  "subject": {
    "uri": "urn:agent-release:meeting-action-agent:rel-20260819-03",
    "digest": { "sha256": "8c31..." }
  },
  "predicate_type": "https://example.org/ai/evaluation-result/v1",
  "predicate": {
    "suite_digest": "sha256:51af...",
    "dataset_digest": "sha256:22d1...",
    "evaluator_digest": "sha256:710c...",
    "trial_count": 5,
    "blocking_failures": 0,
    "unsupported_slices": []
  },
  "activity": {
    "run_id": "eval-run-0042",
    "started_at": "2026-08-19T02:00:00Z",
    "finished_at": "2026-08-19T02:18:20Z"
  },
  "issuer": {
    "identity": "spiffe://assurance.example/verifier/eval-ci",
    "key_id": "kms://assurance/eval-ci/7"
  },
  "validity": {
    "generated_at": "2026-08-19T02:18:21Z",
    "expires_at": "2026-09-02T02:18:21Z"
  },
  "artifact": {
    "uri": "oci://assurance/evidence/eval-run-0042",
    "digest": { "sha256": "3f92..." }
  }
}
```

`predicate_type` URI와 스키마는 예시입니다. in-toto Attestation Framework가 제공하는 Statement·Predicate·Envelope 구조를 참고해 AI 도메인 Predicate를 정의할 수 있지만, 자체 Predicate가 국제표준이 되는 것은 아닙니다. 조직은 Schema, 의미, Versioning, 신뢰 Issuer와 검증 규칙을 문서화해야 합니다.

<a id="ai-section-13"></a>

## 13. W3C PROV로 Entity·Activity·Agent의 출처를 표현한다

W3C PROV-O의 시작점은 `prov:Entity`, `prov:Activity`, `prov:Agent`입니다. Evidence Graph에 다음처럼 매핑할 수 있습니다.

| Evidence Graph | W3C PROV 개념 | 예시 관계 |
|---|---|---|
| Release·Dataset·Evidence Artifact | `prov:Entity` | Evidence `prov:wasDerivedFrom` Dataset Snapshot |
| Evaluation·Contract Test·Review | `prov:Activity` | Result `prov:wasGeneratedBy` Evaluation Run |
| CI Verifier·Human Reviewer·조직 | `prov:Agent` | Run `prov:wasAssociatedWith` Verifier Identity |
| 사용한 입력 | `prov:used` | Evaluation Run이 Release와 Dataset을 사용 |
| 생성 책임 | `prov:wasAttributedTo` | Evidence가 Assurance Service에 귀속 |
| 위임 관계 | `prov:actedOnBehalfOf` | Reviewer가 Risk Committee를 대신해 검토 |

![Agent Release와 Policy·Prompt·Tool·Dataset Snapshot이 Evaluation·인가 Test·Red Team Replay 활동에 사용되고 검증기 Identity와 결과 Evidence가 Claim Set과 Assurance Decision으로 연결되는 출처 그래프](assets/blog-91-evidence-graph-provenance.png)

*Evidence Graph의 출처 축 — 판정 대상, 검증 활동, Evidence Entity, 책임 Identity와 Claim을 분리해 변경 영향과 신뢰 경로를 추적합니다.*

`SUPPORTED_BY`, `CHALLENGED_BY`, `REQUIRES`, `INVALIDATES` 같은 Claim Edge는 이 글의 도메인 확장입니다. W3C PROV의 표준 관계인 것처럼 이름을 섞지 않습니다.

<a id="ai-section-14"></a>

## 14. Digest와 Attestation으로 증거 대상과 무결성을 확인한다

Attestation을 검증할 때 서명만 확인하면 부족합니다.

```text
1. Envelope 형식과 Signature, 사용 방식에 따른 Certificate·Transparency Material 검증
2. Issuer Identity가 해당 Predicate Type의 신뢰 목록에 있는지 확인
3. Statement Subject Digest가 현재 Release Artifact와 일치하는지 확인
4. predicateType과 Schema Version을 Allowlist로 검증
5. Predicate 내부 Dataset·Verifier·Policy Digest를 현재 기대값과 비교
6. generated_at·expires_at·revocation 상태 확인
7. Claim이 요구한 Context·Coverage·Method와 일치하는지 확인
8. Counter-evidence·Finding·Inconclusive 결과가 누락되지 않았는지 확인
```

SLSA Provenance는 Software Artifact가 어디서·언제·어떻게 만들어졌는지 추적하는 Supply Chain 규격입니다. Agent Release의 Code·Container·Build Artifact에는 직접 활용할 수 있습니다. 그러나 SLSA Provenance가 Prompt 품질, 업무 적합성, Bias, Tool 권한 또는 안전성을 자동으로 증명하지는 않습니다. 이런 속성은 별도의 Domain Predicate와 검증 논거가 필요합니다.

<a id="ai-section-15"></a>

## 15. 서명은 진실이 아니라 발행자와 무결성을 증명한다

유효한 서명이 보장하는 범위는 제한적입니다.

```text
서명이 지지하는 것
  - 특정 Key를 가진 주체가 이 Payload에 서명했다
  - 서명 이후 Payload가 변경되지 않았다

서명만으로 지지하지 못하는 것
  - 발행자가 측정을 정확히 수행했다
  - Dataset이 대표성을 가진다
  - Predicate의 주장이 사실이다
  - Evidence가 해당 Claim에 충분하다
```

따라서 Trust Policy에는 Key뿐 아니라 Issuer 역할과 허용 Predicate를 연결합니다.

```yaml
trust_policy:
  - issuer: spiffe://assurance.example/verifier/eval-ci
    may_issue: [evaluation-result]
    forbidden: [risk-acceptance, independent-review]
  - issuer: spiffe://assurance.example/security/redteam
    may_issue: [redteam-result, finding]
  - issuer: urn:person:risk-owner-17
    may_issue: [conditional-risk-acceptance]
    requires_mfa: true
```

Release Builder가 자기 Artifact의 Build Provenance를 발행할 수 있어도 독립 검토나 Risk Acceptance까지 대신 발행하지 않게 역할을 분리합니다.

<a id="ai-section-16"></a>

## 16. Freshness·Expiry·Revocation으로 증거 수명을 관리한다

Evidence는 영구 인증서가 아닙니다. 유효성은 시간과 변경에 따라 달라집니다.

| Trigger | 영향받는 Evidence·Claim 예시 |
|---|---|
| Model·Prompt 변경 | 품질·Safety·Tool Selection Evaluation |
| Tool Schema·권한 변경 | Contract·Authorization·Side Effect Claim |
| RAG Corpus·ACL 변경 | Retrieval·Citation·Tenant Isolation Claim |
| Policy 변경 | 승인·Budget·Egress·Fallback Claim |
| Dataset·Evaluator 변경 | Baseline 비교·Regression Claim |
| Incident·Near Miss | 관련 Prevention·Detection·Recovery Claim |
| Issuer Key 폐기 | 해당 Key로 서명된 Evidence 신뢰 상태 |
| 유효 기간 만료 | 명시된 모든 의존 Claim |

Evidence를 물리적으로 삭제하지 않고 상태를 바꿉니다.

```yaml
evidence_state:
  evidence_id: EVD-AUTHZ-018
  state: INVALIDATED
  reason: policy-bundle-changed
  invalidated_at: 2026-08-20T03:00:00Z
  invalidated_by: CHG-POLICY-411
  affected_claims: [CLM-AUTHZ-02, CLM-EFFECT-01]
```

과거 결정의 재현을 위해 당시 Evidence와 Decision은 보존하되, 현재 승인 계산에서는 유효하지 않은 상태로 처리합니다.

<a id="ai-section-17"></a>

## 17. Coverage와 Unsupported Claim을 PASS에서 분리한다

실행한 Test가 모두 통과해도 필요한 범위를 시험하지 않았다면 Claim은 지지되지 않습니다.

```yaml
coverage_requirement:
  claim_id: CLM-TOOL-SAFETY-01
  required_slices:
    tenant_tier: [pilot, enterprise]
    language: [ko, en]
    tool_class: [read, write-important, external-egress]
    attack_path: [direct-injection, indirect-injection, delegated-agent]
  minimum_trials_per_slice: 20

coverage_result:
  covered: 10
  required: 12
  missing:
    - { language: en, tool_class: external-egress, attack_path: delegated-agent }
    - { tenant_tier: enterprise, tool_class: write-important, attack_path: indirect-injection }
  claim_state: UNSUPPORTED
```

권장 Claim 상태는 단순 Pass/Fail보다 넓습니다.

| 상태 | 의미 | Release 처리 |
|---|---|---|
| `SUPPORTED` | 요구 Evidence가 유효하고 논거·Coverage 충족 | 다음 Gate 가능 |
| `UNSUPPORTED` | 필수 Evidence·Coverage 부족 | 중단·수집 |
| `CONTESTED` | 유효한 Counter-evidence·Defeater 존재 | 독립 검토·해소 |
| `STALE` | Release·Context·시간 불일치 | 재검증 |
| `REJECTED` | Claim이 거짓임을 보여주는 결정적 Evidence | 수정·범위 축소 |

`INCONCLUSIVE` Evaluation은 `SUPPORTED` Evidence로 승격하지 않습니다.

<a id="ai-section-18"></a>

## 18. 충돌하는 증거를 평균으로 지우지 않는다

다음 결과를 하나의 92점으로 평균 내면 중요한 실패가 사라집니다.

| Evidence | 결과 | Claim 영향 |
|---|---|---|
| 정상 업무 Evaluation | 성공률 96% | 품질 Claim 지지 |
| 외부 전송 Negative Test | 1회 금지 Effect 시도 | 권한 Claim 반박 |
| Gateway Effect Ledger | 실제 전송 0건 | Effect 예방 Claim 지지 |
| Detection Trace | Alert 미발생 | 탐지 Claim 반박 |

판정은 영역별로 나눕니다.

```text
품질 Claim          = SUPPORTED
실제 Effect 예방   = SUPPORTED
Planner Goal 통제  = CONTESTED
Detection Claim    = REJECTED
Top Claim          = PAUSE
```

특히 Critical Claim은 다른 점수로 상쇄하지 않는 Non-compensating Gate로 둡니다. 상충 Evidence가 발생하면 어느 결과를 버릴지 먼저 정하지 않고, 대상·Context·Method·시간 차이를 조사합니다.

<a id="ai-section-19"></a>

## 19. Confidence Score를 근거 없는 확률처럼 사용하지 않는다

`Assurance Confidence 87%` 같은 숫자는 계산 근거가 없으면 정밀해 보이는 장식입니다. 다음이 정의되지 않았다면 확률처럼 해석하지 않습니다.

- 어떤 불확실성을 측정하는가?
- Evidence 간 독립성·상관관계를 어떻게 처리하는가?
- Prior와 Calibration Dataset이 있는가?
- 87%가 어떤 의사결정 행동으로 이어지는가?
- Critical Defeater를 점수가 상쇄할 수 있는가?

초기에는 투명한 다차원 상태가 더 안전합니다.

```yaml
assurance_summary:
  claim_coverage: 18/20
  unsupported_critical_claims: 1
  open_critical_defeaters: 0
  stale_evidence: 2
  independent_review: COMPLETE
  residual_risk_acceptances_expiring_days: 6
  decision: PAUSE
```

가중 점수를 사용하더라도 우선순위 정렬용인지 승인용인지 구분하고, Critical Blocker는 점수 계산 밖에서 처리합니다.

<a id="ai-section-20"></a>

## 20. Residual Risk Acceptance에 범위·책임·만료를 둔다

통제를 적용해도 위험이 0이 되지는 않습니다. 잔여 위험을 수용할 수 있지만 `알고 있음`이라는 메모로 끝내지 않습니다.

```yaml
risk_acceptance:
  acceptance_id: RSK-ACC-20260819-07
  risk_id: RSK-HALLUCINATED-DUE-DATE
  decision: ACCEPT_CONDITIONAL
  scope:
    tenants: [pilot-kr-01]
    task_classes: [action-draft]
    prohibited_actions: [auto-submit]
  conditions:
    - human-review-before-ticket-create
    - source-citation-required
    - weekly-error-slice-review
  owner: business-risk-owner
  approvers: [service-owner, security-reviewer]
  expires_at: 2026-09-02T00:00:00Z
  reopen_triggers:
    - harmful-outcome
    - model-route-change
    - citation-missing-rate-above-threshold
```

Risk Acceptance는 실패 Evidence를 PASS로 바꾸지 않습니다. Claim은 여전히 `CONTESTED` 또는 제한적 `SUPPORTED`로 남고, 최상위 Decision이 명시된 범위에서만 조건부 승인됩니다.

<a id="ai-section-21"></a>

## 21. 그래프 질의로 누락·만료·영향 범위를 찾는다

Evidence Graph가 제공해야 할 대표 질의는 다음과 같습니다.

```text
현재 Release의 Critical Claim 중 유효한 Evidence가 없는 것은?
14일 안에 만료되는 Evidence가 지지하는 운영 승인은?
폐기된 Issuer Key로 서명된 Evidence와 파생 Decision은?
Tool Contract Digest 변경으로 무효화해야 할 Claim은?
Open High Finding과 연결된 Risk Acceptance의 Owner·만료는?
한 명이 작성·검증·승인을 모두 수행한 Critical Claim은?
운영 Incident에서 파생됐지만 Regression Suite에 연결되지 않은 Finding은?
```

설명용 Cypher 형태는 다음과 같습니다. 실제 Label과 Query는 선택한 저장소에 맞게 정의합니다.

```cypher
MATCH (c:Claim {critical: true})-[:REQUIRES]->(r:EvidenceRequirement)
WHERE NOT EXISTS {
  MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
  WHERE e.state = 'VALID'
    AND e.subject_digest = $release_digest
    AND e.expires_at > datetime()
    AND (e)-[:SATISFIES]->(r)
}
RETURN c.claim_id, r.requirement_id
```

Graph Query 결과도 최종 판정이 아니라 검토 입력입니다. Edge 누락이나 잘못된 의미를 검증하는 Graph Constraint와 Negative Test가 별도로 필요합니다.

<a id="ai-section-22"></a>

## 22. Assurance Decision을 Release Gate에 연결한다

[AI Agent Release Governance](https://aiarchitect.tistory.com/87)의 Release Bundle은 Assurance Case의 Subject가 됩니다. Gate는 최신 Assurance Decision을 검증합니다.

```yaml
release_gate:
  release_digest: sha256:8c31...
  required_claims:
    - CLM-PURPOSE-01
    - CLM-AUTHZ-02
    - CLM-EFFECT-01
    - CLM-RECOVERY-03
  decision_requirements:
    allowed: [APPROVE_CONDITIONAL, APPROVE]
    subject_digest_must_match: true
    open_critical_defeaters: 0
    unsupported_critical_claims: 0
    stale_critical_evidence: 0
    independent_review_required: true
    decision_not_expired: true
  on_failure: PAUSE
```

Release Gate의 순서는 다음과 같습니다.

1. Bundle과 Provenance를 검증합니다.
2. Bundle Digest와 Assurance Decision Subject가 일치하는지 확인합니다.
3. 필수 Claim의 상태와 Evidence Freshness를 계산합니다.
4. Open Defeater·Finding·Accepted Risk 만료를 확인합니다.
5. 승인 범위가 Canary Cohort와 일치하는지 확인합니다.
6. 하나라도 불명확하면 `INCONCLUSIVE` 또는 `PAUSE`로 처리합니다.

<a id="ai-section-23"></a>

## 23. 변경·사고·Drift가 영향을 받은 주장만 무효화한다

Continuous Assurance는 전체 문서를 매일 다시 작성하는 일이 아닙니다. 변경 Edge를 따라 영향받은 Claim과 Evidence를 계산하고 필요한 부분만 재검증합니다.

![Claim 작성부터 Evidence 수집·무결성·출처·신선도 검증과 독립 검토를 거쳐 범위·조건·만료가 있는 승인을 내리고 변경·사고·만료 시 영향받은 Claim을 무효화해 재검증하는 Assurance 수명주기](assets/blog-91-assurance-decision-lifecycle.png)

*Assurance 수명주기 — 승인은 끝 상태가 아니라 운영 관찰과 변경 Trigger가 다시 Evidence 수집으로 연결되는 만료 가능한 상태입니다.*

```text
Tool Contract 변경
  → 해당 Digest를 사용한 Contract·Authorization·Red Team Evidence 무효화
  → 연결된 Claim을 STALE로 변경
  → 그 Claim에 의존한 Top Claim 재계산
  → Canary Promotion PAUSE
  → 영향 Suite 재실행
  → 독립 검토와 새 Decision 발행
```

반대로 CSS 변경처럼 Agent 동작·Evidence에 영향이 없는 변경까지 전체 재평가하지 않습니다. Change Class와 Dependency Edge로 비례성을 지킵니다. [Red Teaming과 Continuous Assurance](https://aiarchitect.tistory.com/90)의 변경·사고·위협 Trigger는 이 무효화 흐름의 핵심 입력입니다.

<a id="ai-section-24"></a>

## 24. 표준·법규 매핑은 적합성 보증과 구분한다

Assurance Case는 여러 요구사항을 Evidence와 연결하는 데 유용하지만 인증서나 법적 적합성 판정을 자동 생성하지 않습니다.

| 기준 | 활용할 수 있는 부분 | 과도하게 주장하면 안 되는 것 |
|---|---|---|
| ISO/IEC/IEEE 15026-2 | Assurance Case 구조·용어 | 특정 GSN 그림을 쓰면 자동 준수 |
| NIST AI RMF 1.0 | GOVERN·MAP·MEASURE·MANAGE Outcome과 Risk 관리 | 전체 항목을 체크하면 안전 인증 |
| ISO/IEC 42001 | 조직 차원의 AIMS 수립·운영·개선 | 개별 Agent Release의 안전 보증 |
| ISO/IEC 42005 | AI System Impact Assessment 과정 | 모든 기술 통제의 효과 검증 |
| NIST SP 800-53A·OSCAL | 보안·Privacy 통제 평가와 기계 판독 결과 구조 | AI 품질·사회적 영향 전체 평가 |
| W3C PROV | Evidence 출처·활동·책임 관계 | Evidence 내용의 진실성 |
| in-toto·SLSA | Attestation·Artifact Supply Chain Provenance | Agent 목적 적합성·업무 안전성 |

EU에서 서비스를 제공한다면 AI Act 적용 범위와 역할(Provider·Deployer 등)을 별도로 분류해야 합니다. 2026년 8월 19일 기준 유럽위원회 안내상 Article 50의 일부 투명성 의무는 2026년 8월 2일부터 적용되고, Annex III 고위험 시스템 규칙은 2027년 12월 2일, 규제 제품에 내장된 고위험 시스템 규칙은 2028년 8월 2일부터 적용되는 일정입니다. 일정과 적용 대상은 변경될 수 있으므로 최신 EUR-Lex 법문, 유럽위원회 지침과 전문 법률 검토를 확인해야 합니다.

Evidence Graph는 법규 조항→통제→평가→Evidence→Owner 연결을 보여줄 수 있지만, 그 연결만으로 적합성 평가·인증·법률 의견을 대신하지 않습니다.

<a id="ai-section-25"></a>

## 25. 합성 사례로 회의 후속조치 Agent를 판정한다

회의 요약과 후속조치 초안을 만들고, 승인 후 Ticket을 생성하는 Agent의 Pilot을 검토한다고 가정합니다.

### Claim Set

| Claim ID | 주장 | 연결 Evidence |
|---|---|---|
| CLM-FIT-01 | 이 업무는 Human-in-the-loop Agent 방식에 적합 | 적합도 판정 Manifest |
| CLM-READY-01 | 데이터·API·권한·보안·인수 준비도 충족 | Readiness Gate와 Negative Test |
| CLM-QUALITY-01 | 한국어 회의 Slice의 Action Item 품질 기준 충족 | Evaluation Experiment |
| CLM-AUTHZ-01 | 단건 승인 없는 Ticket 쓰기 불가 | Policy·Grant·Execution Receipt |
| CLM-SEC-01 | 악성 문서가 외부 전송 Effect를 만들지 못함 | Red Team Replay·Effect Ledger |
| CLM-RECOVERY-01 | 공격 Task를 탐지·중단하고 오염 상태를 제거 | Alert·Revocation·Recovery Test |

첫 번째 Candidate의 결과는 다음과 같습니다.

```yaml
candidate: rel-20260819-02
claims:
  CLM-FIT-01: SUPPORTED
  CLM-READY-01: SUPPORTED
  CLM-QUALITY-01: SUPPORTED
  CLM-AUTHZ-01: SUPPORTED
  CLM-SEC-01: SUPPORTED
  CLM-RECOVERY-01: REJECTED
counter_evidence:
  - finding: goal-hijack-alert-not-fired
    severity: HIGH
    prohibited_effects: 0
decision: PAUSE
```

실제 외부 전송은 Gateway가 차단했지만 공격 Goal을 탐지하지 못했으므로 전체를 PASS로 평균 내지 않습니다. Detection과 Recovery Claim을 수정한 새 Release에서 관련 Suite만 다시 실행합니다.

```yaml
candidate: rel-20260819-03
supersedes: rel-20260819-02
changed:
  - goal-change-detector
  - incident-routing-policy
revalidated_claims:
  - CLM-SEC-01
  - CLM-RECOVERY-01
decision:
  state: APPROVE_CONDITIONAL
  scope: pilot-kr-01
  max_canary_percent: 5
  expires_at: 2026-09-02T00:00:00Z
```

이 사례에서 [도입 로드맵](https://aiarchitect.tistory.com/65)은 Gate Context, [적합도 판정](https://aiarchitect.tistory.com/70)은 CLM-FIT-01, [준비도 진단](https://aiarchitect.tistory.com/69)은 CLM-READY-01, [평가 아키텍처](https://aiarchitect.tistory.com/74)는 CLM-QUALITY-01, [Release Governance](https://aiarchitect.tistory.com/87)는 Subject와 Canary Decision, [Red Teaming과 Continuous Assurance](https://aiarchitect.tistory.com/90)는 Counter-evidence와 재검증 Trigger를 제공합니다.

<a id="ai-section-26"></a>

## 26. 도입·Pilot·운영 승인 체크리스트를 Evidence에 묶는다

체크 표시만으로 끝내지 않도록 각 항목에 `Claim ID`, `Evidence Requirement`, `Verifier`, `Freshness`, `Failure Decision`을 둡니다.

### 범위와 책임

- [ ] System Boundary에 Model·RAG·Memory·MCP·A2A·Policy·Runtime Dependency가 포함됐는가?
- [ ] Top Claim에 Release Digest·Context·허용 업무·금지 Effect·유효 기간이 있는가?
- [ ] Claim·Evidence 작성자·독립 Reviewer·Risk Owner의 역할이 분리됐는가?
- [ ] Assumption과 외부 Dependency Owner가 명시됐는가?

### Claim과 논거

- [ ] 업무 피해와 불변식에서 Claim을 도출했는가?
- [ ] Critical Claim이 다른 평균 점수로 상쇄되지 않는가?
- [ ] Argument가 Evidence에서 Claim으로 이어지는 이유를 설명하는가?
- [ ] Open Defeater·Counter-evidence·Inconclusive Result가 보이는가?

### Evidence 무결성과 품질

- [ ] Subject Digest가 현재 Release Bundle과 일치하는가?
- [ ] Dataset·Verifier·Policy·Tool Contract Version이 고정됐는가?
- [ ] Issuer Identity·Signature·Predicate Type·Schema를 검증했는가?
- [ ] Relevance·Validity·Coverage·Freshness·Independence를 평가했는가?
- [ ] Evidence 원문과 요약·파생 결과의 Lineage가 남는가?
- [ ] 민감 데이터·Prompt·Trace의 접근·보존·삭제 정책이 있는가?

### 판정과 운영

- [ ] `SUPPORTED·UNSUPPORTED·CONTESTED·STALE·REJECTED` 상태가 구분되는가?
- [ ] Residual Risk Acceptance에 Owner·Scope·조건·만료·재개 Trigger가 있는가?
- [ ] Decision 범위와 실제 Canary Cohort·권한이 일치하는가?
- [ ] 변경·사고·Drift·만료가 영향 Claim을 자동으로 재평가하는가?
- [ ] 만료·폐기 Evidence를 지우지 않고 과거 Decision 재현용으로 보존하는가?
- [ ] Evidence Graph 자체의 Edge 누락·순환·권한 오류를 Negative Test하는가?

<a id="ai-section-27"></a>

## 27. 자주 실패하는 Assurance 안티패턴을 피한다

### Evidence Dump

보고서와 로그를 저장소에 모으지만 어떤 Claim을 지지하는지 연결하지 않습니다. 파일 수는 Assurance 강도가 아닙니다.

### Green Dashboard Argument

모든 Metric이 녹색이라는 화면을 Top Claim의 근거로 사용합니다. Threshold 근거·누락 Metric·지원하지 않는 Slice가 보이지 않습니다.

### Versionless Evidence

Agent 이름만 있고 Release·Prompt·Policy·Dataset Digest가 없습니다. 현재 운영 대상의 증거인지 확인할 수 없습니다.

### Signed Therefore True

서명이 유효하므로 Predicate 내용도 참이라고 결론 냅니다. 서명자는 정확하지 않거나 불완전한 측정에 서명할 수 있습니다.

### Compliance Equals Safety

표준·법규 Mapping을 완료했으므로 Agent가 안전하다고 주장합니다. 요구사항 대응과 실제 위험 통제 효과를 구분해야 합니다.

### No Counter-case

성공 Evidence만 연결하고 반증·가정·미해결 Finding을 문서 밖으로 뺍니다. 독립 Reviewer가 결론을 재현할 수 없습니다.

### Eternal Approval

Release와 Context가 바뀌어도 이전 승인을 재사용합니다. 모든 Decision에는 Subject·Scope·Expiry·Invalidation Trigger가 필요합니다.

<a id="ai-section-28"></a>

## 28. 네 단계로 Assurance Case를 도입한다

### 1단계: 중요한 운영 결정 하나를 선택한다

- Agent 한 개와 Pilot Release 한 개를 고릅니다.
- Top Claim과 금지 Effect를 작성합니다.
- 기존 체크리스트 항목을 Claim·Evidence Requirement로 분류합니다.
- Critical Claim 5~10개부터 시작합니다.

### 2단계: Evidence Manifest와 검증 규칙을 만든다

- Release·Dataset·Policy·Verifier Digest를 기록합니다.
- Evidence Node Schema와 상태·만료 규칙을 정의합니다.
- 자동 Test 결과와 Human Review를 같은 파일로 합치지 않습니다.
- Subject 불일치·만료·누락·변조 Negative Test를 만듭니다.

### 3단계: Release Gate와 독립 검토를 연결한다

- Unsupported·Contested·Stale Critical Claim을 차단합니다.
- Risk Acceptance에 Scope와 만료를 강제합니다.
- Release Builder와 최종 승인자를 분리합니다.
- Decision을 Canary 범위와 Policy Enforcement에 연결합니다.

### 4단계: Evidence Graph와 Continuous Assurance로 확장한다

- W3C PROV 개념을 참고해 Entity·Activity·Agent Lineage를 연결합니다.
- 변경·사고·Drift의 영향 Claim을 질의합니다.
- 자동 무효화와 선택적 재시험을 운영합니다.
- Finding·Incident·Risk Acceptance의 수명주기를 하나의 Graph에서 추적합니다.

처음부터 모든 정책과 Evidence를 거대한 Knowledge Graph로 옮기지 않습니다. 중요한 승인 하나를 재현 가능하게 만든 뒤 반복되는 ID·Edge·Query를 표준화합니다.

<a id="ai-section-29"></a>

## 29. 마무리 — 좋은 검증은 결론보다 추적 가능한 이유를 남긴다

기업 AI Agent 도입 검증의 목표는 `안전함` 도장을 만드는 것이 아닙니다. **현재 Release가 정해진 업무·권한·Context에서 어떤 Claim을 만족하며, 어떤 Evidence와 가정이 그 결론을 지지하고, 어떤 반증과 잔여 위험이 남았고, 무엇이 바뀌면 승인을 다시 열어야 하는지 설명할 수 있는 상태**를 만드는 것입니다.

```text
체크리스트 항목을 Claim과 Evidence Requirement로 바꾼다.
Top Claim에 System·Release·Context·Time을 고정한다.
Evidence 존재와 Evidence 채택을 분리한다.
Digest·출처·Issuer·서명·신선도·Coverage를 검증한다.
서명과 Provenance를 진실성·충분성으로 과대해석하지 않는다.
Counter-evidence와 Defeater를 숨기지 않는다.
Critical Claim은 평균 점수로 상쇄하지 않는다.
Risk Acceptance에 책임·범위·조건·만료를 둔다.
Release Gate는 현재 Subject와 유효한 Decision을 대조한다.
변경·사고·Drift가 영향 Claim만 무효화하고 재검증하게 만든다.
```

도입 순서는 [기업 AI Agent 도입 로드맵](https://aiarchitect.tistory.com/65), 업무 구조 선택은 [AI Agent 적합도 판정](https://aiarchitect.tistory.com/70), PoC 전 조건은 [도입 준비도 진단](https://aiarchitect.tistory.com/69), 품질 근거는 [평가 아키텍처](https://aiarchitect.tistory.com/74), 배포 결정은 [Release Governance](https://aiarchitect.tistory.com/87), 공격·변경 후 근거 갱신은 [Red Teaming과 Continuous Assurance](https://aiarchitect.tistory.com/90)에서 이어서 확인할 수 있습니다.

좋은 Assurance Case는 결론에 동의하라고 요구하는 문서가 아닙니다. 다른 Reviewer가 같은 Release와 Evidence를 따라가 결론을 재현하고, 동의하지 않는 지점을 Claim·가정·Evidence·논거 수준에서 정확히 지적할 수 있게 만드는 검증 구조입니다.

<a id="ai-section-30"></a>

## 30. 공식 참고자료

- [ISO — ISO/IEC/IEEE 15026-2:2022 Systems and software assurance — Assurance case](https://www.iso.org/standard/80625.html)
- [IEEE Standards Association — IEEE/ISO/IEC 15026-2-2022](https://standards.ieee.org/ieee/15026-2/10236/)
- [SCSC Assurance Case Working Group — Goal Structuring Notation](https://scsc.uk/gsn)
- [NIST — Assurance Case Glossary](https://csrc.nist.gov/glossary/term/assurance_case)
- [NIST — SP 800-160 Vol. 1 Rev. 1 Engineering Trustworthy Secure Systems](https://csrc.nist.gov/pubs/sp/800/160/v1/r1/final)
- [NIST — Artificial Intelligence Risk Management Framework 1.0](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10)
- [NIST AI Resource Center — AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- [NIST AI Resource Center — AI RMF Playbook](https://airc.nist.gov/airmf-resources/playbook/)
- [NIST — Generative AI Profile, NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
- [NIST — SP 800-53A Rev. 5 Assessing Security and Privacy Controls](https://csrc.nist.gov/pubs/sp/800/53/a/r5/final)
- [NIST OSCAL — Assessment Results Model](https://pages.nist.gov/OSCAL/learn/concepts/layer/assessment/assessment-results/)
- [ISO — ISO/IEC 42001:2023 AI Management Systems](https://www.iso.org/standard/42001)
- [ISO — ISO/IEC 42005:2025 AI System Impact Assessment](https://www.iso.org/standard/42005)
- [ISO — ISO/IEC 23894:2023 AI Risk Management](https://www.iso.org/standard/77304.html)
- [W3C — PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)
- [W3C — PROV Overview](https://www.w3.org/TR/prov-overview/)
- [in-toto — Attestation Framework Specification](https://github.com/in-toto/attestation/blob/main/spec/README.md)
- [SLSA — Specification 1.2](https://slsa.dev/spec/v1.2/)
- [SLSA — Provenance](https://slsa.dev/spec/v1.2/provenance)
- [EUR-Lex — Regulation (EU) 2024/1689, Artificial Intelligence Act](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:32024R1689)
- [European Commission — AI Act Regulatory Framework and Application Timeline](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)

이 글은 2026년 8월 19일 기준 ISO, IEEE, SCSC, NIST, W3C, in-toto, SLSA, EUR-Lex와 유럽위원회의 공식 공개 자료를 확인해 작성했습니다. ISO/IEC/IEEE 15026-2는 Assurance Case의 구조·용어를 규정하지만 특정 그래픽 표현을 요구하지 않습니다. W3C PROV는 출처 표현, in-toto와 SLSA는 Attestation·Software Supply Chain Provenance에 초점이 있으며, 이 글의 AI Agent Evidence Graph Schema·Claim State·Query·Gate는 이 원칙을 조합한 설계 예시입니다. NIST AI RMF 1.0은 현재 개정이 진행 중이고 NIST Playbook은 전체를 따르는 체크리스트가 아닙니다. EU AI Act 일정과 지침도 계속 갱신될 수 있으므로 실제 적용 전 최신 공식 법문과 전문 검토를 다시 확인해야 합니다.
