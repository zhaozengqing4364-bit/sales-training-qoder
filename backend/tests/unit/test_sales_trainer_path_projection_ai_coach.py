from __future__ import annotations

from typing import Any

from sales_trainer.models import SalesTrainerUnit
from sales_trainer.schemas import SalesTrainerPathConfig
from sales_trainer.services.path_projection_payloads import build_path_payload
from sales_trainer.services.path_progress_service import UnitProgress


def _unit(
    unit_id: str = "business-unit",
    *,
    name: str = "商务技巧",
    unit_type: str = "quiz",
) -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id=unit_id,
        name=name,
        description="阅读文章后练习商务技巧。",
        unit_type=unit_type,
    )


def _business_path_config(*, ai_coach: dict[str, Any] | None) -> SalesTrainerPathConfig:
    return SalesTrainerPathConfig(
        enabled=True,
        path_key="newcomer_training_path_v1",
        module_key="business_skills",
        module_type="article_exam",
        order_index=2,
        level_title="第2关：商务技巧",
        level_description="阅读文章后完成商务技巧考卷。",
        completion_rule="passed",
        primary_action_label="阅读文章并考试",
        ai_coach=ai_coach,
    )


def _path_payload(config: SalesTrainerPathConfig) -> dict[str, Any]:
    return build_path_payload(
        path_key="newcomer_training_path_v1",
        title="新人训练路径",
        goal_title="掌握新人核心训练路径",
        ordered_items=[(_unit(), config)],
        quiz_progress={},
        audio_progress={},
    )


def test_should_recommend_retry_when_ppt_failed_even_if_business_skills_passed() -> None:
    ppt_unit = _unit("ppt-unit", name="PPT讲解", unit_type="audio_scoring")
    business_unit = _unit("business-unit")
    ppt_config = SalesTrainerPathConfig(
        enabled=True,
        path_key="newcomer_training_path_v1",
        module_key="ppt_explanation",
        module_type="audio_scoring",
        order_index=1,
        level_title="第1关：PPT讲解录音",
        completion_rule="passed",
        primary_action_label="上传 PPT 讲解录音",
    )
    business_config = _business_path_config(ai_coach=None)

    payload = build_path_payload(
        path_key="newcomer_training_path_v1",
        title="新人训练路径",
        goal_title="掌握新人核心训练路径",
        ordered_items=[(ppt_unit, ppt_config), (business_unit, business_config)],
        quiz_progress={
            "business-unit": UnitProgress(
                status="scored",
                passed=True,
                score=85,
                max_score=100,
                submitted_at=None,
                result_id="business-attempt",
                target_path="/sales-trainer/quiz/result/business-attempt",
            )
        },
        audio_progress={
            "ppt-unit": UnitProgress(
                status="scored",
                passed=False,
                score=44,
                max_score=100,
                submitted_at=None,
                result_id="ppt-submission",
                target_path="/sales-trainer/audio/result/ppt-submission",
            )
        },
    )
    recommendation = payload["goal_context"]["next_recommendation"]

    assert payload["completed_levels"] == 1
    assert payload["current_level_id"] == "ppt-unit"
    assert recommendation["recommendation_kind"] == "retry_level"
    assert recommendation["target_path"] == "/sales-trainer/audio/ppt-unit"
    assert recommendation["unit_id"] == "ppt-unit"


def test_should_expose_available_ai_coach_without_internal_prompt_fields() -> None:
    payload = _path_payload(
        _business_path_config(
            ai_coach={
                "enabled": True,
                "coach_mode": "mixed_drill",
                "allowed_interaction_types": ["single_choice", "multiple_choice"],
                "prompt_template_id": "11111111-1111-1111-1111-111111111111",
                "prompt_revision_id": "revision-1",
                "scoring_prompt_template_id": None,
                "scoring_prompt_revision_id": None,
                "prompt_contract_hash": None,
                "scoring_contract_hash": None,
                "min_turns": 3,
                "max_turns": 10,
                "mastery_threshold": 80,
                "output_schema_version": "ai_coach_interaction_v1",
            },
        ),
    )

    availability = payload["levels"][0]["ai_coach_availability"]

    assert availability == {
        "enabled": True,
        "configured": True,
        "available": True,
        "coach_path": "/sales-trainer/business-skills/coach",
        "disabled_reason": None,
        "allowed_interaction_types": ["single_choice", "multiple_choice"],
    }
    for internal_field in (
        "prompt_template_id",
        "prompt_revision_id",
        "prompt_contract_hash",
        "scoring_prompt_template_id",
        "scoring_prompt_revision_id",
        "scoring_contract_hash",
    ):
        assert internal_field not in availability


def test_should_hide_ai_coach_when_disabled() -> None:
    payload = _path_payload(
        _business_path_config(
            ai_coach={
                "enabled": False,
                "coach_mode": "mixed_drill",
                "allowed_interaction_types": ["single_choice", "multiple_choice"],
                "prompt_template_id": "11111111-1111-1111-1111-111111111111",
                "min_turns": 3,
                "max_turns": 10,
                "mastery_threshold": 80,
                "output_schema_version": "ai_coach_interaction_v1",
            },
        ),
    )

    availability = payload["levels"][0]["ai_coach_availability"]

    assert availability["enabled"] is False
    assert availability["configured"] is True
    assert availability["available"] is False
    assert availability["coach_path"] is None


def test_should_hide_ai_coach_when_prompt_is_missing() -> None:
    payload = _path_payload(
        _business_path_config(
            ai_coach={
                "enabled": True,
                "coach_mode": "mixed_drill",
                "allowed_interaction_types": ["single_choice", "multiple_choice"],
                "prompt_template_id": None,
                "min_turns": 3,
                "max_turns": 10,
                "mastery_threshold": 80,
                "output_schema_version": "ai_coach_interaction_v1",
            },
        ),
    )

    availability = payload["levels"][0]["ai_coach_availability"]

    assert availability["enabled"] is True
    assert availability["configured"] is False
    assert availability["available"] is False
    assert availability["disabled_reason"] == "AI 教练未绑定生成 Prompt。"
