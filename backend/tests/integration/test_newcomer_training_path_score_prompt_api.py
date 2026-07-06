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
async def test_should_reject_malformed_score_prompt_contract_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/admin/sales-trainer/audio-score-prompts",
        headers=_auth_headers(admin),
        json={
            "name": "PPT 讲解评分",
            "purpose": "ppt_pitch",
            "system_prompt": "你是新人训练路径评分员。",
            "scoring_template": "请根据转写评分：{transcript}",
            "output_schema": {
                "type": "object",
                "properties": {},
                "required": ["total_score"],
            },
            "learner_rubric": {
                "criteria": [{"label": "结构", "weight": 40}],
                "pass_threshold": 80,
            },
        },
    )

    assert response.status_code == 422
    assert "learner_rubric" in response.text
    assert "output_schema" in response.text


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


@pytest.mark.asyncio
async def test_should_list_preview_and_rollback_score_prompt_revisions_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/audio-score-prompts",
        headers=_auth_headers(admin),
        json={
            "name": "PPT 讲解评分回滚",
            "purpose": "ppt_pitch",
            "system_prompt": "你是新人训练路径评分员第一版。",
            "scoring_template": "请根据第一版评分：{transcript}",
            "output_schema": {"type": "object"},
            "learner_rubric": {
                "criteria": [{"key": "structure", "label": "结构", "weight": 40}],
                "pass_threshold": 80,
            },
        },
    )
    assert create_response.status_code == 200
    prompt_id = create_response.json()["data"]["prompt_id"]

    first_publish = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish",
        headers=_auth_headers(admin),
    )
    assert first_publish.status_code == 200
    first_revision = await _prompt_revision(test_db, prompt_id, status="published")

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}",
        headers=_auth_headers(admin),
        json={
            "system_prompt": "你是新人训练路径评分员第二版。",
            "scoring_template": "请根据第二版评分：{transcript}",
            "learner_rubric": {
                "criteria": [{"key": "structure", "label": "结构", "weight": 50}],
                "pass_threshold": 85,
            },
        },
    )
    assert update_response.status_code == 200

    second_publish = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish",
        headers=_auth_headers(admin),
    )
    assert second_publish.status_code == 200
    assert second_publish.json()["data"]["system_prompt"] == "你是新人训练路径评分员第二版。"
    assert second_publish.json()["data"]["version"] == 2

    denied_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/revisions",
        headers=_auth_headers(learner),
    )
    assert denied_response.status_code == 403

    revisions_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/revisions",
        headers=_auth_headers(admin),
    )
    assert revisions_response.status_code == 200
    revisions = revisions_response.json()["data"]["items"]
    assert [item["revision_no"] for item in revisions] == [2, 1]
    assert revisions[0]["is_active"] is True
    assert revisions[1]["revision_id"] == str(first_revision.revision_id)

    preview_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/rollback/preview",
        headers=_auth_headers(admin),
        json={"target_revision_id": str(first_revision.revision_id)},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["action"] == "audio_score_prompt.rollback"
    assert preview["permission"] == "sales_trainer.manage_modules"
    assert preview["requires_reason"] is True
    assert preview["future_only"] is True
    assert preview["mutates_history"] is False
    assert preview["historical_submissions_changed"] is False
    assert "system_prompt" in preview["changed_fields"]
    assert preview["target_revision"]["revision_no"] == 1

    prompt_after_preview = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish",
        headers=_auth_headers(admin),
    )
    assert prompt_after_preview.status_code == 200
    assert prompt_after_preview.json()["data"]["system_prompt"] == (
        "你是新人训练路径评分员第二版。"
    )

    rollback_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/rollback",
        headers=_auth_headers(admin),
        json={
            "target_revision_id": str(first_revision.revision_id),
            "reason": "回滚到第一版评分 Prompt",
        },
    )
    assert rollback_response.status_code == 200
    rollback_trace_id = rollback_response.json()["trace_id"]
    rolled_back = rollback_response.json()["data"]
    assert rolled_back["system_prompt"] == "你是新人训练路径评分员第一版。"
    assert rolled_back["version"] == 1

    logs = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.target_type
            == "sales_trainer_audio_score_prompt",
            SalesTrainerOperationLog.target_id == prompt_id,
            SalesTrainerOperationLog.action
            == "audio_score_prompt_revision_rolled_back",
        )
    )
    rollback_log = logs.scalar_one()
    assert rollback_log.request_id == rollback_trace_id
    assert rollback_log.metadata_json["trace_id"] == rollback_trace_id
    assert rollback_log.metadata_json["future_only"] is True
    assert rollback_log.metadata_json["historical_submissions_changed"] is False


async def _latest_prompt_revision(
    test_db: AsyncSession,
    prompt_id: str,
) -> SalesTrainerAssetRevision:
    return await _prompt_revision(test_db, prompt_id, status="working")


async def _prompt_revision(
    test_db: AsyncSession,
    prompt_id: str,
    *,
    status: str,
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
