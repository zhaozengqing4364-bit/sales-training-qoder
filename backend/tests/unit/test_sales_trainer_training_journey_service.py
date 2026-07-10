from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.service import BusinessRuleConfigService
from common.db.models import PracticeSession, Scenario, User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerBusinessEtiquetteQuizAttempt,
    SalesTrainerOperationLog,
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
    SalesTrainerRoleplayObservation,
    SalesTrainerUnit,
)
from sales_trainer.regrade_models import SalesTrainerRegradeRun
from sales_trainer.schemas import (
    SalesTrainerTrainingRecordResponse,
    TrainingJourneyResponse,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.learner_unit_access import (
    LearnerUnitAccessError,
    require_learner_active_path_module_access,
    require_learner_active_path_unit_access,
)
from sales_trainer.services.learning_topic_config_service import (
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.readiness_state import (
    READINESS_CONTRACT_VERSION,
    READINESS_DOSSIER_TARGET_TYPE,
    REVIEW_ACTION_CREATED,
)
from sales_trainer.services.training_journey_service import (
    TrainingJourneyError,
    TrainingJourneyService,
)
from sales_trainer.services.training_record_service import TrainingRecordService


def _user(role: str, *, department: str = "销售一部") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"journey-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Journey {role}",
        email=f"journey-{role}-{uuid.uuid4().hex[:8]}@example.com",
        department=department,
        role=role,
        is_active=True,
    )


def _unit(unit_id: str, *, unit_type: str, name: str) -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id=unit_id,
        name=name,
        unit_type=unit_type,
        config={},
        status="published",
    )


def _ready_realtime_binding() -> dict[str, object]:
    return {
        "binding_key": "newcomer_realtime_roleplay_v1",
        "runtime_owner": "training_runtime",
        "runtime_descriptor_id": "newcomer-realtime-runtime",
        "scenario_key": "newcomer-realtime-roleplay",
        "runtime_config_revision_id": "runtime-config-rev-1",
        "provider_readiness_snapshot": {
            "provider": "mock",
            "ready": True,
            "checked_at": "2026-06-27T00:00:00Z",
            "config_revision_id": "runtime-config-rev-1",
        },
        "failure_policy": {
            "terminal_codes": ["CONFIG_INVALID"],
            "transient_codes": ["PROVIDER_TIMEOUT"],
            "voluntary_codes": ["USER_CANCELLED"],
            "terminal_retry_allowed": False,
        },
    }


def _scenario() -> Scenario:
    return Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="新人实时对练",
    )


def _realtime_session(
    learner: User,
    scenario: Scenario,
    *,
    revision_id: str,
    path_revision_no: int = 1,
    module_key: str = "realtime_roleplay",
    owner: str = "sales_trainer",
    started_at: datetime | None = None,
) -> PracticeSession:
    session_started_at = started_at or datetime(2026, 7, 2, 10, 0, tzinfo=UTC)
    return PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="completed",
        start_time=session_started_at,
        end_time=session_started_at,
        voice_policy_snapshot={
            "external_binding": {
                "owner": owner,
                "path_key": "newcomer_training_path_v1",
                "path_revision_id": revision_id,
                "path_revision_no": path_revision_no,
                "module_key": module_key,
                "binding_key": "newcomer_realtime_roleplay_v1",
            }
        },
    )


async def _publish_path(
    test_db: AsyncSession,
    *,
    actor: User,
    audio_unit_id: str,
    quiz_unit_id: str,
    realtime_unit_id: str | None = None,
    realtime_binding: dict[str, object] | None = None,
    business_learner_level_required: list[str] | None = None,
) -> str:
    payload = {
        "path_key": "newcomer_training_path_v1",
        "title": "新人训练路径",
        "enabled": True,
        "modules": [
            {
                "module_key": "ppt_explanation",
                "module_type": "audio_scoring",
                "enabled": True,
                "order_index": 1,
                "title": "PPT 讲解录音",
                "target_unit_id": audio_unit_id,
                "completion_rule": "passed",
            },
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 2,
                "title": "商务技巧",
                "target_unit_id": quiz_unit_id,
                "learning_content_id": "article-journey-1",
                "exam_paper_id": "paper-journey-1",
                "completion_rule": "passed",
                "learner_level_required": business_learner_level_required or [],
                "learning_units": [
                    {
                        "unit_key": "customer-visit-prep",
                        "title": "客户拜访准备",
                        "order_index": 1,
                        "enabled": True,
                        "source_chapter_orders": [1],
                        "capability_keys": ["visit_preparation"],
                        "ai_coach_required_capability_keys": ["visit_preparation"],
                    }
                ],
                "ai_coach": {
                    "enabled": True,
                    "prompt_template_id": "11111111-1111-1111-1111-111111111111",
                    "allowed_interaction_types": ["single_choice", "multiple_choice"],
                    "min_turns": 3,
                    "max_turns": 10,
                    "mastery_threshold": 80,
                },
            },
        ],
    }
    if realtime_binding is not None:
        payload["modules"].append(
            {
                "module_key": "realtime_roleplay",
                "module_type": "realtime_roleplay",
                "enabled": True,
                "order_index": 3,
                "title": "实时对练",
                "completion_rule": "submitted",
                "runtime_binding": realtime_binding,
            }
        )
    elif realtime_unit_id is not None:
        payload["modules"].append(
            {
                "module_key": "realtime_roleplay",
                "module_type": "realtime_placeholder",
                "enabled": False,
                "order_index": 3,
                "title": "实时对练",
                "target_unit_id": realtime_unit_id,
                "disabled_reason": "等待 runtime binding 接入。",
                "completion_rule": "submitted",
            }
        )
    result = await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload,
        actor=actor,
        change_class="semantic",
        reason="发布 Journey 测试路径",
    )
    business_module = payload["modules"][1]
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload={
            "schema_version": "newcomer_learning_topics_v1",
            "topics": [
                {
                    "topic_key": "business_etiquette",
                    "source_module_key": "business_skills",
                    "enabled": business_module["enabled"],
                    "title": "商务礼仪规范",
                    "order_index": 1,
                    "learning_content_id": business_module["learning_content_id"],
                    "learning_units": business_module["learning_units"],
                    "ai_coach": business_module["ai_coach"],
                    "required": False,
                    "blocks_next": False,
                    "score_display_policy": "quiz_attempt_score",
                }
            ],
        },
        actor=actor,
        change_class="binding",
        reason="发布 Journey 测试学习专题",
    )
    await test_db.commit()
    return str(result.revision.revision_id)


