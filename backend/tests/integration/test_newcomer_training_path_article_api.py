from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import PromptTemplate, User
from curriculum_practice.models import LearningChapter, LearningContent
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerExamPaper,
    SalesTrainerUnit,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService
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
        wechat_user_id=f"newcomer-article-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Article API {role}",
        email=f"newcomer-article-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _content(content_id: str, *, status: str) -> LearningContent:
    return LearningContent(
        learning_content_id=content_id,
        title="见客户前商务礼仪",
        summary="阅读文章后再进入商务技巧考卷。",
        owner="新人训练路径",
        source="admin_learning_content",
        status=status,
    )


def _ai_coach_config() -> dict[str, object]:
    return {
        "enabled": True,
        "coach_mode": "mixed_drill",
        "allowed_interaction_types": ["single_choice", "multiple_choice"],
        "prompt_template_id": "11111111-1111-1111-1111-111111111111",
        "prompt_revision_id": None,
        "prompt_contract_hash": None,
        "scoring_prompt_template_id": None,
        "scoring_prompt_revision_id": None,
        "scoring_contract_hash": None,
        "min_turns": 3,
        "max_turns": 10,
        "mastery_threshold": 90,
        "output_schema_version": "ai_coach_interaction_v1",
        "generation_model": None,
        "scoring_model": None,
        "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
        "failure_behavior": "skip_turn",
    }


def _ai_coach_prompt_template() -> PromptTemplate:
    return PromptTemplate(
        id="11111111-1111-1111-1111-111111111111",
        name="商务技巧 AI 教练对话生成",
        prompt_type="stage",
        business_purpose=PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION,
        category="sales_trainer_ai_coach",
        template="请根据 {{ module_key }} 和 {{ coach_mode }} 生成教练回复。",
        variables=["module_key", "coach_mode"],
        is_active=True,
        is_default=False,
        is_system=False,
    )


async def _publish_article_path(
    test_db: AsyncSession,
    *,
    actor: User,
    unit_id: str,
    learning_content_id: str,
    learner_level_required: list[str] | None = None,
) -> None:
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": NEWCOMER_PATH_LOGICAL_ID,
            "title": "新人训练路径",
            "enabled": True,
            "modules": [
                {
                    "module_key": "business_skills",
                    "module_type": "article_exam",
                    "enabled": True,
                    "order_index": 2,
                    "title": "商务技巧",
                    "target_unit_id": unit_id,
                    "learning_content_id": learning_content_id,
                    "learner_level_required": learner_level_required or [],
                    "completion_rule": "passed",
                }
            ],
        },
        actor=actor,
        change_class="semantic",
        reason="发布商务技巧文章测试路径",
    )
    await test_db.commit()


@pytest.mark.asyncio
async def test_should_fetch_newcomer_article_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id="newcomer-article-api-active-unit",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={},
    )
    content = _content("newcomer-article-api-content", status="published")
    chapter = LearningChapter(
        chapter_id="newcomer-article-api-chapter",
        learning_content_id=content.learning_content_id,
        title="拜访前准备",
        content="![商务礼仪图](https://example.com/etiquette.png)\n\n确认客户背景。",
        order_index=1,
    )
    test_db.add_all([learner, unit, content, chapter])
    await test_db.commit()
    await _publish_article_path(
        test_db,
        actor=learner,
        unit_id=unit.unit_id,
        learning_content_id=content.learning_content_id,
    )

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": content.learning_content_id},
    )

    assert response.status_code == 200
    article = response.json()["data"]
    assert article["module_key"] == "business_skills"
    assert article["title"] == "见客户前商务礼仪"
    assert article["chapters"][0]["content"].startswith("![商务礼仪图]")


@pytest.mark.asyncio
async def test_should_fetch_newcomer_article_from_module_binding_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    content = _content("newcomer-article-api-bound-content", status="published")
    chapter = LearningChapter(
        chapter_id="newcomer-article-api-bound-chapter",
        learning_content_id=content.learning_content_id,
        title="客户资料",
        content="![客户资料](https://example.com/client.png)\n\n提前确认客户资料。",
        order_index=1,
    )
    module_unit = SalesTrainerUnit(
        unit_id="newcomer-article-api-module-binding",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": 2,
                "learning_content_id": content.learning_content_id,
            }
        },
    )
    test_db.add_all([learner, content, chapter, module_unit])
    await test_db.commit()
    await _publish_article_path(
        test_db,
        actor=learner,
        unit_id=module_unit.unit_id,
        learning_content_id=content.learning_content_id,
    )

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200
    article = response.json()["data"]
    assert article["learning_content_id"] == content.learning_content_id
    assert article["chapters"][0]["content"].startswith("![客户资料]")


