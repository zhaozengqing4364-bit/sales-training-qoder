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
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import PracticeSession, Scenario, User
from common.db.schemas import (
    SessionCreate,
    SessionDetail,
    SessionReport,
    SessionResponse,
    SessionUpdate,
)
from common.db.session import get_db
from common.error_handling.result import Result
from common.monitoring.logger import get_logger, get_trace_id
from presentation_coach.services.coach_service import PresentationCoachService
from sales_bot.services.bot_service import Persona, sales_bot_service
from sales_bot.services.summary_service import summary_service

logger = get_logger(__name__)

router = APIRouter()


def success_response(data, trace_id: str = None):
    """Create unified success response"""
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, trace_id: str = None):
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "trace_id": trace_id or get_trace_id()
    }


@router.post("/practice/sessions")
async def start_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
            if hasattr(session_data.scenario_type, 'value') 
            else session_data.scenario_type
        )
        
        # Validate Agent-Persona association if both provided (R12.2)
        agent_id_str = str(session_data.agent_id) if session_data.agent_id else None
        persona_id_str = str(session_data.persona_id) if session_data.persona_id else None
        
        if agent_id_str and persona_id_str:
            from agent.models import Agent, AgentPersona, Persona
            
            # Check Agent exists and is published
            agent_result = await db.execute(
                select(Agent).where(Agent.id == agent_id_str)
            )
            agent = agent_result.scalar_one_or_none()
            if not agent:
                return error_response("[AGENT_NOT_FOUND]")
            if agent.status != "published":
                return error_response("[AGENT_NOT_PUBLISHED]")
            
            # Check Persona exists
            persona_result = await db.execute(
                select(Persona).where(Persona.id == persona_id_str)
            )
            persona_obj = persona_result.scalar_one_or_none()
            if not persona_obj:
                return error_response("[PERSONA_NOT_FOUND]")
            
            # Check Persona is linked to Agent (R12.2)
            link_result = await db.execute(
                select(AgentPersona).where(
                    AgentPersona.agent_id == agent_id_str,
                    AgentPersona.persona_id == persona_id_str
                )
            )
            link = link_result.scalar_one_or_none()
            if not link:
                return error_response("[PERSONA_NOT_LINKED_TO_AGENT]")
        
        if scenario_type_value == "presentation":
            coach_service = PresentationCoachService(db)

            result = await coach_service.create_session(
                user_id=str(current_user.user_id),
                presentation_id=str(session_data.presentation_id)
            )

            if not result.is_success:
                return error_response("[SESSION_CREATE_FAILED]")

            session = result.value
            
            # Update with agent/persona if provided
            if agent_id_str:
                session.agent_id = agent_id_str
            if persona_id_str:
                session.persona_id = persona_id_str
            await db.commit()
            await db.refresh(session)

        elif scenario_type_value == "sales":
            # Sales bot session - support both legacy and enhanced modes
            
            # Enhanced mode: use agent_id + persona_id
            if agent_id_str and persona_id_str:
                # Find or create sales scenario for this agent
                scenario_result = await db.execute(
                    select(Scenario).where(
                        Scenario.scenario_type == "sales",
                        Scenario.name == f"agent_{agent_id_str}"
                    )
                )
                scenario = scenario_result.scalar_one_or_none()
                
                if not scenario:
                    scenario = Scenario(
                        scenario_id=str(uuid.uuid4()),
                        scenario_type="sales",
                        name=f"agent_{agent_id_str}",
                        description=f"Sales practice with Agent Platform",
                        is_active=True
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
                    status="preparing"
                )
                db.add(session)
                await db.commit()
                await db.refresh(session)
                
            else:
                # Legacy mode: use sales_persona
                if not session_data.sales_persona:
                    return error_response("[SALES_PERSONA_REQUIRED]")

                # Validate persona
                try:
                    persona = Persona(session_data.sales_persona)
                except ValueError:
                    return error_response("[INVALID_PERSONA]")

                # Find or create sales scenario
                scenario_result = await db.execute(
                    select(Scenario).where(
                        Scenario.scenario_type == "sales",
                        Scenario.name == f"sales_{session_data.sales_persona}"
                    )
                )
                scenario = scenario_result.scalar_one_or_none()
                
                if not scenario:
                    scenario = Scenario(
                        scenario_id=str(uuid.uuid4()),
                        scenario_type="sales",
                        name=f"sales_{session_data.sales_persona}",
                        description=f"Sales practice with {session_data.sales_persona} persona",
                        is_active=True
                    )
                    db.add(scenario)
                    await db.flush()

                # Create bot session
                user_id_uuid = uuid.UUID(str(current_user.user_id))
                scenario_id_uuid = uuid.UUID(scenario.scenario_id)
                
                result = await sales_bot_service.create_session(
                    user_id=user_id_uuid,
                    persona=persona,
                    scenario_id=scenario_id_uuid
                )

                if not result.is_success:
                    return error_response("[BOT_SESSION_CREATE_FAILED]")

                # Create practice session record
                session = PracticeSession(
                    session_id=str(result.value),
                    user_id=str(current_user.user_id),
                    scenario_id=scenario.scenario_id,
                    status="preparing"
                )

                db.add(session)
                await db.commit()
                await db.refresh(session)

        else:
            return error_response("[INVALID_SCENARIO_TYPE]")

        return success_response(SessionResponse.model_validate(session))

    except Exception as e:
        logger.error(f"Failed to start session: {str(e)}")
        return error_response("[SESSION_CREATE_FAILED]")


