"""
Integration tests for support runtime release-health endpoints.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import (
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
    Scenario,
    User,
)


async def _create_user(
    db: AsyncSession,
    *,
    email: str,
    role: str,
    is_active: bool = True,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"support_{uuid.uuid4().hex[:8]}",
        name=email.split("@")[0],
        department="Support",
        email=email,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _make_not_evaluable_snapshot(reason: str) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": False,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "continuous_speech_seconds": 0.0,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.0,
        },
        "main_issue": {
            "issue_type": "insufficient_turn_data",
            "issue_text": "当前互动不足，暂时无法评估。",
            "recovery_rule": "补齐有效互动后再结束。",
        },
        "next_goal": {
            "goal_type": "collect_more_evidence",
            "goal_text": "先补齐有效互动，再继续诊断。",
            "rule": "至少完成 1 次往返对话。",
        },
        "version": "rule_v1",
        "evaluable": False,
        "not_evaluable_reason": reason,
    }


async def _seed_sales_session_with_search_failure(
    test_db: AsyncSession,
    *,
    user_id: str,
    now: datetime,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="support runtime sales",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        scenario_id=scenario.scenario_id,
        status="completed",
        voice_mode="stepfun_realtime",
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=3) + timedelta(minutes=6),
        total_duration_seconds=0,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot=_make_not_evaluable_snapshot("INSUFFICIENT_TURN_DATA"),
        report_status="completed",
        voice_policy_snapshot={
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": False,
            },
            "knowledge_base_ids": ["kb-sales-1"],
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 0,
                    "total_results": 0,
                    "last_result_count": 0,
                    "hit_rate": 0.0,
                    "last_query": "石犀产品资料",
                    "last_status": "search_failed",
                    "last_error": "[KNOWLEDGE_SEARCH_UNAVAILABLE] [EMBEDDING_API_ERROR]",
                    "recent_queries": ["石犀产品资料"],
                    "updated_at": (now - timedelta(hours=3)).isoformat(),
                    "upstream_disconnect_count_5m": 0,
                    "upstream_unstable": False,
                }
            },
        },
    )
    test_db.add_all([scenario, session])
    await test_db.commit()
    return session


async def _seed_stuck_scoring_session(
    test_db: AsyncSession,
    *,
    user_id: str,
    now: datetime,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="support runtime scoring",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        scenario_id=scenario.scenario_id,
        status="scoring",
        voice_mode="stepfun_realtime",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=35),
        report_status="processing",
    )
    test_db.add_all([scenario, session])
    await test_db.commit()
    return session


async def _seed_degraded_presentation_session(
    test_db: AsyncSession,
    *,
    user_id: str,
    now: datetime,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="support runtime presentation",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Support Runtime PPT",
        file_url="file:///tmp/support-runtime.pptx",
        status="ready",
        version_number=1,
        total_pages=2,
        ocr_progress=1.0,
    )
    page_1 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=1,
        ocr_extracted_text="第一页业务目标",
    )
    page_2 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=2,
        ocr_extracted_text="第二页ROI结果",
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
        user_id=user_id,
        scenario_id=scenario.scenario_id,
        presentation_id=presentation.presentation_id,
        status="completed",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=2) + timedelta(minutes=10),
        total_duration_seconds=10 * 60,
        report_status="failed",
        report_error="[REPORT_GENERATION_FAILED]",
    )
    messages = [
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="第一页先讲业务目标。",
            timestamp=now - timedelta(hours=2) + timedelta(minutes=1),
            duration_ms=120_000,
            transcript_metadata=None,
            score_snapshot={"overall_score": 86},
        ),
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=2,
            role="user",
            content="第二页继续讲业务目标，但没有说明 ROI。",
            timestamp=now - timedelta(hours=2) + timedelta(minutes=4),
            duration_ms=110_000,
            transcript_metadata=None,
            score_snapshot={"overall_score": 84},
        ),
    ]
    test_db.add_all([
        scenario,
        presentation,
        page_1,
        page_2,
        session,
        *talking_points,
        *messages,
    ])
    await test_db.commit()
    return session


@pytest.mark.asyncio
async def test_support_runtime_overview_requires_authentication(async_client) -> None:
    response = await async_client.get("/api/v1/support/runtime/overview")

    assert response.status_code == 401
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_support_role_can_read_release_health_overview_and_faults(
    async_client,
    test_db: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    support_user = await _create_user(
        test_db,
        email="support-reader@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    sales_session = await _seed_sales_session_with_search_failure(
        test_db,
        user_id=str(support_user.user_id),
        now=now,
    )
    scoring_session = await _seed_stuck_scoring_session(
        test_db,
        user_id=str(support_user.user_id),
        now=now,
    )
    presentation_session = await _seed_degraded_presentation_session(
        test_db,
        user_id=str(support_user.user_id),
        now=now,
    )

    overview_response = await async_client.get(
        "/api/v1/support/runtime/overview?window_hours=24",
        headers=headers,
    )
    assert overview_response.status_code == 200
    overview_body = overview_response.json()
    assert overview_body["success"] is True
    assert "trace_id" in overview_body

    overview = overview_body["data"]
    assert overview["session_health"]["total_sessions_window"] == 3
    assert overview["session_health"]["completed_sessions_window"] == 2
    assert overview["session_health"]["scoring_sessions"] == 1
    assert overview["session_health"]["stuck_scoring_sessions"] == 1
    assert overview["session_health"]["not_evaluable_completed_sessions_window"] == 1
    assert overview["release_health"]["status"] == "blocking"
    assert overview["release_health"]["blocking_count"] == 3
    assert overview["release_health"]["warning_count"] == 2

    faults_response = await async_client.get(
        "/api/v1/support/runtime/faults?limit=20",
        headers=headers,
    )
    assert faults_response.status_code == 200
    faults_body = faults_response.json()
    assert faults_body["success"] is True
    assert "trace_id" in faults_body

    items = faults_body["data"]["items"]
    kinds = {item["kind"] for item in items}
    assert kinds >= {
        "stuck_scoring",
        "knowledge_search_failed",
        "not_evaluable_completed",
        "presentation_degraded_missing_page_metadata",
        "optional_report_failed",
    }

    severity_by_kind = {item["kind"]: item["severity"] for item in items}
    assert severity_by_kind["stuck_scoring"] == "blocking"
    assert severity_by_kind["knowledge_search_failed"] == "blocking"
    assert severity_by_kind["not_evaluable_completed"] == "blocking"
    assert severity_by_kind["presentation_degraded_missing_page_metadata"] == "warning"
    assert severity_by_kind["optional_report_failed"] == "warning"

    sales_fault = next(item for item in items if item["kind"] == "knowledge_search_failed")
    assert sales_fault["session_id"] == sales_session.session_id
    assert sales_fault["scenario_type"] == "sales"
    assert sales_fault["diagnostics"]["last_status"] == "search_failed"

    scoring_fault = next(item for item in items if item["kind"] == "stuck_scoring")
    assert scoring_fault["session_id"] == scoring_session.session_id
    assert scoring_fault["session_status"] == "scoring"

    ppt_fault = next(
        item
        for item in items
        if item["kind"] == "presentation_degraded_missing_page_metadata"
    )
    assert ppt_fault["session_id"] == presentation_session.session_id
    assert ppt_fault["scenario_type"] == "presentation"
    assert ppt_fault["diagnostics"]["degraded_reasons"] == ["missing_page_metadata"]


@pytest.mark.asyncio
async def test_support_runtime_faults_can_filter_by_severity(
    async_client,
    test_db: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    support_user = await _create_user(
        test_db,
        email="support-fault-filter@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    await _seed_stuck_scoring_session(
        test_db,
        user_id=str(support_user.user_id),
        now=now,
    )
    await _seed_degraded_presentation_session(
        test_db,
        user_id=str(support_user.user_id),
        now=now,
    )

    response = await async_client.get(
        "/api/v1/support/runtime/faults?severity=warning&limit=20",
        headers=headers,
    )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert items
    assert all(item["severity"] == "warning" for item in items)


@pytest.mark.asyncio
async def test_support_runtime_faults_rejects_invalid_severity_filter(
    async_client,
    test_db: AsyncSession,
) -> None:
    support_user = await _create_user(
        test_db,
        email="support-invalid-filter@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})

    response = await async_client.get(
        "/api/v1/support/runtime/faults?severity=critical",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"] == "[INVALID_SEVERITY_FILTER]"
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_support_role_is_rejected_for_admin_write_operations(
    async_client,
    test_db: AsyncSession,
) -> None:
    support_user = await _create_user(
        test_db,
        email="support-no-write@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})

    response = await async_client.delete(
        f"/api/v1/admin/training-records/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_non_support_user_is_rejected_from_support_runtime(
    async_client,
    test_db: AsyncSession,
) -> None:
    normal_user = await _create_user(
        test_db,
        email="normal-user@example.com",
        role="user",
    )
    token = create_access_token(data={"sub": str(normal_user.user_id)})

    response = await async_client.get(
        "/api/v1/support/runtime/overview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "trace_id" in body
