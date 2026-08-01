# Tistory 기술자료 초안

- 문서 ID: `BLOG-06`
- 상태: 공개 완료
- 공개 URL: https://aiarchitect.tistory.com/6
- Tistory 상태: 공개 게시·공개 페이지 검증 완료
- 분류: `프로젝트 문제 해결`
- 권장 제목: `브라우저 WebRTC가 연결되지 않을 때: ICE, mDNS, NAT와 TURN 진단 순서`
- 검색 설명: `로컬에서는 되지만 실제 네트워크에서 실패하는 WebRTC 연결을 권한, 시그널링, ICE Candidate, mDNS, NAT, TURN, DTLS와 미디어 통계 순서로 진단하는 방법을 정리합니다.`
- 권장 태그: `WebRTC`, `ICE`, `mDNS`, `NAT`, `TURN`, `Media Server`, `문제 해결`
- 권장 대표 이미지: `portfolio/architecture-diagrams/03-realtime-speech-recording.svg`

---

# 브라우저 WebRTC가 연결되지 않을 때: ICE, mDNS, NAT와 TURN 진단 순서

개발 환경에서는 잘 되던 WebRTC가 사내망, 고객사망 또는 모바일 네트워크에서 갑자기 연결되지 않는 경우가 있습니다. 이때 콘솔에서 `.local` 주소를 발견하고 mDNS를 의심하거나, 곧바로 TURN 서버부터 추가하기 쉽습니다.

하지만 WebRTC 연결은 하나의 요청으로 완성되지 않습니다. 미디어 장치 권한, 시그널링, ICE Candidate 수집과 교환, 후보 쌍 연결성 검사, DTLS와 SRTP, 실제 RTP 전송이 차례로 이어집니다. 앞 단계가 실패했는데 뒤 단계 설정을 바꾸면 원인을 더 찾기 어려워집니다.

브라우저에서 Media Server로 음성을 전송하는 구조를 단순화하면 다음과 같습니다.

```text
Browser Media
  │  장치 권한 · Track
  ▼
RTCPeerConnection
  │  Offer/Answer · Trickle ICE
  ▼
ICE Candidate Pair
  │  host · srflx · relay
  ▼
DTLS · SRTP
  │  암호화된 미디어
  ▼
Media Server
  ├─ Publish · Subscribe
  ├─ Server Recording
  └─ Real-time STT
```

이 글에서는 “연결 안 됨”을 하나의 증상으로 보지 않고, 어느 단계에서 멈췄는지 확인하는 순서로 문제를 나눕니다.

## 1. 먼저 실패를 다섯 구간으로 분리한다

WebRTC 장애를 빠르게 찾으려면 사용자 화면의 결과보다 내부 상태 전이를 봐야 합니다.

| 구간 | 대표 증상 | 먼저 확인할 항목 |
|---|---|---|
| 장치와 Track | 권한 오류, 영상·음성이 처음부터 없음 | 보안 Context, 권한, 장치, Track 상태 |
| 시그널링 | Offer/Answer 또는 Candidate가 상대에게 도착하지 않음 | SDP 교환 순서, 세션 매핑, Trickle ICE |
| ICE | `checking` 후 `failed`, 선택된 후보 쌍 없음 | host·srflx·relay 후보와 연결성 검사 |
| 보안 전송 | ICE는 연결됐지만 PeerConnection이 완성되지 않음 | DTLS 상태, 인증서 Fingerprint, 역할 |
| 미디어 | 연결 상태는 정상인데 소리·영상이 없음 | Track 방향, Codec, RTP 통계, 재생 정책 |

`연결 실패`라는 하나의 로그만으로는 어느 구간인지 알 수 없습니다. 브라우저와 Media Server 양쪽에서 같은 세션의 시간순 상태를 맞춰 볼 수 있어야 합니다.

## 2. 재현 환경을 고정하고 장치 단계부터 확인한다

