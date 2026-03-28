from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import Base, PracticeSession, Scenario, SessionStatus, User
from common.db.session import get_db
from common.error_handling.result import Result
from common.websocket.session_manager import get_session_manager
from evaluation.services.report_generation_trigger import ReportGenerationTrigger
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _make_effectiveness_snapshot(*, evaluable: bool, reason: str | None) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "value_expression_score": 78.0,
            "customer_benefit_score": 72.0,
            "evidence_usage_score": 54.0,
            "objection_handling_score": 76.0,
            "next_step_score": 68.0,
            "value_articulation_rollup": 75.6,
            "evidence_benefit_rollup": 62.1,
            "objection_progress_rollup": 72.8,
        },
        "main_issue": {
            "issue_type": "evidence_gap",
            "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
            "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
        },
        "next_goal": {
            "goal_type": "evidence_backing",
            "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
            "rule": "至少补上一条证据和一个明确的下一步动作。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
    }


def _make_stale_sales_snapshot() -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "value_expression_score": 82.0,
            "customer_benefit_score": 78.0,
            "evidence_usage_score": 61.0,
            "objection_handling_score": 74.0,
            "next_step_score": 69.0,
            "value_articulation_rollup": 80.0,
            "evidence_benefit_rollup": 69.5,
            "objection_progress_rollup": 71.5,
        },
        "main_issue": {
            "issue_type": "value_translation_gap",
            "issue_text": "产品价值说得太功能化，还没有翻译成客户收益与 ROI。",
            "recovery_rule": "下一轮先把价值翻译成客户收益，再回应价格与竞品问题。",
        },
        "next_goal": {
            "goal_type": "value_to_benefit_translation",
            "goal_text": "先把产品价值翻译成客户收益，再进入方案说明。",
            "rule": "至少说清一个客户场景、一个收益指标、一个量化变化。",
        },
        "version": "rule_v1",
        "evaluable": True,
        "not_evaluable_reason": None,
    }


def _expected_retry_focus_intent(
    *,
    session_id: str,
    main_issue: dict[str, object],
    next_goal: dict[str, object],
) -> dict[str, object]:
    return {
        "version": "retry_focus_v1",
        "source_session_id": session_id,
        "main_issue": main_issue,
        "next_goal": next_goal,
    }


