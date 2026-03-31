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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.conversation.models import ConversationMessage
from common.conversation.runtime_diagnostics import (
    build_session_runtime_diagnostics,
    extract_voice_policy_snapshot,
)
from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import PracticeSession, Scenario, SessionAudioSegment, SessionStatus, User
from common.db.schemas import (
    SessionCreate,
    SessionDetail,
    SessionLifecycleRequest,
    SessionLifecycleResponse,
    SessionReport,
    SessionResponse,
    SessionUpdate,
    ScenarioType,
)
from common.db.session import get_db
from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SessionLifecycleService,
    SessionLifecycleTransition,
)
from common.db.voice_policy_snapshot import build_voice_policy_snapshot_ref
from common.effectiveness import (
    build_sales_effectiveness_metrics,
    build_sales_rollup_scores,
    evaluate_effectiveness_snapshot,
)
from common.monitoring.logger import get_logger, get_trace_id
from common.oss.signing import OssConfigError, get_oss_signing_service
from common.websocket.base_handler import get_connection_manager
from common.websocket.session_manager import get_session_manager
from presentation_coach.services.coach_service import PresentationCoachService
from sales_bot.services.bot_service import sales_bot_service
from sales_bot.services.summary_service import summary_service
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from sales_bot.websocket.components.stepfun_message_helpers import (
    normalize_score_snapshot,
)
from training_runtime.service import build_training_runtime_descriptor

logger = get_logger(__name__)

router = APIRouter()


