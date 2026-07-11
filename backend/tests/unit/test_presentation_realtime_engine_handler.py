from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from common.websocket.session_state_service import SessionStateSnapshot
from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
    LegacyPresentationStepFunRealtimeHandler,
)
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeSharedHandler
from sales_bot.websocket.stepfun_realtime_policy import StepFunRealtimePolicyMixin
from sales_bot.websocket.stepfun_realtime_upstream import StepFunRealtimeUpstreamMixin
from training_runtime import PresentationScenarioPlugin, TrainingRuntimeDescriptor
from training_runtime.realtime import (
    GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
    GroundingPhase,
    RealtimeSessionEngine,
    TurnPhase,
)


class FakeRuntimeAdapter:
    def __init__(self, *, runtime_engine: RealtimeSessionEngine) -> None:
        self.runtime_engine = runtime_engine
        self.scenario = "presentation"
        self.session_status = "preparing"
        self.ai_state = "idle"
        self.websocket = None
        self.session_id = None
        self.user_id = None
        self.handle_connection = AsyncMock()
        self.send_message = AsyncMock(return_value="sent")
        self.close = AsyncMock()
        self.sync_lifecycle_transition = AsyncMock()

    def get_runtime_diagnostics(self) -> dict[str, Any]:
        return {
            "session_status": self.session_status,
            "ai_state": self.ai_state,
            "current_request_id": 3,
            "reconnect_state": {"connection_epoch": 2},
            "token": "must-not-leak",
            "raw_prompt": "must-not-leak",
            "transcript": "must-not-leak",
        }


def test_facade_composes_one_adapter_without_sales_handler_inheritance() -> None:
    from presentation_coach.websocket.presentation_realtime_engine_handler import (
        PresentationRealtimeEngineHandler,
    )

    constructed: list[FakeRuntimeAdapter] = []

    def factory(*, runtime_engine: RealtimeSessionEngine) -> FakeRuntimeAdapter:
        adapter = FakeRuntimeAdapter(runtime_engine=runtime_engine)
        constructed.append(adapter)
        return adapter

    handler = PresentationRealtimeEngineHandler(
        runtime_engine_factory=RealtimeSessionEngine,
        runtime_adapter_factory=factory,
    )

    assert not isinstance(handler, StepFunRealtimeSharedHandler)
    assert len(constructed) == 1
    assert handler.runtime_adapter is constructed[0]
    assert handler.runtime_adapter.runtime_engine is handler.engine
    assert handler.engine.state.scenario_type == "presentation"
    assert "__getattr__" not in type(handler).__dict__


@pytest.mark.asyncio
async def test_facade_explicitly_delegates_session_manager_surface() -> None:
    from presentation_coach.websocket.presentation_realtime_engine_handler import (
        PresentationRealtimeEngineHandler,
    )

    adapter = FakeRuntimeAdapter(
        runtime_engine=RealtimeSessionEngine(
            scenario_type="presentation",
            hooks=SimpleNamespace(
                scenario_type="presentation",
                on_transition=lambda _transition: None,
            ),
        )
    )
    handler = PresentationRealtimeEngineHandler(
        runtime_engine_factory=RealtimeSessionEngine,
        runtime_adapter_factory=lambda *, runtime_engine: adapter
    )
    websocket = Mock()
    transition = SimpleNamespace(to_status="in_progress", ai_state="listening")

    await handler.handle_connection(websocket, "session-1", "token", trace_id="trace")
    assert await handler.send_message({"type": "heartbeat"}) == "sent"
    await handler.close(code=1001, reason="going_away")
    await handler.sync_lifecycle_transition(transition)

    adapter.handle_connection.assert_awaited_once_with(
        websocket,
        "session-1",
        "token",
        trace_id="trace",
    )
    adapter.send_message.assert_awaited_once_with({"type": "heartbeat"})
    adapter.close.assert_awaited_once_with(code=1001, reason="going_away")
    adapter.sync_lifecycle_transition.assert_awaited_once_with(transition)
    assert handler.scenario == "presentation"
    assert handler.session_status == "preparing"
    assert handler.ai_state == "idle"


