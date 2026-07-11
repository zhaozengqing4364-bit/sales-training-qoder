"""Immutable evidence contract consumed by Evaluation use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EvidenceTurn:
    role: str
    content: str
    turn_number: int
    evidence_reference: str | None = None


@dataclass(frozen=True, slots=True)
class SessionEvidence:
    session_id: str
    scenario_type: str | None
    transcript: str
    presentation_id: str | None = None
    turns: tuple[EvidenceTurn, ...] = ()
    evidence_references: tuple[str, ...] = ()
    missing_reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_evaluable(self) -> bool:
        return bool(self.transcript.strip()) and not self.missing_reasons


class SessionEvidencePort(Protocol):
    async def load(self, session_id: str) -> SessionEvidence: ...
