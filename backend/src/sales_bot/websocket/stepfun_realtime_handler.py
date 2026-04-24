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
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlencode

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
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
from sales_bot.websocket.stepfun_realtime_constants import (
    DEFAULT_GROUNDING_PREFETCH_TIMEOUT_MS,
    DEFAULT_INTERNAL_RETRIEVAL_CACHE_MAX_ENTRIES,
    DEFAULT_INTERNAL_RETRIEVAL_CACHE_TTL_MS,
    DEFAULT_KB_LOCK_DECISION_TIMEOUT_MS,
    DEFAULT_KB_LOCK_WARMUP_ENABLED,
    DEFAULT_UPSTREAM_AUTO_RECOVER_BASE_DELAY_MS,
    DEFAULT_UPSTREAM_AUTO_RECOVER_ENABLED,
    DEFAULT_UPSTREAM_AUTO_RECOVER_MAX_DELAY_MS,
    DEFAULT_UPSTREAM_AUTO_RECOVER_MAX_RETRIES,
    DEFAULT_UPSTREAM_KEEPALIVE_ENABLED,
    DEFAULT_UPSTREAM_KEEPALIVE_INTERVAL_MS,
    DEFAULT_UPSTREAM_KEEPALIVE_PONG_TIMEOUT_MS,
    GROUNDING_WAIT_GRACE_SECONDS,
    GROUNDING_WAIT_POLL_SECONDS,
    PENDING_RESPONSE_FALLBACK_SECONDS,
    STEPFUN_RUNTIME_EVENT_INVENTORY,
    TERMINAL_SESSION_STATUSES,
    TRANSCRIPTION_DUPLICATE_WINDOW_SECONDS,
    TRANSCRIPTION_WAIT_GRACE_SECONDS,
)
from sales_bot.websocket.stepfun_runtime_types import (
    FunctionCallState,
    RealtimeResponseState,
)

logger = get_logger(__name__)
from sales_bot.websocket.stepfun_realtime_connection import (
    StepFunRealtimeConnectionMixin,
)
from sales_bot.websocket.stepfun_realtime_policy import StepFunRealtimePolicyMixin
from sales_bot.websocket.stepfun_realtime_upstream import StepFunRealtimeUpstreamMixin


class StepFunRealtimeHandler(
    StepFunRealtimeConnectionMixin,
    StepFunRealtimePolicyMixin,
    StepFunRealtimeUpstreamMixin,
    BaseWebSocketHandler,
):
    """
    Proxy handler for StepFun Realtime API.

    Frontend protocol is kept compatible with current app:
    - incoming: audio_chunk/audio_end/text/control/user_speaking/interrupt
    - outgoing: asr_transcript/status/tts_audio/error/heartbeat
    """

    BINARY_AUDIO_CHUNK = 0x01
    BINARY_AUDIO_INTERRUPT = 0x02

    def __init__(self):
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
        self._tts_chunk_protocol_version = str(
            os.getenv("STEPFUN_TTS_CHUNK_PROTOCOL_VERSION", "v1")
        ).strip().lower()
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

    async def _load_effective_policy(self):
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

            self._session_agent_id = str(session.agent_id) if session.agent_id else None
            self._session_persona_id = (
                str(session.persona_id) if session.persona_id else None
            )
            self._session_user_id = str(session.user_id) if session.user_id else None
            await self._refresh_sales_stage_runtime_config(db)

            snapshot = (
                session.voice_policy_snapshot
                if isinstance(session.voice_policy_snapshot, dict)
                else None
            )

            policy_source = "snapshot"
            if snapshot:
                self._effective_policy = snapshot
            else:
                policy_service = VoiceRuntimePolicyService(db)
                resolved_policy = await policy_service.resolve_effective_policy(
                    agent_id=session.agent_id,
                    persona_id=session.persona_id,
                    voice_mode_override=session.voice_mode,
                    runtime_profile_override=session.voice_runtime_profile_id,
                )
                self._effective_policy = resolved_policy
                session.voice_policy_snapshot = self._effective_policy
                session.voice_mode = self._effective_policy.get(
                    "voice_mode", session.voice_mode or "legacy"
                )
                session.voice_runtime_profile_id = self._effective_policy.get(
                    "runtime_profile_id"
                )
                await db.commit()
                policy_source = "resolved"

            guardrail_applied = self._enforce_tool_policy_guardrails()
            if guardrail_applied:
                session.voice_policy_snapshot = self._effective_policy
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

    async def _refresh_sales_stage_runtime_config(self, db) -> None:
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

    async def _sync_session_state(self):
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

    async def _apply_lifecycle_action(self, action: SessionLifecycleAction):
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

    async def _persist_runtime_metrics_to_session(self) -> None:
        """Persist in-memory runtime metrics to practice_sessions.voice_policy_snapshot."""
        await persist_runtime_metrics_to_session(
            session_id=self.session_id,
            effective_policy=self._effective_policy,
            session_factory=AsyncSessionLocal,
        )


def create_stepfun_realtime_handler() -> StepFunRealtimeHandler:
    """Factory for router registration."""
    return StepFunRealtimeHandler()
