from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    AudioSubmissionCreate,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.audio_submission_service import AudioSubmissionService
from sales_trainer.services.deucate_scoring_service import AudioScoreOutcome
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.path_progress_service import load_latest_audio_progress
from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.transcription_service import TranscriptionResult


class _Transcription:
    async def transcribe_file(self, storage_key: str) -> TranscriptionResult:
        return TranscriptionResult(
            provider="fake-asr",
            transcript_text="我会按公司最新材料讲清产品价值。",
            raw_payload={"storage_key": storage_key},
        )


class _PassingScoring:
    async def score_audio(self, **_kwargs) -> AudioScoreOutcome:
        return AudioScoreOutcome(
            prompt_hash="persisted-unlock-hash",
            deucate_model="fake-deucate",
            total_score=88,
            passed=True,
            summary="表达清楚。",
            strengths=["结构完整"],
            improvements=[],
            dimension_scores={"structure": 88},
            raw_response={"total_score": 88},
            error_code=None,
            error_message=None,
            latency_ms=1,
        )


def _user(role: str) -> User:
    token = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"persisted-unlock-{role}-{token}",
        name=f"Persisted Unlock {role}",
        email=f"persisted-unlock-{role}-{token}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_persisted_audio_pass_unlocks_next_level_in_a_new_session(
    test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as seed_db:
        admin = _user("admin")
        learner = _user("user")
        ppt_prompt = SalesTrainerAudioScorePrompt(
            prompt_id=str(uuid.uuid4()),
            name="PPT 讲解评分",
            purpose="ppt_pitch",
            system_prompt="请评分。",
            scoring_template="{transcript}",
            output_schema={},
            status="published",
            created_by=admin.user_id,
            updated_by=admin.user_id,
        )
        elevator_prompt = SalesTrainerAudioScorePrompt(
            prompt_id=str(uuid.uuid4()),
            name="电梯演讲评分",
            purpose="elevator_pitch",
            system_prompt="请评分。",
            scoring_template="{transcript}",
            output_schema={},
            status="published",
            created_by=admin.user_id,
            updated_by=admin.user_id,
        )
        material = SalesTrainerMaterial(
            material_id=str(uuid.uuid4()),
            material_key=f"persisted-unlock-{uuid.uuid4().hex[:8]}",
            name="PPT 材料",
            material_type="ppt_deck",
            purpose="ppt_pitch",
            status="published",
            created_by=admin.user_id,
            updated_by=admin.user_id,
        )
        material_version = SalesTrainerMaterialVersion(
            version_id=str(uuid.uuid4()),
            material_id=material.material_id,
            version_label="v1",
            title="PPT 材料 v1",
            file_name="persisted-unlock.pptx",
            content_type="application/vnd.ms-powerpoint",
            file_size_bytes=1024,
            storage_key="/tmp/persisted-unlock.pptx",
            status="published",
            created_by=admin.user_id,
            published_by=admin.user_id,
        )
        material.current_version_id = material_version.version_id
        first_unit = SalesTrainerUnit(
            unit_id=str(uuid.uuid4()),
            name="第一关：PPT 讲解",
            unit_type="audio_scoring",
            config={
                "audio": {
                    "scenario_key": "ppt_explanation",
                    "purpose": "ppt_pitch",
                    "scoring_prompt_id": ppt_prompt.prompt_id,
                    "pass_threshold": 80,
                },
                "materials": {
                    "bindings": [
                        {
                            "material_id": material.material_id,
                            "locked_version_id": material_version.version_id,
                            "version_policy": "locked_version",
                        }
                    ]
                },
            },
            status="published",
            created_by=admin.user_id,
            updated_by=admin.user_id,
        )
        second_unit = SalesTrainerUnit(
            unit_id=str(uuid.uuid4()),
            name="第二关：电梯演讲",
            unit_type="audio_scoring",
            config={
                "audio": {
                    "scenario_key": "elevator_pitch",
                    "purpose": "elevator_pitch",
                    "scoring_prompt_id": elevator_prompt.prompt_id,
                    "pass_threshold": 80,
                }
            },
            status="published",
            created_by=admin.user_id,
            updated_by=admin.user_id,
        )
        seed_db.add_all(
            [
                admin,
                learner,
                ppt_prompt,
                elevator_prompt,
                material,
                material_version,
                first_unit,
                second_unit,
            ]
        )
        await seed_db.commit()

        path_config = SalesTrainerPathConfigService(seed_db)
        await path_config.save_config(
            NewcomerPathConfigSaveRequest(
                title="新人训练路径",
                reason="持久化解锁跨 session 证明",
                modules=[
                    NewcomerPathModuleConfig(
                        module_key="ppt_explanation",
                        scenario_key="ppt_explanation",
                        module_type="audio_scoring",
                        enabled=True,
                        order_index=1,
                        title=first_unit.name,
                        target_unit_id=first_unit.unit_id,
                        material_id=material.material_id,
                        material_version_id=material_version.version_id,
                        scoring_prompt_id=ppt_prompt.prompt_id,
                        completion_rule="passed",
                    ),
                    NewcomerPathModuleConfig(
                        module_key="elevator_pitch",
                        scenario_key="elevator_pitch",
                        module_type="audio_scoring_group",
                        enabled=True,
                        order_index=2,
                        title=second_unit.name,
                        scoring_prompt_id=elevator_prompt.prompt_id,
                        unlock_after_unit_ids=[first_unit.unit_id],
                        completion_rule="passed",
                        duration_options=[
                            {
                                "option_key": "pitch_10m",
                                "display_name": "10 分钟",
                                "duration_minutes": 10,
                                "target_unit_id": second_unit.unit_id,
                                "order_index": 1,
                            }
                        ],
                    ),
                ],
            ),
            actor=admin,
        )
        publish_result = await path_config.publish_config(
            actor=admin,
            reason="持久化解锁路径生效",
        )

        before = await SalesTrainerPathService(seed_db).list_paths_for_user(
            str(learner.user_id)
        )
        assert before[0]["current_level_id"] == str(first_unit.unit_id)
        assert before[0]["levels"][1]["status"] == "locked"

        audio = AudioSubmissionService(
            seed_db,
            transcription_service=_Transcription(),
            scoring_service=_PassingScoring(),
        )
        submission = await audio.create_submission(
            AudioSubmissionCreate(
                unit_id=str(first_unit.unit_id),
                purpose="ppt_pitch",
                original_filename="persisted-unlock.wav",
                content_type="audio/wav",
                size_bytes=1024,
                storage_key="/tmp/persisted-unlock.wav",
                confirmed_material_version_id=str(material_version.version_id),
                auto_process=False,
            ),
            actor=learner,
        )
        submission = await audio.process_submission(
            str(submission.submission_id),
            actor=learner,
        )
        await seed_db.commit()
        learner_id = str(learner.user_id)
        first_unit_id = str(first_unit.unit_id)
        second_unit_id = str(second_unit.unit_id)
        revision_id = str(publish_result.revision.revision_id)

    async with factory() as fresh_db:
        after = await SalesTrainerPathService(fresh_db).list_paths_for_user(learner_id)

    assert submission.status == "scored"
    assert after[0]["path_revision_id"] == revision_id
    assert after[0]["completed_levels"] == 1
    assert after[0]["levels"][0]["unit_id"] == first_unit_id
    assert after[0]["levels"][0]["status"] == "completed"
    assert after[0]["levels"][1]["unit_id"] == second_unit_id
    assert after[0]["levels"][1]["status"] == "available"
    assert after[0]["current_level_id"] == second_unit_id
    assert after[0]["next_level_id"] == second_unit_id


