"""
Admin Training Records API - Training session management for administrators

Implements CRUD operations for viewing and managing all user training records.

References:
- Requirements: 6.1, 6.2, 6.3
- Design: Section "Admin Training Records API"
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_admin_user
from common.db.models import PracticeSession, Scenario, User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/training-records", tags=["admin-training-records"])

# M018/S01/T01 DB performance discovery inventory:
# - keep the admin list baseline next to the route family that still performs row-level metadata lookups.
# - distinguish confirmed N+1 behavior from search/index ideas that still need real Postgres evidence.
TRAINING_RECORDS_DB_PERFORMANCE_BASELINE: tuple[dict[str, Any], ...] = (
    {
        "path": "list_training_records",
        "callers": (
            "list_training_records",
        ),
        "query_shape": (
            "one paginated PracticeSession/Scenario/User join for the page",
            "one count query for the same filters",
            "one batched Agent metadata lookup for all agent ids on the page",
            "one batched Persona metadata lookup for all persona ids on the page",
        ),
        "risk": "row_level_n_plus_one_fixed_with_page_batched_metadata",
        "n_plus_one_risk": "fixed: page size N now triggers at most one Agent and one Persona metadata query after the paged session query",
        "slow_query_candidates": (
            "admin search uses User.name ILIKE / Scenario.name ILIKE and can become expensive on larger tables",
        ),
        "index_candidates": (
            "fix the confirmed row-level N+1 before adding new indexes here",
            "if admin search becomes slow under real Postgres load, validate text-search/trigram support for user/scenario names instead of adding blind btree indexes",
        ),
        "evidence_level": "code_path_confirmed_for_n_plus_one__search_index_priority_still_needs_runtime_postgres_proof",
    },
    {
        "path": "get_training_record",
        "callers": (
            "get_training_record",
        ),
        "query_shape": (
            "one PracticeSession/Scenario/User join for the record",
            "then one bounded batched Agent/Persona metadata lookup for that single record",
        ),
        "risk": "bounded_single_record_metadata_lookup",
        "n_plus_one_risk": "not applicable for a single record; the code path shares the batched map loader for consistency",
        "evidence_level": "code_path_confirmed_but_lower_priority_than_list_endpoint",
    },
)


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
    agent_names: dict[str, str] | None = None,
    persona_names: dict[str, str] | None = None,
) -> TrainingRecordResponse:
    """Convert PracticeSession to TrainingRecordResponse"""
    agent_names = agent_names or {}
    persona_names = persona_names or {}
    agent_name = agent_names.get(str(session.agent_id)) if session.agent_id else None
    persona_name = (
        persona_names.get(str(session.persona_id)) if session.persona_id else None
    )

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


async def load_agent_persona_name_maps(
    sessions: list[PracticeSession],
    db: AsyncSession,
) -> tuple[dict[str, str], dict[str, str]]:
    agent_ids = {
        str(session.agent_id)
        for session in sessions
        if getattr(session, "agent_id", None)
    }
    persona_ids = {
        str(session.persona_id)
        for session in sessions
        if getattr(session, "persona_id", None)
    }

    from agent.models import Agent, Persona

    agent_names: dict[str, str] = {}
    if agent_ids:
        agent_rows = await db.execute(select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids)))
        agent_names = {str(agent_id): name for agent_id, name in agent_rows.all()}

    persona_names: dict[str, str] = {}
    if persona_ids:
        persona_rows = await db.execute(
            select(Persona.id, Persona.name).where(Persona.id.in_(persona_ids))
        )
        persona_names = {
            str(persona_id): name for persona_id, name in persona_rows.all()
        }

    return agent_names, persona_names


@router.get("", response_model=dict)
async def list_training_records(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by user name or scenario"),
    status: str | None = Query(None, description="Filter by status"),
    scenario_type: str | None = Query(None, description="Filter by scenario type"),
    current_user: User = Depends(get_current_admin_user),
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
    sessions = [row[0] for row in rows]
    agent_names, persona_names = await load_agent_persona_name_maps(sessions, db)

    # Convert to response format
    items = []
    for row in rows:
        session, scenario, user = row
        item = await session_to_response(
            session,
            scenario,
            user,
            agent_names=agent_names,
            persona_names=persona_names,
        )
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
    current_user: User = Depends(get_current_admin_user),
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
    agent_names, persona_names = await load_agent_persona_name_maps([session], db)
    item = await session_to_response(
        session,
        scenario,
        user,
        agent_names=agent_names,
        persona_names=persona_names,
    )

    return success_response(item.model_dump())


@router.delete("/{record_id}", response_model=dict)
async def delete_training_record(
    record_id: str,
    current_user: User = Depends(get_current_admin_user),
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
