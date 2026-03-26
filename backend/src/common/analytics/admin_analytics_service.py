"""
Admin Analytics Service - projection-backed analytics for administrators.

Admin analytics must aggregate from the same session-evidence projection used by
history/report/replay so the admin dashboard, manager drill-ins, and learner
surfaces do not diverge on score semantics.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.analytics.history_service import (
    PROJECTION_SCORE_BASIS,
    HistorySessionSummary,
    history_service,
)
from common.db.models import PracticeSession, SessionStatus, User
from common.error_handling.result import Result

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OverviewStats:
    """System overview statistics."""

    total_users: int
    active_users_today: int
    active_users_week: int
    total_sessions: int
    sessions_today: int
    completed_sessions: int
    completion_rate: float
    average_score: float
    average_duration_minutes: float
    growth: dict[str, float]
    evaluable_sessions: int = 0
    not_evaluable_sessions: int = 0
    score_basis: str = PROJECTION_SCORE_BASIS
    top_issue_families: list[dict[str, Any]] = field(default_factory=list)
    not_evaluable_reasons: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class TrendDataPoint:
    """Single point in trend data."""

    date: str
    sessions_count: int
    average_score: float
    active_users: int


@dataclass(slots=True)
class ScoreDistribution:
    """Score distribution buckets."""

    excellent: int  # 90-100
    good: int  # 70-89
    fair: int  # 50-69
    poor: int  # 0-49


@dataclass(slots=True)
class AgentStats:
    """Agent usage statistics."""

    agent_id: str
    agent_name: str
    category: str
    usage_count: int
    average_score: float
    completion_rate: float
    evaluable_sessions: int = 0
    not_evaluable_sessions: int = 0
    score_basis: str = PROJECTION_SCORE_BASIS


@dataclass(slots=True)
class PersonaStats:
    """Persona usage statistics."""

    persona_id: str
    persona_name: str
    difficulty: str
    usage_count: int
    average_score: float
    evaluable_sessions: int = 0
    not_evaluable_sessions: int = 0
    score_basis: str = PROJECTION_SCORE_BASIS


@dataclass(slots=True)
class LeaderboardEntry:
    """User leaderboard entry."""

    rank: int
    user_id: str
    user_name: str
    department: str | None
    total_sessions: int
    average_score: float
    best_score: float
    total_duration_minutes: float
    evaluable_sessions: int = 0
    not_evaluable_sessions: int = 0
    primary_issue_type: str | None = None
    primary_next_goal_type: str | None = None
    score_basis: str = PROJECTION_SCORE_BASIS


@dataclass(slots=True)
class ProjectionAnalyticsRecord:
    """Joined session + projection summary for admin aggregation."""

    session: PracticeSession
    summary: HistorySessionSummary


def _get_time_range_start(time_range: str) -> datetime:
    """Convert time range string to UTC start datetime."""
    now = datetime.now(UTC)
    if time_range == "7d":
        return now - timedelta(days=7)
    if time_range == "30d":
        return now - timedelta(days=30)
    if time_range == "90d":
        return now - timedelta(days=90)
    return datetime(2000, 1, 1, tzinfo=UTC)


def _normalize_bucket_start(start_time: datetime, *, granularity: str) -> datetime:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)
    else:
        start_time = start_time.astimezone(UTC)
    bucket_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        bucket_start -= timedelta(days=bucket_start.weekday())
    return bucket_start


class AdminAnalyticsService:
    """Projection-backed analytics service for administrators."""

    @staticmethod
    def _round_score(value: float | int | None, digits: int = 1) -> float:
        try:
            return round(float(value or 0.0), digits)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _completed_records(
        records: list[ProjectionAnalyticsRecord],
    ) -> list[ProjectionAnalyticsRecord]:
        return [
            record
            for record in records
            if record.summary.status == SessionStatus.COMPLETED.value
        ]

    @staticmethod
    def _evaluable_records(
        records: list[ProjectionAnalyticsRecord],
    ) -> list[ProjectionAnalyticsRecord]:
        return [
            record
            for record in AdminAnalyticsService._completed_records(records)
            if record.summary.evaluable is True and record.summary.overall_score is not None
        ]

    @staticmethod
    def _not_evaluable_records(
        records: list[ProjectionAnalyticsRecord],
    ) -> list[ProjectionAnalyticsRecord]:
        return [
            record
            for record in AdminAnalyticsService._completed_records(records)
            if record.summary.evaluable is False
        ]

    @staticmethod
    def _build_issue_distribution(
        summaries: list[HistorySessionSummary],
        *,
        field_name: str,
        type_key: str,
        text_key: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        counts: Counter[str] = Counter()
        latest_text_by_type: dict[str, str | None] = {}
        latest_seen_at_by_type: dict[str, datetime] = {}

        for summary in sorted(summaries, key=lambda item: item.start_time):
            payload = getattr(summary, field_name)
            if not isinstance(payload, dict):
                continue
            bucket_type = payload.get(type_key)
            if not isinstance(bucket_type, str) or not bucket_type:
                continue
            counts[bucket_type] += 1
            latest_text_by_type[bucket_type] = (
                str(payload.get(text_key)) if payload.get(text_key) is not None else None
            )
            latest_seen_at_by_type[bucket_type] = summary.start_time

        sorted_types = sorted(
            counts,
            key=lambda bucket_type: (
                -counts[bucket_type],
                -latest_seen_at_by_type[bucket_type].timestamp(),
                bucket_type,
            ),
        )

        return [
            {
                type_key: bucket_type,
                text_key: latest_text_by_type.get(bucket_type),
                "count": counts[bucket_type],
            }
            for bucket_type in sorted_types[:limit]
        ]

    @staticmethod
    def _build_reason_distribution(
        summaries: list[HistorySessionSummary],
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        counts: Counter[str] = Counter(
            str(summary.not_evaluable_reason)
            for summary in summaries
            if isinstance(summary.not_evaluable_reason, str)
            and summary.not_evaluable_reason
        )
        return [
            {"reason": reason, "count": count}
            for reason, count in counts.most_common(limit)
        ]

    @classmethod
    def _build_score_distribution(
        cls,
        records: list[ProjectionAnalyticsRecord],
    ) -> dict[str, int]:
        excellent = 0
        good = 0
        fair = 0
        poor = 0
        for record in cls._evaluable_records(records):
            score = float(record.summary.overall_score or 0.0)
            if score >= 90:
                excellent += 1
            elif score >= 70:
                good += 1
            elif score >= 50:
                fair += 1
            else:
                poor += 1
        return {
            "excellent": excellent,
            "good": good,
            "fair": fair,
            "poor": poor,
        }

    async def _load_projection_records(
        self,
        db: AsyncSession,
        *,
        start_date: datetime,
        end_date: datetime | None = None,
        scenario_type: str | None = None,
    ) -> list[ProjectionAnalyticsRecord]:
        normalized_scenario_type = history_service.normalize_scenario_type(scenario_type)
        query = (
            select(PracticeSession)
            .options(
                selectinload(PracticeSession.user),
                selectinload(PracticeSession.scenario),
                selectinload(PracticeSession.agent),
                selectinload(PracticeSession.persona),
                selectinload(PracticeSession.presentation),
            )
            .where(PracticeSession.start_time >= start_date)
            .order_by(PracticeSession.start_time.asc())
        )

        if end_date is not None:
            query = query.where(PracticeSession.start_time < end_date)

        if normalized_scenario_type:
            query = query.where(
                PracticeSession.scenario.has(scenario_type=normalized_scenario_type)
            )

        result = await db.execute(query)
        sessions = list(result.scalars().all())
        summaries = await history_service.build_projection_summaries_for_sessions(
            db,
            sessions=sessions,
        )

        records = [
            ProjectionAnalyticsRecord(session=session, summary=summary)
            for session, summary in zip(sessions, summaries, strict=False)
        ]
        logger.info(
            "admin_analytics_projection_records_loaded",
            extra={
                "scenario_type": normalized_scenario_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat() if end_date else None,
                "session_count": len(records),
                "completed_sessions": len(self._completed_records(records)),
                "evaluable_sessions": len(self._evaluable_records(records)),
                "not_evaluable_sessions": len(self._not_evaluable_records(records)),
            },
        )
        return records

    @classmethod
    def _build_trends_payload(
        cls,
        records: list[ProjectionAnalyticsRecord],
        *,
        granularity: str,
    ) -> dict[str, Any]:
        summaries = [record.summary for record in records]
        completed_records = cls._completed_records(records)
        evaluable_summaries = [record.summary for record in cls._evaluable_records(records)]
        not_evaluable_summaries = [record.summary for record in cls._not_evaluable_records(records)]

        snapshot = history_service.build_supervisor_progress_snapshot(
            summaries,
            granularity=granularity,
        )
        active_users_by_bucket: dict[str, set[str]] = defaultdict(set)
        normalized_granularity = str(snapshot["granularity"])
        for record in completed_records:
            bucket_key = _normalize_bucket_start(
                record.summary.start_time,
                granularity=normalized_granularity,
            ).isoformat()
            active_users_by_bucket[bucket_key].add(str(record.session.user_id))

        trend_data: list[dict[str, Any]] = []
        for point in snapshot["trend_data"]:
            trend_point = dict(point)
            trend_point["average_score"] = cls._round_score(
                trend_point.get("average_score"),
                digits=1,
            )
            trend_point["logic_score"] = cls._round_score(
                trend_point.get("logic_score"),
                digits=1,
            )
            trend_point["accuracy_score"] = cls._round_score(
                trend_point.get("accuracy_score"),
                digits=1,
            )
            trend_point["completeness_score"] = cls._round_score(
                trend_point.get("completeness_score"),
                digits=1,
            )
            trend_point["active_users"] = len(
                active_users_by_bucket.get(str(point["date"]), set())
            )
            trend_data.append(trend_point)

        score_summary = history_service.build_projection_score_summary(summaries)
        return {
            "trend_data": trend_data,
            "score_distribution": cls._build_score_distribution(records),
            "projection_summary": {
                **score_summary,
                "issue_family_distribution": cls._build_issue_distribution(
                    evaluable_summaries,
                    field_name="main_issue",
                    type_key="issue_type",
                    text_key="issue_text",
                ),
                "not_evaluable_reasons": cls._build_reason_distribution(
                    not_evaluable_summaries,
                ),
                "repeated_main_issues": snapshot["repeated_main_issues"],
                "repeated_next_goals": snapshot["repeated_next_goals"],
                "score_basis": PROJECTION_SCORE_BASIS,
            },
        }

    async def get_overview_stats(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        scenario_type: str | None = None,
    ) -> Result[OverviewStats]:
        try:
            start_date = _get_time_range_start(time_range)
            now = datetime.now(UTC)
            today = now.date()
            week_ago = now - timedelta(days=7)

            current_records = await self._load_projection_records(
                db,
                start_date=start_date,
                scenario_type=scenario_type,
            )
            previous_records: list[ProjectionAnalyticsRecord] = []
            if time_range != "all_time":
                previous_start = start_date - (now - start_date)
                previous_records = await self._load_projection_records(
                    db,
                    start_date=previous_start,
                    end_date=start_date,
                    scenario_type=scenario_type,
                )

            total_users = int(
                await db.scalar(
                    select(func.count(User.user_id)).where(User.is_active.is_(True))
                )
                or 0
            )

            completed_records = self._completed_records(current_records)
            evaluable_records = self._evaluable_records(current_records)
            not_evaluable_records = self._not_evaluable_records(current_records)
            current_summaries = [record.summary for record in current_records]
            score_summary = history_service.build_projection_score_summary(current_summaries)

            total_sessions = len(current_records)
            completed_sessions = len(completed_records)
            sessions_today = sum(
                1
                for record in current_records
                if self._coerce_utc(record.summary.start_time).date() == today
            )
            active_today = len(
                {
                    str(record.session.user_id)
                    for record in current_records
                    if self._coerce_utc(record.summary.start_time).date() == today
                }
            )
            active_week = len(
                {
                    str(record.session.user_id)
                    for record in current_records
                    if self._coerce_utc(record.summary.start_time) >= week_ago
                }
            )
            completion_rate = self._round_score(
                (completed_sessions / total_sessions * 100) if total_sessions else 0,
                digits=1,
            )
            average_duration_minutes = self._round_score(
                (
                    sum(record.summary.duration_seconds for record in completed_records)
                    / len(completed_records)
                    / 60
                )
                if completed_records
                else 0,
                digits=1,
            )

            previous_summaries = [record.summary for record in previous_records]
            previous_score_summary = history_service.build_projection_score_summary(
                previous_summaries
            )
            previous_total_sessions = len(previous_records)

            prev_users = 0
            if time_range != "all_time":
                prev_users = int(
                    await db.scalar(
                        select(func.count(User.user_id)).where(
                            User.created_at < start_date,
                            User.is_active.is_(True),
                        )
                    )
                    or 0
                )

            def _growth(current_value: float, previous_value: float) -> float:
                if previous_value <= 0:
                    return 0.0
                return self._round_score(
                    ((current_value - previous_value) / previous_value) * 100,
                    digits=1,
                )

            stats = OverviewStats(
                total_users=total_users,
                active_users_today=active_today,
                active_users_week=active_week,
                total_sessions=total_sessions,
                sessions_today=sessions_today,
                completed_sessions=completed_sessions,
                completion_rate=completion_rate,
                average_score=self._round_score(score_summary["average_score"], digits=1),
                average_duration_minutes=average_duration_minutes,
                growth={
                    "users_rate": _growth(float(total_users), float(prev_users)),
                    "sessions_rate": _growth(
                        float(total_sessions),
                        float(previous_total_sessions),
                    ),
                    "score_rate": _growth(
                        float(score_summary["average_score"]),
                        float(previous_score_summary["average_score"]),
                    ),
                },
                evaluable_sessions=int(score_summary["evaluable_sessions"]),
                not_evaluable_sessions=int(score_summary["not_evaluable_sessions"]),
                score_basis=PROJECTION_SCORE_BASIS,
                top_issue_families=self._build_issue_distribution(
                    [record.summary for record in evaluable_records],
                    field_name="main_issue",
                    type_key="issue_type",
                    text_key="issue_text",
                ),
                not_evaluable_reasons=self._build_reason_distribution(
                    [record.summary for record in not_evaluable_records]
                ),
            )

            logger.info(
                "Overview stats calculated",
                extra={
                    "time_range": time_range,
                    "scenario_type": history_service.normalize_scenario_type(
                        scenario_type
                    ),
                    "total_sessions": total_sessions,
                    "evaluable_sessions": len(evaluable_records),
                    "not_evaluable_sessions": len(not_evaluable_records),
                    "score_basis": PROJECTION_SCORE_BASIS,
                },
            )
            return Result.ok(stats)

        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error(
                "Failed to calculate overview stats",
                extra={"error": str(exc)},
                exc_info=True,
            )
            return Result.fail(fallback="[OVERVIEW_STATS_FAILED]")

    async def get_trends_data(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        granularity: str = "day",
    ) -> Result[dict[str, Any]]:
        try:
            start_date = _get_time_range_start(time_range)
            records = await self._load_projection_records(
                db,
                start_date=start_date,
                scenario_type=None,
            )
            payload = self._build_trends_payload(records, granularity=granularity)

            logger.info(
                "Trends data calculated",
                extra={
                    "time_range": time_range,
                    "granularity": granularity,
                    "data_points": len(payload["trend_data"]),
                    "score_basis": PROJECTION_SCORE_BASIS,
                },
            )
            return Result.ok(payload)

        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error(
                "Failed to calculate trends data",
                extra={"error": str(exc)},
                exc_info=True,
            )
            return Result.fail(fallback="[TRENDS_DATA_FAILED]")

    async def get_agent_stats(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        limit: int = 10,
    ) -> Result[dict[str, Any]]:
        try:
            start_date = _get_time_range_start(time_range)
            records = await self._load_projection_records(db, start_date=start_date)

            grouped_agents: dict[str, list[ProjectionAnalyticsRecord]] = defaultdict(list)
            agent_meta: dict[str, tuple[str, str]] = {}
            grouped_personas: dict[str, list[ProjectionAnalyticsRecord]] = defaultdict(list)
            persona_meta: dict[str, tuple[str, str]] = {}
            scenario_distribution: Counter[str] = Counter()

            for record in records:
                scenario_distribution[record.summary.scenario_type] += 1

                agent_id = getattr(record.session, "agent_id", None)
                agent = getattr(record.session, "agent", None)
                if agent_id and agent is not None:
                    key = str(agent_id)
                    grouped_agents[key].append(record)
                    agent_meta[key] = (
                        str(getattr(agent, "name", None) or "Unknown Agent"),
                        str(getattr(agent, "category", None) or "unknown"),
                    )

                persona_id = getattr(record.session, "persona_id", None)
                persona = getattr(record.session, "persona", None)
                if persona_id and persona is not None:
                    key = str(persona_id)
                    grouped_personas[key].append(record)
                    persona_meta[key] = (
                        str(getattr(persona, "name", None) or "Unknown Persona"),
                        str(getattr(persona, "difficulty", None) or "unknown"),
                    )

            agent_stats: list[dict[str, Any]] = []
            for agent_id, agent_records in grouped_agents.items():
                summaries = [record.summary for record in agent_records]
                completed_count = len(self._completed_records(agent_records))
                score_summary = history_service.build_projection_score_summary(summaries)
                agent_name, category = agent_meta[agent_id]
                agent_stats.append(
                    {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "category": category,
                        "usage_count": len(agent_records),
                        "average_score": self._round_score(
                            score_summary["average_score"], digits=1
                        ),
                        "completion_rate": self._round_score(
                            (completed_count / len(agent_records) * 100)
                            if agent_records
                            else 0,
                            digits=1,
                        ),
                        "evaluable_sessions": int(score_summary["evaluable_sessions"]),
                        "not_evaluable_sessions": int(
                            score_summary["not_evaluable_sessions"]
                        ),
                        "score_basis": PROJECTION_SCORE_BASIS,
                    }
                )

            persona_stats: list[dict[str, Any]] = []
            for persona_id, persona_records in grouped_personas.items():
                summaries = [record.summary for record in persona_records]
                score_summary = history_service.build_projection_score_summary(summaries)
                persona_name, difficulty = persona_meta[persona_id]
                persona_stats.append(
                    {
                        "persona_id": persona_id,
                        "persona_name": persona_name,
                        "difficulty": difficulty,
                        "usage_count": len(persona_records),
                        "average_score": self._round_score(
                            score_summary["average_score"], digits=1
                        ),
                        "evaluable_sessions": int(score_summary["evaluable_sessions"]),
                        "not_evaluable_sessions": int(
                            score_summary["not_evaluable_sessions"]
                        ),
                        "score_basis": PROJECTION_SCORE_BASIS,
                    }
                )

            agent_stats.sort(
                key=lambda item: (
                    -item["usage_count"],
                    -item["average_score"],
                    item["agent_name"],
                )
            )
            persona_stats.sort(
                key=lambda item: (
                    -item["usage_count"],
                    -item["average_score"],
                    item["persona_name"],
                )
            )

            payload = {
                "agent_stats": agent_stats[:limit],
                "persona_stats": persona_stats[:limit],
                "scenario_distribution": dict(scenario_distribution),
            }

            logger.info(
                "Agent stats calculated",
                extra={
                    "time_range": time_range,
                    "agents": len(payload["agent_stats"]),
                    "personas": len(payload["persona_stats"]),
                    "score_basis": PROJECTION_SCORE_BASIS,
                },
            )
            return Result.ok(payload)

        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error(
                "Failed to calculate agent stats",
                extra={"error": str(exc)},
                exc_info=True,
            )
            return Result.fail(fallback="[AGENT_STATS_FAILED]")

    async def get_leaderboard(
        self,
        db: AsyncSession,
        time_range: str = "30d",
        limit: int = 50,
    ) -> Result[list[dict[str, Any]]]:
        try:
            start_date = _get_time_range_start(time_range)
            records = await self._load_projection_records(db, start_date=start_date)

            grouped_records: dict[str, list[ProjectionAnalyticsRecord]] = defaultdict(list)
            for record in records:
                grouped_records[str(record.session.user_id)].append(record)

            leaderboard_entries: list[dict[str, Any]] = []
            for user_id, user_records in grouped_records.items():
                summaries = [record.summary for record in user_records]
                completed_records = self._completed_records(user_records)
                score_summary = history_service.build_projection_score_summary(summaries)
                first_session = user_records[0].session
                user = getattr(first_session, "user", None)
                user_name = None
                department = None
                if user is not None:
                    user_name = getattr(user, "name", None) or getattr(user, "email", None)
                    department = getattr(user, "department", None)
                if not user_name:
                    user_name = "Unknown"

                latest_completed = max(
                    completed_records,
                    key=lambda item: item.summary.start_time,
                    default=None,
                )
                latest_issue = latest_completed.summary.main_issue if latest_completed else None
                latest_goal = latest_completed.summary.next_goal if latest_completed else None

                total_duration_minutes = self._round_score(
                    sum(record.summary.duration_seconds for record in completed_records) / 60,
                    digits=1,
                )
                leaderboard_entries.append(
                    {
                        "user_id": user_id,
                        "user_name": str(user_name),
                        "department": department,
                        "total_sessions": len(user_records),
                        "average_score": self._round_score(
                            score_summary["average_score"], digits=1
                        ),
                        "best_score": self._round_score(
                            score_summary["best_score"], digits=1
                        ),
                        "total_duration_minutes": total_duration_minutes,
                        "evaluable_sessions": int(score_summary["evaluable_sessions"]),
                        "not_evaluable_sessions": int(
                            score_summary["not_evaluable_sessions"]
                        ),
                        "primary_issue_type": (
                            str(latest_issue.get("issue_type"))
                            if isinstance(latest_issue, dict)
                            and latest_issue.get("issue_type") is not None
                            else None
                        ),
                        "primary_next_goal_type": (
                            str(latest_goal.get("goal_type"))
                            if isinstance(latest_goal, dict)
                            and latest_goal.get("goal_type") is not None
                            else None
                        ),
                        "score_basis": PROJECTION_SCORE_BASIS,
                    }
                )

            leaderboard_entries.sort(
                key=lambda entry: (
                    -entry["evaluable_sessions"],
                    -entry["average_score"],
                    -entry["best_score"],
                    -entry["total_sessions"],
                    entry["user_name"],
                )
            )

            leaderboard = [
                {
                    "rank": rank,
                    **entry,
                }
                for rank, entry in enumerate(leaderboard_entries[:limit], start=1)
            ]

            logger.info(
                "Leaderboard calculated",
                extra={
                    "time_range": time_range,
                    "users": len(leaderboard),
                    "score_basis": PROJECTION_SCORE_BASIS,
                },
            )
            return Result.ok(leaderboard)

        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error(
                "Failed to calculate leaderboard",
                extra={"error": str(exc)},
                exc_info=True,
            )
            return Result.fail(fallback="[LEADERBOARD_FAILED]")


admin_analytics_service = AdminAnalyticsService()
