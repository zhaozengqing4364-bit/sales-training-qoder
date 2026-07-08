from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAssetActiveRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerBusinessEtiquetteQuizAttempt,
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.schemas import ReadinessDossierResponse, ReadinessWorkbenchResponse
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.learning_topic_config_service import (
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.readiness_dossier_service import (
    ReadinessDossierError,
    ReadinessDossierService,
)


def _user(role: str, *, department: str = "销售一部") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"readiness-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Readiness {role}",
        email=f"readiness-{role}-{uuid.uuid4().hex[:8]}@example.com",
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


def _realtime_binding(*, ready: bool = True) -> dict[str, object]:
    failure = (
        {}
        if ready
        else {
            "failure_code": "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]",
            "failure_message": "测试 provider 未就绪。",
        }
    )
    return {
        "binding_key": "newcomer_realtime_roleplay_v1",
        "runtime_owner": "training_runtime",
        "runtime_descriptor_id": "newcomer-realtime-runtime",
        "scenario_key": "newcomer-realtime-roleplay",
        "runtime_config_revision_id": "runtime-config-rev-1",
        "provider_readiness_snapshot": {
            "provider": "mock",
            "ready": ready,
            "checked_at": "2026-07-06T00:00:00Z",
            "config_revision_id": "runtime-config-rev-1",
            **failure,
        },
        "failure_policy": {
            "terminal_codes": ["CONFIG_INVALID"],
            "transient_codes": ["PROVIDER_TIMEOUT"],
            "voluntary_codes": ["USER_CANCELLED"],
            "terminal_retry_allowed": False,
        },
    }


async def _publish_path(
    test_db: AsyncSession,
    *,
    actor: User,
    audio_unit_id: str,
    quiz_unit_id: str,
    realtime_binding: dict[str, object] | None = None,
    audio_capability_keys: list[str] | None = None,
    quiz_capability_keys: list[str] | None = None,
) -> str:
    modules: list[dict[str, object]] = [
        {
            "module_key": "ppt_explanation",
            "module_type": "audio_scoring",
            "enabled": True,
            "order_index": 1,
            "title": "PPT 讲解录音",
            "target_unit_id": audio_unit_id,
            "capability_keys": audio_capability_keys
            or [
                "expression_clarity",
                "structured_presentation",
                "product_understanding",
            ],
            "completion_rule": "passed",
        },
        {
            "module_key": "business_skills",
            "module_type": "article_exam",
            "enabled": True,
            "order_index": 2,
            "title": "商务技巧",
            "target_unit_id": quiz_unit_id,
            "capability_keys": quiz_capability_keys
            or [
                "business_etiquette",
                "customer_perspective",
                "needs_discovery",
            ],
            "learning_content_id": "article-readiness-1",
            "exam_paper_id": "paper-readiness-1",
            "completion_rule": "passed",
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
    ]
    if realtime_binding is not None:
        modules.append(
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
    result = await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": "newcomer_training_path_v1",
            "title": "新人训练路径",
            "enabled": True,
            "modules": modules,
        },
        actor=actor,
        change_class="semantic",
        reason="发布达标档案测试路径",
    )
    business_module = modules[1]
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
        reason="发布达标档案测试学习专题",
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


async def _seed_passed_training_records(
    test_db: AsyncSession,
    *,
    learner: User,
    revision_id: str,
    audio_unit_id: str,
    quiz_unit_id: str,
) -> None:
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="达标档案评分标准",
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
        original_filename="readiness.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/readiness.wav",
        task_brief_snapshot={
            "title": "PPT 讲解",
            "submission_context": _context(
                revision_id,
                module_key="ppt_explanation",
            ),
        },
        status="scored",
    )
    audio_score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=audio.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="readiness-audio-hash",
        total_score=88,
        passed=True,
        strengths=[],
        improvements=[],
        dimension_scores={},
    )
    category = QuestionCategory(
        category_id=f"readiness-category-{uuid.uuid4().hex[:8]}",
        name="达标档案题目",
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
        submitted_at=datetime(2026, 7, 6, 9, 10, tzinfo=UTC),
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
        mastery_state="mastered",
        total_score=90,
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
        submitted_at=datetime(2026, 7, 6, 9, 10, tzinfo=UTC),
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


async def _seed_business_skills_quiz_attempt(
    test_db: AsyncSession,
    *,
    learner: User,
    revision_id: str,
    quiz_unit_id: str,
    submitted_at: datetime,
    passed: bool,
    score: float,
) -> str:
    category = QuestionCategory(
        category_id=f"readiness-retraining-category-{uuid.uuid4().hex[:8]}",
        name="达标档案重练题目",
        usage_scope="sales_trainer",
    )
    question = QuestionItem(
        question_id=str(uuid.uuid4()),
        category_id=category.category_id,
        title="商务礼仪重练",
        stem="客户拜访后如何跟进？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "复盘并确认下一步"}],
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
        total_score=score,
        max_score=100,
        passed=passed,
        status="scored",
        submitted_at=submitted_at,
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
        is_correct=passed,
        score=score,
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
        total_score=score,
        max_score=100,
        passed=passed,
        status="scored",
        submitted_at=submitted_at,
    )
    test_db.add_all([category, question, quiz, answer, topic_attempt])
    await test_db.commit()
    return str(topic_attempt.attempt_id)


async def _seed_ready_learner(
    test_db: AsyncSession,
    *,
    realtime_ready: bool = True,
    audio_capability_keys: list[str] | None = None,
    quiz_capability_keys: list[str] | None = None,
) -> tuple[User, User, str, str]:
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
        realtime_binding=_realtime_binding(ready=realtime_ready),
        audio_capability_keys=audio_capability_keys,
        quiz_capability_keys=quiz_capability_keys,
    )
    await _seed_passed_training_records(
        test_db,
        learner=learner,
        revision_id=revision_id,
        audio_unit_id=audio_unit_id,
        quiz_unit_id=quiz_unit_id,
    )
    return admin, learner, revision_id, quiz_unit_id


