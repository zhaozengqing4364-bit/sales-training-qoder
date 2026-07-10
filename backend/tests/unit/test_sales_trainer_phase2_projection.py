from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, get_args

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
    get_business_rule_definition,
    get_default_business_rule_value,
)
from common.db.models import BusinessRuleConfig, PracticeSession, Scenario, User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAssetRevision,
    SalesTrainerBusinessEtiquetteQuizAttempt,
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.regrade_models import SalesTrainerRegradeRun
from sales_trainer.schemas import (
    NEWCOMER_COMPLETION_RULE_COMPATIBILITY,
    NewcomerPathCompletionRule,
    SalesTrainerManagerDashboardResponse,
    SalesTrainerPathConfig,
    SalesTrainerTrainingRecordResponse,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.phase2_dashboard_service import (
    SalesTrainerPhase2DashboardService,
)
from sales_trainer.services.phase2_policy import resolve_phase2_policy
from sales_trainer.services.training_record_service import TrainingRecordService


def _phase2_config(
    value: dict[str, Any],
    *,
    status: str = "published",
    version: int = 1,
    actor_id: str | None = None,
) -> BusinessRuleConfig:
    definition = get_business_rule_definition(
        SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY
    )
    return BusinessRuleConfig(
        domain=definition.domain,
        key=definition.key,
        schema_version=definition.schema_version,
        status=status,
        version=version,
        value_json=value,
        default_value_json=get_default_business_rule_value(definition.key),
        type=definition.type,
        range_or_allowlist_json=definition.range_or_allowlist,
        read_path=definition.read_path,
        admin_entry=definition.admin_entry,
        permission=definition.permission,
        audit_policy=definition.audit_policy,
        fallback_policy=definition.fallback_policy,
        rollback_policy=definition.rollback_policy,
        enabled=value.get("enabled") is not False,
        validation_errors_json=[],
        created_by=actor_id,
        updated_by=actor_id,
    )


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"phase2-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Phase2 {role}",
        email=f"phase2-{role}-{uuid.uuid4().hex[:8]}@example.com",
        department="销售一部",
        role=role,
    )


def test_training_record_snapshot_dtos_keep_legacy_replay_fields() -> None:
    response = SalesTrainerTrainingRecordResponse.model_validate(
        {
            "record_id": "audio-legacy-snapshot",
            "record_type": "audio_submission",
            "unit_id": "unit-1",
            "unit_type": "audio_scoring",
            "user_id": "user-1",
            "status": "uploaded",
            "material_snapshot": {
                "version": 1,
                "items": [{"material_id": "material-legacy"}],
                "confirmed_material_version_id": "material-version-legacy",
                "legacy_material_field": "still-readable",
            },
            "score_scheme_snapshot": {
                "prompt_id": "prompt-legacy",
                "learner_rubric": {"criteria": []},
                "pass_threshold": 70,
                "prompt_snapshot": {
                    "prompt_id": "prompt-legacy",
                    "name": "历史 Prompt",
                    "scoring_template": "历史评分模板",
                    "output_schema": {},
                    "learner_rubric": {},
                    "version": 4,
                    "legacy_prompt_field": "kept",
                },
                "legacy_scheme_field": True,
            },
            "task_brief_snapshot": {
                "title": "历史任务",
                "instructions": [],
                "success_criteria": [],
                "common_mistakes": [],
                "legacy_snapshot_only": True,
                "legacy_brief_field": {"source": "old-json"},
            },
            "audio_submission": None,
            "quiz_attempt": None,
        }
    )

    assert response.material_snapshot is not None
    assert response.material_snapshot.confirmed_material_version_id == (
        "material-version-legacy"
    )
    assert response.material_snapshot.model_extra is not None
    assert response.material_snapshot.model_extra["legacy_material_field"] == (
        "still-readable"
    )
    assert response.score_scheme_snapshot is not None
    assert response.score_scheme_snapshot.prompt_snapshot is not None
    assert response.score_scheme_snapshot.prompt_snapshot.scoring_template == (
        "历史评分模板"
    )
    assert response.score_scheme_snapshot.prompt_snapshot.model_extra is not None
    assert (
        response.score_scheme_snapshot.prompt_snapshot.model_extra[
            "legacy_prompt_field"
        ]
        == "kept"
    )
    assert response.task_brief_snapshot is not None
    assert response.task_brief_snapshot.title == "历史任务"
    assert response.task_brief_snapshot.model_extra is not None
    assert response.task_brief_snapshot.model_extra["legacy_brief_field"] == {
        "source": "old-json"
    }


