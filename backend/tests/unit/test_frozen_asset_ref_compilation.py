from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from common.business_rules.defaults import DEFAULT_ROLEPLAY_SITUATION_PACKS
from curriculum_practice.schemas import PublishedTemplateRef
from curriculum_practice.services.asset_references import stable_hash
from curriculum_practice.services.frozen_asset_refs import (
    FrozenAssetRefError,
    FrozenSituationPackResolver,
    parse_published_asset_refs,
)
from curriculum_practice.services.roleplay.adapters.business_rule_config_adapter import (
    BusinessRuleConfigSituationPackAdapter,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.snapshots import (
    RuntimeSnapshotBuildError,
    RuntimeSnapshotService,
)


def _published_template_ref() -> PublishedTemplateRef:
    return PublishedTemplateRef(
        asset_id="template-1",
        version=3,
        hash="sha256:template-hash",
    )


def _frozen_pack_entry(*, label: str = "首次拜访") -> dict[str, object]:
    return deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS["packs"][1]) | {
        "label": label,
        "status": "published",
    }


def _published_template(*, published_asset_refs: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "template_id": "template-1",
        "status": "published",
        "version": 3,
        "content_hash": "sha256:template-hash",
        "scenario_type": "sales",
        "mode": "customer_roleplay",
        "agent_id": "agent-1",
        "persona_id": "persona-1",
        "runtime_profile_id": "runtime-1",
        "voice_mode": "stepfun_realtime",
        "scoring_ruleset_id": "ruleset-1",
        "knowledge_base_refs": ["kb-1"],
        "case_item_id": "case-1",
        "situation_pack_code": "first_visit",
        "published_asset_refs": published_asset_refs,
    }


def _reference_reader(asset_type: str, asset_id: str) -> object | None:
    references: dict[tuple[str, str], object] = {
        ("practice_template", "template-1"): _published_template(
            published_asset_refs=_published_asset_refs()
        ),
        ("scoring_ruleset", "ruleset-1"): {
            "ruleset_id": "ruleset-1",
            "status": "published",
            "version": "2026.05",
            "definition_json": {"dimensions": ["opening", "objection"]},
        },
        ("voice_runtime_profile", "runtime-1"): {
            "id": "runtime-1",
            "is_active": True,
            "voice_mode": "stepfun_realtime",
            "model_name": "step-audio-2",
            "voice_name": "qingchunshaonv",
            "temperature": 0.7,
            "tool_policy": {"web_search": False},
        },
        ("knowledge_base", "kb-1"): {
            "id": "kb-1",
            "status": "active",
            "name": "产品知识库",
            "embedding_model": "text-embedding-ada-002",
        },
        ("case_item", "case-1"): {
            "case_item_id": "case-1",
            "status": "published",
            "version": 1,
            "content_hash": "sha256:case-hash",
            "hidden_information": "绝不能进入运行时快照的隐藏预算",
            "allowed_disclosure_policy": {
                "phases": [{"trigger": "ask_budget", "disclose": "budget"}],
                "roleplay": {"situation_code": "first_visit"},
            },
        },
        ("persona", "persona-1"): {
            "id": "persona-1",
            "status": "active",
            "system_prompt": "保持谨慎客户语气。",
            "persona_policy": {},
        },
    }
    return references.get((asset_type, asset_id))


def _published_asset_refs() -> dict[str, dict[str, object]]:
    frozen_entry = _frozen_pack_entry()
    pack = SituationPackDTO.from_ruleset_entry(frozen_entry)
    snapshot_json = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    ruleset_payload = {
        "ruleset_id": "ruleset-1",
        "status": "published",
        "version": "2026.05",
        "definition_json": {"dimensions": ["opening", "objection"]},
    }
    return {
        "case_item_ref": {
            "asset_type": "case_item",
            "asset_id": "case-1",
            "asset_code": None,
            "version": "1",
            "content_hash": "sha256:case-hash",
            "snapshot_label": "published",
            "source_bundle_key": None,
            "source_config_version_id": None,
            "source_config_id": None,
            "snapshot_selector": None,
            "source_snapshot_hash": None,
            "resolved_at": "2026-05-27T10:00:00+00:00",
        },
        "scoring_ruleset_ref": {
            "asset_type": "scoring_ruleset",
            "asset_id": "ruleset-1",
            "asset_code": None,
            "version": "2026.05",
            "content_hash": stable_hash(ruleset_payload),
            "snapshot_label": "published",
            "source_bundle_key": None,
            "source_config_version_id": None,
            "source_config_id": None,
            "snapshot_selector": None,
            "source_snapshot_hash": None,
            "resolved_at": "2026-05-27T10:00:00+00:00",
        },
        "situation_pack_ref": {
            "asset_type": "situation_pack",
            "asset_id": None,
            "asset_code": "first_visit",
            "version": "v1",
            "content_hash": situation_pack_content_hash(pack),
            "snapshot_label": "published",
            "source_bundle_key": "roleplay.situation_packs.ruleset",
            "source_config_version_id": "cfg-version-1",
            "source_config_id": "cfg-source-1",
            "snapshot_selector": "packs[code=first_visit]",
            "source_snapshot_hash": stable_hash(snapshot_json),
            "resolved_at": "2026-05-27T10:00:00+00:00",
        },
    }