@pytest.mark.asyncio
async def test_should_mark_passed_pre_realtime_modules_as_pending_review(
    test_db: AsyncSession,
) -> None:
    admin, learner, _, _ = await _seed_ready_learner(test_db, realtime_ready=False)

    dossier = await ReadinessDossierService(test_db).get_dossier(
        str(learner.user_id),
        viewer=admin,
        team_department=None,
    )

    response = ReadinessDossierResponse.model_validate(dossier)
    assert response.status == "pending_review"
    assert response.summary.evidence_count >= 2
    assert response.realtime_gate.locked is True
    assert response.realtime_gate.reason == "前置训练尚未由培训负责人确认达标。"
    assert all(item.status != "blocked_by_config" for item in response.competencies)


@pytest.mark.asyncio
async def test_should_approve_dossier_and_open_ready_realtime_gate(
    test_db: AsyncSession,
) -> None:
    admin, learner, _, _ = await _seed_ready_learner(test_db, realtime_ready=True)
    service = ReadinessDossierService(test_db)

    action = await service.create_review_action(
        str(learner.user_id),
        actor=admin,
        team_department=None,
        decision="approve",
        reason="证据完整，准许进入真实语音对练。",
    )
    dossier = await service.get_dossier(
        str(learner.user_id),
        viewer=admin,
        team_department=None,
    )

    response = ReadinessDossierResponse.model_validate(dossier)
    assert action["decision"] == "approve"
    assert response.status == "approved"
    assert response.latest_review_action is not None
    assert response.latest_review_action.decision == "approve"
    assert response.realtime_gate.locked is False


@pytest.mark.asyncio
async def test_should_not_approve_before_required_training_is_pending_review(
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
        realtime_binding=_realtime_binding(ready=True),
    )

    with pytest.raises(ReadinessDossierError) as error:
        await ReadinessDossierService(test_db).create_review_action(
            str(learner.user_id),
            actor=admin,
            team_department=None,
            decision="approve",
            reason="未完成训练时不能确认达标。",
        )

    assert error.value.code == "[READINESS_DOSSIER_NOT_READY]"
    assert error.value.status_code == 409
    assert error.value.details["required_status"] == "pending_review"
    assert error.value.details["evidence_count"] == 0


