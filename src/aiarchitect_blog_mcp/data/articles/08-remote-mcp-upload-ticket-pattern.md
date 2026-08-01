# Tistory 기술자료 초안

- 문서 ID: `BLOG-08`
- 상태: 공개 완료
- Tistory 상태: 공개
- 공개 URL: `https://aiarchitect.tistory.com/10`
- 분류: `AI Agent · MCP`
- 권장 제목: `원격 MCP 파일 업로드 설계: 로컬 경로가 실패하는 이유와 Upload Ticket 패턴`
- 검색 설명: `원격 MCP Server가 사용자의 로컬 파일 경로를 읽을 수 없는 이유와 Control Plane(제어 영역)·Data Plane(데이터 전송 영역)을 분리한 Upload Ticket(업로드 티켓) 기반 파일 전달, 검증과 복구 구조를 정리합니다.`
- 권장 태그: `MCP`, `파일 업로드`, `Upload Ticket`, `AI Agent`, `원격 MCP`, `보안`, `대용량 파일`
- 권장 대표 이미지: `portfolio/architecture-diagrams/04-mcp-enterprise-integration.svg`

---

# 원격 MCP 파일 업로드 설계: 로컬 경로가 실패하는 이유와 Upload Ticket 패턴

AI Agent에게 “이 파일을 회의록으로 만들어 줘”라고 요청하면 사용자는 파일 경로를 알려 주는 것으로 충분하다고 생각할 수 있습니다.

로컬 MCP Server에서는 다음 호출이 실제로 동작할 수 있습니다.

```json
{
  "name": "document_create",
  "arguments": {
    "filePath": "/local/path/team-sync.mp3"
  }
}
```

하지만 같은 Tool을 원격 HTTP MCP Server에 연결하면 `file not found`가 발생할 수 있습니다. 파일이 사라진 것이 아니라 **Client와 Server가 서로 다른 파일시스템을 사용하기 때문**입니다.

이 문제를 해결하는 안전한 방법 중 하나가 Upload Ticket(업로드 티켓) 패턴입니다.

```text
1. MCP Tool로 업로드 권한과 목적을 준비한다.
2. 별도 HTTP 경로로 파일 Byte를 전송한다.
3. uploadId를 MCP Tool에 전달해 업무 처리를 시작한다.
```

핵심은 파일 경로와 파일 Byte를 구분하고, MCP 제어 요청과 대용량 데이터 전송의 책임을 분리하는 것입니다.

## 1. `filePath`는 Server의 경로로 해석된다

MCP의 표준 Transport에는 `stdio`와 Streamable HTTP가 있습니다.

로컬 `stdio` 구조에서는 Host가 MCP Server를 같은 장치의 하위 Process로 실행할 수 있습니다.

```text
User Device
├─ AI Host
├─ MCP Client
├─ Local MCP Server Process
└─ /local/path/team-sync.mp3
```

운영체제 권한과 Sandbox 설정이 허용한다면 Local MCP Server가 같은 파일을 읽을 수 있습니다.

원격 Streamable HTTP 구조는 다릅니다.

```text
User Device                       Remote Environment
├─ AI Host                        ├─ MCP Gateway
├─ MCP Client  ─── HTTPS ───────▶ ├─ MCP Server
└─ /local/path/team-sync.mp3      └─ Server Filesystem
```

원격 Server가 `"/local/path/team-sync.mp3"`라는 문자열을 받아도 사용자의 장치에 접근할 수 없습니다. Server는 자신의 Container 또는 VM 안에서 그 경로를 찾습니다.

다음 방식은 해결책이 아닙니다.

- 로컬 절대 경로를 그대로 JSON 인자에 넣음
- 경로 앞에 `file://`를 붙임
- Client의 사용자 이름과 Directory 구조를 Server에 알려 줌
- 공유되지 않은 Network Drive 경로를 추측함
- 파일 Byte를 Base64로 바꿔 거대한 Tool 인자 하나에 넣음

마지막 방법은 작은 데이터에는 가능할 수 있지만 대용량 파일에서는 JSON 크기, 메모리 복사, Timeout, 로그 노출과 재시도 비용을 키웁니다.