def _live_repo_with_changed_label() -> BusinessRuleConfigSituationPackAdapter:
    changed = SituationPackDTO.from_ruleset_entry(
        _frozen_pack_entry(label="已变更的首次拜访")
    )
    return BusinessRuleConfigSituationPackAdapter({"first_visit": changed})


@pytest.mark.asyncio
async def test_should_compile_roleplay_contract_from_frozen_situation_pack_snapshot() -> None:
    snapshot_json = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)

    async def loader(source_config_id: str) -> dict[str, object] | None:
        assert source_config_id == "cfg-version-1"
        return snapshot_json

    service = RuntimeSnapshotService(
        reference_reader=_reference_reader,
        situation_packs=_live_repo_with_changed_label(),
        frozen_situation_pack_resolver=FrozenSituationPackResolver(
            config_version_loader=loader
        ),
    )

    snapshot = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
    )

    assert snapshot.roleplay_contract is not None
    assert snapshot.roleplay_contract["situation"]["label"] == "首次拜访"
    assert snapshot.content_assets[1].hash == "sha256:case-hash"


@pytest.mark.asyncio
async def test_should_keep_legacy_live_compile_path_without_published_asset_refs() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "practice_template" and asset_id == "template-1":
            template = _published_template(published_asset_refs={})
            return template
        return _reference_reader(asset_type, asset_id)

    live_pack = SituationPackDTO.from_ruleset_entry(_frozen_pack_entry(label="Live Pack"))
    service = RuntimeSnapshotService(
        reference_reader=reference_reader,
        situation_packs=BusinessRuleConfigSituationPackAdapter({"first_visit": live_pack}),
    )

    snapshot = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
    )

    assert snapshot.roleplay_contract is not None
    assert snapshot.roleplay_contract["situation"]["label"] == "Live Pack"


@pytest.mark.asyncio
async def test_should_fail_when_frozen_snapshot_hash_mismatches() -> None:
    refs = _published_asset_refs()
    refs["situation_pack_ref"]["source_snapshot_hash"] = "sha256:stale"

    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "practice_template" and asset_id == "template-1":
            return _published_template(published_asset_refs=refs)
        return _reference_reader(asset_type, asset_id)

    async def loader(_source_config_id: str) -> dict[str, object]:
        return deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)

    service = RuntimeSnapshotService(
        reference_reader=reference_reader,
        situation_packs=_live_repo_with_changed_label(),
        frozen_situation_pack_resolver=FrozenSituationPackResolver(
            config_version_loader=loader
        ),
    )

    with pytest.raises(RuntimeSnapshotBuildError) as exc_info:
        await service.build_for_session(
            template_ref=_published_template_ref(),
            training_task_ref={"id": "task-1", "scenario_type": "sales"},
            actor_id="actor-1",
        )

    assert exc_info.value.reason_code == "snapshot_hash_mismatch"


def test_should_parse_published_asset_refs_from_template_payload() -> None:
    refs = parse_published_asset_refs(_published_asset_refs())

    assert refs["situation_pack_ref"].asset_code == "first_visit"
    assert refs["situation_pack_ref"].can_reconstruct_from_snapshot() is True


@pytest.mark.asyncio
async def test_should_mark_legacy_source_config_id_fallback_when_version_id_is_bad() -> None:
    snapshot_json = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)

    async def version_loader(config_version_id: str) -> dict[str, object] | None:
        assert config_version_id == "cfg-version-1"
        return None

    async def legacy_loader(source_config_id: str) -> dict[str, object] | None:
        assert source_config_id == "cfg-source-1"
        return snapshot_json

    service = RuntimeSnapshotService(
        reference_reader=_reference_reader,
        situation_packs=_live_repo_with_changed_label(),
        frozen_situation_pack_resolver=FrozenSituationPackResolver(
            config_version_loader=version_loader,
            legacy_source_config_loader=legacy_loader,
        ),
    )

    snapshot = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
    )

    assert snapshot.roleplay_contract is not None
    assert snapshot.roleplay_contract["situation"]["label"] == "首次拜访"
    assert snapshot.asset_resolution is not None
    assert (
        snapshot.asset_resolution["frozen_situation_pack_resolution_mode"]
        == "legacy_source_config_id_fallback"
    )


@pytest.mark.asyncio
async def test_should_reject_invalid_snapshot_selector() -> None:
    refs = parse_published_asset_refs(_published_asset_refs())
    ref = refs["situation_pack_ref"]

    async def loader(_source_config_id: str) -> dict[str, object]:
        return deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)

    resolver = FrozenSituationPackResolver(config_version_loader=loader)

    with pytest.raises(FrozenAssetRefError) as exc_info:
        await resolver.resolve(
            replace(ref, snapshot_selector="invalid-selector")
        )

    assert exc_info.value.reason_code == "snapshot_selector_invalid"
