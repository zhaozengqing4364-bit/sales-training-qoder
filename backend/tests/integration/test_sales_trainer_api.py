from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import PracticeSession, Scenario, User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerOperationLog,
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
    SalesTrainerRoleplayObservation,
    SalesTrainerUnit,
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str, *, department: str | None = None) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"sales-trainer-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Sales Trainer API {role}",
        email=f"sales-trainer-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        department=department,
    )


@pytest.mark.asyncio
async def test_should_expose_score_results_for_admin_by_user(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="音频评分",
        purpose="ppt_pitch",
        system_prompt="system",
        scoring_template="{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="recording.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/recording.wav",
        status="scored",
    )
    score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=submission.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="hash",
        deucate_model="fake-deucate",
        total_score=91,
        passed=True,
        summary="表达清楚",
        strengths=["结构完整"],
        improvements=[],
        dimension_scores={"content_accuracy": 91},
        raw_response={"total_score": 91},
    )
    test_db.add_all([admin, learner, prompt, submission, score])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/score-results",
        params={"user_id": learner.user_id},
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["submission_id"] == submission.submission_id
    assert payload["items"][0]["total_score"] == 91


@pytest.mark.asyncio
async def test_should_expose_quiz_attempts_for_admin_with_answer_snapshots(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="销售基础做题",
        unit_type="quiz",
        config={"quiz": {"pass_threshold": 10}},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=10,
        max_score=10,
        passed=True,
        status="scored",
    )
    answer = SalesTrainerQuizAnswer(
        answer_id=str(uuid.uuid4()),
        attempt_id=attempt.attempt_id,
        question_id="question-1",
        question_type="single_choice",
        answer_payload={
            "value": "A",
            "question_snapshot": {
                "question_id": "question-1",
                "title": "产品定位",
                "stem": "石犀核心定位是什么？",
                "question_type": "single_choice",
                "options": [{"value": "A", "label": "数据流动治理"}],
                "correct_answer": "A",
                "reference_answer": "A. 数据流动治理",
                "explanation": "石犀聚焦数据流动治理。",
                "points": 10,
            },
            "scoring": {"is_correct": True, "score": 10},
        },
        is_correct=True,
        score=10,
    )
    test_db.add_all([admin, learner, unit, attempt, answer])
    await test_db.commit()

    list_response = await async_client.get(
        "/api/v1/admin/sales-trainer/quiz-attempts",
        params={"user_id": learner.user_id},
        headers=_auth_headers(admin),
    )
    detail_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/quiz-attempts/{attempt.attempt_id}",
        headers=_auth_headers(admin),
    )

    assert list_response.status_code == 200
    list_payload = list_response.json()["data"]
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["attempt_id"] == attempt.attempt_id
    assert list_payload["items"][0]["user_name"] == learner.name
    assert list_payload["items"][0]["answers"][0]["question_title"] == "产品定位"

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["data"]
    assert detail_payload["answers"][0]["answer_payload"] == "A"
    assert detail_payload["answers"][0]["correct_answer"] == "A"
    assert detail_payload["answers"][0]["explanation"] == "石犀聚焦数据流动治理。"


