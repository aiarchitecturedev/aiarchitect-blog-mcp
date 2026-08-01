# Tistory 기술자료 초안

- 문서 ID: `BLOG-11`
- 상태: 공개 완료
- Tistory 상태: 공개 게시·공개 페이지 검증 완료
- 공개 URL: `https://aiarchitect.tistory.com/9`
- 분류: `RAG · LLM 시스템`
- 권장 제목: `RAG 운영 설계: 멱등 인덱싱 (Idempotent Indexing)과 중복 Chunk 방지`
- 검색 설명: `RAG 수집 작업이 재시도되거나 원문·Chunker·Embedding 모델이 바뀌어도 중복 Vector와 오래된 Chunk가 남지 않도록 원본 키 (Source Key), 원본 버전 (Revision), 내용 해시 (Content Hash), 결정적 Chunk ID와 활성 버전을 설계하는 방법을 정리합니다.`
- 권장 태그: `RAG`, `Idempotent Indexing`, `Vector Database`, `Chunking`, `Embedding`, `Content Hash`, `데이터 파이프라인`
- 권장 대표 이미지: `portfolio/architecture-diagrams/02-meeting-knowledge-automation.svg`

---

# RAG 운영 설계: 멱등 인덱싱 (Idempotent Indexing)과 중복 Chunk 방지

검색 증강 생성 (Retrieval-Augmented Generation, RAG) 데모에서는 문서를 읽고 검색 단위 조각 (Chunk)으로 나눈 뒤 벡터 표현 (Embedding)을 저장하면 작업이 끝난 것처럼 보입니다.

운영 환경에서는 같은 수집 작업이 반복됩니다.

- Worker가 Vector 저장 뒤 응답을 받기 전에 종료됩니다.
- Scheduler와 사용자의 수동 재처리가 동시에 실행됩니다.
- 원본 문서가 수정됩니다.
- 문서 해석기 (Parser) 또는 문서 분할기 (Chunker) 설정이 바뀝니다.
- Embedding 모델이 교체됩니다.
- 삭제된 문서의 예전 Chunk가 검색됩니다.
- 같은 파일이 다른 이름이나 경로로 다시 들어옵니다.

이 상황에서 매 실행마다 새 UUID를 만들고 Vector Database에 `insert`하면 의미가 같은 Chunk가 계속 쌓입니다. 검색 결과는 같은 문장으로 채워지고, 오래된 정책과 새 정책이 함께 노출되며, 저장량과 Embedding 비용도 증가합니다.

반대로 `upsert`만 호출한다고 문제가 자동으로 해결되지는 않습니다. **어떤 ID로 업서트 (Upsert, 있으면 갱신하고 없으면 생성)할지, 사라진 Chunk를 어떻게 찾을지, 어떤 원본 버전 (Revision)을 검색에 노출할지**가 먼저 정의돼야 합니다.

운영형 구조는 다음 네 식별자를 분리하는 데서 시작합니다.

```text
Source Key
  └─ Source Revision
       └─ Chunk ID
            └─ Embedding Generation
```

## 1. 중복을 네 가지로 나눠야 원인을 찾을 수 있다

RAG에서 “중복 Chunk”는 하나의 현상이 아닙니다.

| 중복 유형 | 예시 | 필요한 기준 |
|---|---|---|
| 요청 중복 | 같은 수집 요청 재전송 | 수집 작업 키 (Ingestion Key) |
| 원본 중복 | 같은 문서가 두 경로로 발견 | 원본 키 (Source Key)·원문 Hash |
| Chunk 중복 | 같은 Revision을 다시 분할 | 결정적 Chunk ID (Deterministic Chunk ID) |
| 검색 중복 | 다른 문서가 같은 내용을 포함 | 검색 결과 중복 제거 (Retrieval Deduplication) |

각 중복은 처리 위치가 다릅니다.

```text
API · Scheduler       → Ingestion Key
Connector · Source    → Source Key
Parser · Chunker      → Revision · Chunk ID
Vector Retrieval      → Search-time Dedup
```

검색 단계에서 유사 문장을 제거해도 저장소 안의 중복 Vector와 잘못된 활성 버전은 남습니다. 반대로 저장 단계가 완전히 멱등해도 여러 문서가 동일한 약관이나 공지를 포함하면 검색 결과 중복 제거가 필요합니다.

## 2. 원본 (Source), 원본 버전 (Revision), Chunk와 Embedding의 수명을 분리한다

한 문서를 하나의 `documentId`로만 표현하면 변경 원인을 추적하기 어렵습니다.

| 단위 | 바뀌지 않는 기준 | 새 버전이 필요한 경우 |
|---|---|---|
| Source | 외부 시스템 안의 논리적 원본 | 원본 자체가 다른 문서가 됨 |
| Revision | 정규화된 원문 내용 | 본문 또는 검색에 쓰는 Metadata 변경 |
| Chunk | Revision과 Chunker 결과 | 원문·Chunker 정책 변경 |
| Embedding | Chunk와 모델 설정 | 모델·차원·전처리 변경 |

