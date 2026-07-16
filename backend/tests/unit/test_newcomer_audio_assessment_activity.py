from __future__ import annotations

import uuid

import pytest

from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import AudioAssessmentActivity
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.services.activity_audio_snapshot_service import (
    ActivityAudioSnapshotService,
)
from sales_trainer.services.prompt_revision_payloads import PROMPT_RESOURCE_TYPE


async def _published_prompt(test_db, *, prompt_id: str, actor_id: str) -> tuple[
    SalesTrainerAudioScorePrompt, SalesTrainerAssetRevision
]:
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=prompt_id,
        name="产品 A 讲解评分",
        purpose="general_audio_scoring",
        system_prompt="你是销售训练录音评分专家。",
        scoring_template="请评分。\n{transcript}",
        output_schema={},
        learner_rubric={
            "visible_to_learner": True,
            "pass_threshold": 75,
            "criteria": [
                {
                    "key": "accuracy",
                    "label": "内容准确",
                    "description": "关键信息完整",
                    "weight": 1,
                }
            ],
            "common_mistakes": [],
        },
        version=1,
        status="published",
        created_by=actor_id,
        updated_by=actor_id,
    )
    test_db.add(prompt)
    await test_db.flush()
    revision = SalesTrainerAssetRevision(
        resource_type=PROMPT_RESOURCE_TYPE,
        logical_id=prompt_id,
        revision_no=1,
        status="published",
        payload_json={
            "prompt_id": prompt_id,
            "name": prompt.name,
            "purpose": prompt.purpose,
            "system_prompt": prompt.system_prompt,
            "scoring_template": prompt.scoring_template,
            "output_schema": {},
            "learner_rubric": prompt.learner_rubric,
            "version": 1,
            "status": "published",
        },
        payload_hash=uuid.uuid4().hex,
    )
    test_db.add(revision)
    await test_db.flush()
    test_db.add(
        SalesTrainerAssetActiveRevision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=prompt_id,
            active_revision_id=revision.revision_id,
        )
    )
    await test_db.flush()
    return prompt, revision


@pytest.mark.asyncio
async def test_should_freeze_audio_prompt_and_material_without_sales_trainer_unit(
    test_db, test_user
):
    prompt_id = "prompt-product-a"
    _, revision = await _published_prompt(
        test_db, prompt_id=prompt_id, actor_id=str(test_user.user_id)
    )
    material = SalesTrainerMaterial(
        material_key="product-a-demo",
        name="产品 A Demo",
        status="published",
    )
    test_db.add(material)
    await test_db.flush()
    version = SalesTrainerMaterialVersion(
        material_id=material.material_id,
        version_label="v1",
        title="产品 A Demo v1",
        file_name="demo.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes=100,
        storage_key="test/demo.pptx",
        file_hash="hash-v1",
        status="published",
    )
    test_db.add(version)
    await test_db.flush()
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        phase_id="phase-1",
        module_id="product-a",
        activity=AudioAssessmentActivity.model_validate(
            {
                "activity_id": "audio-1",
                "type": "audio_assessment",
                "title": "讲解产品 A",
                "order_index": 1,
                "config": {
                    "scoring_rubric_id": prompt_id,
                    "material_id": str(material.material_id),
                    "pass_score": 75,
                },
            }
        ),
    )

    snapshots = await ActivityAudioSnapshotService(test_db).freeze(
        context=context,
        confirmed_material_version_id=str(version.version_id),
        confirmed_scoring_rubric_revision_id=str(revision.revision_id),
    )

    assert snapshots.score_scheme_snapshot["prompt_id"] == prompt_id
    assert snapshots.score_scheme_snapshot["prompt_snapshot"]["system_prompt"]
    assert (
        "{transcript}"
        in snapshots.score_scheme_snapshot["prompt_snapshot"]["scoring_template"]
    )
    assert snapshots.score_scheme_snapshot["rubric_revision_id"] == str(
        revision.revision_id
    )
    assert snapshots.task_brief_snapshot["activity_id"] == "audio-1"
    assert snapshots.task_brief_snapshot["path_revision_id"] == "path-revision-1"
    assert snapshots.material_snapshot["material_version_id"] == str(version.version_id)


