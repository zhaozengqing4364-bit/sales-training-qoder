from __future__ import annotations

import pytest
from pydantic import ValidationError

from newcomer_training.contracts import (
    ActivityDefinition,
    LessonActivityConfig,
    LessonActivityDefinition,
    PathRevisionDraft,
    RetryPolicy,
    StageDefinition,
)


def _lesson(activity_id: str = "lesson-product") -> dict[str, object]:
    return {
        "activity_id": activity_id,
        "type": "lesson",
        "title": "理解产品价值",
        "objective": "能够准确说明产品解决的问题",
        "why_it_matters": "这是后续需求发现和价值表达的基础",
        "steps": ["学习关键概念", "完成知识检查点"],
        "success_criteria": ["完成全部必修检查点"],
        "estimated_minutes": 20,
        "required": True,
        "prerequisite_activity_ids": [],
        "ai_dependency": "none",
        "retry_policy": {"max_attempts": 0, "retry_interval_seconds": 0},
        "config": {
            "learning_unit_revision_id": "learning-unit-revision-1",
            "required_checkpoint_ids": ["checkpoint-1"],
        },
    }


def _quiz() -> dict[str, object]:
    return {
        "activity_id": "quiz-product",
        "type": "quiz",
        "title": "产品知识测验",
        "objective": "验证产品知识掌握情况",
        "why_it_matters": "确保能够在客户沟通中准确表达",
        "steps": ["阅读规则", "完成测验"],
        "success_criteria": ["达到试卷修订中的通过标准"],
        "estimated_minutes": 15,
        "required": True,
        "prerequisite_activity_ids": ["lesson-product"],
        "ai_dependency": "optional",
        "retry_policy": {"max_attempts": 3, "retry_interval_seconds": 300},
        "config": {"quiz_revision_id": "quiz-revision-1"},
    }


def test_path_revision_is_stage_directly_owning_typed_activities() -> None:
    draft = PathRevisionDraft.model_validate(
        {
            "title": "新人销售基础训练",
            "revision_label": "2026.07 标准版",
            "stages": [
                {
                    "stage_id": "stage-product",
                    "sequence": 1,
                    "title": "产品与客户基础",
                    "objective": "建立可靠的产品与客户基础认知",
                    "entry_conditions": [],
                    "completion_rule": "all_required",
                    "visibility": "learner",
                    "activities": [_lesson(), _quiz()],
                }
            ],
        }
    )

    stage = draft.stages[0]
    assert isinstance(stage, StageDefinition)
    assert [activity.type for activity in stage.activities] == ["lesson", "quiz"]
    assert isinstance(stage.activities[0], ActivityDefinition)
    assert stage.activities[0].config.learning_unit_revision_id == (
        "learning-unit-revision-1"
    )
    assert not hasattr(stage, "modules")


def test_path_revision_rejects_module_layer_realtime_and_arbitrary_config() -> None:
    with pytest.raises(ValidationError):
        PathRevisionDraft.model_validate(
            {
                "title": "非法路径",
                "revision_label": "v1",
                "stages": [
                    {
                        "stage_id": "stage-1",
                        "sequence": 1,
                        "title": "阶段",
                        "objective": "目标",
                        "entry_conditions": [],
                        "completion_rule": "all_required",
                        "visibility": "learner",
                        "modules": [],
                        "activities": [_lesson()],
                    }
                ],
            }
        )

    invalid = _lesson("realtime")
    invalid["type"] = "realtime_roleplay"
    invalid["config"] = {"runtime_profile_id": "provider-direct"}
    with pytest.raises(ValidationError):
        PathRevisionDraft.model_validate(
            {
                "title": "非法路径",
                "revision_label": "v1",
                "stages": [
                    {
                        "stage_id": "stage-1",
                        "sequence": 1,
                        "title": "阶段",
                        "objective": "目标",
                        "entry_conditions": [],
                        "completion_rule": "all_required",
                        "visibility": "learner",
                        "activities": [invalid],
                    }
                ],
            }
        )