로컬 개발 환경과 실제 네트워크는 조건이 다릅니다. 브라우저 버전, 운영체제, VPN, 유선·무선·모바일망, 방화벽과 프록시 정책이 경로 선택에 영향을 줍니다.

먼저 다음 조건을 기록합니다.

- 브라우저와 운영체제 버전
- 접속 네트워크 유형과 VPN 사용 여부
- 같은 장치에서 실패가 반복되는지
- 다른 네트워크로 바꾸면 성공하는지
- 송신만 실패하는지, 수신만 실패하는지, 둘 다 실패하는지
- 같은 시각 Media Server에 세션이 생성됐는지

그다음 `getUserMedia()`가 성공했고 실제 Track이 살아 있는지 확인합니다.

```javascript
const stream = await navigator.mediaDevices.getUserMedia({
  audio: true,
  video: false
});

for (const track of stream.getTracks()) {
  console.info("local-track", {
    kind: track.kind,
    enabled: track.enabled,
    muted: track.muted,
    readyState: track.readyState
  });
}
```

장치 권한이 거부됐거나 Track의 `readyState`가 `ended`라면 아직 ICE나 TURN 문제가 아닙니다. 페이지의 보안 Context, 브라우저 권한, 운영체제 장치 권한과 실제 입력 레벨부터 해결해야 합니다.

## 3. 시그널링은 ICE와 별도의 경로다

WebRTC 표준은 Offer, Answer와 ICE Candidate를 상대에게 전달할 시그널링 프로토콜 자체를 정하지 않습니다. WebSocket, HTTP 또는 업무용 메시지 채널을 사용할 수 있지만, 애플리케이션이 교환 순서와 세션 매핑을 책임져야 합니다.

다음 오류는 네트워크 우회 기술로 해결되지 않습니다.

- Offer가 잘못된 상대 세션에 전달됨
- Answer를 받기 전에 세션이 만료됨
- `setRemoteDescription()` 전에 원격 Candidate를 잘못 처리함
- Candidate의 중간 전달이 누락됨
- 완료 신호를 너무 일찍 보내 뒤 Candidate가 버려짐
- 재연결 중 이전 세대의 ICE 정보가 섞임

Trickle ICE는 모든 후보 수집을 기다리지 않고 새 Candidate를 발견할 때마다 전달해 연결 시작 시간을 줄입니다. 그만큼 메시지 순서, 중복과 `end-of-candidates` 처리가 명확해야 합니다.

시그널링 로그에는 전체 SDP를 그대로 남기기보다 다음과 같은 최소 정보만 기록하는 편이 안전합니다.

```text
session=<opaque-id>
event=remote-description-applied
descriptionType=answer
iceGeneration=<masked-generation>
candidateCount=4
elapsedMs=820
```

SDP에는 주소, Codec 구성과 세션 정보가 들어갈 수 있습니다. 운영 로그에서 원문 SDP와 ICE 자격 증명을 수집해야 한다면 접근 범위, 보존 기간과 마스킹 정책을 별도로 적용해야 합니다.

## 4. ICE Candidate 종류를 보고 도달 가능한 경로를 추정한다

ICE는 여러 통신 경로 후보를 모은 뒤 Local Candidate와 Remote Candidate의 쌍을 만들고 연결성 검사를 수행합니다. 대표 Candidate 유형은 다음과 같습니다.

| 유형 | 의미 | 진단 포인트 |
|---|---|---|
| `host` | 장치의 네트워크 인터페이스에서 얻은 후보 | 같은 망에서는 유용하지만 사설 주소만으로 외부 연결을 보장하지 않음 |
| `srflx` | STUN으로 확인한 서버 반사 후보 | NAT 바깥에서 보이는 매핑을 얻었음을 의미 |
| `prflx` | 연결성 검사 과정에서 발견된 Peer 반사 후보 | 초기 Candidate 교환에 없던 매핑이 검사 중 확인됨 |
| `relay` | TURN 서버가 할당한 중계 후보 | 직접 경로가 실패해도 Relay를 통해 연결할 수 있는 대안 |

