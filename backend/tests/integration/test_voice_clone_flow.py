from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, Persona, VoiceRuntimeProfile
from common.db.models import ScoringRuleset, User
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    CaseItemCreate,
    RoleProfileCreate,
    RoleProfileResponse,
)
from curriculum_practice.services.content_assets import (
    ContentAssetNotEditableError,
    ContentAssetService,
    case_item_content_hash,
    role_profile_content_hash,
)
from curriculum_practice.services.practice_templates import PracticeTemplateService
from curriculum_practice.services.voice_clone import VoiceCloneResult
from sales_bot.websocket.components.stepfun_voice_selection import resolve_session_voice


class _SuccessfulVoiceCloneService:
    async def create_voice(
        self,
        *,
        voice_name: str,
        audio_bytes: bytes,
        content_type: str,
    ) -> VoiceCloneResult:
        return VoiceCloneResult(
            ok=True,
            voice_id="custom_voice_cto",
            retryable=False,
            fallback_voice=None,
            reason_code=None,
        )


class _RejectedVoiceCloneService:
    async def create_voice(
        self,
        *,
        voice_name: str,
        audio_bytes: bytes,
        content_type: str,
    ) -> VoiceCloneResult:
        return VoiceCloneResult(
            ok=False,
            voice_id=None,
            retryable=False,
            fallback_voice="default_voice",
            reason_code="voice_clone_rejected",
        )


def _role_profile_payload(*, content_hash: str = "sha256:pending") -> dict[str, object]:
    return {
        "role_type": "customer",
        "role_name": "谨慎型 CTO",
        "persona_ref": None,
        "communication_style": "直接、重视技术细节和风险控制",
        "pressure_level": "high",
        "knowledge_boundary": ["了解内部预算流程", "不知道最终采购时间"],
        "behavior_rules": ["只回答被直接提问的问题", "价格问题上先反驳再让步"],
        "voice_style_hint": "语速偏快，语调克制",
        "content_hash": content_hash,
    }


@pytest.mark.asyncio
async def test_should_register_voice_and_update_role_profile(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload()
    payload["content_hash"] = role_profile_content_hash(payload)
    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(
        RoleProfileCreate.model_validate(payload), actor_id="admin-1"
    )

    result = await service.register_role_profile_voice(
        role_profile,
        voice_service=_SuccessfulVoiceCloneService(),
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
        voice_sample_url="oss://role-voices/cto.wav",
        actor_id="admin-1",
    )

    refreshed = await service.get_role_profile(role_profile.role_profile_id)
    assert result.ok is True
    assert refreshed is not None
    assert refreshed.voice_id == "custom_voice_cto"
    assert refreshed.voice_sample_url == "oss://role-voices/cto.wav"
    assert refreshed.content_hash == role_profile_content_hash(
        RoleProfileResponse.model_validate(refreshed)
    )


@pytest.mark.asyncio
async def test_should_reject_voice_registration_when_role_profile_not_draft(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload()
    payload["content_hash"] = role_profile_content_hash(payload)
    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(
        RoleProfileCreate.model_validate(payload), actor_id="admin-1"
    )
    role_profile = await service.publish_role_profile(role_profile, actor_id="admin-1")

    with pytest.raises(ContentAssetNotEditableError):
        await service.register_role_profile_voice(
            role_profile,
            voice_service=_SuccessfulVoiceCloneService(),
            voice_name="谨慎型 CTO",
            audio_bytes=b"voice-bytes",
            content_type="audio/wav",
            voice_sample_url="oss://role-voices/cto.wav",
            actor_id="admin-1",
        )


@pytest.mark.asyncio
async def test_should_not_update_role_profile_when_voice_clone_is_rejected(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload()
    payload["content_hash"] = role_profile_content_hash(payload)
    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(
        RoleProfileCreate.model_validate(payload), actor_id="admin-1"
    )

    result = await service.register_role_profile_voice(
        role_profile,
        voice_service=_RejectedVoiceCloneService(),
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
        voice_sample_url="oss://role-voices/cto.wav",
        actor_id="admin-1",
    )

    refreshed = await service.get_role_profile(role_profile.role_profile_id)
    assert result.ok is False
    assert refreshed is not None
    assert refreshed.voice_id is None
    assert refreshed.voice_sample_url is None


@pytest.mark.asyncio
async def test_should_fail_parent_publish_when_child_role_profile_voices_mismatch(
    test_db: AsyncSession,
) -> None:
    actor = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"voice-gate-publisher-{uuid.uuid4()}",
        email=f"voice-gate-publisher-{uuid.uuid4()}@example.com",
        name="Voice Gate Publisher",
        role="admin",
        is_active=True,
    )
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Voice Gate Agent",
        description="agent",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Voice Gate Persona",
        description="persona",
        category="customer",
        system_prompt="Act as a careful buyer.",
        status="active",
    )
    runtime_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="Voice Gate Runtime",
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="default_voice",
    )
    ruleset = ScoringRuleset(
        ruleset_id=str(uuid.uuid4()),
        scenario_type="sales",
        version="sales-v1",
        display_name="Sales v1",
        status="published",
        definition_json={"scenario_type": "sales"},
        is_active=True,
    )
    test_db.add_all([actor, agent, persona, runtime_profile, ruleset])
    await test_db.commit()
    asset_service = ContentAssetService(test_db)
    case_payload: dict[str, object] = {
        "industry": "企业软件",
        "company_profile": "客户正在评估销售训练平台。",
        "customer_role": "CTO",
        "pain_points": ["新人上手慢"],
        "objections": ["预算紧张"],
        "hidden_information": "预算需要追问后披露。",
        "success_criteria": ["确认试点范围"],
        "allowed_disclosure_policy": {
            "phases": [{"trigger": "ask", "disclose": "budget"}],
            "roleplay": {"situation_code": "first_visit"},
        },
        "content_hash": "sha256:pending",
    }
    case_payload["content_hash"] = case_item_content_hash(case_payload)
    case_item = await asset_service.create_case_item(
        CaseItemCreate.model_validate(case_payload),
        actor_id=str(actor.user_id),
    )
    case_item = await asset_service.publish_case_item(
        case_item,
        actor_id=str(actor.user_id),
    )
    child_templates: list[PracticeTemplate] = []
    for voice_id in ("custom_voice_a", "custom_voice_b"):
        role_payload = _role_profile_payload()
        role_payload["content_hash"] = role_profile_content_hash(role_payload)
        role = await asset_service.create_role_profile(
            RoleProfileCreate.model_validate(role_payload),
            actor_id=str(actor.user_id),
        )
        await asset_service.register_role_profile_voice(
            role,
            voice_service=_SuccessfulVoiceCloneServiceFor(voice_id),
            voice_name="谨慎型 CTO",
            audio_bytes=b"voice-bytes",
            content_type="audio/wav",
            voice_sample_url=f"oss://role-voices/{voice_id}.wav",
            actor_id=str(actor.user_id),
        )
        role = await asset_service.publish_role_profile(
            role,
            actor_id=str(actor.user_id),
        )
        child = PracticeTemplate(
            name=f"child {voice_id}",
            description="child stage template",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id=agent.id,
            persona_id=persona.id,
            runtime_profile_id=runtime_profile.id,
            voice_mode="stepfun_realtime",
            scoring_ruleset_id=ruleset.ruleset_id,
            case_item_id=case_item.case_item_id,
            role_profile_id=role.role_profile_id,
            situation_pack_code="first_visit",
        )
        test_db.add(child)
        await test_db.commit()
        published_child, child_decision = await PracticeTemplateService(
            test_db
        ).publish_template(child, actor_id=str(actor.user_id))
        assert child_decision.can_publish is True
        assert published_child is not None
        child_templates.append(published_child)
    parent = PracticeTemplate(
        name="parent with voice mismatch",
        description="parent",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        case_item_id=case_item.case_item_id,
        situation_pack_code="first_visit",
        curriculum_plan={
            "name": "voice mismatch plan",
            "stages": [
                _stage_payload("opening", 1, child_templates[0]),
                _stage_payload("closing", 2, child_templates[1]),
            ],
        },
        max_stage_duration_seconds=900,
    )
    test_db.add(parent)
    await test_db.commit()

    published_parent, decision = await PracticeTemplateService(test_db).publish_template(
        parent, actor_id=str(actor.user_id)
    )

    assert published_parent is None
    assert decision.can_publish is False
    assert "cross_stage_voice_hot_switch_unsupported" in [
        result.reason_code for result in decision.results
    ]


