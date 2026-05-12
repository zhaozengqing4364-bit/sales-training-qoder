from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import PracticeSession, ScoringRuleset, TrainingTask
from common.knowledge.models import KnowledgeBase
from common.services.practice_session_service import PracticeServiceError
from common.training_tasks.schemas import (
    TrainingTaskResponse,
    TrainingTaskStartSessionRequest,
)
from common.training_tasks.service import start_training_task_session
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.services.practice_templates import PracticeTemplateService


async def _seed_sales_runtime(
    db: AsyncSession,
) -> tuple[Agent, Persona, VoiceRuntimeProfile, ScoringRuleset, KnowledgeBase]:
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Training Task Agent",
        description="agent for training task template binding tests",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Training Task Persona",
        description="persona for training task template binding tests",
        category="customer",
        difficulty="medium",
        system_prompt="Act as a cautious buyer.",
        status="active",
    )
    runtime_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="Training Task StepFun Runtime",
        is_default=True,
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
        name="Training Task KB",
        description="kb for training task template binding tests",
        category="product",
        vector_collection="training_task_kb",
        status="active",
    )
    db.add_all([agent, persona, runtime_profile, ruleset, knowledge_base])
    await db.flush()
    db.add(AgentPersona(agent_id=agent.id, persona_id=persona.id, is_default=True))
    await db.commit()
    return agent, persona, runtime_profile, ruleset, knowledge_base