후보가 “있다”와 후보 쌍이 “연결됐다”는 다른 이야기입니다.

- `host`만 있다면 STUN·TURN 서버에 도달하지 못했거나 정책상 다른 후보가 제한됐을 수 있습니다.
- `srflx`가 있다면 STUN 응답을 받았다는 뜻이지만, 그 주소로 상대가 실제 접근할 수 있다는 보장은 아닙니다.
- `relay`가 없다면 TURN 미설정뿐 아니라 DNS, 인증, 전송 프로토콜 또는 서버의 Relay 주소·포트 설정 문제일 수 있습니다.
- 후보가 충분해도 양쪽 후보 쌍의 연결성 검사가 방화벽에서 차단될 수 있습니다.

따라서 Candidate 유형별 개수와 수집 완료 시점을 기록한 뒤, 실제로 선택된 Candidate Pair까지 확인해야 합니다.

## 5. `.local` mDNS 이름을 장애 원인으로 단정하지 않는다

일부 WebRTC 구현은 로컬 IP 주소 노출을 줄이기 위해 host Candidate의 주소를 mDNS 이름으로 표현할 수 있습니다. 이때 로그에 무작위처럼 보이는 `.local` 이름이 나타날 수 있습니다.

이 값은 잘못된 IP 문자열이 아닙니다. 브라우저가 로컬 주소를 애플리케이션에 직접 노출하지 않으면서 ICE 연결을 시도하기 위한 표현일 수 있습니다. WebRTC의 IP 처리에는 연결 성능과 사용자의 네트워크 정보 보호 사이의 균형이 필요합니다.

다음과 같은 임시 수정은 피해야 합니다.

- `.local` Candidate를 모두 제거함
- 애플리케이션 서버가 Candidate 문자열을 임의의 IP로 치환함
- Candidate를 일반 업무 주소처럼 파싱해 별도 연결을 시도함
- 로컬 IP 전체를 운영 로그와 분석 도구에 그대로 저장함

먼저 확인할 것은 이름의 모양이 아니라 결과입니다.

1. host 외에 `srflx` 또는 `relay` Candidate가 수집되는가
2. 원격 ICE Agent에 Candidate가 원문 그대로 전달되는가
3. 선택된 Candidate Pair가 생성되는가
4. 특정 브라우저·망에서만 실패하는가

mDNS 이름이 보였다는 사실과 ICE 실패가 동시에 발생했다는 이유만으로 둘 사이의 인과관계가 확인되는 것은 아닙니다.

## 6. STUN은 NAT를 발견하지만 모든 NAT를 통과시키지는 않는다

STUN을 이용하면 클라이언트는 서버가 관찰한 주소와 포트 매핑을 확인해 `srflx` Candidate를 만들 수 있습니다. 그러나 STUN 자체가 미디어를 중계하는 것은 아닙니다.

다음 상황에서는 `srflx` Candidate가 있어도 직접 연결이 실패할 수 있습니다.

- NAT가 목적지에 따라 서로 다른 매핑을 사용함
- 양쪽 네트워크의 방화벽이 인바운드 UDP를 제한함
- 기업망이 알려지지 않은 UDP 흐름을 차단함
- VPN 또는 다중 인터페이스로 실제 반환 경로가 달라짐
- Media Server의 공개 주소와 실제 수신 주소가 일치하지 않음
- 컨테이너·가상화 환경에서 외부 주소와 포트가 잘못 광고됨

실전에서는 “STUN 서버가 응답했는가”와 “선택 가능한 후보 쌍이 성공했는가”를 분리해서 봐야 합니다. 전자는 후보 수집 단계이고, 후자는 양방향 연결성 검사 결과입니다.

## 7. TURN은 직접 경로가 막힐 때 사용하는 Relay다

