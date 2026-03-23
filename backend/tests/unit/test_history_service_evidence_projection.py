from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from common.analytics.history_service import HistoryService


def _make_effectiveness_snapshot(*, evaluable: bool, reason: str | None) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": evaluable,
            "pass_5turn_defense": evaluable,
            "pass_4step_structure": evaluable,
        },
        "main_capability_passed": evaluable,
        "overall_result": "pass" if evaluable else "fail",
        "metrics": {
            "continuous_speech_seconds": 0.0,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.0,
        },
        "main_issue": {
            "issue_type": "main_capability_not_passed",
            "issue_text": "证据不足，当前无法评估。" if not evaluable else "继续保持。",
            "recovery_rule": "补齐有效互动后再结束。" if not evaluable else "保持当前节奏。",
        },
        "next_goal": {
            "goal_type": "main_capability_focus",
            "goal_text": "先完成一轮有效互动再评估。" if not evaluable else "维持当前表现。",
            "rule": "补齐用户表达和AI回应后再结束。" if not evaluable else "继续按当前节奏推进。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
    }


def _make_session(
    *,
    session_id: str | None = None,
    status: str,
    start_time: datetime,
    scenario_type: str,
    scenario_name: str,
    logic_score: float | None,
    accuracy_score: float | None,
    completeness_score: float | None,
    total_duration_seconds: int | None,
    effectiveness_snapshot: dict[str, object] | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        session_id=session_id or str(uuid.uuid4()),
        scenario_id=str(uuid.uuid4()),
        status=status,
        start_time=start_time,
        end_time=(start_time + timedelta(seconds=total_duration_seconds)) if total_duration_seconds else None,
        total_duration_seconds=total_duration_seconds,
        logic_score=logic_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        report_status="completed" if status == "completed" else "pending",
        report_generated_at=start_time + timedelta(minutes=5) if status == "completed" else None,
        scenario=SimpleNamespace(name=scenario_name, scenario_type=scenario_type),
        agent=SimpleNamespace(name=f"{scenario_name} Agent"),
        persona=SimpleNamespace(name=f"{scenario_name} Persona"),
        effectiveness_snapshot=effectiveness_snapshot,
        voice_policy_snapshot=None,
    )


def _make_message(
    *,
    session_id: str,
    turn_number: int,
    timestamp: datetime,
    sales_stage: str,
    score_snapshot: dict[str, object],
    duration_ms: int = 1200,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"msg-{session_id}-{turn_number}",
        session_id=session_id,
        turn_number=turn_number,
        role="user" if turn_number % 2 else "assistant",
        content=f"message-{turn_number}",
        audio_url=None,
        timestamp=timestamp,
        duration_ms=duration_ms,
        fuzzy_words=None,
        transcript_metadata=None,
        sales_stage=sales_stage,
        score_snapshot=score_snapshot,
        ai_feedback=None,
        is_highlight=False,
        highlight_type=None,
        highlight_reason=None,
    )


def test_build_history_entries_use_shared_projection_for_completed_sessions_only() -> None:
    completed_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 22, 12, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        total_duration_seconds=96,
        effectiveness_snapshot=None,
    )
    in_progress_session = _make_session(
        status="in_progress",
        start_time=datetime(2026, 3, 22, 13, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练进行中",
        logic_score=77.0,
        accuracy_score=75.0,
        completeness_score=74.0,
        total_duration_seconds=None,
        effectiveness_snapshot=None,
    )

    messages_by_session = {
        completed_session.session_id: [
            _make_message(
                session_id=completed_session.session_id,
                turn_number=1,
                timestamp=completed_session.start_time,
                sales_stage="opening",
                score_snapshot={"overall": 74},
            ),
            _make_message(
                session_id=completed_session.session_id,
                turn_number=2,
                timestamp=completed_session.start_time + timedelta(seconds=2),
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 89,
                    "dimension_scores": {
                        "professional": 88,
                        "communication": 82,
                        "discovery": 76,
                    },
                },
            ),
        ],
        in_progress_session.session_id: [],
    }

    summaries = HistoryService.build_history_entries(
        [completed_session, in_progress_session],
        messages_by_session=messages_by_session,
    )
    summary_by_id = {item.session_id: item for item in summaries}

    completed_summary = summary_by_id[completed_session.session_id]
    assert completed_summary.overall_score == pytest.approx(82.0)
    assert completed_summary.evaluable is True
    assert completed_summary.not_evaluable_reason is None
    assert completed_summary.evidence_completeness["legacy_score_key_used"] is True
    assert completed_summary.effectiveness_snapshot["evaluable"] is True

    in_progress_summary = summary_by_id[in_progress_session.session_id]
    assert in_progress_summary.overall_score is None
    assert in_progress_summary.evaluable is None
    assert in_progress_summary.not_evaluable_reason is None
    assert in_progress_summary.evidence_completeness is None
    assert in_progress_summary.effectiveness_snapshot is None


