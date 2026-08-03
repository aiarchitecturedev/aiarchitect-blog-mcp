# STT는 성공했는데 AI 요약은 왜 실패할까: 비동기 파이프라인 장애 진단

회의 음성 파일을 업로드했습니다.

잠시 후 녹취록은 정상적으로 생성됐지만 AI 요약은 계속 나타나지 않습니다.

이 상황에서 가장 먼저 떠올리기 쉬운 결론은 다음과 같습니다.

```text
“STT는 성공했으니 파일에는 문제가 없다.”
“요약 모델이 실패한 것 같다.”
```

하지만 두 문장 모두 아직 입증되지 않은 가설입니다.

실제 회의 처리 시스템에서 STT (Speech-to-Text, 음성 인식)와 AI 요약은 하나의 함수가 아니라 서로 다른 입력·실행 환경·상태·저장소를 가진 단계입니다.

```text
Media Upload
  → STT
  → Transcript Finalization
  → Summary Request
  → Queue
  → Summary Worker
  → LLM Provider
  → Result Store
  → Read API
```

STT 성공은 이 경로 전체가 성공했다는 뜻이 아닙니다.

정확히는 **STT 단계가 자신의 입력으로 녹취록을 만들었다는 한 가지 사실**만 증명합니다.

이 글에서는 “AI가 가끔 실패한다”는 모호한 설명을 벗어나, STT 성공 이후의 요약 파이프라인을 단계별로 분리하고 어떤 증거를 어떤 순서로 확인해야 하는지 정리합니다.

## 1. 먼저 성공의 단위를 분리한다

사용자 화면에서는 “회의 처리” 하나로 보이지만 내부에는 여러 개의 독립적인 성공 조건이 있습니다.

| 단계 | 성공 조건 | 대표 결과 |
|---|---|---|
| 업로드 | 원본 Bytes가 저장되고 무결성 검사가 끝남 | `mediaObjectId` |
| STT | Audio를 읽어 Segment를 생성함 | Transcript |
| 녹취 확정 | 후속 처리 가능한 Final Transcript가 저장됨 | `transcriptVersion` |
| 요약 접수 | 중복되지 않은 요약 작업이 등록됨 | `summaryJobId` |
| Queue 전달 | Worker가 처리할 Message가 전달됨 | `messageId` |
| 요약 실행 | Prompt를 구성하고 LLM 응답을 받음 | Raw Model Output |
| 결과 저장 | 검증된 요약 결과가 Commit됨 | `summaryVersion` |
| 상태 전환 | 외부 조회 상태가 사용 가능으로 바뀜 | `summaryAvailable` |
| 결과 조회 | 권한 있는 사용자가 본문을 읽을 수 있음 | Summary Response |

따라서 다음 상태는 모순이 아닙니다.

```text
STT = SUCCEEDED
Summary = FAILED
```

또한 다음 상태도 가능합니다.

```text
Summary Job = COMPLETED
Summary Body = NOT_AVAILABLE
```

Worker는 실행을 끝냈지만 결과 저장에 실패했거나, 저장은 됐지만 조회 상태가 갱신되지 않았을 수 있기 때문입니다.

장애 진단의 첫 원칙은 **회의 전체의 성공·실패를 묻지 않고 어느 단계가 마지막으로 확실히 성공했는지 찾는 것**입니다.

## 2. 하나의 `completed` Flag로 전체를 표현하지 않는다

다음과 같은 응답은 구현하기 쉽지만 의미가 불분명합니다.

```json
{
  "completed": true
}
```

무엇이 완료된 것인지 알 수 없습니다.

- 업로드가 완료됐는가?
- STT가 완료됐는가?
- 요약 요청이 접수됐는가?
- 최신 요약 작업이 완료됐는가?
- 과거에 생성된 요약 본문이 존재하는가?
- 사용자가 지금 읽을 수 있는가?

서로 다른 사실을 하나의 Boolean으로 합치면 장애가 발생했을 때 상태만 보고 원인을 찾을 수 없습니다.

최소한 단계별 상태와 결과 가용성을 분리합니다.

```json
{
  "media": {
    "state": "STORED"
  },
  "transcript": {
    "state": "READY",
    "version": 3
  },
  "summaryJob": {
    "state": "FAILED",
    "attempt": 4,
    "errorCode": "PROVIDER_TIMEOUT"
  },
  "summaryResult": {
    "available": false
  }
}
```

여기서 중요한 구분은 다음과 같습니다.

```text
Job State
  작업 실행이 어디까지 진행됐는가?

Result Availability
  사용 가능한 결과 본문이 실제로 존재하는가?
```

완료 상태를 어떤 조합으로 판정할지는 다음 글에서 더 자세히 다루고, 이번 글에서는 실패 단계와 원인을 찾는 데 집중하겠습니다.

## 3. 진단은 화면 메시지가 아니라 불변 식별자에서 시작한다

“이 회의 요약이 안 됩니다”라는 사용자 문장만으로는 여러 시스템의 Log를 연결할 수 없습니다.

진단에 필요한 최소 식별자는 다음과 같습니다.

