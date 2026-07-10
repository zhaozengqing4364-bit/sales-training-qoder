from __future__ import annotations

from dataclasses import replace

import pytest

from sales_trainer.schemas import NewcomerPathModuleConfig
from sales_trainer.services.path_prerequisite_policy import (
    PrerequisiteModuleState,
    PrerequisiteReferenceError,
    evaluate_prerequisites,
    validate_prerequisite_references,
)


def _module(
    module_key: str,
    order_index: int,
    target_unit_id: str | None,
    *,
    enabled: bool = True,
    module_type: str = "audio_scoring",
    unlock_after_unit_ids: list[str] | None = None,
) -> NewcomerPathModuleConfig:
    return NewcomerPathModuleConfig.model_validate(
        {
            "module_key": module_key,
            "module_type": module_type,
            "enabled": enabled,
            "order_index": order_index,
            "title": module_key,
            "target_unit_id": target_unit_id,
            "unlock_after_unit_ids": unlock_after_unit_ids or [],
        }
    )


def _state(
    module_key: str,
    order_index: int,
    target_unit_id: str,
    *,
    module_type: str | None = "audio_scoring",
    unlock_after_unit_ids: tuple[str, ...] = (),
    enabled: bool = True,
    completion_satisfied: bool = False,
    already_locked: bool = False,
) -> PrerequisiteModuleState:
    return PrerequisiteModuleState(
        module_key=module_key,
        module_type=module_type,
        order_index=order_index,
        target_unit_ids=(target_unit_id,),
        unlock_after_unit_ids=unlock_after_unit_ids,
        enabled=enabled,
        completion_satisfied=completion_satisfied,
        already_locked=already_locked,
    )


def test_should_accept_earlier_enabled_completable_prerequisite() -> None:
    modules = [
        _module("ppt_explanation", 1, "ppt-unit"),
        _module(
            "company_product_demo",
            2,
            "demo-unit",
            unlock_after_unit_ids=["ppt-unit"],
        ),
    ]

    validate_prerequisite_references(modules)


@pytest.mark.parametrize(
    ("dependencies", "expected_fragment"),
    [
        (["missing-unit"], "不存在"),
        (["second-unit"], "必须早于"),
    ],
)
def test_should_reject_unknown_or_future_prerequisite_reference(
    dependencies: list[str],
    expected_fragment: str,
) -> None:
    modules = [
        _module(
            "ppt_explanation",
            1,
            "first-unit",
            unlock_after_unit_ids=dependencies,
        ),
        _module("company_product_demo", 2, "second-unit"),
    ]

    with pytest.raises(PrerequisiteReferenceError, match=expected_fragment):
        validate_prerequisite_references(modules)


@pytest.mark.parametrize(
    "owner",
    [
        _module("ppt_explanation", 1, "owner-unit", enabled=False),
        _module(
            "realtime_roleplay",
            1,
            "owner-unit",
            module_type="realtime_roleplay",
        ),
        _module(
            "business_skills",
            1,
            "owner-unit",
            module_type="article_exam",
        ),
    ],
)
def test_should_reject_non_blocking_or_non_completable_owner(
    owner: NewcomerPathModuleConfig,
) -> None:
    modules = [
        owner,
        _module(
            "company_product_demo",
            2,
            "dependent-unit",
            unlock_after_unit_ids=["owner-unit"],
        ),
    ]

    with pytest.raises(PrerequisiteReferenceError):
        validate_prerequisite_references(modules)


def test_should_reject_target_owned_by_multiple_modules() -> None:
    modules = [
        _module("ppt_explanation", 1, "shared-unit"),
        _module("company_product_demo", 2, "shared-unit"),
    ]

    with pytest.raises(PrerequisiteReferenceError, match="多个模块"):
        validate_prerequisite_references(modules)


