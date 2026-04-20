from types import SimpleNamespace

from training_runtime.service import build_training_runtime_descriptor


def test_build_training_runtime_descriptor_carries_sales_retry_focus_from_snapshot():
    session = SimpleNamespace(
        session_id="session-1",
        agent_id="agent-1",
        persona_id="persona-1",
        presentation_id=None,
        voice_mode="legacy",
        voice_runtime_profile_id="runtime-1",
        voice_policy_snapshot={
            "focus_intent": {
                "version": "retry_focus_v1",
                "source_session_id": "session-source",
                "main_issue": {
                    "issue_type": "value_unclear",
                    "issue_text": "客户没有听懂收益点。",
                    "recovery_rule": "先复述痛点，再补案例。",
                },
                "next_goal": {
                    "goal_type": "single_next_goal",
                    "goal_text": "下一轮先补 ROI 证据。",
                    "rule": "客户能复述价值和 ROI 逻辑。",
                },
            }
        },
        scenario=None,
    )

    descriptor = build_training_runtime_descriptor(session, scenario_type="sales")

    assert descriptor.focus_intent == {
        "version": "retry_focus_v1",
        "source_session_id": "session-source",
        "main_issue": {
            "issue_type": "value_unclear",
            "issue_text": "客户没有听懂收益点。",
            "recovery_rule": "先复述痛点，再补案例。",
        },
        "next_goal": {
            "goal_type": "single_next_goal",
            "goal_text": "下一轮先补 ROI 证据。",
            "rule": "客户能复述价值和 ROI 逻辑。",
        },
    }


def test_build_training_runtime_descriptor_skips_invalid_focus_for_presentation_runtime():
    session = SimpleNamespace(
        session_id="session-2",
        agent_id=None,
        persona_id=None,
        presentation_id="presentation-1",
        voice_mode="legacy",
        voice_runtime_profile_id=None,
        voice_policy_snapshot={
            "focus_intent": {
                "version": "presentation_page_retry_v1",
                "source_session_id": "session-source",
                "presentation_page": {"page_number": 0},
            }
        },
        scenario=None,
    )

    descriptor = build_training_runtime_descriptor(session, scenario_type="presentation")

    assert descriptor.focus_intent is None


def test_build_training_runtime_descriptor_carries_presentation_page_focus_from_snapshot():
    session = SimpleNamespace(
        session_id="session-ppt-retry",
        agent_id=None,
        persona_id=None,
        presentation_id="presentation-1",
        voice_mode="legacy",
        voice_runtime_profile_id=None,
        voice_policy_snapshot={
            "focus_intent": {
                "version": "presentation_page_retry_v1",
                "source_session_id": "session-source",
                "presentation_page": {
                    "page_number": 2,
                    "reason": "missing_required_points",
                    "summary": "第 2 页缺客户案例",
                    "missing_required_points": ["客户案例", ""],
                },
            }
        },
        scenario=None,
    )

    descriptor = build_training_runtime_descriptor(session, scenario_type="presentation")

    assert descriptor.focus_intent == {
        "version": "presentation_page_retry_v1",
        "source_session_id": "session-source",
        "presentation_page": {
            "page_number": 2,
            "reason": "missing_required_points",
            "summary": "第 2 页缺客户案例",
            "missing_required_points": ["客户案例"],
        },
    }
