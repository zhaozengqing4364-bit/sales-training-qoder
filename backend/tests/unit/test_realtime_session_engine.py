from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from training_runtime.realtime import (
    ENGINE_STATE_VERSION,
    ConnectionPhase,
    ConnectionState,
    EvidenceState,
    GroundingPhase,
    GroundingState,
    NoopScenarioTurnHooks,
    RealtimeSessionEngine,
    RealtimeSessionState,
    RealtimeStateTransitionError,
    RealtimeTransition,
    TurnPhase,
    TurnState,
)

REQUIRED_GOLDEN_CONTRACT_IDS = {
    "admission.invalid_session",
    "admission.runtime_gate",
    "admission.unauthorized",
    "admission.owner_scope",
    "conversation.connect_start_text_audio_response_done",
    "transport.binary_audio",
    "transport.timeout_backpressure_degraded",
    "snapshot.frozen_policy_kb_fail_closed",
    "reconnect.epoch_monotonic",
    "evidence.transcript_score_report_idempotent",
    "roleplay.observation_record_only",
    "rollout.single_writer_rollback",
}
FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "realtime"
    / "golden_conversation_contract_v1.json"
)


def test_should_freeze_required_golden_conversation_contracts() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert payload["version"] == 1
    contracts = payload["contracts"]
    assert {contract["id"] for contract in contracts} == REQUIRED_GOLDEN_CONTRACT_IDS
    assert all(
        set(contract)
        == {
            "id",
            "category",
            "stable_expectation",
            "evidence",
            "rollback_relevance",
        }
        for contract in contracts
    )
    assert all(contract["evidence"] for contract in contracts)


def test_should_create_explicit_default_state() -> None:
    state = RealtimeSessionState(scenario_type="presentation")

    assert ENGINE_STATE_VERSION == 1
    assert state.connection == ConnectionState()
    assert state.connection.phase is ConnectionPhase.DISCONNECTED
    assert state.turn == TurnState()
    assert state.turn.phase is TurnPhase.IDLE
    assert state.grounding == GroundingState()
    assert state.grounding.phase is GroundingPhase.EMPTY
    assert state.evidence == EvidenceState()


def test_should_round_trip_state_without_sharing_mutable_data() -> None:
    state = RealtimeSessionState(scenario_type="presentation")
    state.connection.session_id = "session-1"
    state.connection.epoch = 3
    state.grounding.diagnostics["source"] = "frozen_policy"
    assert state.evidence.record(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload_digest="sha256:learner",
    )
    state.evidence.mark_pending("transcript:1:user")

    payload = state.to_dict()
    restored = RealtimeSessionState.from_dict(payload)

    assert restored == state
    payload["connection"]["epoch"] = 99  # type: ignore[index]
    payload["grounding"]["diagnostics"]["source"] = "mutated"  # type: ignore[index]
    assert state.connection.epoch == 3
    assert state.grounding.diagnostics == {"source": "frozen_policy"}


def test_should_reject_unsupported_future_state_version() -> None:
    with pytest.raises(ValueError, match="unsupported_engine_state_version"):
        RealtimeSessionState.from_dict(
            {
                "version": ENGINE_STATE_VERSION + 1,
                "scenario_type": "presentation",
            }
        )


def test_should_restore_version_one_payload_with_optional_fields_absent() -> None:
    restored = RealtimeSessionState.from_dict(
        {"version": 1, "scenario_type": "presentation"}
    )

    assert restored == RealtimeSessionState(scenario_type="presentation")


def test_should_dedupe_identical_evidence_and_reject_conflicts() -> None:
    evidence = EvidenceState()

    assert evidence.record(
        evidence_key="score:turn-1",
        evidence_type="score",
        turn_number=1,
        payload_digest="sha256:stable",
    )
    assert not evidence.record(
        evidence_key="score:turn-1",
        evidence_type="score",
        turn_number=1,
        payload_digest="sha256:stable",
    )

    with pytest.raises(RealtimeStateTransitionError, match="evidence_key_conflict"):
        evidence.record(
            evidence_key="score:turn-1",
            evidence_type="score",
            turn_number=1,
            payload_digest="sha256:changed",
        )