@pytest.mark.asyncio
async def test_should_freeze_current_published_prompt_when_revision_unconfirmed(
    test_db, test_user
):
    """Legacy clients omit confirmed_scoring_rubric_revision_id; still freeze prompt."""
    prompt_id = "prompt-product-b"
    prompt, revision = await _published_prompt(
        test_db, prompt_id=prompt_id, actor_id=str(test_user.user_id)
    )
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        phase_id="phase-1",
        module_id="product-b",
        activity=AudioAssessmentActivity.model_validate(
            {
                "activity_id": "audio-2",
                "type": "audio_assessment",
                "title": "讲解产品 B",
                "order_index": 1,
                "config": {
                    "scoring_rubric_id": prompt_id,
                    "pass_score": 80,
                },
            }
        ),
    )

    snapshots = await ActivityAudioSnapshotService(test_db).freeze(
        context=context,
        confirmed_material_version_id=None,
        confirmed_scoring_rubric_revision_id=None,
    )

    assert snapshots.material_snapshot is None
    assert snapshots.score_scheme_snapshot["prompt_id"] == prompt_id
    assert snapshots.score_scheme_snapshot["prompt_snapshot"]["prompt_id"] == prompt_id
    assert (
        snapshots.score_scheme_snapshot["prompt_snapshot"]["system_prompt"]
        == prompt.system_prompt
    )
    assert (
        "{transcript}"
        in snapshots.score_scheme_snapshot["prompt_snapshot"]["scoring_template"]
    )
    assert snapshots.score_scheme_snapshot["rubric_revision_id"] == str(
        revision.revision_id
    )


@pytest.mark.asyncio
async def test_should_reject_legacy_audio_scoring_rubric_binding(test_db, test_user):
    revision = SalesTrainerAssetRevision(
        resource_type="audio_scoring_rubric",
        logical_id="rubric-legacy",
        revision_no=1,
        status="published",
        payload_json={"title": "旧评分标准", "dimensions": ["准确性"]},
        payload_hash=uuid.uuid4().hex,
    )
    test_db.add(revision)
    await test_db.flush()
    test_db.add(
        SalesTrainerAssetActiveRevision(
            resource_type="audio_scoring_rubric",
            logical_id="rubric-legacy",
            active_revision_id=revision.revision_id,
        )
    )
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        phase_id="phase-1",
        module_id="product-a",
        activity=AudioAssessmentActivity.model_validate(
            {
                "activity_id": "audio-1",
                "type": "audio_assessment",
                "title": "讲解产品 A",
                "order_index": 1,
                "config": {
                    "scoring_rubric_id": "rubric-legacy",
                    "pass_score": 75,
                },
            }
        ),
    )

    with pytest.raises(NewcomerOrchestrationError) as exc_info:
        await ActivityAudioSnapshotService(test_db).freeze(
            context=context,
            confirmed_material_version_id=None,
        )

    assert exc_info.value.code == "[NEWCOMER_AUDIO_RUBRIC_NOT_PUBLISHED]"
    assert "重新选择" in exc_info.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resource_type", "logical_id", "status"),
    [
        (PROMPT_RESOURCE_TYPE, "prompt-other", "published"),
        ("audio_scoring_rubric", "prompt-product-a", "published"),
        (PROMPT_RESOURCE_TYPE, "prompt-product-a", "working"),
    ],
)
async def test_should_reject_untrusted_confirmed_rubric_revision(
    test_db,
    test_user,
    resource_type: str,
    logical_id: str,
    status: str,
):
    await _published_prompt(
        test_db, prompt_id="prompt-product-a", actor_id=str(test_user.user_id)
    )
    revision = SalesTrainerAssetRevision(
        resource_type=resource_type,
        logical_id=logical_id,
        revision_no=2,
        status=status,
        payload_json={
            "prompt_id": logical_id,
            "system_prompt": "x",
            "scoring_template": "{transcript}",
        },
        payload_hash=uuid.uuid4().hex,
    )
    test_db.add(revision)
    await test_db.flush()
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        phase_id="phase-1",
        module_id="product-a",
        activity=AudioAssessmentActivity.model_validate(
            {
                "activity_id": "audio-1",
                "type": "audio_assessment",
                "title": "讲解产品 A",
                "order_index": 1,
                "config": {
                    "scoring_rubric_id": "prompt-product-a",
                    "pass_score": 75,
                },
            }
        ),
    )

    with pytest.raises(NewcomerOrchestrationError) as exc_info:
        await ActivityAudioSnapshotService(test_db).freeze(
            context=context,
            confirmed_material_version_id=None,
            confirmed_scoring_rubric_revision_id=str(revision.revision_id),
        )

    assert exc_info.value.code == "[NEWCOMER_AUDIO_RUBRIC_VERSION_INVALID]"
    assert exc_info.value.status_code == 409
