"""
Session lifecycle state machine utilities.

This module centralizes lifecycle transition rules for practice sessions so
REST and WebSocket control paths share the same persistence semantics.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.attributes import set_committed_value

from common.db.models import PracticeSession, Scenario
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

SessionLifecycleAction = Literal["start", "pause", "resume", "end"]
SessionLifecycleRacePriority = Literal["critical"]

_TERMINAL_STATUSES = {"scoring", "completed"}


class InvalidSessionTransitionError(ValueError):
    """Raised when lifecycle action violates the allowed state machine."""

    def __init__(
        self,
        *,
        action: SessionLifecycleAction,
        from_status: str,
        expected: str,
        scenario_type: str | None = None,
    ) -> None:
        self.action = action
        self.from_status = from_status
        self.expected = expected
        self.scenario_type = scenario_type
        super().__init__(self.message)

    @property
    def message(self) -> str:
        scenario_text = (
            f", scenario_type={self.scenario_type}" if self.scenario_type else ""
        )
        return (
            "[INVALID_SESSION_TRANSITION] "
            f"action={self.action}, from_status={self.from_status}, expected={self.expected}{scenario_text}"
        )


@dataclass(slots=True)
class SessionLifecycleTransition:
    session: PracticeSession
    scenario_type: str
    action: SessionLifecycleAction
    from_status: str
    to_status: str
    changed: bool

    @property
    def ai_state(self) -> str:
        if self.to_status == "in_progress":
            return "listening"
        return "idle"

    @property
    def session_ended(self) -> bool:
        return self.to_status in _TERMINAL_STATUSES


@dataclass(frozen=True, slots=True)
class SessionLifecycleRaceScenario:
    slug: str
    scenario_type: str
    initial_status: str
    winner_action: SessionLifecycleAction
    stale_action: SessionLifecycleAction
    expected_status: str
    priority: SessionLifecycleRacePriority
    risk: str
    proof_goal: str


@dataclass(frozen=True, slots=True)
class SessionLifecyclePersistedState:
    status: str
    start_time: datetime | None
    end_time: datetime | None
    total_duration_seconds: int | None
    scenario_type: str | None


SESSION_LIFECYCLE_RACE_SCENARIOS: tuple[SessionLifecycleRaceScenario, ...] = (
    SessionLifecycleRaceScenario(
        slug="sales_end_beats_stale_resume",
        scenario_type="sales",
        initial_status="paused",
        winner_action="end",
        stale_action="resume",
        expected_status="scoring",
        priority="critical",
        risk="A stale resume must not reopen a sales session that already converged to scoring.",
        proof_goal="Protect the scoring/report handoff from paused->in_progress regressions.",
    ),
    SessionLifecycleRaceScenario(
        slug="presentation_end_beats_stale_pause",
        scenario_type="presentation",
        initial_status="in_progress",
        winner_action="end",
        stale_action="pause",
        expected_status="completed",
        priority="critical",
        risk="A stale pause must not reopen a presentation session that already converged to completed.",
        proof_goal="Keep presentation terminal semantics stable while concurrency control is added later.",
    ),
)


class SessionLifecycleService:
    """State machine service for session lifecycle transitions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_session_with_scenario(
        self, session_id: str
    ) -> tuple[PracticeSession | None, str | None]:
        stmt = (
            select(PracticeSession, Scenario.scenario_type)
            .join(
                Scenario,
                Scenario.scenario_id == PracticeSession.scenario_id,
                isouter=True,
            )
            .where(PracticeSession.session_id == session_id)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None, None

        session, scenario_type = row
        return session, (str(scenario_type) if scenario_type else None)

    @staticmethod
    def terminal_status_for_scenario(scenario_type: str | None) -> str:
        return (
            "completed"
            if (scenario_type or "").lower() == "presentation"
            else "scoring"
        )

    @staticmethod
    def is_input_allowed(status: str) -> bool:
        return status == "in_progress"

    @staticmethod
    def _coerce_utc_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _is_sqlalchemy_instance(session: Any) -> bool:
        return hasattr(session, "_sa_instance_state")

    def _apply_session_values(
        self,
        session: PracticeSession,
        values: dict[str, Any],
        *,
        mark_committed: bool,
    ) -> None:
        for field, value in values.items():
            if mark_committed and self._is_sqlalchemy_instance(session):
                set_committed_value(session, field, value)
            else:
                setattr(session, field, value)

    async def _load_persisted_state(
        self,
        session_id: str,
    ) -> SessionLifecyclePersistedState | None:
        stmt = (
            select(
                PracticeSession.status,
                PracticeSession.start_time,
                PracticeSession.end_time,
                PracticeSession.total_duration_seconds,
                Scenario.scenario_type,
            )
            .join(
                Scenario,
                Scenario.scenario_id == PracticeSession.scenario_id,
                isouter=True,
            )
            .where(PracticeSession.session_id == session_id)
        )

        if isinstance(self.db, AsyncSession) and self.db.bind is not None:
            factory = async_sessionmaker(
                self.db.bind,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            async with factory() as read_db:
                row = (await read_db.execute(stmt)).first()
        else:
            row = (await self.db.execute(stmt)).first()

        if row is None:
            return None

        (
            status,
            start_time,
            end_time,
            total_duration_seconds,
            persisted_scenario_type,
        ) = row
        return SessionLifecyclePersistedState(
            status=str(status or "preparing"),
            start_time=start_time,
            end_time=end_time,
            total_duration_seconds=total_duration_seconds,
            scenario_type=str(persisted_scenario_type)
            if persisted_scenario_type
            else None,
        )

    def _sync_session_to_persisted_state(
        self,
        session: PracticeSession,
        persisted_state: SessionLifecyclePersistedState,
    ) -> None:
        self._apply_session_values(
            session,
            {
                "status": persisted_state.status,
                "start_time": persisted_state.start_time,
                "end_time": persisted_state.end_time,
                "total_duration_seconds": persisted_state.total_duration_seconds,
            },
            mark_committed=True,
        )

    async def _persist_transition_with_optimistic_status_guard(
        self,
        *,
        session: PracticeSession,
        scenario_type: str,
        action: SessionLifecycleAction,
        from_status: str,
        update_values: dict[str, Any],
        timestamp: datetime,
        retry_on_conflict: bool,
    ) -> SessionLifecycleTransition | None:
        session_id = getattr(session, "session_id", None)
        if not session_id:
            self._apply_session_values(session, update_values, mark_committed=False)
            await self.db.flush()
            return None

        result = await self.db.execute(
            update(PracticeSession)
            .where(PracticeSession.session_id == session_id)
            .where(PracticeSession.status == from_status)
            .values(**update_values)
        )
        rowcount = getattr(result, "rowcount", None)
        if rowcount and rowcount > 0:
            self._apply_session_values(session, update_values, mark_committed=True)
            return None

        persisted_state = await self._load_persisted_state(str(session_id))
        if persisted_state is None:
            self._apply_session_values(session, update_values, mark_committed=False)
            await self.db.flush()
            return None

        self._sync_session_to_persisted_state(session, persisted_state)
        resolved_scenario_type = (
            persisted_state.scenario_type or scenario_type or "sales"
        ).lower()
        converged_to_terminal = (
            persisted_state.status in _TERMINAL_STATUSES and action != "end"
        )
        logger.warning(
            "practice_session_lifecycle_concurrency_conflict",
            session_id=str(session_id),
            action=action,
            stale_status=from_status,
            persisted_status=persisted_state.status,
            scenario_type=resolved_scenario_type,
            converged_to_terminal=converged_to_terminal,
        )

        if converged_to_terminal:
            return SessionLifecycleTransition(
                session=session,
                scenario_type=resolved_scenario_type,
                action=action,
                from_status=persisted_state.status,
                to_status=persisted_state.status,
                changed=False,
            )

        if not retry_on_conflict:
            return SessionLifecycleTransition(
                session=session,
                scenario_type=resolved_scenario_type,
                action=action,
                from_status=persisted_state.status,
                to_status=persisted_state.status,
                changed=False,
            )

        return await self.transition(
            session=session,
            scenario_type=resolved_scenario_type,
            action=action,
            now=timestamp,
            _retry_on_conflict=False,
        )

    async def transition(
        self,
        *,
        session: PracticeSession,
        scenario_type: str | None,
        action: SessionLifecycleAction,
        now: datetime | None = None,
        _retry_on_conflict: bool = True,
    ) -> SessionLifecycleTransition:
        resolved_scenario_type = (scenario_type or "sales").lower()
        timestamp = now or datetime.now(UTC)

        from_status = str(session.status or "preparing")
        to_status = from_status
        changed = False
        update_values: dict[str, Any] = {}

        if action == "start":
            if from_status == "in_progress":
                return SessionLifecycleTransition(
                    session=session,
                    scenario_type=resolved_scenario_type,
                    action=action,
                    from_status=from_status,
                    to_status=from_status,
                    changed=False,
                )
            if from_status != "preparing":
                raise InvalidSessionTransitionError(
                    action=action,
                    from_status=from_status,
                    expected="preparing|in_progress",
                    scenario_type=resolved_scenario_type,
                )

            to_status = "in_progress"
            changed = True
            update_values = {
                "status": to_status,
                "start_time": timestamp,
            }

        elif action == "pause":
            if from_status == "paused":
                return SessionLifecycleTransition(
                    session=session,
                    scenario_type=resolved_scenario_type,
                    action=action,
                    from_status=from_status,
                    to_status=from_status,
                    changed=False,
                )
            if from_status != "in_progress":
                raise InvalidSessionTransitionError(
                    action=action,
                    from_status=from_status,
                    expected="in_progress|paused",
                    scenario_type=resolved_scenario_type,
                )

            to_status = "paused"
            changed = True
            update_values = {"status": to_status}

        elif action == "resume":
            if from_status == "in_progress":
                return SessionLifecycleTransition(
                    session=session,
                    scenario_type=resolved_scenario_type,
                    action=action,
                    from_status=from_status,
                    to_status=from_status,
                    changed=False,
                )
            if from_status != "paused":
                raise InvalidSessionTransitionError(
                    action=action,
                    from_status=from_status,
                    expected="paused|in_progress",
                    scenario_type=resolved_scenario_type,
                )

            to_status = "in_progress"
            changed = True
            update_values = {"status": to_status}

        elif action == "end":
            target_status = self.terminal_status_for_scenario(resolved_scenario_type)
            if from_status in _TERMINAL_STATUSES:
                return SessionLifecycleTransition(
                    session=session,
                    scenario_type=resolved_scenario_type,
                    action=action,
                    from_status=from_status,
                    to_status=from_status,
                    changed=False,
                )
            if from_status not in {"in_progress", "paused"}:
                raise InvalidSessionTransitionError(
                    action=action,
                    from_status=from_status,
                    expected="in_progress|paused|completed|scoring",
                    scenario_type=resolved_scenario_type,
                )

            end_time = session.end_time or timestamp
            start_time = session.start_time or timestamp
            total_duration_seconds = session.total_duration_seconds
            if end_time and start_time:
                end_time_utc = self._coerce_utc_timestamp(end_time)
                start_time_utc = self._coerce_utc_timestamp(start_time)
                total_duration_seconds = max(
                    0,
                    int((end_time_utc - start_time_utc).total_seconds()),
                )

            to_status = target_status
            changed = True
            update_values = {
                "status": target_status,
                "end_time": end_time,
                "start_time": start_time,
                "total_duration_seconds": total_duration_seconds,
            }

        else:
            raise ValueError(f"Unsupported lifecycle action: {action}")

        if changed:
            conflict_transition = (
                await self._persist_transition_with_optimistic_status_guard(
                    session=session,
                    scenario_type=resolved_scenario_type,
                    action=action,
                    from_status=from_status,
                    update_values=update_values,
                    timestamp=timestamp,
                    retry_on_conflict=_retry_on_conflict,
                )
            )
            if conflict_transition is not None:
                return conflict_transition

        return SessionLifecycleTransition(
            session=session,
            scenario_type=resolved_scenario_type,
            action=action,
            from_status=from_status,
            to_status=to_status,
            changed=changed,
        )

    async def trigger_report_generation_if_needed(
        self,
        transition: SessionLifecycleTransition,
    ) -> None:
        """
        Trigger report generation after transaction commit.

        This method is intentionally separate from `transition` so callers can
        control transaction boundaries and avoid state/report non-atomic windows.
        """
        if transition.action != "end" or not transition.changed:
            return
        await self._trigger_report_generation(
            transition.session.session_id,
            transition.scenario_type,
        )

    async def _trigger_report_generation(
        self,
        session_id: str,
        scenario_type: str,
    ) -> None:
        """Trigger async report generation when session ends.

        This is fire-and-forget to not block the session end response.
        Saves realtime scoring context before triggering report generation.
        """
        try:
            from evaluation.services.realtime_scoring import RealtimeScoringService
            from evaluation.services.report_generation_trigger import (
                trigger_report_generation,
            )

            # Save realtime scoring context for report generation (Track D-F integration)
            try:
                scoring_service = RealtimeScoringService()
                await scoring_service.save_scoring_context(session_id, self.db)
                logger.info(
                    "scoring_context_saved",
                    session_id=session_id,
                )
            except Exception as scoring_error:
                # Log but don't block report generation
                logger.warning(
                    "scoring_context_save_failed",
                    session_id=session_id,
                    error=str(scoring_error),
                )

            # Fire-and-forget report generation
            asyncio.create_task(trigger_report_generation(session_id, scenario_type))
            logger.info(
                "report_generation_triggered",
                session_id=session_id,
                scenario_type=scenario_type,
            )
        except Exception as e:
            # Log but don't fail the session end
            logger.error(
                "report_generation_trigger_failed",
                session_id=session_id,
                error=str(e),
            )

    async def transition_by_target_status(
        self,
        *,
        session: PracticeSession,
        scenario_type: str | None,
        target_status: str,
        now: datetime | None = None,
    ) -> SessionLifecycleTransition:
        normalized_target = (target_status or "").lower()
        current_status = str(session.status or "preparing")
        expected_terminal = self.terminal_status_for_scenario(scenario_type)

        if normalized_target == "in_progress":
            action: SessionLifecycleAction = (
                "resume" if current_status == "paused" else "start"
            )
        elif normalized_target == "paused":
            action = "pause"
        elif normalized_target in _TERMINAL_STATUSES:
            if (
                normalized_target != expected_terminal
                and current_status not in _TERMINAL_STATUSES
            ):
                raise InvalidSessionTransitionError(
                    action="end",
                    from_status=current_status,
                    expected=expected_terminal,
                    scenario_type=(scenario_type or "sales").lower(),
                )
            action = "end"
        else:
            raise InvalidSessionTransitionError(
                action="start",
                from_status=current_status,
                expected="in_progress|paused|completed|scoring",
                scenario_type=(scenario_type or "sales").lower(),
            )

        return await self.transition(
            session=session,
            scenario_type=scenario_type,
            action=action,
            now=now,
        )
