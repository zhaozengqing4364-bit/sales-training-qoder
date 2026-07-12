from __future__ import annotations

import uuid

import pytest

from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import AudioAssessmentActivity
from sales_trainer.services.activity_audio_snapshot_service import (
    ActivityAudioSnapshotService,
)


@pytest.mark.asyncio
async def test_should_freeze_audio_rubric_and_material_without_sales_trainer_unit(
    test_db, test_user
):
    rubric_id = "rubric-product-a"
    revision = SalesTrainerAssetRevision(
        resource_type="audio_scoring_rubric",
        logical_id=rubric_id,
        revision_no=1,
        status="published",
        payload_json={"prompt_id": rubric_id, "dimensions": ["准确性"]},
        payload_hash=uuid.uuid4().hex,
    )
    test_db.add(revision)
    await test_db.flush()
    from sales_trainer.models import SalesTrainerAssetActiveRevision

    test_db.add(
        SalesTrainerAssetActiveRevision(
            resource_type="audio_scoring_rubric",
            logical_id=rubric_id,
            active_revision_id=revision.revision_id,
        )
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
                    "scoring_rubric_id": rubric_id,
                    "material_id": str(material.material_id),
                    "pass_score": 75,
                },
            }
        ),
    )

    snapshots = await ActivityAudioSnapshotService(test_db).freeze(
        context=context, confirmed_material_version_id=str(version.version_id)
    )

    assert snapshots.score_scheme_snapshot["prompt_id"] == rubric_id
    assert snapshots.task_brief_snapshot["activity_id"] == "audio-1"
    assert snapshots.task_brief_snapshot["path_revision_id"] == "path-revision-1"
    assert snapshots.material_snapshot["material_version_id"] == str(version.version_id)
