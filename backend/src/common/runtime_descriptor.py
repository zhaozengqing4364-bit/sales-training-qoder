from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class TrainingRuntimeSubject(StrEnum):
    TRAINING_SCENARIO_RUNTIME = "training_scenario_runtime"


class TrainingRuntimeDescriptor(BaseModel):
    subject: TrainingRuntimeSubject = TrainingRuntimeSubject.TRAINING_SCENARIO_RUNTIME
    session_id: str
    scenario_type: str
    agent_id: str | None = None
    persona_id: str | None = None
    presentation_id: str | None = None
    voice_mode: str | None = None
    runtime_profile_id: str | None = None
    focus_intent: dict[str, Any] | None = None
    training_task_id: str | None = None
