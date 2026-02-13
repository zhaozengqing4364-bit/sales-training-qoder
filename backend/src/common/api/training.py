"""
Training API - Training categories and session history

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- V. Cost control - Efficient queries

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}

Requirements: 3.1, 3.2, 3.3
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import PracticeSession, Scenario, User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger(__name__)

router = APIRouter()


# ========== Schemas ==========

class TrainingCategory(BaseModel):
    """Training category definition"""
    id: str
    title: str
    description: str
    icon_key: str
    color_theme: str
    agent_count: int = 0
    tags: list[str] = []
    status: Literal["active", "coming_soon", "inactive"] = "active"


class SessionItem(BaseModel):
    """Session history item"""
    id: str
    title: str
    agent_type: str
    start_time: str
    duration_seconds: int
    score: float


class PaginatedSessions(BaseModel):
    """Paginated session list response"""
    total: int
    items: list[SessionItem]
    page: int
    page_size: int
    has_more: bool


# ========== Helper Functions ==========

def success_response(data, trace_id: str = None):
    """Create unified success response"""
    return {
        "success": True,
        "data": data if isinstance(data, (dict, list)) else data.model_dump() if hasattr(data, 'model_dump') else data,
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


# ========== Static Training Categories ==========

# Define training categories with agent counts (will be updated dynamically)
TRAINING_CATEGORIES = [
    TrainingCategory(
        id="sales",
        title="销售对练",
        description="与AI客户进行销售场景模拟，提升沟通技巧和成交能力",
        icon_key="Briefcase",
        color_theme="bg-blue-50 text-blue-600",
        tags=["销售", "沟通", "谈判"],
        status="active"
    ),
    TrainingCategory(
        id="presentation",
        title="演讲练习",
        description="PPT演讲练习，获得实时反馈和改进建议",
        icon_key="Presentation",
        color_theme="bg-purple-50 text-purple-600",
        tags=["演讲", "表达", "PPT"],
        status="active"
    ),
    TrainingCategory(
        id="customer_service",
        title="客服训练",
        description="客户服务场景模拟，提升服务质量和问题解决能力",
        icon_key="Headphones",
        color_theme="bg-green-50 text-green-600",
        tags=["客服", "服务", "沟通"],
        status="coming_soon"
    ),
]


# ========== Endpoints ==========

@router.get("/training-categories")
async def get_training_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of training categories
    
    Returns training categories with agent counts.
    
    Requirements: 3.1
    """
    try:
        # Get agent counts per category from database
        from agent.models import Agent
        
        agent_counts_stmt = select(
            Agent.category,
            func.count(Agent.id).label("count")
        ).where(
            Agent.status == "published"
        ).group_by(Agent.category)
        
        result = await db.execute(agent_counts_stmt)
        agent_counts = {row.category: row.count for row in result}
        
        # Update categories with actual agent counts
        categories = []
        for cat in TRAINING_CATEGORIES:
            cat_copy = cat.model_copy()
            cat_copy.agent_count = agent_counts.get(cat.id, 0)
            categories.append(cat_copy.model_dump())
        
        return success_response(categories)
        
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get training categories: {str(e)}")
        return error_response("[TRAINING_CATEGORIES_FAILED]", "获取训练分类失败")


@router.get("/sessions")
async def get_sessions(
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("start_time:desc", description="Sort field and direction"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's session history with pagination
    
    Supports:
    - limit: Maximum number of items (overrides page_size if smaller)
    - page, page_size: Standard pagination
    - sort: Sort field and direction (e.g., "start_time:desc", "score:asc")
    
    Returns:
    - total: Total number of sessions
    - items: List of session items with id, title, agent_type, start_time, duration_seconds, score
    
    Requirements: 3.1, 3.2, 3.3
    """
    try:
        user_id = str(current_user.user_id)
        
        # Parse sort parameter
        sort_parts = sort.split(":")
        sort_field = sort_parts[0] if sort_parts else "start_time"
        sort_dir = sort_parts[1] if len(sort_parts) > 1 else "desc"
        
        # Build base query
        base_query = select(PracticeSession).where(
            PracticeSession.user_id == user_id
        )
        
        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_query)).scalar() or 0
        
        # Apply sorting
        if sort_field == "start_time":
            order_col = PracticeSession.start_time
        elif sort_field == "score":
            # Sort by average score
            order_col = (
                func.coalesce(PracticeSession.logic_score, 0) +
                func.coalesce(PracticeSession.accuracy_score, 0) +
                func.coalesce(PracticeSession.completeness_score, 0)
            ) / 3
        elif sort_field == "duration":
            order_col = PracticeSession.total_duration_seconds
        else:
            order_col = PracticeSession.start_time
        
        if sort_dir == "asc":
            base_query = base_query.order_by(order_col.asc())
        else:
            base_query = base_query.order_by(order_col.desc())
        
        # Apply pagination - use smaller of limit and page_size
        effective_page_size = min(limit, page_size)
        offset = (page - 1) * effective_page_size
        base_query = base_query.offset(offset).limit(effective_page_size)
        
        # Execute query
        result = await db.execute(base_query)
        sessions = result.scalars().all()
        
        # Transform to response format
        items = []
        for session in sessions:
            # Calculate duration
            if session.total_duration_seconds:
                duration_seconds = session.total_duration_seconds
            elif session.end_time and session.start_time:
                duration_seconds = int((session.end_time - session.start_time).total_seconds())
            else:
                duration_seconds = 0
            
            # Calculate overall score
            logic = session.logic_score or 0
            accuracy = session.accuracy_score or 0
            completeness = session.completeness_score or 0
            score = round((logic + accuracy + completeness) / 3, 1) if any([logic, accuracy, completeness]) else 0
            
            # Determine agent type and title
            agent_type = "sales_bot"  # Default
            title = "练习会话"
            
            # Try to get scenario type
            if session.scenario_id:
                scenario_result = await db.execute(
                    select(Scenario).where(Scenario.scenario_id == session.scenario_id)
                )
                scenario = scenario_result.scalar_one_or_none()
                if scenario:
                    agent_type = scenario.scenario_type
                    if scenario.scenario_type == "presentation":
                        title = "演讲练习"
                    elif scenario.scenario_type == "sales":
                        title = "销售对练"
            
            # Try to get agent/persona names for better title
            if session.agent_id:
                from agent.models import Agent
                agent_result = await db.execute(
                    select(Agent).where(Agent.id == session.agent_id)
                )
                agent = agent_result.scalar_one_or_none()
                if agent:
                    title = agent.name
                    agent_type = agent.category
            
            if session.persona_id:
                from agent.models import Persona
                persona_result = await db.execute(
                    select(Persona).where(Persona.id == session.persona_id)
                )
                persona = persona_result.scalar_one_or_none()
                if persona:
                    title = f"{title} - {persona.name}"
            
            items.append(SessionItem(
                id=str(session.session_id),
                title=title,
                agent_type=agent_type,
                start_time=session.start_time.isoformat() if session.start_time else datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration_seconds,
                score=score
            ).model_dump())
        
        response_data = {
            "total": total,
            "items": items,
            "page": page,
            "page_size": effective_page_size,
            "has_more": (page * effective_page_size) < total
        }
        
        return success_response(response_data)
        
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get sessions: {str(e)}")
        return error_response("[SESSIONS_FAILED]", "获取会话历史失败")
