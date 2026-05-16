from __future__ import annotations

from json import dumps

import pytest

from curriculum_practice.schemas import PublishedTemplateRef
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


def _published_template() -> dict[str, object]:
    return {
        "template_id": "template-1",
        "status": "published",
        "version": 3,
        "content_hash": "sha256:template-hash",
        "scenario_type": "sales",
        "agent_id": "agent-1",
        "persona_id": "persona-1",
        "runtime_profile_id": "runtime-1",
        "voice_mode": "stepfun_realtime",
        "scoring_ruleset_id": "ruleset-1",
        "knowledge_base_refs": ["kb-1"],
    }


def _reference_reader(asset_type: str, asset_id: str) -> object | None:
    references: dict[tuple[str, str], object] = {
        ("practice_template", "template-1"): _published_template(),
        ("practice_template", "child-template-1"): {
            "template_id": "child-template-1",
            "status": "published",
            "version": 1,
            "content_hash": "sha256:child-template-hash",
            "scenario_type": "sales",
            "mode": "customer_roleplay",
            "agent_id": "agent-1",
            "persona_id": "persona-1",
            "runtime_profile_id": "runtime-1",
            "voice_mode": "stepfun_realtime",
            "scoring_ruleset_id": "ruleset-1",
            "knowledge_base_refs": ["kb-1"],
            "case_item_id": "case-1",
        },
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
        },
        ("learning_content", "learning-1"): {
            "learning_content_id": "learning-1",
            "status": "published",
            "version": 2,
            "content_hash": "sha256:learning-hash",
            "title": "不应冻结的正文标题之外内容",
        },
    }
    return references.get((asset_type, asset_id))


@pytest.mark.asyncio
async def test_should_generate_same_snapshot_hash_when_input_is_same() -> None:
    service = RuntimeSnapshotService(reference_reader=_reference_reader)

    first = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
        trace_id="trace-1",
        created_at="2026-05-11T10:00:00Z",
    )
    second = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-2",
        trace_id="trace-2",
        created_at="2026-05-12T10:00:00Z",
    )

    assert first.snapshot_hash == second.snapshot_hash
    assert first.snapshot_hash.startswith("sha256:")


@pytest.mark.asyncio
async def test_should_fail_with_stable_error_when_template_is_unpublished() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "practice_template":
            return _published_template() | {"status": "draft"}
        return _reference_reader(asset_type, asset_id)

    service = RuntimeSnapshotService(reference_reader=reference_reader)

    with pytest.raises(RuntimeSnapshotBuildError) as exc_info:
        await service.build_for_session(
            template_ref=_published_template_ref(),
            training_task_ref={"id": "task-1", "scenario_type": "sales"},
            actor_id="actor-1",
        )

    assert exc_info.value.reason_code == "template_unpublished"


@pytest.mark.parametrize(
    ("reference_overrides", "template_ref", "expected_reason"),
    [
        (
            {("scoring_ruleset", "ruleset-1"): None},
            _published_template_ref(),
            "rubric_missing",
        ),
        (
            {("voice_runtime_profile", "runtime-1"): None},
            _published_template_ref(),
            "voice_policy_unavailable",
        ),
        (
            {},
            PublishedTemplateRef(
                asset_id="template-1", version=3, hash="sha256:stale-hash"
            ),
            "asset_hash_mismatch",
        ),
        (
            {("knowledge_base", "kb-1"): {"id": "kb-1", "status": "archived"}},
            _published_template_ref(),
            "asset_unpublished",
        ),
    ],
)
@pytest.mark.asyncio
async def test_should_fail_with_stable_error_when_snapshot_dependency_is_invalid(
    reference_overrides: dict[tuple[str, str], object | None],
    template_ref: PublishedTemplateRef,
    expected_reason: str,
) -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        key = (asset_type, asset_id)
        if key in reference_overrides:
            return reference_overrides[key]
        return _reference_reader(asset_type, asset_id)

    service = RuntimeSnapshotService(reference_reader=reference_reader)

    with pytest.raises(RuntimeSnapshotBuildError) as exc_info:
        await service.build_for_session(
            template_ref=template_ref,
            training_task_ref={"id": "task-1", "scenario_type": "sales"},
            actor_id="actor-1",
        )

    assert exc_info.value.reason_code == expected_reason