예시는 다음과 같습니다.

```json
{
  "sourceKey": "src_opaque_hash",
  "revisionId": "rev_opaque_hash",
  "chunkId": "chk_opaque_hash",
  "embeddingGeneration": {
    "model": "embedding-model-family",
    "modelVersion": "version-identifier",
    "dimensions": 1536,
    "preprocessorVersion": "embed-preprocess-v2"
  }
}
```

`sourceKey`는 원본의 정체성을 나타내고 `revisionId`는 특정 시점의 내용을 나타냅니다. 같은 Source의 제목 한 줄이 수정돼도 새 Revision이 생길 수 있지만 Source 자체는 유지됩니다.

Embedding 모델만 바뀐 경우에는 Chunk를 다시 만들 필요가 없습니다. 같은 Chunk에 새 임베딩 생성 버전 (Embedding Generation)을 추가한 뒤 검색 대상을 전환할 수 있습니다.

## 3. 원본 키 (Source Key)는 경로보다 업무 식별자를 우선한다

Source Key를 파일명이나 URL 전체로만 만들면 이동과 이름 변경에 취약합니다.

권장 우선순위는 다음과 같습니다.

1. 원본 시스템이 제공하는 불변 ID
2. 테넌트와 Connector 범위의 복합 키 (Composite Key)
3. 관리되는 저장소의 Object ID
4. 불변 ID가 없을 때만 정규화된 위치와 별도 중복 판단

```text
sourceKey = HASH(
  tenantScope,
  connectorType,
  sourceSystemId
)
```

다음 두 문서는 같은 이름이어도 다른 Source일 수 있습니다.

```text
tenant-A / drive / document-42
tenant-B / drive / document-42
```

따라서 테넌트 범위를 빼고 Hash를 만들면 서로 다른 조직의 문서가 충돌할 수 있습니다.

반대로 위치가 바뀌어도 원본 시스템 ID가 같다면 같은 Source로 유지하는 것이 좋습니다.

```text
/team-a/policy.pdf → /archive/policy.pdf
sourceSystemId는 동일 → 같은 Source
```

Source Key 원재료에 실제 고객명, 문서 제목과 URL을 그대로 노출하지 않습니다. 운영 Log에는 계산된 불투명 Key를 남기고, 원본 위치는 권한이 통제된 Metadata Store에서만 조회합니다.

## 4. 내용 해시 (Content Hash) 전에 정규화 규칙을 버전으로 고정한다

같은 문서라도 Byte 표현은 달라질 수 있습니다.

- 줄바꿈이 `CRLF`에서 `LF`로 바뀜
- Unicode가 조합형·분해형으로 다름
- HTML의 공백과 속성 순서가 다름
- PDF Parser 버전이 Text 순서를 다르게 추출
- JSON Object의 Property 순서가 다름

원본 Byte Hash는 파일 무결성 확인에 유용하지만 검색용 내용이 같은지 판단하는 기준과는 다를 수 있습니다.

권장 Hash를 분리합니다.

```text
binaryHash       = SHA-256(original bytes)
canonicalHash    = SHA-256(canonical extracted content)
revisionId       = HASH(sourceKey, canonicalHash, parserPolicyVersion)
```

텍스트 정규 표현 (Text Canonicalization) 정책의 예시는 다음과 같습니다.

```text
1. Character Encoding을 UTF-8로 통일
2. Unicode NFC 적용
3. CRLF·CR을 LF로 통일
4. 의미 없는 줄 끝 공백 제거
5. Parser가 생성한 반복 Header·Footer를 정의된 규칙으로 제거
6. 문단 경계는 보존
```

Unicode는 NFC, NFD, NFKC와 NFKD의 네 가지 정규화 형식을 정의합니다. NFKC는 표시 차이까지 합칠 수 있어 원문의 의미 구분을 지울 수 있으므로 임의로 적용하지 않습니다. 원문은 별도로 보존하고 검색용 정규화 결과와 정책 버전을 기록합니다.

```json
{
  "normalizer": {
    "unicodeForm": "NFC",
    "lineEnding": "LF",
    "trimTrailingWhitespace": true,
    "boilerplateRuleVersion": "public-rule-v1"
  }
}
```

구조화 JSON을 Hash할 때는 Key 정렬만 직접 구현하기보다 정규 직렬화 (Canonical Serialization) 규칙을 공유해야 합니다. RFC 8785의 JSON 정규화 방식 (JSON Canonicalization Scheme, JCS)은 결정적인 Property 정렬과 직렬화 방법을 정의합니다.

주의할 점은 JCS 자체가 Unicode 문자열을 NFC로 변환하지 않는다는 것입니다. Text 정규화와 JSON 직렬화는 서로 다른 정책으로 관리합니다.

## 5. Hash 입력은 문자열 연결보다 구조화된 형식이 안전하다

다음 ID 생성은 충돌 의미가 모호합니다.

