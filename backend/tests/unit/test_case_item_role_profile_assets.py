from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    CaseItemCreate,
    CaseItemResponse,
    RoleProfileCreate,
    RoleProfileResponse,
)
from curriculum_practice.services.content_assets import (
    ContentAssetAlreadyDraftError,
    ContentAssetPublishError,
    ContentAssetReferencedByTemplatesError,
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
        "content_hash": content_hash,
    }


def test_should_read_legacy_case_item_without_hiding_it_from_remediation() -> None:
    payload = _case_item_payload()
    payload["allowed_disclosure_policy"] = {
        "roleplay": {"situation_code": "first_visit"},
    }
    response = CaseItemResponse.model_validate(
        payload
        | {
            "case_item_id": "legacy-case-item",
            "status": "published",
            "version": 1,
            "published_at": "2026-05-13T00:00:00Z",
            "created_at": "2026-05-13T00:00:00Z",
            "updated_at": "2026-05-13T00:00:00Z",
        }
    )

    assert response.case_item_id == "legacy-case-item"
    assert response.allowed_disclosure_policy["roleplay"] == {
        "situation_code": "first_visit"
    }


def test_should_still_reject_new_case_item_without_disclosure_phases() -> None:
    payload = _case_item_payload()
    payload["allowed_disclosure_policy"] = {
        "roleplay": {"situation_code": "first_visit"},
    }

    with pytest.raises(ValidationError, match="phases must contain at least one phase"):
        CaseItemCreate.model_validate(payload)


def test_should_reject_role_profile_input_voice_id_and_voice_sample_url() -> None:
    payload = _role_profile_payload()
    payload["voice_id"] = "custom_voice_cto"
    payload["voice_sample_url"] = "oss://role-voices/cto.wav"
    payload["content_hash"] = role_profile_content_hash(payload)

    with pytest.raises(ValidationError):
        RoleProfileCreate.model_validate(payload)


def test_should_include_voice_fields_in_role_profile_hash_payload() -> None:
    payload_without_voice = _role_profile_payload()
    payload_without_voice["content_hash"] = role_profile_content_hash(payload_without_voice)
    payload_with_voice = dict(payload_without_voice)
    payload_with_voice["voice_id"] = "custom_voice_cto"
    payload_with_voice["voice_sample_url"] = "oss://role-voices/cto.wav"
    payload_with_voice["content_hash"] = role_profile_content_hash(payload_with_voice)

    assert payload_with_voice["content_hash"] != payload_without_voice["content_hash"]


def test_should_keep_historical_role_profile_hash_when_voice_fields_absent() -> None:
    legacy_payload = {
        key: value
        for key, value in _role_profile_payload().items()
        if key not in {"voice_id", "voice_sample_url"}
    }
    payload_with_absent_voice = _role_profile_payload() | {
        "voice_id": None,
        "voice_sample_url": None,
    }

    assert role_profile_content_hash(payload_with_absent_voice) == role_profile_content_hash(
        legacy_payload
    )


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
async def test_should_filter_case_items_by_status_and_query(test_db: AsyncSession) -> None:
    service = ContentAssetService(test_db)
    manufacturing_payload = _case_item_payload()
    manufacturing_payload["industry"] = "制造业"
    manufacturing_payload["content_hash"] = case_item_content_hash(manufacturing_payload)
    finance_payload = _case_item_payload()
    finance_payload["industry"] = "金融科技"
    finance_payload["customer_role"] = "CFO"
    finance_payload["content_hash"] = case_item_content_hash(finance_payload)
    manufacturing = await service.create_case_item(CaseItemCreate.model_validate(manufacturing_payload), actor_id="admin-1")
    await service.create_case_item(CaseItemCreate.model_validate(finance_payload), actor_id="admin-1")
    await service.publish_case_item(manufacturing, actor_id="admin-1")

    results = await service.list_case_items(status="published", query="制造")

    assert [item.industry for item in results] == ["制造业"]


