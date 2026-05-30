from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import PracticeSession, Presentation, Scenario, ScoringRuleset
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    CaseItemCreate,
    CurriculumRuntimeSnapshot,
)
from curriculum_practice.services.asset_resolution import (
    ASSET_RESOLUTION_DIRECT_PRACTICE_LIVE,
    ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS,
    ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE,
)
from curriculum_practice.services.content_assets import (
    ContentAssetService,
    case_item_content_hash,
)
from curriculum_practice.services.practice_templates import PracticeTemplateService
from curriculum_practice.services.snapshots import (
    RuntimeSnapshotBuildError,
    RuntimeSnapshotService,
)


async def _seed_runtime_entities(
    db: AsyncSession,
) -> tuple[Agent, Persona, VoiceRuntimeProfile, ScoringRuleset, KnowledgeBase]:
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Curriculum Agent",
        description="agent for curriculum session tests",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Curriculum Persona",
        description="persona for curriculum session tests",
        category="customer",
        difficulty="medium",
        system_prompt="Act as a cautious buyer.",
        status="active",
    )
    runtime_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="Curriculum StepFun Runtime",
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
        name="Curriculum KB",
        description="kb for curriculum session tests",
        category="product",
        vector_collection="curriculum_kb",
        status="active",
    )
    db.add_all([agent, persona, runtime_profile, ruleset, knowledge_base])
    await db.flush()
    db.add(
        AgentPersona(
            agent_id=agent.id,
            persona_id=persona.id,
            is_default=True,
        )
    )
    await db.commit()
    return agent, persona, runtime_profile, ruleset, knowledge_base


def _case_item_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "industry": "制造业",
        "company_profile": "客户公司正在扩产，需要降低质检成本。",
        "customer_role": "采购总监",
        "pain_points": ["产线返工率高"],
        "objections": ["预算紧张"],
        "hidden_information": "隐藏预算不能进入初始 prompt",
        "success_criteria": ["确认试点范围"],
        "allowed_disclosure_policy": {
            "phases": [{"trigger": "ask", "disclose": "budget"}],
            "roleplay": {"situation_code": "first_visit"},
        },
        "content_hash": "sha256:pending",
    }
    payload["content_hash"] = case_item_content_hash(payload)
    return payload


async def _create_published_case_item(db: AsyncSession) -> object:
    service = ContentAssetService(db)
    case_item = await service.create_case_item(
        CaseItemCreate.model_validate(_case_item_payload()),
        actor_id="admin-1",
    )
    return await service.publish_case_item(case_item, actor_id="admin-1")


async def _create_published_template(
    db: AsyncSession,
    *,
    agent: Agent,
    persona: Persona,
    runtime_profile: VoiceRuntimeProfile,
    ruleset: ScoringRuleset,
    knowledge_base: KnowledgeBase,
    scenario_type: str = "sales",
    mode: str = "customer_roleplay",
) -> PracticeTemplate:
    case_item_id = None
    if mode == "customer_roleplay":
        case_item = await _create_published_case_item(db)
        case_item_id = case_item.case_item_id
    template = PracticeTemplate(
        name="课程化客户异议训练",
        description="用于 session snapshot 持久化测试",
        scenario_type=scenario_type,
        mode=mode,
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
        case_item_id=case_item_id,
        situation_pack_code="first_visit" if mode == "customer_roleplay" else None,
    )
    db.add(template)
    await db.commit()
    published, decision = await PracticeTemplateService(db).publish_template(
        template,
        actor_id=None,
    )
    assert decision.can_publish is True
    assert published is not None
    return published


@pytest.mark.asyncio
async def test_legacy_session_creation_keeps_curriculum_fields_empty(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    agent, persona, _, _, _ = await _seed_runtime_entities(test_db)

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "stepfun_realtime",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["status"] == "preparing"
    assert data["runtime_subject"] == "training_scenario_runtime"
    assert data["practice_template_id"] is None
    assert data["curriculum_snapshot"] is None
    assert data["voice_policy_snapshot"]["asset_resolution"]["mode"] == (
        ASSET_RESOLUTION_DIRECT_PRACTICE_LIVE
    )
    assert data["runtime_state"]["_lifecycle"]["state"] == "runnable"

    session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == data["session_id"]
            )
        )
    ).scalar_one()
    assert session.practice_template_id is None
    assert session.curriculum_snapshot is None
    assert session.runtime_state["_lifecycle"]["state"] == "runnable"


