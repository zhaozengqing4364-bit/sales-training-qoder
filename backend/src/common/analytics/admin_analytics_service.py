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

# M018/S01/T01 DB performance discovery inventory:
# - keep the first-round baseline next to the projection-backed admin analytics authority.
# - distinguish confirmed multi-query/query-fanout shapes from index ideas that still need
#   EXPLAIN/pg_stat_statements before implementation priority is set.
ADMIN_ANALYTICS_DB_PERFORMANCE_BASELINE: tuple[dict[str, Any], ...] = (
    {
        "path": "projection_window_load",
        "callers": (
            "get_overview_stats",
            "get_trends_data",
            "get_operating_pack",
            "get_agent_stats",
            "get_leaderboard",
            "admin.api.analytics.export_analytics",
        ),
        "query_shape": (
            "one practice_sessions window query with selectinload bursts for user/scenario/agent/persona/presentation",
            "one batched conversation_messages fetch for every completed session in the window via history_service.build_projection_summaries_for_sessions",
            "projection aggregation then runs in Python over all loaded rows",
        ),
        "risk": "near_runtime_hot_path",
        "n_plus_one_risk": "not a row-by-row ORM N+1 inside this service; the main risk is repeating the same bulk projection load for each endpoint/export slice of the same time window",
        "slow_query_candidates": (
            "large time windows force full message fanout into SessionEvidence projection even when the caller only needs cohort aggregates",
            "time_range != all_time doubles the projection load because overview growth compares current and previous windows separately",
            "export_analytics currently fans out into overview + trends + leaderboard, each of which rebuilds the same projection window independently",
        ),
        "index_candidates": (
            "practice_sessions composite access paths around (start_time, user_id) or (status, start_time) may outperform the current single-column indexes for cohort windows, but this still needs real Postgres evidence",
            "scenario.has(scenario_type=...) keeps the scenario filter on a relationship predicate; if that shows up in plans, validate whether the better fix is query-shape change or a supporting scenario/practice-session index before adding anything",
        ),
        "evidence_level": "code_path_confirmed_for_bulk_projection_fanout__index_priority_still_needs_runtime_postgres_proof",
    },
    {
        "path": "leaderboard_python_reduce",
        "callers": (
            "get_leaderboard",
            "admin.api.analytics.export_analytics",
        ),
        "query_shape": (
            "reuses the full projection window load",
            "groups every loaded record by user_id in Python",
            "sorts/ranks leaderboard entries after the full in-memory reduce",
        ),
        "risk": "runtime_hot_if_window_or_user_count_grows",
        "n_plus_one_risk": "none after the loader; the cost is full-window fan-in plus Python grouping/sorting",
        "slow_query_candidates": (
            "leaderboard has to read all sessions in the window before it can rank even when only top-N rows are returned",
        ),
        "index_candidates": (
            "do not add leaderboard-specific indexes before measuring whether the real bottleneck is SQL scan time or Python-side projection/ranking cost",
        ),
        "evidence_level": "code_path_confirmed_for_full_window_reduce__topn_pushdown_strategy_still_needs_real_runtime_measurement",
    },
)


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

    @staticmethod
    def _blocked_evaluable_records(
        records: list[ProjectionAnalyticsRecord],
    ) -> list[ProjectionAnalyticsRecord]:
        return [
            record
            for record in AdminAnalyticsService._evaluable_records(records)
            if record.summary.overall_result not in {"pass", "strong_pass"}
        ]

    @staticmethod
    def _resolve_user_name(record: ProjectionAnalyticsRecord) -> str:
        user = getattr(record.session, "user", None)
        if user is None:
            return str(record.session.user_id)
        return str(getattr(user, "name", None) or getattr(user, "email", None) or record.session.user_id)

    @staticmethod
    def _resolve_department(record: ProjectionAnalyticsRecord) -> str:
        user = getattr(record.session, "user", None)
        department = getattr(user, "department", None) if user is not None else None
        if isinstance(department, str) and department.strip():
            return department.strip()
        return "未分配部门"

    @staticmethod
    def _extract_degraded_reasons(summary: HistorySessionSummary) -> list[str]:
        evidence = summary.evidence_completeness if isinstance(summary.evidence_completeness, dict) else None
        if evidence is None:
            return []

        reasons: list[str] = []
        degraded_reasons = evidence.get("degraded_reasons")
        if isinstance(degraded_reasons, list):
            reasons.extend(
                str(reason)
                for reason in degraded_reasons
                if isinstance(reason, str) and reason.strip()
            )

        if reasons:
            return reasons

        if bool(evidence.get("complete", True)):
            return []

        missing_fields = evidence.get("missing_fields")
        if isinstance(missing_fields, list):
            reasons.extend(
                str(field)
                for field in missing_fields
                if isinstance(field, str) and field.strip()
            )

        if reasons:
            return reasons
        return ["projection_incomplete"]

    @classmethod
    def _build_degraded_reason_distribution(
        cls,
        summaries: list[HistorySessionSummary],
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        counts: Counter[str] = Counter()
        for summary in summaries:
            counts.update(cls._extract_degraded_reasons(summary))

        ranked_reasons = sorted(
            counts,
            key=lambda reason: (-counts[reason], reason),
        )
        return [
            {"reason": reason, "count": counts[reason]}
            for reason in ranked_reasons[:limit]
        ]

    @classmethod
    def _build_blocker_family_buckets(
        cls,
        records: list[ProjectionAnalyticsRecord],
        *,
        include_department_count: bool,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}

        for record in sorted(records, key=lambda item: item.summary.start_time):
            issue_family = history_service.resolve_summary_issue_family(record.summary)
            if not issue_family:
                continue

            payload = record.summary.main_issue if isinstance(record.summary.main_issue, dict) else {}
            issue_type = payload.get("issue_type") if isinstance(payload.get("issue_type"), str) else issue_family
            issue_text = payload.get("issue_text") if isinstance(payload.get("issue_text"), str) else None
            department = cls._resolve_department(record)
            session_start = cls._coerce_utc(record.summary.start_time)

            bucket = grouped.setdefault(
                issue_family,
                {
                    "issue_family": issue_family,
                    "issue_type": issue_type,
                    "issue_text": issue_text,
                    "count": 0,
                    "user_ids": set(),
                    "departments": set(),
                    "latest_start_time": session_start,
                },
            )
            bucket["count"] += 1
            bucket["user_ids"].add(str(record.session.user_id))
            bucket["departments"].add(department)
            if session_start >= bucket["latest_start_time"]:
                bucket["latest_start_time"] = session_start
                bucket["issue_type"] = issue_type
                bucket["issue_text"] = issue_text

        ranked_families = sorted(
            grouped,
            key=lambda issue_family: (
                -int(grouped[issue_family]["count"]),
                -grouped[issue_family]["latest_start_time"].timestamp(),
                issue_family,
            ),
        )

        buckets: list[dict[str, Any]] = []
        for issue_family in ranked_families[:limit]:
            bucket = grouped[issue_family]
            item = {
                "issue_family": issue_family,
                "issue_type": bucket["issue_type"],
                "issue_text": bucket["issue_text"],
                "count": int(bucket["count"]),
                "user_count": len(bucket["user_ids"]),
            }
            if include_department_count:
                item["department_count"] = len(bucket["departments"])
            buckets.append(item)
        return buckets

    @classmethod
    async def _load_last_completed_sessions(
        cls,
        db: AsyncSession,
        *,
        scenario_type: str | None,
    ) -> list[dict[str, Any]]:
        normalized_scenario_type = history_service.normalize_scenario_type(scenario_type)
        query = (
            select(
                PracticeSession.user_id,
                func.max(PracticeSession.start_time).label("last_session_at"),
                User.name,
                User.department,
            )
            .join(User, User.user_id == PracticeSession.user_id)
            .where(PracticeSession.status == SessionStatus.COMPLETED.value)
            .group_by(PracticeSession.user_id, User.name, User.department)
        )
        if normalized_scenario_type:
            query = query.where(
                PracticeSession.scenario.has(scenario_type=normalized_scenario_type)
            )

        rows = (await db.execute(query)).all()
        payload: list[dict[str, Any]] = []
        for row in rows:
            if row.last_session_at is None:
                continue
            payload.append(
                {
                    "user_id": str(row.user_id),
                    "user_name": row.name,
                    "department": row.department,
                    "last_session_at": cls._coerce_utc(row.last_session_at),
                }
            )
        return payload

    @classmethod
    def _build_manager_lists(
        cls,
        records: list[ProjectionAnalyticsRecord],
        *,
        last_completed_rows: list[dict[str, Any]],
        inactive_days: int,
        limit: int,
    ) -> dict[str, Any]:
        evaluable_records = cls._evaluable_records(records)
        grouped_by_user: dict[str, list[ProjectionAnalyticsRecord]] = defaultdict(list)
        for record in evaluable_records:
            grouped_by_user[str(record.session.user_id)].append(record)

        not_passed: list[dict[str, Any]] = []
        for user_id, user_records in grouped_by_user.items():
            latest_record = max(user_records, key=lambda item: item.summary.start_time)
            if latest_record.summary.overall_result in {"pass", "strong_pass"}:
                continue
            not_passed.append(
                {
                    "user_id": user_id,
                    "user_name": cls._resolve_user_name(latest_record),
                    "department": cls._resolve_department(latest_record),
                    "overall_result": latest_record.summary.overall_result or "fail",
                    "session_id": str(latest_record.session.session_id),
                    "session_start_time": cls._coerce_utc(latest_record.summary.start_time).isoformat(),
                    "issue_family": history_service.resolve_summary_issue_family(
                        latest_record.summary
                    ),
                }
            )
        not_passed.sort(
            key=lambda item: (
                item["session_start_time"],
                item["user_name"],
            ),
            reverse=True,
        )

        now = datetime.now(UTC)
        inactive_streak: list[dict[str, Any]] = []
        for row in last_completed_rows:
            last_session_at = row["last_session_at"]
            inactive_span = now - last_session_at
            days_inactive = int(inactive_span.total_seconds() // 86400)
            if days_inactive < inactive_days:
                continue
            inactive_streak.append(
                {
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "department": row["department"],
                    "last_session_at": last_session_at.isoformat(),
                    "inactive_days": days_inactive,
                }
            )
        inactive_streak.sort(
            key=lambda item: (-item["inactive_days"], item["user_name"]),
        )

        improving: list[dict[str, Any]] = []
        for user_id, user_records in grouped_by_user.items():
            if len(user_records) < 4:
                continue
            ordered_records = sorted(user_records, key=lambda item: item.summary.start_time)
            middle = len(ordered_records) // 2
            baseline = ordered_records[:middle]
            current = ordered_records[middle:]
            if not baseline or not current:
                continue

            baseline_pass_rate = sum(
                1
                for record in baseline
                if record.summary.overall_result in {"pass", "strong_pass"}
            ) / len(baseline)
            current_pass_rate = sum(
                1
                for record in current
                if record.summary.overall_result in {"pass", "strong_pass"}
            ) / len(current)
            gain = current_pass_rate - baseline_pass_rate
            if gain <= 0:
                continue

            latest_record = current[-1]
            improving.append(
                {
                    "user_id": user_id,
                    "user_name": cls._resolve_user_name(latest_record),
                    "department": cls._resolve_department(latest_record),
                    "pass_gain": round(gain * 100, 2),
                    "baseline_pass_rate": round(baseline_pass_rate * 100, 2),
                    "current_pass_rate": round(current_pass_rate * 100, 2),
                }
            )
        improving.sort(
            key=lambda item: (-item["pass_gain"], item["user_name"]),
        )

        return {
            "not_passed": not_passed[:limit],
            "inactive_streak": inactive_streak[:limit],
            "improving": improving[:limit],
        }

    @classmethod
    def _build_department_issue_buckets(
        cls,
        records: list[ProjectionAnalyticsRecord],
    ) -> list[dict[str, Any]]:
        completed_records = cls._completed_records(records)
        blocked_records = cls._blocked_evaluable_records(records)

        by_department: dict[str, dict[str, list[Any]]] = defaultdict(
            lambda: {
                "completed": [],
                "blocked": [],
                "not_evaluable": [],
                "degraded": [],
            }
        )

        for record in completed_records:
            department = cls._resolve_department(record)
            by_department[department]["completed"].append(record)
            if record.summary.evaluable is False:
                by_department[department]["not_evaluable"].append(record.summary)
            if cls._extract_degraded_reasons(record.summary):
                by_department[department]["degraded"].append(record.summary)

        for record in blocked_records:
            department = cls._resolve_department(record)
            by_department[department]["blocked"].append(record)

        ranked_departments = sorted(
            by_department,
            key=lambda department: (
                -len(by_department[department]["blocked"]),
                -len(by_department[department]["completed"]),
                department,
            ),
        )

        payload: list[dict[str, Any]] = []
        for department in ranked_departments:
            department_records = by_department[department]
            payload.append(
                {
                    "department": department,
                    "session_count": len(department_records["completed"]),
                    "evaluable_sessions": len(
                        cls._evaluable_records(department_records["completed"])
                    ),
                    "not_evaluable_sessions": len(department_records["not_evaluable"]),
                    "issue_buckets": cls._build_blocker_family_buckets(
                        department_records["blocked"],
                        include_department_count=False,
                    ),
                    "degradation_breakdown": {
                        "not_evaluable_reasons": cls._build_reason_distribution(
                            department_records["not_evaluable"]
                        ),
                        "degraded_reasons": cls._build_degraded_reason_distribution(
                            department_records["degraded"]
                        ),
                    },
                }
            )
        return payload

    @classmethod
    def _build_operating_pack_payload(
        cls,
        records: list[ProjectionAnalyticsRecord],
        *,
        time_range: str,
        manager_lists: dict[str, Any],
    ) -> dict[str, Any]:
        completed_records = cls._completed_records(records)
        blocked_records = cls._blocked_evaluable_records(records)
        evaluable_records = cls._evaluable_records(records)
        not_evaluable_records = cls._not_evaluable_records(records)
        degraded_summaries = [
            record.summary
            for record in completed_records
            if cls._extract_degraded_reasons(record.summary)
        ]

        cohort_issue_buckets = cls._build_blocker_family_buckets(
            blocked_records,
            include_department_count=True,
        )
        repeated_blocker_families = [
            bucket for bucket in cohort_issue_buckets if int(bucket["count"]) >= 2
        ]
        not_evaluable_reasons = cls._build_reason_distribution(
            [record.summary for record in not_evaluable_records]
        )
        degraded_reasons = cls._build_degraded_reason_distribution(degraded_summaries)
        at_risk_user_ids = {
            item["user_id"] for item in manager_lists["not_passed"]
        } | {item["user_id"] for item in manager_lists["inactive_streak"]}

        time_range_days = {
            "7d": 7,
            "30d": 30,
            "90d": 90,
        }.get(time_range)
        now = datetime.now(UTC)
        start_date = _get_time_range_start(time_range)

        return {
            "score_basis": PROJECTION_SCORE_BASIS,
            "weekly_summary": {
                "window_days": time_range_days,
                "window_start": start_date.isoformat(),
                "window_end": now.isoformat(),
                "completed_sessions": len(completed_records),
                "evaluable_sessions": len(evaluable_records),
                "not_evaluable_sessions": len(not_evaluable_records),
                "degraded_sessions": len(degraded_summaries),
                "active_departments": len(
                    {cls._resolve_department(record) for record in completed_records}
                ),
                "at_risk_users": len(at_risk_user_ids),
                "improving_users": len(manager_lists["improving"]),
                "top_issue_family": cohort_issue_buckets[0] if cohort_issue_buckets else None,
                "top_blocker_family": (
                    repeated_blocker_families[0]
                    if repeated_blocker_families
                    else (cohort_issue_buckets[0] if cohort_issue_buckets else None)
                ),
                "top_not_evaluable_reason": (
                    not_evaluable_reasons[0] if not_evaluable_reasons else None
                ),
                "top_degraded_reason": degraded_reasons[0] if degraded_reasons else None,
            },
            "cohort_issue_buckets": cohort_issue_buckets,
            "department_issue_buckets": cls._build_department_issue_buckets(records),
            "repeated_blocker_families": repeated_blocker_families,
            "degradation_breakdown": {
                "not_evaluable_reasons": not_evaluable_reasons,
                "degraded_reasons": degraded_reasons,
            },
            "manager_lists": manager_lists,
        }

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

    async def get_operating_pack(
        self,
        db: AsyncSession,
        time_range: str = "7d",
        scenario_type: str | None = None,
        limit: int = 10,
        inactive_days: int = 7,
    ) -> Result[dict[str, Any]]:
        try:
            start_date = _get_time_range_start(time_range)
            records = await self._load_projection_records(
                db,
                start_date=start_date,
                scenario_type=scenario_type,
            )
            last_completed_rows = await self._load_last_completed_sessions(
                db,
                scenario_type=scenario_type,
            )
            manager_lists = self._build_manager_lists(
                records,
                last_completed_rows=last_completed_rows,
                inactive_days=inactive_days,
                limit=limit,
            )
            payload = self._build_operating_pack_payload(
                records,
                time_range=time_range,
                manager_lists=manager_lists,
            )

            logger.info(
                "admin_operating_pack_calculated",
                extra={
                    "time_range": time_range,
                    "scenario_type": history_service.normalize_scenario_type(
                        scenario_type
                    ),
                    "cohort_issue_bucket_count": len(payload["cohort_issue_buckets"]),
                    "department_issue_bucket_count": len(payload["department_issue_buckets"]),
                    "not_passed_count": len(manager_lists["not_passed"]),
                    "inactive_streak_count": len(manager_lists["inactive_streak"]),
                    "improving_count": len(manager_lists["improving"]),
                    "score_basis": PROJECTION_SCORE_BASIS,
                },
            )
            return Result.ok(payload)

        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error(
                "Failed to calculate admin operating pack",
                extra={"error": str(exc)},
                exc_info=True,
            )
            return Result.fail(fallback="[OPERATING_PACK_FAILED]")

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
