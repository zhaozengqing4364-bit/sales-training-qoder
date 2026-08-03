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
from sales_trainer.schemas import SalesTrainerUnitCreate, UnitQuestionBinding
from sales_trainer.services.unit_service import UnitService


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-unit-revision-api-{role}-{suffix}",
        name=f"Newcomer Unit Revision API {role}",
        email=f"newcomer-unit-revision-api-{role}-{suffix}@example.com",
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
async def test_should_list_and_rollback_unit_revisions_via_sales_trainer_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="newcomer-unit-revision-api-category",
        name="训练单元修订 API",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "unit-revision-api-q1",
        category_id=category.category_id,
        title="第一版题",
    )
    second = _question(
        "unit-revision-api-q2",
        category_id=category.category_id,
        title="第二版题",
    )
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="商务技巧第一版单元",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    initial_revision = await _latest_unit_revision(test_db, str(unit.unit_id))

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}",
        headers=_auth_headers(admin),
        json={
            "name": "商务技巧第二版单元",
            "config": {"quiz": {"pass_threshold": 12}},
            "questions": [
                {
                    "question_id": second.question_id,
                    "order_index": 1,
                    "points": 12,
                }
            ],
        },
    )
    assert update_response.status_code == 200
    update_trace_id = update_response.json()["trace_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}/publish",
        headers=_auth_headers(admin),
    )
    assert publish_response.status_code == 200
    publish_trace_id = publish_response.json()["trace_id"]

    history_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}/revisions",
        headers=_auth_headers(admin),
    )
    assert history_response.status_code == 200
    history = history_response.json()["data"]["items"]
    assert [item["title"] for item in history] == [
        "商务技巧第二版单元",
        "商务技巧第一版单元",
    ]
    assert history[0]["is_active"] is True
    assert history[1]["is_active"] is False
    assert history[0]["question_count"] == 1

    rollback_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}/rollback",
        headers=_auth_headers(admin),
        json={
            "target_revision_id": initial_revision.revision_id,
            "reason": "恢复第一版训练单元",
        },
    )
    assert rollback_response.status_code == 200
    rollback_trace_id = rollback_response.json()["trace_id"]
    rolled_back = rollback_response.json()["data"]
    assert rolled_back["name"] == "商务技巧第一版单元"
    assert rolled_back["config"]["quiz"]["pass_threshold"] == 10
    assert rolled_back["questions"][0]["question_id"] == first.question_id

    logs = await _unit_logs(test_db, str(unit.unit_id))
    saved_log = next(log for log in logs if log.action == "unit_revision_saved")
    published_log = next(log for log in logs if log.action == "unit_revision_published")
    rollback_log = next(log for log in logs if log.action == "unit_revision_rolled_back")
    assert saved_log.request_id == update_trace_id
    assert saved_log.metadata_json["trace_id"] == update_trace_id
    assert published_log.request_id == publish_trace_id
    assert published_log.metadata_json["trace_id"] == publish_trace_id
    assert rollback_log.request_id == rollback_trace_id
    assert rollback_log.metadata_json["trace_id"] == rollback_trace_id


@pytest.mark.asyncio
async def test_should_expose_unit_revision_history_via_sales_trainer_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="compatible-unit-revision-api-category",
        name="兼容训练单元修订 API",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "compatible-unit-revision-api-q1",
        category_id=category.category_id,
        title="兼容第一版题",
    )
    second = _question(
        "compatible-unit-revision-api-q2",
        category_id=category.category_id,
        title="兼容第二版题",
    )
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="兼容商务技巧第一版",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    initial_revision = await _latest_unit_revision(test_db, str(unit.unit_id))

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}",
        headers=_auth_headers(admin),
        json={
            "name": "兼容商务技巧第二版",
            "config": {"quiz": {"pass_threshold": 12}},
            "questions": [
                {
                    "question_id": second.question_id,
                    "order_index": 1,
                    "points": 12,
                }
            ],
        },
    )
    assert update_response.status_code == 200
    publish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}/publish",
        headers=_auth_headers(admin),
    )
    assert publish_response.status_code == 200

    history_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}/revisions",
        headers=_auth_headers(admin),
    )
    assert history_response.status_code == 200
    history = history_response.json()["data"]["items"]
    assert [item["title"] for item in history] == [
        "兼容商务技巧第二版",
        "兼容商务技巧第一版",
    ]

    rollback_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/units/{unit.unit_id}/rollback",
        headers=_auth_headers(admin),
        json={
            "target_revision_id": initial_revision.revision_id,
            "reason": "兼容入口恢复第一版训练单元",
        },
    )
    assert rollback_response.status_code == 200
    rolled_back = rollback_response.json()["data"]
    assert rolled_back["name"] == "兼容商务技巧第一版"


async def _latest_unit_revision(
    test_db: AsyncSession,
    unit_id: str,
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "sales_trainer_unit",
            SalesTrainerAssetRevision.logical_id == unit_id,
            SalesTrainerAssetRevision.status == "published",
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _unit_logs(
    test_db: AsyncSession,
    unit_id: str,
) -> list[SalesTrainerOperationLog]:
    result = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.target_type == "sales_trainer_unit",
            SalesTrainerOperationLog.target_id == unit_id,
        )
    )
    return list(result.scalars().all())
