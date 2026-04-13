from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import Base, PracticeSession, Scenario, SessionAudioSegment, SessionStatus, User
from common.db.session import get_db
from common.error_handling.result import Result
from common.websocket.session_manager import get_session_manager
from evaluation.services.report_generation_trigger import ReportGenerationTrigger
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def test_practice_application_service_inventory_exposes_named_route_clusters() -> None:
    from common.services.practice_service import (
        PRACTICE_APPLICATION_SEAMS,
        PracticeAudioAuditService,
        PracticeRouteServices,
        PracticeRuntimeDescriptorService,
    )

    assert PRACTICE_APPLICATION_SEAMS == (
        "session_create_policy",
        "session_lifecycle",
        "session_report_read_model",
        "audio_audit_and_signing",
        "runtime_descriptor",
    )
    assert PracticeRouteServices.__dataclass_fields__["seam_names"].default == PRACTICE_APPLICATION_SEAMS
    assert PracticeAudioAuditService.__name__ == "PracticeAudioAuditService"
    assert PracticeRuntimeDescriptorService.__name__ == "PracticeRuntimeDescriptorService"


@pytest.mark.asyncio
async def test_practice_application_service_bundle_wires_existing_dependencies(
    db_session: AsyncSession,
) -> None:
    from common.conversation.session_evidence import SessionEvidenceService
    from common.db.session_lifecycle import SessionLifecycleService
    from common.services.practice_service import build_practice_route_services
    from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

    services = build_practice_route_services(db_session)

    assert services.seam_names[0] == "session_create_policy"
    assert isinstance(services.runtime_policy, VoiceRuntimePolicyService)
    assert isinstance(services.lifecycle, SessionLifecycleService)
    assert isinstance(services.evidence, SessionEvidenceService)
    assert services.audio_audit.__class__.__name__ == "PracticeAudioAuditService"
    assert services.runtime_descriptor.__class__.__name__ == "PracticeRuntimeDescriptorService"
    assert callable(services.get_oss_signing_service)


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


