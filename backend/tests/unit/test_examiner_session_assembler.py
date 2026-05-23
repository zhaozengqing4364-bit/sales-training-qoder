"""Unit tests for examiner session assembly."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, User
from curriculum_practice.models import ExaminerAgent, LearningContent, PracticeTemplate, QuestionItem
from curriculum_practice.services.examiner_session_assembler import ExaminerSessionAssembler


@pytest.mark.asyncio
async def test_assembler_prefers_template_bound_examiner(
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
    fallback_agent = ExaminerAgent(
        name="Fallback",
        question_source_ids=[],
        learner_level_strategy={},
        scoring_policy_id="policy-1",
        timeout_config={"max_seconds": 600},
        safety_config={},
        prompt_config={},
        simulation_config={},
        status="published",
        version=1,
        content_hash="fallback-hash",
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
    test_db.add_all([content, fallback_agent, bound_agent, question])
    await test_db.flush()
    bound_agent.question_source_ids = [str(question.question_id)]
    template = PracticeTemplate(
        name="模板",
        scenario_type="sales",
        mode="examiner",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="profile-1",
        scoring_ruleset_id="ruleset-1",
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
    assets = snapshot["content_assets"]
    assert assets[0]["asset_id"] == str(bound_agent.examiner_agent_id)


@pytest.mark.asyncio
async def test_assembler_rejects_when_template_examiner_not_bound(
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
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="profile-1",
        scoring_ruleset_id="ruleset-1",
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
