from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerOperationLog


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-score-prompt-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Score Prompt API {role}",
        email=f"newcomer-score-prompt-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_should_update_published_score_prompt_as_future_revision_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/audio-score-prompts",
        headers=_auth_headers(admin),
        json={
            "name": "PPT 讲解评分",
            "purpose": "ppt_pitch",
            "system_prompt": "你是新人训练路径评分员。",
            "scoring_template": "请根据转写评分：{transcript}",
            "output_schema": {"type": "object"},
            "learner_rubric": {
                "criteria": [{"key": "structure", "label": "结构", "weight": 40}],
                "pass_threshold": 80,
            },
        },
    )
    assert create_response.status_code == 200
    prompt_id = create_response.json()["data"]["prompt_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish",
        headers=_auth_headers(admin),
    )
    assert publish_response.status_code == 200

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}",
        headers=_auth_headers(admin),
        json={
            "system_prompt": "你是更严格的新人训练路径评分员。",
            "scoring_template": "请按最新版评分：{transcript}",
            "learner_rubric": {
                "criteria": [{"key": "structure", "label": "结构", "weight": 50}],
                "pass_threshold": 85,
            },
        },
    )

    assert update_response.status_code == 200
    update_trace_id = update_response.json()["trace_id"]
    data = update_response.json()["data"]
    assert data["system_prompt"] == "你是新人训练路径评分员。"
    assert data["version"] == 1

    working_revision = await _latest_prompt_revision(test_db, prompt_id)
    assert working_revision.change_class == "scoring_high_risk"
    assert working_revision.payload_json["system_prompt"] == (
        "你是更严格的新人训练路径评分员。"
    )
    assert working_revision.payload_json["learner_rubric"]["pass_threshold"] == 85

    audit_log = await _latest_prompt_log(test_db, prompt_id)
    assert audit_log.action == "audio_score_prompt_revision_saved"
    assert audit_log.request_id == update_trace_id
    assert audit_log.metadata_json["trace_id"] == update_trace_id


async def _latest_prompt_revision(
    test_db: AsyncSession,
    prompt_id: str,
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type
            == "sales_trainer_audio_score_prompt",
            SalesTrainerAssetRevision.logical_id == prompt_id,
            SalesTrainerAssetRevision.status == "working",
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _latest_prompt_log(
    test_db: AsyncSession,
    prompt_id: str,
) -> SalesTrainerOperationLog:
    result = await test_db.execute(
        select(SalesTrainerOperationLog)
        .where(
            SalesTrainerOperationLog.target_type
            == "sales_trainer_audio_score_prompt",
            SalesTrainerOperationLog.target_id == prompt_id,
        )
        .order_by(SalesTrainerOperationLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one()
