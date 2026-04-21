"""Report-local score trend read model.

G-02 trend comparisons are intentionally projection/evidence based: they only
count completed sessions that are explicitly marked evaluable and have all score
fields present.  Missing history returns an explanation instead of fake zeroes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.analytics.history_service import PROJECTION_SCORE_BASIS
from common.db.models import PracticeSession, SessionStatus, User
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def _is_admin_user(user: User) -> bool:
    return str(getattr(user, "role", "user")).lower() == "admin"


def _can_read_session(session: PracticeSession, user: User) -> bool:
    return _is_admin_user(user) or str(session.user_id) == str(user.user_id)


def _coerce_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ReportTrendService:
    """Build recent same-scenario trend points for a report page."""

    max_scan_sessions = 100

    @staticmethod
    def _has_complete_scores(session: PracticeSession) -> bool:
        return all(
            getattr(session, field) is not None
            for field in ("logic_score", "accuracy_score", "completeness_score")
        )

    @staticmethod
    def _is_evaluable(session: PracticeSession) -> bool:
        snapshot = session.effectiveness_snapshot
        return isinstance(snapshot, dict) and snapshot.get("evaluable") is True

    @staticmethod
    def _overall_score(session: PracticeSession) -> float:
        return round(
            (
                float(session.logic_score or 0.0)
                + float(session.accuracy_score or 0.0)
                + float(session.completeness_score or 0.0)
            )
            / 3.0,
            2,
        )

    @classmethod
    def _point(cls, session: PracticeSession, current_session_id: str) -> dict[str, Any]:
        scenario_type = getattr(getattr(session, "scenario", None), "scenario_type", None)
        return {
            "session_id": str(session.session_id),
            "date": _coerce_datetime(session.start_time).isoformat(),
            "scenario_type": str(scenario_type or "sales"),
            "logic_score": float(session.logic_score or 0.0),
            "accuracy_score": float(session.accuracy_score or 0.0),
            "completeness_score": float(session.completeness_score or 0.0),
            "overall_score": cls._overall_score(session),
            "is_current": str(session.session_id) == current_session_id,
        }

    @staticmethod
    def _delta(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, float]:
        fields = (
            "logic_score",
            "accuracy_score",
            "completeness_score",
            "overall_score",
        )
        return {
            field: round(float(current[field]) - float(previous[field]), 2)
            for field in fields
        }

    async def get_session_report_trends(
        self,
        *,
        db: AsyncSession,
        requester: User,
        session_id: str,
        limit: int = 5,
    ) -> Result[dict[str, Any]]:
        """Return same-scenario trend points for the target report session."""

        normalized_limit = min(max(int(limit or 5), 1), 12)
        try:
            target_result = await db.execute(
                select(PracticeSession)
                .options(selectinload(PracticeSession.scenario))
                .where(PracticeSession.session_id == session_id)
            )
            target = target_result.scalar_one_or_none()
            if target is None:
                return Result.fail("[SESSION_NOT_FOUND] Session not found")
            if not _can_read_session(target, requester):
                return Result.fail("[ACCESS_DENIED] Access denied")

            scenario_type = str(
                getattr(getattr(target, "scenario", None), "scenario_type", None)
                or "sales"
            )
            if (
                target.status != SessionStatus.COMPLETED.value
                or not self._is_evaluable(target)
                or not self._has_complete_scores(target)
            ):
                return Result.ok(
                    {
                        "session_id": str(target.session_id),
                        "scenario_type": scenario_type,
                        "score_basis": PROJECTION_SCORE_BASIS,
                        "points": [],
                        "delta_vs_previous": None,
                        "explanation": "当前报告缺少完成且可评估的分数证据，暂不展示趋势。",
                    }
                )

            target_time = _coerce_datetime(target.start_time)
            candidate_result = await db.execute(
                select(PracticeSession)
                .options(selectinload(PracticeSession.scenario))
                .where(PracticeSession.user_id == target.user_id)
                .where(PracticeSession.status == SessionStatus.COMPLETED.value)
                .order_by(PracticeSession.start_time.desc())
                .limit(self.max_scan_sessions)
            )
            candidates = list(candidate_result.scalars().all())
            qualified = [
                session
                for session in candidates
                if str(
                    getattr(getattr(session, "scenario", None), "scenario_type", None)
                    or "sales"
                )
                == scenario_type
                and _coerce_datetime(session.start_time) <= target_time
                and self._is_evaluable(session)
                and self._has_complete_scores(session)
            ]
            qualified = sorted(
                qualified,
                key=lambda item: _coerce_datetime(item.start_time),
            )[-normalized_limit:]
            points = [self._point(session, str(target.session_id)) for session in qualified]

            current_index = next(
                (
                    index
                    for index, point in enumerate(points)
                    if point["session_id"] == str(target.session_id)
                ),
                None,
            )
            delta = (
                self._delta(points[current_index], points[current_index - 1])
                if current_index is not None and current_index > 0
                else None
            )
            explanation = None
            if delta is None:
                explanation = "至少需要两次同场景可评估训练后才会显示趋势对比。"

            return Result.ok(
                {
                    "session_id": str(target.session_id),
                    "scenario_type": scenario_type,
                    "score_basis": PROJECTION_SCORE_BASIS,
                    "points": points,
                    "delta_vs_previous": delta,
                    "explanation": explanation,
                }
            )
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error(
                "report_trends_build_failed",
                session_id=session_id,
                error=str(exc),
            )
            return Result.fail(f"[REPORT_TRENDS_FAILED] {exc}")