```text
HASH(tenant + ":" + source + ":" + version)
```

값 자체에 `:`가 들어가면 다른 조합이 같은 입력 문자열이 될 수 있습니다.

```text
["a:b", "c"] → "a:b:c"
["a", "b:c"] → "a:b:c"
```

길이 Prefix(길이 접두사) 또는 정규화된 구조를 사용합니다.

```python
import hashlib
import json
import unicodedata


def canonical_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n"))


def deterministic_hash(parts: list[str]) -> str:
    payload = json.dumps(
        parts,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
```

이 예시는 문자열 배열의 순서를 보존해 모호한 구분자 연결을 피하는 최소 예시입니다. 여러 언어가 같은 ID를 생성해야 한다면 JSON Number, Unicode와 직렬화 차이를 포함한 정규화 계약 (Canonical Contract)을 정하고 고정 검증값 (Golden Vector)으로 교차 검증합니다.

SHA-256은 입력이 같으면 같은 Digest(요약값)를 생성합니다. Hash가 같은 내용인지 빠르게 비교하는 도구가 될 수 있지만, Hash만 보고 업무상 같은 문서인지 결정하지는 않습니다. Source 정체성과 내용 동일성은 별도 축입니다.

## 6. Chunk ID (청크 식별자)에는 분할 정책 버전이 들어가야 한다

같은 원문도 Chunk 설정에 따라 결과가 달라집니다.

```text
chunker-v1: 500 tokens, overlap 50
chunker-v2: topic boundary, max 700 tokens, overlap 80
```

Chunker 설정을 바꾸고 같은 ID를 사용하면 이전 Vector가 새 Text로 조용히 덮어써집니다. 어떤 정책으로 검색됐는지 재현하기 어렵습니다.

분할 정책 지문 (Chunker Fingerprint)에 다음 정보를 포함합니다.

```json
{
  "algorithm": "topic-aware",
  "maxTokens": 700,
  "overlapTokens": 80,
  "tokenizer": "tokenizer-family",
  "tokenizerVersion": "version-identifier",
  "sentenceSplitterVersion": "ko-public-v2",
  "metadataPolicyVersion": "metadata-v3"
}
```

결정적 Chunk ID 예시는 다음과 같습니다.

```text
chunkId = HASH(
  sourceKey,
  revisionId,
  chunkerFingerprint,
  ordinal,
  chunkContentHash
)
```

`ordinal`만 사용하면 중간 문장 삽입 뒤 이후 Chunk의 의미가 모두 이동할 수 있습니다. `chunkContentHash`만 사용하면 같은 문장이 한 문서에 두 번 등장했을 때 충돌할 수 있습니다. Revision, 정책, 순서와 내용을 함께 묶으면 재현과 중복 구분이 쉬워집니다.

각 Chunk는 원문으로 돌아갈 수 있어야 합니다.

```json
{
  "chunkId": "chk_opaque_hash",
  "sourceKey": "src_opaque_hash",
  "revisionId": "rev_opaque_hash",
  "ordinal": 12,
  "startOffset": 8420,
  "endOffset": 9175,
  "contentHash": "sha256:opaque-digest",
  "sourceSegmentIds": [
    "segment-opaque-a",
    "segment-opaque-b"
  ]
}
```

Offset(원문 위치)은 Parser가 안정적으로 제공할 때 사용합니다. PDF Layout이나 OCR 순서가 바뀌는 환경에서는 Page, Block, 시간 범위와 원문 Segment ID를 함께 보존합니다.

## 7. Chunk와 Embedding을 별도 Record로 관리한다

Chunk Text와 Embedding Vector를 한 Record에만 저장하면 모델 교체 때 Chunk까지 중복 생성하기 쉽습니다.

논리적으로 두 Table을 분리할 수 있습니다.

```sql
CREATE TABLE rag_chunk (
    tenant_id        text        NOT NULL,
    chunk_id         text        NOT NULL,
    source_key       text        NOT NULL,
    revision_id      text        NOT NULL,
    chunker_version  text        NOT NULL,
    chunk_ordinal    integer     NOT NULL,
    content_hash     text        NOT NULL,
    content          text        NOT NULL,
    PRIMARY KEY (tenant_id, chunk_id),
    UNIQUE (
        tenant_id,
        revision_id,
        chunker_version,
        chunk_ordinal
    )
);

CREATE TABLE rag_embedding (
    tenant_id             text       NOT NULL,
    chunk_id              text       NOT NULL,
    embedding_model       text       NOT NULL,
    embedding_version     text       NOT NULL,
    dimensions            integer    NOT NULL,
    embedding             vector     NOT NULL,
    PRIMARY KEY (
        tenant_id,
        chunk_id,
        embedding_model,
        embedding_version
    )
);
```

이 Schema(데이터 구조)는 설명용 중립 예시입니다. 실제로는 Foreign Key(외래 키), Row-Level Security(행 단위 보안), Partition(분할), Vector 차원과 Index 정책을 환경에 맞게 추가해야 합니다.

