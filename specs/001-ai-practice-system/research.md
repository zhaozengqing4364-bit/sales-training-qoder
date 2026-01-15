# Research: Enterprise AI Intelligent Practice System

**Date**: 2025-01-10
**Status**: Complete

## Overview

This document captures research findings and technical decisions for implementing the Enterprise AI Intelligent Practice System. All "NEEDS CLARIFICATION" items from the Technical Context have been resolved.

---

## 1. ASR Engine: qwen3-asr-flash

### Decision
Use **qwen3-asr-flash** for streaming speech recognition.

### Rationale
- **Low latency**: Optimized for real-time scenarios with <200ms streaming capability
- **Chinese support**: Excellent Mandarin recognition (critical for enterprise use)
- **Emotion detection**: Built-in emotion recognition for detecting user state
- **Free and open-source**: Aligns with cost control principle (<¥1 per session)
- **Streaming native**: Designed for streaming ASR, not batch processing

### Integration Approach
```python
# Pseudocode for streaming integration
from funasr import AutoModel

asr_model = AutoStreammodel(model="qwen3-asr-flash", device="cuda")

async def stream_audio(websocket):
    async for audio_chunk in websocket:
        # Stream processing returns partial results
        result = await asr_model.generate(input=audio_chunk, stream=True)
        if result["is_final"]:
            yield result["text"]
```

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Whisper | OpenAI quality, multilingual | 5-10x slower, higher latency | Rejected - latency too high |
| SenseVoice | Fast, emotion-aware | Less mature than qwen3 | Rejected - qwen3 has better Chinese support |
| Azure/OpenAI ASR | High accuracy | Expensive, adds cost | Rejected - cost concerns |

---

## 2. TTS Engine: Microsoft Edge-TTS

### Decision
Use **edge-tts** Python library for text-to-speech.

### Rationale
- **Zero cost**: Uses free Edge browser API
- **High quality**: "云希" voice (common in Douyin/TikTok) sounds natural
- **Fast response**: <500ms for most phrases
- **Multiple voices**: Supports various Chinese voices with emotions
- **Simple API**: Easy async integration

### Integration Approach
```python
import edge_tts

async def generate_tts(text: str, voice: str = "zh-CN-XiaoxiaoNeural"):
    communicate = edge_tts.Communicate(text, voice)
    async for chunk in communicate.stream():
        yield chunk["data"]  # Audio bytes
```

### Fallback Strategy
When Edge-TTS fails (network/server issues):
```python
async def tts_with_fallback(text: str):
    try:
        return await edge_tts.generate(text)
    except Exception:
        # Fall back to browser native speechSynthesis
        return {"fallback": True, "text": text}
```

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Azure TTS | Best quality | Expensive ($15/1M chars) | Rejected - cost |
| Google TTS | Good quality | Paid API | Rejected - cost |
| pyttsx3 | Offline, free | Robotic voice | Fallback only |
| Browser SpeechSynthesis | Always available | Poor quality | Fallback only |

---

## 3. Vector Database: ChromaDB

### Decision
Use **ChromaDB** for vector embeddings storage and retrieval.

### Rationale
- **Metadata filtering**: Native support for `{page: 3}` filtering (critical requirement)
- **Zero configuration**: Embedded mode, no separate server needed
- **Fast development**: Simple API, quick to implement
- **Free & open-source**: No licensing costs
- **Python native**: Perfect fit for FastAPI backend

### Integration Approach
```python
import chromadb

client = chromadb.Client()
collection = client.get_or_create_collection("ppt_knowledge")

# Query with metadata filtering
results = collection.query(
    query_texts=["user question"],
    where={"page": 3, "presentation_id": "ppt_001"}
)
```

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Milvus | Scalable, production-grade | Complex setup (Docker/K8s) | Rejected - overkill for 50 concurrent |
| Pinecone | Managed service | Expensive, external dependency | Rejected - cost & data privacy |
| Faiss | Fast, open-source | No metadata filtering | Rejected - missing critical feature |
| Weaviate | Good features | Heavier than ChromaDB | Rejected - simplicity wins |

---

## 4. Database: PostgreSQL vs SQLite

### Decision
Use **PostgreSQL** for production data (users, sessions, entities).
Consider **SQLite** for development/testing.

