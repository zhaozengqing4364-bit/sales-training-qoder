from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
    get_business_rule_definition,
    get_default_business_rule_value,
)
from common.db.models import BusinessRuleConfig, User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.regrade_models import SalesTrainerRegradeRun
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
    test_db.add_all([
        admin,
        learner,
        unit,
        category,
        question,
        attempt,
        answer,
        regrade_run,
    ])
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
