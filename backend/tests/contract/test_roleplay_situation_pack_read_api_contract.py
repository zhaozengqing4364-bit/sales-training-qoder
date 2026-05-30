from __future__ import annotations

import copy

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import DEFAULT_ROLEPLAY_SITUATION_PACKS
from common.business_rules.service import BusinessRuleConfigService
from curriculum_practice.models import PracticeTemplate


@pytest.mark.contract
@pytest.mark.asyncio
async def test_roleplay_situation_pack_resolve_returns_canonical_dto_and_metadata(
    async_client: AsyncClient,
    contract_auth_headers: dict[str, str],
) -> None:
    response = await async_client.get(
        "/api/v1/admin/curriculum-practice/roleplay-situation-packs/first_visit/resolve",
        headers=contract_auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    pack = data["pack"]
    metadata = data["metadata"]

    assert pack["code"] == "first_visit"
    assert pack["label"] == "首次拜访"
    assert pack["status"] == "published"
    assert pack["relationship_context"]["prior_interactions"] == "none"
    assert "industry" in pack["visible_information_scope"]["initial_visible_keys"]
    assert "上次拜访" in pack["forbidden_claim_patterns"]
    assert "default_relationship_context" not in pack
    assert "default_forbidden_claim_patterns" not in pack

    assert metadata["config_key"] == "roleplay.situation_packs.ruleset"
    assert metadata["read_path"].endswith("SituationPackRepository.from_database")
    assert metadata["ruleset_version"]
    assert metadata["source"]
    assert metadata["resolved_at"]


@pytest.mark.contract
@pytest.mark.asyncio
async def test_roleplay_situation_pack_resolve_returns_not_found_for_missing_code(
    async_client: AsyncClient,
    contract_auth_headers: dict[str, str],
) -> None:
    response = await async_client.get(
        "/api/v1/admin/curriculum-practice/roleplay-situation-packs/missing-pack-code/resolve",
        headers=contract_auth_headers,
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == "[ROLEPLAY_SITUATION_PACK_NOT_FOUND]"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_roleplay_situation_pack_resolve_returns_not_published_for_draft_pack(
    async_client: AsyncClient,
    test_db: AsyncSession,
    contract_auth_headers: dict[str, str],
) -> None:
    ruleset = copy.deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    ruleset["packs"] = list(ruleset["packs"]) + [
        {
            "code": "draft_only_pack",
            "label": "仅草稿情景",
            "version": "v1",
            "status": "draft",
            "default_relationship_context": {"prior_interactions": "none"},
            "default_visible_information_scope": {
                "initial_visible_keys": [],
                "conditionally_visible_keys": [],
                "hidden_by_default_keys": [],
            },
            "default_forbidden_claim_patterns": [],
            "default_forbidden_topic_codes": [],
            "default_forbidden_stage_codes": [],
            "default_conflict_response_strategy": "neutral_clarification",
            "default_runtime_violation_policy": {},
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        }
    ]
    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key="roleplay.situation_packs.ruleset",
        value=ruleset,
        actor_id="contract-test-admin",
        reason="seed draft-only situation pack",
    )
    await service.publish(
        key="roleplay.situation_packs.ruleset",
        actor_id="contract-test-admin",
        config_id=str(draft.id),
        reason="publish draft-only ruleset for resolve contract test",
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/curriculum-practice/roleplay-situation-packs/draft_only_pack/resolve",
        headers=contract_auth_headers,
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == "[ROLEPLAY_SITUATION_PACK_NOT_PUBLISHED]"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_roleplay_situation_pack_references_returns_templates_and_empty_lists(
    async_client: AsyncClient,
    test_db: AsyncSession,
    contract_auth_headers: dict[str, str],
) -> None:
    test_db.add(
        PracticeTemplate(
            template_id="contract-template-first-visit",
            name="契约测试模板",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id="agent-1",
            persona_id="persona-1",
            runtime_profile_id="runtime-1",
            voice_mode="stepfun_realtime",
            scoring_ruleset_id="ruleset-1",
            knowledge_base_refs=[],
            timeout_config={"roleplay": {"situation_code": "first_visit"}},
            status="draft",
        )
    )
    await test_db.commit()

    references_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/roleplay-situation-packs/first_visit/references",
        headers=contract_auth_headers,
    )
    empty_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/roleplay-situation-packs/general_practice/references",
        headers=contract_auth_headers,
    )

    assert references_response.status_code == 200
    references = references_response.json()["data"]
    assert any(
        item["asset_id"] == "contract-template-first-visit"
        and item["name"] == "契约测试模板"
        and item["status"] == "draft"
        for item in references["practice_templates"]
    )
    assert references["total"] >= 1

    assert empty_response.status_code == 200
    empty_refs = empty_response.json()["data"]
    assert empty_refs["practice_templates"] == []
    assert empty_refs["case_items"] == []
    assert empty_refs["personas"] == []
    assert empty_refs["total"] == 0
