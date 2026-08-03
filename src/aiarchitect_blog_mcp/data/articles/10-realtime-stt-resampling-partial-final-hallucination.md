# 실시간 STT 설계: 48kHz 리샘플링, Partial·Final 자막과 환각 억제

파일 하나를 끝까지 받은 뒤 처리하는 STT(Speech-to-Text, 음성 인식)는 입력 형식을 정규화하고 모델을 한 번 실행하면 됩니다.

실시간 STT는 다릅니다.

- 브라우저와 장치마다 실제 Sample Rate(샘플링 레이트)가 다를 수 있습니다.
- 작은 Audio Block(오디오 블록)을 끊김 없이 모아야 합니다.
- 네트워크가 밀리면 오래된 음성이 쌓입니다.
- 아직 말이 끝나지 않은 문장은 계속 바뀝니다.
- 침묵과 배경음에서 그럴듯한 문장이 생성될 수 있습니다.
- 연결이 재시작되면 중복 자막과 시간 역행이 발생할 수 있습니다.

따라서 실시간 자막 품질은 모델 정확도만으로 결정되지 않습니다. **입력 Audio Contract(오디오 계약), 리샘플링, Chunk(처리 묶음), Endpointing(발화 종료 판단), 자막 상태와 품질 Gate(품질 관문)를 하나의 시간 흐름으로 설계해야 합니다.**

기준 Pipeline(처리 흐름)은 다음과 같습니다.

```text
Microphone
  → MediaStreamTrack
  → AudioWorklet
  → Capture Buffer
  → Stateful Resampler
  → PCM 16kHz Mono
  → VAD
  → Rolling Audio Window
  → STT Inference
  → Hypothesis Reconciler
  → PARTIAL / FINAL
  → WebSocket
  → Subtitle Store · UI
```

## 1. `48kHz`를 가정하지 말고 실제 입력값을 확인한다

브라우저 음성 입력을 요청할 때 `sampleRate: 48000`을 지정해도 모든 환경에서 정확히 그 값이 선택된다고 가정해서는 안 됩니다.

Media Capture and Streams 사양은 `sampleRate`를 Track Constraint(트랙 제약)와 Track Setting(트랙 실제 설정)으로 정의합니다. Constraint는 선택에 영향을 주지만 실제 값은 권한을 얻은 뒤 `MediaStreamTrack.getSettings()`로 확인해야 합니다.

```javascript
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    channelCount: { ideal: 1 },
    sampleRate: { ideal: 48000 },
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true
  }
});

const track = stream.getAudioTracks()[0];
const settings = track.getSettings();

console.log({
  sampleRate: settings.sampleRate,
  channelCount: settings.channelCount,
  echoCancellation: settings.echoCancellation,
  noiseSuppression: settings.noiseSuppression,
  autoGainControl: settings.autoGainControl
});
```

다음 세 값은 서로 다를 수 있으므로 구분해 기록합니다.

| 값 | 의미 | 확인 위치 |
|---|---|---|
| Capture Sample Rate | 장치와 Track이 제공하는 실제 입력 Rate | `track.getSettings()` |
| AudioContext Sample Rate | Web Audio Graph가 처리하는 Rate | `audioContext.sampleRate` |
| Model Sample Rate | STT 모델이 기대하는 Rate | 모델 전처리 설정 |

OpenAI Whisper의 공개 Audio 전처리 코드는 기본 `SAMPLE_RATE`를 `16000`으로 정의하고, 입력을 Mono Waveform(단일 채널 파형)으로 읽어 필요한 경우 리샘플링합니다. `faster-whisper`도 NumPy 배열 입력은 `16kHz`의 1차원 Float 배열이어야 한다고 명시합니다.

즉 브라우저 처리 Rate가 `48kHz`이고 모델 입력이 `16kHz`라면 경계에서 명시적인 변환이 필요합니다.

## 2. 오디오 Byte보다 먼저 Audio Contract를 고정한다

서버가 PCM Byte만 받으면 그 Byte를 정확히 해석할 수 없습니다. 최소한 다음 Metadata(부가 정보)가 필요합니다.

```json
{
  "type": "audio",
  "streamId": "opaque-stream-id",
  "sequence": 1042,
  "capturedAtMs": 38120,
  "sampleRate": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "frameCount": 640
}
```

