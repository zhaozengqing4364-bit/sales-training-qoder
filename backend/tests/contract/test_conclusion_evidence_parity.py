from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import (
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
    Scenario,
    SessionAudioSegment,
    SessionStatus,
    User,
)


def _make_sales_effectiveness_snapshot() -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": True,
        },
        "main_capability_passed": True,
        "overall_result": "pass",
        "metrics": {
            "value_expression_score": 88.0,
            "customer_benefit_score": 84.0,
            "evidence_usage_score": 89.0,
            "objection_handling_score": 81.0,
            "next_step_score": 79.0,
            "value_articulation_rollup": 86.0,
            "evidence_benefit_rollup": 87.0,
            "objection_progress_rollup": 80.0,
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
        "evaluable": True,
        "not_evaluable_reason": None,
    }


def _make_voice_policy_snapshot_with_retrieval_hit() -> dict[str, object]:
    return {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "parity-runtime-profile",
        "instruction_contract_hash": "parity-contract-hash",
        "network_access_mode": "off",
        "resolved_at": datetime.now(UTC).isoformat(),
        "knowledge_base_ids": ["kb-parity-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": False,
        },
        "source": {
            "voice_mode": "runtime_profile",
            "knowledge_base_ids": "agent",
        },
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 2,
                "hit_query_count": 1,
                "total_results": 2,
                "hit_rate": 0.5,
                "recent_attempts": [
                    {
                        "attempted_at": "2026-03-28T11:50:00Z",
                        "query": "竞品对比数据",
                        "status": "miss",
                        "result_count": 0,
                        "retrieval_mode": "vector",
                        "knowledge_base_ids": ["kb-parity-1"],
                        "result_summaries": [],
                    },
                    {
                        "attempted_at": "2026-03-28T12:00:00Z",
                        "query": "ROI 回本案例",
                        "status": "hit",
                        "result_count": 2,
                        "retrieval_mode": "hybrid",
                        "knowledge_base_ids": ["kb-parity-1"],
                        "result_summaries": [
                            {
                                "knowledge_base_id": "kb-parity-1",
                                "knowledge_base_name": "产品知识库",
                                "snippet": "客户A在6个月内实现ROI回本，迁移期SLA 99.9%",
                                "score": 0.92,
                                "retrieval_mode": "vector",
                            },
                        ],
                    },
                ],
                "audio_audit": {
                    "recording_status": "completed",
                    "storage_prefix": "sessions/parity/audio",
                },
            }
        },
    }