| 식별자 | 용도 |
|---|---|
| `tenantId` | 조직 경계 확인 |
| `meetingId` | 업무 객체 확인 |
| `mediaObjectId` | 원본 파일 확인 |
| `fileId` | 회의 내부 파일 연결 확인 |
| `transcriptId`·`transcriptVersion` | 요약 입력 확인 |
| `summaryJobId` | 비동기 실행 추적 |
| `operationId` | 재요청·중복 실행 연결 |
| `traceId` | 서비스·Queue·Worker·Provider 호출 연결 |

이 값들을 사용자 화면에 모두 노출할 필요는 없습니다.

대신 운영자용 진단 화면이나 Support Code에 다음처럼 묶어 둘 수 있습니다.

```json
{
  "supportCode": "summary_fixture_20260729_001",
  "meetingId": "meeting_fixture_001",
  "fileId": "file_fixture_001",
  "summaryJobId": "job_fixture_001",
  "traceId": "trace_fixture_001"
}
```

실제 Token, 개인 정보, 회의 본문과 내부 경로는 Support Code에 넣지 않습니다.

## 4. 첫 번째 원인: 회의와 파일의 연결이 잘못됐다

회의 하나에 여러 파일이 연결될 수 있습니다.

```text
Meeting
  ├─ File A: Audio
  ├─ File B: Screen Recording
  └─ File C: Attachment
```

목록 API에서 얻은 `meetingId`만 사용해 STT·요약 API를 호출하거나, 최상위 응답에 없는 `fileId`를 추정하면 다른 파일 또는 존재하지 않는 파일을 참조할 수 있습니다.

진단할 때는 다음 연결을 실제 저장 데이터로 확인합니다.

```text
meetingId
  └─ files[]
       └─ fileId
            ├─ mediaObjectId
            ├─ transcriptId
            └─ latestSummaryJobId
```

잘못된 연결은 다음처럼 보일 수 있습니다.

- 회의 목록에는 `summarized=true`지만 선택한 파일에는 요약이 없음
- STT 조회에는 첫 번째 Audio 파일을 사용했지만 요약 요청에는 다른 `fileId`를 사용함
- 재업로드 후 새 파일이 생성됐지만 이전 파일의 요약 상태를 계속 Polling함
- 같은 이름의 회의를 검색해 다른 `meetingId`를 선택함

따라서 이름이나 배열 순서를 신뢰하지 말고 **업무 객체가 반환한 불변 식별자와 관계**를 따라가야 합니다.

## 5. 두 번째 원인: STT와 요약 단계가 같은 입력을 읽지 않는다

“STT가 파일을 읽었으니 요약도 같은 파일을 읽을 수 있다”는 가정은 시스템 구현에 따라 틀릴 수 있습니다.

요약 Worker가 녹취록 Text만 사용하는 구조라면 원본 Audio를 다시 열 필요가 없습니다.

하지만 다음과 같은 구조도 존재합니다.

```text
STT Worker
  └─ Audio Decoder A

Summary Worker
  ├─ Transcript Store
  └─ Media Loader B
       ├─ 길이·언어 Metadata 추출
       ├─ 화자 구간 재확인
       └─ 파형 또는 Multimedia 입력 구성
```

이 경우 두 단계가 사용하는 Decoder, Library, Container Image와 지원 Codec이 다를 수 있습니다.

실제 검증 환경에서 PCM WAV 파일은 STT가 완료됐지만 요약 단계의 Media Loader에서 실패했고, 같은 음성을 MP3로 변환해 다시 올렸을 때 요약이 성공한 사례가 있었습니다.

이 결과에서 말할 수 있는 범위는 제한적입니다.

```text
확인된 사실
  특정 환경에서 특정 PCM WAV 입력의
  STT 성공·요약 Media Load 실패가 재현됨

말할 수 없는 결론
  모든 WAV 파일은 요약할 수 없음
  WAV Format 자체가 문제임
```

이런 현상은 단계마다 실제 입력 계약 (Input Contract)을 기록해야 하는 이유입니다.

| 단계 | 확인할 항목 |
|---|---|
| Upload | 확장자, 실제 MIME Type, File Size, Checksum |
| STT | Container, Codec, Sample Rate, Channel, Duration |
| Summary | Transcript 사용 여부, Media 재로딩 여부, 지원 Format |
| 재처리 | 변환 Format, 새 Checksum, 새 File Version |

확장자만 확인하지 말고 실제 Media Probe 결과를 남깁니다.

```json
{
  "container": "wav",
  "codec": "pcm_s16le",
  "sampleRateHz": 16000,
  "channels": 1,
  "durationMs": 184000,
  "checksum": "sha256:fixture_digest"
}
```

## 6. 세 번째 원인: 녹취록이 존재하지만 요약 입력으로 준비되지 않았다

화면에 Text가 보인다고 해서 후속 처리 가능한 Final Transcript라는 뜻은 아닙니다.

실시간 또는 분할 STT에서는 다음 상태가 존재할 수 있습니다.

```text
PARTIAL
  아직 수정될 수 있는 중간 결과

FINAL
  구간 단위로 확정된 결과

READY_FOR_SUMMARY
  모든 필수 구간 병합·정렬·저장·검증 완료
```