## 2. 파일 업로드는 Control Plane(제어 영역)과 Data Plane(데이터 전송 영역)으로 나눈다

MCP Tool 호출은 “누가, 어떤 목적으로, 어떤 제한 안에서 파일을 올릴 것인가”를 결정하는 Control Plane(제어 영역)에 적합합니다.

실제 파일 Byte는 Object Storage 또는 Upload Service로 보내는 Data Plane(데이터 전송 영역)이 처리하는 편이 효율적입니다.

| 구분 | Control Plane | Data Plane |
|---|---|---|
| 역할 | 권한, 목적, 제한, 상태 연결 | 파일 Byte 전송 |
| 대표 프로토콜 | MCP `tools/call` | HTTPS `PUT`·`POST`, Multipart, tus |
| 데이터 크기 | 작은 구조화 JSON | 수 MB에서 수 GB까지 |
| 인증 | 사용자·테넌트·Tool 권한 | 짧은 수명의 Upload Ticket |
| 재시도 | Tool 호출 단위 | Byte·Part·Offset 단위 |
| 관측성 | 업무 Workflow와 감사 | 전송량, Checksum과 Storage 상태 |

이 분리는 MCP가 파일을 처리할 수 없다는 뜻이 아닙니다. Tool이 직접 Byte를 받는 대신, 제한된 업로드 Handle을 발급하고 후속 Tool 호출에서 그 Handle을 사용한다는 뜻입니다.

현재 MCP Tool 설계 지침도 여러 호출에 걸친 상태가 필요할 때 Server가 명시적인 Handle을 반환하고 후속 호출에서 그 Handle을 인자로 받는 방식을 안내합니다. `uploadId`는 이 원칙을 파일 전달에 적용한 Handle입니다.

## 3. Upload Ticket 흐름을 세 단계로 구성한다

전체 흐름은 다음과 같습니다.

```text
AI Host
  │
  │ ① prepare_file_upload(fileName, size, mediaType, checksum)
  ▼
Remote MCP Server
  │
  │ uploadId + uploadUrl + 제한 조건
  ▼
AI Host
  │
  │ ② HTTPS로 파일 Byte 전송
  ▼
Upload Service · Object Storage
  │
  │ VERIFIED
  ▼
AI Host
  │
  │ ③ document_create(uploadId, business metadata)
  ▼
Remote MCP Server
  │
  ▼
Async Processing Workflow
```

첫 번째 Tool은 파일 자체를 받지 않습니다.

```json
{
  "name": "prepare_file_upload",
  "arguments": {
    "fileName": "team-sync.mp3",
    "size": 48219321,
    "mediaType": "audio/mpeg",
    "checksum": {
      "algorithm": "sha256",
      "value": "<hex-digest>"
    }
  }
}
```

Server는 제한된 Ticket을 구조화된 결과로 반환합니다.

```json
{
  "uploadId": "upl_opaque_handle",
  "uploadUrl": "https://uploads.example.net/v1/objects/upl_opaque_handle",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer <short-lived-upload-token>",
    "X-Upload-Id": "upl_opaque_handle",
    "Content-Type": "audio/mpeg"
  },
  "expiresAt": "2026-07-29T08:15:00Z",
  "maxSize": 104857600,
  "singleUse": true
}
```

Client는 지정된 HTTP Method와 Header로 Byte를 전송한 뒤 `uploadId`를 업무 Tool에 전달합니다.

```json
{
  "name": "document_create",
  "arguments": {
    "uploadId": "upl_opaque_handle",
    "title": "팀 싱크",
    "requestSummary": true,
    "idempotencyKey": "opaque-business-operation"
  }
}
```

## 4. Ticket은 짧고 좁은 권한만 가져야 한다

Upload Ticket은 일반적인 로그인 Token을 복제한 것이 아닙니다. 파일 하나를 제한된 위치에 올리는 데 필요한 최소 권한만 가져야 합니다.

권장 제한은 다음과 같습니다.

- 짧은 만료 시간
- 하나의 `uploadId` 또는 Object Key에만 쓰기 가능
- 허용된 HTTP Method만 사용
- 최대 파일 크기
- 허용된 Media Type과 확장자
- 사용자와 테넌트에 Binding
- 원래 준비한 업무 목적에 Binding
- 필요 시 한 번만 사용
- 예상 Checksum(무결성 해시)과 일치해야 완료
- 읽기, 목록 조회와 다른 Object 덮어쓰기 금지