def _snapshot_ref(snapshot: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(snapshot, dict):
        return None

    source = snapshot.get("source")
    tool_policy = snapshot.get("tool_policy")
    ref: dict[str, object] = {
        "voice_mode": snapshot.get("voice_mode"),
        "runtime_profile_id": snapshot.get("runtime_profile_id"),
        "instruction_contract_hash": snapshot.get("instruction_contract_hash"),
        "network_access_mode": snapshot.get("network_access_mode"),
        "resolved_at": snapshot.get("resolved_at"),
        "tool_policy": tool_policy if isinstance(tool_policy, dict) else {},
        "knowledge_base_ids": [
            str(item)
            for item in (snapshot.get("knowledge_base_ids") or [])
            if item is not None
        ],
        "source": {str(k): str(v) for k, v in source.items()}
        if isinstance(source, dict)
        else {},
    }
    association_override = snapshot.get("agent_persona_override_config")
    if isinstance(association_override, dict):
        ref["agent_persona_override_config"] = association_override
    return ref


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
    assert report_data["conclusion_evidence"] == replay_data["conclusion_evidence"] == {
        "main_issue": {
            "retrieval_source": {"available": False, "reason": "no_voice_policy_snapshot"},
            "transcript_source": {"available": True, "turn_count": 1},
            "audio_source": {"available": True, "reason": None},
        },
        "next_goal": {
            "retrieval_source": {"available": False, "reason": "no_voice_policy_snapshot"},
            "transcript_source": {"available": True, "turn_count": 1},
            "audio_source": {"available": True, "reason": None},
        },
        "claim_truth": {
            "retrieval_source": {"available": False, "reason": "no_voice_policy_snapshot"},
            "transcript_source": {"available": True, "turn_count": 1},
            "audio_source": {"available": True, "reason": None},
        },
    }


@pytest.mark.asyncio
async def test_current_session_route_family_keeps_voice_policy_snapshot_ref_frozen_while_runtime_metrics_expose_retrieval_ledger(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract snapshot ref scenario",
        is_active=True,
    )
    baseline_snapshot = {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "runtime-profile-1",
        "instruction_contract_hash": "contract-hash-1",
        "network_access_mode": "off",
        "resolved_at": datetime.now(UTC).isoformat(),
        "knowledge_base_ids": ["kb-route-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": False,
        },
        "source": {
            "voice_mode": "runtime_profile",
            "knowledge_base_ids": "persona",
        },
    }
    baseline_ref = _snapshot_ref(baseline_snapshot)
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_mode="stepfun_realtime",
        logic_score=75.6,
        accuracy_score=62.1,
        completeness_score=72.8,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=False,
            reason="INSUFFICIENT_TURN_DATA",
        ),
        voice_policy_snapshot={
            **baseline_snapshot,
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 0,
                    "total_results": 0,
                    "recent_attempts": [
                        {
                            "attempted_at": "2026-03-28T12:00:00Z",
                            "query": "ROI 案例",
                            "status": "search_failed",
                            "result_count": 0,
                            "retrieval_mode": "hybrid",
                            "knowledge_base_ids": ["kb-route-1"],
                            "error_summary": "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout",
                            "result_summaries": [],
                        }
                    ],
                }
            },
        },
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="我想确认 ROI 案例。",
                timestamp=datetime.now(UTC),
                duration_ms=1200,
                sales_stage="opening",
                score_snapshot={"overall": 76},
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="assistant",
                content="我们后续补充案例。",
                timestamp=datetime.now(UTC),
                duration_ms=1800,
                sales_stage="discovery",
                score_snapshot={"overall_score": 84},
            ),
        ]
    )
    await db_session.commit()

    detail_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}",
        headers=owner_headers,
    )
    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert detail_resp.status_code == 200
    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    detail_data = detail_resp.json()["data"]
    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    detail_ref = {
        key: value
        for key, value in detail_data["voice_policy_snapshot_ref"].items()
        if not (key == "agent_persona_override_config" and value is None)
    }
    report_ref = {
        key: value
        for key, value in report_data["voice_policy_snapshot_ref"].items()
        if not (key == "agent_persona_override_config" and value is None)
    }
    replay_ref = {
        key: value
        for key, value in replay_data["voice_policy_snapshot_ref"].items()
        if not (key == "agent_persona_override_config" and value is None)
    }

    assert detail_ref == baseline_ref
    assert report_ref == baseline_ref
    assert replay_ref == baseline_ref
    assert (
        detail_data["voice_policy_snapshot"]["runtime_metrics"]["knowledge_retrieval"][
            "recent_attempts"
        ][0]["query"]
        == "ROI 案例"
    )


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
# ---------------------------------------------------------------------------
# S02: retrieval_facts parity contract tests
# ---------------------------------------------------------------------------