TURN 서버는 클라이언트에 Relay 주소를 할당하고, 미디어 패킷을 상대 또는 Media Server로 중계합니다. 직접 연결이 어려운 NAT와 제한된 기업망에서 중요한 복구 경로입니다.

그렇다고 모든 트래픽을 처음부터 Relay로 고정하는 것이 항상 최선은 아닙니다. TURN은 가용성을 높이는 대신 중계 서버의 대역폭 비용, 지연, 용량 계획과 운영 책임을 추가합니다.

TURN 장애는 다음 순서로 확인합니다.

| 점검 항목 | 확인 내용 |
|---|---|
| 이름 해석 | TURN 호스트 이름이 실패 환경에서 해석되는가 |
| 인증 | 사용자 이름, 자격 증명과 만료 시각이 유효한가 |
| 전송 | UDP뿐 아니라 필요한 TCP·TLS 경로가 열려 있는가 |
| 인증서 | TLS 사용 시 호스트 이름과 인증서 체인이 유효한가 |
| 할당 | 브라우저가 실제 `relay` Candidate를 수집하는가 |
| 외부 주소 | TURN이 도달 가능한 Relay 주소를 광고하는가 |
| 포트 범위 | Relay 포트 범위가 방화벽과 일치하는가 |
| 용량 | 동시 세션, 대역폭과 지역별 지연을 감당하는가 |

문제 분리를 위해 일시적으로 다음 정책을 사용해 Relay 경로만 시험할 수 있습니다.

```javascript
const pc = new RTCPeerConnection({
  iceServers: [
    {
      urls: [
        "turn:turn.example.net:3478?transport=udp",
        "turns:turn.example.net:5349?transport=tcp"
      ],
      username: "<short-lived-username>",
      credential: "<short-lived-credential>"
    }
  ],
  iceTransportPolicy: "relay"
});
```

이 설정에서 성공하면 직접 후보 경로에 문제가 있을 가능성이 커집니다. 이 설정에서도 `relay` Candidate가 생기지 않으면 TURN 도달성, 인증 또는 서버 설정부터 봐야 합니다.

`relay` 강제는 진단 도구로 유용하지만, 서비스의 기본 정책으로 채택할지는 보안 요구, 지연, 비용과 네트워크 정책을 함께 평가해 결정해야 합니다. 장기 자격 증명을 클라이언트 코드에 고정해서도 안 됩니다.

## 8. 상태 이벤트를 시간순으로 기록한다

`RTCPeerConnection`은 시그널링과 연결 진행 상황을 여러 상태로 제공합니다. 하나의 최종 상태만 저장하지 말고 전이 시각을 기록해야 합니다.

```javascript
function attachPeerDiagnostics(pc, sessionId) {
  const report = (event, detail = {}) => {
    console.info("webrtc", {
      sessionId,
      event,
      at: new Date().toISOString(),
      signalingState: pc.signalingState,
      iceGatheringState: pc.iceGatheringState,
      iceConnectionState: pc.iceConnectionState,
      connectionState: pc.connectionState,
      ...detail
    });
  };

  pc.addEventListener("signalingstatechange", () =>
    report("signaling-state-change"));
  pc.addEventListener("icegatheringstatechange", () =>
    report("ice-gathering-state-change"));
  pc.addEventListener("iceconnectionstatechange", () =>
    report("ice-connection-state-change"));
  pc.addEventListener("connectionstatechange", () =>
    report("connection-state-change"));
  pc.addEventListener("icecandidateerror", event =>
    report("ice-candidate-error", {
      errorCode: event.errorCode,
      errorText: event.errorText
    }));
}
```

`iceConnectionState`의 `disconnected`는 네트워크 전환이나 일시적인 패킷 손실에서도 나타날 수 있습니다. 이를 즉시 영구 실패로 처리하기보다 짧은 관찰 구간, 복구 여부와 `failed` 전이를 함께 봅니다.

