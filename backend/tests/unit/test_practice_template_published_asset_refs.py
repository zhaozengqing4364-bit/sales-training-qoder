from __future__ import annotations

from datetime import UTC, datetime

import pytest

from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleResolution
from curriculum_practice.schemas import (
    PracticeTemplatePublishCandidate,
    PublishedAssetRefSchema,
)
from curriculum_practice.services.asset_references import stable_hash
from curriculum_practice.services.published_asset_refs import build_published_asset_refs
from curriculum_practice.services.publishing_gates import PublishingGateService
from curriculum_practice.services.roleplay.adapters.business_rule_config_adapter import (
    BusinessRuleConfigSituationPackAdapter,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)


def _candidate(**overrides: object) -> PracticeTemplatePublishCandidate:
    payload = {
        "name": "客户对练模板",
        "scenario_type": "sales",
        "mode": "customer_roleplay",
        "agent_id": "agent-1",
        "persona_id": "persona-1",
        "runtime_profile_id": "runtime-1",
        "voice_mode": "stepfun_realtime",
        "scoring_ruleset_id": "ruleset-1",
        "knowledge_base_refs": ["kb-1"],
        "case_item_id": "case-1",
        "role_profile_id": "role-1",
        "learning_content_id": "learning-1",
        "examiner_agent_id": "examiner-1",
    }
    payload.update(overrides)
    return PracticeTemplatePublishCandidate(**payload)


def _reference_reader() -> object:
    references = {
        ("agent", "agent-1"): {"id": "agent-1", "status": "published", "version": 1},
        ("persona", "persona-1"): {
            "id": "persona-1",
            "status": "active",
            "system_prompt": "首次拜访需求挖掘，保持谨慎客户语气。",
            "persona_policy": {},
        },
        ("voice_runtime_profile", "runtime-1"): {"id": "runtime-1", "is_active": True},
        ("scoring_ruleset", "ruleset-1"): {
            "ruleset_id": "ruleset-1",
            "status": "published",
            "version": "sales-v1",
            "definition_json": {"scenario_type": "sales"},
        },
        ("knowledge_base", "kb-1"): {"id": "kb-1", "status": "active"},
        ("case_item", "case-1"): {
            "case_item_id": "case-1",
            "logical_id": "case-1",
            "revision_id": "case-revision-1",
            "revision_no": 7,
            "status": "published",
            "version": 1,
            "content_hash": "sha256:case-1",
            "allowed_disclosure_policy": {
                "phases": [{"trigger": "ask", "disclose": "budget"}],
                "roleplay": {"situation_code": "first_visit"},
            },
        },
        ("role_profile", "role-1"): {
            "role_profile_id": "role-1",
            "logical_id": "role-1",
            "revision_id": "role-revision-1",
            "revision_no": 8,
            "status": "published",
            "version": 2,
            "content_hash": "sha256:role-1",
        },
        ("learning_content", "learning-1"): {
            "learning_content_id": "learning-1",
            "logical_id": "learning-1",
            "revision_id": "learning-revision-1",
            "revision_no": 9,
            "status": "published",
            "version": 3,
            "content_hash": "sha256:learning-1",
        },
        ("examiner_agent", "examiner-1"): {
            "examiner_agent_id": "examiner-1",
            "logical_id": "examiner-1",
            "revision_id": "examiner-revision-1",
            "revision_no": 10,
            "status": "published",
            "version": 4,
            "content_hash": "sha256:examiner-1",
            "question_source_ids": ["question-1"],
        },
        ("question_item", "question-1"): {
            "question_id": "question-1",
            "logical_id": "question-1",
            "revision_id": "question-revision-1",
            "revision_no": 11,
            "status": "published",
            "version": 5,
            "content_hash": "sha256:question-1",
            "safety_flagged": False,
        },
    }

    def reader(asset_type: str, asset_id: str) -> object | None:
        return references.get((asset_type, asset_id))

    return reader


def _situation_repo(*, published: bool = True) -> BusinessRuleConfigSituationPackAdapter:
    pack = SituationPackDTO.from_ruleset_entry(
        DEFAULT_ROLEPLAY_SITUATION_PACKS["packs"][1]
        | {"status": "published" if published else "draft"}
    )
    return BusinessRuleConfigSituationPackAdapter({"first_visit": pack})


def _config_resolution() -> BusinessRuleResolution:
    return BusinessRuleResolution(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        domain="roleplay",
        value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
        source="database",
        config_id="cfg-source-1",
        config_version_id="cfg-version-1",
        version=1,
        status="published",
    )


def _expected_entity_ref(
    *,
    asset_type: str,
    asset_id: str,
    version: str,
    content_hash: str,
    resolved_at: str,
) -> dict[str, object]:
    return {
        "asset_type": asset_type,
        "asset_id": asset_id,
        "asset_code": None,
        "version": version,
        "content_hash": content_hash,
        "snapshot_label": "published",
        "source_bundle_key": None,
        "source_config_version_id": None,
        "source_config_id": None,
        "snapshot_selector": None,
        "source_snapshot_hash": None,
        "resolved_at": resolved_at,
        "logical_id": None,
        "revision_id": None,
        "revision_no": None,
    }


