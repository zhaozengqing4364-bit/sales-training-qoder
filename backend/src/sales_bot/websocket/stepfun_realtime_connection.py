"""Connection mixin for the StepFun realtime websocket handler."""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportGeneralTypeIssues=false
# ruff: noqa: F401, I001

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
    apply_answerability_output_guard as apply_kb_answerability_output_guard,
    build_answerability_instruction_overlay as build_kb_answerability_instruction_overlay,
    build_blocked_response_from_answerability as build_kb_blocked_response_from_answerability,
    build_kb_coach_grounding_context,
    evaluate_kb_lock_decision,
    resolve_answerability_mode as resolve_kb_answerability_mode,
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
from sales_bot.websocket.components.stepfun_asr_fallback import (
    ASR_FALLBACK_REQUIRED_ERROR_CODE,
    DEFAULT_ASR_FALLBACK_POLICY,
    build_asr_fallback_status_event,
    extract_asr_error_reason,
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
from sales_bot.websocket.components.stepfun_tts_contracts import build_tts_chunk_event
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


def _handler_symbol(name: str, fallback: Any) -> Any:
    """Read monkeypatch-compatible symbols from the public handler module."""
    module = sys.modules.get("sales_bot.websocket.stepfun_realtime_handler")
    return getattr(module, name, fallback) if module is not None else fallback


class StepFunRealtimeConnectionMixin(StepFunRealtimeStateBase):
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
        return (
            resolve_kb_answerability_mode(
                diagnostics,
                kb_lock_required=self._is_kb_lock_required_for_current_policy(),
            ),
            diagnostics,
        )

    @staticmethod
    def _build_answerability_instruction_overlay(
        mode: str,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        return build_kb_answerability_instruction_overlay(mode, diagnostics)

    def _build_blocked_response_from_answerability(
        self,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        return build_kb_blocked_response_from_answerability(diagnostics)

    @staticmethod
    def _split_response_sentences(text: str) -> list[str]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        sentences = re.findall(r"[^。！？!?]+[。！？!?]?", normalized)
        cleaned = [sentence.strip() for sentence in sentences if sentence.strip()]
        return cleaned or [normalized]

    def _apply_answerability_output_guard(self, response_text: str) -> str:
        return apply_kb_answerability_output_guard(
            response_text,
            self._latest_knowledge_answer_diagnostics,
        )

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
        """Restore the minimal StepFun runtime subset required to continue training."""
        await super()._restore_session_state(state)

        runtime_state = (
            state.runtime_state if isinstance(state.runtime_state, dict) else {}
        )
        reconnect_state_raw = runtime_state.get("reconnect_state")
        reconnect_state: dict[str, Any] = (
            copy.deepcopy(reconnect_state_raw)
            if isinstance(reconnect_state_raw, dict)
            else {}
        )
        self._connection_epoch = self._normalize_connection_epoch(
            reconnect_state.get("connection_epoch")
        )
        self._connection_epoch = max(1, self._connection_epoch + 1)
        self._last_disconnect_reason = (
            str(reconnect_state.get("last_disconnect_reason") or "").strip() or None
        )
        self._last_runtime_error = self._copy_runtime_error(
            reconnect_state.get("last_error")
        )
        await self._cancel_pending_response_after_commit()
        self.session_id = state.session_id or self.session_id
        self.user_id = state.user_id or self.user_id
        self.turn_count = state.turn_count
        self.session_status = state.session_status or self.session_status
        self.ai_state = state.ai_state or "idle"
        self.current_request_id = int(runtime_state.get("current_request_id") or 0)
        self._last_emitted_stage = runtime_state.get("last_emitted_stage")
        latest_score_snapshot = runtime_state.get("latest_score_snapshot")
        self._latest_score_snapshot = normalize_score_snapshot(latest_score_snapshot)
        latest_live_session_summary = runtime_state.get("latest_live_session_summary")
        self._latest_live_session_summary = coerce_live_session_conclusion_summary(
            latest_live_session_summary
        )
        latest_claim_truth = runtime_state.get("latest_claim_truth")
        self._latest_claim_truth = (
            copy.deepcopy(latest_claim_truth)
            if isinstance(latest_claim_truth, dict)
            else None
        )
        self._latest_action_card = None
        self._objection_ledger = normalize_objection_ledger(
            runtime_state.get("objection_ledger")
        )
        self._feedback_pacing_state = RealtimeFeedbackPacingState.from_dict(
            runtime_state.get("feedback_pacing_state")
        )
        restored_coach_health = runtime_state.get("coach_health")
        if isinstance(restored_coach_health, dict):
            restored_status = str(restored_coach_health.get("status") or "healthy")
            if restored_status not in {"healthy", "degraded", "resumed"}:
                restored_status = "healthy"
            restored_reason = restored_coach_health.get("reason")
            self._coach_health = restored_status
            self._coach_health_reason = (
                str(restored_reason).strip()
                if isinstance(restored_reason, str) and restored_reason.strip()
                else None
            )
        else:
            self._coach_health = "healthy"
            self._coach_health_reason = None

        self._reset_turn_runtime_state()
        self._pending_response_after_commit = False
        self._grounding_preparation_in_progress = False
        self._last_final_transcript_text = ""
        self._last_final_transcript_turn = None
        self._last_final_transcript_at = 0.0

        logger.info(
            "Restored StepFun reconnect snapshot",
            session_id=state.session_id,
            turn_count=self.turn_count,
            session_status=self.session_status,
            ai_state=self.ai_state,
            restored_runtime_keys=sorted(runtime_state.keys()),
        )
        await self._send_reconnection_success(self._create_state_snapshot())

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