def test_path_revision_rejects_duplicate_ids_and_forward_prerequisites() -> None:
    duplicate = _lesson()
    with pytest.raises(ValidationError):
        PathRevisionDraft.model_validate(
            {
                "title": "非法路径",
                "revision_label": "v1",
                "stages": [
                    {
                        "stage_id": "stage-1",
                        "sequence": 1,
                        "title": "阶段一",
                        "objective": "目标",
                        "entry_conditions": [],
                        "completion_rule": "all_required",
                        "visibility": "learner",
                        "activities": [duplicate, duplicate],
                    }
                ],
            }
        )

    lesson = _lesson()
    lesson["prerequisite_activity_ids"] = ["quiz-product"]
    with pytest.raises(ValidationError):
        PathRevisionDraft.model_validate(
            {
                "title": "非法路径",
                "revision_label": "v1",
                "stages": [
                    {
                        "stage_id": "stage-1",
                        "sequence": 1,
                        "title": "阶段一",
                        "objective": "目标",
                        "entry_conditions": [],
                        "completion_rule": "all_required",
                        "visibility": "learner",
                        "activities": [lesson, _quiz()],
                    }
                ],
            }
        )


def test_working_path_can_preserve_an_unbound_resource_for_later_completion() -> None:
    activity = _lesson()
    activity["config"] = {
        "learning_unit_revision_id": "",
        "required_checkpoint_ids": [],
    }

    draft = PathRevisionDraft.model_validate(
        {
            "title": "新人销售基础训练",
            "revision_label": "未完成草稿",
            "stages": [
                {
                    "stage_id": "stage-1",
                    "sequence": 1,
                    "title": "阶段一",
                    "objective": "保留正在编辑的工作",
                    "entry_conditions": [],
                    "completion_rule": "all_required",
                    "visibility": "learner",
                    "activities": [activity],
                }
            ],
        }
    )

    assert draft.stages[0].activities[0].config.learning_unit_revision_id == ""


@pytest.mark.parametrize(
    "factory",
    [
        lambda: RetryPolicy(max_attempts=2, retry_interval_seconds=0),
        lambda: LessonActivityConfig(
            learning_unit_revision_id="unit-revision-1",
            required_checkpoint_ids=("checkpoint-1", "checkpoint-1"),
        ),
    ],
)
def test_contracts_reject_invalid_retry_and_checkpoint_shapes(factory) -> None:
    with pytest.raises(ValidationError):
        factory()


@pytest.mark.parametrize(
    "updates",
    [
        {"prerequisite_activity_ids": ["earlier", "earlier"]},
        {"prerequisite_activity_ids": ["lesson-product"]},
        {"competency_keys": ["product_knowledge", "product_knowledge"]},
    ],
)
def test_activity_contract_rejects_duplicate_self_and_competency_links(
    updates: dict[str, object],
) -> None:
    payload = _lesson()
    payload.update(updates)

    with pytest.raises(ValidationError):
        LessonActivityDefinition.model_validate(payload)


@pytest.mark.parametrize("duplicate_field", ["stage_id", "sequence"])
def test_path_contract_rejects_duplicate_stage_identity(
    duplicate_field: str,
) -> None:
    first = {
        "stage_id": "stage-1",
        "sequence": 1,
        "title": "阶段一",
        "objective": "目标一",
        "activities": [_lesson("lesson-1")],
    }
    second = {
        "stage_id": "stage-2",
        "sequence": 2,
        "title": "阶段二",
        "objective": "目标二",
        "activities": [_lesson("lesson-2")],
    }
    second[duplicate_field] = first[duplicate_field]

    with pytest.raises(ValidationError):
        PathRevisionDraft.model_validate(
            {
                "title": "非法路径",
                "revision_label": "v1",
                "stages": [first, second],
            }
        )
