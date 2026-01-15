# Design Document: Voice Practice Module Optimization

## Overview

This design document describes the technical implementation for optimizing the voice practice module. The optimization focuses on six key areas:

1. **AudioWorklet Migration** - Moving audio processing from the deprecated ScriptProcessorNode to AudioWorklet for non-blocking, low-latency audio capture
2. **Streaming TTS Playback** - Implementing MediaSource API-based streaming to reduce first-byte latency from 2-5s to <500ms
3. **Complete Interruption Handling** - Building a full interrupt chain that stops TTS, cancels LLM/TTS tasks, and transitions state within 100ms
4. **Backpressure Control** - Adding bounded queues with flow control signals to prevent memory overflow
5. **High-Quality Resampling** - Using OfflineAudioContext for better 48kHz→16kHz conversion
6. **Performance Monitoring** - Adding latency metrics for debugging and optimization

The design maintains backward compatibility through graceful degradation when modern APIs are unavailable.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (Next.js)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────┐    ┌─────────────────────────────────────┐    │
│  │   AudioWorklet      │    │     Streaming Audio Player          │    │
│  │   Processor         │    │     (MediaSource API)               │    │
│  │   ┌─────────────┐   │    │     ┌─────────────────────────┐     │    │
│  │   │ Separate    │   │    │     │ SourceBuffer Queue      │     │    │
│  │   │ Thread      │   │    │     │ Chunk Append Logic      │     │    │
│  │   │ Processing  │   │    │     │ Playback State Mgmt     │     │    │
│  │   └─────────────┘   │    │     └─────────────────────────┘     │    │
│  └──────────┬──────────┘    └──────────────────┬──────────────────┘    │
│             │ postMessage                       │ appendBuffer          │
│             ▼                                   ▼                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                  usePracticeWebSocket Hook                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │ Audio Send  │  │ Interrupt   │  │ Backpressure Response   │  │   │
│  │  │ Rate Ctrl   │  │ Handler     │  │ Handler                 │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │ WebSocket                               │
└──────────────────────────────┼─────────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Backend (FastAPI)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                  EnhancedSalesHandler                            │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   │
│  │  │ Bounded ASR     │  │ Interrupt       │  │ Streaming TTS   │  │   │
│  │  │ Queue (100)     │  │ Coordinator     │  │ Sender          │  │   │
│  │  │ + Backpressure  │  │ (Cancel Tasks)  │  │ (Chunked)       │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ ASR Service │  │ LLM Service │  │ TTS Service │  │ Metrics     │   │
│  │ (Alibaba)   │  │ (OpenAI)    │  │ (Edge-TTS)  │  │ Collector   │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Interrupt Flow Architecture

```
User Starts Speaking
        │
        ▼
┌───────────────────┐
│ Frontend Detects  │
│ (VAD or Button)   │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     ┌───────────────────┐
│ Stop TTS Playback │────▶│ Clear Audio Queue │
│ (Immediate)       │     │                   │
└─────────┬─────────┘     └───────────────────┘
          │
          ▼
┌───────────────────┐
│ Send "interrupt"  │
│ via WebSocket     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Backend Receives  │
│ Interrupt Signal  │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌───────┐  ┌───────┐
│Cancel │  │Cancel │
│LLM    │  │TTS    │
│Task   │  │Task   │
└───┬───┘  └───┬───┘
    │          │
    └────┬─────┘
         ▼
┌───────────────────┐
│ Send "interrupted"│
│ Confirmation      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Transition to     │
│ "listening" State │
└───────────────────┘
```

### Backpressure Flow

```
Audio Chunks Arriving
        │
        ▼
┌───────────────────────────────────────┐
│         ASR Queue (max: 100)          │
│  ┌─────────────────────────────────┐  │
│  │ [chunk][chunk][chunk]...        │  │
│  │                                 │  │
│  │  0%────50%────80%────100%       │  │
│  │         │      │       │        │  │
│  │      Normal  Warning  Drop      │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
        │
        ├── < 50%: Normal operation
        │
        ├── 50-80%: All clear (if recovering)
        │
        ├── 80-100%: Send warning to frontend
        │
        └── 100%: Drop chunk + send critical signal
                         │
                         ▼
              ┌─────────────────────┐
              │ Frontend reduces    │
              │ send rate (2x)      │
              └─────────────────────┘
```