@pytest.mark.asyncio
async def test_should_use_configured_module_capability_keys_for_readiness_mapping(
    test_db: AsyncSession,
) -> None:
    admin, learner, _, _ = await _seed_ready_learner(
        test_db,
        realtime_ready=True,
        audio_capability_keys=["objection_handling"],
        quiz_capability_keys=["business_etiquette"],
    )

    dossier = await ReadinessDossierService(test_db).get_dossier(
        str(learner.user_id),
        viewer=admin,
        team_department=None,
    )
    response = ReadinessDossierResponse.model_validate(dossier)
    audio_evidence = next(
        item
        for item in response.evidence
        if item.module_key == "ppt_explanation"
    )
    objection = next(
        item
        for item in response.competencies
        if item.capability_key == "objection_handling"
    )

    assert audio_evidence.capability_keys == ["objection_handling"]
    assert objection.status == "ai_passed"


@pytest.mark.asyncio
async def test_should_group_retraining_review_actions_in_workbench(
    test_db: AsyncSession,
) -> None:
    admin, learner, _, _ = await _seed_ready_learner(test_db, realtime_ready=True)
    service = ReadinessDossierService(test_db)

    await service.create_review_action(
        str(learner.user_id),
        actor=admin,
        team_department=None,
        decision="require_retraining",
        reason="商务礼仪表达仍需重练。",
        capability_keys=["business_etiquette"],
    )
    workbench = await service.list_workbench(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=10,
        offset=0,
    )
    dossier = await service.get_dossier(
        str(learner.user_id),
        viewer=admin,
        team_department=None,
    )

    workbench_response = ReadinessWorkbenchResponse.model_validate(workbench)
    dossier_response = ReadinessDossierResponse.model_validate(dossier)
    assert workbench_response.summary.needs_retraining_count == 1
    assert workbench_response.groups["needs_retraining"].items[
        0
    ].learner.learner_id == (str(learner.user_id))
    assert dossier_response.retraining_tasks
    assert (
        next(
            item
            for item in dossier_response.competencies
            if item.capability_key == "business_etiquette"
        ).status
        == "needs_retraining"
    )


@pytest.mark.asyncio
async def test_should_group_manual_follow_up_review_actions_as_not_passed(
    test_db: AsyncSession,
) -> None:
    admin, learner, _, _ = await _seed_ready_learner(test_db, realtime_ready=True)
    service = ReadinessDossierService(test_db)

    await service.create_review_action(
        str(learner.user_id),
        actor=admin,
        team_department=None,
        decision="mark_manual_follow_up",
        reason="需要主管单独跟进表达稳定性。",
        capability_keys=["expression_clarity"],
    )
    dossier = await service.get_dossier(
        str(learner.user_id),
        viewer=admin,
        team_department=None,
    )
    workbench = await service.list_workbench(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=10,
        offset=0,
    )

    dossier_response = ReadinessDossierResponse.model_validate(dossier)
    workbench_response = ReadinessWorkbenchResponse.model_validate(workbench)
    assert dossier_response.status == "manual_follow_up"
    assert dossier_response.latest_review_action is not None
    assert dossier_response.latest_review_action.decision == "mark_manual_follow_up"
    assert workbench_response.summary.not_passed_count == 1
    assert workbench_response.groups["not_passed"].items[0].status == (
        "manual_follow_up"
    )


@pytest.mark.asyncio
async def test_should_return_retraining_to_pending_review_after_new_submission(
    test_db: AsyncSession,
) -> None:
    admin, learner, revision_id, quiz_unit_id = await _seed_ready_learner(
        test_db,
        realtime_ready=True,
    )
    service = ReadinessDossierService(test_db)

    await service.create_review_action(
        str(learner.user_id),
        actor=admin,
        team_department=None,
        decision="require_retraining",
        reason="商务礼仪表达仍需重练。",
        capability_keys=["business_etiquette"],
    )
    await _seed_business_skills_quiz_attempt(
        test_db,
        learner=learner,
        revision_id=revision_id,
        quiz_unit_id=quiz_unit_id,
        submitted_at=datetime.now(UTC),
        passed=True,
        score=96,
    )

    dossier = await service.get_dossier(
        str(learner.user_id),
        viewer=admin,
        team_department=None,
    )
    workbench = await service.list_workbench(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=10,
        offset=0,
    )

    dossier_response = ReadinessDossierResponse.model_validate(dossier)
    workbench_response = ReadinessWorkbenchResponse.model_validate(workbench)
    assert dossier_response.status == "pending_review"
    assert dossier_response.summary.retraining_task_count == 1
    assert dossier_response.summary.completed_retraining_task_count == 1
    retraining_task = dossier_response.retraining_tasks[0]
    assert retraining_task.status == "completed"
    assert retraining_task.completed_evidence_ids
    assert retraining_task.comparison is not None
    assert retraining_task.comparison.after_passed is True
    assert workbench_response.summary.needs_retraining_count == 0
    assert workbench_response.summary.pending_review_count == 1
    assert workbench_response.groups["pending_review"].items[0].status == (
        "pending_review"
    )
    assert workbench_response.groups["pending_review"].items[0].evidence_count >= 2


