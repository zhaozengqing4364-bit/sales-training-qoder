from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

PREREQUISITE_NOT_COMPLETED_CODE = "[NEWCOMER_PREREQUISITE_NOT_COMPLETED]"
PREREQUISITE_CONFIG_INVALID_CODE = "[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]"
PREREQUISITE_NOT_COMPLETED_REASON = "请先完成前置训练，再开始本任务。"
PREREQUISITE_CONFIG_INVALID_REASON = "训练路径前置关系配置异常，请联系培训负责人。"

_LEARNING_TOPIC_SOURCE_MODULE_KEYS = frozenset({"business_skills"})
_NON_COMPLETABLE_MODULE_TYPES = frozenset({"realtime_roleplay", "realtime_placeholder"})


class PrerequisiteReferenceError(Exception):
    """Raised when a path revision contains an invalid prerequisite reference."""


@dataclass(frozen=True, slots=True)
class PrerequisiteModuleState:
    module_key: str
    module_type: str | None
    order_index: int
    target_unit_ids: tuple[str, ...]
    unlock_after_unit_ids: tuple[str, ...]
    enabled: bool
    completion_satisfied: bool
    completed_target_unit_ids: tuple[str, ...] | None = None
    already_locked: bool = False


@dataclass(frozen=True, slots=True)
class PrerequisiteDecision:
    locked: bool
    unmet_unit_ids: tuple[str, ...]
    reason_code: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class _ReferenceModule:
    module_key: str
    order_index: int
    target_unit_ids: tuple[str, ...]
    unlock_after_unit_ids: tuple[str, ...]
    enabled: bool
    module_type: str | None


def validate_prerequisite_references(modules: Iterable[Any]) -> None:
    """Validate prerequisite references without importing transport models."""

    references = tuple(_reference_module(module) for module in modules)
    module_key_counts = Counter(module.module_key for module in references)
    duplicate_module_keys = sorted(
        key for key, count in module_key_counts.items() if count > 1
    )
    if duplicate_module_keys:
        raise PrerequisiteReferenceError(
            f"训练路径存在重复模块标识：{', '.join(duplicate_module_keys)}。"
        )

    order_counts = Counter(module.order_index for module in references)
    duplicate_orders = sorted(
        order for order, count in order_counts.items() if count > 1
    )
    if duplicate_orders:
        raise PrerequisiteReferenceError(
            f"训练路径存在重复模块顺序：{', '.join(map(str, duplicate_orders))}。"
        )

    owners_by_unit: dict[str, list[_ReferenceModule]] = defaultdict(list)
    for module in references:
        for unit_id in module.target_unit_ids:
            owners_by_unit[unit_id].append(module)

    ambiguous_unit_ids = sorted(
        unit_id for unit_id, owners in owners_by_unit.items() if len(owners) > 1
    )
    if ambiguous_unit_ids:
        raise PrerequisiteReferenceError(
            f"训练单元被多个模块重复绑定：{', '.join(ambiguous_unit_ids)}。"
        )

    for module in references:
        _validate_unlock_values(module)
        for unit_id in module.unlock_after_unit_ids:
            owners = owners_by_unit.get(unit_id, [])
            if not owners:
                raise PrerequisiteReferenceError(
                    f"模块 {module.module_key} 的前置训练单元 {unit_id} 不存在。"
                )
            owner = owners[0]
            if owner.order_index >= module.order_index:
                raise PrerequisiteReferenceError(
                    f"前置模块 {owner.module_key} 必须早于模块 {module.module_key}。"
                )
            owner_error = _prerequisite_owner_error(
                module_key=owner.module_key,
                module_type=owner.module_type,
                enabled=owner.enabled,
            )
            if owner_error is not None:
                raise PrerequisiteReferenceError(owner_error)