def test_should_lock_until_every_prerequisite_is_completed() -> None:
    first = _state(
        "ppt_explanation",
        1,
        "first-unit",
        completion_satisfied=False,
    )
    second = _state(
        "company_product_demo",
        2,
        "second-unit",
        unlock_after_unit_ids=("first-unit",),
    )

    locked = evaluate_prerequisites([second, first])
    unlocked = evaluate_prerequisites(
        [second, replace(first, completion_satisfied=True)]
    )

    assert locked["company_product_demo"].locked is True
    assert locked["company_product_demo"].unmet_unit_ids == ("first-unit",)
    assert locked["company_product_demo"].reason_code == (
        "[NEWCOMER_PREREQUISITE_NOT_COMPLETED]"
    )
    assert locked["company_product_demo"].reason == ("请先完成前置训练，再开始本任务。")
    assert unlocked["company_product_demo"].locked is False
    assert unlocked["company_product_demo"].reason_code is None


@pytest.mark.parametrize(
    "states",
    [
        [
            _state(
                "company_product_demo",
                2,
                "second-unit",
                unlock_after_unit_ids=("missing-unit",),
            )
        ],
        [
            _state("ppt_explanation", 1, "first-unit", enabled=False),
            _state(
                "company_product_demo",
                2,
                "second-unit",
                unlock_after_unit_ids=("first-unit",),
            ),
        ],
        [
            _state("ppt_explanation", 1, "shared-unit"),
            _state("company_product_demo", 2, "shared-unit"),
        ],
        [
            _state("duplicate", 1, "first-unit"),
            _state("duplicate", 2, "second-unit"),
        ],
    ],
)
def test_should_fail_closed_for_historical_invalid_state(
    states: list[PrerequisiteModuleState],
) -> None:
    decisions = evaluate_prerequisites(states)

    assert any(
        decision.locked
        and decision.reason_code == "[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]"
        for decision in decisions.values()
    )


def test_should_not_relax_an_existing_owner_lock() -> None:
    first = _state(
        "ppt_explanation",
        1,
        "first-unit",
        completion_satisfied=True,
        already_locked=True,
    )
    second = _state(
        "company_product_demo",
        2,
        "second-unit",
        unlock_after_unit_ids=("first-unit",),
    )

    decisions = evaluate_prerequisites([first, second])

    assert decisions["ppt_explanation"].locked is True
    assert decisions["company_product_demo"].locked is True
    assert decisions["company_product_demo"].reason_code == (
        "[NEWCOMER_PREREQUISITE_NOT_COMPLETED]"
    )


def test_should_evaluate_multi_target_owner_by_referenced_target() -> None:
    owner = PrerequisiteModuleState(
        module_key="elevator_pitch",
        module_type="audio_scoring_group",
        order_index=1,
        target_unit_ids=("pitch-3m", "pitch-5m"),
        unlock_after_unit_ids=(),
        enabled=True,
        completion_satisfied=True,
        completed_target_unit_ids=("pitch-3m",),
    )
    depends_on_completed = _state(
        "ppt_explanation",
        2,
        "ppt-unit",
        unlock_after_unit_ids=("pitch-3m",),
    )
    depends_on_incomplete = _state(
        "company_product_demo",
        3,
        "demo-unit",
        unlock_after_unit_ids=("pitch-5m",),
    )

    decisions = evaluate_prerequisites(
        [owner, depends_on_completed, depends_on_incomplete]
    )

    assert decisions["ppt_explanation"].locked is False
    assert decisions["company_product_demo"].locked is True
    assert decisions["company_product_demo"].unmet_unit_ids == ("pitch-5m",)


@pytest.mark.parametrize(
    ("module_key", "module_type"),
    [
        ("realtime_roleplay", "realtime_roleplay"),
        ("realtime_roleplay_placeholder", "realtime_placeholder"),
        ("business_skills", "article_exam"),
    ],
)
def test_should_fail_closed_when_historical_owner_is_not_prerequisite_eligible(
    module_key: str,
    module_type: str,
) -> None:
    owner = PrerequisiteModuleState(
        module_key=module_key,
        module_type=module_type,
        order_index=1,
        target_unit_ids=("owner-unit",),
        unlock_after_unit_ids=(),
        enabled=True,
        completion_satisfied=True,
    )
    dependent = _state(
        "company_product_demo",
        2,
        "dependent-unit",
        unlock_after_unit_ids=("owner-unit",),
    )

    decisions = evaluate_prerequisites([owner, dependent])

    assert decisions["company_product_demo"].locked is True
    assert decisions["company_product_demo"].reason_code == (
        "[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]"
    )