def test_facade_runtime_diagnostics_are_versioned_and_sanitized() -> None:
    from presentation_coach.websocket.presentation_realtime_engine_handler import (
        PresentationRealtimeEngineHandler,
    )

    handler = PresentationRealtimeEngineHandler(
        runtime_engine_factory=RealtimeSessionEngine,
        runtime_adapter_factory=FakeRuntimeAdapter
    )

    diagnostics = handler.get_runtime_diagnostics()

    assert diagnostics["selected_runtime"] == "presentation_realtime_engine"
    assert diagnostics["rollout_enabled"] is True
    assert diagnostics["rollback_runtime"] == "legacy_presentation_stepfun"
    assert diagnostics["engine_state_version"] == 1
    assert diagnostics["engine_state"]["scenario_type"] == "presentation"
    assert diagnostics["adapter"] == {
        "session_status": "preparing",
        "ai_state": "idle",
        "current_request_id": 3,
        "reconnect_state": {"connection_epoch": 2},
    }
    assert "must-not-leak" not in repr(diagnostics)


@pytest.mark.asyncio
async def test_pre_gate_snapshot_derives_engine_state_and_matches_legacy_epoch() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter._cancel_pending_response_after_commit = AsyncMock()
    adapter._send_reconnection_success = AsyncMock()
    pre_gate_snapshot = SessionStateSnapshot(
        session_id="session-pre-gate",
        scenario="presentation",
        turn_count=4,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "current_request_id": 7,
            "reconnect_state": {
                "connection_epoch": 4,
                "request_epoch": 7,
                "last_disconnect_reason": "client_disconnect",
            },
        },
        user_id="user-1",
    )

    await adapter._restore_session_state(pre_gate_snapshot)

    assert adapter._connection_epoch == 5
    assert engine.state.connection.epoch == 5
    assert engine.state.connection.session_id == "session-pre-gate"
    assert engine.state.turn.request_id == 7
    assert engine.state.turn.phase is TurnPhase.COMPLETED


@pytest.mark.asyncio
async def test_engine_snapshot_is_additive_and_round_trips_grounding_and_evidence() -> None:
    source_engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    source_engine.begin_connection("session-round-trip")
    source_engine.mark_connected()
    source_engine.begin_grounding(
        decision_id="presentation:1",
        policy_hash="sha256:frozen-policy",
    )
    source_engine.resolve_grounding(
        outcome="ready",
        mode="grounded",
        diagnostics={
            "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
            "status": "ready",
            "reason_code": "presentation_feedback_ready",
            "source": "presentation",
            "mode": "grounded",
        },
    )
    source_engine.record_evidence(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload=b"normalized transcript",
    )
    source_adapter = LegacyPresentationStepFunRealtimeHandler(
        runtime_engine=source_engine
    )
    source_adapter.session_id = "session-round-trip"
    source_adapter.user_id = "user-1"
    source_adapter._connection_epoch = 1
    source_adapter.current_request_id = 1

    snapshot = source_adapter._create_state_snapshot()

    assert snapshot.runtime_state is not None
    assert set(snapshot.runtime_state) >= {"reconnect_state", "realtime_engine"}
    assert snapshot.runtime_state["reconnect_state"]["connection_epoch"] == 1

    restored_engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    restored_adapter = LegacyPresentationStepFunRealtimeHandler(
        runtime_engine=restored_engine
    )
    restored_adapter._cancel_pending_response_after_commit = AsyncMock()
    restored_adapter._send_reconnection_success = AsyncMock()

    await restored_adapter._restore_session_state(snapshot)

    assert restored_engine.state.connection.epoch == restored_adapter._connection_epoch == 2
    assert restored_engine.state.grounding.phase is GroundingPhase.READY
    assert set(restored_engine.state.evidence.records) == {"transcript:1:user"}


