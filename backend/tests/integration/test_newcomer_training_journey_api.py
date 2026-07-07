from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import PracticeSession, Scenario, User
from sales_trainer.models import SalesTrainerAiCoachSession, SalesTrainerUnit
from sales_trainer.services.asset_revision_service import (
    AssetPublishResult,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)


async def _create_user(
    test_db: AsyncSession,
    *,
    role: str,
    department: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"journey-api-{uuid.uuid4().hex[:8]}",
        name=f"Journey API {role}",
        department=department,
        email=f"journey-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _publish_minimal_path(test_db: AsyncSession, *, actor: User) -> None:
    unit_id = str(uuid.uuid4())
    test_db.add(
        SalesTrainerUnit(
            unit_id=unit_id,
            name="Journey API 单元",
            unit_type="quiz",
            config={},
            status="published",
        )
    )
    await test_db.commit()
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": "newcomer_training_path_v1",
            "title": "新人训练路径",
            "enabled": True,
            "modules": [
                {
                    "module_key": "business_skills",
                    "module_type": "article_exam",
                    "enabled": True,
                    "order_index": 1,
                    "title": "商务技巧",
                    "target_unit_id": unit_id,
                    "completion_rule": "passed",
                }
            ],
        },
        actor=actor,
        change_class="semantic",
        reason="发布 Journey API 测试路径",
    )
    await test_db.commit()


async def _publish_path_with_ai_coach(
    test_db: AsyncSession,
    *,
    actor: User,
) -> AssetPublishResult:
    unit_id = str(uuid.uuid4())
    test_db.add(
        SalesTrainerUnit(
            unit_id=unit_id,
            name="Journey API AI Coach 单元",
            unit_type="quiz",
            config={},
            status="published",
        )
    )
    await test_db.commit()
    result = await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": "newcomer_training_path_v1",
            "title": "新人训练路径",
            "enabled": True,
            "modules": [
                {
                    "module_key": "business_skills",
                    "module_type": "article_exam",
                    "enabled": True,
                    "order_index": 1,
                    "title": "商务技巧",
                    "target_unit_id": unit_id,
                    "learning_content_id": "article-journey-api-1",
                    "exam_paper_id": "paper-journey-api-1",
                    "completion_rule": "passed",
                    "ai_coach": {
                        "enabled": True,
                        "prompt_template_id": str(uuid.uuid4()),
                        "allowed_interaction_types": ["single_choice"],
                        "mastery_threshold": 80,
                    },
                }
            ],
        },
        actor=actor,
        change_class="semantic",
        reason="发布 Journey API AI Coach 测试路径",
    )
    await test_db.commit()
    return result