def _make_voice_policy_snapshot_with_retrieval_ledger(
    *,
    kb_ids: list[str] | None = None,
    enable_internal_retrieval: bool = True,
    attempt_count: int = 2,
    hit_query_count: int = 1,
    hit_rate: float = 0.5,
    recent_attempts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build a realistic voice_policy_snapshot with populated retrieval ledger."""
    kb_ids = kb_ids or ["kb-retrieval-1"]
    recent_attempts = recent_attempts or [
        {
            "attempted_at": "2026-03-28T11:50:00Z",
            "query": "竞品对比数据",
            "status": "miss",
            "result_count": 0,
            "retrieval_mode": "vector",
            "knowledge_base_ids": ["kb-retrieval-1"],
            "result_summaries": [],
        },
        {
            "attempted_at": "2026-03-28T12:00:00Z",
            "query": "ROI 回本案例",
            "status": "hit",
            "result_count": 2,
            "retrieval_mode": "hybrid",
            "knowledge_base_ids": ["kb-retrieval-1"],
            "result_summaries": [
                {
                    "knowledge_base_id": "kb-retrieval-1",
                    "knowledge_base_name": "产品知识库",
                    "snippet": "客户A在6个月内实现ROI回本，迁移期SLA 99.9%",
                    "score": 0.92,
                    "retrieval_mode": "vector",
                },
            ],
        },
    ]
    return {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "runtime-retrieval-test",
        "instruction_contract_hash": "retrieval-contract-hash",
        "network_access_mode": "off",
        "resolved_at": datetime.now(UTC).isoformat(),
        "knowledge_base_ids": kb_ids,
        "tool_policy": {
            "enable_internal_retrieval": enable_internal_retrieval,
            "require_kb_grounding": False,
        },
        "source": {
            "voice_mode": "runtime_profile",
            "knowledge_base_ids": "agent",
        },
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": attempt_count,
                "hit_query_count": hit_query_count,
                "hit_rate": hit_rate,
                "recent_attempts": recent_attempts,
            }
        },
    }


def _make_audio_audit_runtime_metrics(*, recording_status: str = "completed", storage_prefix: str = "sessions/audio") -> dict[str, object]:
    return {
        "runtime_metrics": {
            "audio_audit": {
                "recording_status": recording_status,
                "storage_prefix": storage_prefix,
            }
        }
    }


async def _persist_audio_segments(
    db_session: AsyncSession,
    *,
    session_id: str,
    segments: list[dict[str, object]],
) -> None:
    db_session.add_all(
        [
            SessionAudioSegment(
                session_id=session_id,
                segment_sequence=segment["segment_sequence"],
                object_key=segment.get("object_key") or f"audio/{session_id}/seg_{segment['segment_sequence']:04d}.webm",
                content_type=segment.get("content_type") or "audio/webm",
                size_bytes=segment.get("size_bytes"),
                duration_ms=segment.get("duration_ms"),
                upload_status=segment.get("upload_status") or "pending",
                error_message=segment.get("error_message"),
                created_at=segment.get("created_at") or datetime.now(UTC),
            )
            for segment in segments
        ]
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_report_payload_includes_available_audio_audit_for_uploaded_segments(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio available report scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(
            storage_prefix="sessions/session-audio-available/audio"
        ),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "size_bytes": 20480,
                "duration_ms": 12000,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 4, 0, 0, tzinfo=UTC),
            },
            {
                "segment_sequence": 1,
                "size_bytes": 10240,
                "duration_ms": 8000,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 4, 0, 12, tzinfo=UTC),
            },
        ],
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )

    assert response.status_code == 200
    audio_audit = response.json()["data"]["audio_audit"]
    assert audio_audit["summary"] == {
        "recording_status": "completed",
        "total_segments": 2,
        "uploaded_segments": 2,
        "failed_segments": 0,
        "total_bytes": 30720,
        "latest_segment_sequence": 1,
        "storage_prefix": "sessions/session-audio-available/audio",
        "last_uploaded_at": "2026-03-28T04:00:12",
        "learner_status": "available",
        "degraded_reasons": [],
    }
    assert [segment["playback_path"] for segment in audio_audit["segments"]] == [
        f"/api/v1/sessions/{session.session_id}/audio-segments/0",
        f"/api/v1/sessions/{session.session_id}/audio-segments/1",
    ]


@pytest.mark.asyncio
async def test_report_payload_omits_audio_audit_when_session_has_no_audio_segments(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio missing report scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["audio_audit"] is None


@pytest.mark.asyncio
async def test_report_payload_marks_audio_audit_partial_when_uploads_incomplete(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio partial report scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "size_bytes": 12288,
                "duration_ms": 5000,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 4, 2, 0, tzinfo=UTC),
            },
            {
                "segment_sequence": 1,
                "size_bytes": None,
                "duration_ms": None,
                "upload_status": "pending",
                "created_at": datetime(2026, 3, 28, 4, 2, 5, tzinfo=UTC),
            },
        ],
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )

    assert response.status_code == 200
    audio_audit = response.json()["data"]["audio_audit"]
    assert audio_audit["summary"]["learner_status"] == "partial"
    assert audio_audit["summary"]["uploaded_segments"] == 1
    assert audio_audit["summary"]["total_segments"] == 2
    assert audio_audit["summary"]["total_bytes"] == 12288
    assert audio_audit["segments"][1]["playback_path"] is None


@pytest.mark.asyncio
async def test_replay_payload_includes_same_audio_audit_structure_as_report(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio replay parity scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(
            storage_prefix="sessions/session-audio-replay/audio"
        ),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "size_bytes": 20480,
                "duration_ms": 12000,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 4, 5, 0, tzinfo=UTC),
            },
            {
                "segment_sequence": 1,
                "size_bytes": 10240,
                "duration_ms": None,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 4, 5, 12, tzinfo=UTC),
            },
        ],
    )

    report_response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_response = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert report_response.status_code == 200
    assert replay_response.status_code == 200
    assert replay_response.json()["data"]["audio_audit"] == report_response.json()["data"]["audio_audit"]


@pytest.mark.asyncio
async def test_audio_segment_playback_redirects_to_signed_url_for_owner(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio playback owner scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    object_key = f"audio/{session.session_id}/seg_0000.webm"
    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "object_key": object_key,
                "size_bytes": 20480,
                "duration_ms": 12000,
                "upload_status": "uploaded",
            },
        ],
    )

    signing_service = MagicMock()
    signing_service.generate_get_url.return_value = "https://signed.example.com/audio/seg_0000.webm"

    with patch("common.oss.signing.get_oss_signing_service", return_value=signing_service):
        response = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/audio-segments/0",
            headers=owner_headers,
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == "https://signed.example.com/audio/seg_0000.webm"
    signing_service.generate_get_url.assert_called_once_with(object_key, expires=3600)


@pytest.mark.asyncio
async def test_audio_segment_playback_returns_404_for_missing_segment_sequence(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio playback missing segment scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/audio-segments/99",
        headers=owner_headers,
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert response.json()["error"] == "[SEGMENT_NOT_FOUND]"


@pytest.mark.asyncio
async def test_audio_segment_playback_denies_outsider_access(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
    outsider_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio playback ownership scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "size_bytes": 20480,
                "duration_ms": 12000,
                "upload_status": "uploaded",
            },
        ],
    )

    response = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/audio-segments/0",
        headers=outsider_headers,
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[ACCESS_DENIED]"


@pytest.mark.asyncio
async def test_signed_audio_segment_urls_are_not_persisted_in_database_state(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio signed url persistence scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    object_key = f"audio/{session.session_id}/seg_0000.webm"
    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "object_key": object_key,
                "size_bytes": 20480,
                "duration_ms": 12000,
                "upload_status": "uploaded",
            },
        ],
    )

    signing_service = MagicMock()
    signing_service.generate_get_url.return_value = "https://signed.example.com/audio/seg_0000.webm?signature=secret"

    with patch("common.oss.signing.get_oss_signing_service", return_value=signing_service):
        playback_response = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/audio-segments/0",
            headers=owner_headers,
            follow_redirects=False,
        )

    assert playback_response.status_code == 307

    report_response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    assert report_response.status_code == 200
    report_audio_audit = report_response.json()["data"]["audio_audit"]
    assert report_audio_audit["segments"][0]["playback_path"] == (
        f"/api/v1/sessions/{session.session_id}/audio-segments/0"
    )
    assert "signed.example.com" not in str(report_audio_audit)
    assert "signature=" not in str(report_audio_audit)

    persisted_segment = (
        await db_session.execute(
            select(SessionAudioSegment).where(
                SessionAudioSegment.session_id == session.session_id,
                SessionAudioSegment.segment_sequence == 0,
            )
        )
    ).scalar_one()
    assert persisted_segment.object_key == object_key
    assert "signed.example.com" not in persisted_segment.object_key


@pytest.mark.asyncio
async def test_report_and_knowledge_check_return_identical_retrieval_facts_for_completed_sales_session(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """S02 parity guarantee: retrieval_facts from report projection equals retrieval_facts from knowledge-check diagnostics."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="retrieval facts parity scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_mode="stepfun_realtime",
        logic_score=75.6,
        accuracy_score=62.1,
        completeness_score=72.8,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_effectiveness_snapshot(evaluable=True, reason=None),
        voice_policy_snapshot=_make_voice_policy_snapshot_with_retrieval_ledger(),
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="我想看看ROI案例。",
                timestamp=datetime.now(UTC),
                duration_ms=1200,
                sales_stage="discovery",
                score_snapshot={"overall": 76},
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="assistant",
                content="我们有三家客户在六个月内回本。",
                timestamp=datetime.now(UTC),
                duration_ms=1800,
                sales_stage="objection",
                score_snapshot={"overall_score": 84},
            ),
        ]
    )
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert knowledge_check_resp.status_code == 200

    report_rf = report_resp.json()["data"]["effectiveness_snapshot"]["retrieval_facts"]
    kc_rf = knowledge_check_resp.json()["data"]["retrieval_facts"]

    # Structural parity: same canonical keys
    for key in (
        "kb_bound", "knowledge_base_ids", "knowledge_base_count",
        "retrieval_enabled", "status", "summary",
        "attempt_count", "hit_count", "hit_rate",
        "latest_attempt", "recent_attempts",
    ):
        assert report_rf[key] == kc_rf[key], f"retrieval_facts.{key} mismatch: report={report_rf[key]!r} vs kc={kc_rf[key]!r}"

    assert report_rf["status"] == "hit"
    assert kc_rf["status"] == "hit"
    assert report_rf["attempt_count"] == 2
    assert kc_rf["attempt_count"] == 2
    assert report_rf["hit_count"] == 1
    assert kc_rf["hit_count"] == 1
    assert len(report_rf["recent_attempts"]) == 2
    assert len(kc_rf["recent_attempts"]) == 2

    # latest_attempt preserves knowledge_base_ids and result_summaries
    assert report_rf["latest_attempt"]["knowledge_base_ids"] == ["kb-retrieval-1"]
    assert kc_rf["latest_attempt"]["knowledge_base_ids"] == ["kb-retrieval-1"]
    assert len(report_rf["latest_attempt"]["result_summaries"]) == 1
    assert len(kc_rf["latest_attempt"]["result_summaries"]) == 1