반대로 `checking`이 오래 지속된 뒤 `failed`가 된다면 후보는 교환됐지만 성공한 후보 쌍을 찾지 못했을 가능성이 큽니다. 이때 시그널링 코드를 계속 수정하기보다 후보 유형, 연결성 검사와 방화벽 경로를 확인해야 합니다.

## 9. 선택된 Candidate Pair가 실제 경로를 알려 준다

WebRTC Stats API는 Candidate Pair, Local Candidate, Remote Candidate와 전송 통계를 제공합니다. 브라우저마다 진단 화면은 다를 수 있지만, 애플리케이션에서는 `getStats()`로 표준화된 핵심 지표를 수집할 수 있습니다.

확인할 항목은 다음과 같습니다.

- 선택된 Pair의 Local·Remote Candidate 유형
- UDP, TCP와 Relay 전송 방식
- Candidate Pair의 `bytesSent`, `bytesReceived`
- 연결성 검사 요청과 응답
- 현재 왕복 시간
- Transport의 ICE와 DTLS 상태
- 선택 Pair 변경 횟수

예를 들어 연결은 성공했지만 선택 Pair가 `relay`라면 직접 경로가 아니라 TURN을 통해 동작 중이라는 뜻입니다. 반대로 선택 Pair가 있고 연결 상태가 정상인데 전송 바이트가 증가하지 않는다면 ICE보다 Track, 방향, Codec 또는 Media Server 처리 쪽을 봐야 합니다.

통계는 한 번의 절대값보다 일정 간격의 변화량이 유용합니다.

```text
t0  selectedPair=pair-7  bytesSent=12000  bytesReceived=8800
t1  selectedPair=pair-7  bytesSent=41800  bytesReceived=29600
Δ   송신·수신 증가 → 실제 패킷 흐름 존재
```

주소 원문을 중앙 로그로 보낼 필요는 없습니다. Candidate 유형, 프로토콜, Relay 여부와 통계 변화만으로도 많은 문제를 구분할 수 있습니다.

## 10. ICE 연결 뒤에는 DTLS와 SRTP가 남아 있다

ICE는 패킷이 오갈 수 있는 경로를 선택합니다. WebRTC 미디어 전송이 완성되려면 그 위에서 DTLS가 설정되고 SRTP 키가 만들어져야 합니다.

ICE가 `connected` 또는 `completed`인데 전체 `connectionState`가 정상으로 진행되지 않는다면 다음을 확인합니다.

- Offer와 Answer의 DTLS Fingerprint가 올바르게 교환됐는가
- Media Server 인증서 또는 역할 설정이 유효한가
- 재협상에서 이전 SDP와 새 Transport 정보가 섞이지 않았는가
- ICE 재시작 시 양쪽이 같은 세대의 자격 증명을 사용했는가
- Media Server 로그에서 DTLS Handshake 오류가 발생했는가

ICE 성공을 곧바로 미디어 성공으로 해석하면 이 구간을 놓치게 됩니다. `iceConnectionState`, `connectionState`와 Stats의 `dtlsState`를 함께 봐야 합니다.

## 11. 연결됐는데 미디어가 없으면 RTP와 Track을 본다

PeerConnection이 `connected`여도 사용자가 소리나 영상을 받지 못할 수 있습니다. 이 단계에서는 TURN 설정을 바꾸기 전에 송수신 방향과 RTP 통계를 확인합니다.

송신 측에서는 다음 항목을 봅니다.

- Local Track이 `enabled`이고 `live` 상태인가
- Track이 올바른 PeerConnection 또는 Transceiver에 연결됐는가
- Transceiver 방향이 `sendonly` 또는 `sendrecv`인가
- `outbound-rtp`의 `packetsSent`와 `bytesSent`가 증가하는가
- Media Server가 지원하는 Codec으로 협상됐는가

수신 측에서는 다음 항목을 봅니다.