def _without_replay_anchor(value: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if key != "replay_anchor"}


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def owner(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"contract-owner-{uuid.uuid4().hex[:8]}",
        name="Contract Owner",
        email=f"contract_owner_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def outsider(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"contract-outsider-{uuid.uuid4().hex[:8]}",
        name="Contract Outsider",
        email=f"contract_outsider_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_headers(owner: User):
    token = create_access_token(data={"sub": str(owner.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def outsider_headers(outsider: User):
    token = create_access_token(data={"sub": str(outsider.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_report_and_replay_contract_share_same_session_evidence_fields(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract evidence scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=75.6,
        accuracy_score=62.1,
        completeness_score=72.8,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=False,
            reason="INSUFFICIENT_TURN_DATA",
        ),
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="我先介绍一下我们现在的跟进流程。",
                timestamp=datetime.now(UTC),
                duration_ms=1200,
                sales_stage="opening",
                score_snapshot={"overall": 76},
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="assistant",
                content="目前主要痛点是线索流失。",
                timestamp=datetime.now(UTC),
                duration_ms=1800,
                sales_stage="discovery",
                score_snapshot={"overall_score": 84},
            ),
        ]
    )
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    assert report_data["overall_score"] == replay_data["overall_score"] == pytest.approx(70.2, abs=0.05)
    assert report_data["logic_score"] == pytest.approx(75.6)
    assert report_data["accuracy_score"] == pytest.approx(62.1)
    assert report_data["completeness_score"] == pytest.approx(72.8)
    assert _without_replay_anchor(report_data["main_issue"]) == _without_replay_anchor(
        replay_data["main_issue"]
    )
    assert _without_replay_anchor(report_data["next_goal"]) == _without_replay_anchor(
        replay_data["next_goal"]
    )
    assert report_data["main_issue"]["issue_type"] == "evidence_gap"
    assert report_data["next_goal"]["goal_type"] == "evidence_backing"
    assert report_data["not_evaluable_reason"] == replay_data["not_evaluable_reason"] == "INSUFFICIENT_TURN_DATA"
    assert report_data["evaluable"] is False
    assert replay_data["evaluable"] is False
    assert report_data["stage_summary"] == replay_data["stage_summary"] == [
        {"stage": "opening", "duration_ms": 1200, "score": 76},
        {"stage": "discovery", "duration_ms": 1800, "score": 84},
    ]
    assert report_data["evidence_completeness"]["legacy_score_key_used"] is True
    assert replay_data["evidence_completeness"]["legacy_score_key_used"] is True


@pytest.mark.asyncio
async def test_report_contract_carries_structured_retry_focus_intent_from_issue_and_goal(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    snapshot = _make_effectiveness_snapshot(
        evaluable=True,
        reason=None,
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract retry focus scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=75.6,
        accuracy_score=62.1,
        completeness_score=72.8,
        total_duration_seconds=180,
        effectiveness_snapshot=snapshot,
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    report_data = report_resp.json()["data"]

    assert report_data["retry_entry"] == {
        "scenario_type": "sales",
        "agent_id": None,
        "persona_id": None,
        "presentation_id": None,
        "focus_intent": _expected_retry_focus_intent(
            session_id=session.session_id,
            main_issue=snapshot["main_issue"],
            next_goal=snapshot["next_goal"],
        ),
    }


@pytest.mark.asyncio
async def test_report_and_replay_contract_override_stale_sales_snapshot_with_aligned_fields(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract stale alignment scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="ROI 这一块你们有真实案例吗？",
                timestamp=datetime.now(UTC),
                duration_ms=1600,
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 82.0,
                    "dimension_scores": {
                        "价值表达": 84.0,
                        "客户收益连接": 80.0,
                        "证据使用": 58.0,
                        "异议处理": 76.0,
                        "推进下一步": 72.0,
                    },
                },
            )
        ]
    )
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    assert _without_replay_anchor(report_data["main_issue"]) == _without_replay_anchor(
        replay_data["main_issue"]
    ) == {
        "issue_type": "evidence_gap",
        "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
        "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
    }
    assert _without_replay_anchor(report_data["next_goal"]) == _without_replay_anchor(
        replay_data["next_goal"]
    ) == {
        "goal_type": "evidence_backing",
        "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
        "rule": "至少补上一条证据和一个明确的下一步动作。",
    }
    assert report_data["effectiveness_snapshot"]["claim_truth"] == replay_data["effectiveness_snapshot"][
        "claim_truth"
    ] == {
        "status": "weak_evidence",
        "label": "证据偏弱",
        "source": "score_snapshot",
        "reason": "low_evidence_score",
        "evidence_score": 58.0,
    }


@pytest.mark.asyncio
async def test_report_and_replay_contract_surface_verified_claim_truth_for_strong_roi_evidence(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract verified evidence scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
    )
    db_session.add_all([scenario, session])
    db_session.add(
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="我们有3个同类客户在6个月内回本，迁移期间SLA保持99.9%。",
            timestamp=datetime.now(UTC),
            duration_ms=1600,
            sales_stage="objection",
            score_snapshot={
                "overall_score": 88.0,
                "dimension_scores": {
                    "价值表达": 86.0,
                    "客户收益连接": 84.0,
                    "证据使用": 89.0,
                    "异议处理": 81.0,
                    "推进下一步": 79.0,
                },
            },
        )
    )
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    assert report_data["effectiveness_snapshot"]["claim_truth"] == replay_data["effectiveness_snapshot"][
        "claim_truth"
    ] == {
        "status": "evidence_verified",
        "label": "证据已验证",
        "source": "score_snapshot",
        "reason": "strong_evidence_score",
        "evidence_score": 89.0,
    }


@pytest.mark.asyncio
async def test_knowledge_check_keeps_claim_truth_distinct_from_kb_lock_chain_failures(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract runtime truth scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
        voice_policy_snapshot={
            "knowledge_base_ids": ["kb-truth-1"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": True,
            },
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 0,
                    "total_results": 0,
                    "last_status": "search_failed",
                    "last_error": "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout",
                    "kb_lock_required": True,
                    "kb_lock_last_status": "blocked_search_failed",
                    "kb_lock_block_count": 1,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "kb_lock_updated_at": datetime.now(UTC).isoformat(),
                }
            },
        },
    )
    db_session.add_all([scenario, session])
    db_session.add(
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="ROI 这一块你们有真实案例吗？",
            timestamp=datetime.now(UTC),
            duration_ms=1600,
            sales_stage="discovery",
            score_snapshot={
                "overall_score": 82.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 80.0,
                    "证据使用": 58.0,
                    "异议处理": 76.0,
                    "推进下一步": 72.0,
                },
            },
        )
    )
    await db_session.commit()

    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
        headers=owner_headers,
    )

    assert knowledge_check_resp.status_code == 200
    knowledge_check_data = knowledge_check_resp.json()["data"]
    assert knowledge_check_data["kb_lock_status"] == "blocked_search_failed"
    assert knowledge_check_data["kb_lock_chain_failure"] is True
    assert knowledge_check_data["claim_truth"] == {
        "status": "weak_evidence",
        "label": "证据偏弱",
        "source": "score_snapshot",
        "reason": "low_evidence_score",
        "evidence_score": 58.0,
    }
    assert knowledge_check_data["claim_truth_status"] == "weak_evidence"
    assert knowledge_check_data["claim_truth_source"] == "score_snapshot"


