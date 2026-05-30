"""Unit tests for examiner session assembly."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import PracticeSession, ScoringRuleset, User
from curriculum_practice.models import (
    ExaminerAgent,
    LearningContent,
    PracticeTemplate,
    QuestionItem,
)
from curriculum_practice.services.examiner_session_assembler import (
    ExaminerSessionAssembler,
)


async def _seed_template_runtime(
    db: AsyncSession,
) -> tuple[Agent, Persona, VoiceRuntimeProfile, ScoringRuleset]:
    agent = Agent(
        name="Agent",
        description="agent",
        category="sales",
        status="published",
    )
    persona = Persona(
        name="Persona",
        description="persona",
        category="customer",
        difficulty="medium",
        system_prompt="persona prompt",
        status="active",
    )
    runtime_profile = VoiceRuntimeProfile(
        name=f"Runtime {id(db)}",
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    ruleset = ScoringRuleset(
        scenario_type="sales",
        version=f"ruleset-{id(db)}",
        display_name="Ruleset",
        status="published",
        definition_json={"dimensions": []},
        is_active=True,
    )
    db.add_all([agent, persona, runtime_profile, ruleset])
    await db.flush()
    db.add(AgentPersona(agent_id=agent.id, persona_id=persona.id, is_default=True))
    await db.flush()
    return agent, persona, runtime_profile, ruleset


@pytest.mark.asyncio
async def test_assembler_uses_single_published_template_snapshot(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    agent, persona, runtime_profile, ruleset = await _seed_template_runtime(test_db)
    content = LearningContent(
        title="讲义",
        summary="summary",
        owner="owner",
        source="source",
        status="published",
        version=1,
        content_hash="content-hash",
    )
    bound_agent = ExaminerAgent(
        name="Bound",
        question_source_ids=[],
        learner_level_strategy={},
        scoring_policy_id="policy-1",
        timeout_config={"max_seconds": 600},
        safety_config={},
        prompt_config={},
        simulation_config={},
        status="published",
        version=2,
        content_hash="bound-hash",
    )
    question = QuestionItem(
        category_id="cat-1",
        title="题 1",
        stem="题干",
        reference_answer="答案",
        scoring_criteria={},
        scoring_dimensions=["coverage"],
        status="published",
        safety_flagged=False,
        version=1,
        content_hash="question-hash",
    )
    test_db.add_all([content, bound_agent, question])
    await test_db.flush()
    bound_agent.question_source_ids = [str(question.question_id)]
    template = PracticeTemplate(
        name="模板",
        scenario_type="sales",
        mode="examiner",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        scoring_ruleset_id=ruleset.ruleset_id,
        learning_content_id=str(content.learning_content_id),
        examiner_agent_id=str(bound_agent.examiner_agent_id),
        status="published",
        version=1,
        content_hash="template-hash",
    )
    test_db.add(template)
    await test_db.commit()

    result = await ExaminerSessionAssembler(test_db).create_study_exam_session(
        user_id=str(test_user.user_id),
        learning_content_id=str(content.learning_content_id),
    )

    assert str(result.examiner_agent.examiner_agent_id) == str(
        bound_agent.examiner_agent_id
    )
    snapshot = result.session.curriculum_snapshot
    assert isinstance(snapshot, dict)
    assert snapshot["kind"] == "curriculum_examiner_session"
    assert snapshot["practice_template"]["asset_id"] == str(template.template_id)
    assert snapshot["runtime"]["agent_id"] == agent.id
    assert snapshot["runtime"]["persona_id"] == persona.id
    assets = {
        asset["asset_type"]: asset for asset in snapshot["content_assets"]
    }
    assert assets["examiner_agent"]["asset_id"] == str(bound_agent.examiner_agent_id)
    assert assets["question_item"]["asset_id"] == str(question.question_id)
    assert result.session.practice_template_id == str(template.template_id)
    assert result.session.agent_id == agent.id
    assert result.session.persona_id == persona.id


@pytest.mark.asyncio
async def test_assembler_rejects_when_template_examiner_not_bound(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    agent, persona, runtime_profile, ruleset = await _seed_template_runtime(test_db)
    content = LearningContent(
        title="讲义",
        summary="summary",
        owner="owner",
        source="source",
        status="published",
        version=1,
        content_hash="content-hash",
    )
    test_db.add(content)
    await test_db.commit()

    with pytest.raises(ValueError, match="\\[TEMPLATE_EXAMINER_NOT_BOUND\\]"):
        await ExaminerSessionAssembler(test_db).create_study_exam_session(
            user_id=str(test_user.user_id),
            learning_content_id=str(content.learning_content_id),
        )


@pytest.mark.asyncio
async def test_assembler_rejects_when_bound_examiner_is_unpublished(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    agent, persona, runtime_profile, ruleset = await _seed_template_runtime(test_db)
    content = LearningContent(
        title="讲义",
        summary="summary",
        owner="owner",
        source="source",
        status="published",
        version=1,
        content_hash="content-hash",
    )
    draft_agent = ExaminerAgent(
        name="Draft",
        question_source_ids=[],
        learner_level_strategy={},
        scoring_policy_id="policy-1",
        timeout_config={"max_seconds": 600},
        safety_config={},
        prompt_config={},
        simulation_config={},
        status="draft",
        version=1,
        content_hash="draft-hash",
    )
    test_db.add_all([content, draft_agent])
    await test_db.flush()
    template = PracticeTemplate(
        name="模板",
        scenario_type="sales",
        mode="examiner",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        scoring_ruleset_id=ruleset.ruleset_id,
        learning_content_id=str(content.learning_content_id),
        examiner_agent_id=str(draft_agent.examiner_agent_id),
        status="published",
        version=1,
        content_hash="template-hash",
    )
    test_db.add(template)
    await test_db.commit()

    with pytest.raises(ValueError, match="\\[EXAMINER_AGENT_NOT_FOUND\\]"):
        await ExaminerSessionAssembler(test_db).create_study_exam_session(
            user_id=str(test_user.user_id),
            learning_content_id=str(content.learning_content_id),
        )


@pytest.mark.asyncio
async def test_assembler_rejects_ambiguous_published_examiner_templates(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    agent, persona, runtime_profile, ruleset = await _seed_template_runtime(test_db)
    content = LearningContent(
        title="讲义",
        summary="summary",
        owner="owner",
        source="source",
        status="published",
        version=1,
        content_hash="content-hash",
    )
    examiner = ExaminerAgent(
        name="Examiner",
        question_source_ids=[],
        learner_level_strategy={},
        scoring_policy_id="policy-1",
        timeout_config={"max_seconds": 600},
        safety_config={},
        prompt_config={},
        simulation_config={},
        status="published",
        version=1,
        content_hash="examiner-hash",
    )
    test_db.add_all([content, examiner])
    await test_db.flush()
    for index in range(2):
        test_db.add(
            PracticeTemplate(
                name=f"模板 {index}",
                scenario_type="sales",
                mode="examiner",
                agent_id=agent.id,
                persona_id=persona.id,
                runtime_profile_id=runtime_profile.id,
                scoring_ruleset_id=ruleset.ruleset_id,
                learning_content_id=str(content.learning_content_id),
                examiner_agent_id=str(examiner.examiner_agent_id),
                status="published",
                version=1,
                content_hash=f"template-hash-{index}",
            )
        )
    await test_db.commit()

    with pytest.raises(ValueError, match="\\[TEMPLATE_EXAMINER_AMBIGUOUS\\]"):
        await ExaminerSessionAssembler(test_db).create_study_exam_session(
            user_id=str(test_user.user_id),
            learning_content_id=str(content.learning_content_id),
        )


@pytest.mark.asyncio
async def test_assembler_does_not_fall_back_to_latest_published_examiner(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    content = LearningContent(
        title="讲义",
        summary="summary",
        owner="owner",
        source="source",
        status="published",
        version=1,
        content_hash="content-hash",
    )
    agent = ExaminerAgent(
        name="Published",
        question_source_ids=[],
        learner_level_strategy={},
        scoring_policy_id="policy-1",
        timeout_config={"max_seconds": 600},
        safety_config={},
        prompt_config={},
        simulation_config={},
        status="published",
        version=1,
        content_hash="agent-hash",
    )
    question = QuestionItem(
        category_id="cat-1",
        title="题 1",
        stem="题干",
        reference_answer="答案",
        scoring_criteria={},
        scoring_dimensions=["coverage"],
        status="published",
        safety_flagged=False,
        version=1,
        content_hash="question-hash",
    )
    test_db.add_all([content, agent, question])
    await test_db.flush()
    agent.question_source_ids = [str(question.question_id)]
    await test_db.commit()

    with pytest.raises(ValueError, match="\\[TEMPLATE_EXAMINER_NOT_BOUND\\]"):
        await ExaminerSessionAssembler(test_db).create_study_exam_session(
            user_id=str(test_user.user_id),
            learning_content_id=str(content.learning_content_id),
        )

    session_count = await test_db.execute(select(PracticeSession))
    assert len(list(session_count.scalars().all())) == 0