- `ontrack` 이벤트가 발생했는가
- Remote Track이 `muted` 또는 `ended` 상태가 아닌가
- `inbound-rtp`의 `packetsReceived`와 `bytesReceived`가 증가하는가
- `packetsLost`, `jitter`와 폐기 패킷이 급증하지 않는가
- 브라우저 자동 재생 정책 때문에 재생만 막힌 것은 아닌가

자동 재생 실패는 네트워크 실패와 다릅니다. RTP 통계는 증가하는데 화면 또는 스피커 출력만 없다면 사용자 동작, Media Element 상태와 출력 장치를 확인해야 합니다.

## 12. 브라우저부터 Media Server까지 이 순서로 확인한다

E2E 진단 순서를 한 장으로 정리하면 다음과 같습니다.

```text
1. 장치 권한과 Local Track
   실패 → 브라우저·OS 권한과 입력 장치 확인
   성공
     ↓
2. Offer/Answer와 Candidate 전달
   실패 → 시그널링 순서·세션 매핑 확인
   성공
     ↓
3. host·srflx·relay Candidate 수집
   부족 → STUN·TURN 도달성·정책 확인
   충분
     ↓
4. 선택된 Candidate Pair와 ICE 상태
   실패 → NAT·방화벽·주소·포트 확인
   성공
     ↓
5. DTLS 상태
   실패 → Fingerprint·인증서·역할 확인
   성공
     ↓
6. RTP Stats와 Remote Track
   정지 → 방향·Codec·Track·Media Server 확인
   증가
     ↓
7. 재생·녹화·STT 같은 후속 처리 확인
```

이 순서를 지키면 “연결 안 됨”을 최소한 장치, 애플리케이션 제어 경로, 네트워크 경로, 보안 전송과 미디어 처리 문제로 나눌 수 있습니다.

## 13. 운영 로그는 진단 가능성과 개인정보 보호를 함께 만족해야 한다

운영 환경에서 모든 사용자에게 브라우저 내부 진단 화면을 열어 달라고 요청할 수는 없습니다. 애플리케이션 수준의 최소 진단 이벤트가 필요합니다.

권장 수집 항목은 다음과 같습니다.

- 추측하기 어려운 세션·연결 식별자
- 클라이언트와 서버의 기준 시각
- 브라우저·운영체제의 큰 버전
- 장치 권한과 Track 상태
- 시그널링, ICE Gathering, ICE Connection, 전체 Connection 상태 전이
- Candidate 유형별 개수
- 선택 Pair의 후보 유형과 전송 프로토콜
- TURN 할당 성공 여부와 오류 코드
- DTLS 상태
- RTP 패킷·바이트·손실·Jitter의 구간별 변화량
- 재연결, ICE Restart와 Pair 변경 횟수

수집을 피하거나 보호해야 할 항목도 있습니다.

- 전체 SDP와 ICE 자격 증명
- TURN 장기 자격 증명
- 마스킹되지 않은 사설·공인 IP와 포트
- 장치 이름처럼 사용자를 식별할 수 있는 값
- 불필요한 원본 미디어와 녹음

장애 분석 목적, 접근 권한, 보존 기간과 삭제 정책을 정하고 필요한 최소 데이터만 남깁니다. WebRTC는 연결을 위해 일반 웹 요청보다 더 많은 네트워크 정보를 다룰 수 있으므로 진단 편의만으로 원문을 무제한 수집해서는 안 됩니다.

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| 환경 | 브라우저, OS, VPN과 실패 네트워크를 재현할 수 있는가 |
| 장치 | 권한, 입력 장치와 Local Track 상태를 구분해 기록하는가 |
| 시그널링 | Offer·Answer·Candidate의 순서와 세션 매핑을 추적하는가 |
| Trickle ICE | Candidate 중간 전달과 완료 신호를 빠뜨리지 않는가 |
| Candidate | host·srflx·relay 유형별 수집 여부를 확인하는가 |
| mDNS | `.local` 이름을 임의 변환하거나 무조건 제거하지 않는가 |
| STUN | 응답 성공과 Candidate Pair 성공을 구분하는가 |
| TURN | UDP·TCP·TLS 경로, 단기 인증과 Relay 포트를 검증했는가 |
| ICE | 상태 전이와 선택된 Candidate Pair를 확인하는가 |
| DTLS | ICE 성공 뒤 DTLS 상태와 Fingerprint 교환을 확인하는가 |
| RTP | 송수신 바이트와 패킷의 변화량을 측정하는가 |
| 미디어 | Track 방향, Codec, 재생 정책과 후속 처리를 확인하는가 |
| 복구 | 일시적 `disconnected`, ICE Restart와 재연결 정책이 있는가 |
| 개인정보 | 주소, SDP, 자격 증명과 장치 정보를 최소 수집하는가 |
| E2E | 실제 고객 환경에 가까운 네트워크에서 양방향 시험했는가 |