pgvector 공식 문서는 PostgreSQL `ON CONFLICT`를 이용한 Vector Upsert와 `(model_id, item_id)` 같은 복합 Primary Key 사용 예시를 제공합니다.

## 8. 업서트 (Upsert)의 멱등성은 결정적 ID와 고유 제약 (Unique Constraint)이 만든다

같은 Chunk에 매번 새로운 ID를 만들면 Upsert도 매번 새 Record를 생성합니다.

```python
# 잘못된 방식
chunk_id = random_uuid()
collection.upsert(ids=[chunk_id], documents=[text])
```

재시도 사이에서 같은 ID를 계산해야 합니다.

```python
chunk_id = deterministic_hash([
    tenant_scope,
    source_key,
    revision_id,
    chunker_version,
    str(chunk_ordinal),
    chunk_content_hash,
])

collection.upsert(
    ids=[chunk_id],
    documents=[text],
    metadatas=[{
        "source_key": source_key,
        "revision_id": revision_id,
        "chunker_version": chunker_version,
        "ordinal": chunk_ordinal,
    }],
)
```

Chroma 공식 API에서 `upsert`는 ID가 없으면 만들고 존재하면 갱신합니다. PostgreSQL의 `INSERT ... ON CONFLICT DO UPDATE`도 고유 제약 (Unique Constraint) 충돌 시 원자적인 Insert 또는 Update 결과를 제공합니다.

```sql
INSERT INTO rag_chunk (
    tenant_id,
    chunk_id,
    source_key,
    revision_id,
    chunker_version,
    chunk_ordinal,
    content_hash,
    content
)
VALUES (
    :tenant_id,
    :chunk_id,
    :source_key,
    :revision_id,
    :chunker_version,
    :chunk_ordinal,
    :content_hash,
    :content
)
ON CONFLICT (tenant_id, chunk_id)
DO UPDATE SET
    content_hash = EXCLUDED.content_hash,
    content = EXCLUDED.content
WHERE
    rag_chunk.content_hash = EXCLUDED.content_hash
RETURNING chunk_id;
```

같은 `chunk_id`인데 `content_hash`가 다르면 ID 계산 또는 정규화 계약이 깨진 것입니다. 호출자는 `RETURNING` 결과가 정확히 한 건인지 확인하고, 결과가 없으면서 기존 Hash가 다르면 충돌 (Conflict)로 기록한 뒤 작업을 중단해야 합니다.

OpenSearch를 사용하는 경우에도 `POST`로 자동 ID를 만들기보다 결정적 Document ID로 `PUT`해야 재시도가 같은 문서를 갱신합니다. 동시 갱신은 `if_seq_no`와 `if_primary_term`을 이용한 낙관적 동시성 제어 (Optimistic Concurrency Control)로 충돌을 탐지할 수 있습니다.

## 9. 업서트 (Upsert)만으로 사라진 Chunk는 삭제되지 않는다

원문이 짧아져 Chunk가 `10개 → 7개`가 됐다고 가정해 보겠습니다.

```text
새 실행이 Upsert한 ID: 1, 2, 3, 4, 5, 6, 7
기존 저장소의 ID:     1, 2, 3, 4, 5, 6, 7, 8, 9, 10
```

Upsert 뒤에도 `8, 9, 10`은 남습니다. 이 오래된 조각 (Stale Chunk)이 검색되면 삭제된 문장이 답변 근거로 사용됩니다.

전체 결과를 원하는 집합 (Desired Set)으로 보고 기존 집합과 비교합니다.

```text
toUpsert = desiredChunkIds
toDelete = existingChunkIds - desiredChunkIds
```

단, 새 Chunk 저장 도중 실패했는데 먼저 예전 Chunk를 삭제하면 검색 가능한 문서가 사라질 수 있습니다. 새 Revision을 준비 상태 (Staging)로 만든 뒤 검증하고 활성 버전을 전환하는 방식이 안전합니다.

```text
Revision v1 ACTIVE
  │
  ├─ build Revision v2 as STAGING
  ├─ verify chunk count · vectors · metadata
  ├─ switch activeRevision: v1 → v2
  └─ retire and later delete v1
```

Chroma는 ID를 지정한 삭제 API를 제공하므로 폐기된 원본 버전 (Retired Revision)의 정확한 Chunk ID 목록을 기준으로 정리할 수 있습니다. Metadata 조건 삭제를 지원하더라도 테넌트와 Revision 범위를 함께 제한하고 삭제 예상 건수를 먼저 확인합니다.

## 10. 활성 원본 버전 (Active Revision) 전환을 마지막 Commit으로 취급한다

새 Revision의 일부 Chunk만 저장된 상태를 검색에 노출하면 문서가 중간부터 사라진 것처럼 보입니다.

권장 상태는 다음과 같습니다.

```text
DISCOVERED
  → FETCHED
  → PARSED
  → CHUNKED
  → EMBEDDED
  → INDEXED
  → VERIFIED
  → ACTIVE
```

