from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    DEFAULT_SALES_TRAINER_REALTIME_PROVIDER_REGISTRY,
    SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import PracticeSession, User
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
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerUnit,
)
from sales_trainer.permissions import can_enter_sales_trainer_realtime
from sales_trainer.schemas import RealtimeRoleplayStartResponse
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.realtime_roleplay_start_service import (
    RealtimeRoleplayStartError,
    RealtimeRoleplayStartService,
)


def _user(role: str = "user") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"realtime-start-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Realtime Start {role}",
        email=f"realtime-start-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )


def _ready_binding(template_id: str) -> dict[str, object]:
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
    prerequisite_unit_id: str | None = None,
) -> str:
    modules: list[dict[str, object]] = []
    if prerequisite_unit_id is not None:
        modules.append(
            {
                "module_key": "ppt_explanation",
                "module_type": "audio_scoring",
                "enabled": True,
                "order_index": 1,
                "title": "PPT 讲解",
                "target_unit_id": prerequisite_unit_id,
                "completion_rule": "passed",
                "unlock_after_unit_ids": [],
            }
        )
    modules.append(
        {
            "module_key": "realtime_roleplay",
            "module_type": "realtime_roleplay",
            "enabled": True,
            "order_index": 2 if prerequisite_unit_id is not None else 4,
            "title": "实时对练",
            "completion_rule": "submitted",
            "learner_level_required": learner_level_required or [],
            "unlock_after_unit_ids": (
                [prerequisite_unit_id] if prerequisite_unit_id is not None else []
            ),
            "runtime_binding": binding,
        }
    )
    result = await SalesTrainerAssetRevisionService(db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": NEWCOMER_PATH_LOGICAL_ID,
            "title": "新人训练路径",
            "enabled": True,
            "modules": modules,
        },
        actor=actor,
        change_class="semantic",
        reason="发布 realtime start 测试路径",
    )
    await db.commit()
    return str(result.revision.revision_id)


async def _seed_passed_audio_evidence(
    db: AsyncSession,
    *,
    learner: User,
    prompt: SalesTrainerAudioScorePrompt,
    unit: SalesTrainerUnit,
    revision_id: str,
) -> None:
    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="realtime-prerequisite.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/realtime-prerequisite.wav",
        task_brief_snapshot={
            "submission_context": {
                "path_key": NEWCOMER_PATH_LOGICAL_ID,
                "path_revision_id": revision_id,
                "path_revision_no": 1,
                "module_key": "ppt_explanation",
                "legacy_snapshot_only": False,
            }
        },
        status="scored",
    )
    score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=submission.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="realtime-prerequisite-hash",
        total_score=90,
        passed=True,
        strengths=[],
        improvements=[],
        dimension_scores={},
    )
    db.add_all([submission, score])
    await db.commit()


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
async def test_start_realtime_roleplay_creates_session_with_external_binding(
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
        binding=_ready_binding(template_id),
    )
    _register_practice_ports(
        agent_id=agent_id,
        persona_id=persona_id,
        runtime_profile_id=runtime_profile_id,
    )
    try:
        result = await RealtimeRoleplayStartService(test_db).start(actor=learner)
    finally:
        clear_practice_session_contributors()

    session = await test_db.get(PracticeSession, result["session_id"])
    assert session is not None
    assert session.status == "preparing"
    assert session.practice_template_id == template_id
    assert session.voice_mode == "stepfun_realtime"
    binding = session.voice_policy_snapshot["external_binding"]
    assert binding["owner"] == "sales_trainer"
    assert binding["path_revision_id"] == revision_id
    assert binding["path_revision_no"] == 1
    assert binding["module_key"] == "realtime_roleplay"
    assert binding["practice_template_id"] == template_id
    assert binding["runtime_registry"]["version"] == 1
    assert binding["runtime_registry"]["descriptor"]["provider"] == "mock"
    assert result["practice_url"] == f"/practice/{session.session_id}"
    assert result["runtime_registry"]["version"] == 1
    response = RealtimeRoleplayStartResponse.model_validate(result)
    assert response.external_binding.runtime_registry.descriptor.provider == "mock"
    assert response.provider_readiness_snapshot.ready is True


