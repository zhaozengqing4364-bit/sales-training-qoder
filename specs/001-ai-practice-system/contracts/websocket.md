# WebSocket Protocol Specification

**Version**: 1.0.0
**Date**: 2025-01-10

## Overview

This document defines the WebSocket protocol for real-time voice interaction in the Enterprise AI Intelligent Practice System. The protocol supports full-duplex audio streaming and bidirectional interruption.

## Connection Endpoints

```
# PPT Presentation Coaching
ws://localhost:8000/ws/presentation?session_id={session_id}&token={jwt_token}

# Sales Practice Bot
ws://localhost:8000/ws/sales?session_id={session_id}&token={jwt_token}
```

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| session_id | UUID | Yes | Practice session ID |
| token | string | Yes | JWT authentication token |

## Message Format

All messages are JSON with the following structure:

```json
{
  "type": "message_type",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": { /* type-specific data */ }
}
```

### Message Types

| Direction | Type | Description |
|-----------|------|-------------|
| Client → Server | `audio_chunk` | Streaming audio data |
| Client → Server | `user_speaking` | User started/stopped speaking |
| Client → Server | `page_change` | User changed PPT page |
| Client → Server | `pause` | User paused session |
| Client → Server | `resume` | User resumed session |
| Server → Client | `asr_transcript` | Real-time transcription |
| Server → Client | `tts_audio` | AI speech audio |
| Server → Client | `interruption` | AI is interrupting |
| Server → Client | `status` | Session status update |
| Server → Client | `error` | Error notification (should not show to user) |

## Message Definitions

### Client → Server Messages

#### 1. audio_chunk

Streaming audio from client to server.

```json
{
  "type": "audio_chunk",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "audio": "base64_encoded_audio_data",
    "sequence": 123,
    "sample_rate": 16000
  }
}
```

**Constraints**:
- Audio format: PCM 16-bit, 16kHz mono
- Chunk size: ~200ms (3200 samples)
- `sequence` must be monotonically increasing

#### 2. user_speaking

Indicates user speaking state (for VAD).

```json
{
  "type": "user_speaking",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "speaking": true
  }
}
```

**Usage**:
- `speaking: true` when user starts talking
- `speaking: false` when user stops talking (triggers LLM response)

#### 3. page_change (Presentation only)

User navigated to a different PPT page.

```json
{
  "type": "page_change",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "page_number": 5
  }
}
```

**Server Response**:
```json
{
  "type": "status",
  "timestamp": "2025-01-10T10:30:01Z",
  "data": {
    "current_page": 5,
    "required_points": ["Must mention: proprietary technology"],
    "context": "Page 5 of presentation"
  }
}
```

#### 4. pause / resume

Session control.

```json
{
  "type": "pause",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {}
}
```

**Server Response**:
```json
{
  "type": "status",
  "timestamp": "2025-01-10T10:30:01Z",
  "data": {
    "session_status": "paused"
  }
}
```

### Server → Client Messages

#### 1. asr_transcript

Real-time transcription from ASR.

```json
{
  "type": "asr_transcript",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "text": "Hello everyone, today I want to talk about",
    "is_final": false,
    "confidence": 0.95
  }
}
```

**Behavior**:
- `is_final: false` - Partial result, still processing
- `is_final: true` - Final result, user finished sentence

#### 2. tts_audio

AI speech audio for playback.

```json
{
  "type": "tts_audio",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "audio": "base64_encoded_mp3",
    "text": "Please avoid saying 'I don't know'",
    "duration_ms": 2500
  }
}
```

**Client Behavior**:
1. Stop recording immediately
2. Play the audio
3. Show "AI Speaking" indicator
4. Resume recording after playback

#### 3. interruption

AI is interrupting the user.

```json
{
  "type": "interruption",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "reason": "forbidden_word",
    "trigger": "I don't know",
    "ai_message": "Please avoid saying 'I don't know'. Try 'Let me verify that' instead.",
    "interruption_latency_ms": 85
  }
}
```