실패 상태도 단계별로 구분합니다.

```text
FETCH_FAILED
PARSE_FAILED
EMBED_FAILED
INDEX_FAILED
VERIFY_FAILED
```

활성화 조건의 예시는 다음과 같습니다.

- 예상 Chunk 수와 저장 Chunk 수가 일치
- 모든 Chunk에 필요한 Embedding이 존재
- Embedding 차원이 모델 계약과 일치
- Source·Revision·테넌트 Metadata가 누락되지 않음
- 표본 검색 (Sample Query)이 새 Revision을 반환
- 삭제 또는 비공개 문서가 포함되지 않음

제어 데이터베이스 (Control Database)에서는 Source가 현재 활성 Revision을 가리키게 할 수 있습니다.

```sql
UPDATE rag_source
SET active_revision_id = :new_revision_id,
    updated_at = CURRENT_TIMESTAMP
WHERE tenant_id = :tenant_id
  AND source_key = :source_key
  AND active_revision_id = :expected_old_revision_id;
```

Update 건수가 `0`이면 다른 Worker가 먼저 활성 버전을 바꿨을 수 있습니다. 현재 상태를 다시 읽고 같은 Revision인지 확인합니다.

검색 엔진 전체를 새 Generation으로 교체하는 대규모 재색인에서는 별도 준비 인덱스 (Shadow Index)를 만든 뒤 논리 이름 (Alias)을 전환할 수 있습니다. OpenSearch 공식 문서는 하나의 Alias Update 요청 안에서 기존 Index 제거와 새 Index 추가가 원자적으로 수행된다고 설명합니다.

## 11. Database와 Vector Store를 하나의 Transaction이라고 가정하지 않는다

Metadata는 PostgreSQL에 저장하고 Vector는 별도 Database에 저장한다면 두 시스템을 하나의 원자적 트랜잭션 (ACID Transaction)으로 Commit하기 어렵습니다.

```text
PostgreSQL commit 성공
Vector upsert 실패
```

또는 반대 상황이 생길 수 있습니다.

```text
Vector upsert 성공
PostgreSQL commit 전 Worker 종료
```

이 경계에서는 “정확히 한 번 실행”을 가정하기보다 다음 구조를 사용합니다.

```text
Control DB Transaction
  ├─ Revision 상태 저장
  ├─ Ingestion Step 저장
  └─ Outbox Event 저장
          │
          ▼
      Index Worker
          │ deterministic chunkId
          ▼
      Vector Upsert
          │
          ▼
      Completion · Verification
```

트랜잭션 내 발행 대기 이벤트 (Outbox)는 업무 상태와 후속 작업 요청을 같은 Database Transaction에 저장합니다. Relay 또는 변경 데이터 캡처 (Change Data Capture, CDC)가 Event를 여러 번 전달할 수 있으므로 Index Worker는 `eventId`와 결정적 Chunk ID로 중복을 흡수합니다.

Debezium 공식 Outbox Event Router 문서도 내부 Database 상태와 다른 서비스가 소비하는 Event 사이의 불일치를 피하기 위한 패턴으로 Outbox를 설명하고, 고유 Event ID를 중복 제거에 사용할 수 있다고 안내합니다.

## 12. 수집 작업 자체에도 재시도 동안 변하지 않는 Key가 필요하다

같은 Source Revision에 같은 Pipeline 설정을 적용하는 작업은 하나의 논리적 실행입니다.

```text
ingestionKey = HASH(
  tenantScope,
  sourceKey,
  revisionId,
  parserVersion,
  normalizerVersion,
  chunkerFingerprint,
  embeddingGeneration
)
```

같은 Key로 두 Worker가 시작되면 하나만 실행권을 가져야 합니다.

```sql
INSERT INTO rag_ingestion_run (
    tenant_id,
    ingestion_key,
    source_key,
    revision_id,
    status
)
VALUES (
    :tenant_id,
    :ingestion_key,
    :source_key,
    :revision_id,
    'RUNNING'
)
ON CONFLICT (tenant_id, ingestion_key)
DO NOTHING;
```

삽입 건수가 `0`이면 기존 Run을 조회합니다.

| 기존 상태 | 후속 동작 |
|---|---|
| `RUNNING`, Lease 유효 | 현재 Worker 종료 또는 관찰 |
| `RUNNING`, Lease 만료 | 소유권 전환 후 Checkpoint부터 재개 |
| `SUCCEEDED` | 저장된 결과 반환 |
| `FAILED_RETRYABLE` | 같은 Key와 다음 Attempt로 재개 |
| `FAILED_FINAL` | 설정 변경 또는 운영자 판단 전 중단 |

매 재시도마다 새 `ingestionKey`를 만들면 중복 실행 방지 효과가 없습니다. `attempt`와 `workerId`는 실행 관측용 값이고 업무 Key와 분리합니다.

## 13. Chunker와 Embedding 모델 변경은 별도 마이그레이션 (Migration)이다