def test_should_acknowledge_only_pending_evidence() -> None:
    evidence = EvidenceState()
    evidence.record(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload_digest="sha256:stable",
    )

    with pytest.raises(RealtimeStateTransitionError, match="evidence_not_pending"):
        evidence.acknowledge("transcript:1:user")
    with pytest.raises(RealtimeStateTransitionError, match="unknown_evidence_key"):
        evidence.mark_pending("missing")

    evidence.mark_pending("transcript:1:user")
    assert evidence.acknowledge("transcript:1:user")
    assert not evidence.acknowledge("transcript:1:user")
    assert evidence.pending_flush_keys == set()
    assert evidence.acknowledged_keys == {"transcript:1:user"}


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: ConnectionState(epoch=-1), "connection_epoch_must_be_non_negative"),
        (
            lambda: EvidenceState.from_dict(
                {
                    "records": {
                        "bad": {
                            "evidence_key": "bad",
                            "evidence_type": "transcript",
                            "turn_number": -1,
                            "payload_digest": "sha256:bad",
                        }
                    }
                }
            ),
            "evidence_turn_number_must_be_non_negative",
        ),
    ],
)
def test_should_reject_negative_state_counters(
    factory: Callable[[], object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


class RecordingHooks:
    scenario_type = "presentation"

    def __init__(self) -> None:
        self.transitions: list[RealtimeTransition] = []

    def on_transition(self, transition: RealtimeTransition) -> None:
        self.transitions.append(transition)


def test_should_run_legal_session_path_and_emit_post_transition_snapshots() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)

    engine.begin_connection("session-1")
    engine.mark_connected()
    engine.begin_turn(request_id=1, stream_id="stream-1")
    engine.mark_response_started(response_id="response-1")
    engine.mark_streaming()
    engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")
    engine.resolve_grounding(outcome="ready", mode="grounded")
    assert engine.record_evidence(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload=b"learner transcript",
    )
    engine.complete_turn(request_id=1)
    engine.begin_close(reason="client_disconnect")
    engine.mark_disconnected(reason="client_disconnect")

    assert [transition.event_name for transition in hooks.transitions] == [
        "connection.connecting",
        "connection.connected",
        "turn.receiving",
        "turn.generating",
        "turn.streaming",
        "grounding.preparing",
        "grounding.ready",
        "evidence.recorded",
        "turn.completed",
        "connection.closing",
        "connection.disconnected",
    ]
    assert hooks.transitions[0].snapshot["connection"]["phase"] == "connecting"  # type: ignore[index]
    assert hooks.transitions[-1].snapshot == engine.snapshot()
    record = engine.state.evidence.records["transcript:1:user"]
    assert record.payload_digest.startswith("sha256:")
    assert "learner transcript" not in json.dumps(engine.snapshot())


def test_should_reject_active_turn_reentry_and_stale_request_ids() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_turn(request_id=2, stream_id="stream-2")

    with pytest.raises(RealtimeStateTransitionError, match="active_turn_reentry"):
        engine.begin_turn(request_id=3, stream_id="stream-3")

    engine.mark_response_started(response_id="response-2")
    engine.mark_streaming()
    with pytest.raises(RealtimeStateTransitionError, match="stale_turn_completion"):
        engine.complete_turn(request_id=1)
    engine.complete_turn(request_id=2)

    with pytest.raises(RealtimeStateTransitionError, match="stale_turn_request"):
        engine.begin_turn(request_id=2, stream_id="stream-replayed")


def test_should_reject_illegal_turn_and_grounding_transitions() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )

    with pytest.raises(
        RealtimeStateTransitionError, match="response_start_not_allowed"
    ):
        engine.mark_response_started(response_id="response-1")
    with pytest.raises(RealtimeStateTransitionError, match="grounding_not_preparing"):
        engine.resolve_grounding(outcome="ready", mode="grounded")

    engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")
    engine.resolve_grounding(outcome="blocked", mode="fail_closed")
    with pytest.raises(RealtimeStateTransitionError, match="stale_grounding_decision"):
        engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")


def test_should_increment_connection_epoch_on_reconnect() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )

    engine.begin_connection("session-1")
    engine.mark_connected()
    engine.begin_close(reason="network_reset")
    engine.mark_disconnected(reason="network_reset")
    engine.begin_connection("session-1")

    assert engine.state.connection.epoch == 2
    assert engine.state.connection.reconnecting is True


def test_should_make_evidence_replay_idempotent() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    kwargs = {
        "evidence_key": "audio:turn-1",
        "evidence_type": "audio",
        "turn_number": 1,
        "payload": b"audio bytes",
    }

    assert engine.record_evidence(**kwargs)
    assert not engine.record_evidence(**kwargs)
    assert [transition.event_name for transition in hooks.transitions] == [
        "evidence.recorded"
    ]

    with pytest.raises(RealtimeStateTransitionError, match="evidence_key_conflict"):
        engine.record_evidence(**{**kwargs, "payload": b"different audio"})


def test_should_round_trip_engine_snapshot_and_reject_scenario_mismatch() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_connection("session-1")
    engine.mark_connected()
    payload = engine.snapshot()

    restored = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    restored.restore(payload)
    assert restored.snapshot() == payload

    mismatch = RealtimeSessionEngine(
        scenario_type="sales",
        hooks=NoopScenarioTurnHooks(scenario_type="sales"),
    )
    with pytest.raises(ValueError, match="engine_snapshot_scenario_mismatch"):
        mismatch.restore(payload)


def test_should_not_allow_callers_to_mutate_engine_state_outside_boundary() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_connection("session-1")

    visible_state = engine.state
    visible_state.connection.epoch = 99

    assert engine.state.connection.epoch == 1


def test_should_fail_visibly_when_hook_fails() -> None:
    class FailingHooks:
        scenario_type = "presentation"

        def on_transition(self, transition: RealtimeTransition) -> None:
            raise RuntimeError(transition.event_name)

    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=FailingHooks())

    with pytest.raises(RuntimeError, match="connection.connecting"):
        engine.begin_connection("session-1")
    assert engine.state.connection.phase is ConnectionPhase.CONNECTING


def test_should_reject_mismatched_scenario_hook() -> None:
    with pytest.raises(ValueError, match="scenario_hook_mismatch"):
        RealtimeSessionEngine(
            scenario_type="presentation",
            hooks=NoopScenarioTurnHooks(scenario_type="sales"),
        )
