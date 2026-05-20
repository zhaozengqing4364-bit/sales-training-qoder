"""HTTP runtime preflight facade delegating to RuntimeGate."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.services.runtime_gate import (
    RuntimeGate,
    RuntimeGateResult,
    RuntimePreflightResult,
)

__all__ = [
    "RuntimeGate",
    "RuntimeGateResult",
    "RuntimePreflightResult",
    "RuntimePreflightService",
]


class RuntimePreflightService:
    """Evaluate whether a persisted session can open its runtime WebSocket."""

    def __init__(self, db: AsyncSession) -> None:
        self._gate = RuntimeGate(db)

    async def evaluate_session(self, session_id: str) -> RuntimeGateResult | None:
        return await self._gate.evaluate_session(session_id)
