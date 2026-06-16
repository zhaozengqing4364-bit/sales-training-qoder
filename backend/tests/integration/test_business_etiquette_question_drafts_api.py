from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import PromptTemplate, User
from common.error_handling.result import Result
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from sales_trainer.schemas import (
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteChapterCapabilityBinding,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    BusinessEtiquetteCapabilityService,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.question_bank.contracts import SALES_TRAINER_QUESTION_SCOPE


class _FakeLlmService:
    async def generate(self, **_: object) -> Result[str]:
        return Result.ok(
            json.dumps(
                {
                    "drafts": [
                        {
                            "question_type": "single_choice",
                            "title": "商务迟到处理",
                            "stem": "商务拜访即将迟到时，最合适的做法是什么？",
                            "options": [
                                {"value": "A", "label": "提前说明并表达歉意"},
                                {"value": "B", "label": "到场后再解释"},
                            ],
                            "correct_answer": "A",
                            "explanation": "守时和尊重边界是商务礼仪基础。",
                            "capability_keys": ["respect_boundaries"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-q-draft-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Business Etiquette Question Draft API {role}",
        email=f"business-etiquette-q-draft-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


async def _seed_training_pack(test_db: AsyncSession, *, admin: User) -> None:
    content = LearningContent(
        title="商务礼仪：新人的第一本职业素养手册",
        summary="商务礼仪 API 测试资料",
        owner="新人训练路径",
        source="integration-test",
        status="draft",
        content_hash=uuid.uuid4().hex,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(content)
    await test_db.flush()
    chapter = LearningChapter(
        learning_content_id=content.learning_content_id,
        title="第 1 章 商务礼仪原则",
        content="尊重、守时、边界感是商务礼仪的基础。迟到需要提前说明并表达歉意。",
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(chapter)
    await test_db.flush()
    await SalesTrainerAssetRevisionService(test_db).save_working_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload={
            "schema_version": 1,
            "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
            "learning_content_id": content.learning_content_id,
            "book_title": content.title,
            "original_chapter_count": 1,
            "original_chapters": [
                {"title": chapter.title, "order_index": 1, "line_number": 1}
            ],
        },
        actor=admin,
        change_class="semantic",
        reason="导入商务礼仪 API 测试资料",
    )
    await test_db.commit()
    seed = default_business_etiquette_capability_snapshot()
    capabilities = [
        BusinessEtiquetteCapabilityConfig.model_validate(item)
        for item in seed["capabilities"]
    ]
    await BusinessEtiquetteCapabilityService(test_db).save_snapshot(
        capabilities=capabilities,
        chapter_bindings=[
            BusinessEtiquetteChapterCapabilityBinding(
                chapter_order=1,
                capability_keys=["respect_boundaries"],
            )
        ],
        actor=admin,
        reason="保存商务礼仪 API 测试能力点",
    )


async def _seed_prompt_template(test_db: AsyncSession) -> PromptTemplate:
    template = PromptTemplate(
        id=str(uuid.uuid4()),
        name="商务礼仪 API 题目草稿生成",
        prompt_type="scoring",
        category="sales_trainer",
        template=(
            "章节：{{ chapter_content }}。能力点：{{ capabilities_json }}。"
            "题型：{{ question_types_json }}。数量：{{ draft_count }}。"
            "输出：{{ output_schema }}。"
        ),
        variables=[
            "chapter_content",
            "capabilities_json",
            "question_types_json",
            "draft_count",
            "output_schema",
        ],
        is_active=True,
    )
    test_db.add(template)
    await test_db.commit()
    return template


@pytest.mark.asyncio
async def test_should_reject_question_draft_generation_without_manager_permission(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    test_db.add(learner)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/question-drafts/generate",
        headers=_auth_headers(learner),
        json={
            "chapter_order": 1,
            "prompt_template_id": str(uuid.uuid4()),
            "question_types": ["single_choice"],
        },
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_generate_and_approve_question_draft_via_admin_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sales_trainer.services.business_etiquette_question_draft_service."
        "get_llm_service",
        lambda: _FakeLlmService(),
    )
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_prompt_template(test_db)
    category = QuestionCategory(
        name="商务礼仪",
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(category)
    await test_db.commit()

    generate_response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/question-drafts/generate",
        headers=_auth_headers(admin),
        json={
            "chapter_order": 1,
            "prompt_template_id": str(template.id),
            "question_types": ["single_choice"],
            "draft_count": 1,
            "capability_keys": ["respect_boundaries"],
            "model_config": {
                "provider": "openai",
                "base_url": "https://example.com/v1",
                "model_name": "unit-test",
            },
        },
    )

    assert generate_response.status_code == 200, generate_response.text
    generated = generate_response.json()["data"]
    assert generated["total"] == 1
    draft = generated["items"][0]
    assert draft["status"] == "pending_review"
    assert draft["model_config"]["model_name"] == "unit-test"

    approve_response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/question-drafts/"
        f"{draft['draft_id']}/approve",
        headers=_auth_headers(admin),
        json={
            "category_id": str(category.category_id),
            "review_notes": "API 审批通过",
        },
    )

    assert approve_response.status_code == 200, approve_response.text
    approved = approve_response.json()["data"]
    assert approved["status"] == "converted"
    assert approved["question_id"]
    question = await test_db.get(QuestionItem, approved["question_id"])
    assert question is not None
    assert question.status == "draft"
    assert "capability:respect_boundaries" in question.tags