@pytest.mark.asyncio
async def test_adapter_maps_grounding_to_closed_diagnostics_vocabulary() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter.current_request_id = 2
    adapter._instruction_contract_hash = "sha256:frozen-policy"
    adapter._pending_blocked_response_text = "safe client copy"
    adapter._latest_knowledge_answer_diagnostics = {
        "status": "arbitrary upstream free text",
        "error": "provider token must not cross boundary",
    }

    with patch.object(
        StepFunRealtimeUpstreamMixin,
        "_prepare_grounding_context",
        new=AsyncMock(),
    ):
        await adapter._prepare_grounding_context("learner query")

    assert engine.state.grounding.phase is GroundingPhase.BLOCKED
    assert engine.state.grounding.diagnostics == {
        "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
        "status": "blocked",
        "reason_code": "kb_lock_blocked",
        "source": "presentation",
        "mode": "blocked",
        "degraded": False,
        "blocked": True,
    }
    assert "provider token" not in repr(engine.snapshot())


@pytest.mark.asyncio
async def test_adapter_records_binary_audio_as_length_and_digest_metadata_only() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter.turn_count = 1
    frame = bytes([adapter.BINARY_AUDIO_CHUNK]) + b"sensitive-audio"

    with patch.object(
        StepFunRealtimePolicyMixin,
        "_handle_binary_frame",
        new=AsyncMock(),
    ) as base_binary:
        await adapter._handle_binary_frame(frame)

    base_binary.assert_awaited_once_with(frame)
    [evidence_key] = engine.state.evidence.records
    assert evidence_key.startswith(f"audio:1:{len(frame) - 1}:")
    assert engine.state.evidence.records[evidence_key].payload_digest.startswith("sha256:")
    assert "sensitive-audio" not in repr(engine.snapshot())


@pytest.mark.asyncio
async def test_response_done_completes_captured_request_not_tool_followup() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    engine.begin_turn(request_id=1, stream_id="stream-1")
    engine.mark_response_started(response_id="response-1")
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter.current_request_id = 1
    adapter._active_response = SimpleNamespace(request_id=1, response_id="response-1")

    async def create_followup(_self: object, _event: dict[str, Any]) -> None:
        adapter.current_request_id = 2
        adapter._active_response = SimpleNamespace(
            request_id=2,
            response_id=None,
            stream_id="stream-2",
        )

    with patch.object(
        StepFunRealtimeUpstreamMixin,
        "_handle_upstream_response_done",
        new=create_followup,
    ):
        await adapter._handle_upstream_response_done(
            {"type": "response.done", "response": {"id": "response-1"}}
        )

    assert engine.state.turn.request_id == 1
    assert engine.state.turn.phase is TurnPhase.COMPLETED


@pytest.mark.asyncio
async def test_normalized_transcript_records_deduped_engine_evidence() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter.session_id = "session-transcript"
    adapter.user_id = "user-1"
    adapter._resolve_user_turn_number_for_transcript = Mock(return_value=1)
    adapter._send_transcript = AsyncMock()
    adapter._persist_message = AsyncMock()
    adapter._load_page_requirements = AsyncMock(
        return_value={"required_points": [], "forbidden_words": []}
    )
    adapter._initialize_page_feedback = AsyncMock()
    adapter._evaluate_presentation_feedback = AsyncMock(return_value=False)
    adapter._prepare_grounding_context = AsyncMock()
    adapter._create_response_from_pending_commit = AsyncMock()

    await adapter._handle_upstream_transcription_completed(
        {"transcript": "normalized transcript"}
    )
    await adapter._handle_upstream_transcription_completed(
        {"transcript": "normalized transcript"}
    )

    assert set(engine.state.evidence.records) == {"transcript:1:user"}
    assert engine.state.evidence.records["transcript:1:user"].turn_number == 1


class GoldenConversationAdapter(FakeRuntimeAdapter):
    def __init__(self, *, runtime_engine: RealtimeSessionEngine | None) -> None:
        if runtime_engine is None:
            self.runtime_engine = None
            self.scenario = "presentation"
            self.session_status = "preparing"
            self.ai_state = "idle"
            self.websocket = None
            self.session_id = None
            self.user_id = None
            self.handle_connection = AsyncMock()
            self.send_message = AsyncMock(return_value="sent")
            self.close = AsyncMock(return_value=None)
            self.sync_lifecycle_transition = AsyncMock()
        else:
            super().__init__(runtime_engine=runtime_engine)
            self.close = AsyncMock(return_value=None)
        self.external_events: list[dict[str, object]] = []
        self.persistence_keys: set[str] = set()
        self.write_count = 0

    def emit(self, event_type: str, **stable: object) -> None:
        self.external_events.append({"type": event_type, **stable})

    def persist_once(self, key: str) -> None:
        if key not in self.persistence_keys:
            self.persistence_keys.add(key)
            self.write_count += 1


