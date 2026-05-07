"""
StepFun Realtime WebSocket Handler

Provides a proxy bridge between frontend practice WebSocket protocol and
StepFun Realtime API, enabling a dual-mode runtime:
- legacy: existing ASR -> LLM -> TTS pipeline
- stepfun_realtime: end-to-end realtime speech model
"""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportGeneralTypeIssues=false
# ruff: noqa: F401, I001, E402

import asyncio
import base64
import copy
import inspect
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlencode

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.exceptions import ConnectionClosed

from agent.capabilities.fuzzy_detection import FuzzyDetectionCapability
from agent.capabilities.realtime_scoring import RealtimeScoringCapability
from agent.capabilities.sales_stage import SalesStageCapability
from agent.context import AgentContext
from agent.models import Agent, Persona
from common.ai.embedding_service import get_embedding_service
from common.auth.service import JWTError, resolve_websocket_token, verify_token
from common.conversation.storage import normalize_objection_ledger
from common.db.models import PracticeSession
from common.db.session import AsyncSessionLocal
from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SessionLifecycleAction,
    SessionLifecycleService,
    SessionLifecycleTransition,
)
from common.effectiveness import (
    build_live_session_conclusion_summary,
    build_sales_effectiveness_metrics,
    build_sales_rollup_scores,
    coerce_live_session_conclusion_summary,
    evaluate_effectiveness_snapshot,
    evaluate_pass_flags,
)
from common.effectiveness.schemas import ActionCard, PassFlags
from common.knowledge.kb_lock_guard import (
    build_kb_coach_grounding_context,
    evaluate_kb_lock_decision,
    resolve_kb_lock_mode,
)
from common.knowledge.service import KnowledgeService
from common.knowledge_engine.runtime_events import (
    build_claim_truth_runtime_event,
    enrich_knowledge_answer_diagnostics,
    merge_runtime_events,
)
from common.monitoring.logger import get_logger, get_trace_id, set_trace_id
from common.monitoring.trace_context import normalize_trace_id
from common.resilience.backoff import compute_jitter_backoff_seconds
from common.websocket.base_handler import (
    BaseWebSocketHandler,
    _get_websocket_header_value,
)
from common.websocket.session_manager import get_session_manager
from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.services.transcript_normalization import (
    TranscriptNormalizationResult,
    TranscriptNormalizationService,
)
from sales_bot.services.voice_instruction_compiler import (
    VoiceInstructionCompiler,
    build_instruction_contract_hash,
    enforce_question_limit,
)
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from sales_bot.websocket.components.objection_ledger_helpers import (
    merge_arbiter_context_with_objection_ledger,
    resolve_turn_objection_ledger,
)
from sales_bot.websocket.components.stepfun_event_payloads import (
    build_asr_transcript_event,
    build_error_event,
    build_heartbeat_event,
    build_interrupted_event,
    build_stage_update_event,
    build_status_event,
)
from sales_bot.websocket.components.stepfun_function_call_helpers import (
    build_function_call_output_event,
    build_unsupported_function_output,
    decode_function_arguments,
    is_json_object_payload,
    parse_function_call_event,
)
from sales_bot.websocket.components.stepfun_helpers import (
    ensure_knowledge_runtime_metrics,
    extract_response_text,
    extract_text_payload,
    format_stage_name,
)
from sales_bot.websocket.components.stepfun_internal_knowledge_searcher import (
    search_internal_knowledge,
)
from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    is_product_overview_query,
    resolve_grounding_context_limits,
)
from sales_bot.websocket.components.stepfun_message_helpers import (
    extract_analysis_patch_fields,
    normalize_message_persistence_payload,
    normalize_score_snapshot,
    patch_existing_message_analysis,
    save_stepfun_message,
)
from sales_bot.websocket.components.stepfun_runtime_metrics_helpers import (
    apply_knowledge_runtime_metric,
    persist_runtime_metrics_to_session,
)
from sales_bot.websocket.components.stepfun_tool_helpers import (
    build_stepfun_tools_from_policy,
)
from sales_bot.websocket.components.stepfun_tts_contracts import (
    DEFAULT_TTS_CHUNK_PROTOCOL_VERSION,
)
from sales_bot.websocket.components.stepfun_upstream_router import (
    UpstreamEventRoute,
    classify_upstream_event,
    extract_error_message,
    extract_function_call_from_item_created,
    extract_response_done_function_calls,
)
from sales_bot.websocket.realtime_feedback_arbiter import (
    RealtimeFeedbackArbiter,
    RealtimeFeedbackPacingState,
)
from sales_bot.websocket.stepfun_realtime_state import StepFunRealtimeStateBase

logger = get_logger(__name__)

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


def _optional_runtime_text(value: Any) -> str | None:
    """Normalize nullable ORM/runtime identifiers without treating SQLAlchemy columns as values."""
    if value is None or hasattr(value, "expression"):
        return None
    text = str(value).strip()
    return text or None