def _context(revision_id: str, *, module_key: str) -> dict[str, object]:
    return {
        "path_key": "newcomer_training_path_v1",
        "path_revision_id": revision_id,
        "path_revision_no": 1,
        "module_key": module_key,
        "legacy_snapshot_only": False,
    }


async def _seed_training_records(
    test_db: AsyncSession,
    *,
    learner: User,
    revision_id: str,
    audio_unit_id: str,
    quiz_unit_id: str,
    ai_mastery_state: str = "not_mastered",
    ai_total_score: float = 62,
) -> None:
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="Journey 评分标准",
        purpose="general_audio_scoring",
        system_prompt="评分。",
        scoring_template="评分：{transcript}",
        output_schema={},
        status="published",
        created_by=learner.user_id,
        updated_by=learner.user_id,
    )
    audio = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=audio_unit_id,
        user_id=str(learner.user_id),
        purpose="general_audio_scoring",
        original_filename="journey.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/journey.wav",
        task_brief_snapshot={
            "submission_context": _context(
                revision_id,
                module_key="ppt_explanation",
            )
        },
        status="scored",
    )
    audio_score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=audio.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="journey-hash",
        total_score=88,
        passed=True,
        strengths=[],
        improvements=[],
        dimension_scores={},
    )
    category = QuestionCategory(
        category_id=f"journey-category-{uuid.uuid4().hex[:8]}",
        name="Journey 题目",
        usage_scope="sales_trainer",
    )
    question = QuestionItem(
        question_id=str(uuid.uuid4()),
        category_id=category.category_id,
        title="商务礼仪",
        stem="客户拜访前应做什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "确认目标"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    quiz = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=quiz_unit_id,
        user_id=str(learner.user_id),
        total_score=92,
        max_score=100,
        passed=True,
        status="scored",
    )
    answer = SalesTrainerQuizAnswer(
        answer_id=str(uuid.uuid4()),
        attempt_id=quiz.attempt_id,
        question_id=question.question_id,
        question_type="single_choice",
        answer_payload={
            "value": "A",
            "attempt_context": _context(revision_id, module_key="business_skills"),
        },
        is_correct=True,
        score=100,
    )
    ai_session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        module_key="business_skills",
        path_key="newcomer_training_path_v1",
        path_revision_id=revision_id,
        path_revision_no=1,
        article_snapshot={},
        path_config_snapshot={},
        config_snapshot={},
        coach_state={},
        status="completed",
        mastery_state=ai_mastery_state,
        total_score=ai_total_score,
        max_score=100,
    )
    topic_attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        training_pack_key="business_etiquette_v1",
        learning_unit_key="customer-visit-prep",
        learning_unit_title="客户拜访准备",
        user_id=str(learner.user_id),
        path_revision_id=revision_id,
        path_revision_no=1,
        capability_snapshot={},
        question_snapshots=[],
        answers_snapshot=[],
        capability_scores=[],
        weak_capability_keys=[],
        recommended_chapter_orders=[],
        total_score=92,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
    )
    test_db.add_all(
        [
            prompt,
            audio,
            audio_score,
            category,
            question,
            quiz,
            answer,
            ai_session,
            topic_attempt,
        ]
    )
    await test_db.commit()


async def _publish_learner_level_policy(
    test_db: AsyncSession,
    *,
    actor: User,
) -> None:
    value = {
        "version": "learner_level_policy_test_v1",
        "enabled": True,
        "default_level": {
            "key": "unassigned",
            "label": "未分层",
            "rank": 0,
        },
        "levels": [
            {"key": "unassigned", "label": "未分层", "rank": 0},
            {"key": "ready", "label": "可独立上手", "rank": 10},
            {"key": "needs_coaching", "label": "重点辅导", "rank": 20},
        ],
        "rules": [
            {
                "key": "passed_path",
                "level_key": "ready",
                "priority": 1,
                "enabled": True,
                "conditions": {"training_stage_in": ["passed"], "min_pass_rate": 100},
            },
            {
                "key": "needs_remediation",
                "level_key": "needs_coaching",
                "priority": 2,
                "enabled": True,
                "conditions": {"training_stage_in": ["needs_remediation"]},
            },
        ],
    }
    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key="sales_trainer.learner_level.policy",
        value=value,
        actor_id=str(actor.user_id),
        reason="test learner level policy",
    )
    await service.publish(
        key="sales_trainer.learner_level.policy",
        config_id=str(draft.id),
        actor_id=str(actor.user_id),
        reason="publish test learner level policy",
    )
    await test_db.commit()


async def _publish_role_level_policy(
    test_db: AsyncSession,
    *,
    actor: User,
) -> None:
    value = {
        "version": "role_level_policy_test_v1",
        "enabled": True,
        "default_level": {
            "key": "learner",
            "label": "普通学员",
            "rank": 0,
        },
        "levels": [
            {"key": "learner", "label": "普通学员", "rank": 0},
            {"key": "field_sales", "label": "一线销售", "rank": 10},
        ],
        "rules": [
            {
                "key": "sales_department",
                "level_key": "field_sales",
                "priority": 1,
                "enabled": True,
                "conditions": {"role_in": ["user"], "department_in": ["销售一部"]},
            },
        ],
    }
    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key="sales_trainer.role_level.policy",
        value=value,
        actor_id=str(actor.user_id),
        reason="test role level policy",
    )
    await service.publish(
        key="sales_trainer.role_level.policy",
        config_id=str(draft.id),
        actor_id=str(actor.user_id),
        reason="publish test role level policy",
    )
    await test_db.commit()


