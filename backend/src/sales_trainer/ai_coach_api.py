from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.ai_coach_chat_schemas import (
    AiCoachChatEventAnswerSubmit,
    AiCoachChatMessageCreate,
    AiCoachChatSessionCreate,
)
from sales_trainer.schemas import (
    AI_COACH_INTERACTION_SCHEMA_VERSION,
    AiCoachAnswerPayloadV1,
    AiCoachInteractionPublicV1,
    AiCoachSessionCreate,
    AiCoachTurnPublicV1,
    AiCoachTurnSubmit,
    AiCoachTurnSubmitV1,
)
from sales_trainer.services.ai_coach_chat_service import (
    AiCoachChatService,
    AiCoachChatServiceError,
)
from sales_trainer.services.ai_coach_chat_stream_service import (
    AiCoachChatStreamService,
)
from sales_trainer.services.ai_coach_session_service import (
    AiCoachSessionService,
    AiCoachSessionServiceError,
)
from sales_trainer.services.learner_public_projection import (
    assert_learner_public_payload,
)

router = APIRouter(
    prefix="/newcomer-training/ai-coach",
    tags=["newcomer-training-ai-coach"],
)

_LEARNER_FACING_PUBLIC_SUBTREES: frozenset[str] = frozenset({"public_interaction"})

# Error codes the learner-facing API may emit. Kept here so the route layer
# and the service layer can be cross-checked at import time.
_LEARNER_FACING_ERROR_CODES: frozenset[str] = frozenset(
    {
        "[AI_COACH_DISABLED]",
        "[AI_COACH_NOT_CONFIGURED]",
        "[AI_COACH_PROMPT_TEMPLATE_MISSING]",
        "[AI_COACH_PROMPT_CONFIG_INVALID]",
        "[AI_COACH_PROMPT_REVISION_NOT_FOUND]",
        "[AI_COACH_PROMPT_REVISION_AUDIT_MISSING]",
        "[AI_COACH_PROMPT_REVISION_FALLBACK]",
        "[AI_COACH_PROMPT_CONTRACT_MISMATCH]",
        "[AI_COACH_INTERACTION_INVALID]",
        "[AI_COACH_ANSWER_PAYLOAD_INVALID]",
        "[AI_COACH_ANSWER_OPTION_INVALID]",
        "[AI_COACH_INTERACTION_TYPE_NOT_ALLOWED]",
        "[AI_COACH_SCORING_FAILED]",
        "[AI_COACH_SCORING_EMPTY]",
        "[AI_COACH_SCORING_PROMPT_MISSING]",
        "[AI_COACH_SCHEMA_VERSION_MISMATCH]",
        "[AI_COACH_TURN_NOT_FOUND]",
        "[AI_COACH_SESSION_NOT_FOUND]",
        "[AI_COACH_SESSION_NOT_IN_PROGRESS]",
        "[AI_COACH_CHAT_DISABLED]",
        "[AI_COACH_CHAT_EVENT_NOT_FOUND]",
        "[AI_COACH_CHAT_EVENT_ALREADY_SUBMITTED]",
        "[AI_COACH_CHAT_EVENT_NOT_ANSWERABLE]",
        "[AI_COACH_UI_EVENT_TYPE_NOT_ALLOWED]",
        "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]",
        "[AI_COACH_LLM_GENERATION_FAILED]",
        "[ACCESS_DENIED]",
    }
)
_LEARNER_FACING_ERROR_PREFIXES: tuple[str, ...] = (
    "[AI_COACH_INTERACTION_INVALID:",
    "[AI_COACH_PROMPT_COMPILE_FAILED:",
    "[AI_COACH_SCORING_FAILED:",
)


def _api_error(
    code: str,
    *,
    status_code: int = 400,
    message: str | None = None,
) -> JSONResponse:
    if code not in _LEARNER_FACING_ERROR_CODES and not code.startswith(
        _LEARNER_FACING_ERROR_PREFIXES
    ):
        # Defensive: an unmapped code slipped through. Surface it under the
        # generic NOT_CONFIGURED bucket instead of leaking the service-layer
        # code into the public API surface.
        code = "[AI_COACH_NOT_CONFIGURED]"
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code),
    )


def _success_json(
    *,
    data: dict[str, Any],
    status_code: int = 200,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(success_response(data=data, message=message)),
    )


def _assert_no_internal_leak(payload: dict[str, Any]) -> None:
    try:
        assert_learner_public_payload(
            payload,
            public_subtrees=_LEARNER_FACING_PUBLIC_SUBTREES,
        )
    except RuntimeError as exc:
        raise RuntimeError(f"ai_coach_api {exc}") from exc


def _serialize_session_public(
    session: Any,
    turns: list[Any] | None = None,
) -> dict[str, Any]:
    """Project a session + turns to the strict learner-facing DTO.

    Delegates to ``AiCoachSessionService.serialize_session_public`` so the
    Pydantic allow-list (with ``extra="forbid"``) is the single source of
    truth for what may be returned. The assertion at the end is a runtime
    tripwire that catches schema drift if the SQLAlchemy model ever gains a
    field whose name collides with an internal-only concept.
    """
    service = AiCoachSessionService.__new__(AiCoachSessionService)
    public_dto = service.serialize_session_public(session, turns or [])
    payload = public_dto.model_dump(mode="json")
    _assert_no_internal_leak(payload)
    payload["schema_version"] = AI_COACH_INTERACTION_SCHEMA_VERSION
    return payload


