from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    AudioSubmissionCreate,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.audio_submission_service import (
    AudioSubmissionService,
    AudioSubmissionServiceError,
)
from sales_trainer.services.deucate_scoring_service import AudioScoreOutcome
from sales_trainer.services.path_config_models import SalesTrainerPathConfigError
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.transcription_service import TranscriptionResult


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"audio-lineage-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Audio Lineage {role}",
        email=f"audio-lineage-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _published_material(
    admin: User,
    *,
    key_prefix: str,
) -> tuple[SalesTrainerMaterial, SalesTrainerMaterialVersion]:
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key=f"{key_prefix}-{uuid.uuid4().hex[:8]}",
        name=f"{key_prefix} 材料",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label="v1",
        title=f"{key_prefix} v1",
        file_name=f"{key_prefix}.pptx",
        content_type="application/vnd.ms-powerpoint",
        file_size_bytes=1024,
        storage_key=f"/tmp/{key_prefix}.pptx",
        status="published",
        created_by=admin.user_id,
        published_by=admin.user_id,
    )
    material.current_version_id = version.version_id
    return material, version


class _FakeTranscriptionService:
    async def transcribe_file(self, storage_key: str) -> TranscriptionResult:
        return TranscriptionResult(
            provider="fake-asr",
            transcript_text="大家好，今天我介绍石犀的数据流动治理价值。",
            raw_payload={"storage_key": storage_key},
        )


class _CaptureScoringService:
    def __init__(self) -> None:
        self.prompt_id: str | None = None
        self.pass_threshold: int | None = None

    async def score_audio(self, **kwargs) -> AudioScoreOutcome:
        self.prompt_id = kwargs["prompt"].prompt_id
        self.pass_threshold = kwargs["pass_threshold"]
        return AudioScoreOutcome(
            prompt_hash="path-prompt-hash",
            deucate_model="fake-deucate",
            total_score=86,
            passed=True,
            summary="讲解清楚。",
            strengths=["结构完整"],
            improvements=["补充案例"],
            dimension_scores={"structure": 86},
            raw_response={"total_score": 86},
            error_code=None,
            error_message=None,
            latency_ms=10,
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
    material, version = _published_material(admin, key_prefix="lineage-ppt")
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
    test_db.add_all([admin, learner, prompt, material, version, unit])
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
                    material_id=material.material_id,
                    material_version_id=version.version_id,
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
            confirmed_material_version_id=version.version_id,
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
async def test_should_use_path_audio_bindings_when_submitting_and_scoring(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    legacy_prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="旧评分标准",
        purpose="ppt_pitch",
        system_prompt="旧系统提示词。",
        scoring_template="旧评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    path_prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="路径评分标准",
        purpose="ppt_pitch",
        system_prompt="路径系统提示词。",
        scoring_template="路径评分：{transcript}",
        output_schema={},
        learner_rubric={
            "visible_to_learner": True,
            "criteria": [{"key": "structure", "label": "结构", "weight": 40}],
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key=f"ppt-path-{uuid.uuid4().hex[:8]}",
        name="路径 PPT",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label="v-path",
        title="路径 PPT v-path",
        file_name="path.pptx",
        content_type="application/vnd.ms-powerpoint",
        file_size_bytes=1024,
        storage_key="/tmp/path.pptx",
        status="published",
        created_by=admin.user_id,
        published_by=admin.user_id,
    )
    material.current_version_id = version.version_id
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": legacy_prompt.prompt_id,
                "pass_threshold": 73,
                "purpose": "ppt_pitch",
            },
            "task_brief": {"title": "PPT 讲解", "purpose": "讲清主胶片。"},
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, legacy_prompt, path_prompt, material, version, unit])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="路径配置接管 PPT 录音绑定",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解录音",
                    target_unit_id=unit.unit_id,
                    material_id=material.material_id,
                    material_version_id=version.version_id,
                    scoring_prompt_id=path_prompt.prompt_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )
    await path_service.publish_config(actor=admin, reason="路径配置生效")

    scoring = _CaptureScoringService()
    audio_service = AudioSubmissionService(
        test_db,
        transcription_service=_FakeTranscriptionService(),
        scoring_service=scoring,
    )
    with pytest.raises(AudioSubmissionServiceError) as missing_confirmation:
        await audio_service.create_submission(
            AudioSubmissionCreate(
                unit_id=unit.unit_id,
                purpose="ppt_pitch",
                original_filename="ppt.wav",
                content_type="audio/wav",
                size_bytes=1024,
                storage_key="/tmp/ppt.wav",
                auto_process=False,
            ),
            actor=learner,
        )
    assert getattr(missing_confirmation.value, "code", None) == (
        "[MATERIAL_VERSION_CONFIRMATION_REQUIRED]"
    )

    submission = await audio_service.create_submission(
        AudioSubmissionCreate(
            unit_id=unit.unit_id,
            purpose="ppt_pitch",
            original_filename="ppt.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/ppt.wav",
            confirmed_material_version_id=version.version_id,
            auto_process=False,
        ),
        actor=learner,
    )
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="发布第二版评分绑定",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解录音",
                    target_unit_id=unit.unit_id,
                    material_id=material.material_id,
                    material_version_id=version.version_id,
                    scoring_prompt_id=legacy_prompt.prompt_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )
    await path_service.publish_config(actor=admin, reason="第二版路径配置生效")
    submission = await audio_service.process_submission(
        submission.submission_id,
        actor=learner,
    )
    serialized = await audio_service.serialize_submission(submission)

    assert scoring.prompt_id == path_prompt.prompt_id
    assert scoring.pass_threshold == 73
    assert serialized["score_scheme_snapshot"]["prompt_id"] == path_prompt.prompt_id
    assert serialized["material_snapshot"]["items"][0]["material_id"] == material.material_id
    assert serialized["score_result"]["prompt_id"] == path_prompt.prompt_id
    assert serialized["score_result"]["legacy_snapshot_only"] is False