@pytest.mark.asyncio
async def test_should_fail_closed_when_active_revision_missing(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    test_db.add(learner)
    await test_db.commit()

    with pytest.raises(TrainingJourneyError) as exc:
        await TrainingJourneyService(test_db).get_learner_journey(
            str(learner.user_id),
            viewer=learner,
        )

    assert exc.value.code == "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]"
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_should_aggregate_audio_quiz_and_ai_coach_from_active_revision(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    realtime_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
            _unit(realtime_unit_id, unit_type="quiz", name="实时占位"),
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        realtime_unit_id=realtime_unit_id,
    )
    await _seed_training_records(
        test_db,
        learner=learner,
        revision_id=revision_id,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    modules = {(item["kind"], item["module_key"]): item for item in journey["modules"]}

    assert journey["source"] == "active_revision"
    assert journey["path_revision_id"] == revision_id
    assert (
        modules[("audio_submission", "ppt_explanation")]["latest_outcome"][
            "record_type"
        ]
        == "audio_submission"
    )
    assert modules[("audio_submission", "ppt_explanation")]["passed"] is True
    assert modules[("audio_submission", "ppt_explanation")]["next_action"] == {
        "action_key": "retry_audio_submission",
        "label": "重新上传录音",
        "target_path": f"/sales-trainer/audio/{audio_unit_id}",
        "disabled": False,
        "disabled_reason": None,
    }
    topics = {item["topic_key"]: item for item in journey["learning_topics"]}
    business_topic = topics["business_etiquette"]
    assert business_topic["source_module_key"] == "business_skills"
    assert business_topic["required"] is False
    assert business_topic["blocks_next"] is False
    assert business_topic["status"] == "passed"
    assert business_topic["learning_content_id"] == "article-journey-1"
    assert business_topic["units"][0]["latest_attempt_id"]
    assert business_topic["units"][0]["score"] == 92.0
    assert business_topic["ai_coach"]["available"] is True
    assert business_topic["ai_coach"]["coach_path"] == (
        "/sales-trainer/business-skills/coach"
    )
    assert not any(module_key == "business_skills" for _, module_key in modules)
    assert journey["training_stage"] == "in_progress"
    realtime_module = modules[("realtime_roleplay", "realtime_roleplay")]
    assert realtime_module["locked"] is True
    assert realtime_module["status"] == "disabled"
    assert (
        realtime_module["diagnostics"][0]["code"]
        == "[NEWCOMER_REALTIME_BINDING_INVALID]"
    )
    assert realtime_module["next_action"] == {
        "action_key": "start_realtime_roleplay",
        "label": "开始实时对练",
        "target_path": None,
        "disabled": True,
        "disabled_reason": "等待 runtime binding 接入。",
    }


@pytest.mark.asyncio
async def test_should_project_readiness_retraining_request_to_learner_journey(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )
    await _seed_training_records(
        test_db,
        learner=learner,
        revision_id=revision_id,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        ai_mastery_state="mastered",
        ai_total_score=90,
    )
    ai_session = await test_db.scalar(
        select(SalesTrainerAiCoachSession).where(
            SalesTrainerAiCoachSession.user_id == str(learner.user_id)
        )
    )
    assert ai_session is not None

    await OperationLogService(test_db).record(
        actor=admin,
        action=REVIEW_ACTION_CREATED,
        target_type=READINESS_DOSSIER_TARGET_TYPE,
        target_id=str(learner.user_id),
        metadata={
            "contract_version": READINESS_CONTRACT_VERSION,
            "decision": "require_retraining",
            "decision_label": "要求重练",
            "reason": "商务礼仪表达还需要再练一次。",
            "capability_keys": ["business_etiquette"],
            "source_evidence_ids": [f"ai_coach_session:{ai_session.session_id}"],
            "retraining_task": {
                "task_id": "retraining-task-1",
                "status": "pending",
                "source": "operation_log",
                "capability_keys": ["business_etiquette"],
                "source_evidence_ids": [f"ai_coach_session:{ai_session.session_id}"],
                "target_learner_id": str(learner.user_id),
            },
            "state_storage": "operation_log",
        },
    )
    await test_db.commit()

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    response = TrainingJourneyResponse.model_validate(journey)

    assert len(response.retraining_requests) == 1
    request = response.retraining_requests[0]
    assert request.reason == "商务礼仪表达还需要再练一次。"
    assert request.capability_labels == ["商务礼仪与职业表达"]
    assert request.source_evidence_count == 1
    assert request.primary_target_path == "/sales-trainer/business-skills/coach"
    assert request.target_modules[0].module_key == "business_skills"
    assert request.target_modules[0].kind == "ai_coach"
    assert (
        request.target_modules[0].target_path == "/sales-trainer/business-skills/coach"
    )

    await OperationLogService(test_db).record(
        actor=admin,
        action=REVIEW_ACTION_CREATED,
        target_type=READINESS_DOSSIER_TARGET_TYPE,
        target_id=str(learner.user_id),
        metadata={
            "contract_version": READINESS_CONTRACT_VERSION,
            "decision": "approve",
            "decision_label": "确认达标",
            "reason": "补练后已确认达标。",
            "capability_keys": ["business_etiquette"],
            "source_evidence_ids": [f"ai_coach_session:{ai_session.session_id}"],
            "retraining_task": None,
            "state_storage": "operation_log",
        },
    )
    await test_db.commit()

    approved_journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    assert approved_journey["retraining_requests"] == []


@pytest.mark.asyncio
async def test_should_fail_closed_realtime_roleplay_until_outcome_projection_is_wired(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        realtime_binding=_ready_realtime_binding(),
    )

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    modules = {(item["kind"], item["module_key"]): item for item in journey["modules"]}
    realtime_module = modules[("realtime_roleplay", "realtime_roleplay")]

    assert journey["path_revision_id"] == revision_id
    assert realtime_module["locked"] is False
    assert realtime_module["status"] == "not_started"
    assert realtime_module["latest_outcome"] is None
    assert realtime_module["next_action"] == {
        "action_key": "start_realtime_roleplay",
        "label": "开始实时对练",
        "target_path": None,
        "disabled": False,
        "disabled_reason": None,
    }


@pytest.mark.asyncio
async def test_should_include_completed_realtime_roleplay_outcome(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        realtime_binding=_ready_realtime_binding(),
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="新人实时对练",
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={
            "external_binding": {
                "owner": "sales_trainer",
                "path_revision_id": revision_id,
                "path_revision_no": 1,
                "module_key": "realtime_roleplay",
                "binding_key": "newcomer_realtime_roleplay_v1",
            }
        },
        effectiveness_snapshot={"summary": "完成实时对练"},
        runtime_state={"final_status": "completed"},
        status="completed",
        logic_score=84,
        accuracy_score=90,
        completeness_score=78,
        start_time=datetime(2026, 6, 27, 9, 0, tzinfo=UTC),
        end_time=datetime(2026, 6, 27, 9, 10, tzinfo=UTC),
    )
    test_db.add_all([scenario, session])
    await test_db.commit()

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    modules = {(item["kind"], item["module_key"]): item for item in journey["modules"]}
    realtime_module = modules[("realtime_roleplay", "realtime_roleplay")]

    assert realtime_module["status"] == "scored"
    assert realtime_module["passed"] is None
    assert realtime_module["completion_satisfied"] is True
    assert (
        realtime_module["latest_outcome"]["record_type"] == "realtime_roleplay_session"
    )
    assert realtime_module["latest_outcome"]["source_record_id"] == session.session_id
    assert realtime_module["latest_outcome"]["score"] == 84
    assert realtime_module["latest_outcome"]["passed"] is None
    assert realtime_module["latest_outcome"]["snapshot_ref"] == {
        "snapshot_type": "runtime_outcome_snapshot",
        "legacy_snapshot_only": False,
        "regrade_unavailable": False,
    }


@pytest.mark.asyncio
async def test_should_mark_journey_passed_when_submitted_realtime_completion_is_satisfied(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        realtime_binding=_ready_realtime_binding(),
    )
    await _seed_training_records(
        test_db,
        learner=learner,
        revision_id=revision_id,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        ai_mastery_state="mastered",
        ai_total_score=90,
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="新人实时对练",
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={
            "external_binding": {
                "owner": "sales_trainer",
                "path_revision_id": revision_id,
                "path_revision_no": 1,
                "module_key": "realtime_roleplay",
                "binding_key": "newcomer_realtime_roleplay_v1",
            }
        },
        effectiveness_snapshot={"summary": "完成实时对练"},
        runtime_state={"final_status": "completed"},
        status="completed",
        logic_score=84,
        accuracy_score=90,
        completeness_score=78,
        start_time=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
        end_time=datetime(2026, 6, 27, 10, 10, tzinfo=UTC),
    )
    test_db.add_all([scenario, session])
    await test_db.commit()

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    modules = {(item["kind"], item["module_key"]): item for item in journey["modules"]}

    assert journey["training_stage"] == "passed"
    assert (
        modules[("audio_submission", "ppt_explanation")]["completion_satisfied"] is True
    )
    assert not any(module_key == "business_skills" for _, module_key in modules)
    business_topic = journey["learning_topics"][0]
    assert business_topic["source_module_key"] == "business_skills"
    assert business_topic["blocks_next"] is False
    assert business_topic["status"] == "passed"
    realtime_module = modules[("realtime_roleplay", "realtime_roleplay")]
    assert realtime_module["status"] == "scored"
    assert realtime_module["passed"] is None
    assert realtime_module["completion_satisfied"] is True
    assert realtime_module["latest_outcome"]["passed"] is None


@pytest.mark.asyncio
async def test_should_include_business_etiquette_quiz_attempt_outcome(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )
    attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        training_pack_key="business_etiquette_v1",
        learning_unit_key="customer-visit-prep",
        learning_unit_title="客户拜访准备",
        user_id=str(learner.user_id),
        path_revision_id=revision_id,
        path_revision_no=None,
        capability_snapshot={},
        question_snapshots=[],
        answers_snapshot=[],
        capability_scores=[],
        weak_capability_keys=[],
        recommended_chapter_orders=[],
        total_score=86,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime(2026, 6, 27, tzinfo=UTC),
    )
    test_db.add(attempt)
    await test_db.commit()

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    business_topic = next(
        item
        for item in journey["learning_topics"]
        if item["topic_key"] == "business_etiquette"
    )

    assert business_topic["source_module_key"] == "business_skills"
    assert business_topic["status"] == "passed"
    assert business_topic["units"][0]["latest_attempt_id"] == attempt.attempt_id
    assert business_topic["units"][0]["score"] == 86.0
    assert business_topic["units"][0]["passed"] is True


@pytest.mark.asyncio
async def test_should_include_audio_group_duration_option_outcome(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="Journey 分组评分标准",
        purpose="general_audio_scoring",
        system_prompt="评分。",
        scoring_template="评分：{transcript}",
        output_schema={},
        status="published",
        created_by=learner.user_id,
        updated_by=learner.user_id,
    )
    unit = _unit(audio_unit_id, unit_type="audio_scoring", name="电梯演讲 3 分钟")
    test_db.add_all([admin, learner, prompt, unit])
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
                    "module_key": "elevator_pitch",
                    "module_type": "audio_scoring_group",
                    "enabled": True,
                    "order_index": 1,
                    "title": "电梯演讲",
                    "completion_rule": "passed",
                    "duration_options": [
                        {
                            "option_key": "pitch_3m",
                            "display_name": "3 分钟",
                            "duration_minutes": 3,
                            "target_unit_id": audio_unit_id,
                            "order_index": 1,
                        }
                    ],
                }
            ],
        },
        actor=admin,
        change_class="semantic",
        reason="发布 Journey 音频分组测试路径",
    )
    await test_db.commit()
    revision_id = str(result.revision.revision_id)
    audio = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=audio_unit_id,
        user_id=str(learner.user_id),
        purpose="general_audio_scoring",
        original_filename="pitch.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/pitch.wav",
        task_brief_snapshot={
            "submission_context": _context(revision_id, module_key="elevator_pitch")
        },
        status="scored",
    )
    score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=audio.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="journey-group-hash",
        total_score=90,
        passed=True,
        strengths=[],
        improvements=[],
        dimension_scores={},
    )
    test_db.add_all([audio, score])
    await test_db.commit()

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    module = journey["modules"][0]

    assert module["module_key"] == "elevator_pitch"
    assert module["latest_outcome"]["record_type"] == "audio_submission"
    assert module["latest_outcome"]["path_revision_no"] == 1
    assert module["passed"] is True