요약 입력을 만들 때는 최소한 다음을 검사합니다.

- Final Segment만 포함했는가?
- Segment 순서와 시간이 일관적인가?
- Text가 공백만 남지 않았는가?
- 언어 또는 화자 정보가 필수라면 존재하는가?
- Transcript Version이 요약 요청 시점과 같은가?
- 병합 Transaction이 Commit되기 전에 요약 Event를 발행하지 않았는가?

예를 들어 다음 녹취록은 `segmentCount > 0`이지만 사용할 수 없습니다.

```json
{
  "state": "READY",
  "segments": [
    {
      "index": 0,
      "final": false,
      "content": "   "
    }
  ]
}
```

준비 조건을 별도 함수로 정의합니다.

```javascript
function isTranscriptReady(transcript) {
  return transcript.state === "READY_FOR_SUMMARY"
    && transcript.segments.length > 0
    && transcript.segments.every(segment => segment.final === true)
    && transcript.segments.some(segment => segment.content.trim().length > 0);
}
```

`scripted=true` 같은 요청 이력 Flag보다 실제 입력 본문과 Version을 함께 확인해야 합니다.

## 7. 네 번째 원인: 요약 요청과 요약 완료를 혼동했다

비동기 API에서 다음 응답은 요약 본문이 아닙니다.

```json
{
  "accepted": true,
  "summaryJobId": "job_fixture_001",
  "state": "QUEUED"
}
```

의미는 단 하나입니다.

```text
서버가 요약 작업 요청을 접수했다.
```

다음 사실은 아직 알 수 없습니다.

- Queue에 Message가 실제로 저장됐는가?
- Worker가 Message를 가져갔는가?
- LLM 호출이 시작됐는가?
- 결과가 저장됐는가?
- 사용자가 읽을 수 있는 상태인가?

요약 요청 API가 `200 OK` 또는 `202 Accepted`를 반환했다는 이유로 UI가 “요약 완료”를 표시하면 안 됩니다.

Client가 기다려야 하는 대상은 HTTP 요청이 아니라 `summaryJobId`가 가리키는 비동기 작업입니다.

```text
POST /summaries
  → 202 Accepted
  → jobId
  → Job Status API 또는 Event
  → Result Availability 확인
```

## 8. 다섯 번째 원인: Queue에 들어갔지만 Worker까지 도착하지 않았다

요약 요청 서비스와 요약 Worker 사이에 Queue가 있다면 실패 지점이 늘어납니다.

```text
API Transaction Commit
  → Event Publish
  → Broker Persist
  → Consumer Receive
  → Worker Process
  → Ack
```

대표적인 문제는 다음과 같습니다.

| 문제 | 관찰 증상 |
|---|---|
| DB Commit 후 Event 발행 누락 | Job은 `QUEUED`, Queue에는 Message 없음 |
| 잘못된 Topic·Queue | Producer 성공, 대상 Consumer 수신 없음 |
| Consumer 중지 | Queue Depth와 Oldest Age 증가 |
| Routing Key 불일치 | 일부 유형만 처리되지 않음 |
| Visibility Timeout 부족 | 실행 중 같은 Message 재전달 |
| Ack 시점 오류 | 실패했지만 Message가 제거됨 |
| Poison Message | 같은 입력이 반복 실패 |
| Dead Letter Queue 이동 | 일반 Queue에서는 사라졌지만 결과 없음 |

Google Cloud Tasks 공식 문서는 Task를 At-least-once Delivery (최소 한 번 전달) 방식으로 설명하고, 드물게 중복 실행될 수 있으므로 Handler를 멱등하게 설계하도록 요구합니다.

특정 Queue 제품을 사용하지 않더라도 같은 설계 원칙이 중요합니다.

```text
전달됨 ≠ 한 번만 실행됨
실행됨 ≠ 결과가 한 번만 저장됨
```

반복 실패한 Message는 무한 재시도하지 않고 Dead Letter Queue (실패 격리 큐) 또는 별도 실패 저장소로 이동시켜 원인을 분석할 수 있어야 합니다.

## 9. 여섯 번째 원인: Worker가 잘못된 실행 문맥을 받았다

API 요청에는 사용자·조직 정보가 있었지만 Queue Message에는 빠질 수 있습니다.

```json
{
  "summaryJobId": "job_fixture_001",
  "meetingId": "meeting_fixture_001"
}
```

이 정보만으로 Worker가 올바른 Tenant의 데이터에 접근할 수 있는지 판단해야 합니다.

다음 문맥이 필요할 수 있습니다.

- `tenantId`
- 데이터 위치 또는 Region
- 업무 객체의 소유 Group
- 실행 주체와 요청 주체
- Transcript Version
- Prompt·Model Policy Version
- 데이터 접근 권한 Snapshot 또는 실행 시 재검사 정보

반대로 Access Token 전체를 Queue Message에 복사하는 것도 위험합니다.

짧은 수명의 사용자 Token이 Worker 실행 전에 만료될 수 있고, Queue·Log·DLQ에 Credential이 남을 수 있기 때문입니다.

권장 구조는 다음과 같습니다.