모델을 교체할 때 기존 Vector와 새 Vector를 같은 검색 공간에 무심코 섞으면 안 됩니다.

- Vector 차원이 다를 수 있습니다.
- 모델마다 거리 분포가 다릅니다.
- 같은 숫자 Vector라도 의미 공간이 다릅니다.
- 검색 Threshold와 Reranker 설정이 달라질 수 있습니다.

Embedding Generation에는 최소한 다음을 포함합니다.

```json
{
  "provider": "model-provider",
  "model": "embedding-model-family",
  "modelVersion": "version-identifier",
  "dimensions": 1536,
  "distanceMetric": "cosine",
  "preprocessorVersion": "embed-preprocess-v2"
}
```

Migration 흐름은 다음과 같습니다.

```text
Current Generation A
  ├─ build Generation B
  ├─ validate dimensions and coverage
  ├─ run fixed retrieval evaluation set
  ├─ compare quality · latency · cost
  ├─ switch retrieval target to B
  └─ retain A for rollback window, then retire
```

pgvector 공식 문서는 하나의 `vector` Column에 여러 차원을 저장할 수 있지만 같은 차원의 Row에 대해서만 Expression·Partial Index를 만들 수 있다고 설명합니다. 운영에서는 모델 Generation별 Column, Table, Partition 또는 Index Namespace를 분리하는 편이 정책을 명확하게 만들 수 있습니다.

Chunker 변경도 같은 방식으로 새 Generation을 만듭니다. 기존 ID를 덮어쓰면 이전 검색 결과를 재현하고 A/B 비교하기 어렵습니다.

## 14. 삭제 표식 (Tombstone)에서 모든 파생 데이터까지 전파한다

원본 문서가 삭제되거나 사용자의 접근 권한이 회수됐는데 Vector만 남으면 검색을 통해 내용이 다시 노출될 수 있습니다.

삭제 흐름을 비동기로 운영하더라도 검색 차단은 먼저 적용합니다.

```text
Source DELETE detected
  → Source TOMBSTONED
  → Retrieval deny immediately
  → Chunk · Embedding delete jobs
  → Cache · keyword index invalidation
  → deletion verification
  → retention policy complete
```

삭제 표식 (Tombstone)에는 다음을 기록합니다.

- Source Key
- 테넌트 범위
- 삭제 감지 시각
- 삭제 원인 Code
- 영향을 받는 Revision
- 파생 저장소별 삭제 상태
- 보존·법적 예외 여부

삭제 Event가 중복 전달돼도 같은 Source와 Revision을 대상으로 동작하도록 멱등하게 만듭니다. “없음” 응답은 이미 삭제된 성공 상태로 처리할 수 있습니다.

검색 요청은 Vector 유사도 계산 전후 모두 현재 권한과 Tombstone 상태를 확인해야 합니다. Index 정리가 늦더라도 삭제된 Source를 결과에 포함하지 않는 안전장치가 필요합니다.

## 15. 검색 결과 중복 제거는 저장 멱등성과 별개다

서로 다른 Source가 같은 공지문이나 약관을 포함하면 결정적 ID를 사용해도 여러 결과가 나올 수 있습니다. 이 경우 Source가 다르므로 저장 단계에서 하나로 합치면 출처와 권한이 사라질 수 있습니다.

검색 단계에서는 다음 순서로 처리할 수 있습니다.

```text
Permission Filter
  → Vector · Keyword Retrieval
  → Active Revision Filter
  → Exact Content Hash Dedup
  → Near-duplicate Clustering
  → Reranking
  → Source Diversity
  → LLM Context
```

| 방법 | 장점 | 주의점 |
|---|---|---|
| 같은 `contentHash` 제거 | 정확한 중복을 빠르게 제거 | 출처 목록은 합쳐서 보존 |
| 유사도 기반 Grouping | 거의 같은 문장 축소 | 임계값이 높으면 다른 근거를 합침 |
| Source별 상한 | 한 문서가 결과를 독점하지 않음 | 핵심 문서의 연속 문맥 손실 가능 |
| 인접 Chunk 병합 | 문맥을 자연스럽게 제공 | Token 예산과 중복 구간 관리 |

동일한 Text라도 접근 권한과 보존 정책이 다르면 하나의 공유 Record로 합치지 않습니다. 검색 응답에는 사용자가 실제로 열 수 있는 Source Citation(출처 연결)만 포함합니다.

## 16. 정합성 대조 (Reconciliation)가 누락·중복을 마지막으로 잡는다

멱등 ID와 상태 전이를 설계해도 운영 중 버그, 수동 조작과 외부 장애로 정합성이 깨질 수 있습니다.

정합성 대조 (Reconciliation) Job은 다음을 비교합니다.

```text
Control DB expected state
        ↕
Chunk Store actual state
        ↕
Vector Index actual state
        ↕
Keyword Index actual state
```

권장 검사 항목은 다음과 같습니다.

