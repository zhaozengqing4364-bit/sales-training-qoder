"""Policy mixin for the StepFun realtime websocket handler."""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportGeneralTypeIssues=false, reportMissingImports=false
# ruff: noqa: F401, I001

import asyncio
import base64
import copy
import inspect
import json
import os
import re
import struct
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast

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
from curriculum_practice.services.runtime_dossier import (
    CURRICULUM_RUNTIME_SNAPSHOT_STALE,
    CurriculumRuntimeDossierError,
    CurriculumRuntimeDossierHydrator,
    compose_curriculum_runtime_instructions,
)
from curriculum_practice.services.roleplay_contracts import (
    ROLEPLAY_DISCLOSURE_STATE_KEY,
    initial_roleplay_disclosure_state,
    normalize_roleplay_disclosure_state,
)
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
from sales_bot.websocket.components.stepfun_roleplay_runtime_helpers import (
    restore_roleplay_runtime_state,
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
from sales_bot.websocket.session_control_adapter import SessionControlAdapter
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
from sales_bot.websocket.voice_runtime_profile import VoiceRuntimeProfile

logger = get_logger(__name__)


def _handler_symbol(name: str, fallback: Any) -> Any:
    """Read monkeypatch-compatible symbols from the public handler module."""
    module = sys.modules.get("sales_bot.websocket.stepfun_realtime_handler")
    return getattr(module, name, fallback) if module is not None else fallback


def _optional_runtime_score(value: Any) -> float | None:
    """Normalize nullable ORM/runtime score fields."""
    if value is None or hasattr(value, "expression"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_runtime_text(value: Any) -> str | None:
    """Normalize nullable ORM/runtime identifiers without treating SQLAlchemy columns as values."""
    if value is None or hasattr(value, "expression"):
        return None
    text = str(value).strip()
    return text or None


class StepFunRealtimePolicyMixin(StepFunRealtimeStateBase):
    _voice_runtime_profile: VoiceRuntimeProfile | None

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
        persona_kb_lock_explicitly_disabled = (
            self._is_persona_kb_lock_explicitly_disabled(policy)
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

        source = policy.get("source")
        if not isinstance(source, dict):
            source = {}
            changed = True

        if (
            has_bound_knowledge_base
            and persona_kb_lock_explicitly_disabled
            and retrieval_priority == "kb_only"
        ):
            tool_policy["retrieval_priority"] = "kb_first"
            retrieval_priority = "kb_first"
            source.setdefault(
                "kb_lock_legacy_snapshot_backfill",
                "kb_only_downgraded_to_kb_first_when_lock_disabled",
            )
            changed = True

        # `kb_only` must be equivalent to strict KB lock, otherwise model can still
        # generate from parametric memory when retrieval misses or is weak.
        if (
            has_bound_knowledge_base
            and retrieval_priority == "kb_only"
            and not require_kb_grounding
            and not persona_kb_lock_explicitly_disabled
        ):
            require_kb_grounding = True
            tool_policy["require_kb_grounding"] = True
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

    async def _load_effective_policy(self) -> None:
        """Load effective voice policy from the persisted session snapshot."""
        self._effective_policy = {}
        async with self._db_session_factory() as db:
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
            curriculum_snapshot = getattr(session, "curriculum_snapshot", None)
            self._curriculum_snapshot = (
                copy.deepcopy(curriculum_snapshot)
                if isinstance(curriculum_snapshot, dict)
                else None
            )
            contract = self._resolve_roleplay_contract_from_snapshots(
                curriculum_snapshot=self._curriculum_snapshot,
                voice_policy_snapshot=getattr(session, "voice_policy_snapshot", None),
            )
            runtime_state_raw = getattr(session, "runtime_state", None)
            runtime_state: dict[str, Any] = (
                runtime_state_raw if isinstance(runtime_state_raw, dict) else {}
            )
            self._roleplay_disclosure_state = normalize_roleplay_disclosure_state(
                contract,
                runtime_state.get(ROLEPLAY_DISCLOSURE_STATE_KEY)
                if isinstance(runtime_state, dict)
                else None,
            )
            if isinstance(contract, dict) and not isinstance(
                runtime_state.get(ROLEPLAY_DISCLOSURE_STATE_KEY)
                if isinstance(runtime_state, dict)
                else None,
                dict,
            ):
                runtime_state = dict(runtime_state)
                runtime_state[ROLEPLAY_DISCLOSURE_STATE_KEY] = (
                    self._roleplay_disclosure_state
                )
                session_any.runtime_state = runtime_state
                await db.commit()
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
            snapshot = snapshot_raw if isinstance(snapshot_raw, dict) else None

            policy_source = "snapshot"
            if snapshot:
                self._effective_policy = snapshot
            else:
                raise RuntimeError("VOICE_POLICY_SNAPSHOT_MISSING")

            guardrail_applied = self._enforce_tool_policy_guardrails()
            dictionary_applied = await self._merge_kb_dictionary_into_effective_policy(db)
            if guardrail_applied or dictionary_applied:
                if self._curriculum_snapshot is None:
                    session_any.voice_policy_snapshot = self._effective_policy
                    await db.commit()
            if isinstance(runtime_state, dict):
                restore_roleplay_runtime_state(self._effective_policy, runtime_state)

            profile = self._apply_voice_runtime_profile(self._effective_policy)
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
            await self._hydrate_curriculum_runtime_dossier(db)
            self._ensure_knowledge_runtime_metrics()
            tool_policy = self._effective_policy.get("tool_policy")
            if not isinstance(tool_policy, dict):
                tool_policy = dict(profile.tool_policy)
            knowledge_base_ids = self._effective_policy.get("knowledge_base_ids")
            if not isinstance(knowledge_base_ids, list):
                knowledge_base_ids = list(profile.knowledge_base_ids)
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
                instruction_contract_hash=profile.instruction_contract_hash,
                knowledge_base_count=len(knowledge_base_ids),
            )

    def _apply_voice_runtime_profile(
        self, policy_snapshot: dict[str, Any]
    ) -> VoiceRuntimeProfile:
        """Apply stable StepFun runtime fields via immutable policy profile seam."""

        profile = VoiceRuntimeProfile.from_policy_snapshot(policy_snapshot)
        self._voice_runtime_profile = profile
        self._stepfun_model = profile.model_name
        self._stepfun_voice = profile.voice_name
        self._stepfun_temperature = profile.temperature
        self._stepfun_instructions = profile.instructions
        self._instruction_contract_hash = profile.instruction_contract_hash
        return profile

    async def _hydrate_curriculum_runtime_dossier(self, db: Any) -> None:
        if self._curriculum_snapshot is None:
            return
        try:
            dossier = await CurriculumRuntimeDossierHydrator(db).hydrate(
                self._curriculum_snapshot,
                roleplay_disclosure_state=self._roleplay_disclosure_state,
            )
        except CurriculumRuntimeDossierError as exc:
            logger.warning(
                "Curriculum runtime dossier hydration failed",
                session_id=self.session_id,
                code=exc.code,
                missing=exc.missing,
            )
            raise RuntimeError(CURRICULUM_RUNTIME_SNAPSHOT_STALE) from exc
        if not dossier.has_prompt_context:
            return

        composed_instructions = compose_curriculum_runtime_instructions(
            self._stepfun_instructions,
            dossier,
        )
        self._stepfun_instructions = composed_instructions
        self._instruction_contract_hash = build_instruction_contract_hash(
            composed_instructions
        )
        self._effective_policy = dict(self._effective_policy)
        self._effective_policy["instructions"] = composed_instructions
        self._effective_policy[
            "instruction_contract_hash"
        ] = self._instruction_contract_hash
        runtime_metrics = self._effective_policy.get("runtime_metrics")
        if not isinstance(runtime_metrics, dict):
            runtime_metrics = {}
        runtime_metrics = dict(runtime_metrics)
        runtime_metrics["curriculum_dossier"] = dossier.runtime_metrics()
        self._effective_policy["runtime_metrics"] = runtime_metrics
        self._voice_runtime_profile = VoiceRuntimeProfile.from_policy_snapshot(
            self._effective_policy
        )

    @staticmethod
    def _resolve_roleplay_contract_from_snapshots(
        *,
        curriculum_snapshot: object,
        voice_policy_snapshot: object,
    ) -> dict[str, Any] | None:
        if isinstance(curriculum_snapshot, dict) and isinstance(
            curriculum_snapshot.get("roleplay_contract"),
            dict,
        ):
            return curriculum_snapshot.get("roleplay_contract")
        if isinstance(voice_policy_snapshot, dict) and isinstance(
            voice_policy_snapshot.get("roleplay_contract"),
            dict,
        ):
            return voice_policy_snapshot.get("roleplay_contract")
        return None

    def _active_voice_runtime_profile(self) -> VoiceRuntimeProfile:
        """Return canonical voice runtime profile, falling back to legacy fields before policy load."""

        if self._voice_runtime_profile is not None:
            return self._voice_runtime_profile

        snapshot = dict(self._effective_policy)
        snapshot.setdefault("voice_mode", "legacy")
        snapshot.setdefault("model_name", self._stepfun_model)
        snapshot.setdefault("voice_name", self._stepfun_voice)
        snapshot.setdefault("temperature", self._stepfun_temperature)
        snapshot.setdefault("instructions", self._stepfun_instructions)
        snapshot.setdefault(
            "instruction_contract_hash",
            self._instruction_contract_hash,
        )
        profile = VoiceRuntimeProfile.from_policy_snapshot(snapshot)
        self._voice_runtime_profile = profile
        return profile

    async def _refresh_sales_stage_runtime_config(self, db: Any) -> None:
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

    async def _apply_lifecycle_action(
        self, action: SessionLifecycleAction
    ) -> object | None:
        if not self.session_id:
            return None

        try:
            session_factory = _handler_symbol("AsyncSessionLocal", AsyncSessionLocal)
            async with session_factory() as db:
                lifecycle_service_cls = _handler_symbol(
                    "SessionLifecycleService",
                    SessionLifecycleService,
                )
                lifecycle_service = lifecycle_service_cls(db)
                (
                    session,
                    scenario_type,
                ) = await lifecycle_service.get_session_with_scenario(self.session_id)
                if not session:
                    await self._send_error("[SESSION_NOT_FOUND]", "会话不存在")
                    return None

                self.session_scenario_type = scenario_type or "sales"

                try:
                    session_control_cls = _handler_symbol(
                        "SessionControlAdapter",
                        SessionControlAdapter,
                    )
                    session_control = session_control_cls(lifecycle_service)
                    transition = await session_control.apply_action(
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
                return cast(object, transition)
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
            if not await self._ensure_upstream_ready_for_input("audio_chunk"):
                return
            interrupt = data.get("interrupt", False)
            if interrupt:
                await self._handle_interrupt("user_speaking")
                return
            audio = data.get("audio")
            if audio:
                payload = {"type": "input_audio_buffer.append", "audio": audio}
                if self._should_drop_upstream_for_backpressure(payload):
                    return
                await self._send_upstream(payload)
                self._audio_flow.append_input_audio(audio)
                self._has_uncommitted_audio = True

        elif msg_type == "audio_end":
            if not await self._ensure_input_allowed("audio_end"):
                return
            if not await self._ensure_upstream_ready_for_input("audio_end"):
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
                if not await self._ensure_upstream_ready_for_input("text"):
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
                await self._update_roleplay_disclosure_state(
                    learner_message=text,
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
        if not await self._ensure_upstream_ready_for_input("audio_chunk_binary"):
            return

        self._received_binary_audio_frame_count += 1
        quality_stats = self._summarize_pcm16_payload(payload)
        if self._received_binary_audio_frame_count % 20 == 0:
            self._log_latency_debug(
                "audio_binary_received",
                frame_count=self._received_binary_audio_frame_count,
                **quality_stats,
            )

        audio_b64 = base64.b64encode(payload).decode("utf-8")
        upstream_payload = {"type": "input_audio_buffer.append", "audio": audio_b64}
        if self._should_drop_upstream_for_backpressure(upstream_payload):
            return
        self._record_input_audio_quality(payload)
        await self._send_upstream(upstream_payload)
        self._audio_flow.append_input_audio(audio_b64)
        self._has_uncommitted_audio = True

    @staticmethod
    def _summarize_pcm16_payload(payload: bytes) -> dict[str, Any]:
        """Return aggregate PCM16 diagnostics without exposing raw audio."""
        even_length = len(payload) - (len(payload) % 2)
        if even_length <= 0:
            return {
                "sample_count": 0,
                "rms": 0.0,
                "peak_abs": 0,
                "zero_ratio": 0.0,
                "payload_bytes": len(payload),
                "odd_byte_truncated": bool(payload),
            }

        sample_count = even_length // 2
        sum_squares = 0
        peak_abs = 0
        zero_count = 0
        for (sample,) in struct.iter_unpack("<h", payload[:even_length]):
            sample_abs = abs(sample)
            if sample_abs > peak_abs:
                peak_abs = sample_abs
            if sample == 0:
                zero_count += 1
            sum_squares += sample * sample

        return {
            "sample_count": sample_count,
            "rms": round((sum_squares / sample_count) ** 0.5, 2),
            "peak_abs": peak_abs,
            "zero_ratio": round(zero_count / sample_count, 4),
            "payload_bytes": len(payload),
            "odd_byte_truncated": len(payload) != even_length,
        }

    def _record_input_audio_quality(self, payload: bytes) -> dict[str, Any]:
        """Accumulate turn-scoped PCM16 quality diagnostics."""
        stats = self._summarize_pcm16_payload(payload)
        sample_count = int(stats["sample_count"])
        if sample_count <= 0:
            self._input_audio_quality_odd_payload_frames += int(
                bool(stats["odd_byte_truncated"])
            )
            return stats

        rms = float(stats["rms"])
        self._input_audio_quality_sample_count += sample_count
        self._input_audio_quality_sum_squares += int(round(rms * rms * sample_count))
        self._input_audio_quality_peak_abs = max(
            self._input_audio_quality_peak_abs,
            int(stats["peak_abs"]),
        )
        self._input_audio_quality_zero_count += int(
            round(float(stats["zero_ratio"]) * sample_count)
        )
        self._input_audio_quality_frame_count += 1
        self._input_audio_quality_payload_bytes += len(payload)
        self._input_audio_quality_odd_payload_frames += int(
            bool(stats["odd_byte_truncated"])
        )
        return stats

    def _summarize_pending_input_audio_quality(self) -> dict[str, Any]:
        """Return cumulative PCM16 diagnostics for the pending user utterance."""
        sample_count = self._input_audio_quality_sample_count
        if sample_count <= 0:
            return {
                "audio_quality_frame_count": self._input_audio_quality_frame_count,
                "audio_quality_payload_bytes": self._input_audio_quality_payload_bytes,
                "audio_quality_sample_count": 0,
                "audio_quality_rms": 0.0,
                "audio_quality_peak_abs": 0,
                "audio_quality_zero_ratio": 0.0,
                "audio_quality_odd_payload_frames": (
                    self._input_audio_quality_odd_payload_frames
                ),
            }

        return {
            "audio_quality_frame_count": self._input_audio_quality_frame_count,
            "audio_quality_payload_bytes": self._input_audio_quality_payload_bytes,
            "audio_quality_sample_count": sample_count,
            "audio_quality_rms": round(
                (self._input_audio_quality_sum_squares / sample_count) ** 0.5,
                2,
            ),
            "audio_quality_peak_abs": self._input_audio_quality_peak_abs,
            "audio_quality_zero_ratio": round(
                self._input_audio_quality_zero_count / sample_count,
                4,
            ),
            "audio_quality_odd_payload_frames": (
                self._input_audio_quality_odd_payload_frames
            ),
        }

    def _reset_input_audio_quality(self) -> None:
        """Reset pending user-utterance PCM16 diagnostics."""
        self._input_audio_quality_sample_count = 0
        self._input_audio_quality_sum_squares = 0
        self._input_audio_quality_peak_abs = 0
        self._input_audio_quality_zero_count = 0
        self._input_audio_quality_frame_count = 0
        self._input_audio_quality_payload_bytes = 0
        self._input_audio_quality_odd_payload_frames = 0