@pytest.mark.asyncio
async def test_should_bind_newcomer_article_content_via_admin_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = _content("newcomer-article-admin-bound", status="published")
    chapter = LearningChapter(
        chapter_id="newcomer-article-api-admin-bound-chapter",
        learning_content_id=content.learning_content_id,
        title="拜访礼仪",
        content="![礼仪图片](https://example.com/etiquette.png)\n\n确认拜访礼仪。",
        order_index=1,
    )
    module_unit = SalesTrainerUnit(
        unit_id="article-admin-module-binding",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": 2,
                "ai_coach": _ai_coach_config(),
            }
        },
    )
    paper = SalesTrainerExamPaper(
        paper_id="article-admin-paper-binding",
        paper_key="article-admin-paper-binding",
        title="商务技巧考卷",
        module_key="business_skills",
        unit_id=module_unit.unit_id,
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all(
        [admin, learner, content, chapter, module_unit, paper, _ai_coach_prompt_template()]
    )
    await test_db.commit()

    bind_response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/article-binding",
        headers=_auth_headers(admin),
        json={
            "learning_content_id": content.learning_content_id,
            "reason": "配置商务技巧学习文章",
        },
    )
    assert bind_response.status_code == 200, bind_response.text
    bind_data = bind_response.json()["data"]
    assert bind_data["learning_content_id"] == content.learning_content_id
    assert bind_data["path_key"] == "newcomer_training_path_v1"
    assert bind_data["active_revision_id"] is None
    assert bind_data["active_revision_no"] is None
    assert bind_data["working_revision_id"]
    assert bind_data["working_revision_no"] == 1
    assert bind_data["has_unpublished_revision"] is True
    assert bind_data["impact_scope"] == "future_learners_only"
    bind_trace_id = bind_response.json()["trace_id"]

    await test_db.refresh(module_unit)
    assert "learning_content_id" not in module_unit.config["path"]

    learner_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
    )
    assert learner_response.status_code == 409
    assert learner_response.json()["error"] == "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]"

    path_config_response = await async_client.get(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
    )
    assert path_config_response.status_code == 200
    path_config = path_config_response.json()["data"]
    assert path_config["has_unpublished_revision"] is True
    revisions = await test_db.execute(
        select(SalesTrainerAssetRevision).where(
            SalesTrainerAssetRevision.resource_type == NEWCOMER_PATH_RESOURCE_TYPE,
            SalesTrainerAssetRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
            SalesTrainerAssetRevision.status == "working",
        )
    )
    working_revision = revisions.scalar_one()
    assert bind_data["working_revision_id"] == working_revision.revision_id
    assert (
        working_revision.payload_json["modules"][0]["learning_content_id"]
        == content.learning_content_id
    )

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "商务技巧学习文章绑定生效"},
    )
    assert publish_response.status_code == 409
    assert publish_response.json()["error"] == "[NEWCOMER_MODULE_BINDING_MISSING]"

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json={
            "path_key": "newcomer_training_path_v1",
            "title": "新人训练路径",
            "goal_title": "完成新人训练",
            "reason": "补齐商务技巧考卷绑定",
            "modules": [
                {
                    "module_key": "business_skills",
                    "module_type": "article_exam",
                    "enabled": True,
                    "order_index": 2,
                    "title": "商务技巧",
                    "target_unit_id": module_unit.unit_id,
                    "learning_content_id": content.learning_content_id,
                    "exam_paper_id": paper.paper_id,
                    "ai_coach": _ai_coach_config(),
                    "completion_rule": "passed",
                }
            ],
        },
    )
    assert save_response.status_code == 200, save_response.text

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "商务技巧文章和考卷绑定生效"},
    )
    assert publish_response.status_code == 200

    learner_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
    )
    assert learner_response.status_code == 200
    assert learner_response.json()["data"]["title"] == "见客户前商务礼仪"

    logs, total = await OperationLogService(test_db).list_logs(
        target_type="newcomer_path_config",
    )
    article_logs = [
        log
        for log in logs
        if log.action == "newcomer_path_config.article_binding_saved"
    ]
    assert total >= 2
    assert len(article_logs) == 1
    assert article_logs[0].request_id == bind_trace_id
    assert article_logs[0].metadata_json["trace_id"] == bind_trace_id
    assert article_logs[0].metadata_json["impact_scope"] == "future_learners_only"
    assert (
        article_logs[0].metadata_json["learning_content_id"]
        == content.learning_content_id
    )