Presigned URL(사전 서명 URL)을 사용하는 경우 URL 자체가 임시 자격 증명처럼 작동할 수 있습니다. Amazon S3 공식 문서는 Presigned URL이 특정 Object와 Method, 만료 시간에 대한 제한된 접근을 제공하며 Checksum으로 무결성을 확인할 수 있다고 설명합니다.

다음 값을 운영 로그에 남기지 않습니다.

- 전체 Presigned URL
- Upload Bearer Token
- 서명 Query Parameter
- 원본 MCP Access Token
- 사용자의 로컬 파일 경로

로그에는 `uploadId`, 만료 여부, 허용 크기와 처리 상태처럼 진단에 필요한 비민감 정보만 남깁니다.

## 5. 파일명은 표시값이지 Storage Key가 아니다

사용자가 보낸 파일명을 Object Storage 경로나 Server 파일 경로로 그대로 사용하면 충돌과 경로 조작 위험이 생깁니다.

```text
사용자 표시 파일명: team-sync.mp3
Storage Object Key: tenant/<opaque-scope>/uploads/<generated-id>
```

원본 파일명은 화면 표시와 감사 목적의 Metadata로 보존할 수 있지만 다음 검증이 필요합니다.

- 최대 길이
- Null Byte와 제어문자 제거
- `/`, `\`, 연속된 `..` 같은 경로 표현 제한
- 운영체제 예약 이름 처리
- Unicode 정규화
- Header와 로그에 넣을 때 안전한 Encoding

OWASP File Upload 지침은 Application이 생성한 파일명을 사용하고, 확장자·크기·실제 파일 유형을 검증하며, 가능하면 Web Root 밖이나 별도 Host에 저장할 것을 권장합니다.

## 6. `Content-Type`만 믿지 않고 Byte를 검증한다

Client가 보내는 `Content-Type`은 힌트이지 보안 증거가 아닙니다. 확장자와 MIME Type이 허용 목록에 있어도 실제 Byte가 다른 형식일 수 있습니다.

업로드 완료 뒤 다음 검증 Pipeline을 둡니다.

```text
UPLOADED
  → SIZE_VERIFIED
  → CHECKSUM_VERIFIED
  → SIGNATURE_VERIFIED
  → MALWARE_SCANNED
  → READY
```

필요한 검사는 업무 유형에 따라 달라집니다.

- 실제 Byte 수와 선언한 크기 비교
- SHA-256 같은 Checksum 비교
- Magic Number 또는 File Signature 검사
- 허용 확장자와 실제 형식 교차 확인
- 압축 파일의 경로, 깊이와 해제 후 크기 제한
- Malware Scan 또는 Sandbox
- 문서 유형에 따라 CDR(Content Disarm & Reconstruction, 콘텐츠 무해화) 적용
- Parser에 전달하기 전 Quarantine(격리)

검증 전 파일을 일반 다운로드 URL로 공개하거나 AI Parser와 Media Decoder에 바로 전달하지 않습니다.

## 7. 업로드 상태와 업무 처리 상태를 분리한다

Byte 전송 성공과 업무 처리 성공은 다른 상태입니다.

```text
Upload Lifecycle
PREPARED
  → UPLOADING
  → UPLOADED
  → VERIFYING
  → VERIFIED
  → CONSUMED

종료 상태
EXPIRED · REJECTED · QUARANTINED · DELETED
```

그다음 별도의 업무 Workflow가 시작됩니다.

```text
Document Lifecycle
RECEIVED
  → PARSING
  → TRANSCRIBING
  → SUMMARIZING
  → READY

