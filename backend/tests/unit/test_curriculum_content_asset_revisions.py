from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.schemas import CaseItemCreate, RoleProfileCreate
from curriculum_practice.services.content_assets import (
    ContentAssetService,
    case_item_content_hash,
    role_profile_content_hash,
)
from sales_trainer.models import SalesTrainerAssetRevision


def _case_item_payload() -> dict[str, object]:
    return {
        "industry": "金融科技",
        "company_profile": "中型支付平台，正在评估企业级销售训练系统。",
        "customer_role": "CTO",
        "pain_points": ["销售新人上手慢", "异议处理话术不一致"],
        "objections": ["预算紧张", "担心 AI 训练不贴近真实客户"],
        "hidden_information": "真实预算已批复，但客户不会主动透露。",
        "success_criteria": ["识别预算状态", "完成至少一次异议处理闭环"],
        "allowed_disclosure_policy": {
            "phases": [
                {
                    "trigger": "学员询问预算",
                    "keywords": ["预算"],
                    "disclose": "预算已批复但需 CTO 背书",
                }
            ]
        },
        "content_hash": "sha256:pending",
    }


def _role_profile_payload() -> dict[str, object]:
    return {
        "role_type": "customer",
        "role_name": "谨慎型 CTO",
        "persona_ref": None,
        "communication_style": "直接、重视技术细节和风险控制",
        "pressure_level": "high",
        "knowledge_boundary": ["了解内部预算流程", "不知道最终采购时间"],
        "behavior_rules": ["只回答被直接提问的问题", "价格问题上先反驳再让步"],
        "voice_style_hint": "语速偏快，语调克制",
        "content_hash": "sha256:pending",
    }


@pytest.mark.asyncio
async def test_should_stage_future_revision_when_published_case_item_is_edited(
    test_db: AsyncSession,
) -> None:
    actor = await _create_actor(test_db)
    payload = _case_item_payload()
    payload["content_hash"] = case_item_content_hash(payload)
    service = ContentAssetService(test_db)
    case_item = await service.create_case_item(
        CaseItemCreate.model_validate(payload),
        actor_id=str(actor.user_id),
    )

    published = await service.publish_case_item(
        case_item,
        actor_id=str(actor.user_id),
    )
    initial_revision = await _latest_revision(
        test_db,
        resource_type="curriculum_case_item",
        logical_id=str(published.case_item_id),
        status="published",
    )
    assert initial_revision.payload_json["customer_role"] == "CTO"

    changed_payload = _case_item_payload()
    changed_payload["customer_role"] = "CIO"
    changed_payload["content_hash"] = case_item_content_hash(changed_payload)
    unchanged = await service.update_case_item(
        published,
        CaseItemCreate.model_validate(changed_payload),
        actor_id=str(actor.user_id),
    )

    assert unchanged.customer_role == "CTO"
    working_revision = await _latest_revision(
        test_db,
        resource_type="curriculum_case_item",
        logical_id=str(published.case_item_id),
        status="working",
    )
    assert working_revision.payload_json["customer_role"] == "CIO"
    await test_db.refresh(published)
    assert published.customer_role == "CTO"

    republished = await service.publish_case_item(
        published,
        actor_id=str(actor.user_id),
    )

    assert republished.customer_role == "CIO"
    assert republished.version == 2
    published_revision = await _latest_revision(
        test_db,
        resource_type="curriculum_case_item",
        logical_id=str(published.case_item_id),
        status="published",
    )
    assert published_revision.revision_id == working_revision.revision_id


@pytest.mark.asyncio
async def test_should_stage_future_revision_when_published_role_profile_is_edited(
    test_db: AsyncSession,
) -> None:
    actor = await _create_actor(test_db)
    payload = _role_profile_payload()
    payload["content_hash"] = role_profile_content_hash(payload)
    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(
        RoleProfileCreate.model_validate(payload),
        actor_id=str(actor.user_id),
    )

    published = await service.publish_role_profile(
        role_profile,
        actor_id=str(actor.user_id),
    )
    initial_revision = await _latest_revision(
        test_db,
        resource_type="curriculum_role_profile",
        logical_id=str(published.role_profile_id),
        status="published",
    )
    assert initial_revision.payload_json["pressure_level"] == "high"

    changed_payload = _role_profile_payload()
    changed_payload["pressure_level"] = "medium"
    changed_payload["content_hash"] = role_profile_content_hash(changed_payload)
    unchanged = await service.update_role_profile(
        published,
        RoleProfileCreate.model_validate(changed_payload),
        actor_id=str(actor.user_id),
    )

    assert unchanged.pressure_level == "high"
    working_revision = await _latest_revision(
        test_db,
        resource_type="curriculum_role_profile",
        logical_id=str(published.role_profile_id),
        status="working",
    )
    assert working_revision.payload_json["pressure_level"] == "medium"
    await test_db.refresh(published)
    assert published.pressure_level == "high"

    republished = await service.publish_role_profile(
        published,
        actor_id=str(actor.user_id),
    )

    assert republished.pressure_level == "medium"
    assert republished.version == 2
    published_revision = await _latest_revision(
        test_db,
        resource_type="curriculum_role_profile",
        logical_id=str(published.role_profile_id),
        status="published",
    )
    assert published_revision.revision_id == working_revision.revision_id


async def _create_actor(db: AsyncSession) -> User:
    actor = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"curriculum-content-admin-{uuid.uuid4().hex}",
        name="Curriculum Content Admin",
        email=f"curriculum-content-admin-{uuid.uuid4().hex}@example.com",
        role="admin",
    )
    db.add(actor)
    await db.commit()
    await db.refresh(actor)
    return actor


async def _latest_revision(
    db: AsyncSession,
    *,
    resource_type: str,
    logical_id: str,
    status: str,
) -> SalesTrainerAssetRevision:
    result = await db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == resource_type,
            SalesTrainerAssetRevision.logical_id == logical_id,
            SalesTrainerAssetRevision.status == status,
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
    )
    revision = result.scalars().first()
    assert revision is not None
    return revision