def _is_true_env(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_utc_timestamp(value: datetime) -> datetime:
    """Normalize datetime values to UTC for safe arithmetic."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _duration_seconds_between(
    start_time: datetime | None, end_time: datetime | None
) -> int | None:
    """Calculate non-negative duration seconds between two datetimes."""
    if start_time is None or end_time is None:
        return None
    start_time_utc = _coerce_utc_timestamp(start_time)
    end_time_utc = _coerce_utc_timestamp(end_time)
    return max(0, int((end_time_utc - start_time_utc).total_seconds()))


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


def _filter_retry_focus_fields(
    value: Any,
    *,
    allowed_keys: tuple[str, ...],
) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None

    filtered = {
        key: str(value[key]).strip()
        for key in allowed_keys
        if value.get(key) is not None and str(value.get(key)).strip()
    }
    return filtered or None


def _sanitize_retry_focus_intent(focus_intent: Any) -> dict[str, Any] | None:
    if focus_intent is None:
        return None
    if not isinstance(focus_intent, dict):
        return None

    main_issue = _filter_retry_focus_fields(
        focus_intent.get("main_issue"),
        allowed_keys=("issue_type", "issue_text", "recovery_rule"),
    )
    next_goal = _filter_retry_focus_fields(
        focus_intent.get("next_goal"),
        allowed_keys=("goal_type", "goal_text", "rule"),
    )
    if main_issue is None and next_goal is None:
        return None

    sanitized: dict[str, Any] = {
        "version": str(focus_intent.get("version") or "retry_focus_v1"),
    }
    source_session_id = focus_intent.get("source_session_id")
    if source_session_id is not None and str(source_session_id).strip():
        sanitized["source_session_id"] = str(source_session_id)
    if main_issue is not None:
        sanitized["main_issue"] = main_issue
    if next_goal is not None:
        sanitized["next_goal"] = next_goal
    return sanitized


def _build_retry_focus_intent(
    *,
    session_id: str,
    scenario_type: str,
    main_issue: Any,
    next_goal: Any,
) -> dict[str, Any] | None:
    if str(scenario_type or "").lower() != "sales":
        return None

    return _sanitize_retry_focus_intent(
        {
            "version": "retry_focus_v1",
            "source_session_id": session_id,
            "main_issue": main_issue,
            "next_goal": next_goal,
        }
    )


def _build_retry_entry(
    *,
    session: PracticeSession,
    scenario_type: str,
    main_issue: Any = None,
    next_goal: Any = None,
) -> dict[str, Any]:
    retry_entry: dict[str, Any] = {
        "scenario_type": scenario_type,
        "agent_id": str(session.agent_id) if getattr(session, "agent_id", None) else None,
        "persona_id": str(session.persona_id) if getattr(session, "persona_id", None) else None,
        "presentation_id": (
            str(session.presentation_id)
            if getattr(session, "presentation_id", None)
            else None
        ),
    }
    focus_intent = _build_retry_focus_intent(
        session_id=str(session.session_id),
        scenario_type=scenario_type,
        main_issue=main_issue,
        next_goal=next_goal,
    )
    if focus_intent is not None:
        retry_entry["focus_intent"] = focus_intent
    return retry_entry


def _is_admin_user(user: User) -> bool:
    return str(getattr(user, "role", "user")).lower() == "admin"


def _can_read_session(session: PracticeSession, user: User) -> bool:
    return _is_admin_user(user) or str(session.user_id) == str(user.user_id)


async def build_session_audio_audit(
    db: AsyncSession,
    session_id: str,
    session: PracticeSession,
) -> "AudioAuditPayloadSchema | None":
    """Build a shared audio-audit read model for report and replay payloads.

    Queries SessionAudioSegment rows ordered by segment_sequence, reads the
    bounded summary from voice_policy_snapshot.runtime_metrics.audio_audit, and
    computes a derived learner_status.

    Returns None (not an empty payload) when the session has no audio segments
    at all — this distinguishes "audio not applicable" from "audio applicable
    but nothing uploaded yet".
    """
    from common.db.schemas import (
        AudioAuditPayloadSchema,
        AudioAuditSegmentSchema,
        AudioAuditSummarySchema,
    )

    # Query all segments ordered by sequence
    seg_result = await db.execute(
        select(SessionAudioSegment)
        .where(SessionAudioSegment.session_id == session_id)
        .order_by(SessionAudioSegment.segment_sequence)
    )
    segments = list(seg_result.scalars().all())

    # If the session has never created any audio segments, return None.
    if not segments:
        return None

    # Read bounded summary from voice_policy_snapshot.runtime_metrics.audio_audit
    voice_policy = session.voice_policy_snapshot or {}
    runtime_metrics = voice_policy.get("runtime_metrics") if isinstance(voice_policy, dict) else None
    audio_audit_raw = {}
    if isinstance(runtime_metrics, dict):
        raw = runtime_metrics.get("audio_audit")
        if isinstance(raw, dict):
            audio_audit_raw = raw

    # Compute aggregates from actual segment rows
    uploaded_count = 0
    failed_count = 0
    pending_count = 0
    total_bytes = 0
    latest_sequence: int | None = None
    last_uploaded_at: str | None = None

    segment_schemas: list[AudioAuditSegmentSchema] = []
    for seg in segments:
        if seg.upload_status == "uploaded":
            uploaded_count += 1
            total_bytes += seg.size_bytes or 0
            if latest_sequence is None or seg.segment_sequence > latest_sequence:
                latest_sequence = seg.segment_sequence
            if seg.created_at is not None:
                last_uploaded_at = seg.created_at.isoformat()
        elif seg.upload_status == "failed":
            failed_count += 1
        elif seg.upload_status == "pending":
            pending_count += 1

        playback_path = None
        if seg.upload_status == "uploaded":
            playback_path = f"/api/v1/sessions/{session_id}/audio-segments/{seg.segment_sequence}"

        segment_schemas.append(
            AudioAuditSegmentSchema(
                segment_sequence=seg.segment_sequence,
                created_at=seg.created_at.isoformat() if seg.created_at else None,
                duration_ms=seg.duration_ms,
                size_bytes=seg.size_bytes,
                upload_status=seg.upload_status,
                playback_path=playback_path,
                error_message=seg.error_message,
            )
        )

    total_segments = len(segments)

    # Derive learner_status
    if uploaded_count > 0 and uploaded_count == total_segments:
        learner_status = "available"
    elif uploaded_count > 0:
        learner_status = "partial"
    else:
        learner_status = "missing"

    # Derive degraded_reasons
    degraded_reasons: list[str] = []
    if failed_count > 0:
        degraded_reasons.append("upload_failed")
    if pending_count > 0:
        degraded_reasons.append("segments_pending")

    summary = AudioAuditSummarySchema(
        recording_status=audio_audit_raw.get("recording_status", "active"),
        total_segments=total_segments,
        uploaded_segments=uploaded_count,
        failed_segments=failed_count,
        total_bytes=total_bytes,
        latest_segment_sequence=latest_sequence,
        storage_prefix=audio_audit_raw.get("storage_prefix", f"audio/{session_id}/"),
        last_uploaded_at=last_uploaded_at,
        learner_status=learner_status,
        degraded_reasons=degraded_reasons,
    )

    return AudioAuditPayloadSchema(summary=summary, segments=segment_schemas)


def _build_session_response(
    session: PracticeSession,
    scenario_type: str | None = None,
) -> SessionResponse:
    payload = SessionResponse.model_validate(session)
    resolved_scenario_type = scenario_type
    if not resolved_scenario_type and getattr(session, "scenario", None) is not None:
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


def _build_lifecycle_response_payload(transition) -> SessionLifecycleResponse:
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


@dataclass(slots=True)
class _LifecycleActionResult:
    transition: SessionLifecycleTransition
    snapshot: dict[str, Any] | None = None
    summary: Any | None = None


class _LifecycleActionAbort(Exception):
    def __init__(self, response: JSONResponse) -> None:
        super().__init__("Lifecycle action aborted")
        self.response = response


def _lifecycle_log_context(transition: SessionLifecycleTransition) -> dict[str, Any]:
    return {
        "session_id": str(transition.session.session_id),
        "scenario_type": transition.scenario_type,
        "action": transition.action,
        "to_status": transition.to_status,
    }


def _calculate_session_overall_score(session: PracticeSession) -> float | None:
    scores = (
        session.logic_score,
        session.accuracy_score,
        session.completeness_score,
    )
    if any(score is None for score in scores):
        return None
    return round(sum(float(score) for score in scores) / 3.0, 2)


def _build_sales_realtime_not_evaluable_snapshot(
    *, reason: str,
) -> dict[str, Any]:
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

    overall_score = float(normalized_score_snapshot.get("overall_score") or 0.0)
    rollups = build_sales_rollup_scores(
        overall_score=overall_score,
        dimension_scores=normalized_score_snapshot.get("dimension_scores"),
    )

    session.logic_score = rollups["logic_score"]
    session.accuracy_score = rollups["accuracy_score"]
    session.completeness_score = rollups["completeness_score"]
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
    if _apply_sales_realtime_score_snapshot_to_session(session, persisted_score_snapshot):
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


async def _prepare_terminal_lifecycle_result(
    *,
    session_id: str,
    session: PracticeSession,
    scenario_type: str,
    lifecycle_service: SessionLifecycleService,
    db: AsyncSession,
) -> _LifecycleActionResult:
    transition = await lifecycle_service.transition(
        session=session,
        scenario_type=scenario_type,
        action="end",
    )

    if not transition.changed:
        return _LifecycleActionResult(
            transition=transition,
            snapshot=_ensure_effectiveness_snapshot(session),
        )

    normalized_scenario_type = (scenario_type or "sales").lower()
    summary: Any | None = None

    if normalized_scenario_type == "presentation":
        coach_service = PresentationCoachService(db)
        coach_result = await coach_service.end_session(session_id, commit=False)
        if not coach_result.is_success:
            raise _LifecycleActionAbort(
                build_server_error(
                    "[SESSION_END_FAILED]",
                    message="会话结束失败",
                    session_id=session_id,
                )
            )

        session = coach_result.value
        transition.session = session
        snapshot = _ensure_effectiveness_snapshot(session)
    elif normalized_scenario_type == "sales":
        evidence_source: str | None = None
        if _session_has_persisted_scores(session):
            evidence_source = "session_scores"
        else:
            evidence_source = await _sync_sales_realtime_terminal_evidence(
                session_id=session_id,
                session=session,
                db=db,
            )
            if evidence_source is None:
                summary_result = await summary_service.generate_summary(
                    uuid.UUID(session_id)
                )
                if not summary_result.is_success:
                    logger.warning(
                        "practice_session_summary_generation_failed",
                        session_id=session_id,
                        voice_mode=getattr(session, "voice_mode", None),
                        summary_fallback=summary_result.fallback,
                    )
                    raise _LifecycleActionAbort(
                        build_server_error(
                            "[SUMMARY_GENERATION_FAILED]",
                            message="总结生成失败",
                            session_id=session_id,
                        )
                    )
                summary = summary_result.value
                _apply_sales_summary_scores_if_missing(session, summary)
                evidence_source = "summary"

        snapshot = _ensure_effectiveness_snapshot(session)
        if evidence_source is not None:
            _log_sales_terminal_evidence_state(
                session_id=session_id,
                session=session,
                snapshot=snapshot,
                evidence_source=evidence_source,
            )

        # Keep compatibility with realtime runtime cleanup.
        end_result = await sales_bot_service.end_session(uuid.UUID(session_id))
        if not end_result.is_success:
            logger.warning(
                "Sales bot end_session returned non-success",
                session_id=session_id,
                fallback=end_result.fallback,
            )
    else:
        raise _LifecycleActionAbort(
            error_response("[INVALID_SCENARIO_TYPE]", status_code=400)
        )

    return _LifecycleActionResult(
        transition=transition,
        snapshot=snapshot,
        summary=summary,
    )


async def _run_lifecycle_action(
    *,
    session_id: str,
    session: PracticeSession,
    scenario_type: str | None,
    action: str,
    db: AsyncSession,
) -> _LifecycleActionResult:
    lifecycle_service = SessionLifecycleService(db)

    if action == "end":
        if not scenario_type:
            raise _LifecycleActionAbort(
                error_response("[SCENARIO_NOT_FOUND]", status_code=404)
            )
        result = await _prepare_terminal_lifecycle_result(
            session_id=session_id,
            session=session,
            scenario_type=scenario_type,
            lifecycle_service=lifecycle_service,
            db=db,
        )
    else:
        transition = await lifecycle_service.transition(
            session=session,
            scenario_type=scenario_type,
            action=action,
        )
        result = _LifecycleActionResult(transition=transition)

    await db.commit()
    await db.refresh(result.transition.session)

    logger.info(
        "practice_session_lifecycle_transition_applied",
        **_lifecycle_log_context(result.transition),
        changed=result.transition.changed,
    )
    await lifecycle_service.trigger_report_generation_if_needed(result.transition)
    live_handler_synced = await _sync_live_handler_after_lifecycle_transition(
        result.transition
    )
    logger.info(
        "practice_session_live_handler_sync",
        **_lifecycle_log_context(result.transition),
        live_handler_synced=live_handler_synced,
    )
    await _broadcast_lifecycle_events(result.transition)
    await _close_live_handler_if_terminal(result.transition)

    return result


def _derive_effectiveness_metrics(session: PracticeSession) -> tuple[dict[str, Any], bool, bool, str | None]:
    """Derive 80/20 effectiveness metrics from persisted session fields."""
    logic = float(session.logic_score or 0.0)
    accuracy = float(session.accuracy_score or 0.0)
    completeness = float(session.completeness_score or 0.0)
    duration_seconds = int(session.total_duration_seconds or 0)
    if (
        duration_seconds <= 0
        and session.start_time is not None
        and session.end_time is not None
    ):
        derived_duration_seconds = _duration_seconds_between(
            session.start_time, session.end_time
        )
        if derived_duration_seconds is not None:
            duration_seconds = derived_duration_seconds

    has_scores = any(score > 0 for score in (logic, accuracy, completeness))
    evaluable = has_scores and duration_seconds > 0
    not_evaluable_reason = None if evaluable else "INSUFFICIENT_SESSION_METRICS"

    overall_score = (logic + accuracy + completeness) / 3.0
    metrics = build_sales_effectiveness_metrics(
        overall_score=overall_score,
        logic_score=logic,
        accuracy_score=accuracy,
        completeness_score=completeness,
        duration_seconds=duration_seconds,
    )
    main_capability_passed = overall_score >= 70.0
    return metrics, main_capability_passed, evaluable, not_evaluable_reason


def _ensure_effectiveness_snapshot(session: PracticeSession) -> dict[str, Any]:
    """Ensure session has effectiveness snapshot, creating one if absent."""
    if isinstance(session.effectiveness_snapshot, dict) and session.effectiveness_snapshot:
        existing_snapshot = session.effectiveness_snapshot
        has_required_keys = all(
            key in existing_snapshot
            for key in ("pass_flags", "overall_result", "main_issue", "next_goal")
        )
        if has_required_keys:
            return existing_snapshot

        fallback_metrics, fallback_main_passed, fallback_evaluable, fallback_reason = (
            _derive_effectiveness_metrics(session)
        )
        metrics = existing_snapshot.get("metrics")
        if not isinstance(metrics, dict):
            metrics = fallback_metrics
        else:
            filler_rate_raw = metrics.get(
                "filler_rate_per_100_words",
                fallback_metrics.get("filler_rate_per_100_words", 0.0),
            )
            try:
                filler_rate = float(filler_rate_raw)
            except (TypeError, ValueError):
                filler_rate = float(
                    fallback_metrics.get("filler_rate_per_100_words", 0.0)
                )
            metrics = {
                **metrics,
                "filler_rate_per_100_words": filler_rate,
            }
        main_capability_passed = existing_snapshot.get("main_capability_passed")
        if not isinstance(main_capability_passed, bool):
            main_capability_passed = fallback_main_passed
        evaluable = existing_snapshot.get("evaluable")
        if not isinstance(evaluable, bool):
            evaluable = fallback_evaluable
        not_evaluable_reason = existing_snapshot.get("not_evaluable_reason")
        if not isinstance(not_evaluable_reason, str):
            not_evaluable_reason = fallback_reason

        merged_snapshot = {
            **existing_snapshot,
            **evaluate_effectiveness_snapshot(
                metrics=metrics,
                main_capability_passed=main_capability_passed,
                evaluable=evaluable,
                not_evaluable_reason=not_evaluable_reason,
            ),
        }
        session.effectiveness_snapshot = merged_snapshot
        return merged_snapshot

    metrics, main_capability_passed, evaluable, not_evaluable_reason = (
        _derive_effectiveness_metrics(session)
    )
    snapshot = evaluate_effectiveness_snapshot(
        metrics=metrics,
        main_capability_passed=main_capability_passed,
        evaluable=evaluable,
        not_evaluable_reason=not_evaluable_reason,
    )
    session.effectiveness_snapshot = snapshot
    return snapshot


def _session_has_persisted_scores(session: PracticeSession) -> bool:
    return all(
        score is not None
        for score in (
            session.logic_score,
            session.accuracy_score,
            session.completeness_score,
        )
    )


def _apply_sales_summary_scores_if_missing(session: PracticeSession, summary: Any) -> None:
    """Idempotent score assignment for sales summary."""
    if session.logic_score is None:
        session.logic_score = summary.score_confidence
    if session.accuracy_score is None:
        session.accuracy_score = summary.score_persuasion
    if session.completeness_score is None:
        session.completeness_score = summary.score_clarity


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


async def _sync_live_handler_after_lifecycle_transition(transition) -> bool:
    """Keep the live websocket handler aligned with DB-backed lifecycle state."""

    session_manager = get_session_manager()
    await session_manager.update_activity(str(transition.session.session_id))
    return await session_manager.sync_lifecycle_transition(transition)


async def _close_live_handler_if_terminal(transition) -> bool:
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
    - sales: Sales practice session (agent_id + persona_id required)

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
        raw_session_payload = session_data.model_dump(exclude_unset=True)
        if raw_session_payload.get("sales_persona"):
            return error_response(
                "[FIELD_DEPRECATED_PERSONA_CENTERED]",
                status_code=400,
                message="sales_persona 已废弃，请改用 agent_id + persona_id（并在角色中心配置策略）",
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
        if scenario_type_value == "sales" and not (agent_id_str and persona_id_str):
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
        focus_intent = _sanitize_retry_focus_intent(session_data.focus_intent)
        if (
            scenario_type_value == "sales"
            and session_data.focus_intent is not None
            and focus_intent is None
        ):
            return error_response(
                "[INVALID_RETRY_FOCUS_INTENT]",
                status_code=400,
                message="retry focus intent 必须包含可读的 main_issue 或 next_goal 结构。",
            )
        if scenario_type_value == "sales" and focus_intent is not None:
            session_policy_snapshot["focus_intent"] = deepcopy(focus_intent)
        logger.info(
            "practice_session_voice_policy_resolved",
            user_id=str(current_user.user_id),
            scenario_type=scenario_type_value,
            agent_id=agent_id_str,
            persona_id=persona_id_str,
            voice_mode=effective_voice_mode,
            runtime_profile_id=effective_runtime_profile_id,
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

        if scenario_type_value == "presentation":
            if not session_data.presentation_id:
                return error_response("[PRESENTATION_ID_REQUIRED]", status_code=400)

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
                return build_server_error(
                    "[SESSION_CREATE_FAILED]",
                    message=fallback or "会话创建失败",
                    session_id=str(getattr(session_data, "session_id", "") or "") or None,
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
            return error_response("[INVALID_SCENARIO_TYPE]", status_code=400)

        response_payload = success_response(
            _build_session_response(session, scenario_type=scenario_type_value)
        )
        response_payload["session_id"] = str(session.session_id)
        return response_payload

    except (SQLAlchemyError, ValueError) as e:
        return build_server_error(
            "[SESSION_CREATE_FAILED]",
            message="会话创建失败",
            exc=e,
        )


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
        result = await _run_lifecycle_action(
            session_id=session_id,
            session=session,
            scenario_type=scenario_type,
            action=payload.action.value,
            db=db,
        )
    except _LifecycleActionAbort as exc:
        await db.rollback()
        return exc.response
    except InvalidSessionTransitionError as exc:
        await db.rollback()
        return _invalid_transition_response(
            exc=exc,
            current_status=exc.from_status,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        await db.rollback()
        return build_server_error(
            "[SESSION_END_FAILED]" if payload.action.value == "end" else "[SESSION_LIFECYCLE_FAILED]",
            message="会话结束失败" if payload.action.value == "end" else "会话生命周期控制失败",
            exc=exc,
            session_id=session_id,
            action=payload.action.value,
        )

    return success_response(_build_lifecycle_response_payload(result.transition))


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
        await lifecycle_service.trigger_report_generation_if_needed(transition)
        await _sync_live_handler_after_lifecycle_transition(transition)
        await _broadcast_lifecycle_events(transition)
        await _close_live_handler_if_terminal(transition)

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
    lifecycle_service = SessionLifecycleService(db)
    session, scenario_type = await lifecycle_service.get_session_with_scenario(
        session_id
    )

    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)

    # Verify ownership or admin access
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    if not scenario_type:
        return error_response("[SCENARIO_NOT_FOUND]", status_code=404)

    try:
        result = await _run_lifecycle_action(
            session_id=session_id,
            session=session,
            scenario_type=scenario_type,
            action="end",
            db=db,
        )
    except _LifecycleActionAbort as exc:
        await db.rollback()
        return exc.response
    except InvalidSessionTransitionError as exc:
        await db.rollback()
        return _invalid_transition_response(
            exc=exc,
            current_status=exc.from_status,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        await db.rollback()
        return build_server_error(
            "[SESSION_END_FAILED]",
            message="会话结束失败",
            exc=exc,
            session_id=session_id,
        )

    session = result.transition.session
    summary = result.summary
    snapshot = result.snapshot or _ensure_effectiveness_snapshot(session)

    if scenario_type == "presentation":
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
            effectiveness_snapshot=snapshot,
            pass_flags=snapshot.get("pass_flags"),
            main_capability_passed=snapshot.get("main_capability_passed"),
            overall_result=snapshot.get("overall_result"),
            main_issue=snapshot.get("main_issue"),
            next_goal=snapshot.get("next_goal"),
            retry_entry={
                "scenario_type": "presentation",
                "agent_id": str(session.agent_id) if session.agent_id else None,
                "persona_id": str(session.persona_id) if session.persona_id else None,
                "presentation_id": str(session.presentation_id)
                if session.presentation_id
                else None,
            },
            audio_audit=await build_session_audio_audit(db, session_id, session),
        )
    else:
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

        suggestions = ["会话已结束，可查看历史反馈并继续练习。"]
        if summary is not None:
            suggestions = [
                *summary.strengths,
                f"Improvement: {summary.actionable_feedback}",
            ]

        report = SessionReport(
            session_id=session_id,
            logic_score=session.logic_score or 0,
            accuracy_score=session.accuracy_score or 0,
            completeness_score=session.completeness_score or 0,
            overall_score=(
                (session.logic_score or 0)
                + (session.accuracy_score or 0)
                + (session.completeness_score or 0)
            )
            / 3,
            suggestions=suggestions,
            audio_url=None,
            transcript_url=None,
            voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
                session.voice_policy_snapshot
            ),
            effectiveness_snapshot=snapshot,
            pass_flags=snapshot.get("pass_flags"),
            main_capability_passed=snapshot.get("main_capability_passed"),
            overall_result=snapshot.get("overall_result"),
            main_issue=snapshot.get("main_issue"),
            next_goal=snapshot.get("next_goal"),
            retry_entry={
                "scenario_type": "sales",
                "agent_id": str(session.agent_id) if session.agent_id else None,
                "persona_id": str(session.persona_id) if session.persona_id else None,
            },
            audio_audit=await build_session_audio_audit(db, session_id, session),
        )

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

    scenario_type_result = await db.execute(
        select(Scenario.scenario_type).where(Scenario.scenario_id == session.scenario_id)
    )
    scenario_type_value = scenario_type_result.scalar_one_or_none()
    normalized_scenario_type = (
        str(scenario_type_value) if scenario_type_value else "sales"
    )

    projection_result = await SessionEvidenceService(db).get_projection(
        session_id=session_id,
        session=session,
        scenario_type=normalized_scenario_type,
    )
    if not projection_result.is_success:
        return error_response("[SESSION_EVIDENCE_FAILED]", status_code=500)

    projection = projection_result.value
    scenario_type_enum = (
        ScenarioType.PRESENTATION
        if normalized_scenario_type == "presentation"
        else ScenarioType.SALES
    )
    presentation_review = (
        projection.presentation_review if scenario_type_enum == ScenarioType.PRESENTATION else None
    )
    suggestions = ["Review your performance and practice again!"]
    if scenario_type_enum == ScenarioType.PRESENTATION and isinstance(
        presentation_review,
        dict,
    ):
        review_recommendations = presentation_review.get("recommendations")
        if isinstance(review_recommendations, list) and review_recommendations:
            suggestions = [str(item) for item in review_recommendations]
        else:
            suggestions = ["按页回看关键内容，并针对缺失覆盖点再练一轮。"]

    report = SessionReport(
        session_id=session.session_id,
        scenario_type=scenario_type_enum,
        logic_score=projection.logic_score,
        accuracy_score=projection.accuracy_score,
        completeness_score=projection.completeness_score,
        overall_score=projection.overall_score,
        suggestions=suggestions,
        audio_url=session.audio_url,
        transcript_url=session.transcript_url,
        voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
            session.voice_policy_snapshot
        ),
        effectiveness_snapshot=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.effectiveness_snapshot
        ),
        pass_flags=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.pass_flags
        ),
        main_capability_passed=(
            None
            if scenario_type_enum == ScenarioType.PRESENTATION
            else projection.main_capability_passed
        ),
        overall_result=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.overall_result
        ),
        main_issue=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.main_issue
        ),
        next_goal=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.next_goal
        ),
        stage_summary=(
            [] if scenario_type_enum == ScenarioType.PRESENTATION else projection.stage_summary
        ),
        evaluable=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.evaluable
        ),
        not_evaluable_reason=(
            None
            if scenario_type_enum == ScenarioType.PRESENTATION
            else projection.not_evaluable_reason
        ),
        evidence_completeness=projection.evidence_completeness,
        presentation_review=presentation_review,
        retry_entry=_build_retry_entry(
            session=session,
            scenario_type=normalized_scenario_type,
            main_issue=projection.main_issue,
            next_goal=projection.next_goal,
        ),
        audio_audit=await build_session_audio_audit(db, session_id, session),
        conclusion_evidence=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.conclusion_evidence
        ),
        evidence_degradation=(
            None if scenario_type_enum == ScenarioType.PRESENTATION else projection.evidence_degradation
        ),
    )

    logger.info(
        "practice_session_report_built",
        session_id=session_id,
        scenario_type=scenario_type_enum.value,
        report_overall_score=report.overall_score,
        evidence_complete=projection.evidence_completeness.get("complete"),
        presentation_page_metadata_complete=projection.evidence_completeness.get(
            "page_metadata_complete"
        ),
        presentation_degraded_reasons=projection.evidence_completeness.get(
            "degraded_reasons"
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

    snapshot = extract_voice_policy_snapshot(session)
    preview_tools = VoiceRuntimePolicyService(db).build_stepfun_tools(snapshot)
    effective_tool_types = [
        str(tool.get("type") or "") for tool in preview_tools if isinstance(tool, dict)
    ]

    live_claim_truth = None
    live_coach_health = None
    live_session_summary = None
    session_info = get_session_manager().sessions.get(session_id)
    live_handler = session_info.handler if session_info is not None else None
    live_runtime_active = live_handler is not None
    if live_handler is not None:
        diagnostics_getter = getattr(live_handler, "get_runtime_diagnostics", None)
        if callable(diagnostics_getter):
            runtime_diagnostics = diagnostics_getter()
            if isinstance(runtime_diagnostics, dict):
                live_session_summary = deepcopy(
                    runtime_diagnostics.get("live_session_summary")
                )
                live_claim_truth = deepcopy(runtime_diagnostics.get("claim_truth"))
                live_coach_health = deepcopy(runtime_diagnostics.get("coach_health"))
        if live_session_summary is None:
            live_session_summary = deepcopy(
                getattr(live_handler, "_latest_live_session_summary", None)
            )
        if live_claim_truth is None and isinstance(live_session_summary, dict):
            live_claim_truth = deepcopy(live_session_summary.get("claim_truth"))
        if live_claim_truth is None:
            live_claim_truth = deepcopy(getattr(live_handler, "_latest_claim_truth", None))
        if live_coach_health is None:
            live_coach_health = {
                "status": str(getattr(live_handler, "_coach_health", "healthy") or "healthy"),
                "reason": getattr(live_handler, "_coach_health_reason", None),
                "message": getattr(live_handler, "_coach_health_message", lambda status: "实时辅导正常。")(getattr(live_handler, "_coach_health", "healthy")),
            }

    projection_effectiveness_snapshot = None
    projection_conclusion_evidence = None
    projection_evidence_degradation = None
    resolved_scenario_type = SessionEvidenceService.resolve_scenario_type(session)
    if resolved_scenario_type == "sales" and session.status == SessionStatus.COMPLETED.value:
        projection_result = await SessionEvidenceService(db).get_projection(
            session_id=session_id,
            session=session,
            scenario_type=resolved_scenario_type,
        )
        if projection_result.is_success and isinstance(
            projection_result.value.effectiveness_snapshot,
            dict,
        ):
            projection_effectiveness_snapshot = deepcopy(
                projection_result.value.effectiveness_snapshot
            )
            projection_conclusion_evidence = projection_result.value.conclusion_evidence
            projection_evidence_degradation = projection_result.value.evidence_degradation
        elif not projection_result.is_success:
            logger.warning(
                "practice_session_knowledge_check_projection_unavailable",
                session_id=session_id,
                scenario_type=resolved_scenario_type,
                projection_error=projection_result.fallback,
            )

    diagnostics = build_session_runtime_diagnostics(
        session=session,
        snapshot=snapshot,
        effective_tool_types=effective_tool_types,
        live_claim_truth=live_claim_truth,
        live_coach_health=live_coach_health,
        live_session_summary=live_session_summary,
        live_knowledge_answer_diagnostics=live_knowledge_answer_diagnostics,
        live_runtime_active=live_runtime_active,
        projection_effectiveness_snapshot=projection_effectiveness_snapshot,
        conclusion_evidence=projection_conclusion_evidence,
        evidence_degradation=(
            None if live_runtime_active else projection_evidence_degradation
        ),
    )

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
            duration_seconds = _duration_seconds_between(
                session.start_time, session.end_time
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
                "effectiveness_snapshot": session.effectiveness_snapshot
                if isinstance(session.effectiveness_snapshot, dict)
                else None,
                "feedback_summary": (
                    (
                        session.effectiveness_snapshot.get("main_issue", {}).get(
                            "issue_text"
                        )
                        if isinstance(
                            session.effectiveness_snapshot.get("main_issue"), dict
                        )
                        else None
                    )
                    or session.effectiveness_snapshot.get("next_goal", {}).get(
                        "goal_text"
                    )
                    if isinstance(session.effectiveness_snapshot, dict)
                    and (
                        isinstance(session.effectiveness_snapshot.get("main_issue"), dict)
                        or isinstance(session.effectiveness_snapshot.get("next_goal"), dict)
                    )
                    else None
                ),
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
        duration_seconds = _duration_seconds_between(
            session.start_time, session.end_time
        )
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
        return build_server_error(
            "[REPORT_RETRIEVAL_FAILED]",
            message="报告获取失败",
            exc=e,
            session_id=session_id,
        )


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


# ---------------------------------------------------------------------------
# Audio Segment OSS Direct-Upload Endpoints
# ---------------------------------------------------------------------------


@router.post("/practice/sessions/{session_id}/audio-upload-urls")
async def generate_audio_upload_url(
    session_id: str,
    body: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a presigned PUT URL for browser-direct audio segment upload.

    Request body:
        segment_sequence (int): Zero-based segment index within the session.
        content_type (str): MIME type, default "audio/webm".

    Returns:
        {url, object_key, expires_at} — the browser PUTs raw audio bytes to *url*.
    """
    # --- input validation ---
    segment_sequence = body.get("segment_sequence")
    if segment_sequence is None or not isinstance(segment_sequence, int) or segment_sequence < 0:
        return error_response(
            "[INVALID_SEGMENT_SEQUENCE]",
            status_code=422,
            message="segment_sequence must be a non-negative integer",
        )

    content_type = body.get("content_type", "audio/webm")
    if not isinstance(content_type, str) or not content_type:
        return error_response(
            "[INVALID_CONTENT_TYPE]",
            status_code=422,
            message="content_type must be a non-empty string",
        )

    # --- session ownership check ---
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # --- generate signed URL ---
    try:
        svc = get_oss_signing_service()
    except OssConfigError as exc:
        return error_response(
            "[OSS_NOT_CONFIGURED]",
            status_code=503,
            message=str(exc),
        )

    object_key = svc.build_object_key(session_id, segment_sequence)
    presigned = svc.generate_put_url(object_key, content_type=content_type)

    return success_response(
        {
            "url": presigned.url,
            "object_key": presigned.object_key,
            "expires_at": presigned.expires_at,
        }
    )


@router.post("/practice/sessions/{session_id}/audio-segments")
async def register_audio_segment(
    session_id: str,
    body: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a successfully uploaded audio segment.

    Request body:
        segment_sequence (int): Segment index.
        object_key (str): OSS object key that was uploaded.
        size_bytes (int | null): Upload size in bytes.
        duration_ms (int | null): Segment duration in milliseconds.

    Creates/updates a SessionAudioSegment row with upload_status="uploaded".
    """
    segment_sequence = body.get("segment_sequence")
    if segment_sequence is None or not isinstance(segment_sequence, int) or segment_sequence < 0:
        return error_response(
            "[INVALID_SEGMENT_SEQUENCE]",
            status_code=422,
            message="segment_sequence must be a non-negative integer",
        )

    object_key = body.get("object_key")
    if not object_key or not isinstance(object_key, str):
        return error_response(
            "[INVALID_OBJECT_KEY]",
            status_code=422,
            message="object_key must be a non-empty string",
        )

    size_bytes = body.get("size_bytes")
    duration_ms = body.get("duration_ms")

    # --- session ownership check ---
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # --- upsert segment row ---
    existing = await db.execute(
        select(SessionAudioSegment).where(
            SessionAudioSegment.session_id == session_id,
            SessionAudioSegment.segment_sequence == segment_sequence,
        )
    )
    segment = existing.scalar_one_or_none()

    if segment:
        segment.object_key = object_key
        segment.upload_status = "uploaded"
        segment.error_message = None
        if size_bytes is not None:
            segment.size_bytes = size_bytes
        if duration_ms is not None:
            segment.duration_ms = duration_ms
    else:
        segment = SessionAudioSegment(
            session_id=session_id,
            segment_sequence=segment_sequence,
            object_key=object_key,
            content_type="audio/webm",
            size_bytes=size_bytes,
            duration_ms=duration_ms,
            upload_status="uploaded",
        )
        db.add(segment)

    # Update PracticeSession.audio_url to point to the first segment's directory
    if session.audio_url is None:
        session.audio_url = f"audio/{session_id}/"

    await db.flush()

    # Persist audio-audit runtime metrics without clobbering existing voice policy data.
    audio_audit_result = await db.execute(
        select(
            func.count(SessionAudioSegment.id),
            func.coalesce(func.sum(SessionAudioSegment.size_bytes), 0),
        ).where(
            SessionAudioSegment.session_id == session_id,
            SessionAudioSegment.upload_status == "uploaded",
        )
    )
    uploaded_segment_count, total_uploaded_bytes = audio_audit_result.one()

    # Query failed segment count for bounded failure summary.
    failed_count_result = await db.execute(
        select(func.count(SessionAudioSegment.id)).where(
            SessionAudioSegment.session_id == session_id,
            SessionAudioSegment.upload_status == "failed",
        )
    )
    failed_segment_count_in_register = failed_count_result.scalar() or 0

    base_snapshot = (
        deepcopy(session.voice_policy_snapshot)
        if isinstance(session.voice_policy_snapshot, dict)
        else {}
    )
    runtime_metrics = base_snapshot.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        runtime_metrics = {}
    else:
        runtime_metrics = deepcopy(runtime_metrics)

    audio_audit = runtime_metrics.get("audio_audit")
    if not isinstance(audio_audit, dict):
        audio_audit = {}
    else:
        audio_audit = deepcopy(audio_audit)

    audio_audit.update(
        {
            "segment_count": int(uploaded_segment_count or 0),
            "uploaded_segment_count": int(uploaded_segment_count or 0),
            "total_uploaded_bytes": int(total_uploaded_bytes or 0),
            "last_segment_sequence": segment_sequence,
            "last_object_key": object_key,
            "last_uploaded_at": datetime.now(UTC).isoformat(),
            "storage_prefix": f"audio/{session_id}/",
            "failed_segment_count": int(failed_segment_count_in_register),
        }
    )
    runtime_metrics["audio_audit"] = audio_audit
    base_snapshot["runtime_metrics"] = runtime_metrics
    session.voice_policy_snapshot = base_snapshot

    await db.commit()
    await db.refresh(segment)

    logger.info(
        "audio_segment_registered",
        session_id=session_id,
        segment_sequence=segment_sequence,
        object_key=object_key,
        upload_status="uploaded",
    )

    return success_response(
        {
            "id": segment.id,
            "session_id": session_id,
            "segment_sequence": segment.segment_sequence,
            "object_key": segment.object_key,
            "upload_status": segment.upload_status,
            "size_bytes": segment.size_bytes,
            "duration_ms": segment.duration_ms,
            "created_at": segment.created_at.isoformat() if segment.created_at else None,
        }
    )


@router.get("/practice/sessions/{session_id}/audio-segments")
async def list_audio_segments(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all audio segments registered for a session.

    Returns an array of segment metadata including upload status.
    """
    # --- session ownership check ---
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    seg_result = await db.execute(
        select(SessionAudioSegment)
        .where(SessionAudioSegment.session_id == session_id)
        .order_by(SessionAudioSegment.segment_sequence)
    )
    segments = seg_result.scalars().all()

    return success_response(
        [
            {
                "id": s.id,
                "segment_sequence": s.segment_sequence,
                "object_key": s.object_key,
                "content_type": s.content_type,
                "size_bytes": s.size_bytes,
                "duration_ms": s.duration_ms,
                "upload_status": s.upload_status,
                "error_message": s.error_message,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in segments
        ]
    )


# Allowed error tokens for audio segment failure registration.
_AUDIO_FAILURE_TOKENS = frozenset({
    "signing_failed",
    "oss_put_failed",
    "register_failed",
    "network_error",
    "unknown",
})


@router.post("/practice/sessions/{session_id}/audio-segments/failure")
async def register_audio_segment_failure(
    session_id: str,
    body: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a failed audio segment upload attempt.

    Request body:
        segment_sequence (int): Segment index that failed.
        error_token (str): One of signing_failed, oss_put_failed,
                           register_failed, network_error, unknown.

    Creates/upserts a SessionAudioSegment row with upload_status="failed"
    and stores the compact error token in error_message. Also updates
    voice_policy_snapshot.runtime_metrics.audio_audit with a bounded
    failure summary (failed_segment_count, last_failure_reason).
    """
    # --- input validation ---
    segment_sequence = body.get("segment_sequence")
    if segment_sequence is None or not isinstance(segment_sequence, int) or segment_sequence < 0:
        return error_response(
            "[INVALID_SEGMENT_SEQUENCE]",
            status_code=422,
            message="segment_sequence must be a non-negative integer",
        )

    error_token = body.get("error_token")
    if not error_token or not isinstance(error_token, str):
        return error_response(
            "[INVALID_ERROR_TOKEN]",
            status_code=422,
            message="error_token must be a non-empty string",
        )
    if error_token not in _AUDIO_FAILURE_TOKENS:
        return error_response(
            "[INVALID_ERROR_TOKEN]",
            status_code=422,
            message=f"error_token must be one of: {', '.join(sorted(_AUDIO_FAILURE_TOKENS))}",
        )

    # --- session ownership check ---
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return error_response("[SESSION_NOT_FOUND]", status_code=404)
    if not _can_read_session(session, current_user):
        return error_response("[ACCESS_DENIED]", status_code=403)

    # --- upsert segment row as failed ---
    existing = await db.execute(
        select(SessionAudioSegment).where(
            SessionAudioSegment.session_id == session_id,
            SessionAudioSegment.segment_sequence == segment_sequence,
        )
    )
    segment = existing.scalar_one_or_none()

    if segment:
        # Only overwrite if not already successfully uploaded
        if segment.upload_status != "uploaded":
            segment.upload_status = "failed"
            segment.error_message = error_token
    else:
        segment = SessionAudioSegment(
            session_id=session_id,
            segment_sequence=segment_sequence,
            object_key=f"audio/{session_id}/seg_{segment_sequence:04d}.webm",
            content_type="audio/webm",
            upload_status="failed",
            error_message=error_token,
        )
        db.add(segment)

    # Ensure PracticeSession.audio_url is set
    if session.audio_url is None:
        session.audio_url = f"audio/{session_id}/"

    await db.flush()

    # --- update voice_policy_snapshot.runtime_metrics.audio_audit ---
    await _update_audio_audit_failure_metrics(db, session, session_id, error_token)

    await db.commit()
    await db.refresh(segment)

    logger.info(
        "audio_segment_failure_registered",
        session_id=session_id,
        segment_sequence=segment_sequence,
        error_token=error_token,
        upload_status="failed",
    )

    return success_response(
        {
            "id": segment.id,
            "session_id": session_id,
            "segment_sequence": segment.segment_sequence,
            "upload_status": segment.upload_status,
            "error_message": segment.error_message,
            "created_at": segment.created_at.isoformat() if segment.created_at else None,
        }
    )


async def _update_audio_audit_failure_metrics(
    db: AsyncSession,
    session: PracticeSession,
    session_id: str,
    error_token: str,
) -> None:
    """Update voice_policy_snapshot.runtime_metrics.audio_audit with failure summary."""
    from sqlalchemy import func as sa_func

    failed_count_result = await db.execute(
        select(sa_func.count(SessionAudioSegment.id)).where(
            SessionAudioSegment.session_id == session_id,
            SessionAudioSegment.upload_status == "failed",
        )
    )
    failed_segment_count = failed_count_result.scalar() or 0

    base_snapshot = (
        deepcopy(session.voice_policy_snapshot)
        if isinstance(session.voice_policy_snapshot, dict)
        else {}
    )
    runtime_metrics = base_snapshot.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        runtime_metrics = {}
    else:
        runtime_metrics = deepcopy(runtime_metrics)

    audio_audit = runtime_metrics.get("audio_audit")
    if not isinstance(audio_audit, dict):
        audio_audit = {}
    else:
        audio_audit = deepcopy(audio_audit)

    audio_audit.update(
        {
            "failed_segment_count": int(failed_segment_count),
            "last_failure_reason": error_token,
        }
    )
    runtime_metrics["audio_audit"] = audio_audit
    base_snapshot["runtime_metrics"] = runtime_metrics
    session.voice_policy_snapshot = base_snapshot
