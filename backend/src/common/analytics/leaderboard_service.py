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
from sqlalchemy.ext.asyncio import AsyncSession

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


@dataclass
class LeaderboardStats:
    """Aggregated leaderboard statistics"""
    entries: list[LeaderboardView]
    total_users: int
    time_period: str  # daily, weekly, monthly, all_time


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

    async def calculate_leaderboard(
        self,
        db: AsyncSession,
        scenario_type: str | None = None,
        time_period: str = "all_time",
        limit: int = 100
    ) -> Result[LeaderboardStats]:
        """
        Calculate leaderboard for a scenario type and time period

        Returns: LeaderboardStats or Result.fail
        """
        try:
            # Get time filter
            time_delta = self.time_periods.get(time_period, self.time_periods["all_time"])
            cutoff_time = datetime.now() - time_delta

            # Build query
            query = (
                select(
                    User.user_id,
                    User.name.label("username"),
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
                    ).label("best_score")
                )
                .join(PracticeSession, User.user_id == PracticeSession.user_id)
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
                .where(
                    (PracticeSession.logic_score.isnot(None)) &
                    (PracticeSession.accuracy_score.isnot(None)) &
                    (PracticeSession.completeness_score.isnot(None))
                )
                .group_by(User.user_id, User.name)
                .order_by(desc("average_score"))
                .limit(limit)
            )

            # Filter by scenario type if specified
            if scenario_type:
                query = query.where(Scenario.scenario_type == scenario_type)

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
                    rank=rank
                )
                entries.append(entry)

            # Get total users count
            count_query = (
                select(func.count(func.distinct(User.user_id)))
                .join(PracticeSession, User.user_id == PracticeSession.user_id)
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.start_time >= cutoff_time)
                .where(PracticeSession.status == "completed")
            )

            if scenario_type:
                count_query = count_query.where(Scenario.scenario_type == scenario_type)

            count_result = await db.execute(count_query)
            total_users = count_result.scalar() or 0

            stats = LeaderboardStats(
                entries=entries,
                total_users=total_users,
                time_period=time_period
            )

            logger.info(
                "Leaderboard calculated",
                extra={
                    "scenario_type": scenario_type,
                    "time_period": time_period,
                    "entries": len(entries),
                }
            )

            return Result(value=stats)

        except Exception as e:
            logger.error(
                "Failed to calculate leaderboard",
                extra={"scenario_type": scenario_type, "time_period": time_period, "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[LEADERBOARD_FAILED]")

    async def update_leaderboard_entries(
        self,
        db: AsyncSession
    ) -> Result[bool]:
        """
        Update leaderboard entries in database

        Called periodically to refresh leaderboard tables

        Returns: True or Result.fail
        """
        try:
            # Clear existing entries
            await db.execute(LeaderboardEntry.__table__.delete())

            # Calculate all-time leaderboard for each scenario type
            for scenario_type in ["presentation", "sales_bot"]:
                result = await self.calculate_leaderboard(
                    db=db,
                    scenario_type=scenario_type,
                    time_period="all_time",
                    limit=1000
                )

                if result.is_success:
                    stats = result.value

                    # Insert entries into database
                    for entry in stats.entries:
                        leaderboard_entry = LeaderboardEntry(
                            entry_id=uuid.uuid4(),
                            user_id=entry.user_id,
                            scenario_type=scenario_type,
                            rank=entry.rank,
                            score=entry.average_score,
                            total_sessions=entry.total_sessions,
                            updated_at=datetime.now()
                        )
                        db.add(leaderboard_entry)

            await db.commit()

            logger.info("Leaderboard entries updated")

            return Result(value=True)

        except Exception as e:
            logger.error(
                "Failed to update leaderboard entries",
                extra={"error": str(e)},
                exc_info=True
            )
            await db.rollback()
            return Result.fail(fallback="[UPDATE_FAILED]")

    async def get_user_rank(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        scenario_type: str | None = None
    ) -> Result[dict]:
        """
        Get a user's rank and stats

        Returns: User rank info or Result.fail
        """
        try:
            # Calculate user's average score
            query = (
                select(
                    func.count(PracticeSession.session_id).label("total_sessions"),
                    func.avg(
                        PracticeSession.logic_score * 0.4 +
                         PracticeSession.accuracy_score * 0.3 +
                         PracticeSession.completeness_score * 0.3
                    ).label("average_score")
                )
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.user_id == user_id)
                .where(PracticeSession.status == "completed")
            )

            if scenario_type:
                query = query.where(Scenario.scenario_type == scenario_type)

            result = await db.execute(query)
            row = result.one_or_none()

            if not row or row.total_sessions == 0:
                return Result(value={
                    "user_id": str(user_id),
                    "rank": None,
                    "total_sessions": 0,
                    "average_score": 0,
                    "message": "No completed sessions"
                })

            # Calculate rank (count users with higher average score)
            rank_query = (
                select(func.count(func.distinct(PracticeSession.user_id)))
                .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
                .where(PracticeSession.status == "completed")
                .group_by(PracticeSession.user_id)
                .having(
                    func.avg(
                        PracticeSession.logic_score * 0.4 +
                        PracticeSession.accuracy_score * 0.3 +
                        PracticeSession.completeness_score * 0.3
                    ) > row.average_score
                )
            )

            if scenario_type:
                rank_query = rank_query.where(Scenario.scenario_type == scenario_type)

            rank_result = await db.execute(rank_query)
            higher_count = rank_result.scalar() or 0
            rank = higher_count + 1

            return Result(value={
                "user_id": str(user_id),
                "rank": rank,
                "total_sessions": row.total_sessions,
                "average_score": round(row.average_score or 0, 2),
                "message": "Rank calculated"
            })

        except Exception as e:
            logger.error(
                "Failed to get user rank",
                extra={"user_id": str(user_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[RANK_FAILED]")


# Singleton instance
leaderboard_service = LeaderboardService()