## Components and Interfaces

### Frontend Components

#### 1. AudioWorkletProcessor (audio-worklet-processor.js)

A Web Worker-like processor that runs in a separate audio thread.

```typescript
// public/audio-worklet-processor.js
interface AudioWorkletProcessorOptions {
  bufferSize: number;  // Default: 1024 samples (~21ms at 48kHz)
}

interface AudioProcessorMessage {
  type: 'audio';
  buffer: Float32Array;
  timestamp: number;
}

class AudioProcessor extends AudioWorkletProcessor {
  constructor(options?: AudioWorkletProcessorOptions);
  process(inputs: Float32Array[][], outputs: Float32Array[][], parameters: Record<string, Float32Array>): boolean;
}
```

#### 2. useAudioRecorder Hook (Enhanced)

```typescript
// web/src/hooks/use-audio-recorder.ts
interface AudioRecorderConfig {
  sampleRate: number;           // Target: 16000
  bufferSize: number;           // Default: 1024
  useWorklet: boolean;          // Default: true (with fallback)
}

interface AudioRecorderState {
  isRecording: boolean;
  isWorkletSupported: boolean;
  audioLevel: number;           // 0-1 for visualization
}

interface UseAudioRecorderReturn {
  state: AudioRecorderState;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  onAudioData: (callback: (base64: string) => void) => void;
}

function useAudioRecorder(config?: AudioRecorderConfig): UseAudioRecorderReturn;
```

#### 3. useStreamingAudioPlayer Hook (New)

```typescript
// web/src/hooks/use-streaming-audio-player.ts
interface StreamingAudioPlayerState {
  isPlaying: boolean;
  isBuffering: boolean;
  currentTime: number;
  duration: number;
}

interface StreamingAudioPlayer {
  state: StreamingAudioPlayerState;
  start: () => void;
  appendChunk: (chunk: ArrayBuffer) => void;
  end: () => void;
  stop: () => void;
  isSupported: () => boolean;
}

function useStreamingAudioPlayer(): StreamingAudioPlayer;
```

#### 4. usePracticeWebSocket Hook (Enhanced)

```typescript
// web/src/hooks/use-practice-websocket.ts (additions)
interface BackpressureState {
  level: 'normal' | 'warning' | 'critical';
  queueSize: number;
  maxSize: number;
}

interface PracticeWebSocketState {
  // ... existing fields
  backpressure: BackpressureState;
  audioSendInterval: number;  // ms between sends, adjustable
}

// New message handlers
type IncomingMessage = 
  | { type: 'tts_chunk'; data: TTSChunkData }
  | { type: 'interrupted'; data: { reason: string } }
  | { type: 'backpressure'; data: BackpressureData }
  // ... existing types
```

### Backend Components

#### 1. EnhancedSalesHandler (Enhanced)

```python
# backend/src/sales_bot/websocket/enhanced_handler.py
class EnhancedSalesHandler(BaseWebSocketHandler):
    # Queue configuration
    ASR_QUEUE_MAX_SIZE: int = 100
    ASR_QUEUE_HIGH_WATERMARK: int = 80
    ASR_QUEUE_LOW_WATERMARK: int = 50
    
    # Task references for cancellation
    _llm_task: Optional[asyncio.Task] = None
    _tts_task: Optional[asyncio.Task] = None
    
    async def _handle_interrupt(self, data: dict) -> None:
        """Handle user interruption with full task cancellation."""
        
    async def _handle_audio_chunk(self, data: dict) -> None:
        """Handle audio chunk with backpressure control."""
        
    async def _send_tts_response_streaming(self, text: str) -> None:
        """Send TTS audio in streaming chunks."""
        
    async def _send_backpressure_signal(self, level: str, queue_size: int) -> None:
        """Send backpressure signal to frontend."""
```

#### 2. TTS Service (Enhanced)

```python
# backend/src/common/audio/tts_service.py
class TTSService:
    async def synthesize_streaming(
        self, 
        text: str,
        on_chunk: Callable[[bytes, int], Awaitable[None]]
    ) -> Result[int]:
        """
        Synthesize text to speech with streaming output.
        
        Args:
            text: Text to synthesize
            on_chunk: Callback for each audio chunk (chunk_bytes, chunk_index)
            
        Returns:
            Result containing total duration in ms
        """
```

### WebSocket Message Types (New/Modified)

