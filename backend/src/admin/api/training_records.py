"""
Admin Training Records API - Training session management for administrators

Implements CRUD operations for viewing and managing all user training records.

References:
- Requirements: 6.1, 6.2, 6.3
- Design: Section "Admin Training Records API"
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.auth.service import get_current_user
from common.db.models import PracticeSession, Scenario, User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/training-records", tags=["admin-training-records"])


# Response schemas
class TrainingRecordResponse(BaseModel):
    """Training record response for admin API"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_type: str
    title: str
    start_time: str
    duration_seconds: int | None
    overall_score: float | None
    user_id: str
    user_name: str | None
    status: str
    agent_name: str | None = None
    persona_name: str | None = None


class TrainingRecordListResponse(BaseModel):
    """Paginated training record list response"""
    items: list[TrainingRecordResponse]
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


def calculate_overall_score(session: PracticeSession) -> float | None:
    """Calculate overall score from dimension scores"""
    scores = [
        session.logic_score,
        session.accuracy_score,
        session.completeness_score
    ]
    valid_scores = [s for s in scores if s is not None]
    if not valid_scores:
        return None
    return round(sum(valid_scores) / len(valid_scores), 1)


def calculate_duration(session: PracticeSession) -> int | None:
    """Calculate session duration in seconds"""
    if session.total_duration_seconds:
        return session.total_duration_seconds
    if session.end_time and session.start_time:
        return int((session.end_time - session.start_time).total_seconds())
    return None


def generate_title(session: PracticeSession, scenario: Scenario | None) -> str:
    """Generate session title from metadata"""
    if scenario:
        type_name = "销售对练" if scenario.scenario_type == "sales" else "演讲练习"
        return f"{type_name} - {scenario.name}" if scenario.name else type_name
    return "练习会话"


async def session_to_response(
    session: PracticeSession,
    scenario: Scenario | None,
    user: User | None,
    db: AsyncSession
) -> TrainingRecordResponse:
    """Convert PracticeSession to TrainingRecordResponse"""
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
    
    return TrainingRecordResponse(
        id=str(session.session_id),
        scenario_type=scenario.scenario_type if scenario else "unknown",
        title=generate_title(session, scenario),
        start_time=session.start_time.isoformat() if session.start_time else "",
        duration_seconds=calculate_duration(session),
        overall_score=calculate_overall_score(session),
        user_id=str(session.user_id),
        user_name=user.name if user else None,
        status=session.status or "unknown",
        agent_name=agent_name,
        persona_name=persona_name
    )


@router.get("", response_model=dict)
async def list_training_records(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by user name or scenario"),
    status: str | None = Query(None, description="Filter by status"),
    scenario_type: str | None = Query(None, description="Filter by scenario type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get all training records (admin view - not filtered by user)
    
    Requirements: 6.1, 6.2
    """
    # Build base query with joins
    query = (
        select(PracticeSession, Scenario, User)
        .outerjoin(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
        .outerjoin(User, PracticeSession.user_id == User.user_id)
    )
    
    count_query = select(func.count()).select_from(PracticeSession)
    
    # Apply search filter
    if search:
        search_filter = or_(
            User.name.ilike(f"%{search}%"),
            Scenario.name.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        # For count, we need to join as well
        count_query = (
            select(func.count())
            .select_from(PracticeSession)
            .outerjoin(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .outerjoin(User, PracticeSession.user_id == User.user_id)
            .where(search_filter)
        )
    
    # Apply status filter
    if status:
        query = query.where(PracticeSession.status == status)
        if search:
            count_query = count_query.where(PracticeSession.status == status)
        else:
            count_query = count_query.where(PracticeSession.status == status)
    
    # Apply scenario type filter
    if scenario_type:
        query = query.where(Scenario.scenario_type == scenario_type)
        if not search:
            count_query = (
                select(func.count())
                .select_from(PracticeSession)
                .outerjoin(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(Scenario.scenario_type == scenario_type)
            )
            if status:
                count_query = count_query.where(PracticeSession.status == status)
    
    # Get total count
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination and ordering
    query = query.order_by(PracticeSession.start_time.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    rows = result.all()
    
    # Convert to response format
    items = []
    for row in rows:
        session, scenario, user = row
        item = await session_to_response(session, scenario, user, db)
        items.append(item)
    
    response = TrainingRecordListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )
    
    return success_response(response.model_dump())


@router.get("/{record_id}", response_model=dict)
async def get_training_record(
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get training record details by ID"""
    result = await db.execute(
        select(PracticeSession, Scenario, User)
        .outerjoin(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
        .outerjoin(User, PracticeSession.user_id == User.user_id)
        .where(PracticeSession.session_id == record_id)
    )
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="[TRAINING_RECORD_NOT_FOUND]")
    
    session, scenario, user = row
    item = await session_to_response(session, scenario, user, db)
    
    return success_response(item.model_dump())


@router.delete("/{record_id}", response_model=dict)
async def delete_training_record(
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Delete a training record
    
    Requirements: 6.3
    """
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == record_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="[TRAINING_RECORD_NOT_FOUND]")
    
    # Delete the session (cascade will handle related records)
    await db.delete(session)
    await db.commit()
    
    return success_response({"deleted": True})
