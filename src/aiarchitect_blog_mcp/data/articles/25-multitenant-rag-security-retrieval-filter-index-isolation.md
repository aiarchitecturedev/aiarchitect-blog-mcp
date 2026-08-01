# Tistory 기술자료 초안

- 문서 ID: `BLOG-25`
- 상태: 공개 완료
- Tistory 상태: 2026-07-30 공개 게시 및 공개 페이지 검증 완료
- 분류: `보안`
- 공개 URL: `https://aiarchitect.tistory.com/25`
- 권장 제목: `멀티테넌트 RAG 보안: 수집 권한·Retrieval Filter·Index 격리`
- 검색 설명: `멀티테넌트 RAG에서 원본 문서의 ACL을 Chunk와 Vector에 전파하고, 인증된 Tenant Context로 Retrieval Filter를 강제하며 Index·Cache·Citation·삭제까지 권한 경계를 유지하는 방법을 정리합니다.`
- 권장 태그: `RAG 보안`, `멀티테넌트`, `Retrieval Filter`, `Vector Database`, `ACL`, `Index 격리`, `검색 권한`, `AI Agent 보안`
- 권장 대표 이미지: `portfolio/architecture-diagrams/01-enterprise-ai-reference-architecture.svg`

---

# 멀티테넌트 RAG 보안: 수집 권한·Retrieval Filter·Index 격리

RAG (Retrieval-Augmented Generation, 검색 증강 생성)는 사용자의 질문과 관련된 문서를 찾아 모델 Context에 넣습니다.

이 과정에서 검색 품질만 생각하면 다음 흐름을 만들기 쉽습니다.

```text
전체 Vector Index 검색
  → 관련도 높은 Chunk 선택
    → 권한이 없는 결과 제거
      → 남은 내용으로 답변
```

하지만 권한이 없는 Chunk가 검색 후보와 중간 결과에 이미 포함됐다면 문제가 남습니다.

```text
Similarity Score를 통한 존재 추정
검색 Log·Trace·Debug Result 노출
Reranker·Cache·Model Context 유입
잘못된 Post-filter 구현
다른 Tenant Chunk가 Top-k를 차지해 정상 결과 누락
Citation·Download API에서 직접 객체 접근
```

안전한 RAG는 원본 문서의 권한을 별도 부가 정보로 취급하지 않습니다.

```text
Source ACL
  → Ingestion Authorization
    → Document Security Metadata
      → Chunk ACL Inheritance
        → Tenant·Principal Retrieval Filter
          → Result Object Reauthorization
            → Minimum Context
              → Citation·Cache·Delete Propagation
```

이 글은 RAG의 Chunking 품질이나 Idempotent Indexing (멱등 인덱싱)을 반복하기보다, **여러 Tenant와 사용자 그룹이 하나의 RAG Platform을 공유할 때 데이터 권한이 수집부터 삭제까지 끊기지 않게 만드는 방법**에 집중합니다.

## 1. RAG 권한 문제는 모델 앞에서 이미 발생한다

RAG의 데이터 유출은 최종 답변에서만 일어나지 않습니다.

| 단계 | 유출 가능 지점 |
|---|---|
| 수집 | 권한이 없는 Source를 Crawler가 읽음 |
| 변환 | ACL 없이 Text·OCR·Summary 생성 |
| Chunking | 원본 권한과 연결이 끊김 |
| Embedding | 다른 Tenant Vector와 혼합 |
| Retrieval | 권한 Filter 없이 후보 검색 |
| Reranking | 비인가 Chunk가 외부 Model에 전달 |
| Generation | 다른 Tenant 내용이 Context에 포함 |
| Citation | ID·제목·Excerpt·URL 노출 |
| Cache | 다른 사용자에게 이전 답변 재사용 |
| 삭제 | 원본은 삭제됐지만 Vector·Cache는 잔존 |

OWASP LLM08:2025는 Multi-tenant Vector Store에서 한 Group의 Embedding이 다른 Group의 Query에 검색돼 민감정보가 노출되는 위험을 설명합니다.

보안 경계는 “모델이 답변하지 않도록 Prompt에 지시”하는 것이 아니라, 권한 없는 콘텐츠가 모델에 도달하지 않게 하는 Application과 Data Store의 통제입니다.

## 2. 보호 대상을 Vector 하나로 축소하지 않는다

RAG Pipeline에는 여러 파생 데이터가 생깁니다.

```text
원본 File·Page
추출 Text·OCR·STT
정규화 Document
Chunk
Embedding
Keyword Index
Metadata Index
Summary·Entity·Fact
Search Result
Reranker Input·Output
Prompt Context
Response·Citation
Semantic Cache
Evaluation Dataset
Snapshot·Backup
```

Embedding은 원문을 그대로 보여주지 않는 숫자 배열이지만 공개 데이터가 아닙니다.

OWASP는 Embedding Inversion (임베딩 역변환), Cross-context Leakage (문맥 간 유출)와 Data Poisoning (데이터 오염)을 Vector·Embedding 위험으로 분류합니다.

따라서 원본보다 파생 데이터의 보안 등급을 자동으로 낮추지 않습니다.

각 Artifact (산출물)는 다음을 추적할 수 있어야 합니다.

- 원본 Source와 Version
- Tenant·Owner
- 데이터 분류
- ACL Snapshot과 Version
- 변환 단계·도구·시간
- 보존·삭제 정책
- 무결성 Hash

## 3. Tenant Context는 Client 입력이 아니라 인증 결과다

Tool 인자나 HTTP Header의 `tenantId`를 그대로 검색 Filter에 사용하면 공격자가 다른 Tenant 값을 넣을 수 있습니다.