@pytest.mark.asyncio
async def test_retrieval_facts_and_claim_truth_are_independent_retrieval_hit_with_weak_evidence(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """Claim-truth and retrieval_facts are orthogonal: retrieval can hit while claim truth stays weak_evidence."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="claim truth independence scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_mode="stepfun_realtime",
        logic_score=75.6,
        accuracy_score=62.1,
        completeness_score=72.8,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_effectiveness_snapshot(evaluable=True, reason=None),
        voice_policy_snapshot=_make_voice_policy_snapshot_with_retrieval_ledger(),
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

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert knowledge_check_resp.status_code == 200

    report_data = report_resp.json()["data"]
    kc_data = knowledge_check_resp.json()["data"]

    # retrieval_facts shows "hit"
    report_rf = report_data["effectiveness_snapshot"]["retrieval_facts"]
    kc_rf = kc_data["retrieval_facts"]
    assert report_rf["status"] == "hit"
    assert kc_rf["status"] == "hit"
    assert report_rf["latest_attempt"]["result_count"] > 0
    assert kc_rf["latest_attempt"]["result_count"] > 0

    # claim_truth shows "weak_evidence" — independent from retrieval hit
    report_ct = report_data["effectiveness_snapshot"]["claim_truth"]
    kc_ct = kc_data["claim_truth"]
    assert report_ct["status"] == "weak_evidence"
    assert kc_ct["status"] == "weak_evidence"
    assert report_ct["source"] == "score_snapshot"
    assert kc_ct["source"] == "score_snapshot"

    # Orthogonality: different statuses coexist
    assert report_rf["status"] != report_ct["status"]
    assert kc_rf["status"] != kc_ct["status"]


@pytest.mark.asyncio
async def test_retrieval_facts_parity_with_miss_status(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """Parity holds when retrieval status is miss (triggered but no hits)."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="retrieval miss parity scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_mode="stepfun_realtime",
        logic_score=70.0,
        accuracy_score=65.0,
        completeness_score=68.0,
        total_duration_seconds=150,
        effectiveness_snapshot=_make_effectiveness_snapshot(evaluable=True, reason=None),
        voice_policy_snapshot=_make_voice_policy_snapshot_with_retrieval_ledger(
            attempt_count=1,
            hit_query_count=0,
            hit_rate=0.0,
            recent_attempts=[
                {
                    "attempted_at": "2026-03-28T12:00:00Z",
                    "query": "竞品对比",
                    "status": "miss",
                    "result_count": 0,
                    "retrieval_mode": "vector",
                    "knowledge_base_ids": ["kb-retrieval-1"],
                    "result_summaries": [],
                },
            ],
        ),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert knowledge_check_resp.status_code == 200

    report_rf = report_resp.json()["data"]["effectiveness_snapshot"]["retrieval_facts"]
    kc_rf = knowledge_check_resp.json()["data"]["retrieval_facts"]

    assert report_rf["status"] == "miss"
    assert kc_rf["status"] == "miss"
    assert report_rf["miss_explanation"] is not None
    assert kc_rf["miss_explanation"] is not None
    assert report_rf == kc_rf


# ---------------------------------------------------------------------------
# Audio Audit degraded_reasons and failed_segments contract tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_audio_audit_includes_degraded_reasons_when_segments_failed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """When some segments failed and some uploaded, audio_audit.summary should have
    degraded_reasons=['upload_failed'] and learner_status='partial'."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio failed report scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "size_bytes": 8192,
                "duration_ms": 3000,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 5, 0, 0, tzinfo=UTC),
            },
            {
                "segment_sequence": 1,
                "upload_status": "failed",
                "error_message": "oss_put_failed",
                "created_at": datetime(2026, 3, 28, 5, 0, 5, tzinfo=UTC),
            },
        ],
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    assert response.status_code == 200
    audio_audit = response.json()["data"]["audio_audit"]
    assert audio_audit is not None
    assert audio_audit["summary"]["learner_status"] == "partial"
    assert audio_audit["summary"]["uploaded_segments"] == 1
    assert audio_audit["summary"]["failed_segments"] == 1
    assert audio_audit["summary"]["total_segments"] == 2
    assert "upload_failed" in audio_audit["summary"]["degraded_reasons"]
    # Failed segment should have error_message exposed
    failed_seg = audio_audit["segments"][1]
    assert failed_seg["upload_status"] == "failed"
    assert failed_seg["error_message"] == "oss_put_failed"
    assert failed_seg["playback_path"] is None