@pytest.mark.asyncio
async def test_knowledge_check_prefers_live_session_summary_over_stale_completed_snapshot_when_handler_active(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract live summary scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.IN_PROGRESS.value,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
        voice_policy_snapshot={
            "knowledge_base_ids": ["kb-live-1"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": False,
            },
        },
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    live_handler = SimpleNamespace(
        get_runtime_diagnostics=lambda: {
            "live_session_summary": {
                "alignment_used": True,
                "stage_key": "objection",
                "focus_type": "objection_handling_gap",
                "fallback_reason": None,
                "main_issue": {
                    "issue_type": "objection_handling_gap",
                    "issue_text": "面对价格、竞品或风险顾虑时，承接和重构回应还不够到位。",
                    "recovery_rule": "下一轮先复述顾虑，再用收益、证据和试点方案回应。",
                },
                "next_goal": {
                    "goal_type": "objection_reframe",
                    "goal_text": "下一轮先承接价格/竞品/风险顾虑，再用收益和证据回应。",
                    "rule": "先复述顾虑，再给回应，最后落到低风险推进方案。",
                },
                "claim_truth": {
                    "status": "unsupported_claim",
                    "label": "未被证据支撑",
                    "source": "objection_ledger",
                    "reason": "gap_acknowledged",
                    "closure_state": "gap_acknowledged",
                },
            },
            "claim_truth": {
                "status": "unsupported_claim",
                "label": "未被证据支撑",
                "source": "objection_ledger",
                "reason": "gap_acknowledged",
                "closure_state": "gap_acknowledged",
            },
            "coach_health": {
                "status": "healthy",
                "reason": None,
                "message": "实时辅导正常。",
            },
        },
        _latest_live_session_summary=None,
        _latest_claim_truth=None,
    )
    session_manager = get_session_manager()
    await session_manager.register_session(session.session_id, live_handler)
    try:
        knowledge_check_resp = await async_client.get(
            f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
            headers=owner_headers,
        )

        assert knowledge_check_resp.status_code == 200
        knowledge_check_data = knowledge_check_resp.json()["data"]
        assert knowledge_check_data["main_issue"] == {
            "issue_type": "objection_handling_gap",
            "issue_text": "面对价格、竞品或风险顾虑时，承接和重构回应还不够到位。",
            "recovery_rule": "下一轮先复述顾虑，再用收益、证据和试点方案回应。",
        }
        assert knowledge_check_data["next_goal"] == {
            "goal_type": "objection_reframe",
            "goal_text": "下一轮先承接价格/竞品/风险顾虑，再用收益和证据回应。",
            "rule": "先复述顾虑，再给回应，最后落到低风险推进方案。",
        }
        assert knowledge_check_data["claim_truth"] == {
            "status": "unsupported_claim",
            "label": "未被证据支撑",
            "source": "objection_ledger",
            "reason": "gap_acknowledged",
            "closure_state": "gap_acknowledged",
        }
        assert knowledge_check_data["live_session_summary"]["focus_type"] == "objection_handling_gap"
    finally:
        await session_manager.unregister_session(session.session_id, reason="test_cleanup")


@pytest.mark.asyncio
async def test_knowledge_check_does_not_revive_stale_snapshot_when_live_summary_is_partial(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract partial live summary scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.IN_PROGRESS.value,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
        voice_policy_snapshot={
            "knowledge_base_ids": ["kb-live-2"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": False,
            },
        },
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    live_handler = SimpleNamespace(
        get_runtime_diagnostics=lambda: {
            "live_session_summary": {
                "main_issue": {"issue_type": ""},
                "claim_truth": {"status": "", "source": "score_snapshot"},
            },
            "claim_truth": None,
            "coach_health": {
                "status": "healthy",
                "reason": None,
                "message": "实时辅导正常。",
            },
        },
        _latest_live_session_summary=None,
        _latest_claim_truth=None,
    )
    session_manager = get_session_manager()
    await session_manager.register_session(session.session_id, live_handler)
    try:
        knowledge_check_resp = await async_client.get(
            f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
            headers=owner_headers,
        )

        assert knowledge_check_resp.status_code == 200
        knowledge_check_data = knowledge_check_resp.json()["data"]
        assert knowledge_check_data["main_issue"] is None
        assert knowledge_check_data["next_goal"] is None
        assert knowledge_check_data["claim_truth"] is None
        assert knowledge_check_data["live_session_summary"] is None
    finally:
        await session_manager.unregister_session(session.session_id, reason="test_cleanup")


@pytest.mark.asyncio
async def test_sales_background_finalization_unlocks_same_session_replay_and_highlights(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    stale_snapshot = _make_stale_sales_snapshot()
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract finalized sales scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.SCORING.value,
        report_status="processing",
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=stale_snapshot,
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="assistant",
                content="您现在最想先看哪类 ROI 证明？",
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                sales_stage="discovery",
                score_snapshot={"overall_score": 82},
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="user",
                content="我们有 3 个同行案例在 6 个月内回本，迁移期 SLA 保持 99.9%。",
                timestamp=datetime.now(UTC),
                duration_ms=2100,
                sales_stage="objection",
                score_snapshot={
                    "overall_score": 88,
                    "dimension_scores": {
                        "价值表达": 86.0,
                        "客户收益连接": 84.0,
                        "证据使用": 89.0,
                        "异议处理": 81.0,
                        "推进下一步": 79.0,
                    },
                },
                is_highlight=True,
                highlight_type="good",
                highlight_reason="补上了 ROI 证据。",
            ),
        ]
    )
    await db_session.commit()

    scoring_report = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_before = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )
    highlights_before = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/highlights",
        headers=owner_headers,
    )
    assert scoring_report.status_code == 200
    assert scoring_report.json()["data"]["main_issue"] == stale_snapshot["main_issue"]
    assert scoring_report.json()["data"]["next_goal"] == stale_snapshot["next_goal"]
    assert replay_before.status_code == 400
    assert replay_before.json()["error"] == "[SESSION_NOT_COMPLETED]"
    assert highlights_before.status_code == 400
    assert highlights_before.json()["error"] == "[SESSION_NOT_COMPLETED]"

    mock_report_service = AsyncMock()
    mock_report_service.generate_report = AsyncMock(
        return_value=Result.fail("[ENHANCED_REPORT_FAILED]")
    )
    await ReportGenerationTrigger(db_session, mock_report_service).trigger_on_session_end(
        str(session.session_id),
        "sales",
    )
    await db_session.commit()
    await db_session.refresh(session)

    assert session.report_status == "failed"
    assert session.status == SessionStatus.COMPLETED.value

    report_after = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_after = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )
    highlights_after = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/highlights",
        headers=owner_headers,
    )

    assert report_after.status_code == 200
    assert replay_after.status_code == 200
    assert replay_after.json()["success"] is True
    assert highlights_after.status_code == 200
    assert highlights_after.json()["success"] is True

    report_after_data = report_after.json()["data"]
    replay_after_data = replay_after.json()["data"]
    highlight_after_data = highlights_after.json()["data"]["highlights"][0]

    assert report_after_data["effectiveness_snapshot"]["claim_truth"] == replay_after_data[
        "effectiveness_snapshot"
    ]["claim_truth"] == {
        "status": "evidence_verified",
        "label": "证据已验证",
        "source": "score_snapshot",
        "reason": "strong_evidence_score",
        "evidence_score": 89.0,
    }
    assert _without_replay_anchor(report_after_data["main_issue"]) == _without_replay_anchor(
        replay_after_data["main_issue"]
    )
    assert _without_replay_anchor(report_after_data["next_goal"]) == _without_replay_anchor(
        replay_after_data["next_goal"]
    )
    assert report_after_data["main_issue"] != scoring_report.json()["data"]["main_issue"]
    assert report_after_data["next_goal"] != scoring_report.json()["data"]["next_goal"]
    assert report_after_data["main_issue"]["issue_type"] == highlight_after_data["learning_evidence"]["issue_family"]
    assert replay_after_data["main_issue"]["replay_anchor"]["status"] == "resolved"
    assert replay_after_data["next_goal"]["replay_anchor"]["status"] == "resolved"