@pytest.mark.asyncio
async def test_template_backed_session_persists_runtime_snapshot(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_calls: list[tuple[object, ...]] = []
    original_build_for_session = RuntimeSnapshotService.build_for_session

    async def spy_build_for_session(
        self: RuntimeSnapshotService,
        *args: Any,
        **kwargs: Any,
    ) -> CurriculumRuntimeSnapshot:
        build_calls.append(args)
        return await original_build_for_session(self, *args, **kwargs)

    monkeypatch.setattr(
        RuntimeSnapshotService,
        "build_for_session",
        spy_build_for_session,
    )
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    template = await _create_published_template(
        test_db,
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
    )

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "voice_mode": "stepfun_realtime",
            "practice_template_id": template.template_id,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert len(build_calls) == 1
    assert data["practice_template_id"] == template.template_id
    assert data["agent_id"] == agent.id
    assert data["persona_id"] == persona.id
    assert data["runtime_state"]["_lifecycle"]["state"] == "runnable"
    assert data["curriculum_snapshot"]["practice_template"] == {
        "asset_type": "practice_template",
        "asset_id": template.template_id,
        "version": 1,
        "hash": template.content_hash,
        "snapshot_label": "published",
    }
    assert data["curriculum_snapshot"]["runtime"]["runtime_profile_id"] == runtime_profile.id
    assert data["curriculum_snapshot"]["runtime"]["agent_id"] == agent.id
    assert data["curriculum_snapshot"]["runtime"]["persona_id"] == persona.id
    assert data["curriculum_snapshot"]["training_task"] == {
        "id": data["session_id"],
        "scenario_type": "sales",
    }
    assert data["curriculum_snapshot"]["asset_resolution"]["mode"] == (
        ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS
    )
    assert data["voice_policy_snapshot"]["roleplay_contract"] is not None
    assert (
        data["voice_policy_snapshot"]["roleplay_contract"]["contract_id"]
        == data["curriculum_snapshot"]["roleplay_contract"]["contract_id"]
    )

    session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == data["session_id"]
            )
        )
    ).scalar_one()
    assert session.practice_template_id == template.template_id
    assert session.agent_id == agent.id
    assert session.persona_id == persona.id
    assert session.voice_runtime_profile_id == runtime_profile.id
    assert session.curriculum_snapshot == data["curriculum_snapshot"]
    assert session.status == "preparing"


@pytest.mark.asyncio
async def test_legacy_template_session_uses_live_lookup_and_emits_warning(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    case_item = await _create_published_case_item(test_db)
    template = PracticeTemplate(
        name="无冻结引用的遗留模板",
        description="legacy template live lookup",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
        case_item_id=case_item.case_item_id,
        situation_pack_code="first_visit",
        published_asset_refs={},
        status="published",
        version=1,
        content_hash="sha256:legacy-template",
    )
    test_db.add(template)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "voice_mode": "stepfun_realtime",
            "practice_template_id": template.template_id,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["curriculum_snapshot"]["asset_resolution"]["mode"] == (
        ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE
    )
    assert data["curriculum_snapshot"]["legacy_warnings"]
    assert data["voice_policy_snapshot"]["asset_resolution"]["mode"] == (
        ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE
    )


@pytest.mark.asyncio
async def test_template_backed_session_rejects_runtime_identity_mismatch(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    other_agent = Agent(
        id=str(uuid.uuid4()),
        name="Other Agent",
        description="other",
        category="sales",
        status="published",
    )
    test_db.add(other_agent)
    await test_db.commit()
    template = await _create_published_template(
        test_db,
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
    )

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": other_agent.id,
            "persona_id": persona.id,
            "voice_mode": "stepfun_realtime",
            "practice_template_id": template.template_id,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "[PRACTICE_TEMPLATE_RUNTIME_IDENTITY_MISMATCH]"


@pytest.mark.asyncio
async def test_presentation_snapshot_failure_rolls_back_created_session(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_build_for_session(
        self: RuntimeSnapshotService,
        *args: Any,
        **kwargs: Any,
    ) -> CurriculumRuntimeSnapshot:
        raise RuntimeSnapshotBuildError("rubric_missing", "rubric unavailable")

    monkeypatch.setattr(
        RuntimeSnapshotService,
        "build_for_session",
        fail_build_for_session,
    )
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    template = await _create_published_template(
        test_db,
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
        scenario_type="presentation",
        mode="learning",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="curriculum_presentation",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Curriculum Presentation",
        file_url="https://example.com/curriculum.pptx",
        status="ready",
    )
    test_db.add_all([scenario, presentation])
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "presentation",
            "presentation_id": presentation.presentation_id,
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "stepfun_realtime",
            "practice_template_id": template.template_id,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "[RUNTIME_SNAPSHOT_RUBRIC_MISSING]"
    residual_sessions = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.presentation_id == presentation.presentation_id
            )
        )
    ).scalars().all()
    assert residual_sessions == []


@pytest.mark.asyncio
async def test_practice_session_status_constraint_rejects_curriculum_runtime_status(
    test_db: AsyncSession,
) -> None:
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        scenario_id=str(uuid.uuid4()),
        status="preflight_ready",
    )
    test_db.add(session)

    with pytest.raises(Exception):
        await test_db.commit()
