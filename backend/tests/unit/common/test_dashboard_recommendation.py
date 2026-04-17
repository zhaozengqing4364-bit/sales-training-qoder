"""Unit tests for learner dashboard recommendation helpers."""

from common.api.dashboard import _build_next_goal_recommendation
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
    assert recommendation.title == "按上次主问题再练一轮"
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
