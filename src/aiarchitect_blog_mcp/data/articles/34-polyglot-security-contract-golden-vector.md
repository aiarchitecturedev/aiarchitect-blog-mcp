# Tistory 기술자료 초안

- 문서 ID: `BLOG-34`
- 상태: 공개 완료
- Tistory 상태: 2026-07-31 공개 전환 및 공개 페이지 검증 완료
- 공개 URL: https://aiarchitect.tistory.com/34
- 분류: `엔터프라이즈 아키텍처`
- 권장 제목: `폴리글랏 보안 계약 검증: Java↔Python Golden Vector와 Canonical Byte`
- 검색 설명: `Java Security Gateway와 Python AI Orchestrator처럼 언어가 다른 서비스 사이의 토큰·JWKS·정규 바이트 보안 계약을 골든 벡터로 교차 검증하는 방법을 정리합니다. 직렬화·인코딩·시간·정렬 차이가 만드는 보안 불일치와 계약 테스트, 키 롤오버 운영까지 다룹니다.`
- 권장 태그: `JWT`, `JWKS`, `RS256`, `Golden Vector`, `Canonical`, `Contract Test`, `Java Python`
- 권장 대표 이미지: `portfolio/architecture-diagrams/01-enterprise-ai-reference-architecture.svg`

---

# 폴리글랏 보안 계약 검증: Java↔Python Golden Vector와 Canonical Byte