## 마무리

WebRTC 연결 실패는 mDNS, NAT 또는 TURN 중 하나만의 문제가 아닙니다. 장치와 시그널링이 정상이어야 ICE를 볼 수 있고, ICE가 성공한 뒤에도 DTLS와 실제 미디어 흐름을 확인해야 합니다.

핵심 진단 원칙은 다음과 같습니다.

1. 실패를 장치, 시그널링, ICE, 보안 전송과 미디어로 분리합니다.
2. Candidate의 모양보다 유형과 선택된 Pair를 확인합니다.
3. `srflx` 수집 성공과 직접 연결 성공을 같은 의미로 보지 않습니다.
4. `.local` mDNS 이름을 임의로 제거하거나 변환하지 않습니다.
5. TURN은 직접 경로 실패를 보완하는 Relay이며 할당과 실제 전송을 따로 검증합니다.
6. ICE 연결 뒤 DTLS 상태와 RTP 통계 증가까지 확인합니다.
7. 실제 브라우저와 실제 네트워크에서 E2E로 재현합니다.

좋은 WebRTC 운영 체계는 장애가 없다고 가정하지 않습니다. 어느 단계에서 멈췄는지 빠르게 확인하고, 직접 경로가 막혀도 안전한 Relay로 복구하며, 연결 뒤 미디어 품질까지 측정할 수 있어야 합니다.

다음 글에서는 LLM과 외부 Tool 호출이 포함된 긴 AI Workflow를 실패 후 다시 시작할 수 있도록 Checkpoint, Retry, Idempotency와 Outbox를 설계하는 방법을 살펴보겠습니다.

---

## 참고 자료

- [W3C WebRTC 1.0](https://www.w3.org/TR/webrtc/)
- [W3C WebRTC Statistics API](https://www.w3.org/TR/webrtc-stats/)
- [RFC 8445: Interactive Connectivity Establishment](https://datatracker.ietf.org/doc/html/rfc8445)
- [RFC 8489: Session Traversal Utilities for NAT](https://datatracker.ietf.org/doc/html/rfc8489)
- [RFC 8656: Traversal Using Relays around NAT](https://datatracker.ietf.org/doc/html/rfc8656)
- [RFC 8838: Trickle ICE](https://datatracker.ietf.org/doc/html/rfc8838)
- [RFC 8828: WebRTC IP Address Handling Requirements](https://datatracker.ietf.org/doc/html/rfc8828)
- [Using Multicast DNS to Protect Privacy When Exposing ICE Candidates](https://datatracker.ietf.org/doc/html/draft-ietf-rtcweb-mdns-ice-candidates-03)

> 이 글은 2026년 7월 29일 기준 W3C와 IETF의 공개 표준 문서, 공개 가능한 실시간 음성·WebRTC 검증 경험을 바탕으로 작성했습니다. 브라우저 구현, 네트워크 정책과 Media Server 구성에 따라 제공되는 통계와 연결 동작은 달라질 수 있으므로 실제 배포 환경에서 E2E 검증해야 합니다.