### Rationale
- **Concurrent access**: PostgreSQL handles 50+ concurrent connections better
- **Data integrity**: ACID compliance for session records
- **Scalability**: Easy to scale if user count grows beyond 10K
- **JSON support**: Store flexible data (e.g., interruption_events) as JSONB
- **Enterprise standard**: Well-understood, good tooling

### Integration Approach
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")

# For development with SQLite
# engine = create_async_engine("sqlite+aiosqlite:///./dev.db")
```

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| SQLite | Zero config, embedded | Poor concurrency | Rejected for production |
| MongoDB | Flexible schema | Additional complexity | Rejected - SQL is sufficient |
| Redis | Fast, in-memory | Not primary DB | Use for caching only |

---

## 5. WebSocket Architecture

### Decision
Use **FastAPI native WebSocket** with per-scenario endpoints.

### Rationale
- **Native async**: Built on Starlette, perfect fit with FastAPI
- **Type safety**: Pydantic models for message validation
- **Connection management**: Built-in lifecycle hooks (connect/disconnect)
- **Single framework**: No additional dependencies (e.g., Socket.IO)

### Architecture Pattern
```python
from fastapi import WebSocket

@app.websocket("/ws/presentation")
async def presentation_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Receive audio chunk
            audio_data = await websocket.receive_bytes()

            # ASR → LLM → TTS pipeline
            text = await asr.stream(audio_data)
            decision = await interruption_detector.check(text)
            if decision.should_interrupt:
                response = await llm.generate(decision.prompt)
                audio = await tts.generate(response)
                await websocket.send_bytes(audio)
    except WebSocketDisconnect:
        # Handle reconnection
        pass
```

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Socket.IO | Auto-reconnect, fallbacks | Heavier, less Pythonic | Rejected - native is sufficient |
| gRPC streaming | Bidirectional, fast | Not browser-friendly | Rejected - H5 requirement |
| Server-Sent Events | Simple | One-way only | Rejected - need bidirectional |

---

## 6. Error Handling Strategy (No Error Popups)

### Decision
Implement a **layered fallback strategy** with graceful degradation.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                       │
│         (No error popups, only status indicators)        │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Frontend Error Boundary                     │
│  • Catch all errors                                       │
│  • Convert to status updates                             │
│  • Trigger fallbacks                                     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 WebSocket Reconnection                   │
│  • Exponential backoff (1s, 2s, 4s, 8s)                 │
│  • Buffer audio for 30s                                  │
│  • Silent retry (no popup)                               │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Backend Error Handlers                      │
│  • ASR fail → browser native ASR                         │
│  • TTS fail → browser native TTS + text display          │
│  • LLM timeout → predefined "filler" responses          │
│  • Vector DB fail → keyword search                       │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Logging (JSON)                        │
│  • All errors logged with trace_id                       │
│  • User-facing: "Hmm, let me think..."                   │
│  • Admin-facing: full error details                      │
└─────────────────────────────────────────────────────────┘
```

### Example Implementation

```python
# Backend error handler
async def asr_with_fallback(audio: bytes) -> str:
    try:
        return await qwen3_asr.stream(audio)
    except ASRError:
        logger.warning("ASR failed, using fallback", extra={"trace_id": trace_id})
        # Return placeholder to trigger frontend fallback
        return "[ASR_FALLBACK]"

# Frontend handler
if (text === "[ASR_FALLBACK]") {
    // Switch to browser WebKitSpeechRecognition
    startBrowserASR();
    // Show subtle indicator, not error
    showStatus("Using backup speech recognition...");
}
```

---

## 7. Real-Time Interruption Detection

### Decision
Implement a **two-stage detection system**: keyword + semantic.

### Architecture

```
┌─────────────────────┐
│   ASR Streaming     │
│  (qwen3-asr-flash)  │
└──────────┬──────────┘
           │ text stream
           ▼
┌─────────────────────┐
│  Stage 1: Keyword   │  <100ms
│  Detection (Regex)  │
│  • Forbidden words  │
│  • Required points  │
└──────────┬──────────┘
           │ if matched
           ▼
      [INTERRUPT]

           │ if not matched
           ▼
┌─────────────────────┐
│  Stage 2: Semantic  │  <500ms
│  Analysis (LLM)     │
│  • Vague response   │
│  • Off-topic        │
└──────────┬──────────┘
           │ if detected
           ▼
      [INTERRUPT]
```

### Implementation