@pytest.mark.asyncio
async def test_should_reject_review_action_with_unknown_evidence_or_capability(
    test_db: AsyncSession,
) -> None:
    admin, learner, _, _ = await _seed_ready_learner(test_db, realtime_ready=True)
    service = ReadinessDossierService(test_db)

    with pytest.raises(ReadinessDossierError) as capability_error:
        await service.create_review_action(
            str(learner.user_id),
            actor=admin,
            team_department=None,
            decision="require_retraining",
            reason="能力项不在系统模型中。",
            capability_keys=["made_up_capability"],
        )
    assert capability_error.value.code == "[READINESS_DOSSIER_CAPABILITY_INVALID]"

    with pytest.raises(ReadinessDossierError) as evidence_error:
        await service.create_review_action(
            str(learner.user_id),
            actor=admin,
            team_department=None,
            decision="require_retraining",
            reason="证据不属于当前档案。",
            source_evidence_ids=["audio_submission:not-visible"],
        )
    assert evidence_error.value.code == "[READINESS_DOSSIER_EVIDENCE_INVALID]"


@pytest.mark.asyncio
async def test_should_not_approve_when_path_config_is_blocked(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()

    with pytest.raises(ReadinessDossierError) as error:
        await ReadinessDossierService(test_db).create_review_action(
            str(learner.user_id),
            actor=admin,
            team_department=None,
            decision="approve",
            reason="配置异常时不能确认达标。",
        )
    assert error.value.code == "[READINESS_DOSSIER_CONFIG_BLOCKED]"
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_should_surface_config_exception_even_when_previous_review_approved(
    test_db: AsyncSession,
) -> None:
    admin, learner, _, _ = await _seed_ready_learner(test_db, realtime_ready=True)
    service = ReadinessDossierService(test_db)

    await service.create_review_action(
        str(learner.user_id),
        actor=admin,
        team_department=None,
        decision="approve",
        reason="当前证据完整，准许进入真实语音对练。",
    )
    await test_db.execute(
        delete(SalesTrainerAssetActiveRevision).where(
            SalesTrainerAssetActiveRevision.resource_type
            == NEWCOMER_PATH_RESOURCE_TYPE,
            SalesTrainerAssetActiveRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
        )
    )
    await test_db.commit()

    dossier = await service.get_dossier(
        str(learner.user_id),
        viewer=admin,
        team_department=None,
    )
    workbench = await service.list_workbench(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=10,
        offset=0,
    )

    dossier_response = ReadinessDossierResponse.model_validate(dossier)
    workbench_response = ReadinessWorkbenchResponse.model_validate(workbench)
    assert dossier_response.status == "blocked_by_config"
    assert all(
        item.status == "blocked_by_config" for item in dossier_response.competencies
    )
    assert workbench_response.summary.config_exception_count == 1
    assert workbench_response.groups["config_exception"].items[0].status == (
        "blocked_by_config"
    )


@pytest.mark.asyncio
async def test_should_surface_config_exception_when_active_revision_missing(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()

    workbench = await ReadinessDossierService(test_db).list_workbench(
        viewer=admin,
        team_department=None,
        department="销售一部",
        limit=10,
        offset=0,
    )

    response = ReadinessWorkbenchResponse.model_validate(workbench)
    assert response.summary.config_exception_count == 1
    assert response.groups["config_exception"].items[0].status == "blocked_by_config"
