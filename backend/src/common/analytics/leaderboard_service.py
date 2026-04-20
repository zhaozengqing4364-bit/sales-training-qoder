"""
Leaderboard Calculation Service - Calculates rankings for practice sessions

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation
- V. Cost control - Efficient queries
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import and_, case, desc, func, or_, select
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
    leaderboard_mode: str = "score"
    improvement_score: float | None = None
    first_score: float | None = None
    latest_score: float | None = None
    first_session_at: datetime | None = None
    latest_session_at: datetime | None = None
    sample_size: int | None = None
    issue_type: str | None = None


@dataclass
class LeaderboardStats:
    """Aggregated leaderboard statistics"""

    entries: list[LeaderboardView]
    total_users: int
    time_period: str  # daily, weekly, monthly, all_time
    score_basis: str = PROJECTION_SCORE_BASIS
    evaluable_sessions: int = 0
    not_evaluable_sessions: int = 0
    leaderboard_mode: str = "score"
    issue_type: str | None = None
    issue_type_buckets: list[dict[str, int | str]] = field(default_factory=list)
    eligibility: dict[str, object] = field(default_factory=dict)


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
        self.leaderboard_modes = {"score", "improvement", "issue_type"}

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

    def _normalize_leaderboard_mode(self, leaderboard_mode: str | None) -> str:
        """Normalize and validate leaderboard mode."""
        if not leaderboard_mode:
            return "score"
        normalized_mode = leaderboard_mode.strip().lower()
        if normalized_mode not in self.leaderboard_modes:
            raise ValueError(f"Unsupported leaderboard mode: {leaderboard_mode}")
        return normalized_mode

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

    @staticmethod
    def _score_fields_present_filter():
        return (
            (PracticeSession.logic_score.isnot(None))
            & (PracticeSession.accuracy_score.isnot(None))
            & (PracticeSession.completeness_score.isnot(None))
        )

    @staticmethod
    def _issue_type_expr():
        return PracticeSession.effectiveness_snapshot["main_issue"][
            "issue_type"
        ].as_string()

    def _base_qualified_filters(self, cutoff_time: datetime):
        return (
            PracticeSession.start_time >= cutoff_time,
            PracticeSession.status == "completed",
            self._evaluable_filter(),
            self._score_fields_present_filter(),
        )

    def _eligibility(self, leaderboard_mode: str) -> dict[str, object]:
        if leaderboard_mode == "improvement":
            return {
                "score_basis": PROJECTION_SCORE_BASIS,
                "min_evaluable_sessions": 2,
                "explanation": "进步榜至少需要 2 次可评估训练",
            }
        if leaderboard_mode == "issue_type":
            return {
                "score_basis": PROJECTION_SCORE_BASIS,
                "requires_issue_type": True,
                "explanation": "同目标榜只统计有有效问题类型的可评估训练",
            }
        return {
            "score_basis": PROJECTION_SCORE_BASIS,
            "explanation": "综合分榜只统计可评估训练",
        }

    async def calculate_leaderboard(
        self,
        db: AsyncSession,
        scenario_type: str | None = None,
        time_period: str = "all_time",
        limit: int = 100,
        leaderboard_mode: str = "score",
        issue_type: str | None = None,
    ) -> Result[LeaderboardStats]:
        """
        Calculate leaderboard for a scenario type and time period

        Returns: LeaderboardStats or Result.fail
        """
        try:
            normalized_time_period = self._normalize_time_period(time_period)
            normalized_scenario_type = self._normalize_scenario_type(scenario_type)
            normalized_leaderboard_mode = self._normalize_leaderboard_mode(
                leaderboard_mode
            )

            if normalized_leaderboard_mode == "improvement":
                return await self._calculate_improvement_leaderboard(
                    db=db,
                    scenario_type=normalized_scenario_type,
                    time_period=normalized_time_period,
                    limit=limit,
                )
            if normalized_leaderboard_mode == "issue_type":
                return await self._calculate_issue_type_leaderboard(
                    db=db,
                    scenario_type=normalized_scenario_type,
                    time_period=normalized_time_period,
                    limit=limit,
                    issue_type=issue_type,
                )

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
                .where(self._score_fields_present_filter())
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
                .where(self._score_fields_present_filter())
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
                .where(self._score_fields_present_filter())
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
                leaderboard_mode="score",
                eligibility=self._eligibility("score"),
            )

            logger.info(
                "Leaderboard calculated",
                extra={
                    "scenario_type": scenario_type,
                    "normalized_scenario_type": normalized_scenario_type,
                    "time_period": normalized_time_period,
                    "leaderboard_mode": "score",
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
                    "leaderboard_mode": leaderboard_mode,
                    "issue_type": issue_type,
                    "error": str(e),
                },
                exc_info=True,
            )
            return Result.fail(fallback="[LEADERBOARD_FAILED]")

    async def _calculate_improvement_leaderboard(
        self,
        db: AsyncSession,
        scenario_type: str | None,
        time_period: str,
        limit: int,
    ) -> Result[LeaderboardStats]:
        time_delta = self.time_periods.get(time_period, self.time_periods["all_time"])
        cutoff_time = datetime.now() - time_delta
        score_expr = self._score_expr()

        base_query = (
            select(
                User.user_id.label("user_id"),
                User.name.label("username"),
                PracticeSession.session_id.label("session_id"),
                PracticeSession.start_time.label("start_time"),
                score_expr.label("score"),
            )
            .join(PracticeSession, User.user_id == PracticeSession.user_id)
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(*self._base_qualified_filters(cutoff_time))
        )
        if scenario_type:
            base_query = base_query.where(Scenario.scenario_type == scenario_type)

        base_subquery = base_query.subquery()
        ranked_subquery = (
            select(
                base_subquery.c.user_id,
                base_subquery.c.username,
                base_subquery.c.session_id,
                base_subquery.c.start_time,
                base_subquery.c.score,
                func.row_number()
                .over(
                    partition_by=base_subquery.c.user_id,
                    order_by=(
                        base_subquery.c.start_time.asc(),
                        base_subquery.c.session_id.asc(),
                    ),
                )
                .label("first_rank"),
                func.row_number()
                .over(
                    partition_by=base_subquery.c.user_id,
                    order_by=(
                        base_subquery.c.start_time.desc(),
                        base_subquery.c.session_id.desc(),
                    ),
                )
                .label("latest_rank"),
            )
        ).subquery()

        first_score = func.max(
            case((ranked_subquery.c.first_rank == 1, ranked_subquery.c.score))
        ).label("first_score")
        latest_score = func.max(
            case((ranked_subquery.c.latest_rank == 1, ranked_subquery.c.score))
        ).label("latest_score")
        first_session_at = func.max(
            case((ranked_subquery.c.first_rank == 1, ranked_subquery.c.start_time))
        ).label("first_session_at")
        latest_session_at = func.max(
            case((ranked_subquery.c.latest_rank == 1, ranked_subquery.c.start_time))
        ).label("latest_session_at")

        grouped_subquery = (
            select(
                ranked_subquery.c.user_id,
                ranked_subquery.c.username,
                func.count(ranked_subquery.c.session_id).label("total_sessions"),
                func.avg(ranked_subquery.c.score).label("average_score"),
                func.max(ranked_subquery.c.score).label("best_score"),
                first_score,
                latest_score,
                (latest_score - first_score).label("improvement_score"),
                first_session_at,
                latest_session_at,
            )
            .group_by(ranked_subquery.c.user_id, ranked_subquery.c.username)
            .having(func.count(ranked_subquery.c.session_id) >= 2)
        ).subquery()

        query = (
            select(grouped_subquery)
            .order_by(
                grouped_subquery.c.improvement_score.desc(),
                grouped_subquery.c.latest_score.desc(),
                grouped_subquery.c.total_sessions.desc(),
                grouped_subquery.c.latest_session_at.desc(),
            )
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.all()

        entries = [
            LeaderboardView(
                user_id=row.user_id,
                username=row.username or "Anonymous",
                total_sessions=int(row.total_sessions or 0),
                average_score=round(row.average_score or 0, 2),
                best_score=round(row.best_score or 0, 2),
                rank=rank,
                leaderboard_mode="improvement",
                improvement_score=round(row.improvement_score or 0, 2),
                first_score=round(row.first_score or 0, 2),
                latest_score=round(row.latest_score or 0, 2),
                first_session_at=row.first_session_at,
                latest_session_at=row.latest_session_at,
                sample_size=int(row.total_sessions or 0),
            )
            for rank, row in enumerate(rows, start=1)
        ]

        total_users_result = await db.execute(
            select(func.count()).select_from(grouped_subquery)
        )
        evaluable_sessions_result = await db.execute(
            select(func.coalesce(func.sum(grouped_subquery.c.total_sessions), 0))
        )
        not_evaluable_sessions = await self._count_not_evaluable_sessions(
            db=db,
            cutoff_time=cutoff_time,
            scenario_type=scenario_type,
        )

        stats = LeaderboardStats(
            entries=entries,
            total_users=int(total_users_result.scalar() or 0),
            time_period=time_period,
            evaluable_sessions=int(evaluable_sessions_result.scalar() or 0),
            not_evaluable_sessions=not_evaluable_sessions,
            leaderboard_mode="improvement",
            eligibility=self._eligibility("improvement"),
        )

        logger.info(
            "Leaderboard calculated",
            extra={
                "scenario_type": scenario_type,
                "time_period": time_period,
                "leaderboard_mode": "improvement",
                "entries": len(entries),
            },
        )
        return Result(value=stats)

    async def _calculate_issue_type_leaderboard(
        self,
        db: AsyncSession,
        scenario_type: str | None,
        time_period: str,
        limit: int,
        issue_type: str | None,
    ) -> Result[LeaderboardStats]:
        normalized_issue_type = issue_type.strip() if issue_type else None
        normalized_issue_type = normalized_issue_type or None
        time_delta = self.time_periods.get(time_period, self.time_periods["all_time"])
        cutoff_time = datetime.now() - time_delta
        issue_type_expr = self._issue_type_expr()
        score_expr = self._score_expr()

        if not normalized_issue_type:
            buckets = await self._get_issue_type_buckets(
                db=db,
                cutoff_time=cutoff_time,
                scenario_type=scenario_type,
            )
            not_evaluable_sessions = await self._count_not_evaluable_sessions(
                db=db,
                cutoff_time=cutoff_time,
                scenario_type=scenario_type,
            )
            return Result(
                value=LeaderboardStats(
                    entries=[],
                    total_users=0,
                    time_period=time_period,
                    evaluable_sessions=sum(
                        int(bucket["evaluable_sessions"]) for bucket in buckets
                    ),
                    not_evaluable_sessions=not_evaluable_sessions,
                    leaderboard_mode="issue_type",
                    issue_type=None,
                    issue_type_buckets=buckets,
                    eligibility={
                        **self._eligibility("issue_type"),
                        "explanation": "请选择一个目标问题后查看同目标榜",
                    },
                )
            )

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
            .where(*self._base_qualified_filters(cutoff_time))
            .where(issue_type_expr == normalized_issue_type)
            .group_by(User.user_id, User.name)
            .order_by(desc("average_score"))
            .limit(limit)
        )
        if scenario_type:
            query = query.where(Scenario.scenario_type == scenario_type)

        result = await db.execute(query)
        rows = result.all()
        entries = [
            LeaderboardView(
                user_id=row.user_id,
                username=row.username or "Anonymous",
                total_sessions=int(row.total_sessions or 0),
                average_score=round(row.average_score or 0, 2),
                best_score=round(row.best_score or 0, 2),
                rank=rank,
                leaderboard_mode="issue_type",
                issue_type=normalized_issue_type,
            )
            for rank, row in enumerate(rows, start=1)
        ]

        count_query = (
            select(func.count(func.distinct(User.user_id)))
            .join(PracticeSession, User.user_id == PracticeSession.user_id)
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(*self._base_qualified_filters(cutoff_time))
            .where(issue_type_expr == normalized_issue_type)
        )
        evaluable_sessions_query = (
            select(func.count(PracticeSession.session_id))
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(*self._base_qualified_filters(cutoff_time))
            .where(issue_type_expr == normalized_issue_type)
        )
        if scenario_type:
            count_query = count_query.where(Scenario.scenario_type == scenario_type)
            evaluable_sessions_query = evaluable_sessions_query.where(
                Scenario.scenario_type == scenario_type
            )

        count_result = await db.execute(count_query)
        evaluable_sessions_result = await db.execute(evaluable_sessions_query)
        not_evaluable_sessions = await self._count_not_evaluable_sessions(
            db=db,
            cutoff_time=cutoff_time,
            scenario_type=scenario_type,
        )

        stats = LeaderboardStats(
            entries=entries,
            total_users=int(count_result.scalar() or 0),
            time_period=time_period,
            evaluable_sessions=int(evaluable_sessions_result.scalar() or 0),
            not_evaluable_sessions=not_evaluable_sessions,
            leaderboard_mode="issue_type",
            issue_type=normalized_issue_type,
            issue_type_buckets=await self._get_issue_type_buckets(
                db=db,
                cutoff_time=cutoff_time,
                scenario_type=scenario_type,
            ),
            eligibility=self._eligibility("issue_type"),
        )

        logger.info(
            "Leaderboard calculated",
            extra={
                "scenario_type": scenario_type,
                "time_period": time_period,
                "leaderboard_mode": "issue_type",
                "issue_type": normalized_issue_type,
                "entries": len(entries),
            },
        )
        return Result(value=stats)

    async def _get_issue_type_buckets(
        self,
        db: AsyncSession,
        cutoff_time: datetime,
        scenario_type: str | None,
    ) -> list[dict[str, int | str]]:
        issue_type_expr = self._issue_type_expr()
        query = (
            select(
                issue_type_expr.label("issue_type"),
                func.count(func.distinct(PracticeSession.user_id)).label("count"),
                func.count(PracticeSession.session_id).label("evaluable_sessions"),
            )
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(*self._base_qualified_filters(cutoff_time))
            .where(issue_type_expr.isnot(None))
            .where(func.trim(issue_type_expr) != "")
            .group_by(issue_type_expr)
            .order_by(desc("evaluable_sessions"), issue_type_expr.asc())
        )
        if scenario_type:
            query = query.where(Scenario.scenario_type == scenario_type)

        result = await db.execute(query)
        return [
            {
                "issue_type": row.issue_type,
                "count": int(row.count or 0),
                "evaluable_sessions": int(row.evaluable_sessions or 0),
            }
            for row in result.all()
        ]

    async def _count_not_evaluable_sessions(
        self,
        db: AsyncSession,
        cutoff_time: datetime,
        scenario_type: str | None,
    ) -> int:
        query = (
            select(func.count(PracticeSession.session_id))
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(PracticeSession.start_time >= cutoff_time)
            .where(PracticeSession.status == "completed")
            .where(self._not_evaluable_filter())
        )
        if scenario_type:
            query = query.where(Scenario.scenario_type == scenario_type)
        result = await db.execute(query)
        return int(result.scalar() or 0)

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
        leaderboard_mode: str = "score",
        issue_type: str | None = None,
    ) -> Result[dict]:
        """
        Get a user's rank and stats

        Returns: User rank info or Result.fail
        """
        try:
            normalized_time_period = self._normalize_time_period(time_period)
            normalized_scenario_type = self._normalize_scenario_type(scenario_type)
            normalized_leaderboard_mode = self._normalize_leaderboard_mode(
                leaderboard_mode
            )
            normalized_user_id = str(user_id)
            cutoff_time = datetime.now() - self.time_periods.get(
                normalized_time_period, self.time_periods["all_time"]
            )

            if normalized_leaderboard_mode == "improvement":
                return await self._get_improvement_user_rank(
                    db=db,
                    user_id=normalized_user_id,
                    scenario_type=normalized_scenario_type,
                    time_period=normalized_time_period,
                    cutoff_time=cutoff_time,
                )
            if normalized_leaderboard_mode == "issue_type":
                return await self._get_issue_type_user_rank(
                    db=db,
                    user_id=normalized_user_id,
                    scenario_type=normalized_scenario_type,
                    time_period=normalized_time_period,
                    cutoff_time=cutoff_time,
                    issue_type=issue_type,
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
                .where(self._score_fields_present_filter())
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
                        "leaderboard_mode": "score",
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
                    "leaderboard_mode": "score",
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
                extra={
                    "user_id": str(user_id),
                    "leaderboard_mode": leaderboard_mode,
                    "issue_type": issue_type,
                    "error": str(e),
                },
                exc_info=True,
            )
            return Result.fail(fallback="[RANK_FAILED]")

    async def _get_improvement_user_rank(
        self,
        db: AsyncSession,
        user_id: str,
        scenario_type: str | None,
        time_period: str,
        cutoff_time: datetime,
    ) -> Result[dict]:
        score_expr = self._score_expr()
        base_query = (
            select(
                PracticeSession.user_id.label("user_id"),
                PracticeSession.session_id.label("session_id"),
                PracticeSession.start_time.label("start_time"),
                score_expr.label("score"),
            )
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(*self._base_qualified_filters(cutoff_time))
        )
        user_evaluable_query = (
            select(func.count(PracticeSession.session_id))
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(PracticeSession.user_id == user_id)
            .where(*self._base_qualified_filters(cutoff_time))
        )
        if scenario_type:
            base_query = base_query.where(Scenario.scenario_type == scenario_type)
            user_evaluable_query = user_evaluable_query.where(
                Scenario.scenario_type == scenario_type
            )

        base_subquery = base_query.subquery()
        ranked_subquery = (
            select(
                base_subquery.c.user_id,
                base_subquery.c.session_id,
                base_subquery.c.start_time,
                base_subquery.c.score,
                func.row_number()
                .over(
                    partition_by=base_subquery.c.user_id,
                    order_by=(
                        base_subquery.c.start_time.asc(),
                        base_subquery.c.session_id.asc(),
                    ),
                )
                .label("first_rank"),
                func.row_number()
                .over(
                    partition_by=base_subquery.c.user_id,
                    order_by=(
                        base_subquery.c.start_time.desc(),
                        base_subquery.c.session_id.desc(),
                    ),
                )
                .label("latest_rank"),
            )
        ).subquery()

        first_score = func.max(
            case((ranked_subquery.c.first_rank == 1, ranked_subquery.c.score))
        ).label("first_score")
        latest_score = func.max(
            case((ranked_subquery.c.latest_rank == 1, ranked_subquery.c.score))
        ).label("latest_score")
        first_session_at = func.max(
            case((ranked_subquery.c.first_rank == 1, ranked_subquery.c.start_time))
        ).label("first_session_at")
        latest_session_at = func.max(
            case((ranked_subquery.c.latest_rank == 1, ranked_subquery.c.start_time))
        ).label("latest_session_at")

        grouped_subquery = (
            select(
                ranked_subquery.c.user_id,
                func.count(ranked_subquery.c.session_id).label("total_sessions"),
                func.avg(ranked_subquery.c.score).label("average_score"),
                func.max(ranked_subquery.c.score).label("best_score"),
                first_score,
                latest_score,
                (latest_score - first_score).label("improvement_score"),
                first_session_at,
                latest_session_at,
            )
            .group_by(ranked_subquery.c.user_id)
            .having(func.count(ranked_subquery.c.session_id) >= 2)
        ).subquery()

        total_users_result = await db.execute(
            select(func.count()).select_from(grouped_subquery)
        )
        total_users = int(total_users_result.scalar() or 0)
        user_result = await db.execute(
            select(grouped_subquery).where(grouped_subquery.c.user_id == user_id)
        )
        user_row = user_result.one_or_none()
        not_evaluable_sessions = await self._count_not_evaluable_sessions(
            db=db,
            cutoff_time=cutoff_time,
            scenario_type=scenario_type,
        )

        if not user_row:
            user_evaluable_result = await db.execute(user_evaluable_query)
            user_evaluable_sessions = int(user_evaluable_result.scalar() or 0)
            return Result(
                value={
                    "user_id": user_id,
                    "rank": None,
                    "total_sessions": user_evaluable_sessions,
                    "average_score": 0,
                    "score_basis": PROJECTION_SCORE_BASIS,
                    "leaderboard_mode": "improvement",
                    "evaluable_sessions": user_evaluable_sessions,
                    "not_evaluable_sessions": not_evaluable_sessions,
                    "total_users": total_users,
                    "percentile": 0,
                    "time_period": time_period,
                    "scenario_type": scenario_type,
                    "improvement_score": None,
                    "first_score": None,
                    "latest_score": None,
                    "sample_size": user_evaluable_sessions,
                    "message": "At least 2 evaluable sessions required",
                }
            )

        higher_count_query = (
            select(func.count())
            .select_from(grouped_subquery)
            .where(
                or_(
                    grouped_subquery.c.improvement_score
                    > user_row.improvement_score,
                    and_(
                        grouped_subquery.c.improvement_score
                        == user_row.improvement_score,
                        grouped_subquery.c.latest_score > user_row.latest_score,
                    ),
                    and_(
                        grouped_subquery.c.improvement_score
                        == user_row.improvement_score,
                        grouped_subquery.c.latest_score == user_row.latest_score,
                        grouped_subquery.c.total_sessions > user_row.total_sessions,
                    ),
                    and_(
                        grouped_subquery.c.improvement_score
                        == user_row.improvement_score,
                        grouped_subquery.c.latest_score == user_row.latest_score,
                        grouped_subquery.c.total_sessions == user_row.total_sessions,
                        grouped_subquery.c.latest_session_at
                        > user_row.latest_session_at,
                    ),
                )
            )
        )
        higher_count_result = await db.execute(higher_count_query)
        higher_count = int(higher_count_result.scalar() or 0)
        rank = higher_count + 1
        percentile = (
            round(((total_users - higher_count) / total_users) * 100, 2)
            if total_users > 0
            else 0
        )

        return Result(
            value={
                "user_id": user_id,
                "rank": rank,
                "total_sessions": int(user_row.total_sessions or 0),
                "average_score": round(user_row.average_score or 0, 2),
                "best_score": round(user_row.best_score or 0, 2),
                "score_basis": PROJECTION_SCORE_BASIS,
                "leaderboard_mode": "improvement",
                "evaluable_sessions": int(user_row.total_sessions or 0),
                "not_evaluable_sessions": not_evaluable_sessions,
                "total_users": total_users,
                "percentile": percentile,
                "time_period": time_period,
                "scenario_type": scenario_type,
                "improvement_score": round(user_row.improvement_score or 0, 2),
                "first_score": round(user_row.first_score or 0, 2),
                "latest_score": round(user_row.latest_score or 0, 2),
                "first_session_at": user_row.first_session_at,
                "latest_session_at": user_row.latest_session_at,
                "sample_size": int(user_row.total_sessions or 0),
                "message": "Rank calculated",
            }
        )

    async def _get_issue_type_user_rank(
        self,
        db: AsyncSession,
        user_id: str,
        scenario_type: str | None,
        time_period: str,
        cutoff_time: datetime,
        issue_type: str | None,
    ) -> Result[dict]:
        normalized_issue_type = issue_type.strip() if issue_type else None
        normalized_issue_type = normalized_issue_type or None
        not_evaluable_sessions = await self._count_not_evaluable_sessions(
            db=db,
            cutoff_time=cutoff_time,
            scenario_type=scenario_type,
        )

        if not normalized_issue_type:
            buckets = await self._get_issue_type_buckets(
                db=db,
                cutoff_time=cutoff_time,
                scenario_type=scenario_type,
            )
            return Result(
                value={
                    "user_id": user_id,
                    "rank": None,
                    "total_sessions": 0,
                    "average_score": 0,
                    "score_basis": PROJECTION_SCORE_BASIS,
                    "leaderboard_mode": "issue_type",
                    "issue_type": None,
                    "issue_type_buckets": buckets,
                    "evaluable_sessions": 0,
                    "not_evaluable_sessions": not_evaluable_sessions,
                    "total_users": 0,
                    "percentile": 0,
                    "time_period": time_period,
                    "scenario_type": scenario_type,
                    "message": "Select issue_type to calculate rank",
                }
            )

        score_expr = self._score_expr()
        issue_type_expr = self._issue_type_expr()
        aggregated_query = (
            select(
                PracticeSession.user_id.label("user_id"),
                func.count(PracticeSession.session_id).label("total_sessions"),
                func.avg(score_expr).label("average_score"),
            )
            .join(Scenario, PracticeSession.scenario_id == Scenario.scenario_id)
            .where(*self._base_qualified_filters(cutoff_time))
            .where(issue_type_expr == normalized_issue_type)
        )
        if scenario_type:
            aggregated_query = aggregated_query.where(
                Scenario.scenario_type == scenario_type
            )
        aggregated_subquery = aggregated_query.group_by(
            PracticeSession.user_id
        ).subquery()

        total_users_result = await db.execute(
            select(func.count()).select_from(aggregated_subquery)
        )
        total_users = int(total_users_result.scalar() or 0)
        user_result = await db.execute(
            select(
                aggregated_subquery.c.total_sessions,
                aggregated_subquery.c.average_score,
            ).where(aggregated_subquery.c.user_id == user_id)
        )
        user_row = user_result.one_or_none()

        if not user_row:
            return Result(
                value={
                    "user_id": user_id,
                    "rank": None,
                    "total_sessions": 0,
                    "average_score": 0,
                    "score_basis": PROJECTION_SCORE_BASIS,
                    "leaderboard_mode": "issue_type",
                    "issue_type": normalized_issue_type,
                    "evaluable_sessions": 0,
                    "not_evaluable_sessions": not_evaluable_sessions,
                    "total_users": total_users,
                    "percentile": 0,
                    "time_period": time_period,
                    "scenario_type": scenario_type,
                    "message": "No completed sessions for issue_type",
                }
            )

        higher_count_result = await db.execute(
            select(func.count())
            .select_from(aggregated_subquery)
            .where(aggregated_subquery.c.average_score > user_row.average_score)
        )
        higher_count = int(higher_count_result.scalar() or 0)
        rank = higher_count + 1
        percentile = (
            round(((total_users - higher_count) / total_users) * 100, 2)
            if total_users > 0
            else 0
        )

        return Result(
            value={
                "user_id": user_id,
                "rank": rank,
                "total_sessions": int(user_row.total_sessions or 0),
                "average_score": round(user_row.average_score or 0, 2),
                "score_basis": PROJECTION_SCORE_BASIS,
                "leaderboard_mode": "issue_type",
                "issue_type": normalized_issue_type,
                "evaluable_sessions": int(user_row.total_sessions or 0),
                "not_evaluable_sessions": not_evaluable_sessions,
                "total_users": total_users,
                "percentile": percentile,
                "time_period": time_period,
                "scenario_type": scenario_type,
                "message": "Rank calculated",
            }
        )


# Singleton instance
leaderboard_service = LeaderboardService()
