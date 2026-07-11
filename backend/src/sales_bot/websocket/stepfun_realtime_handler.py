"""
StepFun Realtime WebSocket Handler

Provides a proxy bridge between frontend practice WebSocket protocol and
StepFun Realtime API, enabling a dual-mode runtime:
- legacy: existing ASR -> LLM -> TTS pipeline
- stepfun_realtime: end-to-end realtime speech model
"""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportGeneralTypeIssues=false, reportMissingImports=false
# ruff: noqa: F401, I001, E402

import asyncio
import copy
import inspect
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from collections.abc import Callable
from typing import Any, cast

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
    SessionLifecycleService,
    SessionLifecycleTransition,
)
from common.effectiveness import coerce_live_session_conclusion_summary
from common.effectiveness.schemas import ActionCard
from common.knowledge.kb_lock_guard import (
    resolve_answerability_mode as resolve_kb_answerability_mode,
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
    build_instruction_contract_hash,
    enforce_question_limit,
)
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from sales_bot.websocket.components.curriculum_stage_runtime import (
    CurriculumStageRuntime,
    CurriculumStageRuntimeResult,
)
from sales_bot.websocket.components.stepfun_emotion_analyzer import (
    StepFunEmotionAnalyzer,
)
from sales_bot.websocket.components.stepfun_thinking_capture import (
    StepFunThinkingCapture,
)
from sales_bot.websocket.components.stepfun_turn_transcript_capture import (
    StepFunTurnTranscriptCapture,
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
from sales_bot.websocket.components.stepfun_roleplay_runtime_helpers import (
    build_roleplay_runtime_state_patch,
    restore_roleplay_runtime_state,
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
from sales_bot.websocket.components.stepfun_voice_selection import resolve_session_voice
from sales_bot.websocket.realtime_feedback_arbiter import (
    RealtimeFeedbackArbiter,
    RealtimeFeedbackPacingState,
)
from sales_bot.websocket.realtime_audio_flow import RealtimeAudioFlowModule
from sales_bot.websocket.realtime_turn_coordinator import RealtimeTurnCoordinator
from sales_bot.websocket.session_control_adapter import SessionControlAdapter
from sales_bot.websocket.voice_runtime_profile import VoiceRuntimeProfile
from sales_bot.websocket.grounding_decision_pipeline import (
    GroundingDecisionContext,
    GroundingDecisionPipeline,
)
from sales_bot.websocket.stepfun_tool_execution import (
    StepFunToolExecutionModule,
    ToolExecutionContext,
)
from sales_bot.websocket.phase4_local_provider import (
    Phase4LocalStepFunProvider,
    should_use_phase4_local_provider,
)
from sales_bot.websocket.stepfun_realtime_state import StepFunRealtimeStateBase
from training_runtime import (
    StepFunSessionConfig,
    StepFunTransport,
    build_stepfun_session_update_payload,
)
from training_runtime.stepfun_transport import StepFunBackpressurePolicy
from training_runtime.stepfun_transport import StepFunBackpressureStatus
from training_runtime.stepfun_transport import StepFunHealthStatus
from training_runtime.stepfun_transport import StepFunUpstreamConnectError

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
DEFAULT_UPSTREAM_PROACTIVE_REFRESH_IDLE_MS = 45000
DEFAULT_AUDIO_BACKPRESSURE_HIGH_WATERMARK_BYTES = 512 * 1024
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


class StepFunRealtimeSharedHandler(
    StepFunRealtimeConnectionMixin,
    StepFunRealtimePolicyMixin,
    StepFunRealtimeUpstreamMixin,
    StepFunRealtimeFeedbackMixin,
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

    def __init__(
        self,
        *,
        stepfun_transport: StepFunTransport | None = None,
        db_session_factory: Callable[[], Any] | None = None,
        knowledge_service_factory: Callable[[AsyncSession], Any] | None = None,
        transcript_capture_sink: Callable[[dict[str, Any]], Any] | None = None,
        scenario: str = "sales",
        sales_capabilities_enabled: bool = True,
    ) -> None:
        super().__init__(scenario)
        self.upstream_ws = None
        self._stepfun_transport = stepfun_transport or StepFunTransport(
            local_provider_enabled=should_use_phase4_local_provider,
            local_provider_factory=lambda: Phase4LocalStepFunProvider.from_env(
                self.scenario
            ),
        )
        self._db_session_factory = db_session_factory or self._default_db_session_factory
        self._knowledge_service_factory = (
            knowledge_service_factory or self._default_knowledge_service_factory
        )
        self._tool_execution = StepFunToolExecutionModule()
        self._upstream_task: asyncio.Task | None = None
        self._effective_policy: dict[str, Any] = {}
        self._roleplay_disclosure_state: dict[str, Any] = {}
        self._roleplay_regenerate_attempted_for_turn = False
        self._roleplay_repair_instruction = ""
        self._voice_runtime_profile: VoiceRuntimeProfile | None = None
        self._coach_health: str = "healthy"
        self._coach_health_reason: str | None = None

        self.current_request_id = 0
        self._active_response: RealtimeResponseState | None = None
        self._audio_flow = RealtimeAudioFlowModule()
        self._turn_coordinator = RealtimeTurnCoordinator()
        self._function_call_states: dict[str, FunctionCallState] = {}
        self._executed_call_ids: set[str] = set()

        self._stepfun_api_key = os.getenv("STEPFUN_API_KEY", "")
        self._stepfun_url = os.getenv(
            "STEPFUN_REALTIME_URL", "wss://api.stepfun.com/v1/realtime"
        )
        self._stepfun_model = os.getenv(
            "STEPFUN_REALTIME_MODEL", "stepaudio-2.5-realtime"
        )
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
        if (
            self._stepfun_input_transcription_enabled
            and not self._stepfun_input_transcription_model
        ):
            logger.warning(
                "StepFun input transcription model is not configured; "
                "upstream ASR may return empty transcripts",
                input_transcription_language=self._stepfun_input_transcription_language,
            )
        self._stepfun_instructions = os.getenv("STEPFUN_REALTIME_INSTRUCTIONS", "")
        self._instruction_contract_hash = build_instruction_contract_hash(
            self._stepfun_instructions
        )
        self.session_status = "preparing"
        self.ai_state = "idle"
        self.session_scenario_type = scenario
        self.turn_count = 0
        self._db_lock = asyncio.Lock()
        self._persisted_message_keys: set[tuple[int, str, str]] = set()
        self._sales_stage_runtime_config: dict[str, Any] = {
            "enabled": sales_capabilities_enabled
        }
        self._sales_stage_enabled = sales_capabilities_enabled
        self._sales_stage_capability = (
            SalesStageCapability(self._sales_stage_runtime_config)
            if sales_capabilities_enabled
            else None
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

        self._fuzzy_detection_runtime_config: dict[str, Any] = {
            "enabled": sales_capabilities_enabled
        }
        self._fuzzy_detection_enabled = sales_capabilities_enabled
        self._fuzzy_detection_capability = (
            FuzzyDetectionCapability(self._fuzzy_detection_runtime_config)
            if sales_capabilities_enabled
            else None
        )

        self._realtime_scoring_runtime_config: dict[str, Any] = {
            "enabled": sales_capabilities_enabled
        }
        self._realtime_scoring_enabled = sales_capabilities_enabled
        self._realtime_scoring_capability = (
            RealtimeScoringCapability(self._realtime_scoring_runtime_config)
            if sales_capabilities_enabled
            else None
        )
        self._latest_score_snapshot: dict[str, Any] | None = None
        self._latest_live_session_summary: dict[str, Any] | None = None
        self._latest_claim_truth: dict[str, Any] | None = None
        self._latest_action_card: ActionCard | None = None
        self._latest_knowledge_answer_diagnostics: dict[str, Any] | None = None
        self._curriculum_snapshot: dict[str, Any] | None = None
        self._curriculum_stage_runtime: CurriculumStageRuntime | None = None
        self._emotion_analyzer = StepFunEmotionAnalyzer()
        self._thinking_capture = StepFunThinkingCapture(
            turn_index=lambda: int(self.turn_count or 0),
            template_stage_key=self._current_template_stage_key,
        )
        self._turn_transcript_capture = StepFunTurnTranscriptCapture(
            session_id=lambda: str(self.session_id or ""),
            template_stage_key=self._current_template_stage_key,
            instruction_contract_hash=self._current_transcript_capture_instruction_contract_hash,
            grounding_metadata=self._current_transcript_capture_grounding_metadata,
            sink=transcript_capture_sink,
        )
        self._objection_ledger: dict[str, Any] | None = None
        self._feedback_arbiter = RealtimeFeedbackArbiter()
        self._feedback_pacing_state = RealtimeFeedbackPacingState()

        self._feedback_context: AgentContext | None = None
        self._assistant_transcript_capture_context: dict[str, Any] | None = None
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
        self._received_binary_audio_frame_count = 0
        self._reset_input_audio_quality()
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
        self._tool_execution.configure_cache(
            max_entries=self._internal_retrieval_cache_max_entries,
        )
        self._grounding_pipeline = GroundingDecisionPipeline(
            retriever=self._retrieve_grounding_via_internal_knowledge,
            warmup_callable=self._run_kb_lock_warmup,
            cache_ttl_seconds=self._internal_retrieval_cache_ttl_seconds,
        )
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
        self._upstream_proactive_refresh_idle_seconds = (
            self._resolve_upstream_auto_recover_delay_seconds_from_env(
                "STEPFUN_UPSTREAM_PROACTIVE_REFRESH_IDLE_MS",
                default_ms=DEFAULT_UPSTREAM_PROACTIVE_REFRESH_IDLE_MS,
                min_ms=0,
                max_ms=120000,
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
        self._unavailable_voice_ids: set[str] = set()
        self._selected_stepfun_voice: str | None = None

    def _default_db_session_factory(self) -> Any:
        return AsyncSessionLocal()

    def _default_knowledge_service_factory(self, db: AsyncSession) -> Any:
        return KnowledgeService(db)

    async def _retrieve_grounding_via_internal_knowledge(
        self, arguments_obj: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._tool_search_internal_knowledge(arguments_obj)

    def _reset_turn_runtime_state(self) -> None:
        """Clear turn-scoped state that must not leak across reconnects or interrupts."""
        self._pending_grounding_context = ""
        self._pending_blocked_response_text = ""
        self._roleplay_regenerate_attempted_for_turn = False
        self._roleplay_repair_instruction = ""
        self._latest_input_transcript_delta = ""
        self._pending_tool_followup_response = False
        self._awaiting_transcription_after_commit = False
        self._allow_late_transcription_response = False
        self._has_uncommitted_audio = False
        self._audio_flow.clear_input_audio()
        self._audio_flow.clear_output_audio()
        self._active_response = None
        self._turn_coordinator.reset()
        self._tool_execution.clear_turn_registry()
        self._function_call_states.clear()
        self._executed_call_ids.clear()
        self._thinking_capture.clear()
        self._turn_transcript_capture.clear()
        self._assistant_transcript_capture_context = None

    def _current_transcript_capture_instruction_contract_hash(self) -> str | None:
        try:
            profile = self._active_voice_runtime_profile()
        except AttributeError:
            profile = None
        if profile is not None:
            contract_hash = str(profile.instruction_contract_hash or "").strip()
            if contract_hash:
                return contract_hash
        effective_policy = self._effective_policy if isinstance(self._effective_policy, dict) else {}
        contract_hash = str(
            effective_policy.get("instruction_contract_hash")
            or self._instruction_contract_hash
            or ""
        ).strip()
        return contract_hash or None

    def _current_transcript_capture_grounding_metadata(self) -> dict[str, Any] | None:
        metadata: dict[str, Any] = {}
        effective_policy = (
            self._effective_policy if isinstance(self._effective_policy, dict) else {}
        )
        raw_kb_ids = effective_policy.get("knowledge_base_ids")
        if isinstance(raw_kb_ids, list):
            knowledge_base_ids = [
                str(item).strip() for item in raw_kb_ids if str(item).strip()
            ]
            if knowledge_base_ids:
                metadata["knowledge_base_ids"] = knowledge_base_ids

        diagnostics = (
            self._latest_knowledge_answer_diagnostics
            if isinstance(self._latest_knowledge_answer_diagnostics, dict)
            else {}
        )
        for key in (
            "mode",
            "answerability",
            "source_status",
            "audit_run_id",
            "live_audit_run_id",
            "shadow_audit_run_id",
        ):
            value = diagnostics.get(key)
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()

        raw_citations = diagnostics.get("citations")
        citations: list[dict[str, Any]] = []
        if isinstance(raw_citations, list):
            for item in raw_citations:
                if not isinstance(item, dict):
                    continue
                safe_citation: dict[str, Any] = {}
                for key in (
                    "knowledge_base_id",
                    "knowledge_base_name",
                    "document_title",
                ):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        safe_citation[key] = value.strip()
                score = item.get("score")
                if isinstance(score, (int, float)):
                    safe_citation["score"] = float(score)
                if safe_citation:
                    citations.append(safe_citation)
        if citations:
            metadata["citation_count"] = len(citations)
            metadata["citations"] = citations
        return metadata or None

    def _current_transcript_capture_turn_id(self) -> str | None:
        if self._active_response is not None:
            return str(self._active_response.request_id)
        current_turn = self._turn_coordinator.get_current_turn()
        if current_turn is None:
            return None
        return str(current_turn.turn_id)

    def _current_transcript_capture_turn_index(self) -> int:
        return max(1, int(self.turn_count or 0))

    @staticmethod
    def _build_answerability_instruction_overlay(
        mode: str,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        return GroundingDecisionPipeline().build_instruction_overlay(mode, diagnostics)

    def _build_blocked_response_from_answerability(
        self,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        return self._grounding_pipeline.build_blocked_response(diagnostics)

    def _apply_answerability_output_guard(self, response_text: str) -> str:
        return self._grounding_pipeline.apply_output_guard(
            response_text,
            self._latest_knowledge_answer_diagnostics,
        )

    @staticmethod
    def _merge_transcript_normalization_lexicon(
        base_policy: dict[str, Any],
        kb_lexicon: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        if not kb_lexicon:
            return base_policy, False

        existing_lexicon = base_policy.get("transcript_normalization_lexicon")
        merged_lexicon = (
            list(existing_lexicon) if isinstance(existing_lexicon, list) else []
        )
        seen: set[tuple[str, tuple[str, ...], str]] = set()
        for item in merged_lexicon:
            if not isinstance(item, dict):
                continue
            aliases = item.get("aliases")
            alias_tuple = tuple(str(alias) for alias in aliases if str(alias).strip()) if isinstance(aliases, list) else ()
            seen.add(
                (
                    str(item.get("canonical_term") or ""),
                    alias_tuple,
                    str(item.get("scope") or ""),
                )
            )

        changed = False
        for item in kb_lexicon:
            aliases = item.get("aliases")
            if not isinstance(aliases, list) or not aliases:
                continue
            alias_tuple = tuple(str(alias) for alias in aliases if str(alias).strip())
            key = (
                str(item.get("canonical_term") or ""),
                alias_tuple,
                str(item.get("scope") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged_lexicon.append(dict(item))
            changed = True

        if not changed:
            return base_policy, False
        next_policy = dict(base_policy)
        next_policy["transcript_normalization_lexicon"] = merged_lexicon
        next_policy.setdefault("transcript_normalization_enabled", True)
        return next_policy, True

    async def _merge_kb_dictionary_into_effective_policy(self, db: AsyncSession) -> bool:
        knowledge_base_ids = self._effective_policy.get("knowledge_base_ids")
        if not isinstance(knowledge_base_ids, list) or not knowledge_base_ids:
            return False
        tool_policy = self._effective_policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}

        try:
            kb_lexicon = await self._knowledge_service_factory(db).active_dictionary_lexicon(
                [str(kb_id) for kb_id in knowledge_base_ids if str(kb_id).strip()]
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Skipped KB dictionary transcript normalization merge",
                session_id=self.session_id,
                error=str(exc),
            )
            return False

        merged_tool_policy, changed = self._merge_transcript_normalization_lexicon(
            tool_policy,
            kb_lexicon,
        )
        if not changed:
            return False
        self._effective_policy = dict(self._effective_policy)
        self._effective_policy["tool_policy"] = merged_tool_policy
        source = self._effective_policy.get("source")
        if not isinstance(source, dict):
            source = {}
        source = dict(source)
        source["kb_dictionary_lexicon"] = "knowledge_base_active_dictionary"
        self._effective_policy["source"] = source
        return True

    def _current_audio_backpressure_pending_bytes(self) -> int:
        return self._audio_flow.pending_input_audio_bytes()

    def _should_drop_upstream_for_backpressure(self, payload: dict[str, Any]) -> bool:
        result = self._stepfun_transport.decide_backpressure(
            payload,
            pending_bytes=self._current_audio_backpressure_pending_bytes(),
            policy=StepFunBackpressurePolicy(
                high_watermark_bytes=DEFAULT_AUDIO_BACKPRESSURE_HIGH_WATERMARK_BYTES,
            ),
        )
        return result.status == StepFunBackpressureStatus.DROP

    async def _send_upstream_keepalive_ping(self, upstream_ws: Any) -> None:
        result = await self._stepfun_transport.check_health(
            upstream_ws,
            timeout_seconds=self._upstream_keepalive_pong_timeout_seconds,
        )
        if result.status == StepFunHealthStatus.HEALTHY:
            self._mark_upstream_activity()
            return
        raise RuntimeError(result.error_type or "unhealthy")

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
        if self._feedback_context is not None:
            emotion_log = self._feedback_context.state.get("emotion_log")
            if isinstance(emotion_log, list) and emotion_log:
                runtime_state["emotion_log"] = copy.deepcopy(emotion_log)
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
        if self._curriculum_stage_runtime is not None:
            curriculum_patch = self._curriculum_stage_runtime.runtime_state_patch()
            if curriculum_patch:
                runtime_state.update(copy.deepcopy(curriculum_patch))
        roleplay_patch = build_roleplay_runtime_state_patch(self._effective_policy)
        if roleplay_patch:
            runtime_state.update(copy.deepcopy(roleplay_patch))
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
        runtime_state = state.runtime_state if isinstance(state.runtime_state, dict) else {}
        restore_roleplay_runtime_state(self._effective_policy, runtime_state)
        if self._curriculum_stage_runtime is not None:
            self._curriculum_stage_runtime.restore_runtime_state(runtime_state)

    def _curriculum_runtime_payload(self) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        curriculum_snapshot = self._curriculum_snapshot
        if isinstance(curriculum_snapshot, dict):
            stage_snapshots = curriculum_snapshot.get("stage_snapshots")
            if isinstance(stage_snapshots, dict):
                return None, stage_snapshots
        runtime_snapshot = self._effective_policy.get("runtime_snapshot")
        stage_snapshots = self._effective_policy.get("stage_snapshots")
        if isinstance(runtime_snapshot, dict):
            stage_snapshots = runtime_snapshot.get("stage_snapshots") or stage_snapshots
        if not isinstance(stage_snapshots, dict):
            return None, {}
        return None, stage_snapshots

    async def _initialize_curriculum_stage_runtime(
        self, runtime_state: dict[str, Any] | None = None
    ) -> None:
        curriculum_plan, stage_snapshots = self._curriculum_runtime_payload()
        if not stage_snapshots:
            self._curriculum_stage_runtime = None
            return
        self._curriculum_stage_runtime = CurriculumStageRuntime(
            curriculum_plan=curriculum_plan,
            stage_snapshots=stage_snapshots,
            runtime_state=runtime_state,
        )
        result = self._curriculum_stage_runtime.initialize(
            now_seconds=asyncio.get_running_loop().time()
        )
        await self._apply_curriculum_stage_runtime_result(result)

    async def _apply_curriculum_stage_runtime_result(
        self, result: CurriculumStageRuntimeResult
    ) -> None:
        if not result.runtime_state_patch and not result.websocket_events:
            return
        if result.runtime_state_patch:
            await self._persist_curriculum_stage_runtime_state(result.runtime_state_patch)
        for event in result.websocket_events:
            await self._send_curriculum_stage_event(event)

    async def _persist_curriculum_stage_runtime_state(
        self, runtime_state_patch: dict[str, Any]
    ) -> None:
        if not self.session_id:
            return
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession).where(PracticeSession.session_id == self.session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return
            existing_state: dict[str, Any] = session.runtime_state if isinstance(session.runtime_state, dict) else {}
            cast(Any, session).runtime_state = {
                **copy.deepcopy(existing_state),
                **copy.deepcopy(runtime_state_patch),
            }
            await db.commit()

    async def _send_curriculum_stage_event(self, event: dict[str, Any]) -> None:
        websocket = self._get_active_websocket()
        if not websocket:
            return
        outbound = copy.deepcopy(event)
        outbound.setdefault("timestamp", datetime.now(UTC).isoformat())
        outbound.setdefault("trace_id", get_trace_id())
        data = outbound.get("data")
        outbound["data"] = data if isinstance(data, dict) else {}
        outbound["data"].setdefault("session_id", self.session_id)
        await self.manager.send_json(websocket, outbound)

    async def _handle_curriculum_stage_turn(self, *, turn_number: int) -> None:
        if self._curriculum_stage_runtime is None:
            return
        score = None
        if isinstance(self._latest_score_snapshot, dict):
            score = self._latest_score_snapshot.get("overall_score")
        result = self._curriculum_stage_runtime.handle_turn(
            turn_number=turn_number,
            template_stage_score=score,
            now_seconds=asyncio.get_running_loop().time(),
        )
        await self._apply_curriculum_stage_runtime_result(result)

    async def _handle_curriculum_stage_timing(self) -> None:
        if self._curriculum_stage_runtime is None:
            return
        result = self._curriculum_stage_runtime.handle_timing(
            now_seconds=asyncio.get_running_loop().time()
        )
        await self._apply_curriculum_stage_runtime_result(result)

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
            self.user_id = payload.get("user_id") or payload.get("sub")
        except (JWTError, RuntimeError, ValueError, OSError) as exc:
            logger.warning(f"Token verification failed: {exc}")
            set_trace_id(normalize_trace_id(trace_id) or "")
            await websocket.close(code=4401, reason="unauthorized")
            return

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
        logger.info(
            "practice_ws_session_start",
            session_id=session_id,
            user_id=self.user_id,
            voice_mode="stepfun_realtime",
            connection_epoch=self._connection_epoch,
        )

        if not self._stepfun_api_key:
            await self._send_error(
                "[STEPFUN_KEY_MISSING]",
                "未配置 STEPFUN_API_KEY，无法使用 Realtime 模式",
            )
            await self.close(code=4000, reason="STEPFUN_API_KEY missing")
            await self.manager.disconnect(self.scenario, session_id)
            return

        from common.services.session_runtime_lifecycle_hooks import (
            mark_session_runtime_started,
        )

        await mark_session_runtime_started(
            session_id,
            source="sales_stepfun_on_open",
        )

        self.running = True

        try:
            await self._load_effective_policy()
            existing_runtime_state = (
                existing_state.runtime_state
                if existing_state is not None and isinstance(existing_state.runtime_state, dict)
                else None
            )
            await self._initialize_curriculum_stage_runtime(existing_runtime_state)
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
                    await self._handle_curriculum_stage_timing()
                    await self._send_heartbeat()

        except WebSocketDisconnect:
            self._record_disconnect_reason("client_disconnect")
            logger.info(f"StepFun WS disconnected: session={session_id}")
        except asyncio.CancelledError:
            logger.info(f"StepFun WS cancelled: session={session_id}")
        except StepFunUpstreamConnectError as exc:
            self._record_disconnect_reason("stepfun_upstream_rejected")
            logger.error(
                "StepFun upstream handshake rejected",
                session_id=session_id,
                status_code=exc.status_code,
                error=str(exc),
            )
            await self._send_error("[STEPFUN_UPSTREAM_REJECTED]", str(exc))
        except AttributeError as exc:
            self._record_disconnect_reason("upstream_transport_mismatch")
            logger.error(
                "practice_ws_session_error",
                session_id=session_id,
                error_type=type(exc).__name__,
                error=str(exc),
                exc_info=True,
            )
            await self._send_error(
                "[STEPFUN_TRANSPORT_ERROR]",
                "StepFun 上游协议不兼容（缺少 send/send_json），请更新后端后重试。",
            )
        except (RuntimeError, ValueError, OSError) as e:
            self._record_disconnect_reason("runtime_error")
            logger.error(
                "practice_ws_session_error",
                session_id=session_id,
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            await self._send_error(
                "[STEPFUN_CONNECTION_ERROR]", "Realtime 语音连接失败"
            )
        finally:
            logger.info(
                "practice_ws_session_end",
                session_id=session_id,
                disconnect_reason=self._last_disconnect_reason,
                connection_epoch=self._connection_epoch,
            )
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

    async def _connect_upstream(self) -> None:
        """Connect to StepFun realtime WebSocket and initialize session."""
        profile = self._active_voice_runtime_profile()
        logger.info(f"Connecting StepFun realtime: model={profile.model_name}")
        self.upstream_ws = await self._stepfun_transport.connect(
            api_key=self._stepfun_api_key,
            url=self._stepfun_url,
            model=profile.model_name,
        )
        now = asyncio.get_running_loop().time()
        self._upstream_connected_at = now
        self._upstream_last_activity_at = now
        self._last_upstream_event_type = ""

        session_payload = build_stepfun_session_update_payload(
            self._build_stepfun_session_config()
        )

        await self._send_upstream(session_payload)
        self._ensure_upstream_keepalive_task()
        logger.info("StepFun session.update sent")
        await self._maybe_start_kb_lock_warmup()

    def _build_stepfun_session_config(self) -> StepFunSessionConfig:
        """Collect handler-owned runtime values into transport session config."""

        profile = self._active_voice_runtime_profile()
        turn_detection_value = None
        if self._effective_policy.get("turn_detection") == "server_vad":
            turn_detection_value = {"type": "server_vad"}

        selected_voice = resolve_session_voice(
            default_voice=profile.voice_name,
            runtime_snapshot=self._curriculum_snapshot,
            unavailable_voice_ids=self._unavailable_voice_ids,
        )
        self._selected_stepfun_voice = selected_voice
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
            input_transcription_language=self._stepfun_input_transcription_language,
            input_transcription_model_configured=bool(
                self._stepfun_input_transcription_model
            ),
            input_transcription_model=self._stepfun_input_transcription_model,
            input_audio_format=self._stepfun_input_audio_format,
            output_audio_format=self._stepfun_output_audio_format,
        )
        return StepFunSessionConfig(
            voice=selected_voice,
            temperature=profile.temperature,
            input_audio_format=self._stepfun_input_audio_format,
            output_audio_format=self._stepfun_output_audio_format,
            turn_detection=turn_detection_value,
            input_transcription_enabled=self._stepfun_input_transcription_enabled,
            input_transcription_language=self._stepfun_input_transcription_language,
            input_transcription_model=self._stepfun_input_transcription_model,
            instructions=profile.instructions,
            tools=tools,
        )

    async def _close_upstream(self) -> None:
        """Close upstream connection safely."""
        await self._stop_upstream_keepalive_task()
        await self._stepfun_transport.close(self.upstream_ws)
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
            self._grounding_pipeline.warmup(normalized_kb_ids)
        )

    async def _run_kb_lock_warmup(self, kb_ids: list[str]) -> None:
        started_at = asyncio.get_running_loop().time()
        chromadb_warmed = False
        embedding_client_warmed = False
        try:
            async with self._db_session_factory() as db:
                knowledge_service = self._knowledge_service_factory(db)
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

    async def _persist_runtime_metrics_to_session(self) -> None:
        """Persist in-memory runtime metrics to practice_sessions.voice_policy_snapshot."""
        await persist_runtime_metrics_to_session(
            session_id=self.session_id,
            effective_policy=self._effective_policy,
            session_factory=self._db_session_factory,
        )


class StepFunRealtimeHandler(
    StepFunRealtimeSalesStageMixin,
    StepFunRealtimeSharedHandler,
):
    async def _handle_upstream_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "")
        self._turn_transcript_capture.on_upstream_event(
            event,
            active_response=self._active_response,
            turn_id=self._current_transcript_capture_turn_id(),
            turn_index=self._current_transcript_capture_turn_index(),
        )
        await super()._handle_upstream_event(event)
        if (
            event_type == "response.created"
            and self._active_response is not None
            and self._active_response.response_id
        ):
            self._assistant_transcript_capture_context = {
                "response_id": self._active_response.response_id,
                "turn_id": str(self._active_response.request_id),
                "turn_index": self._current_transcript_capture_turn_index(),
                "source_event_type": "response.done",
            }
        elif event_type == "response.done":
            self._assistant_transcript_capture_context = None

    async def _send_transcript(self, text: str, is_final: bool) -> None:
        await super()._send_transcript(text, is_final)
        if not is_final:
            return
        self._turn_transcript_capture.capture_learner_transcript(
            transcript=text,
            turn_id=None,
            turn_index=self._resolve_user_turn_number_for_transcript(),
            source_event_type="input_audio_transcription.completed",
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
        await super()._persist_message(
            turn_number=turn_number,
            role=role,
            content=content,
            sales_stage=sales_stage,
            analysis_data=analysis_data,
        )
        if role != "assistant":
            return
        context = (
            self._assistant_transcript_capture_context
            if isinstance(self._assistant_transcript_capture_context, dict)
            else {}
        )
        self._turn_transcript_capture.capture_assistant_transcript(
            transcript=content,
            response_id=cast(str | None, context.get("response_id")),
            turn_id=cast(str | None, context.get("turn_id")),
            turn_index=max(1, int(context.get("turn_index") or turn_number or 0)),
            source_event_type=str(
                context.get("source_event_type") or "assistant_message_persisted"
            ),
        )

    async def _send_roleplay_repair_audio(
        self,
        response_state: RealtimeResponseState,
    ) -> None:
        already_sent = response_state.roleplay_repair_sent
        await super()._send_roleplay_repair_audio(response_state)
        if already_sent or not response_state.roleplay_repair_sent:
            return
        repair_text = self._roleplay_repair_message(
            self._roleplay_contract(),
            response_state.roleplay_violation_decision or {},
        )
        self._turn_transcript_capture.capture_assistant_transcript(
            transcript=repair_text,
            response_id=response_state.response_id,
            turn_id=str(response_state.request_id),
            turn_index=self._current_transcript_capture_turn_index(),
            source_event_type="roleplay_repair_audio",
        )


def create_stepfun_realtime_handler(
    *,
    transcript_capture_sink: Callable[[dict[str, Any]], Any] | None = None,
) -> StepFunRealtimeHandler:
    """Factory for router registration."""
    return StepFunRealtimeHandler(transcript_capture_sink=transcript_capture_sink)
