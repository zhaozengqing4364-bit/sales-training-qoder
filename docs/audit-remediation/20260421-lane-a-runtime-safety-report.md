# 2026-04-21 Lane A Runtime Safety Slice Report

Worker: `worker-1`  
Task: `9`  
Scope slice: Q-03/Q-05/Q-08/Q-09/Q-10/Q-11/Q-12/Q-13/Q-29.

## Implemented

- Q-03: `PresentationFeedbackService` now tracks last access, clears expired session-scoped state by TTL, and evicts least-recently-used sessions over the configured cap.
- Q-05: `KnowledgeRetrievalCapability` now runs legacy single-KB fallback searches concurrently after `search_multiple` failure while preserving per-KB error isolation.
- Q-08: `CapabilityRunner` now degrades `ConnectionError`/`OSError` to failure results and propagates `asyncio.CancelledError` instead of disguising cancellation.
- Q-09: `BaseWebSocketHandler` now initializes a bounded message queue with validated env defaults and emits a backpressure message when full.
- Q-10: `BaseSalesHandler` no longer catches `asyncio.CancelledError` in mixed runtime exception handlers; cancellation is raised after cleanup-safe contexts.
- Q-11: `BaseSalesHandler._launch_response_task` uses an async lock around response task check/assignment and clears the active task under the same lock.
- Q-12: `PresentationWebSocketHandler._get_active_websocket` no longer falls back to another session when the current session is missing.
- Q-13: PCM TTS duration calculation now uses sample rate, bytes-per-sample, and channels via shared helper and validated defaults.
- Q-29: source `print(` usages in Lane A/backend source surfaces were replaced with logger usage or doc examples that do not call print.

## Config / Governance

Added env-backed runtime defaults in `common.config.Settings`:

- `WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE`: default `300`, bounded `1..5000`.
- `WEBSOCKET_BACKPRESSURE_POLICY`: default `drop_newest`, allowlist `drop_newest|drop_oldest`.
- `TTS_DEFAULT_SAMPLE_RATE_HZ`: default `16000`, bounded `8000..48000`.
- `TTS_BYTES_PER_SAMPLE`: default `2`, bounded `1..4`.
- `TTS_CHANNELS`: default `1`, bounded `1..2`.
- `PRESENTATION_FEEDBACK_SESSION_TTL_SECONDS`: default `86400`, bounded `60..604800`.
- `PRESENTATION_FEEDBACK_MAX_SESSIONS`: default `10000`, bounded `100..100000`.

No business rules, scoring thresholds, recommendation logic, badges, notifications, Docker/deploy/ops, or frontend Lane C/D files were changed.

## Verification

- PASS: `git diff --check`
- PASS: `cd backend && ruff check src/common/config.py src/presentation_coach/services/feedback_service.py tests/unit/test_presentation_feedback_service_policy.py --quiet`
- PASS: `cd backend && DATABASE_URL='sqlite+aiosqlite:///./test_lane_a.db' PYTHONPATH=src .venv-test/bin/python -m pytest tests/unit/test_presentation_feedback_service_policy.py -q --no-cov` → `5 passed`
- PASS: `cd backend && ruff check src/common/config.py src/common/audio/pcm_duration.py src/agent/capabilities/runner.py src/agent/capabilities/knowledge_retrieval.py src/agent/capabilities/registry.py src/common/websocket/base_handler.py src/common/ai/encryption.py src/common/services/password_reset.py src/evaluation/schemas.py src/sales_bot/websocket/base_sales_handler.py src/sales_bot/websocket/components/tts_component.py src/presentation_coach/websocket/presentation_handler.py tests/unit/test_capability_base.py tests/unit/test_websocket_handler.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_knowledge_retrieval.py tests/unit/sales_bot/websocket/test_tts_component_duration.py tests/unit/sales_bot/websocket/test_base_sales_handler_safety.py --quiet`
- PASS: `cd backend && DATABASE_URL='sqlite+aiosqlite:///./test_lane_a.db' PYTHONPATH=src .venv-test/bin/python -m pytest tests/unit/test_knowledge_retrieval.py tests/unit/test_capability_base.py tests/unit/test_websocket_handler.py tests/unit/test_presentation_handler_persistence.py tests/unit/sales_bot/websocket/test_tts_component_duration.py tests/unit/sales_bot/websocket/test_base_sales_handler_safety.py -q --no-cov` → `115 passed, 1 warning`
- PASS: `cd backend && .venv-test/bin/python -m py_compile <modified source/test files>`

## Deferred Lane A Items

Remaining Lane A items Q-04/Q-07/Q-23/Q-24/Q-25/Q-30 are not claimed complete in this slice and need follow-up targeted tasks/tests.
