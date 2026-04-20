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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, RequiredTalkingPoint, Scenario
from common.error_handling.result import Result

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
    pass_rate_3min_flow: float
    pass_rate_5turn_defense: float
    pass_rate_4step_structure: float
    next_day_retry_rate: float


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

            # Compute effectiveness metrics from persisted session snapshot.
            effective_sessions_query = (
                select(
                    PracticeSession.session_id,
                    PracticeSession.user_id,
                    PracticeSession.start_time,
                    PracticeSession.effectiveness_snapshot,
                )
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
            )
            if scenario_type:
                effective_sessions_query = effective_sessions_query.where(
                    Scenario.scenario_type == scenario_type
                )

            effective_rows = (await db.execute(effective_sessions_query)).all()

            evaluable_rows: list[tuple] = []
            pass_3_count = 0
            pass_5_count = 0
            pass_4_count = 0

            for row_item in effective_rows:
                snapshot = row_item.effectiveness_snapshot
                if not isinstance(snapshot, dict):
                    continue
                if not bool(snapshot.get("evaluable", False)):
                    continue
                pass_flags = snapshot.get("pass_flags")
                if not isinstance(pass_flags, dict):
                    continue

                evaluable_rows.append(row_item)
                if bool(pass_flags.get("pass_3min_flow", False)):
                    pass_3_count += 1
                if bool(pass_flags.get("pass_5turn_defense", False)):
                    pass_5_count += 1
                if bool(pass_flags.get("pass_4step_structure", False)):
                    pass_4_count += 1

            evaluable_total = len(evaluable_rows)

            # next_day_retry_rate: another completed session by same user between 24h and 48h.
            next_day_retry_hits = 0
            if evaluable_rows:
                user_ids = list({str(item.user_id) for item in evaluable_rows})
                followup_query = (
                    select(
                        PracticeSession.user_id,
                        PracticeSession.start_time,
                    )
                    .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                    .where(PracticeSession.user_id.in_(user_ids))
                    .where(PracticeSession.status == "completed")
                    .where(PracticeSession.start_time >= cutoff_time)
                )
                if scenario_type:
                    followup_query = followup_query.where(
                        Scenario.scenario_type == scenario_type
                    )
                followup_rows = (await db.execute(followup_query)).all()
                sessions_by_user: dict[str, list[datetime]] = {}
                for followup in followup_rows:
                    sessions_by_user.setdefault(str(followup.user_id), []).append(
                        followup.start_time
                    )
                for session_times in sessions_by_user.values():
                    session_times.sort()

                for base in evaluable_rows:
                    base_time = base.start_time
                    if base_time is None:
                        continue
                    candidates = sessions_by_user.get(str(base.user_id), [])
                    for candidate_time in candidates:
                        delta_seconds = (candidate_time - base_time).total_seconds()
                        if 24 * 3600 <= delta_seconds <= 48 * 3600:
                            next_day_retry_hits += 1
                            break

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
                sessions_with_high_vagueness=0,
                sessions_with_forbidden_words=0,
                pass_rate_3min_flow=round((pass_3_count / evaluable_total) * 100, 2) if evaluable_total > 0 else 0.0,
                pass_rate_5turn_defense=round((pass_5_count / evaluable_total) * 100, 2) if evaluable_total > 0 else 0.0,
                pass_rate_4step_structure=round((pass_4_count / evaluable_total) * 100, 2) if evaluable_total > 0 else 0.0,
                next_day_retry_rate=round((next_day_retry_hits / evaluable_total) * 100, 2) if evaluable_total > 0 else 0.0,
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