```python
# Stage 1: Fast keyword detection
FORBIDDEN_PATTERNS = [r"不知道", r"不清楚", r"没听过"]

def check_keywords(text: str) -> Optional[str]:
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text):
            return f"Please avoid saying '{pattern}'"
    return None

# Stage 2: Semantic analysis (only if Stage 1 didn't match)
async def check_semantic(text: str, context: dict) -> Optional[str]:
    prompt = f"User said: '{text}'. Is this vague or evasive? Answer yes/no."
    response = await llm.generate(prompt)
    if "yes" in response.lower():
        return "That's too vague. Give me specific details."
    return None

# Main detection loop
async def detect_interruption(text: str, context: dict):
    # Stage 1: <100ms
    keyword_result = check_keywords(text)
    if keyword_result:
        return keyword_result

    # Stage 2: <500ms (async, doesn't block)
    semantic_result = await check_semantic(text, context)
    return semantic_result
```

---

## 8. Frontend: H5 + 企业微信 Integration

### Decision
Use **Vanilla JS + Ant Design Mobile** for H5 pages.

### Rationale
- **Enterprise WeChat compatibility**: Works in WeChat browser
- **Lightweight**: No build step needed for H5
- **Ant Design Mobile**: Enterprise-grade components
- **Responsive**: Mobile-first design

### Key Libraries
- **antd-mobile**: UI components
- **WebSocket API**: Native browser support
- **MediaRecorder API**: Native audio recording
- **Web Audio API**: Waveform visualization

### Enterprise WeChat Integration
```javascript
// Get user info from enterprise WeChat
wx.agent.edit({
  type: 'getuserinfo',
  success: (res) => {
    const { userId, name } = res;
    // Send to backend for authentication
    authWithWeChat(userId, name);
  }
});
```

---

## 9. Cost Tracking & Control

### Decision
Implement **per-session cost tracking** with budget alerts.

### Cost Breakdown (Per 20-min Session)

| Component | Unit Cost | Quantity | Total |
|-----------|-----------|----------|-------|
| qwen3-asr-flash | ¥0 (free) | 20 min | ¥0 |
| Edge-TTS | ¥0 (free) | ~50 phrases | ¥0 |
| LLM (GPT-4o) | ~¥0.05/1K tokens | ~5K tokens | ¥0.25 |
| Vector DB | ¥0 (embedded) | N/A | ¥0 |
| Database | ¥0 (self-hosted) | N/A | ¥0 |
| **Total** | | | **~¥0.25** |

### Implementation

```python
# Cost tracking middleware
class CostTracker:
    def __init__(self):
        self.session_costs = {}  # {session_id: cost}

    def record_llm_call(self, session_id: str, tokens: int):
        cost = tokens * 0.00005  # ¥0.05/1K tokens
        self.session_costs[session_id] = self.session_costs.get(session_id, 0) + cost

        if self.session_costs[session_id] > 0.8:  # 80% of ¥1 budget
            logger.warning(f"Session {session_id} approaching budget limit")
```

---

## 10. Deployment: Docker Compose

### Decision
Use **Docker Compose** for single-machine deployment.

### Architecture

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
    depends_on:
      - db

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    # For caching & session management

  prometheus:
    image: prom/prometheus
    # Metrics collection

  grafana:
    image: grafana/grafana
    # Metrics dashboard
```

### Deployment Strategy
- **Blue-green deployment**: Two containers, switch traffic after health check
- **Rollback**: Previous container kept for 24 hours
- **Health checks**: `/health` endpoint returns system status

---

## Summary of Technical Decisions

| Component | Decision | Key Factor |
|-----------|----------|------------|
| ASR | qwen3-asr-flash | Latency + Chinese + Cost |
| TTS | Edge-TTS | Cost + Quality |
| Vector DB | ChromaDB | Metadata filtering + Simplicity |
| Database | PostgreSQL | Concurrency + Scalability |
| Framework | FastAPI | Async + WebSocket + Python |
| Frontend | Vanilla JS + Ant Design Mobile | WeChat + Lightweight |
| Deployment | Docker Compose | Simplicity + Single-machine |

All decisions align with the 7 constitutional principles:
1. ✅ User experience never interrupted (fallbacks at every layer)
2. ✅ Real-time priority (streaming ASR, <300ms pipeline)
3. ✅ Modular independence (separate scenario modules)
4. ✅ Fault tolerance (graceful degradation)
5. ✅ Cost control (<¥1/session achievable)
6. ✅ Data privacy (TLS, access control)
7. ✅ Observability (structured logging, metrics)
