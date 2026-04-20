"""
Users API - User profile and information endpoints

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- VI. Data Privacy & Compliance

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.history_service import history_service
from common.auth.service import get_current_user
from common.db.models import ManagerIntervention, User, UserTrainingPreference
from common.db.schemas import (
    UserTrainingPreferencesResponse,
    UserTrainingPreferencesUpdate,
)
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter()


# ========== Schemas ==========

class UserSettings(BaseModel):
    """User settings schema"""

    notifications_enabled: bool = True
    language: str = "zh-CN"
    theme: str = "light"


class UserMeResponse(BaseModel):
    """Response schema for /users/me endpoint"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    avatar_url: str | None = None
    role: str = "user"
    department: str | None = None
    email: str | None = None
    settings: UserSettings = UserSettings()


class UserMeUpdateRequest(BaseModel):
    """Partial update schema for /users/me PATCH."""

    name: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None


# ========== Helper Functions ==========

def success_response(data, trace_id: str = None):
    """Create unified success response"""

    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id(),
    }


def error_response(error_code: str, message: str = None, trace_id: str = None):
    """Create unified error response"""

    return {
        "success": False,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id(),
    }


def _serialize_open_intervention(
    intervention: ManagerIntervention | None,
) -> dict[str, str | None] | None:
    if intervention is None:
        return None

    return {
        "intervention_id": str(intervention.intervention_id),
        "issue_family": str(intervention.issue_family),
        "note": intervention.note,
        "due_state": str(intervention.due_state),
        "reminder_status": str(intervention.reminder_status),
        "reminder_sent_at": (
            intervention.reminder_sent_at.isoformat()
            if intervention.reminder_sent_at
            else None
        ),
        "created_at": intervention.created_at.isoformat(),
        "updated_at": intervention.updated_at.isoformat(),
    }


def _normalize_training_preference_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _serialize_training_preferences(
    preferences: UserTrainingPreference | None,
) -> UserTrainingPreferencesResponse:
    if preferences is None:
        return UserTrainingPreferencesResponse()

    return UserTrainingPreferencesResponse(
        voice_mode=preferences.voice_mode,
        agent_id=preferences.agent_id,
        persona_id=preferences.persona_id,
        presentation_id=preferences.presentation_id,
        updated_at=preferences.updated_at,
    )


def _build_user_me_response(current_user: User) -> UserMeResponse:
    """Build normalized current-user response payload."""

    user_role = getattr(current_user, "role", None) or "user"

    settings = UserSettings(
        notifications_enabled=True,
        language="zh-CN",
        theme="light",
    )

    return UserMeResponse(
        id=str(current_user.user_id),
        display_name=current_user.name or "用户",
        avatar_url=None,
        role=user_role,
        department=current_user.department,
        email=current_user.email,
        settings=settings,
    )


# ========== Endpoints ==========

