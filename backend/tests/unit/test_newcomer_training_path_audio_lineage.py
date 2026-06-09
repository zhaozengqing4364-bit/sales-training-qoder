from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    AudioSubmissionCreate,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.audio_submission_service import AudioSubmissionService
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"audio-lineage-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Audio Lineage {role}",
        email=f"audio-lineage-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_should_freeze_path_revision_lineage_when_submitting_audio(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="PPT 讲解评分",
        purpose="general_audio_scoring",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": prompt.prompt_id,
                "pass_threshold": 80,
                "purpose": "general_audio_scoring",
            }
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, prompt, unit])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定 PPT 讲解录音",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解录音",
                    target_unit_id=unit.unit_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )
    publish_result = await path_service.publish_config(
        actor=admin,
        reason="PPT 讲解路径生效",
    )

    audio_service = AudioSubmissionService(test_db)
    submission = await audio_service.create_submission(
        AudioSubmissionCreate(
            unit_id=unit.unit_id,
            purpose="general_audio_scoring",
            original_filename="ppt-explanation.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/ppt-explanation.wav",
            source_page="sales_trainer_unit_detail",
            auto_process=False,
        ),
        actor=learner,
    )
    serialized = await audio_service.serialize_submission(submission)
    task_brief_snapshot = serialized["task_brief_snapshot"]
    assert isinstance(task_brief_snapshot, dict)
    submission_context = task_brief_snapshot["submission_context"]
    assert isinstance(submission_context, dict)

    assert serialized["path_revision_id"] == str(publish_result.revision.revision_id)
    assert serialized["path_revision_no"] == 1
    assert serialized["path_key"] == "newcomer_training_path_v1"
    assert serialized["module_key"] == "ppt_explanation"
    assert serialized["legacy_snapshot_only"] is False
    assert submission_context["path_revision_id"] == serialized["path_revision_id"]
    assert submission_context["module_type"] == "audio_scoring"


@pytest.mark.asyncio
async def test_should_expose_audio_score_result_path_revision_lineage(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="PPT 讲解评分",
        purpose="general_audio_scoring",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": prompt.prompt_id,
                "pass_threshold": 80,
                "purpose": "general_audio_scoring",
            }
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, prompt, unit])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定 PPT 讲解录音",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解录音",
                    target_unit_id=unit.unit_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )
    publish_result = await path_service.publish_config(
        actor=admin,
        reason="PPT 讲解路径生效",
    )

    audio_service = AudioSubmissionService(test_db)
    submission = await audio_service.create_submission(
        AudioSubmissionCreate(
            unit_id=unit.unit_id,
            purpose="general_audio_scoring",
            original_filename="ppt-explanation.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/ppt-explanation.wav",
            source_page="sales_trainer_unit_detail",
            auto_process=False,
        ),
        actor=learner,
    )
    score = SalesTrainerAudioScoreResult(
        submission_id=submission.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="prompt-hash",
        transcript_snapshot="大家好，下面介绍产品。",
        total_score=88,
        passed=True,
        summary="表达清楚。",
        strengths=[],
        improvements=[],
        dimension_scores={},
    )
    test_db.add(score)
    await test_db.commit()
    await test_db.refresh(score)

    serialized = await audio_service.serialize_score_result(score)

    assert serialized["path_revision_id"] == str(publish_result.revision.revision_id)
    assert serialized["path_revision_no"] == 1
    assert serialized["path_key"] == "newcomer_training_path_v1"
    assert serialized["module_key"] == "ppt_explanation"
    assert serialized["legacy_snapshot_only"] is False