**Interruption Reasons**:
- `forbidden_word` - User used forbidden phrase
- `missing_point` - User finished page without required point
- `vague_response` - User's response was too vague (sales bot)

#### 4. status

Session status update.

```json
{
  "type": "status",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "session_status": "in_progress",
    "ai_state": "listening",
    "current_page": 3,
    "interruption_count": 2
  }
}
```

**AI States**:
- `listening` - AI is waiting for user input
- `thinking` - AI is processing user input
- `speaking` - AI is responding to user

#### 5. error

Error notification (for logging, not user display).

```json
{
  "type": "error",
  "timestamp": "2025-01-10T10:30:00Z",
  "data": {
    "code": "ASR_TEMPORARY_FAILURE",
    "message": "ASR service unavailable, using browser fallback",
    "trace_id": "abc123",
    "user_action": "switch_to_browser_asr"
  }
}
```

**Client Behavior**:
- **DO NOT** show error to user
- Log `trace_id` for debugging
- Execute `user_action` if provided
- Show subtle status indicator if needed

## Connection Lifecycle

### 1. Connection Flow

```
Client                    Server
  |                         |
  |----- CONNECT ---------->|
  |                         |  1. Validate token
  |                         |  2. Load session
  |<---- ACK ---------------|
  |                         |
  |----- audio_chunk ------>|
  |----- audio_chunk ------>|
  |                         |  [ASR processing]
  |<-- asr_transcript ------|
  |<-- asr_transcript ------|
  |                         |
  |----- user_speaking ---->|  (false = user stopped)
  |                         |  [LLM processing]
  |<--- tts_audio ----------|
  |                         |
  |----- audio_chunk ------>|
  |                         |
  |--- interruption -------->|  (user interrupted AI)
  |                         |  [Stop TTS, start ASR]
  |<-- status (listening) ---|
```

### 2. Reconnection Flow (No Error Popup!)

```
Client                    Server
  |                         |
  |----- CONNECT ---------->|
  |                         |
  |<---- CLOSE (error) -----|  [Network hiccup]
  |                         |
  | [Buffer audio for 30s]  |
  |                         |
  |----- CONNECT ---------->|  [Exponential backoff]
  |<---- ACK ---------------|
  |                         |
  |----- RESEND_BUFFER ---->|  [Send buffered audio]
  |                         |  [Resume from last state]
  |<--- status (resumed) ---|
```

**Key Rules**:
1. **NEVER** show "Connection lost" error popup
2. Show subtle "Reconnecting..." indicator
3. Buffer locally for 30 seconds max
4. Resend buffered audio on reconnect
5. Resume session state from server

## Bidirectional Interruption Protocol

### User Interrupts AI

1. **AI Speaking**: Server sends `tts_audio`
2. **User Interrupts**: Client sends `audio_chunk` immediately
3. **Server Detects**: VAD detects user speech
4. **Stops TTS**: Server cancels ongoing TTS generation
5. **Switches to ASR**: Server processes user's new input

```json
// Client immediately sends audio when AI is speaking
{
  "type": "audio_chunk",
  "timestamp": "2025-01-10T10:30:05Z",
  "data": {
    "audio": "...",
    "interrupt": true  // Flag indicating interruption
  }
}

// Server responds by stopping TTS
{
  "type": "status",
  "timestamp": "2025-01-10T10:30:05Z",
  "data": {
    "ai_state": "listening",
    "interrupted": true
  }
}
```

### AI Interrupts User

1. **User Speaking**: Client sends `audio_chunk`
2. **Keyword Detected**: Server detects forbidden word
3. **Sends Interruption**: Server sends `interruption` message
4. **Stops Recording**: Client stops recording immediately
5. **Plays TTS**: Client plays AI response

```json
// Server detects forbidden word
{
  "type": "interruption",
  "timestamp": "2025-01-10T10:30:10Z",
  "data": {
    "reason": "forbidden_word",
    "ai_message": "Please avoid saying 'I don't know'"
  }
}

// Client stops recording, plays TTS
// User can interrupt back by sending audio_chunk
```

