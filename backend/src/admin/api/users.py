"""
Admin Users API - User management endpoints for administrators

Implements CRUD operations for user management.

References:
- Requirements: 4.1, 4.2, 4.3, 4.4
- Design: Section "Admin Users API"
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# Request schemas
class CreateUserRequest(BaseModel):
    """Request to create a new user"""
    username: str
    email: EmailStr
    password: str
    name: str | None = None
    department: str | None = None
    role: str = "user"  # user | admin

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码至少需要8位")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码需要包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码需要包含数字")
        return v


class UpdateUserRequest(BaseModel):
    """Request to update user"""
    name: str | None = None
    email: EmailStr | None = None
    department: str | None = None
    role: str | None = None
    is_active: bool | None = None


# Response schemas
class AdminUserResponse(BaseModel):
    """User response for admin API"""
    id: str
    username: str
    email: str | None
    role: str
    status: str
    last_active_at: str | None
    department: str | None
    created_at: str | None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response"""
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


def success_response(data: Any, trace_id: str | None = None) -> dict:
    """Create unified success response"""
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, message: str | None = None, trace_id: str | None = None) -> dict:
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id()
    }


def user_to_response(user: User) -> AdminUserResponse:
    """Convert User model to AdminUserResponse"""
    return AdminUserResponse(
        id=str(user.user_id),
        username=user.name or "",
        email=user.email,
        role=getattr(user, 'role', 'user'),  # Use actual role field
        status="active" if user.is_active else "inactive",
        last_active_at=user.last_login.isoformat() if user.last_login else None,
        department=user.department,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


@router.get("", response_model=dict)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by name or email"),
    status: str | None = Query(None, description="Filter by status (active/inactive)"),
    role: str | None = Query(None, description="Filter by role"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get paginated user list with filtering

    Requirements: 4.1, 4.2, 4.3
    """
    # Build base query
    query = select(User)
    count_query = select(func.count()).select_from(User)

    # Apply search filter
    if search:
        search_filter = or_(
            User.name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Apply status filter
    if status:
        is_active = status.lower() == "active"
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    # Note: role filter is handled at response level since User model doesn't have role field

    # Get total count
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    # Convert to response format
    items = [user_to_response(u) for u in users]

    # Apply role filter at response level if needed
    if role:
        items = [item for item in items if item.role == role]

    response = UserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )

    return success_response(response.model_dump())


@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get user details by ID"""
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    return success_response(user_to_response(user).model_dump())


@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Delete a user (soft delete by setting is_active=False)

    Requirements: 4.4
    """
    # Prevent self-deletion
    if str(current_user.user_id) == user_id:
        raise HTTPException(status_code=400, detail="[CANNOT_DELETE_SELF]")

    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    # Soft delete - set is_active to False
    user.is_active = False
    await db.commit()

    return success_response({"deleted": True})


@router.post("", response_model=dict)
async def create_user(
    request: CreateUserRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Create a new user

    Requirements: 4.1
    """
    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="[EMAIL_ALREADY_EXISTS]")

    # Create new user
    new_user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin_created_{uuid.uuid4().hex[:8]}",  # Placeholder for admin-created users
        name=request.name or request.username,
        email=request.email,
        department=request.department,
        role=request.role,
        is_active=True,
        created_at=datetime.utcnow()
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"User created: {new_user.user_id} by admin {current_user.user_id}")

    return success_response(user_to_response(new_user).model_dump())


@router.put("/{user_id}", response_model=dict)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Update user information

    Requirements: 4.2
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    is_self = str(current_user.user_id) == user_id

    # Prevent self role downgrade
    if is_self and request.role is not None and request.role != "admin":
        raise HTTPException(status_code=400, detail="[CANNOT_DOWNGRADE_SELF]")

    # Prevent self deactivation
    if is_self and request.is_active is False:
        raise HTTPException(status_code=400, detail="[CANNOT_DEACTIVATE_SELF]")

    # Prevent removing the last admin
    if request.role is not None and request.role != "admin" and user.role == "admin":
        admin_count = await db.execute(
            select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
        )
        if (admin_count.scalar() or 0) <= 1:
            raise HTTPException(status_code=400, detail="[CANNOT_REMOVE_LAST_ADMIN]")

    # Check email uniqueness if changing
    if request.email and request.email != user.email:
        existing = await db.execute(
            select(User).where(User.email == request.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="[EMAIL_ALREADY_EXISTS]")
        user.email = request.email

    # Update fields
    if request.name is not None:
        user.name = request.name
    if request.department is not None:
        user.department = request.department
    if request.role is not None:
        user.role = request.role
    if request.is_active is not None:
        user.is_active = request.is_active

    await db.commit()
    await db.refresh(user)

    logger.info(f"User updated: {user_id} by admin {current_user.user_id}")

    return success_response(user_to_response(user).model_dump())


@router.post("/{user_id}/suspend", response_model=dict)
async def suspend_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Suspend a user account

    Requirements: 4.3
    """
    # Prevent self-suspension
    if str(current_user.user_id) == user_id:
        raise HTTPException(status_code=400, detail="[CANNOT_SUSPEND_SELF]")

    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    user.is_active = False
    await db.commit()

    logger.info(f"User suspended: {user_id} by admin {current_user.user_id}")

    return success_response({"suspended": True, "user_id": user_id})


@router.post("/{user_id}/activate", response_model=dict)
async def activate_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Activate a suspended user account
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    user.is_active = True
    await db.commit()

    logger.info(f"User activated: {user_id} by admin {current_user.user_id}")

    return success_response({"activated": True, "user_id": user_id})


@router.get("/export", response_class=StreamingResponse)
async def export_users(
    format: str = Query("csv", description="Export format: csv or json"),
    search: str | None = Query(None, description="Search filter"),
    status: str | None = Query(None, description="Status filter"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export users to CSV or JSON

    Requirements: 4.5
    """
    # Build query
    query = select(User)

    if search:
        search_filter = or_(
            User.name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)

    if status:
        is_active = status.lower() == "active"
        query = query.where(User.is_active == is_active)

    result = await db.execute(query.order_by(User.created_at.desc()))
    users = result.scalars().all()

    # Convert to response format
    user_data = [user_to_response(u).model_dump() for u in users]

    if format.lower() == "json":
        # JSON export
        content = json.dumps(user_data, ensure_ascii=False, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=users_export.json"}
        )
    else:
        # CSV export
        output = io.StringIO()
        if user_data:
            writer = csv.DictWriter(output, fieldnames=user_data[0].keys())
            writer.writeheader()
            writer.writerows(user_data)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=users_export.csv"}
        )