@pytest.mark.asyncio
async def test_should_expose_learner_level_fallback_when_policy_missing(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )

    assert journey["learner_level"]["level_key"] == "unassigned"
    assert journey["learner_level"]["source"] == "training_projection"
    assert journey["learner_level"]["fallback_applied"] is True
    assert journey["learner_level"]["fallback_reason"] == "active_missing"
    assert (
        journey["learner_level"]["policy_key"] == "sales_trainer.learner_level.policy"
    )
    assert journey["learner_level"]["management_entry"] == (
        "/admin/business-rules/sales-trainer-learner-level"
    )
    assert journey["role_level"]["level_key"] == "learner"
    assert journey["role_level"]["label"] == "普通学员"
    assert journey["role_level"]["source"] == "training_projection"
    assert journey["role_level"]["fallback_applied"] is True
    assert journey["role_level"]["fallback_reason"] == "active_missing"
    assert journey["role_level"]["policy_key"] == "sales_trainer.role_level.policy"


@pytest.mark.asyncio
async def test_should_enforce_learner_level_required_in_journey_path_and_unit_access(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        business_learner_level_required=["ready"],
    )

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    business_topic = next(
        topic
        for topic in journey["learning_topics"]
        if topic["source_module_key"] == "business_skills"
    )
    assert journey["learner_level"]["level_key"] == "unassigned"
    assert not any(
        module["module_key"] == "business_skills" for module in journey["modules"]
    )
    assert business_topic["required"] is False
    assert business_topic["blocks_next"] is False
    assert business_topic["status"] == "not_started"

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(
        str(learner.user_id)
    )
    business_level = next(
        level for level in paths[0]["levels"] if level["unit_id"] == quiz_unit_id
    )
    assert business_level["learner_level_required"] == ["ready"]
    assert business_level["locked"] is False

    with pytest.raises(LearnerUnitAccessError) as exc_info:
        await require_learner_active_path_unit_access(
            test_db,
            actor=learner,
            unit_id=quiz_unit_id,
        )
    assert exc_info.value.code == "[SALES_TRAINER_UNIT_NOT_FOUND]"