실패 상태
PARSE_FAILED · TRANSCRIPTION_FAILED · SUMMARY_FAILED
```

파일이 정상적으로 업로드됐더라도 지원하지 않는 Codec, 손상된 Media, 암호화된 문서나 Parser 제한으로 후속 처리가 실패할 수 있습니다.

`uploadStatus=VERIFIED`를 `documentStatus=READY`와 같은 의미로 사용하면 원인을 구분하기 어렵습니다.

## 8. 업무 Tool은 Ticket을 다시 검증한다

누군가 유효한 `uploadId` 문자열을 알고 있다고 해서 그 파일로 업무를 생성할 권한이 생기는 것은 아닙니다.

`document_create(uploadId)`는 실행 시점에 다음을 다시 확인해야 합니다.

1. 현재 MCP 사용자가 인증돼 있는가
2. 현재 사용자와 Ticket 소유자가 같은가
3. 현재 테넌트와 Ticket의 테넌트가 같은가
4. Ticket이 만료·취소되지 않았는가
5. 파일이 `VERIFIED` 상태인가
6. 아직 다른 업무에서 소비되지 않았는가
7. 파일 유형이 해당 Tool의 목적에 맞는가
8. 사용자가 대상 Group·Project에 생성 권한이 있는가

Upload Token은 Byte 전송 권한이고, MCP Access Token은 업무 Tool 호출 권한입니다. 두 자격 증명의 Scope와 수명을 분리해야 합니다.

업무 처리가 시작되면 `uploadId`, 생성된 업무 ID와 `idempotencyKey`의 관계를 저장합니다.

## 9. 재시도와 중복 실행 기준을 정한다

업로드는 네트워크 단절과 Timeout이 자주 발생하는 작업입니다. 단계별 재시도 의미를 구분해야 합니다.

| 실패 지점 | 안전한 기본 대응 |
|---|---|
| Ticket 발급 응답 유실 | 요청 멱등성 키로 기존 Ticket 조회 |
| Byte 전송 전 실패 | 같은 Ticket이 유효하면 다시 전송 |
| 전송 중 연결 종료 | 전체 재전송 또는 Offset 기반 재개 |
| 전송 완료 응답 유실 | Upload 상태·크기·Checksum 조회 |
| 검증 실패 | 같은 Byte 무한 재시도 금지, 원인 반환 |
| 업무 생성 응답 유실 | 업무 멱등성 키로 기존 결과 조회 |
| Ticket 만료 | 새 Ticket을 발급하고 이전 임시 Object 정리 |

Presigned URL은 구현에 따라 만료 전 여러 번 사용할 수 있으므로 Application이 단일 사용을 요구한다면 별도의 상태 전이와 Object Key 정책이 필요합니다.

같은 Object Key에 재전송할 때 기존 Object를 덮어쓰는지, 충돌을 거부하는지 명확히 해야 합니다. 한 Ticket에 다른 Checksum이 들어오면 새 파일로 처리하지 말고 오류로 종료하는 편이 안전합니다.

## 10. 대용량 파일은 재개 가능한 Upload를 고려한다

작은 파일은 단일 `PUT`으로 충분할 수 있습니다. 수백 MB 이상의 영상이나 불안정한 네트워크에서는 처음부터 다시 보내는 비용이 커집니다.

선택지는 다음과 같습니다.

- Object Storage Multipart Upload(분할 업로드)
- Chunk별 Upload URL
- Offset 기반 재개
- tus 같은 Resumable Upload Protocol

tus Core Protocol은 `HEAD`로 현재 `Upload-Offset`을 확인하고 `PATCH`로 남은 Byte를 이어 보내는 방식을 정의합니다. Expiration과 Checksum Extension도 제공합니다.

재개 Upload를 도입하면 다음 Metadata가 추가됩니다.

```json
{
  "uploadId": "upl_opaque_handle",
  "status": "UPLOADING",
  "uploadLength": 734003200,
  "receivedBytes": 314572800,
  "nextOffset": 314572800,
  "expiresAt": "2026-07-29T09:00:00Z"
}
```

Chunk 순서, 중복 Chunk, Part Checksum, 완료 요청의 멱등성과 중단된 Multipart 정리 정책을 함께 설계해야 합니다.

## 11. 오류를 MCP 오류와 Upload HTTP 오류로 나눈다

Ticket 준비와 업무 생성은 MCP Tool 결과로, Byte 전송은 HTTP 응답으로 실패합니다.

| 구간 | 오류 예시 | 반환 위치 |
|---|---|---|
| Ticket 준비 | 권한 없음, 확장자 거부, 크기 초과 | MCP Tool Execution Error |
| Byte 전송 | 서명 만료, Checksum 불일치, 용량 초과 | Upload HTTP Error |
| 파일 검증 | Malware, 실제 형식 불일치 | Upload 상태 또는 검증 API |
| 업무 생성 | Ticket 미완료, 이미 소비됨, 업무 권한 없음 | MCP Tool Execution Error |
| 비동기 처리 | Parser·STT·요약 실패 | 업무 상태 조회 Tool |

HTTP 오류에 Problem Details(표준 오류 형식)를 적용하면 Client가 오류 유형과 재시도 가능성을 구조적으로 처리할 수 있습니다.

```json
{
  "type": "https://api.example.net/problems/upload-expired",
  "title": "Upload ticket expired",
  "status": 410,
  "detail": "Request a new upload ticket and retry the transfer.",
  "uploadId": "upl_opaque_handle",
  "retryable": false
}
```

내부 Stack Trace, Storage Bucket, 실제 Object Key와 보안 정책 세부사항은 오류 응답에 노출하지 않습니다.

## 12. 사용되지 않은 파일을 자동 정리한다

Ticket만 발급하고 사용하지 않거나, Byte는 올렸지만 업무 Tool을 호출하지 않는 경우가 생깁니다.

다음 보존 정책이 필요합니다.

- `PREPARED` 상태 만료
- 중단된 Multipart Upload 정리
- `UPLOADED`지만 검증되지 않은 파일의 Quarantine 보존 기간
- `VERIFIED`지만 소비되지 않은 고아 파일 정리
- `REJECTED` 파일의 조사·삭제 기준
- 업무 레코드 삭제 시 원본 파일 처리
- 법적 보존 또는 감사 예외

Ticket의 만료와 Object 삭제는 같은 시각일 필요가 없습니다. Ticket은 즉시 사용할 수 없게 만들고, Object는 안전한 Background Cleanup으로 제거할 수 있습니다.

정리 Worker도 사용자·테넌트와 업무 참조를 확인해 사용 중인 파일을 삭제하지 않도록 해야 합니다.

## 13. 관측성은 세 구간을 하나의 흐름으로 연결한다

진단을 위해 다음 ID를 연결합니다.

```text
MCP requestId
  └─ uploadId
      ├─ storageObjectId
      ├─ verificationJobId
      └─ businessWorkflowId
