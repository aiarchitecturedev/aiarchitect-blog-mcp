# 프라이빗 API를 연결하는 Java Server SDK 설계: 모듈·Client 수명·전송 계층

고객사 서버에서 프라이빗 API를 호출하는 코드를 프로젝트마다 새로 작성하면 인증 갱신과 재시도, 오류 해석이 조금씩 달라집니다. Java Server SDK가 정해야 할 것은 편의 메서드 목록이 아니라 무엇을 보장하고 무엇을 바꾸지 않을지에 대한 약속입니다. 이 글은 Java Server SDK 설계에 필요한 모듈 경계, 장수명 Client, 동기·비동기 API, 인증·재시도·오류·관측성 원칙을 정리합니다.

![고객사 서버와 Private API 사이에서 안정적인 공개 API·정책 Core·전송 계층을 제공하고 장수명 연결과 재시도·관측 증거를 관리하는 Java Server SDK 아키텍처 이미지](assets/blog-41-java-server-sdk-private-api-hero.png)

> **목차**
>
> 1. [Server SDK는 HTTP Wrapper가 아니라 제품 경계다](#ai-section-1)
> 2. [먼저 목표와 비목표를 고정한다](#ai-section-2)
> 3. [모듈은 기능 수가 아니라 변경 이유로 나눈다](#ai-section-3)
> 4. [생성 코드를 공개 API로 바로 노출하지 않는다](#ai-section-4)
> 5. [Client 수명과 자원 소유권을 함께 설계한다](#ai-section-5)
> 6. [동기 API와 비동기 API의 의미를 먼저 정의한다](#ai-section-6)
> 7. [전송 계층은 성공·실패의 원재료만 반환한다](#ai-section-7)
> 8. [인증 자격 증명과 요청 문맥을 분리한다](#ai-section-8)
> 9. [Timeout은 하나의 숫자가 아니라 예산이다](#ai-section-9)
> 10. [Retry는 HTTP Method가 아니라 작업 의미로 결정한다](#ai-section-10)
> 11. [오류는 안정적인 Java 예외 계층으로 변환한다](#ai-section-11)
> 12. [관측성은 논리 호출과 실제 전송 시도를 구분한다](#ai-section-12)
> 13. [테스트는 실제 HTTP가 없어도 대부분 가능해야 한다](#ai-section-13)
> 14. [Thread Safety는 선언이 아니라 상태 배치로 만든다](#ai-section-14)
> 15. [공개 API와 패키징에 호환성 예산을 둔다](#ai-section-15)
> 16. [구현 체크리스트](#ai-section-16)
> 17. [마무리와 참고 자료](#ai-section-17)

앞선 글에서는 고객사가 Android·iOS 앱과 React 웹을 원하는 형태로 구현하면서도, 프라이빗 망의 API 서버를 직접 노출하지 않는 멀티플랫폼 SDK 구조를 살펴봤습니다.

이 구조에서 Java Server SDK는 단순한 HTTP 호출 편의 라이브러리가 아닙니다. 고객사 서버가 프라이빗 API를 사용할 때 필요한 인증, 테넌트 문맥, 오류 변환, 재시도, 멱등성, 타임아웃과 관측 정책을 한곳에서 적용하는 **신뢰 경계의 실행 구성요소**입니다.

![Mobile·Web 채널은 고객사 공개 API까지만 접근하고 고객사 서버 내부의 Java Server SDK가 허용된 서버 간 연결을 통해 Private API를 호출하는 신뢰 경계](assets/blog-41-private-api-trust-path.png)

구체적인 네트워크 기술은 배포 환경마다 달라질 수 있습니다. 중요한 원칙은 모바일 앱과 브라우저가 프라이빗 Endpoint나 서버 자격 증명을 직접 갖지 않고, 고객사 서버 안의 Java SDK가 통제된 경로를 통해 호출한다는 점입니다.

이 글은 이 역할을 수행하는 Java Server SDK의 공개 API, 모듈 구조, Client 수명, 동기·비동기 실행, 전송 계층과 테스트 경계를 정리합니다. 코드·식별자·구체값은 **공개 가능한 합성 예시**입니다. 다만 본문에서 **"필자"라고 밝힌 단락은 실제 유지보수 경험**에서 회사·제품·저장소·환경·호스트·Endpoint 경로와 실제 API 수처럼 운영 규모를 드러내는 정보를 제거해 재구성한 것입니다. 특정 고객사·회사·비공개 제품·내부 URL·실제 자격 증명은 포함하지 않습니다.

<h2 id="ai-section-1" style="scroll-margin-top: 72px;">1. Server SDK는 HTTP Wrapper가 아니라 제품 경계다</h2>

HTTP Wrapper는 대개 다음 정도의 역할을 합니다.

```java
String body = http.post("/v1/sessions", json);
```

하지만 운영 환경의 Server SDK에는 훨씬 많은 결정이 들어갑니다.

- 어떤 자격 증명을 어느 요청에 적용할 것인가
- 고객·테넌트·사용자 문맥을 어떻게 전달할 것인가
- 어떤 요청을 자동 재시도할 수 있는가
- 생성 요청의 중복 부작용을 어떻게 막을 것인가
- HTTP 오류를 어떤 안정적인 Java 예외로 변환할 것인가
- 연결 풀과 실행 스레드는 누가 만들고 종료할 것인가
- 요청 제한시간과 전체 재시도 예산을 어떻게 계산할 것인가
- 고객 지원에 필요한 Request ID와 Trace를 어디까지 노출할 것인가

애플리케이션마다 이 결정을 다시 구현하면 같은 API를 사용해도 인증·재시도·오류 처리 방식이 달라집니다. SDK의 목적은 HTTP 문법을 숨기는 데 그치지 않고, **제품을 안전하게 사용하는 실행 규칙을 재사용 가능한 계약으로 고정하는 것**입니다.

<h2 id="ai-section-2" style="scroll-margin-top: 72px;">2. 먼저 목표와 비목표를 고정한다</h2>

SDK가 모든 문제를 해결하려 하면 고객사 애플리케이션의 프레임워크와 업무 로직까지 침범하게 됩니다. 시작할 때 목표와 비목표를 함께 적는 편이 좋습니다.

| 목표 | 비목표 |
|---|---|
| 안정적인 Java 공개 API | 고객사의 Controller·UI 제공 |
| 프라이빗 API 전송 세부사항 캡슐화 | 고객사의 로그인 정책 결정 |
| 인증·오류·재시도·관측 정책 통일 | 네트워크 연결 자체를 자동 개통 |
| Thread-safe 장수명 Client | 호출마다 새 Client 생성 |
| 테스트 가능한 전송 추상화 | 내부 HTTP 라이브러리 타입 공개 |
| 버전 호환성 관리 | 서버 API와 SDK 버전을 하나로 강제 |

특히 Server SDK를 사용한다고 해서 프라이빗 망 연결이 자동으로 생기는 것은 아닙니다. 방화벽, DNS, 인증서, Private Link, VPN 또는 Gateway 같은 인프라 연결은 별도 배포 책임입니다. SDK는 **허용된 경로가 존재한다는 전제에서 애플리케이션 수준의 안전한 호출**을 담당합니다.

<h2 id="ai-section-3" style="scroll-margin-top: 72px;">3. 모듈은 기능 수가 아니라 변경 이유로 나눈다</h2>

하나의 `sdk.jar`에 공개 모델, HTTP DTO, 인증, JSON Mapper, Retry 구현과 Spring 설정을 모두 넣으면 작은 변경도 전체 패키지에 영향을 줍니다. 권장하는 시작 구조는 다음과 같습니다.

![sdk-core를 중심으로 공개 API·관측 SPI·HTTP 전송·테스트 Fixture·Spring Boot 조립 모듈의 컴파일 및 런타임 의존 방향을 분리한 Java Server SDK 모듈 구조](assets/blog-41-sdk-module-boundaries.png)

화살표는 호출 흐름이 아니라 **컴파일·런타임 의존 방향**을 뜻합니다. `sdk-api`는 구현 모듈을 알지 않고, Core와 전송 구현을 조립하는 책임은 Starter 같은 최외곽 모듈에 둡니다.

### 3.1 `sdk-api`

고객 애플리케이션이 컴파일 시점에 직접 의존하는 표면입니다.

- `SdkClient`
- 업무 단위 Service Interface
- 요청·응답 공개 Model
- `RequestContext`
- 안정적인 예외 계층
- Builder와 설정 타입

이 모듈에는 특정 JSON 라이브러리의 Annotation, 생성된 OpenAPI DTO, JDK HTTP 구현 타입을 가능한 한 노출하지 않습니다.

### 3.2 `sdk-core`

제품 의미와 실행 정책을 구현합니다.

- 공개 요청을 내부 Command로 변환
- 인증과 테넌트 문맥 적용
- 타임아웃 예산 계산
- 재시도·멱등성 판단
- 전송 응답을 공개 Model과 예외로 변환
- 진단 이벤트 발행

### 3.3 `sdk-transport-http`

교체 가능성이 높은 전송 세부사항을 격리합니다.

- HTTP Request 생성
- Header·Body 직렬화
- OpenAPI 생성 DTO
- Status·Header·Body 수신
- 네트워크 예외 표준화

### 3.4 `sdk-observability-spi`

SDK가 특정 관측 Backend를 강제하지 않도록 작은 SPI를 둡니다. 고객 애플리케이션은 No-op, Micrometer, OpenTelemetry 등 자신의 운영 환경에 맞는 Adapter를 연결할 수 있습니다.

### 3.5 `sdk-testing`

SDK 사용자가 자신의 통합 코드를 실제 프라이빗 API 없이 테스트할 수 있도록 Fake Client, Fixture와 Contract Stub을 제공합니다. 테스트 도구를 운영 Runtime 의존성에 섞지 않는 것이 중요합니다.

<h2 id="ai-section-4" style="scroll-margin-top: 72px;">4. 생성 코드를 공개 API로 바로 노출하지 않는다</h2>

OpenAPI는 언어 독립적인 HTTP API 인터페이스를 정의하고, 사람과 프로그램이 소스 코드나 네트워크 분석 없이 서비스 기능을 이해하도록 돕습니다. 따라서 전송 코드 생성과 계약 검증의 좋은 입력이 됩니다.

그러나 생성된 Client와 DTO를 그대로 SDK 공개 API로 노출하면 다음 문제가 생깁니다.

- 생성기 버전이 바뀌면 메서드와 타입 이름이 흔들릴 수 있음
- `nullable`, 날짜, Enum 표현이 생성기 정책에 종속됨
- 내부 Endpoint 구조가 고객 코드에 고정됨
- HTTP API 변경이 Java 공개 API 변경으로 바로 전파됨
- 생성 코드의 Annotation과 Runtime 의존성이 외부로 유출됨

권장 구조는 생성 코드를 내부 전송 계층에 두고 안정적인 공개 API로 감싸는 것입니다.

![Customer Application이 안정적인 Java 공개 API와 Core Policy를 거쳐 내부 Generated Transport로 Private API를 호출해 생성 코드 변경이 고객 코드로 전파되지 않는 계층 구조](assets/blog-41-stable-api-transport-separation.png)

```java
public interface SessionService {
    Session create(
            CreateSessionRequest request,
            RequestContext context
    );
}
```

공개 `CreateSessionRequest`는 업무 의미가 안정적인 타입이고, 전송 계층의 `CreateSessionRequestDto`와는 Mapper로 분리합니다. 필드가 우연히 같더라도 두 타입의 변경 이유는 다릅니다.

<h2 id="ai-section-5" style="scroll-margin-top: 72px;">5. Client 수명과 자원 소유권을 함께 설계한다</h2>

JDK 21의 `java.net.http.HttpClient` 공식 문서는 한 번 생성된 Client가 불변이며 여러 요청에 사용할 수 있고, 자체 연결 풀을 관리해 연결을 재사용한다고 설명합니다. 요청마다 Client를 만들면 이러한 연결 재사용을 방해할 수 있습니다.

Server SDK도 같은 원칙을 공개 계약으로 명시합니다.

- `SdkClient`는 Thread-safe다.
- 설정은 생성 후 불변이다.
- 애플리케이션 또는 DI Container가 장수명으로 보관한다.
- 요청마다 생성하지 않는다.
- SDK가 소유한 자원은 `close()`에서 정리한다.

```java
SdkClient client = SdkClient.builder()
        .endpoint(URI.create("https://api.example.com"))
        .credentialProvider(credentialProvider)
        .connectTimeout(Duration.ofSeconds(3))
        .requestTimeout(Duration.ofSeconds(15))
        .build();

Session session = client.sessions().create(
        new CreateSessionRequest("user-example"),
        RequestContext.builder()
                .tenantId("tenant-example")
                .requestId(UUID.randomUUID().toString())
                .build()
);
```

여기서 `SdkClient`와 `SessionService`는 호출할 때마다 내부 상태를 바꾸지 않습니다. 요청별 값은 `RequestContext`와 요청 객체에 담습니다.

<h3 data-ke-size="size23">5.1 자원 소유권을 생성 방식으로 구분한다</h3>

Client 수명에서 가장 자주 놓치는 부분은 “누가 만들었고 누가 닫는가”입니다.

![SdkClient Builder가 SDK 소유 자원과 호출자 주입 자원을 구분해 장수명 Thread-safe Client를 만들고 close 시 SDK 소유 자원만 종료하는 수명 주기](assets/blog-41-client-resource-ownership.png)

권장 규칙은 단순합니다.

| 자원 | 생성자 | 종료 책임 |
|---|---|---|
| SDK가 생성한 종료 가능한 HTTP Client·Executor·Scheduler | SDK | SDK |
| 호출자가 주입한 HTTP Client·Executor·Telemetry | 호출자 | 호출자 |
| 요청별 InputStream | 계약에 명시 | 계약에 명시 |

```java
try (SdkClient client = SdkClient.builder()
        .endpoint(endpoint)
        .credentialProvider(credentials)
        .build()) {
    client.sessions().get("session-example", RequestContext.system());
}
```

짧은 CLI나 Batch에서는 `try-with-resources`가 자연스럽습니다. 반면 Spring Boot 같은 서버 애플리케이션에서는 Client를 Singleton Bean으로 만들고 Application Context 종료 시 한 번 닫습니다. 이 통합은 다음 글에서 다룹니다.

Java 버전에 따른 차이도 숨기지 않아야 합니다. Java 21의 JDK `HttpClient`는 `AutoCloseable`과 `close()`·`shutdown()`을 제공하지만, Java 17 API에는 명시적인 Client 종료 메서드가 없습니다. Java 17을 지원한다면 `SdkClient.close()`는 SDK가 실제로 소유한 종료 가능 자원, 예를 들어 Executor·Scheduler와 사용 중인 전송 구현의 자원만 닫아야 하며 런타임별 동작을 호환성 문서에 명시해야 합니다.

`close()`의 의미도 문서화해야 합니다.

- 신규 요청을 거부하는가
- 진행 중 요청을 기다리는가, 취소하는가
- 최대 종료 대기시간은 얼마인가
- 여러 번 호출해도 안전한가
- 종료 후 Service 객체를 호출하면 어떤 예외가 발생하는가


<h3 data-ke-size="size23">5.2 인수한 SDK에서는 가변 범위를 열거하는 일이 먼저다</h3>

위 목록은 "설정은 생성 후 불변"을 공개 계약으로 권합니다. 기본 원칙으로는 이것이 맞습니다. 다만 운영 중 전환이 명시적인 요구사항이면 **가변 범위를 좁혀 예외를 두는** 설계도 성립합니다.

필자는 다른 사람이 만든 Java Server SDK를 인수해 유지보수 가이드를 쓴 일이 있습니다. 그 SDK는 일부 설정을 런타임에 교체할 수 있게 되어 있었습니다. 그때 필자가 한 일은 구현을 불변으로 되돌리는 것이 아니라 **어디까지가 계약인지 문서로 확정하는 것**이었습니다. 가이드에는 구현이 허용하는 가변 범위와 반영 시점을 기록했고, 여기에 호출자 주입 경로의 검증 조건까지 구현과 대조하면 다음 세 가지 경계로 정리됩니다.

- 교체 가능한 것은 **대상 주소와 두 제한시간뿐**입니다. 요청 헤더 전달 목록은 생성자에서 캡처되므로 시작 이후에는 바꿀 수 없습니다. 같은 "설정"이라는 말 안에 성질이 다른 두 묶음이 있었습니다.
- 의도한 반영 경계는 **교체가 끝난 뒤 설정 한 벌을 읽기 시작한 요청**입니다. 이 보장은 요청이 설정 스냅샷을 **한 번만 읽을 때** 성립합니다. 이미 전송 객체를 고른 요청은 이전 설정을 계속 쓰므로 **0초 절체 보장이 아니고**, 값별 접근자를 따로 읽는 구현이라면 한 요청 안에서 서로 다른 세대가 섞일 수도 있습니다. 이 읽기 조건은 [14.1](#ai-section-14)에서 따로 다룹니다.
- 기본 자동 설정 경로에서 대상 주소가 비어 있으면 애플리케이션이 아예 뜨지 않습니다. 의도된 fail-fast입니다. 다만 호출자가 자기 Provider를 주입하면 이 검사를 지나지 않으므로, 그 경로에서는 **교체 시점에도 같은 검증을 걸어야** "설정은 항상 유효하다"가 성립합니다.

📌 인수한 코드에서 원칙 위반을 발견하면 되돌리는 쪽이 먼저 떠오릅니다. 그러나 이미 소비자가 쓰고 있는 기능이면 **가변 항목을 열거하고 각 항목의 반영 시점을 적는 것**이 순서상 먼저입니다. 이것을 적지 않으면 교체 기능은 읽는 사람에게 **무중단 절체 보장**으로 읽히고, 그 오해는 문서가 아니라 장애로 드러납니다.

<h2 id="ai-section-6" style="scroll-margin-top: 72px;">6. 동기 API와 비동기 API의 의미를 먼저 정의한다</h2>

JDK `HttpClient`는 Blocking `send`와 `CompletableFuture`를 반환하는 `sendAsync`를 모두 제공합니다. SDK도 두 방식을 제공할 수 있지만, 단순히 반환 타입만 바꾸면 부족합니다.

### 6.1 동기 API

```java
Session session = client.sessions()
        .create(request, context);
```

다음 내용을 문서화합니다.

- 호출 Thread를 Blocking하는가
- Interrupt를 어떻게 처리하는가
- 시간 초과 시 어떤 예외를 던지는가
- 응답 Body를 반환 전에 모두 소비하는가
- 재시도까지 포함한 최대 Blocking 시간은 얼마인가

### 6.2 비동기 API

```java
CompletableFuture<Session> future = client.sessionsAsync()
        .create(request, context);

future.whenComplete((session, error) -> {
    if (error != null) {
        handleFailure(error);
        return;
    }
    handleSuccess(session);
});
```

비동기 계약에는 다음이 추가됩니다.

- Completion Callback이 실행되는 Executor
- `CompletableFuture.cancel()`이 전송 취소로 이어지는지 여부
- SDK 종료 시 미완료 Future의 처리
- 재시도 중 취소가 들어오면 다음 시도를 중단하는지 여부
- 전송 예외가 `CompletionException` 안에서 어떻게 노출되는지

취소를 공개 계약으로 제공하려면 위 예시처럼 `CompletableFuture`를 반환하거나 별도의 `SdkCall`·`CancellationHandle`을 제공해야 합니다. `CompletionStage`만 노출하면 호출자가 `cancel()`을 호출할 수 없으므로 취소 가능 여부를 API와 문서가 일치하도록 설계합니다.

동기 메서드를 `ForkJoinPool.commonPool()`에 넣어 비동기처럼 보이게 만드는 방식은 피합니다. Blocking I/O가 공용 Pool을 점유하고, 호출자가 실행 자원을 통제하기 어렵기 때문입니다. 실제 비동기 전송을 사용하거나 전용 Executor의 소유권을 명확히 해야 합니다.

<h2 id="ai-section-7" style="scroll-margin-top: 72px;">7. 전송 계층은 성공·실패의 원재료만 반환한다</h2>

전송 계층이 업무 예외까지 결정하면 HTTP 구현을 교체하기 어려워집니다. Transport는 다음과 같은 중립적인 결과를 반환할 수 있습니다.

```java
interface Transport {
    CompletionStage<TransportResponse> execute(
            TransportRequest request,
            CancellationToken cancellation
    );
}

record TransportResponse(
        int statusCode,
        Map<String, List<String>> headers,
        byte[] body
) {}
```

이 예시는 크기가 제한된 작은 JSON 응답을 전제로 합니다. 대용량 응답·파일·Streaming API에는 최대 크기, 소비·취소 방법과 종료 책임을 포함한 별도의 Streaming Body 추상화를 사용하고, 제한 없는 응답을 `byte[]`에 모두 적재하지 않습니다.

Core가 `TransportResponse`를 해석해 다음 단계로 변환합니다.

![Public Request에 요청 문맥과 자격 증명을 적용하고 Deadline·Retry·멱등 정책 안에서 Transport를 실행한 뒤 Response Mapping이 Public Model 또는 안정적인 SDK Exception으로 분기하는 실행 계약](assets/blog-41-operation-execution-contract.png)

전송 라이브러리의 예외를 그대로 외부로 던지지 않습니다. 내부 구현을 JDK HttpClient에서 다른 구현으로 교체해도 고객 애플리케이션의 `catch` 문이 깨지지 않아야 합니다.

<h2 id="ai-section-8" style="scroll-margin-top: 72px;">8. 인증 자격 증명과 요청 문맥을 분리한다</h2>

서비스 자격 증명과 업무 요청 문맥은 수명이 다릅니다.

```java
public interface CredentialProvider {
    CompletionStage<AccessCredential> resolveAsync(
            CredentialContext context
    );
    void invalidate(AccessCredential credential);
}
```

```java
public record RequestContext(
        String tenantId,
        String userId,
        String requestId,
        String traceParent
) {}
```

`CredentialProvider`는 장수명 Client 설정에 속하고, `RequestContext`는 요청마다 달라집니다. 비동기 호출 경로는 `resolveAsync()`를 조합해 자격 증명 갱신 중에도 호출 Thread를 숨겨서 Blocking하지 않습니다. 동기 Facade는 작업 전체 Deadline 안에서 같은 비동기 결과를 기다리며, 동시 Token Refresh는 Single Flight로 합칩니다.

| 구분 | 예 | 로그 원칙 |
|---|---|---|
| 서비스 자격 증명 | Access Token, mTLS Identity | 원문 금지 |
| 고객·테넌트 문맥 | Tenant ID | 정책에 따라 가명화 |
| 최종 사용자 문맥 | User ID | 최소 수집·Masking |
| 상관관계 정보 | Request ID, Trace Context | 진단용 허용 |

Mobile·Front SDK가 서버용 Secret을 갖지 않도록 하는 것만큼, Java SDK가 Secret을 설정 파일 예제나 예외 메시지에 흘리지 않는 것도 중요합니다.

<h2 id="ai-section-9" style="scroll-margin-top: 72px;">9. Timeout은 하나의 숫자가 아니라 예산이다</h2>

운영 Client에는 최소 세 종류의 시간이 있습니다.

```text
Connect Timeout       연결 수립 제한
Attempt Timeout       한 번의 전송 제한
Operation Deadline    재시도를 포함한 전체 업무 제한
```

예를 들어 전체 Deadline이 10초인데 각 시도 Timeout이 8초이고 최대 3회 재시도라면 설정은 서로 모순입니다. Retry는 남은 전체 예산 안에서만 실행되어야 합니다.

```java
Duration remaining = deadline.remaining();
if (remaining.compareTo(minimumAttemptBudget) < 0) {
    throw new SdkTimeoutException(
            "Operation deadline exhausted",
            "OPERATION_DEADLINE_EXCEEDED"
    );
}
```

권장 우선순위는 다음과 같습니다.

1. 호출자가 요청별 Deadline을 지정
2. 없으면 Client의 기본 Operation Timeout 사용
3. 각 Attempt는 남은 예산보다 길 수 없음
4. Backoff도 전체 예산에서 차감
5. Deadline이 끝나면 추가 재시도 금지

<h2 id="ai-section-10" style="scroll-margin-top: 72px;">10. Retry는 HTTP Method가 아니라 작업 의미로 결정한다</h2>

RFC 9110은 같은 요청을 여러 번 보내도 의도된 서버 효과가 한 번과 같은 메서드를 멱등하다고 정의합니다. 또한 비멱등 메서드는 실제 의미가 멱등하다고 알 수 있거나 원 요청이 적용되지 않았음을 감지할 수 있을 때가 아니면 자동 재시도하지 말 것을 권고합니다.

따라서 SDK는 `GET이면 재시도, POST면 금지` 같은 단순 규칙보다 작업 Metadata를 사용해야 합니다.

```java
record OperationPolicy(
        boolean idempotent,
        boolean idempotencyKeyRequired,
        int maxAttempts,
        Set<Integer> retryableStatuses
) {}
```

```text
getSession:
  idempotent = true
  maxAttempts = 3

createSession:
  idempotent = true only with Idempotency-Key
  maxAttempts = 3

approveAction:
  idempotent = false
  maxAttempts = 1
```

재시도 소유자도 하나로 정합니다. 고객 Gateway, Java SDK와 Private API가 모두 같은 요청을 자동 재시도하면 호출이 곱셈으로 늘어날 수 있습니다.

<h2 id="ai-section-11" style="scroll-margin-top: 72px;">11. 오류는 안정적인 Java 예외 계층으로 변환한다</h2>

RFC 9457 Problem Details는 HTTP 오류 응답에 기계 판독 가능한 정보를 담기 위한 형식을 정의합니다. SDK는 `type`, `status`, `title`, `detail`, `instance`와 확장 `code`를 읽어 안정적인 예외로 변환할 수 있습니다.

```java
public abstract class SdkException extends RuntimeException {
    private final String code;
    private final boolean retryable;
    private final String requestId;

    protected SdkException(
            String message,
            String code,
            boolean retryable,
            String requestId,
            Throwable cause
    ) {
        super(message, cause);
        this.code = code;
        this.retryable = retryable;
        this.requestId = requestId;
    }

    public String code() {
        return code;
    }

    public boolean retryable() {
        return retryable;
    }

    public String requestId() {
        return requestId;
    }
}
```

| 오류 | 예외 | 자동 재시도 |
|---|---|---|
| 설정 오류 | `SdkConfigurationException` | 금지 |
| 인증 실패 | `SdkAuthenticationException` | 갱신 정책에 따라 |
| 권한 부족 | `SdkAuthorizationException` | 금지 |
| 입력 검증 | `SdkValidationException` | 금지 |
| 상태 충돌 | `SdkConflictException` | 업무 정책에 따라 |
| Rate Limit | `SdkRateLimitException` | `Retry-After`에 따라 |
| 네트워크 | `SdkNetworkException` | 멱등 작업만 |
| 서버 일시 오류 | `SdkServerException` | 제한적 허용 |
| 응답 계약 위반 | `SdkProtocolException` | 금지·즉시 관측 |
| 호출자 취소 | `SdkCancelledException` | 금지 |

사람용 `detail` 문구를 분기 조건으로 사용하지 않고 안정적인 `code`와 타입을 사용합니다.


<h3 data-ke-size="size23">11.1 업무 의미를 해석하지 않기로 범위를 좁힌 SDK</h3>

위 표는 SDK가 **오류 분류까지 맡는 경우**의 권장 계층입니다. 필자가 인수해 단일 책임을 문서로 고정한 어느 Java Server SDK는 그 분류를 의도적으로 맡지 않은 경우였습니다. 그 SDK의 책임을 "고객사 프로세스와 내부 API 사이를 지나가는 얇은 통과 계층"으로 적었습니다. 통과 계층이 상태 코드를 업무 의미로 바꾸기 시작하면 그 해석 자체가 소비자와의 계약이 되기 때문입니다.

그래서 그 SDK에는 위 표 같은 예외 계층이 없습니다. 응답 오류를 단일 예외 하나로 감싸면서 **상태 코드와 응답 본문 문자열을 함께 보존**하고, 예외 메시지에는 상태 코드만 넣습니다.

ℹ️ 아래 코드는 그 책임 경계를 공개용으로 재구성한 것이며, 실제 구현을 그대로 옮긴 것이 아닙니다. 특히 **하위 예외의 메시지가 cause 체인으로 노출되지 않도록 보안 측면을 보강한** 권장 형태입니다.

```java
public class SdkUpstreamResponseException extends RuntimeException {

    private final int statusCode;
    private final String responseBody;

    // cause 를 받지 않는다. 아래 설명 참고.
    public SdkUpstreamResponseException(int statusCode, String responseBody) {
        super("Upstream responded with " + statusCode);
        this.statusCode = statusCode;
        this.responseBody = responseBody;
    }

    public int statusCode() {
        return statusCode;
    }

    /** 해석하지 않은 응답 본문 문자열. 분류는 호출자 몫이다. */
    public String responseBody() {
        return responseBody;
    }
}
```

메시지에 본문을 넣지 않은 것은 **예외 메시지가 가장 넓게 퍼지는 문자열**이기 때문입니다. Log, 모니터링 알림, 상위 프레임워크의 기본 오류 화면이 메시지를 그대로 옮깁니다. 본문이 필요한 호출자는 접근자로 꺼내고, 그때 어디에 남길지 스스로 결정합니다.

🔴 여기서 메시지만 정리하면 부족합니다. **cause 체인도 로그 노출면입니다.** 하위 HTTP 라이브러리의 응답 예외는 메시지에 응답 본문을 담는 경우가 있고, 그것을 그대로 `cause` 로 연결하면 전체 stack trace를 기록할 때 `Caused by:` 를 통해 본문이 다시 나갑니다. 위 예제가 `cause` 를 받지 않는 이유입니다. 원인 추적이 필요하면 상태 코드·요청 식별자처럼 **정제된 값만** 별도 필드로 옮깁니다.

⚠️ 접근자가 있다는 사실이 기본 Logging이나 상위 응답 노출을 허용한다는 뜻도 아닙니다. 응답 본문에는 개인정보나 자격 증명성 값이 들어 있을 수 있으므로, 본문을 남기는 쪽에서 정제 책임을 함께 져야 합니다. 예외 객체 자체를 기본 오류 응답 직렬화 대상으로 넘겨서도 안 됩니다.

📌 이 선택의 대가는 분명합니다. **분류 규칙이 SDK 밖으로 나가면 호출자마다 갈라집니다.** 어떤 호출자는 상태 코드만 보고 재시도하고, 어떤 호출자는 본문을 Parsing합니다. 위 표의 예외 계층이 권장되는 이유가 정확히 그것입니다. 그래서 이 선택은 **"업무 의미를 SDK 안에서 해석하지 않는다"는 범위를 유지하는 동안만** 유효합니다. 무엇을 하지 않겠다고 적었는지가 이 결정의 유효기간을 정합니다.

⚠️ 오해를 막기 위해 범위를 좁혀 둡니다. 응답 오류를 하나의 SDK 예외로 보존하는 것이 **설정·네트워크·취소·프로토콜 오류까지 하위 라이브러리 예외로 누출해도 된다는 뜻은 아닙니다.** 위 표에서 업무 의미와 무관한 행들은 통과 계층에서도 SDK 자신의 타입으로 감싸야 합니다.

따라서 [16절](#ai-section-16) 체크리스트의 "안정적인 코드와 예외 계층"은 여전히 **권장 기본형**입니다. 여기서 허용한 예외는 상위 응답의 업무별 세분화 하나뿐입니다.

<h2 id="ai-section-12" style="scroll-margin-top: 72px;">12. 관측성은 논리 호출과 실제 전송 시도를 구분한다</h2>

재시도가 있는 Client에서는 사용자가 호출한 업무 작업 한 번과 실제 HTTP 전송 여러 번을 구분해야 합니다.

OpenTelemetry HTTP Semantic Conventions는 HTTP Client Span을 `CLIENT` 종류로 기록하고, 재전송 시 `http.request.resend_count`를 사용하는 방식을 설명합니다. 최초 전송에는 이 속성을 넣지 않고, 첫 번째 재전송부터 `1`, `2`처럼 재전송 횟수를 기록합니다.

SDK의 진단 정보는 다음처럼 나눌 수 있습니다.

- 논리 작업: `sdk.operation`, 최종 결과, 전체 지연시간
- 전송 시도: HTTP Method, Route Template, Status, Attempt
- 상관관계: Request ID, Trace ID
- 정책 결과: Retry 여부, Backoff, Deadline 잔여시간
- 오류: 안정적인 SDK Error Code

고카디널리티 원문 URI, Token, 전체 Request·Response Body와 개인정보 Payload는 기본 관측 정보에 넣지 않습니다.

<h2 id="ai-section-13" style="scroll-margin-top: 72px;">13. 테스트는 실제 HTTP가 없어도 대부분 가능해야 한다</h2>

전송 계층을 분리하면 Core 정책을 Fake Transport로 검증할 수 있습니다.

```java
FakeTransport transport = FakeTransport.sequence(
        response(503, problem("TEMPORARY_UNAVAILABLE")),
        response(201, sessionJson("session-example"))
);

SdkClient client = TestSdkClient.builder()
        .transport(transport)
        .retryPolicy(fixedAttempts(2))
        .build();

Session result = client.sessions().create(request, context);

assertThat(result.id()).isEqualTo("session-example");
assertThat(transport.requestCount()).isEqualTo(2);
```

테스트 층은 다음처럼 구성합니다.

| 층 | 검증 대상 |
|---|---|
| Unit | Mapper, Timeout Budget, Retry 판단, 오류 변환 |
| Transport | Header·직렬화·Status·Body 수신 |
| Contract | OpenAPI 요청·응답과 생성 코드 일치 |
| Conformance | 다른 플랫폼 SDK와 같은 상태·오류 의미 |
| Integration | 실제 HTTP Stub과 연결 풀·취소·Deadline |
| Compatibility | 지원 서버 버전별 핵심 시나리오 |

필수 Negative Test도 포함합니다.

- Secret이 로그에 남지 않는가
- Tenant 문맥이 누락되면 전송 전에 실패하는가
- 비멱등 요청이 재시도되지 않는가
- Deadline 종료 후 추가 Attempt가 없는가
- 미지의 Enum과 추가 응답 필드를 안전하게 처리하는가
- `close()` 후 신규 요청이 거부되는가
- 호출자가 제공한 Executor를 SDK가 종료하지 않는가

<h2 id="ai-section-14" style="scroll-margin-top: 72px;">14. Thread Safety는 선언이 아니라 상태 배치로 만든다</h2>

Thread-safe Client를 만들려면 요청마다 바뀌는 값을 공유 필드에 저장하지 않아야 합니다.

```java
// 잘못된 예: 동시 요청 사이에서 tenantId가 덮어써질 수 있다.
client.setTenantId("tenant-a");
client.sessions().get("session-1");
```

```java
// 권장 예: 요청 문맥을 불변 객체로 전달한다.
client.sessions().get(
        "session-1",
        RequestContext.forTenant("tenant-a")
);
```

공유할 수 있는 상태:

- 불변 설정
- Thread-safe 연결 풀
- Thread-safe Credential Cache
- 원자적으로 갱신되는 인증 상태
- 불변 Mapper와 Codec

요청 지역에 둘 상태:

- Tenant·User·Request ID
- Deadline과 Cancellation
- Retry Attempt
- 응답 Buffer
- 진단 Context

Token Refresh처럼 공유가 필요한 가변 상태는 여러 요청이 동시에 갱신하지 않도록 Single Flight 또는 명시적인 동시성 제어를 적용합니다.


<h3 data-ke-size="size23">14.1 갱신 단위와 읽기 단위가 같은 조합이어야 한다</h3>

위 목록의 "원자적으로 갱신되는 인증 상태"에는 한 칸이 더 필요합니다. 런타임에 바뀌는 값이 **여러 개**일 때, 각 값을 원자적으로 갱신해도 **여러 값을 함께 읽는 쪽**은 서로 다른 세대의 값을 섞어 볼 수 있습니다.

```java
// 각 필드의 단일 읽기와 쓰기는 원자적이다.
// 그러나 세 값을 차례로 읽는 쪽은 이전 주소와 새 제한시간을 섞어 볼 수 있다.
private volatile String endpoint;
private volatile Duration connectTimeout;
private volatile Duration readTimeout;
```

해법은 세 값을 **하나의 불변 레코드로 묶고 그 레코드를 교체**하는 것입니다. 한 값만 바꾸는 메서드도 나머지를 함께 실어 새 한 벌을 만듭니다.

```java
public final class TransportSettings {

    public record Snapshot(String endpoint, Duration connectTimeout, Duration readTimeout) {}

    private final AtomicReference<Snapshot> ref;

    public TransportSettings(Snapshot initial) {
        this.ref = new AtomicReference<>(validated(initial));
    }

    /** 읽는 쪽이 반드시 이 메서드로 한 벌을 받아야 한다. */
    public Snapshot current() {
        return ref.get();
    }

    /** 한 값만 바꿔도 나머지를 함께 실어 새 한 벌을 만든다. */
    public void updateEndpoint(String endpoint) {
        ref.updateAndGet(s -> validated(
                new Snapshot(endpoint, s.connectTimeout(), s.readTimeout())));
    }

    /** 여러 값이 함께 바뀌어야 할 때. 중간 혼합 상태를 만들지 않는다. */
    public void update(Snapshot next) {
        ref.set(validated(next));
    }

    private static Snapshot validated(Snapshot s) {
        Objects.requireNonNull(s, "snapshot");
        if (s.endpoint() == null || s.endpoint().isBlank()) {
            throw new IllegalArgumentException("endpoint must not be blank");
        }
        requirePositive(s.connectTimeout(), "connectTimeout");
        requirePositive(s.readTimeout(), "readTimeout");
        return s;
    }

    private static void requirePositive(Duration value, String field) {
        if (value == null || value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(field + " must be a positive duration");
        }
    }
}
```

여러 값을 한 번에 바꾸는 메서드를 따로 둔 이유도 같습니다. 주소와 제한시간을 함께 옮겨야 하는 절체에서 단일 값 메서드를 잇달아 호출하면, 그 사이에 지나가는 요청이 **새 주소에 옛 제한시간**을 쓰는 조합을 만납니다.

🔴 여기서 실제로 놓치기 쉬운 쪽은 갱신이 아니라 **읽기**입니다. 위처럼 한 벌을 돌려주는 접근자를 만들어 두고도, 호출하는 쪽이 값마다 별도 접근자를 차례로 부르면 원자성은 그 지점에서 무너집니다.

```java
// 잘못된 사용: current() 를 세 번 호출해 서로 다른 세대를 섞을 수 있다.
String endpoint = settings.current().endpoint();
Duration connect = settings.current().connectTimeout();
Duration read = settings.current().readTimeout();
```

```java
// 올바른 사용: 참조를 한 번만 읽고 같은 스냅샷에서 값을 꺼낸다.
TransportSettings.Snapshot now = settings.current();
String endpoint = now.endpoint();
Duration connect = now.connectTimeout();
Duration read = now.readTimeout();
```

📌 불변 스냅샷은 **교체 단위**만 원자적으로 만듭니다. 일관성은 읽는 쪽이 같은 단위로 읽을 때 성립합니다. 그래서 편의용 값별 접근자(`settings.endpoint()` 같은 위임 메서드)를 함께 노출하면 잘못된 사용이 조용히 컴파일됩니다. 그런 접근자를 아예 두지 않는 편이 안전하고, 둘 수밖에 없다면 사용 규칙을 계약 문서에 못 박아야 합니다.

<h3 data-ke-size="size23">14.2 경쟁이 무해하려면 두 조건이 함께 성립해야 한다</h3>

전송 Client를 위 한 벌을 키로 캐시하고 값이 바뀌면 다시 만드는 배치가 흔히 쓰입니다. 여기서 락을 쓰지 않고 **비교·교환에서 진 쪽이 이긴 쪽을 재사용**하게 만들 수 있습니다.

```java
private final AtomicReference<Cached> cached = new AtomicReference<>();

private HttpTransport transport() {
    while (true) {
        TransportSettings.Snapshot now = settings.current();
        Cached current = cached.get();
        if (current != null && current.key().equals(now)) {
            return current.transport();
        }
        Cached fresh = new Cached(now, HttpTransport.create(now));
        if (cached.compareAndSet(current, fresh)) {
            return fresh.transport();
        }
        // 경쟁에서 졌다. 설치된 것이 내가 읽은 설정과 같은지 다시 확인한다.
    }
}

private record Cached(
        TransportSettings.Snapshot key,
        HttpTransport transport
) {}
```

비교·교환 실패 후 곧바로 설치된 값을 반환하는 구현을 자주 보게 되는데, 그것이 안전한 조건은 **경쟁한 두 쪽의 키가 같을 때**입니다. 생성 중에 설정이 또 바뀌면 다음 순서가 가능합니다.

1. 스레드 A가 설정 `S1`을 읽고 Client를 만든다.
2. 설정이 `S2`로 교체된다.
3. 스레드 B가 `S2`를 읽고 Client를 만든다.
4. A가 먼저 설치에 성공한다.
5. B는 비교·교환에서 지고 **자신이 읽지 않은 `S1`** 의 Client로 요청을 보낸다.

다음 요청이 다시 교정하더라도 이 한 건은 "교체는 다음 요청부터 반영된다"는 계약을 벗어납니다. 위 코드처럼 실패 후 루프를 다시 돌면 이 창이 닫힙니다.

⚠️ 두 번째 조건은 **버려지는 후보의 비용**입니다. 이 루프가 단순한 것은 후보 객체가 외부 자원이나 생성 부작용을 갖지 않고, 버려져도 비용이 허용될 때뿐입니다. 그렇지 않다면 회수 대상이 둘로 늘어납니다.

- 비교·교환에 **실패한 후보**를 그 자리에서 정리해야 합니다.
- 교체에 **성공했을 때 밀려난 기존 객체**도 정리해야 합니다.

두 번째가 더 까다롭고, 여기서 흔한 오해가 하나 있습니다. 락은 공유 임계구역 안의 생성·교체를 직렬화하고, 단일 비행(Single Flight)은 같은 키의 중복 생성을 합칠 수 있습니다. 그러나 **어느 쪽도 밀려난 객체를 언제 닫아도 되는지는 알려 주지 않습니다.** 진행 중인 요청이 아직 그 객체를 쓰고 있을 수 있기 때문입니다.

📌 그래서 SDK가 소유하고 닫아야 하는 자원에는 **서로 독립적인 두 장치**가 필요합니다.

| 필요한 것 | 무엇을 보장하나 | 수단과 주의점 |
|---|---|---|
| 생성·설치 경쟁 제어 | 설치 승자를 정하고, 선택한 방식에 따라 중복 생성을 억제한다 | 공유 락 · 키별 단일 비행 · 비교·교환. 단 **비교·교환만으로는 중복 생성이 막히지 않으므로** 패배 후보를 별도로 회수해야 한다 |
| 사용 종료 후 회수 | 새 사용을 막은 뒤 마지막 진행 중 사용자가 끝나면 닫는다 | retire 절차를 포함한 lease · 참조 계수 · 전송 구현의 graceful drain |

[5.1](#ai-section-5)의 자원 소유권 표가 여기서 판정 기준이 됩니다. 첫 번째 장치가 없으면 중복 생성이나 뒤늦은 설치가 생기고, 패배 후보를 회수하지 않으면 누수로 이어집니다. 두 번째 장치가 없으면 밀려난 객체를 즉시 닫아 **사용 중 종료**를 만들거나, 닫지 않아 누수시킵니다. **생성·설치 경쟁 제어는 안전한 회수 시점을 대신하지 못합니다.**

⚠️ 루프 자체에도 한계가 있습니다. 후보 생성이 유한 시간에 끝난다는 전제에서도 이 방식은 **개별 호출의 완료를 보장하는 wait-free 알고리즘이 아닙니다.** 설정 변경과 캐시 교체가 계속되면 특정 호출이 반복해서 비교·교환에 실패할 수 있습니다. 여기서 선택지를 구별해야 합니다.

| 원하는 것 | 필요한 것 | 얻지 못하는 것 |
|---|---|---|
| 재시도 횟수를 제한한다 | 상한 뒤 실패나 시간 초과를 반환 | 성공 보장 |
| 성공할 때까지의 기아 방지 | 모든 생성·교체 참여자가 **공정한 큐나 잠금과 유한한 임계구역**을 공유 | 이 방식도 blocking이며 엄밀한 wait-free나 실행 시간 상한은 아니다 |

일부 호출만 쓰는 별도 잠금은 다른 교체자와 조정되지 않고, 갱신 빈도를 제한하는 것은 운영상 완화책입니다. 둘 다 알고리즘의 완료 보장이 아닙니다.

<h2 id="ai-section-15" style="scroll-margin-top: 72px;">15. 공개 API와 패키징에 호환성 예산을 둔다</h2>

Server API와 Java SDK Package의 버전은 분리합니다.

```text
Private API Contract Version : 2026-07
Java SDK Version             : 2.4.0
Minimum Java Runtime         : 17
Tested Runtime               : 17, 21
```

공개 API에 다음 타입을 노출하면 교체 비용이 커집니다.

- 특정 HTTP Client의 Request·Response
- 특정 JSON 라이브러리의 Tree·Annotation
- 특정 Retry 라이브러리의 Context
- 특정 Telemetry SDK의 Span
- 생성기 전용 DTO

필요하면 SDK 자체의 작은 Interface와 Value Object를 공개하고, Adapter를 별도 모듈로 제공합니다.

<h3 data-ke-size="size23">15.1 패키징과 의존성 정책도 제품 계약이다</h3>

Java SDK 소비자는 Maven 또는 Gradle로 패키지를 가져옵니다. 이때 의존성 충돌은 기능 오류만큼 큰 도입 장벽이 됩니다.

권장 원칙은 다음과 같습니다.

- 공개 API 모듈의 의존성을 최소화
- 구현 의존성은 외부 공개를 줄임
- 동일 라이브러리의 여러 버전을 임의로 강제하지 않음
- BOM 또는 Version Catalog용 정보를 제공
- Java 최소 버전과 테스트 버전을 명시
- 서명, Checksum과 변경 이력을 함께 배포
- CVE 대응 범위와 지원 종료 정책을 공개

SDK 사용자가 내부 전송 라이브러리를 직접 참조해야 정상 동작하는 구조라면 모듈 경계가 새고 있다는 신호입니다.


<h3 data-ke-size="size23">15.2 호환성 경계는 틀린 것을 고칠 때 드러난다</h3>

필자는 인수한 Java Server SDK가 노출하는 호출 목록을 서버가 발행한 OpenAPI 명세와 대조한 일이 있습니다. 방식은 단순했습니다 — 경로의 파라미터 **이름**을 지워 정규화한 뒤 `(HTTP Method, 경로)` 튜플 집합을 양쪽에서 뽑아 비교했습니다. 파라미터 이름이 다른 것은 같은 호출로 봐야 하므로 이름을 비교 대상에서 뺐습니다.

여기서 **SDK 쪽에만 나타나는 후보**가 잡혔습니다. 컴파일되고 공개 시그니처도 안정적인 호출들이었습니다.

📌 경로 문자열 자체는 소스와 함께 컴파일됩니다. 컴파일러가 확인하지 않는 것은 그 문자열이 **실제 서버 라우트와 일치하는지**입니다. 공개 API 호환성 검사도 이것을 보지 않습니다. 이 불일치는 통합·계약 Test, 실제 호출, 명세 대조, 생성 Client 기반 검증 같은 별도 층에서 잡아야 합니다. 이 절이 말하는 호환성 예산에는 공개 시그니처만이 아니라 **SDK가 조립하는 요청의 모양**도 들어갑니다.

첫 결정은 **그대로 두는 것**이었습니다. 명세 한 벌만으로는 판정할 수 없었기 때문입니다. "명세에 없다"는 **"서버에 그 경로가 없다"** 와 **"서버가 명세에서 빼기로 했다"** 를 구별하지 못합니다. 내부 연동 전용 경로를 공개 명세에서 제외하는 것은 흔한 정책이므로, 그 상태에서 코드를 고치면 동작하던 호출을 깨뜨릴 수도 있었습니다.

🔴 다른 환경의 명세까지 교차 검증한 뒤에야 후보들의 성격이 갈렸습니다. **일부는 SDK 쪽 경로 오류로 확정**돼 보정했고, **다른 후보는 그 환경의 명세에 정식 노출된 것이 확인**돼 그대로 유지했습니다. 결과적으로 `(HTTP Method, 경로)` 비교 범위에서는 SDK가 노출하는 호출이 그 환경 명세와 전부 일치했습니다. 질의 파라미터·요청 본문·응답 Schema는 이 비교의 범위가 아니었습니다.

여기서 얻은 것은 대조 방법이 아니라 **판정 기준의 순서**였습니다. 명세는 환경마다 다를 수 있습니다. 어느 환경의 명세를 표준으로 볼지 먼저 정하지 않으면, 같은 대조 결과가 "우리 버그"와 "노출 정책"으로 둘 다 읽힙니다. 그래서 보류는 게으름이 아니라 **근거가 한 벌뿐이라는 사실의 기록**이었습니다.

보정 자체는 호환성 예산을 거의 쓰지 않고 끝났습니다. 값을 한 것은 앞선 절들의 경계였습니다.

- 경로 문자열이 **공개 시그니처에 포함되지 않고 호출 메서드의 구현 안에만** 있었으므로 공개 API를 건드리지 않고 보정할 수 있었습니다.
- 공개 메서드의 이름과 인자, 질의 파라미터 조립 방식이 그대로였으므로 **호출 측 코드 변경이 없었습니다.**
- 즉 작동하지 않던 코드를 작동하게 만드는 수정이 소비자에게 **아무 이전 비용도 지우지 않고** 끝났습니다.

경계가 잘 그어졌는지는 기능을 더할 때보다 **틀린 것을 고칠 때** 드러납니다. 같은 오류가 공개 API에 경로 조각이나 전송 계층 타입을 노출하는 설계였다면 소비자 코드까지 함께 바뀌었을 것입니다.

<h2 id="ai-section-16" style="scroll-margin-top: 72px;">16. 구현 체크리스트</h2>

### 공개 API

- [ ] 공개 Model과 전송 DTO가 분리되어 있다.
- [ ] 특정 HTTP·JSON 구현 타입이 공개 API에 노출되지 않는다.
- [ ] `SdkClient`의 Thread Safety가 문서화되어 있다.
- [ ] 동기·비동기·취소 의미가 정의되어 있다.
- [ ] 오류는 안정적인 코드와 예외 계층으로 제공된다.

### 수명과 자원

- [ ] Client를 요청마다 생성하지 않는다.
- [ ] SDK 소유 자원과 호출자 소유 자원이 구분된다.
- [ ] `close()`의 진행 중 요청 처리 정책이 있다.
- [ ] 호출자가 주입한 Executor를 SDK가 임의로 종료하지 않는다.
- [ ] 응답 Body와 Stream의 종료 책임이 명확하다.

### 보안과 정책

- [ ] Mobile·Browser에 서버 Secret이 전달되지 않는다.
- [ ] Credential과 요청별 Tenant 문맥이 분리되어 있다.
- [ ] Secret·Token·원문 Payload가 기본 로그에서 제외된다.
- [ ] 비멱등 요청은 자동 재시도되지 않는다.
- [ ] 멱등 키와 Deadline이 전체 재시도에 유지된다.

### 품질과 운영

- [ ] Fake Transport로 Core 정책을 테스트할 수 있다.
- [ ] OpenAPI 계약 테스트와 파괴적 변경 검사가 있다.
- [ ] 논리 호출과 실제 전송 Attempt를 구분해 관측한다.
- [ ] 지원 Java·API·SDK 버전 표가 있다.
- [ ] Migration Guide와 Changelog가 패키지와 함께 배포된다.

<h2 id="ai-section-17" style="scroll-margin-top: 72px;">17. 마무리와 참고 자료</h2>

### 좋은 Server SDK는 연결 세부사항보다 책임을 캡슐화한다

프라이빗 API를 연결하는 Java SDK의 가치는 HTTP 요청 코드를 줄이는 데만 있지 않습니다.

1. 고객사 서버와 프라이빗 API 사이의 신뢰 경계를 명확히 합니다.
2. 인증·테넌트·오류·재시도·관측 정책을 일관되게 적용합니다.
3. 장수명 Thread-safe Client와 명시적인 자원 소유권으로 운영 안정성을 높입니다.
4. 생성 코드와 전송 구현을 공개 API에서 격리해 호환성 비용을 줄입니다.
5. Fake Transport와 공통 계약 테스트로 실제 망에 접속하지 않고도 대부분의 통합을 검증하게 합니다.

결국 좋은 Server SDK는 네트워크 세부사항을 숨기는 Wrapper가 아니라, **고객사가 프라이빗 서비스를 안전하고 예측 가능하게 사용할 수 있도록 제품 책임을 캡슐화한 실행 계약**입니다.

다음 글인 [고객사 서버에 SDK를 연결하는 Spring Boot Starter](https://aiarchitect.tistory.com/38)에서는 이 Java Core SDK를 고객사 Spring Boot 애플리케이션에 연결합니다. `@ConfigurationProperties`, 조건부 Auto-configuration, 사용자 Bean 우선권, Secret 주입과 Context 종료 시 Client 정리를 구체적으로 살펴봅니다.

### 상호 참조 및 공식 참고 자료

### 시리즈 상호 참조

- [프라이빗 API를 보호하는 멀티플랫폼 SDK 아키텍처](https://aiarchitect.tistory.com/40)
- [고객사 서버에 SDK를 연결하는 Spring Boot Starter](https://aiarchitect.tistory.com/38)
- [Java Security Gateway와 Python AI Orchestrator의 책임 분리](https://aiarchitect.tistory.com/5)
- [운영 가능한 AI Agent: Checkpoint·Retry·Idempotency·Outbox](https://aiarchitect.tistory.com/7)

### 공식 참고 자료

- [Java SE 21: java.net.http.HttpClient](https://docs.oracle.com/en/java/javase/21/docs/api/java.net.http/java/net/http/HttpClient.html)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- [RFC 9110: HTTP Semantics — Idempotent Methods](https://www.rfc-editor.org/rfc/rfc9110.html#name-idempotent-methods)
- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [OpenTelemetry: Semantic Conventions for HTTP Spans](https://opentelemetry.io/docs/specs/semconv/http/http-spans/)

> 이 글은 2026년 7월 31일 기준 공개된 공식 사양과 문서를 바탕으로 작성했습니다. Java, OpenAPI와 OpenTelemetry 사양은 변경될 수 있으므로 실제 구현 시 사용하는 버전의 공식 문서를 다시 확인해야 합니다.