async def _publish_path_with_ready_realtime(
    test_db: AsyncSession,
    *,
    actor: User,
) -> AssetPublishResult:
    result = await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": "newcomer_training_path_v1",
            "title": "新人训练路径",
            "enabled": True,
            "modules": [
                {
                    "module_key": "realtime_roleplay",
                    "module_type": "realtime_roleplay",
                    "enabled": True,
                    "order_index": 1,
                    "title": "实时对练",
                    "completion_rule": "submitted",
                    "runtime_binding": {
                        "binding_key": "newcomer_realtime_roleplay_v1",
                        "runtime_owner": "training_runtime",
                        "runtime_descriptor_id": "newcomer-realtime-runtime",
                        "scenario_key": "newcomer-realtime-roleplay",
                        "runtime_config_revision_id": "runtime-config-rev-1",
                        "provider_readiness_snapshot": {
                            "provider": "stepfun_realtime",
                            "ready": True,
                            "checked_at": "2026-06-27T00:00:00Z",
                            "config_revision_id": "runtime-config-rev-1",
                        },
                    },
                }
            ],
        },
        actor=actor,
        change_class="semantic",
        reason="发布 Journey API 实时对练测试路径",
    )
    await test_db.commit()
    return result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_return_only_current_learner_journey(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    learner = await _create_user(test_db, role="user", department="销售一部")
    other = await _create_user(test_db, role="user", department="销售二部")
    await _publish_minimal_path(test_db, actor=admin)

    own_response = await async_client.get(
        "/api/v1/sales-trainer/journey",
        headers=_auth_headers(learner),
    )
    other_admin_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/journeys/{other.user_id}",
        headers=_auth_headers(learner),
    )

    assert own_response.status_code == 200
    assert own_response.json()["data"]["learner_id"] == str(learner.user_id)
    assert other_admin_response.status_code == 403
    assert other_admin_response.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_preserve_realtime_next_action_in_journey_api(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    learner = await _create_user(test_db, role="user", department="销售一部")
    revision = await _publish_path_with_ready_realtime(test_db, actor=admin)

    response = await async_client.get(
        "/api/v1/sales-trainer/journey",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["path_revision_id"] == str(revision.revision.revision_id)
    realtime_module = next(
        module
        for module in data["modules"]
        if module["kind"] == "realtime_roleplay"
        and module["module_key"] == "realtime_roleplay"
    )
    assert realtime_module["status"] == "not_started"
    assert realtime_module["next_action"] == {
        "action_key": "start_realtime_roleplay",
        "label": "开始实时对练",
        "target_path": None,
        "disabled": False,
        "disabled_reason": None,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_project_completed_realtime_roleplay_into_training_journey(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    learner = await _create_user(test_db, role="user", department="销售一部")
    revision = await _publish_path_with_ready_realtime(test_db, actor=admin)
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        name="Journey API 实时对练",
        description="Journey API 实时对练",
        scenario_type="sales",
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="completed",
        start_time=datetime(2026, 7, 2, 9, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 2, 9, 8, tzinfo=UTC),
        logic_score=88.0,
        accuracy_score=92.0,
        completeness_score=85.0,
        voice_policy_snapshot={
            "external_binding": {
                "owner": "sales_trainer",
                "path_key": "newcomer_training_path_v1",
                "path_revision_id": str(revision.revision.revision_id),
                "path_revision_no": int(revision.revision.revision_no),
                "module_key": "realtime_roleplay",
                "binding_key": "newcomer_realtime_roleplay_v1",
            }
        },
    )
    test_db.add_all([scenario, session])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/sales-trainer/journey",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    realtime_module = next(
        module
        for module in data["modules"]
        if module["kind"] == "realtime_roleplay"
        and module["module_key"] == "realtime_roleplay"
    )
    assert realtime_module["status"] == "scored"
    assert realtime_module["completion_satisfied"] is True
    assert realtime_module["latest_outcome"]["record_type"] == (
        "realtime_roleplay_session"
    )
    assert realtime_module["latest_outcome"]["source_record_id"] == session.session_id
    assert realtime_module["latest_outcome"]["path_revision_id"] == str(
        revision.revision.revision_id
    )
    assert realtime_module["latest_outcome"]["snapshot_ref"] == {
        "snapshot_type": "runtime_outcome_snapshot",
        "legacy_snapshot_only": False,
        "regrade_unavailable": False,
    }
    assert realtime_module["outcome_history"][0]["evidence"]["record_id"] == (
        session.session_id
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_preserve_ai_coach_next_action_and_bindings_in_journey_api(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    learner = await _create_user(test_db, role="user", department="销售一部")
    revision = await _publish_path_with_ai_coach(test_db, actor=admin)

    response = await async_client.get(
        "/api/v1/sales-trainer/journey",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["path_revision_id"] == str(revision.revision.revision_id)
    quiz_module = next(
        module
        for module in data["modules"]
        if module["kind"] == "quiz_attempt"
        and module["module_key"] == "business_skills"
    )
    ai_module = next(
        module
        for module in data["modules"]
        if module["kind"] == "ai_coach"
        and module["module_key"] == "business_skills"
    )

    assert quiz_module["target_unit_id"]
    assert quiz_module["target_unit_ids"] == [quiz_module["target_unit_id"]]
    assert quiz_module["learning_content_id"] == "article-journey-api-1"
    assert quiz_module["exam_paper_id"] == "paper-journey-api-1"
    assert ai_module["target_unit_id"] is None
    assert ai_module["target_unit_ids"] == []
    assert ai_module["learning_content_id"] == "article-journey-api-1"
    assert ai_module["exam_paper_id"] == "paper-journey-api-1"
    assert ai_module["next_action"] == {
        "action_key": "start_ai_coach",
        "label": "进入 AI 教练",
        "target_path": "/sales-trainer/business-skills/coach",
        "disabled": False,
        "disabled_reason": None,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_reject_non_learner_roles_from_learner_ai_coach_routes(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    headers = _auth_headers(admin)

    chat_response = await async_client.post(
        "/api/v1/newcomer-training/ai-coach/chat/sessions",
        headers=headers,
        json={"module_key": "business_skills"},
    )
    assert chat_response.status_code == 403
    assert chat_response.json()["error"] == "[NEWCOMER_LEARNER_ROLE_REQUIRED]"

    chat_stream_response = await async_client.post(
        "/api/v1/newcomer-training/ai-coach/chat/sessions/stream",
        headers=headers,
        json={"module_key": "business_skills"},
    )
    assert chat_stream_response.status_code == 403
    assert chat_stream_response.json()["error"] == "[NEWCOMER_LEARNER_ROLE_REQUIRED]"

    v1_response = await async_client.post(
        "/api/v1/newcomer-training/ai-coach/sessions",
        headers=headers,
        json={"module_key": "business_skills"},
    )
    assert v1_response.status_code == 403
    assert v1_response.json()["error"] == "[NEWCOMER_LEARNER_ROLE_REQUIRED]"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_fail_closed_for_admin_journey_outside_team_scope(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    manager = await _create_user(test_db, role="training_lead", department="销售一部")
    same_team_learner = await _create_user(test_db, role="user", department="销售一部")
    other_team_learner = await _create_user(test_db, role="user", department="销售二部")
    await _publish_minimal_path(test_db, actor=admin)

    same_team = await async_client.get(
        f"/api/v1/admin/sales-trainer/journeys/{same_team_learner.user_id}",
        headers=_auth_headers(manager),
    )
    other_team = await async_client.get(
        f"/api/v1/admin/sales-trainer/journeys/{other_team_learner.user_id}",
        headers=_auth_headers(manager),
    )

    assert same_team.status_code == 200
    assert same_team.json()["data"]["learner_id"] == str(same_team_learner.user_id)
    assert other_team.status_code == 404
    assert other_team.json()["error"] == "[TRAINING_RECORD_NOT_FOUND]"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_list_and_analyze_admin_journeys_with_team_scope(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    manager = await _create_user(test_db, role="training_lead", department="销售一部")
    same_team_learner = await _create_user(test_db, role="user", department="销售一部")
    other_team_learner = await _create_user(test_db, role="user", department="销售二部")
    await _publish_minimal_path(test_db, actor=admin)

    list_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys",
        headers=_auth_headers(manager),
    )
    cross_department_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys?department=销售二部",
        headers=_auth_headers(manager),
    )
    analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics",
        headers=_auth_headers(manager),
    )
    cross_department_analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics?department=销售二部",
        headers=_auth_headers(manager),
    )
    learner_level_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys?learner_level=unassigned",
        headers=_auth_headers(manager),
    )
    unknown_level_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys?learner_level=unknown_level",
        headers=_auth_headers(manager),
    )
    learner_level_analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics?learner_level=unassigned",
        headers=_auth_headers(manager),
    )
    role_level_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys?role_level=learner",
        headers=_auth_headers(manager),
    )
    unknown_role_level_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys?role_level=unknown_role",
        headers=_auth_headers(manager),
    )
    role_level_analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics?role_level=learner",
        headers=_auth_headers(manager),
    )
    stage_analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics?training_stage=not_started",
        headers=_auth_headers(manager),
    )
    module_analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics?module_key=business_skills",
        headers=_auth_headers(manager),
    )

    assert list_response.status_code == 200
    payload = list_response.json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["learner_id"] == str(same_team_learner.user_id)
    assert payload["items"][0]["training_stage"] == "not_started"
    assert cross_department_response.status_code == 200
    assert cross_department_response.json()["data"]["total"] == 0
    assert learner_level_response.status_code == 200
    learner_level_payload = learner_level_response.json()["data"]
    assert learner_level_payload["total"] == 1
    assert learner_level_payload["items"][0]["learner_level"]["level_key"] == (
        "unassigned"
    )
    assert unknown_level_response.status_code == 200
    assert unknown_level_response.json()["data"]["total"] == 0
    assert role_level_response.status_code == 200
    role_level_payload = role_level_response.json()["data"]
    assert role_level_payload["total"] == 1
    assert role_level_payload["items"][0]["role_level"]["level_key"] == "learner"
    assert unknown_role_level_response.status_code == 200
    assert unknown_role_level_response.json()["data"]["total"] == 0
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()["data"]
    assert analytics["summary"]["learner_count"] == 1
    assert analytics["funnel"][0]["stage"] == "not_started"
    assert analytics["funnel"][0]["learner_count"] == 1
    assert analytics["module_summaries"][0]["module_key"] == "business_skills"
    assert analytics["weakness_heatmap"][0]["module_key"] == "business_skills"
    assert analytics["weakness_heatmap"][0]["heatmap_key"]
    assert analytics["trend_data"] == []
    assert analytics["filters"]["department"] == "销售一部"
    assert cross_department_analytics_response.status_code == 200
    cross_department_analytics = cross_department_analytics_response.json()["data"]
    assert cross_department_analytics["summary"]["learner_count"] == 0
    assert cross_department_analytics["summary"]["loaded_learner_count"] == 0
    assert cross_department_analytics["filters"]["department"] == "销售一部"
    assert learner_level_analytics_response.status_code == 200
    learner_level_analytics = learner_level_analytics_response.json()["data"]
    assert learner_level_analytics["summary"]["learner_count"] == 1
    assert learner_level_analytics["filters"] == {
        "department": "销售一部",
        "training_stage": None,
        "module_key": None,
        "learner_level": "unassigned",
        "role_level": None,
        "limit": 500,
    }
    assert role_level_analytics_response.status_code == 200
    role_level_analytics = role_level_analytics_response.json()["data"]
    assert role_level_analytics["summary"]["learner_count"] == 1
    assert role_level_analytics["filters"] == {
        "department": "销售一部",
        "training_stage": None,
        "module_key": None,
        "learner_level": None,
        "role_level": "learner",
        "limit": 500,
    }
    assert stage_analytics_response.status_code == 200
    stage_analytics = stage_analytics_response.json()["data"]
    assert stage_analytics["summary"]["learner_count"] == 1
    assert stage_analytics["filters"]["training_stage"] == "not_started"
    assert module_analytics_response.status_code == 200
    module_analytics = module_analytics_response.json()["data"]
    assert module_analytics["summary"]["learner_count"] == 1
    assert module_analytics["filters"]["module_key"] == "business_skills"
    assert {item["module_key"] for item in module_analytics["module_summaries"]} == {
        "business_skills"
    }
    assert {item["module_key"] for item in module_analytics["weakness_heatmap"]} == {
        "business_skills"
    }
    assert str(other_team_learner.user_id) not in {
        item["learner_id"] for item in payload["items"]
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_reject_non_record_viewers_from_admin_journey_analytics(
    async_client,
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", department="销售一部")
    content_admin = await _create_user(test_db, role="content_admin", department="总部")

    learner_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics",
        headers=_auth_headers(learner),
    )
    content_admin_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics",
        headers=_auth_headers(content_admin),
    )

    assert learner_response.status_code == 403
    assert learner_response.json()["error"] == "[ROLE_REQUIRED]"
    assert content_admin_response.status_code == 403
    assert content_admin_response.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_apply_analytics_limit_to_loaded_journeys(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    await _create_user(test_db, role="user", department="销售一部")
    await _create_user(test_db, role="user", department="销售一部")
    await _publish_minimal_path(test_db, actor=admin)

    analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics?department=销售一部&limit=1",
        headers=_auth_headers(admin),
    )

    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()["data"]
    assert analytics_payload["summary"]["learner_count"] == 2
    assert analytics_payload["summary"]["loaded_learner_count"] == 1
    assert analytics_payload["filters"]["department"] == "销售一部"
    assert analytics_payload["filters"]["limit"] == 1
    assert analytics_payload["module_summaries"][0]["learner_count"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_project_ai_coach_outcome_into_journey_and_analytics(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    learner = await _create_user(test_db, role="user", department="销售一部")
    published_path = await _publish_path_with_ai_coach(test_db, actor=admin)

    session_id = str(uuid.uuid4())
    session = SalesTrainerAiCoachSession(
        session_id=session_id,
        user_id=str(learner.user_id),
        module_key="business_skills",
        path_key=NEWCOMER_PATH_LOGICAL_ID,
        path_revision_id=str(published_path.revision.revision_id),
        path_revision_no=int(published_path.revision.revision_no),
        article_snapshot={"title": "商务技巧"},
        path_config_snapshot={"module_key": "business_skills"},
        prompt_template_id=str(uuid.uuid4()),
        prompt_revision_id=str(uuid.uuid4()),
        prompt_contract_hash="contract-hash",
        config_snapshot={"mastery_threshold": 80},
        coach_state={"evidence": "integration-test"},
        status="completed",
        mastery_state="mastered",
        total_score=92,
        max_score=100,
        trace_id="trace-ai-coach-journey",
    )
    test_db.add(session)
    await test_db.commit()

    learner_response = await async_client.get(
        "/api/v1/sales-trainer/journey",
        headers=_auth_headers(learner),
    )
    analytics_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics",
        headers=_auth_headers(admin),
    )

    assert learner_response.status_code == 200
    journey = learner_response.json()["data"]
    ai_modules = [
        module for module in journey["modules"] if module["kind"] == "ai_coach"
    ]
    assert len(ai_modules) == 1
    ai_module = ai_modules[0]
    assert ai_module["module_key"] == "business_skills"
    assert ai_module["status"] == "passed"
    assert ai_module["passed"] is True
    assert ai_module["latest_outcome"]["record_type"] == "ai_coach_session"
    assert ai_module["latest_outcome"]["source_record_id"] == session_id
    assert ai_module["latest_outcome"]["path_revision_id"] == str(
        published_path.revision.revision_id
    )
    assert ai_module["latest_outcome"]["snapshot_ref"]["legacy_snapshot_only"] is False

    assert analytics_response.status_code == 200
    analytics = analytics_response.json()["data"]
    ai_heatmap = [
        item
        for item in analytics["weakness_heatmap"]
        if item["heatmap_key"] == "business_skills:ai_coach"
    ]
    assert len(ai_heatmap) == 1
    assert ai_heatmap[0]["passed_count"] == 1
    assert ai_heatmap[0]["risk_count"] == 0
    assert analytics["trend_data"] == [
        {
            "date": session.updated_at.date().isoformat(),
            "outcome_count": 1,
            "passed_outcome_count": 1,
            "risk_outcome_count": 0,
            "active_learner_count": 1,
            "pass_rate": 100.0,
            "average_score": 92.0,
        }
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_return_typed_risk_reasons_for_admin_journey_analytics(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", department="总部")
    learner = await _create_user(test_db, role="user", department="销售一部")
    published_path = await _publish_path_with_ai_coach(test_db, actor=admin)
    session_id = str(uuid.uuid4())
    test_db.add(
        SalesTrainerAiCoachSession(
            session_id=session_id,
            user_id=str(learner.user_id),
            module_key="business_skills",
            path_key=NEWCOMER_PATH_LOGICAL_ID,
            path_revision_id=str(published_path.revision.revision_id),
            path_revision_no=int(published_path.revision.revision_no),
            article_snapshot={"title": "商务技巧"},
            path_config_snapshot={"module_key": "business_skills"},
            prompt_template_id=str(uuid.uuid4()),
            prompt_revision_id=str(uuid.uuid4()),
            prompt_contract_hash="contract-hash",
            config_snapshot={"mastery_threshold": 80},
            coach_state={"evidence": "risk-reason-test"},
            status="completed",
            mastery_state="not_mastered",
            total_score=62,
            max_score=100,
            trace_id="trace-ai-coach-risk-reason",
        )
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys/analytics",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    risk_learners = response.json()["data"]["risk_learners"]
    assert len(risk_learners) == 1
    assert risk_learners[0]["learner_id"] == str(learner.user_id)
    assert risk_learners[0]["risk_module_count"] == 1
    assert risk_learners[0]["risk_module_keys"] == ["business_skills"]
    assert risk_learners[0]["risk_reasons"] == ["business_skills:not_passed"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_training_manager_sees_only_same_department_journeys(
    async_client,
    test_db: AsyncSession,
) -> None:
    """training_manager 角色应通过 team_department 过滤只看到本部门学员。

    覆盖 PRD AC5：training_manager 只能看本部门学员，传其他 department 被后端拒。
    team_department 由后端 _team_scope(current_user) 自动注入，前端传 department
    不能越权查看其他部门。
    """
    admin = await _create_user(test_db, role="admin", department="总部")
    manager = await _create_user(
        test_db, role="training_manager", department="销售一部"
    )
    same_team_learner = await _create_user(
        test_db, role="user", department="销售一部"
    )
    other_team_learner = await _create_user(
        test_db, role="user", department="销售二部"
    )
    await _publish_minimal_path(test_db, actor=admin)

    list_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys",
        headers=_auth_headers(manager),
    )
    cross_department_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys?department=销售二部",
        headers=_auth_headers(manager),
    )

    assert list_response.status_code == 200
    payload = list_response.json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["learner_id"] == str(same_team_learner.user_id)
    assert str(other_team_learner.user_id) not in {
        item["learner_id"] for item in payload["items"]
    }
    # 前端试图传其他 department 绕过 team_scope：后端应忽略并只返回本部门数据
    assert cross_department_response.status_code == 200
    assert cross_department_response.json()["data"]["total"] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_training_manager_cannot_view_other_department_journey_detail(
    async_client,
    test_db: AsyncSession,
) -> None:
    """training_manager 查看其他部门学员的 journey 详情应被拒（404）。

    覆盖 PRD AC5：get_admin_journey 通过 team_department 过滤，跨部门访问返回
    [TRAINING_RECORD_NOT_FOUND]，避免泄露其他部门学员是否存在。
    """
    admin = await _create_user(test_db, role="admin", department="总部")
    manager = await _create_user(
        test_db, role="training_manager", department="销售一部"
    )
    same_team_learner = await _create_user(
        test_db, role="user", department="销售一部"
    )
    other_team_learner = await _create_user(
        test_db, role="user", department="销售二部"
    )
    await _publish_minimal_path(test_db, actor=admin)

    same_team = await async_client.get(
        f"/api/v1/admin/sales-trainer/journeys/{same_team_learner.user_id}",
        headers=_auth_headers(manager),
    )
    other_team = await async_client.get(
        f"/api/v1/admin/sales-trainer/journeys/{other_team_learner.user_id}",
        headers=_auth_headers(manager),
    )

    assert same_team.status_code == 200
    assert same_team.json()["data"]["learner_id"] == str(same_team_learner.user_id)
    assert other_team.status_code == 404
    assert other_team.json()["error"] == "[TRAINING_RECORD_NOT_FOUND]"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_learner_rejected_from_admin_journey_endpoints(
    async_client,
    test_db: AsyncSession,
) -> None:
    """普通 learner 角色无权调 admin journey 接口（403）。

    覆盖 PRD AC9：普通 learner 调 /admin/journeys 和 /admin/journeys/{id} 应被拒。
    """
    admin = await _create_user(test_db, role="admin", department="总部")
    learner = await _create_user(test_db, role="user", department="销售一部")
    other_learner = await _create_user(
        test_db, role="user", department="销售一部"
    )
    await _publish_minimal_path(test_db, actor=admin)

    list_response = await async_client.get(
        "/api/v1/admin/sales-trainer/journeys",
        headers=_auth_headers(learner),
    )
    detail_response = await async_client.get(
        f"/api/v1/admin/sales-trainer/journeys/{other_learner.user_id}",
        headers=_auth_headers(learner),
    )

    assert list_response.status_code == 403
    assert list_response.json()["error"] == "[ROLE_REQUIRED]"
    assert detail_response.status_code == 403
    assert detail_response.json()["error"] == "[ROLE_REQUIRED]"