@pytest.mark.asyncio
async def test_should_reject_non_learner_roles_from_learner_path_gates(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    manager = _user("training_manager")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            manager,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )

    with pytest.raises(LearnerUnitAccessError) as unit_exc:
        await require_learner_active_path_unit_access(
            test_db,
            actor=manager,
            unit_id=audio_unit_id,
        )
    assert unit_exc.value.code == "[NEWCOMER_LEARNER_ROLE_REQUIRED]"
    assert unit_exc.value.status_code == 403

    with pytest.raises(LearnerUnitAccessError) as module_exc:
        await require_learner_active_path_module_access(
            test_db,
            actor=manager,
            module_key="business_skills",
        )
    assert module_exc.value.code == "[NEWCOMER_LEARNER_ROLE_REQUIRED]"
    assert module_exc.value.status_code == 403


@pytest.mark.asyncio
async def test_training_manager_development_team_includes_dev_login_admin(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    publisher = _user("admin", department="总部")
    manager = _user("training_manager", department="新人训练路径")
    learner = _user("user", department="新人训练路径")
    dev_admin = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="dev_wechat_user",
        name="Developer",
        email="dev@example.com",
        department="新人训练路径",
        role="admin",
        is_active=True,
    )
    same_department_admin = _user("admin", department="新人训练路径")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            publisher,
            manager,
            learner,
            dev_admin,
            same_department_admin,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    await _publish_path(
        test_db,
        actor=publisher,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )

    listing = await TrainingJourneyService(test_db).list_admin_journeys(
        viewer=manager,
        team_department="新人训练路径",
        limit=50,
        offset=0,
    )

    learner_ids = {item["learner_id"] for item in listing["items"]}
    assert listing["total"] == 2
    assert str(learner.user_id) in learner_ids
    assert str(dev_admin.user_id) in learner_ids
    assert str(same_department_admin.user_id) not in learner_ids

    monkeypatch.setenv("ENVIRONMENT", "production")
    production_listing = await TrainingJourneyService(test_db).list_admin_journeys(
        viewer=manager,
        team_department="新人训练路径",
        limit=50,
        offset=0,
    )
    assert production_listing["total"] == 1
    assert [item["learner_id"] for item in production_listing["items"]] == [
        str(learner.user_id)
    ]


