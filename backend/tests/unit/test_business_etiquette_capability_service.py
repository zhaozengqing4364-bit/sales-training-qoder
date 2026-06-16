from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerOperationLog
from sales_trainer.schemas import (
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteChapterCapabilityBinding,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
    BusinessEtiquetteCapabilityService,
    BusinessEtiquetteCapabilityServiceError,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)


def _admin() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-cap-admin-{uuid.uuid4().hex[:8]}",
        name="Business Etiquette Capability Admin",
        email=f"business-etiquette-cap-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
    )


async def _seed_training_pack_revision(
    test_db: AsyncSession,
    *,
    admin: User,
    published: bool = False,
) -> SalesTrainerAssetRevision:
    payload = {
        "schema_version": 1,
        "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        "learning_content_id": "business-etiquette-content",
        "book_title": "商务礼仪：新人的第一本职业素养手册",
        "original_chapter_count": 8,
        "original_chapters": [
            {"title": f"第 {index} 章", "order_index": index}
            for index in range(1, 9)
        ],
    }
    revisions = SalesTrainerAssetRevisionService(test_db)
    if published:
        result = await revisions.create_published_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
            payload=payload,
            actor=admin,
            change_class="semantic",
            reason="发布商务礼仪训练包资料",
        )
        await test_db.commit()
        return result.revision
    revision = await revisions.save_working_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=payload,
        actor=admin,
        change_class="semantic",
        reason="导入商务礼仪训练包资料",
    )
    await test_db.commit()
    return revision


@pytest.mark.asyncio
async def test_should_return_default_capability_seed_before_snapshot_is_saved(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack_revision(test_db, admin=admin)

    snapshot = await BusinessEtiquetteCapabilityService(test_db).get_snapshot()

    assert snapshot.source == "default_seed"
    assert snapshot.needs_save is True
    assert len(snapshot.capabilities) == 8
    assert snapshot.capabilities[0].capability_key == "respect_boundaries"
    assert snapshot.capabilities[0].status == "draft"
    assert snapshot.chapter_bindings[0].chapter_order == 1


@pytest.mark.asyncio
async def test_should_save_capability_snapshot_as_new_working_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    base_revision = await _seed_training_pack_revision(test_db, admin=admin)
    seed = default_business_etiquette_capability_snapshot()
    capabilities = [
        BusinessEtiquetteCapabilityConfig.model_validate(item)
        for item in seed["capabilities"]
    ]
    chapter_bindings = [
        BusinessEtiquetteChapterCapabilityBinding.model_validate(item)
        for item in seed["chapter_bindings"]
    ]

    saved = await BusinessEtiquetteCapabilityService(test_db).save_snapshot(
        capabilities=capabilities,
        chapter_bindings=chapter_bindings,
        actor=admin,
        reason="保存 8 个商务礼仪能力点",
        trace_id="trace-capability-save",
    )

    assert saved.source == "working_revision"
    assert saved.working_revision_no == 2
    assert saved.needs_save is False
    revision = await test_db.get(SalesTrainerAssetRevision, saved.working_revision_id)
    assert revision is not None
    assert revision.source_revision_id == base_revision.revision_id
    assert revision.payload_json[CAPABILITY_SNAPSHOT_KEY]["capabilities"][0][
        "display_name"
    ] == "尊重与分寸感"
    assert revision.payload_json[CAPABILITY_SNAPSHOT_KEY]["chapter_bindings"][0][
        "capability_keys"
    ] == ["respect_boundaries"]

    log_result = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action
            == "business_etiquette_training_pack.capabilities_saved"
        )
    )
    log = log_result.scalar_one()
    assert log.request_id == "trace-capability-save"
    assert log.metadata_json["capability_count"] == 8


@pytest.mark.asyncio
async def test_should_reject_duplicate_capability_keys_without_new_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack_revision(test_db, admin=admin)
    seed = default_business_etiquette_capability_snapshot()
    capabilities = [
        BusinessEtiquetteCapabilityConfig.model_validate(item)
        for item in seed["capabilities"]
    ]
    capabilities[1] = capabilities[1].model_copy(
        update={"capability_key": capabilities[0].capability_key}
    )
    chapter_bindings = [
        BusinessEtiquetteChapterCapabilityBinding.model_validate(item)
        for item in seed["chapter_bindings"]
    ]

    with pytest.raises(BusinessEtiquetteCapabilityServiceError) as error:
        await BusinessEtiquetteCapabilityService(test_db).save_snapshot(
            capabilities=capabilities,
            chapter_bindings=chapter_bindings,
            actor=admin,
        )

    assert error.value.code == "[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]"


@pytest.mark.asyncio
async def test_should_publish_capability_by_creating_new_working_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack_revision(test_db, admin=admin)

    published = await BusinessEtiquetteCapabilityService(
        test_db
    ).update_capability_status(
        capability_key="respect_boundaries",
        status="published",
        actor=admin,
        trace_id="trace-capability-publish",
    )

    assert published.working_revision_no == 2
    capability = next(
        item
        for item in published.capabilities
        if item.capability_key == "respect_boundaries"
    )
    assert capability.status == "published"
    log_result = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action
            == "business_etiquette_training_pack.capability_published"
        )
    )
    log = log_result.scalar_one()
    assert log.metadata_json["capability_key"] == "respect_boundaries"