Tenant Context (테넌트 문맥)는 인증된 Principal과 Membership (구성원 관계)에서 Server가 결정합니다.

```json
{
  "requestId": "req_opaque_id",
  "subject": {
    "userId": "usr_opaque_id",
    "tenantId": "ten_opaque_id",
    "groupIds": [
      "grp_opaque_id"
    ],
    "roles": [
      "knowledge_reader"
    ]
  },
  "authentication": {
    "issuer": "https://identity.example.com",
    "audience": "https://rag.example.com",
    "verified": true
  },
  "authorizationContextVersion": 12,
  "evaluatedAt": "2026-07-29T14:00:00Z"
}
```

다음 값을 검색 권한 근거로 사용하지 않습니다.

- Prompt 안의 Tenant 이름
- Query Parameter의 `tenantId`
- 모델이 추출한 조직명
- Source 문서 본문의 “공개” 문구
- 다른 Agent가 주장하는 사용자 Role

OWASP Multi Tenant Security 지침도 Tenant Context를 검증된 인증 정보에서 만들고 모든 계층으로 안전하게 전파하도록 권고합니다.

## 4. 수집 계정의 읽기 권한과 게시 권한을 분리한다

Ingestion Worker (수집 작업자)는 Source에서 문서를 읽을 권한이 필요합니다.

하지만 “Crawler가 읽을 수 있다”와 “모든 RAG 사용자가 검색할 수 있다”는 같은 의미가 아닙니다.

```text
Source Connector 권한
  → 수집에 필요한 기술 권한

Source Document ACL
  → 누가 해당 콘텐츠를 읽을 수 있는지

RAG Publication Policy
  → 어떤 사용자·용도·환경에 검색을 허용할지
```

Service Account가 넓은 읽기 권한으로 수집하더라도 Source ACL을 함께 가져와야 합니다.

다음 흐름은 Privilege Laundering (권한 세탁)이 됩니다.

```text
Crawler가 관리자 권한으로 문서 읽기
  → ACL 없이 공용 Index 저장
    → 일반 사용자가 검색
```

Connector에는 다음 제한을 적용합니다.

- 허용된 Source·Container·Site만 수집
- 증분 Cursor와 Page 범위 제한
- Source ACL·Owner·Classification 동시 수집
- 다른 Environment의 Credential 분리
- 수집·재수집·삭제 Event 감사
- Agent와 일반 Application의 직접 Index Write 금지

## 5. Source 권한 모델을 정규화한다

Source마다 권한 표현이 다릅니다.

```text
사용자·Group ACL
Folder 상속
Role
Project Membership
공유 Link
Organization 공개
분류 등급
시간 제한 접근
법적 보존 상태
```

RAG Platform은 Source 권한을 Canonical Authorization Model (표준 권한 모델)로 변환합니다.

```json
{
  "sourceAuthorization": {
    "sourceSystem": "knowledge_source_fixture",
    "sourceObjectId": "src_opaque_id",
    "visibility": "restricted",
    "allowedSubjects": [
      "usr_opaque_id"
    ],
    "allowedGroups": [
      "grp_opaque_id"
    ],
    "allowedRoles": [],
    "deniedSubjects": [],
    "classification": "CONFIDENTIAL",
    "inheritsFrom": "folder_opaque_id",
    "sourceAclVersion": "acl_fixture_v7",
    "observedAt": "2026-07-29T13:55:00Z"
  }
}
```

정규화 과정에서 다음 의미를 잃으면 안 됩니다.

- Allow와 Deny의 우선순위
- 상속과 예외
- Group 중첩
- 공유 Link의 범위·만료
- Classification과 Clearance
- Source의 ACL Version

표현할 수 없는 권한은 더 넓게 허용하지 않고 검역·수동 검토 또는 Source 직접 조회 방식으로 처리합니다.

## 6. Document Security Envelope을 만든다

정규화된 문서는 본문과 보안 Metadata를 함께 저장합니다.

```json
{
  "documentId": "doc_opaque_id",
  "tenantId": "ten_opaque_id",
  "source": {
    "system": "knowledge_source_fixture",
    "objectId": "src_opaque_id",
    "version": "source_fixture_v3"
  },
  "security": {
    "visibility": "restricted",
    "classification": "CONFIDENTIAL",
    "allowedSubjectIds": [
      "usr_opaque_id"
    ],
    "allowedGroupIds": [
      "grp_opaque_id"
    ],
    "aclVersion": "acl_fixture_v7",
    "policyVersion": "rag_policy_fixture_v1"
  },
  "lifecycle": {
    "status": "ACTIVE",
    "retentionClass": "RETENTION_POLICY",
    "deleteAfter": null
  },
  "integrity": {
    "contentHash": "sha256_fixture_value"
  }
}
```

`tenantId`, ACL과 Classification은 검색 가능한 보안 Field이지만 일반 Search Result에 그대로 반환할 필요는 없습니다.

보안 Field를 Filter 가능하게 만들고 응답에서는 비노출로 설정하는 패턴을 사용할 수 있습니다.

## 7. ACL Snapshot과 현재 권한을 함께 본다

Index에 저장된 ACL은 수집 시점의 Snapshot (스냅샷)입니다.

현재 Source 권한이 바뀌었을 수 있으므로 Snapshot만으로 영구 허용하면 안 됩니다.

```text
Index ACL Snapshot
  → 빠른 후보 제한

현재 Membership·정책
  → Query Context 결정

필요한 경우 Source·Authorization Service
  → 최종 객체 권한 재검증
```

다음 Version을 관리합니다.

- Source ACL Version
- 사용자 Membership Version
- Tenant Authorization Context Version
- RAG Policy Version
- Index Security Schema Version

권한 정보의 허용 가능한 Staleness (오래됨)를 위험별로 정의합니다.

