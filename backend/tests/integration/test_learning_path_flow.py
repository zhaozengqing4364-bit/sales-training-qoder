from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    PracticeSession,
    RetrainingTask,
    Scenario,
    SessionStatus,
    SupervisorReview,
)
from curriculum_practice.models import LearningChapter, LearningContent, LearningProgress, PracticeTemplate
from curriculum_practice.services.learning_path import LearningPathService


@pytest.mark.asyncio
async def test_should_build_weakness_driven_learning_path_from_completed_sessions(
    test_db: AsyncSession,
    test_user,
) -> None:
    template = PracticeTemplate(
        template_id="33333333-3333-3333-3333-333333333333",
        name="产品知识专项",
        description="product knowledge path",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-product",
        curriculum_plan={
            "name": "产品知识路径",
            "stages": [
                {
                    "template_stage_key": "template_stage_product",
                    "order": 1,
                    "name": "产品证据表达",
                    "template_ref": {
                        "asset_type": "practice_template",
                        "asset_id": "33333333-3333-3333-3333-333333333333",
                        "version": 1,
                        "hash": "hash-product",
                        "snapshot_label": "published",
                    },
                    "completion_policy": {"min_score": 7, "min_rounds": 1, "max_duration_seconds": 600},
                    "prerequisites": [],
                }
            ],
        },
    )
    scenario = Scenario(
        scenario_id="scenario-learning-path",
        scenario_type="sales",
        name="销售对练",
    )
    session = PracticeSession(
        session_id="session-learning-path",
        user_id=str(test_user.user_id),
        scenario_id="scenario-learning-path",
        practice_template_id=template.template_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=78,
        accuracy_score=42,
        completeness_score=83,
        effectiveness_snapshot={"evaluable": True},
        start_time=datetime.now(UTC),
    )
    test_db.add_all([template, scenario, session])
    await test_db.commit()

    result = await LearningPathService(test_db).build_for_user(str(test_user.user_id))

    assert result["path_type"] == "weakness_driven"
    assert result["recommended_template_ids"] == [template.template_id]
    assert result["recommendation_reasons"][0]["source_report_id"] == "session-learning-path"
    assert result["recommendation_reasons"][0]["dimension_name"] == "product_knowledge"
    assert result["stages"][0]["report_url"] == "/practice/session-learning-path/report"


@pytest.mark.asyncio
async def test_should_mark_certification_stage_retraining_required_after_supervisor_retrain(
    test_db: AsyncSession,
    test_user,
) -> None:
    template = PracticeTemplate(
        template_id="44444444-4444-4444-4444-444444444444",
        name="认证复核路径",
        description="certification review path",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-certification-review",
        curriculum_plan={
            "name": "认证复核路径",
            "stages": [
                {
                    "template_stage_key": "template_stage_certification_review",
                    "order": 1,
                    "name": "主管认证复核",
                    "template_ref": {
                        "asset_type": "practice_template",
                        "asset_id": "44444444-4444-4444-4444-444444444444",
                        "version": 1,
                        "hash": "hash-certification-review",
                        "snapshot_label": "published",
                    },
                    "completion_policy": {
                        "min_score": 8,
                        "min_rounds": 1,
                        "max_duration_seconds": 600,
                    },
                    "prerequisites": [],
                }
            ],
        },
    )
    scenario = Scenario(
        scenario_id="scenario-certification-review",
        scenario_type="sales",
        name="销售认证复核",
    )
    session = PracticeSession(
        session_id="session-certification-review",
        user_id=str(test_user.user_id),
        scenario_id="scenario-certification-review",
        practice_template_id=template.template_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=42,
        accuracy_score=68,
        completeness_score=73,
        effectiveness_snapshot={"evaluable": True},
        start_time=datetime.now(UTC),
    )
    review = SupervisorReview(
        review_id="review-certification-retrain",
        session_id=session.session_id,
        trainee_user_id=str(test_user.user_id),
        supervisor_user_id=str(test_user.user_id),
        decision="needs_retraining",
        readiness_status="shadow_only",
        comment="认证未通过，需要复训价值逻辑。",
        required_retraining=True,
    )
    retraining_task = RetrainingTask(
        task_id="task-certification-retrain",
        user_id=str(test_user.user_id),
        source_session_id=session.session_id,
        source_review_id=review.review_id,
        skill_dimension="value_logic",
        title="复训：value_logic",
        status="todo",
    )
    test_db.add_all([template, scenario, session, review, retraining_task])
    await test_db.commit()

    result = await LearningPathService(test_db).build_for_user(str(test_user.user_id))

    stage = result["stages"][0]
    assert stage["template_stage_key"] == "template_stage_certification_review"
    assert stage["state"] == "retraining_required"
    assert result["next_task"]["state"] == "retraining_required"


@pytest.mark.asyncio
async def test_should_reflect_learning_content_progress_in_next_cta(
    test_db: AsyncSession,
    test_user,
) -> None:
    content = LearningContent(
        title="销售入门讲义",
        status="published",
        safety_flagged=False,
        version=1,
    )
    test_db.add(content)
    await test_db.flush()
    first = LearningChapter(
        learning_content_id=content.learning_content_id,
        title="第一章",
        content="建立信任",
        order_index=1,
    )
    second = LearningChapter(
        learning_content_id=content.learning_content_id,
        title="第二章",
        content="需求澄清",
        order_index=2,
    )
    test_db.add_all([first, second])
    await test_db.commit()

    partial = await LearningPathService(test_db).build_for_user(str(test_user.user_id))
    assert partial["next_task"]["state"] == "not_started"
    assert partial["next_task"]["primary_cta"] == "continue learning"

    test_db.add_all(
        [
            LearningProgress(
                user_id=str(test_user.user_id),
                learning_content_id=content.learning_content_id,
                chapter_id=first.chapter_id,
            ),
            LearningProgress(
                user_id=str(test_user.user_id),
                learning_content_id=content.learning_content_id,
                chapter_id=second.chapter_id,
            ),
        ]
    )
    await test_db.commit()

    completed = await LearningPathService(test_db).build_for_user(str(test_user.user_id))
    assert completed["next_task"]["state"] == "completed"
    assert completed["next_task"]["primary_cta"] == "start exam"