def test_build_statistics_and_trends_use_projection_scores_and_skip_not_evaluable_sessions() -> None:
    legacy_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        total_duration_seconds=96,
        effectiveness_snapshot=None,
    )
    no_evidence_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 21, 10, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="无证据会话",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        total_duration_seconds=0,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=False,
            reason="INSUFFICIENT_TURN_DATA",
        ),
    )
    scored_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        scenario_type="presentation",
        scenario_name="演讲训练",
        logic_score=90.0,
        accuracy_score=84.0,
        completeness_score=87.0,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=True,
            reason=None,
        ),
    )

    messages_by_session = {
        legacy_session.session_id: [
            _make_message(
                session_id=legacy_session.session_id,
                turn_number=1,
                timestamp=legacy_session.start_time,
                sales_stage="opening",
                score_snapshot={"overall": 74},
            ),
            _make_message(
                session_id=legacy_session.session_id,
                turn_number=2,
                timestamp=legacy_session.start_time + timedelta(seconds=2),
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 89,
                    "dimension_scores": {
                        "professional": 88,
                        "communication": 82,
                        "discovery": 76,
                    },
                },
            ),
        ],
        no_evidence_session.session_id: [],
        scored_session.session_id: [],
    }

    summaries = HistoryService.build_history_entries(
        [legacy_session, no_evidence_session, scored_session],
        messages_by_session=messages_by_session,
    )

    stats = HistoryService.build_statistics_payload(summaries)
    assert stats == {
        "total_sessions": 3,
        "evaluable_sessions": 2,
        "not_evaluable_sessions": 1,
        "average_score": 84.5,
        "best_score": 87.0,
        "total_practice_time_seconds": 276,
        "total_practice_time_minutes": 4.6,
    }

    trends = HistoryService.build_trend_points(summaries)
    assert [point["session_id"] for point in trends] == [
        legacy_session.session_id,
        scored_session.session_id,
    ]
    assert [point["overall_score"] for point in trends] == [82.0, 87.0]
    assert [point["scenario_type"] for point in trends] == ["sales", "presentation"]
    assert all(point["evaluable"] is True for point in trends)

    with patch("common.analytics.history_service.logger") as logger:
        HistoryService()._log_history_query(
            query_name="history_trends",
            user_id="user-1",
            summaries=summaries,
            filters={"days": 30, "scenario_type": "sales"},
        )

    logger.info.assert_called_once()
    call = logger.info.call_args
    assert call.args[0] == "practice_history_projection_query"
    assert call.kwargs["query_name"] == "history_trends"
    assert call.kwargs["user_id"] == "user-1"
    assert call.kwargs["evidence_source"] == "session_evidence_projection"
    assert call.kwargs["filters"] == {"days": 30, "scenario_type": "sales"}
    assert call.kwargs["session_count"] == 3
    assert call.kwargs["completed_session_count"] == 3
    assert call.kwargs["projected_session_count"] == 3
    assert call.kwargs["evaluable_session_count"] == 2
    assert call.kwargs["not_evaluable_session_count"] == 1
    assert no_evidence_session.session_id in call.kwargs["not_evaluable_session_ids"]