```text
Queue Message
  └─ 최소 업무 식별자 + 정책 문맥 참조

Worker
  └─ 자신의 Service Identity로 실행
       └─ 대상 Tenant·Object 권한 재검사
```

인증 실패, 권한 거부, 데이터 없음은 모두 다른 Error Code로 기록합니다.

```text
AUTH_CONTEXT_EXPIRED
TENANT_CONTEXT_MISSING
OBJECT_ACCESS_DENIED
TRANSCRIPT_NOT_FOUND
```

모두 `SUMMARY_FAILED`로만 저장하면 재시도 여부도 결정할 수 없습니다.

## 10. 일곱 번째 원인: LLM 호출 전에 Prompt 구성에서 실패했다

요약 Worker가 실행됐다고 바로 LLM Provider를 호출하는 것은 아닙니다.

먼저 다음 과정을 거칠 수 있습니다.

```text
Transcript Load
  → Normalize
  → Speaker·Timestamp Format
  → Prompt Template Render
  → Token Estimate
  → Model Routing
  → Safety·Data Policy
  → Provider Request
```

이 단계의 대표적인 실패는 다음과 같습니다.

- Transcript Encoding 오류
- 지원하지 않는 언어 코드
- Prompt Template 변수 누락
- 잘못된 JSON Schema
- Model Routing 규칙 불일치
- 입력 Token 한도 초과
- 개인정보 정책에 따른 전송 차단
- 빈 입력 또는 최소 길이 미달

긴 회의 녹취록 전체를 한 번에 전달하면 Model의 Context Window (문맥 창)를 넘거나 처리 시간이 증가할 수 있습니다.

Provider 문서의 현재 한도를 코드에 고정하기보다 Model Registry에서 관리합니다.

```json
{
  "modelPolicy": {
    "provider": "provider_fixture",
    "model": "summary_model_fixture",
    "maxContextTokens": 100000,
    "reservedOutputTokens": 4000,
    "promptVersion": "summary_prompt_v7"
  }
}
```

위 숫자는 설명용 Fixture입니다. 실제 값은 선택한 Provider·Model의 공식 문서와 계정 설정을 기준으로 확인해야 합니다.

입력이 길면 무조건 잘라 버리지 말고 다음 전략 중 품질 요구에 맞는 방식을 선택합니다.

- Topic 또는 시간 구간별 Map-Reduce Summary (분할·통합 요약)
- 결정사항·업무·일정 등 목적별 추출
- 중복·무음·인사말 Segment 제거
- 이전 단계의 구조화된 Transcript 사용
- 더 긴 Context를 지원하는 승인된 Model로 Routing

## 11. 여덟 번째 원인: Provider 호출이 실패했다

LLM Provider 오류는 모두 같은 재시도 정책을 적용하면 안 됩니다.

Google Gemini API 공식 문제 해결 문서는 잘못된 요청, 권한, Rate Limit, 호출 취소, 내부 오류, 일시적 서비스 불가와 Deadline 초과 등을 서로 다른 오류로 구분합니다.

일반화하면 다음과 같은 분류를 사용할 수 있습니다.

| 오류 분류 | 예시 | 기본 대응 |
|---|---|---|
| 입력 오류 (Invalid Input) | 잘못된 Schema·지원하지 않는 값 | 재시도하지 않고 입력 수정 |
| 인증 오류 (Authentication) | 잘못된 API Key·Token | Credential 복구 후 제한적 재시도 |
| 권한 오류 (Authorization) | Model 접근 권한 없음 | 설정·권한 수정 |
| 사용량 제한 (Rate Limit) | Request·Token 한도 초과 | Backoff·Jitter 후 재시도 |
| 문맥 초과 (Context Exceeded) | 입력이 Model 한도 초과 | 분할·축약·Model 변경 |
| 안전 정책 차단 (Safety Block) | 정책에 의해 요청·응답 차단 | 별도 상태와 사용자 설명 |
| 시간 초과 (Timeout) | Deadline 안에 응답 없음 | 결과 확인 후 멱등 재시도 |
| 일시 장애 (Transient Failure) | `5xx`, Service Unavailable | 제한된 재시도·Fallback |
| 영구 장애 (Permanent Failure) | 존재하지 않는 Model | 구성 수정 후 재처리 |

`429`, `408`, `5xx`처럼 일시적일 수 있는 오류에는 Exponential Backoff (지수 백오프)와 Jitter (무작위 지연)를 적용할 수 있습니다.

하지만 다음 오류는 같은 요청을 반복해도 해결되지 않습니다.

```text
INVALID_PROMPT_SCHEMA
MODEL_NOT_FOUND
CONTEXT_EXCEEDED
OBJECT_ACCESS_DENIED
```

재시도 가능 여부를 문자열 Message Parsing에 의존하지 말고 구조화된 Error Taxonomy (오류 분류 체계)로 결정합니다.

## 12. 아홉 번째 원인: 응답은 받았지만 결과 검증에 실패했다

Provider가 HTTP 성공 응답을 반환해도 업무 결과가 유효하다는 뜻은 아닙니다.

다음 문제가 남아 있습니다.