| 필드 | 필요한 이유 |
|---|---|
| `streamId` | 재연결 전후 Stream을 구분 |
| `sequence` | 유실·중복·순서 역전을 탐지 |
| `capturedAtMs` | 음성 시간축과 지연 계산 |
| `sampleRate` | Sample 수를 시간으로 환산 |
| `channels` | Mono·Stereo 해석 오류 방지 |
| `encoding` | Float32·PCM16·Endian 구분 |
| `frameCount` | 선언 길이와 실제 Payload 검증 |

예를 들어 `640` Frame의 `16kHz` Mono PCM은 `40ms`입니다.

```text
durationMs = frameCount / sampleRate × 1000
           = 640 / 16000 × 1000
           = 40ms
```

Server는 연결 최초의 `start` Message에서 Format을 확정하고, Stream 도중 Format이 바뀌면 조용히 추측하지 말고 새 Stream으로 다시 협상해야 합니다.

## 3. AudioWorklet Callback 크기를 고정값으로 가정하지 않는다

Web Audio API는 Audio Graph를 Render Quantum(렌더링 처리 블록) 단위로 실행합니다. 현재 기본 크기는 `128` Frame이지만, 사양에는 다른 크기를 선택할 수 있는 `renderSizeHint`도 정의돼 있습니다.

따라서 다음과 같은 코드는 피합니다.

```javascript
// 잘못된 가정: Callback은 항상 128 Frame이다.
processedMs += 128 / 48000 * 1000;
```

실제 입력 배열 길이를 사용해야 합니다.

```javascript
process(inputs) {
  const channel = inputs[0]?.[0];
  if (!channel) return true;

  this.totalFrames += channel.length;
  this.appendToCaptureBuffer(channel);
  return true;
}
```

AudioWorklet(오디오 전용 작업 모듈)은 실시간 Audio Rendering Thread(오디오 렌더링 스레드)에서 실행됩니다. 이 경로에서는 다음 작업을 최소화합니다.

- 네트워크 요청
- JSON 문자열 변환
- 큰 배열의 반복 생성
- 긴 동기 계산
- Log 남발
- Main Thread UI 갱신

Worklet은 Float Frame을 빠르게 Buffer에 모아 전달하고, Encoding·리샘플링·전송처럼 비용이 큰 작업은 Worker 또는 Server 경계에서 처리하는 구성이 관리하기 쉽습니다.

## 4. `48kHz → 16kHz`는 세 Sample 중 하나를 고르는 일이 아니다

`48kHz`를 `16kHz`로 바꾸는 비율은 정확히 `1/3`입니다. 그러나 다음처럼 세 번째 Sample만 선택하면 안 됩니다.

```python
# Anti-alias Filter가 없는 단순 Decimation(간격 추출)
pcm16k = pcm48k[::3]
```

`16kHz`의 Nyquist Frequency(나이퀴스트 주파수)는 `8kHz`입니다. 변환 전에 `8kHz`보다 높은 성분을 Low-pass Filter(저역 통과 필터)로 제한하지 않으면 고주파 성분이 낮은 대역으로 접혀 들어오는 Aliasing(에일리어싱)이 생깁니다.

Offline 예시는 Polyphase Resampling(다상 리샘플링)을 사용할 수 있습니다.

```python
from scipy.signal import resample_poly

pcm16k = resample_poly(pcm48k, up=1, down=3)
```

SciPy 공식 문서는 `resample_poly`가 Up-sampling(업샘플링), Zero-phase Low-pass FIR Filter(영위상 저역 통과 FIR 필터), Down-sampling(다운샘플링) 순서로 처리한다고 설명합니다.

실시간에서는 각 Network Chunk마다 독립적으로 `resample_poly`를 호출하는 것만으로 충분하지 않을 수 있습니다. Filter가 이전 Chunk의 Sample을 필요로 하기 때문입니다.

```text
Chunk A ─┐
         ├─ Stateful Resampler ── Continuous 16kHz PCM
Chunk B ─┤   ├─ filter state
Chunk C ─┘   └─ fractional phase
```

Streaming Resampler(스트리밍 리샘플러)는 다음 상태를 연결 사이에 보존해야 합니다.

- FIR Filter Delay Line(필터 지연선)
- 입력과 출력의 Fractional Phase(분수 위상)
- 누적 입력·출력 Frame 수
- Stream 종료 시 남은 Sample 처리 방식

검증식도 함께 둡니다.

```text
expectedOutputFrames ≈ totalInputFrames × 16000 / inputSampleRate
driftFrames = actualOutputFrames - expectedOutputFrames
```

