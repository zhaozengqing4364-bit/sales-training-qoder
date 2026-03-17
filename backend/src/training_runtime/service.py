"""Helpers for constructing unified training runtime descriptors."""

from __future__ import annotations

from common.db.models import PracticeSession

from .models import TrainingRuntimeDescriptor


def build_training_runtime_descriptor(
    session: PracticeSession,
    *,
    scenario_type: str | None = None,
) -> TrainingRuntimeDescriptor:
    """Build the canonical runtime descriptor for one persisted session."""

    resolved_scenario_type = str(
        scenario_type
        or getattr(getattr(session, "scenario", None), "scenario_type", None)
        or "sales"
    ).lower()

    return TrainingRuntimeDescriptor(
        session_id=str(session.session_id),
        scenario_type=resolved_scenario_type,
        agent_id=str(session.agent_id) if getattr(session, "agent_id", None) else None,
        persona_id=(
            str(session.persona_id) if getattr(session, "persona_id", None) else None
        ),
        presentation_id=(
            str(session.presentation_id)
            if getattr(session, "presentation_id", None)
            else None
        ),
        voice_mode=str(getattr(session, "voice_mode", "") or "") or None,
        runtime_profile_id=(
            str(session.voice_runtime_profile_id)
            if getattr(session, "voice_runtime_profile_id", None)
            else None
        ),
    )