async def _publish_phase2_business_path(
    test_db: AsyncSession,
    *,
    actor: User,
    quiz_unit_id: str,
) -> str:
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
                    "target_unit_id": quiz_unit_id,
                    "completion_rule": "passed",
                    "learning_units": [
                        {
                            "unit_key": "trust_opening",
                            "title": "建立信任",
                            "order_index": 1,
                            "enabled": True,
                            "source_chapter_orders": [1],
                            "capability_keys": ["business_etiquette_trust"],
                            "ai_coach_required_capability_keys": [
                                "business_etiquette_trust"
                            ],
                        }
                    ],
                    "ai_coach": {
                        "enabled": True,
                        "prompt_template_id": "11111111-1111-1111-1111-111111111111",
                        "allowed_interaction_types": ["single_choice"],
                        "min_turns": 1,
                        "max_turns": 5,
                        "mastery_threshold": 80,
                    },
                }
            ],
        },
        actor=actor,
        change_class="semantic",
        reason="phase2 training-record filter test",
    )
    await test_db.commit()
    return str(result.revision.revision_id)


def test_newcomer_completion_rule_contract_pins_legacy_wire_values() -> None:
    allowed_rules = set(get_args(NewcomerPathCompletionRule))

    assert allowed_rules == {"passed", "scored", "submitted"}
    assert dict(NEWCOMER_COMPLETION_RULE_COMPATIBILITY) == {
        "audio_scored": "scored",
        "paper_passed": "passed",
        "all_audio_options_scored": "scored",
        "placeholder_disabled": "submitted",
    }

    for completion_rule in allowed_rules:
        config = SalesTrainerPathConfig(completion_rule=completion_rule)
        assert config.completion_rule == completion_rule

    for canonical_rule in NEWCOMER_COMPLETION_RULE_COMPATIBILITY:
        with pytest.raises(ValidationError):
            SalesTrainerPathConfig(completion_rule=canonical_rule)