권한 추가는 잠시 검색되지 않는 가용성 문제일 수 있지만, 권한 철회가 늦게 반영되면 기밀성 문제가 됩니다.

그래서 Grant와 Revoke의 처리 우선순위를 다르게 설계할 수 있습니다.

## 8. Chunk는 원본 ACL을 상속하고 원본으로 돌아갈 수 있어야 한다

Chunking 과정에서 본문만 저장하고 ACL을 Document Table에만 남기면 Vector Store가 독립적으로 권한을 적용하기 어렵습니다.

각 Chunk에 필요한 보안 Metadata를 함께 저장합니다.

```json
{
  "chunkId": "chk_opaque_id",
  "documentId": "doc_opaque_id",
  "tenantId": "ten_opaque_id",
  "chunkVersion": "chunk_fixture_v2",
  "text": "설명용 문서의 일부 내용",
  "security": {
    "visibility": "restricted",
    "classification": "CONFIDENTIAL",
    "allowedSubjectIds": [
      "usr_opaque_id"
    ],
    "allowedGroupIds": [
      "grp_opaque_id"
    ],
    "aclVersion": "acl_fixture_v7",
    "authorizationDigest": "sha256_fixture_acl_digest"
  },
  "provenance": {
    "sourceObjectId": "src_opaque_id",
    "page": 3,
    "contentHash": "sha256_fixture_chunk"
  },
  "status": "ACTIVE"
}
```

Chunk가 원본보다 넓은 권한을 가지면 안 됩니다.

여러 문서를 결합한 Summary·Entity·Fact는 입력 중 가장 제한적인 권한과 분류를 기본으로 상속합니다.

공개 가능한 파생물을 만들려면 별도의 Declassification (보안 등급 해제) 승인과 검증이 필요합니다.

## 9. Embedding Model 경계도 Tenant 정책에 포함한다

Embedding을 만들기 위해 외부 Model API에 원문 Chunk를 보낼 수 있습니다.

이때 Vector Store 이전에 이미 데이터가 다른 Processor로 이동합니다.

확인할 질문은 다음과 같습니다.

- 이 데이터 등급을 외부 Model에 전송할 수 있는가?
- Region·보존·학습 사용 정책은 무엇인가?
- Tenant별 계약과 Data Processing 조건이 다른가?
- Batch에 여러 Tenant의 Chunk가 섞이는가?
- Request·Error·Provider Log에 원문이 남는가?
- Embedding Cache가 Tenant별로 분리되는가?

고위험 데이터는 내부 Embedding Model, 전용 Endpoint 또는 별도 Processing 경계를 사용할 수 있습니다.

Embedding을 생성한 뒤 원문을 지웠다고 외부 전송 사실이 사라지는 것은 아닙니다.

## 10. Index 격리 수준을 위험에 맞게 선택한다

모든 Tenant에 별도 Cluster가 필요한 것은 아니지만, 하나의 Flat Namespace도 안전한 기본값이 아닙니다.

| 전략 | 격리 | 운영 비용 | 적합한 상황 |
|---|---|---:|---|
| Tenant별 Cluster·Account | 가장 강함 | 높음 | 규제·고위험·대형 Tenant |
| Tenant별 Database·Index | 강함 | 중상 | 명확한 데이터 경계 필요 |
| Tenant별 Collection·Namespace | 중상 | 중간 | 많은 Tenant와 논리 격리 |
| Partition·Table 분리 | 중상 | 중간 | 관계형 Metadata와 결합 |
| Shared Index + Metadata Filter | 정책 의존 | 낮음 | 저위험·많은 소형 Tenant |
| Hybrid Tier | 가변 | 가변 | Tenant 위험·계약별 차등 |

결정 기준은 다음과 같습니다.

- 데이터 분류와 규제
- Tenant 수와 크기
- ACL 복잡도
- Key·Backup·Region 분리 요구
- Noisy Neighbor (이웃 Tenant 간 자원 간섭)
- 복구·삭제·Offboarding 요구
- Vector Engine의 Filter와 Namespace 보장
- 운영팀의 자동화 능력

pgvector 공식 문서는 여러 Tenant가 Approximate Index (근사 인덱스)를 공유하면 서로의 Recall (재현율)과 속도에 영향을 줄 수 있다고 설명하고, Partition이나 별도 Table을 격리 방법으로 제시합니다.

## 11. Shared Index는 다층 통제가 필요하다

Shared Index를 사용한다면 Tenant Field 하나로 끝내지 않습니다.

```text
Network·Credential 격리
  → 인증된 Tenant Context
    → Query Builder의 강제 Tenant Predicate
      → Vector Store Namespace·Partition
        → Row·Document Level Security
          → 결과 객체 재인가
            → Tenant-aware Cache·Audit
```

관계형 Store에 Vector를 저장한다면 Row-Level Security (행 수준 보안)를 Defense in Depth (다층 방어)로 적용할 수 있습니다.

PostgreSQL Row Security는 정책이 없는 경우 Row가 보이지 않는 Default-deny 방식을 지원하지만, Table Owner와 `BYPASSRLS` Role 같은 예외도 있으므로 실행 Role을 별도로 검증해야 합니다.

Application의 일반 검색 Credential에는 전체 Index Admin·Export 권한을 주지 않습니다.

## 12. Retrieval Request를 보안 계약으로 만든다

사용자의 자연어 Query와 보안 Filter를 문자열로 섞지 않습니다.

Retrieval Contract (검색 계약)를 구조화합니다.

