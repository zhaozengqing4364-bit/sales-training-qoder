# sales_bot — Sales Practice Runtime Domain

This subtree governs the high-pressure sales practice runtime: voice-driven, websocket-backed, persona-driven conversation sessions.

## Local Structure

```
backend/src/sales_bot/
├── api/           # Scenario & persona REST endpoints
├── prompts/       # Persona prompt templates
├── services/      # Bot runtime, context, scoring, voice policy
└── websocket/     # WebSocket handlers & realtime orchestration
```

## Where to Look

| Concern | Location |
|---------|----------|
| Scenario / persona APIs | `api/scenarios.py` |
| Bot response generation | `services/bot_service.py` |
| Session context & turns | `services/context_manager.py` |
| Post-session summary | `services/summary_service.py` |
| ASR transcript lexicon fixes | `services/transcript_normalization.py` |
| Realtime vague-speech detection | `services/vagueness_detector.py` |
| Voice policy compilation | `services/voice_instruction_compiler.py`, `services/voice_runtime_policy.py` |
| WebSocket routing | `websocket/router.py` |
| Base handler (ASR → LLM → TTS pipeline) | `websocket/base_sales_handler.py` |
| Simple / enhanced handler variants | `websocket/simple_handler.py`, `websocket/enhanced_handler.py` |
| StepFun realtime integration | `websocket/stepfun_realtime_handler.py` |
| StepFun helpers / tools / events | `websocket/components/` |
| Realtime feedback arbiter | `websocket/realtime_feedback_arbiter.py` |

## Complexity Hotspot

**`websocket/` is the dominant complexity hotspot in this subtree.**
- `websocket/stepfun_realtime_handler.py` is the largest source file in the repo.
- `websocket/components/` contains a dense concentration of StepFun-specific helpers (message helpers, knowledge helpers, function-call helpers, tool helpers, event payloads, runtime metrics, upstream router, TTS component, capability processor, score processor, objection ledger, message persistence).
- `websocket/base_sales_handler.py` defines the shared Audio → ASR → LLM → TTS pipeline with backpressure, deduplication, and lifecycle state sync.

## Local Cautions

- **Realtime state is fragile**: `BaseSalesHandler` uses strict asyncio locks, request/stream ID versioning, and backpressure thresholds (`ASR_QUEUE_MAX_SIZE`, `MAX_MESSAGE_QUEUE_SIZE`). Do not weaken these guards.
- **Binary audio frames** (`v1-13`) bypass Base64 entirely; changes to the frame protocol must stay backward-compatible.
- **Voice policy snapshots** are persisted per-session and evaluated during response generation (`evaluate_kb_lock_decision`). Changing policy shapes affects both runtime and stored sessions.
- **Session lifecycle** transitions (start/pause/resume/end) are gated by `SessionLifecycleService`. WebSocket handlers mirror these transitions live; keep REST and WebSocket state machines in sync.
- **Graceful degradation is mandatory**: all LLM/ASR/TTS failures must fallback to predefined responses or browser TTS; never raise unhandled exceptions to the client.

## References

- Backend coding rules: `.kiro/steering/backend-principles.md`
- Shared platform/kernel: `backend/src/common/AGENTS.md`
- Backend domain router: `backend/AGENTS.md`
- API contracts: `docs/api-contract/`
