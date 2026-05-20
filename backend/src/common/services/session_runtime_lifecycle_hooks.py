"""Fire-and-forget hooks for session runtime lifecycle from WS routers."""

from __future__ import annotations

from common.db.session import AsyncSessionLocal
from common.services.session_runtime_state_service import SessionRuntimeStateService


async def mark_session_runtime_started(session_id: str, *, source: str) -> None:
    async with AsyncSessionLocal() as db:
        await SessionRuntimeStateService(db).mark_started(session_id, source=source)


async def mark_session_runtime_completed(session_id: str, *, source: str) -> None:
    async with AsyncSessionLocal() as db:
        await SessionRuntimeStateService(db).mark_completed(session_id, source=source)


async def mark_session_runtime_failed(
    session_id: str,
    *,
    failure_code: str,
    failure_hint: str | None = None,
    source: str,
) -> None:
    async with AsyncSessionLocal() as db:
        await SessionRuntimeStateService(db).mark_failed(
            session_id,
            failure_code=failure_code,
            failure_hint=failure_hint,
            source=source,
        )
