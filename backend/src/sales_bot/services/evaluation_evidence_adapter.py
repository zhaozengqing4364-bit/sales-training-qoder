"""Sales compatibility evidence supplied at the application composition root."""

from __future__ import annotations

from uuid import UUID

from evaluation.ports.evidence import EvidenceTurn, SessionEvidence
from sales_bot.services.context_manager import context_manager


async def load_legacy_sales_session_evidence(
    session_id: str,
) -> SessionEvidence | None:
    try:
        context_result = await context_manager.get_context(UUID(session_id))
    except (RuntimeError, ValueError):
        return None
    if not context_result.is_success or context_result.value is None:
        return None
    turns = tuple(
        item
        for turn_number, turn in enumerate(context_result.value.turns, start=1)
        for item in (
            EvidenceTurn(
                role="user",
                content=str(turn.user_text or ""),
                turn_number=turn_number,
            ),
            EvidenceTurn(
                role="assistant",
                content=str(turn.bot_response or ""),
                turn_number=turn_number,
            ),
        )
        if item.content.strip()
    )
    transcript = "\n".join(
        f"{'用户' if item.role == 'user' else 'AI'}: {item.content}" for item in turns
    )
    if not transcript.strip():
        return None
    return SessionEvidence(
        session_id=session_id,
        scenario_type="sales",
        transcript=transcript,
        turns=turns,
    )
