from __future__ import annotations

import pytest

from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import CurriculumPlanSchema, PracticeTemplateCreate


def test_should_accept_valid_curriculum_plan_with_ordered_template_stages() -> None:
    plan = CurriculumPlanSchema.model_validate(
        {
            "name": "新人销售闯关训练",
            "description": "从开场到异议处理的多阶段训练",
            "stages": [
                {
                    "template_stage_key": "template_stage_opening",
                    "order": 1,
                    "name": "开场破冰",
                    "template_ref": {
                        "asset_type": "practice_template",
                        "asset_id": "template-opening",
                        "version": 1,
                        "hash": "sha256:opening",
                        "snapshot_label": "published",
                    },
                    "completion_policy": {
                        "min_score": 7.0,
                        "min_rounds": 2,
                        "max_duration_seconds": 600,
                    },
                    "failure_policy": "retry_current",
                    "prerequisites": [],
                },
                {
                    "template_stage_key": "template_stage_objection",
                    "order": 2,
                    "name": "异议处理",
                    "template_ref": {
                        "asset_type": "practice_template",
                        "asset_id": "template-objection",
                        "version": 1,
                        "hash": "sha256:objection",
                        "snapshot_label": "published",
                    },
                    "completion_policy": {
                        "min_score": 8.0,
                        "min_rounds": 3,
                        "max_duration_seconds": 900,
                    },
                    "failure_policy": "fallback_to_previous",
                    "prerequisites": [
                        {
                            "template_stage_key": "template_stage_opening",
                            "required_result": "completed",
                        }
                    ],
                },
            ],
        }
    )

    assert [stage.template_stage_key for stage in plan.stages] == [
        "template_stage_opening",
        "template_stage_objection",
    ]


def test_should_reject_duplicate_template_stage_keys() -> None:
    payload = {
        "name": "重复阶段训练",
        "stages": [
            _stage_payload("template_stage_opening", 1),
            _stage_payload("template_stage_opening", 2),
        ],
    }

    with pytest.raises(ValueError, match="template_stage_key"):
        CurriculumPlanSchema.model_validate(payload)


def test_should_reject_invalid_prerequisite_stage_key() -> None:
    payload = {
        "name": "错误前置训练",
        "stages": [
            _stage_payload(
                "template_stage_objection",
                1,
                prerequisites=[
                    {
                        "template_stage_key": "template_stage_missing",
                        "required_result": "completed",
                    }
                ],
            )
        ],
    }

    with pytest.raises(ValueError, match="prerequisite"):
        CurriculumPlanSchema.model_validate(payload)


def test_should_reject_unreachable_curriculum_stage() -> None:
    payload = {
        "name": "不可达阶段训练",
        "stages": [
            _stage_payload("template_stage_opening", 1),
            _stage_payload(
                "template_stage_objection",
                2,
                prerequisites=[
                    {
                        "template_stage_key": "template_stage_objection",
                        "required_result": "completed",
                    }
                ],
            ),
        ],
    }

    with pytest.raises(ValueError, match="unreachable"):
        CurriculumPlanSchema.model_validate(payload)


def test_should_reject_curriculum_plan_cycle() -> None:
    payload = {
        "name": "循环依赖训练",
        "stages": [
            _stage_payload(
                "template_stage_opening",
                1,
                prerequisites=[
                    {
                        "template_stage_key": "template_stage_objection",
                        "required_result": "completed",
                    }
                ],
            ),
            _stage_payload(
                "template_stage_objection",
                2,
                prerequisites=[
                    {
                        "template_stage_key": "template_stage_opening",
                        "required_result": "completed",
                    }
                ],
            ),
        ],
    }

    with pytest.raises(ValueError, match="cycle"):
        CurriculumPlanSchema.model_validate(payload)


def test_should_reject_stage_duration_above_stepfun_safe_limit() -> None:
    payload = {
        "name": "超时阶段训练",
        "max_stage_duration_seconds": 600,
        "stages": [
            _stage_payload(
                "template_stage_opening",
                1,
                max_duration_seconds=900,
            )
        ],
    }

    with pytest.raises(ValueError, match="stage duration"):
        CurriculumPlanSchema.model_validate(payload)


def test_should_accept_curriculum_plan_on_practice_template_create_schema() -> None:
    plan = CurriculumPlanSchema.model_validate(
        {
            "name": "新人销售闯关训练",
            "max_stage_duration_seconds": 600,
            "stages": [_stage_payload("template_stage_opening", 1)],
        }
    )

    payload = PracticeTemplateCreate(
        name="闯关模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
        curriculum_plan=plan,
        max_stage_duration_seconds=600,
    )

    assert payload.curriculum_plan is not None
    assert payload.max_stage_duration_seconds == 600


def test_should_define_curriculum_plan_columns_on_practice_template_model() -> None:
    column_names = {column.name for column in PracticeTemplate.__table__.columns}

    assert "curriculum_plan" in column_names
    assert "max_stage_duration_seconds" in column_names


def test_should_accept_template_runtime_bindings_on_create_schema() -> None:
    payload = PracticeTemplateCreate(
        name="分层学习模板",
        scenario_type="sales",
        mode="examiner",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
        learning_content_id="learning-1",
        examiner_agent_id="examiner-1",
        target_learner_level="beginner",
        timeout_config={"study_seconds": 300, "exam_seconds": 600},
    )

    assert payload.learning_content_id == "learning-1"
    assert payload.examiner_agent_id == "examiner-1"
    assert payload.target_learner_level == "beginner"
    assert payload.timeout_config == {"study_seconds": 300, "exam_seconds": 600}


def test_should_accept_curriculum_stage_types_for_learning_exam_practice_report() -> None:
    plan = CurriculumPlanSchema.model_validate(
        {
            "name": "学习考试闭环",
            "stages": [
                _stage_payload("study_stage", 1) | {"stage_type": "study"},
                _stage_payload("exam_stage", 2) | {"stage_type": "exam"},
                _stage_payload("practice_stage", 3) | {"stage_type": "practice"},
                _stage_payload("report_stage", 4) | {"stage_type": "report"},
            ],
        }
    )

    assert [stage.stage_type for stage in plan.stages] == [
        "study",
        "exam",
        "practice",
        "report",
    ]


def _stage_payload(
    template_stage_key: str,
    order: int,
    *,
    prerequisites: list[dict[str, str]] | None = None,
    max_duration_seconds: int = 600,
) -> dict[str, object]:
    return {
        "template_stage_key": template_stage_key,
        "order": order,
        "name": f"阶段 {order}",
        "template_ref": {
            "asset_type": "practice_template",
            "asset_id": f"template-{order}",
            "version": 1,
            "hash": f"sha256:{order}",
            "snapshot_label": "published",
        },
        "completion_policy": {
            "min_score": 7.0,
            "min_rounds": 2,
            "max_duration_seconds": max_duration_seconds,
        },
        "failure_policy": "retry_current",
        "prerequisites": prerequisites or [],
    }
