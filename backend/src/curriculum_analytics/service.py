from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    PracticeSession,
    RetrainingTask,
    SupervisorReview,
    SupervisorScoreCalibration,
    TrainingReportSnapshot,
    TrainingTask,
)
from common.error_handling.result import Result
from curriculum_analytics.schemas import (
    CurriculumAnalyticsCacheInfo,
    CurriculumAnalyticsDashboard,
    CurriculumAnalyticsSummary,
    CurriculumHeatmapCell,
    CurriculumRetrainingConversion,
    CurriculumReviewOutcomes,
    CurriculumScoreTrendPoint,
)

TimeRange = Literal["7d", "30d", "90d", "all_time"]
QUERY_LIMIT = 1000


class CurriculumAnalyticsService:
    async def get_dashboard(
        self,
        *,
        db: AsyncSession,
        time_range: TimeRange = "30d",
    ) -> Result[CurriculumAnalyticsDashboard]:
        since = _since_for_range(time_range)
        try:
            sessions = await _fetch_sessions(db, since)
            session_ids = [str(session.session_id) for session in sessions]
            tasks = await _fetch_training_tasks(db, since)
            snapshots = await _fetch_report_snapshots(db, session_ids)
            reviews, calibrated_review_ids = await _fetch_reviews(db, session_ids)
            retraining_tasks = await _fetch_retraining_tasks(db, session_ids)
        except RuntimeError as exc:
            return Result.fail(str(exc))

        return Result.ok(
            CurriculumAnalyticsDashboard(
                summary=_build_summary(tasks, sessions, snapshots),
                heatmap=_build_heatmap(sessions, snapshots),
                score_trend=_build_score_trend(sessions, snapshots),
                review_outcomes=_build_review_outcomes(reviews, calibrated_review_ids),
                retraining_conversion=_build_retraining_conversion(retraining_tasks),
                cache=CurriculumAnalyticsCacheInfo(
                    enabled=False,
                    hit=False,
                    ttl_seconds=None,
                ),
            )
        )


async def _fetch_sessions(
    db: AsyncSession,
    since: datetime | None,
) -> list[PracticeSession]:
    statement: Select[tuple[PracticeSession]] = select(PracticeSession).where(
        PracticeSession.practice_template_id.is_not(None)
    )
    if since is not None:
        statement = statement.where(PracticeSession.start_time >= since)
    statement = statement.order_by(PracticeSession.start_time.desc()).limit(QUERY_LIMIT)
    result = await db.execute(statement)
    return list(reversed(result.scalars().all()))


async def _fetch_training_tasks(
    db: AsyncSession,
    since: datetime | None,
) -> list[TrainingTask]:
    statement: Select[tuple[TrainingTask]] = select(TrainingTask).where(
        TrainingTask.practice_template_id.is_not(None)
    )
    if since is not None:
        statement = statement.where(TrainingTask.created_at >= since)
    result = await db.execute(statement.order_by(TrainingTask.created_at.desc()).limit(QUERY_LIMIT))
    return list(result.scalars().all())


async def _fetch_report_snapshots(
    db: AsyncSession,
    session_ids: list[str],
) -> list[TrainingReportSnapshot]:
    if not session_ids:
        return []
    result = await db.execute(
        select(TrainingReportSnapshot)
        .where(TrainingReportSnapshot.session_id.in_(session_ids))
        .order_by(TrainingReportSnapshot.generated_at.desc())
        .limit(QUERY_LIMIT)
    )
    return list(result.scalars().all())


async def _fetch_reviews(
    db: AsyncSession,
    session_ids: list[str],
) -> tuple[list[SupervisorReview], set[str]]:
    if not session_ids:
        return [], set()
    result = await db.execute(
        select(SupervisorReview, SupervisorScoreCalibration.review_id)
        .outerjoin(
            SupervisorScoreCalibration,
            SupervisorScoreCalibration.review_id == SupervisorReview.review_id,
        )
        .where(SupervisorReview.session_id.in_(session_ids))
        .order_by(SupervisorReview.created_at.desc())
        .limit(QUERY_LIMIT)
    )
    reviews_by_id: dict[str, SupervisorReview] = {}
    calibrated_review_ids: set[str] = set()
    for review, calibration_review_id in result.all():
        review_id = str(review.review_id)
        reviews_by_id[review_id] = review
        if calibration_review_id is not None:
            calibrated_review_ids.add(str(calibration_review_id))
    return list(reviews_by_id.values()), calibrated_review_ids


async def _fetch_retraining_tasks(
    db: AsyncSession,
    session_ids: list[str],
) -> list[RetrainingTask]:
    if not session_ids:
        return []
    result = await db.execute(
        select(RetrainingTask)
        .where(RetrainingTask.source_session_id.in_(session_ids))
        .order_by(RetrainingTask.created_at.desc())
        .limit(QUERY_LIMIT)
    )
    return list(result.scalars().all())


def _build_summary(
    tasks: list[TrainingTask],
    sessions: list[PracticeSession],
    snapshots: list[TrainingReportSnapshot],
) -> CurriculumAnalyticsSummary:
    assigned_count = len(tasks)
    completed_count = len([session for session in sessions if session.status == "completed"])
    completion_rate = round(completed_count / assigned_count, 4) if assigned_count else 0.0
    top_weak_dimension = _top_weak_dimension(snapshots)
    trend_scores = [_session_average_score(session) for session in sessions]
    valid_scores = [score for score in trend_scores if score is not None]
    average_score_delta = 0.0
    if len(valid_scores) >= 2:
        average_score_delta = round(valid_scores[-1] - valid_scores[0], 2)
    return CurriculumAnalyticsSummary(
        assigned_count=assigned_count,
        completed_count=completed_count,
        completion_rate=completion_rate,
        top_weak_dimension=top_weak_dimension,
        average_score_delta=average_score_delta,
    )


