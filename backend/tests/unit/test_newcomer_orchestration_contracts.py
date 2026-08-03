from __future__ import annotations

import pytest
from pydantic import ValidationError

from sales_trainer.orchestration.contracts import (
    AudioAssessmentConfig,
    TrainingPathPayload,
)


def _lesson_activity(*, product: str) -> dict[str, object]:
    return {
        "activity_id": f"activity-product-{product}-lesson",
        "type": "lesson",
        "title": "学习资料",
        "order_index": 1,
        "required": True,
        "config": {"learning_content_id": f"content-{product}"},
    }


def _product_module(*, product: str, order_index: int) -> dict[str, object]:
    return {
        "module_id": f"module-product-{product}",
        "title": f"产品 {product.upper()}",
        "order_index": order_index,
        "required": True,
        "completion_policy": {"mode": "all_required"},
        "activities": [_lesson_activity(product=product)],
    }


def test_should_accept_three_product_modules_without_business_key_enum() -> None:
    payload = TrainingPathPayload.model_validate(
        {
            "title": "新人训练路径",
            "phases": [
                {
                    "phase_id": "phase-product",
                    "title": "产品能力",
                    "order_index": 1,
                    "required": True,
                    "modules": [
                        _product_module(product=product, order_index=index)
                        for index, product in enumerate(("a", "b", "c"), start=1)
                    ],
                }
            ],
        }
    )

    assert [module.title for module in payload.phases[0].modules] == [
        "产品 A",
        "产品 B",
        "产品 C",
    ]


def test_should_reject_unknown_activity_type_and_executable_config() -> None:
    payload = {
        "title": "新人训练路径",
        "phases": [
            {
                "phase_id": "phase-1",
                "title": "阶段",
                "order_index": 1,
                "required": True,
                "modules": [
                    {
                        "module_id": "module-1",
                        "title": "模块",
                        "order_index": 1,
                        "required": True,
                        "completion_policy": {"mode": "all_required"},
                        "activities": [
                            {
                                "activity_id": "activity-1",
                                "type": "arbitrary_script",
                                "title": "非法活动",
                                "order_index": 1,
                                "required": True,
                                "config": {"script": "rm -rf /"},
                            }
                        ],
                    }
                ],
            }
        ],
    }

    with pytest.raises(ValidationError):
        TrainingPathPayload.model_validate(payload)


@pytest.mark.parametrize(
    ("activity_type", "config"),
    [
        ("lesson", {"learning_content_id": "content-id"}),
        ("quiz", {"exam_paper_id": "paper-id", "pass_score": 80}),
        (
            "audio_assessment",
            {"scoring_rubric_id": "rubric-id", "pass_score": 75},
        ),
        (
            "realtime_roleplay",
            {
                "practice_template_id": "template-id",
                "runtime_profile_id": "stepaudio-2.5-realtime",
            },
        ),
        ("ai_coach", {"coach_profile_id": "coach-profile-id"}),
        (
            "assignment",
            {"submission_type": "text_or_file", "review_mode": "manual_review"},
        ),
    ],
)
def test_should_accept_each_supported_activity_type(
    activity_type: str,
    config: dict[str, object],
) -> None:
    payload = {
        "title": "新人训练路径",
        "phases": [
            {
                "phase_id": "phase-1",
                "title": "阶段",
                "order_index": 1,
                "modules": [
                    {
                        "module_id": "module-1",
                        "title": "模块",
                        "order_index": 1,
                        "completion_policy": {"mode": "all_required"},
                        "activities": [
                            {
                                "activity_id": "activity-1",
                                "type": activity_type,
                                "title": "训练活动",
                                "order_index": 1,
                                "config": config,
                            }
                        ],
                    }
                ],
            }
        ],
    }

    parsed = TrainingPathPayload.model_validate(payload)

    assert parsed.phases[0].modules[0].activities[0].type == activity_type