장시간 실행 후 `driftFrames`가 계속 증가한다면 Chunk 경계에서 Sample을 버리거나 중복 처리하고 있을 가능성이 큽니다.

## 5. Channel과 PCM Encoding을 모델 입력 전에 정규화한다

Sample Rate만 맞아도 Format이 다르면 음성이 깨집니다.

권장 Model Boundary(모델 경계)는 단순하게 유지합니다.

```text
16kHz
Mono
Float32 [-1.0, 1.0] 또는 PCM S16LE
연속된 시간축
```

Stereo 입력을 Mono로 바꿀 때 두 Channel을 단순 합산하면 Peak가 두 배가 되어 Clipping(진폭 잘림)이 생길 수 있습니다.

```text
mono = 0.5 × left + 0.5 × right
```

Float32를 Signed 16-bit PCM(부호 있는 16비트 PCM)으로 변환할 때는 범위를 제한하고 양수·음수 Scaling을 구분합니다.

```javascript
function floatToPcm16(sample) {
  const x = Math.max(-1, Math.min(1, sample));
  return x < 0 ? Math.round(x * 32768) : Math.round(x * 32767);
}
```

Server에서는 다음 오류를 즉시 거부합니다.

- 선언한 `frameCount`와 Payload 길이 불일치
- `sampleRate` 미지원
- Stereo인데 Mono로 해석
- `pcm_s16le`와 Big-endian 혼동
- Float32 범위를 PCM16 정수로 해석
- 연결 중 Format의 예고 없는 변경

음성이 느리거나 빠르게 들리는 문제는 모델보다 Sample Rate Metadata 불일치에서 먼저 찾는 편이 빠릅니다.

## 6. Capture Chunk와 Inference Window를 분리한다

낮은 지연을 위해 아주 작은 Chunk를 모델에 바로 넣으면 호출 횟수가 늘고 문맥이 부족해집니다. 반대로 큰 Chunk만 기다리면 자막이 늦습니다.

세 단위를 분리합니다.

| 단위 | 역할 | 대표 판단 기준 |
|---|---|---|
| Capture Block | Audio Thread가 내보내는 작은 Frame | 실제 Callback 길이 |
| Transport Chunk | Network 전송과 Backpressure 단위 | 수십 ms 수준부터 측정 |
| Inference Window | STT가 문맥과 함께 보는 Audio | 모델·GPU·언어별 튜닝 |

```text
Capture Block × N
  → Transport Chunk × M
  → Rolling Inference Window
```

Whisper 계열 모델은 본래 완성된 입력을 처리하는 성격이 강하므로, 실시간 서비스는 새 Audio를 기존 Window에 겹쳐 다시 추론하고 안정된 Prefix(앞부분)를 확정하는 방식을 사용할 수 있습니다.

Chunk 크기는 하나의 숫자로 고정하기보다 다음 Latency Budget(지연 예산)을 나눠 측정합니다.

```text
capture
+ buffering
+ network
+ queue
+ inference
+ reconciliation
+ delivery
+ browser render
= user-visible subtitle latency
```

GPU가 빨라도 Queue 대기와 발화 종료 대기가 길면 Final 자막은 늦습니다. 반대로 Partial을 너무 자주 보내면 UI가 흔들리고 Network와 Rendering 비용이 커집니다.

## 7. Partial은 수정 가능하고 Final만 확정 데이터다

Partial(중간 결과)은 아직 뒤집힐 수 있는 현재 가설입니다. Final(확정 결과)은 해당 Audio 구간에 대해 더 이상 수정하지 않겠다는 Server의 계약입니다.

Google Cloud의 Streaming Recognition 결과도 `isFinal=false`를 변경 가능한 Interim Result(중간 결과), `isFinal=true`를 같은 Audio 구간에 더 이상 가설을 보내지 않는 최종 결과로 정의합니다.

Application Message는 이 의미를 명시적으로 표현해야 합니다.

```json
{
  "type": "transcript",
  "streamId": "opaque-stream-id",
  "segmentId": "segment-42",
  "revision": 7,
  "state": "PARTIAL",
  "startMs": 38120,
  "endMs": 40760,
  "text": "이번 배포 일정은",
  "stability": 0.78
}
```

확정 시 같은 `segmentId`의 새 Revision을 보냅니다.

