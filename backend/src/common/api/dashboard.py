"""
Dashboard API - User dashboard statistics and recommendations

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- V. Cost control - Efficient queries

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""
import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.analytics.history_service import PROJECTION_SCORE_BASIS, history_service
from common.auth.service import get_current_user
from common.db.models import PracticeSession, User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from common.services.practice_session_service import PracticeRetryEntryAssembler

logger = get_logger(__name__)

router = APIRouter()


# ========== Schemas ==========

class WeeklyActivity(BaseModel):
    """Weekly activity statistics"""
    total_duration_minutes: int = 0
    session_count: int = 0
    trend_percentage: float = 0.0
    trend_direction: Literal["up", "down", "flat"] = "flat"


class LastSession(BaseModel):
    """Last session score info"""
    score: float = 0.0
    percentile: int = 50
    trend: Literal["up", "down", "stable"] = "stable"


class DashboardStats(BaseModel):
    """Dashboard statistics response"""
    weekly_activity: WeeklyActivity
    last_session: LastSession
    effectiveness: dict[str, float] | None = None
    score_basis: str = PROJECTION_SCORE_BASIS
    evaluable_sessions: int = 0
    not_evaluable_sessions: int = 0


class Recommendation(BaseModel):
    """Training recommendation"""
    title: str
    reason: str
    action_label: str
    target_path: str
    score_basis: str | None = None


def _encode_focus_intent(focus_intent: dict | None) -> str | None:
    if not focus_intent:
        return None
    return quote(json.dumps(focus_intent, ensure_ascii=False, separators=(",", ":")))


def _build_retry_target_path(retry_entry: dict) -> str:
    scenario_type = retry_entry.get("scenario_type")
    agent_id = retry_entry.get("agent_id")
    persona_id = retry_entry.get("persona_id")
    focus_intent = retry_entry.get("focus_intent")

    if scenario_type == "sales":
        if agent_id and persona_id and focus_intent:
            return (
                f"/agents/{quote(str(agent_id))}"
                f"?persona_id={quote(str(persona_id))}"
                f"&focus_intent={_encode_focus_intent(focus_intent)}"
            )
        return "/training/sales"

    if scenario_type == "presentation":
        return "/training/presentation"

    return "/training"


def _build_next_goal_recommendation(session: PracticeSession) -> Recommendation | None:
    scenario = getattr(session, "scenario", None)
    scenario_type = getattr(scenario, "scenario_type", None) or "sales"
    snapshot = session.effectiveness_snapshot if isinstance(session.effectiveness_snapshot, dict) else {}
    main_issue = snapshot.get("main_issue") if isinstance(snapshot.get("main_issue"), dict) else None
    next_goal = snapshot.get("next_goal") if isinstance(snapshot.get("next_goal"), dict) else None

    if not main_issue and not next_goal:
        return None

    retry_entry = PracticeRetryEntryAssembler.build_retry_entry(
        session=session,
        scenario_type=str(scenario_type),
        main_issue=main_issue,
        next_goal=next_goal,
    )
    focus_intent = retry_entry.get("focus_intent")
    if not isinstance(focus_intent, dict):
        return None

    goal_text = (
        str(next_goal.get("goal_text"))
        if isinstance(next_goal, dict) and next_goal.get("goal_text")
        else "沿着上次报告的主问题再练一轮。"
    )
    issue_text = (
        str(main_issue.get("issue_text"))
        if isinstance(main_issue, dict) and main_issue.get("issue_text")
        else "上次报告已经给出可复练重点。"
    )
    target_path = _build_retry_target_path(retry_entry)
    if target_path == "/training/sales" and scenario_type == "sales":
        reason = f"{goal_text} 当前报告缺少完整智能体或客户画像配置，请先在销售训练页重新选择。"
    else:
        reason = f"{goal_text} 上次主问题：{issue_text}"

    return Recommendation(
        title="按上次主问题再练一轮",
        reason=reason,
        action_label="按目标再练一轮",
        target_path=target_path,
        score_basis=PROJECTION_SCORE_BASIS,
    )


# ========== Helper Functions ==========

def success_response(data, trace_id: str = None):
    """Create unified success response"""
    return {
        "success": True,
        "data": data if isinstance(data, dict) else data.model_dump() if hasattr(data, 'model_dump') else data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, message: str = None, trace_id: str = None):
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id()
    }


def calculate_trend_direction(current: float, previous: float) -> Literal["up", "down", "flat"]:
    """Calculate trend direction based on current and previous values"""
    if previous == 0:
        return "up" if current > 0 else "flat"

    change_pct = ((current - previous) / previous) * 100

    if change_pct > 5:
        return "up"
    elif change_pct < -5:
        return "down"
    else:
        return "flat"


def calculate_trend_percentage(current: float, previous: float) -> float:
    """Calculate percentage change between current and previous values"""
    if previous == 0:
        return 100.0 if current > 0 else 0.0

    return round(((current - previous) / previous) * 100, 1)


# ========== Endpoints ==========

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get dashboard statistics for current user

    Returns:
    - weekly_activity: This week's practice statistics with trend comparison
    - last_session: Last session score with percentile ranking

    Requirements: 2.1, 2.2, 2.3
    """
    try:
        user_id = str(current_user.user_id)
        now = datetime.now(UTC)

        # Calculate week boundaries
        # This week: from Monday 00:00 to now
        days_since_monday = now.weekday()
        this_week_start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Last week: previous Monday to previous Sunday
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start

        # ========== This Week Stats ==========
        this_week_stmt = select(
            func.count(PracticeSession.session_id).label("session_count"),
            func.coalesce(func.sum(PracticeSession.total_duration_seconds), 0).label("total_seconds")
        ).where(
            PracticeSession.user_id == user_id,
            PracticeSession.start_time >= this_week_start
        )

        this_week_result = await db.execute(this_week_stmt)
        this_week_row = this_week_result.one()

        this_week_sessions = this_week_row.session_count or 0
        this_week_seconds = this_week_row.total_seconds or 0
        this_week_minutes = this_week_seconds // 60

        # ========== Last Week Stats ==========
        last_week_stmt = select(
            func.count(PracticeSession.session_id).label("session_count"),
            func.coalesce(func.sum(PracticeSession.total_duration_seconds), 0).label("total_seconds")
        ).where(
            PracticeSession.user_id == user_id,
            PracticeSession.start_time >= last_week_start,
            PracticeSession.start_time < last_week_end
        )

        last_week_result = await db.execute(last_week_stmt)
        last_week_row = last_week_result.one()

        last_week_sessions = last_week_row.session_count or 0
        # Calculate trends
        trend_direction = calculate_trend_direction(this_week_sessions, last_week_sessions)
        trend_percentage = abs(calculate_trend_percentage(this_week_sessions, last_week_sessions))

        weekly_activity = WeeklyActivity(
            total_duration_minutes=this_week_minutes,
            session_count=this_week_sessions,
            trend_percentage=trend_percentage,
            trend_direction=trend_direction
        )

        # ========== Projection-backed score summary ==========
        history_result = await history_service.get_user_history(
            db=db,
            user_id=current_user.user_id,
            limit=100,
            offset=0,
        )
        history_summaries = history_result.value if history_result.is_success else []
        score_summary = history_service.build_projection_score_summary(history_summaries)
        evaluable_summaries = [
            summary
            for summary in history_summaries
            if summary.status == "completed"
            and summary.evaluable is True
            and summary.overall_score is not None
        ]

        if evaluable_summaries:
            ordered_evaluable = sorted(
                evaluable_summaries,
                key=lambda summary: summary.end_time or summary.start_time,
                reverse=True,
            )
            last_score = round(float(ordered_evaluable[0].overall_score or 0.0), 1)
            previous_score = (
                float(ordered_evaluable[1].overall_score or 0.0)
                if len(ordered_evaluable) > 1
                else last_score
            )
            if last_score > previous_score + 5:
                score_trend = "up"
            elif last_score < previous_score - 5:
                score_trend = "down"
            else:
                score_trend = "stable"

            all_projection_scores = [
                float(summary.overall_score or 0.0)
                for summary in evaluable_summaries
            ]
            below_count = sum(1 for score in all_projection_scores if score < last_score)
            percentile = (
                int((below_count / len(all_projection_scores)) * 100)
                if all_projection_scores
                else 50
            )
            last_session_info = LastSession(
                score=last_score,
                percentile=percentile,
                trend=score_trend,
            )
        else:
            last_session_info = LastSession(
                score=0.0,
                percentile=50,
                trend="stable",
            )

        stats = DashboardStats(
            weekly_activity=weekly_activity,
            last_session=last_session_info,
            score_basis=str(score_summary.get("score_basis", PROJECTION_SCORE_BASIS)),
            evaluable_sessions=int(score_summary.get("evaluable_sessions", 0)),
            not_evaluable_sessions=int(score_summary.get("not_evaluable_sessions", 0)),
        )

        # 80/20 communication effectiveness metrics (last 30 days, evaluable snapshots only)
        effect_cutoff = now - timedelta(days=30)
        effect_result = await db.execute(
            select(PracticeSession.start_time, PracticeSession.effectiveness_snapshot)
            .where(PracticeSession.user_id == user_id)
            .where(PracticeSession.status == "completed")
            .where(PracticeSession.start_time >= effect_cutoff)
            .order_by(PracticeSession.start_time.asc())
        )
        effect_rows = effect_result.all()

        pass_3 = 0
        pass_5 = 0
        pass_4 = 0
        evaluable_count = 0
        evaluable_times: list[datetime] = []
        for row_item in effect_rows:
            snapshot = row_item.effectiveness_snapshot
            if not isinstance(snapshot, dict) or not bool(snapshot.get("evaluable", False)):
                continue
            pass_flags = snapshot.get("pass_flags")
            if not isinstance(pass_flags, dict):
                continue
            evaluable_count += 1
            evaluable_times.append(row_item.start_time)
            if bool(pass_flags.get("pass_3min_flow", False)):
                pass_3 += 1
            if bool(pass_flags.get("pass_5turn_defense", False)):
                pass_5 += 1
            if bool(pass_flags.get("pass_4step_structure", False)):
                pass_4 += 1

        next_day_retry_hits = 0
        for idx, base_time in enumerate(evaluable_times):
            for candidate_time in evaluable_times[idx + 1 :]:
                delta_seconds = (candidate_time - base_time).total_seconds()
                if delta_seconds < 24 * 3600:
                    continue
                if delta_seconds <= 48 * 3600:
                    next_day_retry_hits += 1
                break

        if evaluable_count > 0:
            stats.effectiveness = {
                "pass_rate_3min_flow": round((pass_3 / evaluable_count) * 100, 2),
                "pass_rate_5turn_defense": round((pass_5 / evaluable_count) * 100, 2),
                "pass_rate_4step_structure": round((pass_4 / evaluable_count) * 100, 2),
                "next_day_retry_rate": round((next_day_retry_hits / evaluable_count) * 100, 2),
            }
        else:
            stats.effectiveness = {
                "pass_rate_3min_flow": 0.0,
                "pass_rate_5turn_defense": 0.0,
                "pass_rate_4step_structure": 0.0,
                "next_day_retry_rate": 0.0,
            }

        return success_response(stats.model_dump())

    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {type(e).__name__}: {str(e)}")
        return error_response("[DASHBOARD_STATS_FAILED]", "获取仪表盘数据失败")