@pytest.mark.asyncio
async def test_should_filter_role_profiles_by_status_and_query(test_db: AsyncSession) -> None:
    service = ContentAssetService(test_db)
    careful_payload = _role_profile_payload()
    careful_payload["role_name"] = "谨慎采购总监"
    careful_payload["content_hash"] = role_profile_content_hash(careful_payload)
    direct_payload = _role_profile_payload()
    direct_payload["role_name"] = "强势运营经理"
    direct_payload["content_hash"] = role_profile_content_hash(direct_payload)
    careful = await service.create_role_profile(RoleProfileCreate.model_validate(careful_payload), actor_id="admin-1")
    await service.create_role_profile(RoleProfileCreate.model_validate(direct_payload), actor_id="admin-1")
    await service.publish_role_profile(careful, actor_id="admin-1")

    results = await service.list_role_profiles(status="published", query="谨慎")

    assert [item.role_name for item in results] == ["谨慎采购总监"]


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
async def test_should_reject_role_profile_create_when_persona_ref_is_unavailable(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload(persona_ref=str(uuid.uuid4()))
    payload["content_hash"] = role_profile_content_hash(payload)
    schema = RoleProfileCreate.model_validate(payload)
    service = ContentAssetService(test_db)

    with pytest.raises(ContentAssetPublishError) as exc_info:
        await service.create_role_profile(schema, actor_id="admin-1")

    assert exc_info.value.reason_code == "persona_ref_unavailable"


@pytest.mark.asyncio
async def test_should_reject_role_profile_update_when_persona_ref_is_unavailable(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload()
    payload["content_hash"] = role_profile_content_hash(payload)
    schema = RoleProfileCreate.model_validate(payload)
    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(schema, actor_id="admin-1")
    invalid_payload = _role_profile_payload(persona_ref=str(uuid.uuid4()))
    invalid_payload["content_hash"] = role_profile_content_hash(invalid_payload)
    invalid_schema = RoleProfileCreate.model_validate(invalid_payload)

    with pytest.raises(ContentAssetPublishError) as exc_info:
        await service.update_role_profile(role_profile, invalid_schema, actor_id="admin-1")

    assert exc_info.value.reason_code == "persona_ref_unavailable"


@pytest.mark.asyncio
async def test_should_reject_role_profile_publish_when_persona_ref_is_unavailable(
    test_db: AsyncSession,
) -> None:
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Later Inactive Persona",
        description="persona deactivated before publish",
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
    persona.status = "inactive"
    await test_db.commit()

    with pytest.raises(ContentAssetPublishError) as exc_info:
        await service.publish_role_profile(role_profile, actor_id="admin-1")

    assert exc_info.value.reason_code == "persona_ref_unavailable"


@pytest.mark.asyncio
async def test_should_duplicate_case_item_as_new_draft_with_recomputed_hash(
    test_db: AsyncSession,
) -> None:
    payload = _case_item_payload()
    payload["content_hash"] = case_item_content_hash(payload)
    service = ContentAssetService(test_db)
    source = await service.create_case_item(
        CaseItemCreate.model_validate(payload), actor_id="admin-1"
    )
    published = await service.publish_case_item(source, actor_id="admin-1")

    duplicate = await service.duplicate_case_item(published, actor_id="admin-1")

    assert duplicate.case_item_id != published.case_item_id
    assert duplicate.status == "draft"
    assert duplicate.customer_role.endswith("(副本)")
    assert duplicate.content_hash != published.content_hash


@pytest.mark.asyncio
async def test_should_duplicate_role_profile_without_voice_fields(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload()
    payload["content_hash"] = role_profile_content_hash(payload)
    service = ContentAssetService(test_db)
    source = await service.create_role_profile(
        RoleProfileCreate.model_validate(payload), actor_id="admin-1"
    )
    source.voice_id = "voice-1"
    source.voice_sample_url = "https://example/voice.wav"
    source.content_hash = role_profile_content_hash(
        {
            "role_type": source.role_type,
            "role_name": source.role_name,
            "persona_ref": source.persona_ref,
            "communication_style": source.communication_style,
            "pressure_level": source.pressure_level,
            "knowledge_boundary": source.knowledge_boundary,
            "behavior_rules": source.behavior_rules,
            "voice_style_hint": source.voice_style_hint,
            "voice_id": source.voice_id,
            "voice_sample_url": source.voice_sample_url,
        }
    )
    await test_db.commit()
    published = await service.publish_role_profile(source, actor_id="admin-1")

    duplicate = await service.duplicate_role_profile(published, actor_id="admin-1")

    assert duplicate.role_profile_id != published.role_profile_id
    assert duplicate.status == "draft"
    assert duplicate.role_name.endswith("(副本)")
    assert duplicate.voice_id is None
    assert duplicate.voice_sample_url is None


@pytest.mark.asyncio
async def test_should_unpublish_case_item_when_no_template_references(
    test_db: AsyncSession,
) -> None:
    payload = _case_item_payload()
    payload["content_hash"] = case_item_content_hash(payload)
    service = ContentAssetService(test_db)
    case_item = await service.create_case_item(
        CaseItemCreate.model_validate(payload), actor_id="admin-1"
    )
    published = await service.publish_case_item(case_item, actor_id="admin-1")

    unpublished = await service.unpublish_case_item(
        published, actor_id="admin-1", acknowledge=False
    )

    assert unpublished.status == "draft"
    assert unpublished.published_at is None


@pytest.mark.asyncio
async def test_should_reject_unpublish_case_item_when_referenced_without_acknowledge(
    test_db: AsyncSession,
) -> None:
    payload = _case_item_payload()
    payload["content_hash"] = case_item_content_hash(payload)
    service = ContentAssetService(test_db)
    case_item = await service.create_case_item(
        CaseItemCreate.model_validate(payload), actor_id="admin-1"
    )
    published = await service.publish_case_item(case_item, actor_id="admin-1")
    test_db.add(
        PracticeTemplate(
            template_id=str(uuid.uuid4()),
            name="引用模板",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id=str(uuid.uuid4()),
            persona_id=str(uuid.uuid4()),
            runtime_profile_id=str(uuid.uuid4()),
            scoring_ruleset_id=str(uuid.uuid4()),
            knowledge_base_refs=[],
            case_item_id=published.case_item_id,
            status="published",
        )
    )
    await test_db.commit()

    with pytest.raises(ContentAssetReferencedByTemplatesError) as exc_info:
        await service.unpublish_case_item(
            published, actor_id="admin-1", acknowledge=False
        )

    assert exc_info.value.referencing_templates[0]["name"] == "引用模板"


@pytest.mark.asyncio
async def test_should_reject_unpublish_when_case_item_already_draft(
    test_db: AsyncSession,
) -> None:
    payload = _case_item_payload()
    payload["content_hash"] = case_item_content_hash(payload)
    service = ContentAssetService(test_db)
    case_item = await service.create_case_item(
        CaseItemCreate.model_validate(payload), actor_id="admin-1"
    )

    with pytest.raises(ContentAssetAlreadyDraftError):
        await service.unpublish_case_item(
            case_item, actor_id="admin-1", acknowledge=False
        )