```json
{
  "retrievalRequestId": "ret_opaque_id",
  "subject": {
    "userId": "usr_opaque_id",
    "tenantId": "ten_opaque_id",
    "groupIds": [
      "grp_opaque_id"
    ],
    "clearance": "CONFIDENTIAL"
  },
  "query": {
    "text": "배포 전 확인 사항",
    "mode": "hybrid",
    "topK": 8
  },
  "authorization": {
    "requiredAction": "document.read",
    "authorizationContextVersion": 12,
    "policyVersion": "rag_policy_fixture_v1"
  },
  "limits": {
    "maxChunks": 8,
    "maxDocuments": 5
  }
}
```

Model이 `tenantId`, Group, Clearance와 정책 Version을 생성하거나 수정할 수 없습니다.

Retrieval Service가 인증된 Server Context에서 값을 주입합니다.

## 13. Retrieval Filter는 후보 검색 전에 권한 범위를 고정한다

권장 논리는 다음과 같습니다.

```text
tenant_id = authenticated_tenant
AND status = ACTIVE
AND classification <= subject_clearance
AND (
  visibility = TENANT
  OR owner_id = subject_id
  OR allowed_subject_ids contains subject_id
  OR allowed_group_ids intersects subject_groups
)
AND NOT denied_by_current_policy
```

Filter Plan (필터 계획)도 감사 가능한 구조로 만듭니다.

```json
{
  "retrievalRequestId": "ret_opaque_id",
  "filterPlan": {
    "tenantId": "ten_opaque_id",
    "statuses": [
      "ACTIVE"
    ],
    "maximumClassification": "CONFIDENTIAL",
    "subjectId": "usr_opaque_id",
    "groupIds": [
      "grp_opaque_id"
    ],
    "policyVersion": "rag_policy_fixture_v1"
  },
  "defaultDecision": "deny"
}
```

이 구조는 검색 Engine의 Query DSL로 변환되더라도 Security Predicate가 누락됐는지 검사할 수 있게 합니다.

## 14. Pre-filter와 Post-filter의 의미를 제품별로 검증한다

Pre-filter (사전 필터)는 권한 조건으로 후보 집합을 제한한 뒤 유사도 검색을 수행합니다.

Post-filter (사후 필터)는 더 넓은 후보를 찾은 뒤 결과에서 제거합니다.

OWASP RAG Security 지침은 Post-retrieval Filtering (검색 후 필터링)에만 의존하지 말고, 검색 결과가 반환되기 전에 권한 경계를 적용하도록 권고합니다.

다만 Vector Engine마다 구현이 다릅니다.

| 방식 | 보안 검토 질문 |
|---|---|
| Exact Pre-filter | 비인가 Row가 Score 계산에 들어가지 않는가? |
| Filtered ANN | Graph·List 탐색 중 Filter 의미가 무엇인가? |
| Post-filter | 비인가 Candidate·Score·Trace가 노출되는가? |
| Namespace | Query가 다른 Namespace를 지정할 수 있는가? |
| Partition | Planner가 Tenant Partition만 읽는가? |

OpenSearch는 Filter가 Vector Search 중 적용되는 Efficient k-NN, Exact Pre-filter와 Post-filter의 차이를 구분합니다.

Azure AI Search도 Vector Filter Mode에 따라 Filter 적용 시점이 달라집니다.

제품의 `filter`라는 이름만 믿지 말고 실제 Query Plan, Trace와 Negative Test로 검증합니다.

## 15. Hybrid Search의 모든 Branch에 같은 권한을 적용한다

Hybrid Search (혼합 검색)는 Vector, Keyword, Metadata와 Graph 검색 결과를 합칠 수 있습니다.

다음 구현은 위험합니다.

```text
Vector Search
  → Tenant·ACL Filter 적용

Keyword Search
  → Filter 누락

Result Fusion
  → 비인가 Keyword Result 포함
```

모든 Branch에서 같은 Authorization Context를 사용합니다.

```text
Authorization Context
  ├→ Vector Filter
  ├→ Keyword Filter
  ├→ Metadata Filter
  ├→ Graph Traversal Policy
  └→ Direct Object Lookup
        ↓
Authorized Result Fusion
```

Filter Compiler (필터 변환기)는 하나의 Canonical Policy에서 Engine별 Query를 생성하고, 누락된 Branch가 있으면 검색을 거부합니다.

## 16. Filter와 ANN 품질을 함께 시험한다

근사 Vector 검색에서는 Filter가 강해질수록 후보가 줄어 Top-k를 충분히 채우지 못할 수 있습니다.

이때 보안을 위해 Filter를 약화하면 안 됩니다.

대안은 다음과 같습니다.

- Tenant·고빈도 분류별 Partition
- Filter Field의 별도 Index
- Partial Index
- Engine의 Filtered ANN 기능
- Iterative Scan·Probe 범위 조정
- 작은 권한 집합에는 Exact Search
- Tenant 규모에 따른 Index Tier 분리

pgvector도 Approximate Index와 Filter를 함께 쓸 때 결과 수가 줄 수 있고, Iterative Scan·Partial Index·Partition을 선택할 수 있다고 설명합니다.

다음 두 Metric을 분리합니다.

```text
Security Isolation
  비인가 Chunk 반환 수 = 0

Authorized Recall
  권한이 있는 정답 Chunk를 찾는 비율
```

검색 품질 저하를 해결하기 위해 Tenant Filter를 제거하는 변경은 허용하지 않습니다.

## 17. Retrieval 결과를 객체 단위로 다시 인가한다

Index Filter는 빠른 후보 제한을 담당하지만 최종 권한의 유일한 근거로 사용하지 않습니다.

Search Result를 Model Context에 넣기 전에 현재 객체 권한을 다시 확인합니다.