@router.post("/chat/sessions")
async def create_ai_coach_chat_session(
    payload: AiCoachChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    service = AiCoachChatService(db)
    try:
        session = await service.create_session(
            user_id=str(current_user.user_id),
            module_key=payload.module_key,
            resume_strategy=payload.resume_strategy,
            actor=current_user,
        )
    except AiCoachChatServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return _success_json(
        status_code=201,
        data=session.model_dump(mode="json"),
        message="AI 教练对话会话创建成功。",
    )


@router.post("/chat/sessions/stream")
async def create_ai_coach_chat_session_stream(
    payload: AiCoachChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = AiCoachChatStreamService(db)
    return StreamingResponse(
        service.stream_create_session(payload=payload, actor=current_user),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/sessions/{session_id}")
async def get_ai_coach_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    service = AiCoachChatService(db)
    try:
        session = await service.public_session(
            session_id,
            str(current_user.user_id),
        )
    except AiCoachChatServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return _success_json(data=session.model_dump(mode="json"))


@router.post("/chat/sessions/{session_id}/messages/stream")
async def send_ai_coach_chat_message_stream(
    session_id: str,
    payload: AiCoachChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = AiCoachChatStreamService(db)
    return StreamingResponse(
        service.stream_send_message(
            session_id=session_id,
            payload=payload,
            actor=current_user,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/sessions/{session_id}/messages")
async def send_ai_coach_chat_message(
    session_id: str,
    payload: AiCoachChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    service = AiCoachChatService(db)
    try:
        session = await service.send_message(
            session_id=session_id,
            user_id=str(current_user.user_id),
            payload=payload,
            actor=current_user,
        )
    except AiCoachChatServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return _success_json(
        data=session.model_dump(mode="json"),
        message="AI 教练已生成回复。",
    )


@router.post("/chat/sessions/{session_id}/events/{event_id}/answer/stream")
async def submit_ai_coach_chat_event_answer_stream(
    session_id: str,
    event_id: str,
    payload: AiCoachChatEventAnswerSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = AiCoachChatStreamService(db)
    return StreamingResponse(
        service.stream_submit_answer(
            session_id=session_id,
            event_id=event_id,
            payload=payload,
            actor=current_user,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/sessions/{session_id}/events/{event_id}/answer")
async def submit_ai_coach_chat_event_answer(
    session_id: str,
    event_id: str,
    payload: AiCoachChatEventAnswerSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    service = AiCoachChatService(db)
    try:
        session = await service.submit_event_answer(
            session_id=session_id,
            event_id=event_id,
            user_id=str(current_user.user_id),
            answer_payload=payload.answer_payload,
            actor=current_user,
        )
    except AiCoachChatServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return _success_json(
        data=session.model_dump(mode="json"),
        message="互动卡片提交成功。",
    )


@router.post("/sessions")
async def create_ai_coach_session(
    payload: AiCoachSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Create a new AI coach session."""
    service = AiCoachSessionService(db)
    try:
        session = await service.create_session_v1(
            user_id=str(current_user.user_id),
            module_key=payload.module_key,
            coach_mode=payload.coach_mode,
            interaction_type=payload.interaction_type,
        )
    except AiCoachSessionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    turns = await service.list_turns(session.session_id)
    return _success_json(
        status_code=201,
        data=_serialize_session_public(session, turns=turns),
        message="AI 教练会话创建成功。",
    )


@router.post("/sessions/{session_id}/turns")
async def submit_ai_coach_turn(
    session_id: str,
    payload: AiCoachTurnSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Submit an answer for the current turn."""
    service = AiCoachSessionService(db)
    try:
        # Verify ownership / access. Raises AiCoachSessionServiceError for
        # ownership failures and the public-mapped codes for missing state.
        session = await service.get_session(
            session_id,
            str(current_user.user_id),
        )
        if session is None:
            return _api_error(
                "[AI_COACH_SESSION_NOT_FOUND]",
                status_code=404,
                message="AI 教练会话不存在。",
            )

        if payload.answer_payload is None:
            return _api_error(
                "[AI_COACH_ANSWER_PAYLOAD_INVALID]",
                status_code=422,
                message="AI 教练 v1 只接受结构化 answer_payload。",
            )
        from sales_trainer.schemas import AiCoachTurnSubmitV1

        v1_payload = AiCoachTurnSubmitV1(answer_payload=payload.answer_payload)
        await service.submit_turn_v1(
            session_id=session_id,
            answer_payload=v1_payload.answer_payload,
            actor=current_user,
        )
    except AiCoachSessionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)

    try:
        updated_session = await service.get_session(
            session_id,
            str(current_user.user_id),
        )
    except AiCoachSessionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if updated_session is None:
        return _api_error(
            "[AI_COACH_SESSION_NOT_FOUND]",
            status_code=404,
            message="AI 教练会话不存在。",
        )
    turns = await service.list_turns(session_id)
    return _success_json(
        data=_serialize_session_public(updated_session, turns=turns),
        message="回答提交成功。",
    )


def _serialize_turn_feedback_public(
    session: Any,
    turn: Any,
    score_result: Any | None,
    next_turn_available: bool,
) -> dict[str, Any]:
    """Build the slim AiCoachTurnFeedbackV1 payload returned by the
    explicit ``/turns/{turn_id}/submit`` route.

    This is intentionally narrower than ``_serialize_session_public`` so the
    caller can update local UI state without refetching the full session.
    """
    public_interaction = None
    if getattr(turn, "public_interaction", None):
        try:
            public_interaction = AiCoachInteractionPublicV1.model_validate(
                turn.public_interaction
            )
        except ValidationError:
            public_interaction = None
    user_answer_payload = None
    if getattr(turn, "answer_payload", None):
        try:
            user_answer_payload = AiCoachAnswerPayloadV1.model_validate(
                turn.answer_payload
            ).model_dump(mode="json")
        except ValidationError:
            user_answer_payload = None
    public_turn = AiCoachTurnPublicV1(
        turn_id=str(turn.turn_id),
        turn_number=int(turn.turn_number),
        public_interaction=public_interaction,
        user_answer_payload=user_answer_payload,
        score=float(turn.score) if turn.score is not None else None,
        max_score=float(turn.max_score) if turn.max_score is not None else None,
        ai_feedback=turn.ai_feedback,
        missed_points=list(turn.missed_points or []),
        next_turn_available=next_turn_available,
    )
    turn_payload = public_turn.model_dump(mode="json")
    turn_payload["next_turn_available"] = next_turn_available
    return {
        "session_id": str(session.session_id),
        "turn": turn_payload,
        "score_result": score_result,
        "next_turn_available": next_turn_available,
        "overall_mastered": bool(getattr(session, "mastery_state", None) == "mastered"),
    }


@router.post("/sessions/{session_id}/turns/{turn_id}/submit")
async def submit_ai_coach_turn_v1(
    session_id: str,
    turn_id: str,
    payload: AiCoachTurnSubmitV1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Explicit per-turn submit endpoint.

    Matches the frontend URL shape ``/sessions/{session_id}/turns/{turn_id}``
    and validates that ``turn_id`` corresponds to the latest turn (otherwise
    we 409 to prevent a stale client from writing against a replaced
    binding).
    """
    service = AiCoachSessionService(db)
    try:
        session = await service.get_session(
            session_id, str(current_user.user_id)
        )
        if session is None:
            return _api_error(
                "[AI_COACH_SESSION_NOT_FOUND]",
                status_code=404,
                message="AI 教练会话不存在。",
            )
        latest_turn = await service._get_latest_turn(session_id)
        if latest_turn is None or str(latest_turn.turn_id) != str(turn_id):
            return _api_error(
                "[AI_COACH_TURN_NOT_FOUND]",
                status_code=409,
                message="提交的 turn_id 与当前活跃轮次不一致，请刷新后重试。",
            )
        submitted_turn = await service.submit_turn_v1(
            session_id=session_id,
            answer_payload=payload.answer_payload,
            actor=current_user,
        )
    except AiCoachSessionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)

    updated_session = await service.get_session(session_id, str(current_user.user_id))
    if updated_session is None:
        return _api_error(
            "[AI_COACH_SESSION_NOT_FOUND]",
            status_code=404,
            message="AI 教练会话不存在。",
        )
    latest_after_submit = await service._get_latest_turn(session_id)
    # ``updated_session.mastery_state`` flips to "mastered"/"not_mastered"
    # when finished; either way there is no next turn to answer.
    finished = updated_session.status != "in_progress"
    feedback = _serialize_turn_feedback_public(
        session=updated_session,
        turn=submitted_turn,
        score_result={
            "score": float(submitted_turn.score)
            if submitted_turn.score is not None
            else None,
            "max_score": float(submitted_turn.max_score)
            if submitted_turn.max_score is not None
            else None,
            "feedback": submitted_turn.ai_feedback,
            "missed_points": list(submitted_turn.missed_points or []),
            "next_turn_available": not finished,
            "finished": finished,
        }
        if submitted_turn
        else None,
        next_turn_available=not finished and latest_after_submit is not None,
    )
    return _success_json(data=feedback, message="回答提交成功。")


@router.get("/sessions/{session_id}")
async def get_ai_coach_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Get an AI coach session with all turns."""
    service = AiCoachSessionService(db)
    try:
        session = await service.get_session(
            session_id,
            str(current_user.user_id),
        )
    except AiCoachSessionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if session is None:
        return _api_error(
            "[AI_COACH_SESSION_NOT_FOUND]",
            status_code=404,
            message="AI 教练会话不存在。",
        )

    turns = await service.list_turns(session_id)
    return _success_json(data=_serialize_session_public(session, turns=turns))
