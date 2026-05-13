from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, SessionStatus
from curriculum_practice.models import PracticeTemplate
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