- 응답 본문이 비어 있음
- 출력이 중간에 잘림
- 기대한 JSON Schema와 다름
- 필수 Section이 없음
- 잘못된 언어로 생성됨
- 안전 Filter로 일부 결과가 제거됨
- 동일 문장이 비정상적으로 반복됨
- Transcript에 없는 사실이 핵심 결정으로 생성됨

결과를 바로 공개 저장하지 않고 검증 단계를 둡니다.

```javascript
function validateSummary(result) {
  if (!result || typeof result.text !== "string") {
    return { valid: false, code: "SUMMARY_BODY_MISSING" };
  }

  if (result.text.trim().length === 0) {
    return { valid: false, code: "SUMMARY_BODY_EMPTY" };
  }

  if (!Array.isArray(result.actionItems)) {
    return { valid: false, code: "SUMMARY_SCHEMA_INVALID" };
  }

  return { valid: true };
}
```

유효성 실패와 Provider 호출 실패를 구분해야 Prompt 수정, Parser 수정, 재요청 중 올바른 대응을 선택할 수 있습니다.

## 13. 열 번째 원인: 결과 저장과 상태 전환이 원자적이지 않았다

Worker가 유효한 결과를 만들었지만 DB 저장 중 실패할 수 있습니다.

더 위험한 경우는 두 작업의 순서가 어긋나는 것입니다.

```text
1. Job State를 SUCCEEDED로 변경
2. Summary Body 저장 시도
3. DB 오류 발생
```

최종 상태는 다음처럼 됩니다.

```text
Job = SUCCEEDED
Summary Body = 없음
```

반대 순서도 문제가 될 수 있습니다.

```text
1. Summary Body 저장
2. Job State를 SUCCEEDED로 변경
3. Worker 중단
```

이 경우 본문은 있지만 UI가 계속 처리 중으로 보일 수 있습니다.

같은 Database를 사용한다면 하나의 Transaction으로 결과와 상태를 Commit합니다.

```sql
BEGIN;

INSERT INTO summary_result (
  summary_job_id,
  transcript_version,
  summary_version,
  body_json
) VALUES (
  'job_fixture_001',
  3,
  1,
  '{"text":"fixture summary"}'
);

UPDATE summary_job
SET state = 'SUCCEEDED',
    completed_at = CURRENT_TIMESTAMP
WHERE summary_job_id = 'job_fixture_001'
  AND state = 'RUNNING';

COMMIT;
```

서로 다른 저장소를 사용한다면 Transactional Outbox (트랜잭션 아웃박스), 재조정 작업 (Reconciliation Job) 또는 상태 복구 절차가 필요합니다.

## 14. 열한 번째 원인: 결과는 있는데 조회 API가 없다고 판단했다

쓰기 경로가 성공했는데 읽기 경로의 상태 해석이 틀릴 수도 있습니다.

예를 들어 다음 응답에는 사용할 수 있는 요약 본문이 있습니다.

```json
{
  "completed": false,
  "summaryAvailable": true,
  "originalSummary": {
    "text": "결정 사항과 후속 업무가 포함된 요약"
  }
}
```

Client가 `completed=false` 하나만 보고 “요약이 없습니다”라고 표시하면 실제 결과를 숨기게 됩니다.

반대로 다음 응답을 성공으로 표시해서도 안 됩니다.

```json
{
  "completed": true,
  "summaryAvailable": true,
  "originalSummary": null
}
```

이것은 정상 완료가 아니라 **상태 불일치 (State Inconsistency)**입니다.

진단할 때는 다음 세 가지를 따로 조회합니다.

```text
1. 최신 Job State
2. 실제 Result Body 존재 여부
3. Read API의 가용성 판정 결과
```

운영 환경에서는 과거 요약 본문과 최신 재생성 Job이 동시에 존재할 수도 있습니다.

```text
기존 Summary Version 2 = 사용 가능
재생성 Job Version 3 = 처리 중
```

이때 기존 결과까지 숨길지, “기존 결과 + 새 버전 처리 중”으로 보여 줄지는 명시적인 제품 계약으로 정해야 합니다.

## 15. 가장 빠른 장애 진단 순서

진단 순서는 가능하면 비용이 적고 사실을 빠르게 좁힐 수 있는 방향이어야 합니다.

### 1단계: 사용자 증상을 정확히 분류한다

```text
요약 요청 버튼이 실패했는가?
처리 중에서 멈췄는가?
실패 상태가 보이는가?
완료로 보이는데 본문이 비었는가?
과거 요약은 보이는데 재생성만 실패했는가?
```

### 2단계: 대상 식별자를 고정한다

```text
tenantId
meetingId
fileId
transcriptVersion
summaryJobId
traceId
```

### 3단계: 마지막으로 성공한 단계를 찾는다

```text
Upload 저장 확인
→ STT 결과 확인
→ Final Transcript 확인
→ Summary Job 확인
→ Queue 전달 확인
→ Worker 실행 확인
→ Provider 호출 확인
→ Result 저장 확인
→ Read API 확인
```

### 4단계: 실패 코드를 재시도 가능성으로 분류한다

```text
Transient
  Timeout, Rate Limit, 일시적 5xx

Permanent until changed
  잘못된 입력, 권한, Model, Context 초과

Inconsistent
  상태와 실제 결과가 서로 다름
```

