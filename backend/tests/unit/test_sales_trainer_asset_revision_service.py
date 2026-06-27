from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)


def _admin() -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"asset-revision-admin-{suffix}",
        name="Asset Revision Admin",
        email=f"asset-revision-admin-{suffix}@example.com",
        role="admin",
    )


@pytest.mark.asyncio
async def test_should_publish_working_revision_and_return_immutable_snapshot(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    service = SalesTrainerAssetRevisionService(test_db)
    payload = {
        "title": "初始配置",
        "nested": {"score": 80},
    }

    working = await service.save_working_revision(
        resource_type="governed_asset",
        logical_id="asset-1",
        payload=payload,
        actor=admin,
        change_class="semantic",
        reason="save draft",
        trace_id="trace-asset-1",
    )
    payload["nested"]["score"] = 99

    publish_result = await service.publish_working_revision(
        working,
        actor=admin,
        reason="publish draft",
        trace_id="trace-asset-1-publish",
    )
    active = await service.active_revision(
        resource_type="governed_asset",
        logical_id="asset-1",
    )
    snapshot = service.snapshot(active)

    assert publish_result.previous_revision_id is None
    assert active is not None
    assert active.revision_id == working.revision_id
    assert snapshot is not None
    assert snapshot["resource_type"] == "governed_asset"
    assert snapshot["logical_id"] == "asset-1"
    assert snapshot["revision_id"] == working.revision_id
    assert snapshot["revision_no"] == 1
    assert snapshot["status"] == "published"
    assert snapshot["payload_hash"] == working.payload_hash
    assert snapshot["payload"]["nested"]["score"] == 80

    snapshot["payload"]["nested"]["score"] = 100
    active_again = await service.active_revision(
        resource_type="governed_asset",
        logical_id="asset-1",
    )

    assert active_again is not None
    assert active_again.payload_json["nested"]["score"] == 80


@pytest.mark.asyncio
async def test_should_reject_invalid_publish_and_mismatched_rollback_target(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    service = SalesTrainerAssetRevisionService(test_db)
    first = await service.create_published_revision(
        resource_type="governed_asset",
        logical_id="asset-1",
        payload={"title": "已发布版本"},
        actor=admin,
        change_class="semantic",
        reason="initial publish",
        trace_id="trace-initial",
    )

    with pytest.raises(SalesTrainerAssetRevisionError) as publish_error:
        await service.publish_working_revision(
            first.revision,
            actor=admin,
            reason="publish already published",
        )

    assert publish_error.value.code == "[ASSET_REVISION_NOT_PUBLISHABLE]"

    with pytest.raises(SalesTrainerAssetRevisionError) as rollback_error:
        await service.rollback_to_revision(
            first.revision,
            actor=admin,
            reason="rollback wrong asset",
            expected_resource_type="governed_asset",
            expected_logical_id="asset-2",
        )

    assert rollback_error.value.code == "[ASSET_REVISION_TARGET_MISMATCH]"