@pytest.mark.asyncio
async def test_should_forbid_regular_user_from_admin_quiz_attempts(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="销售基础做题",
        unit_type="quiz",
        config={"quiz": {"pass_threshold": 10}},
        status="published",
        created_by=learner.user_id,
        updated_by=learner.user_id,
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=10,
        max_score=10,
        passed=True,
        status="scored",
    )
    test_db.add_all([learner, unit, attempt])
    await test_db.commit()

    list_response = await async_client.get(
        "/api/v1/admin/sales-trainer/quiz-attempts",
        headers=_auth_headers(learner),
    )
    detail_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/quiz-attempts/{attempt.attempt_id}",
        headers=_auth_headers(learner),
    )

    assert list_response.status_code == 403
    assert list_response.json()["error"] == "[ROLE_REQUIRED]"
    assert detail_response.status_code == 403
    assert detail_response.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_return_audio_upload_url_without_duration_requirement(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "local")
    learner = _user("user")
    test_db.add(learner)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/sales-trainer/audio-submissions/upload-url",
        headers=_auth_headers(learner),
        json={"filename": "any-length-recording.wav", "content_type": "audio/wav"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["storage_backend"] == "local"
    assert payload["content_type"] == "audio/wav"


@pytest.mark.asyncio
async def test_support_should_manage_sales_trainer_questions_without_global_test_bank_access(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    support = _user("support")
    general_category = QuestionCategory(
        category_id="general-api-category",
        name="通用题库",
        usage_scope="general",
        order_index=1,
    )
    general_question = QuestionItem(
        question_id="general-api-question",
        category_id=general_category.category_id,
        title="通用题",
        stem="不应进入销售训练题库",
        reference_answer="general",
        scoring_criteria={"question_type": "short_answer"},
        scoring_dimensions=["general"],
        status="published",
        usage_scope="general",
    )
    test_db.add_all([support, general_category, general_question])
    await test_db.commit()
    headers = _auth_headers(support)

    forbidden_response = await async_client.get(
        "/api/v1/curriculum/test-bank/questions",
        headers=headers,
    )
    category_response = await async_client.post(
        "/api/v1/admin/sales-trainer/question-categories",
        headers=headers,
        json={"name": "销售训练 API 分类", "description": "only sales trainer"},
    )
    category = category_response.json()["data"]
    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/questions",
        headers=headers,
        json={
            "title": "客户异议识别",
            "stem": "客户说太贵了，优先识别哪类异议？",
            "category_id": category["category_id"],
            "question_type": "single_choice",
            "difficulty": "easy",
            "tags": ["异议处理"],
            "options": [
                {"value": "A", "label": "价格异议"},
                {"value": "B", "label": "权限异议"},
            ],
            "correct_answer": "A",
            "explanation": "先识别价格异议，再回到价值。",
        },
    )
    list_response = await async_client.get(
        "/api/v1/admin/sales-trainer/questions",
        headers=headers,
    )

    assert forbidden_response.status_code == 403
    assert category_response.status_code == 200
    assert category["usage_scope"] == "sales_trainer"
    assert create_response.status_code == 200
    question = create_response.json()["data"]
    assert question["usage_scope"] == "sales_trainer"
    assert question["question_type"] == "single_choice"
    assert question["scoring_criteria"]["correct_answer"] == "A"
    assert question["explanation"] == "先识别价格异议，再回到价值。"
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert [item["question_id"] for item in items] == [question["question_id"]]


@pytest.mark.asyncio
async def test_sales_trainer_question_api_should_validate_business_question_shapes(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    manager = _user("support")
    category = QuestionCategory(
        category_id="sales-trainer-api-category",
        name="销售题库",
        usage_scope="sales_trainer",
        order_index=1,
    )
    test_db.add_all([manager, category])
    await test_db.commit()
    headers = _auth_headers(manager)

    invalid_response = await async_client.post(
        "/api/v1/admin/sales-trainer/questions",
        headers=headers,
        json={
            "title": "非法单选",
            "stem": "缺答案",
            "category_id": category.category_id,
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "有效选项"}],
        },
    )
    multi_response = await async_client.post(
        "/api/v1/admin/sales-trainer/questions",
        headers=headers,
        json={
            "title": "多选题",
            "stem": "哪些属于销售训练资产？",
            "category_id": category.category_id,
            "question_type": "multiple_choice",
            "options": [
                {"value": "A", "label": "题库"},
                {"value": "B", "label": "评分标准"},
            ],
            "correct_answers": ["A", "B"],
        },
    )
    true_false_response = await async_client.post(
        "/api/v1/admin/sales-trainer/questions",
        headers=headers,
        json={
            "title": "判断题",
            "stem": "录音评分标准由销售训练单元绑定。",
            "category_id": category.category_id,
            "question_type": "true_false",
            "correct_bool": True,
        },
    )
    short_response = await async_client.post(
        "/api/v1/admin/sales-trainer/questions",
        headers=headers,
        json={
            "title": "简答题",
            "stem": "如何回应价格异议？",
            "category_id": category.category_id,
            "question_type": "short_answer",
            "reference_answer": "先确认预算约束，再回到价值和风险成本。",
            "scoring_dimensions": ["异议识别", "价值表达"],
            "explanation": "优秀答案应兼顾共情、澄清和价值重构。",
            "ai_scoring": {
                "enabled": True,
                "pass_threshold": 75,
                "temperature": 0.2,
                "timeout": 20,
                "max_retries": 1,
            },
        },
    )
    default_ai_response = await async_client.post(
        "/api/v1/admin/sales-trainer/questions",
        headers=headers,
        json={
            "title": "默认 AI 参数简答题",
            "stem": "如何确认客户异议背后的真实顾虑？",
            "category_id": category.category_id,
            "question_type": "short_answer",
            "reference_answer": "先复述客户问题，再追问预算、风险、决策链或时机等真实原因。",
            "ai_scoring": {
                "enabled": True,
            },
        },
    )

    assert invalid_response.status_code == 422
    assert invalid_response.json()["error"] == "[QUESTION_CORRECT_ANSWER_INVALID]"
    assert multi_response.status_code == 200
    assert multi_response.json()["data"]["scoring_criteria"]["correct_answers"] == [
        "A",
        "B",
    ]
    assert true_false_response.status_code == 200
    assert (
        true_false_response.json()["data"]["scoring_criteria"]["correct_bool"] is True
    )
    assert short_response.status_code == 200
    assert (
        short_response.json()["data"]["reference_answer"]
        == "先确认预算约束，再回到价值和风险成本。"
    )
    assert (
        short_response.json()["data"]["explanation"]
        == "优秀答案应兼顾共情、澄清和价值重构。"
    )
    assert short_response.json()["data"]["ai_scoring"]["pass_threshold"] == 75
    assert default_ai_response.status_code == 200
    assert default_ai_response.json()["data"]["ai_scoring"] == {
        "enabled": True,
        "pass_threshold": 60,
    }


