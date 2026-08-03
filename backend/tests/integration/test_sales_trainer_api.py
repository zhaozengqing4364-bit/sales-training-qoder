from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"sales-trainer-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Sales Trainer API {role}",
        email=f"sales-trainer-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


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
    assert list_response.status_code == 200
    assert [item["question_id"] for item in list_response.json()["data"]["items"]] == [
        question["question_id"]
    ]


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
            "ai_scoring": {"enabled": True},
        },
    )

    assert invalid_response.status_code == 422
    assert invalid_response.json()["error"] == "[QUESTION_CORRECT_ANSWER_INVALID]"
    assert multi_response.status_code == 200
    assert multi_response.json()["data"]["scoring_criteria"]["correct_answers"] == [
        "A",
        "B",
    ]
    assert short_response.status_code == 200
    assert short_response.json()["data"]["ai_scoring"] == {
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
    for secret in ("secret-id", "secret-key", "dashscope-secret", "deucate-secret"):
        assert secret not in serialized


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