```json
{
  "type": "transcript",
  "streamId": "opaque-stream-id",
  "segmentId": "segment-42",
  "revision": 8,
  "state": "FINAL",
  "startMs": 38120,
  "endMs": 41640,
  "text": "이번 배포 일정은 금요일입니다"
}
```

Client의 기본 규칙은 다음과 같습니다.

```text
if revision <= storedRevision:
    ignore
elif storedState == FINAL:
    reject mutation
else:
    replace same segmentId
```

UI는 `PARTIAL`을 임시 영역에서 교체하고, `FINAL`만 확정 Transcript Store(녹취 저장소)에 Append(추가)합니다.

```text
[FINAL]   이번 배포 일정은 금요일입니다.
[PARTIAL] 다음 주 점검 항목은...
```

Partial을 Database에 새 행으로 계속 추가하면 “이번 배포”, “이번 배포 일정”, “이번 배포 일정은”처럼 같은 발화가 중복 저장됩니다.

## 8. 안정된 Prefix를 합의한 뒤 Final로 이동한다

실시간 Whisper 구현에서는 같은 Audio Window를 새 음성과 함께 반복 추론할 수 있습니다. 이때 매번 전체 문장이 조금씩 달라질 수 있습니다.

Whisper-Streaming은 LocalAgreement-n(연속 결과 합의) 정책을 사용합니다. 새 Audio가 추가된 연속 추론 결과들이 같은 Prefix에 동의하면 그 부분을 확정합니다.

예를 들어 두 번의 연속 결과를 비교할 수 있습니다.

```text
update 1: "이번 배포 일정은 금"
update 2: "이번 배포 일정은 금요일"
common:   "이번 배포 일정은 금"
```

단어 단위 Timestamp(타임스탬프)가 있다면 문자열만 비교하는 것보다 안전합니다.

```python
def stable_prefix(previous_words, current_words):
    committed = []

    for prev, curr in zip(previous_words, current_words):
        same_text = normalize(prev.text) == normalize(curr.text)
        close_time = abs(prev.end_ms - curr.end_ms) <= ALLOWED_DRIFT_MS

        if not (same_text and close_time):
            break

        committed.append(curr)

    return committed
```

다만 연속 결과 합의만으로 즉시 문장 전체를 Final로 만들지는 않습니다. 다음 신호를 조합합니다.

- VAD가 충분한 침묵을 감지
- 모델이 Segment 종료 Timestamp를 반환
- 안정된 Prefix가 여러 Revision에서 유지
- 최대 발화 길이에 도달
- 사용자가 녹음을 종료
- 연결 종료 시 남은 Buffer를 Flush(마지막 처리)

Finalization(확정 처리)은 Accuracy(정확도)와 Latency(지연)의 Trade-off(상충 관계)입니다. 한국어 조사나 문장 끝 표현은 뒤 Audio에서 바뀔 수 있으므로 실제 회의 자료로 임계값을 조정해야 합니다.

## 9. 시간축은 Browser Clock이 아니라 Audio Frame에서 계산한다

자막 시간은 Message 도착 시각으로 만들지 않습니다. Network 지연과 재전송 때문에 도착 순서는 Audio 순서와 다를 수 있습니다.

기준 시간은 누적 Audio Frame입니다.

```text
audioTimeMs = cumulativeFrames / sampleRate × 1000
```

필요한 시간축을 분리합니다.

| 시간 | 의미 |
|---|---|
| `capturedAtMs` | Stream 시작 이후 Audio가 캡처된 위치 |
| `receivedAt` | Server가 Chunk를 받은 Wall Clock |
| `inferenceStartedAt` | 모델 처리 시작 시각 |
| `emittedAt` | 자막 Message를 만든 시각 |
| `renderedAt` | Client가 화면에 표시한 시각 |

이 값을 연결하면 어디에서 지연이 생겼는지 구분할 수 있습니다.

```text
networkDelay    = receivedAt - capturedWallTime
queueDelay      = inferenceStartedAt - receivedAt
inferenceDelay  = emittedAt - inferenceStartedAt
deliveryDelay   = renderedAt - emittedAt
```

Wall Clock이 다른 장치 사이에서는 Clock Skew(시계 오차)가 있으므로 한 방향 Timestamp만 빼서 절대 Network 지연이라고 단정하지 않습니다. Server 수신 간격, Client 측 측정 또는 시간 동기화된 Trace를 함께 사용합니다.

## 10. 환각 억제는 VAD 하나가 아니라 여러 Gate로 구성한다

