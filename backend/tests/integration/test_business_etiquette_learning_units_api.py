from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.services.learning_progress_service import (
    LearningProgressService,
)
from sales_trainer.models import SalesTrainerUnit
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
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


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-units-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Business Etiquette Units {role}",
        email=f"business-etiquette-units-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _learning_unit(index: int, *, chapter_orders: list[int]) -> dict[str, object]:
    capability_keys = {
        1: ["respect_boundaries", "professional_image"],
        2: ["meeting_social_actions"],
        3: ["business_communication"],
        4: ["reception_visit_execution"],
        5: ["meeting_negotiation_order"],
        6: ["dining_social_boundary"],
        7: ["repair_reflection_internalization"],
    }[index]
    return {
        "unit_key": f"etiquette_unit_{index}",
        "title": f"商务礼仪小单元 {index}",
        "description": f"第 {index} 个商务礼仪训练小单元。",
        "order_index": index,
        "enabled": True,
        "source_chapter_orders": chapter_orders,
        "capability_keys": capability_keys,
        "unlock_after_unit_keys": [] if index == 1 else [f"etiquette_unit_{index - 1}"],
        "require_reading": True,
        "require_quiz": True,
        "require_ai_coach": True,
        "allow_skip_reading": False,
        "block_next_until_complete": True,
        "empty_state_message": None,
    }


async def _seed_business_etiquette_path(
    test_db: AsyncSession,
    *,
    admin: User,
    content: LearningContent,
    learner_level_required: list[str] | None = None,
) -> None:
    unit = SalesTrainerUnit(
        unit_id=f"be-units-{uuid.uuid4().hex[:8]}",
        name="商务礼仪考试",
        unit_type="quiz",
        status="published",
        config={},
    )
    test_db.add(unit)
    await test_db.flush()
    payload = {
        "path_key": NEWCOMER_PATH_LOGICAL_ID,
        "title": "新人训练路径",
        "goal_title": "完成商务礼仪训练",
        "description": None,
        "enabled": True,
        "modules": [
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 2,
                "title": "商务礼仪",
                "description": "按 7 个小单元完成商务礼仪训练。",
                "target_unit_id": unit.unit_id,
                "learning_content_id": content.learning_content_id,
                "learner_level_required": learner_level_required or [],
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
                "learning_units": [
                    _learning_unit(1, chapter_orders=[1, 2]),
                    _learning_unit(2, chapter_orders=[3]),
                    _learning_unit(3, chapter_orders=[4]),
                    _learning_unit(4, chapter_orders=[5]),
                    _learning_unit(5, chapter_orders=[6]),
                    _learning_unit(6, chapter_orders=[7]),
                    _learning_unit(7, chapter_orders=[8]),
                ],
            }
        ],
    }
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload,
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪 7 个训练小单元",
    )
    await test_db.commit()


async def _seed_business_etiquette_capabilities(
    test_db: AsyncSession,
    *,
    admin: User,
) -> None:
    seed = default_business_etiquette_capability_snapshot()
    capabilities = [
        {**capability, "status": "published"}
        for capability in seed["capabilities"]
    ]
    payload = {
        "schema_version": 1,
        "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        "learning_content_id": "business-etiquette-learning-content",
        "book_title": "商务礼仪：新人的第一本职业素养手册",
        "original_chapter_count": 8,
        "capability_snapshot": {
            "schema_version": 1,
            "capabilities": capabilities,
            "chapter_bindings": seed["chapter_bindings"],
        },
    }
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=payload,
        actor=admin,
        change_class="semantic",
        reason="发布商务礼仪能力点快照",
    )
    await test_db.commit()


