from __future__ import annotations

from common.db.models import PracticeSession
from common.runtime_descriptor import TrainingRuntimeDescriptor
from common.services.practice_session_ports import register_runtime_descriptor_builder
from training_runtime.service import build_training_runtime_descriptor


def _build_training_runtime_descriptor(
    session: PracticeSession,
    scenario_type: str | None,
) -> TrainingRuntimeDescriptor:
    return build_training_runtime_descriptor(session, scenario_type=scenario_type)


def register_training_runtime_practice_session_contributor() -> None:
    register_runtime_descriptor_builder(_build_training_runtime_descriptor)
