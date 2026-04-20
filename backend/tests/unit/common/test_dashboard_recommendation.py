"""Unit tests for learner dashboard recommendation helpers."""

from common.api.dashboard import (
    _build_next_goal_recommendation,
    _build_presentation_page_recommendation,
)
from common.db.models import PracticeSession, Scenario


def test_dashboard_next_goal_recommendation_links_to_focused_sales_retry():
    session = PracticeSession(
        session_id="session-1",
        agent_id="agent-1",
        persona_id="persona-1",
        scenario_id="scenario-1",
        effectiveness_snapshot={
            "main_issue": {
                "issue_type": "value_evidence_gap",
                "issue_text": "价值主张缺少案例、数据或ROI支撑。",
                "recovery_rule": "先给证据，再回应价格顾虑。",
            },
            "next_goal": {
                "goal_type": "evidence_backing",
                "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
                "rule": "至少补上一条证据和一个明确下一步。",
            },
        },
    )
    session.scenario = Scenario(
        scenario_id="scenario-1",
        scenario_type="sales",
        name="销售对练",
    )

    recommendation = _build_next_goal_recommendation(session)

    assert recommendation is not None
    assert recommendation.title == "今日复练：按上次主问题再练一轮"
    assert recommendation.action_label == "按目标再练一轮"
    assert recommendation.score_basis == "session_evidence_projection_evaluable_only"
    assert recommendation.target_path.startswith(
        "/agents/agent-1?persona_id=persona-1&focus_intent="
    )
    assert "先用案例、数据或ROI证据支撑主张" in recommendation.reason


def test_dashboard_next_goal_recommendation_recovers_when_sales_pairing_missing():
    session = PracticeSession(
        session_id="session-2",
        scenario_id="scenario-1",
        effectiveness_snapshot={
            "next_goal": {
                "goal_type": "objection_reframe",
                "goal_text": "先承接客户异议，再给报价依据。",
                "rule": "必须完成异议承接。",
            },
        },
    )
    session.scenario = Scenario(
        scenario_id="scenario-1",
        scenario_type="sales",
        name="销售对练",
    )

    recommendation = _build_next_goal_recommendation(session)

    assert recommendation is not None
    assert recommendation.target_path == "/training/sales"
    assert "缺少完整智能体或客户画像配置" in recommendation.reason


def test_dashboard_presentation_recommendation_points_to_most_actionable_page():
    session = PracticeSession(session_id="session-ppt-1")

    recommendation = _build_presentation_page_recommendation(
        session,
        {
            "page_summaries": [
                {
                    "page_number": 2,
                    "average_score": 72,
                    "missing_required_points": ["讲清楚落地周期"],
                    "issue_clusters": [],
                },
                {
                    "page_number": 5,
                    "average_score": 68,
                    "missing_required_points": ["补充客户案例", "说明 ROI"],
                    "issue_clusters": [{"issue_type": "missing_point"}],
                },
            ],
        },
    )

    assert recommendation is not None
    assert recommendation.recommendation_kind == "presentation_page_retry"
    assert recommendation.scenario_type == "presentation"
    assert recommendation.focus_page == 5
    assert recommendation.title == "今日复练：补练 PPT 第 5 页"
    assert "补充客户案例" in recommendation.reason
    assert recommendation.action_label == "查看逐页复练任务"
    assert recommendation.target_path == (
        "/practice/session-ppt-1/report?focus=presentation_page&page=5"
    )
