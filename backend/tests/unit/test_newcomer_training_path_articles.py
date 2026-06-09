from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import LearningChapter, LearningContent
from sales_trainer.models import SalesTrainerUnit
from sales_trainer.schemas import NewcomerArticleBinding
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-article-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Article {role}",
        email=f"newcomer-article-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _content(content_id: str, *, status: str) -> LearningContent:
    return LearningContent(
        learning_content_id=content_id,
        title="见客户前商务礼仪",
        summary="见客户前应具备的商务礼仪教学文章。",
        owner="新人训练路径",
        source="admin_learning_content",
        status=status,
        created_by="system",
        updated_by="system",
    )


@pytest.mark.asyncio
async def test_should_resolve_published_business_skills_article(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    content = _content("business-skills-article", status="published")
    chapter = LearningChapter(
        chapter_id="business-skills-chapter-1",
        learning_content_id=content.learning_content_id,
        title="拜访前准备",
        content="![礼仪示例](https://example.com/business-etiquette.png)\n\n见客户前先确认议程。",
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([admin, content, chapter])
    await test_db.commit()

    article = await ArticleBindingService(test_db).resolve_module_article(
        NewcomerArticleBinding(
            module_key="business_skills",
            learning_content_id=content.learning_content_id,
        )
    )

    assert article["module_key"] == "business_skills"
    assert article["learning_content_id"] == content.learning_content_id
    assert article["title"] == "见客户前商务礼仪"
    assert article["chapters"][0]["content"].startswith("![礼仪示例]")


@pytest.mark.asyncio
async def test_should_resolve_article_from_published_module_binding(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    content = _content("bound-business-skills-article", status="published")
    chapter = LearningChapter(
        chapter_id="bound-business-skills-chapter-1",
        learning_content_id=content.learning_content_id,
        title="客户背景",
        content="![客户资料](https://example.com/client-profile.png)\n\n先确认客户画像。",
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    module_unit = SalesTrainerUnit(
        unit_id="business-skills-module-binding",
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
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([admin, content, chapter, module_unit])
    await test_db.commit()

    article = await ArticleBindingService(test_db).resolve_module_article(
        NewcomerArticleBinding(module_key="business_skills")
    )

    assert article["learning_content_id"] == content.learning_content_id
    assert article["chapters"][0]["content"].startswith("![客户资料]")


@pytest.mark.asyncio
async def test_should_reject_missing_draft_and_archived_article_bindings(
    test_db: AsyncSession,
) -> None:
    draft = _content("draft-business-skills-article", status="draft")
    archived = _content("archived-business-skills-article", status="archived")
    test_db.add_all([draft, archived])
    await test_db.commit()

    service = ArticleBindingService(test_db)

    for content_id in (None, draft.learning_content_id, archived.learning_content_id):
        with pytest.raises(ArticleBindingServiceError) as error:
            await service.resolve_module_article(
                NewcomerArticleBinding(
                    module_key="business_skills",
                    learning_content_id=content_id,
                )
            )
        assert error.value.code == "[LEARNING_CONTENT_NOT_PUBLISHED]"

    with pytest.raises(ArticleBindingServiceError) as missing_error:
        await service.resolve_module_article(
            NewcomerArticleBinding(
                module_key="business_skills",
                learning_content_id=str(uuid.uuid4()),
            )
        )
    assert missing_error.value.code == "[LEARNING_CONTENT_NOT_FOUND]"


@pytest.mark.asyncio
async def test_should_reject_published_article_without_learning_chapters(
    test_db: AsyncSession,
) -> None:
    content = _content("empty-business-skills-article", status="published")
    test_db.add(content)
    await test_db.commit()

    with pytest.raises(ArticleBindingServiceError) as error:
        await ArticleBindingService(test_db).resolve_module_article(
            NewcomerArticleBinding(
                module_key="business_skills",
                learning_content_id=content.learning_content_id,
            )
        )

    assert error.value.code == "[LEARNING_CONTENT_CHAPTERS_MISSING]"