```

권장 지표는 다음과 같습니다.

- 발급·사용·만료 Ticket 수
- Upload 성공률과 전송 시간
- 크기 구간별 실패율
- Checksum·형식·Malware 검증 실패
- 재개 Upload 비율과 평균 재전송 Byte
- `VERIFIED` 후 미소비 파일 수
- 가장 오래된 고아 Upload 나이
- 업무 처리 단계별 실패율
- 사용자·테넌트별 저장량과 한도

Trace Context(추적 문맥)를 MCP 호출, Upload Service, 검증 Worker와 업무 Workflow에 전파하면 한 요청의 전체 경로를 볼 수 있습니다. 단, 서명 URL과 Bearer Token을 Trace Attribute나 Baggage에 넣지 않습니다.

## 14. 구현 선택 기준

| 조건 | 권장 시작점 |
|---|---|
| 작은 파일, 낮은 트래픽 | Application Upload API + 단일 `PUT` |
| Object Storage 사용 | Presigned URL + Checksum + 상태 확인 |
| 대용량 파일 | Multipart 또는 tus |
| 강한 보안 요구 | Quarantine + 비동기 Scan + 별도 Storage |
| 여러 업무가 같은 파일 사용 | 불변 Object + 참조 수명주기 |
| 단일 사용이 중요 | Ticket 상태 전이 + 소비 Transaction |
| 불안정한 Client 네트워크 | Offset·Part 재개 + 만료 연장 정책 |

처음부터 가장 복잡한 Upload Platform을 만들 필요는 없습니다. 하지만 파일 경로와 Byte 전송의 경계, Ticket의 Scope, 검증 전 격리와 고아 파일 정리는 초기 설계에 포함해야 합니다.

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| 실행 위치 | MCP Server가 로컬 Process인지 원격 서비스인지 구분하는가 |
| Tool 계약 | 원격 Tool이 Client 로컬 경로를 요구하지 않는가 |
| 제어·데이터 | MCP 요청과 파일 Byte 전송 경로가 분리돼 있는가 |
| Ticket | `uploadId`, 만료, Method, 크기와 Scope가 명확한가 |
| 권한 | Ticket이 사용자·테넌트·업무 목적에 묶여 있는가 |
| 자격 증명 | Upload Token과 MCP Access Token이 분리돼 있는가 |
| 로그 | Presigned URL, Token과 로컬 경로를 기록하지 않는가 |
| 파일명 | Application이 생성한 Storage Key를 사용하는가 |
| 형식 | 확장자·MIME·File Signature를 함께 검증하는가 |
| 무결성 | 선언 크기와 Checksum을 확인하는가 |
| 악성 파일 | Quarantine, Scan과 Parser 격리가 있는가 |
| 상태 | Upload 상태와 업무 처리 상태를 분리하는가 |
| 소비 | 업무 Tool이 Ticket 소유자·상태·권한을 재검증하는가 |
| 재시도 | 응답 유실, 중복 전송과 만료 후 동작이 정의돼 있는가 |
| 대용량 | Multipart·Offset 재개가 필요한 기준이 있는가 |
| 오류 | MCP 오류와 Upload HTTP 오류를 구분하는가 |
| 정리 | 만료 Ticket, 고아 파일과 중단 Upload를 제거하는가 |
| 관측성 | MCP 요청부터 업무 Workflow까지 ID와 Trace가 연결되는가 |

## 마무리

원격 MCP 파일 업로드 문제의 출발점은 단순합니다. **파일 경로는 파일이 아니라 한 파일시스템 안에서만 의미가 있는 문자열**입니다.

안전한 원격 업로드를 위해서는 다음 원칙이 필요합니다.

1. 로컬 `stdio`와 원격 HTTP MCP의 실행 위치를 구분합니다.
2. MCP Tool은 Upload Ticket을 준비하고, 실제 Byte는 별도 HTTPS 경로로 전송합니다.
3. Ticket을 짧은 수명, 작은 Scope와 특정 Object에 묶습니다.
4. 파일명, 크기, Checksum, 실제 형식과 악성 여부를 검증합니다.
5. Upload 완료와 STT·Parsing·요약 같은 업무 완료를 분리합니다.
6. 후속 Tool은 현재 사용자, 테넌트, Ticket 상태와 업무 권한을 다시 확인합니다.
7. 대용량 파일은 Multipart 또는 Offset 기반 재개를 고려합니다.
8. 중복 전송, 만료와 고아 파일 정리 정책을 운영 지표와 함께 관리합니다.

Upload Ticket은 단순한 임시 URL이 아닙니다. 사용자의 로컬 파일과 원격 업무 시스템 사이에 제한된 데이터 전달 경계를 만드는 보안·운영 계약입니다.

다음 글에서는 원격 MCP Server를 기업 환경에 연결할 때 OAuth 2.1 Discovery, PKCE와 Resource Server의 권한 경계를 어떻게 구성할지 살펴보겠습니다.

---

## 참고 자료

- [MCP 2026-07-28 Specification Release Candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
- [MCP Draft: Transports](https://modelcontextprotocol.io/specification/draft/basic/transports)
- [MCP Draft: Stateful Tools and Explicit Handles](https://modelcontextprotocol.io/specification/draft/server/tools)
- [Amazon S3: Download and upload objects with presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
- [AWS Presigned URL Best Practices: Additional guardrails](https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/additional-guardrails.html)
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [tus Resumable Upload Protocol](https://tus.io/protocols/resumable-upload)
- [RFC 9457: Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc9457)
- [RFC 6750: OAuth 2.0 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)

> 이 글은 2026년 7월 29일 기준 공개된 MCP·HTTP·Object Storage·보안 문서와 공개 가능한 원격 MCP 파일 업로드 검증 경험을 바탕으로 작성했습니다. 실제 구현에서는 사용 중인 Storage, 최대 파일 크기, 규제 요건과 Client의 재개 Upload 지원 범위를 함께 확인해야 합니다.