@pytest.mark.asyncio
async def test_settings_api_should_report_health_without_secret_values(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    monkeypatch.setenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "cos")
    monkeypatch.setenv("TENCENT_COS_SECRET_ID", "secret-id")
    monkeypatch.setenv("TENCENT_COS_SECRET_KEY", "secret-key")
    monkeypatch.setenv("TENCENT_COS_BUCKET", "bucket")
    monkeypatch.setenv("TENCENT_COS_REGION", "ap-guangzhou")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-secret")
    monkeypatch.setenv("DEUCATE_BASE_URL", "https://deucate.example.com")
    monkeypatch.setenv("DEUCATE_API_KEY", "deucate-secret")
    monkeypatch.setenv("DEUCATE_MODEL", "deepseek-v4-flash")

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/settings",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["direct_upload_supported"] is True
    assert data["cos_configured"] is True
    assert data["dashscope_configured"] is True
    assert data["deucate_configured"] is True
    serialized = str(data)
    assert "secret-id" not in serialized
    assert "secret-key" not in serialized
    assert "dashscope-secret" not in serialized
    assert "deucate-secret" not in serialized


@pytest.mark.asyncio
async def test_register_cos_audio_submission_should_head_object_and_reject_size_mismatch(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learner = _user("user")
    test_db.add(learner)
    await test_db.commit()

    class FakeSigner:
        def __init__(self, size: int) -> None:
            self.size = size
            self.seen_keys: list[str] = []

        def get_object_size(self, object_key: str) -> int:
            self.seen_keys.append(object_key)
            return self.size

    signer = FakeSigner(size=12)
    monkeypatch.setattr(
        "sales_trainer.services.audio_submission_service.get_cos_signing_service",
        lambda: signer,
    )

    ok_response = await async_client.post(
        "/api/v1/sales-trainer/audio-submissions",
        headers=_auth_headers(learner),
        json={
            "unit_id": None,
            "purpose": "general_audio_scoring",
            "original_filename": "direct.wav",
            "content_type": "audio/wav",
            "size_bytes": 12,
            "storage_key": "cos://sales-trainer/audio/user/direct.wav",
            "auto_process": False,
        },
    )
    mismatch_response = await async_client.post(
        "/api/v1/sales-trainer/audio-submissions",
        headers=_auth_headers(learner),
        json={
            "unit_id": None,
            "purpose": "general_audio_scoring",
            "original_filename": "direct.wav",
            "content_type": "audio/wav",
            "size_bytes": 13,
            "storage_key": "cos://sales-trainer/audio/user/direct.wav",
            "auto_process": False,
        },
    )

    assert ok_response.status_code == 200
    assert signer.seen_keys == [
        "sales-trainer/audio/user/direct.wav",
        "sales-trainer/audio/user/direct.wav",
    ]
    assert mismatch_response.status_code == 409
    assert mismatch_response.json()["error"] == "[AUDIO_OBJECT_SIZE_MISMATCH]"


@pytest.mark.asyncio
async def test_register_audio_submission_should_schedule_processing_after_response(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learner = _user("user")
    test_db.add(learner)
    await test_db.commit()

    class FakeSigner:
        def get_object_size(self, object_key: str) -> int:
            assert object_key == "sales-trainer/audio/user/direct.wav"
            return 12

    scheduled: list[tuple[str, str | None]] = []

    async def fake_process_audio_submission_background(
        submission_id: str,
        *,
        actor_id: str | None = None,
    ) -> None:
        scheduled.append((submission_id, actor_id))

    monkeypatch.setattr(
        "sales_trainer.services.audio_submission_service.get_cos_signing_service",
        lambda: FakeSigner(),
    )
    monkeypatch.setattr(
        "sales_trainer.api.process_audio_submission_background",
        fake_process_audio_submission_background,
    )

    response = await async_client.post(
        "/api/v1/sales-trainer/audio-submissions",
        headers=_auth_headers(learner),
        json={
            "unit_id": None,
            "purpose": "general_audio_scoring",
            "original_filename": "direct.wav",
            "content_type": "audio/wav",
            "size_bytes": 12,
            "storage_key": "cos://sales-trainer/audio/user/direct.wav",
            "auto_process": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "uploaded"
    assert scheduled == [(payload["submission_id"], learner.user_id)]


@pytest.mark.asyncio
async def test_should_reject_non_admin_from_sales_trainer_admin_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    test_db.add(learner)
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/operation-logs",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_should_allow_training_manager_to_reach_readiness_review_scope_guard(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SALES_TRAINER_MANAGER_ROLES", raising=False)
    manager = _user("support", department="华东销售")
    learner = _user("user", department="华东销售")
    ops = _user("operations", department="运维")
    test_db.add_all([manager, learner, ops])
    await test_db.commit()

    manager_response = await async_client.post(
        "/api/v1/admin/sales-trainer/readiness/dossiers/missing-learner/review-actions",
        headers=_auth_headers(manager),
        json={
            "decision": "mark_manual_follow_up",
            "reason": "测试权限应先进入对象级校验。",
            "capability_keys": [],
            "source_evidence_ids": [],
            "idempotency_key": "review-api-manager-0001",
            "expected_latest_review_action_id": None,
        },
    )
    missing_version_response = await async_client.post(
        "/api/v1/admin/sales-trainer/readiness/dossiers/missing-learner/review-actions",
        headers=_auth_headers(manager),
        json={
            "decision": "mark_manual_follow_up",
            "reason": "缺少显式版本前置字段时应由请求契约拒绝。",
            "capability_keys": [],
            "source_evidence_ids": [],
            "idempotency_key": "review-api-missing-version-0001",
        },
    )
    learner_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/readiness/dossiers/{manager.user_id}/review-actions",
        headers=_auth_headers(learner),
        json={
            "decision": "mark_manual_follow_up",
            "reason": "普通学员不能复核。",
            "capability_keys": [],
            "source_evidence_ids": [],
            "idempotency_key": "review-api-learner-0001",
            "expected_latest_review_action_id": None,
        },
    )
    ops_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/readiness/dossiers/{manager.user_id}/review-actions",
        headers=_auth_headers(ops),
        json={
            "decision": "mark_manual_follow_up",
            "reason": "运维只有记录读取权限，不能执行复核。",
            "capability_keys": [],
            "source_evidence_ids": [],
            "idempotency_key": "review-api-operations-0001",
            "expected_latest_review_action_id": None,
        },
    )

    assert manager_response.status_code == 404
    assert manager_response.json()["error"] == "[TRAINING_RECORD_NOT_FOUND]"
    assert missing_version_response.status_code == 422
    assert learner_response.status_code == 403
    assert learner_response.json()["error"] == "[READINESS_REVIEW_ROLE_REQUIRED]"
    assert ops_response.status_code == 403
    assert ops_response.json()["error"] == "[READINESS_REVIEW_ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_scope_sales_trainer_manager_to_same_department(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SALES_TRAINER_MANAGER_ROLES", raising=False)
    manager = _user("support", department="华东销售")
    same_department_user = _user("user", department="华东销售")
    other_department_user = _user("user", department="华南销售")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="音频评分",
        purpose="ppt_pitch",
        system_prompt="system",
        scoring_template="{transcript}",
        output_schema={},
        status="published",
        created_by=manager.user_id,
        updated_by=manager.user_id,
    )
    same_submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=same_department_user.user_id,
        purpose="ppt_pitch",
        original_filename="same.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/same.wav",
        status="scored",
    )
    other_submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=other_department_user.user_id,
        purpose="ppt_pitch",
        original_filename="other.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/other.wav",
        status="scored",
    )
    same_score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=same_submission.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="same-hash",
        deucate_model="fake-deucate",
        total_score=90,
        passed=True,
        summary="同部门",
        strengths=[],
        improvements=[],
        dimension_scores={},
        raw_response={"total_score": 90},
    )
    other_score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=other_submission.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="other-hash",
        deucate_model="fake-deucate",
        total_score=60,
        passed=False,
        summary="跨部门",
        strengths=[],
        improvements=[],
        dimension_scores={},
        raw_response={"total_score": 60},
    )
    same_log = SalesTrainerOperationLog(
        actor_id=same_department_user.user_id,
        actor_role="user",
        action="audio_uploaded",
        target_type="sales_trainer_audio_submission",
        target_id=same_submission.submission_id,
        metadata_json={},
    )
    other_log = SalesTrainerOperationLog(
        actor_id=other_department_user.user_id,
        actor_role="user",
        action="audio_uploaded",
        target_type="sales_trainer_audio_submission",
        target_id=other_submission.submission_id,
        metadata_json={},
    )
    same_unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="同部门做题",
        unit_type="quiz",
        config={"quiz": {"pass_threshold": 10}},
        status="published",
        created_by=manager.user_id,
        updated_by=manager.user_id,
    )
    same_attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=same_unit.unit_id,
        user_id=same_department_user.user_id,
        total_score=10,
        max_score=10,
        passed=True,
        status="scored",
    )
    other_attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=same_unit.unit_id,
        user_id=other_department_user.user_id,
        total_score=0,
        max_score=10,
        passed=False,
        status="scored",
    )
    test_db.add_all(
        [
            manager,
            same_department_user,
            other_department_user,
            prompt,
            same_submission,
            other_submission,
            same_score,
            other_score,
            same_log,
            other_log,
            same_unit,
            same_attempt,
            other_attempt,
        ]
    )
    await test_db.commit()

    headers = _auth_headers(manager)
    submissions_response = await async_client.get(
        "/api/v1/admin/sales-trainer/audio-submissions",
        headers=headers,
    )
    same_detail_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/audio-submissions/{same_submission.submission_id}",
        headers=headers,
    )
    other_detail_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/audio-submissions/{other_submission.submission_id}",
        headers=headers,
    )
    same_training_record_detail_response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records/detail/"
        f"audio_submission/{same_submission.submission_id}",
        headers=headers,
    )
    other_training_record_detail_response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records/detail/"
        f"audio_submission/{other_submission.submission_id}",
        headers=headers,
    )
    score_response = await async_client.get(
        "/api/v1/admin/sales-trainer/score-results",
        headers=headers,
    )
    logs_response = await async_client.get(
        "/api/v1/admin/sales-trainer/operation-logs",
        headers=headers,
    )
    quiz_attempts_response = await async_client.get(
        "/api/v1/admin/sales-trainer/quiz-attempts",
        headers=headers,
    )
    same_quiz_detail_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/quiz-attempts/{same_attempt.attempt_id}",
        headers=headers,
    )
    other_quiz_detail_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/quiz-attempts/{other_attempt.attempt_id}",
        headers=headers,
    )

    assert submissions_response.status_code == 200
    submissions_payload = submissions_response.json()["data"]
    assert submissions_payload["total"] == 1
    assert (
        submissions_payload["items"][0]["submission_id"]
        == same_submission.submission_id
    )
    assert submissions_payload["items"][0]["user_name"] == same_department_user.name
    assert submissions_payload["items"][0]["user_email"] == same_department_user.email
    assert (
        submissions_payload["items"][0]["user_department"]
        == same_department_user.department
    )
    assert same_detail_response.status_code == 200
    same_detail_payload = same_detail_response.json()["data"]
    assert same_detail_payload["user_name"] == same_department_user.name
    assert same_detail_payload["user_email"] == same_department_user.email
    assert other_detail_response.status_code == 403
    assert other_detail_response.json()["error"] == "[ACCESS_DENIED]"
    assert same_training_record_detail_response.status_code == 200
    same_record_detail = same_training_record_detail_response.json()["data"]
    assert same_record_detail["record_id"] == same_submission.submission_id
    assert same_record_detail["user_department"] == same_department_user.department
    assert other_training_record_detail_response.status_code == 404
    assert other_training_record_detail_response.json()["error"] == (
        "[TRAINING_RECORD_NOT_FOUND]"
    )

    assert score_response.status_code == 200
    score_payload = score_response.json()["data"]
    assert score_payload["total"] == 1
    assert score_payload["items"][0]["submission_id"] == same_submission.submission_id

    assert logs_response.status_code == 403
    assert logs_response.json()["error"] == "[ROLE_REQUIRED]"

    assert quiz_attempts_response.status_code == 200
    quiz_payload = quiz_attempts_response.json()["data"]
    assert quiz_payload["total"] == 1
    assert quiz_payload["items"][0]["attempt_id"] == same_attempt.attempt_id
    assert same_quiz_detail_response.status_code == 200
    assert other_quiz_detail_response.status_code == 403


