from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from common.analytics.history_service import HistoryService


def _make_effectiveness_snapshot(
    *,
    evaluable: bool,
    reason: str | None,
    overall_result: str | None = None,
    issue_type: str = "main_capability_not_passed",
    issue_text: str | None = None,
    recovery_rule: str | None = None,
    goal_type: str = "main_capability_focus",
    goal_text: str | None = None,
    goal_rule: str | None = None,
) -> dict[str, object]:
    is_not_evaluable = not evaluable
    return {
        "pass_flags": {
            "pass_3min_flow": evaluable,
            "pass_5turn_defense": evaluable,
            "pass_4step_structure": evaluable,
        },
        "main_capability_passed": evaluable,
        "overall_result": overall_result or ("pass" if evaluable else "fail"),
        "metrics": {
            "continuous_speech_seconds": 0.0,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.0,
        },
        "main_issue": {
            "issue_type": issue_type,
            "issue_text": issue_text or ("证据不足，当前无法评估。" if is_not_evaluable else "继续保持。"),
            "recovery_rule": recovery_rule or ("补齐有效互动后再结束。" if is_not_evaluable else "保持当前节奏。"),
        },
        "next_goal": {
            "goal_type": goal_type,
            "goal_text": goal_text or ("先完成一轮有效互动再评估。" if is_not_evaluable else "维持当前表现。"),
            "rule": goal_rule or ("补齐用户表达和AI回应后再结束。" if is_not_evaluable else "继续按当前节奏推进。"),
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
    }


def _make_stale_sales_snapshot() -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "value_expression_score": 82.0,
            "customer_benefit_score": 78.0,
            "evidence_usage_score": 61.0,
            "objection_handling_score": 74.0,
            "next_step_score": 69.0,
            "value_articulation_rollup": 80.0,
            "evidence_benefit_rollup": 69.5,
            "objection_progress_rollup": 71.5,
        },
        "main_issue": {
            "issue_type": "value_translation_gap",
            "issue_text": "产品价值说得太功能化，还没有翻译成客户收益与 ROI。",
            "recovery_rule": "下一轮先把价值翻译成客户收益，再回应价格与竞品问题。",
        },
        "next_goal": {
            "goal_type": "value_to_benefit_translation",
            "goal_text": "先把产品价值翻译成客户收益，再进入方案说明。",
            "rule": "至少说清一个客户场景、一个收益指标、一个量化变化。",
        },
        "version": "rule_v1",
        "evaluable": True,
        "not_evaluable_reason": None,
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


def test_build_history_entries_sales_alignment_overrides_stale_snapshot_feedback_summary() -> None:
    completed_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 22, 12, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练",
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
    )

    messages_by_session = {
        completed_session.session_id: [
            _make_message(
                session_id=completed_session.session_id,
                turn_number=1,
                timestamp=completed_session.start_time,
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 82.0,
                    "dimension_scores": {
                        "价值表达": 84.0,
                        "客户收益连接": 80.0,
                        "证据使用": 58.0,
                        "异议处理": 76.0,
                        "推进下一步": 72.0,
                    },
                },
            ),
        ],
    }

    summary = HistoryService.build_history_entries(
        [completed_session],
        messages_by_session=messages_by_session,
    )[0]

    assert summary.main_issue["issue_type"] == "evidence_gap"
    assert summary.next_goal["goal_type"] == "evidence_backing"
    assert summary.effectiveness_snapshot["main_issue"]["issue_type"] == "evidence_gap"
    assert summary.effectiveness_snapshot["next_goal"]["goal_type"] == "evidence_backing"
    assert summary.feedback_summary == "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。"
    assert completed_session.effectiveness_snapshot["main_issue"]["issue_type"] == "value_translation_gap"


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
        "score_basis": "session_evidence_projection_evaluable_only",
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


