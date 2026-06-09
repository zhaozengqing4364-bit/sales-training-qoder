from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.schemas import AudioScorePromptCreate, AudioScorePromptUpdate
from sales_trainer.services.prompt_service import AudioScorePromptService


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"score-prompt-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Score Prompt {role}",
        email=f"score-prompt-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_should_edit_published_score_prompt_as_future_revision(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    service = AudioScorePromptService(test_db)
    prompt = await service.create_prompt(
        AudioScorePromptCreate(
            name="PPT 讲解评分",
            purpose="ppt_pitch",
            system_prompt="你是新人训练路径评分员。",
            scoring_template="请根据转写评分：{transcript}",
            output_schema={"type": "object"},
            learner_rubric={
                "criteria": [{"key": "structure", "label": "结构", "weight": 40}],
                "pass_threshold": 80,
            },
        ),
        actor=admin,
    )
    published = await service.publish_prompt(prompt, actor=admin)
    initial_revision = await _latest_prompt_revision(test_db, published.prompt_id)

    saved = await service.update_prompt(
        published,
        AudioScorePromptUpdate(
            system_prompt="你是更严格的新人训练路径评分员。",
            scoring_template="请按最新版评分：{transcript}",
            learner_rubric={
                "criteria": [{"key": "structure", "label": "结构", "weight": 50}],
                "pass_threshold": 85,
            },
        ),
        actor=admin,
    )
    working_revision = await _latest_prompt_revision(
        test_db,
        published.prompt_id,
        status="working",
    )

    assert saved.system_prompt == "你是新人训练路径评分员。"
    assert saved.scoring_template == "请根据转写评分：{transcript}"
    assert saved.version == 1
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert working_revision.change_class == "scoring_high_risk"
    assert working_revision.payload_json["system_prompt"] == (
        "你是更严格的新人训练路径评分员。"
    )
    assert working_revision.payload_json["learner_rubric"]["pass_threshold"] == 85

    republished = await service.publish_prompt(published, actor=admin)
    published_revision = await _latest_prompt_revision(test_db, published.prompt_id)

    assert republished.system_prompt == "你是更严格的新人训练路径评分员。"
    assert republished.scoring_template == "请按最新版评分：{transcript}"
    assert republished.version == 2
    assert published_revision.revision_id == working_revision.revision_id


async def _latest_prompt_revision(
    test_db: AsyncSession,
    prompt_id: str,
    *,
    status: str = "published",
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type
            == "sales_trainer_audio_score_prompt",
            SalesTrainerAssetRevision.logical_id == prompt_id,
            SalesTrainerAssetRevision.status == status,
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()
