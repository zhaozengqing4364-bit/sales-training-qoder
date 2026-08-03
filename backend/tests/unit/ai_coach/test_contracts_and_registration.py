from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from ai_coach.ai_schemas import (
    COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
    COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
    COACH_CARD_GENERATION_INPUT_SCHEMA,
    COACH_CARD_GENERATION_OUTPUT_SCHEMA,
    COACH_EXPLANATION_INPUT_SCHEMA,
    COACH_EXPLANATION_OUTPUT_SCHEMA,
    build_coach_ai_schema_registry,
)
from ai_coach.contracts import (
    CoachAnswerEvaluationOutput,
    CoachCardDraft,
    CoachProfileSnapshot,
)
from ai_coach.task_definitions import register_coach_task_definitions
from ai_coach.task_types import (
    COACH_ANSWER_EVALUATION_TASK_TYPE,
    COACH_ASSISTANCE_TASK_TYPE,
    COACH_CARD_GENERATION_TASK_TYPE,
)
from task_runtime import TaskRegistry


def _ai_contract(purpose: str) -> dict[str, object]:
    return {
        "business_purpose": purpose,
        "prompt_template_id": f"{purpose}-template",
        "prompt_revision_id": f"{purpose}-prompt-v1",
        "model_routing_profile_id": f"{purpose}-models",
        "model_routing_revision_id": f"{purpose}-models-v1",
        "input_schema_version": f"{purpose}-input-v1",
        "output_schema_version": f"{purpose}-output-v1",
        "timeout_policy_ref": f"{purpose}-timeout-v1",
        "retry_policy_ref": f"{purpose}-retry-v1",
    }


def _profile_payload() -> dict[str, Any]:
    return {
        "title": "新人销售结构化教练",
        "training_goal": "依次巩固识别、表达和场景迁移能力。",
        "applicable_competency_keys": ["identify", "express", "transfer"],
        "allowed_knowledge_scope": ["learning-unit-revision-1"],
        "tone_principles": ["具体", "尊重"],
        "feedback_principles": ["引用回答证据", "给出下一步"],
        "checkpoints": [
            {
                "checkpoint_key": "identify",
                "title": "识别与理解",
                "objective": "识别客户问题与方法边界。",
                "competency_keys": ["identify"],
            },
            {
                "checkpoint_key": "express",
                "title": "组织与表达",
                "objective": "用客户语言组织清晰表达。",
                "competency_keys": ["express"],
            },
            {
                "checkpoint_key": "transfer",
                "title": "销售场景迁移",
                "objective": "把方法迁移到销售推进场景。",
                "competency_keys": ["transfer"],
            },
        ],
        "card_type_whitelist": [
            "single_choice",
            "multiple_choice",
            "ordering",
            "short_answer_rewrite",
            "scenario_choice",
            "key_points_completion",
            "example_comparison",
            "summary",
        ],
        "mastery_rule": {
            "threshold_percent": 82,
            "minimum_scored_cards": 3,
            "maximum_uncertainty": 0.25,
        },
        "remediation_policy": {
            "cards_per_cycle_min": 3,
            "cards_per_cycle_max": 5,
            "maximum_automatic_cycles": 2,
        },
        "ai": {
            "card_generation": _ai_contract("coach_generation"),
            "answer_evaluation": _ai_contract("coach_evaluation"),
            "feedback_explanation": _ai_contract("coach_explanation"),
        },
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "card_type": "single_choice",
            "prompt": "第一步应该做什么？",
            "source_ref_ids": ["source-1"],
            "options": [
                {"option_id": "a", "text": "澄清目标"},
                {"option_id": "b", "text": "立即承诺"},
            ],
            "correct_option_ids": ["a"],
        },
        {
            "card_type": "multiple_choice",
            "prompt": "哪些信息需要澄清？",
            "source_ref_ids": ["source-1"],
            "options": [
                {"option_id": "a", "text": "业务目标"},
                {"option_id": "b", "text": "影响范围"},
            ],
            "correct_option_ids": ["a", "b"],
        },
        {
            "card_type": "ordering",
            "prompt": "排列沟通步骤。",
            "source_ref_ids": ["source-1"],
            "items": [
                {"item_id": "a", "text": "澄清"},
                {"item_id": "b", "text": "回应"},
            ],
            "correct_order_ids": ["a", "b"],
        },
        {
            "card_type": "short_answer_rewrite",
            "prompt": "改写下面的回答。",
            "source_ref_ids": ["source-1"],
            "instruction": "使用客户语言。",
            "reference_points": ["客户目标", "业务影响"],
        },
        {
            "card_type": "scenario_choice",
            "prompt": "选择最合适的回应。",
            "source_ref_ids": ["source-1"],
            "scenario": "客户担心交付风险。",
            "options": [
                {"option_id": "a", "text": "先确认风险场景"},
                {"option_id": "b", "text": "否认风险"},
            ],
            "correct_option_ids": ["a"],
        },
        {
            "card_type": "key_points_completion",
            "prompt": "补全需求澄清要点。",
            "source_ref_ids": ["source-1"],
            "hints": ["目标"],
            "reference_points": ["目标", "影响", "约束"],
        },
        {
            "card_type": "example_comparison",
            "prompt": "比较两个示例。",
            "source_ref_ids": ["source-1"],
            "examples": ["直接承诺", "先澄清再回应"],
            "comparison_criteria": ["是否有依据"],
            "reference_points": ["先澄清"],
        },
        {
            "card_type": "summary",
            "prompt": "总结当前方法。",
            "source_ref_ids": ["source-1"],
            "scope": "总结本检查点。",
            "reference_points": ["目标", "影响", "下一步"],
        },
    ],
)
def test_all_whitelisted_card_types_have_strict_typed_contracts(
    payload: dict[str, object],
) -> None:
    card: Any = TypeAdapter(CoachCardDraft).validate_python(payload)

    assert card.card_type == payload["card_type"]
    with pytest.raises(ValidationError):
        TypeAdapter(CoachCardDraft).validate_python({**payload, "unexpected": True})


