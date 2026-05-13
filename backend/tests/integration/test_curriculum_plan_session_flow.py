from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import PracticeSession, ScoringRuleset
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    CurriculumPlanSchema,
)
from curriculum_practice.services.practice_templates import PracticeTemplateService


async def _seed_template_runtime(
    db: AsyncSession,
) -> tuple[Agent, Persona, VoiceRuntimeProfile, ScoringRuleset, KnowledgeBase, PracticeTemplate]:
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Curriculum Flow Agent",
        description="agent for curriculum flow tests",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Curriculum Flow Persona",
        description="persona for curriculum flow tests",
        category="customer",
        difficulty="medium",
        system_prompt="Act as a careful buyer.",
        status="active",
    )
    runtime_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="Curriculum Flow Runtime",
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
        name="Curriculum Flow KB",
        description="kb for curriculum flow tests",
        category="product",
        vector_collection="curriculum_flow_kb",
        status="active",
    )
    db.add_all([agent, persona, runtime_profile, ruleset, knowledge_base])
    await db.flush()
    db.add(AgentPersona(agent_id=agent.id, persona_id=persona.id, is_default=True))
    child_template = PracticeTemplate(
        name="课程化子阶段训练",
        description="child stage template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
    )
    db.add(child_template)
    await db.commit()
    child_published, child_decision = await PracticeTemplateService(db).publish_template(
        child_template,
        actor_id=None,
    )
    assert child_decision.can_publish is True
    assert child_published is not None
    parent_template = PracticeTemplate(
        name="课程化多阶段训练",
        description="session flow stage snapshots test",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
        curriculum_plan=CurriculumPlanSchema(
            name="课程化多阶段训练",
            max_stage_duration_seconds=900,
            stages=[
                {
                    "template_stage_key": "template_stage_opening",
                    "order": 1,
                    "name": "开场",
                    "template_ref": {
                        "asset_type": "practice_template",
                        "asset_id": str(child_published.template_id),
                        "version": int(child_published.version),
                        "hash": str(child_published.content_hash),
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
            ],
        ).model_dump(mode="json"),
        max_stage_duration_seconds=900,
    )
    db.add(parent_template)
    await db.commit()
    published, decision = await PracticeTemplateService(db).publish_template(
        parent_template,
        actor_id=None,
    )
    assert decision.can_publish is True
    assert published is not None
    return agent, persona, runtime_profile, ruleset, knowledge_base, published


@pytest.mark.asyncio
async def test_should_create_session_with_curriculum_stage_snapshots(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    agent, persona, runtime_profile, _ruleset, _knowledge_base, template = (
        await _seed_template_runtime(test_db)
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
    assert data["curriculum_snapshot"]["stage_snapshots"]["template_stage_opening"][
        "runtime_payload"
    ]["voice_mode"] == "stepfun_realtime"
    assert data["curriculum_snapshot"]["stage_snapshots"]["template_stage_opening"][
        "runtime"
    ]["agent_id"] == agent.id
    assert data["curriculum_snapshot"]["stage_snapshots"]["template_stage_opening"][
        "runtime"
    ]["persona_id"] == persona.id
    assert data["curriculum_snapshot"]["stage_snapshots"]["template_stage_opening"][
        "runtime"
    ]["runtime_profile_id"] == runtime_profile.id

    session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == data["session_id"])
        )
    ).scalar_one()
    assert session.curriculum_snapshot["stage_snapshots"] == data["curriculum_snapshot"][
        "stage_snapshots"
    ]