@pytest.mark.asyncio
async def test_should_store_version_refs_and_hashes_without_large_text_blobs() -> None:
    large_text = "敏感话术正文" * 30_000

    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "voice_runtime_profile":
            reference = _reference_reader(asset_type, asset_id)
            assert isinstance(reference, dict)
            return reference | {"system_instruction_template": large_text}
        if asset_type == "knowledge_base":
            reference = _reference_reader(asset_type, asset_id)
            assert isinstance(reference, dict)
            return reference | {"document_body": large_text}
        return _reference_reader(asset_type, asset_id)

    service = RuntimeSnapshotService(reference_reader=reference_reader)

    snapshot = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
    )
    payload = snapshot.model_dump()
    encoded = dumps(payload, ensure_ascii=False)

    assert snapshot.practice_template.model_dump() == {
        "asset_type": "practice_template",
        "asset_id": "template-1",
        "version": 3,
        "hash": "sha256:template-hash",
        "snapshot_label": "published",
    }
    assert snapshot.rubric.asset_type == "scoring_ruleset"
    assert snapshot.content_assets[0].asset_type == "knowledge_base"
    assert "敏感话术正文" not in encoded
    assert len(encoded.encode("utf-8")) < 256 * 1024


@pytest.mark.asyncio
async def test_should_include_stage_snapshots_without_hidden_information() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if (asset_type, asset_id) == ("practice_template", "template-1"):
            return _published_template() | {
                "curriculum_plan": {
                    "name": "多阶段训练",
                    "stages": [
                        {
                            "template_stage_key": "template_stage_opening",
                            "order": 1,
                            "name": "开场",
                            "template_ref": {
                                "asset_type": "practice_template",
                                "asset_id": "child-template-1",
                                "version": 1,
                                "hash": "sha256:child-template-hash",
                                "snapshot_label": "published",
                            },
                            "completion_policy": {
                                "min_score": 7.0,
                                "min_rounds": 2,
                                "max_duration_seconds": 600,
                            },
                            "failure_policy": "retry_current",
                            "prerequisites": [],
                        }
                    ],
                }
            }
        return _reference_reader(asset_type, asset_id)

    service = RuntimeSnapshotService(reference_reader=reference_reader)

    snapshot = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
    )
    encoded = dumps(snapshot.model_dump(), ensure_ascii=False)

    stage_snapshot = snapshot.stage_snapshots["template_stage_opening"]
    assert stage_snapshot.template_ref.asset_id == "child-template-1"
    assert stage_snapshot.runtime_payload == {
        "template_id": "child-template-1",
        "version": 1,
        "content_hash": "sha256:child-template-hash",
        "mode": "customer_roleplay",
        "scenario_type": "sales",
        "agent_id": "agent-1",
        "persona_id": "persona-1",
        "runtime_profile_id": "runtime-1",
        "voice_mode": "stepfun_realtime",
        "scoring_ruleset_id": "ruleset-1",
    }
    assert stage_snapshot.content_assets[0].asset_type == "knowledge_base"
    assert stage_snapshot.content_assets[1].asset_type == "case_item"
    assert "hidden_information" not in encoded
    assert "隐藏预算" not in encoded


@pytest.mark.asyncio
async def test_should_freeze_study_stage_asset_and_learner_level() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if (asset_type, asset_id) == ("practice_template", "template-1"):
            return _published_template() | {
                "curriculum_plan": {
                    "name": "学习考试闭环",
                    "stages": [
                        {
                            "template_stage_key": "study_stage",
                            "stage_type": "study",
                            "order": 1,
                            "name": "学习",
                            "template_ref": {
                                "asset_type": "learning_content",
                                "asset_id": "learning-1",
                                "version": 2,
                                "hash": "sha256:learning-hash",
                                "snapshot_label": "published",
                            },
                            "completion_policy": {
                                "min_score": 0,
                                "min_rounds": 0,
                                "max_duration_seconds": 300,
                            },
                        }
                    ],
                }
            }
        return _reference_reader(asset_type, asset_id)

    service = RuntimeSnapshotService(reference_reader=reference_reader)

    snapshot = await service.build_for_session(
        template_ref=_published_template_ref(),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
        learner_level="beginner",
    )

    assert snapshot.learner_level == "beginner"
    stage_snapshot = snapshot.stage_snapshots["study_stage"]
    assert stage_snapshot.runtime_payload == {
        "stage_type": "study",
        "asset_type": "learning_content",
        "asset_id": "learning-1",
        "version": 2,
        "content_hash": "sha256:learning-hash",
    }
    assert stage_snapshot.content_assets[0].asset_type == "learning_content"