STT Hallucination(음성 근거가 없는 문장 생성)은 Text가 자연스러워 보여 더 위험합니다. 특히 침묵, 긴 비음성 구간, 음악, 반복 Noise와 불완전한 Audio Window에서 발생할 수 있습니다.

한 가지 Threshold(임계값)로 완전히 막을 수 없으므로 다층 방어로 구성합니다.

```text
Input Gate
  → Signal Gate
  → VAD Gate
  → Decoder Gate
  → Stability Gate
  → Output Policy
```

### Input Gate

- 지원하는 Sample Rate·Channel·Encoding만 허용
- 지나치게 작은 Payload와 손상된 Frame 거부
- Sequence 유실률이 높은 구간 표시
- Stream 재연결 뒤 이전 Decoder Context를 무조건 이어 붙이지 않음

### Signal Gate

- RMS·Peak·Clipping 비율 측정
- 완전 무음과 DC Offset 탐지
- 지나치게 낮은 Signal-to-Noise Ratio는 품질 낮음으로 표시
- Echo Cancellation 사용 여부와 장치별 품질을 별도 관찰

### VAD Gate

VAD(Voice Activity Detection, 음성 활동 감지)는 추론 전 비음성 구간을 줄이고 발화 경계를 찾는 데 사용합니다.

`faster-whisper`는 Silero VAD를 통합하며 `vad_filter`와 `min_silence_duration_ms` 같은 Parameter(매개변수)를 제공합니다.

```python
segments, info = model.transcribe(
    audio,
    language="ko",
    vad_filter=True,
    vad_parameters={
        "min_silence_duration_ms": 500
    },
    word_timestamps=True
)
```

이 숫자는 시작 예시일 뿐 운영 권장값이 아닙니다. 너무 공격적인 VAD는 짧은 대답, 문장 첫 음절과 낮은 음량의 발화를 잘라낼 수 있습니다.

### Decoder Gate

Whisper와 `faster-whisper`에는 다음 신호와 Option(선택 항목)이 있습니다.

- `no_speech_threshold`: 비음성 가능성이 높은 구간 판단
- `log_prob_threshold`: 평균 Token 확률이 낮은 결과 판단
- `compression_ratio_threshold`: 반복적인 출력 감지
- `condition_on_previous_text`: 이전 결과를 다음 Window 문맥으로 사용할지 결정
- `hallucination_silence_threshold`: 의심되는 환각 주변의 긴 침묵 건너뛰기
- `suppress_tokens`: 특정 비음성 Token 억제

`condition_on_previous_text=false`는 반복 Failure Loop(실패 반복)에 빠질 가능성을 낮출 수 있지만 Window 간 문장 일관성이 줄 수 있습니다. 전체 Stream에 하나의 고정값을 적용하기보다 반복 탐지나 재연결 시 Context를 Reset(초기화)하는 정책도 고려할 수 있습니다.

### Stability Gate

- 한 번만 나타난 Partial을 Final로 저장하지 않음
- 연속 Revision에서 합의된 Prefix 확인
- 매우 짧은 비음성 구간의 긴 문장 거부
- 낮은 확률·높은 반복률·긴 무음이 함께 나타나면 보류
- Timestamp가 역행하거나 비정상적으로 긴 단어가 이어지면 재처리

### Output Policy

- 확신이 낮은 구간은 빈 문자열 대신 `인식 불확실` 상태로 표현
- 삭제한 결과의 이유 Code를 기록
- 업무 자동화와 AI 요약에는 `FINAL`만 전달
- 원 Audio와 검토 가능한 Timestamp를 연결
- Denylist(차단 문구 목록)는 반복되는 알려진 문구를 막는 최후 방어로만 사용

Denylist만 사용하면 새로운 환각 문구를 막지 못하고 실제 발화까지 삭제할 수 있습니다. VAD, Decoder 신호, 반복 탐지와 Audio 근거를 함께 사용해야 합니다.

## 11. 한국어 품질은 고유명사와 문장 경계를 따로 조정한다

한국어 회의에는 사람 이름, 제품명, 영문 약어와 숫자가 자주 등장합니다. 일반 모델 설정만으로 모두 안정적으로 인식되지는 않습니다.

권장 순서는 다음과 같습니다.