```json
{
  "retrievalRequestId": "ret_opaque_id",
  "candidate": {
    "chunkId": "chk_opaque_id",
    "documentId": "doc_opaque_id",
    "tenantId": "ten_opaque_id",
    "aclVersion": "acl_fixture_v7",
    "status": "ACTIVE"
  },
  "authorizationDecision": {
    "decision": "allow",
    "reasonCodes": [
      "TENANT_MATCH",
      "GROUP_ALLOWED",
      "OBJECT_ACTIVE"
    ],
    "policyVersion": "rag_policy_fixture_v1",
    "decisionId": "dec_opaque_id"
  }
}
```

특히 다음 상황에서 재인가가 중요합니다.

- Index ACL이 오래됐을 수 있음
- 사용자 Group Membership이 변경됨
- Source 문서가 삭제·이동됨
- Legal Hold·Classification이 변경됨
- 공유 Link가 만료됨
- Search Index와 Source가 비동기 동기화됨

재인가 실패 Candidate는 Reranker, LLM, Citation과 Cache에 전달하지 않습니다.

## 18. Reranker와 Model에는 허용된 최소 Chunk만 전달한다

Reranker가 외부 Model Service라면 비인가 Candidate를 모두 보낸 뒤 순위만 받는 구조는 이미 데이터 노출입니다.

안전한 순서는 다음과 같습니다.

```text
권한 Filter
  → 객체 재인가
    → 허용 Candidate만 Rerank
      → Top Document·Chunk 제한
        → Model Context
```

Context Minimization (문맥 최소화)을 적용합니다.

- 질문에 필요한 Chunk만 전달
- 동일 문서의 과도한 인접 Chunk 제한
- 민감 Field·숨은 Metadata 제거
- 데이터 등급에 맞는 Model Endpoint 사용
- 출처와 권한 Context는 Application이 관리

Model의 긴 Context Window를 사용할 수 있다는 이유로 권한 있는 모든 문서를 한 번에 넣지 않습니다.

## 19. Query 자체도 탐색 공격의 입력이다

권한 Filter가 있어도 공격자가 Query를 조금씩 바꾸며 존재하는 주제, 문서와 Group 구조를 추정할 수 있습니다.

Query Reconnaissance (검색 정찰)에 대비합니다.

- 사용자·Agent·Tenant별 Rate Limit
- Query Pattern과 반복 변형 탐지
- 결과 수·Score·Index 통계 노출 제한
- 권한 없음과 존재하지 않음의 Error 구분 최소화
- Wildcard·Filter DSL 직접 입력 차단
- Query Length·복잡도·Top-k 제한
- 비정상 Export·Pagination 탐지

OWASP RAG Security 지침도 반복 Query로 Corpus 구조를 탐색하는 행동을 Monitor하고 사용자·Agent별 Rate Limit을 적용하도록 권고합니다.

검색 실패 시 권한 Filter를 건너뛰거나 Model-only 답변으로 조용히 전환하지 않습니다.

## 20. Citation과 원문 열기에서 권한을 다시 확인한다

안전한 검색 결과도 Citation Endpoint에서 ID만으로 원문을 반환하면 Broken Object Level Authorization (객체 수준 인가 실패)이 됩니다.

다음 기능은 모두 독립적으로 인가합니다.

```text
문서 제목·Excerpt 표시
원문 Page 열기
File Download
Thumbnail·Preview
OCR Text
Summary·Entity
공유 Link 생성
다른 Tool로 전달
```

Citation은 Model이 만든 URL을 그대로 사용하지 않습니다.

Application이 `documentId`, `chunkId`, Version과 Hash를 검증해 사용자에게 허용된 Link를 생성합니다.

```json
{
  "citationId": "cit_opaque_id",
  "documentId": "doc_opaque_id",
  "chunkId": "chk_opaque_id",
  "sourceVersion": "source_fixture_v3",
  "contentHash": "sha256_fixture_chunk",
  "authorizationDecisionId": "dec_opaque_id",
  "expiresAt": "2026-07-29T14:10:00Z"
}
```

Citation Metadata 자체에도 민감한 제목·경로·Owner가 포함될 수 있으므로 최소한만 반환합니다.

## 21. Semantic Cache도 검색 권한 경계다

Semantic Cache (의미 기반 캐시)는 비슷한 질문에 이전 답변을 재사용합니다.

Query Text만 Cache Key로 사용하면 다른 Tenant나 다른 권한 사용자가 같은 답변을 받을 수 있습니다.

Cache Context는 최소한 다음을 포함합니다.

```json
{
  "cacheContext": {
    "tenantId": "ten_opaque_id",
    "subjectId": "usr_opaque_id",
    "groupSetDigest": "sha256_fixture_group_digest",
    "authorizationContextVersion": 12,
    "policyVersion": "rag_policy_fixture_v1",
    "indexSecurityVersion": "index_security_fixture_v4",
    "modelVersion": "model_fixture_v1",
    "retrievalMode": "hybrid"
  },
  "dependencies": [
    {
      "documentId": "doc_opaque_id",
      "aclVersion": "acl_fixture_v7",
      "sourceVersion": "source_fixture_v3"
    }
  ]
}
```

Cache Hit에서도 현재 Membership, ACL Version과 문서 상태를 확인합니다.

권한 철회·삭제·Tenant Offboarding 시 관련 Query·Retrieval·Rerank·Response Cache를 무효화해야 합니다.

## 22. 비동기 Pipeline에는 권한 Metadata를 함께 전달한다

수집, OCR, Chunking, Embedding과 Indexing은 Queue 기반 비동기 작업일 수 있습니다.

Message에 본문만 담으면 중간 Worker가 Tenant와 ACL을 잃을 수 있습니다.

