"""
Leaderboard Calculation Service - Calculates rankings for practice sessions

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation
- V. Cost control - Efficient queries
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.history_service import PROJECTION_SCORE_BASIS
from common.db.models import LeaderboardEntry, PracticeSession, Scenario, User
from common.error_handling.result import Result

logger = logging.getLogger(__name__)


@dataclass
class LeaderboardView:
    """Represents a leaderboard entry view (non-model)"""

    user_id: uuid.UUID
    username: str
    total_sessions: int
    average_score: float
    best_score: float
    rank: int
    score_basis: str = PROJECTION_SCORE_BASIS


@dataclass
class LeaderboardStats:
    """Aggregated leaderboard statistics"""

    entries: list[LeaderboardView]
    total_users: int
    time_period: str  # daily, weekly, monthly, all_time
    score_basis: str = PROJECTION_SCORE_BASIS
    evaluable_sessions: int = 0
    not_evaluable_sessions: int = 0


class LeaderboardService:
    """
    Calculates and manages leaderboards

    Key responsibilities:
    - Calculate rankings based on practice scores
    - Support different time periods (daily, weekly, monthly, all-time)
    - Handle ties appropriately
    - Update leaderboard entries in database
    """

    def __init__(self):
        self.time_periods = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
            "all_time": timedelta(days=365 * 100),  # Effectively forever
        }
        self.time_period_aliases = {
            "day": "daily",
            "daily": "daily",
            "week": "weekly",
            "weekly": "weekly",
            "month": "monthly",
            "monthly": "monthly",
            "all": "all_time",
            "all_time": "all_time",
        }
        self.scenario_aliases = {
            "sales": "sales",
            "sales_bot": "sales",
            "presentation": "presentation",
        }

    def _normalize_time_period(self, time_period: str | None) -> str:
        """Normalize time-period aliases to canonical values."""
        if not time_period:
            return "all_time"
        return self.time_period_aliases.get(time_period, "all_time")

    def _normalize_scenario_type(self, scenario_type: str | None) -> str | None:
        """Normalize scenario aliases to canonical values."""
        if not scenario_type:
            return None
        return self.scenario_aliases.get(scenario_type, scenario_type)

    @staticmethod
    def _evaluable_filter():
        return PracticeSession.effectiveness_snapshot["evaluable"].as_boolean().is_(True)

    @staticmethod
    def _not_evaluable_filter():
        return PracticeSession.effectiveness_snapshot["evaluable"].as_boolean().is_(False)

    @staticmethod
    def _score_expr():
        return (
            PracticeSession.logic_score
            + PracticeSession.accuracy_score
            + PracticeSession.completeness_score
        ) / 3.0

    async def calculate_leaderboard(
        self,
        db: AsyncSession,
        scenario_type: str | None = None,
        time_period: str = "all_time",
        limit: int = 100,
    ) -> Result[LeaderboardStats]:
        """
        Calculate leaderboard for a scenario type and time period

        Returns: LeaderboardStats or Result.fail
        """
        try:
            normalized_time_period = self._normalize_time_period(time_period)
            normalized_scenario_type = self._normalize_scenario_type(scenario_type)

            # Get time filter
            time_delta = self.time_periods.get(
                normalized_time_period, self.time_periods["all_time"]
            )
            cutoff_time = datetime.now() - time_delta

            score_expr = self._score_expr()

            # Build query. Leaderboard scores are evaluable-only: completed
            # sessions must carry an evidence snapshot explicitly marked
            # evaluable, and score fields must be present. Evidence-deficient
            # sessions remain in history but are not coalesced to 0 here.
            query = (
                select(
                    User.user_id,
                    User.name.label("username"),
                    func.count(PracticeSession.session_id).label("total_sessions"),
                    func.avg(score_expr).label("average_score"),
                    func.max(score_expr).label("best_score"),
                )
                .join(PracticeSession, User.user_id == PracticeSession.user_id)
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
                .where(self._evaluable_filter())
                .where(
                    (PracticeSession.logic_score.isnot(None))
                    & (PracticeSession.accuracy_score.isnot(None))
                    & (PracticeSession.completeness_score.isnot(None))
                )
                .group_by(User.user_id, User.name)
                .order_by(desc("average_score"))
                .limit(limit)
            )

            # Filter by scenario type if specified
            if normalized_scenario_type:
                query = query.where(Scenario.scenario_type == normalized_scenario_type)

            result = await db.execute(query)
            rows = result.all()

            # Convert to leaderboard entries
            entries = []
            for rank, row in enumerate(rows, start=1):
                entry = LeaderboardView(
                    user_id=row.user_id,
                    username=row.username or "Anonymous",
                    total_sessions=row.total_sessions,
                    average_score=round(row.average_score or 0, 2),
                    best_score=round(row.best_score or 0, 2),
                    rank=rank,
                )
                entries.append(entry)

            # Get total users count
            count_query = (
                select(func.count(func.distinct(User.user_id)))
                .join(PracticeSession, User.user_id == PracticeSession.user_id)
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
                .where(self._evaluable_filter())
                .where(
                    (PracticeSession.logic_score.isnot(None))
                    & (PracticeSession.accuracy_score.isnot(None))
                    & (PracticeSession.completeness_score.isnot(None))
                )
            )

            if normalized_scenario_type:
                count_query = count_query.where(
                    Scenario.scenario_type == normalized_scenario_type
                )

            count_result = await db.execute(count_query)
            total_users = count_result.scalar() or 0

            evaluable_sessions_query = (
                select(func.count(PracticeSession.session_id))
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
                .where(self._evaluable_filter())
                .where(
                    (PracticeSession.logic_score.isnot(None))
                    & (PracticeSession.accuracy_score.isnot(None))
                    & (PracticeSession.completeness_score.isnot(None))
                )
            )
            if normalized_scenario_type:
                evaluable_sessions_query = evaluable_sessions_query.where(
                    Scenario.scenario_type == normalized_scenario_type
                )
            evaluable_sessions_result = await db.execute(evaluable_sessions_query)
            evaluable_sessions = int(evaluable_sessions_result.scalar() or 0)
            not_evaluable_query = (
                select(func.count(PracticeSession.session_id))
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
                .where(self._not_evaluable_filter())
            )
            if normalized_scenario_type:
                not_evaluable_query = not_evaluable_query.where(
                    Scenario.scenario_type == normalized_scenario_type
                )
            not_evaluable_result = await db.execute(not_evaluable_query)
            not_evaluable_sessions = int(not_evaluable_result.scalar() or 0)

            stats = LeaderboardStats(
                entries=entries,
                total_users=total_users,
                time_period=normalized_time_period,
                evaluable_sessions=int(evaluable_sessions),
                not_evaluable_sessions=not_evaluable_sessions,
            )

            logger.info(
                "Leaderboard calculated",
                extra={
                    "scenario_type": scenario_type,
                    "normalized_scenario_type": normalized_scenario_type,
                    "time_period": normalized_time_period,
                    "entries": len(entries),
                },
            )

            return Result(value=stats)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to calculate leaderboard",
                extra={
                    "scenario_type": scenario_type,
                    "time_period": time_period,
                    "error": str(e),
                },
                exc_info=True,
            )
            return Result.fail(fallback="[LEADERBOARD_FAILED]")

    async def update_leaderboard_entries(self, db: AsyncSession) -> Result[bool]:
        """
        Update leaderboard entries in database

        Called periodically to refresh leaderboard tables

        Returns: True or Result.fail
        """
        try:
            # Clear existing entries
            await db.execute(LeaderboardEntry.__table__.delete())

            # Calculate all-time leaderboard for each scenario type
            for scenario_type in ["presentation", "sales"]:
                result = await self.calculate_leaderboard(
                    db=db,
                    scenario_type=scenario_type,
                    time_period="all_time",
                    limit=1000,
                )

                if result.is_success:
                    stats = result.value

                    # Insert entries into database
                    for entry in stats.entries:
                        leaderboard_entry = LeaderboardEntry(
                            entry_id=str(uuid.uuid4()),
                            user_id=str(entry.user_id),
                            scenario_type=scenario_type,
                            rank=entry.rank,
                            average_score=entry.average_score,
                            total_sessions=entry.total_sessions,
                            last_updated=datetime.now(),
                        )
                        db.add(leaderboard_entry)

            await db.commit()

            logger.info("Leaderboard entries updated")

            return Result(value=True)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to update leaderboard entries",
                extra={"error": str(e)},
                exc_info=True,
            )
            await db.rollback()
            return Result.fail(fallback="[UPDATE_FAILED]")

    async def get_user_rank(
        self,
        db: AsyncSession,
        user_id: str | uuid.UUID,
        scenario_type: str | None = None,
        time_period: str = "all_time",
    ) -> Result[dict]:
        """
        Get a user's rank and stats

        Returns: User rank info or Result.fail
        """
        try:
            normalized_time_period = self._normalize_time_period(time_period)
            normalized_scenario_type = self._normalize_scenario_type(scenario_type)
            normalized_user_id = str(user_id)
            cutoff_time = datetime.now() - self.time_periods.get(
                normalized_time_period, self.time_periods["all_time"]
            )

            score_expr = self._score_expr()

            aggregated_query = (
                select(
                    PracticeSession.user_id.label("user_id"),
                    func.count(PracticeSession.session_id).label("total_sessions"),
                    func.avg(score_expr).label("average_score"),
                )
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.status == "completed")
                .where(PracticeSession.start_time >= cutoff_time)
                .where(self._evaluable_filter())
                .where(
                    (PracticeSession.logic_score.isnot(None))
                    & (PracticeSession.accuracy_score.isnot(None))
                    & (PracticeSession.completeness_score.isnot(None))
                )
            )

            if normalized_scenario_type:
                aggregated_query = aggregated_query.where(
                    Scenario.scenario_type == normalized_scenario_type
                )

            aggregated_query = aggregated_query.group_by(PracticeSession.user_id)
            aggregated_subquery = aggregated_query.subquery()

            total_users_query = select(func.count()).select_from(aggregated_subquery)
            total_users_result = await db.execute(total_users_query)
            total_users = total_users_result.scalar() or 0

            user_query = select(
                aggregated_subquery.c.total_sessions,
                aggregated_subquery.c.average_score,
            ).where(aggregated_subquery.c.user_id == normalized_user_id)
            user_result = await db.execute(user_query)
            user_row = user_result.one_or_none()
            user_not_evaluable_query = (
                select(func.count(PracticeSession.session_id))
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.user_id == normalized_user_id)
                .where(PracticeSession.status == "completed")
                .where(PracticeSession.start_time >= cutoff_time)
                .where(self._not_evaluable_filter())
            )
            if normalized_scenario_type:
                user_not_evaluable_query = user_not_evaluable_query.where(
                    Scenario.scenario_type == normalized_scenario_type
                )
            user_not_evaluable_result = await db.execute(user_not_evaluable_query)
            user_not_evaluable_sessions = int(user_not_evaluable_result.scalar() or 0)

            if not user_row:
                return Result(
                    value={
                        "user_id": normalized_user_id,
                        "rank": None,
                        "total_sessions": 0,
                        "average_score": 0,
                        "score_basis": PROJECTION_SCORE_BASIS,
                        "evaluable_sessions": 0,
                        "not_evaluable_sessions": user_not_evaluable_sessions,
                        "total_users": total_users,
                        "percentile": 0,
                        "time_period": normalized_time_period,
                        "scenario_type": normalized_scenario_type,
                        "message": "No completed sessions",
                    }
                )

            higher_count_query = (
                select(func.count())
                .select_from(aggregated_subquery)
                .where(aggregated_subquery.c.average_score > user_row.average_score)
            )
            higher_count_result = await db.execute(higher_count_query)
            higher_count = higher_count_result.scalar() or 0
            rank = higher_count + 1
            percentile = (
                round(((total_users - higher_count) / total_users) * 100, 2)
                if total_users > 0
                else 0
            )

            return Result(
                value={
                    "user_id": normalized_user_id,
                    "rank": rank,
                    "total_sessions": int(user_row.total_sessions or 0),
                    "average_score": round(user_row.average_score or 0, 2),
                    "score_basis": PROJECTION_SCORE_BASIS,
                    "evaluable_sessions": int(user_row.total_sessions or 0),
                    "not_evaluable_sessions": user_not_evaluable_sessions,
                    "total_users": total_users,
                    "percentile": percentile,
                    "time_period": normalized_time_period,
                    "scenario_type": normalized_scenario_type,
                    "message": "Rank calculated",
                }
            )

        except (SQLAlchemyError, ValueError) as e:
            logger.error(
                "Failed to get user rank",
                extra={"user_id": str(user_id), "error": str(e)},
                exc_info=True,
            )
            return Result.fail(fallback="[RANK_FAILED]")


# Singleton instance
leaderboard_service = LeaderboardService()