- Active Revision인데 Chunk가 `0개`
- 예상 Chunk 수와 실제 저장 수 불일치
- Chunk는 있지만 Embedding이 없음
- Embedding은 있지만 Source·Revision Metadata가 없음
- Retired Revision이 검색 결과에 포함
- Tombstoned Source의 Vector가 검색 가능
- 같은 `(revision, chunker, ordinal)`이 여러 개 존재
- 선언 모델과 Vector 차원 불일치
- Orphan Chunk(원본 없는 조각)
- 장시간 `RUNNING` 또는 `STAGING` 상태

자동 복구는 안전한 범위만 수행합니다.

| 상태 | 자동 조치 예시 |
|---|---|
| 누락 Embedding | 결정적 ID로 다시 생성·Upsert |
| 중복 Event | 이미 성공한 결과 반환 |
| Retired Vector 잔존 | 현재 활성 버전 확인 후 삭제 |
| Tombstone 잔존 | 검색 차단 유지 후 삭제 재시도 |
| Hash 불일치 | 자동 덮어쓰기 금지, 격리·조사 |
| 권한 Metadata 누락 | 검색 노출 금지, 재색인 |

삭제와 대량 수정 전에 예상 대상 수, 테넌트와 Revision 범위를 다시 확인합니다.

## 17. 관측성은 Run, Source, Revision과 Chunk를 연결한다

진단에 필요한 Correlation(연결) 구조는 다음과 같습니다.

```text
requestId
  └─ ingestionKey
       └─ runId
            ├─ sourceKey
            ├─ revisionId
            └─ chunkId × N
                 └─ embeddingGeneration
```

권장 지표는 다음과 같습니다.

### 처리량과 비용

- 발견 Source 수
- 신규·변경 없음·변경·삭제 Source 비율
- 생성 Chunk와 Embedding 수
- Content Hash 적중으로 생략한 작업 수
- 모델·Generation별 처리 시간과 비용

### 정합성

- Upsert 생성·갱신 비율
- Unique Conflict 수
- 예상·실제 Chunk 수 차이
- Stale·Orphan Chunk 수
- Active Revision 전환 실패
- Reconciliation 오류와 자동 복구 수

### 검색 영향

- 중복 제거 전후 결과 수
- Retired Revision 검색 차단 수
- Tombstoned Source 차단 수
- Source 다양성
- Citation 열기 실패율

실제 Chunk Text, 문서 제목, URL과 사용자 정보를 Metric Label에 넣지 않습니다. Trace에는 불투명 Source·Revision·Run ID와 상태 Code를 사용하고, 원문은 권한이 통제된 진단 화면에서만 조회합니다.

## 18. 테스트는 같은 입력의 반복 실행부터 시작한다

멱등성은 한 번 성공하는 Test가 아니라 같은 작업을 여러 번 실행했을 때 검증됩니다.

| 시나리오 | 기대 결과 |
|---|---|
| 같은 Source를 두 번 수집 | Source·Revision·Chunk 수 불변 |
| Vector 저장 직후 Worker 종료 | 재시도 후 중복 없이 성공 |
| 같은 수집 요청 동시 실행 | 하나의 Run만 실행권 획득 |
| 줄바꿈만 변경 | 정규화 정책에 따라 같은 Revision |
| 본문 한 문장 변경 | 새 Revision 생성 |
| 중간 문장 삭제 | 새 Revision 활성화 후 예전 Chunk 검색 안 됨 |
| Chunker 설정 변경 | 새 Chunk Generation 생성 |
| Embedding 모델 변경 | 새 Embedding Generation 분리 |
| 활성화 직전 실패 | 기존 Revision 계속 검색 가능 |
| 활성화 응답 유실 | 현재 Active Revision 조회로 결과 확인 |
| 원본 삭제 Event 중복 | 삭제 상태와 결과 동일 |
| 테넌트가 다른 같은 원문 | 저장·검색 범위 분리 |
| Hash 계약이 다른 구현 | Golden Vector Test에서 실패 |
| 일부 Vector 유실 | Reconciliation이 탐지·복구 |

검증식은 단순하게 시작할 수 있습니다.

```text
same input + same policy + repeated execution
→ same sourceKey
→ same revisionId
→ same desired chunkId set
→ same active retrieval result
```

