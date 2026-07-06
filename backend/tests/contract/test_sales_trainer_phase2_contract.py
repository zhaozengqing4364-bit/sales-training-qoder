from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import sales_trainer.api as sales_trainer_api
from common.auth.service import create_access_token
from common.business_rules.defaults import (
    DEFAULT_SALES_TRAINER_REALTIME_PROVIDER_REGISTRY,
    SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import PracticeSession, Scenario, User
from common.services.practice_session_ports import (
    PracticeTemplateRuntimeIdentity,
    clear_practice_session_contributors,
    register_agent_persona_pair_validator,
    register_practice_session_snapshot_applier,
    register_practice_template_runtime_identity_resolver,
    register_runtime_policy_resolver_factory,
)
from curriculum_practice.models import PracticeTemplate
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAssetRevision,
    SalesTrainerAudioSubmission,
    SalesTrainerBusinessEtiquetteQuizAttempt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerOperationLog,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    RealtimeRoleplayStartResponse,
    SalesTrainerTrainingRecordResponse,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str, *, department: str | None = None) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"phase2-contract-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Phase2 Contract {role}",
        email=f"phase2-contract-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        department=department,
    )


def _unit(admin: User, *, name: str = "阶段 2 训练") -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name=name,
        unit_type="quiz",
        config={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )


def _ready_realtime_binding(template_id: str) -> dict[str, object]:
    return {
        "binding_key": "newcomer_realtime_roleplay_v1",
        "runtime_owner": "training_runtime",
        "runtime_descriptor_id": "newcomer-realtime-runtime",
        "scenario_key": "newcomer-realtime-roleplay",
        "practice_template_id": template_id,
        "runtime_config_revision_id": "runtime-config-rev-1",
        "provider_readiness_snapshot": {
            "provider": "mock",
            "ready": True,
            "checked_at": "2026-06-27T00:00:00Z",
            "config_revision_id": "runtime-config-rev-1",
        },
        "failure_policy": {
            "terminal_codes": ["CONFIG_INVALID"],
            "transient_codes": ["NETWORK_TIMEOUT"],
            "voluntary_codes": ["USER_CANCELLED"],
            "terminal_retry_allowed": False,
        },
        "rollback_policy": {
            "rollback_via_active_revision": True,
            "disable_module_on_invalid_binding": True,
            "fallback_to_placeholder": False,
        },
    }


async def _publish_realtime_path(
    db: AsyncSession,
    *,
    actor: User,
    binding: dict[str, object],
    learner_level_required: list[str] | None = None,
) -> str:
    result = await SalesTrainerAssetRevisionService(db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": NEWCOMER_PATH_LOGICAL_ID,
            "title": "新人训练路径",
            "enabled": True,
            "modules": [
                {
                    "module_key": "realtime_roleplay",
                    "module_type": "realtime_roleplay",
                    "enabled": True,
                    "order_index": 4,
                    "title": "实时对练",
                    "completion_rule": "submitted",
                    "learner_level_required": learner_level_required or [],
                    "runtime_binding": binding,
                }
            ],
        },
        actor=actor,
        change_class="semantic",
        reason="发布 realtime start contract 测试路径",
    )
    await db.commit()
    return str(result.revision.revision_id)


async def _publish_ready_runtime_registry(
    db: AsyncSession,
    *,
    actor: User,
    descriptor_id: str = "newcomer-realtime-runtime",
) -> None:
    value = dict(DEFAULT_SALES_TRAINER_REALTIME_PROVIDER_REGISTRY)
    value["enabled"] = True
    value["descriptors"] = [
        {
            "descriptor_id": descriptor_id,
            "label": "新人训练实时对练",
            "provider": "mock",
            "runtime_owner": "training_runtime",
            "enabled": True,
            "runtime_profile_id": None,
            "config_revision_id": "runtime-config-rev-1",
            "rollback_to_descriptor_id": None,
            "readiness": {
                "ready": True,
                "checked_at": "2026-06-27T00:00:00Z",
                "failure_code": None,
                "failure_message": None,
            },
        }
    ]
    service = BusinessRuleConfigService(db)
    draft = await service.create_or_update_draft(
        key=SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
        value=value,
        actor_id=str(actor.user_id),
        reason="enable realtime provider registry",
    )
    await service.publish(
        key=SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
        actor_id=str(actor.user_id),
        config_id=str(draft.id),
        reason="publish ready realtime provider registry",
    )
    await db.commit()


