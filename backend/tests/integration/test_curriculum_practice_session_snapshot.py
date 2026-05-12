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
from curriculum_practice.schemas import CurriculumRuntimeSnapshot
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


async def _create_published_template(
    db: AsyncSession,
    *,
    agent: Agent,
    persona: Persona,
    runtime_profile: VoiceRuntimeProfile,
    ruleset: ScoringRuleset,
    knowledge_base: KnowledgeBase,
    scenario_type: str = "sales",
) -> PracticeTemplate:
    template = PracticeTemplate(
        name="课程化客户异议训练",
        description="用于 session snapshot 持久化测试",
        scenario_type=scenario_type,
        mode="customer_roleplay",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
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
    assert data["runtime_state"] is None

    session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == data["session_id"]
            )
        )
    ).scalar_one()
    assert session.practice_template_id is None
    assert session.curriculum_snapshot is None
    assert session.runtime_state is None


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
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "stepfun_realtime",
            "practice_template_id": template.template_id,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert len(build_calls) == 1
    assert data["practice_template_id"] == template.template_id
    assert data["runtime_state"] is None
    assert data["curriculum_snapshot"]["practice_template"] == {
        "asset_type": "practice_template",
        "asset_id": template.template_id,
        "version": 1,
        "hash": template.content_hash,
        "snapshot_label": "published",
    }
    assert data["curriculum_snapshot"]["runtime"]["runtime_profile_id"] == runtime_profile.id
    assert data["curriculum_snapshot"]["training_task"] == {
        "id": data["session_id"],
        "scenario_type": "sales",
    }

    session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == data["session_id"]
            )
        )
    ).scalar_one()
    assert session.practice_template_id == template.template_id
    assert session.curriculum_snapshot == data["curriculum_snapshot"]
    assert session.status == "preparing"


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