@pytest.mark.asyncio
async def test_should_expose_realtime_roleplay_observations_with_record_scope_guard(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user", department="华东销售")
    manager = _user("support", department="华东销售")
    outside_manager = _user("support", department="华北销售")
    content_admin = _user("content_admin", department="华东销售")
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        name="新人实时对练",
        description="新人实时对练",
        scenario_type="sales",
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="completed",
        voice_policy_snapshot={
            "external_binding": {
                "owner": "sales_trainer",
                "path_key": "newcomer_training_path_v1",
                "path_revision_id": "path-rev-002",
                "path_revision_no": 2,
                "module_key": "realtime_roleplay",
                "binding_key": "newcomer_realtime_roleplay_v1",
            }
        },
    )
    heuristic = SalesTrainerRoleplayObservation(
        observation_id=str(uuid.uuid4()),
        session_id=session.session_id,
        source_record_id=session.session_id,
        source="heuristic",
        turn_index=1,
        evaluator_status="completed",
        dimensions_json=[
            {
                "key": "capture_context",
                "main_chain_effect": "none",
            },
            {
                "key": "evaluation_runtime",
                "realtime_disposition": "record_only",
                "blocking": False,
                "main_chain_effect": "none",
            },
        ],
        signals_json=[
            {"signal_type": "quality_flag", "value": "knowledge_gap_degradation"}
        ],
        payload_hash="sha256:heuristic",
    )
    llm = SalesTrainerRoleplayObservation(
        observation_id=str(uuid.uuid4()),
        session_id=session.session_id,
        source_record_id=session.session_id,
        source="llm_evaluator",
        turn_index=2,
        evaluator_status="failed",
        dimensions_json=[
            {
                "key": "capture_context",
                "main_chain_effect": "none",
            },
            {
                "key": "evaluation_runtime",
                "realtime_disposition": "record_only",
                "blocking": False,
                "main_chain_effect": "none",
            },
        ],
        signals_json=[{"signal_type": "manual_review_required", "value": True}],
        error_json={"code": "[LLM_EVALUATOR_TIMEOUT]", "message": "timeout"},
        payload_hash="sha256:llm",
    )
    test_db.add_all(
        [
            learner,
            manager,
            outside_manager,
            content_admin,
            scenario,
            session,
            heuristic,
            llm,
        ]
    )
    await test_db.commit()

    missing_session_id = str(uuid.uuid4())
    manager_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/training-records/realtime-roleplay/{session.session_id}/observations",
        headers=_auth_headers(manager),
    )
    outside_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/training-records/realtime-roleplay/{session.session_id}/observations",
        headers=_auth_headers(outside_manager),
    )
    outside_missing_response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records/realtime-roleplay/"
        f"{missing_session_id}/observations",
        headers=_auth_headers(outside_manager),
    )
    content_admin_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/training-records/realtime-roleplay/{session.session_id}/observations",
        headers=_auth_headers(content_admin),
    )

    assert manager_response.status_code == 200
    payload = manager_response.json()["data"]
    assert payload["session_id"] == session.session_id
    assert payload["total"] == 2
    assert payload["source_counts"] == {"heuristic": 1, "llm_evaluator": 1}
    assert payload["status_counts"]["completed"] == 1
    assert payload["status_counts"]["failed"] == 1
    heuristic_item = next(
        item for item in payload["items"] if item["source"] == "heuristic"
    )
    llm_item = next(
        item for item in payload["items"] if item["source"] == "llm_evaluator"
    )
    assert heuristic_item["dimensions"][0]["main_chain_effect"] == "none"
    assert heuristic_item["dimensions"][1]["realtime_disposition"] == "record_only"
    assert heuristic_item["dimensions"][1]["blocking"] is False
    assert heuristic_item["dimensions"][1]["main_chain_effect"] == "none"
    assert llm_item["dimensions"][0]["main_chain_effect"] == "none"
    assert llm_item["dimensions"][1]["realtime_disposition"] == "record_only"
    assert llm_item["dimensions"][1]["blocking"] is False
    assert llm_item["dimensions"][1]["main_chain_effect"] == "none"
    assert llm_item["error"]["code"] == "[LLM_EVALUATOR_TIMEOUT]"

    assert outside_response.status_code == 404
    assert outside_response.json()["error"] == "[TRAINING_RECORD_NOT_FOUND]"
    assert outside_missing_response.status_code == 404
    assert outside_missing_response.json()["error"] == "[TRAINING_RECORD_NOT_FOUND]"
    assert str(session.session_id) not in str(outside_response.json())

    assert content_admin_response.status_code == 403
    assert content_admin_response.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_serve_audio_file_to_owner_and_admin_only(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    other_learner = _user("user")
    storage_root = tmp_path / "sales-trainer-audio"
    audio_dir = storage_root / learner.user_id
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / "pitch.wav"
    audio_path.write_bytes(b"fake wav bytes")
    monkeypatch.setenv("SALES_TRAINER_AUDIO_STORAGE_PATH", str(storage_root))

    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="pitch.wav",
        content_type="audio/wav",
        size_bytes=audio_path.stat().st_size,
        storage_key=str(audio_path),
        status="uploaded",
    )
    test_db.add_all([admin, learner, other_learner, submission])
    await test_db.commit()

    owner_response = await async_client.get(
        f"/api/v1/sales-trainer/audio-submissions/{submission.submission_id}/file",
        headers=_auth_headers(learner),
    )
    admin_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/audio-submissions/{submission.submission_id}/file",
        headers=_auth_headers(admin),
    )
    other_response = await async_client.get(
        f"/api/v1/sales-trainer/audio-submissions/{submission.submission_id}/file",
        headers=_auth_headers(other_learner),
    )

    assert owner_response.status_code == 200
    assert owner_response.content == b"fake wav bytes"
    assert owner_response.headers["content-type"].startswith("audio/wav")
    assert admin_response.status_code == 200
    assert admin_response.content == b"fake wav bytes"
    assert other_response.status_code == 403
    assert other_response.json()["error"] == "[ACCESS_DENIED]"


