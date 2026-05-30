"""Unit tests for runtime preflight evaluation."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from common.services.runtime_preflight_service import RuntimePreflightService
from curriculum_practice.models import ExaminerAgent, QuestionItem
from curriculum_practice.services.roleplay_contracts import RoleplayContractCompiler


@pytest.mark.asyncio
async def test_sales_preflight_rejects_kb_lock_unbound(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="销售",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        agent_id="agent-1",
        persona_id="persona-1",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={
            "tool_policy": {"require_kb_grounding": True},
            "knowledge_base_ids": [],
        },
    )
    test_db.add(session)
    await test_db.commit()

    result = await RuntimePreflightService(test_db).evaluate_session(
        str(session.session_id)
    )

    assert result is not None
    assert result.runnable is False
    assert result.runtime_type == "sales"
    assert result.code == "KB_LOCK_UNBOUND"
    assert "persona.knowledge_base_ids" in result.missing


@pytest.mark.asyncio
async def test_sales_preflight_rejects_missing_agent_persona(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="销售",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        voice_mode="stepfun_realtime",
    )
    test_db.add(session)
    await test_db.commit()

    result = await RuntimePreflightService(test_db).evaluate_session(
        str(session.session_id)
    )

    assert result is not None
    assert result.runnable is False
    assert result.code == "AGENT_PERSONA_REQUIRED"


@pytest.mark.asyncio
async def test_sales_preflight_rejects_missing_voice_policy_snapshot(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="销售",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()
    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        agent_id="agent-1",
        persona_id="persona-1",
        voice_mode="stepfun_realtime",
    )
    test_db.add(session)
    await test_db.commit()

    result = await RuntimePreflightService(test_db).evaluate_session(
        str(session.session_id)
    )

    assert result is not None
    assert result.runnable is False
    assert result.code == "VOICE_POLICY_SNAPSHOT_MISSING"
    assert result.missing == ["voice_policy_snapshot"]


@pytest.mark.asyncio
async def test_sales_preflight_rejects_curriculum_runtime_identity_mismatch(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="销售",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()
    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        agent_id="agent-session",
        persona_id="persona-1",
        voice_runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={"instruction_contract_hash": "voice-hash"},
        curriculum_snapshot={
            "snapshot_hash": "snapshot-hash",
            "runtime": {
                "agent_id": "agent-snapshot",
                "persona_id": "persona-1",
                "runtime_profile_id": "runtime-1",
                "instruction_contract_hash": "curriculum-hash",
            },
        },
    )
    test_db.add(session)
    await test_db.commit()

    result = await RuntimePreflightService(test_db).evaluate_session(
        str(session.session_id)
    )

    assert result is not None
    assert result.runnable is False
    assert result.code == "CURRICULUM_RUNTIME_IDENTITY_MISMATCH"
    assert result.snapshot_hash == "snapshot-hash"
    assert result.instruction_contract_hash == "curriculum-hash"
    assert result.runtime_identity == {
        "agent_id": "agent-snapshot",
        "persona_id": "persona-1",
        "runtime_profile_id": "runtime-1",
    }


@pytest.mark.asyncio
async def test_sales_preflight_reports_roleplay_contract_readiness(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="销售",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()
    contract = RoleplayContractCompiler().compile_from_persona_sync(
        {
            "id": "persona-1",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": "first_visit",
                    "relationship_context": {
                        "prior_interactions": "none",
                        "has_prior_meeting": False,
                    },
                }
            },
        },
        actor_id="actor-1",
    )
    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        agent_id="agent-1",
        persona_id="persona-1",
        voice_runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={
            "instruction_contract_hash": "voice-hash",
            "roleplay_contract": contract,
        },
    )
    test_db.add(session)
    await test_db.commit()

    result = await RuntimePreflightService(test_db).evaluate_session(
        str(session.session_id)
    )

    assert result is not None
    assert result.runnable is True
    assert result.roleplay_contract == {
        "status": "ready",
        "schema_version": "roleplay_contract_v1",
        "contract_hash": contract["audit"]["contract_hash"],
        "situation_code": "first_visit",
        "blocking_issues": [],
    }


@pytest.mark.asyncio
async def test_examiner_preflight_accepts_valid_snapshot(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="考核",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    agent = ExaminerAgent(
        name="考官",
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
    test_db.add_all([agent, question])
    await test_db.flush()
    agent.question_source_ids = [str(question.question_id)]

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        curriculum_snapshot={
            "kind": "curriculum_examiner_session",
            "learning_content_id": "content-1",
            "content_assets": [
                {
                    "asset_type": "examiner_agent",
                    "asset_id": str(agent.examiner_agent_id),
                    "version": 1,
                    "hash": "agent-hash",
                    "snapshot_label": "考官",
                },
                {
                    "asset_type": "question_item",
                    "asset_id": str(question.question_id),
                    "version": 1,
                    "hash": "question-hash",
                    "snapshot_label": "题 1",
                },
            ],
        },
    )
    test_db.add(session)
    await test_db.commit()

    result = await RuntimePreflightService(test_db).evaluate_session(
        str(session.session_id)
    )

    assert result is not None
    assert result.runnable is True
    assert result.runtime_type == "examiner"


@pytest.mark.asyncio
async def test_examiner_preflight_rejects_missing_questions(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="考核",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    agent = ExaminerAgent(
        name="考官",
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
    test_db.add(agent)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        curriculum_snapshot={
            "kind": "curriculum_examiner_session",
            "content_assets": [
                {
                    "asset_type": "examiner_agent",
                    "asset_id": str(agent.examiner_agent_id),
                    "version": 1,
                    "hash": "agent-hash",
                    "snapshot_label": "考官",
                }
            ],
        },
    )
    test_db.add(session)
    await test_db.commit()

    result = await RuntimePreflightService(test_db).evaluate_session(
        str(session.session_id)
    )

    assert result is not None
    assert result.runnable is False
    assert result.code == "EXAMINER_RUNTIME_CONFIG_MISSING"