def evaluate_prerequisites(
    states: list[PrerequisiteModuleState],
) -> dict[str, PrerequisiteDecision]:
    """Evaluate ordered prerequisites and fail closed for historical bad config."""

    module_key_counts = Counter(state.module_key for state in states)
    owners_by_unit: dict[str, list[PrerequisiteModuleState]] = defaultdict(list)
    for state in states:
        for unit_id in set(state.target_unit_ids):
            owners_by_unit[unit_id].append(state)

    ambiguous_units = {
        unit_id for unit_id, owners in owners_by_unit.items() if len(owners) != 1
    }
    structurally_invalid_keys = {
        state.module_key
        for state in states
        if module_key_counts[state.module_key] != 1
        or any(not unit_id.strip() for unit_id in state.target_unit_ids)
        or len(set(state.target_unit_ids)) != len(state.target_unit_ids)
        or any(unit_id in ambiguous_units for unit_id in state.target_unit_ids)
        or any(not unit_id.strip() for unit_id in state.unlock_after_unit_ids)
        or len(set(state.unlock_after_unit_ids)) != len(state.unlock_after_unit_ids)
    }

    decisions: dict[str, PrerequisiteDecision] = {}
    for state in sorted(states, key=lambda item: item.order_index):
        invalid_unit_ids = _runtime_invalid_unit_ids(
            state,
            owners_by_unit=owners_by_unit,
            structurally_invalid_keys=structurally_invalid_keys,
        )
        if state.module_key in structurally_invalid_keys or invalid_unit_ids:
            decisions[state.module_key] = _invalid_decision(
                invalid_unit_ids or state.unlock_after_unit_ids or state.target_unit_ids
            )
            continue

        unmet_unit_ids: list[str] = []
        inherited_invalid_unit_ids: list[str] = []
        for unit_id in state.unlock_after_unit_ids:
            owner = owners_by_unit[unit_id][0]
            owner_decision = decisions.get(owner.module_key)
            if (
                owner_decision is not None
                and owner_decision.reason_code == PREREQUISITE_CONFIG_INVALID_CODE
            ):
                inherited_invalid_unit_ids.append(unit_id)
            elif (
                not _target_completion_satisfied(owner, unit_id)
                or owner_decision is None
                or owner_decision.locked
            ):
                unmet_unit_ids.append(unit_id)

        if inherited_invalid_unit_ids:
            decisions[state.module_key] = _invalid_decision(
                tuple(inherited_invalid_unit_ids)
            )
            continue

        unmet = tuple(unmet_unit_ids)
        decisions[state.module_key] = PrerequisiteDecision(
            locked=state.already_locked or bool(unmet),
            unmet_unit_ids=unmet,
            reason_code=PREREQUISITE_NOT_COMPLETED_CODE if unmet else None,
            reason=PREREQUISITE_NOT_COMPLETED_REASON if unmet else None,
        )
    return decisions


def _target_completion_satisfied(
    owner: PrerequisiteModuleState,
    target_unit_id: str,
) -> bool:
    if owner.completed_target_unit_ids is None:
        return owner.completion_satisfied
    return target_unit_id in owner.completed_target_unit_ids


def _reference_module(module: Any) -> _ReferenceModule:
    target_unit_ids: list[str] = []
    target_unit_id = getattr(module, "target_unit_id", None)
    if target_unit_id is not None:
        if not isinstance(target_unit_id, str) or not target_unit_id.strip():
            raise PrerequisiteReferenceError("模块 target_unit_id 不能是空白值。")
        target_unit_ids.append(target_unit_id)
    for option in getattr(module, "duration_options", ()):
        option_target = getattr(option, "target_unit_id", None)
        if not isinstance(option_target, str) or not option_target.strip():
            raise PrerequisiteReferenceError("时长选项 target_unit_id 不能是空白值。")
        if option_target not in target_unit_ids:
            target_unit_ids.append(option_target)

    return _ReferenceModule(
        module_key=str(getattr(module, "module_key")),
        order_index=int(getattr(module, "order_index")),
        target_unit_ids=tuple(target_unit_ids),
        unlock_after_unit_ids=tuple(getattr(module, "unlock_after_unit_ids", ())),
        enabled=bool(getattr(module, "enabled")),
        module_type=getattr(module, "module_type", None),
    )


def _validate_unlock_values(module: _ReferenceModule) -> None:
    if any(
        not isinstance(unit_id, str) or not unit_id.strip()
        for unit_id in module.unlock_after_unit_ids
    ):
        raise PrerequisiteReferenceError(
            f"模块 {module.module_key} 的前置训练单元不能包含空白值。"
        )
    if len(set(module.unlock_after_unit_ids)) != len(module.unlock_after_unit_ids):
        raise PrerequisiteReferenceError(
            f"模块 {module.module_key} 的前置训练单元存在重复值。"
        )


def _runtime_invalid_unit_ids(
    state: PrerequisiteModuleState,
    *,
    owners_by_unit: dict[str, list[PrerequisiteModuleState]],
    structurally_invalid_keys: set[str],
) -> tuple[str, ...]:
    invalid: list[str] = []
    for unit_id in state.unlock_after_unit_ids:
        owners = owners_by_unit.get(unit_id, [])
        if (
            len(owners) != 1
            or _prerequisite_owner_error(
                module_key=owners[0].module_key,
                module_type=owners[0].module_type,
                enabled=owners[0].enabled,
            )
            is not None
            or owners[0].order_index >= state.order_index
            or owners[0].module_key in structurally_invalid_keys
        ):
            invalid.append(unit_id)
    return tuple(invalid)


def _prerequisite_owner_error(
    *,
    module_key: str,
    module_type: str | None,
    enabled: bool,
) -> str | None:
    if not enabled:
        return f"前置模块 {module_key} 已停用，不能作为解锁条件。"
    if module_key in _LEARNING_TOPIC_SOURCE_MODULE_KEYS:
        return f"学习专题来源模块 {module_key} 不能作为主路径前置条件。"
    if module_type in _NON_COMPLETABLE_MODULE_TYPES:
        return f"模块 {module_key} 不可完成，不能作为前置条件。"
    return None


def _invalid_decision(unit_ids: tuple[str, ...]) -> PrerequisiteDecision:
    return PrerequisiteDecision(
        locked=True,
        unmet_unit_ids=unit_ids,
        reason_code=PREREQUISITE_CONFIG_INVALID_CODE,
        reason=PREREQUISITE_CONFIG_INVALID_REASON,
    )