@pytest.mark.asyncio
async def test_report_audio_audit_all_failed_yields_missing_with_degraded_reasons(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """When all segments failed, learner_status should be 'missing' with
    degraded_reasons=['upload_failed']."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio all-failed report scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "upload_status": "failed",
                "error_message": "signing_failed",
                "created_at": datetime(2026, 3, 28, 5, 1, 0, tzinfo=UTC),
            },
            {
                "segment_sequence": 1,
                "upload_status": "failed",
                "error_message": "network_error",
                "created_at": datetime(2026, 3, 28, 5, 1, 5, tzinfo=UTC),
            },
        ],
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    assert response.status_code == 200
    audio_audit = response.json()["data"]["audio_audit"]
    assert audio_audit is not None
    assert audio_audit["summary"]["learner_status"] == "missing"
    assert audio_audit["summary"]["uploaded_segments"] == 0
    assert audio_audit["summary"]["failed_segments"] == 2
    assert audio_audit["summary"]["degraded_reasons"] == ["upload_failed"]


@pytest.mark.asyncio
async def test_report_audio_audit_no_degraded_reasons_when_all_uploaded(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """When all segments are uploaded, degraded_reasons should be empty."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="audio all-uploaded degraded check",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(
            storage_prefix="sessions/audio-all-uploaded"
        ),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "size_bytes": 20480,
                "duration_ms": 12000,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 5, 2, 0, tzinfo=UTC),
            },
        ],
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    assert response.status_code == 200
    audio_audit = response.json()["data"]["audio_audit"]
    assert audio_audit["summary"]["learner_status"] == "available"
    assert audio_audit["summary"]["failed_segments"] == 0
    assert audio_audit["summary"]["degraded_reasons"] == []


