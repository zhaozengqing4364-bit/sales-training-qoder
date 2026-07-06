from __future__ import annotations

from copy import deepcopy

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from common.services.practice_session_ports import (
    PracticeSessionCreateContext,
    PracticeSessionPortError,
    PracticeSessionTerminalContext,
    PracticeSessionTerminalResult,
    apply_registered_practice_session_snapshot,
    register_practice_session_creator,
    register_practice_session_terminal_handler,
)
from common.services.practice_session_service import ensure_effectiveness_snapshot
from common.services.session_runtime_state_service import SessionRuntimeStateService
from presentation_coach.services.coach_service import PresentationCoachService


async def create_presentation_practice_session(
    db: AsyncSession,
    context: PracticeSessionCreateContext,
) -> PracticeSession:
    session_data = context.session_data
    if not session_data.presentation_id:
        raise PracticeSessionPortError("[PRESENTATION_ID_REQUIRED]", status_code=400)

    coach_service = PresentationCoachService(db)
    result = await coach_service.create_session(
        user_id=str(context.current_user.user_id),
        presentation_id=str(session_data.presentation_id),
    )
    if not result.is_success:
        fallback = str(result.fallback or "").strip()
        fallback_lower = fallback.lower()
        if "presentation not found or not ready" in fallback_lower:
            raise PracticeSessionPortError(
                "[PRESENTATION_NOT_READY]",
                status_code=400,
                message="演练PPT不存在或尚未就绪",
            )
        raise PracticeSessionPortError(
            "[SESSION_CREATE_FAILED]",
            status_code=500,
            message=fallback or "会话创建失败",
        )

    session = result.value
    if session is None:
        raise PracticeSessionPortError(
            "[SESSION_CREATE_FAILED]",
            status_code=500,
            message="会话创建失败",
        )
    if context.agent_id_str:
        setattr(session, "agent_id", context.agent_id_str)
    if context.persona_id_str:
        setattr(session, "persona_id", context.persona_id_str)
    setattr(
        session,
        "voice_mode",
        str(context.effective_voice_policy.get("voice_mode", "stepfun_realtime")),
    )
    setattr(
        session,
        "voice_runtime_profile_id",
        context.effective_voice_policy.get("runtime_profile_id"),
    )
    setattr(
        session,
        "voice_policy_snapshot",
        deepcopy(context.session_policy_snapshot),
    )
    if context.requested_scenario:
        setattr(session, "scenario_id", context.requested_scenario.scenario_id)
    try:
        await apply_registered_practice_session_snapshot(
            db,
            session=session,
            session_data=session_data,
            scenario_type_value="presentation",
            current_user=context.current_user,
        )
    except PracticeSessionPortError:
        await db.delete(session)
        await db.commit()
        raise
    await db.commit()
    await db.refresh(session)
    await SessionRuntimeStateService(db).initialize_on_create(
        str(session.session_id),
        has_runtime_snapshot=bool(session.voice_policy_snapshot),
        source="practice_session_create",
    )
    return session


async def finish_presentation_practice_session(
    db: AsyncSession,
    context: PracticeSessionTerminalContext,
) -> PracticeSessionTerminalResult:
    coach_service = PresentationCoachService(db)
    coach_result = await coach_service.end_session(context.session_id, commit=False)
    if not coach_result.is_success:
        raise PracticeSessionPortError(
            "[SESSION_END_FAILED]",
            status_code=500,
            message="会话结束失败",
        )

    session = coach_result.value
    if session is None:
        raise PracticeSessionPortError(
            "[SESSION_END_FAILED]",
            status_code=500,
            message="会话结束失败",
        )
    snapshot = ensure_effectiveness_snapshot(session)
    return PracticeSessionTerminalResult(session=session, snapshot=snapshot)


def register_presentation_coach_practice_session_contributor() -> None:
    register_practice_session_creator(
        "presentation",
        create_presentation_practice_session,
    )
    register_practice_session_terminal_handler(
        "presentation",
        finish_presentation_practice_session,
    )