async def _persist_audio_segments(
    db_session: AsyncSession,
    *,
    session_id: str,
    uploaded: bool = True,
) -> None:
    db_session.add_all(
        [
            SessionAudioSegment(
                session_id=session_id,
                segment_sequence=0,
                object_key=f"audio/{session_id}/seg_0000.webm",
                content_type="audio/webm",
                size_bytes=20_480 if uploaded else None,
                duration_ms=12_000 if uploaded else None,
                upload_status="uploaded" if uploaded else "pending",
                created_at=datetime(2026, 3, 28, 4, 0, 0, tzinfo=UTC),
            ),
            SessionAudioSegment(
                session_id=session_id,
                segment_sequence=1,
                object_key=f"audio/{session_id}/seg_0001.webm",
                content_type="audio/webm",
                size_bytes=10_240 if uploaded else None,
                duration_ms=8_000 if uploaded else None,
                upload_status="uploaded" if uploaded else "pending",
                created_at=datetime(2026, 3, 28, 4, 0, 12, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()


async def _seed_completed_sales_session(
    db_session: AsyncSession,
    *,
    owner: User,
    include_retrieval_hit: bool,
    include_audio_segments: bool,
    report_status: str | None = None,
    report_error: str | None = None,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="conclusion evidence parity sales",
        is_active=True,
    )
    voice_policy_snapshot = (
        _make_voice_policy_snapshot_with_retrieval_hit() if include_retrieval_hit else None
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=88.0,
        accuracy_score=84.0,
        completeness_score=80.0,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_sales_effectiveness_snapshot(),
        voice_policy_snapshot=voice_policy_snapshot,
        report_status=report_status,
        report_error=report_error,
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="我们有3个同类客户在6个月内回本，迁移期间SLA保持99.9%。",
                timestamp=datetime.now(UTC),
                duration_ms=1_500 if include_audio_segments else None,
                sales_stage="objection",
                audio_url="https://example.com/audio-1.webm" if include_audio_segments else None,
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
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="assistant",
                content="明白，我先用真实案例和回本周期回应这个ROI担忧。",
                timestamp=datetime.now(UTC),
                duration_ms=1_700 if include_audio_segments else None,
                sales_stage="objection",
                score_snapshot={"overall_score": 85.0},
            ),
        ]
    )
    await db_session.commit()

    if include_audio_segments:
        await _persist_audio_segments(db_session, session_id=session.session_id, uploaded=True)

    return session


async def _seed_completed_presentation_session(
    db_session: AsyncSession,
    *,
    owner: User,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="conclusion evidence parity presentation",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Presentation parity contract",
        file_url="file:///tmp/presentation-parity-contract.pptx",
        status="ready",
        version_number=1,
        total_pages=2,
        ocr_progress=1.0,
    )
    page_1 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=1,
        ocr_extracted_text="第一页业务目标与客户问题",
    )
    page_2 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=2,
        ocr_extracted_text="第二页ROI结果与客户案例",
    )
    talking_points = [
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_1.page_id,
            description="业务目标",
            created_by="admin",
            confirmed_by_admin=True,
        ),
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_2.page_id,
            description="ROI结果",
            created_by="admin",
            confirmed_by_admin=True,
        ),
    ]
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        presentation_id=presentation.presentation_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime.now(UTC) - timedelta(minutes=12),
        end_time=datetime.now(UTC),
        total_duration_seconds=12 * 60,
        audio_url="https://example.com/presentation.mp3",
        transcript_url="https://example.com/presentation.txt",
    )
    messages = [
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="第一页先讲业务目标和客户问题。",
            timestamp=datetime.now(UTC) - timedelta(minutes=11),
            duration_ms=95_000,
            transcript_metadata={"page_number": 1},
            score_snapshot={"overall_score": 84},
        ),
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=2,
            role="user",
            content="第二页补充 ROI 结果和同类客户案例。",
            timestamp=datetime.now(UTC) - timedelta(minutes=9),
            duration_ms=110_000,
            transcript_metadata={"page_number": 2},
            score_snapshot={"overall_score": 88},
        ),
    ]
    db_session.add_all([scenario, presentation, page_1, page_2, session, *talking_points, *messages])
    await db_session.commit()
    return session


def _extract_evidence_degradation(data: dict[str, object]) -> dict[str, object] | None:
    value = data.get("evidence_degradation")
    return value if isinstance(value, dict) else None


async def _fetch_route_family(
    async_client: AsyncClient,
    *,
    session_id: str,
    headers: dict[str, str],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/report",
        headers=headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session_id}/replay",
        headers=headers,
    )
    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        headers=headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200
    assert knowledge_check_resp.status_code == 200

    return (
        report_resp.json()["data"],
        replay_resp.json()["data"],
        knowledge_check_resp.json()["data"],
    )