def _optional_runtime_score(value: Any) -> float | None:
    """Normalize nullable ORM/runtime score fields."""
    if value is None or hasattr(value, "expression"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

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
from sales_bot.websocket.stepfun_realtime_connection import (
    StepFunRealtimeConnectionMixin,
)
from sales_bot.websocket.stepfun_realtime_policy import StepFunRealtimePolicyMixin
from sales_bot.websocket.stepfun_realtime_feedback import StepFunRealtimeFeedbackMixin
from sales_bot.websocket.stepfun_realtime_upstream import StepFunRealtimeUpstreamMixin
from sales_bot.websocket.stepfun_realtime_sales_stage import (
    StepFunRealtimeSalesStageMixin,
)
from sales_bot.websocket.stepfun_runtime_types import (
    FunctionCallState,
    RealtimeResponseState,
)


class StepFunRealtimeHandler(
    StepFunRealtimeConnectionMixin,
    StepFunRealtimePolicyMixin,
    StepFunRealtimeFeedbackMixin,
    StepFunRealtimeUpstreamMixin,
    StepFunRealtimeSalesStageMixin,
    StepFunRealtimeStateBase,
):
    """
    Proxy handler for StepFun Realtime API.

    Frontend protocol is kept compatible with current app:
    - incoming: audio_chunk/audio_end/text/control/user_speaking/interrupt
    - outgoing: asr_transcript/status/tts_audio/error/heartbeat
    """

    BINARY_AUDIO_CHUNK = 0x01
    BINARY_AUDIO_INTERRUPT = 0x02

    def __init__(self) -> None:
        super().__init__("sales")
        self.upstream_ws = None
        self._upstream_task: asyncio.Task | None = None
        self._effective_policy: dict[str, Any] = {}
        self._coach_health: str = "healthy"
        self._coach_health_reason: str | None = None

        self.current_request_id = 0
        self._active_response: RealtimeResponseState | None = None
        self._function_call_states: dict[str, FunctionCallState] = {}
        self._executed_call_ids: set[str] = set()

        self._stepfun_api_key = os.getenv("STEPFUN_API_KEY", "")
        self._stepfun_url = os.getenv(
            "STEPFUN_REALTIME_URL", "wss://api.stepfun.com/v1/realtime"
        )
        self._stepfun_model = os.getenv("STEPFUN_REALTIME_MODEL", "step-audio-2")
        self._stepfun_voice = os.getenv("STEPFUN_REALTIME_VOICE", "qingchunshaonv")
        self._stepfun_temperature = float(
            os.getenv("STEPFUN_REALTIME_TEMPERATURE", "0.7")
        )
        self._stepfun_input_audio_format = os.getenv(
            "STEPFUN_REALTIME_INPUT_AUDIO_FORMAT", "pcm16"
        )
        self._stepfun_output_audio_format = os.getenv(
            "STEPFUN_REALTIME_OUTPUT_AUDIO_FORMAT", "pcm16"
        )
        self._stepfun_output_sample_rate = int(
            os.getenv("STEPFUN_REALTIME_OUTPUT_SAMPLE_RATE", "24000")
        )
        self._stepfun_playback_rate = 1.0
        self._tts_chunk_protocol_version = DEFAULT_TTS_CHUNK_PROTOCOL_VERSION
        self._stepfun_input_transcription_enabled = str(
            os.getenv("STEPFUN_REALTIME_ENABLE_INPUT_TRANSCRIPTION", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._stepfun_input_transcription_language = str(
            os.getenv("STEPFUN_REALTIME_INPUT_TRANSCRIPTION_LANGUAGE", "zh")
        ).strip()
        self._stepfun_input_transcription_model = str(
            os.getenv("STEPFUN_REALTIME_INPUT_TRANSCRIPTION_MODEL", "")
        ).strip()
        self._stepfun_instructions = os.getenv("STEPFUN_REALTIME_INSTRUCTIONS", "")
        self._instruction_contract_hash = build_instruction_contract_hash(
            self._stepfun_instructions
        )
        self.session_status = "preparing"
        self.ai_state = "idle"
        self.session_scenario_type = "sales"
        self.turn_count = 0
        self._db_lock = asyncio.Lock()
        self._persisted_message_keys: set[tuple[int, str, str]] = set()
        self._sales_stage_runtime_config: dict[str, Any] = {"enabled": True}
        self._sales_stage_enabled = True
        self._sales_stage_capability = SalesStageCapability(
            self._sales_stage_runtime_config
        )
        self._sales_stage_context: AgentContext | None = None
        self._sales_stage_lock = asyncio.Lock()
        self._last_emitted_stage: str | None = None
        self._latest_stage_data: dict[str, Any] | None = None
        self._session_agent_id: str | None = None
        self._session_persona_id: str | None = None
        self._session_user_id: str | None = None
        self._agent_capabilities_config: dict[str, Any] = {}
        self._persona_behavior_config: dict[str, Any] = {}
        self._persona_scoring_weights: list[dict[str, Any]] | None = None

        self._fuzzy_detection_runtime_config: dict[str, Any] = {"enabled": True}
        self._fuzzy_detection_enabled = True
        self._fuzzy_detection_capability = FuzzyDetectionCapability(
            self._fuzzy_detection_runtime_config
        )

        self._realtime_scoring_runtime_config: dict[str, Any] = {"enabled": True}
        self._realtime_scoring_enabled = True
        self._realtime_scoring_capability = RealtimeScoringCapability(
            self._realtime_scoring_runtime_config
        )
        self._latest_score_snapshot: dict[str, Any] | None = None
        self._latest_live_session_summary: dict[str, Any] | None = None
        self._latest_claim_truth: dict[str, Any] | None = None
        self._latest_action_card: ActionCard | None = None
        self._latest_knowledge_answer_diagnostics: dict[str, Any] | None = None
        self._objection_ledger: dict[str, Any] | None = None
        self._feedback_arbiter = RealtimeFeedbackArbiter()
        self._feedback_pacing_state = RealtimeFeedbackPacingState()

        self._feedback_context: AgentContext | None = None
        self._pending_grounding_context: str = ""
        self._pending_blocked_response_text: str = ""
        self._pending_response_after_commit = False
        self._awaiting_transcription_after_commit = False
        self._allow_late_transcription_response = False
        self._pending_response_timeout_task: asyncio.Task | None = None
        self._pending_response_generation = 0
        self._pending_response_lock = asyncio.Lock()
        self._pending_tool_followup_response = False
        self._has_uncommitted_audio = False
        self._grounding_preparation_in_progress = False
        self._last_final_transcript_text = ""
        self._last_final_transcript_turn: int | None = None
        self._last_final_transcript_at: float = 0.0
        self._latest_input_transcript_delta = ""
        self._grounding_debug_log = os.getenv(
            "STEPFUN_GROUNDING_DEBUG_LOG", "false"
        ).lower() in {"1", "true", "yes", "on"}
        self._latency_debug_log = os.getenv(
            "STEPFUN_LATENCY_DEBUG_LOG", "false"
        ).lower() in {"1", "true", "yes", "on"}
        self._grounding_prefetch_timeout_seconds = (
            self._resolve_grounding_prefetch_timeout_seconds_from_env()
        )
        self._kb_lock_decision_timeout_seconds = (
            self._resolve_kb_lock_decision_timeout_seconds_from_env()
        )
        self._internal_retrieval_cache_ttl_seconds = (
            self._resolve_internal_retrieval_cache_ttl_seconds_from_env()
        )
        self._internal_retrieval_cache_max_entries = (
            self._resolve_internal_retrieval_cache_max_entries_from_env()
        )
        self._internal_retrieval_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._kb_lock_warmup_enabled = self._resolve_kb_lock_warmup_enabled_from_env()
        self._kb_lock_warmup_task: asyncio.Task | None = None
        self._upstream_auto_recover_enabled = (
            self._resolve_upstream_auto_recover_enabled_from_env()
        )
        self._upstream_auto_recover_max_retries = (
            self._resolve_upstream_auto_recover_max_retries_from_env()
        )
        self._upstream_auto_recover_base_delay_seconds = (
            self._resolve_upstream_auto_recover_delay_seconds_from_env(
                "STEPFUN_UPSTREAM_AUTO_RECOVER_BASE_DELAY_MS",
                default_ms=DEFAULT_UPSTREAM_AUTO_RECOVER_BASE_DELAY_MS,
                min_ms=100,
                max_ms=10000,
            )
        )
        self._upstream_auto_recover_max_delay_seconds = (
            self._resolve_upstream_auto_recover_delay_seconds_from_env(
                "STEPFUN_UPSTREAM_AUTO_RECOVER_MAX_DELAY_MS",
                default_ms=DEFAULT_UPSTREAM_AUTO_RECOVER_MAX_DELAY_MS,
                min_ms=500,
                max_ms=30000,
            )
        )
        self._upstream_keepalive_enabled = (
            self._resolve_upstream_keepalive_enabled_from_env()
        )
        self._upstream_keepalive_interval_seconds = (
            self._resolve_upstream_auto_recover_delay_seconds_from_env(
                "STEPFUN_UPSTREAM_KEEPALIVE_INTERVAL_MS",
                default_ms=DEFAULT_UPSTREAM_KEEPALIVE_INTERVAL_MS,
                min_ms=5000,
                max_ms=45000,
            )
        )
        self._upstream_keepalive_pong_timeout_seconds = (
            self._resolve_upstream_auto_recover_delay_seconds_from_env(
                "STEPFUN_UPSTREAM_KEEPALIVE_PONG_TIMEOUT_MS",
                default_ms=DEFAULT_UPSTREAM_KEEPALIVE_PONG_TIMEOUT_MS,
                min_ms=500,
                max_ms=15000,
            )
        )
        self._upstream_keepalive_task: asyncio.Task | None = None
        self._upstream_connected_at: float = 0.0
        self._upstream_last_activity_at: float = 0.0
        self._last_upstream_event_type: str = ""
        self._timeout_disconnect_requested = False
        self._connection_epoch = 0
        self._last_disconnect_reason: str | None = None
        self._last_runtime_error: dict[str, str] | None = None
        self._transcript_normalization_service = TranscriptNormalizationService()

    @staticmethod
    def _normalize_connection_epoch(value: Any) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _copy_runtime_error(value: Any) -> dict[str, str] | None:
        if not isinstance(value, dict):
            return None
        code = str(value.get("code") or "").strip()
        message = str(value.get("message") or "").strip()
        if not code and not message:
            return None
        return {
            "code": code,
            "message": message,
        }

    def _build_reconnect_state_payload(self) -> dict[str, Any]:
        return {
            "connection_epoch": self._normalize_connection_epoch(
                self._connection_epoch
            ),
            "request_epoch": int(self.current_request_id or 0),
            "last_disconnect_reason": self._last_disconnect_reason,
            "last_error": self._copy_runtime_error(self._last_runtime_error),
        }

    def _record_disconnect_reason(self, reason: str | None) -> None:
        normalized = str(reason or "").strip()
        if normalized:
            self._last_disconnect_reason = normalized

    def _record_runtime_error(self, code: str, message: str) -> None:
        self._last_runtime_error = self._copy_runtime_error(
            {
                "code": code,
                "message": message,
            }
        )

    def _reset_turn_runtime_state(self) -> None:
        """Clear turn-scoped state that must not leak across reconnects or interrupts."""
        self._pending_grounding_context = ""
        self._pending_blocked_response_text = ""
        self._latest_input_transcript_delta = ""
        self._pending_tool_followup_response = False
        self._awaiting_transcription_after_commit = False
        self._allow_late_transcription_response = False
        self._has_uncommitted_audio = False
        self._active_response = None
        self._function_call_states.clear()
        self._executed_call_ids.clear()

    async def _clear_upstream_generation(self) -> None:
        """Abort any active upstream response and clear buffered audio input."""
        if self.upstream_ws is None:
            return
        await self._send_upstream({"type": "response.cancel"})
        await self._send_upstream({"type": "input_audio_buffer.clear"})

    def _log_grounding_debug(self, event: str, **fields: Any) -> None:
        if not self._grounding_debug_log:
            return
        logger.info(
            f"[GROUNDING_DEBUG] {event}",
            session_id=self.session_id,
            **fields,
        )

    def _log_latency_debug(self, event: str, **fields: Any) -> None:
        if not self._latency_debug_log:
            return
        logger.info(
            f"[LATENCY_DEBUG] {event}",
            session_id=self.session_id,
            **fields,
        )

    def _is_auto_kb_lock_default_enabled(self) -> bool:
        return str(
            os.getenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}

    def _has_explicit_persona_kb_lock_flag(self, policy: dict[str, Any]) -> bool:
        persona_policy = policy.get("persona_policy")
        if not isinstance(persona_policy, dict):
            return False
        persona_tool_policy = persona_policy.get("tool_policy")
        if not isinstance(persona_tool_policy, dict):
            return False
        return "require_kb_grounding" in persona_tool_policy

    def _is_kb_lock_required_for_current_policy(self) -> bool:
        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            return False
        return bool(tool_policy.get("require_kb_grounding", False))

    def _resolve_answerability_mode(self) -> tuple[str, dict[str, Any] | None]:
        diagnostics = self._latest_knowledge_answer_diagnostics
        if not isinstance(diagnostics, dict):
            return "default", None

        answerability = str(diagnostics.get("answerability") or "").strip().lower()
        source_status = str(diagnostics.get("source_status") or "").strip().lower()
        kb_lock_required = self._is_kb_lock_required_for_current_policy()

        if kb_lock_required and answerability in {"blocked", "insufficient"}:
            return "blocked", diagnostics
        if answerability == "partial":
            return "partial", diagnostics
        if answerability in {"blocked", "insufficient"} or source_status in {
            "miss",
            "kb_not_ready",
            "search_failed",
        }:
            return "ungrounded", diagnostics
        return "grounded", diagnostics

    @staticmethod
    def _build_answerability_instruction_overlay(
        mode: str,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        if not isinstance(diagnostics, dict):
            return ""

        answerability = str(diagnostics.get("answerability") or "").strip().lower()
        rewritten_queries = diagnostics.get("rewritten_queries")
        citations = diagnostics.get("citations")
        query_line = ""
        if isinstance(rewritten_queries, list):
            normalized_queries = [
                str(item).strip() for item in rewritten_queries if str(item).strip()
            ]
            if normalized_queries:
                query_line = "\n本轮检索改写：" + "；".join(normalized_queries[:4])
        citation_count = len(citations) if isinstance(citations, list) else 0

        if mode == "partial":
            return (
                "\n【回答约束】当前仅有部分内部证据可用。"
                "你只能回答已被当前内部片段直接支持的部分；未被支持的部分必须明确说“当前内部知识库未提供足够依据”。"
                "禁止把推测、常识补充或模型记忆写成内部事实。"
                f"\n当前 answerability：{answerability or 'partial'}；可引用片段数：{citation_count}"
                f"{query_line}"
            )
        if mode == "ungrounded":
            return (
                "\n【回答约束】当前回答不以内部知识库确认为准。"
                "如果继续回答，只能提供一般性参考，并必须明确标注“以下回答不以内部知识库确认为准”。"
                "不得把一般性知识描述成企业内部资料、正式产品事实、报价、版本承诺或客户案例。"
                f"\n当前 answerability：{answerability or 'unknown'}；可引用片段数：{citation_count}"
                f"{query_line}"
            )
        if mode == "grounded":
            return (
                "\n【回答约束】当前轮应优先依据已命中的内部片段回答；若片段未覆盖某部分，请明确说明不确定。"
                f"\n当前 answerability：{answerability or 'sufficient'}；可引用片段数：{citation_count}"
                f"{query_line}"
            )
        return ""

    def _build_blocked_response_from_answerability(
        self,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        if not isinstance(diagnostics, dict):
            return "当前内部知识库没有足够依据回答这个问题，请补充更具体的产品关键词或版本信息。"
        source_status = str(diagnostics.get("source_status") or "").strip().lower()
        if source_status == "kb_not_ready":
            return "当前内部知识库尚未就绪，暂时无法基于内部资料回答。请稍后重试，或补充更具体的产品关键词。"
        if source_status == "search_failed":
            return "当前内部知识检索失败，暂时无法基于内部资料安全回答。请稍后重试。"
        return "当前内部知识库没有足够依据回答这个问题，请补充更具体的产品关键词或版本信息。"

    @staticmethod
    def _split_response_sentences(text: str) -> list[str]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        sentences = re.findall(r"[^。！？!?]+[。！？!?]?", normalized)
        cleaned = [sentence.strip() for sentence in sentences if sentence.strip()]
        return cleaned or [normalized]

    def _apply_answerability_output_guard(self, response_text: str) -> str:
        diagnostics = self._latest_knowledge_answer_diagnostics
        if not isinstance(diagnostics, dict):
            return response_text

        answerability = str(diagnostics.get("answerability") or "").strip().lower()
        if answerability != "partial":
            return response_text

        citations = diagnostics.get("citations")
        if not isinstance(citations, list) or not citations:
            return "当前内部知识库仅支持部分信息，暂无法确认更多细节。"

        support_texts: list[str] = []
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            for key in ("claim", "snippet"):
                value = str(citation.get(key) or "").strip()
                if value:
                    support_texts.append(value)

        if not support_texts:
            return "当前内部知识库仅支持部分信息，暂无法确认更多细节。"

        kept_sentences: list[str] = []
        for sentence in self._split_response_sentences(response_text):
            compact_sentence = sentence.replace(" ", "")
            if any(
                compact_sentence
                and (
                    compact_sentence in support_text.replace(" ", "")
                    or support_text.replace(" ", "") in compact_sentence
                )
                for support_text in support_texts
            ):
                kept_sentences.append(sentence)

        if kept_sentences:
            return "".join(kept_sentences)
        return "当前内部知识库仅支持部分信息，暂无法确认更多细节。"

    def _get_effective_tool_policy(self) -> dict[str, Any]:
        tool_policy = self._effective_policy.get("tool_policy")
        if isinstance(tool_policy, dict):
            return tool_policy
        return {}

    def _get_max_questions_per_turn(self) -> int:
        raw_value = self._get_effective_tool_policy().get("max_questions_per_turn", 1)
        try:
            return max(1, int(raw_value))
        except (TypeError, ValueError):
            return 1

    def _normalize_transcript(
        self,
        text: str,
        *,
        is_final: bool,
    ) -> TranscriptNormalizationResult:
        return self._transcript_normalization_service.normalize(
            text=text,
            tool_policy=self._get_effective_tool_policy(),
            is_final=is_final,
        )

    @staticmethod
    def _build_transcript_metadata(
        normalization_result: TranscriptNormalizationResult,
        *,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "raw_text": normalization_result.raw_text,
            "normalized_text": normalization_result.normalized_text,
            "replacements": normalization_result.replacements,
        }
        if isinstance(extras, dict):
            metadata.update(extras)
        return metadata

    @staticmethod
    def _resolve_grounding_prefetch_timeout_seconds_from_env() -> float:
        raw_timeout = os.getenv(
            "STEPFUN_GROUNDING_PREFETCH_TIMEOUT_MS",
            str(DEFAULT_GROUNDING_PREFETCH_TIMEOUT_MS),
        )
        try:
            timeout_ms = int(raw_timeout)
        except (TypeError, ValueError):
            timeout_ms = DEFAULT_GROUNDING_PREFETCH_TIMEOUT_MS
        timeout_ms = max(0, min(5000, timeout_ms))
        return timeout_ms / 1000.0

    @staticmethod
    def _resolve_kb_lock_decision_timeout_seconds_from_env() -> float:
        raw_timeout = os.getenv(
            "STEPFUN_KB_LOCK_DECISION_TIMEOUT_MS",
            str(DEFAULT_KB_LOCK_DECISION_TIMEOUT_MS),
        )
        try:
            timeout_ms = int(raw_timeout)
        except (TypeError, ValueError):
            timeout_ms = DEFAULT_KB_LOCK_DECISION_TIMEOUT_MS
        timeout_ms = max(100, min(8000, timeout_ms))
        return timeout_ms / 1000.0

    @staticmethod
    def _resolve_internal_retrieval_cache_ttl_seconds_from_env() -> float:
        raw_timeout = os.getenv(
            "STEPFUN_INTERNAL_RETRIEVAL_CACHE_TTL_MS",
            str(DEFAULT_INTERNAL_RETRIEVAL_CACHE_TTL_MS),
        )
        try:
            timeout_ms = int(raw_timeout)
        except (TypeError, ValueError):
            timeout_ms = DEFAULT_INTERNAL_RETRIEVAL_CACHE_TTL_MS
        timeout_ms = max(0, min(30000, timeout_ms))
        return timeout_ms / 1000.0

    @staticmethod
    def _resolve_internal_retrieval_cache_max_entries_from_env() -> int:
        raw_limit = os.getenv(
            "STEPFUN_INTERNAL_RETRIEVAL_CACHE_MAX_ENTRIES",
            str(DEFAULT_INTERNAL_RETRIEVAL_CACHE_MAX_ENTRIES),
        )
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = DEFAULT_INTERNAL_RETRIEVAL_CACHE_MAX_ENTRIES
        return max(16, min(1024, limit))

    @staticmethod
    def _resolve_kb_lock_warmup_enabled_from_env() -> bool:
        raw_value = os.getenv(
            "STEPFUN_KB_LOCK_WARMUP_ENABLED",
            "true" if DEFAULT_KB_LOCK_WARMUP_ENABLED else "false",
        )
        return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _resolve_upstream_auto_recover_enabled_from_env() -> bool:
        raw_value = os.getenv(
            "STEPFUN_UPSTREAM_AUTO_RECOVER_ENABLED",
            "true" if DEFAULT_UPSTREAM_AUTO_RECOVER_ENABLED else "false",
        )
        return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _resolve_upstream_keepalive_enabled_from_env() -> bool:
        raw_value = os.getenv(
            "STEPFUN_UPSTREAM_KEEPALIVE_ENABLED",
            "true" if DEFAULT_UPSTREAM_KEEPALIVE_ENABLED else "false",
        )
        return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _resolve_upstream_auto_recover_max_retries_from_env() -> int:
        raw_value = os.getenv(
            "STEPFUN_UPSTREAM_AUTO_RECOVER_MAX_RETRIES",
            str(DEFAULT_UPSTREAM_AUTO_RECOVER_MAX_RETRIES),
        )
        try:
            retries = int(raw_value)
        except (TypeError, ValueError):
            retries = DEFAULT_UPSTREAM_AUTO_RECOVER_MAX_RETRIES
        return max(0, min(10, retries))

    @staticmethod
    def _resolve_upstream_auto_recover_delay_seconds_from_env(
        name: str,
        *,
        default_ms: int,
        min_ms: int,
        max_ms: int,
    ) -> float:
        raw_value = os.getenv(name, str(default_ms))
        try:
            delay_ms = int(raw_value)
        except (TypeError, ValueError):
            delay_ms = default_ms
        delay_ms = max(min_ms, min(max_ms, delay_ms))
        return delay_ms / 1000.0

    async def _touch_session_activity(self) -> None:
        """Refresh SessionManager activity for reconnect/timeout decisions."""
        if self.session_id:
            await get_session_manager().update_activity(self.session_id)

    def _mark_upstream_activity(self) -> None:
        self._upstream_last_activity_at = asyncio.get_running_loop().time()

    async def _stop_upstream_keepalive_task(self) -> None:
        keepalive_task = self._upstream_keepalive_task
        self._upstream_keepalive_task = None
        if keepalive_task and not keepalive_task.done():
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass

    def _ensure_upstream_keepalive_task(self) -> None:
        if (
            not self._upstream_keepalive_enabled
            or self.upstream_ws is None
            or not self.running
        ):
            return
        if self._upstream_keepalive_task and not self._upstream_keepalive_task.done():
            return
        self._upstream_keepalive_task = asyncio.create_task(
            self._run_upstream_keepalive_loop(self.upstream_ws)
        )

    async def _send_upstream_keepalive_ping(self, upstream_ws: Any) -> None:
        ping = getattr(upstream_ws, "ping", None)
        if not callable(ping):
            return
        ping_result = ping()
        pong_waiter = (
            await ping_result if inspect.isawaitable(ping_result) else ping_result
        )
        self._mark_upstream_activity()
        if pong_waiter is not None and inspect.isawaitable(pong_waiter):
            await asyncio.wait_for(
                pong_waiter,
                timeout=self._upstream_keepalive_pong_timeout_seconds,
            )

    async def _run_upstream_keepalive_loop(self, upstream_ws: Any) -> None:
        while self.running and self.upstream_ws is upstream_ws:
            await asyncio.sleep(self._upstream_keepalive_interval_seconds)
            if self.upstream_ws is not upstream_ws:
                break
            last_activity_at = max(
                self._upstream_last_activity_at,
                self._upstream_connected_at,
            )
            if last_activity_at > 0:
                idle_seconds = asyncio.get_running_loop().time() - last_activity_at
                if idle_seconds < self._upstream_keepalive_interval_seconds:
                    continue
            try:
                await self._send_upstream_keepalive_ping(upstream_ws)
            except asyncio.CancelledError:
                raise
            except ConnectionClosed:
                break
            except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
                logger.warning(
                    "StepFun upstream keepalive degraded",
                    session_id=self.session_id,
                    error=str(exc),
                )
                break

    def _create_state_snapshot(self) -> SessionStateSnapshot:
        """Persist only reconnect-safe runtime fields for StepFun sales sessions."""
        runtime_state: dict[str, Any] = {}
        if self.current_request_id:
            runtime_state["current_request_id"] = self.current_request_id
        if self._last_emitted_stage:
            runtime_state["last_emitted_stage"] = self._last_emitted_stage
        normalized_score_snapshot = normalize_score_snapshot(
            self._latest_score_snapshot
        )
        if normalized_score_snapshot is not None:
            runtime_state["latest_score_snapshot"] = copy.deepcopy(
                normalized_score_snapshot
            )
        normalized_live_session_summary = coerce_live_session_conclusion_summary(
            self._latest_live_session_summary
        )
        if normalized_live_session_summary is not None:
            runtime_state["latest_live_session_summary"] = copy.deepcopy(
                normalized_live_session_summary
            )
        if isinstance(self._latest_claim_truth, dict):
            runtime_state["latest_claim_truth"] = copy.deepcopy(
                self._latest_claim_truth
            )
        normalized_objection_ledger = normalize_objection_ledger(self._objection_ledger)
        if normalized_objection_ledger is not None:
            runtime_state["objection_ledger"] = copy.deepcopy(
                normalized_objection_ledger
            )
        feedback_pacing_state = self._feedback_pacing_state.to_dict()
        if feedback_pacing_state:
            runtime_state["feedback_pacing_state"] = copy.deepcopy(
                feedback_pacing_state
            )
        if self._coach_health != "healthy" or self._coach_health_reason is not None:
            runtime_state["coach_health"] = self._coach_health_payload()
        runtime_state["reconnect_state"] = self._build_reconnect_state_payload()

        return SessionStateSnapshot(
            session_id=self.session_id or "",
            scenario=self.scenario,
            turn_count=self.turn_count,
            session_status=self.session_status,
            ai_state=self.ai_state,
            runtime_state=runtime_state or None,
            user_id=self.user_id,
        )

    async def _restore_session_state(self, state: SessionStateSnapshot) -> None:
        """Restore reconnect state using the StepFun connection mixin authority."""
        await super()._restore_session_state(state)

    async def _save_session_state(self) -> None:
        """Persist reconnectable state, or clear dirty snapshots after terminal exits."""
        if not self.session_id:
            return

        should_delete_snapshot = (
            self.session_status in TERMINAL_SESSION_STATUSES
            or self._timeout_disconnect_requested
        )
        if should_delete_snapshot:
            result = await self.state_service.delete_state(self.session_id)
            if result.is_success:
                logger.info(
                    "Deleted StepFun session snapshot",
                    session_id=self.session_id,
                    session_status=self.session_status,
                    timeout_disconnect=self._timeout_disconnect_requested,
                )
            else:
                logger.warning(
                    "Failed to delete StepFun session snapshot",
                    session_id=self.session_id,
                    session_status=self.session_status,
                    timeout_disconnect=self._timeout_disconnect_requested,
                    error=result.fallback,
                )
            return

        snapshot = self._create_state_snapshot()
        result = await self.state_service.save_state(snapshot)
        if result.is_success:
            logger.info(
                "Saved StepFun session snapshot",
                session_id=self.session_id,
                turn_count=snapshot.turn_count,
                session_status=snapshot.session_status,
                ai_state=snapshot.ai_state,
            )
        else:
            logger.warning(
                "Failed to save StepFun session snapshot",
                session_id=self.session_id,
                error=result.fallback,
            )

    async def send_message(self, message: dict[str, Any]) -> None:
        """Send SessionManager notifications with reconnect diagnostics."""
        websocket = self._get_active_websocket()
        if not websocket:
            return

        outbound = copy.deepcopy(message)
        if outbound.get("type") == "session_timeout":
            payload = outbound.get("data")
            data = dict(payload) if isinstance(payload, dict) else {}
            data.update(
                {
                    "session_status": self.session_status,
                    "ai_state": self.ai_state,
                    "turn_count": self.turn_count,
                    "disconnect_reason": "session_timeout",
                }
            )
            outbound["data"] = data
            outbound.setdefault("trace_id", get_trace_id())
            self._timeout_disconnect_requested = True
            self._record_disconnect_reason("session_timeout")

        await self.manager.send_json(websocket, outbound)

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ) -> None:
        """Main lifecycle for frontend WS + upstream StepFun WS."""
        resolved_token = resolve_websocket_token(
            query_token=token,
            authorization_header=_get_websocket_header_value(
                websocket,
                "authorization",
            ),
            cookie_header=_get_websocket_header_value(
                websocket,
                "cookie",
            ),
        )
        try:
            payload = verify_token(resolved_token)
            set_trace_id(
                normalize_trace_id(trace_id)
                or normalize_trace_id(payload.get("trace_id", ""))
                or ""
            )
            self.user_id = payload.get("user_id")
        except (JWTError, RuntimeError, ValueError, OSError) as exc:
            logger.warning(f"Token verification failed: {exc}")
            set_trace_id(normalize_trace_id(trace_id) or "")

        existing_state_result = await self.state_service.get_state(session_id)
        existing_state = (
            existing_state_result.value if existing_state_result.is_success else None
        )

        self.websocket = websocket
        self.session_id = session_id
        self._timeout_disconnect_requested = False
        self._connection_epoch = max(
            1, self._normalize_connection_epoch(self._connection_epoch)
        )

        await self.manager.connect(websocket, self.scenario, session_id)

        if not self._stepfun_api_key:
            await self._send_error(
                "[STEPFUN_KEY_MISSING]",
                "未配置 STEPFUN_API_KEY，无法使用 Realtime 模式",
            )
            await self.close(code=4000, reason="STEPFUN_API_KEY missing")
            await self.manager.disconnect(self.scenario, session_id)
            return

        self.running = True

        try:
            await self._load_effective_policy()
            await self._sync_session_state()
            if existing_state and self.session_status in TERMINAL_SESSION_STATUSES:
                await self.state_service.delete_state(session_id)
                existing_state = None
            if existing_state is not None:
                logger.info(f"Reconnection detected for session: {session_id}")
                await self._restore_session_state(existing_state)

            await self._connect_upstream()
            self._upstream_task = asyncio.create_task(self._receive_upstream_events())
            initial_ai_state = (
                self.ai_state
                if self.ai_state in {"idle", "listening"}
                else ("listening" if self.session_status == "in_progress" else "idle")
            )
            await self._send_status(initial_ai_state)

            while self.running:
                try:
                    raw = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                    if raw.get("type") == "websocket.disconnect":
                        self._record_disconnect_reason("client_disconnect")
                        break
                    if raw.get("text") is not None:
                        await self._touch_session_activity()
                        await self._handle_client_text(raw["text"])
                    elif raw.get("bytes") is not None:
                        await self._touch_session_activity()
                        await self._handle_binary_frame(raw["bytes"])
                except TimeoutError:
                    await self._send_heartbeat()

        except WebSocketDisconnect:
            self._record_disconnect_reason("client_disconnect")
            logger.info(f"StepFun WS disconnected: session={session_id}")
        except asyncio.CancelledError:
            logger.info(f"StepFun WS cancelled: session={session_id}")
        except (RuntimeError, ValueError, OSError) as e:
            self._record_disconnect_reason("runtime_error")
            logger.error(f"StepFun WS error: {e}", exc_info=True)
            await self._send_error(
                "[STEPFUN_CONNECTION_ERROR]", "Realtime 语音连接失败"
            )
        finally:
            self.running = False
            await self._cancel_pending_response_after_commit()
            warmup_task = self._kb_lock_warmup_task
            self._kb_lock_warmup_task = None
            if warmup_task and not warmup_task.done():
                warmup_task.cancel()
                try:
                    await warmup_task
                except asyncio.CancelledError:
                    pass
            if self._upstream_task:
                self._upstream_task.cancel()
                try:
                    await self._upstream_task
                except (asyncio.CancelledError, ConnectionClosed):
                    pass
            await self._close_upstream()
            await self._save_session_state()
            await self.manager.disconnect(self.scenario, session_id)

    async def _load_effective_policy(self) -> None:
        """Load effective voice policy from session snapshot or resolver service."""
        self._effective_policy = {}
        async with AsyncSessionLocal() as db:
            session_result = await db.execute(
                select(PracticeSession).where(
                    PracticeSession.session_id == self.session_id
                )
            )
            session = session_result.scalar_one_or_none()
            if not session:
                logger.warning(
                    f"Session not found when loading voice policy: {self.session_id}"
                )
                return

            session_any = cast(Any, session)
            self._session_agent_id = _optional_runtime_text(
                getattr(session, "agent_id", None)
            )
            self._session_persona_id = _optional_runtime_text(
                getattr(session, "persona_id", None)
            )
            self._session_user_id = _optional_runtime_text(
                getattr(session, "user_id", None)
            )
            await self._refresh_sales_stage_runtime_config(db)

            snapshot_raw = getattr(session, "voice_policy_snapshot", None)
            snapshot = (
                snapshot_raw
                if isinstance(snapshot_raw, dict)
                else None
            )

            policy_source = "snapshot"
            if snapshot:
                self._effective_policy = snapshot
            else:
                policy_service = VoiceRuntimePolicyService(db)
                resolved_policy = await policy_service.resolve_effective_policy(
                    agent_id=self._session_agent_id,
                    persona_id=self._session_persona_id,
                    voice_mode_override=_optional_runtime_text(
                        getattr(session, "voice_mode", None)
                    ),
                    runtime_profile_override=_optional_runtime_text(
                        getattr(session, "voice_runtime_profile_id", None)
                    ),
                )
                self._effective_policy = resolved_policy
                session_any.voice_policy_snapshot = self._effective_policy
                session_any.voice_mode = self._effective_policy.get(
                    "voice_mode",
                    _optional_runtime_text(getattr(session, "voice_mode", None))
                    or "legacy",
                )
                session_any.voice_runtime_profile_id = self._effective_policy.get(
                    "runtime_profile_id"
                )
                await db.commit()
                policy_source = "resolved"

            guardrail_applied = self._enforce_tool_policy_guardrails()
            if guardrail_applied:
                session_any.voice_policy_snapshot = self._effective_policy
                await db.commit()

            self._stepfun_model = str(
                self._effective_policy.get("model_name", self._stepfun_model)
            )
            self._stepfun_voice = str(
                self._effective_policy.get("voice_name", self._stepfun_voice)
            )
            self._stepfun_temperature = float(
                self._effective_policy.get("temperature", self._stepfun_temperature)
            )
            self._stepfun_input_audio_format = str(
                self._effective_policy.get(
                    "input_audio_format", self._stepfun_input_audio_format
                )
            )
            self._stepfun_output_audio_format = str(
                self._effective_policy.get(
                    "output_audio_format", self._stepfun_output_audio_format
                )
            )
            self._stepfun_output_sample_rate = int(
                self._effective_policy.get(
                    "output_sample_rate", self._stepfun_output_sample_rate
                )
            )
            self._stepfun_playback_rate = float(
                self._effective_policy.get(
                    "playback_rate",
                    self._stepfun_playback_rate,
                )
            )
            self._stepfun_instructions = str(
                self._effective_policy.get("instructions", self._stepfun_instructions)
            )
            self._instruction_contract_hash = str(
                self._effective_policy.get("instruction_contract_hash")
                or build_instruction_contract_hash(self._stepfun_instructions)
            )
            self._ensure_knowledge_runtime_metrics()
            tool_policy = self._effective_policy.get("tool_policy")
            if not isinstance(tool_policy, dict):
                tool_policy = {}
            knowledge_base_ids = self._effective_policy.get("knowledge_base_ids")
            if not isinstance(knowledge_base_ids, list):
                knowledge_base_ids = []
            logger.info(
                "StepFun policy loaded",
                session_id=self.session_id,
                policy_source=policy_source,
                voice_mode=str(self._effective_policy.get("voice_mode") or ""),
                internal_retrieval_enabled=bool(
                    tool_policy.get("enable_internal_retrieval", False)
                ),
                retrieval_priority=str(tool_policy.get("retrieval_priority") or ""),
                network_access_mode=str(tool_policy.get("network_access_mode") or ""),
                instruction_contract_hash=self._instruction_contract_hash,
                knowledge_base_count=len(knowledge_base_ids),
            )

    @staticmethod
    def _normalize_kb_ids(raw_kb_ids: Any) -> list[str]:
        if not isinstance(raw_kb_ids, list):
            return []
        normalized: list[str] = []
        for item in raw_kb_ids:
            kb_id = str(item).strip()
            if not kb_id:
                continue
            normalized.append(kb_id)
        return sorted(set(normalized))

    @classmethod
    def _build_policy_core_signature(cls, policy: dict[str, Any]) -> dict[str, Any]:
        tool_policy = policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}
        persona_policy = policy.get("persona_policy")
        if not isinstance(persona_policy, dict):
            persona_policy = {}
        persona_tool_policy = persona_policy.get("tool_policy")
        if not isinstance(persona_tool_policy, dict):
            persona_tool_policy = {}

        return {
            "voice_mode": str(policy.get("voice_mode") or ""),
            "runtime_profile_id": str(policy.get("runtime_profile_id") or ""),
            "instructions": str(policy.get("instructions") or "").strip(),
            "instruction_contract_hash": str(
                policy.get("instruction_contract_hash") or ""
            ),
            "playback_rate": float(policy.get("playback_rate") or 1.0),
            "knowledge_base_ids": cls._normalize_kb_ids(
                policy.get("knowledge_base_ids")
            ),
            "tool_policy": dict(tool_policy),
            "persona_policy": {
                "version": persona_policy.get("version"),
                "system_prompt": str(persona_policy.get("system_prompt") or "").strip(),
                "knowledge_base_ids": cls._normalize_kb_ids(
                    persona_policy.get("knowledge_base_ids")
                ),
                "tool_policy": dict(persona_tool_policy),
            },
        }

    @classmethod
    def _is_policy_snapshot_stale(
        cls,
        *,
        snapshot: dict[str, Any],
        resolved_policy: dict[str, Any],
    ) -> bool:
        snapshot_signature = cls._build_policy_core_signature(snapshot)
        resolved_signature = cls._build_policy_core_signature(resolved_policy)
        return snapshot_signature != resolved_signature

    @staticmethod
    def _merge_resolved_policy_with_snapshot_overlays(
        *,
        resolved_policy: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        merged_policy = dict(resolved_policy)
        runtime_metrics = snapshot.get("runtime_metrics")
        if isinstance(runtime_metrics, dict):
            merged_policy["runtime_metrics"] = runtime_metrics
        if "agent_persona_override_config" in snapshot:
            merged_policy["agent_persona_override_config"] = snapshot.get(
                "agent_persona_override_config"
            )
        return merged_policy

    def _enforce_tool_policy_guardrails(self) -> bool:
        policy = self._effective_policy
        if not isinstance(policy, dict):
            self._effective_policy = {}
            return False

        changed = False
        knowledge_base_ids = policy.get("knowledge_base_ids")
        if not isinstance(knowledge_base_ids, list):
            knowledge_base_ids = []
            changed = True
        normalized_kb_ids = [
            str(item).strip() for item in knowledge_base_ids if str(item).strip()
        ]
        has_bound_knowledge_base = bool(normalized_kb_ids)

        tool_policy = policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}
            changed = True

        network_access_mode = str(
            tool_policy.get("network_access_mode") or "off"
        ).lower()
        if network_access_mode not in {"off", "controlled"}:
            network_access_mode = "off"
            changed = True
        if tool_policy.get("network_access_mode") != network_access_mode:
            tool_policy["network_access_mode"] = network_access_mode
            changed = True

        enforcement_level = str(
            tool_policy.get("enforcement_level") or "strict"
        ).lower()
        if enforcement_level not in {"strict", "best_effort"}:
            enforcement_level = "strict"
            changed = True
        if tool_policy.get("enforcement_level") != enforcement_level:
            tool_policy["enforcement_level"] = enforcement_level
            changed = True

        allow_web_search_without_kb = bool(
            tool_policy.get("allow_web_search_without_kb", False)
        )
        if (
            tool_policy.get("allow_web_search_without_kb")
            != allow_web_search_without_kb
        ):
            tool_policy["allow_web_search_without_kb"] = allow_web_search_without_kb
            changed = True

        has_raw_kb_lock_flag = "require_kb_grounding" in tool_policy
        require_kb_grounding = bool(tool_policy.get("require_kb_grounding", False))
        retrieval_priority = (
            str(tool_policy.get("retrieval_priority") or "").strip().lower()
        )
        has_explicit_persona_kb_lock_flag = self._has_explicit_persona_kb_lock_flag(
            policy
        )
        auto_kb_lock_default_applied = False
        if (
            not require_kb_grounding
            and has_bound_knowledge_base
            and self._is_auto_kb_lock_default_enabled()
            and not has_explicit_persona_kb_lock_flag
        ):
            require_kb_grounding = True
            auto_kb_lock_default_applied = True
            tool_policy["require_kb_grounding"] = True
            changed = True
        if tool_policy.get("require_kb_grounding") != require_kb_grounding:
            tool_policy["require_kb_grounding"] = require_kb_grounding
            changed = True

        if has_bound_knowledge_base and not bool(
            tool_policy.get("enable_internal_retrieval", False)
        ):
            tool_policy["enable_internal_retrieval"] = True
            changed = True

        if has_bound_knowledge_base and bool(
            tool_policy.get("enable_web_search", False)
        ):
            tool_policy["enable_web_search"] = False
            changed = True

        if (
            has_bound_knowledge_base
            and require_kb_grounding
            and retrieval_priority != "kb_only"
        ):
            tool_policy["retrieval_priority"] = "kb_only"
            retrieval_priority = "kb_only"
            changed = True

        if (
            not has_bound_knowledge_base
            and not allow_web_search_without_kb
            and bool(tool_policy.get("enable_web_search", False))
        ):
            tool_policy["enable_web_search"] = False
            changed = True

        if network_access_mode == "off" and bool(
            tool_policy.get("enable_web_search", False)
        ):
            tool_policy["enable_web_search"] = False
            changed = True

        if require_kb_grounding and not bool(
            tool_policy.get("enable_internal_retrieval", False)
        ):
            tool_policy["enable_internal_retrieval"] = True
            changed = True

        if require_kb_grounding and bool(tool_policy.get("enable_web_search", False)):
            tool_policy["enable_web_search"] = False
            changed = True

        if require_kb_grounding and retrieval_priority != "kb_only":
            tool_policy["retrieval_priority"] = "kb_only"
            retrieval_priority = "kb_only"
            changed = True

        # `kb_only` must be equivalent to strict KB lock, otherwise model can still
        # generate from parametric memory when retrieval misses or is weak.
        if (
            has_bound_knowledge_base
            and retrieval_priority == "kb_only"
            and not require_kb_grounding
        ):
            require_kb_grounding = True
            tool_policy["require_kb_grounding"] = True
            changed = True

        source = policy.get("source")
        if not isinstance(source, dict):
            source = {}
            changed = True
        if auto_kb_lock_default_applied:
            source.setdefault("kb_lock_default", "auto_enabled_when_kb_bound")
            if has_raw_kb_lock_flag:
                source.setdefault(
                    "kb_lock_legacy_snapshot_backfill",
                    "require_kb_grounding_false_to_true",
                )
        if (
            has_bound_knowledge_base
            and retrieval_priority == "kb_only"
            and require_kb_grounding
        ):
            source.setdefault("kb_lock_enforced_by_retrieval_priority", "kb_only")

        if (
            require_kb_grounding
            and str(policy.get("turn_detection") or "").strip().lower() == "server_vad"
        ):
            policy["turn_detection"] = None
            source["turn_detection_enforcement"] = "manual_commit_required_by_kb_lock"
            changed = True

        enforcement_reason = ""
        if network_access_mode == "off":
            enforcement_reason = "network_off"
        elif require_kb_grounding and has_bound_knowledge_base:
            enforcement_reason = "kb_lock_enforced"
        elif require_kb_grounding:
            enforcement_reason = "kb_lock_unbound"
        elif has_bound_knowledge_base:
            enforcement_reason = "kb_internal_only"
        elif not allow_web_search_without_kb:
            enforcement_reason = "no_kb_no_web"

        if (
            enforcement_reason
            and source.get("tool_policy_enforcement") != enforcement_reason
        ):
            source["tool_policy_enforcement"] = enforcement_reason
            changed = True

        if not changed:
            return False

        instructions = str(policy.get("instructions") or "").strip()
        if not instructions:
            instructions = VoiceInstructionCompiler.compile_base_contract(
                policy=policy,
                agent=None,
                persona=None,
            ).base_instructions
        if (
            str(tool_policy.get("network_access_mode") or "").lower() == "off"
            and "禁止联网检索" not in instructions
        ):
            instructions = (
                f"{instructions}\n\n【执行约束补丁】\n- 禁止联网检索，禁止引用外部实时信息。"
                if instructions
                else "【执行约束补丁】\n- 禁止联网检索，禁止引用外部实时信息。"
            )

        policy["knowledge_base_ids"] = normalized_kb_ids
        policy["tool_policy"] = tool_policy
        policy["network_access_mode"] = str(
            tool_policy.get("network_access_mode") or "off"
        )
        policy["instructions"] = instructions
        policy["instruction_contract_hash"] = build_instruction_contract_hash(
            instructions
        )
        policy["source"] = source
        self._effective_policy = policy
        self._log_grounding_debug(
            "policy_guardrail_applied",
            kb_count=len(normalized_kb_ids),
        )
        return True

    @staticmethod
    def _merge_sales_stage_runtime_config(
        agent_capabilities_config: Any,
        persona_behavior_config: Any,
    ) -> dict[str, Any]:
        """Merge sales-stage config with Agent as base and Persona as override."""
        merged: dict[str, Any] = {"enabled": True}

        if isinstance(agent_capabilities_config, dict):
            agent_stage_config = agent_capabilities_config.get("sales_stage")
            if isinstance(agent_stage_config, dict):
                merged.update(agent_stage_config)

        if isinstance(persona_behavior_config, dict):
            persona_stage_overrides = persona_behavior_config.get("sales_stage")
            if isinstance(persona_stage_overrides, dict):
                merged.update(persona_stage_overrides)

        return merged

    @staticmethod
    def _merge_capability_runtime_config(
        *,
        capability_key: str,
        agent_capabilities_config: Any,
        persona_behavior_config: Any,
        default_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Merge capability config with Agent as base and Persona as override."""
        merged: dict[str, Any] = {"enabled": True}
        if isinstance(default_config, dict):
            merged.update(default_config)

        if isinstance(agent_capabilities_config, dict):
            agent_config = agent_capabilities_config.get(capability_key)
            if isinstance(agent_config, dict):
                merged.update(agent_config)

        if isinstance(persona_behavior_config, dict):
            persona_overrides = persona_behavior_config.get(capability_key)
            if isinstance(persona_overrides, dict):
                merged.update(persona_overrides)

        return merged

    async def _refresh_sales_stage_runtime_config(self, db: AsyncSession) -> None:
        """Load stage runtime config from Agent/Persona and rebuild capability."""
        agent_capabilities_config: dict[str, Any] = {}
        persona_behavior_config: dict[str, Any] = {}
        persona_scoring_weights: list[dict[str, Any]] | None = None

        if self._session_agent_id:
            agent_result = await db.execute(
                select(Agent.capabilities_config).where(
                    Agent.id == self._session_agent_id
                )
            )
            agent_raw = agent_result.scalar_one_or_none()
            if isinstance(agent_raw, dict):
                agent_capabilities_config = agent_raw

        if self._session_persona_id:
            persona_result = await db.execute(
                select(Persona.behavior_config, Persona.scoring_weights).where(
                    Persona.id == self._session_persona_id
                )
            )
            persona_row = persona_result.first()
            if persona_row:
                persona_behavior_raw, persona_scoring_raw = persona_row
                if isinstance(persona_behavior_raw, dict):
                    persona_behavior_config = persona_behavior_raw
                if isinstance(persona_scoring_raw, list):
                    persona_scoring_weights = persona_scoring_raw

        self._agent_capabilities_config = agent_capabilities_config
        self._persona_behavior_config = persona_behavior_config
        self._persona_scoring_weights = persona_scoring_weights

        runtime_config = self._merge_sales_stage_runtime_config(
            agent_capabilities_config,
            persona_behavior_config,
        )

        try:
            self._sales_stage_runtime_config = runtime_config
            self._sales_stage_enabled = bool(runtime_config.get("enabled", True))
            self._sales_stage_capability = SalesStageCapability(runtime_config)
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Invalid sales-stage runtime config, fallback to defaults",
                session_id=self.session_id,
                error=str(exc),
            )
            self._sales_stage_runtime_config = {"enabled": True}
            self._sales_stage_enabled = True
            self._sales_stage_capability = SalesStageCapability(
                self._sales_stage_runtime_config
            )

        fuzzy_runtime_config = self._merge_capability_runtime_config(
            capability_key="fuzzy_detection",
            agent_capabilities_config=agent_capabilities_config,
            persona_behavior_config=persona_behavior_config,
            default_config={"enabled": True},
        )
        try:
            self._fuzzy_detection_runtime_config = fuzzy_runtime_config
            self._fuzzy_detection_enabled = bool(
                fuzzy_runtime_config.get("enabled", True)
            )
            self._fuzzy_detection_capability = FuzzyDetectionCapability(
                fuzzy_runtime_config
            )
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Invalid fuzzy-detection runtime config, fallback to defaults",
                session_id=self.session_id,
                error=str(exc),
            )
            self._fuzzy_detection_runtime_config = {"enabled": True}
            self._fuzzy_detection_enabled = True
            self._fuzzy_detection_capability = FuzzyDetectionCapability(
                self._fuzzy_detection_runtime_config
            )

        scoring_runtime_config = self._merge_capability_runtime_config(
            capability_key="realtime_scoring",
            agent_capabilities_config=agent_capabilities_config,
            persona_behavior_config=persona_behavior_config,
            default_config={"enabled": True},
        )
        if (
            persona_scoring_weights
            and isinstance(persona_scoring_weights, list)
            and not isinstance(scoring_runtime_config.get("dimensions"), list)
        ):
            scoring_runtime_config["dimensions"] = persona_scoring_weights

        try:
            self._realtime_scoring_runtime_config = scoring_runtime_config
            self._realtime_scoring_enabled = bool(
                scoring_runtime_config.get("enabled", True)
            )
            self._realtime_scoring_capability = RealtimeScoringCapability(
                scoring_runtime_config
            )
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Invalid realtime-scoring runtime config, fallback to defaults",
                session_id=self.session_id,
                error=str(exc),
            )
            self._realtime_scoring_runtime_config = {"enabled": True}
            self._realtime_scoring_enabled = True
            self._realtime_scoring_capability = RealtimeScoringCapability(
                self._realtime_scoring_runtime_config
            )

        self._sales_stage_context = None
        self._feedback_context = None
        self._last_emitted_stage = None
        self._latest_action_card = None
        self._feedback_pacing_state = RealtimeFeedbackPacingState()

    async def _sync_session_state(self) -> None:
        if not self.session_id:
            return

        try:
            async with AsyncSessionLocal() as db:
                lifecycle_service = SessionLifecycleService(db)
                (
                    session,
                    scenario_type,
                ) = await lifecycle_service.get_session_with_scenario(self.session_id)
                if session:
                    self.session_status = str(session.status or "preparing")
                    self.session_scenario_type = scenario_type or "sales"
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning(f"Failed to sync StepFun lifecycle state: {exc}")

    def _apply_latest_scores_to_session(self, session: PracticeSession) -> None:
        """Sync latest realtime score snapshot into session-level score fields."""
        normalized_score_snapshot = normalize_score_snapshot(
            self._latest_score_snapshot
        )
        evaluable = self.turn_count > 0
        not_evaluable_reason = None if evaluable else "INSUFFICIENT_TURN_DATA"

        if normalized_score_snapshot is None:
            setattr(
                session,
                "effectiveness_snapshot",
                evaluate_effectiveness_snapshot(
                metrics=build_sales_effectiveness_metrics(
                    overall_score=0.0,
                    logic_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    turn_count=max(0, self.turn_count),
                ),
                main_capability_passed=False,
                evaluable=False,
                not_evaluable_reason="INSUFFICIENT_TURN_DATA",
                ),
            )
            logger.info(
                "practice_session_evidence_not_evaluable",
                session_id=self.session_id,
                evidence_source="stepfun_runtime",
                not_evaluable_reason="INSUFFICIENT_TURN_DATA",
                turn_count=max(0, self.turn_count),
            )
            return

        self._latest_score_snapshot = normalized_score_snapshot

        try:
            overall_score = float(normalized_score_snapshot.get("overall_score") or 0.0)
        except (TypeError, ValueError):
            overall_score = 0.0
        overall_score = max(0.0, min(100.0, overall_score))

        rollups = build_sales_rollup_scores(
            overall_score=overall_score,
            dimension_scores=normalized_score_snapshot.get("dimension_scores"),
        )
        logic_score = _optional_runtime_score(rollups.get("logic_score")) or 0.0
        accuracy_score = _optional_runtime_score(rollups.get("accuracy_score")) or 0.0
        completeness_score = (
            _optional_runtime_score(rollups.get("completeness_score")) or 0.0
        )
        setattr(session, "logic_score", logic_score)
        setattr(session, "accuracy_score", accuracy_score)
        setattr(session, "completeness_score", completeness_score)

        snapshot = evaluate_effectiveness_snapshot(
            metrics=build_sales_effectiveness_metrics(
                overall_score=overall_score,
                dimension_scores=normalized_score_snapshot.get("dimension_scores"),
                logic_score=logic_score,
                accuracy_score=accuracy_score,
                completeness_score=completeness_score,
                turn_count=max(0, self.turn_count),
            ),
            main_capability_passed=overall_score >= 70.0,
            evaluable=evaluable,
            not_evaluable_reason=not_evaluable_reason,
        )
        setattr(session, "effectiveness_snapshot", snapshot)

        if snapshot.get("evaluable", False):
            logger.info(
                "practice_session_evidence_persisted",
                session_id=self.session_id,
                evidence_scope="session",
                evidence_source="stepfun_runtime",
                overall_score=overall_score,
                turn_count=max(0, self.turn_count),
            )
        else:
            logger.info(
                "practice_session_evidence_not_evaluable",
                session_id=self.session_id,
                evidence_source="stepfun_runtime",
                not_evaluable_reason=snapshot.get("not_evaluable_reason"),
                turn_count=max(0, self.turn_count),
            )

    async def _apply_lifecycle_action(
        self, action: SessionLifecycleAction
    ) -> object | None:
        if not self.session_id:
            return None

        try:
            async with AsyncSessionLocal() as db:
                lifecycle_service = SessionLifecycleService(db)
                (
                    session,
                    scenario_type,
                ) = await lifecycle_service.get_session_with_scenario(self.session_id)
                if not session:
                    await self._send_error("[SESSION_NOT_FOUND]", "会话不存在")
                    return None

                self.session_scenario_type = scenario_type or "sales"

                try:
                    transition = await lifecycle_service.transition(
                        session=session,
                        scenario_type=self.session_scenario_type,
                        action=cast(SessionLifecycleAction, action),
                    )
                except InvalidSessionTransitionError as exc:
                    await db.rollback()
                    self.session_status = str(session.status or self.session_status)
                    await self._send_error("[INVALID_SESSION_TRANSITION]", exc.message)
                    await self._send_status(
                        "idle" if self.session_status != "in_progress" else "listening"
                    )
                    return None

                if action == "end":
                    self._apply_latest_scores_to_session(session)

                await db.commit()
                await lifecycle_service.trigger_report_generation_if_needed(transition)
                self.session_status = transition.to_status
                return transition
        except (RuntimeError, ValueError, OSError) as exc:
            logger.error(f"Failed to apply StepFun lifecycle action {action}: {exc}")
            await self._send_error("[SESSION_LIFECYCLE_FAILED]", "会话状态更新失败")
            return None

    async def _ensure_input_allowed(self, msg_type: str) -> bool:
        if SessionLifecycleService.is_input_allowed(self.session_status):
            return True

        if self.session_status == "paused":
            code = "[SESSION_PAUSED]"
            message = f"当前会话已暂停，拒绝 {msg_type}"
        elif self.session_status == "preparing":
            code = "[SESSION_NOT_STARTED]"
            message = f"会话尚未开始，拒绝 {msg_type}"
        else:
            code = "[SESSION_NOT_ACTIVE]"
            message = f"会话状态为 {self.session_status}，拒绝 {msg_type}"

        await self._send_error(code, message)
        await self._send_status("idle")
        return False

    async def _connect_upstream(self) -> None:
        """Connect to StepFun realtime WebSocket and initialize session."""
        query = urlencode({"model": self._stepfun_model})
        endpoint = f"{self._stepfun_url}?{query}"
        headers = {"Authorization": f"Bearer {self._stepfun_api_key}"}

        logger.info(f"Connecting StepFun realtime: model={self._stepfun_model}")
        self.upstream_ws = await websockets.connect(
            endpoint, additional_headers=headers
        )
        now = asyncio.get_running_loop().time()
        self._upstream_connected_at = now
        self._upstream_last_activity_at = now
        self._last_upstream_event_type = ""

        turn_detection_value = None
        if self._effective_policy.get("turn_detection") == "server_vad":
            turn_detection_value = {"type": "server_vad"}

        session_payload: dict = {
            "type": "session.update",
            "session": {
                "voice": self._stepfun_voice,
                "temperature": self._stepfun_temperature,
                "input_audio_format": self._stepfun_input_audio_format,
                "output_audio_format": self._stepfun_output_audio_format,
                "turn_detection": turn_detection_value,
            },
        }
        if self._stepfun_input_transcription_enabled:
            input_audio_transcription: dict[str, Any] = {}
            if self._stepfun_input_transcription_language:
                input_audio_transcription["language"] = (
                    self._stepfun_input_transcription_language
                )
            if self._stepfun_input_transcription_model:
                input_audio_transcription["model"] = (
                    self._stepfun_input_transcription_model
                )
            if input_audio_transcription:
                session_payload["session"]["input_audio_transcription"] = (
                    input_audio_transcription
                )
        if self._stepfun_instructions:
            session_payload["session"]["instructions"] = self._stepfun_instructions
        tools = self._enforce_stepfun_tool_guardrails(
            self._build_stepfun_tools_from_policy()
        )
        knowledge_base_ids = self._effective_policy.get("knowledge_base_ids")
        has_bound_knowledge_base = isinstance(knowledge_base_ids, list) and bool(
            [item for item in knowledge_base_ids if str(item).strip()]
        )
        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}
        logger.info(
            "StepFun tools prepared",
            session_id=self.session_id,
            tool_types=[str(tool.get("type") or "") for tool in tools],
            kb_bound=has_bound_knowledge_base,
            network_access_mode=str(tool_policy.get("network_access_mode") or ""),
            input_transcription_enabled=self._stepfun_input_transcription_enabled,
        )
        if tools:
            session_payload["session"]["tools"] = tools

        await self._send_upstream(session_payload)
        self._ensure_upstream_keepalive_task()
        logger.info("StepFun session.update sent")
        await self._maybe_start_kb_lock_warmup()

    async def _close_upstream(self) -> None:
        """Close upstream connection safely."""
        await self._stop_upstream_keepalive_task()
        if self.upstream_ws:
            try:
                await self.upstream_ws.close()
            except (RuntimeError, ValueError, OSError):
                pass
            self.upstream_ws = None
        self._upstream_connected_at = 0.0
        self._upstream_last_activity_at = 0.0

    async def _maybe_start_kb_lock_warmup(self) -> None:
        if not self._kb_lock_warmup_enabled:
            return
        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            return
        if not bool(tool_policy.get("require_kb_grounding", False)):
            return

        kb_ids = self._effective_policy.get("knowledge_base_ids")
        if not isinstance(kb_ids, list):
            kb_ids = []
        normalized_kb_ids = [str(item).strip() for item in kb_ids if str(item).strip()]
        if not normalized_kb_ids:
            return

        if self._kb_lock_warmup_task and not self._kb_lock_warmup_task.done():
            return

        self._kb_lock_warmup_task = asyncio.create_task(
            self._run_kb_lock_warmup(normalized_kb_ids)
        )

    async def _run_kb_lock_warmup(self, kb_ids: list[str]) -> None:
        started_at = asyncio.get_running_loop().time()
        chromadb_warmed = False
        embedding_client_warmed = False
        try:
            async with AsyncSessionLocal() as db:
                knowledge_service = KnowledgeService(db)
                _ = await knowledge_service.get_search_health(kb_ids=kb_ids)
                chromadb_warmed = True

            embedding_service = get_embedding_service()
            get_client = getattr(embedding_service, "_get_client", None)
            if embedding_service.is_configured and callable(get_client):
                maybe_client = get_client()
                if asyncio.iscoroutine(maybe_client):
                    await maybe_client
                embedding_client_warmed = True

            self._log_grounding_debug(
                "kb_lock_warmup_completed",
                kb_count=len(kb_ids),
                chromadb_warmed=chromadb_warmed,
                embedding_client_warmed=embedding_client_warmed,
                duration_ms=round(
                    (asyncio.get_running_loop().time() - started_at) * 1000, 1
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "KB lock warmup degraded",
                session_id=self.session_id,
                error=str(exc),
                kb_count=len(kb_ids),
                chromadb_warmed=chromadb_warmed,
                embedding_client_warmed=embedding_client_warmed,
            )

    async def _handle_client_text(self, raw_text: str) -> None:
        """Parse and route frontend JSON messages."""
        try:
            message = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from frontend")
            return

        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "audio_chunk":
            if not await self._ensure_input_allowed("audio_chunk"):
                return
            interrupt = data.get("interrupt", False)
            if interrupt:
                await self._handle_interrupt("user_speaking")
                return
            audio = data.get("audio")
            if audio:
                await self._send_upstream(
                    {"type": "input_audio_buffer.append", "audio": audio}
                )
                self._has_uncommitted_audio = True

        elif msg_type == "audio_end":
            if not await self._ensure_input_allowed("audio_end"):
                return
            await self._commit_and_respond()

        elif msg_type == "user_speaking":
            speaking = data.get("speaking", False)
            if not speaking:
                if SessionLifecycleService.is_input_allowed(self.session_status):
                    await self._commit_and_respond()
            else:
                if not await self._ensure_input_allowed("user_speaking"):
                    return

        elif msg_type == "text":
            text = self._extract_text_payload(data)
            if text:
                if not await self._ensure_input_allowed("text"):
                    return
                turn_number = self.turn_count + 1
                sales_stage = await self._analyze_and_emit_sales_stage(
                    user_text=text,
                    turn_number=turn_number,
                )
                realtime_analysis = await self._run_realtime_feedback(
                    user_text=text,
                    turn_number=turn_number,
                    sales_stage=sales_stage,
                )
                await self._persist_message(
                    turn_number=turn_number,
                    role="user",
                    content=text,
                    sales_stage=sales_stage,
                    analysis_data=realtime_analysis,
                )
                await self._send_upstream(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": text}],
                        },
                    }
                )
                try:
                    await self._prepare_grounding_context(text)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        f"Failed to prepare grounding context for text message: {exc}",
                        exc_info=True,
                    )
                    await self._send_error(
                        "[GROUNDING_PREPARE_FAILED]",
                        "知识检索暂时不可用，请稍后重试。",
                    )
                    return

                try:
                    await self._create_response(count_turn=True)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        f"Failed to create response for text message: {exc}",
                        exc_info=True,
                    )
                    await self._send_error(
                        "[RESPONSE_CREATE_FAILED]",
                        "响应生成暂时失败，请重试。",
                    )

        elif msg_type == "interrupt":
            reason = data.get("reason", "manual")
            await self._handle_interrupt(reason)

        elif msg_type == "control":
            action = data.get("action", "")
            if action == "start":
                transition = await self._apply_lifecycle_action("start")
                if transition:
                    await self._send_status("listening")
            elif action == "end":
                transition = await self._apply_lifecycle_action("end")
                if transition:
                    await self._handle_session_end()
            elif action == "pause":
                transition = await self._apply_lifecycle_action("pause")
                if transition:
                    await self._cancel_pending_response_after_commit()
                    self._pending_grounding_context = ""
                    self._pending_blocked_response_text = ""
                    await self._send_upstream({"type": "response.cancel"})
                    await self._send_upstream({"type": "input_audio_buffer.clear"})
                    await self._send_status("idle")
            elif action == "resume":
                transition = await self._apply_lifecycle_action("resume")
                if transition:
                    await self._send_status("listening")

        elif msg_type == "pause":
            transition = await self._apply_lifecycle_action("pause")
            if transition:
                await self._cancel_pending_response_after_commit()
                self._pending_grounding_context = ""
                self._pending_blocked_response_text = ""
                await self._send_upstream({"type": "response.cancel"})
                await self._send_upstream({"type": "input_audio_buffer.clear"})
                await self._send_status("idle")

        elif msg_type == "resume":
            transition = await self._apply_lifecycle_action("resume")
            if transition:
                await self._send_status("listening")

        elif msg_type == "negotiate":
            runtime_options = data if isinstance(data, dict) else {}
            await self.manager.send_json(
                self.websocket,
                {
                    "type": "negotiate_ack",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "trace_id": get_trace_id(),
                    "data": {
                        "accepted": True,
                        "prefer_binary": bool(
                            runtime_options.get("prefer_binary", False)
                        ),
                    },
                },
            )

    async def _handle_binary_frame(self, data: bytes) -> None:
        """Handle binary audio frames from frontend."""
        if len(data) < 2:
            return

        frame_type = data[0]
        payload = data[1:]

        if frame_type == self.BINARY_AUDIO_INTERRUPT:
            await self._handle_interrupt("user_speaking")
            return

        if frame_type != self.BINARY_AUDIO_CHUNK or not payload:
            return

        if not await self._ensure_input_allowed("audio_chunk_binary"):
            return

        audio_b64 = base64.b64encode(payload).decode("utf-8")
        await self._send_upstream(
            {"type": "input_audio_buffer.append", "audio": audio_b64}
        )
        self._has_uncommitted_audio = True

    async def _ensure_feedback_context(self) -> None:
        """Initialize context used by fuzzy detection and realtime scoring."""
        if self._feedback_context is not None:
            return

        self._feedback_context = AgentContext(
            session_id=self.session_id or "",
            agent_id=self._session_agent_id or "unknown-agent",
            persona_id=self._session_persona_id or "unknown-persona",
            user_id=self._session_user_id or "unknown-user",
            state={},
            conversation_history=[],
            agent_config={
                "capabilities_config": self._agent_capabilities_config,
                "default_knowledge_base_ids": self._effective_policy.get(
                    "knowledge_base_ids", []
                ),
            },
            persona_config={
                **self._persona_behavior_config,
                "scoring_weights": self._persona_scoring_weights or [],
            },
            turn_count=max(0, self.turn_count),
        )

        if self._fuzzy_detection_enabled:
            await self._fuzzy_detection_capability.on_session_start(
                self._feedback_context
            )
        if self._realtime_scoring_enabled:
            await self._realtime_scoring_capability.on_session_start(
                self._feedback_context
            )

    async def _send_fuzzy_detection(self, detections: list[dict[str, Any]]) -> None:
        if not detections:
            return
        await self.manager.send_json(
            self.websocket,
            {
                "type": "fuzzy_detection",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {"detections": detections},
            },
        )

    async def _send_score_update(
        self,
        *,
        turn_number: int,
        overall_score: float,
        dimension_scores: dict[str, float],
        suggestions: list[str],
        stage_name: str = "",
        claim_truth: dict[str, Any] | None = None,
        live_session_summary: dict[str, Any] | None = None,
    ) -> None:
        payload_data: dict[str, Any] = {
            "session_id": self.session_id,
            "turn_count": turn_number,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "suggestions": suggestions,
            "stage_name": stage_name,
        }
        normalized_live_session_summary = coerce_live_session_conclusion_summary(
            live_session_summary
        )
        if isinstance(normalized_live_session_summary, dict):
            payload_data["live_session_summary"] = copy.deepcopy(
                normalized_live_session_summary
            )
            if claim_truth is None:
                summary_claim_truth = normalized_live_session_summary.get("claim_truth")
                if isinstance(summary_claim_truth, dict):
                    claim_truth = summary_claim_truth
        if isinstance(claim_truth, dict):
            payload_data["claim_truth"] = copy.deepcopy(claim_truth)
        await self.manager.send_json(
            self.websocket,
            {
                "type": "score_update",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": payload_data,
            },
        )

    async def _send_action_card(self, card: ActionCard) -> None:
        """Send one actionable card for the next turn."""
        await self.manager.send_json(
            self.websocket,
            {
                "type": "action_card",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": card,
            },
        )

    @staticmethod
    def _format_stage_name(stage_id: str | None) -> str:
        return format_stage_name(stage_id)

    @staticmethod
    def _coach_health_message(status: str) -> str:
        if status == "degraded":
            return "实时辅导暂不可用，训练仍可继续。"
        if status == "resumed":
            return "实时辅导已恢复，后续建议会继续更新。"
        return "实时辅导正常。"

    def _coach_health_payload(self) -> dict[str, Any]:
        return {
            "status": self._coach_health,
            "reason": self._coach_health_reason,
            "message": self._coach_health_message(self._coach_health),
        }

    def get_runtime_diagnostics(self) -> dict[str, Any]:
        live_session_summary = coerce_live_session_conclusion_summary(
            self._latest_live_session_summary
        )
        claim_truth = None
        if isinstance(live_session_summary, dict):
            summary_claim_truth = live_session_summary.get("claim_truth")
            if isinstance(summary_claim_truth, dict):
                claim_truth = copy.deepcopy(summary_claim_truth)
        if claim_truth is None and isinstance(self._latest_claim_truth, dict):
            claim_truth = copy.deepcopy(self._latest_claim_truth)

        knowledge_answer_diagnostics = None
        if isinstance(self._latest_knowledge_answer_diagnostics, dict):
            knowledge_answer_diagnostics = enrich_knowledge_answer_diagnostics(
                self._latest_knowledge_answer_diagnostics
            )

        runtime_events = merge_runtime_events(
            (
                knowledge_answer_diagnostics.get("runtime_events")
                if isinstance(knowledge_answer_diagnostics, dict)
                else []
            ),
            [build_claim_truth_runtime_event(claim_truth)]
            if isinstance(claim_truth, dict)
            else [],
        )
        return {
            "session_status": self.session_status,
            "ai_state": self.ai_state,
            "current_request_id": int(self.current_request_id or 0),
            "live_session_summary": copy.deepcopy(live_session_summary)
            if isinstance(live_session_summary, dict)
            else None,
            "claim_truth": claim_truth,
            "coach_health": self._coach_health_payload(),
            "reconnect_state": self._build_reconnect_state_payload(),
            "knowledge_answer_diagnostics": knowledge_answer_diagnostics,
            "runtime_events": runtime_events,
        }

    async def _send_coach_health(self) -> None:
        await self.manager.send_json(
            self.websocket,
            {
                "type": "coach_health_update",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": self._coach_health_payload(),
            },
        )

    async def _set_coach_health(self, status: str, reason: str | None = None) -> None:
        normalized_reason = (
            reason.strip() if isinstance(reason, str) and reason.strip() else None
        )
        if (
            self._coach_health == status
            and self._coach_health_reason == normalized_reason
        ):
            return
        self._coach_health = status
        self._coach_health_reason = normalized_reason
        await self._send_coach_health()

    async def _run_realtime_feedback(
        self,
        *,
        user_text: str,
        turn_number: int,
        sales_stage: str | None,
    ) -> dict[str, Any]:
        """Run realtime fuzzy/scoring capabilities and emit websocket feedback."""
        text = user_text.strip()
        if not text:
            return {}

        analysis_data: dict[str, Any] = {}
        detections_for_card: list[dict[str, Any]] = []
        suggestions_for_card: list[str] = []
        pass_flags_for_card: PassFlags | None = None
        stage_context_for_arbiter: dict[str, Any] | None = None
        score_context_for_arbiter: dict[str, Any] | None = None

        latest_stage_data = self._latest_stage_data
        if isinstance(latest_stage_data, dict) and (
            not sales_stage or latest_stage_data.get("current_stage") == sales_stage
        ):
            stage_context_for_arbiter = copy.deepcopy(latest_stage_data)
        elif sales_stage:
            stage_context_for_arbiter = {
                "current_stage": sales_stage,
                "stage_name": self._format_stage_name(sales_stage),
            }

        await self._ensure_feedback_context()
        if self._feedback_context is None:
            return analysis_data

        self._feedback_context.turn_count = max(
            self._feedback_context.turn_count, turn_number
        )

        capability_pipeline_degraded = False

        if self._fuzzy_detection_enabled:
            try:
                fuzzy_result = await self._fuzzy_detection_capability.execute(
                    self._feedback_context, text
                )
            except Exception as exc:
                capability_pipeline_degraded = True
                logger.warning(
                    "StepFun realtime fuzzy detection degraded",
                    session_id=self.session_id,
                    turn_number=turn_number,
                    error=str(exc),
                )
            else:
                if getattr(fuzzy_result, "success", True):
                    fuzzy_payload = (
                        fuzzy_result.data if isinstance(fuzzy_result.data, dict) else {}
                    )
                    detections = (
                        fuzzy_payload.get("detections")
                        if isinstance(fuzzy_payload, dict)
                        else None
                    )
                    if isinstance(detections, list) and detections:
                        await self._send_fuzzy_detection(detections)
                        detections_for_card = [
                            item for item in detections if isinstance(item, dict)
                        ]
                        analysis_data["fuzzy_words"] = detections
                else:
                    capability_pipeline_degraded = True

        score_update_payload: dict[str, Any] | None = None
        if self._realtime_scoring_enabled:
            try:
                score_result = await self._realtime_scoring_capability.execute(
                    self._feedback_context, text
                )
            except Exception as exc:
                capability_pipeline_degraded = True
                logger.warning(
                    "StepFun realtime scoring degraded",
                    session_id=self.session_id,
                    turn_number=turn_number,
                    error=str(exc),
                )
            else:
                if getattr(score_result, "success", True):
                    score_payload = (
                        score_result.data if isinstance(score_result.data, dict) else {}
                    )
                    dimension_scores = (
                        score_payload.get("dimension_scores")
                        if isinstance(score_payload, dict)
                        else None
                    )
                    if not isinstance(dimension_scores, dict):
                        dimensions = (
                            score_payload.get("dimensions")
                            if isinstance(score_payload, dict)
                            else None
                        )
                        dimension_scores = {}
                        if isinstance(dimensions, list):
                            for item in dimensions:
                                if not isinstance(item, dict):
                                    continue
                                name = item.get("name")
                                score = item.get("score")
                                if isinstance(name, str) and isinstance(
                                    score, (int, float)
                                ):
                                    dimension_scores[name] = max(
                                        0.0, min(100.0, float(score))
                                    )

                    overall_raw = (
                        score_payload.get("overall_score")
                        if isinstance(score_payload, dict)
                        else None
                    )
                    if not isinstance(overall_raw, (int, float)):
                        overall_raw = (
                            score_payload.get("overall")
                            if isinstance(score_payload, dict)
                            else None
                        )
                    if not isinstance(overall_raw, (int, float)):
                        overall_raw = (
                            sum(dimension_scores.values()) / len(dimension_scores)
                            if dimension_scores
                            else 0.0
                        )
                    overall_score = max(0.0, min(100.0, float(overall_raw)))

                    feedback_message = (
                        score_payload.get("feedback")
                        if isinstance(score_payload, dict)
                        else None
                    )
                    suggestions: list[str] = []
                    if isinstance(feedback_message, str) and feedback_message.strip():
                        suggestions = [feedback_message.strip()]
                    suggestions_for_card = suggestions

                    if dimension_scores:
                        score_snapshot = {
                            "overall_score": overall_score,
                            "dimension_scores": dimension_scores,
                            "suggestions": suggestions,
                            "stage_name": self._format_stage_name(sales_stage),
                        }
                        self._latest_score_snapshot = score_snapshot
                        analysis_data["score_snapshot"] = score_snapshot
                        score_context_for_arbiter = copy.deepcopy(score_payload)
                        score_context_for_arbiter["overall_score"] = overall_score
                        score_context_for_arbiter["dimension_scores"] = dict(
                            dimension_scores
                        )
                        score_context_for_arbiter["suggestions"] = list(suggestions)
                        score_context_for_arbiter["stage_name"] = score_snapshot[
                            "stage_name"
                        ]
                        score_update_payload = {
                            "turn_number": turn_number,
                            "overall_score": overall_score,
                            "dimension_scores": dimension_scores,
                            "suggestions": suggestions,
                            "stage_name": score_snapshot["stage_name"],
                        }
                        pass_flags_for_card = evaluate_pass_flags(
                            build_sales_effectiveness_metrics(
                                overall_score=overall_score,
                                dimension_scores=dimension_scores,
                                turn_count=turn_number,
                            )
                        )
                else:
                    capability_pipeline_degraded = True

        if capability_pipeline_degraded:
            await self._set_coach_health(
                "degraded", reason="capability_pipeline_failed"
            )
        elif self._coach_health == "degraded":
            await self._set_coach_health(
                "resumed", reason="capability_pipeline_resumed"
            )
        elif self._coach_health == "resumed":
            await self._set_coach_health("healthy")

        previous_objection_ledger = normalize_objection_ledger(self._objection_ledger)
        resolved_objection_ledger = resolve_turn_objection_ledger(
            existing_ledger=previous_objection_ledger,
            user_text=text,
            stage_context=stage_context_for_arbiter,
            score_context=score_context_for_arbiter,
        )
        self._objection_ledger = resolved_objection_ledger
        if resolved_objection_ledger is not None:
            analysis_data["objection_ledger"] = copy.deepcopy(resolved_objection_ledger)
        if resolved_objection_ledger != previous_objection_ledger:
            logger.info(
                "Updated StepFun objection ledger",
                session_id=self.session_id,
                turn_number=turn_number,
                objection_ledger=resolved_objection_ledger,
            )

        (
            stage_context_for_arbiter,
            score_context_for_arbiter,
        ) = merge_arbiter_context_with_objection_ledger(
            objection_ledger=resolved_objection_ledger,
            stage_context=stage_context_for_arbiter,
            score_context=score_context_for_arbiter,
        )

        live_claim_truth: dict[str, Any] | None = None
        live_session_summary: dict[str, Any] | None = None
        live_score_snapshot = analysis_data.get("score_snapshot")
        if (
            isinstance(live_score_snapshot, dict)
            or resolved_objection_ledger is not None
        ):
            live_session_summary = build_live_session_conclusion_summary(
                sales_stage=sales_stage,
                score_snapshot=(
                    live_score_snapshot
                    if isinstance(live_score_snapshot, dict)
                    else None
                ),
                objection_ledger=resolved_objection_ledger,
            )
            self._latest_live_session_summary = copy.deepcopy(live_session_summary)
            aligned_claim_truth = live_session_summary.get("claim_truth")
            if isinstance(aligned_claim_truth, dict):
                live_claim_truth = copy.deepcopy(aligned_claim_truth)
                self._latest_claim_truth = copy.deepcopy(aligned_claim_truth)
            else:
                self._latest_claim_truth = None

        if score_update_payload is not None:
            await self._send_score_update(
                turn_number=int(score_update_payload["turn_number"]),
                overall_score=float(score_update_payload["overall_score"]),
                dimension_scores=dict(score_update_payload["dimension_scores"]),
                suggestions=list(score_update_payload["suggestions"]),
                stage_name=str(score_update_payload["stage_name"]),
                claim_truth=live_claim_truth,
                live_session_summary=live_session_summary,
            )

        decision = self._feedback_arbiter.decide(
            turn_number=turn_number,
            fuzzy_detections=detections_for_card,
            score_suggestions=suggestions_for_card,
            stage_context=stage_context_for_arbiter,
            score_context=score_context_for_arbiter,
            pass_flags=pass_flags_for_card,
            prior_state=self._feedback_pacing_state,
        )
        self._feedback_pacing_state = decision.state

        if decision.action_card:
            self._latest_action_card = decision.action_card
            analysis_data["ai_feedback"] = decision.action_card.get("replacement", "")
            await self._send_action_card(decision.action_card)

        self._feedback_context.add_message(role="user", content=text)
        return analysis_data

    async def _prepare_grounding_context(self, query: str) -> None:
        """
        Pre-fetch internal knowledge for the current user turn.

        This provides deterministic grounding for realtime mode (even when model
        does not proactively call `search_internal_knowledge`).
        """
        normalized_query = query.strip()
        self._pending_grounding_context = ""
        self._pending_blocked_response_text = ""
        if not normalized_query:
            self._log_grounding_debug("prefetch_skipped", reason="empty_query")
            return

        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}
        knowledge_base_ids = self._effective_policy.get("knowledge_base_ids")
        has_bound_knowledge_base = isinstance(knowledge_base_ids, list) and bool(
            [item for item in knowledge_base_ids if str(item).strip()]
        )
        require_kb_grounding = bool(tool_policy.get("require_kb_grounding", False))
        if require_kb_grounding:
            decision: Any | None = None
            decision_id = uuid.uuid4().hex[:12]
            decision_started_at = asyncio.get_running_loop().time()
            kb_lock_timeout_seconds = self._kb_lock_decision_timeout_seconds
            decision_coro = evaluate_kb_lock_decision(
                query=normalized_query,
                effective_policy=self._effective_policy,
                record_metric=self._record_knowledge_runtime_metric,
                decision_id=decision_id,
            )
            try:
                decision = await asyncio.wait_for(
                    decision_coro,
                    timeout=kb_lock_timeout_seconds,
                )
            except TimeoutError:
                decision_coro.close()
                decision_duration_ms = round(
                    (asyncio.get_running_loop().time() - decision_started_at) * 1000,
                    1,
                )
                timeout_phase_breakdown = {
                    "phase_total_ms": decision_duration_ms,
                    "phase_health_ms": 0.0,
                    "phase_search_ms": 0.0,
                    "phase_vector_ms": 0.0,
                    "phase_keyword_ms": 0.0,
                    "timeout_budget_ms": int(kb_lock_timeout_seconds * 1000),
                    "cache_hit_health": False,
                    "cache_hit_ready_docs": False,
                    "cache_hit_internal_retrieval": False,
                }
                kb_lock_mode = resolve_kb_lock_mode(tool_policy)
                product_overview_query = is_product_overview_query(normalized_query)
                if kb_lock_mode == "coach_mode" and not product_overview_query:
                    decision_status = "coach_search_timeout"
                    blocked = False
                    self._pending_blocked_response_text = ""
                    self._pending_grounding_context = build_kb_coach_grounding_context(
                        normalized_query,
                        decision_status,
                    )
                else:
                    decision_status = "blocked_search_timeout"
                    blocked = True
                    self._pending_blocked_response_text = (
                        "当前内部知识检索超时，暂时无法基于内部资料确认该产品信息。"
                        "请稍后重试，或补充更具体的产品关键词、版本或业务场景。"
                    )
                    self._pending_grounding_context = ""
                await self._record_kb_lock_decision(
                    status=decision_status,
                    blocked=blocked,
                    decision_id=decision_id,
                    duration_ms=decision_duration_ms,
                    phase_breakdown=timeout_phase_breakdown,
                    error_detail="[KB_LOCK_TIMEOUT]",
                )
                self._log_grounding_debug(
                    "prefetch_kb_lock_timeout",
                    decision_id=decision_id,
                    query_length=len(normalized_query),
                    timeout_ms=int(kb_lock_timeout_seconds * 1000),
                    kb_count=len(knowledge_base_ids)
                    if isinstance(knowledge_base_ids, list)
                    else 0,
                    status=decision_status,
                    decision_duration_ms=decision_duration_ms,
                )
                logger.info(
                    "kb_lock_timing_breakdown",
                    session_id=self.session_id,
                    decision_id=decision_id,
                    query_length=len(normalized_query),
                    timeout_budget_ms=int(kb_lock_timeout_seconds * 1000),
                    decision_status=decision_status,
                    phase_health_ms=0.0,
                    phase_search_ms=0.0,
                    phase_vector_ms=0.0,
                    phase_keyword_ms=0.0,
                    phase_total_ms=decision_duration_ms,
                    cache_hit_health=False,
                    cache_hit_ready_docs=False,
                    cache_hit_internal_retrieval=False,
                    max_score=0.0,
                    min_pass_score=self._safe_float(
                        timeout_phase_breakdown.get("min_pass_score"), 0.0
                    ),
                    result_count=0,
                )
                return

            if decision is None:
                return
            decision_id = str(getattr(decision, "decision_id", "") or decision_id)
            fallback_duration_ms = round(
                (asyncio.get_running_loop().time() - decision_started_at) * 1000,
                1,
            )
            decision_duration_ms = self._safe_float(
                getattr(decision, "duration_ms", 0.0),
                fallback_duration_ms,
            )
            if decision_duration_ms <= 0:
                decision_duration_ms = fallback_duration_ms
            phase_breakdown = getattr(decision, "phase_breakdown", None)
            if not isinstance(phase_breakdown, dict):
                phase_breakdown = {}
            phase_breakdown = dict(phase_breakdown)
            phase_breakdown.setdefault("phase_total_ms", round(decision_duration_ms, 1))
            phase_breakdown.setdefault(
                "timeout_budget_ms", int(kb_lock_timeout_seconds * 1000)
            )
            phase_breakdown.setdefault("cache_hit_internal_retrieval", False)
            if decision.allow_generation:
                self._pending_blocked_response_text = ""
                self._pending_grounding_context = decision.grounding_context
                await self._record_kb_lock_decision(
                    status=decision.status,
                    blocked=False,
                    decision_id=decision_id,
                    duration_ms=decision_duration_ms,
                    phase_breakdown=phase_breakdown,
                    error_detail=decision.error_detail,
                )
                self._log_grounding_debug(
                    "prefetch_kb_lock_passed",
                    decision_id=decision_id,
                    query_length=len(normalized_query),
                    result_count=decision.result_count,
                    retrieval_mode=decision.retrieval_mode,
                    decision_duration_ms=round(decision_duration_ms, 1),
                )
            else:
                self._pending_blocked_response_text = decision.user_message
                self._pending_grounding_context = ""
                await self._record_kb_lock_decision(
                    status=decision.status,
                    blocked=True,
                    decision_id=decision_id,
                    duration_ms=decision_duration_ms,
                    phase_breakdown=phase_breakdown,
                    error_detail=decision.error_detail,
                )
                self._log_grounding_debug(
                    "prefetch_kb_lock_blocked",
                    decision_id=decision_id,
                    query_length=len(normalized_query),
                    kb_count=len(knowledge_base_ids)
                    if isinstance(knowledge_base_ids, list)
                    else 0,
                    status=decision.status,
                    error_detail=decision.error_detail,
                    decision_duration_ms=round(decision_duration_ms, 1),
                )
            logger.info(
                "kb_lock_timing_breakdown",
                session_id=self.session_id,
                decision_id=decision_id,
                query_length=len(normalized_query),
                timeout_budget_ms=int(kb_lock_timeout_seconds * 1000),
                decision_status=str(decision.status),
                phase_health_ms=self._safe_float(
                    phase_breakdown.get("phase_health_ms"), 0.0
                ),
                phase_search_ms=self._safe_float(
                    phase_breakdown.get("phase_search_ms"), 0.0
                ),
                phase_vector_ms=self._safe_float(
                    phase_breakdown.get("phase_vector_ms"), 0.0
                ),
                phase_keyword_ms=self._safe_float(
                    phase_breakdown.get("phase_keyword_ms"), 0.0
                ),
                phase_total_ms=self._safe_float(
                    phase_breakdown.get("phase_total_ms"), decision_duration_ms
                ),
                cache_hit_health=bool(phase_breakdown.get("cache_hit_health", False)),
                cache_hit_ready_docs=bool(
                    phase_breakdown.get("cache_hit_ready_docs", False)
                ),
                cache_hit_internal_retrieval=bool(
                    phase_breakdown.get("cache_hit_internal_retrieval", False)
                ),
                max_score=self._safe_float(phase_breakdown.get("max_score"), 0.0),
                min_pass_score=self._safe_float(
                    phase_breakdown.get("min_pass_score"), 0.0
                ),
                result_count=int(getattr(decision, "result_count", 0) or 0),
            )
            return

        internal_retrieval_enabled = bool(
            tool_policy.get("enable_internal_retrieval", True)
        )
        if not internal_retrieval_enabled and not has_bound_knowledge_base:
            self._log_grounding_debug(
                "prefetch_skipped",
                reason="internal_retrieval_disabled",
                query_length=len(normalized_query),
            )
            return
        if not internal_retrieval_enabled and has_bound_knowledge_base:
            self._log_grounding_debug(
                "prefetch_internal_retrieval_forced",
                reason="kb_bound_guardrail",
                query_length=len(normalized_query),
            )

        try:
            top_k = int(tool_policy.get("retrieval_top_k", 3) or 3)
        except (TypeError, ValueError):
            top_k = 3
        retrieval_payload = {"query": normalized_query, "top_k": max(1, min(8, top_k))}
        retrieval: dict[str, Any] | None = None
        prefetch_timeout_seconds = self._grounding_prefetch_timeout_seconds
        if prefetch_timeout_seconds > 0:
            try:
                retrieval = await asyncio.wait_for(
                    self._tool_search_internal_knowledge(retrieval_payload),
                    timeout=prefetch_timeout_seconds,
                )
            except TimeoutError:
                self._log_grounding_debug(
                    "prefetch_timeout",
                    query_length=len(normalized_query),
                    timeout_ms=int(prefetch_timeout_seconds * 1000),
                    kb_count=len(knowledge_base_ids)
                    if isinstance(knowledge_base_ids, list)
                    else 0,
                )
                return
        else:
            retrieval = await self._tool_search_internal_knowledge(retrieval_payload)

        if not isinstance(retrieval, dict):
            self._log_grounding_debug(
                "prefetch_skipped",
                reason="invalid_retrieval_payload",
                query_length=len(normalized_query),
            )
            return
        knowledge_answer_diagnostics = retrieval.get("_answerability")
        self._latest_knowledge_answer_diagnostics = (
            copy.deepcopy(knowledge_answer_diagnostics)
            if isinstance(knowledge_answer_diagnostics, dict)
            else None
        )
        if int(retrieval.get("count") or 0) <= 0:
            self._log_grounding_debug(
                "prefetch_skipped",
                reason="retrieval_empty",
                query_length=len(normalized_query),
                retrieval_message=str(retrieval.get("message") or ""),
            )
            if has_bound_knowledge_base:
                retrieval_message = str(retrieval.get("message") or "").strip()
                if (
                    "尚未处理完成" in retrieval_message
                    or "kb_not_ready" in retrieval_message.lower()
                ):
                    self._pending_grounding_context = (
                        "当前内部知识库尚未就绪。\n"
                        f"用户问题：{normalized_query}\n"
                        "如果继续回答，只能给出一般性参考，并必须明确标注“以下回答不以内部知识库确认为准”。\n"
                        "请优先提示用户稍后重试，或改问已确认录入的产品关键词。"
                    )
                else:
                    self._pending_grounding_context = (
                        "当前内部知识库未检索到充分证据。\n"
                        f"用户问题：{normalized_query}\n"
                        "如果继续回答，只能给出一般性参考，并必须明确标注“以下回答不以内部知识库确认为准”。\n"
                        "不得将一般性知识表述为企业内部资料、正式产品事实、报价、版本承诺或客户案例。\n"
                        "请优先引导用户补充更具体的产品关键词、版本信息或场景。"
                    )
                self._log_grounding_debug(
                    "prefetch_guardrail_applied",
                    reason="retrieval_empty",
                    query_length=len(normalized_query),
                )
            return

        rows = retrieval.get("results")
        if not isinstance(rows, list):
            return

        snippet_limit, snippet_char_limit = resolve_grounding_context_limits(
            normalized_query
        )
        snippets: list[str] = []
        for index, row in enumerate(rows[:snippet_limit], start=1):
            if not isinstance(row, dict):
                continue
            snippet = str(row.get("snippet") or "").strip()
            if not snippet:
                continue
            snippet = snippet[:snippet_char_limit]
            snippets.append(f"{index}. {snippet}")

        if not snippets:
            self._log_grounding_debug(
                "prefetch_skipped",
                reason="snippet_empty",
                query_length=len(normalized_query),
            )
            self._pending_grounding_context = (
                "当前检索结果缺少可直接引用的内部片段。\n"
                f"用户问题：{normalized_query}\n"
                "如果继续回答，只能给出一般性参考，并必须明确标注“以下回答不以内部知识库确认为准”。\n"
                "不得把未被内部片段支持的内容说成公司正式资料或确定产品事实。"
            )
            self._log_grounding_debug(
                "prefetch_guardrail_applied",
                reason="snippet_empty",
                query_length=len(normalized_query),
            )
            return

        self._pending_grounding_context = (
            "请在当前轮优先依据以下内部知识回答，并保持角色真实自然；若命中片段与模型既有知识冲突，必须以命中片段为准，不得自行补充片段外事实。\n"
            f"用户问题：{normalized_query}\n"
            + "\n".join(snippets)
            + "\n若信息不足，请明确说明不确定之处。"
        )
        answerability_mode, answerability_diagnostics = (
            self._resolve_answerability_mode()
        )
        if answerability_mode == "blocked":
            self._pending_grounding_context = ""
            self._pending_blocked_response_text = (
                self._build_blocked_response_from_answerability(
                    answerability_diagnostics,
                )
            )
            self._log_grounding_debug(
                "prefetch_answerability_blocked",
                query_length=len(normalized_query),
                answerability=str(
                    (answerability_diagnostics or {}).get("answerability") or ""
                ),
                source_status=str(
                    (answerability_diagnostics or {}).get("source_status") or ""
                ),
            )
            return
        answerability_overlay = self._build_answerability_instruction_overlay(
            answerability_mode,
            answerability_diagnostics,
        )
        if answerability_overlay:
            self._pending_grounding_context += answerability_overlay
        self._log_grounding_debug(
            "prefetch_applied",
            query_length=len(normalized_query),
            snippet_count=len(snippets),
            answerability_mode=answerability_mode,
        )

    async def _schedule_response_after_commit(self) -> None:
        """
        Schedule response creation after audio commit.

        We wait briefly for final transcription so we can run sales-stage,
        fuzzy/scoring, and grounding before creating the response.
        """
        async with self._pending_response_lock:
            if self._pending_response_after_commit:
                return
            self._pending_response_after_commit = True
            self._awaiting_transcription_after_commit = True
            self._allow_late_transcription_response = False
            self._latest_input_transcript_delta = ""
            self._pending_response_generation += 1
            generation = self._pending_response_generation
            timeout_task = self._pending_response_timeout_task
            self._pending_response_timeout_task = asyncio.create_task(
                self._pending_response_timeout_fallback(generation)
            )

        if timeout_task:
            timeout_task.cancel()

    async def _pending_response_timeout_fallback(
        self, expected_generation: int | None = None
    ) -> None:
        try:
            await asyncio.sleep(PENDING_RESPONSE_FALLBACK_SECONDS)
            if (
                expected_generation is not None
                and expected_generation != self._pending_response_generation
            ):
                self._log_grounding_debug(
                    "skip_stale_pending_response_timeout",
                    expected_generation=expected_generation,
                    active_generation=self._pending_response_generation,
                )
                return
            transcription_deadline = (
                asyncio.get_running_loop().time() + TRANSCRIPTION_WAIT_GRACE_SECONDS
            )
            while (
                self._awaiting_transcription_after_commit
                and asyncio.get_running_loop().time() < transcription_deadline
            ):
                await asyncio.sleep(GROUNDING_WAIT_POLL_SECONDS)
            if self._awaiting_transcription_after_commit:
                self._log_grounding_debug(
                    "timeout_proceeded_without_transcription_completion"
                )
                fallback_transcript = self._latest_input_transcript_delta.strip()
                if fallback_transcript:
                    self._log_grounding_debug(
                        "timeout_use_delta_transcript_as_final",
                        transcript_length=len(fallback_transcript),
                    )
                    await self._handle_final_user_transcript(fallback_transcript)
                    return

                self._pending_grounding_context = ""
                self._pending_blocked_response_text = ""
                await self._cancel_pending_response_after_commit()
                self._allow_late_transcription_response = True

                if self._is_kb_lock_required_for_current_policy():
                    await self._record_kb_lock_decision(
                        status="transcription_timeout_suppressed",
                        blocked=False,
                    )
                else:
                    self._log_grounding_debug("timeout_suppressed_without_transcript")

                await self._send_status("listening")
                return
            if self._grounding_preparation_in_progress:
                self._log_grounding_debug("timeout_waiting_for_prefetch")
            deadline = asyncio.get_running_loop().time() + GROUNDING_WAIT_GRACE_SECONDS
            while (
                self._grounding_preparation_in_progress
                and asyncio.get_running_loop().time() < deadline
            ):
                await asyncio.sleep(GROUNDING_WAIT_POLL_SECONDS)
            if self._grounding_preparation_in_progress:
                self._log_grounding_debug(
                    "timeout_proceeded_without_prefetch_completion"
                )
            await self._create_response_from_pending_commit(
                expected_generation=expected_generation
            )
        except asyncio.CancelledError:
            return

    async def _cancel_pending_response_after_commit(self) -> None:
        async with self._pending_response_lock:
            self._pending_response_after_commit = False
            self._awaiting_transcription_after_commit = False
            self._allow_late_transcription_response = False
            self._latest_input_transcript_delta = ""
            self._pending_response_generation += 1
            timeout_task = self._pending_response_timeout_task
            self._pending_response_timeout_task = None

        if timeout_task:
            timeout_task.cancel()

    async def _create_response_from_pending_commit(
        self, expected_generation: int | None = None
    ) -> bool:
        async with self._pending_response_lock:
            if not self._pending_response_after_commit:
                return False
            if (
                expected_generation is not None
                and expected_generation != self._pending_response_generation
            ):
                self._log_grounding_debug(
                    "skip_stale_pending_response_commit",
                    expected_generation=expected_generation,
                    active_generation=self._pending_response_generation,
                )
                return False
            self._pending_response_after_commit = False
            self._awaiting_transcription_after_commit = False
            timeout_task = self._pending_response_timeout_task
            self._pending_response_timeout_task = None

        if timeout_task and timeout_task is not asyncio.current_task():
            timeout_task.cancel()

        return await self._create_response(count_turn=True)

    async def _commit_and_respond(self) -> None:
        """Commit buffered user audio and trigger model response."""
        if not self._has_uncommitted_audio:
            logger.debug(
                "Ignore duplicate audio commit without new audio",
                session_id=self.session_id,
            )
            return
        await self._send_upstream({"type": "input_audio_buffer.commit"})
        self._has_uncommitted_audio = False
        await self._schedule_response_after_commit()

    async def _create_response(self, *, count_turn: bool = False) -> bool:
        """Create a new upstream response and initialize local response state."""
        if self._active_response is not None:
            logger.info(
                "Skip response.create because active response exists",
                session_id=self.session_id,
                active_request_id=self._active_response.request_id,
                pending_followup=self._pending_tool_followup_response,
            )
            return False

        blocked_response_text = self._pending_blocked_response_text.strip()
        if blocked_response_text:
            self.current_request_id += 1
            if count_turn:
                self.turn_count += 1
            stream_id = str(uuid.uuid4())
            await self._send_status("thinking")
            await self._persist_message(
                turn_number=max(1, self.turn_count),
                role="assistant",
                content=blocked_response_text,
            )
            async with self._sales_stage_lock:
                self._append_sales_stage_context_message(
                    role="assistant",
                    content=blocked_response_text,
                    turn_number=max(1, self.turn_count),
                )
            if self._feedback_context is not None:
                self._feedback_context.add_message(
                    role="assistant",
                    content=blocked_response_text,
                )
            await self.manager.send_json(
                self.websocket,
                {
                    "type": "tts_audio",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "stream_id": stream_id,
                    "request_id": self.current_request_id,
                    "data": {
                        "text": blocked_response_text,
                        "audio": "",
                        "audio_format": "",
                        "duration_ms": len(blocked_response_text) * 100,
                        "fallback": "browser_tts",
                        "playback_rate": self._stepfun_playback_rate,
                    },
                },
            )
            self._pending_blocked_response_text = ""
            self._pending_grounding_context = ""
            self._log_grounding_debug(
                "response_blocked_by_kb_lock",
                request_id=self.current_request_id,
                turn_count=self.turn_count,
            )
            await self._send_status("listening")
            return True

        self.current_request_id += 1
        if count_turn:
            self.turn_count += 1
        self._active_response = RealtimeResponseState(
            request_id=self.current_request_id,
            stream_id=str(uuid.uuid4()),
        )

        response_payload: dict[str, Any] = {
            "type": "response.create",
            "response": {"modalities": ["audio", "text"]},
        }
        grounding_context = self._pending_grounding_context.strip()
        turn_instructions = VoiceInstructionCompiler.compose_turn_instructions(
            base_instructions=self._stepfun_instructions,
            grounding_context=grounding_context,
        )
        if turn_instructions:
            response_payload["response"]["instructions"] = turn_instructions
        self._pending_grounding_context = ""
        self._log_grounding_debug(
            "response_create",
            request_id=self.current_request_id,
            has_grounding_context=bool(grounding_context),
            grounding_context_length=len(grounding_context),
            has_base_instructions=bool(self._stepfun_instructions.strip()),
            final_instruction_length=len(turn_instructions),
            instruction_contract_hash=self._instruction_contract_hash,
        )

        await self._send_status("thinking")
        await self._send_upstream(response_payload)
        return True

    async def _handle_interrupt(self, reason: str) -> None:
        """Stop current generation and clear buffered input."""
        interrupted_stream_id = (
            self._active_response.stream_id if self._active_response else None
        )
        await self._cancel_pending_response_after_commit()
        await self._clear_upstream_generation()
        self._reset_turn_runtime_state()

        await self.manager.send_json(
            self.websocket,
            {
                "type": "interrupted",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "stream_id": interrupted_stream_id,
                "data": {
                    "reason": reason,
                    "session_status": self.session_status,
                    "ai_state": "listening"
                    if self.session_status == "in_progress"
                    else "idle",
                    "turn_count": self.turn_count,
                },
            },
        )
        await self._send_status(
            "listening" if self.session_status == "in_progress" else "idle"
        )

    async def _handle_session_end(self) -> None:
        """Close session after notifying frontend."""
        await self._cancel_pending_response_after_commit()
        self._reset_turn_runtime_state()
        if self._feedback_context is not None:
            if self._fuzzy_detection_enabled:
                await self._fuzzy_detection_capability.on_session_end(
                    self._feedback_context
                )
            if self._realtime_scoring_enabled:
                await self._realtime_scoring_capability.on_session_end(
                    self._feedback_context
                )
        await self.manager.send_json(
            self.websocket,
            {
                "type": "session_ended",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_id": self.session_id,
                    "session_status": self.session_status,
                    "turn_count": self.turn_count,
                },
            },
        )
        self.running = False

    def _compute_upstream_ws_lifetime_ms(self) -> float | None:
        if self._upstream_connected_at <= 0:
            return None
        return round(
            max(0.0, asyncio.get_running_loop().time() - self._upstream_connected_at)
            * 1000,
            1,
        )

    @staticmethod
    def _is_upstream_idle_timeout_disconnect(
        *,
        close_code: Any,
        close_reason: str,
        ws_lifetime_ms: float | None,
    ) -> bool:
        normalized_reason = close_reason.strip().lower()
        if (
            "too long without operation" in normalized_reason
            or "too long without operatio" in normalized_reason
        ):
            return True
        if normalized_reason:
            return False
        return (
            close_code == 1006
            and ws_lifetime_ms is not None
            and 55000 <= ws_lifetime_ms <= 70000
        )

    @staticmethod
    def _build_upstream_close_user_message(
        *,
        close_reason: str,
        inferred_idle_timeout: bool,
    ) -> str:
        if inferred_idle_timeout:
            return (
                "Realtime 上游连接疑似空闲超时（too long without operation）。"
                "请继续提问或点击“重新连接”。"
            )
        if close_reason:
            return f"Realtime 上游连接已关闭：{close_reason}"
        return "Realtime 上游连接已关闭，请点击“重新连接”。"

    async def _recover_upstream_after_disconnect(
        self,
        *,
        close_code: Any,
        close_reason: str,
        ws_lifetime_ms: float | None,
    ) -> bool:
        if not self.running:
            return False
        if not self._upstream_auto_recover_enabled:
            return False
        if self._upstream_auto_recover_max_retries <= 0:
            return False

        for attempt in range(1, self._upstream_auto_recover_max_retries + 1):
            backoff_seconds = compute_jitter_backoff_seconds(
                attempt=attempt,
                base_delay_seconds=self._upstream_auto_recover_base_delay_seconds,
                max_delay_seconds=self._upstream_auto_recover_max_delay_seconds,
            )
            try:
                await asyncio.sleep(backoff_seconds)
            except asyncio.CancelledError:
                raise
            if not self.running:
                return False

            try:
                await self._close_upstream()
                await self._connect_upstream()
                await self._cancel_pending_response_after_commit()
                self._reset_turn_runtime_state()
                await self._send_status(
                    "listening" if self.session_status == "in_progress" else "idle"
                )
                logger.info(
                    "StepFun upstream recovered",
                    session_id=self.session_id,
                    close_code=close_code,
                    close_reason=close_reason,
                    ws_lifetime_ms=ws_lifetime_ms,
                    attempt=attempt,
                    backoff_ms=round(backoff_seconds * 1000, 1),
                )
                return True
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "StepFun upstream recover attempt failed",
                    session_id=self.session_id,
                    close_code=close_code,
                    close_reason=close_reason,
                    attempt=attempt,
                    backoff_ms=round(backoff_seconds * 1000, 1),
                    error=str(exc),
                )

        return False

    async def sync_lifecycle_transition(
        self, transition: SessionLifecycleTransition
    ) -> None:
        """Mirror REST lifecycle transitions through the StepFun upstream mixin."""
        await super().sync_lifecycle_transition(transition)

    async def _receive_upstream_events(self) -> None:
        """Receive events from StepFun and map them to frontend messages."""
        while self.running:
            if self.upstream_ws is None:
                await asyncio.sleep(0.05)
                continue
            try:
                raw = await self.upstream_ws.recv()
                self._mark_upstream_activity()
                event = json.loads(raw)
                await self._handle_upstream_event(event)
            except asyncio.CancelledError:
                raise
            except ConnectionClosed as e:
                code = getattr(e, "code", None)
                reason_text = str(getattr(e, "reason", "") or "").strip()
                ws_lifetime_ms = self._compute_upstream_ws_lifetime_ms()
                inferred_idle_timeout = self._is_upstream_idle_timeout_disconnect(
                    close_code=code,
                    close_reason=reason_text,
                    ws_lifetime_ms=ws_lifetime_ms,
                )
                await self._record_upstream_disconnect_diagnostics(
                    close_code=code,
                    close_reason=reason_text,
                )
                recovered = await self._recover_upstream_after_disconnect(
                    close_code=code,
                    close_reason=reason_text,
                    ws_lifetime_ms=ws_lifetime_ms,
                )
                logger.info(
                    "StepFun upstream closed",
                    session_id=self.session_id,
                    code=code,
                    reason=reason_text,
                    ws_lifetime_ms=ws_lifetime_ms,
                    inferred_idle_timeout=inferred_idle_timeout,
                    recovered=recovered,
                )
                if recovered:
                    continue
                await self._send_error(
                    "[STEPFUN_UPSTREAM_CLOSED]",
                    self._build_upstream_close_user_message(
                        close_reason=reason_text,
                        inferred_idle_timeout=inferred_idle_timeout,
                    ),
                )
                self.running = False
            except json.JSONDecodeError as exc:
                logger.warning(
                    "StepFun upstream invalid JSON",
                    session_id=self.session_id,
                    error=str(exc),
                )
            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"StepFun upstream receive error: {e}", exc_info=True)
                await self._send_error(
                    "[STEPFUN_UPSTREAM_ERROR]", "Realtime 上游连接异常"
                )
                self.running = False

    async def _handle_upstream_event(self, event: dict[str, Any]) -> None:
        """Map selected StepFun events to existing frontend contract."""
        event_type = str(event.get("type", ""))
        self._last_upstream_event_type = event_type
        route = classify_upstream_event(event_type)

        if route == UpstreamEventRoute.IGNORE:
            return
        if route == UpstreamEventRoute.CONVERSATION_ITEM_CREATED:
            await self._handle_upstream_conversation_item_created(event)
            return
        if route == UpstreamEventRoute.TRANSCRIPTION_DELTA:
            await self._handle_upstream_transcription_delta(event)
            return
        if route == UpstreamEventRoute.TRANSCRIPTION_COMPLETED:
            await self._handle_upstream_transcription_completed(event)
            return
        if route == UpstreamEventRoute.RESPONSE_CREATED:
            await self._handle_upstream_response_created(event)
            return
        if route == UpstreamEventRoute.RESPONSE_TEXT_DELTA:
            await self._handle_upstream_response_text_delta(event)
            return
        if route == UpstreamEventRoute.FUNCTION_ARGUMENTS_DELTA:
            await self._accumulate_function_call_arguments(event)
            return
        if route == UpstreamEventRoute.FUNCTION_ARGUMENTS_DONE:
            await self._accumulate_function_call_arguments(event, done=True)
            return
        if route == UpstreamEventRoute.RESPONSE_AUDIO_DELTA:
            await self._handle_upstream_response_audio_delta(event)
            return
        if route == UpstreamEventRoute.RESPONSE_DONE:
            await self._handle_upstream_response_done(event)
            return
        if route == UpstreamEventRoute.ERROR:
            await self._handle_upstream_error(event)
            return

    async def _handle_upstream_conversation_item_created(self, event: dict) -> None:
        """Track function-call state created by upstream model."""
        function_call = extract_function_call_from_item_created(event)
        if not function_call:
            return

        call_id, name = function_call
        self._function_call_states[call_id] = FunctionCallState(
            call_id=call_id,
            name=name,
        )

    async def _handle_upstream_transcription_delta(self, event: dict) -> None:
        """Forward interim ASR transcript to frontend."""
        transcript = self._extract_transcription_delta_text(event)
        if transcript:
            normalized_transcript = self._normalize_transcript(
                str(transcript),
                is_final=False,
            ).normalized_text
            self._latest_input_transcript_delta = self._merge_transcription_delta_text(
                self._latest_input_transcript_delta,
                normalized_transcript,
            )
            await self._send_transcript(normalized_transcript, is_final=False)

    async def _handle_upstream_transcription_completed(self, event: dict) -> None:
        """Persist final ASR transcript and continue response chain."""
        transcript = self._extract_final_transcript_text(event)
        if not transcript:
            transcript = self._latest_input_transcript_delta.strip()
            if transcript:
                self._log_grounding_debug(
                    "transcription_completed_fallback_to_delta",
                    transcript_length=len(transcript),
                )
        if not transcript:
            return
        await self._handle_final_user_transcript(transcript)

    def _extract_final_transcript_text(self, event: dict) -> str:
        """Extract final transcript from upstream payload variations."""
        direct_candidates = (
            event.get("transcript"),
            event.get("text"),
            event.get("audio_transcript"),
            event.get("stash"),
            event.get("delta"),
        )
        for candidate in direct_candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        item = event.get("item")
        if isinstance(item, dict):
            item_candidates = (
                item.get("transcript"),
                item.get("text"),
                item.get("audio_transcript"),
                item.get("stash"),
            )
            for candidate in item_candidates:
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

        return ""

    def _extract_transcription_delta_text(self, event: dict) -> str:
        """Extract interim transcript text from upstream payload variations."""
        direct_candidates = (
            event.get("delta"),
            event.get("text"),
            event.get("stash"),
            event.get("audio_transcript"),
        )
        for candidate in direct_candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate

        item = event.get("item")
        if isinstance(item, dict):
            item_candidates = (
                item.get("delta"),
                item.get("text"),
                item.get("stash"),
                item.get("audio_transcript"),
                item.get("transcript"),
            )
            for candidate in item_candidates:
                if isinstance(candidate, str) and candidate.strip():
                    return candidate

        return ""

    def _merge_transcription_delta_text(self, previous: str, incoming: str) -> str:
        """Merge transcript chunks for both append-style and snapshot-style events."""
        incoming = incoming or ""
        if not incoming.strip():
            return previous
        if not previous:
            return incoming

        # Some providers emit a growing full snapshot for each delta frame.
        if incoming.startswith(previous):
            return incoming
        # Ignore exact suffix duplicates to prevent repeated concatenation noise.
        if previous.endswith(incoming):
            return previous
        return previous + incoming

    async def _handle_final_user_transcript(self, transcript: str) -> None:
        """Persist one final ASR transcript and continue response chain."""
        turn_started_at = asyncio.get_running_loop().time()
        turn_number = self._resolve_user_turn_number_for_transcript()
        normalization_result = self._normalize_transcript(
            transcript,
            is_final=True,
        )
        normalized_transcript = normalization_result.normalized_text.strip()
        if not normalized_transcript:
            return
        now = asyncio.get_running_loop().time()
        is_duplicate_transcript = (
            bool(normalized_transcript)
            and normalized_transcript == self._last_final_transcript_text
            and turn_number == self._last_final_transcript_turn
            and (now - self._last_final_transcript_at)
            <= TRANSCRIPTION_DUPLICATE_WINDOW_SECONDS
        )
        if is_duplicate_transcript:
            self._log_grounding_debug(
                "duplicate_transcription_completed_ignored",
                turn_number=turn_number,
                transcript_length=len(normalized_transcript),
            )
            return

        self._last_final_transcript_text = normalized_transcript
        self._last_final_transcript_turn = turn_number
        self._last_final_transcript_at = now
        self._awaiting_transcription_after_commit = False
        self._latest_input_transcript_delta = ""
        await self._send_transcript(normalized_transcript, is_final=True)
        feedback_started_at = asyncio.get_running_loop().time()
        grounding_started_at = feedback_started_at
        feedback_finished_at = feedback_started_at
        grounding_finished_at = grounding_started_at

        async def _prepare_grounding_context_with_timing() -> float:
            await self._prepare_grounding_context(normalized_transcript)
            return asyncio.get_running_loop().time()

        self._grounding_preparation_in_progress = True
        grounding_task: asyncio.Task[float] | None = asyncio.create_task(
            _prepare_grounding_context_with_timing()
        )
        try:
            sales_stage = await self._analyze_and_emit_sales_stage(
                user_text=normalized_transcript,
                turn_number=turn_number,
            )
            realtime_analysis = await self._run_realtime_feedback(
                user_text=normalized_transcript,
                turn_number=turn_number,
                sales_stage=sales_stage,
            )
            if not isinstance(realtime_analysis, dict):
                realtime_analysis = {}
            if (
                self._get_effective_tool_policy().get(
                    "transcript_normalization_enabled", False
                )
                or normalization_result.replacements
            ):
                realtime_analysis = {
                    **realtime_analysis,
                    "transcript_metadata": self._build_transcript_metadata(
                        normalization_result,
                    ),
                }
            await self._persist_message(
                turn_number=turn_number,
                role="user",
                content=normalized_transcript,
                sales_stage=sales_stage,
                analysis_data=realtime_analysis,
            )
            feedback_finished_at = asyncio.get_running_loop().time()
        except asyncio.CancelledError:
            if grounding_task is not None and not grounding_task.done():
                grounding_task.cancel()
                try:
                    await grounding_task
                except asyncio.CancelledError:
                    pass
            raise
        except Exception:  # noqa: BLE001
            if grounding_task is not None and not grounding_task.done():
                grounding_task.cancel()
                try:
                    await grounding_task
                except asyncio.CancelledError:
                    pass
            raise
        finally:
            if (
                grounding_task is not None
                and grounding_task.done()
                and grounding_finished_at <= grounding_started_at
            ):
                try:
                    grounding_finished_at = grounding_task.result()
                except asyncio.CancelledError:
                    pass
                except Exception:  # noqa: BLE001
                    pass

        try:
            if grounding_task is not None:
                grounding_finished_at = await grounding_task
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"Failed to prepare grounding context: {exc}",
                exc_info=True,
            )
            await self._cancel_pending_response_after_commit()
            await self._send_error(
                "[GROUNDING_PREPARE_FAILED]",
                "知识检索暂时不可用，请稍后重试。",
            )
            return
        finally:
            self._grounding_preparation_in_progress = False

        try:
            allow_late_transcription_response = self._allow_late_transcription_response
            self._allow_late_transcription_response = False
            response_created = await self._create_response_from_pending_commit()
            if (
                not response_created
                and allow_late_transcription_response
                and self._active_response is None
                and self.session_status not in TERMINAL_SESSION_STATUSES
            ):
                self._log_grounding_debug(
                    "late_transcription_response_recovered",
                    turn_number=turn_number,
                    transcript_length=len(normalized_transcript),
                )
                response_created = await self._create_response(count_turn=True)
            response_created_at = asyncio.get_running_loop().time()
            ready_to_create_at = max(feedback_finished_at, grounding_finished_at)
            self._log_latency_debug(
                "final_transcript_to_response_create",
                turn_number=turn_number,
                transcript_length=len(normalized_transcript),
                total_ms=round((response_created_at - turn_started_at) * 1000, 1),
                feedback_ms=round(
                    (feedback_finished_at - feedback_started_at) * 1000, 1
                ),
                grounding_ms=round(
                    (grounding_finished_at - grounding_started_at) * 1000, 1
                ),
                response_create_ms=round(
                    (response_created_at - ready_to_create_at) * 1000, 1
                ),
                late_recovery=allow_late_transcription_response and response_created,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"Failed to create response from pending commit: {exc}",
                exc_info=True,
            )
            await self._cancel_pending_response_after_commit()
            await self._send_error(
                "[RESPONSE_CREATE_FAILED]",
                "响应生成暂时失败，请重试。",
            )

    async def _handle_upstream_response_created(self, event: dict) -> None:
        """Bind upstream response id to current active response state."""
        response = (
            event.get("response", {}) if isinstance(event.get("response"), dict) else {}
        )
        response_id = response.get("id")
        if response_id and self._active_response is None:
            if self._is_kb_lock_required_for_current_policy():
                self._log_grounding_debug(
                    "unexpected_upstream_response_created_cancelled",
                    response_id=str(response_id),
                )
                await self._send_upstream({"type": "response.cancel"})
            return
        if self._active_response and response_id:
            self._active_response.response_id = response_id

    async def _handle_upstream_response_text_delta(self, event: dict) -> None:
        """Accumulate response text/audio transcript delta for fallback flush."""
        delta = event.get("delta", "")
        if self._active_response and delta:
            self._active_response.text_parts.append(delta)

    async def _handle_upstream_response_audio_delta(self, event: dict) -> None:
        """Forward realtime audio chunk to frontend."""
        delta = event.get("delta", "")
        if self._active_response and delta:
            if self._active_response.question_limit_enforced:
                return
            await self._forward_audio_delta_chunk(delta)

    async def _handle_upstream_response_done(self, event: dict) -> None:
        """Finalize response and execute potential tool follow-ups."""
        had_active_response = await self._flush_active_response(event)
        handled_from_done = False
        if had_active_response:
            handled_from_done = await self._handle_function_calls_from_response_done(
                event
            )
        if handled_from_done:
            self._pending_tool_followup_response = False
        elif self._pending_tool_followup_response and had_active_response:
            self._pending_tool_followup_response = False
            await self._create_response()
        elif self._pending_tool_followup_response:
            self._pending_tool_followup_response = False
            self._log_grounding_debug(
                "skip_followup_without_active_response",
                event_type=str(event.get("type") or ""),
            )

    async def _handle_upstream_error(self, event: dict) -> None:
        """Normalize upstream errors through the StepFun upstream mixin."""
        await super()._handle_upstream_error(event)

    async def _flush_active_response(self, response_done_event: dict) -> bool:
        """Finalize active response and send final marker (or fallback)."""
        response_state = self._active_response
        if not response_state:
            await self._send_status("listening")
            return False

        response_obj = (
            response_done_event.get("response", {})
            if isinstance(response_done_event.get("response"), dict)
            else {}
        )
        done_response_id = response_obj.get("id")
        if (
            response_state.response_id
            and done_response_id
            and done_response_id != response_state.response_id
        ):
            self._log_grounding_debug(
                "skip_mismatched_response_done",
                active_response_id=response_state.response_id,
                done_response_id=str(done_response_id),
            )
            return False

        self._active_response = None

        response_text = self._extract_response_text(response_done_event)
        if not response_text:
            response_text = "".join(response_state.text_parts).strip()
        response_text = enforce_question_limit(
            response_text,
            self._get_max_questions_per_turn(),
        )
        response_text = self._apply_answerability_output_guard(response_text)

        if response_text:
            await self._persist_message(
                turn_number=max(1, self.turn_count),
                role="assistant",
                content=response_text,
            )
            async with self._sales_stage_lock:
                self._append_sales_stage_context_message(
                    role="assistant",
                    content=response_text,
                    turn_number=max(1, self.turn_count),
                )
            if self._feedback_context is not None:
                self._feedback_context.add_message(
                    role="assistant",
                    content=response_text,
                )

        # No output at all in this round; only reset status.
        if response_state.chunk_index == 0 and not response_text:
            await self._send_status("listening")
            return True

        # Streaming path: already sent audio chunks, now send final marker with text.
        if response_state.chunk_index > 0:
            await self.manager.send_json(
                self.websocket,
                {
                    "type": "tts_chunk",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "stream_id": response_state.stream_id,
                    "request_id": response_state.request_id,
                    "data": {
                        "chunk_index": response_state.chunk_index,
                        "audio": "",
                        "duration_ms": 0,
                        "is_final": True,
                        "text": response_text,
                        "total_duration_ms": response_state.total_duration_ms,
                        "audio_format": self._stepfun_output_audio_format.lower(),
                        "sample_rate": self._stepfun_output_sample_rate,
                        "playback_rate": self._stepfun_playback_rate,
                    },
                },
            )
            await self._send_status("listening")
            return True

        # Fallback path: no audio chunks received from upstream.
        payload_data = {
            "text": response_text,
            "audio": "",
            "audio_format": "",
            "duration_ms": len(response_text) * 100,
            "fallback": "browser_tts",
            "playback_rate": self._stepfun_playback_rate,
        }
        if isinstance(self._latest_knowledge_answer_diagnostics, dict):
            payload_data["knowledge_answer_diagnostics"] = copy.deepcopy(
                self._latest_knowledge_answer_diagnostics
            )
        await self.manager.send_json(
            self.websocket,
            {
                "type": "tts_audio",
                "timestamp": datetime.now(UTC).isoformat(),
                "stream_id": response_state.stream_id,
                "request_id": response_state.request_id,
                "data": payload_data,
            },
        )

        await self._send_status("listening")
        return True

    async def _forward_audio_delta_chunk(self, delta_b64: str) -> None:
        """Forward audio deltas through the StepFun upstream TTS contract builder."""
        await super()._forward_audio_delta_chunk(delta_b64)

    async def _accumulate_function_call_arguments(
        self, event: dict, done: bool = False
    ) -> None:
        """Collect function-call arguments from delta/done events."""
        call_id, name, arguments_part = parse_function_call_event(event)
        if not call_id:
            return

        state = self._function_call_states.get(call_id)
        if not state:
            state = FunctionCallState(call_id=call_id, name=name or "unknown")
            self._function_call_states[call_id] = state
        elif name and state.name == "unknown":
            state.name = name

        if done:
            if arguments_part:
                state.done_arguments = arguments_part
            raw_arguments, source = self._resolve_function_call_arguments(state)
            self._log_grounding_debug(
                "function_call_arguments_resolved",
                call_id=call_id,
                function_name=state.name,
                delta_length=len(state.delta_arguments),
                done_length=len(state.done_arguments),
                selected_source=source,
                selected_is_valid_json=is_json_object_payload(raw_arguments),
            )
            await self._execute_function_call(
                call_id=call_id,
                function_name=state.name,
                raw_arguments=raw_arguments,
                trigger_followup_response=True,
            )
            return

        if arguments_part:
            state.delta_arguments += arguments_part

    @staticmethod
    def _resolve_function_call_arguments(state: FunctionCallState) -> tuple[str, str]:
        done_arguments = state.done_arguments.strip()
        delta_arguments = state.delta_arguments.strip()

        if done_arguments and is_json_object_payload(done_arguments):
            return done_arguments, "done"
        if delta_arguments and is_json_object_payload(delta_arguments):
            return delta_arguments, "delta"
        if done_arguments:
            return done_arguments, "done_invalid_json"
        return delta_arguments, "delta_invalid_json"

    async def _handle_function_calls_from_response_done(
        self, response_done_event: dict
    ) -> bool:
        """
        Execute function calls emitted in `response.done`.
        Returns True if at least one function call was handled.
        """
        function_calls = extract_response_done_function_calls(response_done_event)
        if not function_calls:
            return False

        handled_new_call = False
        for function_call in function_calls:
            executed = await self._execute_function_call(
                call_id=function_call["call_id"],
                function_name=function_call["name"],
                raw_arguments=function_call["arguments"],
                trigger_followup_response=False,
            )
            handled_new_call = handled_new_call or executed

        if handled_new_call:
            await self._create_response()
            return True
        return False

    async def _execute_function_call(
        self,
        call_id: str,
        function_name: str,
        raw_arguments: str,
        trigger_followup_response: bool,
    ) -> bool:
        """Run one custom tool call and return output back to StepFun."""
        if not call_id or call_id in self._executed_call_ids:
            return False

        function_name = function_name or "unknown"
        arguments_obj = decode_function_arguments(raw_arguments)
        self._log_grounding_debug(
            "function_call_execute",
            call_id=call_id,
            function_name=function_name,
            raw_arguments_length=len(raw_arguments),
            argument_keys=sorted(arguments_obj.keys()),
            has_query=bool(str(arguments_obj.get("query") or "").strip()),
        )

        output_payload: dict[str, Any]
        if function_name == "search_internal_knowledge":
            output_payload = await self._tool_search_internal_knowledge(arguments_obj)
        else:
            output_payload = build_unsupported_function_output(function_name)

        self._log_grounding_debug(
            "function_call_output",
            call_id=call_id,
            function_name=function_name,
            result_count=int(output_payload.get("count") or 0),
            retrieval_mode=str(output_payload.get("retrieval_mode") or ""),
            message=str(output_payload.get("message") or ""),
            has_error=bool(output_payload.get("error")),
        )

        self._executed_call_ids.add(call_id)
        self._function_call_states.pop(call_id, None)

        await self._send_upstream(
            build_function_call_output_event(
                call_id=call_id,
                output_payload=output_payload,
            )
        )

        if trigger_followup_response:
            if self._active_response is not None:
                self._pending_tool_followup_response = True
            else:
                await self._create_response()
        return True

    def _build_internal_retrieval_cache_key(self, arguments_obj: dict[str, Any]) -> str:
        query = str(arguments_obj.get("query") or "").strip().lower()
        if not query:
            return ""

        top_k = arguments_obj.get("top_k")
        metadata_filter = arguments_obj.get("metadata_filter")
        if not isinstance(metadata_filter, dict):
            metadata_filter = {}
        metadata_filter_signature = json.dumps(
            metadata_filter,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{query}|top_k={top_k}|filter={metadata_filter_signature}"

    async def _tool_search_internal_knowledge(
        self, arguments_obj: dict[str, Any]
    ) -> dict[str, Any]:
        """Search internal knowledge bases bound to current policy."""
        cache_key = self._build_internal_retrieval_cache_key(arguments_obj)
        cache_hit = False
        output: dict[str, Any] = {}
        if cache_key and self._internal_retrieval_cache_ttl_seconds > 0:
            cached = self._internal_retrieval_cache.get(cache_key)
            now = asyncio.get_running_loop().time()
            if cached and cached[0] > now:
                output = cached[1]
                cache_hit = True
            else:
                self._internal_retrieval_cache.pop(cache_key, None)

        if not cache_hit:
            output = {}
            try:
                output = await search_internal_knowledge(
                    arguments_obj={
                        **arguments_obj,
                        "session_id": self.session_id,
                    },
                    effective_policy=self._effective_policy,
                    session_factory=AsyncSessionLocal,
                    knowledge_service_cls=KnowledgeService,
                    record_metric=self._record_knowledge_runtime_metric,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"Internal knowledge search crashed: {exc}",
                    exc_info=True,
                )
                output = {
                    "query": str(arguments_obj.get("query") or ""),
                    "count": 0,
                    "results": [],
                    "retrieval_mode": "unknown",
                    "message": "internal_search_error",
                    "error": str(exc),
                }

            if (
                cache_key
                and self._internal_retrieval_cache_ttl_seconds > 0
                and isinstance(output, dict)
                and not output.get("error")
            ):
                if (
                    len(self._internal_retrieval_cache)
                    >= self._internal_retrieval_cache_max_entries
                ):
                    self._internal_retrieval_cache.clear()
                self._internal_retrieval_cache[cache_key] = (
                    asyncio.get_running_loop().time()
                    + self._internal_retrieval_cache_ttl_seconds,
                    output,
                )
        if isinstance(output, dict):
            diagnostics = output.get("_diagnostics")
            if not isinstance(diagnostics, dict):
                diagnostics = {}
            diagnostics["cache_hit_internal_retrieval"] = cache_hit
            output["_diagnostics"] = diagnostics
        knowledge_base_ids = self._effective_policy.get("knowledge_base_ids")
        if not isinstance(knowledge_base_ids, list):
            knowledge_base_ids = []
        query_text = str(arguments_obj.get("query") or "")
        self._log_grounding_debug(
            "internal_retrieval",
            query_length=len(query_text.strip()),
            kb_count=len(knowledge_base_ids),
            result_count=int(output.get("count") or 0),
            retrieval_mode=str(output.get("retrieval_mode") or ""),
            status_message=str(output.get("message") or ""),
            has_error=bool(output.get("error")),
            cache_hit=cache_hit,
        )
        output.pop("_diagnostics", None)
        return output

    async def _record_knowledge_runtime_metric(
        self,
        *,
        query: str,
        result_count: int,
        status: str,
        knowledge_base_ids: list[str],
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        error_message: str | None = None,
        retrieval_mode: str | None = None,
        ledger_event: dict[str, Any] | None = None,
    ) -> None:
        """Record knowledge retrieval diagnostics for later report verification."""
        try:
            apply_knowledge_runtime_metric(
                effective_policy=self._effective_policy,
                query=query,
                result_count=result_count,
                status=status,
                knowledge_base_ids=knowledge_base_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                error_message=error_message,
                retrieval_mode=retrieval_mode,
                ledger_event=ledger_event,
            )

            await self._persist_runtime_metrics_to_session()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to record knowledge runtime metric: {exc}")

    @staticmethod
    def _normalize_recent_timestamps(
        raw_values: Any,
        *,
        now_ts: float,
        window_seconds: float,
        max_entries: int,
    ) -> list[float]:
        if not isinstance(raw_values, list):
            return []
        normalized: list[float] = []
        lower_bound = now_ts - max(1.0, window_seconds)
        for item in raw_values:
            try:
                value = float(item)
            except (TypeError, ValueError):
                continue
            if value >= lower_bound:
                normalized.append(value)
        if len(normalized) > max_entries:
            normalized = normalized[-max_entries:]
        return normalized

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    async def _record_kb_lock_decision(
        self,
        *,
        status: str,
        blocked: bool,
        decision_id: str = "",
        duration_ms: float | None = None,
        phase_breakdown: dict[str, Any] | None = None,
        error_detail: str | None = None,
    ) -> None:
        """Record per-turn KB lock decision for diagnostics."""
        try:
            metrics = self._ensure_knowledge_runtime_metrics()
            metrics["kb_lock_required"] = True
            metrics["kb_lock_last_status"] = status
            metrics["kb_lock_updated_at"] = datetime.now(UTC).isoformat()
            if blocked:
                metrics["kb_lock_block_count"] = (
                    int(metrics.get("kb_lock_block_count") or 0) + 1
                )
            else:
                metrics.setdefault("kb_lock_block_count", 0)
            metrics["last_decision_id"] = str(decision_id or "")
            if duration_ms is None:
                metrics["last_decision_duration_ms"] = 0.0
            else:
                metrics["last_decision_duration_ms"] = round(
                    max(0.0, float(duration_ms)), 1
                )
            metrics["last_decision_phase_breakdown"] = (
                dict(phase_breakdown) if isinstance(phase_breakdown, dict) else None
            )

            now_ts = time.time()
            decision_timestamps = self._normalize_recent_timestamps(
                metrics.get("kb_lock_decision_timestamps"),
                now_ts=now_ts,
                window_seconds=300.0,
                max_entries=256,
            )
            decision_timestamps.append(now_ts)
            metrics["kb_lock_decision_timestamps"] = decision_timestamps

            timeout_timestamps = self._normalize_recent_timestamps(
                metrics.get("kb_lock_timeout_timestamps"),
                now_ts=now_ts,
                window_seconds=300.0,
                max_entries=256,
            )
            if status == "blocked_search_timeout":
                timeout_timestamps.append(now_ts)
            metrics["kb_lock_timeout_timestamps"] = timeout_timestamps
            metrics["timeout_rate_5m"] = round(
                len(timeout_timestamps) / max(1, len(decision_timestamps)),
                4,
            )

            if error_detail:
                metrics["last_error"] = str(error_detail)
            await self._persist_runtime_metrics_to_session()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to record KB lock decision: {exc}")

    async def _record_upstream_disconnect_diagnostics(
        self,
        *,
        close_code: Any,
        close_reason: str,
    ) -> None:
        try:
            metrics = self._ensure_knowledge_runtime_metrics()
            now_ts = time.time()
            recent_disconnects = self._normalize_recent_timestamps(
                metrics.get("upstream_disconnect_timestamps"),
                now_ts=now_ts,
                window_seconds=300.0,
                max_entries=256,
            )
            recent_disconnects.append(now_ts)
            disconnect_count_5m = len(recent_disconnects)

            ws_lifetime_ms = None
            if self._upstream_connected_at > 0:
                ws_lifetime_ms = round(
                    max(
                        0.0,
                        asyncio.get_running_loop().time() - self._upstream_connected_at,
                    )
                    * 1000,
                    1,
                )

            metrics["upstream_disconnect_timestamps"] = recent_disconnects
            metrics["upstream_disconnect_count_5m"] = disconnect_count_5m
            metrics["upstream_unstable"] = disconnect_count_5m >= 3
            metrics["upstream_disconnect_last_code"] = close_code
            metrics["upstream_disconnect_last_reason"] = str(close_reason or "")
            metrics["upstream_disconnect_last_event_type"] = (
                self._last_upstream_event_type
            )
            metrics["upstream_disconnect_last_ws_lifetime_ms"] = ws_lifetime_ms
            metrics["upstream_disconnect_last_at"] = datetime.now(UTC).isoformat()
            self._record_disconnect_reason("upstream_disconnect")

            await self._persist_runtime_metrics_to_session()
            logger.info(
                "upstream_disconnect_diagnostics",
                session_id=self.session_id,
                close_code=close_code,
                close_reason=str(close_reason or ""),
                active_response_exists=self._active_response is not None,
                last_upstream_event_type=self._last_upstream_event_type,
                ws_lifetime_ms=ws_lifetime_ms,
                reconnect_count_window_5m=disconnect_count_5m,
                upstream_unstable=disconnect_count_5m >= 3,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to record upstream disconnect diagnostics: {exc}")

    async def _persist_runtime_metrics_to_session(self) -> None:
        """Persist in-memory runtime metrics to practice_sessions.voice_policy_snapshot."""
        await persist_runtime_metrics_to_session(
            session_id=self.session_id,
            effective_policy=self._effective_policy,
            session_factory=AsyncSessionLocal,
        )

    def _build_stepfun_tools_from_policy(self) -> list[dict[str, Any]]:
        """Build StepFun tool definitions from resolved policy."""
        return build_stepfun_tools_from_policy(self._effective_policy)

    def _enforce_stepfun_tool_guardrails(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter tool list using final effective policy guarantees."""
        filtered_tools = list(tools)
        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}

        knowledge_base_ids = self._effective_policy.get("knowledge_base_ids")
        has_bound_knowledge_base = isinstance(knowledge_base_ids, list) and bool(
            [item for item in knowledge_base_ids if str(item).strip()]
        )
        network_access_mode = str(
            tool_policy.get("network_access_mode") or "off"
        ).lower()
        allow_web_search_without_kb = bool(
            tool_policy.get("allow_web_search_without_kb", False)
        )

        should_remove_web_search = (
            network_access_mode == "off"
            or has_bound_knowledge_base
            or not allow_web_search_without_kb
        )
        if should_remove_web_search:
            filtered_tools = [
                tool
                for tool in filtered_tools
                if str(tool.get("type") or "").lower() != "web_search"
            ]
        return filtered_tools

    async def _send_upstream(self, payload: dict[str, Any]) -> None:
        """Send one event to StepFun upstream."""
        if self.upstream_ws is None:
            return
        await self.upstream_ws.send(json.dumps(payload, ensure_ascii=False))
        self._mark_upstream_activity()

    async def _ensure_sales_stage_context(self) -> None:
        """Initialize sales-stage capability context once per handler session."""
        if self._sales_stage_context is not None:
            return

        self._sales_stage_context = AgentContext(
            session_id=self.session_id or "",
            agent_id=self._session_agent_id or "unknown-agent",
            persona_id=self._session_persona_id or "unknown-persona",
            user_id=self._session_user_id or "unknown-user",
            state={},
            conversation_history=[],
            agent_config={
                "capabilities_config": {"sales_stage": self._sales_stage_runtime_config}
            },
            persona_config={},
            turn_count=max(0, self.turn_count),
        )
        await self._sales_stage_capability.on_session_start(self._sales_stage_context)

    async def _analyze_and_emit_sales_stage(
        self,
        *,
        user_text: str,
        turn_number: int,
    ) -> str | None:
        """
        Analyze sales stage from user text and emit stage_update only when needed.

        Returns:
            Current stage id for persistence, or None when unavailable.
        """
        normalized_text = user_text.strip()
        if not normalized_text:
            return None

        if not self._sales_stage_enabled:
            return None

        try:
            async with self._sales_stage_lock:
                await self._ensure_sales_stage_context()
                if self._sales_stage_context is None:
                    return None

                self._sales_stage_context.turn_count = max(
                    self._sales_stage_context.turn_count,
                    turn_number,
                )
                result = await self._sales_stage_capability.execute(
                    self._sales_stage_context,
                    normalized_text,
                )
                if not result.success or not isinstance(result.data, dict):
                    return None

                stage_data = result.data
                current_stage = stage_data.get("current_stage")
                if not isinstance(current_stage, str) or not current_stage:
                    return None

                self._latest_stage_data = copy.deepcopy(stage_data)
                stage_changed = bool(stage_data.get("stage_changed", False))
                should_emit = (
                    self._last_emitted_stage is None
                    or stage_changed
                    or current_stage != self._last_emitted_stage
                )
                if should_emit:
                    await self._send_stage_update(stage_data)
                    self._last_emitted_stage = current_stage

                self._append_sales_stage_context_message(
                    role="user",
                    content=normalized_text,
                    turn_number=turn_number,
                )
                return current_stage
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Sales stage analysis degraded on StepFun path",
                session_id=self.session_id,
                turn_number=turn_number,
                error=str(exc),
            )
            return None

    def _append_sales_stage_context_message(
        self,
        *,
        role: str,
        content: str,
        turn_number: int,
    ) -> None:
        """Append message into sales-stage context history for next-turn analysis."""
        if self._sales_stage_context is None:
            return
        text = content.strip()
        if not text:
            return

        self._sales_stage_context.turn_count = max(
            self._sales_stage_context.turn_count,
            turn_number,
        )
        self._sales_stage_context.add_message(role=role, content=text)

    async def _send_stage_update(self, stage_data: dict[str, Any]) -> None:
        """Send stage update event with unified websocket envelope."""
        await self.manager.send_json(
            self.websocket,
            build_stage_update_event(stage_data=stage_data, trace_id=get_trace_id()),
        )

    async def _update_existing_message_sales_stage(
        self,
        *,
        turn_number: int,
        role: str,
        content: str,
        sales_stage: str | None,
        fuzzy_words: list[dict[str, Any]] | None = None,
        score_snapshot: dict[str, Any] | None = None,
        ai_feedback: str | None = None,
        transcript_metadata: dict[str, Any] | None = None,
        objection_ledger: dict[str, Any] | None = None,
    ) -> None:
        """Patch analysis fields for an already persisted duplicate message."""
        if not self.session_id:
            return

        await patch_existing_message_analysis(
            session_id=self.session_id,
            turn_number=turn_number,
            role=role,
            content=content,
            sales_stage=sales_stage,
            fuzzy_words=fuzzy_words,
            score_snapshot=score_snapshot,
            ai_feedback=ai_feedback,
            transcript_metadata=transcript_metadata,
            objection_ledger=objection_ledger,
            db_lock=self._db_lock,
        )

    async def _persist_message(
        self,
        *,
        turn_number: int,
        role: str,
        content: str,
        sales_stage: str | None = None,
        analysis_data: dict[str, Any] | None = None,
    ) -> None:
        """Persist one conversation message for replay/report consistency."""
        if not self.session_id:
            return

        normalized_payload = normalize_message_persistence_payload(
            turn_number=turn_number,
            content=content,
            sales_stage=sales_stage,
            analysis_data=analysis_data,
        )
        if normalized_payload is None:
            return

        normalized_turn, normalized_content, analysis_payload = normalized_payload
        message_key = (normalized_turn, role, normalized_content)

        if message_key in self._persisted_message_keys:
            if analysis_payload:
                patch_fields = extract_analysis_patch_fields(analysis_payload)
                patch_kwargs: dict[str, Any] = {
                    "turn_number": normalized_turn,
                    "role": role,
                    "content": normalized_content,
                    "sales_stage": patch_fields["sales_stage"],
                    "fuzzy_words": patch_fields["fuzzy_words"],
                    "score_snapshot": patch_fields["score_snapshot"],
                    "ai_feedback": patch_fields["ai_feedback"],
                }
                if patch_fields["transcript_metadata"] is not None:
                    patch_kwargs["transcript_metadata"] = patch_fields[
                        "transcript_metadata"
                    ]
                if patch_fields["objection_ledger"] is not None:
                    patch_kwargs["objection_ledger"] = patch_fields["objection_ledger"]
                await self._update_existing_message_sales_stage(
                    **patch_kwargs,
                )
            return

        self._persisted_message_keys.add(message_key)
        saved = await save_stepfun_message(
            session_id=self.session_id,
            turn_number=normalized_turn,
            role=role,
            content=normalized_content,
            analysis_payload=analysis_payload,
            db_lock=self._db_lock,
        )
        if not saved:
            self._persisted_message_keys.discard(message_key)

    def _resolve_user_turn_number_for_transcript(self) -> int:
        """
        Resolve turn_number for final ASR transcript persistence.

        `transcription.completed` may arrive before or after `_create_response(count_turn=True)`.
        - If response state already exists, `turn_count` has advanced to current turn.
        - Otherwise, transcript belongs to the next turn (`turn_count + 1`).
        """
        if self._active_response is not None:
            return max(1, self.turn_count)
        return max(1, self.turn_count + 1)

    async def _send_transcript(self, text: str, is_final: bool) -> None:
        """Send ASR transcript in existing frontend message format."""
        await self.manager.send_json(
            self.websocket,
            build_asr_transcript_event(text=text, is_final=is_final),
        )

    async def _send_status(self, ai_state: str) -> None:
        self.ai_state = ai_state
        await self.manager.send_json(
            self.websocket,
            build_status_event(
                session_status=self.session_status,
                ai_state=ai_state,
                turn_count=self.turn_count,
                trace_id=get_trace_id(),
            ),
        )

    async def _send_heartbeat(self) -> None:
        await self.manager.send_json(
            self.websocket,
            build_heartbeat_event(),
        )

    async def _send_error(self, code: str, message: str) -> None:
        self._record_runtime_error(code, message)
        await self.manager.send_json(
            self.websocket,
            build_error_event(
                code=code,
                message=message,
                session_status=self.session_status,
                ai_state=self.ai_state,
                turn_count=self.turn_count,
                trace_id=get_trace_id(),
            ),
        )

    @staticmethod
    def _extract_text_payload(data: dict) -> str:
        """Extract text payload from websocket data with legacy fallback."""
        return extract_text_payload(data)

    @staticmethod
    def _extract_response_text(response_done_event: dict) -> str:
        """Extract assistant text from response.done payload."""
        return extract_response_text(response_done_event)


def create_stepfun_realtime_handler() -> StepFunRealtimeHandler:
    """Factory for router registration."""
    return StepFunRealtimeHandler()
