from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import set_trace_id
from sales_trainer.models import SalesTrainerOperationLog
from sales_trainer.schemas import (
    SalesTrainerMaterialCreate,
    SalesTrainerMaterialUpdate,
    SalesTrainerMaterialVersionCreate,
)
from sales_trainer.services.material_service import SalesTrainerMaterialService


def _user(role: str) -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"material-governance-{role}-{suffix}",
        name=f"材料治理 {role}",
        email=f"material-governance-{role}-{suffix}@example.com",
        role=role,
    )


def _version_payload(label: str, file_name: str) -> SalesTrainerMaterialVersionCreate:
    return SalesTrainerMaterialVersionCreate(
        version_label=label,
        title=f"公司主胶片 {label}",
        file_name=file_name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes=100,
        storage_key=f"/tmp/{file_name}",
    )


@pytest.mark.asyncio
async def test_should_audit_material_version_publish_as_future_only_pointer_change(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    service = SalesTrainerMaterialService(test_db)
    material = await service.create_material(
        SalesTrainerMaterialCreate(
            material_key=f"company_master_deck_{uuid.uuid4().hex[:8]}",
            name="公司主胶片",
            material_type="ppt_deck",
            purpose="ppt_pitch",
        ),
        actor=admin,
    )
    first = await service.create_version(
        material,
        _version_payload("v2026.05", "deck-v1.pptx"),
        actor=admin,
    )
    second = await service.create_version(
        material,
        _version_payload("v2026.06", "deck-v2.pptx"),
        actor=admin,
    )

    set_trace_id("material-publish-trace-first")
    await service.publish_version(first, actor=admin)
    set_trace_id("material-publish-trace-second")
    await service.publish_version(second, actor=admin)

    logs = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action == "material_version_published",
            SalesTrainerOperationLog.target_id == second.version_id,
        )
    )
    publish_log = logs.scalar_one()

    assert publish_log.request_id == "material-publish-trace-second"
    assert publish_log.metadata_json["trace_id"] == "material-publish-trace-second"
    assert publish_log.metadata_json["before_version_id"] == first.version_id
    assert publish_log.metadata_json["after_version_id"] == second.version_id
    assert publish_log.metadata_json["archived_version_ids"] == [first.version_id]
    assert publish_log.metadata_json["impact_scope"] == "future_submissions_only"


@pytest.mark.asyncio
async def test_should_audit_published_material_metadata_update_with_before_after(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    service = SalesTrainerMaterialService(test_db)
    material = await service.create_material(
        SalesTrainerMaterialCreate(
            material_key=f"company_deck_metadata_{uuid.uuid4().hex[:8]}",
            name="旧版公司主胶片",
            material_type="ppt_deck",
            description="旧说明",
            purpose="ppt_pitch",
        ),
        actor=admin,
    )
    version = await service.create_version(
        material,
        _version_payload("v2026.06", "deck-metadata.pptx"),
        actor=admin,
    )
    await service.publish_version(version, actor=admin)

    set_trace_id("material-metadata-update-trace")
    updated = await service.update_material(
        material,
        SalesTrainerMaterialUpdate(
            name="新版公司主胶片",
            description="新版说明",
            purpose="elevator_pitch",
        ),
        actor=admin,
    )

    logs = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action == "material_metadata_updated",
            SalesTrainerOperationLog.target_id == updated.material_id,
        )
    )
    update_log = logs.scalar_one()

    assert updated.status == "published"
    assert updated.name == "新版公司主胶片"
    assert update_log.request_id == "material-metadata-update-trace"
    assert update_log.metadata_json["trace_id"] == "material-metadata-update-trace"
    assert update_log.metadata_json["future_only"] is True
    assert update_log.metadata_json["impact_scope"] == "future_submissions_only"
    assert update_log.metadata_json["changed_fields"] == [
        "name",
        "description",
        "purpose",
    ]
    assert update_log.metadata_json["before"]["name"] == "旧版公司主胶片"
    assert update_log.metadata_json["before"]["description"] == "旧说明"
    assert update_log.metadata_json["before"]["purpose"] == "ppt_pitch"
    assert update_log.metadata_json["after"]["name"] == "新版公司主胶片"
    assert update_log.metadata_json["after"]["description"] == "新版说明"
    assert update_log.metadata_json["after"]["purpose"] == "elevator_pitch"
