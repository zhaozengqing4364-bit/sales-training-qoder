"""
Practice history query service backed by the shared session evidence projection.

History/statistics/trends must read the same completed-session evidence baseline as
report/replay instead of mixing ComprehensiveReport caches and ad-hoc score formulas.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.conversation.models import ConversationMessage
from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import PracticeSession, Scenario, SessionStatus
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HistorySessionSummary:
    """Projection-backed summary for history/statistics/trends consumers."""

    session_id: str
    scenario_id: str
    scenario_name: str
    scenario_type: str
    persona_name: str | None
    agent_name: str | None
    title: str
    start_time: datetime
    end_time: datetime | None
    duration_seconds: int
    overall_score: float | None
    report_status: str
    report_generated_at: datetime | None
    status: str
    logic_score: float | None
    accuracy_score: float | None
    completeness_score: float | None
    evaluable: bool | None
    not_evaluable_reason: str | None
    evidence_completeness: dict[str, Any] | None
    effectiveness_snapshot: dict[str, Any] | None
    feedback_summary: str | None
    stage_summary: list[dict[str, Any]]
    main_issue: dict[str, Any] | None
    next_goal: dict[str, Any] | None


class HistoryService:
    """Queries practice history for users on top of the shared evidence projection."""

    @staticmethod
    def normalize_scenario_type(scenario_type: str | None) -> str | None:
        if not scenario_type:
            return None
        if scenario_type == "sales_bot":
            return "sales"
        return scenario_type

    @staticmethod
    def _duration_seconds_between(
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> int | None:
        if start_time is None or end_time is None:
            return None
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)
        else:
            start_time = start_time.astimezone(UTC)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=UTC)
        else:
            end_time = end_time.astimezone(UTC)
        return max(0, int((end_time - start_time).total_seconds()))

    @classmethod
    def _calculate_duration_seconds(cls, session: PracticeSession) -> int:
        duration_seconds = getattr(session, "total_duration_seconds", None)
        if isinstance(duration_seconds, int):
            return max(0, duration_seconds)
        derived = cls._duration_seconds_between(
            getattr(session, "start_time", None),
            getattr(session, "end_time", None)
        )
        return derived or 0

    @staticmethod
    def _coerce_optional_score(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_feedback_summary(effectiveness_snapshot: dict[str, Any] | None) -> str | None:
        if not isinstance(effectiveness_snapshot, dict):
            return None

        main_issue = effectiveness_snapshot.get("main_issue")
        if isinstance(main_issue, dict) and main_issue.get("issue_text"):
            return str(main_issue["issue_text"])

        next_goal = effectiveness_snapshot.get("next_goal")
        if isinstance(next_goal, dict) and next_goal.get("goal_text"):
            return str(next_goal["goal_text"])

        return None

    @classmethod
    def build_history_entries(
        cls,
        sessions: list[PracticeSession],
        *,
        messages_by_session: dict[str, list[ConversationMessage]],
    ) -> list[HistorySessionSummary]:
        summaries: list[HistorySessionSummary] = []

        for session in sessions:
            session_id = str(getattr(session, "session_id"))
            scenario = getattr(session, "scenario", None)
            agent = getattr(session, "agent", None)
            persona = getattr(session, "persona", None)
            projection = None

            if getattr(session, "status", None) == SessionStatus.COMPLETED.value:
                projection = SessionEvidenceService.build_projection(
                    session,
                    list(messages_by_session.get(session_id, [])),
                )

            effectiveness_snapshot = (
                projection.effectiveness_snapshot if projection else None
            )

            summaries.append(
                HistorySessionSummary(
                    session_id=session_id,
                    scenario_id=str(getattr(session, "scenario_id", "")),
                    scenario_name=getattr(scenario, "name", None) or "未知场景",
                    scenario_type=getattr(scenario, "scenario_type", None) or "unknown",
                    persona_name=getattr(persona, "name", None),
                    agent_name=getattr(agent, "name", None),
                    title=(
                        getattr(agent, "name", None)
                        or getattr(scenario, "name", None)
                        or "练习记录"
                    ),
                    start_time=getattr(session, "start_time"),
                    end_time=getattr(session, "end_time", None),
                    duration_seconds=cls._calculate_duration_seconds(session),
                    overall_score=(projection.overall_score if projection else None),
                    report_status=getattr(session, "report_status", None) or "pending",
                    report_generated_at=getattr(session, "report_generated_at", None),
                    status=str(getattr(session, "status", "unknown")),
                    logic_score=(
                        projection.logic_score
                        if projection
                        else cls._coerce_optional_score(getattr(session, "logic_score", None))
                    ),
                    accuracy_score=(
                        projection.accuracy_score
                        if projection
                        else cls._coerce_optional_score(getattr(session, "accuracy_score", None))
                    ),
                    completeness_score=(
                        projection.completeness_score
                        if projection
                        else cls._coerce_optional_score(
                            getattr(session, "completeness_score", None)
                        )
                    ),
                    evaluable=(projection.evaluable if projection else None),
                    not_evaluable_reason=(
                        projection.not_evaluable_reason if projection else None
                    ),
                    evidence_completeness=(
                        projection.evidence_completeness if projection else None
                    ),
                    effectiveness_snapshot=effectiveness_snapshot,
                    feedback_summary=cls._build_feedback_summary(effectiveness_snapshot),
                    stage_summary=(projection.stage_summary if projection else []),
                    main_issue=(projection.main_issue if projection else None),
                    next_goal=(projection.next_goal if projection else None),
                )
            )

        return summaries

    @staticmethod
    def build_statistics_payload(
        summaries: list[HistorySessionSummary],
    ) -> dict[str, int | float]:
        completed_sessions = [
            summary
            for summary in summaries
            if summary.status == SessionStatus.COMPLETED.value
        ]
        if not completed_sessions:
            return {
                "total_sessions": 0,
                "evaluable_sessions": 0,
                "not_evaluable_sessions": 0,
                "average_score": 0,
                "best_score": 0,
                "total_practice_time_seconds": 0,
                "total_practice_time_minutes": 0,
            }

        evaluable_sessions = [
            summary
            for summary in completed_sessions
            if summary.evaluable is True and summary.overall_score is not None
        ]
        not_evaluable_sessions = [
            summary for summary in completed_sessions if summary.evaluable is False
        ]

        average_score = (
            round(
                sum(float(summary.overall_score or 0.0) for summary in evaluable_sessions)
                / len(evaluable_sessions),
                2,
            )
            if evaluable_sessions
            else 0
        )
        best_score = (
            round(
                max(float(summary.overall_score or 0.0) for summary in evaluable_sessions),
                2,
            )
            if evaluable_sessions
            else 0
        )
        total_practice_time_seconds = sum(
            int(summary.duration_seconds) for summary in completed_sessions
        )

        return {
            "total_sessions": len(completed_sessions),
            "evaluable_sessions": len(evaluable_sessions),
            "not_evaluable_sessions": len(not_evaluable_sessions),
            "average_score": average_score,
            "best_score": best_score,
            "total_practice_time_seconds": total_practice_time_seconds,
            "total_practice_time_minutes": round(total_practice_time_seconds / 60, 1),
        }

    @staticmethod
    def build_trend_points(
        summaries: list[HistorySessionSummary],
    ) -> list[dict[str, Any]]:
        evaluable_sessions = sorted(
            (
                summary
                for summary in summaries
                if summary.status == SessionStatus.COMPLETED.value
                and summary.evaluable is True
                and summary.overall_score is not None
            ),
            key=lambda summary: summary.start_time,
        )

        return [
            {
                "session_id": summary.session_id,
                "date": summary.start_time.isoformat(),
                "logic_score": summary.logic_score or 0,
                "accuracy_score": summary.accuracy_score or 0,
                "completeness_score": summary.completeness_score or 0,
                "overall_score": float(summary.overall_score),
                "scenario_type": summary.scenario_type,
                "evaluable": True,
                "not_evaluable_reason": None,
                "evidence_completeness": summary.evidence_completeness,
                "stage_summary": summary.stage_summary,
                "main_issue": summary.main_issue,
                "next_goal": summary.next_goal,
            }
            for summary in evaluable_sessions
        ]

    @staticmethod
    def _summarize_projection_state(
        summaries: list[HistorySessionSummary],
    ) -> dict[str, Any]:
        incomplete_projection_session_ids = [
            summary.session_id
            for summary in summaries
            if isinstance(summary.evidence_completeness, dict)
            and not bool(summary.evidence_completeness.get("complete", False))
        ][:25]
        skipped_not_completed_session_ids = [
            summary.session_id
            for summary in summaries
            if summary.status != SessionStatus.COMPLETED.value
        ][:25]
        not_evaluable_session_ids = [
            summary.session_id for summary in summaries if summary.evaluable is False
        ][:25]

        return {
            "session_count": len(summaries),
            "completed_session_count": sum(
                1
                for summary in summaries
                if summary.status == SessionStatus.COMPLETED.value
            ),
            "projected_session_count": sum(
                1 for summary in summaries if summary.evidence_completeness is not None
            ),
            "evaluable_session_count": sum(
                1 for summary in summaries if summary.evaluable is True
            ),
            "not_evaluable_session_count": sum(
                1 for summary in summaries if summary.evaluable is False
            ),
            "incomplete_projection_session_ids": incomplete_projection_session_ids,
            "skipped_not_completed_session_ids": skipped_not_completed_session_ids,
            "not_evaluable_session_ids": not_evaluable_session_ids,
        }

    def _log_history_query(
        self,
        *,
        query_name: str,
        user_id: str,
        summaries: list[HistorySessionSummary],
        filters: dict[str, Any],
    ) -> None:
        summary = self._summarize_projection_state(summaries)
        logger.info(
            "practice_history_projection_query",
            query_name=query_name,
            user_id=user_id,
            evidence_source="session_evidence_projection",
            filters=filters,
            **summary,
        )

    async def _query_sessions(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID | str,
        scenario_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        completed_only: bool = False,
        cutoff_time: datetime | None = None,
        order_desc: bool = True,
        include_total: bool = False,
    ) -> tuple[list[PracticeSession], int | None]:
        normalized_scenario_type = self.normalize_scenario_type(scenario_type)

        query = (
            select(PracticeSession)
            .options(
                selectinload(PracticeSession.scenario),
                selectinload(PracticeSession.agent),
                selectinload(PracticeSession.persona),
                selectinload(PracticeSession.presentation),
            )
            .where(PracticeSession.user_id == str(user_id))
        )

        if normalized_scenario_type:
            query = query.where(
                PracticeSession.scenario.has(scenario_type=normalized_scenario_type)
            )

        if completed_only:
            query = query.where(PracticeSession.status == SessionStatus.COMPLETED.value)

        if cutoff_time is not None:
            query = query.where(PracticeSession.start_time >= cutoff_time)

        total: int | None = None
        if include_total:
            count_query = select(func.count()).select_from(query.order_by(None).subquery())
            total = int((await db.execute(count_query)).scalar() or 0)

        order_clause = desc(PracticeSession.start_time) if order_desc else PracticeSession.start_time
        query = query.order_by(order_clause)
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def _load_messages_by_session(
        self,
        db: AsyncSession,
        *,
        session_ids: list[str],
    ) -> dict[str, list[ConversationMessage]]:
        if not session_ids:
            return {}

        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id.in_(session_ids))
            .order_by(
                ConversationMessage.session_id,
                ConversationMessage.turn_number,
                ConversationMessage.timestamp,
            )
        )
        grouped_messages: dict[str, list[ConversationMessage]] = defaultdict(list)
        for message in result.scalars().all():
            grouped_messages[str(message.session_id)].append(message)
        return dict(grouped_messages)

    async def _build_history_summaries(
        self,
        db: AsyncSession,
        *,
        sessions: list[PracticeSession],
    ) -> list[HistorySessionSummary]:
        completed_session_ids = [
            str(session.session_id)
            for session in sessions
            if session.status == SessionStatus.COMPLETED.value
        ]
        messages_by_session = await self._load_messages_by_session(
            db,
            session_ids=completed_session_ids,
        )
        return self.build_history_entries(
            sessions,
            messages_by_session=messages_by_session,
        )

    async def get_user_history(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        scenario_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Result[list[HistorySessionSummary]]:
        try:
            sessions, _ = await self._query_sessions(
                db,
                user_id=user_id,
                scenario_type=scenario_type,
                limit=limit,
                offset=offset,
                order_desc=True,
                include_total=False,
            )
            summaries = await self._build_history_summaries(db, sessions=sessions)
            self._log_history_query(
                query_name="analytics_history",
                user_id=str(user_id),
                summaries=summaries,
                filters={
                    "scenario_type": self.normalize_scenario_type(scenario_type),
                    "limit": limit,
                    "offset": offset,
                },
            )
            return Result.ok(summaries)

        except (SQLAlchemyError, ValueError) as exc:
            logger.error(
                "practice_history_projection_failed",
                query_name="analytics_history",
                user_id=str(user_id),
                error=str(exc),
            )
            return Result.fail(fallback="[HISTORY_FAILED]")

    async def get_session_detail(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Result[PracticeSession]:
        try:
            query = (
                select(PracticeSession)
                .options(
                    selectinload(PracticeSession.scenario),
                    selectinload(PracticeSession.presentation),
                )
                .where(PracticeSession.session_id == str(session_id))
                .where(PracticeSession.user_id == str(user_id))
            )

            result = await db.execute(query)
            session = result.scalar_one_or_none()
            if not session:
                return Result.fail(fallback="[SESSION_NOT_FOUND]")

            logger.info(
                "practice_history_session_detail_loaded",
                user_id=str(user_id),
                session_id=str(session_id),
            )
            return Result.ok(session)

        except (SQLAlchemyError, ValueError) as exc:
            logger.error(
                "practice_history_session_detail_failed",
                user_id=str(user_id),
                session_id=str(session_id),
                error=str(exc),
            )
            return Result.fail(fallback="[DETAIL_FAILED]")

    async def get_recent_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        days: int = 7,
        limit: int = 10,
    ) -> Result[list[PracticeSession]]:
        try:
            cutoff_time = datetime.now(UTC) - timedelta(days=days)
            sessions, _ = await self._query_sessions(
                db,
                user_id=user_id,
                cutoff_time=cutoff_time,
                limit=limit,
                order_desc=True,
                include_total=False,
            )
            logger.info(
                "practice_history_recent_sessions_loaded",
                user_id=str(user_id),
                days=days,
                count=len(sessions),
            )
            return Result.ok(sessions)

        except (SQLAlchemyError, ValueError) as exc:
            logger.error(
                "practice_history_recent_sessions_failed",
                user_id=str(user_id),
                error=str(exc),
            )
            return Result.fail(fallback="[RECENT_FAILED]")

    async def get_score_trends(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> Result[list[dict[str, Any]]]:
        try:
            cutoff_time = datetime.now(UTC) - timedelta(days=days)
            sessions, _ = await self._query_sessions(
                db,
                user_id=user_id,
                completed_only=True,
                cutoff_time=cutoff_time,
                order_desc=False,
                include_total=False,
            )
            summaries = await self._build_history_summaries(db, sessions=sessions)
            trends = self.build_trend_points(summaries)
            self._log_history_query(
                query_name="history_trends",
                user_id=str(user_id),
                summaries=summaries,
                filters={"days": days},
            )
            return Result.ok(trends)

        except (SQLAlchemyError, ValueError) as exc:
            logger.error(
                "practice_history_projection_failed",
                query_name="history_trends",
                user_id=str(user_id),
                error=str(exc),
            )
            return Result.fail(fallback="[TRENDS_FAILED]")

    async def get_statistics(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Result[dict[str, Any]]:
        try:
            sessions, _ = await self._query_sessions(
                db,
                user_id=user_id,
                completed_only=True,
                order_desc=True,
                include_total=False,
            )
            summaries = await self._build_history_summaries(db, sessions=sessions)
            stats = self.build_statistics_payload(summaries)
            self._log_history_query(
                query_name="history_statistics",
                user_id=str(user_id),
                summaries=summaries,
                filters={},
            )
            return Result.ok(stats)

        except (SQLAlchemyError, ValueError) as exc:
            logger.error(
                "practice_history_projection_failed",
                query_name="history_statistics",
                user_id=str(user_id),
                error=str(exc),
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
        try:
            sessions, total = await self._query_sessions(
                db,
                user_id=user_id,
                scenario_type=scenario_type,
                offset=(page - 1) * page_size,
                limit=page_size,
                order_desc=True,
                include_total=True,
            )
            summaries = await self._build_history_summaries(db, sessions=sessions)
            self._log_history_query(
                query_name="user_history",
                user_id=str(user_id),
                summaries=summaries,
                filters={
                    "scenario_type": self.normalize_scenario_type(scenario_type),
                    "page": page,
                    "page_size": page_size,
                },
            )
            total_value = int(total or 0)
            return Result.ok(
                {
                    "sessions": summaries,
                    "total": total_value,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_value + page_size - 1) // page_size,
                }
            )

        except (SQLAlchemyError, ValueError) as exc:
            logger.error(
                "practice_history_projection_failed",
                query_name="user_history",
                user_id=str(user_id),
                error=str(exc),
            )
            return Result.fail(fallback="[HISTORY_FAILED]")


history_service = HistoryService()