### 5단계: 수정 전 재현 입력을 보존한다

- 원본 파일의 Checksum과 Media Metadata
- Transcript Version과 Segment Count
- Prompt Version과 Model
- Error Code와 Attempt
- 개인 정보를 제거한 Trace

수정 과정에서 원본 증거가 사라지면 원인을 확인하지 못한 채 “재시도하니 됐다”로 끝날 수 있습니다.

## 16. 재시도는 오류 분류와 멱등성이 준비된 뒤 적용한다

비동기 시스템에서 재시도 자체는 정상적인 복구 수단입니다.

하지만 준비 없이 재시도하면 같은 회의의 요약이 여러 번 생성되거나 비용이 중복될 수 있습니다.

Google Cloud Tasks는 최소 한 번 전달될 수 있으므로 Handler를 멱등하게 만들어야 한다고 설명합니다. RFC 9110도 통신 실패 후 자동 재시도가 안전하려면 요청의 의미가 멱등해야 한다는 기준을 제공합니다.

요약 생성에는 업무 멱등성 Key를 정의합니다.

```text
summaryIdempotencyKey =
  tenantId
  + meetingId
  + fileId
  + transcriptVersion
  + promptVersion
  + modelPolicyVersion
```

동일 Key의 작업이 이미 있으면 상태를 확인합니다.

```javascript
async function requestSummary(input) {
  const key = createSummaryKey(input);
  const existing = await summaryJobRepository.findByKey(key);

  if (existing) {
    return existing;
  }

  return summaryJobRepository.create({
    idempotencyKey: key,
    state: "QUEUED",
    input
  });
}
```

재시도 정책의 예시는 다음과 같습니다.

| 오류 | 자동 재시도 | 조건 |
|---|---:|---|
| Network Timeout | 가능 | Operation 결과 확인 후 |
| Provider `429` | 가능 | Backoff·Jitter·최대 횟수 |
| Provider `503` | 가능 | Circuit Breaker와 함께 |
| Context 초과 | 불가 | 입력 분할 또는 Model 변경 |
| 권한 거부 | 불가 | 권한·정책 수정 |
| Media Load 실패 | 조건부 | Format 정규화 후 새 Version |
| 결과 저장 충돌 | 조건부 | 멱등 Key로 기존 결과 확인 |
| Schema 검증 실패 | 조건부 | Prompt·Parser Version 변경 |

같은 입력을 무한 반복하지 않고 최대 시도 횟수와 총 재시도 시간을 제한합니다.

## 17. 실패 상태에는 원인과 다음 행동이 포함돼야 한다

운영자에게 다음 상태만 보여 주면 부족합니다.

```json
{
  "state": "FAILED"
}
```

최소한 다음 구조를 권장합니다.

```json
{
  "state": "FAILED",
  "stage": "LLM_PROVIDER",
  "error": {
    "code": "PROVIDER_RATE_LIMITED",
    "category": "TRANSIENT",
    "retryable": true,
    "safeMessage": "요약 서비스 사용량 제한으로 처리가 지연되고 있습니다."
  },
  "attempt": 3,
  "nextRetryAt": "2026-07-29T10:05:00Z",
  "supportCode": "summary_fixture_20260729_001"
}
```

내부 Exception Stack, Provider Credential과 원문 녹취록은 사용자 응답에 포함하지 않습니다.

운영자용 정보와 사용자용 문구를 분리합니다.

| 대상 | 제공 정보 |
|---|---|
| 사용자 | 현재 상태, 안전한 설명, 예상 다음 행동 |
| Support | Support Code, 실패 단계, 분류된 Error Code |
| 개발·운영 | Trace, Attempt, Worker, Provider 응답, Stack |
| 보안 감사 | 접근 주체, Tenant, 정책 결정, 민감정보 처리 |

## 18. 분산 추적으로 끊어진 경로를 연결한다

API Log, Queue Log와 Worker Log가 각각 있어도 서로 연결할 수 없다면 진단 시간이 길어집니다.

W3C Trace Context는 `traceparent`와 `tracestate`를 통해 분산된 구성요소가 하나의 Trace 문맥을 전달하는 표준을 정의합니다.

OpenTelemetry의 Messaging Semantic Conventions (메시징 의미 규약)은 Producer의 Message Creation Context를 Consumer까지 전달해 비동기 흐름을 연결하도록 설명합니다.

권장 Span 구조는 다음과 같습니다.

```text
POST /meetings/{id}/summaries
  └─ summary.job.create
      └─ send summary.jobs

process summary.jobs
  ├─ transcript.load
  ├─ summary.prompt.build
  ├─ gen_ai.generate_content
  ├─ summary.validate
  └─ summary.result.commit
```

각 Span에는 낮은 Cardinality (카디널리티)의 진단 속성을 우선 기록합니다.

```json
{
  "summary.stage": "LLM_PROVIDER",
  "summary.error_code": "PROVIDER_TIMEOUT",
  "summary.attempt": 2,
  "transcript.version": 3,
  "prompt.version": "summary_prompt_v7",
  "gen_ai.operation.name": "generate_content",
  "gen_ai.request.model": "summary_model_fixture"
}
```

