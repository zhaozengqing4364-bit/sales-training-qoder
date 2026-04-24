from datetime import UTC, date, datetime, timedelta

import pytest

from common.db.models import PracticeSession, Scenario, SessionStatus, User
from common.growth.growth_service import GrowthCenterService


async def _seed_user_and_scenario(test_db, scenario_type: str = "sales"):
    user = User(wechat_user_id=f"growth-{scenario_type}", name="Growth User")
    scenario = Scenario(scenario_type=scenario_type, name=f"{scenario_type} scenario")
    test_db.add_all([user, scenario])
    await test_db.flush()
    return user, scenario


def _session(user: User, scenario: Scenario, *, days_ago: int, score: float = 70):
    started_at = datetime.now(UTC) - timedelta(days=days_ago)
    return PracticeSession(
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=started_at,
        end_time=started_at + timedelta(minutes=10),
        logic_score=score,
        accuracy_score=score,
        completeness_score=score,
        effectiveness_snapshot={"evaluable": True},
    )


@pytest.mark.asyncio
async def test_growth_achievements_unlock_idempotently_from_evaluable_sessions(test_db):
    user, scenario = await _seed_user_and_scenario(test_db)
    test_db.add(_session(user, scenario, days_ago=0, score=82))
    await test_db.commit()

    service = GrowthCenterService()
    first = await service.evaluate_achievements(db=test_db, user_id=str(user.user_id))
    second = await service.evaluate_achievements(db=test_db, user_id=str(user.user_id))

    assert first.is_success
    assert second.is_success
    assert [item["code"] for item in first.value["newly_unlocked"]] == [
        "first_evaluable_session",
        "score_breakthrough_80",
    ]
    assert second.value["newly_unlocked"] == []
    dashboard = await service.get_dashboard_growth(db=test_db, user_id=str(user.user_id))
    assert dashboard.is_success
    assert {item["code"] for item in dashboard.value["achievements"]["unlocked"]} == {
        "first_evaluable_session",
        "score_breakthrough_80",
    }


@pytest.mark.asyncio
async def test_growth_goal_progress_counts_only_completed_evaluable_sessions(test_db):
    user, sales = await _seed_user_and_scenario(test_db)
    presentation = Scenario(scenario_type="presentation", name="PPT")
    test_db.add(presentation)
    await test_db.flush()

    service = GrowthCenterService()
    await service.upsert_goal(
        db=test_db,
        user_id=str(user.user_id),
        goal_type="weekly_sessions",
        target_count=3,
        period="weekly",
        start_date=date.today() - timedelta(days=1),
        end_date=date.today() + timedelta(days=6),
    )
    test_db.add_all(
        [
            _session(user, sales, days_ago=0),
            _session(user, presentation, days_ago=0),
            PracticeSession(
                user_id=user.user_id,
                scenario_id=sales.scenario_id,
                status=SessionStatus.COMPLETED.value,
                start_time=datetime.now(UTC),
                logic_score=0,
                accuracy_score=0,
                completeness_score=0,
                effectiveness_snapshot={"evaluable": False},
            ),
        ]
    )
    await test_db.commit()

    dashboard = await service.get_dashboard_growth(db=test_db, user_id=str(user.user_id))

    assert dashboard.is_success
    goal = dashboard.value["goal"]
    assert goal["current_progress"] == 2
    assert goal["target_count"] == 3
    assert goal["progress_ratio"] == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_ai_coach_notification_is_based_on_latest_evaluable_session(test_db):
    user, scenario = await _seed_user_and_scenario(test_db)
    low_score_session = _session(user, scenario, days_ago=0, score=52)
    test_db.add(low_score_session)
    await test_db.commit()

    service = GrowthCenterService()
    generated = await service.generate_ai_coach_notification(
        db=test_db,
        user_id=str(user.user_id),
    )
    repeated = await service.generate_ai_coach_notification(
        db=test_db,
        user_id=str(user.user_id),
    )

    assert generated.is_success
    assert generated.value is not None
    assert generated.value["type"] == "ai_coach"
    assert str(low_score_session.session_id) in generated.value["source"]
    assert "52" in generated.value["content"]
    assert repeated.is_success
    assert repeated.value is None

    notifications = await service.list_notifications(
        db=test_db,
        user_id=str(user.user_id),
    )
    assert notifications.is_success
    assert notifications.value["unread_count"] == 1

    notification_id = notifications.value["items"][0]["notification_id"]
    marked = await service.mark_notification_read(
        db=test_db,
        user_id=str(user.user_id),
        notification_id=notification_id,
    )
    assert marked.is_success
    assert marked.value["is_read"] is True

@pytest.mark.asyncio
async def test_growth_achievements_use_published_business_rule_config(test_db):
    from copy import deepcopy

    from common.business_rules.defaults import (
        ACHIEVEMENT_RULES_KEY,
        DEFAULT_ACHIEVEMENT_RULESET,
    )
    from common.business_rules.service import BusinessRuleConfigService

    user, scenario = await _seed_user_and_scenario(test_db)
    test_db.add(_session(user, scenario, days_ago=0, score=82))
    await test_db.flush()

    custom_ruleset = deepcopy(DEFAULT_ACHIEVEMENT_RULESET)
    custom_ruleset["version"] = "growth_achievement_custom_v1"
    custom_ruleset["achievements"] = [
        {
            "code": "two_sessions_required",
            "name": "两次有效训练",
            "description": "完成两场可评估训练。",
            "icon_key": "trophy",
            "condition": {"type": "evaluable_session_count", "min": 2},
        }
    ]
    rule_service = BusinessRuleConfigService(test_db)
    draft = await rule_service.create_or_update_draft(
        key=ACHIEVEMENT_RULES_KEY,
        value=custom_ruleset,
        actor_id=str(user.user_id),
    )
    await rule_service.publish(
        key=ACHIEVEMENT_RULES_KEY,
        actor_id=str(user.user_id),
        config_id=str(draft.id),
        reason="custom achievement threshold",
    )
    await test_db.commit()

    result = await GrowthCenterService().evaluate_achievements(
        db=test_db,
        user_id=str(user.user_id),
    )

    assert result.is_success
    assert result.value["newly_unlocked"] == []
    assert result.value["ruleset_version"] == "growth_achievement_custom_v1"
    assert result.value["ruleset_source"] == "database"


@pytest.mark.asyncio
async def test_ai_coach_disabled_business_rule_config_suppresses_notification(test_db):
    from copy import deepcopy

    from common.business_rules.defaults import (
        AI_COACH_RULES_KEY,
        DEFAULT_AI_COACH_RULESET,
    )
    from common.business_rules.service import BusinessRuleConfigService

    user, scenario = await _seed_user_and_scenario(test_db)
    test_db.add(_session(user, scenario, days_ago=0, score=45))
    await test_db.flush()

    disabled_ruleset = deepcopy(DEFAULT_AI_COACH_RULESET)
    disabled_ruleset["version"] = "ai_coach_disabled_v1"
    disabled_ruleset["enabled"] = False
    rule_service = BusinessRuleConfigService(test_db)
    draft = await rule_service.create_or_update_draft(
        key=AI_COACH_RULES_KEY,
        value=disabled_ruleset,
        actor_id=str(user.user_id),
    )
    await rule_service.publish(
        key=AI_COACH_RULES_KEY,
        actor_id=str(user.user_id),
        config_id=str(draft.id),
        reason="turn off AI coach cards",
    )
    await test_db.commit()

    generated = await GrowthCenterService().generate_ai_coach_notification(
        db=test_db,
        user_id=str(user.user_id),
    )

    assert generated.is_success
    assert generated.value is None