async def _seed_business_etiquette_topic(
    test_db: AsyncSession,
    *,
    admin: User,
    content: LearningContent,
    learning_units: list[dict[str, object]] | None = None,
) -> None:
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload={
            "schema_version": "newcomer_learning_topics_v1",
            "topics": [
                {
                    "topic_key": BUSINESS_ETIQUETTE_TOPIC_KEY,
                    "source_module_key": BUSINESS_SKILLS_SOURCE_MODULE_KEY,
                    "content_kind": "article",
                    "enabled": True,
                    "title": "商务礼仪规范",
                    "order_index": 1,
                    "learning_content_id": content.learning_content_id,
                    "learning_units": (
                        learning_units
                        if learning_units is not None
                        else [
                            _learning_unit(1, chapter_orders=[1, 2]),
                            _learning_unit(2, chapter_orders=[3]),
                            _learning_unit(3, chapter_orders=[4]),
                            _learning_unit(4, chapter_orders=[5]),
                            _learning_unit(5, chapter_orders=[6]),
                            _learning_unit(6, chapter_orders=[7]),
                            _learning_unit(7, chapter_orders=[8]),
                        ]
                    ),
                    "required": False,
                    "blocks_next": False,
                    "score_display_policy": "quiz_attempt_score",
                }
            ],
        },
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪学习专题配置",
    )
    await test_db.commit()


@pytest.mark.asyncio
async def test_should_list_business_etiquette_learning_units_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = LearningContent(
        learning_content_id="business-etiquette-learning-content",
        title="商务礼仪：新人的第一本职业素养手册",
        summary="商务礼仪训练包 v1。",
        owner="新人训练路径",
        source="sales_trainer.business_etiquette_import",
        status="published",
    )
    chapters = [
        LearningChapter(
            chapter_id=f"business-etiquette-chapter-{index}",
            learning_content_id=content.learning_content_id,
            title=f"第 {index} 节",
            content=f"第 {index} 节内容。",
            order_index=index,
        )
        for index in range(1, 9)
    ]
    test_db.add_all([admin, learner, content, *chapters])
    await test_db.commit()
    complete_result = await LearningProgressService(test_db).complete_chapter(
        user_id=str(learner.user_id),
        content_id=content.learning_content_id,
        chapter_id="business-etiquette-chapter-1",
    )
    assert complete_result.is_success
    await _seed_business_etiquette_path(test_db, admin=admin, content=content)
    await _seed_business_etiquette_topic(test_db, admin=admin, content=content)
    await _seed_business_etiquette_capabilities(test_db, admin=admin)

    response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/learning-units",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["module_key"] == "business_skills"
    assert data["learning_content_id"] == content.learning_content_id
    assert data["path_revision_no"] == 1
    assert len(data["units"]) == 7
    first_unit = data["units"][0]
    assert first_unit["title"] == "商务礼仪小单元 1"
    assert first_unit["source_chapter_orders"] == [1, 2]
    assert first_unit["capability_keys"] == [
        "respect_boundaries",
        "professional_image",
    ]
    assert [item["display_name"] for item in first_unit["capabilities"]] == [
        "尊重与分寸感",
        "职业形象与仪态",
    ]
    assert first_unit["progress"]["completed_chapters"] == 1
    assert first_unit["progress"]["total_chapters"] == 2
    assert first_unit["progress"]["is_completed"] is False
    assert first_unit["chapters"][0]["completed"] is True
    assert first_unit["chapters"][1]["completed"] is False


