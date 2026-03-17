"""Unified runtime subject models for training session flows."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class TrainingRuntimeSubject(StrEnum):
    """Single runtime subject across practice scenarios."""

    TRAINING_SCENARIO_RUNTIME = "training_scenario_runtime"


class TrainingRuntimeDescriptor(BaseModel):
    """Canonical runtime descriptor for one training session."""

    subject: TrainingRuntimeSubject = (
        TrainingRuntimeSubject.TRAINING_SCENARIO_RUNTIME
    )
    session_id: str
    scenario_type: str
    agent_id: str | None = None
    persona_id: str | None = None
    presentation_id: str | None = None
    voice_mode: str | None = None
    runtime_profile_id: str | None = None
