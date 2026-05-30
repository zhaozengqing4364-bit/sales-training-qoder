"""Unit tests for SituationPack ORM model."""

from __future__ import annotations

import pytest

from curriculum_practice.models import SituationPack
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO


def test_situation_pack_model_instantiation() -> None:
    pack = SituationPack(
        code="first_visit",
        label="首次拜访",
    )

    assert pack.code == "first_visit"
    assert pack.label == "首次拜访"


@pytest.mark.asyncio
async def test_situation_pack_model_defaults_after_flush(test_db) -> None:
    pack = SituationPack(
        code="first_visit",
        label="首次拜访",
    )
    test_db.add(pack)
    await test_db.flush()

    assert pack.version == "v1"
    assert pack.status == "draft"
    assert pack.relationship_context == {}
    assert pack.visible_information_scope == {}
    assert pack.forbidden_claim_patterns == []
    assert pack.forbidden_topic_codes == []
    assert pack.forbidden_stage_codes == []
    assert pack.conflict_response_strategy == "neutral_clarification"
    assert pack.behavior_rules_for_prompt_only == []
    assert pack.disclosure_policy == {}
    assert pack.runtime_violation_policy == {}
    assert pack.compatible_practice_modes == ["customer_roleplay"]
    assert pack.compatible_scenario_types == ["sales"]


def test_situation_pack_dto_from_entity_round_trip() -> None:
    pack = SituationPack(
        code="follow_up",
        label="复访跟进",
        version="v2",
        status="published",
        relationship_context={"prior_interactions": "multiple"},
        visible_information_scope={"initial_visible_keys": ["industry"]},
        forbidden_claim_patterns=["我们上次已经签约"],
        forbidden_topic_codes=["pricing"],
        forbidden_stage_codes=["closing"],
        conflict_response_strategy="firm_boundary",
        behavior_rules_for_prompt_only=["不要主动报价"],
        disclosure_policy={"max_disclosures_per_turn": 1},
        runtime_violation_policy={"warn_threshold": 2},
        compatible_practice_modes=["customer_roleplay", "mixed_path"],
        compatible_scenario_types=["sales"],
        content_hash="sha256:abc123",
    )

    dto = SituationPackDTO.from_entity(pack)

    assert dto.code == "follow_up"
    assert dto.label == "复访跟进"
    assert dto.version == "v2"
    assert dto.status == "published"
    assert dto.relationship_context == {"prior_interactions": "multiple"}
    assert dto.visible_information_scope == {"initial_visible_keys": ["industry"]}
    assert dto.forbidden_claim_patterns == ["我们上次已经签约"]
    assert dto.forbidden_topic_codes == ["pricing"]
    assert dto.forbidden_stage_codes == ["closing"]
    assert dto.conflict_response_strategy == "firm_boundary"
    assert dto.behavior_rules_for_prompt_only == ["不要主动报价"]
    assert dto.disclosure_policy == {"max_disclosures_per_turn": 1}
    assert dto.runtime_violation_policy == {"warn_threshold": 2}
    assert dto.compatible_practice_modes == ["customer_roleplay", "mixed_path"]
    assert dto.compatible_scenario_types == ["sales"]
