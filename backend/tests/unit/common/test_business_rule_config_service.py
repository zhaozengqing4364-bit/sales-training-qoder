from __future__ import annotations

from copy import deepcopy

import pytest

from common.business_rules.defaults import (
    AI_COACH_RULES_KEY,
    DEFAULT_AI_COACH_RULESET,
    DEFAULT_RECOMMENDATION_RULESET,
    DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE,
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    NEXT_PRACTICE_RECOMMENDATION_KEY,
    ROLEPLAY_EVAL_RELEASE_GATE_KEY,
    ROLEPLAY_SITUATION_PACKS_KEY,
    list_business_rule_definitions,
)
from common.business_rules.service import BusinessRuleConfigService
from common.business_rules.validators import BusinessRuleValidationError
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
async def test_business_rule_resolver_uses_previous_valid_version_when_active_corrupt(
    test_db,
):
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
    definitions = list_business_rule_definitions()

    assert len(first) == len(definitions)
    assert second == []
    assert len(rows) == len(definitions)
    assert {row.key for row in rows} == {definition.key for definition in definitions}
    assert all(row.status == "published" for row in rows)
    assert {row.version for row in rows} == {1}


@pytest.mark.asyncio
async def test_roleplay_situation_pack_ruleset_validates_and_resolves(test_db):
    admin = await _admin(test_db)
    value = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    value["version"] = "roleplay_situation_packs_custom_v1"
    value["packs"] = [
        pack | {"default_forbidden_claim_patterns": [*pack["default_forbidden_claim_patterns"], "老客户"]}
        if pack["code"] == "first_visit"
        else pack
        for pack in value["packs"]
    ]

    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        value=value,
        actor_id=str(admin.user_id),
        reason="tighten first visit patterns",
    )
    await service.publish(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        actor_id=str(admin.user_id),
        config_id=str(draft.id),
        reason="publish roleplay packs",
    )
    await test_db.commit()

    resolution = await service.resolve_active_config(ROLEPLAY_SITUATION_PACKS_KEY)

    assert resolution.source == "database"
    assert resolution.value["version"] == "roleplay_situation_packs_custom_v1"
    first_visit = next(
        pack for pack in resolution.value["packs"] if pack["code"] == "first_visit"
    )
    assert "老客户" in first_visit["default_forbidden_claim_patterns"]


@pytest.mark.asyncio
async def test_roleplay_situation_pack_ruleset_rejects_hidden_visible_overlap(test_db):
    admin = await _admin(test_db)
    value = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    first_visit = next(pack for pack in value["packs"] if pack["code"] == "first_visit")
    first_visit["default_visible_information_scope"]["initial_visible_keys"].append(
        "hidden_information"
    )

    with pytest.raises(BusinessRuleValidationError):
        await BusinessRuleConfigService(test_db).create_or_update_draft(
            key=ROLEPLAY_SITUATION_PACKS_KEY,
            value=value,
            actor_id=str(admin.user_id),
            reason="invalid overlap",
        )


@pytest.mark.asyncio
async def test_roleplay_eval_release_gate_config_validates_and_resolves(test_db):
    admin = await _admin(test_db)
    value = deepcopy(DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE)
    value["version"] = "roleplay_eval_release_gate_custom_v1"
    value["llm_grader_mode"] = "blocking"
    value["artifact_retention_days"] = 45

    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key=ROLEPLAY_EVAL_RELEASE_GATE_KEY,
        value=value,
        actor_id=str(admin.user_id),
        reason="tighten eval release gate",
    )
    await service.publish(
        key=ROLEPLAY_EVAL_RELEASE_GATE_KEY,
        actor_id=str(admin.user_id),
        config_id=str(draft.id),
        reason="publish eval release gate",
    )
    await test_db.commit()

    resolution = await service.resolve_active_config(ROLEPLAY_EVAL_RELEASE_GATE_KEY)

    assert resolution.source == "database"
    assert resolution.value["version"] == "roleplay_eval_release_gate_custom_v1"
    assert resolution.value["deterministic_gate_mode"] == "blocking"
    assert resolution.value["llm_grader_mode"] == "blocking"


@pytest.mark.asyncio
async def test_roleplay_eval_release_gate_rejects_invalid_mode(test_db):
    admin = await _admin(test_db)
    value = deepcopy(DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE)
    value["deterministic_gate_mode"] = "silent_ignore"

    with pytest.raises(BusinessRuleValidationError):
        await BusinessRuleConfigService(test_db).create_or_update_draft(
            key=ROLEPLAY_EVAL_RELEASE_GATE_KEY,
            value=value,
            actor_id=str(admin.user_id),
            reason="invalid gate mode",
        )