@router.get("/users/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user information

    Returns:
    - id: User ID
    - display_name: User's display name
    - avatar_url: User's avatar URL (if available)
    - role: User's role (user/support/admin)
    - department: User's department
    - email: User email
    - settings: User settings (notifications, language, theme)

    Requirements: 1.1, 1.2
    """
    try:
        user_data = _build_user_me_response(current_user)
        return success_response(user_data.model_dump())

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get user info: {str(e)}")
        return error_response("[USER_INFO_FAILED]", "获取用户信息失败")


@router.patch("/users/me")
async def update_current_user_info(
    request: UserMeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user profile fields.

    Supports partial updates for:
    - name
    - department
    - email
    """
    try:
        updates: dict[str, str | None] = {}

        if request.name is not None:
            clean_name = request.name.strip()
            if clean_name:
                updates["name"] = clean_name

        if request.department is not None:
            clean_department = request.department.strip()
            updates["department"] = clean_department or None

        if request.email is not None:
            clean_email = str(request.email).strip().lower()
            if clean_email:
                duplicate_result = await db.execute(
                    select(User).where(
                        User.email == clean_email,
                        User.user_id != current_user.user_id,
                    )
                )
                duplicate_user = duplicate_result.scalar_one_or_none()
                if duplicate_user:
                    return error_response("[EMAIL_ALREADY_EXISTS]", "邮箱已被使用")
                updates["email"] = clean_email

        for field_name, value in updates.items():
            setattr(current_user, field_name, value)

        if updates:
            await db.commit()
            await db.refresh(current_user)

        user_data = _build_user_me_response(current_user)
        return success_response(user_data.model_dump())

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to update user info: {str(e)}")
        await db.rollback()
        return error_response("[USER_UPDATE_FAILED]", "更新用户信息失败")


@router.get("/users/me/training-preferences")
async def get_my_training_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user's saved training preferences only."""
    try:
        result = await db.execute(
            select(UserTrainingPreference).where(
                UserTrainingPreference.user_id == str(current_user.user_id)
            )
        )
        preferences = result.scalar_one_or_none()
        return success_response(_serialize_training_preferences(preferences).model_dump())
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get training preferences: {str(e)}")
        return error_response("[TRAINING_PREFERENCES_FAILED]", "获取训练偏好失败")


@router.patch("/users/me/training-preferences")
async def update_my_training_preferences(
    request: UserTrainingPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert current user's training preferences; user_id is never accepted."""
    try:
        result = await db.execute(
            select(UserTrainingPreference).where(
                UserTrainingPreference.user_id == str(current_user.user_id)
            )
        )
        preferences = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if preferences is None:
            preferences = UserTrainingPreference(
                user_id=str(current_user.user_id),
                created_at=now,
            )
            db.add(preferences)

        preferences.voice_mode = request.voice_mode
        preferences.agent_id = _normalize_training_preference_id(request.agent_id)
        preferences.persona_id = _normalize_training_preference_id(request.persona_id)
        preferences.presentation_id = _normalize_training_preference_id(request.presentation_id)
        preferences.updated_at = now

        await db.commit()
        await db.refresh(preferences)

        return success_response(_serialize_training_preferences(preferences).model_dump())
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to update training preferences: {str(e)}")
        await db.rollback()
        return error_response("[TRAINING_PREFERENCES_UPDATE_FAILED]", "更新训练偏好失败")


@router.get("/users/me/interventions/open")
async def get_my_open_intervention(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest unresolved manager intervention for the current learner only."""
    try:
        result = await db.execute(
            select(ManagerIntervention)
            .where(
                ManagerIntervention.user_id == str(current_user.user_id),
                ManagerIntervention.due_state.in_(["pending", "due"]),
                ManagerIntervention.resolving_session_id.is_(None),
            )
            .order_by(
                ManagerIntervention.updated_at.desc(),
                ManagerIntervention.created_at.desc(),
            )
            .limit(1)
        )
        intervention = result.scalar_one_or_none()
        return success_response(_serialize_open_intervention(intervention))

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get open manager intervention: {str(e)}")
        return error_response("[OPEN_INTERVENTION_FAILED]", "获取主管提醒失败")


@router.get("/users/me/history")
async def get_my_history(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    scenario_type: str | None = Query(None, description="Filter by scenario type (sales/presentation)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's practice history with report summary (Story 3.2).

    Returns paginated list of practice sessions with report summary including:
    - session_id: Session ID
    - scenario_name: Scenario name
    - scenario_type: Scenario type (sales/presentation)
    - persona_name: Persona name (if available)
    - agent_name: Agent name (if available)
    - start_time: Session start time
    - duration_seconds: Session duration in seconds
    - overall_score: Overall score from report (if available)
    - report_status: Report generation status (pending/processing/completed/failed)

    Permission: Current user only (enforced by JWT)
    """
    try:
        normalized_scenario_type = history_service.normalize_scenario_type(scenario_type)
        result = await history_service.get_user_history_with_report_summary(
            db=db,
            user_id=current_user.user_id,
            page=page,
            page_size=page_size,
            scenario_type=normalized_scenario_type,
        )

        if not result.is_success:
            return error_response(result.fallback or "[HISTORY_FAILED]")

        data = result.value

        # Convert dataclasses to dicts for JSON serialization
        sessions = []
        for session in data["sessions"]:
            sessions.append({
                "session_id": session.session_id,
                "scenario_id": session.scenario_id,
                "scenario_name": session.scenario_name,
                "scenario_type": session.scenario_type,
                "persona_name": session.persona_name,
                "agent_name": session.agent_name,
                "title": session.title,
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "duration_seconds": session.duration_seconds,
                "overall_score": session.overall_score,
                "logic_score": session.logic_score,
                "accuracy_score": session.accuracy_score,
                "completeness_score": session.completeness_score,
                "report_status": session.report_status,
                "report_generated_at": session.report_generated_at.isoformat() if session.report_generated_at else None,
                "status": session.status,
                "evaluable": session.evaluable,
                "not_evaluable_reason": session.not_evaluable_reason,
                "evidence_completeness": session.evidence_completeness,
                "effectiveness_snapshot": session.effectiveness_snapshot,
                "feedback_summary": session.feedback_summary,
                "stage_summary": session.stage_summary,
                "main_issue": session.main_issue,
                "next_goal": session.next_goal,
            })

        return success_response({
            "sessions": sessions,
            "total": data["total"],
            "page": data["page"],
            "page_size": data["page_size"],
            "total_pages": data["total_pages"],
        })

    except Exception as e:
        logger.error(f"Failed to get user history: {str(e)}")
        return error_response("[HISTORY_FAILED]", "获取历史记录失败")
