"""
Users API - User profile and information endpoints

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- VI. Data Privacy & Compliance

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.history_service import history_service
from common.auth.service import get_current_user
from common.db.models import User
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
        result = await history_service.get_user_history_with_report_summary(
            db=db,
            user_id=current_user.user_id,
            page=page,
            page_size=page_size,
            scenario_type=scenario_type,
        )

        if not result.is_success:
            return error_response(result.fallback or "[HISTORY_FAILED]")

        data = result.value

        # Convert dataclasses to dicts for JSON serialization
        sessions = []
        for session in data["sessions"]:
            sessions.append({
                "session_id": session.session_id,
                "scenario_name": session.scenario_name,
                "scenario_type": session.scenario_type,
                "persona_name": session.persona_name,
                "agent_name": session.agent_name,
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "duration_seconds": session.duration_seconds,
                "overall_score": session.overall_score,
                "report_status": session.report_status,
                "report_generated_at": session.report_generated_at.isoformat() if session.report_generated_at else None,
                "status": session.status,
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
