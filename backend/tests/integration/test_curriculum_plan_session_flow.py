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
    CurriculumRuntimeSnapshot,
    CurriculumVersionRef,
    TemplateStageSnapshot,
)
from curriculum_practice.services.practice_templates import PracticeTemplateService
from curriculum_practice.services.snapshots import RuntimeSnapshotService


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
    template = PracticeTemplate(
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
    )
    db.add(template)
    await db.commit()
    published, decision = await PracticeTemplateService(db).publish_template(
        template,
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base, template = (
        await _seed_template_runtime(test_db)
    )

    async def build_snapshot(
        self: RuntimeSnapshotService,
        template_ref,
        training_task_ref: dict[str, object],
        actor_id: str,
        *,
        trace_id: str | None = None,
        created_at: str | None = None,
    ) -> CurriculumRuntimeSnapshot:
        stage_template_ref = CurriculumVersionRef(
            asset_type="practice_template",
            asset_id=template.template_id,
            version=1,
            hash=str(template.content_hash),
            snapshot_label="published",
        )
        rubric_ref = CurriculumVersionRef(
            asset_type="scoring_ruleset",
            asset_id=ruleset.ruleset_id,
            version=ruleset.version,
            hash="sha256:ruleset",
            snapshot_label="published",
        )
        return CurriculumRuntimeSnapshot(
            snapshot_hash="sha256:flow",
            created_at=created_at or "2026-05-13T00:00:00+00:00",
            trace_id=trace_id,
            training_task={"id": str(training_task_ref["id"]), "scenario_type": "sales"},
            practice_template={
                "asset_type": template_ref.asset_type,
                "asset_id": template_ref.asset_id,
                "version": template_ref.version,
                "hash": template_ref.hash,
                "snapshot_label": template_ref.snapshot_label,
            },
            content_assets=[
                {
                    "asset_type": "knowledge_base",
                    "asset_id": knowledge_base.id,
                    "version": 1,
                    "hash": "sha256:kb",
                    "snapshot_label": "legacy_unversioned",
                }
            ],
            rubric=rubric_ref,
            runtime={
                "agent_id": agent.id,
                "persona_id": persona.id,
                "runtime_profile_id": runtime_profile.id,
                "voice_policy_snapshot_hash": "sha256:voice",
                "instruction_contract_hash": "sha256:instruction",
            },
            stage_snapshots={
                "template_stage_opening": TemplateStageSnapshot(
                    template_ref=stage_template_ref,
                    runtime_payload={
                        "template_id": template.template_id,
                        "mode": "customer_roleplay",
                        "voice_mode": "stepfun_realtime",
                    },
                    content_assets=[],
                    rubric=rubric_ref,
                    runtime={
                        "agent_id": agent.id,
                        "persona_id": persona.id,
                        "runtime_profile_id": runtime_profile.id,
                        "voice_policy_snapshot_hash": "sha256:voice",
                        "instruction_contract_hash": "sha256:instruction",
                    },
                )
            },
        )

    monkeypatch.setattr(RuntimeSnapshotService, "build_for_session", build_snapshot)

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
    ]["template_id"] == template.template_id

    session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == data["session_id"])
        )
    ).scalar_one()
    assert session.curriculum_snapshot["stage_snapshots"] == data["curriculum_snapshot"][
        "stage_snapshots"
    ]
