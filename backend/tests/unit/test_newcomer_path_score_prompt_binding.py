"""Path scoring-rubric bindings must resolve published AudioScorePrompt rows."""

from __future__ import annotations

import uuid

import pytest

from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
)
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.resource_validator import PathResourceValidator


def _audio_payload(scoring_rubric_id: str) -> TrainingPathPayload:
    return TrainingPathPayload.model_validate(
        {
            "title": "评分标准绑定校验",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "讲解",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "module-1",
                            "title": "录音",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "audio-1",
                                    "type": "audio_assessment",
                                    "title": "产品讲解录音",
                                    "order_index": 1,
                                    "config": {
                                        "scoring_rubric_id": scoring_rubric_id,
                                        "pass_score": 80,
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_should_accept_published_audio_score_prompt_binding(test_db, test_user):
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id="prompt-valid",
        name="有效评分标准",
        purpose="general_audio_scoring",
        system_prompt="评分专家",
        scoring_template="文本：{transcript}",
        output_schema={},
        learner_rubric={"visible_to_learner": True, "criteria": [], "common_mistakes": []},
        version=1,
        status="published",
        created_by=str(test_user.user_id),
        updated_by=str(test_user.user_id),
    )
    test_db.add(prompt)
    await test_db.flush()

    issues = await PathResourceValidator(test_db).validate(
        _audio_payload("prompt-valid")
    )

    assert issues == ()


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

    issues = await PathResourceValidator(test_db).validate(
        _audio_payload("rubric-legacy")
    )

    assert len(issues) == 1
    assert issues[0].code == "scoring_rubric_not_published"
    assert "请重新选择或新建评分标准" in issues[0].message
    assert issues[0].field_path.endswith("config.scoring_rubric_id")
