"""Integration tests for asset governance summaries on current admin routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona, VoiceRuntimeProfile
from agent.schemas import PersonaListItem, PersonaResponse
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
from common.db.schemas import PresentationResponse
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from common.knowledge.schemas import KnowledgeBaseListItem, KnowledgeBaseResponse


async def _create_admin_user(db: AsyncSession) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"asset_admin_{uuid.uuid4().hex[:8]}",
        name="Asset Admin",
        department="Operations",
        email=f"asset-admin-{uuid.uuid4().hex[:6]}@example.com",
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_headers(test_db: AsyncSession) -> dict[str, str]:
    admin_user = await _create_admin_user(test_db)
    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


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


def _assert_governance_summary_schema_ref(model: type[object]) -> None:
    schema = model.model_json_schema()
    governance_property = schema["properties"]["governance_summary"]
    refs = [
        option.get("$ref")
        for option in governance_property.get("anyOf", [])
        if isinstance(option, dict)
    ]
    assert any(
        isinstance(ref, str) and ref.endswith("/AssetGovernanceSummary") for ref in refs
    )
    assert "AssetGovernanceSummary" in schema.get("$defs", {})


def _assert_governance_summary_payload(
    summary: dict[str, object],
    *,
    impact_level: str,
    recent_session_count: int,
    sessions_since_change: int,
    health_status: str,
    expected_anomaly_kinds: set[str],
) -> None:
    impact_summary = summary["impact_summary"]
    assert isinstance(impact_summary, dict)
    assert impact_summary["impact_level"] == impact_level
    assert impact_summary["recent_session_count"] == recent_session_count
    assert isinstance(impact_summary["active_session_count"], int)
    assert isinstance(impact_summary["impacted_user_count"], int)

    recent_change_summary = summary["recent_change_summary"]
    assert isinstance(recent_change_summary, dict)
    assert recent_change_summary["sessions_since_change"] == sessions_since_change
    assert isinstance(recent_change_summary["change_count_7d"], int)
    assert isinstance(recent_change_summary["latest_change_label"], str)
    assert recent_change_summary["latest_change_label"]

    health_summary = summary["health_summary"]
    assert isinstance(health_summary, dict)
    assert health_summary["status"] == health_status
    assert isinstance(health_summary["anomaly_count"], int)
    assert isinstance(health_summary["blocking_count"], int)
    assert isinstance(health_summary["warning_count"], int)

    sample_anomalies = health_summary["sample_anomalies"]
    assert isinstance(sample_anomalies, list)
    assert {
        anomaly["kind"]
        for anomaly in sample_anomalies
        if isinstance(anomaly, dict) and isinstance(anomaly.get("kind"), str)
    } >= expected_anomaly_kinds
    for anomaly in sample_anomalies:
        assert isinstance(anomaly, dict)
        assert isinstance(anomaly.get("kind"), str)
        assert anomaly["kind"]
        assert isinstance(anomaly.get("source"), str)
        assert anomaly["source"]
        assert anomaly.get("severity") in {"warning", "blocking"}
        assert isinstance(anomaly.get("summary"), str)
        assert anomaly["summary"]


@pytest.mark.parametrize(
    "model",
    [
        KnowledgeBaseResponse,
        KnowledgeBaseListItem,
        PersonaResponse,
        PersonaListItem,
        PresentationResponse,
    ],
)
def test_asset_response_models_use_shared_governance_summary_schema(model: type[object]) -> None:
    _assert_governance_summary_schema_ref(model)


async def test_runtime_profile_openapi_exposes_typed_governance_summary(
    async_client,
) -> None:
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200

    document = response.json()
    route_schema = document["paths"]["/api/v1/admin/voice-runtime/profiles"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in route_schema

    components = document.get("components", {}).get("schemas", {})
    assert "AssetGovernanceSummary" in components
    assert any(
        any(
            isinstance(option, dict)
            and option.get("$ref", "").endswith("/AssetGovernanceSummary")
            for option in schema.get("properties", {})
            .get("governance_summary", {})
            .get("anyOf", [])
        )
        for schema in components.values()
        if isinstance(schema, dict)
    )


async def _seed_asset_graph(test_db: AsyncSession) -> dict[str, str]:
    now = datetime.now(UTC)

    learner = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"asset_user_{uuid.uuid4().hex[:8]}",
        name="Asset Learner",
        department="Sales",
        email=f"asset-user-{uuid.uuid4().hex[:6]}@example.com",
        role="user",
        is_active=True,
    )
    test_db.add(learner)

    sales_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="Asset governance sales",
        is_active=True,
    )
    presentation_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="Asset governance presentation",
        is_active=True,
    )

    knowledge_base = KnowledgeBase(
        id=str(uuid.uuid4()),
        name="产品资料库",
        description="产品参数与话术",
        category="product",
        vector_collection=f"kb_{uuid.uuid4().hex[:8]}",
        document_count=2,
        total_chunks=12,
        status="active",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(hours=5),
    )
    ready_document = KnowledgeDocument(
        id=str(uuid.uuid4()),
        knowledge_base_id=knowledge_base.id,
        title="产品手册",
        file_type="pdf",
        file_url="file:///tmp/product-manual.pdf",
        file_size=1024,
        status="ready",
        chunk_count=10,
        created_at=now - timedelta(hours=6),
    )
    failed_document = KnowledgeDocument(
        id=str(uuid.uuid4()),
        knowledge_base_id=knowledge_base.id,
        title="竞品对比",
        file_type="pdf",
        file_url="file:///tmp/competitor.pdf",
        file_size=1024,
        status="failed",
        chunk_count=0,
        error_message="embedding timeout",
        created_at=now - timedelta(hours=4),
    )

    persona = Persona(
        id=str(uuid.uuid4()),
        name="高压客户",
        description="持续要求证据与 ROI",
        category="customer",
        difficulty="hard",
        system_prompt="你是一个要求证据的客户。",
        knowledge_base_ids=[knowledge_base.id],
        persona_policy={
            "version": 1,
            "system_prompt": "你是一个要求证据的客户。",
            "knowledge_base_ids": [knowledge_base.id],
            "tool_policy": {"require_kb_grounding": True},
            "sales_focus": "roi",
            "value_axes": ["roi"],
            "objection_axes": ["price"],
            "expected_customer_questions": ["ROI 依据是什么？"],
        },
        status="active",
        is_public=True,
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(hours=5),
    )

    runtime_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="销售默认 Realtime",
        description="默认销售实时语音配置",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        input_audio_format="pcm16",
        output_audio_format="pcm16",
        output_sample_rate=24000,
        tool_policy={"kb_lock_mode": "strict_audit"},
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(hours=5),
    )

    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="季度复盘",
        file_url="file:///tmp/qbr.pptx",
        file_size_bytes=2048,
        upload_date=now - timedelta(hours=6),
        version_number=3,
        status="ready",
        uploaded_by_admin_id=None,
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

    completed_sales = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=sales_scenario.scenario_id,
        persona_id=persona.id,
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id=runtime_profile.id,
        status="completed",
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=3) + timedelta(minutes=6),
        total_duration_seconds=6 * 60,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot=_make_not_evaluable_snapshot("INSUFFICIENT_TURN_DATA"),
        report_status="completed",
        voice_policy_snapshot={
            "runtime_profile_id": runtime_profile.id,
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": True,
            },
            "knowledge_base_ids": [knowledge_base.id],
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
    stuck_scoring = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=sales_scenario.scenario_id,
        persona_id=persona.id,
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id=runtime_profile.id,
        status="scoring",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=40),
        report_status="processing",
        voice_policy_snapshot={
            "runtime_profile_id": runtime_profile.id,
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": True,
            },
            "knowledge_base_ids": [knowledge_base.id],
        },
    )
    completed_presentation = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=presentation_scenario.scenario_id,
        presentation_id=presentation.presentation_id,
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id=runtime_profile.id,
        status="completed",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=2) + timedelta(minutes=10),
        total_duration_seconds=10 * 60,
        report_status="failed",
        report_error="[REPORT_GENERATION_FAILED]",
        voice_policy_snapshot={
            "runtime_profile_id": runtime_profile.id,
            "tool_policy": {
                "enable_internal_retrieval": False,
                "require_kb_grounding": False,
            },
            "knowledge_base_ids": [],
        },
    )

    presentation_messages = [
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=completed_presentation.session_id,
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
            session_id=completed_presentation.session_id,
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
        learner,
        sales_scenario,
        presentation_scenario,
        knowledge_base,
        ready_document,
        failed_document,
        persona,
        runtime_profile,
        presentation,
        page_1,
        page_2,
        *talking_points,
        completed_sales,
        stuck_scoring,
        completed_presentation,
        *presentation_messages,
    ])
    await test_db.commit()

    return {
        "knowledge_base_id": knowledge_base.id,
        "persona_id": persona.id,
        "runtime_profile_id": runtime_profile.id,
        "presentation_id": presentation.presentation_id,
    }


@pytest.mark.asyncio
async def test_asset_routes_expose_governance_summaries(
    async_client,
    test_db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    seeded = await _seed_asset_graph(test_db)

    knowledge_response = await async_client.get(
        "/api/v1/admin/knowledge?page=1&page_size=20",
        headers=admin_headers,
    )
    assert knowledge_response.status_code == 200
    knowledge_items = knowledge_response.json()["data"]["knowledge_bases"]
    knowledge_item = next(item for item in knowledge_items if item["id"] == seeded["knowledge_base_id"])
    _assert_governance_summary_payload(
        knowledge_item["governance_summary"],
        impact_level="high",
        recent_session_count=2,
        sessions_since_change=2,
        health_status="blocking",
        expected_anomaly_kinds={"kb_lock_blocked_search_failed", "document_failed"},
    )

    persona_response = await async_client.get(
        "/api/v1/admin/personas?page=1&page_size=20",
        headers=admin_headers,
    )
    assert persona_response.status_code == 200
    persona_items = persona_response.json()["data"]["personas"]
    persona_item = next(item for item in persona_items if item["id"] == seeded["persona_id"])
    _assert_governance_summary_payload(
        persona_item["governance_summary"],
        impact_level="high",
        recent_session_count=2,
        sessions_since_change=2,
        health_status="blocking",
        expected_anomaly_kinds={"policy_issue_pressure_model_legacy_only"},
    )

    presentations_response = await async_client.get(
        "/api/v1/presentations?limit=20",
        headers=admin_headers,
    )
    assert presentations_response.status_code == 200
    presentation_item = next(
        item
        for item in presentations_response.json()
        if item["presentation_id"] == seeded["presentation_id"]
    )
    _assert_governance_summary_payload(
        presentation_item["governance_summary"],
        impact_level="medium",
        recent_session_count=1,
        sessions_since_change=1,
        health_status="warning",
        expected_anomaly_kinds={"presentation_degraded_missing_page_metadata", "optional_report_failed"},
    )

    runtime_response = await async_client.get(
        "/api/v1/admin/voice-runtime/profiles",
        headers=admin_headers,
    )
    assert runtime_response.status_code == 200
    runtime_items = runtime_response.json()["data"]["items"]
    runtime_item = next(item for item in runtime_items if item["id"] == seeded["runtime_profile_id"])
    _assert_governance_summary_payload(
        runtime_item["governance_summary"],
        impact_level="high",
        recent_session_count=3,
        sessions_since_change=3,
        health_status="blocking",
        expected_anomaly_kinds={
            "kb_lock_blocked_search_failed",
            "stuck_scoring",
            "presentation_degraded_missing_page_metadata",
        },
    )