@pytest.mark.asyncio
async def test_should_reject_draft_newcomer_article_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id="newcomer-article-api-draft-unit",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={},
    )
    content = _content("newcomer-article-api-draft", status="draft")
    test_db.add_all([learner, unit, content])
    await test_db.commit()
    await _publish_article_path(
        test_db,
        actor=learner,
        unit_id=unit.unit_id,
        learning_content_id=content.learning_content_id,
    )

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": content.learning_content_id},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "[LEARNING_CONTENT_NOT_PUBLISHED]"


@pytest.mark.asyncio
async def test_should_reject_legacy_path_key_for_article_binding_write(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/article-binding",
        headers=_auth_headers(admin),
        json={
            "learning_content_id": "legacy-path-write-content",
            "path_key": "new_seller_modules_v1",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[NEWCOMER_PATH_CONFIG_ALIAS_READ_ONLY]"


@pytest.mark.asyncio
async def test_should_reject_empty_chapter_newcomer_article_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id="newcomer-article-api-empty-unit",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={},
    )
    content = _content("newcomer-article-api-empty-chapters", status="published")
    test_db.add_all([learner, unit, content])
    await test_db.commit()
    await _publish_article_path(
        test_db,
        actor=learner,
        unit_id=unit.unit_id,
        learning_content_id=content.learning_content_id,
    )

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": content.learning_content_id},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[LEARNING_CONTENT_CHAPTERS_MISSING]"


@pytest.mark.asyncio
async def test_should_reject_article_progress_for_content_outside_active_path(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id="newcomer-article-api-progress-unit",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={},
    )
    bound_content = _content("newcomer-article-bound-for-progress", status="published")
    bound_chapter = LearningChapter(
        chapter_id="bound-progress-chapter",
        learning_content_id=bound_content.learning_content_id,
        title="路径内章节",
        content="路径内文章内容。",
        order_index=1,
    )
    outside_content = _content("newcomer-article-outside-progress", status="published")
    outside_chapter = LearningChapter(
        chapter_id="outside-progress-chapter",
        learning_content_id=outside_content.learning_content_id,
        title="路径外章节",
        content="路径外文章内容。",
        order_index=1,
    )
    test_db.add_all(
        [learner, unit, bound_content, bound_chapter, outside_content, outside_chapter]
    )
    await test_db.commit()
    await _publish_article_path(
        test_db,
        actor=learner,
        unit_id=unit.unit_id,
        learning_content_id=bound_content.learning_content_id,
    )

    read_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": outside_content.learning_content_id},
    )
    write_response = await async_client.post(
        "/api/v1/newcomer-training/modules/business_skills/article-progress",
        headers=_auth_headers(learner),
        json={
            "learning_content_id": outside_content.learning_content_id,
            "chapter_id": outside_chapter.chapter_id,
        },
    )

    assert read_response.status_code == 409
    assert read_response.json()["error"] == "[LEARNING_CONTENT_MISMATCH]"
    assert write_response.status_code == 409
    assert write_response.json()["error"] == "[LEARNING_CONTENT_MISMATCH]"


@pytest.mark.asyncio
async def test_should_fail_closed_article_surfaces_when_journey_module_locked(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id="newcomer-article-api-locked-unit",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={},
    )
    content = _content("newcomer-article-api-locked-content", status="published")
    chapter = LearningChapter(
        chapter_id="newcomer-article-api-locked-chapter",
        learning_content_id=content.learning_content_id,
        title="路径锁定章节",
        content="路径锁定时不能读取。",
        order_index=1,
    )
    test_db.add_all([learner, unit, content, chapter])
    await test_db.commit()
    await _publish_article_path(
        test_db,
        actor=learner,
        unit_id=unit.unit_id,
        learning_content_id=content.learning_content_id,
        learner_level_required=["ready"],
    )

    read_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
    )
    progress_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article-progress",
        headers=_auth_headers(learner),
    )
    write_response = await async_client.post(
        "/api/v1/newcomer-training/modules/business_skills/article-progress",
        headers=_auth_headers(learner),
        json={
            "learning_content_id": content.learning_content_id,
            "chapter_id": chapter.chapter_id,
        },
    )

    for response in (read_response, progress_response, write_response):
        assert response.status_code == 404, response.text
        assert response.json()["error"] == "[SALES_TRAINER_UNIT_NOT_FOUND]"
