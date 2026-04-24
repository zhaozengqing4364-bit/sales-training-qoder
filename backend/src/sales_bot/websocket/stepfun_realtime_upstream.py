"""Upstream mixin for the StepFun realtime websocket handler."""

from __future__ import annotations

# ruff: noqa: F401, I001

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


class StepFunRealtimeUpstreamMixin:
        async def _commit_and_respond(self):
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

        async def _handle_interrupt(self, reason: str):
            """Stop current generation and clear buffered input."""
            interrupted_stream_id = (
                self._active_response.stream_id if self._active_response else None
            )
            await self._cancel_pending_response_after_commit()
            await self._clear_upstream_generation()
            self._reset_turn_runtime_state()

            await self.manager.send_json(
                self.websocket,
                build_interrupted_event(
                    reason=reason,
                    session_status=self.session_status,
                    ai_state="listening"
                    if self.session_status == "in_progress"
                    else "idle",
                    turn_count=self.turn_count,
                    trace_id=get_trace_id(),
                    stream_id=interrupted_stream_id,
                ),
            )
            await self._send_status(
                "listening" if self.session_status == "in_progress" else "idle"
            )

        async def _handle_session_end(self):
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

        async def sync_lifecycle_transition(self, transition) -> None:
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

        async def _receive_upstream_events(self):
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

        async def _handle_upstream_event(self, event: dict):
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
            """Normalize upstream error and forward to frontend."""
            await self._send_error("[STEPFUN_API_ERROR]", extract_error_message(event))

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

        async def _forward_audio_delta_chunk(self, delta_b64: str):
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
                {
                    "type": "tts_chunk",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "stream_id": response_state.stream_id,
                    "request_id": response_state.request_id,
                    "data": {
                        "chunk_index": chunk_index,
                        "audio": audio_payload,
                        "duration_ms": duration_ms,
                        "is_final": False,
                        "audio_format": output_format,
                        "sample_rate": self._stepfun_output_sample_rate,
                        "playback_rate": self._stepfun_playback_rate,
                    },
                },
            )

            if not response_state.first_chunk_sent:
                response_state.first_chunk_sent = True
                await self._send_status("speaking")

            response_state.chunk_index += 1

        async def _accumulate_function_call_arguments(
            self, event: dict, done: bool = False
        ):
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

        def _ensure_knowledge_runtime_metrics(self) -> dict[str, Any]:
            """Ensure runtime metrics structure exists on effective policy snapshot."""
            return ensure_knowledge_runtime_metrics(self._effective_policy)

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

        async def _send_upstream(self, payload: dict):
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

        async def _send_transcript(self, text: str, is_final: bool):
            """Send ASR transcript in existing frontend message format."""
            await self.manager.send_json(
                self.websocket,
                build_asr_transcript_event(text=text, is_final=is_final),
            )

        async def _send_status(self, ai_state: str):
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

        async def _send_heartbeat(self):
            await self.manager.send_json(
                self.websocket,
                build_heartbeat_event(),
            )

        async def _send_error(self, code: str, message: str):
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
