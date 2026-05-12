from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import ScoringRuleset
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import CaseItemCreate, RoleProfileCreate
from curriculum_practice.services.content_assets import (
    ContentAssetService,
    case_item_content_hash,
    role_profile_content_hash,
)
from curriculum_practice.services.practice_templates import (
    PracticeTemplateService,
    published_ref,
)
from curriculum_practice.services.snapshots import RuntimeSnapshotService


async def _seed_runtime_entities(
    db: AsyncSession,
) -> tuple[Agent, Persona, VoiceRuntimeProfile, ScoringRuleset, KnowledgeBase]:
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Case Role Agent",
        description="agent",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Case Role Persona",
        description="persona",
        category="customer",
        system_prompt="Act as a careful customer.",
        status="active",
    )
    runtime_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="Case Role StepFun Runtime",
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
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
    knowledge_base = KnowledgeBase(
        id=str(uuid.uuid4()),
        name="Case Role KB",
        description="kb",
        category="product",
        vector_collection="case_role_kb",
        status="active",
    )
    db.add_all([agent, persona, runtime_profile, ruleset, knowledge_base])
    await db.flush()
    db.add(AgentPersona(agent_id=agent.id, persona_id=persona.id, is_default=True))
    await db.commit()
    return agent, persona, runtime_profile, ruleset, knowledge_base


def _case_item_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "industry": "金融科技",
        "company_profile": "中型支付平台，正在评估企业级销售训练系统。",
        "customer_role": "CTO",
        "pain_points": ["销售新人上手慢"],
        "objections": ["预算紧张"],
        "hidden_information": "隐藏预算为 80 万，不能进入 StepFun 初始输入。",
        "success_criteria": ["识别预算状态"],
        "allowed_disclosure_policy": {
            "phases": [{"trigger": "询问预算", "keywords": ["预算"], "disclose": "预算范围"}]
        },
        "content_hash": "sha256:pending",
    }
    payload["content_hash"] = case_item_content_hash(payload)
    return payload


def _role_profile_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "role_type": "customer",
        "role_name": "谨慎型 CTO",
        "persona_ref": None,
        "communication_style": "直接、重视技术细节",
        "pressure_level": "high",
        "knowledge_boundary": ["了解预算流程"],
        "behavior_rules": ["只回答被直接提问的问题"],
        "voice_style_hint": "语速偏快",
        "content_hash": "sha256:pending",
    }
    payload["content_hash"] = role_profile_content_hash(payload)
    return payload


async def _create_case_and_role(db: AsyncSession, *, publish: bool) -> tuple[object, object]:
    service = ContentAssetService(db)
    case_item = await service.create_case_item(
        CaseItemCreate.model_validate(_case_item_payload()), actor_id="admin-1"
    )
    role_profile = await service.create_role_profile(
        RoleProfileCreate.model_validate(_role_profile_payload()), actor_id="admin-1"
    )
    if publish:
        case_item = await service.publish_case_item(case_item, actor_id="admin-1")
        role_profile = await service.publish_role_profile(role_profile, actor_id="admin-1")
    return case_item, role_profile


def _template(
    *,
    agent: Agent,
    persona: Persona,
    runtime_profile: VoiceRuntimeProfile,
    ruleset: ScoringRuleset,
    knowledge_base: KnowledgeBase,
    case_item_id: str,
    role_profile_id: str,
) -> PracticeTemplate:
    return PracticeTemplate(
        name="客户异议案例训练",
        description="引用 CaseItem 和 RoleProfile 的模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
        case_item_id=case_item_id,
        role_profile_id=role_profile_id,
    )


@pytest.mark.asyncio
async def test_should_reject_template_publish_when_case_or_role_is_unpublished(
    test_db: AsyncSession,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    case_item, role_profile = await _create_case_and_role(test_db, publish=False)
    template = _template(
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
        case_item_id=case_item.case_item_id,
        role_profile_id=role_profile.role_profile_id,
    )
    test_db.add(template)
    await test_db.commit()

    published, decision = await PracticeTemplateService(test_db).publish_template(
        template, actor_id="admin-1"
    )

    assert published is None
    assert decision.can_publish is False
    assert [item.reason_code for item in decision.results] == [
        "case_item_unpublished",
        "role_profile_unpublished",
    ]


@pytest.mark.asyncio
async def test_should_include_case_and_role_version_refs_without_hidden_information(
    test_db: AsyncSession,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    case_item, role_profile = await _create_case_and_role(test_db, publish=True)
    template = _template(
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
        case_item_id=case_item.case_item_id,
        role_profile_id=role_profile.role_profile_id,
    )
    test_db.add(template)
    await test_db.commit()
    published, decision = await PracticeTemplateService(test_db).publish_template(
        template, actor_id="admin-1"
    )
    assert decision.can_publish is True
    assert published is not None

    async def read_reference(asset_type: str, asset_id: str) -> dict[str, object] | None:
        if asset_type == "practice_template":
            item = await test_db.get(PracticeTemplate, asset_id)
            if item is None:
                return None
            return {
                "template_id": item.template_id,
                "status": item.status,
                "content_hash": item.content_hash,
                "runtime_profile_id": item.runtime_profile_id,
                "agent_id": item.agent_id,
                "persona_id": item.persona_id,
                "knowledge_base_refs": list(item.knowledge_base_refs or []),
                "scoring_ruleset_id": item.scoring_ruleset_id,
                "case_item_id": item.case_item_id,
                "role_profile_id": item.role_profile_id,
            }
        if asset_type == "voice_runtime_profile":
            item = await test_db.get(VoiceRuntimeProfile, asset_id)
            if item is None:
                return None
            return {
                "id": item.id,
                "is_active": item.is_active,
                "voice_mode": item.voice_mode,
                "model_name": item.model_name,
                "voice_name": item.voice_name,
            }
        if asset_type == "scoring_ruleset":
            item = await test_db.get(ScoringRuleset, asset_id)
            if item is None:
                return None
            return {
                "ruleset_id": item.ruleset_id,
                "status": item.status,
                "version": item.version,
                "definition_json": item.definition_json,
            }
        if asset_type == "knowledge_base":
            item = await test_db.get(KnowledgeBase, asset_id)
            if item is None:
                return None
            return {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "category": item.category,
                "vector_collection": item.vector_collection,
            }
        return await ContentAssetService(test_db).read_snapshot_reference(asset_type, asset_id)

    snapshot = await RuntimeSnapshotService(read_reference).build_for_session(
        published_ref(published),
        {"id": "session-case-role", "scenario_type": "sales"},
        "admin-1",
        created_at="2026-05-12T00:00:00+00:00",
    )

    refs = {item.asset_type: item for item in snapshot.content_assets}
    assert refs["case_item"].asset_id == case_item.case_item_id
    assert refs["case_item"].version == 1
    assert refs["case_item"].hash == case_item.content_hash
    assert refs["role_profile"].asset_id == role_profile.role_profile_id
    assert refs["role_profile"].hash == role_profile.content_hash

    serialized = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)
    assert "隐藏预算" not in serialized
    assert "hidden_information" not in serialized