@pytest.mark.asyncio
async def test_should_apply_configured_learner_level_and_filter_admin_analytics(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    other_learner = _user("user", department="销售一部")
    learner.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    other_learner.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner,
            other_learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )
    await _publish_learner_level_policy(test_db, actor=admin)
    await _publish_role_level_policy(test_db, actor=admin)
    await _seed_training_records(
        test_db,
        learner=learner,
        revision_id=revision_id,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        ai_mastery_state="mastered",
        ai_total_score=90,
    )

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )
    assert journey["training_stage"] == "passed"
    assert journey["learner_level"]["level_key"] == "ready"
    assert journey["learner_level"]["label"] == "可独立上手"
    assert journey["learner_level"]["source"] == "org_rule"
    assert journey["learner_level"]["fallback_applied"] is False
    assert journey["learner_level"]["config_revision_id"]
    assert journey["role_level"]["level_key"] == "field_sales"
    assert journey["role_level"]["label"] == "一线销售"
    assert journey["role_level"]["source"] == "org_rule"
    assert journey["role_level"]["fallback_applied"] is False

    listing = await TrainingJourneyService(test_db).list_admin_journeys(
        viewer=admin,
        team_department=None,
        department="销售一部",
        training_stage="passed",
        module_key="business_skills",
        learner_level="ready",
        role_level="field_sales",
        limit=1,
        offset=0,
    )
    assert listing["total"] == 1
    assert [item["learner_id"] for item in listing["items"]] == [str(learner.user_id)]

    empty_listing = await TrainingJourneyService(test_db).list_admin_journeys(
        viewer=admin,
        team_department=None,
        department="销售一部",
        learner_level="unknown_level",
        limit=20,
        offset=0,
    )
    assert empty_listing["total"] == 0
    assert empty_listing["items"] == []

    role_empty_listing = await TrainingJourneyService(test_db).list_admin_journeys(
        viewer=admin,
        team_department=None,
        department="销售一部",
        role_level="unknown_role",
        limit=20,
        offset=0,
    )
    assert role_empty_listing["total"] == 0
    assert role_empty_listing["items"] == []

    analytics = await TrainingJourneyService(test_db).get_admin_analytics(
        viewer=admin,
        team_department=None,
        department="销售一部",
        training_stage="passed",
        module_key="business_skills",
        learner_level="ready",
        role_level="field_sales",
        limit=1,
    )
    assert analytics["filters"] == {
        "department": "销售一部",
        "training_stage": "passed",
        "module_key": "business_skills",
        "learner_level": "ready",
        "role_level": "field_sales",
        "limit": 1,
    }
    assert analytics["summary"]["loaded_learner_count"] == 1
    assert analytics["module_summaries"] == []
    assert analytics["weakness_heatmap"] == []
    assert analytics["learning_topic_summaries"][0] == {
        "topic_key": "business_etiquette",
        "source_module_key": "business_skills",
        "title": "商务礼仪规范",
        "learner_count": 1,
        "completed_count": 1,
        "needs_remediation_count": 0,
        "status_counts": {"passed": 1},
        "completion_rate": 100.0,
        "average_unit_score": 92.0,
        "blocking_required_path": False,
    }
    assert analytics["learner_level_summaries"] == [
        {
            "key": "ready",
            "label": "可独立上手",
            "learner_count": 1,
            "passed_count": 1,
            "pass_rate": 100.0,
            "source": "org_rule",
        }
    ]
    assert analytics["role_level_summaries"] == [
        {
            "key": "field_sales",
            "label": "一线销售",
            "learner_count": 1,
            "passed_count": 1,
            "pass_rate": 100.0,
            "source": "org_rule",
        }
    ]


@pytest.mark.asyncio
async def test_should_return_empty_additive_observation_block_when_scope_has_no_rows(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    scenario = _scenario()
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
            scenario,
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        realtime_binding=_ready_realtime_binding(),
    )
    session = _realtime_session(
        learner,
        scenario,
        revision_id=revision_id,
    )
    test_db.add(session)
    await test_db.commit()

    analytics = await TrainingJourneyService(test_db).get_admin_analytics(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=10,
    )

    assert analytics["additive_observation"] == {
        "storage_ready": True,
        "migration_applied": True,
        "session_count": 1,
        "observed_session_count": 0,
        "observation_count": 0,
        "source_counts": {"heuristic": 0, "llm_evaluator": 0},
        "status_counts": {
            "pending": 0,
            "completed": 0,
            "failed": 0,
            "ignored": 0,
        },
        "top_signal_keys": [],
        "high_risk_session_count": 0,
        "latest_observed_at": None,
    }