@pytest.mark.asyncio
async def test_replay_completion_gate_and_report_access_control_remain_unchanged(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
    outsider_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract gate scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.IN_PROGRESS.value,
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    owner_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    owner_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )
    outsider_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=outsider_headers,
    )
    outsider_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=outsider_headers,
    )

    assert owner_report_resp.status_code == 200
    assert owner_replay_resp.status_code == 400
    assert owner_replay_resp.json()["error"] == "[SESSION_NOT_COMPLETED]"
    assert outsider_report_resp.status_code == 403
    assert outsider_report_resp.json()["error"] == "[ACCESS_DENIED]"
    assert outsider_replay_resp.status_code == 403
    assert outsider_replay_resp.json()["error"] == "[ACCESS_DENIED]"


@pytest.mark.asyncio
async def test_same_session_report_stays_available_during_scoring_and_replay_matches_after_unlock(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract scoring parity scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.SCORING.value,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
    )
    db_session.add_all([scenario, session])
    db_session.add(
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="ROI 这一块你们有真实案例吗？",
            timestamp=datetime.now(UTC),
            duration_ms=1600,
            sales_stage="objection",
            score_snapshot={
                "overall_score": 88.0,
                "dimension_scores": {
                    "价值表达": 86.0,
                    "客户收益连接": 84.0,
                    "证据使用": 89.0,
                    "异议处理": 81.0,
                    "推进下一步": 79.0,
                },
            },
            is_highlight=True,
            highlight_type="good",
            highlight_reason="补上了 ROI 证据。",
        )
    )
    await db_session.commit()

    scoring_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    scoring_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert scoring_report_resp.status_code == 200
    assert scoring_replay_resp.status_code == 400
    assert scoring_replay_resp.json()["error"] == "[SESSION_NOT_COMPLETED]"

    session.status = SessionStatus.COMPLETED.value
    await db_session.commit()
    await db_session.refresh(session)

    completed_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    completed_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert completed_report_resp.status_code == 200
    assert completed_replay_resp.status_code == 200

    scoring_report_data = scoring_report_resp.json()["data"]
    completed_report_data = completed_report_resp.json()["data"]
    completed_replay_data = completed_replay_resp.json()["data"]

    assert scoring_report_data["main_issue"] == _make_stale_sales_snapshot()["main_issue"]
    assert scoring_report_data["next_goal"] == _make_stale_sales_snapshot()["next_goal"]
    assert completed_report_data["effectiveness_snapshot"]["claim_truth"] == completed_replay_data[
        "effectiveness_snapshot"
    ]["claim_truth"] == {
        "status": "evidence_verified",
        "label": "证据已验证",
        "source": "score_snapshot",
        "reason": "strong_evidence_score",
        "evidence_score": 89.0,
    }
    assert _without_replay_anchor(completed_report_data["main_issue"]) == _without_replay_anchor(
        completed_replay_data["main_issue"]
    )
    assert _without_replay_anchor(completed_report_data["next_goal"]) == _without_replay_anchor(
        completed_replay_data["next_goal"]
    )
    assert completed_report_data["main_issue"]["issue_type"] != scoring_report_data["main_issue"][
        "issue_type"
    ]
    assert completed_report_data["next_goal"]["goal_type"] != scoring_report_data["next_goal"][
        "goal_type"
    ]
    assert completed_replay_data["main_issue"]["replay_anchor"]["status"] == "resolved"
    assert completed_replay_data["next_goal"]["replay_anchor"]["status"] == "resolved"
