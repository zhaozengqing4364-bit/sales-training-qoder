from datetime import UTC, datetime, timedelta

import pytest

from common.analytics.report_trends import ReportTrendService
from common.db.models import PracticeSession, Scenario, SessionStatus, User


@pytest.mark.asyncio
async def test_report_trends_only_use_current_user_same_scenario_completed_evaluable(
    test_db,
):
    user = User(wechat_user_id="trend-user", name="Trend User")
    other_user = User(wechat_user_id="trend-other", name="Trend Other")
    sales = Scenario(scenario_type="sales", name="销售对练")
    presentation = Scenario(scenario_type="presentation", name="PPT 演练")
    test_db.add_all([user, other_user, sales, presentation])
    await test_db.flush()

    base_time = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
    eligible_previous = PracticeSession(
        user_id=user.user_id,
        scenario_id=sales.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=base_time,
        end_time=base_time + timedelta(minutes=10),
        logic_score=60,
        accuracy_score=70,
        completeness_score=80,
        effectiveness_snapshot={"evaluable": True},
    )
    eligible_current = PracticeSession(
        user_id=user.user_id,
        scenario_id=sales.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=base_time + timedelta(days=1),
        end_time=base_time + timedelta(days=1, minutes=12),
        logic_score=70,
        accuracy_score=80,
        completeness_score=90,
        effectiveness_snapshot={"evaluable": True},
    )
    same_user_wrong_scenario = PracticeSession(
        user_id=user.user_id,
        scenario_id=presentation.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=base_time + timedelta(hours=2),
        logic_score=99,
        accuracy_score=99,
        completeness_score=99,
        effectiveness_snapshot={"evaluable": True},
    )
    same_user_not_evaluable = PracticeSession(
        user_id=user.user_id,
        scenario_id=sales.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=base_time + timedelta(hours=3),
        logic_score=10,
        accuracy_score=10,
        completeness_score=10,
        effectiveness_snapshot={"evaluable": False},
    )
    other_user_session = PracticeSession(
        user_id=other_user.user_id,
        scenario_id=sales.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=base_time + timedelta(hours=4),
        logic_score=100,
        accuracy_score=100,
        completeness_score=100,
        effectiveness_snapshot={"evaluable": True},
    )
    test_db.add_all(
        [
            eligible_previous,
            eligible_current,
            same_user_wrong_scenario,
            same_user_not_evaluable,
            other_user_session,
        ]
    )
    await test_db.commit()

    result = await ReportTrendService().get_session_report_trends(
        db=test_db,
        requester=user,
        session_id=str(eligible_current.session_id),
        limit=5,
    )

    assert result.is_success
    payload = result.value
    assert payload["score_basis"] == "session_evidence_projection_evaluable_only"
    assert [point["session_id"] for point in payload["points"]] == [
        str(eligible_previous.session_id),
        str(eligible_current.session_id),
    ]
    assert payload["delta_vs_previous"] == {
        "logic_score": 10.0,
        "accuracy_score": 10.0,
        "completeness_score": 10.0,
        "overall_score": 10.0,
    }


@pytest.mark.asyncio
async def test_report_trends_explain_insufficient_history_without_fake_zero(test_db):
    user = User(wechat_user_id="trend-single", name="Trend Single")
    scenario = Scenario(scenario_type="sales", name="销售对练")
    test_db.add_all([user, scenario])
    await test_db.flush()

    current = PracticeSession(
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
        logic_score=75,
        accuracy_score=70,
        completeness_score=80,
        effectiveness_snapshot={"evaluable": True},
    )
    test_db.add(current)
    await test_db.commit()

    result = await ReportTrendService().get_session_report_trends(
        db=test_db,
        requester=user,
        session_id=str(current.session_id),
        limit=5,
    )

    assert result.is_success
    payload = result.value
    assert len(payload["points"]) == 1
    assert payload["delta_vs_previous"] is None
    assert "至少需要两次" in payload["explanation"]