@pytest.mark.asyncio
async def test_should_list_admin_business_etiquette_learning_units_without_learner_progress(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = LearningContent(
        learning_content_id="business-etiquette-admin-content",
        title="商务礼仪：新人的第一本职业素养手册",
        summary="商务礼仪训练包 v1。",
        owner="新人训练路径",
        source="sales_trainer.business_etiquette_import",
        status="published",
    )
    chapters = [
        LearningChapter(
            chapter_id=f"business-etiquette-admin-chapter-{index}",
            learning_content_id=content.learning_content_id,
            title=f"第 {index} 节",
            content=f"第 {index} 节内容。",
            order_index=index,
        )
        for index in range(1, 9)
    ]
    test_db.add_all([admin, learner, content, *chapters])
    await test_db.commit()
    complete_result = await LearningProgressService(test_db).complete_chapter(
        user_id=str(learner.user_id),
        content_id=content.learning_content_id,
        chapter_id="business-etiquette-admin-chapter-1",
    )
    assert complete_result.is_success
    await _seed_business_etiquette_path(test_db, admin=admin, content=content)
    await _seed_business_etiquette_topic(test_db, admin=admin, content=content)
    await _seed_business_etiquette_capabilities(test_db, admin=admin)

    response = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/learning-units",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["module_key"] == "business_skills"
    assert len(data["units"]) == 7
    first_unit = data["units"][0]
    assert first_unit["progress"]["completed_chapters"] == 0
    assert first_unit["progress"]["total_chapters"] == 2
    assert first_unit["progress"]["is_completed"] is False
    assert first_unit["chapters"][0]["completed"] is False

    forbidden = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/learning-units",
        headers=_auth_headers(learner),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_reject_missing_business_etiquette_learning_unit_config(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = LearningContent(
        learning_content_id="be-missing-units-content",
        title="商务礼仪",
        status="published",
    )
    chapter = LearningChapter(
        chapter_id="be-missing-units-chapter",
        learning_content_id=content.learning_content_id,
        title="第一节",
        content="第一节内容。",
        order_index=1,
    )
    test_db.add_all([admin, learner, content, chapter])
    await test_db.commit()
    unit = SalesTrainerUnit(
        unit_id="be-missing-units-target-unit",
        name="商务礼仪考试",
        unit_type="quiz",
        status="published",
        config={},
    )
    test_db.add(unit)
    await test_db.flush()
    payload = {
        "path_key": NEWCOMER_PATH_LOGICAL_ID,
        "title": "新人训练路径",
        "goal_title": None,
        "description": None,
        "enabled": True,
        "modules": [
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 2,
                "title": "商务礼仪",
                "description": None,
                "target_unit_id": unit.unit_id,
                "learning_content_id": content.learning_content_id,
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
                "learning_units": [],
            }
        ],
    }
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload,
        actor=admin,
        change_class="binding",
    )
    await test_db.commit()
    await _seed_business_etiquette_topic(
        test_db,
        admin=admin,
        content=content,
        learning_units=[],
    )

    response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/learning-units",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[BUSINESS_ETIQUETTE_LEARNING_UNITS_MISSING]"


@pytest.mark.asyncio
async def test_should_fail_closed_learning_units_when_journey_module_locked(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = LearningContent(
        learning_content_id="business-etiquette-locked-content",
        title="商务礼仪：锁定路径",
        summary="锁定路径时不能读取。",
        owner="新人训练路径",
        source="sales_trainer.business_etiquette_import",
        status="published",
    )
    chapters = [
        LearningChapter(
            chapter_id=f"business-etiquette-locked-chapter-{index}",
            learning_content_id=content.learning_content_id,
            title=f"第 {index} 节",
            content=f"第 {index} 节内容。",
            order_index=index,
        )
        for index in range(1, 9)
    ]
    test_db.add_all([admin, learner, content, *chapters])
    await test_db.commit()
    await _seed_business_etiquette_path(
        test_db,
        admin=admin,
        content=content,
        learner_level_required=["ready"],
    )

    response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/learning-units",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"] == "[SALES_TRAINER_UNIT_NOT_FOUND]"


@pytest.mark.asyncio
async def test_should_fail_closed_learning_units_when_path_module_binding_missing(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = LearningContent(
        learning_content_id="be-missing-target-content",
        title="商务礼仪：缺少目标单元",
        summary="缺少 target_unit_id 时不能绕过 Journey locked。",
        owner="新人训练路径",
        source="sales_trainer.business_etiquette_import",
        status="published",
    )
    chapters = [
        LearningChapter(
            chapter_id=f"be-missing-target-chapter-{index}",
            learning_content_id=content.learning_content_id,
            title=f"第 {index} 节",
            content=f"第 {index} 节内容。",
            order_index=index,
        )
        for index in range(1, 9)
    ]
    test_db.add_all([admin, learner, content, *chapters])
    await test_db.commit()
    payload = {
        "path_key": NEWCOMER_PATH_LOGICAL_ID,
        "title": "新人训练路径",
        "goal_title": "完成商务礼仪训练",
        "description": None,
        "enabled": True,
        "modules": [
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 2,
                "title": "商务礼仪",
                "description": "缺少 target_unit_id 的坏历史 revision。",
                "target_unit_id": None,
                "learning_content_id": content.learning_content_id,
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
                "learning_units": [
                    _learning_unit(1, chapter_orders=[1, 2]),
                ],
            }
        ],
    }
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload,
        actor=admin,
        change_class="binding",
        reason="写入缺少 target_unit_id 的坏历史 revision",
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/learning-units",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"] == "[SALES_TRAINER_UNIT_NOT_FOUND]"