def _build_heatmap(
    sessions: list[PracticeSession],
    snapshots: list[TrainingReportSnapshot],
) -> list[CurriculumHeatmapCell]:
    sessions_by_id = {str(session.session_id): session for session in sessions}
    grouped_scores: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for snapshot in snapshots:
        session = sessions_by_id.get(str(snapshot.session_id))
        if session is None or not session.practice_template_id:
            continue
        template_name = _template_name_from_session(session)
        for dimension, score in _dimension_scores(snapshot):
            grouped_scores[(str(session.practice_template_id), template_name, dimension)].append(score)

    cells = [
        CurriculumHeatmapCell(
            template_id=template_id,
            template_name=template_name,
            dimension=dimension,
            average_score=round(sum(scores) / len(scores), 2),
            sample_count=len(scores),
        )
        for (template_id, template_name, dimension), scores in grouped_scores.items()
    ]
    return sorted(
        cells,
        key=lambda cell: (cell.average_score, cell.template_name, cell.dimension),
    )


def _build_score_trend(
    sessions: list[PracticeSession],
    snapshots: list[TrainingReportSnapshot],
) -> list[CurriculumScoreTrendPoint]:
    snapshot_ids = {str(snapshot.session_id) for snapshot in snapshots}
    grouped_scores: dict[str, list[float]] = defaultdict(list)
    for session in sessions:
        if str(session.session_id) not in snapshot_ids or session.start_time is None:
            continue
        score = _session_average_score(session)
        if score is None:
            continue
        grouped_scores[session.start_time.date().isoformat()].append(score)
    return [
        CurriculumScoreTrendPoint(
            date=date,
            average_score=round(sum(scores) / len(scores), 2),
            sample_count=len(scores),
        )
        for date, scores in sorted(grouped_scores.items())
    ]


def _build_review_outcomes(
    reviews: list[SupervisorReview],
    calibrated_review_ids: set[str],
) -> CurriculumReviewOutcomes:
    counts = Counter(str(review.decision) for review in reviews)
    return CurriculumReviewOutcomes(
        approved=counts["approved"],
        rejected=counts["rejected"],
        calibrated=len(calibrated_review_ids),
        retraining_required=counts["needs_retraining"],
    )


def _build_retraining_conversion(
    tasks: list[RetrainingTask],
) -> CurriculumRetrainingConversion:
    counts = Counter(str(task.status) for task in tasks)
    return CurriculumRetrainingConversion(
        created=len(tasks),
        started=counts["in_progress"] + counts["completed"],
        completed=counts["completed"],
    )


def _top_weak_dimension(snapshots: list[TrainingReportSnapshot]) -> str | None:
    lowest_scores: dict[str, list[float]] = defaultdict(list)
    for snapshot in snapshots:
        for dimension, score in _dimension_scores(snapshot):
            lowest_scores[dimension].append(score)
    if not lowest_scores:
        return None
    return min(
        lowest_scores.items(),
        key=lambda item: (sum(item[1]) / len(item[1]), item[0]),
    )[0]


def _dimension_scores(snapshot: TrainingReportSnapshot) -> list[tuple[str, float]]:
    payload = snapshot.report_payload if isinstance(snapshot.report_payload, dict) else {}
    raw_scores = payload.get("dimension_scores")
    parsed = _parse_dimension_score_items(raw_scores)
    if parsed:
        return parsed
    lineage = payload.get("lineage")
    if not isinstance(lineage, dict):
        return []
    stage_snapshots = lineage.get("stage_snapshots")
    if not isinstance(stage_snapshots, dict):
        return []
    stage_scores: list[tuple[str, float]] = []
    for stage_snapshot in stage_snapshots.values():
        if not isinstance(stage_snapshot, dict):
            continue
        stage_scores.extend(_parse_dimension_score_items(stage_snapshot.get("dimension_scores")))
    return stage_scores


def _parse_dimension_score_items(raw_scores: object) -> list[tuple[str, float]]:
    if not isinstance(raw_scores, list):
        return []
    parsed: list[tuple[str, float]] = []
    for item in raw_scores:
        if not isinstance(item, dict):
            continue
        raw_name = item.get("name") or item.get("dimension")
        raw_score = item.get("score")
        if not isinstance(raw_name, str) or not isinstance(raw_score, int | float):
            continue
        parsed.append((raw_name, float(raw_score)))
    return parsed


def _template_name_from_session(session: PracticeSession) -> str:
    snapshot = session.curriculum_snapshot
    if isinstance(snapshot, dict):
        template = snapshot.get("practice_template")
        if isinstance(template, dict) and isinstance(template.get("name"), str):
            return template["name"]
    return str(session.practice_template_id)


def _session_average_score(session: PracticeSession) -> float | None:
    scores = [session.logic_score, session.accuracy_score, session.completeness_score]
    valid_scores = [float(score) for score in scores if isinstance(score, int | float)]
    if not valid_scores:
        return None
    return round(sum(valid_scores) / len(valid_scores), 2)


def _since_for_range(time_range: TimeRange) -> datetime | None:
    if time_range == "all_time":
        return None
    days_by_range = {"7d": 7, "30d": 30, "90d": 90}
    return datetime.now(UTC) - timedelta(days=days_by_range[time_range])


curriculum_analytics_service = CurriculumAnalyticsService()