```json
{
  "jobId": "idx_opaque_id",
  "tenantId": "ten_opaque_id",
  "documentId": "doc_opaque_id",
  "sourceVersion": "source_fixture_v3",
  "aclVersion": "acl_fixture_v7",
  "classification": "CONFIDENTIAL",
  "operation": "UPSERT_INDEX",
  "policyVersion": "rag_policy_fixture_v1",
  "notAfter": "2026-07-29T15:00:00Z"
}
```

Consumer는 다음을 검증합니다.

- Tenant·Document 관계
- Source·ACL Version 최신성
- 작업 만료와 중복 여부
- 현재 Document 상태
- Worker의 Index Write 권한
- 대상 Namespace·Partition

Dead Letter Queue와 Retry Log에도 원문 Chunk·Embedding·ACL 전체를 무제한 저장하지 않습니다.

## 23. 권한 변경은 Index에 Event로 전파한다

Source ACL 변경을 정기 전체 재색인으로만 처리하면 철회가 오래 지연될 수 있습니다.

ACL Change Event (접근 권한 변경 이벤트)를 별도 처리합니다.

```json
{
  "eventId": "evt_opaque_id",
  "eventType": "DOCUMENT_ACL_CHANGED",
  "tenantId": "ten_opaque_id",
  "documentId": "doc_opaque_id",
  "previousAclVersion": "acl_fixture_v7",
  "newAclVersion": "acl_fixture_v8",
  "changeDirection": "RESTRICT",
  "occurredAt": "2026-07-29T14:02:00Z",
  "sourceVersion": "source_fixture_v4"
}
```

권한 축소는 다음 순서로 처리합니다.

```text
즉시 Deny Overlay·Tombstone
  → Cache 무효화
    → Index Chunk ACL 갱신
      → 검색 Negative Test
        → Overlay 해제
```

권한 확대는 Index가 갱신될 때까지 잠시 검색되지 않아도 기밀성 침해는 아닙니다.

Revoke Propagation SLO (권한 철회 전파 목표)를 별도로 정의하고 지연을 Monitor합니다.

## 24. 삭제는 Tombstone을 먼저 적용하고 물리 삭제를 추적한다

원본이 삭제됐다고 Vector와 Cache가 자동으로 사라지는 것은 아닙니다.

Deletion Tombstone (삭제 표식)은 검색 경로를 즉시 차단합니다.

```json
{
  "tombstoneId": "del_opaque_id",
  "tenantId": "ten_opaque_id",
  "documentId": "doc_opaque_id",
  "sourceObjectId": "src_opaque_id",
  "deleteReason": "SOURCE_DELETED",
  "effectiveAt": "2026-07-29T14:03:00Z",
  "targets": [
    "document_store",
    "chunk_store",
    "vector_index",
    "keyword_index",
    "semantic_cache",
    "response_cache",
    "preview_store"
  ],
  "status": "BLOCKED_PENDING_PHYSICAL_DELETE"
}
```

그 뒤 물리 삭제를 각 저장소에서 완료하고 증거를 수집합니다.

```text
원본·파생 Document
Chunk·Embedding
Keyword·Metadata Index
Summary·Entity·Fact
Cache·Preview
Evaluation Copy
Snapshot·Backup 정책
```

OWASP RAG Security 지침도 원본 삭제·권한 제거가 Vector Store, Cache와 파생 Index에 명시적으로 전파돼야 한다고 설명합니다.

Audit Log는 법적 보존과 삭제 요구를 별도 정책으로 처리하되 원문을 불필요하게 보관하지 않습니다.

## 25. 멱등 인덱싱 Key에 보안 Version을 포함한다

같은 문서 본문이라도 ACL이 바뀌면 보안 상태가 달라집니다.

Content Hash만으로 “이미 인덱싱됨”을 판단하면 ACL Update를 놓칠 수 있습니다.

```text
Index Identity
  tenantId
  sourceObjectId
  sourceVersion
  contentHash
  chunkingVersion
  embeddingVersion
  aclVersion
  policyVersion
  indexSecuritySchemaVersion
```

본문이 같고 ACL만 변경된 경우 Embedding을 다시 만들 필요는 없을 수 있습니다.

하지만 Chunk의 Security Metadata, Filter Index와 Cache Dependency는 반드시 갱신해야 합니다.

```text
Content Change
  → Chunk·Embedding·Security Metadata 갱신

ACL-only Change
  → Security Metadata·Filter Index·Cache 갱신

Delete
  → 즉시 Tombstone + 모든 파생물 제거
```

멱등성은 중복 방지뿐 아니라 최신 권한 Version이 적용됐다는 증거를 포함해야 합니다.

## 26. Index Writer와 Search Reader 권한을 분리한다

검색 Application이나 Agent Endpoint가 Vector Index에 직접 Write할 수 있으면 Data Poisoning과 권한 Metadata 변조가 쉬워집니다.

```text
Ingestion Writer
  검증된 Pipeline만 Insert·Update·Delete

Search Reader
  허용된 Namespace·Filter Query만 Read

Index Administrator
  Schema·Snapshot·Rebuild

Security Auditor
  무결성·격리·삭제 증거 조회
```

다음 운영 통제가 필요합니다.

- Writer Workload Identity와 최소 권한
- Schema·Filter Field 변경 승인
- Index Mutation 감사
- 문서·Chunk Count와 Tenant 분포 이상 탐지
- Snapshot·Checksum·복구 시험
- 비정상 Bulk Upload·Delete Alert
- Agent·사용자의 직접 Index Endpoint 접근 차단

OWASP는 Index Write를 승인된 Ingestion Pipeline로 제한하고, 수정 Event와 무결성을 Monitor하도록 권고합니다.

## 27. Backup·Export·관리 도구에도 Tenant 경계를 적용한다

