from __future__ import annotations

import pytest

from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from curriculum_practice.services.roleplay.adapters.business_rule_config_adapter import (
    BusinessRuleConfigSituationPackAdapter,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)


def test_from_ruleset_entry_maps_default_fields_to_canonical_shape() -> None:
    entry = DEFAULT_ROLEPLAY_SITUATION_PACKS["packs"][1]

    dto = SituationPackDTO.from_ruleset_entry(entry)

    assert dto.code == "first_visit"
    assert dto.label == "首次拜访"
    assert dto.status == "published"
    assert dto.relationship_context["prior_interactions"] == "none"
    assert "industry" in dto.visible_information_scope["initial_visible_keys"]
    assert "上次拜访" in dto.forbidden_claim_patterns
    assert dto.forbidden_stage_codes == ["price_negotiation", "contract_closing"]
    assert dto.conflict_response_strategy == "customer_confused_correction"
    assert dto.compatible_practice_modes == ["customer_roleplay"]
    assert (
        dto.as_legacy_dict()["default_relationship_context"] == dto.relationship_context
    )
    canonical = dto.as_canonical_dict()
    assert canonical["relationship_context"] == dto.relationship_context
    assert canonical["forbidden_claim_patterns"] == dto.forbidden_claim_patterns
    assert "default_relationship_context" not in canonical


def test_builtin_defaults_repository_returns_published_first_visit() -> None:
    repo = SituationPackRepository.from_defaults()

    pack = repo.get_published("first_visit")

    assert pack is not None
    assert pack.label == "首次拜访"
    assert pack.status == "published"
    assert repo.get_published("missing-code") is None


def test_list_published_excludes_non_published_packs() -> None:
    repo = BusinessRuleConfigSituationPackAdapter(
        {
            "draft_only": SituationPackDTO.from_ruleset_entry(
                {
                    "code": "draft_only",
                    "label": "草稿包",
                    "status": "draft",
                    "default_relationship_context": {},
                    "default_visible_information_scope": {},
                }
            ),
            "published_pack": SituationPackDTO.from_ruleset_entry(
                {
                    "code": "published_pack",
                    "label": "已发布",
                    "status": "published",
                    "default_relationship_context": {},
                    "default_visible_information_scope": {},
                }
            ),
        }
    )

    published = repo.list_published()

    assert [item.code for item in published] == ["published_pack"]
    assert repo.get_any("draft_only") is not None
    assert repo.get_published("draft_only") is None
    assert len(repo.list_all()) == 2


@pytest.mark.asyncio
async def test_from_database_loads_active_business_rule_config(test_db) -> None:
    value = DEFAULT_ROLEPLAY_SITUATION_PACKS | {"version": "roleplay_pack_repo_v2"}
    value["packs"] = [
        pack | {"label": "首次拜访-Repository 测试版"}
        if pack["code"] == "first_visit"
        else pack
        for pack in DEFAULT_ROLEPLAY_SITUATION_PACKS["packs"]
    ]
    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        value=value,
        actor_id="admin-1",
        reason="customize first_visit label for repository test",
    )
    await service.publish(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        actor_id="admin-1",
        config_id=str(draft.id),
        reason="publish repository test packs",
    )
    await test_db.commit()

    repo = await SituationPackRepository.from_database(test_db)
    pack = repo.get_published("first_visit")

    assert pack is not None
    assert pack.label == "首次拜访-Repository 测试版"
    assert isinstance(repo, BusinessRuleConfigSituationPackAdapter)
