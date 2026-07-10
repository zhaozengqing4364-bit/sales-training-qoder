from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import SalesTrainerUnit
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.learning_topic_config_service import (
    BUSINESS_ETIQUETTE_TOPIC_KEY,
    BUSINESS_SKILLS_SOURCE_MODULE_KEY,
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.question_bank.contracts import SALES_TRAINER_QUESTION_SCOPE


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str, *, department: str | None = None) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-quiz-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Business Etiquette Quiz API {role}",
        email=f"business-etiquette-quiz-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        department=department,
    )


async def _seed_active_path(
    test_db: AsyncSession,
    *,
    admin: User,
    include_unmet_main_prerequisite: bool = False,
) -> None:
    unit = SalesTrainerUnit(
        unit_id=f"be-quiz-{uuid.uuid4().hex[:8]}",
        name="商务礼仪考试",
        unit_type="quiz",
        status="published",
        config={},
    )
    prerequisite_units: list[SalesTrainerUnit] = []
    if include_unmet_main_prerequisite:
        prerequisite_units = [
            SalesTrainerUnit(
                unit_id=f"be-owner-{uuid.uuid4().hex[:8]}",
                name="PPT 讲解",
                unit_type="audio_scoring",
                status="published",
                config={},
            ),
            SalesTrainerUnit(
                unit_id=f"be-dependent-{uuid.uuid4().hex[:8]}",
                name="公司产品 Demo",
                unit_type="audio_scoring",
                status="published",
                config={},
            ),
        ]
    test_db.add_all([unit, *prerequisite_units])
    await test_db.flush()
    modules: list[dict[str, object]] = []
    if include_unmet_main_prerequisite:
        owner, dependent = prerequisite_units
        modules.extend(
            [
                {
                    "module_key": "ppt_explanation",
                    "module_type": "audio_scoring",
                    "enabled": True,
                    "order_index": 1,
                    "title": "PPT 讲解",
                    "target_unit_id": owner.unit_id,
                    "unlock_after_unit_ids": [],
                    "completion_rule": "passed",
                },
                {
                    "module_key": "company_product_demo",
                    "module_type": "audio_scoring",
                    "enabled": True,
                    "order_index": 2,
                    "title": "公司产品 Demo",
                    "target_unit_id": dependent.unit_id,
                    "unlock_after_unit_ids": [owner.unit_id],
                    "completion_rule": "passed",
                },
            ]
        )
    modules.append(
        {
            "module_key": "business_skills",
            "module_type": "article_exam",
            "enabled": True,
            "order_index": 3,
            "title": "商务礼仪",
            "description": "按小单元完成商务礼仪训练。",
            "target_unit_id": unit.unit_id,
            "learning_content_id": None,
            "learner_level_required": [],
            "exam_paper_id": None,
            "material_id": None,
            "material_version_id": None,
            "scoring_prompt_id": None,
            "disabled_reason": None,
            "unlock_after_unit_ids": [],
            "completion_rule": "passed",
            "primary_action_label": "开始训练",
            "retry_action_label": None,
            "review_action_label": None,
            "guidance_templates": {},
            "ai_coach": None,
            "learning_units": [_business_learning_unit()],
        }
    )
    payload = {
        "path_key": NEWCOMER_PATH_LOGICAL_ID,
        "title": "新人训练路径",
        "goal_title": "完成商务礼仪训练",
        "description": None,
        "enabled": True,
        "modules": modules,
    }
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload,
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪小测路径配置",
    )
    await test_db.commit()


async def _seed_active_training_pack(test_db: AsyncSession, *, admin: User) -> None:
    snapshot = default_business_etiquette_capability_snapshot()
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload={
            "schema_version": 1,
            "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
            "book_title": "商务礼仪",
            "original_chapter_count": 1,
            "original_chapters": [{"title": "第 1 章", "order_index": 1}],
            CAPABILITY_SNAPSHOT_KEY: {
                "schema_version": 1,
                "capabilities": [
                    {**item, "status": "published"} for item in snapshot["capabilities"]
                ],
                "chapter_bindings": [
                    {
                        "chapter_order": 1,
                        "capability_keys": ["respect_boundaries"],
                    }
                ],
            },
        },
        actor=admin,
        change_class="semantic",
        reason="发布商务礼仪训练包",
    )
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload={
            "schema_version": NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
            "topics": [
                {
                    "topic_key": BUSINESS_ETIQUETTE_TOPIC_KEY,
                    "source_module_key": BUSINESS_SKILLS_SOURCE_MODULE_KEY,
                    "enabled": True,
                    "title": "商务礼仪规范",
                    "order_index": 1,
                    "learning_units": [_business_learning_unit()],
                    "required": False,
                    "blocks_next": False,
                    "score_display_policy": "quiz_attempt_score",
                }
            ],
        },
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪学习专题",
    )
    await test_db.commit()


