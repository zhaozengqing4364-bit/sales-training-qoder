from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, TypeVar

from .state import (
    ConnectionPhase,
    GroundingPhase,
    GroundingState,
    RealtimeSessionState,
    RealtimeStateTransitionError,
    TurnPhase,
)


@dataclass(frozen=True, slots=True)
class RealtimeTransition:
    event_name: str
    snapshot: dict[str, object]


class ScenarioTurnHooks(Protocol):
    scenario_type: str

    def on_transition(self, transition: RealtimeTransition) -> None: ...


@dataclass(slots=True)
class NoopScenarioTurnHooks:
    scenario_type: str

    def on_transition(self, transition: RealtimeTransition) -> None:
        del transition


_TransitionResult = TypeVar("_TransitionResult")


class RealtimeSessionEngine:
    def __init__(self, *, scenario_type: str, hooks: ScenarioTurnHooks) -> None:
        if hooks.scenario_type != scenario_type:
            raise ValueError("scenario_hook_mismatch")
        self._state = RealtimeSessionState(scenario_type=scenario_type)
        self._hooks = hooks

    @property
    def state(self) -> RealtimeSessionState:
        return RealtimeSessionState.from_dict(self.snapshot())

    def snapshot(self) -> dict[str, object]:
        return self._state.to_dict()

    def restore(self, payload: Mapping[str, object]) -> None:
        pristine_state = RealtimeSessionState(scenario_type=self._state.scenario_type)
        if self._state != pristine_state:
            raise RealtimeStateTransitionError("engine_restore_requires_pristine_state")
        restored = RealtimeSessionState.from_dict(payload)
        if restored.scenario_type != self._state.scenario_type:
            raise ValueError("engine_snapshot_scenario_mismatch")
        self._state = restored

    def begin_connection(self, session_id: str) -> None:
        def mutate() -> None:
            connection = self._state.connection
            if connection.phase is not ConnectionPhase.DISCONNECTED:
                raise RealtimeStateTransitionError("connection_start_not_allowed")
            if (
                connection.session_id is not None
                and connection.session_id != session_id
            ):
                raise RealtimeStateTransitionError("connection_session_mismatch")
            if not session_id.strip():
                raise ValueError("connection_session_id_must_be_non_empty")
            connection.session_id = session_id
            connection.epoch += 1
            connection.reconnecting = connection.epoch > 1
            connection.healthy = False
            connection.reason = None
            connection.phase = ConnectionPhase.CONNECTING

        self._transition("connection.connecting", mutate)

    def mark_connected(self) -> None:
        def mutate() -> None:
            connection = self._state.connection
            if connection.phase is not ConnectionPhase.CONNECTING:
                raise RealtimeStateTransitionError("connection_not_connecting")
            connection.phase = ConnectionPhase.CONNECTED
            connection.healthy = True
            connection.reason = None

        self._transition("connection.connected", mutate)

    def mark_degraded(self, *, reason: str) -> None:
        def mutate() -> None:
            connection = self._state.connection
            if connection.phase not in {
                ConnectionPhase.CONNECTING,
                ConnectionPhase.CONNECTED,
            }:
                raise RealtimeStateTransitionError("connection_degrade_not_allowed")
            if not reason.strip():
                raise ValueError("connection_reason_must_be_non_empty")
            connection.phase = ConnectionPhase.DEGRADED
            connection.healthy = False
            connection.reason = reason

        self._transition("connection.degraded", mutate)

    def begin_close(self, *, reason: str) -> None:
        def mutate() -> None:
            connection = self._state.connection
            if connection.phase not in {
                ConnectionPhase.CONNECTING,
                ConnectionPhase.CONNECTED,
                ConnectionPhase.DEGRADED,
            }:
                raise RealtimeStateTransitionError("connection_close_not_allowed")
            if not reason.strip():
                raise ValueError("connection_reason_must_be_non_empty")
            connection.phase = ConnectionPhase.CLOSING
            connection.healthy = False
            connection.reason = reason

        self._transition("connection.closing", mutate)

    def mark_disconnected(self, *, reason: str) -> None:
        def mutate() -> None:
            connection = self._state.connection
            if connection.phase is not ConnectionPhase.CLOSING:
                raise RealtimeStateTransitionError("connection_not_closing")
            if not reason.strip():
                raise ValueError("connection_reason_must_be_non_empty")
            connection.phase = ConnectionPhase.DISCONNECTED
            connection.healthy = False
            connection.reason = reason

        self._transition("connection.disconnected", mutate)

    def begin_turn(self, *, request_id: int, stream_id: str) -> None:
        def mutate() -> None:
            turn = self._state.turn
            if turn.phase in {
                TurnPhase.RECEIVING,
                TurnPhase.GENERATING,
                TurnPhase.STREAMING,
            }:
                raise RealtimeStateTransitionError("active_turn_reentry")
            if request_id < 0:
                raise ValueError("turn_request_id_must_be_non_negative")
            if turn.request_id is not None and request_id <= turn.request_id:
                raise RealtimeStateTransitionError("stale_turn_request")
            if not stream_id.strip():
                raise ValueError("turn_stream_id_must_be_non_empty")
            turn.phase = TurnPhase.RECEIVING
            turn.request_id = request_id
            turn.response_id = None
            turn.stream_id = stream_id
            turn.interruption_reason = None
            turn.timeout_reason = None
            turn.completion_reason = None

        self._transition("turn.receiving", mutate)

    def mark_response_started(self, *, response_id: str) -> None:
        def mutate() -> None:
            turn = self._state.turn
            if turn.phase is not TurnPhase.RECEIVING:
                raise RealtimeStateTransitionError("response_start_not_allowed")
            if not response_id.strip():
                raise ValueError("turn_response_id_must_be_non_empty")
            turn.phase = TurnPhase.GENERATING
            turn.response_id = response_id

        self._transition("turn.generating", mutate)

    def mark_streaming(self) -> None:
        def mutate() -> None:
            turn = self._state.turn
            if turn.phase is not TurnPhase.GENERATING:
                raise RealtimeStateTransitionError("stream_start_not_allowed")
            turn.phase = TurnPhase.STREAMING

        self._transition("turn.streaming", mutate)

    def complete_turn(self, *, request_id: int, reason: str = "response_done") -> bool:
        turn = self._state.turn
        if turn.request_id != request_id:
            raise RealtimeStateTransitionError("stale_turn_completion")
        if turn.phase is TurnPhase.COMPLETED:
            return False

        def mutate() -> bool:
            if turn.phase not in {TurnPhase.GENERATING, TurnPhase.STREAMING}:
                raise RealtimeStateTransitionError("turn_completion_not_allowed")
            if not reason.strip():
                raise ValueError("turn_completion_reason_must_be_non_empty")
            turn.phase = TurnPhase.COMPLETED
            turn.completion_reason = reason
            return True

        return self._transition("turn.completed", mutate)

    def interrupt_turn(self, *, request_id: int, reason: str) -> None:
        def mutate() -> None:
            turn = self._state.turn
            if turn.request_id != request_id:
                raise RealtimeStateTransitionError("stale_turn_interruption")
            if turn.phase not in {
                TurnPhase.RECEIVING,
                TurnPhase.GENERATING,
                TurnPhase.STREAMING,
            }:
                raise RealtimeStateTransitionError("turn_interruption_not_allowed")
            if not reason.strip():
                raise ValueError("turn_interruption_reason_must_be_non_empty")
            turn.phase = TurnPhase.INTERRUPTED
            turn.interruption_reason = reason

        self._transition("turn.interrupted", mutate)

    def timeout_turn(self, *, request_id: int, reason: str) -> None:
        def mutate() -> None:
            turn = self._state.turn
            if turn.request_id != request_id:
                raise RealtimeStateTransitionError("stale_turn_timeout")
            if turn.phase not in {
                TurnPhase.RECEIVING,
                TurnPhase.GENERATING,
                TurnPhase.STREAMING,
            }:
                raise RealtimeStateTransitionError("turn_timeout_not_allowed")
            if not reason.strip():
                raise ValueError("turn_timeout_reason_must_be_non_empty")
            turn.phase = TurnPhase.TIMED_OUT
            turn.timeout_reason = reason

        self._transition("turn.timed_out", mutate)

    def begin_grounding(self, *, decision_id: str, policy_hash: str) -> None:
        def mutate() -> None:
            grounding = self._state.grounding
            if grounding.phase is GroundingPhase.PREPARING:
                raise RealtimeStateTransitionError("grounding_already_preparing")
            if grounding.decision_id == decision_id:
                raise RealtimeStateTransitionError("stale_grounding_decision")
            if not decision_id.strip():
                raise ValueError("grounding_decision_id_must_be_non_empty")
            if not policy_hash.strip():
                raise ValueError("grounding_frozen_policy_hash_must_be_non_empty")
            grounding.phase = GroundingPhase.PREPARING
            grounding.decision_id = decision_id
            grounding.frozen_policy_hash = policy_hash
            grounding.mode = None
            grounding.diagnostics = {}

        self._transition("grounding.preparing", mutate)

    def resolve_grounding(
        self,
        *,
        outcome: str,
        mode: str,
        diagnostics: Mapping[str, object] | None = None,
    ) -> None:
        def mutate() -> None:
            grounding = self._state.grounding
            if grounding.phase is not GroundingPhase.PREPARING:
                raise RealtimeStateTransitionError("grounding_not_preparing")
            try:
                phase = GroundingPhase(outcome)
            except ValueError as exc:
                raise RealtimeStateTransitionError(
                    "unsupported_grounding_outcome"
                ) from exc
            if phase not in {
                GroundingPhase.READY,
                GroundingPhase.BLOCKED,
                GroundingPhase.DEGRADED,
            }:
                raise RealtimeStateTransitionError("unsupported_grounding_outcome")
            if not mode.strip():
                raise ValueError("grounding_mode_must_be_non_empty")
            validated_diagnostics = GroundingState.validate_diagnostics(
                diagnostics or {}
            )
            grounding.phase = phase
            grounding.mode = mode
            grounding.diagnostics = validated_diagnostics

        self._transition(f"grounding.{outcome}", mutate)

    def record_evidence(
        self,
        *,
        evidence_key: str,
        evidence_type: str,
        turn_number: int,
        payload: bytes,
    ) -> bool:
        payload_digest = f"sha256:{sha256(payload).hexdigest()}"
        return self.record_evidence_digest(
            evidence_key=evidence_key,
            evidence_type=evidence_type,
            turn_number=turn_number,
            payload_digest=payload_digest,
        )

    def record_evidence_digest(
        self,
        *,
        evidence_key: str,
        evidence_type: str,
        turn_number: int,
        payload_digest: str,
    ) -> bool:
        if (
            len(payload_digest) != 71
            or not payload_digest.startswith("sha256:")
            or any(
                character not in "0123456789abcdef" for character in payload_digest[7:]
            )
        ):
            raise ValueError("evidence_payload_digest_must_be_sha256")
        evidence = self._state.evidence
        existing = evidence.records.get(evidence_key)
        if existing is not None:
            return evidence.record(
                evidence_key=evidence_key,
                evidence_type=evidence_type,
                turn_number=turn_number,
                payload_digest=payload_digest,
            )

        def mutate() -> bool:
            return evidence.record(
                evidence_key=evidence_key,
                evidence_type=evidence_type,
                turn_number=turn_number,
                payload_digest=payload_digest,
            )

        return self._transition("evidence.recorded", mutate)

    def mark_evidence_pending(self, evidence_key: str) -> bool:
        evidence = self._state.evidence
        if (
            evidence_key in evidence.pending_flush_keys
            or evidence_key in evidence.acknowledged_keys
        ):
            return False
        return self._transition(
            "evidence.flush_pending",
            lambda: evidence.mark_pending(evidence_key),
        )

    def acknowledge_evidence(self, evidence_key: str) -> bool:
        evidence = self._state.evidence
        if evidence_key in evidence.acknowledged_keys:
            return False
        return self._transition(
            "evidence.flush_acknowledged",
            lambda: evidence.acknowledge(evidence_key),
        )

    def _transition(
        self,
        event_name: str,
        mutation: Callable[[], _TransitionResult],
    ) -> _TransitionResult:
        result = mutation()
        transition = RealtimeTransition(
            event_name=event_name,
            snapshot=self.snapshot(),
        )
        self._hooks.on_transition(transition)
        return result