## Latency Tracking

Every message includes timestamps for latency monitoring:

```json
{
  "type": "interruption",
  "timestamp": "2025-01-10T10:30:10Z",
  "data": {
    "trigger_timestamp": "2025-01-10T10:30:09.915Z",  // When user said word
    "detection_timestamp": "2025-01-10T10:30:09.985Z", // When detected
    "interruption_latency_ms": 70,
    "ai_message": "..."
  }
}
```

**Client-side tracking**:
```javascript
const metrics = {
  asrLatency: [],
  llmLatency: [],
  ttsLatency: [],
  endToEndLatency: []
};

// Track end-to-end latency
function onTTSPlaybackStart() {
  const latency = Date.now() - userStoppedSpeakingTime;
  metrics.endToEndLatency.push(latency);
  // Alert if >300ms
  if (latency > 300) {
    logger.warn('High latency detected', { latency });
  }
}
```

## Error Handling Matrix

| Error | Server Action | Client Action | User Sees |
|-------|---------------|---------------|-----------|
| ASR failure | Send `error` with `user_action: switch_to_browser_asr` | Switch to WebKitSpeechRecognition | "Using backup recognition..." |
| TTS failure | Send `error` with `user_action: use_browser_tts` | Use speechSynthesis API + text display | Text on screen |
| LLM timeout | Send fallback `tts_audio` with filler phrase | Play filler, retry in background | "Hmm, let me think..." |
| WebSocket disconnect | (close connection) | Reconnect with backoff, buffer audio | Subtle "Reconnecting..." |
| Vector DB failure | Use keyword search fallback | (no action needed) | (no change) |
| All other errors | Send generic fallback TTS | Play "Can you repeat that?" | "Can you repeat that?" |

**Client Error Handler Template**:

```javascript
websocket.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'error') {
    // NEVER show error popup
    logger.error('Server error', {
      code: message.data.code,
      trace_id: message.data.trace_id
    });

    // Execute fallback action
    const action = message.data.user_action;
    if (action === 'switch_to_browser_asr') {
      startBrowserASR();
      showStatus('Using backup speech recognition...');
    } else if (action === 'use_browser_tts') {
      const text = message.data.fallback_text;
      speakWithBrowser(text);
    }
  }

  // Handle other message types...
};
```

## Example Session

```javascript
// 1. Connect
const ws = new WebSocket('ws://localhost:8000/ws/presentation?session_id=abc&token=xyz');

ws.onopen = () => {
  console.log('Connected');
  // Send metadata
  ws.send(JSON.stringify({
    type: 'client_ready',
    data: { browser: 'Chrome', os: 'iOS' }
  }));
};

// 2. Start recording
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    const recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => {
      // Send audio chunk
      ws.send(JSON.stringify({
        type: 'audio_chunk',
        data: {
          audio: btoa(e.data),
          sequence: sequence++
        }
      }));
    };
    recorder.start(200); // 200ms chunks
  });

// 3. Handle incoming messages
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'asr_transcript':
      updateTranscriptUI(msg.data.text);
      break;

    case 'tts_audio':
      playAudio(msg.data.audio);
      break;

    case 'interruption':
      stopRecording();
      playAudio(msg.data.ai_message);
      showStatus('AI interrupted: ' + msg.data.reason);
      break;

    case 'error':
      logger.error(msg.data);
      executeFallback(msg.data.user_action);
      break;
  }
};
```

## Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| ASR streaming latency | <200ms | Time from audio chunk to first transcript |
| Interruption detection | <100ms | Time from trigger word to interruption message |
| End-to-end latency | <300ms (95th) | User stops speaking → AI audio starts |
| Reconnection time | <5s | WebSocket disconnect → reconnected |
| Message throughput | 50 msg/sec | Server can handle 50 concurrent streams |