def _business_learning_unit() -> dict[str, object]:
    return {
        "unit_key": "trust_foundation",
        "title": "职业信任底座",
        "description": "尊重分寸、第一印象。",
        "order_index": 1,
        "enabled": True,
        "source_chapter_orders": [1],
        "capability_keys": ["respect_boundaries"],
        "unlock_after_unit_keys": [],
        "require_reading": True,
        "require_quiz": True,
        "require_ai_coach": True,
        "quiz_question_count": 1,
        "quiz_pass_threshold": None,
        "quiz_allow_retake": True,
        "quiz_max_attempts": None,
        "quiz_question_type_weights": {"single_choice": 1},
        "allow_skip_reading": False,
        "block_next_until_complete": True,
        "empty_state_message": None,
    }


async def _seed_published_question(
    test_db: AsyncSession, *, admin: User
) -> QuestionItem:
    category = QuestionCategory(
        name="商务礼仪",
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(category)
    await test_db.flush()
    question = QuestionItem(
        category_id=category.category_id,
        title="迟到处理",
        stem="商务拜访即将迟到时，最合适的做法是什么？",
        reference_answer="提前说明并表达歉意",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "提前说明并表达歉意"},
                {"value": "B", "label": "到场后再解释"},
            ],
            "correct_answer": "A",
            "dimensions": ["respect_boundaries"],
            "explanation": "守时体现尊重。",
        },
        scoring_dimensions=["respect_boundaries"],
        tags=[
            "business_etiquette",
            "capability:respect_boundaries",
            "chapter:1",
        ],
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        difficulty="easy",
        status="published",
        safety_flagged=False,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(question)
    await test_db.commit()
    await test_db.refresh(question)
    return question


@pytest.mark.asyncio
async def test_should_get_submit_and_list_business_etiquette_unit_quiz_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(test_db, admin=admin)
    await _seed_active_training_pack(test_db, admin=admin)
    question = await _seed_published_question(test_db, admin=admin)

    quiz_response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/"
        "learning-units/trust_foundation/quiz",
        headers=_auth_headers(learner),
    )

    assert quiz_response.status_code == 200, quiz_response.text
    quiz = quiz_response.json()["data"]
    assert quiz["learning_unit_key"] == "trust_foundation"
    assert quiz["question_count"] == 1
    assert quiz["questions"][0]["question_id"] == question.question_id
    assert quiz["questions"][0]["capability_keys"] == ["respect_boundaries"]

    submit_response = await async_client.post(
        "/api/v1/newcomer-training/business-etiquette/"
        "learning-units/trust_foundation/quiz-attempts",
        headers=_auth_headers(learner),
        json={
            "answers": [
                {
                    "question_id": question.question_id,
                    "answer_payload": "A",
                }
            ],
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    attempt = submit_response.json()["data"]
    assert attempt["status"] == "scored"
    assert attempt["passed"] is True
    assert attempt["capability_scores"][0]["capability_key"] == "respect_boundaries"
    assert attempt["answers"][0]["is_correct"] is True
    assert attempt["answers"][0]["analysis"] == "守时体现尊重。"
    assert attempt["answers"][0]["scoring_source"] == "rule_answer_key"
    assert attempt["answers"][0]["scoring_provider"] is None
    assert attempt["answers"][0]["scoring_model"] is None
    assert attempt["answers"][0]["scoring_latency_ms"] is None

    learner_list_response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/"
        "learning-units/trust_foundation/quiz-attempts?limit=10",
        headers=_auth_headers(learner),
    )

    assert learner_list_response.status_code == 200, learner_list_response.text
    learner_attempts = learner_list_response.json()["data"]
    assert learner_attempts["total"] == 1
    assert learner_attempts["items"][0]["attempt_id"] == attempt["attempt_id"]
    assert learner_attempts["items"][0]["answers"][0]["analysis"] == "守时体现尊重。"
    assert (
        learner_attempts["items"][0]["answers"][0]["scoring_source"]
        == "rule_answer_key"
    )

    list_response = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/quiz-attempts"
        "?learning_unit_key=trust_foundation",
        headers=_auth_headers(admin),
    )

    assert list_response.status_code == 200, list_response.text
    attempts = list_response.json()["data"]
    assert attempts["total"] == 1
    assert attempts["items"][0]["attempt_id"] == attempt["attempt_id"]
    assert attempts["items"][0]["user_id"] == str(learner.user_id)