회의 제목, 전체 녹취록, Prompt 원문과 Summary 본문은 Trace 속성에 기본 기록하지 않습니다.

OpenTelemetry의 GenAI 속성에는 입력 Message나 System Instruction처럼 민감할 수 있는 항목이 있으므로 수집 여부, Masking과 보존 기간을 별도로 통제해야 합니다.

## 19. 단계별 Metric으로 “느림”과 “실패”를 분리한다

전체 처리 시간 평균만 보면 Queue 대기와 Provider 지연을 구분할 수 없습니다.

다음 Metric을 단계별로 수집합니다.

| 구간 | Metric 예시 |
|---|---|
| 요청 | `summary_job_created_total` |
| Queue | `summary_queue_depth`, `summary_queue_oldest_age` |
| Worker | `summary_job_duration`, `summary_worker_active` |
| Provider | `llm_request_duration`, `llm_error_total` |
| 결과 | `summary_result_commit_total` |
| 품질 | `summary_validation_failure_total` |
| 상태 | `summary_job_stuck_total` |
| 재시도 | `summary_retry_total`, `summary_dlq_depth` |

다음 비율도 중요합니다.

```text
Summary Success Rate
  = 사용 가능한 Summary Result 수
    / 유효한 Summary 요청 수
```

`HTTP 202 Accepted` 수를 성공 분자로 사용하면 실제 사용자 성공률을 과대평가합니다.

실패율은 Stage와 Error Code별로 분해합니다.

```text
MEDIA_LOAD_FAIL
TRANSCRIPT_NOT_READY
QUEUE_DELIVERY_FAIL
WORKER_TIMEOUT
CONTEXT_EXCEEDED
PROVIDER_RATE_LIMITED
SUMMARY_SCHEMA_INVALID
RESULT_COMMIT_FAIL
STATE_INCONSISTENT
```

## 20. 재현 테스트는 단계별 Fixture로 만든다

하나의 긴 End-to-end Test만으로는 실패 원인을 빠르게 찾기 어렵습니다.

다음 Fixture를 독립적으로 준비합니다.

| 테스트 | 확인 목적 |
|---|---|
| Media Contract Test | Container·Codec별 단계 호환성 |
| Transcript Readiness Test | Partial·Final·빈 Segment 처리 |
| Job Creation Test | 중복 요청과 멱등 Key |
| Queue Delivery Test | Routing·재전달·DLQ |
| Worker Context Test | Tenant·권한·Version 전달 |
| Prompt Build Test | Template 변수·Token Budget |
| Provider Error Test | `429`·`5xx`·Timeout·권한 |
| Result Validation Test | 빈 본문·Schema 불일치 |
| Persistence Test | 결과와 상태의 원자적 Commit |
| Read Contract Test | 상태 Flag와 실제 본문 조합 |

특히 같은 Audio를 다른 Container·Codec으로 변환한 Fixture는 단계별 Media 지원 차이를 찾는 데 유용합니다.

```text
fixture-a.wav  → PCM 16-bit, mono
fixture-a.mp3  → MPEG audio
fixture-a.m4a  → AAC
```

결과가 다르면 “Model이 불안정하다”로 결론 내리기 전에 어느 단계가 어떤 Format을 다시 읽는지 확인합니다.

## 21. 자주 실패하는 진단 방식

### “STT가 됐으니 파일 문제는 아니다”

단계별 Media Loader가 다르면 성립하지 않습니다.

### “요약 요청 API가 성공했으니 기다리면 된다”

접수 성공과 처리 성공은 다릅니다. Queue·Worker·Provider·저장 상태를 확인해야 합니다.

### “일단 재요청한다”

멱등성 없이 반복하면 중복 Job, 중복 비용과 상태 경합이 발생합니다.

### “완료 Flag만 확인한다”

Job 완료와 결과 가용성이 다를 수 있습니다. 실제 본문과 Version을 확인해야 합니다.

### “모든 오류를 Timeout으로 감싼다”

입력 오류, 권한 거부, Context 초과와 일시 장애의 대응 방법이 달라집니다.

### “녹취록과 Prompt를 Log에 모두 남긴다”

진단은 쉬워질 수 있지만 회의 내용과 개인정보가 관측 시스템에 확산됩니다. 식별자, Version, 길이, Hash와 분류된 Error Code를 우선 사용합니다.

## 22. 운영 Runbook

STT 성공·요약 실패가 발생했을 때 다음 순서로 확인합니다.

### 대상 확인

- [ ] Tenant, Meeting, File 식별자가 같은 업무 객체를 가리키는가?
- [ ] 재업로드 후 이전 File·Job을 조회하고 있지 않은가?
- [ ] Transcript Version과 Summary 입력 Version이 일치하는가?

### 입력 확인

- [ ] 원본 Media의 Container·Codec·Sample Rate·Channel을 확인했는가?
- [ ] 요약 단계가 원본 Media를 다시 읽는지 확인했는가?
- [ ] Final Transcript가 비어 있지 않은가?
- [ ] Partial Segment가 요약 입력에 섞이지 않았는가?

### 비동기 실행 확인