기업용 AI 백엔드는 **한 언어로만 만들어지지 않는 경우가 많습니다.** 인증과 테넌트 정책을 담당하는 Java 17 / Spring Boot 기반 Security Gateway가 앞에 있고, Agent·RAG·모델 조율을 담당하는 Python / FastAPI 기반 Orchestrator가 뒤에 있는 구조를 종종 사용합니다. 이 두 서비스의 책임을 어떻게 나눌지는 이미 별도 글([Java Security Gateway와 Python AI Orchestrator의 책임 분리](https://aiarchitect.tistory.com/5))에서 다뤘습니다.

이 글은 그 다음 질문을 다룹니다.

> 두 서비스가 서로 다른 언어로 짜여 있는데, **같은 토큰·같은 서명·같은 해시를 정말 똑같이 계산하고 있다는 것을 어떻게 증명하는가?**

책임 분리는 설계 문제이지만, 이 질문은 **정확성 (Correctness)** 문제입니다. Java가 만든 서명을 Python이 검증하고, Python이 계산한 요청 지문 (Request Fingerprint)을 Java가 재현할 수 없다면, 겉으로는 동작하는 것처럼 보여도 보안 경계에 조용한 구멍이 생깁니다. 이 글은 그 구멍을 **골든 벡터 (Golden Vector)** 와 **정규 바이트 (Canonical Byte)** 로 막는 방법을 정리합니다.

아래 내용은 필자가 설계·검증 단계에서 정리한 원칙을 익명화해 재구성한 것이며, 특정 고객사·내부 시스템·비공개 제품 정보·실측 수치는 포함하지 않습니다(Keycloak·KMS·mTLS 등은 널리 알려진 공개 기술로만 언급합니다). 실제 Keycloak Token Exchange, KMS, mTLS 같은 인프라 연동은 후속 과제로 두고, 이 글은 **언어 간 계약의 정확성 검증**에 집중합니다.

## 1. 폴리글랏 (Polyglot)의 진짜 위험은 언어가 아니라 표현 차이다

폴리글랏 아키텍처 (Polyglot Architecture)의 위험은 흔히 `언어를 두 개 쓰면 복잡하다` 정도로 이야기됩니다. 하지만 보안 관점에서 진짜 위험은 다른 곳에 있습니다.

두 언어가 **같은 논리적 데이터를 서로 다른 바이트로 표현할 때** 문제가 생깁니다. 서명과 해시는 논리값이 아니라 **바이트열 (Byte Sequence)** 위에서 계산되기 때문에, 표현이 1바이트만 달라도 검증은 실패합니다. 더 위험한 경우는 서명 검증 자체는 정상인데 — 즉 수신한 바이트에 대한 서명은 유효한데 — **파서·인가기·실행기가 그 같은 바이트를 서로 다르게 해석하는 의미론적 불일치 (semantic mismatch)** 입니다. 이때는 서명이 통과하고도 두 서비스가 다른 것을 "승인된 요청"으로 받아들이게 됩니다.

| 차이 유형 | Java 17 기본 동작 예 | Python 기본 동작 예 | 보안 영향 |
|---|---|---|---|
| JSON 키 순서 | `LinkedHashMap` 삽입 순서 / `HashMap` 순회 순서 명세상 미보장 | `dict` 삽입 순서 (3.7+) | 서명 대상 바이트 불일치 |
| 공백·구분자 | 라이브러리별 `": "` vs `":"` | `json.dumps` 기본 `", "` 공백 포함 | 다이제스트 불일치 |
| 유니코드 정규화 | `String`은 정규화 안 함 | `str`도 정규화 안 함 | 결합 문자에서 지문 불일치 |
| 정수 인코딩 | `BigInteger` 부호 바이트 | `int.to_bytes` 부호·길이 | 키 파라미터 불일치 |
| 실수 표현 | `Double.toString` | `repr(float)` | 다이제스트 불일치 |
| 시간 정밀도 | `Instant` 나노초 | `datetime` 마이크로초 | `exp`/`nbf` 경계 오판 |
| 널/생략 필드 | `null` 직렬화 vs 생략 | `None` 직렬화 vs 생략 | 대상 바이트 불일치 |

핵심은 이렇습니다. **"둘 다 유효한 JSON을 만들지만, 둘의 바이트는 다르다."** 유효한 JSON은 여러 개일 수 있어도, 서명·해시 대상은 **하나로 고정된 바이트**여야 합니다.

## 2. 무엇을 계약 (Contract)으로 볼 것인가

언어 간 계약을 이야기하기 전에, 무엇이 계약의 대상인지 명확히 해야 합니다. 이 글에서 다루는 계약은 세 층으로 나눕니다.

```text
[1] 토큰 계약        : RS256 서명·검증, kid 매칭, 클레임 검증 규칙
[2] 정규 바이트 계약 : 서명/해시 대상의 정규 직렬화 규칙
[3] 파생 식별자 계약 : 결정적 ID·요청 지문의 계산 규칙
```

이 세 계약은 서로 독립적으로 깨질 수 있습니다. 예를 들어 토큰 검증은 정상인데 요청 지문만 언어별로 다르게 계산될 수 있습니다. 그래서 **계약별로 골든 벡터를 따로 관리**해야 어디가 규격을 위반했는지 좁혀낼 수 있습니다.

## 3. 정규 바이트 (Canonical Byte)란 무엇인가

정규 바이트는 `같은 논리 데이터 → 항상 같은 바이트열`을 보장하는 직렬화 규칙입니다. 표준화된 접근으로는 **JSON 정규화 스킴 (JSON Canonicalization Scheme, JCS, RFC 8785)** 이 있고, JCS는 다음을 규정합니다.

- 객체 키를 정렬한다 (UTF-16 코드 유닛 기준).
- 불필요한 공백을 제거한다.
- 숫자를 ECMAScript 규칙으로 정규화한다.
- 문자열을 최소 이스케이프로 표현한다.

여기서 반드시 짚어야 할 점이 있습니다. **JCS는 문자열의 유니코드 정규화(NFC 등)를 수행하지 않으며, 입력 문자열을 원문 그대로 보존합니다.** JCS가 다루는 것은 이스케이프·직렬화 형식이지, 유니코드 정규화 형식이 아닙니다. 또한 JCS는 중복 키나 비정상 유니코드(lone surrogate 등)를 허용하지 않고 거부합니다(RFC 8785). 따라서 결합 문자를 정규화하고 싶다면 그것은 JCS와 **별개의 규칙**으로, 아래 자체 정규 형식(NFC 강제)에서 명시적으로 추가해야 합니다.

JCS를 그대로 채택하면 형식 논쟁의 여지가 줄어듭니다. 하지만 (1) JCS는 숫자 표현을 ECMAScript(즉 IEEE 754 double) 규칙에 맡기므로 **큰 정수·통화·정밀도가 중요한 값**에서 주의가 필요하고, (2) 유니코드 정규화를 하지 않으므로 결합 문자 정규화가 필요하면 입력 단계에서 별도로 해결해야 합니다. 그래서 실무에서는 다음 두 갈래 중 하나를 명시적으로 고릅니다.

| 전략 | 설명 | 장점 | 주의점 |
|---|---|---|---|
| JCS 채택 | RFC 8785을 그대로 사용 | 표준·검증기 존재, 중복 키·비정상 유니코드 거부 | 숫자를 double로 취급, 유니코드 정규화는 하지 않음 |
| 자체 정규 형식 | 조직 표준 직렬화 규칙 정의(NFC 포함) | 정수·정밀도·정규화 통제 가능 | 규격 문서·검증기 직접 관리 |

어느 쪽을 고르든 원칙은 하나입니다. **"서명·해시 대상은 사람이 읽는 JSON이 아니라, 규칙으로 재현 가능한 바이트열이다."**

## 4. 정규 직렬화 규칙을 명세로 못 박기

정규 바이트 계약은 코드보다 먼저 **명세 문서**로 존재해야 합니다. 아래는 자체 정규 형식을 택했을 때의 규칙 명세 예시입니다.

```text
CANONICAL-JSON v1
1. 인코딩: UTF-8, BOM 없음
2. 객체 키: UTF-16 코드 유닛 오름차순 정렬
3. 구분자: 키-값 ":" (공백 없음), 항목 "," (공백 없음)
4. 문자열: 유니코드 정규화 NFC 후 최소 이스케이프
   (바이트 수준 규칙, RFC 8785 문자열 직렬화와 동일:
    " → \" , \ → \\ ,
    U+0008/0009/000A/000C/000D → \b \t \n \f \r ,
    그 밖의 U+0000~001F → 소문자 \u00xx ,
    나머지 유효 문자는 원문 UTF-8, '/'는 이스케이프하지 않음)
5. 정수: JSON number 토큰으로 10진 표기(따옴표 없음), 선행 0 금지, -0 금지
   (원문 바이트 경로에서만 검출 가능 — 6절 "입력 경로 분리" 참조)
6. 실수: 계약에서 금지 (문자열 또는 정수 최소단위로 표현)
7. 불리언/널: true / false / null (소문자)
8. 널/생략 규칙: 아래 "널 처리" 참조 — 정규화기가 임의로 삭제하지 않는다
9. 배열: 요소 순서 보존(정렬하지 않음)

거부 규칙 (아래 중 하나라도 위반하면 정규화 실패로 처리)
R1. 같은 객체 내 중복 키
R2. NFC 적용 후 서로 다른 키가 같은 키로 합쳐지는 정규화 충돌
R3. lone surrogate 등 유효하지 않은 유니코드
R4. 문자열이 아닌 객체 키, NaN, Infinity, 실수 입력
R5. 최대 입력 크기·중첩 깊이 초과 (한계값은 배포별로 고정)
```

**널 처리 (중요):** 정규화기가 `null` 값을 임의로 삭제하면 "필드 부재"와 "명시적 null"이라는 서로 다른 입력이 같은 바이트로 합쳐져 버립니다. 이는 계약 정확성을 훼손합니다. 따라서 이 계약은 정규화기 단계에서 삭제하지 않고, 다음 중 하나를 **입력 DTO 투영 단계**에서 명시적으로 정한다.

- 선택 필드는 애초에 페이로드에 넣지 않는다(부재 = 없음).
- 명시적 `null`은 그대로 유지해 직렬화하거나, 계약이 금지한다면 거부한다.

즉 "널이면 키를 지운다"는 정규화기 규칙이 아니라, 무엇을 페이로드에 담을지의 상위 설계 결정입니다.

이 명세는 언어에 종속되지 않아야 합니다. Java와 Python은 각자 이 명세를 구현할 뿐이며, **명세가 진실의 원천 (Source of Truth)** 입니다. 명세와 구현이 다르면 명세가 이깁니다.

## 5. 정규 바이트 구현: Java 예시

Java에서는 JSON 라이브러리의 기본 직렬화에 의존하지 말고, 정규 규칙을 직접 구현하거나 JCS 라이브러리를 사용합니다. 아래는 **개념 코드 (실행용 아님)** 로, 정규 직렬화의 핵심 골격만 보여줍니다. 실제 구현은 4절의 거부 규칙(R1~R5)과 정렬·인코딩을 모두 갖춰야 합니다.

핵심 순서가 중요합니다. 키는 **먼저 NFC로 정규화한 뒤 그 결과를 기준으로 정렬**해야 Python 구현과 규칙이 일치합니다(정규화 전 원본 키를 정렬하면 두 언어가 갈립니다). 그리고 NFC 후 키가 겹치면(R2) 즉시 실패해야 합니다.

```java
// 개념 코드 (실행용 아님): 정규 직렬화의 핵심 골격
// 실제 구현은 R1~R5 거부 규칙, 정수/불리언/배열 인코딩, 최소 이스케이프를 모두 포함해야 함
static String canonicalize(JsonNode node) {
    StringBuilder sb = new StringBuilder();
    write(node, sb);
    return sb.toString();
}

static void write(JsonNode node, StringBuilder sb) {
    if (node.isObject()) {
        // 1) 키를 먼저 NFC로 정규화하고, 정규화 결과 기준으로 정렬한다.
        // TreeMap 자연 정렬 = String.compareTo = UTF-16 코드 유닛 사전식 순서
        Map<String, JsonNode> byNfcKey = new TreeMap<>();
        node.fields().forEachRemaining(e -> {
            String nfcKey = Normalizer.normalize(e.getKey(), Normalizer.Form.NFC);
            if (byNfcKey.put(nfcKey, e.getValue()) != null) {
                throw new IllegalArgumentException("R2 위반: NFC 정규화 후 키 충돌 - " + nfcKey);
            }
        });
        sb.append('{');
        boolean first = true;
        for (Map.Entry<String, JsonNode> e : byNfcKey.entrySet()) {
            if (!first) sb.append(',');
            first = false;
            writeString(e.getKey(), sb);   // 키는 이미 NFC, 최소 이스케이프로 출력
            sb.append(':');
            write(e.getValue(), sb);
        }
        sb.append('}');
    } else if (node.isTextual()) {
        String nfc = Normalizer.normalize(node.asText(), Normalizer.Form.NFC);
        writeString(nfc, sb);
    }
    // 정수/불리언/널/배열 처리 및 R1·R3·R4·R5 거부는 명세 규칙대로 (여기서는 생략)
}
```

여기서 중요한 것은 라이브러리 선택이 아니라, **명세의 각 조항이 코드의 한 지점으로 대응되는지**입니다. 정렬 기준(코드 유닛 정렬)과 정규화 순서(NFC → 정렬)가 명세·다른 언어 구현과 다르면 그 자체가 계약 위반입니다. 위 코드의 `TreeMap` 자연 정렬은 Java `String.compareTo`를 사용하므로 UTF-16 `char`(코드 유닛)의 사전식 순서와 정확히 일치합니다(RFC 8785도 Java를 UTF-16 정렬이 직접 대응되는 환경으로 듭니다). 의도를 드러내기 위해 `Comparator.naturalOrder()`를 명시할 수는 있지만, 별도 정렬 알고리즘은 필요하지 않습니다. 진짜 주의할 곳은 뒤에서 볼 **Python 쪽**으로, 파이썬 기본 정렬은 코드 포인트 기준이라 UTF-16 코드 유닛 순서와 다를 수 있습니다(6절).

## 6. 정규 바이트 구현: Python 예시

Python의 `json.dumps`는 기본으로 공백을 넣고(`, ` / `: `), 비ASCII를 이스케이프하며, 키 정렬을 하지 않습니다. 게다가 `sort_keys=True`를 켜도 그 정렬은 **파이썬 문자열 비교(코드 포인트 기준)** 라, 명세가 요구하는 **UTF-16 코드 유닛 기준** 정렬과 **다릅니다**(보충 평면 키에서 Java와 갈립니다 — 아래 참조). 그래서 `json.dumps`의 옵션에 기대지 말고, **정렬과 문자열 이스케이프까지 직접 구현**하고 **명세의 거부 규칙(R1~R4)을 코드로 강제**해야 합니다. 아래는 **개념 코드 (실행용 아님)** 이지만, 정렬 기준·이스케이프·거부 규칙을 어디에 넣어야 하는지를 명확히 보여줍니다.

```python
# 개념 코드 (실행용 아님): UTF-16 정렬·바이트 수준 이스케이프·거부 규칙을 직접 구현
import unicodedata

# 명세 4절의 "최소 이스케이프" (RFC 8785 문자열 직렬화와 동일):
#   " → \" , \ → \\ , U+0008/0009/000A/000C/000D → \b \t \n \f \r ,
#   그 밖의 U+0000~001F → 소문자 \u00xx , 나머지는 원문 UTF-8, '/'는 이스케이프하지 않음.
_SHORT_ESC = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t",
              "\n": "\\n", "\f": "\\f", "\r": "\\r"}

def _encode_string(s: str) -> str:
    out = ['"']
    for ch in s:                       # s 는 이미 NFC 정규화된 문자열
        if ch in _SHORT_ESC:
            out.append(_SHORT_ESC[ch])
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))   # 소문자 hex
        else:
            out.append(ch)             # 원문 그대로 (UTF-8 인코딩은 마지막에)
    out.append('"')
    return "".join(out)

def _utf16_key(k: str) -> bytes:
    # UTF-16 코드 유닛 순서로 정렬하기 위한 키. Java String.compareTo 와 일치.
    return k.encode("utf-16-be")

def _canonicalize(v) -> str:
    # R4: 실수 입력 거부 (bool 은 int 의 하위형이므로 먼저 통과시킴)
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, float):
        raise ValueError("R4 위반: 실수 입력 금지 (정수 최소단위/문자열로 표현할 것)")
    if isinstance(v, int):
        return str(v)                  # -0 은 파이썬 int 에서 이미 0
    if isinstance(v, str):
        return _encode_string(unicodedata.normalize("NFC", v))
    if isinstance(v, list):
        return "[" + ",".join(_canonicalize(x) for x in v) + "]"
    if isinstance(v, dict):
        norm = {}
        for k, x in v.items():
            if not isinstance(k, str):
                raise ValueError("R4 위반: 문자열이 아닌 객체 키")
            nk = unicodedata.normalize("NFC", k)
            if nk in norm:                     # R2: NFC 정규화 후 키 충돌
                raise ValueError(f"R2 위반: NFC 정규화 후 키 충돌 - {nk!r}")
            norm[nk] = x
        # 정렬은 sort_keys 가 아니라 UTF-16 코드 유닛 기준으로 직접 수행
        items = sorted(norm.items(), key=lambda kv: _utf16_key(kv[0]))
        return "{" + ",".join(_encode_string(k) + ":" + _canonicalize(x)
                              for k, x in items) + "}"
    raise ValueError(f"R4 위반: 허용되지 않은 타입 {type(v).__name__}")

def canonicalize(value) -> bytes:
    text = _canonicalize(value)
    # R3(lone surrogate 등)은 여기서 UTF-8 인코딩이 실패하며 드러난다.
    return text.encode("utf-8")
```

세 가지를 강조합니다. 첫째, **정렬을 `sort_keys=True`에 맡기지 않습니다.** 파이썬 기본 정렬은 코드 포인트 기준이라, U+E000과 `😀`(U+1F600)처럼 BMP 안팎이 섞이면 UTF-16 코드 유닛 정렬(`😀` → U+E000)과 순서가 뒤집힙니다. 그래서 `key.encode("utf-16-be")`로 정렬해 Java `String.compareTo`와 바이트 단위로 맞춥니다. 둘째, **문자열 이스케이프도 직접 구현**해 명세 4절의 "최소 이스케이프"를 바이트 수준으로 못 박습니다(위 `_encode_string`). 셋째, 실수·NaN·Infinity·비문자열 키는 `_canonicalize`에서 예외로 거부하므로 `allow_nan` 같은 옵션에 의존하지 않습니다.

**입력 경로 분리 (중요):** 위 `canonicalize`는 **이미 파서를 통과해 데이터 모델(파이썬 값)이 된 입력**을 다룹니다. 그런데 원문 JSON의 함정 중 일부는 파싱 단계에서 이미 사라집니다. 예를 들어 원문 중복 키(R1)는 `dict`가 되는 순간 하나로 병합되고, `-0`은 정수 `0`으로 바뀝니다. 따라서 이 계약은 **두 경로를 명시적으로 분리**합니다.

```python
# 개념 코드 (실행용 아님): 원문 바이트 경로와 데이터 모델 경로의 분리
def canonicalize_raw(raw: bytes) -> bytes:
    # 원문 바이트에서만 검출 가능한 규칙을 파싱 단계에서 검사:
    #   UTF-8/BOM, 최대 크기·중첩 깊이(R5), 같은 객체 내 중복 키(R1),
    #   숫자 토큰 규칙(선행 0 금지·-0 금지 등). 이를 위해 중복 키를 보존하는
    #   커스텀 파서(예: object_pairs_hook 로 중복 검사)를 사용한다.
    value = parse_strict(raw)         # 위 규칙을 강제하는 파서 (개념)
    return canonicalize(value)        # 검증된 데이터 모델을 정규 직렬화

# 이미 신뢰된 인메모리 값이면 canonicalize(value) 를 직접 호출한다.
```

즉 `canonicalize`(데이터 모델)에서는 R2(NFC 충돌)·R4(타입)만 확실히 검출할 수 있고, R1(원문 중복 키)·`-0`·크기/깊이(R5)는 반드시 `canonicalize_raw`(원문 바이트)에서 검사해야 합니다. 만약 `-0` 금지를 별도로 두기 부담스럽다면, 규칙을 "`-0`은 정수 0으로 정규화한다"로 바꿔 데이터 모델 경로 하나로 합칠 수도 있습니다. 어느 쪽이든 **어느 경로가 어떤 규칙을 책임지는지**를 명세에 못 박아야 두 언어의 수락 집합이 일치합니다.

## 7. 토큰 계약: RS256 서명과 검증

내부 서비스 간 신뢰는 **RS256(RSASSA-PKCS1-v1_5 + SHA-256, RFC 7518)** 로 서명한 JWT(RFC 7519)로 전달합니다. Gateway가 발급하고 Orchestrator가 검증하는 구조에서, 계약의 검증 항목은 다음과 같습니다.

| 검증 항목 | 규칙 | 실패 시 |
|---|---|---|
| `alg` | `RS256`만 허용, `none`·HS* 거부 (수신 헤더값을 신뢰하지 않음) | 검증 거부 |
| 서명 | JWKS의 공개키로 `header.payload` 바이트를 검증 (RFC 7515) | 검증 거부 |
| `kid` | **필수 string.** 헤더 `kid`로 JWKS 키 선택(`jku`/`x5u` 등 수신 URL은 신뢰하지 않음, RFC 7517). 부재·빈 문자열·미매칭·동일 `kid` 복수 키는 모두 거부 | 거부 |
| 키-알고리즘 결합 | 선택된 키가 `RS256`용(`kty=RSA`, `use=sig`)인지 확인 | 거부 |
| `iss` | 발급자 고정값 일치 + `iss`와 검증 키(JWKS)의 결합 확인 | 거부 |
| `typ` | 프로파일이 요구하면 `at+jwt` 등 기대 타입 확인 (RFC 8725 권고) | 거부 |
| `aud` | 대상 서비스 식별자 일치 (문자열 또는 배열 — 아래 P1 표 참조) | 거부 |
| `exp` | **현재 시각이 `exp`와 같거나 크면(now ≥ exp) 만료** | 거부 |
| `nbf` | 현재 시각이 `nbf` 미만이면(now < nbf) 미유효 | 거부 |
| `iat` | **본 프로파일에서 필수.** `iat > now + L`(미래 발급) 거부, `exp > iat`가 아니면 거부, `exp - iat > MAX_TOKEN_LIFETIME` 거부 | 거부 |
| 필수 클레임 | `iss`/`aud`/`exp`/`iat`/`kid` 등 필수 클레임 부재 시 거부, 중복 클레임 거부 | 거부 |

`alg` 혼동 공격(algorithm confusion)을 막으려면 **검증 측이 허용 알고리즘을 화이트리스트로 고정**해야 합니다. 토큰 헤더가 지정한 알고리즘을 그대로 신뢰하면 안 됩니다. RFC 8725(JWT Best Current Practices)는 여기에 더해 **알고리즘 허용 목록 고정, 키와 알고리즘의 결합, issuer와 검증 키의 결합, audience 검증**을 함께 요구합니다. 또한 `kid`·`jku`·`x5u` 같은 헤더 수신값을 신뢰해 임의 조회하면 안 됩니다.

> 여기서 검증하는 것은 **JWT의 JWS Signing Input(즉 수신한 `header.payload` 바이트)에 대한 서명**입니다. 이는 애플리케이션 페이로드를 JCS로 정규화하는 문제와 **별개**입니다. 일반적인 JWT 검증기는 수신한 바이트를 그대로 검증하므로 JCS 재직렬화가 필요하지 않습니다. 정규 바이트 계약(3~6절)은 JWT 안이 아니라, 요청 지문·결정적 ID·AAD처럼 **애플리케이션이 스스로 해시·서명 대상을 만들 때** 적용됩니다.

계약을 실제 프로파일로 굳히려면 클레임 타입과 경계까지 못 박아야 합니다.

| 클레임 | 타입 | 프로파일 규칙 |
|---|---|---|
| `iss` | string | 필수, 신뢰 발급자 목록과 일치, 검증 키와 결합 |
| `aud` | string 또는 string 배열 | 필수, 내 서비스 식별자가 값(또는 배열 원소)에 포함되어야 통과 |
| `exp` | NumericDate | 필수, `now ≥ exp`이면 거부 (스큐는 아래 15절 적용식) |
| `nbf` | NumericDate | 있으면 `now < nbf`일 때 거부 |
| `iat` | NumericDate | **본 프로파일에서 필수**(RFC 7519 자체는 선택). `iat > now + L`이면 거부, `exp > iat`가 아니면 거부, `exp - iat > MAX_TOKEN_LIFETIME`이면 거부 |
| `kid`(헤더) | string | **필수.** 부재·빈 문자열·미매칭·동일 `kid` 복수 키 모두 거부 |
| `jti` | string | 재생 방지용 고유값(원자적 저장소와 함께 사용, 17절) |
| `typ`(헤더) | string | 프로파일이 요구하면 기대값 고정 |

`aud`가 배열일 수 있다는 점은 특히 놓치기 쉽습니다. 문자열만 가정하고 비교하면 배열 형태의 정상 토큰을 거부하거나, 반대로 배열 처리 실수로 검증이 느슨해질 수 있으므로 두 형태를 모두 명세에 적어야 합니다.

또한 `iat`의 두 규칙을 혼동하지 말아야 합니다. `exp - iat <= MAX_TOKEN_LIFETIME`은 **토큰이 선언한 수명 자체**를 제한하는 규칙이고, `now - iat`는 **검증 시점의 토큰 나이**를 뜻합니다. 둘은 다른 값이므로, 수명을 제한하려면 `exp - iat`를, 오래된 토큰을 추가로 걷어내려면 별도로 `now - iat <= MAX_TOKEN_AGE + L`을 둡니다. 본 프로파일은 `iat` 필수, `exp > iat`, `exp - iat <= MAX_TOKEN_LIFETIME`, `iat <= now + L`을 기본으로 하고, `MAX_TOKEN_AGE`는 필요 시 추가합니다.

## 8. JWKS 계약: 키 배포와 `kid` 매칭

**JWKS(JSON Web Key Set, RFC 7517)** 는 공개키를 JSON으로 배포하는 표준입니다. RS256 공개키는 모듈러스 `n`과 지수 `e`를 **base64url(RFC 4648)** 로 인코딩해 표현합니다.

```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "alg": "RS256",
      "kid": "example-key-1",
      "n": "0vx7agoebGcQSuuPiLJXZptN...(base64url, 예시값)",
      "e": "AQAB"
    }
  ]
}
```

여기서 언어 간 함정은 **`n`의 정수 인코딩**입니다. RSA 모듈러스는 부호 없는 큰 정수인데, Java `BigInteger.toByteArray()`는 최상위 비트가 1이면 **부호 바이트 `0x00`을 앞에 붙입니다.** 이 선행 0을 그대로 base64url 인코딩하면 Python의 인코딩 결과와 달라질 수 있습니다. 계약 명세는 다음을 못 박아야 합니다.

- `n`, `e`는 **부호 없는 빅엔디안 최소 길이** 바이트열로 인코딩한다(선행 `0x00` 제거, 단 값이 0이면 예외 규칙).
- base64url은 **패딩(`=`)을 붙이지 않는다** (JWS/JWK 관례).

## 9. base64url 패딩: 가장 흔한 조용한 실패

base64url 자체는 RFC 4648 표준이지만, **패딩 처리**가 언어·라이브러리마다 다릅니다.

| 상황 | Java | Python |
|---|---|---|
| 인코딩 시 패딩 | `Base64.getUrlEncoder().withoutPadding()` 필요 | `base64.urlsafe_b64encode`는 패딩 포함 → 제거 필요 |
| 디코딩 시 패딩 | `getUrlDecoder()`는 패딩 유무에 관대한 편 | `urlsafe_b64decode`는 길이가 4의 배수가 아니면 `Incorrect padding` → 보정 필요 |

JWS에서는 base64url이 단순 관례가 아니라 **trailing `=`을 제거하도록 정의**되어 있습니다(RFC 7515, base64url without padding). 디코딩 시 길이 처리는 정확히 다음과 같습니다.

- 길이 `mod 4 == 0`: 그대로 디코딩.
- 길이 `mod 4 == 2` 또는 `== 3`: `=` 패딩을 보정해 디코딩.
- 길이 `mod 4 == 1`: base64로 **표현 불가능한 잘못된 입력** → 거부해야 함.

즉 Python 디코더가 "패딩 필수"라고 절대적으로 말하는 것은 부정확합니다. 입력 길이에 따라 무패딩도 정상 동작하며, 문제는 오직 보정을 빠뜨렸을 때뿐입니다.

다만 길이만 보정하는 디코더는 **보안 입력에 충분히 엄격하지 않습니다.** Python의 `urlsafe_b64decode`는 (기본 `validate=False`에서) 알파벳 밖 문자를 조용히 버릴 수 있고, canonical pad bit도 검사하지 않습니다. 그래서 무패딩 `AA`와 `AB`가 **둘 다 `b"\x00"`으로 디코딩**되지만, `AB`는 canonical 인코딩이 아닙니다(다시 인코딩하면 `AA`가 됩니다). JWS/JWK용 디코더는 다음을 **모두** 검사해야 합니다. (1) ASCII이며 `[A-Za-z0-9_-]`만 허용, (2) `=` 금지, (3) `mod 4 == 1` 거부, (4) 엄격 디코딩, (5) 디코딩 결과를 다시 무패딩 base64url로 인코딩해 원문과 정확히 일치하는지 확인. 아래는 **개념 코드 (실행용 아님)** 입니다.

```python
# 개념 코드 (실행용 아님): JWS/JWK 용 엄격 base64url 디코더
import base64
import re

_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]*$")

def b64url_decode(s: str) -> bytes:
    # (1) ASCII + base64url 알파벳만, (2) '=' 금지
    if not isinstance(s, str) or not _B64URL_RE.match(s):
        raise ValueError("잘못된 base64url 문자(알파벳 외 문자 또는 '=' 포함)")
    r = len(s) % 4
    if r == 1:                                    # (3) 표현 불가능한 길이 거부
        raise ValueError("잘못된 base64url 입력 길이(mod 4 == 1)")
    pad = (-len(s)) % 4          # mod 4 == 2 → '==', == 3 → '=', == 0 → ''
    raw = base64.urlsafe_b64decode(s + "=" * pad)  # (4) 엄격 디코딩
    # (5) canonical 재인코딩 검사: 비정규 pad bit(예: 'AB')를 거부
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != s:
        raise ValueError("비정규 base64url(canonical 인코딩 아님)")
    return raw
```

길이 보정을 빠뜨리면 `Incorrect padding` 예외가 특정 입력에서만 간헐적으로 터지고, canonical 검사를 빠뜨리면 `AB` 같은 비정규 입력을 조용히 받아들입니다. 골든 벡터에 **패딩 경계 케이스(길이 mod 4 = 2, 3, 그리고 거부되어야 할 mod 4 = 1)와 비정규 인코딩 케이스(예: `AB` → 거부)** 를 반드시 넣어야 하는 이유입니다.

## 10. Golden Vector (골든 벡터): 정의와 목적

골든 벡터는 **고정 입력 → 기대 출력**을 언어 독립 픽스처(fixture)로 저장한 것입니다. 목적은 하나입니다. **"Java와 Python이 같은 입력에 대해 같은 바이트를 만드는지 대조한다."**

```text
golden vector = { 입력, 기대 정규 바이트, 기대 다이제스트, (선택) 기대 서명 }
```

골든 벡터의 성격은 두 가지로 나뉩니다.

| 종류 | 결정성 | 예 | 양쪽 대조 방식 |
|---|---|---|---|
| 결정적 출력 | 있음 | 정규 바이트, 다이제스트, 결정적 ID, **RS256 서명** | Java·Python 모두 값이 기대와 일치해야 함 |
| 비결정적 출력 | 없음(무작위 salt 등) | **PS256 서명** | 한쪽이 서명 → 다른 쪽이 검증 통과해야 함 |

여기서 알고리즘을 정확히 구분해야 합니다. **RS256(RSASSA-PKCS1-v1_5)은 결정적**입니다. 고정 키와 동일한 JWS Signing Input이면 서명 바이트도 항상 같습니다. 따라서 RS256은 **기대 서명 벡터 대조(결정적)와 교차 검증(발급↔검증) 둘 다** 적용할 수 있습니다. 반면 **PS256(RSASSA-PSS)은 무작위 salt 때문에 비결정적**이라 매번 서명이 달라지므로, 값 대조는 불가능하고 **교차 검증으로만** 다뤄야 합니다.

그래서 원칙은 이렇게 나눕니다. 결정적 알고리즘(RS256)은 기대 서명 벡터를 골든 벡터에 넣어 값까지 대조하고, 비결정적 알고리즘(PS256)으로 나중에 바꾸더라도 **교차 검증 테스트는 그대로 유효**하도록 설계해 둡니다. 즉 "서명은 무조건 교차 검증만"이 아니라 "알고리즘의 결정성에 맞춰 대조 방식을 고른다"가 정확한 원칙입니다.

## 11. 골든 벡터 픽스처 구조

픽스처는 언어 중립 형식(JSON)으로 저장하고, 두 언어의 테스트가 같은 파일을 읽습니다. 골든 벡터라면 자리표시자가 아니라 **실제 값**이어야 실행 가능한 픽스처가 됩니다. 아래는 자체 NFC 형식(4절)을 전제로 실제로 계산·검증한 값입니다.

```json
{
  "version": "canonical-json-v1",
  "cases": [
    {
      "id": "case-key-order",
      "input": { "b": 1, "a": 2 },
      "expected_canonical": "{\"a\":2,\"b\":1}",
      "expected_canonical_utf8_hex": "7b2261223a322c2262223a317d",
      "expected_sha256_hex": "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
    },
    {
      "id": "case-unicode-nfc",
      "input": { "name": "é" },
      "expected_canonical": "{\"name\":\"é\"}",
      "expected_canonical_utf8_hex": "7b226e616d65223a22c3a9227d",
      "expected_sha256_hex": "2f16b8477146a1b2ba7d6bb7cf7c9979c191cc2838a107dbf5f0d920b4cb3ba1"
    },
    {
      "id": "case-explicit-null",
      "input": { "a": 1, "b": null },
      "expected_canonical": "{\"a\":1,\"b\":null}",
      "expected_canonical_utf8_hex": "7b2261223a312c2262223a6e756c6c7d",
      "expected_sha256_hex": "46e0ff59f6164548317489fbea1133a48f7a83c325c3535e44559c9619afb76b"
    },
    {
      "id": "case-reject-duplicate-key",
      "input_utf8_hex": "7b2261223a312c2261223a327d",
      "expect": "reject",
      "reason": "R1: 원문 JSON 중복 키 (raw = {\"a\":1,\"a\":2})"
    }
  ]
}
```

몇 가지 짚을 점이 있습니다.

- `case-unicode-nfc`의 입력은 `"é"`(e + 결합 acute)이고, NFC 결과는 `"é"`(U+00E9)입니다. 앞선 초안에서 예로 들던 `"가" + 결합 acute`는 NFC를 적용해도 **`"각"`이 되지 않고** 그대로 결합 상태(`"가́"`)로 남습니다(U+AC00 뒤의 acute는 종성 기역이 아니므로). 그래서 정규화 효과를 정확히 보여주는 `e + acute → é` 사례로 교체했습니다.
- `case-explicit-null`은 명시적 `null`을 **삭제하지 않고 보존**합니다. 널 자동 생략은 서로 다른 입력을 같은 바이트로 합쳐 계약 정확성을 훼손하기 때문입니다(4절 "널 처리").
- `case-reject-duplicate-key`처럼 원문 JSON의 함정(중복 키 등)을 검증하려면, 파서가 이미 병합해 버린 객체가 아니라 **원문 바이트(`input_utf8_hex`) 또는 raw JSON 문자열**을 입력으로 두어야 합니다. 객체로 넣으면 중복 키가 파싱 단계에서 사라져 테스트 의미가 없어집니다.

여기서 **1차 대조 기준은 `expected_canonical_utf8_hex`(정확한 바이트열)**, 2차 보조 기준은 `expected_sha256_hex`입니다. "정규 바이트 계약"의 진짜 기준은 정확한 바이트열이고, 다이제스트는 그 바이트열을 간결하게 대조하기 위한 보조값입니다. `expected_canonical` 문자열은 사람이 눈으로 검토하기 위한 표기이며, 이스케이프 때문에 직접 비교보다는 UTF-8 hex와 다이제스트로 대조하는 편이 오탐을 줄입니다.

## 12. Java 측 계약 테스트

Java 테스트는 픽스처를 읽어 자신의 정규화 결과를 대조합니다.

```java
// 개념 코드 (실행용 아님)
@Test
void canonical_matches_golden() throws Exception {
    GoldenSet set = load("canonical-golden.json");
    for (GoldenCase c : set.cases()) {
        if (c.expectReject()) {                       // 거부 케이스
            byte[] raw = hexToBytes(c.inputUtf8Hex());
            assertThrows(IllegalArgumentException.class,
                () -> Canonicalizer.canonicalizeRaw(raw),
                () -> "should reject at case: " + c.id());
            continue;
        }
        byte[] canonical = Canonicalizer.canonicalize(c.input()); // bytes 반환
        // 1차: 정확한 바이트열 대조
        assertEquals(c.expectedCanonicalUtf8Hex(), toHex(canonical),
            () -> "byte mismatch at case: " + c.id());
        // 2차: 다이제스트 보조 대조
        assertEquals(c.expectedSha256Hex(), sha256Hex(canonical),
            () -> "digest mismatch at case: " + c.id());
    }
}
```

실패 메시지에 **케이스 ID**를 넣는 것이 중요합니다. `case-unicode-nfc`가 실패했다면 유니코드 정규화 규칙을, `case-key-order`가 실패했다면 정렬 규칙을 의심할 수 있습니다.

## 13. Python 측 계약 테스트

Python도 **같은 픽스처 파일**을 읽습니다. 두 언어가 다른 픽스처를 쓰면 계약 테스트의 의미가 사라집니다.

```python
# 개념 코드 (실행용 아님)
import hashlib, json, pytest

def test_canonical_matches_golden():
    with open("canonical-golden.json", encoding="utf-8") as f:
        golden = json.load(f)
    for case in golden["cases"]:
        if case.get("expect") == "reject":                # 거부 케이스
            raw = bytes.fromhex(case["input_utf8_hex"])
            with pytest.raises(ValueError):
                canonicalize_raw(raw)                     # 원문 바이트를 직접 파싱
            continue
        canonical = canonicalize(case["input"])           # bytes 반환
        # 1차: 정확한 바이트열 대조
        assert canonical.hex() == case["expected_canonical_utf8_hex"], (
            f"byte mismatch at case: {case['id']}"
        )
        # 2차: 다이제스트 보조 대조
        assert hashlib.sha256(canonical).hexdigest() == case["expected_sha256_hex"], (
            f"digest mismatch at case: {case['id']}"
        )
```

두 테스트가 같은 파일을 공유하므로, 어느 한쪽이라도 규격을 벗어나면 CI에서 즉시 드러납니다.

## 14. 교차 서명·검증 테스트

서명 계약은 (RS256처럼 결정적이면 값 대조도 하지만) 기본적으로 **역할 교차**로 검증합니다. Java가 서명한 토큰을 Python이 검증하고, 그 반대도 확인합니다.

```text
[Java 서명] ---- token.jwt ----> [Python 검증]  → PASS 기대
[Python 서명] --- token.jwt ---> [Java 검증]    → PASS 기대(테스트 전용 키)
[변조 토큰]  ---- token.jwt ----> [양쪽 검증]     → FAIL 기대(음성 케이스)
```

**중요:** 운영 구조가 "Java Gateway만 발급, Python은 검증만" 이라면, Python→Java 역방향 서명은 **테스트 전용 키로만** 수행하는 상호운용성 확인입니다. 즉 이 테스트가 Python에 운영 서명 권한이 있다는 뜻은 아니며, 테스트 키와 운영 키는 완전히 분리합니다. 역방향 발급이 실제 계약에 없다면 이 방향 테스트는 **선택 사항**으로 두어도 됩니다. 반대로 Python 검증기가 규격을 정확히 따르는지 확인하는 정방향(Java 서명 → Python 검증)과 음성 케이스는 필수입니다.

여기서 **음성 케이스(negative case)** 가 특히 중요합니다. 서명 1비트를 뒤집은 토큰, `kid`가 없는 토큰, `alg: none` 토큰, `exp`가 지난 토큰을 넣었을 때 **양쪽이 모두 거부**해야 합니다. 정상 케이스만 테스트하면 "둘 다 무엇이든 통과시키는" 상태를 놓칩니다.

| 음성 케이스 | 기대 결과 | 노리는 함정 |
|---|---|---|
| 서명 변조 | 양쪽 거부 | 서명 검증 자체 |
| `alg: none` | 양쪽 거부 | 알고리즘 혼동 공격 |
| `kid` 미매칭 | 양쪽 거부 | 키 선택 로직 |
| `exp` 만료 | 양쪽 거부 | 시간 검증 |
| `aud` 불일치 | 양쪽 거부 | 대상 검증 |

## 15. 시간 계약: 정밀도와 시간대의 함정

시간은 폴리글랏에서 가장 조용히 어긋나는 값입니다.

- **정밀도:** Java `Instant`는 나노초, Python `datetime`은 마이크로초까지 다룹니다. RFC 7519의 `NumericDate`는 **비정수(소수 초) 값도 표현할 수 있습니다.** 따라서 "RFC가 정수만 허용한다"는 것은 부정확하며, 정확히는 **본 계약이 상호운용성을 위해 `exp`/`nbf`/`iat`를 정수 초로 제한한다**입니다. 이렇게 못 박아야 두 언어의 소수 초 반올림 차이가 사라집니다.
- **시간대:** `exp`/`nbf`는 UTC 기준 epoch 초입니다. 로컬 시간대를 섞으면 경계에서 오판이 납니다.
- **경계 규칙:** `exp`는 **`now ≥ exp`이면 만료**(경계 포함 거부), `nbf`는 `now < nbf`이면 미유효입니다. "`exp` 이전이면 만료" 같은 모호한 표현은 경계 케이스에서 두 언어가 갈릴 수 있으므로 부등호로 못 박습니다.
- **클럭 스큐(clock skew):** 두 서비스의 시계 차이를 흡수하려면 허용 오차 `L`(예: 수 초)을 명시하고 적용식을 고정합니다. 예: `exp` 검증은 `now - L ≥ exp`이면 거부, `nbf` 검증은 `now + L < nbf`이면 거부. 다만 골든 벡터에서는 **시각을 고정 주입**하고 `L = 0`으로 두어 스큐를 배제하고 순수 규칙만 검증합니다.

```text
규칙: exp/nbf/iat 는 UTC epoch 초(정수)로만 표현한다 (본 계약의 제한).
경계: now >= exp 이면 만료 거부, now < nbf 이면 미유효 거부.
스큐: 허용오차 L 을 두면 (now - L) >= exp 거부, (now + L) < nbf 거부.

exp 경계 테스트 (exp = T 고정, L = 0, now 를 움직임):
        now = T-1  → 통과
        now = T    → 거부 (now >= exp)
        now = T+1  → 거부

nbf 경계 테스트 (nbf = T 고정, L = 0, now 를 움직임):
        now = T-1  → 거부 (now < nbf)
        now = T    → 통과
        now = T+1  → 통과
```

## 16. 결정적 식별자 (Deterministic ID)의 언어 간 동일성

멱등성(idempotency)과 재개 가능한 워크플로우를 위해서는 **같은 입력 → 같은 ID**가 언어와 무관하게 성립해야 합니다. 이 주제 자체는 [재개 가능한 AI 에이전트 워크플로우](https://aiarchitect.tistory.com/7) 글에서 다뤘고, 여기서는 **언어 간 동일성**에만 초점을 둡니다.

결정적 ID는 보통 `정규 바이트 → 해시 → 인코딩` 순으로 계산합니다. 따라서 결정적 ID 계약은 **정규 바이트 계약 위에 얹힌** 계약입니다. 여기에 계약 버전과 도메인 구분자(domain separator)를 접두로 넣어, 계약이 바뀌거나 용도가 다른 ID끼리 값이 우연히 겹치는 것을 막습니다.

```text
prefix = contract_version || "\x1f" || domain_tag   // 예: "id-v1" + 도메인 태그
digest = sha256( prefix_bytes || canonical_bytes(payload) )
deterministic_id = base64url_nopad( digest[:M바이트] )   // 해시를 먼저 M바이트로 자름
```

이 공식이 언어 간에 동일하려면 세 요소가 모두 일치해야 합니다.

| 요소 | 일치 조건 |
|---|---|
| `contract_version` + `domain_tag` | 접두 바이트를 두 언어가 동일하게 구성 |
| `canonical_bytes` | 정규 바이트 계약(3~6절) |
| `sha256` | 표준 해시라 문제없음 |
| 자르기 + `base64url_nopad` | **해시를 먼저 M바이트로 자른 뒤** 인코딩, 패딩 규칙 통일 |

자르기에서 흔히 오해하는 점이 있습니다. **SHA-256을 base64url로 인코딩한 결과는 ASCII뿐이므로, 인코딩 문자열을 `[:N]`으로 잘라도 멀티바이트 경계 문제는 생기지 않습니다.** 진짜 명시해야 할 것은 (1) **해시 원시 바이트를 먼저 M바이트로 자를지, 인코딩 결과 문자열을 N문자로 자를지**를 하나로 고정하는 것과, (2) 그 결과의 **충돌 강도(비트 수)** 및 저장소 고유 제약입니다. 예를 들어 해시를 8바이트(64비트)로 자르면 생일 역설상 약 `2^32`개 규모에서 충돌 가능성이 유의미해지므로, ID 규모에 맞춰 길이를 정하고 **DB 고유 제약(unique constraint)으로 충돌을 최종 방어**해야 합니다.

## 17. 요청 지문 (Request Fingerprint)의 계약

요청 지문은 감사·중복 탐지에 쓰는, 요청의 핵심 필드를 정규화해 해시한 값입니다. 요청 지문의 함정은 **"무엇을 지문에 포함할 것인가"** 를 두 언어가 다르게 해석하는 데 있습니다.

```text
fingerprint = sha256( canonical_bytes({
  contract_version, domain, method, path, tenant, actor, body_digest, ts_bucket
}) )
```

지문 계약이 명시해야 할 것들:

- **포함 필드 목록**을 고정한다(헤더 순서·대소문자 같은 불안정한 값은 제외).
- **계약 버전·도메인 구분자**를 필드에 포함해 버전이 바뀌거나 용도가 다른 지문끼리 값이 겹치지 않게 한다.
- 본문은 통째로 넣지 않고 `body_digest`로 넣는다(큰 본문·비결정 직렬화 회피).
- 시간은 원시 타임스탬프가 아니라 **버킷(bucket)** 으로 넣어 재생 창(window)을 정의한다.
- 필드 누락/널 처리는 정규 바이트 계약의 널 처리 규칙(4절)을 그대로 따른다.

두 언어가 같은 필드 집합을 같은 순서 규칙(정렬)으로 넣기만 하면, 지문은 자동으로 일치합니다. 즉 요청 지문 계약은 대부분 **정규 바이트 계약의 응용**입니다.

> **주의 — 지문만으로는 재생(replay)을 막지 못합니다.** 요청 지문은 재생을 *탐지*하기 위한 키일 뿐입니다. 실제 재생 방지는 (1) 이미 처리한 지문(또는 `jti`/nonce)을 **원자적으로 기록하고**, (2) **TTL(재생 창)** 동안 같은 값의 재사용을 거부하며, (3) 공격자가 지문 대상 필드를 임의로 바꾸지 못하도록 **서명·MAC 또는 인증된 요청 경계**로 보호할 때 성립합니다. 세 가지가 함께 있어야 "탐지 키"가 "방지 장치"가 됩니다.

## 18. 함정 목록: 언어별 기본값 대조표

지금까지 나온 함정을 한 표로 모읍니다. 계약 명세를 쓸 때 각 항목을 명시적으로 결정했는지 점검하는 체크리스트로 씁니다.

| # | 함정 | 미결정 시 증상 | 계약이 정해야 할 것 |
|---|---|---|---|
| 1 | JSON 키 순서 | 다이제스트 간헐 불일치 | 정렬 기준(코드 유닛) |
| 2 | 공백·구분자 | 다이제스트 상시 불일치 | `","`/`":"` 무공백 |
| 3 | 유니코드 정규화 | 결합 문자에서만 불일치 | NFC 강제 |
| 4 | 비ASCII 이스케이프 | `\uXXXX` vs 원문 | ensure_ascii=false |
| 5 | base64 패딩 | 특정 길이에서만 예외 | 패딩 없음 |
| 6 | 정수 부호 바이트 | RSA `n` 불일치 | 부호 없는 최소 길이 |
| 7 | 실수 표현 | 통화·좌표 불일치 | 실수 금지/문자열화 |
| 8 | 시간 정밀도 | 경계에서만 만료 오판 | 정수 초 |
| 9 | 시간대 | 상수 오프셋만큼 어긋남 | UTC epoch |
| 10 | 널 vs 생략 | 서로 다른 입력이 같은 바이트로 합쳐짐 | 널 처리 정책 통일(투영 단계에서 결정, 정규화기가 삭제 금지) |
| 11 | 자르기 기준 | ID 꼬리 불일치 | 해시 바이트 자르기 vs 인코딩 문자 자르기 중 하나로 고정 + 비트 강도 |
| 12 | 중복 키/NFC 충돌 | 조용한 덮어쓰기 | 원문 중복 키·NFC 정규화 충돌 거부 |
| 13 | 비정상 유니코드/타입 | 인코딩 예외·비표준 토큰 | lone surrogate·NaN·Infinity·실수·비문자열 키 거부 |

## 19. 계약 테스트 (Contract Test)를 CI 게이트로

계약 테스트는 "가끔 돌려보는 검증"이 아니라 **병합을 막는 게이트**여야 의미가 있습니다.

```text
파이프라인 게이트
1) 공유 픽스처 로드(Java·Python 동일 파일)
2) 정규 바이트 대조(다이제스트)
3) 교차 서명·검증(정상 + 음성 케이스)
4) 시간/식별자/지문 계약 대조
→ 하나라도 실패하면 병합 차단
```

실패했을 때 **어느 쪽이 규격 위반인지** 판정하는 원칙도 정해 둡니다.

- 픽스처의 기대값은 **명세로부터 독립 계산**한다(한 언어의 출력을 기대값으로 삼지 않는다).
- Java만 실패하면 Java 구현이, Python만 실패하면 Python 구현이 규격 위반이다.
- **둘 다 실패**하면 명세·픽스처가 어긋났을 가능성을 먼저 본다.

한쪽 언어의 출력을 그대로 기대값으로 굳히면 "그 언어가 곧 규격"이 되어 버려, 다른 쪽만 계속 맞추게 됩니다. 이는 계약이 아니라 종속입니다.

## 20. 계약 버전과 키 롤오버 운영

계약과 키는 **버전을 달고 살아 있는 자산**입니다.

**키 롤오버(key rollover):** JWKS는 여러 키를 동시에 담을 수 있으므로, 새 키를 먼저 배포하고(`kid`로 구분), 검증 측이 두 키를 모두 신뢰하는 기간을 둔 뒤, 서명 측이 새 키로 전환하고, 마지막에 옛 키를 제거합니다.

```text
1) 신규 kid=example-key-2 를 JWKS에 추가(검증 측 캐시 갱신 대기)
2) 검증 측: key-1, key-2 모두 신뢰(중첩 기간)
3) 서명 측: 신규 토큰을 key-2 로 서명 전환
4) 옛 키 제거는 다음을 모두 지난 뒤:
   (a) key-1 로 서명된 마지막 토큰의 최대 수명 경과
   (b) 클럭 스큐 허용 오차 L
   (c) 검증 측 JWKS 캐시 TTL
   → 즉 "옛 토큰 만료 후"만으로는 부족하다.
```

구키 제거 시점을 "옛 토큰 만료 후"로만 잡으면, 아직 만료되지 않은 토큰·스큐·오래된 JWKS 캐시 때문에 정상 토큰이 갑자기 거부될 수 있습니다. 그래서 **최대 토큰 수명 + 클럭 스큐 + JWKS 캐시 여유**를 모두 지난 뒤 제거해야 안전합니다.

**JWKS 캐시와 unknown `kid`:** 검증 측은 JWKS를 캐시하되 **TTL**을 두고, 캐시에 없는 `kid`를 만나면 **제한된 빈도로만**(예: 쿨다운·레이트 리밋을 둔) JWKS를 새로고침합니다. 그렇지 않으면 임의 `kid`를 담은 토큰이 무제한 새로고침(사실상 DoS)을 유발할 수 있습니다. 또한 새로고침 후에도 없는 `kid`는 거부하고, `iss`와 JWKS(검증 키)의 결합, `kty`/`use`/`alg`/`kid` 필터를 항상 함께 적용합니다.

**버전드 계약(versioned contract):** 정규 형식·지문 규칙이 바뀌면 `canonical-json-v1 → v2`처럼 버전을 올리고, 골든 벡터도 버전별로 병존시킵니다. 저장된 지문·ID가 과거 버전으로 계산되어 있을 수 있으므로, 마이그레이션 창 동안은 **두 버전을 함께 검증**할 수 있어야 합니다.

## 21. 인접 계약: AES-256-GCM 봉투 (Envelope)

같은 원칙은 대칭 암호에도 적용됩니다. 자격 증명 브로커(credential broker)가 **AES-256-GCM 봉투(envelope)** 로 비밀을 감쌀 때, Java와 Python은 다음을 동일하게 약속해야 복호가 됩니다.

| 요소 | 계약이 정할 것 |
|---|---|
| 논스(nonce) 길이 | 12바이트로 고정(계약상의 선택) |
| 태그(tag) 길이 | 128비트 |
| 추가 인증 데이터(AAD) | 포함 필드와 그 정규 바이트 |
| 봉투 직렬화 | nonce·ciphertext·tag의 배치·인코딩 |

논스 길이는 정확히 짚을 필요가 있습니다. **12바이트(96비트) IV는 NIST SP 800-38D의 권고값이고 좋은 기본값이지만, AES-GCM이 12바이트만 허용하는 것은 아닙니다.** 96비트 IV는 `IV || 0^31 || 1`로 128비트 pre-counter block `J0`를 바로 구성하고, 그 외 길이의 IV는 길이 정보를 포함해 GHASH한 128비트 결과를 `J0`로 사용합니다(즉 96비트로 유도되는 것이 아니라 128비트 `J0`로 변환됩니다, NIST SP 800-38D §7.1). 상호운용성과 성능을 위해 **계약에서 12바이트로 고정**하는 것입니다(사양상 강제가 아니라 우리 계약의 선택).

특히 **AAD**는 정규 바이트 계약을 그대로 재사용합니다. AAD의 바이트가 한쪽이라도 다르면 태그 검증이 실패하므로, AES-GCM 봉투 역시 골든 벡터(고정 키·고정 논스·고정 평문 → 기대 암호문·태그)로 교차 검증할 수 있습니다. 다만 운영에서 **동일 키 아래에서는 논스를 절대 재사용하지 않으며**(GCM에서 동일 키·동일 논스 재사용은 기밀성과 인증성을 함께 무너뜨립니다), 골든 벡터의 고정 논스는 오직 테스트 목적임을 명시합니다.

## 22. 무엇을 지금 하고, 무엇을 후속으로 둘 것인가

이 글의 범위는 **계약의 정확성 검증**입니다. 실제 운영 인프라는 별도 단계로 둡니다.

| 지금(설계·검증 단계) | 후속(인프라 연동) |
|---|---|
| 정규 바이트·토큰·지문 골든 벡터 | 실제 Keycloak Token Exchange 연동 |
| 내부 RS256 발급·검증 계약 | KMS 기반 키 보관·서명 |
| AES-256-GCM 봉투 계약 검증 | 서비스 간 mTLS |
| 계약 테스트 CI 게이트 | 키 자동 롤오버 파이프라인 |

골든 벡터로 **선택된 계약 사례에 대해** 두 언어의 결과가 일치함을 먼저 굳혀 두면, 핵심 변환 계약(정규 바이트·토큰·지문)의 언어 간 불일치 위험을 크게 줄일 수 있습니다. 다만 KMS·mTLS·JWKS 캐시·권한 설정 같은 인프라는 **각각 별도의 보안 정확성과 운영 위험을 추가**하므로, "남은 것은 배포뿐"이라고 볼 수는 없습니다. 정확한 표현은 **"핵심 변환 계약의 불일치 위험을 회귀 방지 수준으로 낮춰 둔 출발선"** 입니다.

## 23. 정리

폴리글랏 보안의 핵심은 "언어를 통일하라"가 아닙니다. **표현을 계약으로 못 박고, 그 계약이 선택된 사례에서 언어 간에 일치함을 골든 벡터로 검증하라**입니다. 유한한 벡터는 전체 정확성의 수학적 증명이 아니라 **강한 회귀 방지 증거**이며, 그렇게 이해할 때 오히려 계약을 계속 넓혀 갈 동기가 생깁니다.

- 서명·해시 대상은 유효한 JSON이 아니라 **재현 가능한 정규 바이트**여야 한다.
- 토큰·정규 바이트·파생 식별자는 **계약별로** 골든 벡터를 관리한다.
- 정상 케이스뿐 아니라 **음성 케이스·거부 케이스**로 "무엇이든 통과"를 막는다.
- 기대값은 한 언어가 아니라 **명세로부터 독립 계산**한다.
- 계약 테스트는 **CI 게이트**로, 키·계약은 **버전과 롤오버**로 운영한다.

책임 분리가 두 서비스를 나누는 설계라면, 계약 검증은 나눠진 두 서비스가 **선택된 사례에서 같은 결과를 계산함을 회귀 수준으로 보장**하는 장치입니다. 폴리글랏은 그 보장이 쌓일수록 위험이 아니라 자산이 됩니다.

## 참고 표준 (References)

- RFC 7515 — JSON Web Signature (JWS): https://www.rfc-editor.org/info/rfc7515
- RFC 7517 — JSON Web Key (JWK / JWKS): https://www.rfc-editor.org/info/rfc7517
- RFC 7518 — JSON Web Algorithms (JWA, RS256 포함): https://www.rfc-editor.org/info/rfc7518
- RFC 7519 — JSON Web Token (JWT): https://www.rfc-editor.org/info/rfc7519
- RFC 8725 — JSON Web Token Best Current Practices: https://www.rfc-editor.org/info/rfc8725
- RFC 4648 — The Base16, Base32, and Base64 Data Encodings (base64url): https://www.rfc-editor.org/info/rfc4648
- RFC 8785 — JSON Canonicalization Scheme (JCS): https://www.rfc-editor.org/info/rfc8785
- Unicode Normalization Forms (UAX #15): https://www.unicode.org/reports/tr15/
- NIST SP 800-38D — Recommendation for GCM: https://csrc.nist.gov/pubs/sp/800/38/d/final