부하 Test에서는 같은 ID에 대한 동시 Upsert, Activation 경쟁, 대량 Retired Revision 정리와 Reconciliation이 실제 저장소의 제한 안에서 동작하는지 확인합니다.

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| 중복 유형 | 요청·원본·Chunk·검색 중복을 구분하는가 |
| Source Key | 테넌트와 원본 시스템의 불변 ID를 포함하는가 |
| Revision | 원본 수정이 새 버전으로 남는가 |
| 정규화 | Unicode·줄바꿈·Parser 규칙과 버전이 고정돼 있는가 |
| Hash | 원본 Byte와 검색용 정규 내용 Hash를 구분하는가 |
| 직렬화 | 언어별로 같은 Canonical Input을 만드는가 |
| Chunk ID | Revision·Chunker·순서·내용을 함께 식별하는가 |
| Chunker | Tokenizer·크기·Overlap·분할 정책 버전이 있는가 |
| Embedding | 모델·버전·차원·전처리 Generation을 기록하는가 |
| 저장 제약 | Primary Key와 Unique Constraint가 중복을 막는가 |
| Upsert | 재시도에서 같은 ID를 사용하는가 |
| Stale 처리 | 새 결과에 없는 이전 Chunk를 정리하는가 |
| Stage | 새 Revision을 완성·검증한 뒤 활성화하는가 |
| 활성 전환 | 경쟁 Update와 응답 유실을 처리하는가 |
| 분산 경계 | Control DB와 Vector Store의 부분 실패를 복구하는가 |
| 작업 Key | 같은 Pipeline 의도에 같은 Ingestion Key를 사용하는가 |
| 삭제 | Tombstone이 검색 차단과 파생 데이터 정리로 이어지는가 |
| 권한 | 테넌트·문서 권한을 저장과 검색에 모두 적용하는가 |
| 중복 검색 | 같은 Text라도 출처와 권한을 보존하는가 |
| Reconciliation | 기대 상태와 실제 Index를 주기적으로 비교하는가 |
| 개인정보 | 원문·제목·URL을 일반 Log와 Metric Label에서 제외하는가 |
| 테스트 | 재시도·동시 실행·변경·삭제·Migration을 검증하는가 |

## 마무리

RAG의 멱등 인덱싱 (Idempotent Indexing)은 `upsert()` 한 줄로 완성되지 않습니다. **같은 업무 의도와 같은 콘텐츠가 재시도 사이에서 같은 식별자로 계산되고, 새 버전이 완성되기 전까지 기존 검색 결과가 유지되며, 사라진 Chunk까지 정리되는 전체 수명주기 계약**입니다.

운영 환경에서는 다음 원칙이 필요합니다.

1. Source, Revision, Chunk와 Embedding Generation을 분리합니다.
2. Source Key에 테넌트와 원본 시스템의 불변 ID를 포함합니다.
3. Content Hash 전에 정규화 정책과 Parser 버전을 고정합니다.
4. Chunk ID에 Revision, Chunker 정책, 순서와 내용 Hash를 포함합니다.
5. 결정적 ID와 Unique Constraint를 기반으로 Upsert합니다.
6. 새 결과에 없는 Stale Chunk를 Desired Set 비교로 찾습니다.
7. 새 Revision을 Stage·검증한 뒤 활성 버전을 전환합니다.
8. Database와 Vector Store의 부분 실패는 Outbox와 멱등 Worker로 복구합니다.
9. Chunker와 Embedding 변경은 별도 Generation으로 Migration합니다.
10. Tombstone, Retrieval Filter와 Reconciliation으로 삭제·권한·정합성을 끝까지 확인합니다.

중복 없는 RAG Index는 저장 공간을 아끼는 최적화에 그치지 않습니다. 사용자가 현재 권한 안에서 최신 원문을 근거로 답변받게 만드는 데이터 신뢰성의 기반입니다.

다음 글에서는 GPT·Claude·Gemini처럼 서로 다른 Model Provider(모델 제공자)를 하나의 Agent Core(에이전트 핵심)에 연결할 때 Message, Tool Call, Streaming, 오류와 사용량 계약을 어떻게 통일할지 살펴보겠습니다.

---

## 참고 자료

- [PostgreSQL: INSERT and ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html)
- [PostgreSQL: Unique Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [pgvector 공식 문서](https://github.com/pgvector/pgvector)
- [Chroma: Upsert records](https://docs.trychroma.com/reference/chroma-api/record/upsert-records)
- [Chroma: Delete records](https://docs.trychroma.com/reference/chroma-api/record/delete-records)
- [OpenSearch: Index Document API](https://docs.opensearch.org/latest/api-reference/document-apis/index-document/)
- [OpenSearch: Manage Aliases API](https://docs.opensearch.org/latest/api-reference/alias/aliases-api/)
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)
- [Unicode Standard Annex #15: Unicode Normalization Forms](https://www.unicode.org/reports/tr15/)
- [NIST FIPS 180-4: Secure Hash Standard](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)
- [Debezium: Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [OpenTelemetry: Database Client Spans](https://opentelemetry.io/docs/specs/semconv/db/database-spans/)

> 이 글은 2026년 7월 29일 기준 공개된 PostgreSQL·pgvector·Chroma·OpenSearch·RFC·Unicode·NIST·Debezium 문서와 공개 가능한 회의록·웹 문서 RAG 인덱싱 경험을 바탕으로 작성했습니다. ChromaDB 멱등 Upsert는 구현 경험에 근거하며, pgvector와 OpenSearch의 세부 구조는 공식 문서를 바탕으로 제시한 선택지입니다. 실제 적용에서는 사용 중인 Vector Database의 Transaction, Filter, Bulk API, Consistency와 삭제 보장 범위를 다시 확인해야 합니다.