@pytest.mark.asyncio
async def test_training_record_projection_uses_append_only_regrade_as_effective_score(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="商务技巧考卷",
        unit_type="quiz",
        config={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    category = QuestionCategory(
        category_id=str(uuid.uuid4()),
        name="阶段 2 闭环",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = QuestionItem(
        question_id=str(uuid.uuid4()),
        category_id=category.category_id,
        title="价值表达",
        stem="如何解释产品价值？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "客户价值"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["value_expression"],
        status="published",
        usage_scope="sales_trainer",
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
    answer = SalesTrainerQuizAnswer(
        answer_id=str(uuid.uuid4()),
        attempt_id=attempt.attempt_id,
        question_id=question.question_id,
        question_type="single_choice",
        answer_payload={
            "value": "A",
            "question_snapshot": {
                "question_id": question.question_id,
                "title": question.title,
                "stem": question.stem,
                "question_type": "single_choice",
                "correct_answer": "A",
                "scoring_dimensions": ["value_expression"],
                "points": 100,
            },
            "scoring": {
                "is_correct": True,
                "score": 90,
                "normalized_score": 90,
                "feedback": "原始版本判为通过。",
            },
        },
        is_correct=True,
        score=90,
    )
    regrade_run = SalesTrainerRegradeRun(
        target_type="quiz_attempt",
        target_id=attempt.attempt_id,
        target_revision_id=None,
        status="completed",
        reason="考卷正确答案修订后重新评估",
        impact_scope_json={"record_count": 1, "history_overwrite": False},
        before_snapshot_json={"total_score": 90, "max_score": 100, "passed": True},
        after_snapshot_json={
            "total_score": 40,
            "max_score": 100,
            "passed": False,
            "answers": [
                {
                    "question_id": question.question_id,
                    "question_type": "single_choice",
                    "answer_payload": {"value": "A"},
                    "is_correct": False,
                    "score": 40,
                    "question_snapshot": {
                        "question_id": question.question_id,
                        "title": question.title,
                        "stem": question.stem,
                        "question_type": "single_choice",
                        "correct_answer": "B",
                        "scoring_dimensions": ["value_expression"],
                        "points": 100,
                    },
                },
            ],
        },
        trace_id="trace-phase2-regrade",
        created_by=admin.user_id,
    )
    test_db.add_all(
        [
            admin,
            learner,
            unit,
            category,
            question,
            attempt,
            answer,
            regrade_run,
        ]
    )
    await test_db.commit()

    records, total = await TrainingRecordService(test_db).list_records(limit=50)

    assert total == 1
    record = records[0]
    assert record["score"] == 90
    assert record["passed"] is True
    assert record["effective_score"]["source"] == "latest_regrade"
    assert record["effective_score"]["score"] == 40
    assert record["effective_score"]["passed"] is False
    assert record["effective_score"]["original_score"] == 90
    assert record["effective_score"]["score_delta"] == -50
    assert record["effective_score"]["history_overwrite"] is False
    assert record["latest_regrade"]["regrade_run_id"] == regrade_run.run_id
    assert record["ability_profile"]["weak_dimensions"][0]["key"] == "value_expression"
    assert record["remediation"]["needed"] is True
    response = SalesTrainerTrainingRecordResponse.model_validate(record)
    assert response.effective_score is not None
    assert response.effective_score.source == "latest_regrade"
    assert response.effective_score.score == 40
    assert response.latest_regrade is not None
    assert response.latest_regrade.regrade_run_id == regrade_run.run_id
    assert response.score_explanation is not None
    assert response.score_explanation.issues[0].type == "incorrect_answer"
    assert response.ability_profile is not None
    assert response.ability_profile.weak_dimensions[0].key == "value_expression"
    assert response.remediation is not None
    assert response.remediation.needed is True

    preserved_attempt = await test_db.get(SalesTrainerQuizAttempt, attempt.attempt_id)
    assert float(preserved_attempt.total_score) == 90
    assert preserved_attempt.passed is True


@pytest.mark.asyncio
async def test_manager_dashboard_uses_same_phase2_projection(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="quiz",
        config={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
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
    regrade_run = SalesTrainerRegradeRun(
        target_type="quiz_attempt",
        target_id=attempt.attempt_id,
        target_revision_id=None,
        status="completed",
        reason="阶段 2 看板使用有效分",
        impact_scope_json={"record_count": 1, "history_overwrite": False},
        before_snapshot_json={"total_score": 90, "max_score": 100, "passed": True},
        after_snapshot_json={"total_score": 40, "max_score": 100, "passed": False},
        trace_id="trace-dashboard-effective-score",
        created_by=admin.user_id,
    )
    test_db.add_all([admin, learner, unit, attempt, regrade_run])
    await test_db.commit()

    dashboard = await SalesTrainerPhase2DashboardService(test_db).get_dashboard(
        team_department=None,
    )

    assert dashboard["summary"]["record_count"] == 1
    assert dashboard["summary"]["low_score_record_count"] == 1
    assert dashboard["summary"]["pass_rate"] == 0
    assert dashboard["risk_learners"][0]["user_id"] == learner.user_id
    assert dashboard["intervention_suggestions"][0]["action"] == "打回并安排补救训练"
    response = SalesTrainerManagerDashboardResponse.model_validate(dashboard)
    assert response.policy.key == SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY
    assert (
        response.policy.management_entry == "/admin/business-rules/sales-trainer-phase2"
    )
    assert (
        response.policy.dashboard_record_limit >= response.summary.loaded_record_count
    )
    assert response.summary.low_score_record_count == 1
    assert response.module_summaries[0].module_key == unit.unit_id
    assert response.risk_learners[0].user_id == learner.user_id
    assert response.risk_learners[0].priority == "high"
    assert response.intervention_suggestions[0].reason_codes == [
        "low_score",
        "not_passed",
    ]


def test_manager_dashboard_policy_contract_rejects_malformed_payload() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SalesTrainerManagerDashboardResponse.model_validate(
            {
                "generated_at": datetime(2026, 6, 29, tzinfo=UTC),
                "policy": {
                    "low_score_threshold": 70,
                    "repeat_practice_threshold": 2,
                },
                "summary": {
                    "record_count": 0,
                    "loaded_record_count": 0,
                    "learner_count": 0,
                    "completed_record_count": 0,
                    "low_score_record_count": 0,
                    "repeat_practice_learner_count": 0,
                },
                "module_summaries": [],
                "weak_dimensions": [],
                "risk_learners": [],
                "intervention_suggestions": [],
            }
        )

    errors = exc_info.value.errors()
    missing_fields = {
        ".".join(str(part) for part in error["loc"])
        for error in errors
        if error["type"] == "missing"
    }
    assert "policy.key" in missing_fields
    assert "policy.dashboard_record_limit" in missing_fields
    assert "policy.fallback_applied" in missing_fields


@pytest.mark.asyncio
async def test_ai_coach_in_progress_record_requires_continuation(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        module_key="business_skills",
        status="in_progress",
        mastery_state=None,
        trace_id="trace-ai-coach-phase2",
    )
    test_db.add_all([learner, session])
    await test_db.commit()

    records, total = await TrainingRecordService(test_db).list_records(limit=50)

    assert total == 1
    assert records[0]["record_type"] == "ai_coach_session"
    assert records[0]["remediation"]["needed"] is True
    assert records[0]["remediation"]["action_label"] == "继续 AI 教练训练"
    assert records[0]["remediation"]["target_path"] == (
        "/sales-trainer/business-skills/coach"
    )


@pytest.mark.asyncio
async def test_ai_coach_not_mastered_record_projects_remediation_and_snapshot(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    path_revision_id = str(uuid.uuid4())
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        module_key="business_skills",
        path_key="newcomer_training_path_v1",
        path_revision_id=path_revision_id,
        path_revision_no=5,
        article_snapshot={"title": "商务礼仪"},
        path_config_snapshot={
            "path_key": "newcomer_training_path_v1",
            "path_revision_id": path_revision_id,
            "path_revision_no": 5,
            "module_key": "business_skills",
            "legacy_snapshot_only": False,
        },
        config_snapshot={"mastery_threshold": 80},
        coach_state={"last_action": "remediate"},
        status="completed",
        mastery_state="not_mastered",
        total_score=61,
        max_score=100,
        trace_id="trace-ai-coach-not-mastered",
    )
    test_db.add_all([learner, session])
    await test_db.commit()

    records, total = await TrainingRecordService(test_db).list_records(
        user_id=learner.user_id,
        limit=50,
    )

    assert total == 1
    record = records[0]
    assert record["record_type"] == "ai_coach_session"
    assert record["passed"] is False
    assert record["path_key"] == "newcomer_training_path_v1"
    assert record["path_revision_id"] == path_revision_id
    assert record["legacy_snapshot_only"] is False
    assert record["ai_coach_session"]["session_id"] == session.session_id
    assert record["ai_coach_session"]["mastery_state"] == "not_mastered"
    assert record["ai_coach_session"]["article_snapshot"]["title"] == "商务礼仪"
    response = SalesTrainerTrainingRecordResponse.model_validate(record)
    assert response.ai_coach_session is not None
    assert response.ai_coach_session.prompt_revision_id == session.prompt_revision_id
    assert response.ai_coach_session.article_snapshot is not None
    assert response.ai_coach_session.article_snapshot.title == "商务礼仪"
    assert response.ai_coach_session.config_snapshot is not None
    assert response.ai_coach_session.config_snapshot.mastery_threshold == 80
    assert response.ai_coach_session.coach_state is not None
    assert response.ai_coach_session.coach_state.last_action == "remediate"
    assert response.score_explanation is not None
    assert response.score_explanation.issues[0].type == "not_mastered"
    assert response.ability_profile is not None
    assert response.ability_profile.weak_dimensions[0].key == (
        "business_skills_ai_coach"
    )
    assert response.remediation is not None
    assert response.remediation.target_path == "/sales-trainer/business-skills/coach"
    assert record["score_explanation"]["issues"][0]["type"] == "not_mastered"
    assert record["ability_profile"]["weak_dimensions"][0]["key"] == (
        "business_skills_ai_coach"
    )
    assert record["remediation"]["needed"] is True
    assert record["remediation"]["action_label"] == "继续 AI 教练训练"
    assert (
        record["remediation"]["target_path"] == "/sales-trainer/business-skills/coach"
    )


@pytest.mark.asyncio
async def test_business_etiquette_quiz_attempt_enters_training_records(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    path_revision = SalesTrainerAssetRevision(
        revision_id=str(uuid.uuid4()),
        resource_type="newcomer_path_config",
        logical_id="newcomer_training_path_v1",
        revision_no=6,
        status="published",
        payload_json={"path_key": "newcomer_training_path_v1"},
        payload_hash="hash-path-business-quiz",
        change_class="semantic",
    )
    pack_revision = SalesTrainerAssetRevision(
        revision_id=str(uuid.uuid4()),
        resource_type="business_etiquette_training_pack",
        logical_id="business_etiquette_v1",
        revision_no=3,
        status="published",
        payload_json={"training_pack_key": "business_etiquette_v1"},
        payload_hash="hash-pack-business-quiz",
        change_class="semantic",
    )
    attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        training_pack_key="business_etiquette_v1",
        learning_unit_key="trust_opening",
        learning_unit_title="建立信任",
        user_id=learner.user_id,
        path_revision_id=path_revision.revision_id,
        path_revision_no=6,
        training_pack_revision_id=pack_revision.revision_id,
        training_pack_revision_no=3,
        capability_snapshot={"capabilities": ["business_etiquette_trust"]},
        question_snapshots=[{"question_id": "beq-1", "stem": "如何开场？"}],
        answers_snapshot=[
            {
                "question_id": "beq-1",
                "question_type": "single_choice",
                "score": 4,
                "max_score": 10,
                "is_correct": False,
                "capability_keys": ["business_etiquette_trust"],
                "analysis": "需要先确认客户上下文。",
            }
        ],
        capability_scores=[
            {
                "capability_key": "business_etiquette_trust",
                "display_name": "建立信任",
                "score": 4,
                "max_score": 10,
                "normalized_score": 40,
                "mastered": False,
            }
        ],
        weak_capability_keys=["business_etiquette_trust"],
        recommended_chapter_orders=[1],
        total_score=4,
        max_score=10,
        passed=False,
        status="scored",
        submitted_at=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
    )
    test_db.add_all([learner, path_revision, pack_revision, attempt])
    await test_db.commit()

    records, total = await TrainingRecordService(test_db).list_records(
        user_id=learner.user_id,
        limit=50,
    )
    detail = await TrainingRecordService(test_db).get_record(
        "business_etiquette_quiz_attempt",
        attempt.attempt_id,
    )

    assert total == 1
    record = records[0]
    assert record["record_type"] == "business_etiquette_quiz_attempt"
    assert record["record_id"] == attempt.attempt_id
    assert record["path_revision_id"] == path_revision.revision_id
    assert record["path_revision_no"] == 6
    assert record["module_key"] == "business_skills"
    assert record["legacy_snapshot_only"] is False
    assert record["unit_id"] == "trust_opening"
    assert record["unit_type"] == "business_etiquette_quiz"
    assert record["business_etiquette_quiz_attempt"]["training_pack_revision_id"] == (
        pack_revision.revision_id
    )
    assert record["score_explanation"]["basis"] == (
        "business_etiquette_quiz_attempt_snapshot_v1"
    )
    assert record["ability_profile"]["weak_dimensions"][0]["key"] == (
        "business_etiquette_trust"
    )
    assert record["remediation"]["needed"] is True
    assert record["remediation"]["action_label"] == "复习后重做小测"
    assert record["remediation"]["target_path"] == (
        "/sales-trainer/business-skills?learningUnitKey=trust_opening"
    )
    assert detail is not None
    assert detail["record_type"] == "business_etiquette_quiz_attempt"
    assert detail["business_etiquette_quiz_attempt"]["attempt_id"] == attempt.attempt_id
    response = SalesTrainerTrainingRecordResponse.model_validate(detail)
    assert response.score_explanation is not None
    assert response.score_explanation.basis == (
        "business_etiquette_quiz_attempt_snapshot_v1"
    )
    assert response.ability_profile is not None
    assert response.ability_profile.weak_dimensions[0].key == (
        "business_etiquette_trust"
    )
    assert response.remediation is not None
    assert response.remediation.action_label == "复习后重做小测"
    assert response.business_etiquette_quiz_attempt is not None
    assert response.business_etiquette_quiz_attempt.attempt_id == attempt.attempt_id
    assert response.business_etiquette_quiz_attempt.training_pack_key == (
        "business_etiquette_v1"
    )
    assert response.business_etiquette_quiz_attempt.training_pack_revision_id == (
        pack_revision.revision_id
    )
    assert response.business_etiquette_quiz_attempt.answers[0].question_id == "beq-1"
    assert response.business_etiquette_quiz_attempt.answers[0].analysis == (
        "需要先确认客户上下文。"
    )
    assert (
        response.business_etiquette_quiz_attempt.capability_scores[0].capability_key
        == "business_etiquette_trust"
    )


@pytest.mark.asyncio
async def test_legacy_business_etiquette_quiz_attempt_is_marked_legacy(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
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
        capability_snapshot={"capabilities": ["business_etiquette_trust"]},
        question_snapshots=[],
        answers_snapshot=[],
        capability_scores=[],
        weak_capability_keys=[],
        recommended_chapter_orders=[],
        total_score=None,
        max_score=None,
        passed=None,
        status="submitted",
        submitted_at=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
    )
    test_db.add_all([learner, attempt])
    await test_db.commit()

    record = await TrainingRecordService(test_db).get_record(
        "business_etiquette_quiz_attempt",
        attempt.attempt_id,
    )

    assert record is not None
    assert record["record_type"] == "business_etiquette_quiz_attempt"
    assert record["path_revision_id"] is None
    assert record["path_revision_no"] is None
    assert record["module_key"] == "business_skills"
    assert record["legacy_snapshot_only"] is True
    assert record["business_etiquette_quiz_attempt"]["attempt_id"] == attempt.attempt_id
    response = SalesTrainerTrainingRecordResponse.model_validate(record)
    assert response.business_etiquette_quiz_attempt is not None
    assert response.business_etiquette_quiz_attempt.path_revision_id is None
    assert response.business_etiquette_quiz_attempt.path_revision_no is None
    assert response.business_etiquette_quiz_attempt.question_snapshots == []
    assert response.business_etiquette_quiz_attempt.answers == []


@pytest.mark.asyncio
async def test_training_records_filter_by_module_stage_and_levels(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    quiz_unit_id = str(uuid.uuid4())
    unit = SalesTrainerUnit(
        unit_id=quiz_unit_id,
        name="商务技巧",
        unit_type="quiz",
        config={},
        status="published",
    )
    test_db.add_all([admin, learner, unit])
    await test_db.commit()
    revision_id = await _publish_phase2_business_path(
        test_db,
        actor=admin,
        quiz_unit_id=quiz_unit_id,
    )
    attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        training_pack_key="business_etiquette_v1",
        learning_unit_key="trust_opening",
        learning_unit_title="建立信任",
        user_id=learner.user_id,
        path_revision_id=revision_id,
        path_revision_no=1,
        training_pack_revision_id=None,
        training_pack_revision_no=None,
        capability_snapshot={"capabilities": ["business_etiquette_trust"]},
        question_snapshots=[],
        answers_snapshot=[],
        capability_scores=[],
        weak_capability_keys=[],
        recommended_chapter_orders=[],
        total_score=96,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
    )
    test_db.add(attempt)
    await test_db.commit()

    default_records, default_total = await TrainingRecordService(test_db).list_records(
        viewer=admin,
        limit=50,
    )
    assert default_total == 1
    assert len(default_records) == 1
    # Learning-topic evidence is non-blocking and must not advance required-path stage.
    assert default_records[0]["training_stage"] == "not_started"
    assert default_records[0]["learner_level"]["level_key"] == "unassigned"
    assert default_records[0]["role_level"]["level_key"] == "learner"

    module_records, module_total = await TrainingRecordService(test_db).list_records(
        module_key="business_skills",
        viewer=admin,
        limit=50,
    )
    assert module_total == 1
    assert len(module_records) == 1
    module_record = module_records[0]
    assert module_record["training_stage"] == "not_started"
    assert module_record["learner_level"]["level_key"] == "unassigned"
    assert module_record["role_level"]["level_key"] == "learner"

    records, total = await TrainingRecordService(test_db).list_records(
        module_key="business_skills",
        training_stage=module_record["training_stage"],
        learner_level=module_record["learner_level"]["level_key"],
        role_level=module_record["role_level"]["level_key"],
        status="scored",
        viewer=admin,
        limit=50,
    )
    unknown_records, unknown_total = await TrainingRecordService(test_db).list_records(
        module_key="unknown_module",
        viewer=admin,
        limit=50,
    )
    wrong_status_records, wrong_status_total = await TrainingRecordService(
        test_db,
    ).list_records(
        module_key="business_skills",
        status="failed",
        viewer=admin,
        limit=50,
    )

    assert total == 1
    assert len(records) == 1
    record = records[0]
    assert record["record_id"] == attempt.attempt_id
    assert record["module_key"] == "business_skills"
    assert record["training_stage"] == module_record["training_stage"]
    assert record["learner_level"]["level_key"] == "unassigned"
    assert record["role_level"]["level_key"] == "learner"
    assert record["legacy_snapshot_only"] is False
    assert unknown_records == []
    assert unknown_total == 0
    assert wrong_status_records == []
    assert wrong_status_total == 0


@pytest.mark.asyncio
async def test_realtime_roleplay_session_enters_training_records(
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        name="新人实时对练",
        description="新人实时对练",
        scenario_type="sales",
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="completed",
        start_time=datetime(2026, 6, 27, 9, 0, tzinfo=UTC),
        end_time=datetime(2026, 6, 27, 9, 12, tzinfo=UTC),
        logic_score=88,
        accuracy_score=82,
        completeness_score=76,
        voice_policy_snapshot={
            "external_binding": {
                "owner": "sales_trainer",
                "path_key": "newcomer_training_path_v1",
                "path_revision_id": "path-rev-001",
                "path_revision_no": 3,
                "module_key": "realtime_roleplay",
                "binding_key": "newcomer_realtime_roleplay_v1",
                "runtime_registry": {
                    "registry_key": "sales_trainer.realtime_provider.registry",
                    "version": 1,
                    "source": "published",
                    "descriptor": {
                        "descriptor_id": "newcomer-realtime-runtime",
                        "provider": "mock",
                        "runtime_owner": "training_runtime",
                        "enabled": True,
                        "readiness": {"ready": True},
                    },
                },
                "provider_readiness_snapshot": {
                    "provider": "mock",
                    "ready": True,
                    "checked_at": "2026-06-27T00:00:00Z",
                },
                "failure_policy": {
                    "terminal_codes": ["CONFIG_INVALID"],
                    "transient_codes": ["NETWORK_TIMEOUT"],
                    "voluntary_codes": ["USER_CANCELLED"],
                    "terminal_retry_allowed": False,
                },
            }
        },
        effectiveness_snapshot={"summary": "完成实时对练"},
        runtime_state={"state": "completed"},
    )
    test_db.add_all([learner, scenario, session])
    await test_db.commit()

    records, total = await TrainingRecordService(test_db).list_records(
        user_id=learner.user_id,
        limit=50,
    )
    detail = await TrainingRecordService(test_db).get_record(
        "realtime_roleplay_session",
        session.session_id,
    )

    assert total == 1
    assert records[0]["record_type"] == "realtime_roleplay_session"
    assert records[0]["record_id"] == session.session_id
    assert records[0]["score"] == 82
    assert records[0]["path_revision_id"] == "path-rev-001"
    assert records[0]["path_revision_no"] == 3
    assert records[0]["module_key"] == "realtime_roleplay"
    assert records[0]["legacy_snapshot_only"] is False
    assert (
        records[0]["realtime_roleplay_session"]["external_binding"]["binding_key"]
        == "newcomer_realtime_roleplay_v1"
    )
    assert (
        records[0]["realtime_roleplay_session"]["snapshot"]["external_binding"][
            "binding_key"
        ]
        == "newcomer_realtime_roleplay_v1"
    )
    assert records[0]["score_explanation"]["basis"] == (
        "realtime_roleplay_runtime_outcome_snapshot_v1"
    )
    assert detail is not None
    assert detail["record_type"] == "realtime_roleplay_session"
    assert detail["realtime_roleplay_session"]["session_id"] == session.session_id
    assert detail["realtime_roleplay_session"]["external_binding"]["module_key"] == (
        "realtime_roleplay"
    )
    response = SalesTrainerTrainingRecordResponse.model_validate(detail)
    assert response.realtime_roleplay_session is not None
    assert response.realtime_roleplay_session.snapshot.scores.accuracy_score == 82
    binding = response.realtime_roleplay_session.external_binding
    assert binding.runtime_registry is not None
    assert binding.runtime_registry.descriptor is not None
    assert binding.runtime_registry.descriptor.provider == "mock"
    assert binding.provider_readiness_snapshot is not None
    assert binding.provider_readiness_snapshot.ready is True
    assert binding.failure_policy is not None
    assert binding.failure_policy.terminal_retry_allowed is False
    runtime_snapshot = response.realtime_roleplay_session.snapshot
    assert runtime_snapshot.voice_policy_snapshot.external_binding is not None
    assert runtime_snapshot.effectiveness_snapshot.summary == "完成实时对练"
    assert runtime_snapshot.runtime_state.state == "completed"


@pytest.mark.asyncio
async def test_phase2_policy_uses_published_business_rule_config(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    value = get_default_business_rule_value(SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY)
    value["low_score_threshold"] = 65.0
    value["manager_actions"][1]["label"] = "配置化弱项复习"
    test_db.add_all([admin, _phase2_config(value, actor_id=admin.user_id)])
    await test_db.commit()

    policy, payload = await resolve_phase2_policy(test_db)

    assert policy.low_score_threshold == 65.0
    assert policy.manager_action({"low_score"})["label"] == "配置化弱项复习"
    assert payload["source"] == "database"
    assert payload["fallback_applied"] is False


@pytest.mark.asyncio
async def test_phase2_policy_falls_back_when_missing_or_disabled(
    test_db: AsyncSession,
) -> None:
    policy, payload = await resolve_phase2_policy(test_db)

    assert policy.low_score_threshold == 70.0
    assert policy.repeat_practice_threshold == 2
    assert policy.dashboard_record_limit == 500
    assert payload["fallback_applied"] is True
    assert payload["fallback_reason"] == "active_missing"

    disabled_value = get_default_business_rule_value(
        SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY
    )
    disabled_value["enabled"] = False
    test_db.add(_phase2_config(disabled_value, status="disabled"))
    await test_db.commit()

    disabled_policy, disabled_payload = await resolve_phase2_policy(test_db)

    assert disabled_policy.low_score_threshold == 70.0
    assert disabled_payload["fallback_applied"] is True
    assert disabled_payload["fallback_reason"] == "active_disabled"
