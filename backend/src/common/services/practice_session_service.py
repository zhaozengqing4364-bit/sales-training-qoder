"""Practice session application services.

Extracts session creation, retry-focus shaping, runtime descriptor assembly, and
lifecycle orchestration out of the route layer while preserving the existing API
contract.
"""

from __future__ import annotations

import os
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.models import ConversationMessage
from common.conversation.score_snapshot import normalize_score_snapshot
from common.conversation.session_evidence import (
    ensure_effectiveness_snapshot as ensure_session_evidence_snapshot,
)
from common.db.models import PracticeSession, Scenario, User
from common.db.schemas import (
    ScenarioType,
    SessionCreate,
    SessionLifecycleResponse,
    SessionResponse,
    SessionUpdate,
)
from common.db.session_lifecycle import (
    SessionLifecycleService,
    SessionLifecycleTransition,
)
from common.db.voice_policy_snapshot import build_voice_policy_snapshot_ref
from common.effectiveness import (
    build_canonical_views,
    build_sales_effectiveness_metrics,
    evaluate_effectiveness_snapshot,
)
from common.monitoring.logger import get_logger, get_trace_id
from common.services.practice_helpers import PracticeRetryEntryAssembler
from common.websocket.base_handler import get_connection_manager
from common.websocket.session_manager import get_session_manager
from presentation_coach.services.coach_service import PresentationCoachService
from sales_bot.services.bot_service import sales_bot_service
from sales_bot.services.summary_service import summary_service
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from training_runtime.service import build_training_runtime_descriptor

logger = get_logger(__name__)


