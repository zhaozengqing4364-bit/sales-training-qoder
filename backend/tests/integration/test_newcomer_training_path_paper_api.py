from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerOperationLog


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-paper-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Paper API {role}",
        email=f"newcomer-paper-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _question(question_id: str, *, category_id: str, title: str) -> QuestionItem:
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title=title,
        stem=f"{title} 怎么做？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "正确"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )


@pytest.mark.asyncio
async def test_should_create_publish_and_fetch_sales_trainer_paper_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="newcomer-paper-api-category",
        name="商务技巧 API",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "newcomer-paper-api-question-1",
        category_id=category.category_id,
        title="见客户前礼仪",
    )
    test_db.add_all([admin, learner, category, question])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/papers",
        headers=_auth_headers(admin),
        json={
            "paper_key": "business-skills-api-paper",
            "title": "商务礼仪入门考卷",
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
    paper = create_response.json()["data"]
    assert paper["status"] == "draft"

    publish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/papers/{paper['paper_id']}/publish",
        headers=_auth_headers(admin),
    )
    assert publish_response.status_code == 200

    learner_response = await async_client.get(
        f"/api/v1/sales-trainer/papers/{paper['paper_id']}",
        headers=_auth_headers(learner),
    )
    assert learner_response.status_code == 200
    learner_paper = learner_response.json()["data"]
    assert learner_paper["title"] == "商务礼仪入门考卷"
    assert learner_paper["questions"][0]["question_id"] == question.question_id


@pytest.mark.asyncio
async def test_should_hide_draft_sales_trainer_paper_from_learner_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="newcomer-paper-draft-api-category",
        name="商务技巧草稿 API",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "newcomer-paper-draft-api-question-1",
        category_id=category.category_id,
        title="草稿考卷题",
    )
    test_db.add_all([admin, learner, category, question])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/papers",
        headers=_auth_headers(admin),
        json={
            "paper_key": "business-skills-draft-api-paper",
            "title": "草稿商务礼仪考卷",
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

    learner_response = await async_client.get(
        f"/api/v1/sales-trainer/papers/{paper_id}",
        headers=_auth_headers(learner),
    )

    assert learner_response.status_code == 404
    assert learner_response.json()["error"] == "[PAPER_NOT_PUBLISHED]"


@pytest.mark.asyncio
async def test_should_update_draft_sales_trainer_paper_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="newcomer-paper-update-api-category",
        name="商务技巧更新 API",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "newcomer-paper-update-api-question-1",
        category_id=category.category_id,
        title="原题",
    )
    second = _question(
        "newcomer-paper-update-api-question-2",
        category_id=category.category_id,
        title="新增题",
    )
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/papers",
        headers=_auth_headers(admin),
        json={
            "paper_key": "business-skills-update-api-paper",
            "title": "商务技巧草稿考卷",
            "module_key": "business_skills",
            "questions": [
                {
                    "question_id": first.question_id,
                    "order_index": 1,
                    "points": 10,
                }
            ],
        },
    )
    assert create_response.status_code == 200
    paper_id = create_response.json()["data"]["paper_id"]

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/papers/{paper_id}",
        headers=_auth_headers(admin),
        json={
            "title": "商务技巧已编辑草稿",
            "module_key": "business_skills",
            "questions": [
                {
                    "question_id": first.question_id,
                    "order_index": 1,
                    "points": 12,
                },
                {
                    "question_id": second.question_id,
                    "order_index": 2,
                    "points": 12,
                },
            ],
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["title"] == "商务技巧已编辑草稿"
    assert [item["question_id"] for item in updated["questions"]] == [
        first.question_id,
        second.question_id,
    ]


@pytest.mark.asyncio
async def test_should_rollback_published_sales_trainer_paper_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="newcomer-paper-rollback-api-category",
        name="商务技巧回滚 API",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "paper-rollback-api-q1",
        category_id=category.category_id,
        title="第一版题",
    )
    second = _question(
        "paper-rollback-api-q2",
        category_id=category.category_id,
        title="第二版题",
    )
    test_db.add_all([admin, learner, category, first, second])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/papers",
        headers=_auth_headers(admin),
        json={
            "paper_key": "business-skills-rollback-api-paper",
            "title": "商务技巧第一版",
            "module_key": "business_skills",
            "questions": [
                {
                    "question_id": first.question_id,
                    "order_index": 1,
                    "points": 10,
                }
            ],
        },
    )
    assert create_response.status_code == 200
    paper_id = create_response.json()["data"]["paper_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/papers/{paper_id}/publish",
        headers=_auth_headers(admin),
    )
    assert publish_response.status_code == 200
    initial_revision = await _latest_paper_revision(test_db, paper_id)

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/papers/{paper_id}",
        headers=_auth_headers(admin),
        json={
            "title": "商务技巧第二版",
            "questions": [
                {
                    "question_id": second.question_id,
                    "order_index": 1,
                    "points": 10,
                }
            ],
        },
    )
    assert update_response.status_code == 200
    update_trace_id = update_response.json()["trace_id"]

    republish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/papers/{paper_id}/publish",
        headers=_auth_headers(admin),
    )
    assert republish_response.status_code == 200
    republish_trace_id = republish_response.json()["trace_id"]
    history_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/papers/{paper_id}/revisions",
        headers=_auth_headers(admin),
    )
    assert history_response.status_code == 200
    history = history_response.json()["data"]["items"]
    assert [item["title"] for item in history] == [
        "商务技巧第二版",
        "商务技巧第一版",
    ]
    assert history[0]["is_active"] is True
    assert history[0]["status"] == "published"
    assert history[1]["is_active"] is False
    second_version = await async_client.get(
        f"/api/v1/sales-trainer/papers/{paper_id}",
        headers=_auth_headers(learner),
    )
    assert second_version.status_code == 200
    assert second_version.json()["data"]["questions"][0]["question_id"] == second.question_id

    rollback_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/papers/{paper_id}/rollback",
        headers=_auth_headers(admin),
        json={
            "target_revision_id": initial_revision.revision_id,
            "reason": "恢复第一版题",
        },
    )
    assert rollback_response.status_code == 200
    rollback_trace_id = rollback_response.json()["trace_id"]

    rolled_back = await async_client.get(
        f"/api/v1/sales-trainer/papers/{paper_id}",
        headers=_auth_headers(learner),
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["data"]["title"] == "商务技巧第一版"
    assert rolled_back.json()["data"]["questions"][0]["question_id"] == first.question_id

    logs = await _paper_logs(test_db, paper_id)
    saved_log = next(log for log in logs if log.action == "exam_paper_revision_saved")
    published_log = next(
        log for log in logs if log.action == "exam_paper_revision_published"
    )
    rollback_log = next(
        log for log in logs if log.action == "exam_paper_revision_rolled_back"
    )
    assert saved_log.request_id == update_trace_id
    assert saved_log.metadata_json["trace_id"] == update_trace_id
    assert published_log.request_id == republish_trace_id
    assert published_log.metadata_json["trace_id"] == republish_trace_id
    assert rollback_log.request_id == rollback_trace_id
    assert rollback_log.metadata_json["trace_id"] == rollback_trace_id


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


async def _paper_logs(
    test_db: AsyncSession,
    paper_id: str,
) -> list[SalesTrainerOperationLog]:
    result = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.target_type == "sales_trainer_exam_paper",
            SalesTrainerOperationLog.target_id == paper_id,
        )
    )
    return list(result.scalars().all())