@router.get("/practice/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get session details"""
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]")

    # Verify ownership
    if str(session.user_id) != str(current_user.user_id):
        return error_response("[ACCESS_DENIED]")

    return success_response(SessionDetail.model_validate(session))


@router.patch("/practice/sessions/{session_id}")
async def update_session(
    session_id: str,
    update_data: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update session status"""
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]")

    # Verify ownership
    if str(session.user_id) != str(current_user.user_id):
        return error_response("[ACCESS_DENIED]")

    # Update fields
    if update_data.status:
        session.status = update_data.status.value

    if update_data.current_page is not None:
        session.current_page = update_data.current_page

    await db.commit()
    await db.refresh(session)

    return success_response(SessionResponse.model_validate(session))


@router.delete("/practice/sessions/{session_id}")
async def end_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End session and generate report

    Supports both presentation and sales_bot sessions
    """
    # Get session to determine type
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]")

    # Verify ownership
    if str(session.user_id) != str(current_user.user_id):
        return error_response("[ACCESS_DENIED]")

    # Check scenario type from scenario
    scenario_result = await db.execute(
        select(Scenario).where(Scenario.scenario_id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()

    if not scenario:
        return error_response("[SCENARIO_NOT_FOUND]")

    if scenario.scenario_type == "presentation":
        # PPT coaching session
        coach_service = PresentationCoachService(db)
        result = await coach_service.end_session(session_id)

        if not result.is_success:
            return error_response("[SESSION_END_FAILED]")

        session = result.value

        # Generate report
        report = SessionReport(
            session_id=session.session_id,
            logic_score=session.logic_score or 0,
            accuracy_score=session.accuracy_score or 0,
            completeness_score=session.completeness_score or 0,
            overall_score=(
                (session.logic_score or 0) +
                (session.accuracy_score or 0) +
                (session.completeness_score or 0)
            ) / 3,
            suggestions=["Great practice! Keep working on your presentation skills."],
            audio_url=session.audio_url,
            transcript_url=session.transcript_url
        )

    elif scenario.scenario_type == "sales":
        # Sales bot session - generate summary
        summary_result = await summary_service.generate_summary(uuid.UUID(session_id))

        if not summary_result.is_success:
            return error_response("[SUMMARY_GENERATION_FAILED]")

        summary = summary_result.value

        # End bot session
        await sales_bot_service.end_session(uuid.UUID(session_id))

        # Generate report from summary
        report = SessionReport(
            session_id=session_id,
            logic_score=summary.score_confidence,
            accuracy_score=summary.score_persuasion,
            completeness_score=summary.score_clarity,
            overall_score=(
                summary.score_confidence +
                summary.score_persuasion +
                summary.score_clarity
            ) / 3,
            suggestions=[
                *summary.strengths,
                f"Improvement: {summary.actionable_feedback}"
            ],
            audio_url=None,  # Sales bot doesn't store audio by default
            transcript_url=None
        )

    else:
        return error_response("[INVALID_SCENARIO_TYPE]")

    return success_response(report)


@router.get("/practice/sessions/{session_id}/report")
async def get_session_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get session report with scores"""
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return error_response("[SESSION_NOT_FOUND]")

    # Verify ownership
    if str(session.user_id) != str(current_user.user_id):
        return error_response("[ACCESS_DENIED]")

    # Generate report
    report = SessionReport(
        session_id=session.session_id,
        logic_score=session.logic_score or 0,
        accuracy_score=session.accuracy_score or 0,
        completeness_score=session.completeness_score or 0,
        overall_score=(
            (session.logic_score or 0) +
            (session.accuracy_score or 0) +
            (session.completeness_score or 0)
        ) / 3,
        suggestions=["Review your performance and practice again!"],
        audio_url=session.audio_url,
        transcript_url=session.transcript_url
    )

    return success_response(report)


@router.get("/practice/history")
async def get_practice_history(
    scenario_type: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's practice history with pagination"""
    # Build base query
    query = select(PracticeSession).where(
        PracticeSession.user_id == current_user.user_id
    )

    if scenario_type:
        # Join with scenario to filter by type
        query = query.join(Scenario).where(Scenario.scenario_type == scenario_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(PracticeSession.start_time.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    sessions = result.scalars().all()

    return success_response({
        "items": [SessionResponse.model_validate(s) for s in sessions],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total
    })


# ========== Enhanced Session Endpoints (R12) ==========

@router.get("/sessions/stats")
async def get_session_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
    total_stmt = select(func.count()).where(
        PracticeSession.user_id == user_id
    )
    total_sessions = (await db.execute(total_stmt)).scalar() or 0
    
    # Weekly sessions (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_stmt = select(func.count()).where(
        PracticeSession.user_id == user_id,
        PracticeSession.start_time >= week_ago
    )
    weekly_sessions = (await db.execute(weekly_stmt)).scalar() or 0
    
    # Completed sessions
    completed_stmt = select(func.count()).where(
        PracticeSession.user_id == user_id,
        PracticeSession.status == "completed"
    )
    completed_sessions = (await db.execute(completed_stmt)).scalar() or 0
    
    # Average score (from completed sessions with scores)
    avg_stmt = select(
        func.avg(
            (func.coalesce(PracticeSession.logic_score, 0) +
             func.coalesce(PracticeSession.accuracy_score, 0) +
             func.coalesce(PracticeSession.completeness_score, 0)) / 3
        )
    ).where(
        PracticeSession.user_id == user_id,
        PracticeSession.status == "completed"
    )
    average_score = (await db.execute(avg_stmt)).scalar() or 0.0
    
    # Total practice minutes
    duration_stmt = select(
        func.sum(PracticeSession.total_duration_seconds)
    ).where(
        PracticeSession.user_id == user_id
    )
    total_seconds = (await db.execute(duration_stmt)).scalar() or 0
    total_practice_minutes = total_seconds // 60
    
    stats = SessionStats(
        total_sessions=total_sessions,
        weekly_sessions=weekly_sessions,
        average_score=round(average_score, 1),
        completed_sessions=completed_sessions,
        total_practice_minutes=total_practice_minutes
    )
    
    return success_response(stats)


@router.get("/sessions/{session_id}/enhanced-report")
async def get_enhanced_session_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get enhanced session report with dimension scores (R12.3)
    
    Returns detailed report including:
    - Dimension scores with weights
    - Strengths and improvements
    - Suggestions
    - Highlights from the session
    """
    from common.db.schemas import (
        DimensionScore,
        EnhancedSessionReport,
        SessionHighlight,
    )
    from common.conversation.models import ConversationMessage
    
    # Get session
    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        return error_response("[SESSION_NOT_FOUND]")
    
    # Verify ownership
    if str(session.user_id) != str(current_user.user_id):
        return error_response("[ACCESS_DENIED]")
    
    # Check session is completed
    if session.status != "completed":
        return error_response("[SESSION_NOT_COMPLETED]")
    
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
        select(ConversationMessage).where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.is_highlight == True
        ).order_by(ConversationMessage.turn_number)
    )
    highlight_messages = messages_result.scalars().all()
    
    # Build highlights
    highlights = []
    for msg in highlight_messages:
        highlights.append(SessionHighlight(
            message_id=str(msg.id),
            turn_number=msg.turn_number,
            highlight_type=msg.highlight_type or "neutral",
            reason=msg.highlight_reason or "",
            content=msg.content[:200] if msg.content else ""
        ))
    
    # Calculate dimension scores from session data
    dimension_scores = []
    
    # Use existing scores if available
    if session.logic_score is not None:
        dimension_scores.append(DimensionScore(
            name="逻辑性",
            score=session.logic_score,
            weight=0.33
        ))
    if session.accuracy_score is not None:
        dimension_scores.append(DimensionScore(
            name="准确性",
            score=session.accuracy_score,
            weight=0.33
        ))
    if session.completeness_score is not None:
        dimension_scores.append(DimensionScore(
            name="完整性",
            score=session.completeness_score,
            weight=0.34
        ))
    
    # If no dimension scores, try to get from last message's score_snapshot
    if not dimension_scores:
        last_msg_result = await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.session_id == session_id,
                ConversationMessage.score_snapshot.isnot(None)
            ).order_by(ConversationMessage.turn_number.desc()).limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()
        
        if last_msg and last_msg.score_snapshot:
            snapshot = last_msg.score_snapshot
            if isinstance(snapshot, dict) and "dimensions" in snapshot:
                for dim in snapshot["dimensions"]:
                    dimension_scores.append(DimensionScore(
                        name=dim.get("name", ""),
                        score=dim.get("score", 0),
                        weight=dim.get("weight", 0.2)
                    ))
    
    # Calculate overall score
    if dimension_scores:
        total_weight = sum(d.weight for d in dimension_scores)
        overall_score = sum(d.score * d.weight for d in dimension_scores) / total_weight if total_weight > 0 else 0
    else:
        overall_score = (
            (session.logic_score or 0) +
            (session.accuracy_score or 0) +
            (session.completeness_score or 0)
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
        "尝试不同难度的角色进行练习"
    ]
    
    # Calculate duration
    duration_seconds = None
    if session.end_time and session.start_time:
        duration_seconds = int((session.end_time - session.start_time).total_seconds())
    elif session.total_duration_seconds:
        duration_seconds = session.total_duration_seconds
    
    # Count total turns
    turn_count_result = await db.execute(
        select(func.count()).where(
            ConversationMessage.session_id == session_id
        )
    )
    total_turns = (turn_count_result.scalar() or 0) // 2  # Divide by 2 for user turns only
    
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
        persona_name=persona_name
    )
    
    return success_response(report)
