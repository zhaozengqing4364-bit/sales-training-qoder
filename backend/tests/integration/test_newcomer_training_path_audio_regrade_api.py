from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerOperationLog,
)
from sales_trainer.services.deucate_scoring_service import AudioScoreOutcome


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-audio-regrade-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Audio Regrade {role}",
        email=f"newcomer-audio-regrade-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


class _FakeAudioScoringService:
    async def score_audio(
        self,
        *,
        submission: SalesTrainerAudioSubmission,
        prompt: SalesTrainerAudioScorePrompt,
        transcript_text: str,
        unit_name: str | None,
        pass_threshold: float,
        scoring_standard: str = "",
    ) -> AudioScoreOutcome:
        assert submission.submission_id
        assert prompt.system_prompt == "你是更严格的新人训练路径评分员。"
        assert transcript_text == "大家好，下面介绍产品。"
        assert unit_name is None
        assert pass_threshold == 70
        assert scoring_standard == ""
        return AudioScoreOutcome(
            prompt_hash="target-prompt-hash",
            deucate_model="fake-deucate-regrade",
            total_score=42,
            passed=False,
            summary="新版 prompt 判断结构不足。",
            strengths=["开场清晰"],
            improvements=["补充客户利益点"],
            dimension_scores={"structure": 42},
            raw_response={"total_score": 42, "summary": "新版 prompt 判断结构不足。"},
            error_code=None,
            error_message=None,
            latency_ms=12,
        )


@pytest.mark.asyncio
async def test_should_regrade_audio_submission_as_explicit_append_only_action(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    content_admin = _user("content_admin")
    learner = _user("user")
    test_db.add_all([admin, content_admin, learner])
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
            "learner_rubric": {"pass_threshold": 80},
        },
    )
    assert create_response.status_code == 200
    prompt_id = create_response.json()["data"]["prompt_id"]

    first_publish = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish",
        headers=_auth_headers(admin),
    )
    assert first_publish.status_code == 200

    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="ppt.wav",
        content_type="audio/wav",
        size_bytes=2048,
        storage_key="/tmp/ppt.wav",
        status="scored",
    )
    original_score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=submission.submission_id,
        prompt_id=prompt_id,
        prompt_version=1,
        prompt_hash="source-prompt-hash",
        deucate_model="fake-deucate",
        transcript_snapshot="大家好，下面介绍产品。",
        total_score=88,
        passed=True,
        summary="表达清楚。",
        strengths=["结构完整"],
        improvements=[],
        dimension_scores={"structure": 88},
        raw_response={"total_score": 88},
    )
    test_db.add_all([submission, original_score])
    await test_db.commit()

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}",
        headers=_auth_headers(admin),
        json={
            "system_prompt": "你是更严格的新人训练路径评分员。",
            "scoring_template": "请按最新版评分：{transcript}",
            "learner_rubric": {"pass_threshold": 85},
        },
    )
    assert update_response.status_code == 200
    second_publish = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish",
        headers=_auth_headers(admin),
    )
    assert second_publish.status_code == 200
    target_revision = await _latest_prompt_revision(test_db, prompt_id)

    monkeypatch.setattr(
        "sales_trainer.services.audio_regrade_service.DeucateScoringService",
        _FakeAudioScoringService,
        raising=False,
    )

    forbidden_preview = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"audio-submissions/{submission.submission_id}/preview",
        headers=_auth_headers(content_admin),
        json={"target_revision_id": target_revision.revision_id},
    )
    assert forbidden_preview.status_code == 403

    missing_reason = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"audio-submissions/{submission.submission_id}/run",
        headers=_auth_headers(admin),
        json={"target_revision_id": target_revision.revision_id, "reason": ""},
    )
    assert missing_reason.status_code == 422

    preview_response = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"audio-submissions/{submission.submission_id}/preview",
        headers=_auth_headers(admin),
        json={"target_revision_id": target_revision.revision_id},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["target_type"] == "audio_submission"
    assert preview["before_snapshot"]["score_id"] == original_score.score_id
    assert preview["before_snapshot"]["prompt_hash"] == "source-prompt-hash"
    assert preview["after_snapshot"]["prompt_hash"] == "target-prompt-hash"
    assert preview["after_snapshot"]["total_score"] == 42

    run_response = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"audio-submissions/{submission.submission_id}/run",
        headers=_auth_headers(admin),
        json={
            "target_revision_id": target_revision.revision_id,
            "reason": "评分 prompt 发布新版后，对历史录音做显式补充重评。",
        },
    )
    assert run_response.status_code == 200
    run = run_response.json()["data"]
    assert run["status"] == "completed"
    assert run["target_revision_id"] == target_revision.revision_id
    assert run["before_snapshot"]["total_score"] == 88
    assert run["after_snapshot"]["total_score"] == 42
    assert run["trace_id"]

    preserved_score = await test_db.get(
        SalesTrainerAudioScoreResult,
        original_score.score_id,
    )
    assert preserved_score is not None
    assert float(preserved_score.total_score) == 88
    assert preserved_score.prompt_hash == "source-prompt-hash"

    run_count = await test_db.scalar(text("select count(*) from sales_trainer_regrade_runs"))
    assert run_count == 1
    log = await _latest_regrade_log(test_db, submission.submission_id)
    assert log.action == "historical_regrade.completed"
    assert log.request_id == run["trace_id"]
    assert log.metadata_json["target_type"] == "audio_submission"
    assert log.metadata_json["append_only"] is True
    assert log.metadata_json["history_overwrite"] is False
    assert log.metadata_json["impact_scope"]["record_count"] == 1


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
            SalesTrainerAssetRevision.status == "published",
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _latest_regrade_log(
    test_db: AsyncSession,
    submission_id: str,
) -> SalesTrainerOperationLog:
    result = await test_db.execute(
        select(SalesTrainerOperationLog)
        .where(
            SalesTrainerOperationLog.target_type
            == "sales_trainer_audio_submission",
            SalesTrainerOperationLog.target_id == submission_id,
            SalesTrainerOperationLog.action == "historical_regrade.completed",
        )
        .order_by(SalesTrainerOperationLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one()
