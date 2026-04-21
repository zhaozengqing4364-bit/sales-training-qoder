# 2026-04-21 Lane A Backend Safety Brief

Worker: `worker-1`  
Task: `9` — corrective continuation for Lane A Backend Safety / Runtime Stability.

## Scope

Lane A owns Q-03/Q-04/Q-05/Q-07/Q-08/Q-09/Q-10/Q-11/Q-12/Q-13/Q-23/Q-24/Q-25/Q-29/Q-30.

This slice starts with high-safety, low-cross-lane runtime fixes:

- Q-03 PresentationFeedbackService TTL/max_sessions cleanup.
- Q-05 parallel single-KB fallback after `search_multiple` failure.
- Q-07 staged evaluation real conversation-slice bounds.
- Q-08 capability runner infrastructure exception degradation and cancellation propagation.
- Q-09 bounded base websocket message queue with configured backpressure.
- Q-10 sales websocket `CancelledError` propagation.
- Q-11 response pipeline task launch lock.
- Q-12 PPT websocket session isolation.
- Q-13 PCM TTS duration formula with validated defaults.
- Q-25 Redis cache memory fallback LRU cap and glob pattern deletion.
- Q-29 remove source `print(` usage from backend source surfaces.

## Configuration / Governance Notes

- `WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE`: env-backed default `300`, bounded `1..5000`.
- `WEBSOCKET_BACKPRESSURE_POLICY`: env-backed allowlist `drop_newest|drop_oldest`, default `drop_newest`.
- `TTS_DEFAULT_SAMPLE_RATE_HZ`: env-backed default `16000`, bounded `8000..48000`.
- `TTS_BYTES_PER_SAMPLE`: env-backed default `2`, bounded `1..4`.
- `TTS_CHANNELS`: env-backed default `1`, bounded `1..2`.

These are runtime safety/resource settings. Future admin UI work should expose them through the existing admin config governance pattern with audit and rollback before making them mutable from the product surface.

## Verification Plan

Targeted tests first:

- `backend/tests/unit/common/cache/test_redis_cache.py`
- `backend/tests/unit/evaluation/test_staged_evaluation_service.py`
- `backend/tests/unit/test_presentation_feedback_service_policy.py`
- `backend/tests/unit/test_knowledge_retrieval.py`
- `backend/tests/unit/test_capability_base.py`
- `backend/tests/unit/test_websocket_handler.py`
- `backend/tests/unit/test_presentation_handler_persistence.py`
- `backend/tests/unit/sales_bot/websocket/test_tts_component_duration.py`
- `backend/tests/unit/sales_bot/websocket/test_base_sales_handler_safety.py`

Also run ruff on modified backend source/test files and `git diff --check`.
