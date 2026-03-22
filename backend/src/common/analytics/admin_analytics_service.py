"""
Admin Analytics Service - System-wide analytics for administrators

Implements aggregated statistics across all users for admin dashboard.

References:
- Requirements: Admin Analytics Page
- Constitution Principles:
  - I. NO ERROR POPUPS - Graceful degradation with Result type
  - II. Real-time priority - Efficient database queries
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from common.error_handling.result import Result
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass
class OverviewStats:
    """System overview statistics"""
    total_users: int
    active_users_today: int
    active_users_week: int
    total_sessions: int
    sessions_today: int
    completed_sessions: int
    completion_rate: float
    average_score: float
    average_duration_minutes: float
    growth: dict[str, float]  # users_rate, sessions_rate, score_rate


@dataclass
class TrendDataPoint:
    """Single point in trend data"""
    date: str
    sessions_count: int
    average_score: float
    active_users: int


@dataclass
class ScoreDistribution:
    """Score distribution buckets"""
    excellent: int  # 90-100
    good: int       # 70-89
    fair: int       # 50-69
    poor: int       # 0-49


@dataclass
class AgentStats:
    """Agent usage statistics"""
    agent_id: str
    agent_name: str
    category: str
    usage_count: int
    average_score: float
    completion_rate: float


@dataclass
class PersonaStats:
    """Persona usage statistics"""
    persona_id: str
    persona_name: str
    difficulty: str
    usage_count: int
    average_score: float


@dataclass
class LeaderboardEntry:
    """User leaderboard entry"""
    rank: int
    user_id: str
    user_name: str
    department: str | None
    total_sessions: int
    average_score: float
    best_score: float
    total_duration_minutes: float


def _calculate_overall_score(logic: float | None, accuracy: float | None, completeness: float | None) -> float:
    """Calculate weighted overall score"""
    if logic is None or accuracy is None or completeness is None:
        return 0.0
    return logic * 0.4 + accuracy * 0.3 + completeness * 0.3


def _get_time_range_start(time_range: str) -> datetime:
    """Convert time range string to start datetime"""
    now = datetime.now()
    if time_range == "7d":
        return now - timedelta(days=7)
    elif time_range == "30d":
        return now - timedelta(days=30)
    elif time_range == "90d":
        return now - timedelta(days=90)
    else:  # all_time
        return datetime(2000, 1, 1)


class AdminAnalyticsService:
    """
    System-wide analytics service for administrators
    
    Provides aggregated statistics, trends, and rankings
    across all users and sessions.
    """

    async def get_overview_stats(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        scenario_type: str | None = None
    ) -> Result[OverviewStats]:
        """
        Get system overview statistics
        
        Args:
            db: Database session
            time_range: Time range filter (7d, 30d, 90d, all_time)
            scenario_type: Optional filter by scenario type
            
        Returns:
            Result containing OverviewStats or error
        """
        try:
            start_date = _get_time_range_start(time_range)
            previous_start = start_date - (datetime.now() - start_date)
            today = datetime.now().date()
            week_ago = datetime.now() - timedelta(days=7)

            # Total users
            total_users = await db.scalar(
                select(func.count(User.user_id)).where(User.is_active == True)
            ) or 0

            # Build session base query
            session_query = select(PracticeSession).where(
                PracticeSession.start_time >= start_date
            )
            if scenario_type:
                session_query = session_query.join(
                    Scenario, PracticeSession.scenario_id == Scenario.scenario_id
                ).where(Scenario.scenario_type == scenario_type)

            # Active users today
            active_today = await db.scalar(
                select(func.count(distinct(PracticeSession.user_id))).where(
                    func.date(PracticeSession.start_time) == today
                )
            ) or 0

            # Active users this week
            active_week = await db.scalar(
                select(func.count(distinct(PracticeSession.user_id))).where(
                    PracticeSession.start_time >= week_ago
                )
            ) or 0

            # Session statistics for current period
            current_stats_query = select(
                func.count(PracticeSession.session_id).label("total"),
                func.sum(case((PracticeSession.status == "completed", 1), else_=0)).label("completed"),
                func.avg(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).label("avg_score"),
                func.avg(PracticeSession.total_duration_seconds).label("avg_duration")
            ).where(PracticeSession.start_time >= start_date)

            if scenario_type:
                current_stats_query = current_stats_query.join(
                    Scenario, PracticeSession.scenario_id == Scenario.scenario_id
                ).where(Scenario.scenario_type == scenario_type)

            result = await db.execute(current_stats_query)
            row = result.one()

            total_sessions = row.total or 0
            completed_sessions = row.completed or 0
            avg_score = round(row.avg_score or 0, 1)
            avg_duration = round((row.avg_duration or 0) / 60, 1)  # Convert to minutes

            # Sessions today
            sessions_today = await db.scalar(
                select(func.count(PracticeSession.session_id)).where(
                    func.date(PracticeSession.start_time) == today
                )
            ) or 0

            # Calculate completion rate
            completion_rate = round(
                (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0, 1
            )

            # Previous period statistics for growth calculation
            previous_stats_query = select(
                func.count(PracticeSession.session_id).label("total"),
                func.avg(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).label("avg_score")
            ).where(
                PracticeSession.start_time >= previous_start,
                PracticeSession.start_time < start_date
            )

            if scenario_type:
                previous_stats_query = previous_stats_query.join(
                    Scenario, PracticeSession.scenario_id == Scenario.scenario_id
                ).where(Scenario.scenario_type == scenario_type)

            prev_result = await db.execute(previous_stats_query)
            prev_row = prev_result.one()

            prev_sessions = prev_row.total or 0
            prev_score = prev_row.avg_score or 0

            # Calculate growth rates
            sessions_growth = round(
                ((total_sessions - prev_sessions) / prev_sessions * 100) if prev_sessions > 0 else 0, 1
            )
            score_growth = round(
                ((avg_score - prev_score) / prev_score * 100) if prev_score > 0 else 0, 1
            )

            # User growth (compare with previous period)
            prev_users = await db.scalar(
                select(func.count(User.user_id)).where(
                    User.created_at < start_date,
                    User.is_active == True
                )
            ) or 0
            users_growth = round(
                ((total_users - prev_users) / prev_users * 100) if prev_users > 0 else 0, 1
            )

            stats = OverviewStats(
                total_users=total_users,
                active_users_today=active_today,
                active_users_week=active_week,
                total_sessions=total_sessions,
                sessions_today=sessions_today,
                completed_sessions=completed_sessions,
                completion_rate=completion_rate,
                average_score=avg_score,
                average_duration_minutes=avg_duration,
                growth={
                    "users_rate": users_growth,
                    "sessions_rate": sessions_growth,
                    "score_rate": score_growth
                }
            )

            logger.info(
                "Overview stats calculated",
                extra={
                    "time_range": time_range,
                    "scenario_type": scenario_type,
                    "total_sessions": total_sessions
                }
            )

            return Result(value=stats)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate overview stats",
                extra={"error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[OVERVIEW_STATS_FAILED]")

    async def get_trends_data(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        granularity: str = "day"
    ) -> Result[dict]:
        """
        Get trend data for charts
        
        Args:
            db: Database session
            time_range: Time range filter
            granularity: Data granularity (day, week, month)
            
        Returns:
            Result containing trend data and score distribution
        """
        try:
            start_date = _get_time_range_start(time_range)

            # Trend data query - group by date
            trend_query = select(
                func.date(PracticeSession.start_time).label("date"),
                func.count(PracticeSession.session_id).label("sessions_count"),
                func.avg(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).label("average_score"),
                func.count(distinct(PracticeSession.user_id)).label("active_users")
            ).where(
                PracticeSession.start_time >= start_date,
                PracticeSession.status == "completed"
            ).group_by(
                func.date(PracticeSession.start_time)
            ).order_by(
                func.date(PracticeSession.start_time)
            )

            result = await db.execute(trend_query)
            rows = result.all()

            trend_data = [
                {
                    "date": str(row.date),
                    "sessions_count": row.sessions_count,
                    "average_score": round(row.average_score or 0, 1),
                    "active_users": row.active_users
                }
                for row in rows
            ]

            # Score distribution query
            score_query = select(
                PracticeSession.session_id,
                (PracticeSession.logic_score * 0.4 +
                 PracticeSession.accuracy_score * 0.3 +
                 PracticeSession.completeness_score * 0.3).label("overall_score")
            ).where(
                PracticeSession.start_time >= start_date,
                PracticeSession.status == "completed",
                PracticeSession.logic_score.isnot(None)
            )

            score_result = await db.execute(score_query)
            scores = score_result.all()

            excellent = sum(1 for _, score in scores if score is not None and score >= 90)
            good = sum(1 for _, score in scores if score is not None and 70 <= score < 90)
            fair = sum(1 for _, score in scores if score is not None and 50 <= score < 70)
            poor = sum(1 for _, score in scores if score is not None and score < 50)

            logger.info(
                "Trends data calculated",
                extra={
                    "time_range": time_range,
                    "data_points": len(trend_data)
                }
            )

            return Result(value={
                "trend_data": trend_data,
                "score_distribution": {
                    "excellent": excellent,
                    "good": good,
                    "fair": fair,
                    "poor": poor
                }
            })

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate trends data",
                extra={"error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[TRENDS_DATA_FAILED]")

    async def get_agent_stats(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        limit: int = 10
    ) -> Result[dict]:
        """
        Get Agent and Persona usage statistics
        
        Args:
            db: Database session
            time_range: Time range filter
            limit: Max number of items to return
            
        Returns:
            Result containing agent stats, persona stats, and scenario distribution
        """
        try:
            from agent.models import Agent, Persona
            
            start_date = _get_time_range_start(time_range)

            # Agent statistics
            agent_query = select(
                Agent.id,
                Agent.name,
                Agent.category,
                func.count(PracticeSession.session_id).label("usage_count"),
                func.avg(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).label("average_score"),
                func.sum(case((PracticeSession.status == "completed", 1), else_=0)).label("completed"),
                func.count(PracticeSession.session_id).label("total")
            ).join(
                PracticeSession, Agent.id == PracticeSession.agent_id
            ).where(
                PracticeSession.start_time >= start_date
            ).group_by(
                Agent.id, Agent.name, Agent.category
            ).order_by(
                func.count(PracticeSession.session_id).desc()
            ).limit(limit)

            agent_result = await db.execute(agent_query)
            agent_rows = agent_result.all()

            agent_stats = [
                {
                    "agent_id": str(row.id),
                    "agent_name": row.name,
                    "category": row.category,
                    "usage_count": row.usage_count,
                    "average_score": round(row.average_score or 0, 1),
                    "completion_rate": round(
                        (row.completed / row.total * 100) if row.total > 0 else 0, 1
                    )
                }
                for row in agent_rows
            ]

            # Persona statistics
            persona_query = select(
                Persona.id,
                Persona.name,
                Persona.difficulty,
                func.count(PracticeSession.session_id).label("usage_count"),
                func.avg(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).label("average_score")
            ).join(
                PracticeSession, Persona.id == PracticeSession.persona_id
            ).where(
                PracticeSession.start_time >= start_date
            ).group_by(
                Persona.id, Persona.name, Persona.difficulty
            ).order_by(
                func.count(PracticeSession.session_id).desc()
            ).limit(limit)

            persona_result = await db.execute(persona_query)
            persona_rows = persona_result.all()

            persona_stats = [
                {
                    "persona_id": str(row.id),
                    "persona_name": row.name,
                    "difficulty": row.difficulty,
                    "usage_count": row.usage_count,
                    "average_score": round(row.average_score or 0, 1)
                }
                for row in persona_rows
            ]

            # Scenario distribution
            scenario_query = select(
                Scenario.scenario_type,
                func.count(PracticeSession.session_id).label("count")
            ).join(
                PracticeSession, Scenario.scenario_id == PracticeSession.scenario_id
            ).where(
                PracticeSession.start_time >= start_date
            ).group_by(
                Scenario.scenario_type
            )

            scenario_result = await db.execute(scenario_query)
            scenario_rows = scenario_result.all()

            scenario_distribution = {
                row.scenario_type: row.count for row in scenario_rows
            }

            logger.info(
                "Agent stats calculated",
                extra={
                    "time_range": time_range,
                    "agents": len(agent_stats),
                    "personas": len(persona_stats)
                }
            )

            return Result(value={
                "agent_stats": agent_stats,
                "persona_stats": persona_stats,
                "scenario_distribution": scenario_distribution
            })

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate agent stats",
                extra={"error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[AGENT_STATS_FAILED]")

    async def get_leaderboard(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        limit: int = 50
    ) -> Result[list[dict]]:
        """
        Get user leaderboard
        
        Args:
            db: Database session
            time_range: Time range filter
            limit: Max number of users to return
            
        Returns:
            Result containing list of leaderboard entries
        """
        try:
            start_date = _get_time_range_start(time_range)

            # Leaderboard query
            leaderboard_query = select(
                User.user_id,
                User.name,
                User.department,
                func.count(PracticeSession.session_id).label("total_sessions"),
                func.avg(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).label("average_score"),
                func.max(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).label("best_score"),
                func.sum(PracticeSession.total_duration_seconds).label("total_duration")
            ).join(
                PracticeSession, User.user_id == PracticeSession.user_id
            ).where(
                PracticeSession.start_time >= start_date,
                PracticeSession.status == "completed"
            ).group_by(
                User.user_id, User.name, User.department
            ).order_by(
                func.avg(
                    PracticeSession.logic_score * 0.4 +
                    PracticeSession.accuracy_score * 0.3 +
                    PracticeSession.completeness_score * 0.3
                ).desc()
            ).limit(limit)

            result = await db.execute(leaderboard_query)
            rows = result.all()

            leaderboard = []
            for rank, row in enumerate(rows, 1):
                leaderboard.append({
                    "rank": rank,
                    "user_id": str(row.user_id),
                    "user_name": row.name or "Unknown",
                    "department": row.department,
                    "total_sessions": row.total_sessions,
                    "average_score": round(row.average_score or 0, 1),
                    "best_score": round(row.best_score or 0, 1),
                    "total_duration_minutes": round((row.total_duration or 0) / 60, 1)
                })

            logger.info(
                "Leaderboard calculated",
                extra={
                    "time_range": time_range,
                    "users": len(leaderboard)
                }
            )

            return Result(value=leaderboard)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate leaderboard",
                extra={"error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[LEADERBOARD_FAILED]")


# Singleton instance
admin_analytics_service = AdminAnalyticsService()