def test_build_supervisor_progress_snapshot_groups_truthfully_and_flags_repeated_stalled_focus() -> None:
    first_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 9, 10, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练",
        logic_score=64.0,
        accuracy_score=62.0,
        completeness_score=60.0,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=True,
            reason=None,
            overall_result="fail",
            issue_type="objection_response",
            issue_text="异议回应还不够具体。",
            recovery_rule="先回应风险，再补证据。",
            goal_type="objection_response_drill",
            goal_text="下一轮继续把异议回应说完整。",
            goal_rule="至少完成 1 次完整异议回应。",
        ),
    )
    second_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 12, 15, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练",
        logic_score=60.0,
        accuracy_score=58.0,
        completeness_score=56.0,
        total_duration_seconds=150,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=True,
            reason=None,
            overall_result="fail",
            issue_type="objection_response",
            issue_text="异议回应还不够具体。",
            recovery_rule="先回应风险，再补证据。",
            goal_type="objection_response_drill",
            goal_text="下一轮继续把异议回应说完整。",
            goal_rule="至少完成 1 次完整异议回应。",
        ),
    )
    third_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 17, 11, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练",
        logic_score=56.0,
        accuracy_score=54.0,
        completeness_score=52.0,
        total_duration_seconds=165,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=True,
            reason=None,
            overall_result="fail",
            issue_type="objection_response",
            issue_text="异议回应还不够具体。",
            recovery_rule="先回应风险，再补证据。",
            goal_type="objection_response_drill",
            goal_text="下一轮继续把异议回应说完整。",
            goal_rule="至少完成 1 次完整异议回应。",
        ),
    )
    not_evaluable_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="薄证据会话",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        total_duration_seconds=30,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=False,
            reason="INSUFFICIENT_TURN_DATA",
            issue_type="insufficient_turn_data",
            issue_text="当前互动不足，暂时无法判断真实问题。",
            recovery_rule="至少完成一轮用户表达和AI回应。",
            goal_type="collect_more_evidence",
            goal_text="先补齐有效互动，再继续诊断。",
            goal_rule="至少完成 1 次往返对话。",
        ),
    )
    in_progress_session = _make_session(
        status="in_progress",
        start_time=datetime(2026, 3, 18, 10, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="进行中会话",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        total_duration_seconds=None,
        effectiveness_snapshot=None,
    )

    summaries = HistoryService.build_history_entries(
        [
            first_session,
            second_session,
            third_session,
            not_evaluable_session,
            in_progress_session,
        ],
        messages_by_session={
            first_session.session_id: [],
            second_session.session_id: [],
            third_session.session_id: [],
            not_evaluable_session.session_id: [],
            in_progress_session.session_id: [],
        },
    )

    day_snapshot = HistoryService.build_supervisor_progress_snapshot(
        summaries,
        granularity="day",
    )
    week_snapshot = HistoryService.build_supervisor_progress_snapshot(
        summaries,
        granularity="week",
    )

    assert day_snapshot["granularity"] == "day"
    assert [point["date"][:10] for point in day_snapshot["trend_data"]] == [
        "2026-03-09",
        "2026-03-12",
        "2026-03-17",
    ]

    assert week_snapshot["granularity"] == "week"
    assert [point["date"][:10] for point in week_snapshot["trend_data"]] == [
        "2026-03-09",
        "2026-03-16",
    ]
    assert [point["average_score"] for point in week_snapshot["trend_data"]] == [60.0, 54.0]
    assert week_snapshot["trend_data"][0]["sessions_count"] == 3
    assert week_snapshot["trend_data"][0]["evaluable_session_count"] == 2
    assert week_snapshot["trend_data"][0]["not_evaluable_session_count"] == 1
    assert week_snapshot["trend_data"][0]["overall_result"] == "fail"
    assert week_snapshot["trend_data"][0]["main_issue"]["issue_type"] == "objection_response"
    assert week_snapshot["trend_data"][0]["next_goal"]["goal_type"] == "objection_response_drill"

    assert week_snapshot["evaluable_session_count"] == 3
    assert week_snapshot["not_evaluable_session_count"] == 1
    assert week_snapshot["non_completed_session_count"] == 1
    assert week_snapshot["repeated_main_issues"] == [
        {
            "issue_type": "objection_response",
            "issue_text": "异议回应还不够具体。",
            "count": 3,
        }
    ]
    assert week_snapshot["repeated_next_goals"] == [
        {
            "goal_type": "objection_response_drill",
            "goal_text": "下一轮继续把异议回应说完整。",
            "count": 3,
        }
    ]
    assert week_snapshot["should_switch_focus"] is True
    assert week_snapshot["recommendation"] == {
        "reason": "stalled_repeated_focus",
        "summary": "最近多次训练仍卡在同一重点且没有改善，建议切换训练重点或训练方法。",
    }

    with patch("common.analytics.history_service.logger") as logger:
        HistoryService()._log_history_query(
            query_name="admin_user_progress",
            user_id="user-1",
            summaries=summaries,
            filters={"granularity": "week", "time_range": "all_time"},
            extra_fields={
                "repeated_main_issues": week_snapshot["repeated_main_issues"],
                "repeated_next_goals": week_snapshot["repeated_next_goals"],
                "should_switch_focus": week_snapshot["should_switch_focus"],
                "recommendation_reason": week_snapshot["recommendation"]["reason"],
            },
        )

    logger.info.assert_called_once()
    logged = logger.info.call_args
    assert logged.kwargs["repeated_main_issues"] == week_snapshot["repeated_main_issues"]
    assert logged.kwargs["repeated_next_goals"] == week_snapshot["repeated_next_goals"]
    assert logged.kwargs["should_switch_focus"] is True
    assert logged.kwargs["recommendation_reason"] == "stalled_repeated_focus"


def test_build_history_entries_attach_canonical_kernel_and_compat_readers() -> None:
    sales_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 22, 12, 0, tzinfo=UTC),
        scenario_type="sales",
        scenario_name="销售对练",
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
    )
    presentation_session = _make_session(
        status="completed",
        start_time=datetime(2026, 3, 23, 12, 0, tzinfo=UTC),
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

    summaries = HistoryService.build_history_entries(
        [sales_session, presentation_session],
        messages_by_session={
            sales_session.session_id: [
                _make_message(
                    session_id=sales_session.session_id,
                    turn_number=1,
                    timestamp=sales_session.start_time,
                    sales_stage="objection",
                    score_snapshot={
                        "overall_score": 88.0,
                        "dimension_scores": {
                            "价值表达": 86.0,
                            "客户收益连接": 84.0,
                            "证据使用": 89.0,
                            "异议处理": 81.0,
                            "推进下一步": 79.0,
                        },
                    },
                )
            ],
            presentation_session.session_id: [],
        },
    )

    sales_summary = next(item for item in summaries if item.scenario_type == "sales")
    presentation_summary = next(
        item for item in summaries if item.scenario_type == "presentation"
    )

    assert sales_summary.canonical_evaluation_kernel["schema_version"] == "evaluation_kernel_v1"
    assert sales_summary.canonical_evaluation_kernel["scenario_type"] == "sales"
    assert sales_summary.compatibility_readers["practice_session_rollup_fields_v1"]["logic_score"] == pytest.approx(
        sales_summary.logic_score
    )
    assert sales_summary.compatibility_readers["sales_realtime_score_snapshot_v1"]["overall_score"] == pytest.approx(
        sales_summary.overall_score
    )
    assert sales_summary.canonical_evaluation_kernel["methodology"]["contract_id"] == "sales_methodology_rubric_v1"
    assert sales_summary.canonical_evaluation_kernel["methodology"]["surface_id"] == "report"
    assert sales_summary.canonical_evaluation_kernel["methodology"]["current_stage"] == "objection"
    assert sales_summary.compatibility_readers["sales_methodology_rubric_v1"] == sales_summary.canonical_evaluation_kernel["methodology"]

    assert presentation_summary.canonical_evaluation_kernel["schema_version"] == "evaluation_kernel_v1"
    assert presentation_summary.canonical_evaluation_kernel["scenario_type"] == "presentation"
    assert presentation_summary.compatibility_readers["practice_session_rollup_fields_v1"]["accuracy_score"] == pytest.approx(
        presentation_summary.accuracy_score
    )
    assert presentation_summary.compatibility_readers["presentation_review_dimensions_v1"]["overall_score"] == pytest.approx(
        presentation_summary.overall_score
    )
