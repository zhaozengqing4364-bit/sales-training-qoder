from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import QuestionCategory
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerOperationLog


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-question-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Question API {role}",
        email=f"newcomer-question-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_should_update_published_question_as_future_revision_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="newcomer-question-api-category",
        name="商务技巧题目 API",
        order_index=1,
        usage_scope="sales_trainer",
    )
    test_db.add_all([admin, category])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/questions",
        headers=_auth_headers(admin),
        json={
            "title": "旧题",
            "stem": "见客户前应优先准备什么？",
            "category_id": category.category_id,
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "客户背景和拜访目标"},
                {"value": "B", "label": "临场自由发挥"},
            ],
            "correct_answer": "A",
            "explanation": "先准备客户背景和目标。",
        },
    )
    assert create_response.status_code == 200
    question_id = create_response.json()["data"]["question_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/questions/{question_id}/publish",
        headers=_auth_headers(admin),
    )
    assert publish_response.status_code == 200
    active_revision = await _latest_question_revision(
        test_db,
        question_id,
        status="published",
    )

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/questions/{question_id}",
        headers=_auth_headers(admin),
        json={
            "title": "新题",
            "stem": "见客户前最不应该依赖什么？",
            "options": [
                {"value": "A", "label": "客户背景和拜访目标"},
                {"value": "B", "label": "临场自由发挥"},
            ],
            "correct_answer": "B",
            "explanation": "不能只依赖临场发挥。",
        },
    )

    assert update_response.status_code == 200
    update_trace_id = update_response.json()["trace_id"]
    response_data = update_response.json()["data"]
    assert response_data["title"] == "旧题"
    assert response_data["correct_answer"] == "A"

    working_revision = await _latest_question_revision(
        test_db,
        question_id,
        status="working",
    )
    assert working_revision.source_revision_id == active_revision.revision_id
    assert working_revision.change_class == "scoring_high_risk"
    assert working_revision.payload_json["title"] == "新题"
    assert working_revision.payload_json["scoring_criteria"]["correct_answer"] == "B"

    audit_log = await _latest_question_log(test_db, question_id)
    assert audit_log.action == "question_revision_saved"
    assert audit_log.metadata_json["future_only"] is True
    assert audit_log.metadata_json["working_revision_id"] == working_revision.revision_id
    assert audit_log.metadata_json["source_revision_id"] == active_revision.revision_id
    assert audit_log.request_id == update_trace_id
    assert audit_log.metadata_json["trace_id"] == update_trace_id


async def _latest_question_revision(
    test_db: AsyncSession,
    question_id: str,
    *,
    status: str,
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "sales_trainer_question",
            SalesTrainerAssetRevision.logical_id == question_id,
            SalesTrainerAssetRevision.status == status,
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _latest_question_log(
    test_db: AsyncSession,
    question_id: str,
) -> SalesTrainerOperationLog:
    result = await test_db.execute(
        select(SalesTrainerOperationLog)
        .where(
            SalesTrainerOperationLog.target_type == "sales_trainer_question",
            SalesTrainerOperationLog.target_id == question_id,
        )
        .order_by(SalesTrainerOperationLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one()