1. Audio 품질과 Format 오류를 먼저 제거합니다.
2. 언어를 알고 있다면 `language="ko"`처럼 명시합니다.
3. 공개 가능한 도메인 용어만 Hotwords(우선 인식 단어) 또는 Prompt에 제한적으로 제공합니다.
4. 같은 발음의 고유명사 치환은 사후 Dictionary(용어 사전)에서 추적 가능하게 처리합니다.
5. Partial에는 과도한 문장부호 후처리를 적용하지 않습니다.
6. Final 이후 맞춤법·문장 분리를 별도 단계로 실행합니다.

Prompt에 긴 회의 요약이나 이전 Transcript 전체를 계속 넣으면 잘못된 문구가 다음 Window로 증폭될 수 있습니다.

```text
좋은 Context
- 짧은 언어 힌트
- 제한된 용어 목록
- 최근의 확정된 문장 일부

피해야 할 Context
- 아직 바뀔 수 있는 Partial 전체
- 사용자 비밀정보
- 이전 오류 문장을 무제한 누적
- 실제로 발화되지 않은 목표 문장
```

문장 교정 결과와 원본 STT는 별도 필드로 보존합니다.

```json
{
  "rawText": "다음주 금요일 배포 입니다",
  "displayText": "다음 주 금요일 배포입니다.",
  "normalizationVersion": "public-rule-v1"
}
```

## 12. 느린 연결에서는 오래된 음성을 무제한 쌓지 않는다

실시간 전송 Queue가 증가하면 사용자는 현재 발화를 말하고 있는데 Server는 몇 초 전 Audio를 처리하게 됩니다.

WebSocket은 전송 대기 Byte를 `bufferedAmount`로 확인할 수 있습니다. Application은 임계치를 넘을 때 정책을 가져야 합니다.

```javascript
const MAX_BUFFERED_BYTES = 512 * 1024;

function sendAudio(socket, payload) {
  if (socket.readyState !== WebSocket.OPEN) {
    return { accepted: false, reason: "socket_not_open" };
  }

  if (socket.bufferedAmount > MAX_BUFFERED_BYTES) {
    return { accepted: false, reason: "backpressure" };
  }

  socket.send(payload);
  return { accepted: true };
}
```

Backpressure(처리 지연 압력) 발생 시 선택지는 서비스 목적에 따라 다릅니다.

| 목적 | 가능한 정책 |
|---|---|
| 실시간 자막 우선 | 오래된 미전송 Partial Audio를 제한하고 최신성 회복 |
| 완전한 회의록 우선 | 로컬 Buffer·서버 녹화를 유지하고 자막 지연 표시 |
| 두 목적 모두 | 실시간 경로와 무손실 녹화 경로 분리 |

무조건 Audio를 버리면 회의록이 손실되고, 무조건 쌓으면 실시간성이 사라집니다. Drop Policy(버림 정책)를 제품 요구사항으로 명시해야 합니다.

재연결할 때는 새 `streamId` 또는 `epoch`을 발급하고, 마지막으로 Server가 확인한 `sequence`를 기준으로 복구합니다. 오래된 연결에서 늦게 도착한 Partial이 새 Final을 덮어쓰지 못하도록 합니다.

## 13. 자막 저장은 상태 전이와 멱등성을 가져야 한다

권장 상태 전이는 단순합니다.

```text
PARTIAL(revision 1)
  → PARTIAL(revision 2)
  → PARTIAL(revision N)
  → FINAL
```

허용하지 않는 전이는 다음과 같습니다.

```text
FINAL → PARTIAL
FINAL → 다른 Text로 수정
낮은 revision → 높은 revision 덮어쓰기
다른 streamId → 같은 segmentId 갱신
```

저장 Key는 다음 조합을 사용할 수 있습니다.

```text
(tenantScope, meetingId, streamId, segmentId)
```

쓰기 조건은 `incomingRevision > storedRevision`으로 제한합니다. 같은 Message가 재전송돼도 결과가 변하지 않는 Idempotency(멱등성)가 필요합니다.

업무 Pipeline에는 확정 Event만 발행합니다.

```json
{
  "eventType": "transcript.finalized",
  "eventId": "opaque-event-id",
  "streamId": "opaque-stream-id",
  "segmentId": "segment-42",
  "revision": 8,
  "startMs": 38120,
  "endMs": 41640
}
```

AI 요약, 검색 Index와 업무 자동화가 Partial까지 소비하면 수정될 문장이 후속 시스템에 중복 반영됩니다.

## 14. 지연과 정확도는 같은 Dashboard에서 본다

실시간 STT 운영 지표는 평균 응답 시간 하나로 부족합니다.

### Audio 입력

