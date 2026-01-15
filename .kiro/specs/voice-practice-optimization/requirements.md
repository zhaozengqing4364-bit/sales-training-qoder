# Requirements Document

## Introduction

This document defines the requirements for optimizing the voice practice module in the Enterprise AI Intelligent Practice System. The optimization addresses critical performance issues including deprecated audio APIs, non-streaming TTS playback, incomplete interruption handling, and lack of backpressure control. The goal is to achieve lower latency, better user experience, and improved system stability.

## Glossary

- **AudioWorklet**: A modern Web Audio API interface that processes audio in a separate thread, replacing the deprecated ScriptProcessorNode
- **ScriptProcessorNode**: A deprecated Web Audio API that processes audio on the main thread, causing UI blocking
- **TTS**: Text-to-Speech service that converts AI responses to audio
- **ASR**: Automatic Speech Recognition service that converts user speech to text
- **MediaSource_API**: A Web API that enables streaming audio/video playback by appending chunks to a buffer
- **Backpressure**: A flow control mechanism that prevents buffer overflow when producers outpace consumers
- **PCM**: Pulse Code Modulation, a raw audio format used for ASR input
- **Resampling**: The process of converting audio from one sample rate to another (e.g., 48kHz to 16kHz)
- **VAD**: Voice Activity Detection, used to detect when a user starts/stops speaking
- **Streaming_Audio_Player**: A component that plays audio chunks as they arrive without waiting for the complete file

## Requirements

### Requirement 1: AudioWorklet Migration

**User Story:** As a user, I want smooth audio recording without UI freezes, so that I can have an uninterrupted practice experience.

#### Acceptance Criteria

1. WHEN the user starts recording, THE Audio_Recorder SHALL use AudioWorklet for audio processing instead of ScriptProcessorNode
2. WHEN AudioWorklet is not supported by the browser, THE Audio_Recorder SHALL fall back to ScriptProcessorNode with a console warning
3. WHILE recording audio, THE Audio_Recorder SHALL process audio in a separate thread without blocking the main UI thread
4. WHEN processing audio chunks, THE AudioWorklet SHALL use a buffer size of 1024 samples to achieve approximately 21ms latency
5. WHEN audio data is ready, THE AudioWorklet SHALL send PCM data to the main thread via postMessage for encoding and transmission

### Requirement 2: Streaming TTS Playback

**User Story:** As a user, I want to hear AI responses immediately as they are generated, so that I don't have to wait for the entire response to be synthesized.

#### Acceptance Criteria

1. WHEN the backend generates TTS audio, THE TTS_Service SHALL send audio chunks incrementally via WebSocket as they become available
2. WHEN the frontend receives the first TTS chunk, THE Streaming_Audio_Player SHALL begin playback immediately without waiting for subsequent chunks
3. WHEN receiving TTS chunks, THE Streaming_Audio_Player SHALL use MediaSource API to append audio data to the playback buffer
4. WHEN the final TTS chunk is received, THE Backend SHALL send an is_final flag to signal stream completion
5. IF MediaSource API is not supported, THEN THE Audio_Player SHALL fall back to buffering the complete audio before playback
6. WHEN streaming TTS, THE Backend SHALL include chunk_index and duration_ms metadata with each chunk for synchronization

### Requirement 3: Complete Interruption Handling

**User Story:** As a user, I want to interrupt the AI while it's speaking, so that I can take control of the conversation naturally.

#### Acceptance Criteria

1. WHEN the user starts speaking while AI audio is playing, THE Frontend SHALL immediately stop TTS playback
2. WHEN the user interrupts, THE Frontend SHALL clear the audio playback queue before sending the interrupt signal
3. WHEN the backend receives an interrupt signal, THE Backend SHALL cancel any in-progress LLM requests
4. WHEN the backend receives an interrupt signal, THE Backend SHALL cancel any in-progress TTS generation
5. WHEN the backend successfully processes an interrupt, THE Backend SHALL send an "interrupted" confirmation message
6. WHEN an interrupt is confirmed, THE System SHALL transition to "listening" state within 100ms

### Requirement 4: Backpressure Control

**User Story:** As a system operator, I want the system to handle audio processing overload gracefully, so that memory doesn't overflow during high-load scenarios.

#### Acceptance Criteria

1. THE ASR_Queue SHALL have a maximum size of 100 audio chunks to prevent unbounded memory growth
2. WHEN the ASR queue reaches 80% capacity, THE Backend SHALL send a backpressure warning to the frontend
3. WHEN the ASR queue is full, THE Backend SHALL drop incoming audio chunks and send a critical backpressure signal
4. WHEN the frontend receives a critical backpressure signal, THE Audio_Recorder SHALL reduce the audio send rate
5. WHEN the ASR queue drops below 50% capacity, THE Backend SHALL send an "all clear" signal to resume normal operation

### Requirement 5: High-Quality Audio Resampling

**User Story:** As a user, I want accurate speech recognition, so that the AI understands what I'm saying correctly.

#### Acceptance Criteria

1. WHEN resampling audio from 48kHz to 16kHz, THE Resampler SHALL use OfflineAudioContext for high-quality conversion
2. WHEN OfflineAudioContext is not available, THE Resampler SHALL fall back to linear interpolation with a warning
3. WHEN resampling is complete, THE Resampler SHALL output 16-bit PCM audio at exactly 16kHz sample rate

### Requirement 6: Binary WebSocket Transmission (Optional)

**User Story:** As a system operator, I want to reduce bandwidth usage, so that the system can handle more concurrent users efficiently.

#### Acceptance Criteria

1. WHERE binary transmission is enabled, THE WebSocket SHALL send audio data as binary frames instead of Base64-encoded JSON
2. WHERE binary transmission is enabled, THE Binary_Protocol SHALL include a 4-byte header containing message type and sequence number
3. WHERE binary transmission is enabled, THE System SHALL reduce bandwidth usage by approximately 33% compared to Base64 encoding
4. WHERE binary transmission is not supported, THE System SHALL fall back to Base64-encoded JSON transmission

### Requirement 7: Performance Monitoring

**User Story:** As a developer, I want to monitor audio processing performance, so that I can identify and fix latency issues.

#### Acceptance Criteria

1. THE System SHALL measure and log audio capture latency (time from microphone to WebSocket send)
2. THE System SHALL measure and log TTS first-byte latency (time from request to first audio chunk received)
3. THE System SHALL measure and log interrupt response time (time from user speaking to TTS stop)
4. WHEN any latency metric exceeds its threshold, THE System SHALL emit a warning log with trace_id
5. THE System SHALL expose latency metrics via the existing monitoring infrastructure