Production Query가 안전해도 다음 경로에서 전체 Tenant 데이터가 노출될 수 있습니다.

```text
Snapshot·Backup
Reindex·Migration
Analytics Export
Debug Console
Search Playground
Evaluation Dataset Builder
Support Download
Disaster Recovery 복원
```

확인할 항목은 다음과 같습니다.

- Backup Encryption Key와 조회 권한
- Tenant별 Export 승인과 범위
- 복원 환경의 Network·Identity 통제
- 개발 환경으로 운영 Snapshot 복사 금지
- Offboarding Tenant의 Backup Retention
- Admin Query에도 명시적 Tenant 범위 요구
- Break-glass 사용과 사후 검토

`admin=true`라는 이유로 Tenant Filter를 자동 제거하지 않습니다.

다중 Tenant 조사가 필요하면 목적, 승인, 대상 Tenant, 시간과 Export 위치를 명확히 결속합니다.

## 28. Retrieval 감사 Event를 구조화한다

모든 Query 원문과 Chunk Text를 Audit Log에 저장하면 감사 저장소가 새로운 민감정보 저장소가 됩니다.

다음 Metadata 중심으로 기록합니다.

```json
{
  "eventType": "rag_retrieval_completed",
  "retrievalRequestId": "ret_opaque_id",
  "subjectId": "usr_opaque_id",
  "tenantId": "ten_opaque_id",
  "queryDigest": "sha256_fixture_query_digest",
  "authorizationContextVersion": 12,
  "policyVersion": "rag_policy_fixture_v1",
  "indexSecurityVersion": "index_security_fixture_v4",
  "candidateCount": 20,
  "authorizedResultCount": 5,
  "deniedCandidateCount": 0,
  "documentIds": [
    "doc_opaque_id"
  ],
  "decisionIds": [
    "dec_opaque_id"
  ],
  "crossTenantResultCount": 0,
  "occurredAt": "2026-07-29T14:04:00Z"
}
```

반복적인 다른 Tenant ID 접근, 비정상 Query 변형, 대량 Pagination, Filter 누락과 철회된 문서 검색을 Security Event로 탐지합니다.

원문이 Incident 조사에 필요하다면 별도 승인·암호화·보존 정책 아래 제한적으로 수집합니다.

## 29. Cross-tenant Negative Test를 Release Gate로 사용한다

Multi-tenant RAG 보안은 정상 질문의 답변 품질만으로 검증할 수 없습니다.

| 시험 | 기대 결과 |
|---|---|
| Query의 Tenant ID 변조 | Server Context로 무시·다른 Tenant 결과 0 |
| 다른 Tenant Document ID 직접 조회 | 거부·내용·제목·존재 여부 비노출 |
| Vector Branch Filter 제거 | Contract 검증 실패·검색 차단 |
| Keyword Branch Filter 제거 | Result Fusion 전에 실패 |
| ACL 없는 Chunk 삽입 | Index Write 거부·검역 |
| 다른 Tenant Namespace 지정 | 거부 |
| Group Membership 철회 직후 검색 | 결과 0·Cache Miss·거부 Event |
| Source 삭제 직후 검색 | Tombstone으로 즉시 차단 |
| ACL Version 오래된 Cache | 무효화·재검색 |
| Citation URL 재사용 | 현재 사용자 객체 인가 실패 |
| Reranker에 비인가 Candidate 전달 | 전송 0건 |
| Admin Search에서 Tenant 누락 | Default Deny |
| Backup Export로 다른 Tenant 포함 | 범위 검증 실패 |
| 동일 Query 반복으로 Score 탐색 | Rate·탐지 정책 작동 |
| Search Service 장애 | Filter 없는 Fallback 금지 |

테스트 Fixture에는 Tenant A와 Tenant B에 의미가 매우 비슷한 문서를 넣습니다.

그래야 Vector 유사도가 높아도 권한 경계가 결과를 완전히 분리하는지 확인할 수 있습니다.

## 30. 운영 전 체크리스트

### 수집·권한 Metadata

- [ ] Tenant Context를 인증된 사용자·Membership에서 결정한다.
- [ ] Crawler의 기술 권한과 최종 사용자 검색 권한을 분리한다.
- [ ] Source ACL·상속·Deny·Group·Classification을 함께 수집한다.
- [ ] 표현할 수 없는 ACL을 더 넓게 허용하지 않는다.
- [ ] Document Security Envelope에 Tenant·ACL Version·분류·Hash를 저장한다.
- [ ] OCR·Summary·Entity·Embedding 등 파생물에 권한과 Provenance를 전파한다.

### Chunk·Index 격리

- [ ] 모든 Chunk에 원본 Document·Tenant·ACL Version을 연결한다.
- [ ] 파생 데이터의 보안 등급을 자동으로 낮추지 않는다.
- [ ] Tenant 위험에 맞는 Cluster·Index·Namespace·Partition 전략을 선택한다.
- [ ] Shared Index에는 강제 Filter·저장소 보안·결과 재인가를 함께 적용한다.
- [ ] Index Writer·Search Reader·Administrator 권한을 분리한다.
- [ ] Embedding Model과 Cache도 Tenant의 데이터 처리 정책을 따른다.

### Retrieval·Context

- [ ] Model이 Tenant·Group·Clearance를 생성하거나 변경할 수 없다.
- [ ] Canonical Filter Plan에서 모든 Search Branch Query를 만든다.
- [ ] Vector·Keyword·Metadata·Graph·Direct Lookup에 같은 권한을 적용한다.
- [ ] Engine의 Pre·During·Post Filter 의미를 실제 Query와 Trace로 검증한다.
- [ ] 비인가 Candidate를 Reranker와 Model에 전달하지 않는다.
- [ ] Model Context를 허용된 최소 Document·Chunk로 제한한다.
- [ ] Citation·Preview·Download·공유 기능에서 객체 권한을 재검증한다.