async def _drive_golden_conversation(adapter: GoldenConversationAdapter) -> None:
    engine = adapter.runtime_engine
    adapter.emit("connected", session_id="session-golden")
    adapter.emit("status", session_status="in_progress", ai_state="listening")
    if engine is not None:
        engine.begin_connection("session-golden")
        engine.mark_connected()
        engine.begin_turn(request_id=1, stream_id="stream-stable")
        engine.begin_grounding(
            decision_id="presentation:golden:1",
            policy_hash="sha256:frozen-policy",
        )
        engine.resolve_grounding(
            outcome="ready",
            mode="grounded",
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                "status": "ready",
                "reason_code": "presentation_feedback_ready",
                "source": "presentation",
                "mode": "grounded",
            },
        )
        engine.record_evidence(
            evidence_key="audio:1:4:stable",
            evidence_type="audio",
            turn_number=1,
            payload=b"audio",
        )
    adapter.emit("asr_transcript", text="讲解第一页", is_final=True)
    adapter.persist_once("transcript:1:user")
    adapter.persist_once("transcript:1:user")
    if engine is not None:
        engine.record_evidence(
            evidence_key="transcript:1:user",
            evidence_type="transcript",
            turn_number=1,
            payload="讲解第一页".encode(),
        )
        engine.record_evidence(
            evidence_key="transcript:1:user",
            evidence_type="transcript",
            turn_number=1,
            payload="讲解第一页".encode(),
        )
        engine.mark_response_started(response_id="response-stable")
        engine.mark_streaming()
        engine.complete_turn(request_id=1)
    adapter.emit("tts_audio", request_id=1, is_final=True)
    if engine is not None:
        engine.begin_close(reason="network_reset")
        engine.mark_disconnected(reason="network_reset")
        engine.begin_connection("session-golden")
        engine.mark_connected()
    adapter.emit("connected", session_id="session-golden")
    adapter.emit("status", session_status="in_progress", ai_state="listening")


@pytest.mark.asyncio
async def test_golden_differential_preserves_external_single_writer_contract() -> None:
    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures/realtime/golden_conversation_contract_v1.json"
    )
    inventory = json.loads(fixture_path.read_text(encoding="utf-8"))
    contract_ids = {item["id"] for item in inventory["contracts"]}
    assert "conversation.connect_start_text_audio_response_done" in contract_ids
    assert "rollout.single_writer_rollback" in contract_ids

    descriptor = TrainingRuntimeDescriptor(
        session_id="session-golden",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )
    selection = PresentationScenarioPlugin(
        rollout_resolver=lambda: True
    ).select_runtime_handler(descriptor)
    assert selection.handler_factory_name == "PresentationRealtimeEngineHandler"

    legacy = GoldenConversationAdapter(runtime_engine=None)
    from presentation_coach.websocket.presentation_realtime_engine_handler import (
        PresentationRealtimeEngineHandler,
    )

    facade = PresentationRealtimeEngineHandler(
        runtime_engine_factory=RealtimeSessionEngine,
        runtime_adapter_factory=GoldenConversationAdapter
    )
    engine_adapter = facade.runtime_adapter
    assert isinstance(engine_adapter, GoldenConversationAdapter)

    await _drive_golden_conversation(legacy)
    await _drive_golden_conversation(engine_adapter)

    assert engine_adapter.external_events == legacy.external_events
    assert engine_adapter.persistence_keys == legacy.persistence_keys
    assert engine_adapter.write_count == legacy.write_count == 1
    assert await facade.close() == await legacy.close()
    assert facade.engine.state.connection.epoch == 2
    assert facade.engine.state.turn.phase is TurnPhase.COMPLETED
    assert facade.engine.state.grounding.phase is GroundingPhase.READY
    assert set(facade.engine.state.evidence.records) == {
        "audio:1:4:stable",
        "transcript:1:user",
    }
