"""
Practice Sessions API - CRUD operations for practice sessions

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- V. Cost control - Track tokens per session

Enhanced for Agent Platform (R12):
- Support agent_id and persona_id parameters
- Validate Persona is linked to Agent
- Generate enhanced reports with dimension scores
- Session statistics endpoint

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}
- Errors use error codes like "[ERROR_CODE]"
"""

import os
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.auth.service import get_current_user
from common.db.models import PracticeSession, Scenario, User
from common.db.schemas import (
    SessionCreate,
    SessionDetail,
    SessionLifecycleRequest,
    SessionLifecycleResponse,
    SessionReport,
    SessionResponse,
    SessionUpdate,
)
from common.db.session import get_db
from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SessionLifecycleService,
)
from common.db.voice_policy_snapshot import build_voice_policy_snapshot_ref
from common.monitoring.logger import get_logger, get_trace_id
from common.websocket.base_handler import get_connection_manager
from presentation_coach.services.coach_service import PresentationCoachService
from sales_bot.services.bot_service import Persona, sales_bot_service
from sales_bot.services.summary_service import summary_service
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

logger = get_logger(__name__)

router = APIRouter()


def _is_true_env(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def success_response(data, trace_id: str = None):
    """Create unified success response"""
    return {"success": True, "data": data, "trace_id": trace_id or get_trace_id()}


def error_response(
    error_code: str,
    trace_id: str = None,
    status_code: int = 400,
    message: str | None = None,
    details: dict[str, Any] | None = None,
):
    """Create unified error response with HTTP status code."""
    payload: dict[str, Any] = {
        "success": False,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id(),
    }
    if details:
        payload["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=payload,
    )


def _is_admin_user(user: User) -> bool:
    return str(getattr(user, "role", "user")).lower() == "admin"


def _can_read_session(session: PracticeSession, user: User) -> bool:
    return _is_admin_user(user) or str(session.user_id) == str(user.user_id)


def _build_session_response(
    session: PracticeSession,
    scenario_type: str | None = None,
) -> SessionResponse:
    payload = SessionResponse.model_validate(session)
    resolved_scenario_type = scenario_type
    if not resolved_scenario_type and getattr(session, "scenario", None) is not None:
        resolved_scenario_type = getattr(session.scenario, "scenario_type", None)

    payload.scenario_type = resolved_scenario_type or "sales"
    payload.runtime_profile_id = getattr(session, "voice_runtime_profile_id", None)
    payload.voice_policy_snapshot_ref = build_voice_policy_snapshot_ref(
        payload.voice_policy_snapshot
    )
    return payload


def _build_lifecycle_response_payload(transition) -> SessionLifecycleResponse:
    start_time = transition.session.start_time or datetime.now(UTC)
    return SessionLifecycleResponse(
        session_id=transition.session.session_id,
        previous_status=transition.from_status,
        status=transition.to_status,
        ai_state=transition.ai_state,
        changed=transition.changed,
        scenario_type=transition.scenario_type,
        start_time=start_time,
        end_time=transition.session.end_time,
        total_duration_seconds=transition.session.total_duration_seconds,
    )


def _invalid_transition_response(
    *,
    exc: InvalidSessionTransitionError,
    current_status: str,
) -> JSONResponse:
    return error_response(
        "[INVALID_SESSION_TRANSITION]",
        status_code=409,
        message=exc.message,
        details={
            "current_status": current_status,
            "requested_action": exc.action,
            "expected": exc.expected,
        },
    )


def _resolve_ws_scenario(scenario_type: str | None) -> str:
    return (
        "presentation" if (scenario_type or "").lower() == "presentation" else "sales"
    )


def _build_ws_status_payload(transition) -> dict[str, Any]:
    return {
        "type": "status",
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": get_trace_id(),
        "data": {
            "session_status": transition.to_status,
            "ai_state": transition.ai_state,
        },
    }


def _build_ws_session_ended_payload(transition) -> dict[str, Any]:
    return {
        "type": "session_ended",
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": get_trace_id(),
        "data": {
            "session_id": str(transition.session.session_id),
            "session_status": transition.to_status,
        },
    }


async def _broadcast_lifecycle_events(transition) -> None:
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


@router.post("/practice/sessions", status_code=201)
async def start_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new practice session

    Supports:
    - presentation: PPT coaching session
    - sales: Sales practice with persona (sales_persona required)

    Enhanced (R12):
    - agent_id + persona_id: Enhanced session with Agent Platform
    - Validates Persona is linked to Agent
    """
    try:
        # Get scenario_type value for comparison
        scenario_type_value = (
            session_data.scenario_type.value
            if hasattr(session_data.scenario_type, "value")
            else session_data.scenario_type
        )
        voice_mode_override = session_data.voice_mode
        runtime_profile_override = (
            str(session_data.runtime_profile_id)
            if session_data.runtime_profile_id
            else None
        )
        association_override_config = None
        requested_scenario: Scenario | None = None

        if session_data.scenario_id:
            requested_scenario_result = await db.execute(
                select(Scenario).where(
                    Scenario.scenario_id == str(session_data.scenario_id)
                )
            )
            requested_scenario = requested_scenario_result.scalar_one_or_none()
            if not requested_scenario:
                return error_response("[SCENARIO_NOT_FOUND]", status_code=404)
            if requested_scenario.scenario_type != scenario_type_value:
                return error_response("[SCENARIO_TYPE_MISMATCH]", status_code=400)
            if not requested_scenario.is_active:
                return error_response("[SCENARIO_INACTIVE]", status_code=400)

        # Validate Agent-Persona association if both provided (R12.2)
        agent_id_str = str(session_data.agent_id) if session_data.agent_id else None
        persona_id_str = (
            str(session_data.persona_id) if session_data.persona_id else None
        )

        # Require enhanced mode identifiers to be provided as a pair.
        # Prevents silently falling back to legacy flow when only one is passed.
        if bool(agent_id_str) != bool(persona_id_str):
            return error_response("[AGENT_PERSONA_PAIR_REQUIRED]", status_code=400)
        if (
            scenario_type_value == "presentation"
            and _is_true_env("PRESENTATION_REQUIRE_AGENT_PERSONA", "true")
            and not (agent_id_str and persona_id_str)
        ):
            return error_response("[AGENT_PERSONA_PAIR_REQUIRED]", status_code=400)

        if agent_id_str and persona_id_str:
            from agent.models import Agent, AgentPersona
            from agent.models import Persona as AgentPersonaModel

            # Check Agent exists and is published
            agent_result = await db.execute(
                select(Agent).where(Agent.id == agent_id_str)
            )
            agent = agent_result.scalar_one_or_none()
            if not agent:
                return error_response("[AGENT_NOT_FOUND]", status_code=404)
            if agent.status == "archived":
                return error_response("[AGENT_ARCHIVED]", status_code=400)
            if agent.status != "published":
                return error_response("[AGENT_NOT_PUBLISHED]", status_code=400)

            # Check Persona exists
            persona_result = await db.execute(
                select(AgentPersonaModel).where(AgentPersonaModel.id == persona_id_str)
            )
            persona_obj = persona_result.scalar_one_or_none()
            if not persona_obj:
                return error_response("[PERSONA_NOT_FOUND]", status_code=404)
            if persona_obj.status != "active":
                return error_response("[PERSONA_INACTIVE]", status_code=400)

            # Check Persona is linked to Agent (R12.2)
            link_result = await db.execute(
                select(AgentPersona).where(
                    AgentPersona.agent_id == agent_id_str,
                    AgentPersona.persona_id == persona_id_str,
                )
            )
            link = link_result.scalar_one_or_none()
            if not link:
                return error_response("[PERSONA_NOT_LINKED_TO_AGENT]", status_code=400)
            association_override_config = link.override_config or None

        runtime_policy_service = VoiceRuntimePolicyService(db)
        effective_voice_policy = await runtime_policy_service.resolve_effective_policy(
            agent_id=agent_id_str,
            persona_id=persona_id_str,
            voice_mode_override=voice_mode_override,
            runtime_profile_override=runtime_profile_override,
        )
        if association_override_config:
            effective_voice_policy = {
                **effective_voice_policy,
                "agent_persona_override_config": association_override_config,
            }
        session_policy_snapshot = deepcopy(effective_voice_policy)
        effective_voice_mode = effective_voice_policy.get("voice_mode", "legacy")
        effective_runtime_profile_id = effective_voice_policy.get("runtime_profile_id")

        if scenario_type_value == "presentation":
            coach_service = PresentationCoachService(db)

            result = await coach_service.create_session(
                user_id=str(current_user.user_id),
                presentation_id=str(session_data.presentation_id),
            )

            if not result.is_success:
                fallback = str(result.fallback or "").strip()
                fallback_lower = fallback.lower()
                if "presentation not found or not ready" in fallback_lower:
                    return error_response(
                        "[PRESENTATION_NOT_READY]",
                        status_code=400,
                        message="演练PPT不存在或尚未就绪",
                    )
                return error_response(
                    "[SESSION_CREATE_FAILED]",
                    status_code=500,
                    message=fallback or "会话创建失败",
                )

            session = result.value

            # Update with agent/persona if provided
            if agent_id_str:
                session.agent_id = agent_id_str
            if persona_id_str:
                session.persona_id = persona_id_str
            session.voice_mode = effective_voice_mode
            session.voice_runtime_profile_id = effective_runtime_profile_id
            session.voice_policy_snapshot = deepcopy(session_policy_snapshot)
            if requested_scenario:
                session.scenario_id = requested_scenario.scenario_id
            await db.commit()
            await db.refresh(session)

        elif scenario_type_value == "sales":
            # Sales bot session - support both legacy and enhanced modes

            # Enhanced mode: use agent_id + persona_id
            if agent_id_str and persona_id_str:
                scenario = requested_scenario
                if not scenario:
                    # Keep compatibility with clients that do not pass scenario_id yet.
                    scenario_result = await db.execute(
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
                        db.add(scenario)
                        await db.flush()

                # Create practice session with agent/persona
                session = PracticeSession(
                    session_id=str(uuid.uuid4()),
                    user_id=str(current_user.user_id),
                    scenario_id=scenario.scenario_id,
                    agent_id=agent_id_str,
                    persona_id=persona_id_str,
                    voice_mode=effective_voice_mode,
                    voice_runtime_profile_id=effective_runtime_profile_id,
                    voice_policy_snapshot=deepcopy(session_policy_snapshot),
                    status="preparing",
                )
                db.add(session)
                await db.commit()
                await db.refresh(session)

            else:
                # Legacy mode: use sales_persona
                if not session_data.sales_persona:
                    return error_response("[SALES_PERSONA_REQUIRED]", status_code=400)

                # Validate persona
                try:
                    persona = Persona(session_data.sales_persona)
                except ValueError:
                    return error_response("[INVALID_PERSONA]", status_code=400)

                scenario = requested_scenario
                if not scenario:
                    # Find or create sales scenario
                    scenario_result = await db.execute(
                        select(Scenario).where(
                            Scenario.scenario_type == "sales",
                            Scenario.name == f"sales_{session_data.sales_persona}",
                        )
                    )
                    scenario = scenario_result.scalar_one_or_none()

                    if not scenario:
                        scenario = Scenario(
                            scenario_id=str(uuid.uuid4()),
                            scenario_type="sales",
                            name=f"sales_{session_data.sales_persona}",
                            description=f"Sales practice with {session_data.sales_persona} persona",
                            is_active=True,
                        )
                        db.add(scenario)
                        await db.flush()

                # Create bot session
                user_id_uuid = uuid.UUID(str(current_user.user_id))
                scenario_id_uuid = uuid.UUID(scenario.scenario_id)

                result = await sales_bot_service.create_session(
                    user_id=user_id_uuid, persona=persona, scenario_id=scenario_id_uuid
                )

                if not result.is_success:
                    return error_response(
                        "[BOT_SESSION_CREATE_FAILED]", status_code=500
                    )

                # Create practice session record
                session = PracticeSession(
                    session_id=str(result.value),
                    user_id=str(current_user.user_id),
                    scenario_id=scenario.scenario_id,
                    voice_mode=effective_voice_mode,
                    voice_runtime_profile_id=effective_runtime_profile_id,
                    voice_policy_snapshot=deepcopy(session_policy_snapshot),
                    status="preparing",
                )

                db.add(session)
                await db.commit()
                await db.refresh(session)

        else:
            return error_response("[INVALID_SCENARIO_TYPE]", status_code=400)

        response_payload = success_response(
            _build_session_response(session, scenario_type=scenario_type_value)
        )
        response_payload["session_id"] = str(session.session_id)
        return response_payload

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to start session: {str(e)}")
        return error_response("[SESSION_CREATE_FAILED]", status_code=500)


@router.get("/practice/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get session details"""
    result = await db.execute(
        select(PracticeSession, Scenario.scenario_type)
        .join(
            Scenario, Scenario.scenario_id == PracticeSession.scenario_id, isouter=True
        )
        .where(PracticeSession.session_id == session_id)
    )
    row = result.first()
    session = row[0] if row else None
    scenario_type = str(row[1]) if row and row[1] else None

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership or admin access
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # Avoid async lazy-loading issues on relationship fields when serializing ORM model
    session_base = _build_session_response(session, scenario_type=scenario_type)
    session_detail = SessionDetail.model_validate(session_base.model_dump())
    return success_response(session_detail)


@router.post("/practice/sessions/{session_id}/lifecycle")
async def control_session_lifecycle(
    session_id: str,
    payload: SessionLifecycleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Control session lifecycle using explicit start/pause/resume/end actions."""
    lifecycle_service = SessionLifecycleService(db)
    session, scenario_type = await lifecycle_service.get_session_with_scenario(
        session_id
    )

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    try:
        transition = await lifecycle_service.transition(
            session=session,
            scenario_type=scenario_type,
            action=payload.action.value,
        )
    except InvalidSessionTransitionError as exc:
        await db.rollback()
        return _invalid_transition_response(
            exc=exc,
            current_status=exc.from_status,
        )

    await db.commit()
    await db.refresh(session)
    transition.session = session
    await _broadcast_lifecycle_events(transition)

    return success_response(_build_lifecycle_response_payload(transition))


@router.patch("/practice/sessions/{session_id}")
async def update_session(
    session_id: str,
    update_data: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update session status"""
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    lifecycle_service = SessionLifecycleService(db)

    transition = None

    # Update fields
    if update_data.status:
        scenario_result = await db.execute(
            select(Scenario.scenario_type).where(
                Scenario.scenario_id == session.scenario_id
            )
        )
        scenario_type = scenario_result.scalar_one_or_none()
        try:
            transition = await lifecycle_service.transition_by_target_status(
                session=session,
                scenario_type=str(scenario_type) if scenario_type else None,
                target_status=update_data.status.value,
            )
        except InvalidSessionTransitionError as exc:
            await db.rollback()
            return _invalid_transition_response(
                exc=exc,
                current_status=exc.from_status,
            )

    if update_data.current_page is not None:
        session.current_page = update_data.current_page

    await db.commit()
    await db.refresh(session)
    if transition:
        transition.session = session
        await _broadcast_lifecycle_events(transition)

    scenario_type_value = None
    if transition and getattr(transition, "scenario_type", None):
        scenario_type_value = str(transition.scenario_type)
    else:
        scenario_type_result = await db.execute(
            select(Scenario.scenario_type).where(
                Scenario.scenario_id == session.scenario_id
            )
        )
        scenario_type_value = scenario_type_result.scalar_one_or_none()

    return success_response(
        _build_session_response(
            session,
            scenario_type=str(scenario_type_value) if scenario_type_value else None,
        )
    )


@router.delete("/practice/sessions/{session_id}")
async def end_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    End session and generate report

    Supports both presentation and sales_bot sessions
    """
    # Get session to determine type
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership or admin access
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # Check scenario type from scenario
    scenario_result = await db.execute(
        select(Scenario).where(Scenario.scenario_id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()

    if not scenario:
        return error_response("[SCENARIO_NOT_FOUND]", status_code=404)

    lifecycle_service = SessionLifecycleService(db)
    try:
        transition = await lifecycle_service.transition(
            session=session,
            scenario_type=scenario.scenario_type,
            action="end",
        )
    except InvalidSessionTransitionError as exc:
        await db.rollback()
        return _invalid_transition_response(
            exc=exc,
            current_status=exc.from_status,
        )

    await db.commit()
    await db.refresh(session)
    transition.session = session
    await _broadcast_lifecycle_events(transition)

    if scenario.scenario_type == "presentation":
        # PPT coaching session
        coach_service = PresentationCoachService(db)
        result = await coach_service.end_session(session_id)

        if not result.is_success:
            return error_response("[SESSION_END_FAILED]", status_code=500)

        session = result.value

        # Generate report
        report = SessionReport(
            session_id=session.session_id,
            logic_score=session.logic_score or 0,
            accuracy_score=session.accuracy_score or 0,
            completeness_score=session.completeness_score or 0,
            overall_score=(
                (session.logic_score or 0)
                + (session.accuracy_score or 0)
                + (session.completeness_score or 0)
            )
            / 3,
            suggestions=["Great practice! Keep working on your presentation skills."],
            audio_url=session.audio_url,
            transcript_url=session.transcript_url,
            voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
                session.voice_policy_snapshot
            ),
        )

    elif scenario.scenario_type == "sales":
        # Sales bot session - generate summary
        summary_result = await summary_service.generate_summary(uuid.UUID(session_id))

        if not summary_result.is_success:
            return error_response("[SUMMARY_GENERATION_FAILED]", status_code=500)

        summary = summary_result.value

        # End bot session
        await sales_bot_service.end_session(uuid.UUID(session_id))

        # Generate comprehensive report using AI evaluation
        try:
            from common.ai.llm_service import LLMService
            from evaluation.services.comprehensive_report import (
                ComprehensiveReportService,
            )
            from evaluation.services.staged_evaluation import StagedEvaluationService
            from prompt_templates.service import PromptTemplateService

            llm_service = LLMService()
            prompt_service = PromptTemplateService(db)
            staged_eval_service = StagedEvaluationService(
                db_session=db, prompt_service=prompt_service, llm_service=llm_service
            )
            report_service = ComprehensiveReportService(
                db_session=db,
                staged_eval_service=staged_eval_service,
                prompt_service=prompt_service,
                llm_service=llm_service,
            )
            comprehensive_result = await report_service.generate_report(
                session_id, scenario_type="sales"
            )
            if comprehensive_result.is_success:
                logger.info(f"Comprehensive report generated for session {session_id}")
            else:
                logger.warning(
                    f"Comprehensive report generation failed: {comprehensive_result.fallback}"
                )
        except (RuntimeError, ValueError, OSError, ImportError) as e:
            logger.warning(f"Comprehensive report generation skipped: {str(e)}")

        # Generate basic report from summary
        report = SessionReport(
            session_id=session_id,
            logic_score=summary.score_confidence,
            accuracy_score=summary.score_persuasion,
            completeness_score=summary.score_clarity,
            overall_score=(
                summary.score_confidence
                + summary.score_persuasion
                + summary.score_clarity
            )
            / 3,
            suggestions=[
                *summary.strengths,
                f"Improvement: {summary.actionable_feedback}",
            ],
            audio_url=None,
            transcript_url=None,
            voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
                session.voice_policy_snapshot
            ),
        )

    else:
        return error_response("[INVALID_SCENARIO_TYPE]", status_code=400)

    return success_response(report)


@router.get("/practice/sessions/{session_id}/report")
async def get_session_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get session report with scores"""
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership or admin access
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # Generate report
    report = SessionReport(
        session_id=session.session_id,
        logic_score=session.logic_score or 0,
        accuracy_score=session.accuracy_score or 0,
        completeness_score=session.completeness_score or 0,
        overall_score=(
            (session.logic_score or 0)
            + (session.accuracy_score or 0)
            + (session.completeness_score or 0)
        )
        / 3,
        suggestions=["Review your performance and practice again!"],
        audio_url=session.audio_url,
        transcript_url=session.transcript_url,
        voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
            session.voice_policy_snapshot
        ),
    )

    return success_response(report)


@router.get("/practice/sessions/{session_id}/knowledge-check")
async def get_session_knowledge_check(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Knowledge grounding diagnostics for one session.

    Used by report page to verify whether internal knowledge retrieval
    was actually triggered and produced hits.
    """
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    snapshot = (
        session.voice_policy_snapshot
        if isinstance(session.voice_policy_snapshot, dict)
        else {}
    )
    tool_policy = snapshot.get("tool_policy")
    if not isinstance(tool_policy, dict):
        tool_policy = {}

    network_access_mode = str(tool_policy.get("network_access_mode") or "off").lower()
    enforcement_level = str(tool_policy.get("enforcement_level") or "strict").lower()
    allow_web_search_without_kb = bool(
        tool_policy.get("allow_web_search_without_kb", False)
    )
    require_kb_grounding = bool(tool_policy.get("require_kb_grounding", False))
    internal_retrieval_enabled = bool(
        tool_policy.get("enable_internal_retrieval", False)
    )
    web_search_enabled = bool(tool_policy.get("enable_web_search", False))

    knowledge_base_ids = snapshot.get("knowledge_base_ids")
    if not isinstance(knowledge_base_ids, list):
        knowledge_base_ids = []
    knowledge_base_ids = [str(kb_id) for kb_id in knowledge_base_ids if kb_id]
    kb_bound = bool(knowledge_base_ids)

    preview_tools = VoiceRuntimePolicyService(db).build_stepfun_tools(snapshot)
    effective_tool_types = [
        str(tool.get("type") or "") for tool in preview_tools if isinstance(tool, dict)
    ]

    runtime_metrics = snapshot.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        runtime_metrics = {}
    knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
    if not isinstance(knowledge_metrics, dict):
        knowledge_metrics = {}

    attempt_count = int(knowledge_metrics.get("attempt_count") or 0)
    hit_query_count = int(knowledge_metrics.get("hit_query_count") or 0)
    total_results = int(knowledge_metrics.get("total_results") or 0)
    last_result_count = int(knowledge_metrics.get("last_result_count") or 0)
    hit_rate = float(knowledge_metrics.get("hit_rate") or 0.0)

    last_status = str(knowledge_metrics.get("last_status") or "not_triggered")
    last_error = str(knowledge_metrics.get("last_error") or "")
    kb_lock_required = require_kb_grounding
    kb_lock_block_count = int(knowledge_metrics.get("kb_lock_block_count") or 0)
    kb_lock_last_status = str(
        knowledge_metrics.get("kb_lock_last_status") or "not_required"
    )
    kb_lock_status = "pass"
    if kb_lock_required:
        if not kb_bound:
            kb_lock_status = "blocked_no_kb"
        elif kb_lock_last_status and kb_lock_last_status != "not_required":
            kb_lock_status = kb_lock_last_status
        elif last_status == "kb_not_ready" or "[KB_NOT_READY]" in last_error:
            kb_lock_status = "blocked_not_ready"
        elif last_status == "search_failed" or last_error:
            kb_lock_status = "blocked_search_failed"
        elif attempt_count > 0 and hit_query_count <= 0:
            kb_lock_status = "blocked_empty"

    if not internal_retrieval_enabled:
        status = "disabled"
        summary = "内部知识检索未启用"
    elif not knowledge_base_ids:
        status = "no_knowledge_base"
        summary = "当前会话未绑定知识库"
    elif last_status == "kb_not_ready" or "[KB_NOT_READY]" in last_error:
        status = "kb_not_ready"
        summary = "知识库文档尚未处理完成"
    elif attempt_count == 0:
        status = "not_triggered"
        summary = "本次对话尚未触发知识检索"
    elif hit_query_count > 0:
        status = "hit"
        summary = "知识检索已触发并命中知识库"
    else:
        status = "miss"
        summary = "知识检索已触发，但本次未命中有效内容"

    diagnostics = {
        "session_id": str(session.session_id),
        "voice_mode": session.voice_mode,
        "status": status,
        "summary": summary,
        "internal_retrieval_enabled": internal_retrieval_enabled,
        "web_search_enabled": web_search_enabled,
        "network_access_mode": network_access_mode,
        "enforcement_level": enforcement_level,
        "allow_web_search_without_kb": allow_web_search_without_kb,
        "require_kb_grounding": require_kb_grounding,
        "kb_bound": kb_bound,
        "effective_tool_types": effective_tool_types,
        "instruction_contract_hash": str(
            snapshot.get("instruction_contract_hash") or ""
        ),
        "knowledge_base_ids": knowledge_base_ids,
        "knowledge_base_count": len(knowledge_base_ids),
        "attempt_count": attempt_count,
        "hit_query_count": hit_query_count,
        "total_results": total_results,
        "hit_rate": round(hit_rate, 4),
        "last_query": str(knowledge_metrics.get("last_query") or ""),
        "last_result_count": last_result_count,
        "last_status": last_status,
        "last_top_k": knowledge_metrics.get("last_top_k"),
        "last_similarity_threshold": knowledge_metrics.get("last_similarity_threshold"),
        "last_error": last_error,
        "last_retrieval_mode": str(knowledge_metrics.get("last_retrieval_mode") or ""),
        "recent_queries": knowledge_metrics.get("recent_queries")
        if isinstance(knowledge_metrics.get("recent_queries"), list)
        else [],
        "updated_at": knowledge_metrics.get("updated_at"),
        "kb_lock_required": kb_lock_required,
        "kb_lock_status": kb_lock_status,
        "kb_lock_block_count": kb_lock_block_count,
        "kb_lock_last_status": kb_lock_last_status,
        "kb_lock_updated_at": knowledge_metrics.get("kb_lock_updated_at"),
    }

    return success_response(diagnostics)


@router.get("/practice/history")
async def get_practice_history(
    scenario_type: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's practice history with pagination and summary metrics."""
    query = (
        select(PracticeSession)
        .options(
            selectinload(PracticeSession.scenario),
            selectinload(PracticeSession.agent),
            selectinload(PracticeSession.persona),
        )
        .where(PracticeSession.user_id == current_user.user_id)
    )

    if scenario_type:
        query = query.join(Scenario).where(Scenario.scenario_type == scenario_type)

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(PracticeSession.start_time.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    sessions = result.scalars().all()

    items = []
    for session in sessions:
        logic_score = session.logic_score or 0
        accuracy_score = session.accuracy_score or 0
        completeness_score = session.completeness_score or 0

        has_any_score = any(
            value is not None
            for value in [
                session.logic_score,
                session.accuracy_score,
                session.completeness_score,
            ]
        )
        overall_score = (
            round((logic_score + accuracy_score + completeness_score) / 3, 2)
            if has_any_score
            else 0
        )

        duration_seconds = session.total_duration_seconds
        if duration_seconds is None and session.end_time and session.start_time:
            duration_seconds = int(
                (session.end_time - session.start_time).total_seconds()
            )

        scenario_value = (
            getattr(session.scenario, "scenario_type", None) or scenario_type or "sales"
        )
        title = (
            getattr(session.agent, "name", None)
            or getattr(session.scenario, "name", None)
            or "练习记录"
        )

        items.append(
            {
                "session_id": str(session.session_id),
                "scenario_id": str(session.scenario_id),
                "scenario_type": scenario_value,
                "status": session.status,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "logic_score": logic_score,
                "accuracy_score": accuracy_score,
                "completeness_score": completeness_score,
                "overall_score": overall_score,
                "total_duration_seconds": duration_seconds or 0,
                "duration_seconds": duration_seconds or 0,
                "agent_name": getattr(session.agent, "name", None),
                "persona_name": getattr(session.persona, "name", None),
                "title": title,
            }
        )

    return success_response(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": (page * page_size) < total,
        }
    )


# ========== Enhanced Session Endpoints (R12) ==========


@router.get("/sessions/stats")
async def get_session_stats(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get user session statistics (R12.4)

    Returns:
    - total_sessions: Total number of sessions
    - weekly_sessions: Sessions in the last 7 days
    - average_score: Average overall score
    - completed_sessions: Number of completed sessions
    - total_practice_minutes: Total practice time in minutes
    """
    from common.db.schemas import SessionStats

    user_id = str(current_user.user_id)

    # Total sessions
    total_stmt = select(func.count()).where(PracticeSession.user_id == user_id)
    total_sessions = (await db.execute(total_stmt)).scalar() or 0

    # Weekly sessions (last 7 days)
    week_ago = datetime.now(UTC) - timedelta(days=7)
    weekly_stmt = select(func.count()).where(
        PracticeSession.user_id == user_id, PracticeSession.start_time >= week_ago
    )
    weekly_sessions = (await db.execute(weekly_stmt)).scalar() or 0

    # Completed sessions
    completed_stmt = select(func.count()).where(
        PracticeSession.user_id == user_id, PracticeSession.status == "completed"
    )
    completed_sessions = (await db.execute(completed_stmt)).scalar() or 0

    # Average score (from completed sessions with scores)
    avg_stmt = select(
        func.avg(
            (
                func.coalesce(PracticeSession.logic_score, 0)
                + func.coalesce(PracticeSession.accuracy_score, 0)
                + func.coalesce(PracticeSession.completeness_score, 0)
            )
            / 3
        )
    ).where(PracticeSession.user_id == user_id, PracticeSession.status == "completed")
    average_score = (await db.execute(avg_stmt)).scalar() or 0.0

    # Total practice minutes
    duration_stmt = select(func.sum(PracticeSession.total_duration_seconds)).where(
        PracticeSession.user_id == user_id
    )
    total_seconds = (await db.execute(duration_stmt)).scalar() or 0
    total_practice_minutes = total_seconds // 60

    stats = SessionStats(
        total_sessions=total_sessions,
        weekly_sessions=weekly_sessions,
        average_score=round(average_score, 1),
        completed_sessions=completed_sessions,
        total_practice_minutes=total_practice_minutes,
    )

    return success_response(stats)


@router.get("/sessions/{session_id}/enhanced-report")
async def get_enhanced_session_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get enhanced session report with dimension scores (R12.3)

    Returns detailed report including:
    - Dimension scores with weights
    - Strengths and improvements
    - Suggestions
    - Highlights from the session
    """
    from common.conversation.models import ConversationMessage
    from common.db.schemas import (
        DimensionScore,
        EnhancedSessionReport,
        SessionHighlight,
    )

    # Get session
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership or admin access
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # Check session is completed
    if session.status != "completed":
        return error_response("[SESSION_NOT_COMPLETED]", status_code=400)

    # Get agent and persona names if available
    agent_name = None
    persona_name = None

    if session.agent_id:
        from agent.models import Agent

        agent_result = await db.execute(
            select(Agent).where(Agent.id == session.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if agent:
            agent_name = agent.name

    if session.persona_id:
        from agent.models import Persona

        persona_result = await db.execute(
            select(Persona).where(Persona.id == session.persona_id)
        )
        persona = persona_result.scalar_one_or_none()
        if persona:
            persona_name = persona.name

    # Get conversation messages for highlights
    messages_result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.is_highlight,
        )
        .order_by(ConversationMessage.turn_number)
    )
    highlight_messages = messages_result.scalars().all()

    # Build highlights
    highlights = []
    for msg in highlight_messages:
        highlights.append(
            SessionHighlight(
                message_id=str(msg.id),
                turn_number=msg.turn_number,
                highlight_type=msg.highlight_type or "neutral",
                reason=msg.highlight_reason or "",
                content=msg.content[:200] if msg.content else "",
            )
        )

    # Calculate dimension scores from session data
    dimension_scores = []

    # Use existing scores if available
    if session.logic_score is not None:
        dimension_scores.append(
            DimensionScore(name="逻辑性", score=session.logic_score, weight=0.33)
        )
    if session.accuracy_score is not None:
        dimension_scores.append(
            DimensionScore(name="准确性", score=session.accuracy_score, weight=0.33)
        )
    if session.completeness_score is not None:
        dimension_scores.append(
            DimensionScore(name="完整性", score=session.completeness_score, weight=0.34)
        )

    # If no dimension scores, try to get from last message's score_snapshot
    if not dimension_scores:
        last_msg_result = await db.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.session_id == session_id,
                ConversationMessage.score_snapshot.isnot(None),
            )
            .order_by(ConversationMessage.turn_number.desc())
            .limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()

        if last_msg and last_msg.score_snapshot:
            snapshot = last_msg.score_snapshot
            if isinstance(snapshot, dict) and "dimensions" in snapshot:
                for dim in snapshot["dimensions"]:
                    dimension_scores.append(
                        DimensionScore(
                            name=dim.get("name", ""),
                            score=dim.get("score", 0),
                            weight=dim.get("weight", 0.2),
                        )
                    )

    # Calculate overall score
    if dimension_scores:
        total_weight = sum(d.weight for d in dimension_scores)
        overall_score = (
            sum(d.score * d.weight for d in dimension_scores) / total_weight
            if total_weight > 0
            else 0
        )
    else:
        overall_score = (
            (session.logic_score or 0)
            + (session.accuracy_score or 0)
            + (session.completeness_score or 0)
        ) / 3

    # Generate strengths and improvements based on scores
    strengths = []
    improvements = []

    for dim in dimension_scores:
        if dim.score >= 80:
            strengths.append(f"{dim.name}表现优秀")
        elif dim.score < 60:
            improvements.append(f"建议加强{dim.name}方面的练习")

    # Default suggestions
    suggestions = [
        "继续保持练习频率",
        "关注反馈中的改进建议",
        "尝试不同难度的角色进行练习",
    ]

    # Calculate duration
    duration_seconds = None
    if session.end_time and session.start_time:
        duration_seconds = int((session.end_time - session.start_time).total_seconds())
    elif session.total_duration_seconds:
        duration_seconds = session.total_duration_seconds

    # Count total turns
    turn_count_result = await db.execute(
        select(func.count()).where(ConversationMessage.session_id == session_id)
    )
    total_turns = (
        turn_count_result.scalar() or 0
    ) // 2  # Divide by 2 for user turns only

    report = EnhancedSessionReport(
        session_id=uuid.UUID(session_id),
        overall_score=round(overall_score, 1),
        dimension_scores=dimension_scores,
        strengths=strengths if strengths else ["继续保持良好的练习习惯"],
        improvements=improvements if improvements else ["整体表现良好"],
        suggestions=suggestions,
        highlights=highlights,
        total_turns=total_turns,
        duration_seconds=duration_seconds,
        agent_name=agent_name,
        persona_name=persona_name,
        voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
            session.voice_policy_snapshot
        ),
    )

    return success_response(report)


@router.get("/practice/sessions/{session_id}/comprehensive-report")
async def get_comprehensive_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive evaluation report for a session (Story 3.1).

    Returns detailed report with dimension scores, stage summaries,
    key strengths, improvements, and recommendations.
    """
    from common.ai.llm_service import LLMService
    from evaluation.services.comprehensive_report import ComprehensiveReportService
    from evaluation.services.staged_evaluation import StagedEvaluationService
    from prompt_templates.service import PromptTemplateService

    # Get session
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership or admin access
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # Check report generation status
    if session.report_status == "pending":
        return success_response(
            {"status": "pending", "message": "报告生成中，请稍后再试"}
        )

    if session.report_status == "processing":
        return success_response({"status": "processing", "message": "报告正在生成中"})

    if session.report_status == "failed":
        return success_response(
            {
                "status": "failed",
                "message": "报告生成失败",
                "error": session.report_error,
            }
        )

    # Get comprehensive report
    try:
        llm_service = LLMService()
        prompt_service = PromptTemplateService(db)
        staged_eval_service = StagedEvaluationService(
            db_session=db, prompt_service=prompt_service, llm_service=llm_service
        )
        report_service = ComprehensiveReportService(
            db_session=db,
            staged_eval_service=staged_eval_service,
            prompt_service=prompt_service,
            llm_service=llm_service,
        )

        report_result = await report_service.get_report(session_id)

        if not report_result.is_success:
            return error_response("[REPORT_NOT_FOUND]", status_code=404)

        report = report_result.value

        return success_response(
            {
                "status": "completed",
                "session_id": report.session_id,
                "generated_at": report.generated_at.isoformat()
                if report.generated_at
                else None,
                "overall_score": report.overall_score,
                "dimension_scores": [
                    {
                        "name": ds.name,
                        "score": ds.score,
                        "weight": ds.weight,
                        "description": ds.description,
                    }
                    for ds in report.dimension_scores
                ],
                "stage_summaries": report.stage_summaries,
                "key_strengths": report.key_strengths,
                "key_improvements": report.key_improvements,
                "detailed_feedback": report.detailed_feedback,
                "recommendations": report.recommendations,
            }
        )

    except Exception as e:
        logger.error(f"Failed to get comprehensive report: {str(e)}")
        return error_response("[REPORT_RETRIEVAL_FAILED]", status_code=500)


@router.get("/practice/sessions/{session_id}/report-status")
async def get_report_generation_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get report generation status for a session (Story 3.1).

    Returns the current status of report generation:
    - pending: Report not yet generated
    - processing: Report is being generated
    - completed: Report generated successfully
    - failed: Report generation failed
    """
    # Get session
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership or admin access
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    return success_response(
        {
            "session_id": session_id,
            "report_status": session.report_status,
            "report_generated_at": session.report_generated_at.isoformat()
            if session.report_generated_at
            else None,
            "report_error": session.report_error,
        }
    )