@pytest.mark.asyncio
async def test_replay_audio_audit_includes_degraded_reasons_for_failed_segments(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """Replay audio_audit should share the same degraded_reasons structure as report."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="replay degraded audio scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        voice_policy_snapshot=_make_audio_audit_runtime_metrics(
            storage_prefix="sessions/replay-degraded"
        ),
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    await _persist_audio_segments(
        db_session,
        session_id=session.session_id,
        segments=[
            {
                "segment_sequence": 0,
                "size_bytes": 8192,
                "upload_status": "uploaded",
                "created_at": datetime(2026, 3, 28, 5, 3, 0, tzinfo=UTC),
            },
            {
                "segment_sequence": 1,
                "upload_status": "failed",
                "error_message": "oss_put_failed",
                "created_at": datetime(2026, 3, 28, 5, 3, 5, tzinfo=UTC),
            },
            {
                "segment_sequence": 2,
                "upload_status": "pending",
                "created_at": datetime(2026, 3, 28, 5, 3, 10, tzinfo=UTC),
            },
        ],
    )

    # Fetch report
    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    assert report_resp.status_code == 200

    # Fetch replay
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )
    assert replay_resp.status_code == 200

    report_audit = report_resp.json()["data"]["audio_audit"]
    replay_audit = replay_resp.json()["data"]["audio_audit"]

    # Both should have same degraded reasons
    assert report_audit["summary"]["degraded_reasons"] == replay_audit["summary"]["degraded_reasons"]
    assert set(report_audit["summary"]["degraded_reasons"]) == {"upload_failed", "segments_pending"}
    assert report_audit["summary"]["failed_segments"] == 1
