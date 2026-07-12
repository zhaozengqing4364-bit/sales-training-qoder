from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
    SalesTrainerAssetRevision,
    SalesTrainerOperationLog,
)
from sales_trainer.services.regrade_service import (
    SalesTrainerRegradeService,
    SalesTrainerRegradeServiceError,
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str, *, department: str | None = None) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-regrade-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Regrade {role}",
        email=f"newcomer-regrade-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        department=department,
    )


def _question(question_id: str, *, category_id: str) -> QuestionItem:
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title="见客户前礼仪",
        stem="见客户前应该先确认什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "客户背景"},
                {"value": "B", "label": "会议室颜色"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )


async def _link_activity_evidence(
    db: AsyncSession, *, learner: User, evidence_id: str
) -> None:
    revision = SalesTrainerAssetRevision(
        revision_id=str(uuid.uuid4()),
        resource_type="newcomer_training_path_orchestration",
        logical_id=f"quiz-regrade-{uuid.uuid4()}",
        revision_no=1,
        status="published",
        payload_json={},
        payload_hash=uuid.uuid4().hex,
    )
    enrollment = NewcomerTrainingEnrollment(
        learner_id=str(learner.user_id),
        path_id=revision.logical_id,
        path_revision_id=str(revision.revision_id),
    )
    db.add_all([revision, enrollment])
    await db.flush()
    db.add(
        NewcomerTrainingActivityAttempt(
            enrollment_id=str(enrollment.enrollment_id),
            path_revision_id=str(revision.revision_id),
            activity_id="quiz-regrade-activity",
            activity_type="quiz",
            attempt_no=1,
            status="completed",
            client_token=f"quiz-regrade-{uuid.uuid4()}",
            activity_snapshot={"activity_id": "quiz-regrade-activity"},
            evidence_type="quiz_attempt",
            evidence_id=evidence_id,
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_should_regrade_quiz_attempt_as_explicit_high_risk_append_only_action(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    content_admin = _user("content_admin")
    learner = _user("user", department="华东销售")
    manager = _user("training_manager", department="华东销售")
    outside_manager = _user("training_manager", department="华南销售")
    category = QuestionCategory(
        category_id="newcomer-regrade-category",
        name="商务技巧重评",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question("newcomer-regrade-question", category_id=category.category_id)
    test_db.add_all([admin, content_admin, learner, manager, outside_manager, category, question])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/newcomer-training/papers",
        headers=_auth_headers(admin),
        json={
            "paper_key": "business-skills-regrade-paper",
            "title": "商务技巧重评考卷",
            "module_key": "business_skills",
            "pass_threshold": 10,
            "questions": [
                {
                    "question_id": question.question_id,
                    "order_index": 1,
                    "points": 10,
                }
            ],
        },
    )
    assert create_response.status_code == 200
    paper_id = create_response.json()["data"]["paper_id"]

    first_publish = await async_client.post(
        f"/api/v1/admin/newcomer-training/papers/{paper_id}/publish",
        headers=_auth_headers(admin),
    )
    assert first_publish.status_code == 200
    first_revision = await _latest_paper_revision(test_db, paper_id)

    attempt_response = await async_client.post(
        "/api/v1/newcomer-training/paper-attempts",
        headers=_auth_headers(learner),
        json={
            "paper_id": paper_id,
            "answers": [
                {
                    "question_id": question.question_id,
                    "answer_payload": "A",
                }
            ],
        },
    )
    assert attempt_response.status_code == 200
    attempt = attempt_response.json()["data"]
    assert attempt["paper_revision_id"] == first_revision.revision_id
    assert attempt["total_score"] == 10
    assert attempt["passed"] is True
    await _link_activity_evidence(
        test_db, learner=learner, evidence_id=str(attempt["attempt_id"])
    )

    question.scoring_criteria = {
        **question.scoring_criteria,
        "correct_answer": "B",
    }
    await test_db.commit()
    update_response = await async_client.put(
        f"/api/v1/admin/newcomer-training/papers/{paper_id}",
        headers=_auth_headers(admin),
        json={
            "title": "商务技巧重评考卷第二版",
            "module_key": "business_skills",
            "pass_threshold": 10,
            "questions": [
                {
                    "question_id": question.question_id,
                    "order_index": 1,
                    "points": 10,
                }
            ],
        },
    )
    assert update_response.status_code == 200
    second_publish = await async_client.post(
        f"/api/v1/admin/newcomer-training/papers/{paper_id}/publish",
        headers=_auth_headers(admin),
    )
    assert second_publish.status_code == 200
    second_revision = await _latest_paper_revision(test_db, paper_id)
    assert second_revision.revision_id != first_revision.revision_id

    service = SalesTrainerRegradeService(test_db)
    same_scope_preview = await service.preview_quiz_attempt(
        attempt["attempt_id"],
        target_revision_id=second_revision.revision_id,
        viewer=manager,
        team_department=manager.department,
    )
    assert same_scope_preview.target_id == attempt["attempt_id"]
    with pytest.raises(SalesTrainerRegradeServiceError) as denied:
        await service.preview_quiz_attempt(
            attempt["attempt_id"],
            target_revision_id=second_revision.revision_id,
            viewer=outside_manager,
            team_department=outside_manager.department,
        )
    assert denied.value.code == "[REGRADING_TARGET_NOT_FOUND]"
    monkeypatch.setattr(
        "sales_trainer.regrade_api.can_regrade_sales_trainer_history",
        lambda user: user.role in {"admin", "ops", "training_manager"},
    )
    manager_preview = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"quiz-attempts/{attempt['attempt_id']}/preview",
        headers=_auth_headers(manager),
        json={"target_revision_id": second_revision.revision_id},
    )
    assert manager_preview.status_code == 200
    cross_department_run = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"quiz-attempts/{attempt['attempt_id']}/run",
        headers=_auth_headers(outside_manager),
        json={
            "target_revision_id": second_revision.revision_id,
            "reason": "跨部门负责人不应能重评历史考试记录。",
        },
    )
    assert cross_department_run.status_code == 404
    assert cross_department_run.json()["error"] == "[REGRADING_TARGET_NOT_FOUND]"
    assert await test_db.scalar(text("select count(*) from sales_trainer_regrade_runs")) == 0

    forbidden_preview = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"quiz-attempts/{attempt['attempt_id']}/preview",
        headers=_auth_headers(content_admin),
        json={"target_revision_id": second_revision.revision_id},
    )
    assert forbidden_preview.status_code == 403

    missing_reason = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"quiz-attempts/{attempt['attempt_id']}/run",
        headers=_auth_headers(admin),
        json={"target_revision_id": second_revision.revision_id, "reason": ""},
    )
    assert missing_reason.status_code == 422

    preview_response = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"quiz-attempts/{attempt['attempt_id']}/preview",
        headers=_auth_headers(admin),
        json={"target_revision_id": second_revision.revision_id},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["target_type"] == "quiz_attempt"
    assert preview["target_id"] == attempt["attempt_id"]
    assert preview["impact_scope"]["record_count"] == 1
    assert preview["impact_scope"]["future_records_changed"] is False
    assert preview["before_snapshot"]["total_score"] == 10
    assert preview["after_snapshot"]["total_score"] == 0
    assert preview["after_snapshot"]["target_revision_id"] == second_revision.revision_id

    run_response = await async_client.post(
        "/api/v1/admin/newcomer-training/regrades/"
        f"quiz-attempts/{attempt['attempt_id']}/run",
        headers=_auth_headers(admin),
        json={
            "target_revision_id": second_revision.revision_id,
            "reason": "正确答案修订后重新评估历史成绩，仅生成补充记录",
        },
    )
    assert run_response.status_code == 200
    run = run_response.json()["data"]
    assert run["status"] == "completed"
    assert run["target_revision_id"] == second_revision.revision_id
    assert run["reason"] == "正确答案修订后重新评估历史成绩，仅生成补充记录"
    assert run["trace_id"]
    assert run["before_snapshot"]["total_score"] == 10
    assert run["after_snapshot"]["total_score"] == 0

    attempt_after_regrade = await async_client.get(
        f"/api/v1/admin/sales-trainer/quiz-attempts/{attempt['attempt_id']}",
        headers=_auth_headers(admin),
    )
    assert attempt_after_regrade.status_code == 200
    preserved_attempt = attempt_after_regrade.json()["data"]
    assert preserved_attempt["total_score"] == 10
    assert preserved_attempt["answers"][0]["correct_answer"] == "A"

    run_count = await test_db.scalar(text("select count(*) from sales_trainer_regrade_runs"))
    assert run_count == 1
    logs = await _regrade_logs(test_db, attempt["attempt_id"])
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "historical_regrade.completed"
    assert log.request_id == run["trace_id"]
    assert log.metadata_json["reason"] == run["reason"]
    assert log.metadata_json["before_snapshot"]["total_score"] == 10
    assert log.metadata_json["after_snapshot"]["total_score"] == 0
    assert log.metadata_json["impact_scope"]["record_count"] == 1


async def _latest_paper_revision(
    test_db: AsyncSession,
    paper_id: str,
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "sales_trainer_exam_paper",
            SalesTrainerAssetRevision.logical_id == paper_id,
            SalesTrainerAssetRevision.status == "published",
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _regrade_logs(
    test_db: AsyncSession,
    attempt_id: str,
) -> list[SalesTrainerOperationLog]:
    result = await test_db.execute(
        select(SalesTrainerOperationLog)
        .where(
            SalesTrainerOperationLog.target_type == "sales_trainer_quiz_attempt",
            SalesTrainerOperationLog.target_id == attempt_id,
            SalesTrainerOperationLog.action == "historical_regrade.completed",
        )
        .order_by(SalesTrainerOperationLog.created_at.desc())
    )
    return list(result.scalars().all())
