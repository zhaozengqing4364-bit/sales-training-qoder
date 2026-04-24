from __future__ import annotations

from copy import deepcopy

import pytest

from common.business_rules.defaults import (
    AI_COACH_RULES_KEY,
    DEFAULT_AI_COACH_RULESET,
    DEFAULT_RECOMMENDATION_RULESET,
    NEXT_PRACTICE_RECOMMENDATION_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import User


async def _admin(test_db) -> User:
    user = User(
        wechat_user_id="business-rule-admin",
        name="Business Rule Admin",
        email="business-rule-admin@example.com",
        role="admin",
    )
    test_db.add(user)
    await test_db.flush()
    return user


@pytest.mark.asyncio
async def test_business_rule_service_publishes_and_resolves_database_ruleset(test_db):
    admin = await _admin(test_db)
    value = deepcopy(DEFAULT_RECOMMENDATION_RULESET)
    value["version"] = "recommendation_custom_v1"
    value["weak_score_threshold"] = 72

    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key=NEXT_PRACTICE_RECOMMENDATION_KEY,
        value=value,
        actor_id=str(admin.user_id),
        reason="raise weak threshold",
    )
    published = await service.publish(
        key=NEXT_PRACTICE_RECOMMENDATION_KEY,
        actor_id=str(admin.user_id),
        config_id=str(draft.id),
        reason="approved by enablement",
    )
    await test_db.commit()

    resolution = await service.resolve_active_config(NEXT_PRACTICE_RECOMMENDATION_KEY)
    audits = await service.list_audit_logs(key=NEXT_PRACTICE_RECOMMENDATION_KEY)

    assert published.status == "published"
    assert resolution.source == "database"
    assert resolution.version == 1
    assert resolution.value["version"] == "recommendation_custom_v1"
    assert resolution.value["weak_score_threshold"] == 72.0
    assert [audit.action for audit in audits] == ["publish", "create_draft"]
    assert audits[0].before_version is None
    assert audits[0].after_version == 1
    assert audits[0].reason == "approved by enablement"


@pytest.mark.asyncio
async def test_business_rule_resolver_uses_previous_valid_version_when_active_corrupt(test_db):
    admin = await _admin(test_db)
    service = BusinessRuleConfigService(test_db)

    first_value = deepcopy(DEFAULT_RECOMMENDATION_RULESET)
    first_value["version"] = "recommendation_custom_v1"
    first_value["weak_score_threshold"] = 70
    first_draft = await service.create_or_update_draft(
        key=NEXT_PRACTICE_RECOMMENDATION_KEY,
        value=first_value,
        actor_id=str(admin.user_id),
    )
    await service.publish(
        key=NEXT_PRACTICE_RECOMMENDATION_KEY,
        actor_id=str(admin.user_id),
        config_id=str(first_draft.id),
        reason="first publish",
    )

    second_value = deepcopy(DEFAULT_RECOMMENDATION_RULESET)
    second_value["version"] = "recommendation_custom_v2"
    second_value["weak_score_threshold"] = 80
    second_draft = await service.create_or_update_draft(
        key=NEXT_PRACTICE_RECOMMENDATION_KEY,
        value=second_value,
        actor_id=str(admin.user_id),
    )
    active = await service.publish(
        key=NEXT_PRACTICE_RECOMMENDATION_KEY,
        actor_id=str(admin.user_id),
        config_id=str(second_draft.id),
        reason="second publish",
    )
    active.value_json = {"version": "", "dimensions": {}}
    await test_db.commit()

    resolution = await service.resolve_active_config(NEXT_PRACTICE_RECOMMENDATION_KEY)

    assert resolution.source == "database_previous"
    assert resolution.version == 1
    assert resolution.value["version"] == "recommendation_custom_v1"
    assert resolution.value["weak_score_threshold"] == 70.0
    assert resolution.fallback_reason == "active_invalid_used_previous"


@pytest.mark.asyncio
async def test_business_rule_resolver_preserves_disabled_ai_coach_config(test_db):
    admin = await _admin(test_db)
    value = deepcopy(DEFAULT_AI_COACH_RULESET)
    value["version"] = "ai_coach_disabled_v1"
    value["enabled"] = False

    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key=AI_COACH_RULES_KEY,
        value=value,
        actor_id=str(admin.user_id),
    )
    await service.publish(
        key=AI_COACH_RULES_KEY,
        actor_id=str(admin.user_id),
        config_id=str(draft.id),
        reason="disable coach notifications",
    )
    await test_db.commit()

    resolution = await service.resolve_active_config(AI_COACH_RULES_KEY)

    assert resolution.source == "database_disabled"
    assert resolution.status == "disabled"
    assert resolution.value["enabled"] is False


@pytest.mark.asyncio
async def test_business_rule_seed_defaults_is_idempotent(test_db):
    admin = await _admin(test_db)
    service = BusinessRuleConfigService(test_db)

    first = await service.seed_defaults(actor_id=str(admin.user_id))
    second = await service.seed_defaults(actor_id=str(admin.user_id))
    await test_db.commit()
    rows = await service.list_configs()

    assert len(first) == 3
    assert second == []
    assert len(rows) == 3
    assert all(row.status == "published" for row in rows)
    assert {row.version for row in rows} == {1}