#### TTS Chunk Message (New)

```typescript
interface TTSChunkMessage {
  type: 'tts_chunk';
  timestamp: string;
  trace_id: string;
  data: {
    chunk_index: number;
    audio: string;        // Base64 encoded MP3 chunk
    duration_ms: number;
    is_final: boolean;
    text?: string;        // Only on final chunk
    total_duration_ms?: number;  // Only on final chunk
  };
}
```

#### Interrupt Message (Enhanced)

```typescript
// Outgoing (frontend → backend)
interface InterruptMessage {
  type: 'interrupt';
  data: {
    reason: 'user_speaking' | 'manual';
    timestamp: number;
  };
}

// Incoming (backend → frontend)
interface InterruptedMessage {
  type: 'interrupted';
  timestamp: string;
  data: {
    reason: string;
  };
}
```

#### Backpressure Message (New)

```typescript
interface BackpressureMessage {
  type: 'backpressure';
  timestamp: string;
  data: {
    level: 'warning' | 'critical' | 'normal';
    queue_size: number;
    max_size: number;
    action?: 'slow_down' | 'resume';
  };
}
```

## Data Models

### Frontend State Models

```typescript
// Audio recording state
interface AudioRecordingMetrics {
  captureLatencyMs: number;      // Time from mic to WebSocket send
  workletProcessingMs: number;   // Time in AudioWorklet
  resamplingMs: number;          // Time for resampling
}

// TTS playback state
interface TTSPlaybackMetrics {
  firstByteLatencyMs: number;    // Time from request to first chunk
  totalChunks: number;
  bufferedDurationMs: number;
}

// Interrupt metrics
interface InterruptMetrics {
  detectionToStopMs: number;     // Time from detection to TTS stop
  roundTripMs: number;           // Time to receive 'interrupted' confirmation
}
```

### Backend State Models

```python
# backend/src/sales_bot/websocket/models.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class ASRQueueMetrics:
    current_size: int
    max_size: int
    high_watermark: int
    low_watermark: int
    chunks_dropped: int
    last_warning_time: Optional[datetime]

@dataclass
class InterruptState:
    is_interrupted: bool
    interrupt_reason: Optional[str]
    interrupt_time: Optional[datetime]
    llm_cancelled: bool
    tts_cancelled: bool

@dataclass
class StreamingTTSState:
    is_streaming: bool
    current_chunk_index: int
    total_chunks_sent: int
    total_duration_ms: int
    start_time: Optional[datetime]
```

### Performance Metrics Schema

