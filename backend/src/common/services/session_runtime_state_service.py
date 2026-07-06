"""Machine-readable practice session runtime lifecycle state.

Persists under PracticeSession.runtime_state["_lifecycle"] per ADR boundary contract.
Business ``status`` (preparing/in_progress/...) stays unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from common.db.models import PracticeSession
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

SessionRuntimeLifecycleState = Literal[
    "draft",
    "validated",
    "runnable",
    "started",
    "completed",
    "failed",
]

LIFECYCLE_KEY = "_lifecycle"
_TERMINAL_STATES: frozenset[str] = frozenset({"completed", "failed"})

_TERMINAL_BUSINESS_STATUSES: frozenset[str] = frozenset({"completed", "scoring"})

_ALLOWED_TRANSITIONS: dict[str | None, frozenset[str]] = {
    None: frozenset({"validated", "runnable", "completed", "failed"}),
    "draft": frozenset({"validated", "runnable", "failed"}),
    "validated": frozenset({"runnable", "failed"}),
    "runnable": frozenset({"started", "failed", "runnable"}),
    "started": frozenset({"completed", "failed", "started"}),
    "completed": frozenset(),
    "failed": frozenset({"runnable", "validated"}),
}


@dataclass(frozen=True, slots=True)
class SessionRuntimeLifecycleSnapshot:
    state: SessionRuntimeLifecycleState | None
    failure_code: str | None
    failure_hint: str | None
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class SessionRuntimeTransitionResult:
    changed: bool
    from_state: SessionRuntimeLifecycleState | None
    to_state: SessionRuntimeLifecycleState | None
    rejected: bool = False


def read_lifecycle_snapshot(
    runtime_state: dict[str, Any] | None,
) -> SessionRuntimeLifecycleSnapshot:
    if not isinstance(runtime_state, dict):
        return SessionRuntimeLifecycleSnapshot(
            state=None,
            failure_code=None,
            failure_hint=None,
            updated_at=None,
        )
    payload = runtime_state.get(LIFECYCLE_KEY)
    if not isinstance(payload, dict):
        return SessionRuntimeLifecycleSnapshot(
            state=None,
            failure_code=None,
            failure_hint=None,
            updated_at=None,
        )
    raw_state = payload.get("state")
    state = str(raw_state) if isinstance(raw_state, str) and raw_state else None
    failure_code = _optional_str(payload.get("failure_code"))
    failure_hint = _optional_str(payload.get("failure_hint"))
    updated_at = _optional_str(payload.get("updated_at"))
    return SessionRuntimeLifecycleSnapshot(
        state=cast(SessionRuntimeLifecycleState | None, state),
        failure_code=failure_code,
        failure_hint=failure_hint,
        updated_at=updated_at,
    )


def is_transition_allowed(
    from_state: SessionRuntimeLifecycleState | None,
    to_state: SessionRuntimeLifecycleState,
) -> bool:
    return to_state in _ALLOWED_TRANSITIONS.get(from_state, frozenset())


def suggested_action_for_lifecycle(
    *,
    lifecycle_state: SessionRuntimeLifecycleState | None,
    runnable: bool,
) -> str:
    if runnable:
        return "connect_ws"
    if lifecycle_state == "failed":
        return "show_failure"
    if lifecycle_state == "completed":
        return "view_report"
    if lifecycle_state == "started":
        return "resume_session"
    if lifecycle_state == "runnable":
        return "connect_ws"
    if lifecycle_state in {"validated", "draft", None}:
        return "run_preflight"
    return "return_entry"


class SessionRuntimeStateService:
    """Persist and validate session runtime lifecycle transitions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_snapshot(self, session_id: str) -> SessionRuntimeLifecycleSnapshot:
        session = await self._load_session(session_id)
        if session is None:
            return SessionRuntimeLifecycleSnapshot(
                state=None,
                failure_code=None,
                failure_hint=None,
                updated_at=None,
            )
        return read_lifecycle_snapshot(
            session.runtime_state if isinstance(session.runtime_state, dict) else None
        )

    async def initialize_on_create(
        self,
        session_id: str,
        *,
        has_runtime_snapshot: bool,
        source: str,
    ) -> SessionRuntimeTransitionResult:
        target: SessionRuntimeLifecycleState = (
            "runnable" if has_runtime_snapshot else "validated"
        )
        return await self.transition(
            session_id,
            to_state=target,
            source=source,
        )

    async def ensure_lifecycle_initialized(
        self,
        session_id: str,
        *,
        source: str,
    ) -> SessionRuntimeLifecycleSnapshot:
        """Lazy backfill for sessions created before runtime lifecycle persistence."""
        session = await self._load_session(session_id)
        if session is None:
            return SessionRuntimeLifecycleSnapshot(
                state=None,
                failure_code=None,
                failure_hint=None,
                updated_at=None,
            )

        runtime_state: dict[str, Any] = (
            session.runtime_state if isinstance(session.runtime_state, dict) else {}
        )
        current = read_lifecycle_snapshot(runtime_state)
        if current.state is not None:
            return current

        business_status = str(getattr(session, "status", "") or "")
        if business_status in _TERMINAL_BUSINESS_STATUSES:
            await self.transition(
                session_id,
                to_state="completed",
                source=source,
            )
            return await self.get_snapshot(session_id)

        from common.services.runtime_gate import RuntimeGate

        preflight = await RuntimeGate(self._db).evaluate_session(session_id)
        if preflight is None:
            return current

        if preflight.runnable:
            await self.transition(
                session_id,
                to_state="runnable",
                source=source,
            )
        else:
            await self.transition(
                session_id,
                to_state="validated",
                source=source,
            )
        return await self.get_snapshot(session_id)

    async def apply_preflight_result(
        self,
        session_id: str,
        *,
        runnable: bool,
        code: str | None,
        hint: str | None,
    ) -> SessionRuntimeTransitionResult:
        current = await self.get_snapshot(session_id)
        if current.state in {"started", "completed"}:
            return SessionRuntimeTransitionResult(
                changed=False,
                from_state=current.state,
                to_state=current.state,
            )
        if runnable:
            return await self.transition(
                session_id,
                to_state="runnable",
                source="preflight",
            )
        return await self.transition(
            session_id,
            to_state="failed",
            failure_code=code or "PREFLIGHT_BLOCKED",
            failure_hint=hint,
            source="preflight",
        )

    async def mark_started(
        self,
        session_id: str,
        *,
        source: str,
    ) -> SessionRuntimeTransitionResult:
        return await self.transition(
            session_id,
            to_state="started",
            source=source,
        )

    async def mark_completed(
        self,
        session_id: str,
        *,
        source: str,
    ) -> SessionRuntimeTransitionResult:
        return await self.transition(
            session_id,
            to_state="completed",
            source=source,
        )

    async def mark_failed(
        self,
        session_id: str,
        *,
        failure_code: str,
        failure_hint: str | None = None,
        source: str,
    ) -> SessionRuntimeTransitionResult:
        return await self.transition(
            session_id,
            to_state="failed",
            failure_code=failure_code,
            failure_hint=failure_hint,
            source=source,
        )

    async def transition(
        self,
        session_id: str,
        *,
        to_state: SessionRuntimeLifecycleState,
        failure_code: str | None = None,
        failure_hint: str | None = None,
        source: str,
    ) -> SessionRuntimeTransitionResult:
        session = await self._load_session(session_id)
        if session is None:
            logger.warning(
                "session_runtime_lifecycle_session_missing",
                session_id=session_id,
                to_state=to_state,
                source=source,
            )
            return SessionRuntimeTransitionResult(
                changed=False,
                from_state=None,
                to_state=None,
                rejected=True,
            )

        runtime_state: dict[str, Any] = (
            dict(session.runtime_state)
            if isinstance(session.runtime_state, dict)
            else {}
        )
        current = read_lifecycle_snapshot(runtime_state)
        from_state = current.state

        if from_state == to_state and to_state not in {"runnable", "started"}:
            return SessionRuntimeTransitionResult(
                changed=False,
                from_state=from_state,
                to_state=to_state,
            )

        if (
            from_state in _TERMINAL_STATES
            and to_state != from_state
            and not (
                from_state == "failed"
                and to_state in {"runnable", "validated"}
            )
        ):
            logger.warning(
                "session_runtime_lifecycle_transition_rejected",
                session_id=session_id,
                from_state=from_state,
                to_state=to_state,
                source=source,
                reason="terminal_state",
            )
            return SessionRuntimeTransitionResult(
                changed=False,
                from_state=from_state,
                to_state=from_state,
                rejected=True,
            )

        if not is_transition_allowed(from_state, to_state):
            logger.warning(
                "session_runtime_lifecycle_transition_rejected",
                session_id=session_id,
                from_state=from_state,
                to_state=to_state,
                source=source,
                reason="illegal_transition",
            )
            return SessionRuntimeTransitionResult(
                changed=False,
                from_state=from_state,
                to_state=from_state,
                rejected=True,
            )

        if to_state == "failed" and not failure_code:
            failure_code = "RUNTIME_FATAL"

        lifecycle_payload: dict[str, Any] = {
            "state": to_state,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if to_state == "failed":
            lifecycle_payload["failure_code"] = failure_code
            lifecycle_payload["failure_hint"] = failure_hint
        else:
            lifecycle_payload["failure_code"] = None
            lifecycle_payload["failure_hint"] = None

        runtime_state[LIFECYCLE_KEY] = lifecycle_payload
        setattr(session, "runtime_state", runtime_state)
        flag_modified(session, "runtime_state")
        await self._db.commit()

        logger.info(
            "session_runtime_lifecycle_transition_applied",
            session_id=session_id,
            from_state=from_state,
            to_state=to_state,
            source=source,
            failure_code=failure_code if to_state == "failed" else None,
        )
        return SessionRuntimeTransitionResult(
            changed=True,
            from_state=from_state,
            to_state=to_state,
        )

    async def _load_session(self, session_id: str) -> PracticeSession | None:
        result = await self._db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        return result.scalar_one_or_none()


def _optional_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
