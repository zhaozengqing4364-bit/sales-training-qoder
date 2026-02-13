"""
Analytics Aggregation Service - Aggregates analytics data for dashboard

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation
- V. Cost control - Efficient aggregation queries
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, RequiredTalkingPoint, Scenario
from common.error_handling.result import Result
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsStats:
    """Aggregated analytics statistics"""
    # Completion metrics
    total_sessions: int
    completed_sessions: int
    completion_rate: float

    # Score metrics
    average_logic_score: float
    average_accuracy_score: float
    average_completeness_score: float
    average_overall_score: float

    # Engagement metrics
    average_duration_seconds: float
    average_interruptions_per_session: float

    # Quality metrics
    sessions_with_high_vagueness: int
    sessions_with_forbidden_words: int


@dataclass
class ScoreDistribution:
    """Score distribution data"""
    excellent: int  # 90-100
    good: int  # 70-89
    fair: int  # 50-69
    poor: int  # 0-49


@dataclass
class CommonGaps:
    """Common talking point gaps"""
    point_text: str
    miss_count: int
    miss_rate: float


class AnalyticsService:
    """
    Aggregates analytics data for admin dashboard

    Key responsibilities:
    - Calculate completion rates
    - Aggregate score distributions
    - Identify common gaps in talking points
    - Generate trend data
    """

    async def get_dashboard_stats(
        self,
        db: AsyncSession,
        scenario_type: str | None = None,
        days: int = 30
    ) -> Result[AnalyticsStats]:
        """
        Get aggregated dashboard statistics

        Returns: AnalyticsStats or Result.fail
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            # Build base query
            query = (
                select(
                    func.count(PracticeSession.session_id).label("total_sessions"),
                    func.sum(
                        case((PracticeSession.status == "completed", 1), else_=0)
                    ).label("completed_sessions"),
                    func.avg(PracticeSession.logic_score).label("avg_logic"),
                    func.avg(PracticeSession.accuracy_score).label("avg_accuracy"),
                    func.avg(PracticeSession.completeness_score).label("avg_completeness"),
                    func.avg(
                        PracticeSession.logic_score * 0.4 +
                         PracticeSession.accuracy_score * 0.3 +
                         PracticeSession.completeness_score * 0.3
                    ).label("avg_overall")
                )
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
            )

            if scenario_type:
                query = query.where(Scenario.scenario_type == scenario_type)

            result = await db.execute(query)
            row = result.one()

            total_sessions = row.total_sessions or 0
            completed_sessions = row.completed_sessions or 0

            stats = AnalyticsStats(
                total_sessions=total_sessions,
                completed_sessions=completed_sessions,
                completion_rate=round(completed_sessions / total_sessions * 100, 1) if total_sessions > 0 else 0,
                average_logic_score=round(row.avg_logic or 0, 2),
                average_accuracy_score=round(row.avg_accuracy or 0, 2),
                average_completeness_score=round(row.avg_completeness or 0, 2),
                average_overall_score=round(row.avg_overall or 0, 2),
                average_duration_seconds=0.0,  # Would need end_time
                average_interruptions_per_session=0.0,  # Would need interruption count
                sessions_with_high_vagueness=0,  # Would need vagueness tracking
                sessions_with_forbidden_words=0,  # Would need forbidden word tracking
            )

            logger.info(
                "Dashboard stats calculated",
                extra={
                    "scenario_type": scenario_type,
                    "days": days,
                    "total_sessions": total_sessions,
                }
            )

            return Result(value=stats)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate dashboard stats",
                extra={"scenario_type": scenario_type, "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[ANALYTICS_FAILED]")

    async def get_score_distribution(
        self,
        db: AsyncSession,
        scenario_type: str | None = None,
        days: int = 30
    ) -> Result[ScoreDistribution]:
        """
        Get distribution of scores

        Returns: ScoreDistribution or Result.fail
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            # Calculate overall scores for each session
            query = (
                select(
                    PracticeSession.session_id,
                    (PracticeSession.logic_score * 0.4 +
                     PracticeSession.accuracy_score * 0.3 +
                     PracticeSession.completeness_score * 0.3).label("overall_score")
                )
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
            )

            if scenario_type:
                query = query.where(Scenario.scenario_type == scenario_type)

            result = await db.execute(query)
            rows = result.all()

            # Count scores in each bucket
            excellent = sum(1 for _, score in rows if score >= 90)
            good = sum(1 for _, score in rows if 70 <= score < 90)
            fair = sum(1 for _, score in rows if 50 <= score < 70)
            poor = sum(1 for _, score in rows if score < 50)

            distribution = ScoreDistribution(
                excellent=excellent,
                good=good,
                fair=fair,
                poor=poor
            )

            logger.info(
                "Score distribution calculated",
                extra={
                    "scenario_type": scenario_type,
                    "total": len(rows),
                }
            )

            return Result(value=distribution)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate score distribution",
                extra={"scenario_type": scenario_type, "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[DISTRIBUTION_FAILED]")

    async def get_common_gaps(
        self,
        db: AsyncSession,
        scenario_type: str | None = None,
        days: int = 30,
        limit: int = 10
    ) -> Result[list[CommonGaps]]:
        """
        Get most commonly missed talking points

        Returns: List of CommonGaps or Result.fail
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            # Get required talking points
            query = (
                select(RequiredTalkingPoint)
                .join(PracticeSession, RequiredTalkingPoint.presentation_id == PracticeSession.presentation_id)
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
            )

            if scenario_type:
                query = query.where(Scenario.scenario_type == scenario_type)

            result = await db.execute(query)
            points = result.scalars().all()

            # For each point, count how many times it was missed
            # This is a simplified version - in production would track actual coverage
            gaps = []
            for point in points:
                # Simulated miss count (in production, would track actual coverage)
                miss_count = 1  # Placeholder
                miss_rate = 0.5  # Placeholder

                gaps.append(CommonGaps(
                    point_text=point.point_text,
                    miss_count=miss_count,
                    miss_rate=miss_rate
                ))

            # Sort by miss count
            gaps.sort(key=lambda g: g.miss_count, reverse=True)
            gaps = gaps[:limit]

            logger.info(
                "Common gaps calculated",
                extra={
                    "scenario_type": scenario_type,
                    "gaps": len(gaps),
                }
            )

            return Result(value=gaps)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate common gaps",
                extra={"scenario_type": scenario_type, "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[GAPS_FAILED]")

    async def get_trend_data(
        self,
        db: AsyncSession,
        scenario_type: str | None = None,
        days: int = 30
    ) -> Result[dict]:
        """
        Get trend data for charts (daily aggregates)

        Returns: Dict with date -> avg_score mapping or Result.fail
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            # Group by date and calculate average score
            query = (
                select(
                    func.date(PracticeSession.start_time).label("date"),
                    func.avg(
                        PracticeSession.logic_score * 0.4 +
                         PracticeSession.accuracy_score * 0.3 +
                         PracticeSession.completeness_score * 0.3
                    ).label("avg_score"),
                    func.count(PracticeSession.session_id).label("session_count")
                )
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
                .group_by(func.date(PracticeSession.start_time))
                .order_by(func.date(PracticeSession.start_time))
            )

            if scenario_type:
                query = query.where(Scenario.scenario_type == scenario_type)

            result = await db.execute(query)
            rows = result.all()

            # Convert to dict
            trend_data = {
                str(row.date): {
                    "avg_score": round(row.avg_score or 0, 2),
                    "session_count": row.session_count
                }
                for row in rows
            }

            logger.info(
                "Trend data calculated",
                extra={
                    "scenario_type": scenario_type,
                    "days": len(trend_data),
                }
            )

            return Result(value=trend_data)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate trend data",
                extra={"scenario_type": scenario_type, "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[TREND_FAILED]")


# Singleton instance
analytics_service = AnalyticsService()