- [ ] 요약 요청이 단순 접수됐는지 실제 Message까지 발행됐는지 구분했는가?
- [ ] Queue Depth와 Oldest Age가 증가하고 있지 않은가?
- [ ] Worker가 Message를 수신했는가?
- [ ] 반복 실패 Message가 DLQ로 이동했는가?
- [ ] Worker의 Tenant·권한 문맥이 유효한가?

### LLM 확인

- [ ] Prompt Template과 Model Policy Version을 확인했는가?
- [ ] 입력 Token이 Context Budget 안에 있는가?
- [ ] Provider 오류를 입력·권한·제한·일시 장애로 분류했는가?
- [ ] 재시도 가능 오류에만 Backoff·Jitter를 적용했는가?

### 결과 확인

- [ ] Model 응답이 업무 Schema 검증을 통과했는가?
- [ ] Summary Body와 Job State가 함께 Commit됐는가?
- [ ] 실제 결과가 있는데 Read API가 숨기고 있지 않은가?
- [ ] Support Code로 API부터 Worker까지 하나의 Trace를 찾을 수 있는가?

## 23. 설계 체크리스트

- [ ] Upload, STT, Transcript, Summary Job과 Result 상태를 분리한다.
- [ ] 단계마다 입력·출력 계약과 불변 식별자를 정의한다.
- [ ] 요약 요청 접수와 요약 완료를 구분한다.
- [ ] Transcript의 Final·Version·본문 존재 여부를 검증한다.
- [ ] Queue Message에 최소 업무 문맥과 Trace Context를 전달한다.
- [ ] Credential 원문을 Queue·Log·DLQ에 남기지 않는다.
- [ ] 오류를 Stage·Code·Category·Retryable로 구조화한다.
- [ ] 재시도 전에 멱등성 Key와 기존 결과 확인 절차를 둔다.
- [ ] 반복 실패 Message를 격리하고 재처리 절차를 제공한다.
- [ ] Prompt·Model·Parser Version을 결과와 함께 기록한다.
- [ ] 결과 저장과 상태 전환의 원자성 또는 복구 절차를 확보한다.
- [ ] Job State와 Result Availability를 독립적으로 검증한다.
- [ ] Trace·Metric·Log에서 회의 원문과 개인 정보를 최소화한다.
- [ ] 단계별 Fixture와 실패 주입 테스트를 운영한다.

## 마무리

STT는 성공했는데 AI 요약이 실패했다면 “Model이 불안정하다”는 결론부터 내리면 안 됩니다.

먼저 전체 흐름을 단계로 분리해야 합니다.

```text
Media
→ STT
→ Final Transcript
→ Summary Request
→ Queue
→ Worker
→ Prompt
→ LLM
→ Validation
→ Result Commit
→ Read API
```

그리고 각 단계에서 다음 네 가지를 확인합니다.

```text
Input
  이 단계가 읽은 실제 입력은 무엇인가?

State
  요청·처리·완료·실패 중 어디에 있는가?

Evidence
  어떤 식별자·오류 코드·Trace로 입증할 수 있는가?

Recovery
  재시도 가능한가, 입력이나 설정을 바꿔야 하는가?
```

**STT 성공과 요약 실패는 이상한 예외가 아니라, 독립된 비동기 단계가 정확히 드러난 상태**입니다.

좋은 운영 시스템은 실패를 하나의 `false`로 감추지 않습니다. 어느 단계에서 왜 실패했고, 다시 실행해도 안전한지, 사용자는 무엇을 할 수 있는지를 구조화된 상태와 증거로 보여 줍니다.

다음 글에서는 비동기 AI 요약에서 `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED` 같은 Job State와 실제 Summary Body의 존재 여부가 다를 때, 사용 가능한 완료 상태를 어떻게 판정해야 하는지 살펴보겠습니다.

## 참고 자료

- [Google Cloud Tasks: Understand Cloud Tasks](https://cloud.google.com/tasks/docs/dual-overview)
- [Google Cloud Tasks: Configure task retries](https://cloud.google.com/tasks/docs/configure-retry-task)
- [Google Cloud Run: Jobs retries and checkpoints best practices](https://cloud.google.com/run/docs/jobs-retries)
- [Amazon SQS: Using dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [RFC 9110: HTTP Semantics — Idempotent Methods](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [OpenTelemetry: Semantic conventions for messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/)
- [OpenTelemetry: Generative AI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
- [Google Gemini API: Troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting)
- [Google Gemini API: Understand and count tokens](https://ai.google.dev/gemini-api/docs/tokens)

---

> 이 글은 2026년 7월 29일 기준 공식 Cloud Tasks·Cloud Run·Amazon SQS·RFC 9110·W3C Trace Context·OpenTelemetry·Gemini API 문서와 공개 가능한 STT·AI 요약 검증 경험을 바탕으로 작성했습니다. 특정 PCM WAV 입력에서 확인된 요약 단계 실패는 한 검증 환경의 재현 결과이며, 모든 WAV 파일이나 제품에 일반화할 수 없습니다. 실제 지원 Format, Context 한도, 오류 코드와 재시도 정책은 사용하는 Media Library, Queue와 LLM Provider의 현재 공식 문서 및 운영 설정으로 다시 확인해야 합니다.
