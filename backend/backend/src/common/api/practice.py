"""
Practice Session API Routes
Provides endpoints for creating and managing practice sessions
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import PracticeSession, Scenario, User
from common.db.session import get_db

router = APIRouter()


# Pydantic schemas
class PracticeSessionCreate(BaseModel):
    scenario_type: str  # "presentation" or "sales"
    presentation_id: str = None


class PracticeSessionResponse(BaseModel):
    session_id: str
    scenario_type: str
    status: str
    start_time: str

    class Config:
        from_attributes = True


@router.post("/sessions", response_model=PracticeSessionResponse)
async def create_session(
    session_data: PracticeSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new practice session

    FR-015: 实时语音对练
    FR-016: 中断与纠错
    """
    # Get scenario
    result = await db.execute(
        select(Scenario).where(Scenario.scenario_type == session_data.scenario_type)
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=400, detail="Invalid scenario type")

    # Create session
    new_session = PracticeSession(
        user_id=current_user.user_id,
        scenario_id=scenario.scenario_id,
        presentation_id=session_data.presentation_id,
        status="preparing"
    )

    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    return PracticeSessionResponse(
        session_id=str(new_session.session_id),
        session_type=session_data.scenario_type,
        status=new_session.status,
        start_time=new_session.start_time.isoformat()
    )


@router.get("/sessions/{session_id}", response_model=PracticeSessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific practice session by ID"""
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check permission
    if str(session.user_id) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return PracticeSessionResponse(
        session_id=str(session.session_id),
        session_type=session.scenario.scenario_type,
        status=session.status,
        start_time=session.start_time.isoformat()
    )


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    End a practice session and calculate scores

    FR-031: 三维评分公式
    Overall_Score = Logic×0.3 + Accuracy×0.4 + Completeness×0.3
    """
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check permission
    if str(session.user_id) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Update session
    session.status = "completed"
    session.end_time = datetime.utcnow()

    # TODO: Calculate scores based on interruptions, coverage, etc.

    await db.commit()

    return {
        "message": "Session ended successfully",
        "session_id": str(session.session_id),
        "scores": {
            "logic": session.logic_score,
            "accuracy": session.accuracy_score,
            "completeness": session.completeness_score
        }
    }