- 실제 Sample Rate·Channel 분포
- Sequence Gap(순번 누락)과 중복률
- 입력 대비 출력 Frame Drift
- Clipping·무음·낮은 음량 비율
- Reconnect(재연결) 횟수

### 처리 성능

- Capture-to-Server 지연
- Queue 대기 시간
- Inference 시간과 Real-time Factor(실시간 대비 처리 비율)
- GPU Memory·사용률
- Stream당 Rolling Window 길이

### 자막 상태

- 첫 Partial까지 걸린 시간
- Partial Revision 수
- Partial 변경률
- Final 확정 지연
- Final 이후 수정 시도 수
- Timestamp 역행·중복 Segment 수

### 품질과 환각

- VAD로 제거된 Audio 비율
- `no_speech`·낮은 Log Probability로 거부된 Segment
- 반복 문구 탐지 수
- Context Reset 횟수
- 사용자 수정률
- 원 Audio가 없는 Final 발생 수

Metric에는 실제 발화 Text, 사람 이름과 회의 제목을 Label로 넣지 않습니다. `modelVersion`, `language`, `deviceClass`, `failureReason`처럼 집계 가능한 비민감 차원을 사용합니다.

## 15. 테스트는 녹음 파일 재생과 실제 브라우저를 모두 사용한다

고정 Audio Fixture(검증용 음성)를 사용하면 같은 입력으로 Regression Test(회귀 테스트)를 반복할 수 있습니다. 그러나 그것만으로 Microphone, AudioWorklet, Network와 장치 차이를 검증할 수는 없습니다.

두 계층을 함께 운영합니다.

| 계층 | 검증 대상 |
|---|---|
| 결정적 Audio Test | 리샘플링, Frame 수, Timestamp, Partial 병합, 환각 규칙 |
| Browser E2E Test | 권한, 실제 Sample Rate, Worklet, Network, UI와 재연결 |

필수 Test Matrix(테스트 조합)는 다음과 같습니다.

| 입력·상황 | 확인 결과 |
|---|---|
| 48kHz Mono 음성 | 16kHz 변환 후 시간 Drift 없음 |
| 44.1kHz 입력 | 비정수 비율 리샘플링 정상 |
| Stereo 입력 | 정의된 Mono Downmix 적용 |
| 완전 무음 | Final 문장 생성 안 됨 |
| 배경 음악·반복 Noise | 비음성 Gate와 낮은 확신 처리 |
| 매우 짧은 대답 | VAD가 발화를 과도하게 제거하지 않음 |
| 긴 발화 | Window Trim 후 중복·누락 없음 |
| 네트워크 지연·순서 역전 | Sequence로 탐지하고 복구 |
| 연결 종료 | 남은 Buffer Flush 후 하나의 Final |
| 재연결 | 이전 Partial이 새 Stream을 덮어쓰지 않음 |
| 같은 Message 재전송 | 같은 Revision이 중복 저장되지 않음 |
| 고유명사·숫자 | 제한된 용어 Context와 원문 보존 |

정확도 평가는 WER(Word Error Rate, 단어 오류율) 또는 CER(Character Error Rate, 문자 오류율)만 보지 않습니다. 실시간 자막에서는 다음도 사용자 경험에 직접 영향을 줍니다.

- 첫 Partial 지연
- Final 지연
- 화면에서 바뀐 글자 수
- 누락·중복 Segment
- 무음 환각
- 화자 전환 정확성

## 운영 전 점검 체크리스트

| 점검 영역 | 확인 질문 |
|---|---|
| 실제 입력 | `getSettings()`와 `audioContext.sampleRate`를 기록하는가 |
| Audio Contract | Rate·Channel·Encoding·Frame 수가 명시돼 있는가 |
| Worklet | Callback 길이를 고정값으로 가정하지 않는가 |
| 리샘플링 | Anti-alias Filter와 Streaming State가 있는가 |
| 시간 Drift | 누적 입력·출력 Frame을 비교하는가 |
| Encoding | Float32·PCM16·Endian 변환을 검증하는가 |
| Buffer | Capture·Transport·Inference 단위가 분리돼 있는가 |
| 시간축 | Audio Frame 기준 Timestamp를 사용하는가 |
| Partial | 같은 Segment를 Revision으로 교체하는가 |
| Final | 확정 뒤 변경을 막는가 |
| 합의 | 연속 결과의 안정된 Prefix를 확인하는가 |
| Endpoint | VAD·Timestamp·종료·Timeout 기준이 있는가 |
| 환각 | VAD·Decoder·Stability·Output Gate를 함께 쓰는가 |
| Context | Partial과 오류 문장을 무제한 누적하지 않는가 |
| Backpressure | 전송 Queue의 상한과 Drop·보존 정책이 있는가 |
| 재연결 | Stream Epoch과 Sequence로 오래된 결과를 차단하는가 |
| 후속 처리 | 요약·검색·자동화가 Final만 소비하는가 |
| 관측성 | 지연·정확도·환각 지표를 함께 보는가 |
| 개인정보 | 실제 발화 Text를 Metric Label과 일반 Log에 넣지 않는가 |
| 검증 | 고정 Audio와 실제 Browser E2E를 모두 수행하는가 |

