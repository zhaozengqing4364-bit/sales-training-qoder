from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona
from curriculum_practice.schemas import (
    CaseItemCreate,
    RoleProfileCreate,
    RoleProfileResponse,
)
from curriculum_practice.services.content_assets import (
    ContentAssetPublishError,
    ContentAssetService,
    case_item_content_hash,
    role_profile_content_hash,
)


def _case_item_payload(*, content_hash: str = "sha256:pending") -> dict[str, object]:
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
        "content_hash": content_hash,
    }


def _role_profile_payload(
    *, persona_ref: str | None = None, content_hash: str = "sha256:pending"
) -> dict[str, object]:
    return {
        "role_type": "customer",
        "role_name": "谨慎型 CTO",
        "persona_ref": persona_ref,
        "communication_style": "直接、重视技术细节和风险控制",
        "pressure_level": "high",
        "knowledge_boundary": ["了解内部预算流程", "不知道最终采购时间"],
        "behavior_rules": ["只回答被直接提问的问题", "价格问题上先反驳再让步"],
        "voice_style_hint": "语速偏快，语调克制",
        "voice_id": None,
        "voice_sample_url": None,
        "content_hash": content_hash,
    }


def test_should_accept_role_profile_voice_id_and_voice_sample_url() -> None:
    payload = _role_profile_payload()
    payload["voice_id"] = "custom_voice_cto"
    payload["voice_sample_url"] = "oss://role-voices/cto.wav"
    payload["content_hash"] = role_profile_content_hash(payload)

    schema = RoleProfileCreate.model_validate(payload)

    assert schema.voice_id == "custom_voice_cto"
    assert schema.voice_sample_url == "oss://role-voices/cto.wav"


def test_should_include_voice_fields_in_role_profile_hash_payload() -> None:
    payload_without_voice = _role_profile_payload()
    payload_without_voice["content_hash"] = role_profile_content_hash(payload_without_voice)
    payload_with_voice = dict(payload_without_voice)
    payload_with_voice["voice_id"] = "custom_voice_cto"
    payload_with_voice["voice_sample_url"] = "oss://role-voices/cto.wav"
    payload_with_voice["content_hash"] = role_profile_content_hash(payload_with_voice)

    assert payload_with_voice["content_hash"] != payload_without_voice["content_hash"]


def test_should_include_voice_fields_in_role_profile_response() -> None:
    payload = _role_profile_payload()
    payload["voice_id"] = "custom_voice_cto"
    payload["voice_sample_url"] = "oss://role-voices/cto.wav"
    payload["content_hash"] = role_profile_content_hash(payload)
    response_payload = {
        **payload,
        "role_profile_id": str(uuid.uuid4()),
        "version": 1,
        "status": "draft",
        "published_at": None,
        "created_at": "2026-05-13T00:00:00Z",
        "updated_at": "2026-05-13T00:00:00Z",
    }

    response = RoleProfileResponse.model_validate(response_payload)

    assert response.voice_id == "custom_voice_cto"
    assert response.voice_sample_url == "oss://role-voices/cto.wav"


@pytest.mark.asyncio
async def test_should_validate_and_publish_case_item_asset(
    test_db: AsyncSession,
) -> None:
    payload = _case_item_payload()
    payload["content_hash"] = case_item_content_hash(payload)
    schema = CaseItemCreate.model_validate(payload)

    service = ContentAssetService(test_db)
    case_item = await service.create_case_item(schema, actor_id="admin-1")
    published = await service.publish_case_item(case_item, actor_id="admin-1")

    assert published.status == "published"
    assert published.version == 1
    assert published.content_hash == payload["content_hash"]
    assert published.hidden_information == "真实预算已批复，但客户不会主动透露。"


@pytest.mark.asyncio
async def test_should_reject_case_item_publish_when_hash_is_stale(
    test_db: AsyncSession,
) -> None:
    schema = CaseItemCreate.model_validate(_case_item_payload(content_hash="sha256:stale"))
    service = ContentAssetService(test_db)
    case_item = await service.create_case_item(schema, actor_id="admin-1")

    with pytest.raises(ContentAssetPublishError) as exc_info:
        await service.publish_case_item(case_item, actor_id="admin-1")

    assert exc_info.value.reason_code == "content_hash_mismatch"


@pytest.mark.asyncio
async def test_should_validate_and_publish_role_profile_with_persona_ref(
    test_db: AsyncSession,
) -> None:
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Existing Persona",
        description="reused persona",
        category="customer",
        system_prompt="Act as a careful customer.",
        status="active",
    )
    test_db.add(persona)
    await test_db.commit()
    payload = _role_profile_payload(persona_ref=persona.id)
    payload["content_hash"] = role_profile_content_hash(payload)
    schema = RoleProfileCreate.model_validate(payload)

    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(schema, actor_id="admin-1")
    published = await service.publish_role_profile(role_profile, actor_id="admin-1")

    assert published.status == "published"
    assert published.persona_ref == persona.id
    assert published.content_hash == payload["content_hash"]


@pytest.mark.asyncio
async def test_should_reject_role_profile_publish_when_persona_ref_is_unavailable(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload(persona_ref=str(uuid.uuid4()))
    payload["content_hash"] = role_profile_content_hash(payload)
    schema = RoleProfileCreate.model_validate(payload)
    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(schema, actor_id="admin-1")

    with pytest.raises(ContentAssetPublishError) as exc_info:
        await service.publish_role_profile(role_profile, actor_id="admin-1")

    assert exc_info.value.reason_code == "persona_ref_unavailable"