@pytest.mark.asyncio
async def test_should_use_effective_path_config_for_unit_brief_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    legacy_prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="旧评分标准",
        purpose="ppt_pitch",
        system_prompt="旧系统提示词。",
        scoring_template="旧评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    path_prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="路径评分标准",
        purpose="ppt_pitch",
        system_prompt="路径系统提示词。",
        scoring_template="路径评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    material, version = _published_material(admin, key_prefix="brief-path")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": legacy_prompt.prompt_id,
                "pass_threshold": 75,
                "purpose": "ppt_pitch",
            },
            "task_brief": {"title": "PPT 讲解", "purpose": "讲清主胶片。"},
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, legacy_prompt, path_prompt, material, version, unit])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="路径配置接管 brief",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解录音",
                    target_unit_id=unit.unit_id,
                    material_id=material.material_id,
                    material_version_id=version.version_id,
                    scoring_prompt_id=path_prompt.prompt_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )
    await path_service.publish_config(actor=admin, reason="路径配置生效")

    response = await async_client.get(
        f"/api/v1/sales-trainer/units/{unit.unit_id}/brief",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["score_scheme"]["prompt_id"] == path_prompt.prompt_id
    assert data["materials"][0]["material_id"] == material.material_id
    assert data["materials"][0]["current_version"]["version_id"] == version.version_id


@pytest.mark.asyncio
async def test_should_reject_publishing_audio_path_without_effective_prompt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="audio_scoring",
        config={"audio": {"purpose": "general_audio_scoring"}},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, unit])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="缺少评分标准",
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

    with pytest.raises(SalesTrainerPathConfigError) as exc:
        await path_service.publish_config(actor=admin, reason="应拒绝")

    assert exc.value.code == "[NEWCOMER_MODULE_BINDING_MISSING]"


@pytest.mark.asyncio
async def test_should_reject_audio_group_without_duration_options(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="电梯演讲评分",
        purpose="elevator_pitch",
        system_prompt="你是电梯演讲评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, prompt])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="缺少时长档位",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="elevator_pitch",
                    module_type="audio_scoring_group",
                    enabled=True,
                    order_index=3,
                    title="电梯演讲",
                    scoring_prompt_id=prompt.prompt_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )

    with pytest.raises(SalesTrainerPathConfigError) as exc:
        await path_service.publish_config(actor=admin, reason="应拒绝")

    assert exc.value.code == "[NEWCOMER_MODULE_BINDING_MISSING]"


@pytest.mark.asyncio
async def test_should_expand_audio_group_duration_options_and_score_with_group_prompt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="电梯演讲评分",
        purpose="elevator_pitch",
        system_prompt="你是电梯演讲评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit_10 = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="电梯演讲 10 分钟",
        unit_type="audio_scoring",
        config={"audio": {"purpose": "elevator_pitch", "pass_threshold": 70}},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit_20 = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="电梯演讲 20 分钟",
        unit_type="audio_scoring",
        config={"audio": {"purpose": "elevator_pitch", "pass_threshold": 70}},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, prompt, unit_10, unit_20])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定电梯演讲时长档位",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="elevator_pitch",
                    module_type="audio_scoring_group",
                    enabled=True,
                    order_index=3,
                    title="电梯演讲",
                    scoring_prompt_id=prompt.prompt_id,
                    completion_rule="scored",
                    duration_options=[
                        {
                            "option_key": "pitch_10m",
                            "display_name": "10 分钟",
                            "duration_minutes": 10,
                            "target_unit_id": unit_10.unit_id,
                            "order_index": 1,
                        },
                        {
                            "option_key": "pitch_20m",
                            "display_name": "20 分钟",
                            "duration_minutes": 20,
                            "target_unit_id": unit_20.unit_id,
                            "order_index": 2,
                        },
                    ],
                )
            ],
        ),
        actor=admin,
    )
    publish_result = await path_service.publish_config(
        actor=admin,
        reason="电梯演讲路径生效",
    )

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(str(learner.user_id))
    levels = paths[0]["levels"]
    assert [level["unit_id"] for level in levels] == [unit_10.unit_id, unit_20.unit_id]
    assert [level["level_title"] for level in levels] == ["10 分钟", "20 分钟"]
    assert {level["module_type"] for level in levels} == {"audio_scoring_group"}

    scoring = _CaptureScoringService()
    audio_service = AudioSubmissionService(
        test_db,
        transcription_service=_FakeTranscriptionService(),
        scoring_service=scoring,
    )
    submission = await audio_service.create_submission(
        AudioSubmissionCreate(
            unit_id=unit_20.unit_id,
            purpose="elevator_pitch",
            original_filename="pitch-20.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/pitch-20.wav",
            auto_process=False,
        ),
        actor=learner,
    )
    submission = await audio_service.process_submission(
        submission.submission_id,
        actor=learner,
    )
    serialized = await audio_service.serialize_submission(submission)

    assert scoring.prompt_id == prompt.prompt_id
    assert serialized["path_revision_id"] == str(publish_result.revision.revision_id)
    assert serialized["module_key"] == "elevator_pitch"
    assert serialized["score_scheme_snapshot"]["prompt_id"] == prompt.prompt_id


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
    material, version = _published_material(admin, key_prefix="score-result-ppt")
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
    test_db.add_all([admin, learner, prompt, material, version, unit])
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
                    material_id=material.material_id,
                    material_version_id=version.version_id,
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
            confirmed_material_version_id=version.version_id,
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