async def _create_training_task(db: AsyncSession, *, assignee_id: str) -> TrainingTask:
    task = TrainingTask(
        task_id=str(uuid.uuid4()),
        title="补强客户异议处理",
        assignee_id=assignee_id,
        scenario_type="sales",
        goal="练习用客户案例回应价格异议",
        focus_intent="price_objection",
        completion_criteria={"minimum_sessions": 1},
        source="manual",
        status="assigned",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _create_published_template(
    db: AsyncSession,
    *,
    agent: Agent,
    persona: Persona,
    runtime_profile: VoiceRuntimeProfile,
    ruleset: ScoringRuleset,
    knowledge_base: KnowledgeBase,
) -> PracticeTemplate:
    template = PracticeTemplate(
        name="Training Task Template",
        description="template for training task binding tests",
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
    return published


@pytest.mark.asyncio
async def test_training_task_start_session_keeps_unbound_legacy_path(
    test_db: AsyncSession,
    test_user,
) -> None:
    agent, persona, _, _, _ = await _seed_sales_runtime(test_db)
    task = await _create_training_task(test_db, assignee_id=str(test_user.user_id))

    updated_task, session = await start_training_task_session(
        test_db,
        task,
        TrainingTaskStartSessionRequest(
            agent_id=agent.id,
            persona_id=persona.id,
            voice_mode="stepfun_realtime",
        ),
        current_user=test_user,
    )

    data = TrainingTaskResponse.model_validate(updated_task).model_dump(mode="json")
    assert data["status"] == "in_progress"
    assert data["practice_template_id"] is None
    assert "preflight" not in data
    assert "stage" not in data
    assert "reconnect" not in data
    assert session.practice_template_id is None
    assert session.curriculum_snapshot is None
    assert session.runtime_state is None
    assert session.status == "preparing"

    refreshed_task = await test_db.get(TrainingTask, task.task_id)
    assert refreshed_task is not None
    assert refreshed_task.status == "in_progress"


@pytest.mark.asyncio
async def test_training_task_start_session_uses_bound_published_template(
    test_db: AsyncSession,
    test_user,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_sales_runtime(
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
    task = await _create_training_task(test_db, assignee_id=str(test_user.user_id))
    task.practice_template_id = template.template_id
    await test_db.commit()

    updated_task, session = await start_training_task_session(
        test_db,
        task,
        TrainingTaskStartSessionRequest(
            agent_id=agent.id,
            persona_id=persona.id,
            voice_mode="stepfun_realtime",
        ),
        current_user=test_user,
    )

    data = TrainingTaskResponse.model_validate(updated_task).model_dump(mode="json")
    assert data["practice_template_id"] == template.template_id
    assert data["status"] == "in_progress"
    assert session.practice_template_id == template.template_id
    assert session.runtime_state is None
    assert session.curriculum_snapshot is not None
    assert session.curriculum_snapshot["practice_template"] == {
        "asset_type": "practice_template",
        "asset_id": template.template_id,
        "version": 1,
        "hash": template.content_hash,
        "snapshot_label": "published",
    }
    assert session.curriculum_snapshot["training_task"] == {
        "id": str(session.session_id),
        "scenario_type": "sales",
    }

    session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == str(session.session_id)
            )
        )
    ).scalar_one()
    assert session.practice_template_id == template.template_id
    assert session.status == "preparing"


@pytest.mark.asyncio
async def test_training_task_start_session_rejects_unusable_template_dependency(
    test_db: AsyncSession,
    test_user,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_sales_runtime(
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
    ruleset.status = "draft"
    task = await _create_training_task(test_db, assignee_id=str(test_user.user_id))
    task.practice_template_id = template.template_id
    await test_db.commit()

    with pytest.raises(PracticeServiceError) as exc_info:
        await start_training_task_session(
            test_db,
            task,
            TrainingTaskStartSessionRequest(
                agent_id=agent.id,
                persona_id=persona.id,
                voice_mode="stepfun_realtime",
            ),
            current_user=test_user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "[RUNTIME_SNAPSHOT_RUBRIC_MISSING]"


@pytest.mark.asyncio
async def test_training_task_start_session_rejects_unpublished_template(
    test_db: AsyncSession,
    test_user,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_sales_runtime(
        test_db
    )
    template = PracticeTemplate(
        name="Draft Training Task Template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
        status="draft",
    )
    test_db.add(template)
    await test_db.commit()
    task = await _create_training_task(test_db, assignee_id=str(test_user.user_id))
    task.practice_template_id = template.template_id
    await test_db.commit()

    with pytest.raises(PracticeServiceError) as exc_info:
        await start_training_task_session(
            test_db,
            task,
            TrainingTaskStartSessionRequest(
                agent_id=agent.id,
                persona_id=persona.id,
                voice_mode="stepfun_realtime",
            ),
            current_user=test_user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "[PRACTICE_TEMPLATE_NOT_PUBLISHED]"


@pytest.mark.asyncio
async def test_training_task_start_session_rejects_missing_template(
    test_db: AsyncSession,
    test_user,
) -> None:
    agent, persona, _, _, _ = await _seed_sales_runtime(test_db)
    task = await _create_training_task(test_db, assignee_id=str(test_user.user_id))
    task.practice_template_id = str(uuid.uuid4())
    await test_db.commit()

    with pytest.raises(PracticeServiceError) as exc_info:
        await start_training_task_session(
            test_db,
            task,
            TrainingTaskStartSessionRequest(
                agent_id=agent.id,
                persona_id=persona.id,
                voice_mode="stepfun_realtime",
            ),
            current_user=test_user,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "[PRACTICE_TEMPLATE_NOT_FOUND]"


@pytest.mark.asyncio
async def test_training_task_start_session_rejects_invalid_template_id(
    test_db: AsyncSession,
    test_user,
) -> None:
    agent, persona, _, _, _ = await _seed_sales_runtime(test_db)
    task = await _create_training_task(test_db, assignee_id=str(test_user.user_id))
    task.practice_template_id = "not-a-template-id"
    await test_db.commit()

    with pytest.raises(PracticeServiceError) as exc_info:
        await start_training_task_session(
            test_db,
            task,
            TrainingTaskStartSessionRequest(
                agent_id=agent.id,
                persona_id=persona.id,
                voice_mode="stepfun_realtime",
            ),
            current_user=test_user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "[PRACTICE_TEMPLATE_INVALID]"


@pytest.mark.asyncio
async def test_training_task_status_constraint_excludes_runtime_states(
    test_db: AsyncSession,
    test_user,
) -> None:
    assignee_id = str(test_user.user_id)
    allowed_statuses = {"assigned", "in_progress", "completed", "expired", "cancelled"}
    for status in allowed_statuses:
        test_db.add(
            TrainingTask(
                task_id=str(uuid.uuid4()),
                title=f"状态约束 {status}",
                assignee_id=assignee_id,
                scenario_type="sales",
                goal="验证 TrainingTask 状态约束",
                completion_criteria={},
                source="manual",
                status=status,
            )
        )
    await test_db.commit()

    for runtime_status in ("preflight", "stage", "reconnect"):
        test_db.add(
            TrainingTask(
                task_id=str(uuid.uuid4()),
                title=f"非法运行态 {runtime_status}",
                assignee_id=assignee_id,
                scenario_type="sales",
                goal="验证 TrainingTask 不接收运行态",
                completion_criteria={},
                source="manual",
                status=runtime_status,
            )
        )
        with pytest.raises(IntegrityError):
            await test_db.commit()
        await test_db.rollback()