@pytest.mark.parametrize(
    ("activity_type", "config"),
    [
        ("lesson", {"learning_content_id": ""}),
        ("quiz", {"exam_paper_id": "", "pass_score": 80}),
        (
            "audio_assessment",
            {"scoring_rubric_id": "", "material_id": "", "pass_score": 80},
        ),
        (
            "realtime_roleplay",
            {"practice_template_id": "", "runtime_profile_id": ""},
        ),
        ("ai_coach", {"coach_profile_id": ""}),
    ],
)
def test_should_accept_incomplete_resource_bindings_in_working_draft(
    activity_type: str,
    config: dict[str, object],
) -> None:
    parsed = TrainingPathPayload.model_validate(
        {
            "title": "待补资源的新人训练路径",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "阶段",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "module-1",
                            "title": "模块",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "activity-1",
                                    "type": activity_type,
                                    "title": "待配置活动",
                                    "order_index": 1,
                                    "config": config,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    activity = parsed.phases[0].modules[0].activities[0]
    assert activity.type == activity_type
    if activity.type == "audio_assessment":
        assert activity.config.material_id is None


def test_should_reject_arbitrary_route_in_activity_config() -> None:
    payload = {
        "title": "新人训练路径",
        "phases": [
            {
                "phase_id": "phase-1",
                "title": "阶段",
                "order_index": 1,
                "modules": [
                    {
                        "module_id": "module-1",
                        "title": "模块",
                        "order_index": 1,
                        "completion_policy": {"mode": "all_required"},
                        "activities": [
                            {
                                "activity_id": "activity-1",
                                "type": "lesson",
                                "title": "学习",
                                "order_index": 1,
                                "config": {
                                    "learning_content_id": "content-id",
                                    "target_url": "https://example.com/run",
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }

    with pytest.raises(ValidationError):
        TrainingPathPayload.model_validate(payload)


def test_should_accept_optional_learner_presentation_and_default_legacy_values() -> (
    None
):
    legacy = TrainingPathPayload.model_validate(
        {
            "title": "旧版路径",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "阶段",
                    "order_index": 1,
                    "modules": [_product_module(product="a", order_index=1)],
                }
            ],
        }
    )
    legacy_phase = legacy.phases[0]
    legacy_module = legacy_phase.modules[0]
    legacy_activity = legacy_module.activities[0]

    assert legacy_phase.outcome is None
    assert legacy_module.outcome is None
    assert legacy_activity.objective is None
    assert legacy_activity.why_it_matters is None
    assert legacy_activity.steps == []
    assert legacy_activity.success_criteria == []
    assert legacy_activity.primary_action_label is None

    enriched = TrainingPathPayload.model_validate(
        {
            "title": "新版路径",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "产品讲解",
                    "outcome": "能独立完成产品讲解",
                    "order_index": 1,
                    "modules": [
                        {
                            **_product_module(product="a", order_index=1),
                            "outcome": "能讲清适用场景",
                            "activities": [
                                {
                                    **_lesson_activity(product="a"),
                                    "objective": "完成核心资料学习",
                                    "why_it_matters": "讲解前先建立准确认知",
                                    "steps": ["阅读", "记录", "确认完成"],
                                    "success_criteria": ["完成全部章节"],
                                    "primary_action_label": "开始学习",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    assert enriched.phases[0].outcome == "能独立完成产品讲解"
    assert enriched.phases[0].modules[0].activities[0].steps == [
        "阅读",
        "记录",
        "确认完成",
    ]


def test_audio_assessment_should_accept_configured_example_transcript() -> None:
    config = AudioAssessmentConfig.model_validate(
        {
            "scoring_rubric_id": "rubric-ppt-intro",
            "material_id": "material-ppt-intro",
            "pass_score": 80,
            "example_transcript": "先说明客户问题，再结合材料讲清方案价值。",
        }
    )

    assert config.example_transcript == "先说明客户问题，再结合材料讲清方案价值。"


def test_audio_assessment_should_reject_oversized_example_transcript() -> None:
    with pytest.raises(ValidationError):
        AudioAssessmentConfig.model_validate(
            {
                "scoring_rubric_id": "rubric-ppt-intro",
                "pass_score": 80,
                "example_transcript": "讲" * 8001,
            }
        )


def test_audio_assessment_should_normalize_blank_example_transcript() -> None:
    config = AudioAssessmentConfig.model_validate(
        {
            "scoring_rubric_id": "rubric-ppt-intro",
            "pass_score": 80,
            "example_transcript": "   \n  ",
        }
    )

    assert config.example_transcript is None
