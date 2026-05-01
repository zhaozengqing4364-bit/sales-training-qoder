"""Policy mixin for the StepFun realtime websocket handler."""

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


class StepFunRealtimePolicyMixin:
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

    def _apply_latest_scores_to_session(self, session: PracticeSession) -> None:
        """Sync latest realtime score snapshot into session-level score fields."""
        normalized_score_snapshot = normalize_score_snapshot(
            self._latest_score_snapshot
        )
        evaluable = self.turn_count > 0
        not_evaluable_reason = None if evaluable else "INSUFFICIENT_TURN_DATA"

        if normalized_score_snapshot is None:
            session.effectiveness_snapshot = evaluate_effectiveness_snapshot(
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
        session.logic_score = rollups["logic_score"]
        session.accuracy_score = rollups["accuracy_score"]
        session.completeness_score = rollups["completeness_score"]

        snapshot = evaluate_effectiveness_snapshot(
            metrics=build_sales_effectiveness_metrics(
                overall_score=overall_score,
                dimension_scores=normalized_score_snapshot.get("dimension_scores"),
                logic_score=session.logic_score,
                accuracy_score=session.accuracy_score,
                completeness_score=session.completeness_score,
                turn_count=max(0, self.turn_count),
            ),
            main_capability_passed=overall_score >= 70.0,
            evaluable=evaluable,
            not_evaluable_reason=not_evaluable_reason,
        )
        session.effectiveness_snapshot = snapshot

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

    async def _connect_upstream(self):
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

    async def _close_upstream(self):
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

    async def _handle_client_text(self, raw_text: str):
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

    async def _handle_binary_frame(self, data: bytes):
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
