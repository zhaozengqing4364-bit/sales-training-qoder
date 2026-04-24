"""Policy mixin for the StepFun realtime websocket handler."""

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