class PracticeServiceError(Exception):
    """Typed application-service error for route-level HTTP mapping."""

    def __init__(
        self,
        error_code: str,
        *,
        status_code: int = 400,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message
        self.details = details


@dataclass(slots=True)
class PracticeSessionCreateResult:
    session: PracticeSession
    scenario_type: str


@dataclass(slots=True)
class PracticeLifecycleActionResult:
    transition: SessionLifecycleTransition
    snapshot: dict[str, Any] | None = None
    summary: Any | None = None


@dataclass(slots=True)
class PracticeSessionUpdateResult:
    session: PracticeSession
    transition: SessionLifecycleTransition | None
    scenario_type: str | None


class PracticeRuntimeDescriptorService:
    """Assemble runtime-aware session payloads without route glue."""

    @staticmethod
    def build_session_response(
        session: PracticeSession,
        scenario_type: str | None = None,
    ) -> SessionResponse:
        payload = SessionResponse.model_validate(session)
        resolved_scenario_type = scenario_type
        if (
            not resolved_scenario_type
            and getattr(session, "scenario", None) is not None
        ):
            resolved_scenario_type = getattr(session.scenario, "scenario_type", None)

        try:
            payload.scenario_type = ScenarioType(resolved_scenario_type or "sales")
        except ValueError:
            payload.scenario_type = ScenarioType.SALES

        runtime_descriptor = build_training_runtime_descriptor(
            session,
            scenario_type=payload.scenario_type.value,
        )
        payload.runtime_subject = runtime_descriptor.subject
        payload.runtime_descriptor = runtime_descriptor
        runtime_profile_id = getattr(session, "voice_runtime_profile_id", None)
        payload.runtime_profile_id = (
            uuid.UUID(str(runtime_profile_id)) if runtime_profile_id else None
        )
        payload.voice_policy_snapshot_ref = build_voice_policy_snapshot_ref(
            payload.voice_policy_snapshot
        )
        return payload


class PracticeSessionCreateService:
    """Orchestrate session creation while keeping route handlers thin."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        runtime_policy_service: VoiceRuntimePolicyService | None = None,
    ) -> None:
        self.db = db
        self.runtime_policy_service = (
            runtime_policy_service or VoiceRuntimePolicyService(db)
        )
        self.logger = logger

    async def create_session(
        self,
        session_data: SessionCreate,
        *,
        current_user: User,
    ) -> PracticeSessionCreateResult:
        scenario_type_value = self._resolve_scenario_type_value(session_data)
        raw_session_payload = session_data.model_dump(exclude_unset=True)
        if raw_session_payload.get("sales_persona"):
            raise PracticeServiceError(
                "[FIELD_DEPRECATED_PERSONA_CENTERED]",
                status_code=400,
                message="sales_persona 已废弃，请改用 agent_id + persona_id（并在角色中心配置策略）",
            )

        requested_scenario = await self._resolve_requested_scenario(
            scenario_id=session_data.scenario_id,
            scenario_type_value=scenario_type_value,
        )
        agent_id_str, persona_id_str = self._resolve_agent_persona_pair(session_data)
        association_override_config = await self._validate_agent_persona_pair(
            agent_id_str=agent_id_str,
            persona_id_str=persona_id_str,
        )
        self._enforce_required_pairing(
            scenario_type_value=scenario_type_value,
            agent_id_str=agent_id_str,
            persona_id_str=persona_id_str,
        )

        effective_voice_policy = (
            await self.runtime_policy_service.resolve_effective_policy(
                agent_id=agent_id_str,
                persona_id=persona_id_str,
                voice_mode_override=session_data.voice_mode,
                runtime_profile_override=(
                    str(session_data.runtime_profile_id)
                    if session_data.runtime_profile_id
                    else None
                ),
            )
        )
        if association_override_config:
            effective_voice_policy = {
                **effective_voice_policy,
                "agent_persona_override_config": association_override_config,
            }

        session_policy_snapshot = deepcopy(effective_voice_policy)
        focus_intent = PracticeRetryEntryAssembler.sanitize_focus_intent(
            session_data.focus_intent
        )
        if session_data.focus_intent is not None and focus_intent is None:
            raise PracticeServiceError(
                "[INVALID_RETRY_FOCUS_INTENT]",
                status_code=400,
                message="retry focus intent 必须包含可读的 main_issue、next_goal 或 presentation_page 结构。",
            )
        if focus_intent is not None:
            session_policy_snapshot["focus_intent"] = deepcopy(focus_intent)

        self._enforce_sales_stepfun_only(
            scenario_type_value=scenario_type_value,
            requested_voice_mode=session_data.voice_mode,
            effective_voice_policy=effective_voice_policy,
        )

        self._log_voice_policy_resolution(
            current_user=current_user,
            scenario_type_value=scenario_type_value,
            agent_id_str=agent_id_str,
            persona_id_str=persona_id_str,
            effective_voice_policy=effective_voice_policy,
            focus_intent=focus_intent,
        )

        if scenario_type_value == "presentation":
            session = await self._create_presentation_session(
                session_data=session_data,
                current_user=current_user,
                requested_scenario=requested_scenario,
                agent_id_str=agent_id_str,
                persona_id_str=persona_id_str,
                session_policy_snapshot=session_policy_snapshot,
                effective_voice_policy=effective_voice_policy,
            )
        elif scenario_type_value == "sales":
            session = await self._create_sales_session(
                current_user=current_user,
                requested_scenario=requested_scenario,
                agent_id_str=agent_id_str,
                persona_id_str=persona_id_str,
                session_policy_snapshot=session_policy_snapshot,
                effective_voice_policy=effective_voice_policy,
            )
        else:
            raise PracticeServiceError("[INVALID_SCENARIO_TYPE]", status_code=400)

        return PracticeSessionCreateResult(
            session=session,
            scenario_type=scenario_type_value,
        )

    @staticmethod
    def _resolve_scenario_type_value(session_data: SessionCreate) -> str:
        return (
            session_data.scenario_type.value
            if hasattr(session_data.scenario_type, "value")
            else str(session_data.scenario_type)
        )

    @staticmethod
    def _enforce_sales_stepfun_only(
        *,
        scenario_type_value: str,
        requested_voice_mode: str | None,
        effective_voice_policy: dict[str, Any],
    ) -> None:
        if scenario_type_value != "sales":
            return
        if effective_voice_policy.get("voice_mode") == "stepfun_realtime":
            return

        raise PracticeServiceError(
            "[LEGACY_SALES_VOICE_MODE_DISABLED]",
            status_code=400,
            message="新建销售训练会话仅支持 StepFun Realtime，请使用 voice_mode=stepfun_realtime。",
            details={
                "requested_voice_mode": requested_voice_mode,
                "resolved_voice_mode": effective_voice_policy.get("voice_mode"),
            },
        )

    async def _resolve_requested_scenario(
        self,
        *,
        scenario_id: Any,
        scenario_type_value: str,
    ) -> Scenario | None:
        if not scenario_id:
            return None

        requested_scenario_result = await self.db.execute(
            select(Scenario).where(Scenario.scenario_id == str(scenario_id))
        )
        requested_scenario = requested_scenario_result.scalar_one_or_none()
        if not requested_scenario:
            raise PracticeServiceError("[SCENARIO_NOT_FOUND]", status_code=404)
        if requested_scenario.scenario_type != scenario_type_value:
            raise PracticeServiceError("[SCENARIO_TYPE_MISMATCH]", status_code=400)
        if not requested_scenario.is_active:
            raise PracticeServiceError("[SCENARIO_INACTIVE]", status_code=400)
        return requested_scenario

    @staticmethod
    def _resolve_agent_persona_pair(
        session_data: SessionCreate,
    ) -> tuple[str | None, str | None]:
        return (
            str(session_data.agent_id) if session_data.agent_id else None,
            str(session_data.persona_id) if session_data.persona_id else None,
        )

    def _enforce_required_pairing(
        self,
        *,
        scenario_type_value: str,
        agent_id_str: str | None,
        persona_id_str: str | None,
    ) -> None:
        if bool(agent_id_str) != bool(persona_id_str):
            raise PracticeServiceError("[AGENT_PERSONA_PAIR_REQUIRED]", status_code=400)
        if (
            scenario_type_value == "presentation"
            and _is_true_env("PRESENTATION_REQUIRE_AGENT_PERSONA", "true")
            and not (agent_id_str and persona_id_str)
        ):
            raise PracticeServiceError("[AGENT_PERSONA_PAIR_REQUIRED]", status_code=400)
        if scenario_type_value == "sales" and not (agent_id_str and persona_id_str):
            raise PracticeServiceError("[AGENT_PERSONA_PAIR_REQUIRED]", status_code=400)

    async def _validate_agent_persona_pair(
        self,
        *,
        agent_id_str: str | None,
        persona_id_str: str | None,
    ) -> dict[str, Any] | None:
        if not (agent_id_str and persona_id_str):
            return None

        from agent.models import Agent, AgentPersona
        from agent.models import Persona as AgentPersonaModel

        agent_result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id_str)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise PracticeServiceError("[AGENT_NOT_FOUND]", status_code=404)
        if agent.status == "archived":
            raise PracticeServiceError("[AGENT_ARCHIVED]", status_code=400)
        if agent.status != "published":
            raise PracticeServiceError("[AGENT_NOT_PUBLISHED]", status_code=400)

        persona_result = await self.db.execute(
            select(AgentPersonaModel).where(AgentPersonaModel.id == persona_id_str)
        )
        persona_obj = persona_result.scalar_one_or_none()
        if not persona_obj:
            raise PracticeServiceError("[PERSONA_NOT_FOUND]", status_code=404)
        if persona_obj.status != "active":
            raise PracticeServiceError("[PERSONA_INACTIVE]", status_code=400)

        link_result = await self.db.execute(
            select(AgentPersona).where(
                AgentPersona.agent_id == agent_id_str,
                AgentPersona.persona_id == persona_id_str,
            )
        )
        link = link_result.scalar_one_or_none()
        if not link:
            raise PracticeServiceError("[PERSONA_NOT_LINKED_TO_AGENT]", status_code=400)
        return link.override_config or None

    def _log_voice_policy_resolution(
        self,
        *,
        current_user: User,
        scenario_type_value: str,
        agent_id_str: str | None,
        persona_id_str: str | None,
        effective_voice_policy: dict[str, Any],
        focus_intent: dict[str, Any] | None,
    ) -> None:
        resolved_kb_ids = effective_voice_policy.get("knowledge_base_ids")
        if not isinstance(resolved_kb_ids, list):
            resolved_kb_ids = []
        customer_pressure = effective_voice_policy.get("customer_pressure")
        if not isinstance(customer_pressure, dict):
            customer_pressure = {}
        pressure_direction = customer_pressure.get("pressure_direction")
        if not isinstance(pressure_direction, dict):
            pressure_direction = {}
        follow_up_behavior = customer_pressure.get("follow_up_behavior")
        if not isinstance(follow_up_behavior, dict):
            follow_up_behavior = {}

        self.logger.info(
            "practice_session_voice_policy_resolved",
            user_id=str(current_user.user_id),
            scenario_type=scenario_type_value,
            agent_id=agent_id_str,
            persona_id=persona_id_str,
            voice_mode=effective_voice_policy.get("voice_mode", "legacy"),
            runtime_profile_id=effective_voice_policy.get("runtime_profile_id"),
            knowledge_base_count=len(resolved_kb_ids),
            customer_pressure_source=str(customer_pressure.get("source") or "none"),
            customer_pressure_focus=str(pressure_direction.get("sales_focus") or ""),
            question_strategy=str(follow_up_behavior.get("question_strategy") or ""),
            revisit_on_evasion=bool(
                follow_up_behavior.get("revisit_on_evasion", False)
            ),
            require_evidence=bool(follow_up_behavior.get("require_evidence", False)),
            instruction_contract_hash=str(
                effective_voice_policy.get("instruction_contract_hash") or ""
            ),
            retry_focus_issue_type=(
                focus_intent.get("main_issue", {}).get("issue_type")
                if isinstance(focus_intent, dict)
                else None
            ),
            retry_focus_goal_type=(
                focus_intent.get("next_goal", {}).get("goal_type")
                if isinstance(focus_intent, dict)
                else None
            ),
            retry_focus_source_session_id=(
                focus_intent.get("source_session_id")
                if isinstance(focus_intent, dict)
                else None
            ),
        )

    async def _create_presentation_session(
        self,
        *,
        session_data: SessionCreate,
        current_user: User,
        requested_scenario: Scenario | None,
        agent_id_str: str | None,
        persona_id_str: str | None,
        session_policy_snapshot: dict[str, Any],
        effective_voice_policy: dict[str, Any],
    ) -> PracticeSession:
        if not session_data.presentation_id:
            raise PracticeServiceError("[PRESENTATION_ID_REQUIRED]", status_code=400)

        coach_service = PresentationCoachService(self.db)
        result = await coach_service.create_session(
            user_id=str(current_user.user_id),
            presentation_id=str(session_data.presentation_id),
        )
        if not result.is_success:
            fallback = str(result.fallback or "").strip()
            fallback_lower = fallback.lower()
            if "presentation not found or not ready" in fallback_lower:
                raise PracticeServiceError(
                    "[PRESENTATION_NOT_READY]",
                    status_code=400,
                    message="演练PPT不存在或尚未就绪",
                )
            raise PracticeServiceError(
                "[SESSION_CREATE_FAILED]",
                status_code=500,
                message=fallback or "会话创建失败",
            )

        session = result.value
        if agent_id_str:
            session.agent_id = agent_id_str
        if persona_id_str:
            session.persona_id = persona_id_str
        session.voice_mode = effective_voice_policy.get(
            "voice_mode", "stepfun_realtime"
        )
        session.voice_runtime_profile_id = effective_voice_policy.get(
            "runtime_profile_id"
        )
        session.voice_policy_snapshot = deepcopy(session_policy_snapshot)
        if requested_scenario:
            session.scenario_id = requested_scenario.scenario_id
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def _create_sales_session(
        self,
        *,
        current_user: User,
        requested_scenario: Scenario | None,
        agent_id_str: str,
        persona_id_str: str,
        session_policy_snapshot: dict[str, Any],
        effective_voice_policy: dict[str, Any],
    ) -> PracticeSession:
        scenario = requested_scenario
        if not scenario:
            scenario_result = await self.db.execute(
                select(Scenario).where(
                    Scenario.scenario_type == "sales",
                    Scenario.name == f"agent_{agent_id_str}",
                )
            )
            scenario = scenario_result.scalar_one_or_none()
            if not scenario:
                scenario = Scenario(
                    scenario_id=str(uuid.uuid4()),
                    scenario_type="sales",
                    name=f"agent_{agent_id_str}",
                    description="Sales practice with Agent Platform",
                    is_active=True,
                )
                self.db.add(scenario)
                await self.db.flush()

        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(current_user.user_id),
            scenario_id=scenario.scenario_id,
            agent_id=agent_id_str,
            persona_id=persona_id_str,
            voice_mode=effective_voice_policy.get("voice_mode", "stepfun_realtime"),
            voice_runtime_profile_id=effective_voice_policy.get("runtime_profile_id"),
            voice_policy_snapshot=deepcopy(session_policy_snapshot),
            status="preparing",
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session


class PracticeSessionLifecycleApplicationService:
    """Orchestrate lifecycle transitions, summary/evidence sync, and live-state fanout."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        lifecycle_service: SessionLifecycleService | None = None,
    ) -> None:
        self.db = db
        self.lifecycle_service = lifecycle_service or SessionLifecycleService(db)
        self.logger = logger

    async def get_session_with_scenario(
        self,
        session_id: str,
    ) -> tuple[PracticeSession | None, str | None]:
        return await self.lifecycle_service.get_session_with_scenario(session_id)

    async def run_action(
        self,
        *,
        session_id: str,
        session: PracticeSession,
        scenario_type: str | None,
        action: str,
    ) -> PracticeLifecycleActionResult:
        if action == "end":
            if not scenario_type:
                raise PracticeServiceError("[SCENARIO_NOT_FOUND]", status_code=404)
            result = await self._prepare_terminal_lifecycle_result(
                session_id=session_id,
                session=session,
                scenario_type=scenario_type,
            )
        else:
            transition = await self.lifecycle_service.transition(
                session=session,
                scenario_type=scenario_type,
                action=action,
            )
            result = PracticeLifecycleActionResult(transition=transition)

        await self.db.commit()
        await self.db.refresh(result.transition.session)

        self.logger.info(
            "practice_session_lifecycle_transition_applied",
            **_lifecycle_log_context(result.transition),
            changed=result.transition.changed,
        )
        await self.lifecycle_service.trigger_report_generation_if_needed(
            result.transition
        )
        live_handler_synced = await _sync_live_handler_after_lifecycle_transition(
            result.transition
        )
        self.logger.info(
            "practice_session_live_handler_sync",
            **_lifecycle_log_context(result.transition),
            live_handler_synced=live_handler_synced,
        )
        await _broadcast_lifecycle_events(result.transition)
        await self._close_live_handler_if_terminal(result.transition)
        return result

    async def update_session(
        self,
        *,
        session: PracticeSession,
        update_data: SessionUpdate,
    ) -> PracticeSessionUpdateResult:
        transition: SessionLifecycleTransition | None = None
        scenario_type = await self.resolve_session_scenario_type(session)

        if update_data.status:
            transition = await self.lifecycle_service.transition_by_target_status(
                session=session,
                scenario_type=scenario_type,
                target_status=update_data.status.value,
            )

        if update_data.current_page is not None:
            session.current_page = update_data.current_page

        await self.db.commit()
        await self.db.refresh(session)
        if transition:
            transition.session = session
            await self.lifecycle_service.trigger_report_generation_if_needed(transition)
            await _sync_live_handler_after_lifecycle_transition(transition)
            await _broadcast_lifecycle_events(transition)
            await _close_live_handler_if_terminal(transition)
            scenario_type = (
                str(transition.scenario_type)
                if getattr(transition, "scenario_type", None)
                else scenario_type
            )

        return PracticeSessionUpdateResult(
            session=session,
            transition=transition,
            scenario_type=scenario_type,
        )

    async def resolve_session_scenario_type(
        self, session: PracticeSession
    ) -> str | None:
        scenario_result = await self.db.execute(
            select(Scenario.scenario_type).where(
                Scenario.scenario_id == session.scenario_id
            )
        )
        scenario_type = scenario_result.scalar_one_or_none()
        return str(scenario_type) if scenario_type else None

    @staticmethod
    def build_response_payload(
        transition: SessionLifecycleTransition,
    ) -> SessionLifecycleResponse:
        start_time = transition.session.start_time or datetime.now(UTC)
        return SessionLifecycleResponse(
            session_id=transition.session.session_id,
            previous_status=transition.from_status,
            status=transition.to_status,
            ai_state=transition.ai_state,
            changed=transition.changed,
            scenario_type=transition.scenario_type,
            runtime_subject="training_scenario_runtime",
            start_time=start_time,
            end_time=transition.session.end_time,
            total_duration_seconds=transition.session.total_duration_seconds,
        )

    async def _prepare_terminal_lifecycle_result(
        self,
        *,
        session_id: str,
        session: PracticeSession,
        scenario_type: str,
    ) -> PracticeLifecycleActionResult:
        transition = await self.lifecycle_service.transition(
            session=session,
            scenario_type=scenario_type,
            action="end",
        )

        if not transition.changed:
            return PracticeLifecycleActionResult(
                transition=transition,
                snapshot=ensure_effectiveness_snapshot(session),
            )

        normalized_scenario_type = (scenario_type or "sales").lower()
        summary: Any | None = None

        if normalized_scenario_type == "presentation":
            coach_service = PresentationCoachService(self.db)
            coach_result = await coach_service.end_session(session_id, commit=False)
            if not coach_result.is_success:
                raise PracticeServiceError(
                    "[SESSION_END_FAILED]",
                    status_code=500,
                    message="会话结束失败",
                )

            session = coach_result.value
            transition.session = session
            snapshot = ensure_effectiveness_snapshot(session)
        elif normalized_scenario_type == "sales":
            evidence_source: str | None = None
            if _session_has_persisted_scores(session):
                evidence_source = "session_scores"
            else:
                evidence_source = await _sync_sales_realtime_terminal_evidence(
                    session_id=session_id,
                    session=session,
                    db=self.db,
                )
                if evidence_source is None:
                    summary_result = await summary_service.generate_summary(
                        uuid.UUID(session_id)
                    )
                    if not summary_result.is_success:
                        self.logger.warning(
                            "practice_session_summary_generation_failed",
                            session_id=session_id,
                            voice_mode=getattr(session, "voice_mode", None),
                            summary_fallback=summary_result.fallback,
                        )
                        raise PracticeServiceError(
                            "[SUMMARY_GENERATION_FAILED]",
                            status_code=500,
                            message="总结生成失败",
                        )
                    summary = summary_result.value
                    _apply_sales_summary_scores_if_missing(session, summary)
                    evidence_source = "summary"

            snapshot = ensure_effectiveness_snapshot(session)
            if evidence_source is not None:
                _log_sales_terminal_evidence_state(
                    session_id=session_id,
                    session=session,
                    snapshot=snapshot,
                    evidence_source=evidence_source,
                )

            end_result = await sales_bot_service.end_session(uuid.UUID(session_id))
            if not end_result.is_success:
                self.logger.warning(
                    "Sales bot end_session returned non-success",
                    session_id=session_id,
                    fallback=end_result.fallback,
                )
        else:
            raise PracticeServiceError("[INVALID_SCENARIO_TYPE]", status_code=400)

        return PracticeLifecycleActionResult(
            transition=transition,
            snapshot=snapshot,
            summary=summary,
        )

    async def _close_live_handler_if_terminal(
        self,
        transition: SessionLifecycleTransition,
    ) -> bool:
        if not transition.session_ended:
            return False

        closed = await get_session_manager().close_session_connection(
            str(transition.session.session_id),
            reason="Session ended",
        )
        self.logger.info(
            "practice_session_terminal_connection_close",
            **_lifecycle_log_context(transition),
            terminal_connection_closed=closed,
        )
        return closed


