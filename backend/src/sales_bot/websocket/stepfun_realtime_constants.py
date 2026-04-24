"""Shared constants for the StepFun realtime websocket runtime."""

from __future__ import annotations

from typing import Any

PENDING_RESPONSE_FALLBACK_SECONDS = 0.8
TRANSCRIPTION_WAIT_GRACE_SECONDS = 2.4
GROUNDING_WAIT_GRACE_SECONDS = 8.0
GROUNDING_WAIT_POLL_SECONDS = 0.05
TRANSCRIPTION_DUPLICATE_WINDOW_SECONDS = 2.0
DEFAULT_GROUNDING_PREFETCH_TIMEOUT_MS = 220
DEFAULT_KB_LOCK_DECISION_TIMEOUT_MS = 2200
DEFAULT_INTERNAL_RETRIEVAL_CACHE_TTL_MS = 8000
DEFAULT_INTERNAL_RETRIEVAL_CACHE_MAX_ENTRIES = 128
DEFAULT_KB_LOCK_WARMUP_ENABLED = True
DEFAULT_UPSTREAM_AUTO_RECOVER_ENABLED = True
DEFAULT_UPSTREAM_AUTO_RECOVER_MAX_RETRIES = 4
DEFAULT_UPSTREAM_AUTO_RECOVER_BASE_DELAY_MS = 400
DEFAULT_UPSTREAM_AUTO_RECOVER_MAX_DELAY_MS = 5000
DEFAULT_UPSTREAM_KEEPALIVE_ENABLED = True
DEFAULT_UPSTREAM_KEEPALIVE_INTERVAL_MS = 20000
DEFAULT_UPSTREAM_KEEPALIVE_PONG_TIMEOUT_MS = 5000
TERMINAL_SESSION_STATUSES = {"scoring", "completed"}

# T01 inventory for M021/S04: these are the shipped StepFun/runtime behaviors that
# already emit degraded/fallback signals implicitly, but not yet as one normalized
# quality/cost/failure event schema.
STEPFUN_RUNTIME_EVENT_INVENTORY: tuple[dict[str, Any], ...] = (
    {
        "event_id": "kb_lock_warmup_degraded",
        "phase": "kb_lock_warmup",
        "trigger": "_run_kb_lock_warmup() catches exceptions and logs `KB lock warmup degraded`.",
        "current_surface": "warning log only; no explicit runtime_diagnostics/event row is attached to the session payload.",
        "hidden_risk": "future readers must infer that retrieval readiness degraded before the first user turn by scraping logs instead of inspecting one quality event stream.",
    },
    {
        "event_id": "capability_pipeline_failed",
        "phase": "live_coach_pipeline",
        "trigger": "_run_realtime_feedback() flips capability_pipeline_degraded when fuzzy detection or realtime scoring throws/fails and then calls _set_coach_health('degraded', reason='capability_pipeline_failed').",
        "current_surface": "coach_health status transitions (healthy/degraded/resumed) plus warning logs such as `StepFun realtime scoring degraded`.",
        "hidden_risk": "the session clearly degraded, but the exact capability failure is still fragmented across status state and logs instead of one normalized quality event.",
    },
    {
        "event_id": "knowledge_answer_rollout_mode",
        "phase": "knowledge_answer",
        "trigger": "The live/dual_run/legacy decision is owned by common.knowledge_engine.compat.resolve_knowledge_answer_rollout_mode() and attach_rollout_diagnostics(...).",
        "current_surface": "_latest_knowledge_answer_diagnostics plus payload._diagnostics.knowledge_answer_rollout expose mode/live_audit_run_id/shadow_audit_run_id when the compat seam runs.",
        "hidden_risk": "knowledge-answer path truth is inspectable today, but still split across compat payloads rather than promoted into the same explicit quality/failure/mode event line as other runtime diagnostics.",
    },
    {
        "event_id": "browser_tts_fallback",
        "phase": "response_delivery",
        "trigger": "Blocked-response and no-upstream-audio paths emit websocket tts_audio payloads with data.fallback='browser_tts'.",
        "current_surface": "frontend receives a valid tts_audio event with browser_tts fallback, often without a separate explicit failure event explaining why upstream audio was absent.",
        "hidden_risk": "delivery degradation can look like a normal response unless a reader knows to inspect the fallback field on individual websocket payloads.",
    },
    {
        "event_id": "transcription_timeout_blocked",
        "phase": "transcription_wait",
        "trigger": "_pending_response_timeout_fallback() suppresses learner-facing blocked copy when KB grounding is required but final ASR never completes in time, records transcription_timeout_suppressed, and leaves late transcripts recoverable.",
        "current_surface": "runtime diagnostics via _record_kb_lock_decision(status='transcription_timeout_suppressed', blocked=False) plus grounding debug logs; no assistant-side blocked coach copy is emitted anymore.",
        "hidden_risk": "the timeout is now intentionally silent for learners, so operators still need diagnostics to distinguish a suppressed ASR timeout from an ordinary no-response turn.",
    },
)