class _RuntimePolicyResolver:
    async def resolve_effective_policy(
        self,
        *,
        agent_id: str | None,
        persona_id: str | None,
        voice_mode_override: str | None,
        runtime_profile_override: str | None,
    ) -> dict[str, object]:
        return {
            "voice_mode": voice_mode_override or "stepfun_realtime",
            "runtime_profile_id": runtime_profile_override,
            "agent_id": agent_id,
            "persona_id": persona_id,
        }


def _register_practice_ports(
    *,
    agent_id: str,
    persona_id: str,
    runtime_profile_id: str,
) -> None:
    clear_practice_session_contributors()
    register_runtime_policy_resolver_factory(lambda db: _RuntimePolicyResolver())

    async def _identity_resolver(
        db: AsyncSession,
        session_data,
        scenario_type_value: str,
        requested_agent_id: str | None,
        requested_persona_id: str | None,
    ) -> PracticeTemplateRuntimeIdentity:
        return PracticeTemplateRuntimeIdentity(
            agent_id=agent_id,
            persona_id=persona_id,
            runtime_profile_id=runtime_profile_id,
            voice_mode="stepfun_realtime",
        )

    async def _validator(
        db: AsyncSession,
        agent_id_str: str | None,
        persona_id_str: str | None,
    ) -> dict[str, object] | None:
        return None

    async def _snapshot_applier(
        db: AsyncSession,
        session: PracticeSession,
        session_data,
        scenario_type_value: str,
        current_user: User,
    ) -> None:
        session.practice_template_id = str(session_data.practice_template_id)

    register_practice_template_runtime_identity_resolver(_identity_resolver)
    register_agent_persona_pair_validator(_validator)
    register_practice_session_snapshot_applier(_snapshot_applier)


@pytest.mark.asyncio
async def test_manager_dashboard_should_match_phase2_contract(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    unit = _unit(admin)
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=55,
        max_score=100,
        passed=False,
        status="scored",
        submitted_at=datetime.now(UTC),
    )
    test_db.add_all([admin, learner, unit, attempt])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/manager-dashboard",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["policy"]["key"] == "sales_trainer.phase2.closed_loop_policy"
    assert data["summary"]["record_count"] == 1
    assert data["summary"]["low_score_record_count"] == 1
    assert data["risk_learners"][0]["suggested_action"]
    assert data["intervention_suggestions"][0]["action"]


@pytest.mark.asyncio
async def test_legacy_admin_training_records_should_not_expose_sales_trainer_realtime_sessions(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        name="旧训练记录接口旁路复核",
        scenario_type="sales",
    )
    normal_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="completed",
        start_time=datetime(2026, 6, 29, 8, 0, tzinfo=UTC),
        end_time=datetime(2026, 6, 29, 8, 10, tzinfo=UTC),
    )
    sales_trainer_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="completed",
        start_time=datetime(2026, 6, 29, 9, 0, tzinfo=UTC),
        end_time=datetime(2026, 6, 29, 9, 10, tzinfo=UTC),
        voice_policy_snapshot={
            "external_binding": {
                "owner": "sales_trainer",
                "path_key": "newcomer_training_path_v1",
                "module_key": "realtime_roleplay",
            }
        },
    )
    test_db.add_all([admin, learner, scenario, normal_session, sales_trainer_session])
    await test_db.commit()

    list_response = await async_client.get(
        "/api/v1/admin/training-records",
        headers=_headers(admin),
    )

    assert list_response.status_code == 200
    list_data = list_response.json()["data"]
    assert list_data["total"] == 1
    assert [item["id"] for item in list_data["items"]] == [normal_session.session_id]

    detail_response = await async_client.get(
        f"/api/v1/admin/training-records/{sales_trainer_session.session_id}",
        headers=_headers(admin),
    )
    delete_response = await async_client.delete(
        f"/api/v1/admin/training-records/{sales_trainer_session.session_id}",
        headers=_headers(admin),
    )

    assert detail_response.status_code == 404
    assert delete_response.status_code == 404
    assert await test_db.get(PracticeSession, sales_trainer_session.session_id) is not None