```python
# backend/src/common/monitoring/metrics.py
from prometheus_client import Histogram, Counter, Gauge

# Audio capture metrics
audio_capture_latency = Histogram(
    'voice_practice_audio_capture_latency_ms',
    'Audio capture latency in milliseconds',
    buckets=[10, 20, 30, 50, 100, 200]
)

# TTS streaming metrics
tts_first_byte_latency = Histogram(
    'voice_practice_tts_first_byte_latency_ms',
    'TTS first byte latency in milliseconds',
    buckets=[100, 200, 300, 500, 1000, 2000]
)

# Interrupt metrics
interrupt_response_time = Histogram(
    'voice_practice_interrupt_response_ms',
    'Interrupt response time in milliseconds',
    buckets=[50, 100, 150, 200, 300]
)

# Backpressure metrics
asr_queue_size = Gauge(
    'voice_practice_asr_queue_size',
    'Current ASR queue size'
)

backpressure_events = Counter(
    'voice_practice_backpressure_events_total',
    'Total backpressure events',
    ['level']  # warning, critical
)
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: AudioWorklet Usage for Recording

*For any* recording session initiated by the user on a browser that supports AudioWorklet, the Audio_Recorder SHALL create and connect an AudioWorkletNode (not ScriptProcessorNode) for audio processing.

**Validates: Requirements 1.1**

### Property 2: AudioWorklet Communication

*For any* audio buffer processed by the AudioWorklet, the processor SHALL send the data to the main thread via postMessage with type 'audio' and a Float32Array buffer.

**Validates: Requirements 1.5**

### Property 3: TTS Streaming Message Format

*For any* TTS generation request, the backend SHALL:
- Send multiple tts_chunk messages before the final message
- Include chunk_index (incrementing from 0) and duration_ms in each chunk
- Set is_final=true only on the last chunk, which also includes the full text

**Validates: Requirements 2.1, 2.4, 2.6**

### Property 4: Streaming Playback Initialization

*For any* TTS streaming session, when the frontend receives a chunk with chunk_index=0, the Streaming_Audio_Player SHALL immediately initialize playback (call audio.play()) without waiting for subsequent chunks.

**Validates: Requirements 2.2**

### Property 5: MediaSource Buffer Appending

*For any* TTS chunk received (where is_final=false), the Streaming_Audio_Player SHALL call SourceBuffer.appendBuffer() with the decoded audio data.

**Validates: Requirements 2.3**

### Property 6: Interrupt Stops Playback

*For any* interrupt triggered while TTS audio is playing, the frontend SHALL stop audio playback (audio.pause() and clear src) within the same event loop tick as the interrupt detection.

**Validates: Requirements 3.1**

### Property 7: Interrupt Queue Clearing

*For any* interrupt event, the frontend SHALL clear the audio chunk queue before sending the interrupt message to the backend.

**Validates: Requirements 3.2**

### Property 8: Interrupt Task Cancellation

*For any* interrupt signal received by the backend, if there are in-progress LLM or TTS tasks, they SHALL be cancelled (task.cancel() called).

**Validates: Requirements 3.3, 3.4**

### Property 9: Interrupt Confirmation

*For any* interrupt signal successfully processed by the backend, an "interrupted" message SHALL be sent back to the frontend with the interrupt reason.

**Validates: Requirements 3.5**

### Property 10: Interrupt State Transition Timing

*For any* interrupt event, the time from interrupt detection to "listening" state transition SHALL be less than 100ms.

**Validates: Requirements 3.6**

### Property 11: Backpressure Signaling

*For any* ASR queue state:
- When queue size >= 80 (80% of max), a "warning" level backpressure message SHALL be sent
- When queue size = 100 (full), incoming chunks SHALL be dropped and a "critical" level message SHALL be sent
- When queue size drops below 50 after being >= 80, a "normal" level message SHALL be sent

**Validates: Requirements 4.2, 4.3, 4.5**

### Property 12: Frontend Backpressure Response

*For any* "critical" level backpressure message received, the frontend SHALL increase the audio send interval (reduce send rate) by at least 2x.

**Validates: Requirements 4.4**

### Property 13: High-Quality Resampling

*For any* audio resampling operation on a browser that supports OfflineAudioContext, the Resampler SHALL use OfflineAudioContext.startRendering() for the conversion.

**Validates: Requirements 5.1**

### Property 14: Resampling Output Format

*For any* resampled audio output, the result SHALL be 16-bit signed PCM at exactly 16000 Hz sample rate.

**Validates: Requirements 5.3**

### Property 15: Binary Transmission Efficiency (Optional Feature)

*For any* audio data transmitted when binary mode is enabled:
- The WebSocket frame SHALL be binary (not text)
- The message SHALL have a 4-byte header (1 byte type + 3 bytes sequence)
- The total message size SHALL be approximately 25% smaller than the equivalent Base64-encoded JSON

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 16: Latency Threshold Alerting

*For any* latency metric that exceeds its configured threshold, the system SHALL emit a warning-level log entry containing the trace_id and the exceeded metric value.

**Validates: Requirements 7.4**

## Error Handling

### Frontend Error Handling

| Error Scenario | Detection | Handling | User Feedback |
|----------------|-----------|----------|---------------|
| AudioWorklet not supported | Feature detection on init | Fall back to ScriptProcessorNode | None (silent fallback) |
| MediaSource not supported | Feature detection on init | Fall back to buffered playback | None (silent fallback) |
| OfflineAudioContext not supported | Feature detection on init | Fall back to linear interpolation | Console warning |
| WebSocket disconnection | onclose event | Exponential backoff reconnect | Status indicator: "Reconnecting..." |
| Audio playback failure | Audio error event | Retry once, then show text | Display AI response as text |
| Microphone permission denied | getUserMedia rejection | Show permission guide | Inline permission card |

### Backend Error Handling

| Error Scenario | Detection | Handling | Frontend Notification |
|----------------|-----------|----------|----------------------|
| ASR service unavailable | Connection timeout | Return [USE_BROWSER_ASR] | Fallback signal in response |
| TTS service failure | Exception during synthesis | Return [USE_BROWSER_TTS] | Fallback signal in response |
| LLM timeout | asyncio.TimeoutError | Return predefined response | Normal response (degraded) |
| Queue overflow | Queue full check | Drop chunk, log warning | Backpressure signal |
| Task cancellation | CancelledError | Clean up resources | Interrupted confirmation |

### Error Recovery Flows

```
AudioWorklet Load Failure
    └─▶ Log warning
    └─▶ Set isWorkletSupported = false
    └─▶ Create ScriptProcessorNode instead
    └─▶ Continue with degraded latency