@pytest.mark.asyncio
async def test_should_list_only_own_audio_submissions_for_learner(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    """学员侧 GET /sales-trainer/audio-submissions 只返回自己的录音。

    覆盖 PRD R5：学员在路径首页看"我的录音"区，后端按 current_user 过滤。
    """
    learner = _user("user", department="华东销售")
    other_learner = _user("user", department="华东销售")
    admin = _user("admin")

    own_submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="own.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/own.wav",
        status="scored",
    )
    other_submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=other_learner.user_id,
        purpose="ppt_pitch",
        original_filename="other.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/other.wav",
        status="scored",
    )
    test_db.add_all([learner, other_learner, admin, own_submission, other_submission])
    await test_db.commit()

    # 学员只看到自己的录音
    learner_response = await async_client.get(
        "/api/v1/sales-trainer/audio-submissions",
        headers=_auth_headers(learner),
    )
    assert learner_response.status_code == 200
    learner_payload = learner_response.json()["data"]
    assert learner_payload["total"] == 1
    assert learner_payload["items"][0]["submission_id"] == str(
        own_submission.submission_id
    )
    assert learner_payload["items"][0]["user_id"] == str(learner.user_id)

    # admin 端 list 不受学员端端点影响（走 admin_router，可看到全部）
    admin_response = await async_client.get(
        "/api/v1/admin/sales-trainer/audio-submissions",
        headers=_auth_headers(admin),
    )
    assert admin_response.status_code == 200
    admin_payload = admin_response.json()["data"]
    assert admin_payload["total"] == 2