async def test_should_initialize_stepfun_session_with_role_profile_voice_id() -> None:
    voice = resolve_session_voice(
        default_voice="default_voice",
        runtime_snapshot={"role_profile_voice_id": "custom_voice_cto"},
    )

    assert voice == "custom_voice_cto"


async def test_should_fallback_to_default_voice_when_role_voice_unavailable() -> None:
    voice = resolve_session_voice(
        default_voice="default_voice",
        runtime_snapshot={"role_profile_voice_id": "custom_voice_cto"},
        unavailable_voice_ids={"custom_voice_cto"},
    )

    assert voice == "default_voice"


async def test_should_not_attempt_voice_hot_switching_during_runtime() -> None:
    voice = resolve_session_voice(
        default_voice="default_voice",
        runtime_snapshot={
            "role_profile_voice_id": "custom_voice_cto",
            "stage_snapshots": {
                "opening": {"runtime_payload": {"role_profile_voice_id": "voice_a"}},
                "closing": {"runtime_payload": {"role_profile_voice_id": "voice_b"}},
            },
        },
        current_stage_key="closing",
        allow_hot_switch=False,
    )

    assert voice == "custom_voice_cto"


class _SuccessfulVoiceCloneServiceFor:
    def __init__(self, voice_id: str) -> None:
        self._voice_id = voice_id

    async def create_voice(
        self,
        *,
        voice_name: str,
        audio_bytes: bytes,
        content_type: str,
    ) -> VoiceCloneResult:
        return VoiceCloneResult(
            ok=True,
            voice_id=self._voice_id,
            retryable=False,
            fallback_voice=None,
            reason_code=None,
        )


def _stage_payload(
    template_stage_key: str, order: int, template: PracticeTemplate
) -> dict[str, object]:
    return {
        "template_stage_key": template_stage_key,
        "order": order,
        "name": template_stage_key,
        "template_ref": {
            "asset_type": "practice_template",
            "asset_id": str(template.template_id),
            "version": int(template.version),
            "hash": str(template.content_hash),
            "snapshot_label": "published",
        },
        "completion_policy": {
            "min_score": 7.0,
            "min_rounds": 1,
            "max_duration_seconds": 600,
        },
        "failure_policy": "retry_current",
        "prerequisites": [],
    }