MediaSource Initialization Failure
    └─▶ Log warning
    └─▶ Set isStreamingSupported = false
    └─▶ Buffer complete audio before playback
    └─▶ Continue with higher first-byte latency

Backpressure Critical
    └─▶ Frontend receives signal
    └─▶ Double audio send interval
    └─▶ Wait for "normal" signal
    └─▶ Gradually restore send rate
```

## Testing Strategy

### Testing Approach

This feature requires both unit tests and property-based tests:

- **Unit tests**: Verify specific examples, edge cases, browser compatibility fallbacks, and error conditions
- **Property-based tests**: Verify universal properties across all valid inputs using randomized testing

### Property-Based Testing Configuration

- **Library**: fast-check (TypeScript/JavaScript), Hypothesis (Python)
- **Minimum iterations**: 100 per property test
- **Tag format**: `Feature: voice-practice-optimization, Property {number}: {property_text}`

### Frontend Tests

#### Unit Tests

| Test Case | Description | Requirements |
|-----------|-------------|--------------|
| AudioWorklet fallback | Verify ScriptProcessorNode is used when AudioWorklet unavailable | 1.2 |
| Buffer size configuration | Verify 1024 sample buffer size | 1.4 |
| MediaSource fallback | Verify buffered playback when MediaSource unavailable | 2.5 |
| Backpressure rate adjustment | Verify send interval doubles on critical signal | 4.4 |
| Resampling fallback | Verify linear interpolation when OfflineAudioContext unavailable | 5.2 |

#### Property Tests

| Property | Test Description | Generator |
|----------|------------------|-----------|
| P1 | AudioWorklet node creation | Random recording sessions |
| P2 | postMessage communication | Random audio buffers |
| P4 | Playback starts on first chunk | Random TTS sessions |
| P5 | SourceBuffer append calls | Random chunk sequences |
| P6 | Interrupt stops playback | Random interrupt timings |
| P7 | Queue cleared before signal | Random interrupt scenarios |
| P12 | Send rate reduction | Random backpressure signals |
| P13 | OfflineAudioContext usage | Random audio data |
| P14 | Output format verification | Random input audio |

### Backend Tests

#### Unit Tests

| Test Case | Description | Requirements |
|-----------|-------------|--------------|
| Queue max size | Verify ASR queue limited to 100 | 4.1 |
| Metrics collection | Verify latency metrics recorded | 7.1, 7.2, 7.3 |
| Metrics exposure | Verify Prometheus endpoint | 7.5 |
| Binary header format | Verify 4-byte header structure | 6.2 |

#### Property Tests

| Property | Test Description | Generator |
|----------|------------------|-----------|
| P3 | TTS chunk message format | Random text inputs |
| P8 | Task cancellation on interrupt | Random task states |
| P9 | Interrupt confirmation | Random interrupt reasons |
| P10 | State transition timing | Random system loads |
| P11 | Backpressure signaling | Random queue fill levels |
| P15 | Binary transmission size | Random audio payloads |
| P16 | Threshold alerting | Random latency values |

### Integration Tests

| Test Scenario | Description | Components |
|---------------|-------------|------------|
| Full interrupt flow | User interrupts during AI speech | Frontend + Backend |
| Streaming TTS playback | Complete TTS streaming session | Frontend + Backend + TTS |
| Backpressure recovery | System recovers from queue overflow | Frontend + Backend |
| Graceful degradation | All fallbacks work correctly | Frontend (mocked APIs) |

### Performance Tests

| Metric | Target | Test Method |
|--------|--------|-------------|
| Audio capture latency | <30ms | Timestamp comparison |
| TTS first-byte latency | <500ms | Request to first chunk |
| Interrupt response time | <100ms | Detection to state change |
| Memory under load | <50MB growth | Long session monitoring |
| Main thread blocking | 0ms | Chrome DevTools Performance |