@pytest.mark.asyncio
async def test_start_realtime_roleplay_fails_without_active_revision(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    test_db.add(learner)
    await test_db.commit()

    with pytest.raises(RealtimeRoleplayStartError) as exc_info:
        await RealtimeRoleplayStartService(test_db).start(actor=learner)

    assert exc_info.value.code == "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_start_realtime_roleplay_fails_when_provider_not_ready(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    admin = _user("admin")
    binding = _ready_binding(str(uuid.uuid4()))
    binding["provider_readiness_snapshot"] = {
        "provider": "mock",
        "ready": False,
        "checked_at": "2026-06-27T00:00:00Z",
        "config_revision_id": "runtime-config-rev-1",
        "failure_code": "PROVIDER_OFFLINE",
        "failure_message": "provider offline",
    }
    test_db.add_all([learner, admin])
    await test_db.commit()
    await _publish_realtime_path(test_db, actor=admin, binding=binding)

    with pytest.raises(RealtimeRoleplayStartError) as exc_info:
        await RealtimeRoleplayStartService(test_db).start(actor=learner)

    assert exc_info.value.code == "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]"
    assert exc_info.value.status_code == 503
    assert exc_info.value.details["failure_code"] == "PROVIDER_OFFLINE"


@pytest.mark.asyncio
async def test_start_realtime_roleplay_fails_when_module_is_locked_by_learner_level(
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
        binding=_ready_binding(template_id),
        learner_level_required=["ready"],
    )

    with pytest.raises(RealtimeRoleplayStartError) as exc_info:
        await RealtimeRoleplayStartService(test_db).start(actor=learner)

    assert exc_info.value.code == "[SALES_TRAINER_UNIT_NOT_FOUND]"
    assert exc_info.value.status_code == 404
    session_count = await test_db.scalar(select(func.count(PracticeSession.session_id)))
    assert session_count == 0


@pytest.mark.asyncio
async def test_start_realtime_roleplay_requires_active_revision_prerequisite_evidence(
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
        name="前置闸门实时对练模板",
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
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="实时对练前置评分",
        purpose="ppt_pitch",
        system_prompt="评分。",
        scoring_template="评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    prerequisite_unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解",
        unit_type="audio_scoring",
        config={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([learner, admin, template, prompt, prerequisite_unit])
    await test_db.commit()
    await _publish_ready_runtime_registry(test_db, actor=admin)
    active_revision_id = await _publish_realtime_path(
        test_db,
        actor=admin,
        binding=_ready_binding(template_id),
        prerequisite_unit_id=prerequisite_unit.unit_id,
    )

    with pytest.raises(RealtimeRoleplayStartError) as locked:
        await RealtimeRoleplayStartService(test_db).start(actor=learner)
    assert locked.value.code == "[SALES_TRAINER_UNIT_NOT_FOUND]"
    assert locked.value.status_code == 404
    assert await test_db.scalar(select(func.count(PracticeSession.session_id))) == 0

    await _seed_passed_audio_evidence(
        test_db,
        learner=learner,
        prompt=prompt,
        unit=prerequisite_unit,
        revision_id="old-path-revision",
    )
    with pytest.raises(RealtimeRoleplayStartError) as stale:
        await RealtimeRoleplayStartService(test_db).start(actor=learner)
    assert stale.value.code == "[SALES_TRAINER_UNIT_NOT_FOUND]"
    assert stale.value.status_code == 404
    assert await test_db.scalar(select(func.count(PracticeSession.session_id))) == 0

    await _seed_passed_audio_evidence(
        test_db,
        learner=learner,
        prompt=prompt,
        unit=prerequisite_unit,
        revision_id=active_revision_id,
    )
    _register_practice_ports(
        agent_id=agent_id,
        persona_id=persona_id,
        runtime_profile_id=runtime_profile_id,
    )
    try:
        result = await RealtimeRoleplayStartService(test_db).start(actor=learner)
    finally:
        clear_practice_session_contributors()

    assert result["path_revision_id"] == active_revision_id
    assert await test_db.scalar(select(func.count(PracticeSession.session_id))) == 1


@pytest.mark.asyncio
async def test_start_realtime_roleplay_fails_when_registry_is_disabled(
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
        binding=_ready_binding(template_id),
    )

    with pytest.raises(RealtimeRoleplayStartError) as exc_info:
        await RealtimeRoleplayStartService(test_db).start(actor=learner)

    assert exc_info.value.code == "[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]"
    assert exc_info.value.status_code == 503
    assert exc_info.value.details["registry_key"] == (
        SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY
    )
    assert exc_info.value.details["source"] == "default"


def test_realtime_roleplay_enter_permission_is_learner_only() -> None:
    assert can_enter_sales_trainer_realtime(_user("user")) is True
    assert can_enter_sales_trainer_realtime(_user("learner")) is True
    assert can_enter_sales_trainer_realtime(_user("admin")) is False
    assert can_enter_sales_trainer_realtime(_user("training_manager")) is False
