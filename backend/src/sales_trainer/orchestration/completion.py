"""Pure progress aggregation across activity, module, phase and path levels."""

from __future__ import annotations

from dataclasses import dataclass

from sales_trainer.orchestration.activities.base import ActivityProjection
from sales_trainer.orchestration.contracts import (
    ModuleConfig,
    PhaseConfig,
    TrainingPathPayload,
)


@dataclass(frozen=True, slots=True)
class ProgressAggregate:
    completed: bool
    completed_count: int
    total_required: int
    percent: float


def aggregate_module_progress(
    module: ModuleConfig, states: dict[str, ActivityProjection]
) -> ProgressAggregate:
    policy = module.completion_policy
    if policy.mode == "at_least_count":
        member_ids = tuple(policy.activity_ids)
        target = int(policy.count or 0)
    else:
        member_ids = tuple(
            item.activity_id for item in module.activities if item.required
        )
        target = len(member_ids)
    completed_count = sum(
        1
        for activity_id in member_ids
        if states.get(activity_id) is not None and states[activity_id].completed
    )
    return _aggregate(completed_count, target)


def aggregate_phase_progress(
    phase: PhaseConfig, modules: dict[str, ProgressAggregate]
) -> ProgressAggregate:
    required_ids = tuple(item.module_id for item in phase.modules if item.required)
    completed = sum(
        1
        for item_id in required_ids
        if modules.get(item_id) and modules[item_id].completed
    )
    return _aggregate(completed, len(required_ids))


def aggregate_path_progress(
    path: TrainingPathPayload, phases: dict[str, ProgressAggregate]
) -> ProgressAggregate:
    required_ids = tuple(item.phase_id for item in path.phases if item.required)
    completed = sum(
        1
        for item_id in required_ids
        if phases.get(item_id) and phases[item_id].completed
    )
    return _aggregate(completed, len(required_ids))


def _aggregate(completed_count: int, target: int) -> ProgressAggregate:
    completed = completed_count >= target
    percent = 100.0 if target == 0 else min(100.0, completed_count * 100.0 / target)
    return ProgressAggregate(completed, completed_count, target, percent)


__all__ = [
    "ProgressAggregate",
    "aggregate_module_progress",
    "aggregate_path_progress",
    "aggregate_phase_progress",
]