@pytest.mark.asyncio
async def test_latest_audio_attempt_wins_for_path_progress(
    test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        user = _user("user")
        unit_id = str(uuid.uuid4())
        prompt_id = str(uuid.uuid4())
        prompt = SalesTrainerAudioScorePrompt(
            prompt_id=prompt_id,
            name="Latest attempt fixture",
            purpose="elevator_pitch",
            system_prompt="Score the latest attempt.",
            scoring_template="Return a score.",
            output_schema={},
            learner_rubric={},
            version=1,
            status="published",
        )
        older = SalesTrainerAudioSubmission(
            submission_id=str(uuid.uuid4()),
            user_id=user.user_id,
            unit_id=unit_id,
            purpose="elevator_pitch",
            status="scored",
            storage_key="/tmp/older.wav",
            original_filename="older.wav",
            content_type="audio/wav",
            size_bytes=1,
            created_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        newer = SalesTrainerAudioSubmission(
            submission_id=str(uuid.uuid4()),
            user_id=user.user_id,
            unit_id=unit_id,
            purpose="elevator_pitch",
            status="scored",
            storage_key="/tmp/newer.wav",
            original_filename="newer.wav",
            content_type="audio/wav",
            size_bytes=1,
            created_at=datetime.now(UTC),
        )
        older_score = SalesTrainerAudioScoreResult(
            submission_id=older.submission_id,
            prompt_id=prompt_id,
            prompt_version=1,
            prompt_hash="latest-attempt-fixture",
            total_score=88,
            passed=True,
            strengths=[],
            improvements=[],
            dimension_scores={},
        )
        newer_score = SalesTrainerAudioScoreResult(
            submission_id=newer.submission_id,
            prompt_id=prompt_id,
            prompt_version=1,
            prompt_hash="latest-attempt-fixture",
            total_score=40,
            passed=False,
            strengths=[],
            improvements=[],
            dimension_scores={},
        )
        db.add_all([user, prompt, older, newer, older_score, newer_score])
        await db.commit()

        progress = await load_latest_audio_progress(db, str(user.user_id))

    assert progress[unit_id].result_id == str(newer.submission_id)
    assert progress[unit_id].passed is False
