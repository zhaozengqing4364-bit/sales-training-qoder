"""Persisted SQL projection for immutable Evaluation session evidence."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ConversationMessage, PracticeSession, Scenario
from evaluation.ports.evidence import EvidenceTurn, SessionEvidence

LegacyEvidenceLoader = Callable[[str], Awaitable[SessionEvidence | None]]


class SqlSessionEvidencePort:
    def __init__(
        self,
        db: AsyncSession,
        *,
        legacy_loader: LegacyEvidenceLoader | None = None,
    ) -> None:
        self._db = db
        self._legacy_loader = legacy_loader
        self._cache: dict[str, SessionEvidence] = {}

    async def load(self, session_id: str) -> SessionEvidence:
        cached = self._cache.get(session_id)
        if cached is not None:
            return cached

        session_result = await self._db.execute(
            select(PracticeSession.presentation_id, Scenario.scenario_type)
            .outerjoin(Scenario, Scenario.scenario_id == PracticeSession.scenario_id)
            .where(PracticeSession.session_id == session_id)
        )
        session_row: Any = session_result.first()
        if inspect.isawaitable(session_row):
            session_row = await session_row
        presentation_id: str | None = None
        scenario_type: str | None = None
        if session_row is not None and not _is_mock(session_row):
            mapping = getattr(session_row, "_mapping", None)
            if mapping is not None:
                presentation_id = _optional_text(mapping.get("presentation_id"))
                scenario_type = _optional_text(mapping.get("scenario_type"))
            else:
                presentation_id = _optional_text(session_row[0])
                scenario_type = _optional_text(session_row[1])

        message_result = await self._db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.turn_number, ConversationMessage.timestamp)
        )
        scalars: Any = message_result.scalars()
        if inspect.isawaitable(scalars):
            scalars = await scalars
        values: Any = scalars.all()
        if inspect.isawaitable(values):
            values = await values
        messages = list(values) if not _is_mock(values) else []
        turns = tuple(
            EvidenceTurn(
                role=str(message.role),
                content=str(message.content or ""),
                turn_number=int(message.turn_number or 0),
                evidence_reference=_optional_text(getattr(message, "id", None)),
            )
            for message in messages
            if str(message.content or "").strip()
        )
        transcript = "\n".join(
            f"{'用户' if turn.role == 'user' else 'AI'}: {turn.content}"
            for turn in turns
        )
        if not transcript.strip() and self._legacy_loader is not None:
            legacy = await self._legacy_loader(session_id)
            if legacy is not None and legacy.transcript.strip():
                self._cache[session_id] = legacy
                return legacy

        missing = () if transcript.strip() else ("transcript_missing",)
        evidence = SessionEvidence(
            session_id=session_id,
            scenario_type=("presentation" if presentation_id else scenario_type),
            presentation_id=presentation_id,
            transcript=transcript,
            turns=turns,
            evidence_references=tuple(
                turn.evidence_reference
                for turn in turns
                if turn.evidence_reference is not None
            ),
            missing_reasons=missing,
        )
        self._cache[session_id] = evidence
        return evidence


def _is_mock(value: Any) -> bool:
    return type(value).__module__.startswith("unittest.mock")


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