def test_unknown_card_type_fails_closed() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(CoachCardDraft).validate_python(
            {
                "card_type": "html_widget",
                "prompt": "render arbitrary component",
                "source_ref_ids": ["source-1"],
                "html": "<script>run()</script>",
            }
        )


def test_coach_evaluation_requires_evidence_from_learner_answer() -> None:
    with pytest.raises(ValidationError):
        CoachAnswerEvaluationOutput.model_validate(
            {
                "score_percent": 80,
                "mastered": True,
                "evidence_from_answer": [],
                "missing_points": [],
                "misconception": None,
                "feedback": "回答覆盖了主要内容。",
                "improvement_action": "补充决策参与人。",
                "next_suggestion": "继续训练",
                "uncertainty": 0.1,
                "source_ref_ids": ["source-1"],
            }
        )


def test_profile_freezes_exactly_three_checkpoints_and_bounded_remediation() -> None:
    profile = CoachProfileSnapshot.model_validate(_profile_payload())

    assert tuple(item.checkpoint_key for item in profile.checkpoints) == (
        "identify",
        "express",
        "transfer",
    )
    assert profile.mastery_rule.threshold_percent == 82
    assert profile.remediation_policy.maximum_automatic_cycles == 2

    too_few = _profile_payload()
    too_few["checkpoints"] = list(too_few["checkpoints"])[:2]
    with pytest.raises(ValidationError):
        CoachProfileSnapshot.model_validate(too_few)

    unknown_competency = _profile_payload()
    checkpoints = list(unknown_competency["checkpoints"])
    checkpoints[0] = {**checkpoints[0], "competency_keys": ["unknown"]}
    unknown_competency["checkpoints"] = checkpoints
    with pytest.raises(ValidationError):
        CoachProfileSnapshot.model_validate(unknown_competency)


def test_coach_ai_schemas_and_durable_tasks_are_explicitly_registered() -> None:
    schemas = build_coach_ai_schema_registry()
    assert set(schemas._inputs) == {  # noqa: SLF001 - registration contract
        COACH_CARD_GENERATION_INPUT_SCHEMA,
        COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
        COACH_EXPLANATION_INPUT_SCHEMA,
    }
    assert set(schemas._outputs) == {  # noqa: SLF001 - registration contract
        COACH_CARD_GENERATION_OUTPUT_SCHEMA,
        COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
        COACH_EXPLANATION_OUTPUT_SCHEMA,
    }

    registry = TaskRegistry()
    register_coach_task_definitions(registry)
    assert registry.registered_types() == tuple(
        sorted(
            (
                COACH_CARD_GENERATION_TASK_TYPE,
                COACH_ANSWER_EVALUATION_TASK_TYPE,
                COACH_ASSISTANCE_TASK_TYPE,
            )
        )
    )
    for task_type in registry.registered_types():
        definition = registry.resolve(task_type, 1)
        assert definition.handler is None
        assert definition.allowed_data_classifications == frozenset({"confidential"})
        assert definition.max_payload_bytes == 1_024