@router.get("/recommendations/latest")
async def get_recommendation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get training recommendation for current user

    Based on user's recent practice data, generates a personalized recommendation.

    Returns:
    - title: Recommendation title
    - reason: Why this is recommended
    - action_label: Button text
    - target_path: Navigation path

    Requirements: 2.4, 2.5
    """
    try:
        user_id = str(current_user.user_id)
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)

        # Get recent sessions
        recent_sessions_stmt = select(PracticeSession).where(
            PracticeSession.user_id == user_id,
            PracticeSession.start_time >= week_ago
        ).order_by(PracticeSession.start_time.desc())

        recent_result = await db.execute(recent_sessions_stmt)
        recent_sessions = recent_result.scalars().all()

        # Get last completed session with evidence for retry recommendation
        last_completed_stmt = select(PracticeSession).where(
            PracticeSession.user_id == user_id,
            PracticeSession.status == "completed"
        ).options(
            selectinload(PracticeSession.scenario),
        ).order_by(PracticeSession.end_time.desc()).limit(1)

        last_completed_result = await db.execute(last_completed_stmt)
        last_completed = last_completed_result.scalar_one_or_none()

        # Generate recommendation based on user's practice patterns
        if len(recent_sessions) == 0:
            # No recent practice - encourage to start
            recommendation = Recommendation(
                title="开始您的第一次练习",
                reason="本周还没有练习记录，开始一次练习来提升您的技能吧！",
                action_label="开始练习",
                target_path="/training"
            )
        elif last_completed:
            next_goal_recommendation = _build_next_goal_recommendation(last_completed)
            if next_goal_recommendation is not None:
                return success_response(next_goal_recommendation.model_dump())

            # Analyze scores to find weakest area
            logic = last_completed.logic_score or 0
            accuracy = last_completed.accuracy_score or 0
            completeness = last_completed.completeness_score or 0

            scores = {
                "逻辑性": logic,
                "准确性": accuracy,
                "完整性": completeness
            }

            weakest = min(scores, key=scores.get)
            weakest_score = scores[weakest]

            if weakest_score < 60:
                # Low score in an area - recommend focused practice
                recommendation = Recommendation(
                    title=f"提升{weakest}能力",
                    reason=f"您上次练习的{weakest}得分为 {weakest_score:.0f} 分，建议针对性练习来提升。",
                    action_label="针对练习",
                    target_path="/training"
                )
            elif len(recent_sessions) < 3:
                # Few sessions - encourage more practice
                recommendation = Recommendation(
                    title="保持练习频率",
                    reason=f"本周您完成了 {len(recent_sessions)} 次练习，建议每周至少练习 3 次以保持进步。",
                    action_label="继续练习",
                    target_path="/training"
                )
            else:
                # Good progress - suggest trying new scenarios
                recommendation = Recommendation(
                    title="尝试新的练习场景",
                    reason="您的练习表现很好！尝试不同的场景来全面提升技能。",
                    action_label="探索场景",
                    target_path="/training"
                )
        else:
            # Has sessions but none completed
            recommendation = Recommendation(
                title="完成一次完整练习",
                reason="您有未完成的练习，完成练习可以获得详细的反馈报告。",
                action_label="继续练习",
                target_path="/history"
            )

        return success_response(recommendation.model_dump())

    except Exception as e:
        logger.error(f"Failed to get recommendation: {type(e).__name__}: {str(e)}")
        return error_response("[RECOMMENDATION_FAILED]", "获取推荐失败")