@pytest.mark.asyncio
async def test_report_replay_and_knowledge_check_share_same_conclusion_evidence_for_completed_sales_session(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    session = await _seed_completed_sales_session(
        test_db,
        owner=test_user,
        include_retrieval_hit=True,
        include_audio_segments=True,
    )

    report_data, replay_data, knowledge_check_data = await _fetch_route_family(
        async_client,
        session_id=session.session_id,
        headers=contract_auth_headers,
    )

    expected = {
        "main_issue": {
            "retrieval_source": {"available": True, "reason": None},
            "transcript_source": {"available": True, "turn_count": 1},
            "audio_source": {"available": True, "reason": None},
        },
        "next_goal": {
            "retrieval_source": {"available": True, "reason": None},
            "transcript_source": {"available": True, "turn_count": 1},
            "audio_source": {"available": True, "reason": None},
        },
        "claim_truth": {
            "retrieval_source": {"available": True, "reason": None},
            "transcript_source": {"available": True, "turn_count": 1},
            "audio_source": {"available": True, "reason": None},
        },
    }

    assert report_data["conclusion_evidence"] == replay_data["conclusion_evidence"] == knowledge_check_data["conclusion_evidence"] == expected


@pytest.mark.asyncio
async def test_report_replay_and_knowledge_check_share_same_evidence_degradation_for_happy_path_sales_session(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    session = await _seed_completed_sales_session(
        test_db,
        owner=test_user,
        include_retrieval_hit=True,
        include_audio_segments=True,
    )

    report_data, replay_data, knowledge_check_data = await _fetch_route_family(
        async_client,
        session_id=session.session_id,
        headers=contract_auth_headers,
    )

    expected = {
        "retrieval": {"status": "ok", "token": "retrieval_ok", "explanation": None},
        "transcript": {"status": "ok", "token": "transcript_ok", "explanation": None},
        "audio": {"status": "ok", "token": "audio_ok", "explanation": None},
        "enhanced_report": {
            "status": "ok",
            "token": "enhanced_report_ok",
            "explanation": None,
        },
    }

    assert _extract_evidence_degradation(report_data) == _extract_evidence_degradation(replay_data) == _extract_evidence_degradation(knowledge_check_data) == expected


@pytest.mark.asyncio
async def test_report_replay_and_knowledge_check_share_same_evidence_degradation_when_retrieval_missing(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    session = await _seed_completed_sales_session(
        test_db,
        owner=test_user,
        include_retrieval_hit=False,
        include_audio_segments=True,
    )

    report_data, replay_data, knowledge_check_data = await _fetch_route_family(
        async_client,
        session_id=session.session_id,
        headers=contract_auth_headers,
    )

    expected = {
        "retrieval": {
            "status": "degraded",
            "token": "no_retrieval_facts",
            "explanation": "no_voice_policy_snapshot",
        },
        "transcript": {"status": "ok", "token": "transcript_ok", "explanation": None},
        "audio": {"status": "ok", "token": "audio_ok", "explanation": None},
        "enhanced_report": {
            "status": "ok",
            "token": "enhanced_report_ok",
            "explanation": None,
        },
    }

    assert _extract_evidence_degradation(report_data) == _extract_evidence_degradation(replay_data) == _extract_evidence_degradation(knowledge_check_data) == expected


@pytest.mark.asyncio
async def test_report_replay_and_knowledge_check_share_same_evidence_degradation_when_audio_missing(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    session = await _seed_completed_sales_session(
        test_db,
        owner=test_user,
        include_retrieval_hit=True,
        include_audio_segments=False,
    )

    report_data, replay_data, knowledge_check_data = await _fetch_route_family(
        async_client,
        session_id=session.session_id,
        headers=contract_auth_headers,
    )

    expected = {
        "retrieval": {"status": "ok", "token": "retrieval_ok", "explanation": None},
        "transcript": {"status": "ok", "token": "transcript_ok", "explanation": None},
        "audio": {
            "status": "degraded",
            "token": "no_audio_segments",
            "explanation": "no_audio_segments",
        },
        "enhanced_report": {
            "status": "ok",
            "token": "enhanced_report_ok",
            "explanation": None,
        },
    }

    assert _extract_evidence_degradation(report_data) == _extract_evidence_degradation(replay_data) == _extract_evidence_degradation(knowledge_check_data) == expected


@pytest.mark.asyncio
async def test_route_family_keeps_conclusion_evidence_null_for_presentation_sessions(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    session = await _seed_completed_presentation_session(test_db, owner=test_user)

    report_data, replay_data, knowledge_check_data = await _fetch_route_family(
        async_client,
        session_id=session.session_id,
        headers=contract_auth_headers,
    )

    assert report_data["scenario_type"] == "presentation"
    assert replay_data["scenario_type"] == "presentation"
    assert report_data["conclusion_evidence"] is None
    assert replay_data["conclusion_evidence"] is None
    assert knowledge_check_data["conclusion_evidence"] is None


@pytest.mark.asyncio
async def test_evidence_degradation_null_for_presentation_sessions(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    session = await _seed_completed_presentation_session(test_db, owner=test_user)

    report_data, replay_data, knowledge_check_data = await _fetch_route_family(
        async_client,
        session_id=session.session_id,
        headers=contract_auth_headers,
    )

    assert report_data["evidence_degradation"] is None
    assert replay_data["evidence_degradation"] is None
    assert knowledge_check_data["evidence_degradation"] is None


@pytest.mark.asyncio
async def test_evidence_degradation_marks_enhanced_report_degraded_when_report_failed(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    session = await _seed_completed_sales_session(
        test_db,
        owner=test_user,
        include_retrieval_hit=True,
        include_audio_segments=True,
        report_status="failed",
        report_error="REPORT_GENERATION_FAILED",
    )

    report_data, replay_data, knowledge_check_data = await _fetch_route_family(
        async_client,
        session_id=session.session_id,
        headers=contract_auth_headers,
    )

    expected = {
        "retrieval": {"status": "ok", "token": "retrieval_ok", "explanation": None},
        "transcript": {"status": "ok", "token": "transcript_ok", "explanation": None},
        "audio": {"status": "ok", "token": "audio_ok", "explanation": None},
        "enhanced_report": {
            "status": "degraded",
            "token": "report_generation_failed",
            "explanation": "REPORT_GENERATION_FAILED",
        },
    }

    assert _extract_evidence_degradation(report_data) == _extract_evidence_degradation(replay_data) == _extract_evidence_degradation(knowledge_check_data) == expected


@pytest.mark.asyncio
async def test_support_runtime_faults_carry_same_runtime_event_line_for_knowledge_failures(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    contract_auth_headers: dict[str, str],
):
    test_user.role = "support"
    await test_db.commit()
    support_headers = {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(test_user.user_id)})}"
    }

    session = await _seed_completed_sales_session(
        test_db,
        owner=test_user,
        include_retrieval_hit=False,
        include_audio_segments=True,
    )

    snapshot = _make_voice_policy_snapshot_with_retrieval_hit()
    snapshot["knowledge_base_ids"] = []
    snapshot["tool_policy"] = {
        "enable_internal_retrieval": True,
        "require_kb_grounding": False,
    }
    snapshot["runtime_metrics"] = {
        "knowledge_retrieval": {
            "attempt_count": 1,
            "hit_query_count": 0,
            "total_results": 0,
            "last_result_count": 0,
            "hit_rate": 0.0,
            "last_query": "ROI 回本案例",
            "last_status": "search_failed",
            "last_error": "[KNOWLEDGE_SEARCH_UNAVAILABLE]",
            "recent_queries": ["ROI 回本案例"],
        },
        "knowledge_answer_diagnostics": {
            "mode": "grounded_preferred",
            "answerability": "insufficient",
            "source_status": "search_failed",
            "query": "ROI 回本案例",
            "path_mode": "compat",
            "rollout_mode": "dual_run",
            "shadow_audit_run_id": "audit-shadow-002",
        },
    }
    session.voice_policy_snapshot = snapshot
    session.effectiveness_snapshot = {
        **_make_sales_effectiveness_snapshot(),
        "claim_truth": {
            "status": "unsupported_claim",
            "source": "score_snapshot",
        },
    }
    session.report_status = "failed"
    session.report_error = "[REPORT_GENERATION_FAILED]"
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/support/runtime/faults?limit=20",
        headers=support_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    item = next(
        entry
        for entry in body["data"]["items"]
        if entry["session_id"] == session.session_id
    )
    runtime_events = item["diagnostics"]["runtime_events"]
    assert any(
        event["event_id"] == "knowledge_answer_path_mode"
        and event["status"] == "compat"
        and event["details"]["rollout_mode"] == "dual_run"
        for event in runtime_events
    )
    assert any(
        event["event_id"] == "knowledge_answer_quality"
        and event["status"] == "insufficient"
        and event["severity"] == "failure"
        for event in runtime_events
    )
    assert any(
        event["event_id"] == "claim_truth_status"
        and event["status"]
        and event["severity"] in {"degraded", "failure"}
        for event in runtime_events
    )
    serialized_events = str(runtime_events).lower()
    assert "token" not in serialized_events
    assert "base_url" not in serialized_events