### Cache·변경·삭제

- [ ] Cache Key에 Tenant·Subject·Group·권한·정책 Version을 포함한다.
- [ ] Cache Hit에서도 Membership·ACL·Document 상태를 확인한다.
- [ ] ACL 변경을 Event로 전파하고 권한 축소를 먼저 차단한다.
- [ ] Revoke Propagation SLO와 지연 Alert가 있다.
- [ ] 삭제 시 Tombstone을 즉시 적용한 뒤 모든 파생물을 제거한다.
- [ ] Content Hash뿐 아니라 ACL·Policy·Security Schema Version을 추적한다.
- [ ] Orphan Chunk·Embedding·Cache를 정기 검사한다.

### 운영·검증

- [ ] Query·Retrieval·인가·Citation을 Decision ID로 연결한다.
- [ ] Score·통계·Error를 통한 Corpus 추정을 제한한다.
- [ ] Tenant별 Query Rate·Top-k·Export·비용 한도가 있다.
- [ ] Backup·Migration·Evaluation·Support 도구에도 Tenant 경계를 적용한다.
- [ ] 의미가 유사한 Cross-tenant Fixture로 격리 Test를 실행한다.
- [ ] 모든 경로에서 Cross-tenant Result 목표를 0으로 둔다.
- [ ] Search·Authorization 장애 시 Filter 없는 Fallback을 금지한다.

## 마무리

멀티테넌트 RAG의 보안 흐름은 다음과 같이 정리할 수 있습니다.

```text
인증된 Subject·Tenant
  → Source ACL과 수집 권한 분리
    → Document Security Envelope
      → Chunk·Embedding 권한 상속
        → Index·Namespace·Partition 격리
          → 모든 Search Branch의 권한 Filter
            → 객체 재인가
              → 최소 Reranker·Model Context
                → Citation·Cache 재인가
                  → ACL 변경·삭제 전파
                    → Cross-tenant Negative Test
```

핵심 원칙은 다음과 같습니다.

1. Tenant는 Prompt와 Tool 인자가 아니라 인증 결과에서 결정합니다.
2. Crawler가 읽을 수 있다는 사실을 전체 사용자 검색 권한으로 바꾸지 않습니다.
3. ACL·분류·보존·삭제 정보를 모든 Chunk와 파생물에 전파합니다.
4. 검색 후 답변에서 가리지 않고 권한 있는 후보 집합 안에서 검색합니다.
5. Vector·Keyword·Reranker·Citation·Cache의 모든 경로에 같은 권한을 적용합니다.
6. Shared Index는 Filter 하나가 아니라 Namespace·저장소 권한·객체 재인가로 보완합니다.
7. ACL 철회와 삭제는 재색인을 기다리지 않고 즉시 Deny Overlay와 Tombstone으로 차단합니다.
8. 의미가 비슷한 Cross-tenant 문서를 사용해 결과가 0건인지 반복 검증합니다.

RAG 보안의 목적은 다른 Tenant의 내용이 최종 답변에 우연히 나오지 않기를 기대하는 것이 아닙니다.

**다른 Tenant의 문서가 검색 후보, Reranker, Model Context, Citation과 Cache 어디에도 들어오지 않았다는 증거를 만드는 것**입니다.

다음 글에서는 File Upload (파일 업로드) 경로를 Presigned URL (사전 서명 URL), Quarantine (검역), 형식·크기 검증, Malware Scan (악성코드 검사)과 Decompression Bomb (압축 폭탄) 방어로 구성하는 방법을 살펴보겠습니다.

## 참고 자료

- [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)
- [OWASP LLM08:2025 Vector and Embedding Weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/)
- [OWASP Multi Tenant Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)
- [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [OWASP Insecure Direct Object Reference Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html)
- [NIST SP 800-162: Guide to Attribute Based Access Control](https://csrc.nist.gov/pubs/sp/800/162/upd2/final)
- [NIST SP 800-207: Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final)
- [pgvector: Filtering and Multitenancy](https://github.com/pgvector/pgvector)
- [PostgreSQL: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [OpenSearch: Filtering Vector Search Results](https://docs.opensearch.org/latest/vector-search/filter-search-knn/index/)
- [Azure AI Search: Security Filter Pattern](https://learn.microsoft.com/en-us/azure/search/search-security-trimming-for-azure-search)
- [Azure AI Search: Query-Time ACL and RBAC Enforcement](https://learn.microsoft.com/en-us/azure/search/search-query-access-control-rbac-enforcement)
- [Azure AI Search: Vector Query Filters](https://learn.microsoft.com/en-us/azure/search/vector-search-filters)
- [Elasticsearch: Filtered kNN Search](https://www.elastic.co/docs/solutions/search/vector/knn)

---

> 이 글은 2026년 7월 29일 기준 OWASP, NIST, pgvector, PostgreSQL, OpenSearch, Azure AI Search와 Elasticsearch의 공식 공개 자료 및 공개 가능한 엔터프라이즈 RAG 보안 설계 경험을 바탕으로 작성했습니다. 예시 ID, Domain, ACL, Role, Classification, Version, Hash, 수명과 정책은 설명용 Fixture이며 실제 고객·Tenant·계정·내부 시스템 정보가 아닙니다. 실제 적용 시 Source 권한 모델, Vector Engine의 Filter 의미, 데이터 분류, Embedding Provider, Cache·Backup, 삭제 의무, 관련 법규와 Tenant별 계약을 검토하고 Cross-tenant Negative Test와 권한 철회·삭제 전파 시험으로 검증해야 합니다.
