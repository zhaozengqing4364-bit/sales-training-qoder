"""
Users API - User profile and information endpoints

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- VI. Data Privacy & Compliance

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

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
    settings: UserSettings = UserSettings()


# ========== Helper Functions ==========

def success_response(data, trace_id: str = None):
    """Create unified success response"""
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, message: str = None, trace_id: str = None):
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id()
    }


# ========== Endpoints ==========

@router.get("/users/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user information
    
    Returns:
    - id: User ID
    - display_name: User's display name
    - avatar_url: User's avatar URL (if available)
    - role: User's role (user/admin)
    - department: User's department
    - settings: User settings (notifications, language, theme)
    
    Requirements: 1.1, 1.2
    """
    try:
        # Get actual role from database
        user_role = getattr(current_user, 'role', None) or 'user'

        # Build user settings (can be extended with actual settings storage)
        settings = UserSettings(
            notifications_enabled=True,
            language="zh-CN",
            theme="light"
        )

        user_data = UserMeResponse(
            id=str(current_user.user_id),
            display_name=current_user.name or "用户",
            avatar_url=None,  # Can be extended with avatar storage
            role=user_role,
            department=current_user.department,
            settings=settings
        )

        return success_response(user_data.model_dump())

    except Exception as e:
        logger.error(f"Failed to get user info: {str(e)}")
        return error_response("[USER_INFO_FAILED]", "获取用户信息失败")
