from __future__ import annotations

import uuid
from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.integration.test_curriculum_practice_session_snapshot import (
    _create_published_template,
    _seed_runtime_entities,
)

from common.db.models import PracticeSession, Scenario, User
from curriculum_practice.models import (
    ExaminerAgent,
    PracticeTemplate,
    QuestionCategory,
    QuestionItem,
)
from curriculum_practice.services.examiner_agents import examiner_agent_content_hash
from curriculum_practice.services.practice_templates import PracticeTemplateService
from curriculum_practice.services.session_snapshots import (
    apply_curriculum_snapshot_to_session,
)


@pytest.mark.asyncio
async def test_should_keep_session_curriculum_snapshot_immutable_after_template_v2_publish(
    test_db: AsyncSession,
) -> None:
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
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="snapshot_immutability_user",
        name="Snapshot Immutability User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="snapshot_immutability_sales",
        is_active=True,
    )
    session = PracticeSession(
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        agent_id=agent.id,
        persona_id=persona.id,
        voice_mode="stepfun_realtime",
        status="preparing",
    )
    test_db.add_all([user, scenario, session])
    await test_db.flush()

    await apply_curriculum_snapshot_to_session(
        db=test_db,
        session=session,
        practice_template_id=UUID(str(template.template_id)),
        scenario_type_value="sales",
        actor_id=str(user.user_id),
    )
    await test_db.commit()
    session_id = session.session_id
    original_snapshot = deepcopy(session.curriculum_snapshot)

    stored_template = await test_db.get(PracticeTemplate, template.template_id)
    assert stored_template is not None
    stored_template.name = "课程化客户异议训练 v2"
    stored_template.description = "template v2 should not rewrite old sessions"
    stored_template.version = 2
    stored_template.content_hash = "sha256:template-v2"
    stored_template.status = "published"
    await test_db.commit()

    refreshed = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
    ).scalar_one()

    assert refreshed.curriculum_snapshot == original_snapshot
    assert refreshed.curriculum_snapshot["practice_template"] == original_snapshot[
        "practice_template"
    ]


@pytest.mark.asyncio
async def test_should_freeze_examiner_agent_ref_in_session_snapshot(
    test_db: AsyncSession,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    category = QuestionCategory(category_id="exam-category", name="考试题", order_index=1)
    question = QuestionItem(
        question_id="exam-question",
        category_id="exam-category",
        title="确认预算",
        stem="如何确认客户预算？",
        reference_answer="询问预算区间和审批流程。",
        scoring_criteria={"dimensions": [{"id": "discovery"}]},
        scoring_dimensions=["discovery"],
        status="published",
        safety_flagged=False,
        content_hash="sha256:exam-question",
    )
    examiner_agent = ExaminerAgent(
        examiner_agent_id="examiner-snapshot",
        name="快照考试官",
        question_source_ids=["exam-question"],
        learner_level_strategy={
            "default_level": "beginner",
            "allowed_levels": ["beginner", "intermediate"],
        },
        scoring_policy_id=ruleset.ruleset_id,
        timeout_config={"max_seconds": 600},
        safety_config={"reject_safety_flagged": True},
        prompt_config={"system_prompt": "按题库提问。"},
        simulation_config={},
        status="published",
        version=1,
    )
    examiner_agent.content_hash = examiner_agent_content_hash(examiner_agent)
    examiner_agent_v1_hash = examiner_agent.content_hash
    test_db.add_all([category, question, examiner_agent])
    await test_db.commit()
    template = await _create_published_template(
        test_db,
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
    )
    template.status = "draft"
    template.examiner_agent_id = "examiner-snapshot"
    await test_db.commit()
    published, decision = await PracticeTemplateService(test_db).publish_template(
        template,
        actor_id=None,
    )
    assert decision.can_publish is True
    assert published is not None
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="examiner_snapshot_user",
        name="Examiner Snapshot User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="examiner_snapshot_sales",
        is_active=True,
    )
    session = PracticeSession(
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        agent_id=agent.id,
        persona_id=persona.id,
        voice_mode="stepfun_realtime",
        status="preparing",
    )
    test_db.add_all([user, scenario, session])
    await test_db.flush()

    await apply_curriculum_snapshot_to_session(
        db=test_db,
        session=session,
        practice_template_id=UUID(str(template.template_id)),
        scenario_type_value="sales",
        actor_id=str(user.user_id),
    )
    await test_db.commit()
    original_snapshot = deepcopy(session.curriculum_snapshot)
    examiner_ref = next(
        item
        for item in original_snapshot["content_assets"]
        if item["asset_type"] == "examiner_agent"
    )
    question_ref = next(
        item
        for item in original_snapshot["content_assets"]
        if item["asset_type"] == "question_item"
    )

    stored_examiner = await test_db.get(ExaminerAgent, "examiner-snapshot")
    assert stored_examiner is not None
    stored_examiner.version = 2
    stored_examiner.prompt_config = {"system_prompt": "发布后的新提示词。"}
    stored_examiner.content_hash = "sha256:examiner-v2"
    await test_db.commit()

    refreshed = await test_db.get(PracticeSession, session.session_id)
    assert refreshed is not None
    assert refreshed.curriculum_snapshot == original_snapshot
    assert examiner_ref == {
        "asset_type": "examiner_agent",
        "asset_id": "examiner-snapshot",
        "version": 1,
        "hash": examiner_agent_v1_hash,
        "snapshot_label": "published",
    }
    assert question_ref == {
        "asset_type": "question_item",
        "asset_id": "exam-question",
        "version": 1,
        "hash": "sha256:exam-question",
        "snapshot_label": "published",
    }