@pytest.mark.asyncio
async def test_should_build_non_empty_published_asset_refs_with_matching_hashes() -> None:
    resolved_at = datetime(2026, 5, 27, 10, 0, tzinfo=UTC).isoformat()
    reader = _reference_reader()
    pack = _situation_repo().get_published("first_visit")
    assert pack is not None

    refs = await build_published_asset_refs(
        _candidate(),
        reference_reader=reader,
        situation_packs=_situation_repo(),
        situation_pack_config=_config_resolution(),
        resolved_at=resolved_at,
    )

    assert set(refs) == {
        "persona_ref",
        "case_item_ref",
        "role_profile_ref",
        "learning_content_ref",
        "scoring_ruleset_ref",
        "examiner_agent_ref",
        "examiner_question_refs",
        "situation_pack_ref",
    }
    assert refs["persona_ref"] == _expected_entity_ref(
        asset_type="persona",
        asset_id="persona-1",
        version="1",
        content_hash=stable_hash(reader("persona", "persona-1")),
        resolved_at=resolved_at,
    )
    assert refs["case_item_ref"]["content_hash"] == "sha256:case-1"
    assert refs["case_item_ref"]["revision_id"] == "case-revision-1"
    assert refs["case_item_ref"]["revision_no"] == 7
    assert refs["role_profile_ref"]["content_hash"] == "sha256:role-1"
    assert refs["role_profile_ref"]["revision_id"] == "role-revision-1"
    assert refs["role_profile_ref"]["revision_no"] == 8
    assert refs["learning_content_ref"]["content_hash"] == "sha256:learning-1"
    assert refs["learning_content_ref"]["revision_id"] == "learning-revision-1"
    assert refs["learning_content_ref"]["revision_no"] == 9
    assert refs["examiner_agent_ref"]["content_hash"] == "sha256:examiner-1"
    assert refs["examiner_agent_ref"]["revision_id"] == "examiner-revision-1"
    assert refs["examiner_agent_ref"]["revision_no"] == 10
    assert refs["examiner_question_refs"]["question-1"]["content_hash"] == "sha256:question-1"
    assert refs["examiner_question_refs"]["question-1"]["revision_id"] == "question-revision-1"
    assert refs["examiner_question_refs"]["question-1"]["revision_no"] == 11
    assert refs["scoring_ruleset_ref"]["content_hash"] == stable_hash(
        reader("scoring_ruleset", "ruleset-1")
    )
    assert refs["situation_pack_ref"] == {
        "asset_type": "situation_pack",
        "asset_id": None,
        "asset_code": "first_visit",
        "version": "v1",
        "content_hash": situation_pack_content_hash(pack),
        "snapshot_label": "published",
        "source_bundle_key": ROLEPLAY_SITUATION_PACKS_KEY,
        "source_config_version_id": "cfg-version-1",
        "source_config_id": "cfg-source-1",
        "snapshot_selector": "packs[code=first_visit]",
        "source_snapshot_hash": stable_hash(DEFAULT_ROLEPLAY_SITUATION_PACKS),
        "resolved_at": resolved_at,
        "logical_id": None,
        "revision_id": None,
        "revision_no": None,
    }

    restored = {
        key: PublishedAssetRefSchema.model_validate(payload).to_dataclass()
        for key, payload in refs.items()
        if key != "examiner_question_refs"
    }
    assert restored["situation_pack_ref"].can_reconstruct_from_snapshot() is True
    restored_question_refs = {
        key: PublishedAssetRefSchema.model_validate(payload).to_dataclass()
        for key, payload in refs["examiner_question_refs"].items()
    }
    assert restored_question_refs["question-1"].asset_type == "question_item"


@pytest.mark.asyncio
async def test_should_build_legacy_situation_pack_ref_when_config_resolution_is_missing() -> None:
    resolved_at = datetime(2026, 5, 27, 10, 0, tzinfo=UTC).isoformat()
    pack = _situation_repo().get_published("first_visit")
    assert pack is not None

    refs = await build_published_asset_refs(
        _candidate(),
        reference_reader=_reference_reader(),
        situation_packs=_situation_repo(),
        situation_pack_config=None,
        resolved_at=resolved_at,
    )

    assert refs["situation_pack_ref"] == {
        "asset_type": "situation_pack",
        "asset_id": None,
        "asset_code": "first_visit",
        "version": "v1",
        "content_hash": situation_pack_content_hash(pack),
        "snapshot_label": "published",
        "source_bundle_key": None,
        "source_config_version_id": None,
        "source_config_id": None,
        "snapshot_selector": None,
        "source_snapshot_hash": None,
        "resolved_at": resolved_at,
        "logical_id": None,
        "revision_id": None,
        "revision_no": None,
    }
    restored = PublishedAssetRefSchema.model_validate(
        refs["situation_pack_ref"]
    ).to_dataclass()
    assert restored.can_reconstruct_from_snapshot() is False


@pytest.mark.asyncio
async def test_should_fail_publish_gate_when_situation_pack_is_unpublished() -> None:
    service = PublishingGateService(
        reference_reader=_reference_reader(),
        situation_packs=_situation_repo(published=False),
    )
    candidate = _candidate()

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert [result.reason_code for result in decision.results] == [
        "situation_pack_missing"
    ]
    assert decision.results[0].gate_name == "situation_pack_compatibility"