def ensure_effectiveness_snapshot(session: PracticeSession) -> dict[str, Any]:
    """Compatibility wrapper for the canonical session evidence snapshot path."""
    return ensure_session_evidence_snapshot(session)


def _is_true_env(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _session_has_persisted_scores(session: PracticeSession) -> bool:
    return all(
        score is not None
        for score in (
            session.logic_score,
            session.accuracy_score,
            session.completeness_score,
        )
    )


def _apply_sales_summary_scores_if_missing(
    session: PracticeSession, summary: Any
) -> None:
    if session.logic_score is None:
        session.logic_score = summary.score_confidence
    if session.accuracy_score is None:
        session.accuracy_score = summary.score_persuasion
    if session.completeness_score is None:
        session.completeness_score = summary.score_clarity


def _calculate_session_overall_score(session: PracticeSession) -> float | None:
    scores = (
        session.logic_score,
        session.accuracy_score,
        session.completeness_score,
    )
    if any(score is None for score in scores):
        return None
    return round(sum(float(score) for score in scores) / 3.0, 2)


def _build_sales_realtime_not_evaluable_snapshot(*, reason: str) -> dict[str, Any]:
    return evaluate_effectiveness_snapshot(
        metrics=build_sales_effectiveness_metrics(
            overall_score=0.0,
            logic_score=0.0,
            accuracy_score=0.0,
            completeness_score=0.0,
            duration_seconds=0,
        ),
        main_capability_passed=False,
        evaluable=False,
        not_evaluable_reason=reason,
    )


def _apply_sales_realtime_score_snapshot_to_session(
    session: PracticeSession,
    score_snapshot: dict[str, Any] | None,
) -> bool:
    normalized_score_snapshot = normalize_score_snapshot(score_snapshot)
    if normalized_score_snapshot is None:
        return False

    canonical_kernel, compatibility_readers = build_canonical_views(
        scenario_type="sales",
        surface_id="realtime",
        source_reader_id="sales_realtime_score_snapshot_v1",
        overall_score=float(normalized_score_snapshot.get("overall_score") or 0.0),
        dimension_scores=normalized_score_snapshot.get("dimension_scores"),
        methodology_context={
            "current_stage": normalized_score_snapshot.get("stage_name"),
        },
    )
    rollups = compatibility_readers.get("practice_session_rollup_fields_v1", {})

    session.logic_score = float(rollups.get("logic_score") or 0.0)
    session.accuracy_score = float(rollups.get("accuracy_score") or 0.0)
    session.completeness_score = float(rollups.get("completeness_score") or 0.0)
    session.effectiveness_snapshot = None
    return True


async def _sync_sales_realtime_terminal_evidence(
    *,
    session_id: str,
    session: PracticeSession,
    db: AsyncSession,
) -> str | None:
    if str(getattr(session, "voice_mode", "") or "").lower() != "stepfun_realtime":
        return None

    session_info = get_session_manager().sessions.get(session_id)
    live_handler = session_info.handler if session_info is not None else None
    live_score_snapshot = getattr(live_handler, "_latest_score_snapshot", None)
    if _apply_sales_realtime_score_snapshot_to_session(session, live_score_snapshot):
        return "stepfun_runtime"

    result = await db.execute(
        select(ConversationMessage.score_snapshot)
        .where(ConversationMessage.session_id == session_id)
        .where(ConversationMessage.score_snapshot.is_not(None))
        .order_by(
            ConversationMessage.turn_number.desc(),
            ConversationMessage.timestamp.desc(),
        )
        .limit(1)
    )
    row = result.first()
    persisted_score_snapshot = row[0] if row else None
    if _apply_sales_realtime_score_snapshot_to_session(
        session, persisted_score_snapshot
    ):
        return "stepfun_message_analysis"

    session.effectiveness_snapshot = _build_sales_realtime_not_evaluable_snapshot(
        reason="INSUFFICIENT_TURN_DATA"
    )
    return "stepfun_insufficient_evidence"


def _log_sales_terminal_evidence_state(
    *,
    session_id: str,
    session: PracticeSession,
    snapshot: dict[str, Any] | None,
    evidence_source: str,
) -> None:
    if not isinstance(snapshot, dict):
        return

    if bool(snapshot.get("evaluable", False)):
        logger.info(
            "practice_session_evidence_persisted",
            session_id=session_id,
            evidence_source=evidence_source,
            voice_mode=getattr(session, "voice_mode", None),
            overall_score=_calculate_session_overall_score(session),
            evaluable=True,
        )
        return

    logger.info(
        "practice_session_evidence_not_evaluable",
        session_id=session_id,
        evidence_source=evidence_source,
        voice_mode=getattr(session, "voice_mode", None),
        evaluable=False,
        not_evaluable_reason=snapshot.get("not_evaluable_reason"),
    )


def _resolve_ws_scenario(scenario_type: str | None) -> str:
    return (
        "presentation" if (scenario_type or "").lower() == "presentation" else "sales"
    )


def _build_ws_status_payload(transition: SessionLifecycleTransition) -> dict[str, Any]:
    return {
        "type": "status",
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": get_trace_id(),
        "data": {
            "session_status": transition.to_status,
            "ai_state": transition.ai_state,
        },
    }


def _build_ws_session_ended_payload(
    transition: SessionLifecycleTransition,
) -> dict[str, Any]:
    return {
        "type": "session_ended",
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": get_trace_id(),
        "data": {
            "session_id": str(transition.session.session_id),
            "session_status": transition.to_status,
        },
    }


def _lifecycle_log_context(transition: SessionLifecycleTransition) -> dict[str, Any]:
    return {
        "session_id": str(transition.session.session_id),
        "scenario_type": transition.scenario_type,
        "action": transition.action,
        "to_status": transition.to_status,
    }


async def _broadcast_lifecycle_events(transition: SessionLifecycleTransition) -> None:
    manager = get_connection_manager()
    scenario_key = _resolve_ws_scenario(getattr(transition, "scenario_type", None))
    session_id = str(transition.session.session_id)

    await manager.broadcast_to_session(
        scenario_key,
        session_id,
        _build_ws_status_payload(transition),
    )

    if transition.session_ended:
        await manager.broadcast_to_session(
            scenario_key,
            session_id,
            _build_ws_session_ended_payload(transition),
        )


async def _sync_live_handler_after_lifecycle_transition(
    transition: SessionLifecycleTransition,
) -> bool:
    session_manager = get_session_manager()
    await session_manager.update_activity(str(transition.session.session_id))
    return await session_manager.sync_lifecycle_transition(transition)


async def _close_live_handler_if_terminal(
    transition: SessionLifecycleTransition,
) -> bool:
    if not transition.session_ended:
        return False

    closed = await get_session_manager().close_session_connection(
        str(transition.session.session_id),
        reason="Session ended",
    )
    logger.info(
        "practice_session_terminal_connection_close",
        **_lifecycle_log_context(transition),
        terminal_connection_closed=closed,
    )
    return closed


__all__ = [
    "PracticeLifecycleActionResult",
    "PracticeRetryEntryAssembler",
    "PracticeRuntimeDescriptorService",
    "PracticeServiceError",
    "PracticeSessionCreateResult",
    "PracticeSessionCreateService",
    "PracticeSessionLifecycleApplicationService",
    "PracticeSessionUpdateResult",
    "ensure_effectiveness_snapshot",
]
