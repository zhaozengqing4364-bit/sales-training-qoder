# Implementation Plan: Enterprise AI Intelligent Practice System

**Branch**: `001-ai-practice-system` | **Date**: 2025-01-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ai-practice-system/spec.md`

## Summary

Build a real-time voice-based AI training platform with two core scenarios: PPT presentation coaching and sales practice bot. The system must support bidirectional interruption with <300ms end-to-end latency, using qwen3-asr-flash for speech recognition, Edge-TTS for speech synthesis, and LangChain for AI orchestration. The key differentiator is a "no error popups" user experience where all failures are handled gracefully with fallbacks and retries.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- FastAPI (web framework with native WebSocket)
- qwen3-asr-flash (streaming ASR)
- edge-tts (text-to-speech)
- LangChain/LangSmith (AI orchestration)
- ChromaDB (vector database with metadata filtering)
- Pydantic (data validation)

**Storage**:
- ChromaDB (vector embeddings for RAG)
- File system (audio recordings, PPT files)
- SQLite/PostgreSQL (user data, practice sessions - choice depends on scaling needs)

**Testing**: pytest + pytest-asyncio (async WebSocket testing), pytest-benchmark (latency validation)

**Target Platform**:
- Backend: Linux server (venv + systemd/supervisor deployment)
- Frontend: Web/H5 accessible via enterprise WeChat workbench

**Project Type**: Web application (backend + frontend)

**Performance Goals**:
- End-to-end latency: <300ms (95th percentile)
- ASR streaming latency: <200ms
- Interruption detection: <100ms
- Support 50 concurrent WebSocket connections
- Page load time: <2s

**Constraints**:
- All I/O must be asynchronous (no blocking calls)
- Zero error popups to users (constitution requirement)
- Audio buffering for 30s during network interruptions
- Single session cost <¥1

**Scale/Scope**:
- 1K-10K users
- <50 concurrent practice sessions
- <100GB storage (1 year retention)
- 2 core scenarios (PPT coaching, sales bot)
- 9 data entities
- 40 functional requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: User Experience Never Interrupts (NON-NEGOTIABLE)

**Status**: ✅ ADDRESSED IN DESIGN

**Implementation Requirements**:
- [ ] No error popups in frontend code
- [ ] All exceptions caught and converted to fallback responses
- [ ] WebSocket reconnection with exponential backoff
- [ ] Audio buffering for 30s during network issues
- [ ] Fallback TTS (browser native) when Edge-TTS fails
- [ ] Fallback ASR (browser native) when qwen3-asr-flash fails
- [ ] Predefined "filler" responses when LLM times out
- [ ] Keyword search fallback when vector DB fails

### Principle II: Real-Time Priority

**Status**: ✅ ADDRESSED IN DESIGN

**Implementation Requirements**:
- [ ] Use streaming ASR (qwen3-asr-flash) with <200ms latency
- [ ] Implement keyword detection in <100ms for interruption triggers
- [ ] End-to-end pipeline monitoring (ASR → LLM → TTS)
- [ ] Latency metrics on every interaction
- [ ] Alert when 95th percentile exceeds 300ms

### Principle III: Modular Scenario Independence

**Status**: ✅ ADDRESSED IN DESIGN

**Implementation Requirements**:
- [ ] Directory structure: `presentation_coach/`, `sales_bot/`, `common/`
- [ ] Separate API routes per scenario (`/api/presentation/*`, `/api/sales/*`)
- [ ] Separate WebSocket endpoints (`/ws/presentation`, `/ws/sales`)
- [ ] Scenario type field in data model for isolation
- [ ] No code sharing between scenarios except in `common/`

### Principle IV: Fault Tolerance & Recovery

**Status**: ✅ ADDRESSED IN DESIGN

**Implementation Requirements**:
- [ ] Exponential backoff retry for all external APIs
- [ ] Circuit breaker for LLM API (stop after N failures)
- [ ] Graceful degradation for each component
- [ ] Structured logging with trace_id for debugging
- [ ] Health check endpoint for monitoring

### Principle V: Cost Control

**Status**: ✅ ADDRESSED IN DESIGN

**Implementation Requirements**:
- [ ] Use free/open-source ASR (qwen3-asr-flash) and TTS (Edge-TTS)
- [ ] LLM call optimization (cache where possible, batch requests)
- [ ] Cost tracking per session
- [ ] Automated archival of audio after 1 year

### Principle VI: Data Privacy & Compliance

**Status**: ✅ ADDRESSED IN DESIGN

**Implementation Requirements**:
- [ ] TLS for all data in transit
- [ ] Access control (user can only see their own sessions)
- [ ] Soft delete with admin purge capability
- [ ] Log redaction (no audio transcripts in logs)

### Principle VII: Observability

**Status**: ✅ ADDRESSED IN DESIGN

**Implementation Requirements**:
- [ ] Structured JSON logging with trace_id
- [ ] Metrics dashboard (latency, error rate, concurrency, API usage)
- [ ] Distributed tracing (WebSocket → ASR → LLM → TTS)
- [ ] User analytics (completion rate, session duration, score distribution)

**Gate Status**: ✅ ALL PRINCIPLES ADDRESSED - Proceed to Phase 0

---

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-practice-system/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── openapi.yaml     # REST API specification
│   └── websocket.md     # WebSocket protocol specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Option 2: Web application (backend + frontend)

backend/
├── src/
│   ├── presentation_coach/    # PPT 演练场景模块
│   │   ├── models/            # 数据模型
│   │   ├── services/          # 业务逻辑
│   │   ├── api/               # REST endpoints
│   │   └── websocket/         # WebSocket handler
│   ├── sales_bot/             # 销售对练场景模块
│   │   ├── models/
│   │   ├── services/
│   │   ├── api/
│   │   └── websocket/
│   └── common/                # 共享模块
│       ├── audio/             # 音频处理 (ASR/TTS 封装)
│       ├── ai/                # AI 服务 (LangChain 封装)
│       ├── knowledge/         # 向量数据库 (ChromaDB)
│       ├── error_handling/    # 统一错误处理
│       ├── monitoring/        # 日志、指标、追踪
│       └── auth/              # 企业微信 SSO
├── tests/
│   ├── contract/              # 契约测试
│   ├── integration/           # 集成测试 (WebSocket 流程)
│   ├── unit/                  # 单元测试
│   └── performance/           # 性能测试 (50 并发)
├── requirements.txt           # Python 依赖
├── pyproject.toml             # 项目配置
└── venv/                      # 虚拟环境 (不提交)

frontend/
├── src/
│   ├── components/            # 共享组件
│   │   ├── AudioRecorder/     # 录音组件
│   │   ├── AudioPlayer/       # 播放组件
│   │   ├── Waveform/          # 声波纹动画
│   │   └── StatusIndicator/   # 状态指示灯
│   ├── pages/
│   │   ├── Presentation/      # PPT 演练页面
│   │   │   ├── PPTViewer/     # PPT 阅读器
│   │   │   └── PracticeArea/  # 演练区域
│   │   ├── SalesBot/          # 销售对练页面
│   │   └── Admin/             # 管理后台
│   ├── services/
│   │   ├── websocket.js       # WebSocket 客户端
│   │   └── audio.js           # 音频处理
│   └── utils/
│       └── error-handler.js   # 前端错误处理 (无弹窗)
└── tests/
    ├── unit/
    └── e2e/
```

**Structure Decision**: Web application structure selected because:
1. Constitution requires backend (FastAPI) for WebSocket and AI services
2. Frontend (H5) required for enterprise WeChat integration
3. Modularity requirement: `presentation_coach/` and `sales_bot/` are independent
4. `common/` directory for shared audio/AI/error-handling infrastructure

---

## Complexity Tracking

> **No constitution violations requiring justification**

All complexity is justified by the core bidirectional interruption requirement and the "no error popups" principle. The modular structure (two independent scenarios) actually reduces complexity by isolating concerns.