@pytest.mark.asyncio
async def test_should_aggregate_additive_observation_metrics_from_authorized_sessions(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    scenario = _scenario()
    test_db.add_all(
        [
            admin,
            learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
            scenario,
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        realtime_binding=_ready_realtime_binding(),
    )
    session_a = _realtime_session(
        learner,
        scenario,
        revision_id=revision_id,
        started_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
    )
    session_b = _realtime_session(
        learner,
        scenario,
        revision_id=revision_id,
        started_at=datetime(2026, 7, 2, 11, 0, tzinfo=UTC),
    )
    observations = [
        SalesTrainerRoleplayObservation(
            observation_id=str(uuid.uuid4()),
            session_id=session_a.session_id,
            source_record_id=session_a.session_id,
            source="heuristic",
            turn_index=1,
            evaluator_status="completed",
            dimensions_json=[{"key": "capture_context"}],
            signals_json=[
                {"key": "prompt_leak_risk", "severity": "high"},
            ],
            payload_hash="hash-a-1",
            created_at=datetime(2026, 7, 2, 10, 5, tzinfo=UTC),
            updated_at=datetime(2026, 7, 2, 10, 5, tzinfo=UTC),
        ),
        SalesTrainerRoleplayObservation(
            observation_id=str(uuid.uuid4()),
            session_id=session_a.session_id,
            source_record_id=session_a.session_id,
            source="llm_evaluator",
            turn_index=2,
            evaluator_status="failed",
            dimensions_json=[{"key": "evaluation_runtime"}],
            signals_json=[
                {"key": "prompt_leak_risk", "severity": "medium"},
                {"key": "manual_review_required", "severity": "medium"},
            ],
            error_json={"code": "[LLM_EVALUATOR_TIMEOUT]", "message": "timeout"},
            payload_hash="hash-a-2",
            created_at=datetime(2026, 7, 2, 10, 6, tzinfo=UTC),
            updated_at=datetime(2026, 7, 2, 10, 6, tzinfo=UTC),
        ),
        SalesTrainerRoleplayObservation(
            observation_id=str(uuid.uuid4()),
            session_id=session_b.session_id,
            source_record_id=session_b.session_id,
            source="heuristic",
            turn_index=1,
            evaluator_status="completed",
            dimensions_json=[{"key": "capture_context"}],
            signals_json=[
                {"key": "too_many_questions", "severity": "medium"},
            ],
            payload_hash="hash-b-1",
            created_at=datetime(2026, 7, 2, 11, 5, tzinfo=UTC),
            updated_at=datetime(2026, 7, 2, 11, 5, tzinfo=UTC),
        ),
    ]
    test_db.add_all([session_a, session_b, *observations])
    await test_db.commit()

    analytics = await TrainingJourneyService(test_db).get_admin_analytics(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=10,
    )

    additive_observation = analytics["additive_observation"]
    assert additive_observation["storage_ready"] is True
    assert additive_observation["migration_applied"] is True
    assert additive_observation["session_count"] == 2
    assert additive_observation["observed_session_count"] == 2
    assert additive_observation["observation_count"] == 3
    assert additive_observation["source_counts"] == {
        "heuristic": 2,
        "llm_evaluator": 1,
    }
    assert additive_observation["status_counts"] == {
        "pending": 0,
        "completed": 2,
        "failed": 1,
        "ignored": 0,
    }
    assert additive_observation["top_signal_keys"][0] == {
        "key": "prompt_leak_risk",
        "count": 2,
    }
    assert {item["key"] for item in additive_observation["top_signal_keys"][1:]} == {
        "manual_review_required",
        "too_many_questions",
    }
    assert additive_observation["high_risk_session_count"] == 1
    assert additive_observation["latest_observed_at"] == datetime(
        2026, 7, 2, 11, 5, tzinfo=UTC
    )


@pytest.mark.asyncio
async def test_should_limit_additive_observation_metrics_to_department_scope(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    manager = _user("support", department="华东销售")
    same_department_learner = _user("user", department="华东销售")
    other_department_learner = _user("user", department="华北销售")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    scenario = _scenario()
    test_db.add_all(
        [
            admin,
            manager,
            same_department_learner,
            other_department_learner,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
            scenario,
        ]
    )
    await test_db.commit()
    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
        realtime_binding=_ready_realtime_binding(),
    )
    same_department_session = _realtime_session(
        same_department_learner,
        scenario,
        revision_id=revision_id,
        started_at=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
    )
    other_department_session = _realtime_session(
        other_department_learner,
        scenario,
        revision_id=revision_id,
        started_at=datetime(2026, 7, 2, 13, 0, tzinfo=UTC),
    )
    test_db.add_all(
        [
            same_department_session,
            other_department_session,
            SalesTrainerRoleplayObservation(
                observation_id=str(uuid.uuid4()),
                session_id=same_department_session.session_id,
                source_record_id=same_department_session.session_id,
                source="heuristic",
                turn_index=1,
                evaluator_status="completed",
                dimensions_json=[{"key": "capture_context"}],
                signals_json=[{"key": "prompt_leak_risk", "severity": "high"}],
                payload_hash="same-department-hash",
            ),
            SalesTrainerRoleplayObservation(
                observation_id=str(uuid.uuid4()),
                session_id=other_department_session.session_id,
                source_record_id=other_department_session.session_id,
                source="heuristic",
                turn_index=1,
                evaluator_status="completed",
                dimensions_json=[{"key": "capture_context"}],
                signals_json=[{"key": "too_many_questions", "severity": "medium"}],
                payload_hash="other-department-hash",
            ),
        ]
    )
    await test_db.commit()

    analytics = await TrainingJourneyService(test_db).get_admin_analytics(
        viewer=manager,
        team_department="华东销售",
        department=None,
        limit=10,
    )

    assert analytics["summary"]["learner_count"] == 1
    assert analytics["summary"]["loaded_learner_count"] == 1
    assert analytics["additive_observation"]["session_count"] == 1
    assert analytics["additive_observation"]["observed_session_count"] == 1
    assert analytics["additive_observation"]["observation_count"] == 1
    assert analytics["additive_observation"]["source_counts"] == {
        "heuristic": 1,
        "llm_evaluator": 0,
    }
    assert analytics["additive_observation"]["top_signal_keys"] == [
        {"key": "prompt_leak_risk", "count": 1}
    ]


@pytest.mark.asyncio
async def test_training_record_detail_audit_logs_include_journey_level_context(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    audio_unit = _unit(str(uuid.uuid4()), unit_type="audio_scoring", name="PPT 讲解")
    quiz_unit = _unit(str(uuid.uuid4()), unit_type="quiz", name="商务技巧")
    test_db.add_all([admin, learner, audio_unit, quiz_unit])
    await test_db.commit()

    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit.unit_id,
        quiz_unit_id=quiz_unit.unit_id,
    )
    await _publish_learner_level_policy(test_db, actor=admin)
    await _publish_role_level_policy(test_db, actor=admin)

    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=quiz_unit.unit_id,
        user_id=learner.user_id,
        total_score=55,
        max_score=100,
        passed=False,
        status="scored",
        submitted_at=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
    )
    category = QuestionCategory(
        category_id=f"journey-audit-category-{uuid.uuid4().hex[:8]}",
        name="Journey 审计题目",
        usage_scope="sales_trainer",
    )
    question = QuestionItem(
        question_id=str(uuid.uuid4()),
        category_id=category.category_id,
        title="商务技巧审计",
        stem="如何确认客户诉求？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "复述确认"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    answer = SalesTrainerQuizAnswer(
        answer_id=str(uuid.uuid4()),
        attempt_id=attempt.attempt_id,
        question_id=question.question_id,
        question_type="single_choice",
        answer_payload={
            "value": "A",
            "attempt_context": _context(revision_id, module_key="business_skills"),
        },
        is_correct=False,
        score=55,
    )
    log = SalesTrainerOperationLog(
        actor_id=learner.user_id,
        actor_role=learner.role,
        action="sales_trainer_quiz.submitted",
        target_type="sales_trainer_quiz_attempt",
        target_id=attempt.attempt_id,
        request_id="trace-journey-context-audit",
        metadata_json={"unit_id": quiz_unit.unit_id},
    )
    test_db.add_all([category, question, attempt, answer, log])
    await test_db.commit()

    record = await TrainingRecordService(test_db).get_record_for_viewer(
        "quiz_attempt",
        attempt.attempt_id,
        viewer=admin,
        team_department=None,
    )

    assert record is not None
    assert record["training_stage"] == "not_started"
    assert record["learner_level"]["level_key"] == "unassigned"
    assert record["role_level"]["level_key"] == "field_sales"
    assert record["operation_logs"][0]["action"] == "sales_trainer_quiz.submitted"
    context = record["operation_logs"][0]["training_context"]
    assert context["path_key"] == "newcomer_training_path_v1"
    assert context["path_revision_id"] == revision_id
    assert context["path_revision_no"] == 1
    assert context["training_stage"] == "not_started"
    assert context["learner_level"]["level_key"] == "unassigned"
    assert context["role_level"]["level_key"] == "field_sales"
    assert record["operation_logs"][0]["metadata"] == {"unit_id": quiz_unit.unit_id}
    response = SalesTrainerTrainingRecordResponse.model_validate(record)
    assert response.operation_logs[0].training_context is not None
    assert response.operation_logs[0].training_context.training_stage == "not_started"


@pytest.mark.asyncio
async def test_should_ignore_legacy_business_skills_regrade_in_required_journey_history(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    audio_unit = _unit(str(uuid.uuid4()), unit_type="audio_scoring", name="PPT 讲解")
    quiz_unit = _unit(str(uuid.uuid4()), unit_type="quiz", name="商务技巧")
    test_db.add_all([admin, learner, audio_unit, quiz_unit])
    await test_db.commit()

    revision_id = await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit.unit_id,
        quiz_unit_id=quiz_unit.unit_id,
    )
    category = QuestionCategory(
        category_id=f"journey-regrade-category-{uuid.uuid4().hex[:8]}",
        name="Journey 重评题目",
        usage_scope="sales_trainer",
    )
    question = QuestionItem(
        question_id=str(uuid.uuid4()),
        category_id=category.category_id,
        title="商务技巧重评",
        stem="客户拜访前应做什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "确认目标"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=quiz_unit.unit_id,
        user_id=learner.user_id,
        total_score=90,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
    )
    answer = SalesTrainerQuizAnswer(
        answer_id=str(uuid.uuid4()),
        attempt_id=attempt.attempt_id,
        question_id=question.question_id,
        question_type="single_choice",
        answer_payload={
            "value": "A",
            "attempt_context": _context(revision_id, module_key="business_skills"),
        },
        is_correct=True,
        score=90,
    )
    regrade_run = SalesTrainerRegradeRun(
        target_type="quiz_attempt",
        target_id=attempt.attempt_id,
        target_revision_id=None,
        status="completed",
        reason="考卷答案修订后重评",
        impact_scope_json={"record_count": 1, "history_overwrite": False},
        before_snapshot_json={"total_score": 90, "max_score": 100, "passed": True},
        after_snapshot_json={"total_score": 40, "max_score": 100, "passed": False},
        trace_id="trace-journey-regrade",
        created_by=admin.user_id,
        created_at=datetime(2026, 6, 27, 10, 30, tzinfo=UTC),
        completed_at=datetime(2026, 6, 27, 10, 31, tzinfo=UTC),
    )
    test_db.add_all([category, question, attempt, answer, regrade_run])
    await test_db.commit()

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )

    assert not any(
        module["module_key"] == "business_skills" for module in journey["modules"]
    )
    assert journey["training_stage"] == "not_started"
    assert journey["learning_topics"][0]["topic_key"] == "business_etiquette"
    assert journey["learning_topics"][0]["status"] == "not_started"


