"""
Practice History Query Service - Queries and retrieves practice history

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation
- V. Cost control - Efficient queries

Story 3.2: 学员历史记录与报告摘要列表
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.db.models import PracticeSession, Scenario, ComprehensiveReport
from common.error_handling.result import Result
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass
class SessionWithReportSummary:
    """Session with report summary for history list."""
    session_id: str
    scenario_name: str
    scenario_type: str
    persona_name: str | None
    agent_name: str | None
    start_time: datetime
    duration_seconds: int
    overall_score: float | None
    report_status: str
    report_generated_at: datetime | None
    status: str


class HistoryService:
    """
    Queries practice history for users

    Key responsibilities:
    - Get user's practice sessions
    - Filter by scenario type, date range
    - Sort by various criteria
    - Paginate results
    """

    async def get_user_history(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        scenario_type: str | None = None,
        limit: int = 20,
        offset: int = 0
    ) -> Result[list]:
        """
        Get practice history for a user

        Returns: List of sessions or Result.fail
        """
        try:
            query = (
                select(PracticeSession)
                .options(
                    selectinload(PracticeSession.scenario),
                    selectinload(PracticeSession.presentation)
                )
                .where(PracticeSession.user_id == user_id)
                .order_by(desc(PracticeSession.start_time))
                .limit(limit)
                .offset(offset)
            )

            # Filter by scenario type if specified
            if scenario_type:
                query = query.join(Scenario).where(Scenario.scenario_type == scenario_type)

            result = await db.execute(query)
            sessions = result.scalars().all()

            logger.info(
                "User history retrieved",
                extra={
                    "user_id": str(user_id),
                    "count": len(sessions),
                }
            )

            return Result(value=sessions)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to get user history",
                extra={"user_id": str(user_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[HISTORY_FAILED]")

    async def get_session_detail(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID
    ) ->Result[PracticeSession]:
        """
        Get detailed information about a specific session

        Returns: PracticeSession or Result.fail
        """
        try:
            query = (
                select(PracticeSession)
                .options(
                    selectinload(PracticeSession.scenario),
                    selectinload(PracticeSession.presentation)
                )
                .where(PracticeSession.session_id == session_id)
                .where(PracticeSession.user_id == user_id)
            )

            result = await db.execute(query)
            session = result.scalar_one_or_none()

            if not session:
                return Result.fail(fallback="[SESSION_NOT_FOUND]")

            logger.info(
                "Session detail retrieved",
                extra={"session_id": str(session_id)}
            )

            return Result(value=session)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to get session detail",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[DETAIL_FAILED]")

    async def get_recent_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        days: int = 7,
        limit: int = 10
    ) -> Result[list]:
        """
        Get recent practice sessions for a user

        Returns: List of sessions or Result.fail
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            query = (
                select(PracticeSession)
                .options(
                    selectinload(PracticeSession.scenario),
                    selectinload(PracticeSession.presentation)
                )
                .where(PracticeSession.user_id == user_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .order_by(desc(PracticeSession.start_time))
                .limit(limit)
            )

            result = await db.execute(query)
            sessions = result.scalars().all()

            logger.info(
                "Recent sessions retrieved",
                extra={
                    "user_id": str(user_id),
                    "days": days,
                    "count": len(sessions),
                }
            )

            return Result(value=sessions)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to get recent sessions",
                extra={"user_id": str(user_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[RECENT_FAILED]")

    async def get_score_trends(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        days: int = 30
    ) -> Result[dict]:
        """
        Get score trends for a user over time

        Returns: Dict with date -> scores or Result.fail
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            query = (
                select(PracticeSession)
                .where(PracticeSession.user_id == user_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
                .order_by(PracticeSession.start_time)
            )

            result = await db.execute(query)
            sessions = result.scalars().all()

            # Build trend data
            trends = []
            for session in sessions:
                overall_score = (
                    (session.logic_score or 0) * 0.4 +
                    (session.accuracy_score or 0) * 0.3 +
                    (session.completeness_score or 0) * 0.3
                )

                trends.append({
                    "date": session.start_time.isoformat(),
                    "logic_score": session.logic_score or 0,
                    "accuracy_score": session.accuracy_score or 0,
                    "completeness_score": session.completeness_score or 0,
                    "overall_score": round(overall_score, 2),
                    "scenario_type": session.scenario.scenario_type if session.scenario else "unknown",
                })

            logger.info(
                "Score trends retrieved",
                extra={
                    "user_id": str(user_id),
                    "days": days,
                    "data_points": len(trends),
                }
            )

            return Result(value=trends)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to get score trends",
                extra={"user_id": str(user_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[TRENDS_FAILED]")

    async def get_statistics(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> Result[dict]:
        """
        Get overall statistics for a user

        Returns: Dict with stats or Result.fail
        """
        try:
            # Get all completed sessions
            query = (
                select(PracticeSession)
                .where(PracticeSession.user_id == user_id)
                .where(PracticeSession.status == "completed")
            )

            result = await db.execute(query)
            sessions = result.scalars().all()

            if not sessions:
                return Result(value={
                    "total_sessions": 0,
                    "average_score": 0,
                    "best_score": 0,
                    "total_practice_time_seconds": 0,
                })

            # Calculate statistics
            total_sessions = len(sessions)
            total_practice_time = sum(
                (s.end_time - s.start_time).total_seconds()
                for s in sessions
                if s.end_time
            )

            scores = []
            for session in sessions:
                overall_score = (
                    (session.logic_score or 0) * 0.4 +
                    (session.accuracy_score or 0) * 0.3 +
                    (session.completeness_score or 0) * 0.3
                )
                scores.append(overall_score)

            average_score = sum(scores) / len(scores) if scores else 0
            best_score = max(scores) if scores else 0

            stats = {
                "total_sessions": total_sessions,
                "average_score": round(average_score, 2),
                "best_score": round(best_score, 2),
                "total_practice_time_seconds": int(total_practice_time),
                "total_practice_time_minutes": round(total_practice_time / 60, 1),
            }

            logger.info(
                "User statistics retrieved",
                extra={
                    "user_id": str(user_id),
                    "total_sessions": total_sessions,
                }
            )

            return Result(value=stats)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to get user statistics",
                extra={"user_id": str(user_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[STATS_FAILED]")


    async def get_user_history_with_report_summary(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        scenario_type: str | None = None,
    ) -> Result[dict[str, Any]]:
        """
        Get practice history with report summary for a user (Story 3.2).

        Args:
            db: Database session
            user_id: User ID
            page: Page number (1-based)
            page_size: Items per page
            scenario_type: Filter by scenario type (optional)

        Returns:
            Result with sessions list, total count, and pagination info
        """
        try:
            # Build base query with joins
            query = (
                select(
                    PracticeSession,
                    ComprehensiveReport.overall_score,
                )
                .options(
                    selectinload(PracticeSession.scenario),
                    selectinload(PracticeSession.agent),
                    selectinload(PracticeSession.persona),
                )
                .outerjoin(
                    ComprehensiveReport,
                    ComprehensiveReport.session_id == PracticeSession.session_id
                )
                .where(PracticeSession.user_id == user_id)
            )

            # Filter by scenario type if specified
            if scenario_type:
                query = query.where(PracticeSession.scenario.has(scenario_type=scenario_type))

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_query)).scalar() or 0

            # Apply sorting and pagination
            query = (
                query.order_by(desc(PracticeSession.start_time))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )

            result = await db.execute(query)
            rows = result.all()

            # Build response items
            sessions = []
            for row in rows:
                session = row[0]
                overall_score = row[1]

                # Calculate duration
                duration_seconds = 0
                if session.end_time and session.start_time:
                    duration_seconds = int(
                        (session.end_time - session.start_time).total_seconds()
                    )
                elif session.total_duration_seconds:
                    duration_seconds = session.total_duration_seconds

                sessions.append(SessionWithReportSummary(
                    session_id=session.session_id,
                    scenario_name=session.scenario.name if session.scenario else "未知场景",
                    scenario_type=session.scenario.scenario_type if session.scenario else "unknown",
                    persona_name=session.persona.name if session.persona else None,
                    agent_name=session.agent.name if session.agent else None,
                    start_time=session.start_time,
                    duration_seconds=duration_seconds,
                    overall_score=overall_score,
                    report_status=session.report_status or "pending",
                    report_generated_at=session.report_generated_at,
                    status=session.status,
                ))

            logger.info(
                "User history with report summary retrieved",
                extra={
                    "user_id": str(user_id),
                    "count": len(sessions),
                    "total": total,
                    "page": page,
                }
            )

            return Result(value={
                "sessions": sessions,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            })

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to get user history with report summary",
                extra={"user_id": str(user_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[HISTORY_FAILED]")


# Singleton instance
history_service = HistoryService()
