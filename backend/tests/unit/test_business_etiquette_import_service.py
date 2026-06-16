from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import LearningChapter, LearningContent
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerOperationLog
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
    BusinessEtiquetteImportService,
    BusinessEtiquetteImportServiceError,
    BusinessEtiquetteImportSettings,
)


def _admin() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-admin-{uuid.uuid4().hex[:8]}",
        name="Business Etiquette Admin",
        email=f"business-etiquette-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
    )


def _markdown(title_suffix: str = "") -> bytes:
    chapter_names = [
        "第一节：礼仪的底层逻辑",
        "第二节：职业形象塑造",
        "第三节：见面与社交礼仪",
        "第四节：商务沟通礼仪",
        "第五节：接待与拜访礼仪",
        "第六节：会议与活动礼仪",
        "第七节：商务餐饮礼仪",
        "第八节：礼仪的内化",
    ]
    lines = [
        f"# 商务礼仪：新人的第一本职业素养手册{title_suffix}",
        "",
        "## 全书总目录",
        "",
        "按 8 个原始章节组织。",
        "",
    ]
    for index, chapter_name in enumerate(chapter_names, start=1):
        lines.extend(
            [
                f"# {chapter_name}",
                "",
                "## 引子",
                "",
                f"第 {index} 章正文。",
                "",
                "### 核心知识点",
                "",
                f"第 {index} 章知识点。",
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


@pytest.mark.asyncio
async def test_should_import_business_etiquette_markdown_as_draft_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()

    result = await BusinessEtiquetteImportService(test_db).import_markdown(
        file_bytes=_markdown(),
        source_filename="business-etiquette.md",
        content_type="text/markdown",
        actor=admin,
        trace_id="trace-business-etiquette-import",
    )

    assert result["training_pack_key"] == DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY
    assert result["learning_content_status"] == "draft"
    assert result["working_revision_no"] == 1
    assert result["active_revision_id"] is None
    assert result["original_chapter_count"] == 8
    assert result["micro_chapter_count"] == 8
    assert result["knowledge_point_count"] == 8
    assert result["ai_suggestions_enabled"] is False

    content = await test_db.get(LearningContent, result["learning_content_id"])
    assert content is not None
    assert content.status == "draft"
    assert content.content_hash == result["content_hash"]
    assert content.source.startswith("sales_trainer.business_etiquette_import:")

    chapter_result = await test_db.execute(
        select(LearningChapter)
        .where(LearningChapter.learning_content_id == content.learning_content_id)
        .order_by(LearningChapter.order_index)
    )
    chapters = list(chapter_result.scalars().all())
    assert len(chapters) == 8
    assert chapters[0].title == "第一节：礼仪的底层逻辑"
    assert "## 引子" in chapters[0].content

    revision = await test_db.get(
        SalesTrainerAssetRevision,
        result["working_revision_id"],
    )
    assert revision is not None
    assert revision.resource_type == BUSINESS_ETIQUETTE_RESOURCE_TYPE
    assert revision.status == "working"
    assert revision.payload_json["learning_content_id"] == content.learning_content_id
    assert revision.payload_json["original_chapter_count"] == 8
    assert (
        revision.payload_json["original_chapters"][0]["micro_chapters"][0][
            "knowledge_points"
        ][0]["title"]
        == "核心知识点"
    )

    log_result = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action
            == "business_etiquette_training_pack.markdown_imported"
        )
    )
    log = log_result.scalar_one()
    assert log.request_id == "trace-business-etiquette-import"
    assert log.metadata_json["working_revision_id"] == result["working_revision_id"]
    assert log.metadata_json["original_chapter_count"] == 8


@pytest.mark.asyncio
async def test_should_overwrite_only_working_draft_and_keep_published_revision_active(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    import_service = BusinessEtiquetteImportService(test_db)

    first = await import_service.import_markdown(
        file_bytes=_markdown(),
        source_filename="business-etiquette.md",
        content_type="text/markdown",
        actor=admin,
    )
    first_revision = await SalesTrainerAssetRevisionService(test_db).revision_by_id(
        first["working_revision_id"]
    )
    assert first_revision is not None
    await SalesTrainerAssetRevisionService(test_db).publish_working_revision(
        first_revision,
        actor=admin,
        reason="发布商务礼仪训练包 v1",
    )
    await test_db.commit()

    second = await import_service.import_markdown(
        file_bytes=_markdown(" 第二版草稿"),
        source_filename="business-etiquette-v2.md",
        content_type="text/markdown",
        actor=admin,
    )

    active_revision = await SalesTrainerAssetRevisionService(test_db).active_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
    )
    assert active_revision is not None
    assert active_revision.revision_id == first["working_revision_id"]
    assert second["active_revision_id"] == first["working_revision_id"]
    assert second["working_revision_no"] == 2
    second_revision = await test_db.get(
        SalesTrainerAssetRevision,
        second["working_revision_id"],
    )
    assert second_revision is not None
    assert second_revision.status == "working"


@pytest.mark.asyncio
async def test_should_reject_overwrite_when_draft_overwrite_is_disabled(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    import_service = BusinessEtiquetteImportService(
        test_db,
        settings=BusinessEtiquetteImportSettings(allow_overwrite_draft=False),
    )

    first = await import_service.import_markdown(
        file_bytes=_markdown(),
        source_filename="business-etiquette.md",
        content_type="text/markdown",
        actor=admin,
    )
    with pytest.raises(BusinessEtiquetteImportServiceError) as error:
        await import_service.import_markdown(
            file_bytes=_markdown(" blocked"),
            source_filename="business-etiquette-blocked.md",
            content_type="text/markdown",
            actor=admin,
        )

    assert error.value.code == "[BUSINESS_ETIQUETTE_DRAFT_EXISTS]"
    revision_count = await test_db.scalar(
        select(func.count(SalesTrainerAssetRevision.revision_id))
    )
    assert revision_count == 1
    content_count = await test_db.scalar(
        select(func.count(LearningContent.learning_content_id))
    )
    assert content_count == 1
    revision = await test_db.get(
        SalesTrainerAssetRevision, first["working_revision_id"]
    )
    assert revision is not None
    assert revision.status == "working"


@pytest.mark.asyncio
async def test_should_reject_invalid_markdown_without_creating_partial_assets(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()

    with pytest.raises(BusinessEtiquetteImportServiceError) as error:
        await BusinessEtiquetteImportService(test_db).import_markdown(
            file_bytes=b"# Broken\n\n## Only front matter\n",
            source_filename="broken.md",
            content_type="text/markdown",
            actor=admin,
        )

    assert error.value.code == "[BUSINESS_ETIQUETTE_IMPORT_STRUCTURE_INVALID]"
    content_count = await test_db.scalar(
        select(func.count(LearningContent.learning_content_id))
    )
    assert content_count == 0
    revision_count = await test_db.scalar(
        select(func.count(SalesTrainerAssetRevision.revision_id))
    )
    assert revision_count == 0
