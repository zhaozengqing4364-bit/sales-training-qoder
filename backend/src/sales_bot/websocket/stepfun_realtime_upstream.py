"""Upstream mixin for the StepFun realtime websocket handler."""

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
from curriculum_practice.services.roleplay_contracts import (
    ROLEPLAY_COMPLIANCE_METRICS_KEY,
    ROLEPLAY_DISCLOSURE_STATE_KEY,
    build_roleplay_turn_context,
    initial_roleplay_disclosure_state,
    normalize_roleplay_disclosure_state,
    resolve_roleplay_disclosure_state,
    visible_case_payload,
    _as_dict as _roleplay_as_dict,
)
from sales_bot.services.roleplay_compliance_checker import (
    check_realtime_roleplay_output,
)
from prompt_templates.compiled_contract import (
    build_turn_instruction_hash,
    compose_turn_instruction_text,
)
from sales_bot.services.voice_instruction_compiler import (
    VoiceInstructionCompiler,
    build_instruction_contract_hash,
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
from sales_bot.websocket.components.stepfun_voice_errors import is_voice_unavailable_error
from sales_bot.websocket.realtime_feedback_arbiter import (
    RealtimeFeedbackArbiter,
    RealtimeFeedbackPacingState,
)
from sales_bot.websocket.grounding_decision_pipeline import GroundingDecisionContext
from sales_bot.websocket.phase4_local_provider import should_use_phase4_local_provider
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
from sales_bot.websocket.stepfun_tool_execution import ToolExecutionContext
from training_runtime.stepfun_transport import StepFunSendStatus
from training_runtime.realtime import (
    FrozenJsonMapping,
    JsonValue,
    ProviderCommand,
    ProviderCommandKind,
    ProviderErrorReason,
    ProviderEvent,
    ProviderEventKind,
    RealtimeProviderError,
)

logger = get_logger(__name__)
ROLEPLAY_INSTRUCTION_HASH_METRICS_KEY = "roleplay_instruction_hash"
ROLEPLAY_INSTRUCTION_HASH_SAMPLE_LIMIT = 10

_PROVIDER_RESPONSE_AUTHORITY_EVENT_KINDS = frozenset(
    {
        ProviderEventKind.RESPONSE_CREATED,
        ProviderEventKind.RESPONSE_TEXT_DELTA,
        ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA,
        ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
        ProviderEventKind.RESPONSE_AUDIO_DELTA,
        ProviderEventKind.THINKING_DELTA,
        ProviderEventKind.THINKING_DONE,
        ProviderEventKind.FUNCTION_ARGUMENTS_DELTA,
        ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
        ProviderEventKind.RESPONSE_DONE,
    }
)


def _handler_symbol(name: str, fallback: Any) -> Any:
    """Read monkeypatch-compatible symbols from the public handler module."""
    module = sys.modules.get("sales_bot.websocket.stepfun_realtime_handler")
    return getattr(module, name, fallback) if module is not None else fallback


class StepFunRealtimeUpstreamMixin(StepFunRealtimeStateBase):
    @staticmethod
    def _provider_command_from_legacy_payload(
        payload: dict[str, Any],
    ) -> ProviderCommand:
        return _provider_command_from_legacy_payload(payload)

    async def _after_input_audio_committed_before_response(self) -> None:
        """Allow scenario adapters to finalize locally committed audio metadata."""

    async def _commit_and_respond(self) -> None:
        """Commit buffered user audio and trigger model response."""
        if not self._has_uncommitted_audio:
            logger.debug(
                "Ignore duplicate audio commit without new audio",
                session_id=self.session_id,
            )
            return
        log_latency_debug = getattr(self, "_log_latency_debug", None)
        if callable(log_latency_debug):
            log_latency_debug(
                "audio_commit_requested",
                binary_frame_count=getattr(
                    self,
                    "_received_binary_audio_frame_count",
                    0,
                ),
                **self._summarize_pending_input_audio_quality(),
            )
        await self._send_upstream({"type": "input_audio_buffer.commit"})
        audio_flow = getattr(self, "_audio_flow", None)
        if audio_flow is not None:
            audio_flow.commit_input_audio()
        self._has_uncommitted_audio = False
        reset_input_audio_quality = getattr(self, "_reset_input_audio_quality", None)
        if callable(reset_input_audio_quality):
            reset_input_audio_quality()
        await self._after_input_audio_committed_before_response()
        await self._schedule_response_after_commit()

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
        if should_use_phase4_local_provider():
            self._log_grounding_debug(
                "prefetch_skipped",
                reason="phase4_local_provider",
            )
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
            decision_coro = self._grounding_pipeline.evaluate(
                query=normalized_query,
                context=GroundingDecisionContext(
                    effective_policy=self._effective_policy,
                    record_metric=self._record_knowledge_runtime_metric,
                ),
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
                decision_status = "blocked_search_timeout"
                blocked = True
                self._pending_blocked_response_text = (
                    "当前内部知识检索超时，暂时无法基于内部资料回答这个问题。"
                    "请稍后重试，或补充更具体的关键词、版本信息或业务场景。"
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
        retrieval_top_k = max(1, min(8, top_k))
        retrieval: dict[str, Any] | None = None
        prefetch_timeout_seconds = self._grounding_prefetch_timeout_seconds
        if prefetch_timeout_seconds > 0:
            try:
                retrieval = await asyncio.wait_for(
                    self._grounding_pipeline.retrieve(
                        normalized_query,
                        top_k=retrieval_top_k,
                    ),
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
                if has_bound_knowledge_base:
                    self._pending_blocked_response_text = (
                        "当前内部知识检索超时，暂时无法基于内部资料回答这个问题。"
                        "请稍后重试，或补充更具体的关键词、版本信息或业务场景。"
                    )
                    self._pending_grounding_context = ""
                return
        else:
            retrieval = await self._grounding_pipeline.retrieve(
                normalized_query,
                top_k=retrieval_top_k,
            )

        if not isinstance(retrieval, dict):
            self._log_grounding_debug(
                "prefetch_skipped",
                reason="invalid_retrieval_payload",
                query_length=len(normalized_query),
            )
            if has_bound_knowledge_base:
                self._pending_blocked_response_text = (
                    "当前内部知识检索结果不可用，暂时无法基于内部资料回答这个问题。"
                    "请稍后重试，或补充更具体的关键词、版本信息或业务场景。"
                )
                self._pending_grounding_context = ""
            return
        grounding_decision = self._grounding_pipeline.evaluate_retrieval(
            normalized_query,
            GroundingDecisionContext(effective_policy=self._effective_policy),
            retrieval,
        )
        self._latest_knowledge_answer_diagnostics = (
            copy.deepcopy(grounding_decision.diagnostics)
            if isinstance(grounding_decision.diagnostics, dict)
            else None
        )
        self._pending_grounding_context = grounding_decision.grounding_context
        self._pending_blocked_response_text = grounding_decision.user_message
        if not grounding_decision.allow_generation:
            self._log_grounding_debug(
                "prefetch_grounding_blocked",
                query_length=len(normalized_query),
                status=grounding_decision.status,
                answerability_mode=grounding_decision.answerability_mode,
                answerability=str(
                    (grounding_decision.diagnostics or {}).get("answerability") or ""
                ),
                source_status=str(
                    (grounding_decision.diagnostics or {}).get("source_status") or ""
                ),
            )
            return
        self._log_grounding_debug(
            "prefetch_applied",
            query_length=len(normalized_query),
            snippet_count=grounding_decision.result_count,
            answerability_mode=grounding_decision.answerability_mode,
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

                if self._is_kb_lock_required_for_current_policy():
                    await self._cancel_pending_response_after_commit()
                    self._allow_late_transcription_response = True
                    await self._record_kb_lock_decision(
                        status="transcription_timeout_suppressed",
                        blocked=False,
                    )
                    await self._send_status("listening")
                    return

                self._log_grounding_debug("timeout_create_response_without_transcript")
                await self._create_response_from_pending_commit(
                    expected_generation=expected_generation
                )
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

        turn_coordinator = getattr(self, "_turn_coordinator", None)
        interruption = (
            turn_coordinator.resolve_interruption()
            if turn_coordinator is not None
            else None
        )
        if (
            turn_coordinator is not None
            and interruption is not None
            and interruption.should_interrupt
        ):
            logger.info(
                "Realtime turn coordinator resolved interruption before response.create",
                session_id=self.session_id,
                turn_id=interruption.turn_id,
                reason=interruption.reason,
            )
            await self._clear_upstream_generation()
            turn_coordinator.reset()

        self.current_request_id += 1
        if count_turn:
            self.turn_count += 1
        self._active_response = RealtimeResponseState(
            request_id=self.current_request_id,
            stream_id=str(uuid.uuid4()),
        )
        if turn_coordinator is not None:
            turn_start = turn_coordinator.start_turn(str(self.current_request_id))
            if not turn_start.started:
                logger.warning(
                    "Realtime turn coordinator rejected response start",
                    session_id=self.session_id,
                    request_id=self.current_request_id,
                    reason=turn_start.reason,
                )
            turn_coordinator.on_model_response_start()

        response_payload: dict[str, Any] = {
            "type": "response.create",
            "response": {"modalities": ["audio", "text"]},
        }
        grounding_context = self._pending_grounding_context.strip()
        roleplay_soft_correction_hint = str(
            getattr(self, "_roleplay_repair_instruction", "") or ""
        ).strip()
        roleplay_turn_context = self._roleplay_turn_instruction_context()
        roleplay_turn_instruction = self._format_roleplay_turn_instruction(
            roleplay_turn_context
        )
        try:
            profile = self._active_voice_runtime_profile()
        except AttributeError:
            profile = None
        if profile is not None:
            base_instructions = profile.instructions
            instruction_contract_hash = profile.instruction_contract_hash
            role_anchor_text = profile.role_anchor_text
            turn_instructions = profile.compile_instructions(
                grounding_context=grounding_context,
                roleplay_turn_instruction=roleplay_turn_instruction,
            )
        else:
            effective_policy = getattr(self, "_effective_policy", None)
            role_anchor_text = ""
            if isinstance(effective_policy, dict):
                role_anchor_text = str(
                    effective_policy.get("role_anchor_text") or ""
                ).strip()
            base_instructions = self._stepfun_instructions
            instruction_contract_hash = self._instruction_contract_hash
            turn_instructions = compose_turn_instruction_text(
                base_instructions=base_instructions,
                grounding_context=grounding_context,
                roleplay_turn_instruction=roleplay_turn_instruction,
                role_anchor_text=role_anchor_text,
            )
        if roleplay_soft_correction_hint:
            turn_instructions = (
                f"{turn_instructions}\n\n【下一轮角色合同软纠偏提示】\n"
                f"{roleplay_soft_correction_hint}"
                if turn_instructions
                else f"【下一轮角色合同软纠偏提示】\n"
                f"{roleplay_soft_correction_hint}"
            )
        turn_instruction_hash = build_turn_instruction_hash(turn_instructions)
        if turn_instructions:
            response_payload["response"]["instructions"] = turn_instructions
        self._pending_grounding_context = ""
        self._roleplay_repair_instruction = ""
        grounding_debug_payload = {
            "request_id": self.current_request_id,
            "has_grounding_context": bool(grounding_context),
            "grounding_context_length": len(grounding_context),
            "has_base_instructions": bool(base_instructions.strip()),
            "has_role_anchor": bool(role_anchor_text),
            "role_anchor_length": len(role_anchor_text),
            "final_instruction_length": len(turn_instructions),
            "instruction_contract_hash": instruction_contract_hash,
            "turn_instruction_hash": turn_instruction_hash,
        }
        if roleplay_turn_context.get("disclosure_state_status") == "ready":
            grounding_debug_payload["roleplay_visible_keys_count"] = len(
                roleplay_turn_context.get("visible_keys", [])
            )
        if roleplay_soft_correction_hint:
            grounding_debug_payload["roleplay_soft_correction_hint"] = True
        await self._record_roleplay_instruction_hash_metric(grounding_debug_payload)
        self._log_grounding_debug("response_create", **grounding_debug_payload)

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
            if (
                self._fuzzy_detection_enabled
                and self._fuzzy_detection_capability is not None
            ):
                await self._fuzzy_detection_capability.on_session_end(
                    self._feedback_context
                )
            if (
                self._realtime_scoring_enabled
                and self._realtime_scoring_capability is not None
            ):
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
            backoff_seconds = _handler_symbol(
                "compute_jitter_backoff_seconds",
                compute_jitter_backoff_seconds,
            )(
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

    def _is_upstream_idle_timeout_error(self, event: dict[str, Any]) -> bool:
        reason = extract_error_message(event).strip()
        return self._is_upstream_idle_timeout_disconnect(
            close_code=None,
            close_reason=reason,
            ws_lifetime_ms=self._compute_upstream_ws_lifetime_ms(),
        )

    async def _recover_upstream_after_idle_timeout_error(self, event: dict[str, Any]) -> bool:
        if not self._is_upstream_idle_timeout_error(event):
            return False
        recovered = await self._refresh_upstream_for_next_input(
            reason="upstream_idle_timeout_error",
        )
        if recovered:
            logger.info(
                "StepFun upstream recovered from idle timeout error",
                session_id=self.session_id,
                error_message=extract_error_message(event),
            )
        return bool(recovered)

    async def sync_lifecycle_transition(
        self, transition: SessionLifecycleTransition
    ) -> None:
        """Mirror REST lifecycle transitions into the live StepFun runtime."""
        await super().sync_lifecycle_transition(transition)
        self.session_scenario_type = transition.scenario_type or self.scenario

        if transition.action in {"pause", "end"}:
            await self._cancel_pending_response_after_commit()
            self._reset_turn_runtime_state()
            if self.upstream_ws is not None:
                try:
                    await self._clear_upstream_generation()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to sync StepFun upstream after REST lifecycle change",
                        session_id=self.session_id,
                        action=transition.action,
                        error=str(exc),
                    )

    async def _receive_upstream_events(self) -> None:
        """Receive events from StepFun and map them to frontend messages."""
        while self.running:
            if self.upstream_ws is None:
                await asyncio.sleep(0.05)
                continue
            try:
                if self._using_provider_port():
                    provider = self._realtime_provider
                    if provider is None:
                        raise RuntimeError("realtime_provider_not_constructed")
                    provider_event = await provider.receive(
                        connection_epoch=self._connection_epoch
                    )
                    self._mark_upstream_activity()
                    await self._handle_provider_event(provider_event)
                    continue
                raw = await self.upstream_ws.recv()
                self._mark_upstream_activity()
                event = json.loads(raw)
                await self._handle_upstream_event(event)
            except asyncio.CancelledError:
                raise
            except RealtimeProviderError as error:
                reason_text = error.reason.value
                ws_lifetime_ms = self._compute_upstream_ws_lifetime_ms()
                await self._record_upstream_disconnect_diagnostics(
                    close_code=None,
                    close_reason=reason_text,
                )
                recovered = await self._recover_upstream_after_disconnect(
                    close_code=None,
                    close_reason=reason_text,
                    ws_lifetime_ms=ws_lifetime_ms,
                )
                logger.info(
                    "realtime_provider_receive_closed",
                    session_id=self.session_id,
                    error_category=error.category.value,
                    error_reason=error.reason.value,
                    ws_lifetime_ms=ws_lifetime_ms,
                    recovered=recovered,
                )
                if recovered:
                    continue
                await self._send_error(
                    "[STEPFUN_UPSTREAM_CLOSED]",
                    _provider_error_delivery_message(error.reason),
                )
                self.running = False
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

    async def _handle_provider_event(self, event: ProviderEvent) -> None:
        """Project one canonical Provider event into the legacy delivery adapter."""

        if not self._provider_event_has_active_authority(event):
            logger.warning(
                "stale_realtime_provider_event_ignored",
                session_id=self.session_id,
                current_connection_epoch=self._connection_epoch,
                event_kind=event.kind.value,
            )
            return
        await self._handle_upstream_event(_legacy_event_from_provider_event(event))

    def _provider_event_has_active_authority(self, event: ProviderEvent) -> bool:
        """Validate canonical event IDs before any persistence/audio/tool side effect."""
        if event.connection_epoch != self._connection_epoch:
            return False

        is_function_item = (
            event.kind is ProviderEventKind.CONVERSATION_ITEM
            and event.call_id is not None
            and event.data.get("item_type") == "function_call"
        )
        if (
            event.kind not in _PROVIDER_RESPONSE_AUTHORITY_EVENT_KINDS
            and not is_function_item
        ):
            return True

        active_response = self._active_response
        if active_response is None:
            return False
        if (
            event.request_id is not None
            and event.request_id != active_response.request_id
        ):
            return False
        if (
            event.response_id is not None
            and active_response.response_id is not None
            and event.response_id != active_response.response_id
        ):
            return False
        if event.stream_id is not None and event.stream_id != active_response.stream_id:
            return False

        if event.kind in {
            ProviderEventKind.FUNCTION_ARGUMENTS_DELTA,
            ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
        }:
            known_calls = self._function_call_states
            if known_calls and event.call_id not in known_calls:
                return False
        if event.kind is ProviderEventKind.RESPONSE_DONE:
            function_outputs = event.data.get("function_outputs")
            known_calls = self._function_call_states
            if known_calls and isinstance(function_outputs, tuple):
                for output in function_outputs:
                    if (
                        isinstance(output, FrozenJsonMapping)
                        and output.get("call_id") not in known_calls
                    ):
                        return False
        return True

    async def _handle_upstream_event(self, event: dict[str, Any]) -> None:
        """Map selected StepFun events to existing frontend contract."""
        event_type = str(event.get("type", ""))
        self._last_upstream_event_type = event_type
        await self._handle_emotion_event(event)
        await self._handle_thinking_event(event)
        route = classify_upstream_event(event_type)
        self._log_latency_debug(
            "upstream_event_received",
            event_type=event_type,
            route=str(route),
        )

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
        if route in {
            UpstreamEventRoute.SPEECH_STARTED,
            UpstreamEventRoute.SPEECH_STOPPED,
        }:
            if route == UpstreamEventRoute.SPEECH_STARTED:
                self._turn_coordinator.on_user_audio_start()
            else:
                self._turn_coordinator.on_user_audio_stop()
            return
        if event_type == "input_audio_buffer.committed":
            self._turn_coordinator.on_user_audio_stop()
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
        """Track function-call state and user-item transcript hints from upstream."""
        function_call = extract_function_call_from_item_created(event)
        if not function_call:
            transcript = self._extract_final_transcript_text(event)
            if transcript:
                self._latest_input_transcript_delta = transcript
                self._log_latency_debug(
                    "conversation_item_created_transcript_cached",
                    transcript_length=len(transcript),
                    item_role=self._extract_conversation_item_role(event),
                )
            return

        call_id, name = function_call
        self._function_call_states[call_id] = FunctionCallState(
            call_id=call_id,
            name=name,
        )

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
            await self._handle_curriculum_stage_turn(turn_number=turn_number)
            await self._update_roleplay_disclosure_state(
                learner_message=normalized_transcript,
                turn_number=turn_number,
                sales_stage=sales_stage,
            )
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

    async def _handle_upstream_response_audio_delta(self, event: dict) -> None:
        """Forward realtime audio chunk to frontend."""
        delta = event.get("delta", "")
        if self._active_response and delta:
            if self._active_response.roleplay_suppressed:
                return
            if self._active_response.question_limit_enforced:
                return
            await self._forward_audio_delta_chunk(delta)

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
        turn_coordinator = getattr(self, "_turn_coordinator", None)
        if turn_coordinator is not None:
            turn_coordinator.on_model_response_done()
            turn_coordinator.end_turn(str(response_state.request_id))

        response_text = self._extract_response_text(response_done_event)
        if not response_text:
            response_text = "".join(response_state.text_parts).strip()
        response_text = self._grounding_pipeline.apply_output_guard(
            response_text,
            self._latest_knowledge_answer_diagnostics
            if isinstance(self._latest_knowledge_answer_diagnostics, dict)
            else None,
        )
        response_text = await self._apply_roleplay_output_guard(
            response_text,
            existing_decision=response_state.roleplay_violation_decision,
        )

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

        if response_state.roleplay_suppressed:
            if not response_state.roleplay_repair_sent:
                await self._send_roleplay_repair_audio(response_state)
            await self._send_status("listening")
            return True

        # Streaming path: already sent audio chunks, now send final marker with text.
        if response_state.chunk_index > 0:
            self._audio_flow.drain_output_audio()
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

    async def _apply_roleplay_output_guard(
        self,
        response_text: str,
        *,
        existing_decision: dict[str, Any] | None = None,
    ) -> str:
        if not response_text:
            return response_text
        contract = self._roleplay_contract()
        current_stage = self._current_sales_stage_code()
        decision = check_realtime_roleplay_output(
            roleplay_contract=contract if isinstance(contract, dict) else None,
            text=response_text,
            runtime_state=self._roleplay_checker_runtime_state(contract),
            current_sales_stage=current_stage,
        )
        if not isinstance(decision, dict) or decision.get("severity") in (None, "none"):
            return response_text
        duplicate_decision = self._roleplay_decisions_match(
            existing_decision,
            decision,
        )
        if not duplicate_decision:
            self._roleplay_repair_instruction = (
                self._build_roleplay_soft_correction_hint(decision)
            )
            await self._record_roleplay_compliance_decision(
                decision,
                response_id=None,
                action_override="observe_only",
            )
        self._log_grounding_debug(
            "roleplay_output_guard_decision",
            violation_code=decision.get("violation_code"),
            severity=decision.get("severity"),
            action=decision.get("action"),
            matched_pattern=decision.get("matched_pattern"),
            observe_only=True,
        )
        return response_text

    async def _apply_roleplay_stream_guard(self) -> None:
        response_state = self._active_response
        if response_state is None or response_state.roleplay_suppressed:
            return
        text = "".join(response_state.text_parts).strip()
        if not text:
            return
        contract = self._roleplay_contract()
        current_stage = self._current_sales_stage_code()
        decision = check_realtime_roleplay_output(
            roleplay_contract=contract if isinstance(contract, dict) else None,
            text=text,
            runtime_state=self._roleplay_checker_runtime_state(contract),
            current_sales_stage=current_stage,
        )
        if (
            not isinstance(decision, dict)
            or decision.get("severity") != "blocking"
        ):
            return
        if self._roleplay_decisions_match(
            response_state.roleplay_violation_decision,
            decision,
        ):
            return
        response_state.roleplay_violation_decision = decision
        self._roleplay_repair_instruction = self._build_roleplay_soft_correction_hint(
            decision
        )
        await self._record_roleplay_compliance_decision(
            decision,
            response_id=response_state.response_id,
            action_override="observe_only",
            count_violation=True,
        )
        self._log_grounding_debug(
            "roleplay_stream_guard_observed_only",
            request_id=response_state.request_id,
            response_id=response_state.response_id,
            violation_code=decision.get("violation_code"),
            matched_pattern=decision.get("matched_pattern"),
            audio_forwarded=response_state.roleplay_audio_forwarded,
        )

    async def _record_roleplay_compliance_decision(
        self,
        decision: dict[str, Any],
        *,
        response_id: str | None,
        action_override: str | None,
        count_violation: bool = True,
    ) -> None:
        runtime_metrics = self._effective_policy.get("runtime_metrics")
        if not isinstance(runtime_metrics, dict):
            runtime_metrics = {}
        roleplay_metrics = runtime_metrics.get(ROLEPLAY_COMPLIANCE_METRICS_KEY)
        if not isinstance(roleplay_metrics, dict):
            roleplay_metrics = {
                "violation_count": 0,
                "blocking_violation_count": 0,
                "regenerate_count": 0,
                "cancel_stream_count": 0,
            }
        action = action_override or str(decision.get("action") or "")
        if count_violation:
            roleplay_metrics["violation_count"] = int(
                roleplay_metrics.get("violation_count") or 0
            ) + 1
            if decision.get("severity") == "blocking":
                roleplay_metrics["blocking_violation_count"] = int(
                    roleplay_metrics.get("blocking_violation_count") or 0
                ) + 1
        if action == "regenerate_once":
            roleplay_metrics["regenerate_count"] = int(
                roleplay_metrics.get("regenerate_count") or 0
            ) + 1
        if action == "cancel_stream":
            roleplay_metrics["cancel_stream_count"] = int(
                roleplay_metrics.get("cancel_stream_count") or 0
            ) + 1
        if (
            action != "observe_only"
            and decision.get("violation_code") == "ROLEPLAY_HIDDEN_INFORMATION_LEAK"
        ):
            roleplay_metrics["hidden_leak_prevented_count"] = int(
                roleplay_metrics.get("hidden_leak_prevented_count") or 0
            ) + 1
        roleplay_metrics["last_decision"] = decision
        roleplay_metrics["last_action"] = action or decision.get("action")
        roleplay_metrics["last_action_at"] = datetime.now(UTC).isoformat()
        roleplay_metrics["response_id"] = response_id
        timeline = roleplay_metrics.get("timeline")
        if not isinstance(timeline, list):
            timeline = []
        timeline.append(
            {
                "turn_number": max(1, int(self.turn_count or 0)),
                "response_id": response_id,
                "action": action or decision.get("action"),
                "decision": decision,
                "sales_stage": self._current_sales_stage_code(),
                "visible_keys": self._roleplay_visible_keys(self._roleplay_contract()),
                "disclosed_keys": self._roleplay_disclosed_keys(),
                "created_at": roleplay_metrics["last_action_at"],
                "trace_id": get_trace_id(),
            }
        )
        roleplay_metrics["timeline"] = timeline[-100:]
        runtime_metrics[ROLEPLAY_COMPLIANCE_METRICS_KEY] = roleplay_metrics
        self._effective_policy["runtime_metrics"] = runtime_metrics
        try:
            await self._persist_runtime_metrics_to_session()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to persist roleplay compliance metrics: {exc}")

    async def _send_roleplay_repair_audio(
        self,
        response_state: RealtimeResponseState,
    ) -> None:
        if response_state.roleplay_repair_sent:
            return
        response_state.roleplay_repair_sent = True
        decision = response_state.roleplay_violation_decision or {}
        contract = self._roleplay_contract()
        repair_text = self._roleplay_repair_message(contract, decision)
        await self.manager.send_json(
            self.websocket,
            {
                "type": "tts_audio",
                "timestamp": datetime.now(UTC).isoformat(),
                "stream_id": response_state.stream_id,
                "request_id": response_state.request_id,
                "data": {
                    "text": repair_text,
                    "audio": "",
                    "audio_format": "",
                    "duration_ms": len(repair_text) * 100,
                    "fallback": "browser_tts",
                    "roleplay_guard": True,
                    "playback_rate": self._stepfun_playback_rate,
                },
            },
        )

    @staticmethod
    def _build_roleplay_soft_correction_hint(decision: dict[str, Any]) -> str:
        code = str(decision.get("violation_code") or "unknown")
        return (
            f"上一轮角色口径疑似偏离（{code}）。下一轮自然纠正：只使用当前可见信息，"
            "保持首次正式沟通口径，不解释系统规则。"
        )

    @staticmethod
    def _roleplay_decisions_match(
        existing_decision: dict[str, Any] | None,
        decision: dict[str, Any],
    ) -> bool:
        if not isinstance(existing_decision, dict):
            return False
        return (
            str(existing_decision.get("severity") or "")
            == str(decision.get("severity") or "")
            and str(existing_decision.get("violation_code") or "")
            == str(decision.get("violation_code") or "")
            and str(existing_decision.get("matched_pattern") or "")
            == str(decision.get("matched_pattern") or "")
        )

    def _roleplay_contract(self) -> dict[str, Any] | None:
        contract = None
        curriculum_snapshot = getattr(self, "_curriculum_snapshot", None)
        if isinstance(curriculum_snapshot, dict):
            contract = curriculum_snapshot.get("roleplay_contract")
        if not isinstance(contract, dict):
            effective_policy = getattr(self, "_effective_policy", {})
            contract = (
                effective_policy.get("roleplay_contract")
                if isinstance(effective_policy, dict)
                else None
            )
        return contract if isinstance(contract, dict) else None

    def _current_sales_stage_code(self) -> str | None:
        latest_stage_data = getattr(self, "_latest_stage_data", None)
        if isinstance(latest_stage_data, dict):
            stage = latest_stage_data.get("current_stage")
            return str(stage) if stage else None
        return None

    def _roleplay_checker_runtime_state(
        self,
        contract: object,
    ) -> dict[str, Any]:
        return {
            "current_sales_stage": self._current_sales_stage_code(),
            "visible_keys": self._roleplay_visible_keys(contract),
            "disclosed_keys": self._roleplay_disclosed_keys(),
        }

    def _roleplay_disclosed_keys(self) -> list[str]:
        disclosure_state = getattr(self, "_roleplay_disclosure_state", {})
        if not isinstance(disclosure_state, dict):
            return []
        raw_keys = disclosure_state.get("disclosed_keys")
        if not isinstance(raw_keys, list):
            return []
        return [str(item) for item in raw_keys if str(item).strip()]

    async def _update_roleplay_disclosure_state(
        self,
        *,
        learner_message: str,
        turn_number: int,
        sales_stage: Any,
    ) -> None:
        contract = self._roleplay_contract()
        current_state = getattr(self, "_roleplay_disclosure_state", {})
        previous = (
            current_state
            if isinstance(current_state, dict)
            else initial_roleplay_disclosure_state(contract)
        )
        next_state = resolve_roleplay_disclosure_state(
            contract=contract,
            previous_state=previous,
            learner_message=learner_message,
            current_sales_stage=str(sales_stage or self._current_sales_stage_code() or ""),
            turn_number=turn_number,
            evidence={"trace_id": get_trace_id()},
        )
        if next_state == previous:
            return
        self._roleplay_disclosure_state = next_state
        await self._persist_roleplay_disclosure_state()

    async def _persist_roleplay_disclosure_state(self) -> None:
        disclosure_state = getattr(self, "_roleplay_disclosure_state", None)
        if not self.session_id or not isinstance(disclosure_state, dict):
            return
        async with self._db_session_factory() as db:
            result = await db.execute(
                select(PracticeSession).where(PracticeSession.session_id == self.session_id)
            )
            session = result.scalar_one_or_none()
            if session is None:
                return
            runtime_state = (
                dict(session.runtime_state)
                if isinstance(session.runtime_state, dict)
                else {}
            )
            runtime_state[ROLEPLAY_DISCLOSURE_STATE_KEY] = disclosure_state
            session.runtime_state = runtime_state
            await db.commit()

    def _roleplay_turn_instruction_context(self) -> dict[str, Any]:
        contract = self._roleplay_contract()
        state = normalize_roleplay_disclosure_state(
            contract,
            getattr(self, "_roleplay_disclosure_state", {}),
        )
        self._roleplay_disclosure_state = state
        return build_roleplay_turn_context(
            contract=contract,
            disclosure_state=state,
            visible_payload=_roleplay_as_dict(state.get("disclosed_payload")),
            current_sales_stage=self._current_sales_stage_code(),
        )

    @staticmethod
    def _format_roleplay_turn_instruction(context: dict[str, Any]) -> str:
        if not isinstance(context, dict):
            return ""
        if context.get("disclosure_state_status") != "ready":
            return ""
        visible_keys = context.get("visible_keys")
        disclosed_keys = context.get("disclosed_keys")
        visible_payload = context.get("visible_payload")
        lines = [
            "【当前轮角色合同可见范围】",
            f"- 当前销售阶段：{context.get('current_sales_stage') or 'unknown'}",
            "- 当前可见字段："
            + ("、".join(str(item) for item in visible_keys) if isinstance(visible_keys, list) and visible_keys else "无"),
            "- 已披露字段："
            + ("、".join(str(item) for item in disclosed_keys) if isinstance(disclosed_keys, list) and disclosed_keys else "无"),
        ]
        if isinstance(visible_payload, dict) and visible_payload:
            payload_text = "；".join(
                f"{key}={value}"
                for key, value in visible_payload.items()
                if str(value).strip()
            )
            if payload_text:
                lines.append(f"- 本轮新增可见信息：{payload_text}")
        lines.append("- 未列入当前可见字段的信息不得主动使用。")
        return "\n".join(lines)

    @staticmethod
    def _roleplay_visible_keys(contract: object) -> list[str]:
        if not isinstance(contract, dict):
            return []
        scope = contract.get("visible_information_scope")
        if not isinstance(scope, dict):
            return []
        raw_keys = scope.get("initial_visible_keys")
        if not isinstance(raw_keys, list):
            return []
        return [str(item) for item in raw_keys if str(item).strip()]

    @staticmethod
    def _roleplay_repair_message(
        contract: object,
        decision: dict[str, Any],
    ) -> str:
        strategy = ""
        if isinstance(contract, dict):
            strategy = str(contract.get("conflict_response_strategy") or "")
        if decision.get("violation_code") == "ROLEPLAY_HISTORY_CONTRADICTION":
            if strategy == "customer_confused_correction":
                return "我有点困惑，我们今天应该是第一次正式沟通。你可以先介绍一下这次想了解什么。"
            return "我不确定你说的上次沟通指什么。我们先按这次正式沟通来聊。"
        if decision.get("violation_code") == "ROLEPLAY_HIDDEN_INFORMATION_LEAK":
            return "这个信息我现在还不方便展开。你可以先说明为什么需要了解这部分。"
        return "这个话题现在还不适合展开。我们先回到当前沟通目标。"

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
        tool_call = {"id": call_id, "name": function_name, "arguments": arguments_obj}
        routing_decision = self._tool_execution.decide_tool_routing(
            tool_call,
            turn_context={
                "session_id": self.session_id,
                "turn_id": self.turn_count,
                "call_id": call_id,
            },
        )
        if not routing_decision.should_execute:
            self._function_call_states.pop(call_id, None)
            return False
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
            grounding_decision = self._grounding_pipeline.evaluate_retrieval(
                str(arguments_obj.get("query") or ""),
                GroundingDecisionContext(effective_policy=self._effective_policy),
                output_payload,
            )
            self._latest_knowledge_answer_diagnostics = (
                copy.deepcopy(grounding_decision.diagnostics)
                if isinstance(grounding_decision.diagnostics, dict)
                else None
            )
            if grounding_decision.allow_generation:
                self._pending_blocked_response_text = ""
                if grounding_decision.grounding_context:
                    self._pending_grounding_context = grounding_decision.grounding_context
            else:
                self._pending_grounding_context = ""
                self._pending_blocked_response_text = grounding_decision.user_message
                self._log_grounding_debug(
                    "function_call_grounding_blocked",
                    call_id=call_id,
                    query_length=len(str(arguments_obj.get("query") or "").strip()),
                    status=grounding_decision.status,
                    answerability_mode=grounding_decision.answerability_mode,
                )
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
        self._tool_execution.mark_tool_call_completed(call_id)
        self._function_call_states.pop(call_id, None)

        await self._send_upstream(
            self._tool_execution.build_tool_response(
                tool_call_id=call_id,
                result=output_payload,
            )
        )

        if trigger_followup_response:
            if self._active_response is not None:
                self._pending_tool_followup_response = True
            else:
                await self._create_response()
        return True

    def _build_internal_retrieval_cache_key(self, arguments_obj: dict[str, Any]) -> str:
        cache_key: str = self._tool_execution.build_internal_retrieval_cache_key(
            arguments_obj
        )
        return cache_key

    async def _tool_search_internal_knowledge(
        self, arguments_obj: dict[str, Any]
    ) -> dict[str, Any]:
        """Search internal knowledge bases bound to current policy."""
        cache_key = self._build_internal_retrieval_cache_key(arguments_obj)
        cache_hit = False
        output: dict[str, Any] = {}
        if cache_key and self._internal_retrieval_cache_ttl_seconds > 0:
            cached = self._tool_execution.get_cached_result(cache_key)
            if cached is not None:
                output = cached
                cache_hit = True

        if not cache_hit:
            output = {}
            try:
                output = await self._tool_execution.execute_tool(
                    {"name": "search_internal_knowledge", "arguments": arguments_obj},
                    context=ToolExecutionContext(
                        session_id=cast(str, self.session_id),
                        effective_policy=self._effective_policy,
                        session_factory=self._db_session_factory,
                        knowledge_service_factory=self._knowledge_service_factory,
                        record_metric=self._record_knowledge_runtime_metric,
                    ),
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._tool_execution.record_execution_error()
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
                self._tool_execution.cache_result(
                    cache_key,
                    output,
                    ttl_seconds=self._internal_retrieval_cache_ttl_seconds,
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
            apply_metric = _handler_symbol(
                "apply_knowledge_runtime_metric",
                apply_knowledge_runtime_metric,
            )
            apply_metric(
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
            _handler_symbol("logger", logger).warning(
                f"Failed to record knowledge runtime metric: {exc}"
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
            raw_transcript = event.get("transcript")
            self._log_latency_debug(
                "transcription_completed_empty_text",
                event_keys=sorted(str(key) for key in event.keys()),
                transcript_shape=self._summarize_payload_shape(raw_transcript),
                transcript_string_length=(
                    len(raw_transcript)
                    if isinstance(raw_transcript, str)
                    else None
                ),
                transcript_blank=(
                    not raw_transcript.strip()
                    if isinstance(raw_transcript, str)
                    else None
                ),
                item_keys=self._extract_dict_keys(event.get("item")),
                content_item_keys=self._extract_list_item_keys(event.get("content")),
                item_content_keys=self._extract_list_item_keys(
                    event.get("item", {}).get("content")
                    if isinstance(event.get("item"), dict)
                    else None
                ),
            )
            return
        self._log_latency_debug(
            "transcription_completed_text_extracted",
            transcript_length=len(transcript),
        )
        await self._handle_final_user_transcript(transcript)

    def _extract_final_transcript_text(self, event: dict) -> str:
        """Extract final transcript from upstream payload variations."""
        return self._extract_text_from_transcription_payload(event).strip()

    def _extract_transcription_delta_text(self, event: dict) -> str:
        """Extract interim transcript text from upstream payload variations."""
        return self._extract_text_from_transcription_payload(event)

    def _extract_text_from_transcription_payload(self, payload: Any) -> str:
        """Extract transcript text from StepFun/OpenAI-style nested ASR payloads."""
        text_keys = (
            "transcript",
            "text",
            "audio_transcript",
            "stash",
            "delta",
        )
        container_keys = (
            "item",
            "content",
            "parts",
            "part",
            "transcription",
            "input_audio_transcription",
            "audio",
        )
        return self._extract_text_from_keys(
            payload,
            text_keys=text_keys,
            container_keys=container_keys,
            max_depth=5,
        )

    def _extract_text_from_keys(
        self,
        payload: Any,
        *,
        text_keys: tuple[str, ...],
        container_keys: tuple[str, ...],
        max_depth: int,
    ) -> str:
        if max_depth < 0:
            return ""
        if isinstance(payload, str):
            return payload if payload.strip() else ""
        if isinstance(payload, list):
            for item in payload:
                extracted = self._extract_text_from_keys(
                    item,
                    text_keys=text_keys,
                    container_keys=container_keys,
                    max_depth=max_depth - 1,
                )
                if extracted.strip():
                    return extracted
            return ""
        if not isinstance(payload, dict):
            return ""

        for key in text_keys:
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
            if isinstance(candidate, (dict, list)):
                extracted = self._extract_text_from_keys(
                    candidate,
                    text_keys=text_keys,
                    container_keys=container_keys,
                    max_depth=max_depth - 1,
                )
                if extracted.strip():
                    return extracted

        for key in container_keys:
            if key not in payload:
                continue
            extracted = self._extract_text_from_keys(
                payload.get(key),
                text_keys=text_keys,
                container_keys=container_keys,
                max_depth=max_depth - 1,
            )
            if extracted.strip():
                return extracted
        return ""

    def _extract_dict_keys(self, payload: Any) -> list[str]:
        if not isinstance(payload, dict):
            return []
        return sorted(str(key) for key in payload.keys())

    def _extract_list_item_keys(self, payload: Any) -> list[list[str]]:
        if not isinstance(payload, list):
            return []
        keys: list[list[str]] = []
        for item in payload[:3]:
            keys.append(self._extract_dict_keys(item))
        return keys

    def _summarize_payload_shape(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, str):
            return {"type": "str", "length": len(payload), "blank": not payload.strip()}
        if isinstance(payload, dict):
            return {"type": "dict", "keys": self._extract_dict_keys(payload)}
        if isinstance(payload, list):
            return {
                "type": "list",
                "length": len(payload),
                "item_keys": self._extract_list_item_keys(payload),
            }
        if payload is None:
            return {"type": "none"}
        return {"type": type(payload).__name__}

    def _extract_conversation_item_role(self, event: dict) -> str:
        item = event.get("item")
        if not isinstance(item, dict):
            return ""
        role = item.get("role")
        return str(role or "")

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
            if self._active_response.roleplay_suppressed:
                return
            self._active_response.text_parts.append(delta)
            await self._apply_roleplay_stream_guard()

    async def _after_response_flushed_before_followup(
        self,
        *,
        expected_request_id: int,
        event: dict[str, Any],
    ) -> None:
        """Scenario hook after the completed response is flushed, before follow-up."""

    async def _handle_upstream_response_done(self, event: dict) -> None:
        """Finalize response and execute potential tool follow-ups."""
        expected_request_id = (
            self._active_response.request_id
            if self._active_response is not None
            else None
        )
        had_active_response = await self._flush_active_response(event)
        if had_active_response and expected_request_id is not None:
            await self._after_response_flushed_before_followup(
                expected_request_id=expected_request_id,
                event=event,
            )
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
        """Normalize upstream error and forward to frontend."""
        asr_reason = extract_asr_error_reason(event)
        if asr_reason:
            await self.manager.send_json(
                self.websocket,
                build_asr_fallback_status_event(
                    reason=asr_reason,
                    session_status=self.session_status,
                    ai_state=self.ai_state,
                    turn_count=self.turn_count,
                    trace_id=get_trace_id(),
                    policy=DEFAULT_ASR_FALLBACK_POLICY,
                ),
            )
            await self._send_error(
                ASR_FALLBACK_REQUIRED_ERROR_CODE,
                DEFAULT_ASR_FALLBACK_POLICY.user_message,
            )
            return
        if is_voice_unavailable_error(event):
            selected_voice = getattr(self, "_selected_stepfun_voice", None)
            if isinstance(selected_voice, str) and selected_voice:
                self._unavailable_voice_ids.add(selected_voice)
            await self._send_error(
                "[STEPFUN_VOICE_UNAVAILABLE]",
                "当前角色音色不可用，将在下次初始化时回退到默认音色。",
            )
            return
        if await self._recover_upstream_after_idle_timeout_error(event):
            await self._send_error(
                "[STEPFUN_UPSTREAM_RECOVERED]",
                "Realtime 上游连接已从空闲超时中恢复，请重新发送这一轮内容。",
            )
            return
        await self._send_error("[STEPFUN_API_ERROR]", extract_error_message(event))

    async def _forward_audio_delta_chunk(self, delta_b64: str) -> None:
        """Forward one upstream audio delta as frontend tts_chunk for low-latency playback."""
        response_state = self._active_response
        if not response_state:
            return

        chunk_index = response_state.chunk_index
        output_format = self._stepfun_output_audio_format.lower()

        try:
            raw_bytes = base64.b64decode(delta_b64)
        except (ValueError, RuntimeError):
            logger.warning("Failed to decode StepFun audio delta")
            return

        if output_format == "pcm16":
            duration_ms = int(
                len(raw_bytes) / 2 / self._stepfun_output_sample_rate * 1000
            )
            audio_payload = base64.b64encode(raw_bytes).decode("utf-8")
        else:
            # Approximate mp3/other encoded chunk duration
            duration_ms = max(1, len(raw_bytes) // 16)
            audio_payload = delta_b64

        response_state.total_duration_ms += max(0, duration_ms)

        await self.manager.send_json(
            self.websocket,
            build_tts_chunk_event(
                stream_id=response_state.stream_id,
                request_id=response_state.request_id,
                chunk_index=chunk_index,
                audio=audio_payload,
                duration_ms=duration_ms,
                is_final=False,
                audio_format=output_format,
                sample_rate=self._stepfun_output_sample_rate,
                playback_rate=self._stepfun_playback_rate,
                protocol_version=self._tts_chunk_protocol_version,
            ),
        )
        audio_flow = getattr(self, "_audio_flow", None)
        if audio_flow is not None:
            audio_flow.append_output_audio(delta_b64)

        if not response_state.first_chunk_sent:
            response_state.first_chunk_sent = True
            await self._send_status("speaking")

        response_state.roleplay_audio_forwarded = True
        response_state.chunk_index += 1

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

    def _ensure_knowledge_runtime_metrics(self) -> dict[str, Any]:
        """Ensure runtime metrics structure exists on effective policy snapshot."""
        return ensure_knowledge_runtime_metrics(self._effective_policy)

    async def _record_roleplay_instruction_hash_metric(
        self,
        grounding_debug_payload: dict[str, Any],
    ) -> None:
        effective_policy = getattr(self, "_effective_policy", None)
        if not isinstance(effective_policy, dict):
            return
        runtime_metrics = effective_policy.get("runtime_metrics")
        if not isinstance(runtime_metrics, dict):
            runtime_metrics = {}
        audit = runtime_metrics.get(ROLEPLAY_INSTRUCTION_HASH_METRICS_KEY)
        if not isinstance(audit, dict):
            audit = {}
        sample = {
            "request_id": grounding_debug_payload.get("request_id"),
            "instruction_contract_hash": grounding_debug_payload.get(
                "instruction_contract_hash"
            ),
            "turn_instruction_hash": grounding_debug_payload.get(
                "turn_instruction_hash"
            ),
            "final_instruction_length": grounding_debug_payload.get(
                "final_instruction_length"
            ),
            "role_anchor_length": grounding_debug_payload.get("role_anchor_length"),
            "has_grounding_context": grounding_debug_payload.get(
                "has_grounding_context"
            ),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        previous_samples = audit.get("samples")
        samples = previous_samples if isinstance(previous_samples, list) else []
        audit = {
            "latest": sample,
            "samples": [sample, *samples][:ROLEPLAY_INSTRUCTION_HASH_SAMPLE_LIMIT],
        }
        runtime_metrics[ROLEPLAY_INSTRUCTION_HASH_METRICS_KEY] = audit
        effective_policy["runtime_metrics"] = runtime_metrics
        self._effective_policy = effective_policy
        persist = getattr(self, "_persist_runtime_metrics_to_session", None)
        if callable(persist):
            await persist()

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

    def _build_stepfun_tools_from_policy(self) -> list[dict[str, Any]]:
        """Build StepFun tool definitions from resolved policy."""
        tool_execution = getattr(self, "_tool_execution", None)
        if tool_execution is not None:
            tools: list[dict[str, Any]] = tool_execution.build_tools_from_policy(
                self._effective_policy
            )
            return tools
        return build_stepfun_tools_from_policy(self._effective_policy)

    def _enforce_stepfun_tool_guardrails(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter tool list using final effective policy guarantees."""
        tool_execution = getattr(self, "_tool_execution", None)
        if tool_execution is not None:
            filtered: list[dict[str, Any]] = tool_execution.enforce_guardrails(
                tools,
                self._effective_policy,
            )
            return filtered

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

    async def _send_upstream(self, payload: dict[str, Any]) -> bool:
        """Send one event to StepFun upstream."""
        if self.upstream_ws is None:
            return False
        event_type = str(payload.get("type") or "")
        if self._using_provider_port():
            provider = self._realtime_provider
            if provider is None:
                return False
            command = self._provider_command_from_legacy_payload(payload)
            result = await provider.send(command)
            if result.accepted:
                self._mark_upstream_activity()
                return True
            logger.error(
                "realtime_provider_send_rejected",
                session_id=self.session_id,
                command_kind=command.kind.value,
                error_category=(
                    result.error_category.value
                    if result.error_category is not None
                    else None
                ),
                error_reason=(
                    result.error_reason.value
                    if result.error_reason is not None
                    else None
                ),
            )
            return False
        result = await self._stepfun_transport.send_json(self.upstream_ws, payload)
        if result.status == StepFunSendStatus.SENT:
            self._mark_upstream_activity()
            return True
        logger.error(
            "stepfun_upstream_send_rejected",
            session_id=self.session_id,
            event_type=event_type,
            error_type=result.error_type,
        )
        if event_type == "session.update":
            raise RuntimeError(
                f"StepFun session.update failed ({result.error_type or 'unknown'})"
            )
        return False


def _provider_command_from_legacy_payload(payload: dict[str, Any]) -> ProviderCommand:
    event_type = payload.get("type")
    if event_type == "input_audio_buffer.append":
        return ProviderCommand(
            kind=ProviderCommandKind.APPEND_AUDIO,
            data={"audio": payload.get("audio")},
        )
    if event_type == "input_audio_buffer.commit":
        return ProviderCommand(kind=ProviderCommandKind.COMMIT_AUDIO, data={})
    if event_type == "input_audio_buffer.clear":
        return ProviderCommand(kind=ProviderCommandKind.CLEAR_AUDIO, data={})
    if event_type == "response.create":
        response = payload.get("response")
        if not isinstance(response, dict):
            response = {}
        data: dict[str, Any] = {
            "modalities": response.get("modalities", ["text", "audio"]),
        }
        if "instructions" in response:
            data["instructions"] = response["instructions"]
        return ProviderCommand(kind=ProviderCommandKind.CREATE_RESPONSE, data=data)
    if event_type == "response.cancel":
        data = {}
        if "response_id" in payload:
            data["response_id"] = payload["response_id"]
        return ProviderCommand(kind=ProviderCommandKind.CANCEL_RESPONSE, data=data)
    if event_type == "conversation.item.create":
        item = payload.get("item")
        if not isinstance(item, dict):
            item = {}
        if item.get("type") == "function_call_output":
            return ProviderCommand(
                kind=ProviderCommandKind.TOOL_OUTPUT,
                data={
                    "call_id": item.get("call_id"),
                    "output": item.get("output"),
                },
            )
        data = {
            "role": item.get("role"),
            "content": item.get("content"),
        }
        if "id" in item:
            data["item_id"] = item["id"]
        return ProviderCommand(
            kind=ProviderCommandKind.CREATE_CONVERSATION_ITEM,
            data=data,
        )
    raise ValueError("unsupported_provider_command_type")


def _legacy_event_from_provider_event(event: ProviderEvent) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": event.provider_event_type}
    for key, value in (
        ("request_id", event.request_id),
        ("response_id", event.response_id),
        ("stream_id", event.stream_id),
        ("call_id", event.call_id),
        ("event_id", event.event_id),
        ("turn_id", event.turn_id),
        ("timestamp_ms", event.timestamp_ms),
        ("duration_ms", event.duration_ms),
    ):
        if value is not None:
            payload[key] = value
    data = {key: _plain_provider_value(value) for key, value in event.data.items()}

    if event.kind is ProviderEventKind.UNKNOWN:
        return {"type": "unknown"}
    if event.kind is ProviderEventKind.ERROR:
        reason = event.error_reason or ProviderErrorReason.UNKNOWN
        return {
            "type": "error",
            "error": {
                "code": reason.value,
                "message": _provider_error_delivery_message(reason),
            },
        }
    if event.kind is ProviderEventKind.CONVERSATION_ITEM:
        item = {
            "type": data.get("item_type"),
            **{
                key: data[key]
                for key in ("role", "name", "arguments", "transcript", "content")
                if key in data
            },
        }
        if event.call_id is not None:
            item["call_id"] = event.call_id
        payload["item"] = item
    elif event.kind in {
        ProviderEventKind.TRANSCRIPTION_DELTA,
        ProviderEventKind.RESPONSE_TEXT_DELTA,
        ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA,
        ProviderEventKind.THINKING_DELTA,
    }:
        payload["delta"] = data.get("text", "")
    elif event.kind in {
        ProviderEventKind.TRANSCRIPTION_FINAL,
        ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
    }:
        if "text" in data:
            payload["transcript"] = data["text"]
    elif event.kind is ProviderEventKind.THINKING_DONE:
        if "text" in data:
            payload["thinking"] = data["text"]
    elif event.kind is ProviderEventKind.RESPONSE_AUDIO_DELTA:
        payload["delta"] = data.get("audio", "")
    elif event.kind in {
        ProviderEventKind.FUNCTION_ARGUMENTS_DELTA,
        ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
    }:
        arguments_key = (
            "arguments"
            if event.kind is ProviderEventKind.FUNCTION_ARGUMENTS_DONE
            else "delta"
        )
        payload[arguments_key] = data.get("arguments", "")
        if "name" in data:
            payload["name"] = data["name"]
    elif event.kind is ProviderEventKind.RESPONSE_CREATED:
        payload["response"] = {"id": event.response_id} if event.response_id else {}
    elif event.kind is ProviderEventKind.RESPONSE_DONE:
        output = []
        function_outputs = data.get("function_outputs")
        if isinstance(function_outputs, list):
            for item in function_outputs:
                if not isinstance(item, dict):
                    continue
                output.append({"type": "function_call", **item})
        response: dict[str, Any] = {"output": output}
        if event.response_id is not None:
            response["id"] = event.response_id
        payload["response"] = response
    return payload


def _plain_provider_value(value: JsonValue) -> Any:
    if isinstance(value, FrozenJsonMapping):
        return {key: _plain_provider_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_provider_value(item) for item in value]
    return value


def _provider_error_delivery_message(reason: ProviderErrorReason) -> str:
    messages = {
        ProviderErrorReason.INVALID_CREDENTIALS: "StepFun API 密钥无效或未授权。",
        ProviderErrorReason.FORBIDDEN: "StepFun API 访问被拒绝。",
        ProviderErrorReason.QUOTA_EXHAUSTED: "StepFun 账户余额不足或额度已用尽。",
        ProviderErrorReason.RATE_LIMITED: "StepFun 请求过于频繁，请稍后再试。",
        ProviderErrorReason.ASR_UNAVAILABLE: "asr_unavailable",
        ProviderErrorReason.VOICE_UNAVAILABLE: "voice_unavailable",
        ProviderErrorReason.IDLE_TIMEOUT: "too long without operation",
        ProviderErrorReason.UPSTREAM_UNAVAILABLE: "Realtime 服务暂不可用",
        ProviderErrorReason.INVALID_EVENT: "Realtime 服务返回无效事件",
        ProviderErrorReason.CONNECTION_CLOSED: "Realtime 上游连接已关闭",
        ProviderErrorReason.BACKPRESSURE_LIMIT: "Realtime 上游负载过高",
        ProviderErrorReason.UNKNOWN: "Realtime 服务返回错误",
    }
    return messages[reason]