## 마무리

실시간 STT의 문제는 “브라우저 음성을 Whisper에 보내는 것”보다 넓습니다. **서로 다른 시간과 상태를 가진 Audio, Model Hypothesis(모델 가설), Network Message와 화면 자막을 하나의 일관된 흐름으로 만드는 문제**입니다.

운영 가능한 실시간 자막을 위해서는 다음 원칙이 필요합니다.

1. 요청한 Sample Rate가 아니라 실제 Track과 AudioContext Rate를 확인합니다.
2. Model Boundary에서 Sample Rate·Channel·Encoding을 명시적으로 정규화합니다.
3. `48kHz → 16kHz` 변환에 Anti-alias Filter와 Streaming State를 사용합니다.
4. Capture Block, Transport Chunk와 Inference Window를 분리합니다.
5. Partial은 Revision으로 교체하고 Final만 영구 저장합니다.
6. 연속 추론의 안정된 Prefix와 발화 종료 신호를 조합합니다.
7. Audio Frame을 기준으로 Timestamp와 지연을 계산합니다.
8. VAD, Decoder 신호, 반복 탐지와 Context Reset으로 환각을 다층 억제합니다.
9. Backpressure와 재연결에서도 Sequence와 Stream 경계를 보존합니다.
10. 지연·변경률·누락·무음 환각을 실제 Browser E2E에서 함께 검증합니다.

실시간 자막은 가장 빨리 나온 문장을 보여 주는 기능이 아닙니다. 바뀔 수 있는 결과와 확정된 결과를 구분하고, Audio 근거가 없는 문장이 후속 시스템으로 넘어가지 않도록 통제하는 운영 Pipeline입니다.

다음 글에서는 STT로 확정된 Transcript를 RAG에 반영할 때 같은 회의와 Chunk가 중복 Indexing(색인)되지 않도록 Idempotency Key(멱등성 키), Content Hash(내용 해시)와 Version을 설계하는 방법을 살펴보겠습니다.

---

## 참고 자료

- [W3C Media Capture and Streams](https://www.w3.org/TR/mediacapture-streams/)
- [W3C Web Audio API 1.1](https://www.w3.org/TR/webaudio-1.1/)
- [WHATWG WebSockets Standard](https://websockets.spec.whatwg.org/)
- [OpenAI Whisper: Audio preprocessing](https://github.com/openai/whisper/blob/main/whisper/audio.py)
- [OpenAI Whisper: Transcription logic](https://github.com/openai/whisper/blob/main/whisper/transcribe.py)
- [faster-whisper README: Word timestamps and VAD](https://github.com/SYSTRAN/faster-whisper/blob/master/README.md)
- [faster-whisper Transcription options](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)
- [faster-whisper VAD options](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/vad.py)
- [SciPy: Polyphase resampling](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html)
- [Google Cloud Speech-to-Text: StreamingRecognitionResult](https://cloud.google.com/speech-to-text/v2/docs/reference/rest/v2/StreamingRecognitionResult)
- [Whisper-Streaming: Local Agreement policy](https://github.com/ufal/whisper_streaming)
- [Careless Whisper: Speech-to-Text Hallucination Harms](https://arxiv.org/abs/2402.08021)

> 이 글은 2026년 7월 29일 기준 공개된 Web Audio·Media Capture·Whisper·faster-whisper·Streaming STT 문서와 공개 가능한 실시간 STT·WebRTC 검증 경험을 바탕으로 작성했습니다. 구체적인 Chunk 크기, VAD와 Decoder 임계값은 모델 버전, 언어, 장치, 소음 환경과 지연 목표에 따라 실제 Audio Dataset으로 다시 측정해야 합니다.