@pytest.mark.asyncio
async def test_should_apply_analytics_limit_to_loaded_journeys(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    learner_a = _user("user", department="销售一部")
    learner_b = _user("user", department="销售一部")
    learner_c = _user("user", department="销售一部")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner_a,
            learner_b,
            learner_c,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )
    service = TrainingJourneyService(test_db)
    build_calls: list[str] = []
    original_build_journey = service._build_journey

    async def counted_build_journey(*, learner: User, viewer: User):
        build_calls.append(str(learner.user_id))
        return await original_build_journey(learner=learner, viewer=viewer)

    monkeypatch.setattr(service, "_build_journey", counted_build_journey)

    analytics = await service.get_admin_analytics(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=1,
    )

    assert analytics["summary"]["learner_count"] == 3
    assert analytics["summary"]["loaded_learner_count"] == 1
    assert analytics["filters"]["limit"] == 1
    assert analytics["funnel"][0]["learner_count"] == 1
    assert analytics["learner_level_summaries"][0]["learner_count"] == 1
    assert analytics["role_level_summaries"][0]["learner_count"] == 1
    assert len(build_calls) == 1


@pytest.mark.asyncio
async def test_should_apply_analytics_limit_before_journey_filters(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    learner_a = _user("user", department="销售一部")
    learner_b = _user("user", department="销售一部")
    audio_unit_id = str(uuid.uuid4())
    quiz_unit_id = str(uuid.uuid4())
    test_db.add_all(
        [
            admin,
            learner_a,
            learner_b,
            _unit(audio_unit_id, unit_type="audio_scoring", name="PPT 讲解"),
            _unit(quiz_unit_id, unit_type="quiz", name="商务技巧"),
        ]
    )
    await test_db.commit()
    await _publish_path(
        test_db,
        actor=admin,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )
    service = TrainingJourneyService(test_db)
    observed_limits: list[int | None] = []
    original_list_learners = service._list_learners_for_admin

    async def counted_list_learners_for_admin(
        *,
        team_department: str | None,
        department: str | None,
        limit: int | None = None,
    ):
        observed_limits.append(limit)
        return await original_list_learners(
            team_department=team_department,
            department=department,
            limit=limit,
        )

    monkeypatch.setattr(
        service,
        "_list_learners_for_admin",
        counted_list_learners_for_admin,
    )

    analytics = await service.get_admin_analytics(
        viewer=admin,
        team_department=None,
        department="销售一部",
        learner_level="novice",
        limit=1,
    )

    assert observed_limits == [1]
    assert analytics["filters"]["learner_level"] == "novice"
    assert analytics["summary"]["loaded_learner_count"] <= 1