@pytest.mark.asyncio
async def test_training_records_should_page_after_unified_union_window(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit(admin)
    base = datetime(2026, 6, 12, tzinfo=UTC)
    attempts = [
        SalesTrainerQuizAttempt(
            attempt_id=str(uuid.uuid4()),
            unit_id=unit.unit_id,
            user_id=learner.user_id,
            total_score=80,
            max_score=100,
            passed=True,
            status="scored",
            submitted_at=base + timedelta(seconds=index),
        )
        for index in range(505)
    ]
    test_db.add_all([admin, learner, unit, *attempts])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records?limit=1&offset=500",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 505
    assert data["items"][0]["record_id"] == attempts[4].attempt_id
    assert data["items"][0]["score"] == 80
    assert data["items"][0]["effective_score"]["score"] == 80


@pytest.mark.asyncio
async def test_training_records_api_should_forward_journey_and_status_filters(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    captured: dict[str, object] = {}

    class FakeTrainingRecordService:
        def __init__(self, db: AsyncSession) -> None:
            captured["db"] = db

        async def list_records(self, **kwargs: object) -> tuple[list[dict[str, object]], int]:
            captured.update(kwargs)
            return [], 0

    monkeypatch.setattr(
        sales_trainer_api,
        "TrainingRecordService",
        FakeTrainingRecordService,
    )

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records"
        "?user_id=user-1"
        "&unit_id=unit-1"
        "&material_version_id=material-version-1"
        "&module_key=business_skills"
        "&training_stage=needs_remediation"
        "&learner_level=unassigned"
        "&role_level=learner"
        "&status=scored"
        "&limit=25"
        "&offset=5",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"items": [], "total": 0}
    assert captured["user_id"] == "user-1"
    assert captured["unit_id"] == "unit-1"
    assert captured["material_version_id"] == "material-version-1"
    assert captured["module_key"] == "business_skills"
    assert captured["training_stage"] == "needs_remediation"
    assert captured["learner_level"] == "unassigned"
    assert captured["role_level"] == "learner"
    assert captured["status"] == "scored"
    assert captured["limit"] == 25
    assert captured["offset"] == 5
    assert captured["team_department"] is None
    assert captured["viewer"] is not None
    assert getattr(captured["viewer"], "user_id") == admin.user_id


@pytest.mark.asyncio
async def test_training_record_detail_should_cover_all_record_types(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit(admin)
    audio = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="pitch.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/pitch.wav",
        confirmed_material_version_id="material-version-contract",
        material_snapshot={
            "version": 1,
            "items": [{"material_id": "material-contract"}],
            "confirmed_material_version_id": "material-version-contract",
            "frozen_at": "2026-06-27T00:00:00+00:00",
            "legacy_extra": {"kept": True},
        },
        score_scheme_snapshot={
            "prompt_id": "prompt-contract",
            "name": "合同评分标准",
            "purpose": "ppt_pitch",
            "version": 3,
            "status": "published",
            "learner_rubric": {"criteria": [{"key": "structure", "label": "结构"}]},
            "pass_threshold": 70,
            "prompt_snapshot": {
                "prompt_id": "prompt-contract",
                "name": "冻结评分 Prompt",
                "purpose": "ppt_pitch",
                "system_prompt": "按历史标准评分",
                "scoring_template": "历史模板 v3",
                "output_schema": {"type": "object"},
                "learner_rubric": {
                    "criteria": [{"key": "structure", "label": "结构"}]
                },
                "version": 3,
                "status": "published",
            },
        },
        task_brief_snapshot={
            "enabled": True,
            "title": "冻结 PPT 讲解任务",
            "purpose": "讲清价值",
            "scenario": "客户拜访",
            "instructions": ["先讲痛点"],
            "success_criteria": ["结构清晰"],
            "common_mistakes": [],
            "upload_guidance": "上传录音",
            "submission_context": {
                "path_key": "newcomer_training_path_v1",
                "path_revision_id": "path-rev-contract",
                "path_revision_no": 2,
                "module_key": "audio_pitch",
                "module_type": "audio_scoring",
                "legacy_snapshot_only": False,
            },
        },
        status="uploaded",
        created_at=datetime.now(UTC),
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=90,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime.now(UTC),
    )
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        module_key="business_skills",
        status="in_progress",
        trace_id="trace-phase2-detail",
        created_at=datetime.now(UTC),
    )
    path_revision = SalesTrainerAssetRevision(
        revision_id=str(uuid.uuid4()),
        resource_type="newcomer_path_config",
        logical_id="newcomer_training_path_v1",
        revision_no=2,
        status="published",
        payload_json={"path_key": "newcomer_training_path_v1"},
        payload_hash="hash-contract-business-quiz-path",
        change_class="semantic",
    )
    pack_revision = SalesTrainerAssetRevision(
        revision_id=str(uuid.uuid4()),
        resource_type="business_etiquette_training_pack",
        logical_id="business_etiquette_v1",
        revision_no=1,
        status="published",
        payload_json={"training_pack_key": "business_etiquette_v1"},
        payload_hash="hash-contract-business-quiz-pack",
        change_class="semantic",
    )
    business_attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        training_pack_key="business_etiquette_v1",
        learning_unit_key="trust_opening",
        learning_unit_title="建立信任",
        user_id=learner.user_id,
        path_revision_id=path_revision.revision_id,
        path_revision_no=2,
        training_pack_revision_id=pack_revision.revision_id,
        training_pack_revision_no=1,
        capability_snapshot={"capabilities": ["business_etiquette_trust"]},
        question_snapshots=[{"question_id": "beq-contract-1"}],
        answers_snapshot=[
            {
                "question_id": "beq-contract-1",
                "question_type": "single_choice",
                "score": 8,
                "max_score": 10,
                "is_correct": True,
                "capability_keys": ["business_etiquette_trust"],
            }
        ],
        capability_scores=[
            {
                "capability_key": "business_etiquette_trust",
                "display_name": "建立信任",
                "score": 8,
                "max_score": 10,
                "normalized_score": 80,
                "mastered": True,
            }
        ],
        weak_capability_keys=[],
        recommended_chapter_orders=[],
        total_score=8,
        max_score=10,
        passed=True,
        status="scored",
        submitted_at=datetime.now(UTC),
    )
    log = SalesTrainerOperationLog(
        actor_id=learner.user_id,
        actor_role=learner.role,
        action="business_etiquette_unit_quiz.submitted",
        target_type="business_etiquette_unit_quiz_attempt",
        target_id=business_attempt.attempt_id,
        request_id="trace-business-quiz-contract",
        metadata_json={"learning_unit_key": "trust_opening"},
    )
    test_db.add_all([
        admin,
        learner,
        unit,
        audio,
        attempt,
        session,
        path_revision,
        pack_revision,
        business_attempt,
        log,
    ])
    await test_db.commit()

    for record_type, record_id in (
        ("audio_submission", audio.submission_id),
        ("quiz_attempt", attempt.attempt_id),
        ("ai_coach_session", session.session_id),
        ("business_etiquette_quiz_attempt", business_attempt.attempt_id),
    ):
        response = await async_client.get(
            f"/api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}",
            headers=_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["record_type"] == record_type
        assert data["effective_score"] is not None
        assert data["score_explanation"] is not None
        assert data["ability_profile"] is not None
        assert data["remediation"] is not None
        typed_data = SalesTrainerTrainingRecordResponse.model_validate(data)
        if record_type == "audio_submission":
            assert typed_data.audio_submission is not None
            assert typed_data.audio_submission.submission_id == audio.submission_id
            assert data["material_snapshot"]["items"][0]["material_id"] == (
                "material-contract"
            )
            assert data["material_snapshot"]["legacy_extra"]["kept"] is True
            assert data["score_scheme_snapshot"]["pass_threshold"] == 70
            assert data["score_scheme_snapshot"]["prompt_snapshot"]["name"] == (
                "冻结评分 Prompt"
            )
            assert data["task_brief_snapshot"]["title"] == "冻结 PPT 讲解任务"
            assert data["audio_submission"]["score_scheme_snapshot"][
                "prompt_snapshot"
            ]["scoring_template"] == "历史模板 v3"
        if record_type == "quiz_attempt":
            assert typed_data.quiz_attempt is not None
            assert typed_data.quiz_attempt.attempt_id == attempt.attempt_id
            assert typed_data.quiz_attempt.passed is True
        if record_type == "business_etiquette_quiz_attempt":
            assert data["path_revision_id"] == path_revision.revision_id
            assert data["legacy_snapshot_only"] is False
            assert data["business_etiquette_quiz_attempt"]["attempt_id"] == (
                business_attempt.attempt_id
            )
            assert data["business_etiquette_quiz_attempt"][
                "training_pack_revision_id"
            ] == pack_revision.revision_id
            assert data["business_etiquette_quiz_attempt"]["answers"][0][
                "question_id"
            ] == "beq-contract-1"
            assert data["operation_logs"][0]["action"] == (
                "business_etiquette_unit_quiz.submitted"
            )

    unit_filter = await async_client.get(
        f"/api/v1/admin/sales-trainer/training-records?unit_id={unit.unit_id}",
        headers=_headers(admin),
    )
    assert unit_filter.status_code == 200
    assert {
        item["record_type"] for item in unit_filter.json()["data"]["items"]
    } == {"audio_submission", "quiz_attempt"}


@pytest.mark.asyncio
async def test_business_etiquette_legacy_training_record_detail_should_stay_replayable(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        training_pack_key="business_etiquette_v1",
        learning_unit_key="trust_opening",
        learning_unit_title="建立信任",
        user_id=learner.user_id,
        path_revision_id=None,
        path_revision_no=None,
        training_pack_revision_id=None,
        training_pack_revision_no=None,
        capability_snapshot={},
        question_snapshots=[],
        answers_snapshot=[],
        capability_scores=[],
        weak_capability_keys=[],
        recommended_chapter_orders=[],
        total_score=None,
        max_score=None,
        passed=None,
        status="submitted",
        submitted_at=datetime.now(UTC),
    )
    test_db.add_all([admin, learner, attempt])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records/detail/"
        f"business_etiquette_quiz_attempt/{attempt.attempt_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    snapshot = data["business_etiquette_quiz_attempt"]
    assert data["record_type"] == "business_etiquette_quiz_attempt"
    assert data["legacy_snapshot_only"] is True
    assert snapshot["attempt_id"] == attempt.attempt_id
    assert snapshot["path_revision_id"] is None
    assert snapshot["path_revision_no"] is None
    assert snapshot["training_pack_revision_id"] is None
    assert snapshot["question_snapshots"] == []
    assert snapshot["answers"] == []
    assert snapshot["capability_scores"] == []


@pytest.mark.asyncio
async def test_ai_coach_training_record_detail_should_expose_lineage_audit_and_remediation(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    session_id = str(uuid.uuid4())
    path_revision_id = str(uuid.uuid4())
    session = SalesTrainerAiCoachSession(
        session_id=session_id,
        user_id=learner.user_id,
        module_key="business_skills",
        path_key="newcomer_training_path_v1",
        path_revision_id=path_revision_id,
        path_revision_no=7,
        article_snapshot={
            "title": "商务礼仪",
            "chapters": [{"title": "建立信任"}],
        },
        path_config_snapshot={
            "path_key": "newcomer_training_path_v1",
            "path_revision_id": path_revision_id,
            "path_revision_no": 7,
            "module_key": "business_skills",
            "legacy_snapshot_only": False,
            "ai_coach": {"enabled": True},
        },
        prompt_template_id=str(uuid.uuid4()),
        prompt_revision_id=str(uuid.uuid4()),
        prompt_contract_hash="hash-ai-coach-contract",
        config_snapshot={"mastery_threshold": 80, "min_turns": 3},
        coach_state={"last_action": "remediate"},
        status="completed",
        mastery_state="not_mastered",
        total_score=62,
        max_score=100,
        trace_id="trace-ai-coach-detail",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    log = SalesTrainerOperationLog(
        actor_id=admin.user_id,
        actor_role=admin.role,
        action="ai_coach_session_finished_v1",
        target_type="sales_trainer_ai_coach_session",
        target_id=session_id,
        request_id="trace-ai-coach-detail",
        metadata_json={"mastery_state": "not_mastered"},
    )
    test_db.add_all([admin, learner, session, log])
    await test_db.commit()

    response = await async_client.get(
        f"/api/v1/admin/sales-trainer/training-records/detail/ai_coach_session/{session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["record_type"] == "ai_coach_session"
    assert data["path_key"] == "newcomer_training_path_v1"
    assert data["path_revision_id"] == path_revision_id
    assert data["path_revision_no"] == 7
    assert data["module_key"] == "business_skills"
    assert data["legacy_snapshot_only"] is False
    assert data["score"] == 62
    assert data["passed"] is False
    assert data["effective_score"]["score"] == 62
    assert data["effective_score"]["passed"] is False
    assert data["score_explanation"]["basis"] == "ai_coach_session_snapshot_v1"
    assert data["score_explanation"]["issues"][0]["type"] == "not_mastered"
    assert data["ability_profile"]["weak_dimensions"][0]["key"] == (
        "business_skills_ai_coach"
    )
    assert data["remediation"]["needed"] is True
    assert data["remediation"]["action_label"] == "继续 AI 教练训练"
    assert data["remediation"]["target_path"] == "/sales-trainer/business-skills/coach"
    assert data["ai_coach_session"]["article_snapshot"]["title"] == "商务礼仪"
    assert data["ai_coach_session"]["config_snapshot"]["mastery_threshold"] == 80
    assert data["ai_coach_session"]["coach_state"]["last_action"] == "remediate"
    assert data["ai_coach_session"]["prompt_revision_id"] == session.prompt_revision_id
    assert data["operation_logs"][0]["action"] == "ai_coach_session_finished_v1"
    assert data["operation_logs"][0]["metadata"]["mastery_state"] == "not_mastered"


@pytest.mark.asyncio
async def test_training_records_material_version_filter_should_only_match_audio(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit(admin)
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key=f"phase2-{uuid.uuid4().hex[:8]}",
        name="阶段 2 材料",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label="v1",
        title="阶段 2 材料 v1",
        file_name="phase2.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        storage_key="/tmp/phase2.pdf",
        status="published",
        created_by=admin.user_id,
    )
    material.current_version_id = version.version_id
    audio = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="pitch.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/pitch.wav",
        confirmed_material_version_id=version.version_id,
        status="uploaded",
        created_at=datetime.now(UTC),
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=90,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime.now(UTC),
    )
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        module_key="business_skills",
        status="in_progress",
        trace_id="trace-phase2-material-filter",
    )
    test_db.add_all([
        admin,
        learner,
        unit,
        material,
        version,
        audio,
        attempt,
        session,
    ])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records"
        f"?material_version_id={version.version_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["record_type"] == "audio_submission"


@pytest.mark.asyncio
async def test_training_records_should_filter_department_scope(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    manager = _user("training_manager", department="销售一部")
    admin = _user("admin")
    learner_a = _user("user", department="销售一部")
    learner_b = _user("user", department="销售二部")
    unit = _unit(admin)
    attempts = [
        SalesTrainerQuizAttempt(
            attempt_id=str(uuid.uuid4()),
            unit_id=unit.unit_id,
            user_id=learner_a.user_id,
            total_score=80,
            max_score=100,
            passed=True,
            status="scored",
            submitted_at=datetime.now(UTC),
        ),
        SalesTrainerQuizAttempt(
            attempt_id=str(uuid.uuid4()),
            unit_id=unit.unit_id,
            user_id=learner_b.user_id,
            total_score=80,
            max_score=100,
            passed=True,
            status="scored",
            submitted_at=datetime.now(UTC),
        ),
    ]
    test_db.add_all([manager, admin, learner_a, learner_b, unit, *attempts])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records",
        headers=_headers(manager),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["user_id"] == learner_a.user_id


@pytest.mark.asyncio
async def test_realtime_roleplay_start_api_should_expose_runtime_binding_contract(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    admin = _user("admin")
    template_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    persona_id = str(uuid.uuid4())
    runtime_profile_id = str(uuid.uuid4())
    template = PracticeTemplate(
        template_id=template_id,
        name="新人实时对练模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=agent_id,
        persona_id=persona_id,
        runtime_profile_id=runtime_profile_id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=str(uuid.uuid4()),
        knowledge_base_refs=[],
        status="published",
    )
    test_db.add_all([learner, admin, template])
    await test_db.commit()
    await _publish_ready_runtime_registry(test_db, actor=admin)
    revision_id = await _publish_realtime_path(
        test_db,
        actor=admin,
        binding=_ready_realtime_binding(template_id),
    )
    _register_practice_ports(
        agent_id=agent_id,
        persona_id=persona_id,
        runtime_profile_id=runtime_profile_id,
    )

    try:
        response = await async_client.post(
            "/api/v1/sales-trainer/realtime-roleplay/start",
            json={"module_key": "realtime_roleplay"},
            headers=_headers(learner),
        )
    finally:
        clear_practice_session_contributors()

    assert response.status_code == 200
    data = response.json()["data"]
    typed = RealtimeRoleplayStartResponse.model_validate(data)
    assert typed.session_id
    assert typed.practice_url == f"/practice/{typed.session_id}"
    assert typed.path_revision_id == revision_id
    assert typed.provider_readiness_snapshot.ready is True
    assert typed.runtime_registry.descriptor.provider == "mock"
    assert typed.runtime_registry.version == 1
    assert typed.external_binding.owner == "sales_trainer"
    assert typed.external_binding.module_key == "realtime_roleplay"
    assert typed.external_binding.path_revision_id == revision_id
    assert typed.external_binding.runtime_registry.descriptor.provider == "mock"
    assert typed.external_binding.provider_readiness_snapshot.ready is True


@pytest.mark.asyncio
async def test_realtime_roleplay_start_api_should_fail_closed_when_registry_disabled(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    admin = _user("admin")
    template_id = str(uuid.uuid4())
    template = PracticeTemplate(
        template_id=template_id,
        name="新人实时对练模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=str(uuid.uuid4()),
        persona_id=str(uuid.uuid4()),
        runtime_profile_id=str(uuid.uuid4()),
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=str(uuid.uuid4()),
        knowledge_base_refs=[],
        status="published",
    )
    test_db.add_all([learner, admin, template])
    await test_db.commit()
    await _publish_realtime_path(
        test_db,
        actor=admin,
        binding=_ready_realtime_binding(template_id),
    )

    response = await async_client.post(
        "/api/v1/sales-trainer/realtime-roleplay/start",
        json={"module_key": "realtime_roleplay"},
        headers=_headers(learner),
    )

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]"
    assert body["details"]["registry_key"] == (
        SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY
    )


@pytest.mark.asyncio
async def test_realtime_roleplay_start_api_should_fail_closed_when_module_locked(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    admin = _user("admin")
    template_id = str(uuid.uuid4())
    template = PracticeTemplate(
        template_id=template_id,
        name="新人实时对练模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id=str(uuid.uuid4()),
        persona_id=str(uuid.uuid4()),
        runtime_profile_id=str(uuid.uuid4()),
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=str(uuid.uuid4()),
        knowledge_base_refs=[],
        status="published",
    )
    test_db.add_all([learner, admin, template])
    await test_db.commit()
    await _publish_ready_runtime_registry(test_db, actor=admin)
    await _publish_realtime_path(
        test_db,
        actor=admin,
        binding=_ready_realtime_binding(template_id),
        learner_level_required=["ready"],
    )

    response = await async_client.post(
        "/api/v1/sales-trainer/realtime-roleplay/start",
        json={"module_key": "realtime_roleplay"},
        headers=_headers(learner),
    )

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[SALES_TRAINER_UNIT_NOT_FOUND]"
    session_count = await test_db.scalar(select(func.count(PracticeSession.session_id)))
    assert session_count == 0