@pytest.mark.asyncio
async def test_should_reject_quiz_attempt_list_without_manager_permission(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    content_admin = _user("content_admin")
    test_db.add(content_admin)
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/quiz-attempts",
        headers=_auth_headers(content_admin),
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_keep_optional_topic_accessible_when_main_prerequisite_is_unmet(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(
        test_db,
        admin=admin,
        include_unmet_main_prerequisite=True,
    )
    await _seed_active_training_pack(test_db, admin=admin)
    question = await _seed_published_question(test_db, admin=admin)

    journey_response = await async_client.get(
        "/api/v1/sales-trainer/journey",
        headers=_auth_headers(learner),
    )
    assert journey_response.status_code == 200, journey_response.text
    dependent_module = next(
        module
        for module in journey_response.json()["data"]["modules"]
        if module["module_key"] == "company_product_demo"
        and module["kind"] == "audio_submission"
    )
    assert dependent_module["locked"] is True
    assert dependent_module["status"] == "not_started"
    assert any(
        diagnostic["code"] == "[NEWCOMER_PREREQUISITE_NOT_COMPLETED]"
        and diagnostic["terminal"] is False
        for diagnostic in dependent_module["diagnostics"]
    )

    quiz_response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/"
        "learning-units/trust_foundation/quiz",
        headers=_auth_headers(learner),
    )
    submit_response = await async_client.post(
        "/api/v1/newcomer-training/business-etiquette/"
        "learning-units/trust_foundation/quiz-attempts",
        headers=_auth_headers(learner),
        json={
            "answers": [
                {
                    "question_id": question.question_id,
                    "answer_payload": "A",
                }
            ]
        },
    )
    list_response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/"
        "learning-units/trust_foundation/quiz-attempts?limit=10",
        headers=_auth_headers(learner),
    )

    for response in (quiz_response, submit_response, list_response):
        assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_should_scope_business_etiquette_quiz_attempts_to_manager_department(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    manager = _user("training_manager", department="华东销售")
    east_learner = _user("user", department="华东销售")
    west_learner = _user("user", department="华北销售")
    test_db.add_all([admin, manager, east_learner, west_learner])
    await test_db.commit()
    await _seed_active_path(test_db, admin=admin)
    await _seed_active_training_pack(test_db, admin=admin)
    question = await _seed_published_question(test_db, admin=admin)

    for learner in (east_learner, west_learner):
        response = await async_client.post(
            "/api/v1/newcomer-training/business-etiquette/"
            "learning-units/trust_foundation/quiz-attempts",
            headers=_auth_headers(learner),
            json={
                "answers": [
                    {
                        "question_id": question.question_id,
                        "answer_payload": "A",
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text

    manager_response = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/quiz-attempts"
        "?learning_unit_key=trust_foundation",
        headers=_auth_headers(manager),
    )

    assert manager_response.status_code == 200, manager_response.text
    manager_payload = manager_response.json()["data"]
    assert manager_payload["total"] == 1
    assert manager_payload["items"][0]["user_id"] == str(east_learner.user_id)
    assert manager_payload["items"][0]["user_department"] == "华东销售"

    cross_department_response = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/quiz-attempts"
        f"?user_id={west_learner.user_id}",
        headers=_auth_headers(manager),
    )

    assert cross_department_response.status_code == 200, cross_department_response.text
    cross_department_payload = cross_department_response.json()["data"]
    assert cross_department_payload["total"] == 0
    assert cross_department_payload["items"] == []
