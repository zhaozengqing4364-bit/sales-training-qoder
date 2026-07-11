from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from starlette.websockets import WebSocketState

from common.websocket.session_state_service import SessionStateSnapshot
from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
    LegacyPresentationStepFunRealtimeHandler,
)
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeSharedHandler
from sales_bot.websocket.stepfun_realtime_upstream import StepFunRealtimeUpstreamMixin
from sales_bot.websocket.stepfun_runtime_types import RealtimeResponseState
from training_runtime import PresentationScenarioPlugin, TrainingRuntimeDescriptor
from training_runtime.realtime import (
    GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
    GroundingPhase,
    RealtimeSessionEngine,
    TurnPhase,
)
from training_runtime.stepfun_transport import (
    StepFunBackpressureResult,
    StepFunBackpressureStatus,
    StepFunSendResult,
    StepFunSendStatus,
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
            "live_session_summary": {
                "focus_type": "objection_handling_gap",
                "claim_truth": {"status": "unsupported_claim"},
            },
            "claim_truth": {"status": "unsupported_claim"},
            "coach_health": {
                "status": "healthy",
                "reason": None,
                "message": "实时辅导正常。",
            },
            "knowledge_answer_diagnostics": {
                "status": "ready",
                "source": "presentation",
            },
            "reconnect_state": {"connection_epoch": 2},
            "runtime_events": [{"event": "response.done"}],
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
        runtime_adapter_factory=lambda *, runtime_engine: adapter,
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
        runtime_adapter_factory=FakeRuntimeAdapter,
    )

    diagnostics = handler.get_runtime_diagnostics()

    assert diagnostics["selected_runtime"] == "presentation_realtime_engine"
    assert diagnostics["rollout_enabled"] is True
    assert diagnostics["rollback_runtime"] == "legacy_presentation_stepfun"
    assert diagnostics["engine_state_version"] == 1
    assert diagnostics["engine_state"]["scenario_type"] == "presentation"
    assert diagnostics["live_session_summary"] == {
        "focus_type": "objection_handling_gap",
        "claim_truth": {"status": "unsupported_claim"},
    }
    assert diagnostics["claim_truth"] == {"status": "unsupported_claim"}
    assert diagnostics["coach_health"] == {
        "status": "healthy",
        "reason": None,
        "message": "实时辅导正常。",
    }
    assert diagnostics["knowledge_answer_diagnostics"] == {
        "status": "ready",
        "source": "presentation",
    }
    assert diagnostics["runtime_events"] == [{"event": "response.done"}]
    assert diagnostics["adapter"] == {
        "session_status": "preparing",
        "ai_state": "idle",
        "current_request_id": 3,
        "live_session_summary": {
            "focus_type": "objection_handling_gap",
            "claim_truth": {"status": "unsupported_claim"},
        },
        "claim_truth": {"status": "unsupported_claim"},
        "coach_health": {
            "status": "healthy",
            "reason": None,
            "message": "实时辅导正常。",
        },
        "knowledge_answer_diagnostics": {
            "status": "ready",
            "source": "presentation",
        },
        "reconnect_state": {"connection_epoch": 2},
        "runtime_events": [{"event": "response.done"}],
    }
    assert "must-not-leak" not in repr(diagnostics)


@pytest.mark.asyncio
async def test_pre_gate_snapshot_derives_engine_state_and_matches_legacy_epoch() -> (
    None
):
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
async def test_engine_snapshot_is_additive_and_round_trips_grounding_and_evidence() -> (
    None
):
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

    assert (
        restored_engine.state.connection.epoch
        == restored_adapter._connection_epoch
        == 2
    )
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


def _configure_accepted_audio_input(
    adapter: LegacyPresentationStepFunRealtimeHandler,
) -> None:
    adapter.session_status = "in_progress"
    adapter._ensure_input_allowed = AsyncMock(return_value=True)
    adapter._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    adapter._should_drop_upstream_for_backpressure = Mock(return_value=False)
    adapter._send_upstream = AsyncMock(return_value=True)
    adapter._schedule_response_after_commit = AsyncMock()


@pytest.mark.asyncio
async def test_adapter_aggregates_accepted_audio_once_at_real_commit_boundary() -> None:
    transitions: list[str] = []
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda transition: transitions.append(transition.event_name),
        ),
    )
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter.turn_count = 0
    _configure_accepted_audio_input(adapter)
    payloads = [index.to_bytes(4, byteorder="little") for index in range(1000)]
    snapshot_size_after_first_frame = 0

    for index, payload in enumerate(payloads):
        accepted = await adapter._handle_binary_frame(
            bytes([adapter.BINARY_AUDIO_CHUNK]) + payload
        )
        assert accepted is True
        if index == 0:
            snapshot_size_after_first_frame = len(json.dumps(engine.snapshot()))

    assert engine.state.evidence.records == {}
    assert transitions == []
    assert len(json.dumps(engine.snapshot())) == snapshot_size_after_first_frame

    await adapter._commit_and_respond()

    evidence_key = "audio:1:chunks:1000:bytes:4000"
    assert set(engine.state.evidence.records) == {evidence_key}
    assert engine.state.evidence.records[evidence_key].payload_digest == (
        f"sha256:{sha256(b''.join(payloads)).hexdigest()}"
    )
    assert transitions == ["evidence.recorded"]
    assert "sensitive-audio" not in repr(engine.snapshot())

    await adapter._commit_and_respond()

    assert set(engine.state.evidence.records) == {evidence_key}
    assert transitions == ["evidence.recorded"]


@pytest.mark.asyncio
async def test_adapter_scopes_committed_identical_audio_to_frozen_user_turn() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    _configure_accepted_audio_input(adapter)
    frame = bytes([adapter.BINARY_AUDIO_CHUNK]) + b"same-audio"

    adapter.turn_count = 0
    assert await adapter._handle_binary_frame(frame) is True
    await adapter._commit_and_respond()
    adapter.turn_count = 1
    assert await adapter._handle_binary_frame(frame) is True
    await adapter._commit_and_respond()

    assert set(engine.state.evidence.records) == {
        "audio:1:chunks:1:bytes:10",
        "audio:2:chunks:1:bytes:10",
    }
    assert {
        record.turn_number for record in engine.state.evidence.records.values()
    } == {1, 2}
    assert (
        len(
            {record.payload_digest for record in engine.state.evidence.records.values()}
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "frame"),
    [
        ("empty", b""),
        (
            "empty_chunk",
            bytes([LegacyPresentationStepFunRealtimeHandler.BINARY_AUDIO_CHUNK]),
        ),
        ("invalid", b"\x7fnot-audio"),
        (
            "interrupt",
            bytes([LegacyPresentationStepFunRealtimeHandler.BINARY_AUDIO_INTERRUPT]),
        ),
        ("paused", b"\x01audio"),
        ("upstream_not_ready", b"\x01audio"),
        ("upstream_rejected", b"\x01audio"),
        ("backpressure", b"\x01audio"),
    ],
)
async def test_adapter_records_no_evidence_for_rejected_audio(
    case: str,
    frame: bytes,
) -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda _transition: None,
        ),
    )
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter.session_status = "in_progress"
    adapter._handle_interrupt = AsyncMock()
    adapter._ensure_input_allowed = AsyncMock(return_value=case != "paused")
    adapter._ensure_upstream_ready_for_input = AsyncMock(
        return_value=case != "upstream_not_ready"
    )
    adapter._should_drop_upstream_for_backpressure = Mock(
        return_value=case == "backpressure"
    )
    adapter._send_upstream = AsyncMock(return_value=case != "upstream_rejected")
    adapter._schedule_response_after_commit = AsyncMock()

    assert await adapter._handle_binary_frame(frame) is False
    await adapter._commit_and_respond()

    assert engine.state.evidence.records == {}


@pytest.mark.asyncio
async def test_response_done_completes_engine_turn_before_real_tool_followup() -> None:
    transitions: list[str] = []
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=SimpleNamespace(
            scenario_type="presentation",
            on_transition=lambda transition: transitions.append(transition.event_name),
        ),
    )
    engine.begin_turn(request_id=1, stream_id="stream-1")
    engine.mark_response_started(response_id="response-1")
    adapter = LegacyPresentationStepFunRealtimeHandler(runtime_engine=engine)
    adapter.current_request_id = 1
    adapter._active_response = RealtimeResponseState(
        request_id=1,
        stream_id="stream-1",
        response_id="response-1",
    )
    adapter._pending_tool_followup_response = True
    adapter._send_status = AsyncMock()
    adapter._send_upstream = AsyncMock()
    adapter._record_roleplay_instruction_hash_metric = AsyncMock()

    await adapter._handle_upstream_response_done(
        {"type": "response.done", "response": {"id": "response-1"}}
    )

    assert adapter.current_request_id == 2
    assert adapter._active_response is not None
    assert adapter._active_response.request_id == 2
    assert engine.state.turn.request_id == 2
    assert engine.state.turn.phase is TurnPhase.RECEIVING
    assert transitions[-2:] == ["turn.completed", "turn.receiving"]


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


class GoldenWebSocket:
    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.events: list[dict[str, Any]] = []
        self.closed: tuple[int, str] | None = None

    async def accept(self) -> None:
        self.client_state = WebSocketState.CONNECTED

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.events.append(deepcopy(payload))

    async def close(self, *, code: int, reason: str) -> None:
        self.closed = (code, reason)
        self.client_state = WebSocketState.DISCONNECTED


class GoldenStepFunTransport:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events
        self.upstream = SimpleNamespace()

    async def connect(self, **_kwargs: Any) -> object:
        return self.upstream

    async def send_json(
        self,
        _upstream: object,
        payload: dict[str, Any],
    ) -> StepFunSendResult:
        self.events.append(deepcopy(payload))
        return StepFunSendResult(status=StepFunSendStatus.SENT)

    async def close(self, _upstream: object) -> None:
        return None

    def decide_backpressure(
        self,
        _payload: dict[str, Any],
        **_kwargs: Any,
    ) -> StepFunBackpressureResult:
        return StepFunBackpressureResult(status=StepFunBackpressureStatus.ALLOW)


def _normalize_golden_value(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {
                "timestamp",
                "trace_id",
                "last_activity",
                "realtime_engine",
            }:
                continue
            if key == "stream_id" and item:
                normalized[key] = "<stream-id>"
            else:
                normalized[key] = _normalize_golden_value(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_golden_value(item) for item in value]
    return value


def _configure_golden_handler(
    handler: LegacyPresentationStepFunRealtimeHandler,
    *,
    websocket: GoldenWebSocket,
    upstream_events: list[dict[str, Any]],
    mutate_transcript_event: bool,
) -> None:
    handler.websocket = websocket
    handler.session_id = "session-golden"
    handler.user_id = "user-golden"
    handler.running = True
    handler._connection_epoch = 1
    handler._instruction_contract_hash = "sha256:golden-policy"
    handler._stepfun_transport = GoldenStepFunTransport(upstream_events)
    handler._ensure_upstream_keepalive_task = Mock()
    handler._maybe_start_kb_lock_warmup = AsyncMock()
    handler._record_roleplay_instruction_hash_metric = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value=None)
    handler._run_realtime_feedback = AsyncMock(return_value=None)
    handler._update_roleplay_disclosure_state = AsyncMock()
    handler._load_page_requirements = AsyncMock(
        return_value={
            "total_pages": 2,
            "page_content": "第一页：产品价值",
            "required_points": ["说明客户收益"],
            "forbidden_words": [],
        }
    )
    handler._initialize_page_feedback = AsyncMock()
    handler._evaluate_presentation_feedback = AsyncMock(return_value=False)
    handler._apply_roleplay_output_guard = AsyncMock(
        side_effect=lambda text, **_kwargs: text
    )

    async def apply_lifecycle_action(action: str) -> object:
        assert action == "start"
        handler.session_status = "in_progress"
        handler.ai_state = "listening"
        return SimpleNamespace(to_status="in_progress", ai_state="listening")

    handler._apply_lifecycle_action = apply_lifecycle_action

    if mutate_transcript_event:
        original_send_transcript = handler._presentation_event_emitter.send_transcript

        async def send_mutated_transcript(
            *,
            text: str,
            is_final: bool,
            websocket: Any = None,
        ) -> bool:
            return await original_send_transcript(
                text=f"{text}（变更）",
                is_final=is_final,
                websocket=websocket,
            )

        handler._presentation_event_emitter.send_transcript = send_mutated_transcript


async def _drive_real_golden_conversation(
    *,
    initial_handler: LegacyPresentationStepFunRealtimeHandler,
    initial_surface: Any,
    reconnect_factory: Any,
    mutate_transcript_event: bool = False,
) -> dict[str, Any]:
    downstream_events: list[dict[str, Any]] = []
    upstream_events: list[dict[str, Any]] = []
    persistence_writes: list[dict[str, Any]] = []

    async def save_message(**kwargs: Any) -> bool:
        persistence_writes.append(
            {
                "session_id": kwargs["session_id"],
                "turn_number": kwargs["turn_number"],
                "role": kwargs["role"],
                "content": kwargs["content"],
                "analysis_payload": deepcopy(kwargs["analysis_payload"]),
            }
        )
        return True

    first_websocket = GoldenWebSocket()
    _configure_golden_handler(
        initial_handler,
        websocket=first_websocket,
        upstream_events=upstream_events,
        mutate_transcript_event=mutate_transcript_event,
    )

    with (
        patch(
            "presentation_coach.websocket.presentation_stepfun_realtime_handler.save_stepfun_message",
            new=save_message,
        ),
        patch.object(
            StepFunRealtimeUpstreamMixin,
            "_prepare_grounding_context",
            new=AsyncMock(),
        ),
    ):
        await initial_handler.manager.connect(
            first_websocket,
            initial_handler.scenario,
            "session-golden",
        )
        await initial_handler._connect_upstream()
        await initial_handler._handle_client_text(
            json.dumps({"type": "control", "data": {"action": "start"}})
        )
        await initial_handler._handle_client_text(
            json.dumps({"type": "text", "data": {"text": "讲解第一页"}})
        )
        await initial_handler._handle_upstream_response_created(
            {"type": "response.created", "response": {"id": "response-1"}}
        )
        assert initial_handler._active_response is not None
        initial_handler._active_response.text_parts.append("第一轮回应")
        await initial_handler._handle_upstream_response_done(
            {"type": "response.done", "response": {"id": "response-1"}}
        )

        frame = bytes([initial_handler.BINARY_AUDIO_CHUNK]) + b"golden-audio"
        await initial_handler._handle_binary_frame(frame)
        await initial_handler._handle_binary_frame(frame)
        await initial_handler._commit_and_respond()
        transcription_event = {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "补充客户收益",
        }
        await initial_handler._handle_upstream_transcription_completed(
            transcription_event
        )
        await initial_handler._handle_upstream_transcription_completed(
            transcription_event
        )
        await initial_handler._handle_upstream_response_created(
            {"type": "response.created", "response": {"id": "response-2"}}
        )
        assert initial_handler._active_response is not None
        initial_handler._active_response.text_parts.append("第二轮回应")
        await initial_handler._handle_upstream_response_done(
            {"type": "response.done", "response": {"id": "response-2"}}
        )

        snapshot = initial_handler._create_state_snapshot()
        await initial_handler.manager.disconnect(
            initial_handler.scenario,
            "session-golden",
        )

        reconnect_handler, reconnect_surface = reconnect_factory()
        reconnect_websocket = GoldenWebSocket()
        _configure_golden_handler(
            reconnect_handler,
            websocket=reconnect_websocket,
            upstream_events=upstream_events,
            mutate_transcript_event=False,
        )
        await reconnect_handler.manager.connect(
            reconnect_websocket,
            reconnect_handler.scenario,
            "session-golden",
        )
        await reconnect_handler._restore_session_state(snapshot)
        await reconnect_handler._connect_upstream()
        await reconnect_handler._send_status(reconnect_handler.ai_state)
        reconnect_snapshot = reconnect_handler._create_state_snapshot()
        runtime_engine = reconnect_handler._runtime_engine
        engine_snapshot = (
            runtime_engine.snapshot() if runtime_engine is not None else None
        )
        await reconnect_surface.close(code=1001, reason="golden_complete")
        await reconnect_handler.manager.disconnect(
            reconnect_handler.scenario,
            "session-golden",
        )

    downstream_events.extend(first_websocket.events)
    downstream_events.extend(reconnect_websocket.events)
    return {
        "downstream_events": _normalize_golden_value(downstream_events),
        "upstream_events": _normalize_golden_value(upstream_events),
        "persistence_writes": _normalize_golden_value(persistence_writes),
        "initial_snapshot": snapshot,
        "reconnect_snapshot": reconnect_snapshot,
        "engine_snapshot": engine_snapshot,
        "expected_reconnect_epoch": (
            int(
                (snapshot.runtime_state or {})
                .get("reconnect_state", {})
                .get("connection_epoch", 0)
            )
            + 1
        ),
        "closed": reconnect_websocket.closed,
        "initial_surface": type(initial_surface).__name__,
    }


def _legacy_snapshot_projection(snapshot: SessionStateSnapshot) -> dict[str, Any]:
    return _normalize_golden_value(snapshot.to_dict())


def _assert_golden_differential(
    legacy_result: dict[str, Any],
    engine_result: dict[str, Any],
) -> None:
    assert _legacy_snapshot_projection(engine_result["initial_snapshot"]) == (
        _legacy_snapshot_projection(legacy_result["initial_snapshot"])
    )
    assert _legacy_snapshot_projection(engine_result["reconnect_snapshot"]) == (
        _legacy_snapshot_projection(legacy_result["reconnect_snapshot"])
    )
    assert engine_result["downstream_events"] == legacy_result["downstream_events"]
    assert engine_result["upstream_events"] == legacy_result["upstream_events"]
    assert engine_result["persistence_writes"] == legacy_result["persistence_writes"]
    assert engine_result["closed"] == legacy_result["closed"]


def _assert_golden_engine_terminal_state(result: dict[str, Any]) -> None:
    engine_snapshot = result["engine_snapshot"]
    assert isinstance(engine_snapshot, dict)
    assert engine_snapshot["connection"]["phase"] == "connected"
    assert engine_snapshot["connection"]["epoch"] == result["expected_reconnect_epoch"]
    assert engine_snapshot["connection"]["epoch"] == 2
    assert engine_snapshot["turn"]["phase"] == "completed"
    assert engine_snapshot["grounding"]["phase"] == "ready"
    assert engine_snapshot["grounding"]["frozen_policy_hash"] == (
        "sha256:golden-policy"
    )

    records = engine_snapshot["evidence"]["records"]
    audio_key = "audio:2:chunks:2:bytes:24"
    audio_keys = [key for key in records if key == audio_key]
    transcript_keys = [key for key in records if key == "transcript:2:user"]
    assert len(audio_keys) == 1
    assert len(transcript_keys) == 1
    assert len(records) == 2
    assert records[audio_key]["turn_number"] == 2
    assert records[audio_key]["payload_digest"] == (
        f"sha256:{sha256(b'golden-audiogolden-audio').hexdigest()}"
    )
    assert records[transcript_keys[0]]["turn_number"] == 2


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

    from presentation_coach.websocket.presentation_realtime_engine_handler import (
        PresentationRealtimeEngineHandler,
    )

    legacy = LegacyPresentationStepFunRealtimeHandler()
    facade = PresentationRealtimeEngineHandler(
        runtime_engine_factory=RealtimeSessionEngine,
    )
    engine_adapter = facade.runtime_adapter
    assert isinstance(legacy, LegacyPresentationStepFunRealtimeHandler)
    assert isinstance(engine_adapter, LegacyPresentationStepFunRealtimeHandler)

    def legacy_reconnect_factory() -> tuple[Any, Any]:
        adapter = LegacyPresentationStepFunRealtimeHandler()
        return adapter, adapter

    def engine_reconnect_factory() -> tuple[Any, Any]:
        reconnect_facade = PresentationRealtimeEngineHandler(
            runtime_engine_factory=RealtimeSessionEngine,
        )
        return reconnect_facade.runtime_adapter, reconnect_facade

    legacy_result = await _drive_real_golden_conversation(
        initial_handler=legacy,
        initial_surface=legacy,
        reconnect_factory=legacy_reconnect_factory,
    )
    engine_result = await _drive_real_golden_conversation(
        initial_handler=engine_adapter,
        initial_surface=facade,
        reconnect_factory=engine_reconnect_factory,
    )

    _assert_golden_differential(legacy_result, engine_result)
    _assert_golden_engine_terminal_state(engine_result)
    downstream_types = {event["type"] for event in engine_result["downstream_events"]}
    upstream_types = {event["type"] for event in engine_result["upstream_events"]}
    assert downstream_types >= {
        "connected",
        "status",
        "slide_update",
        "asr_transcript",
        "tts_audio",
        "reconnected",
    }
    assert upstream_types >= {
        "session.update",
        "conversation.item.create",
        "input_audio_buffer.append",
        "response.create",
    }
    persistence_keys = {
        (write["turn_number"], write["role"], write["content"])
        for write in engine_result["persistence_writes"]
    }
    assert len(persistence_keys) == len(engine_result["persistence_writes"])
    assert len(persistence_keys) == 4

    snapshot_mutation = deepcopy(engine_result)
    snapshot_mutation["initial_snapshot"].turn_count = 999
    with pytest.raises(AssertionError):
        _assert_golden_differential(legacy_result, snapshot_mutation)

    epoch_mutation = deepcopy(engine_result)
    epoch_mutation["engine_snapshot"]["connection"]["epoch"] = 1
    with pytest.raises(AssertionError):
        _assert_golden_engine_terminal_state(epoch_mutation)

    grounding_mutation = deepcopy(engine_result)
    grounding_mutation["engine_snapshot"]["grounding"]["phase"] = "empty"
    with pytest.raises(AssertionError):
        _assert_golden_engine_terminal_state(grounding_mutation)

    evidence_mutation = deepcopy(engine_result)
    evidence_records = evidence_mutation["engine_snapshot"]["evidence"]["records"]
    audio_key = next(key for key in evidence_records if key.startswith("audio:2:"))
    evidence_records.pop(audio_key)
    with pytest.raises(AssertionError):
        _assert_golden_engine_terminal_state(evidence_mutation)


@pytest.mark.asyncio
async def test_golden_differential_detects_real_handler_event_mutation() -> None:
    from presentation_coach.websocket.presentation_realtime_engine_handler import (
        PresentationRealtimeEngineHandler,
    )

    def legacy_reconnect_factory() -> tuple[Any, Any]:
        adapter = LegacyPresentationStepFunRealtimeHandler()
        return adapter, adapter

    def engine_reconnect_factory() -> tuple[Any, Any]:
        reconnect_facade = PresentationRealtimeEngineHandler(
            runtime_engine_factory=RealtimeSessionEngine,
        )
        return reconnect_facade.runtime_adapter, reconnect_facade

    legacy = LegacyPresentationStepFunRealtimeHandler()
    facade = PresentationRealtimeEngineHandler(
        runtime_engine_factory=RealtimeSessionEngine,
    )
    legacy_result = await _drive_real_golden_conversation(
        initial_handler=legacy,
        initial_surface=legacy,
        reconnect_factory=legacy_reconnect_factory,
    )
    mutated_engine_result = await _drive_real_golden_conversation(
        initial_handler=facade.runtime_adapter,
        initial_surface=facade,
        reconnect_factory=engine_reconnect_factory,
        mutate_transcript_event=True,
    )

    with pytest.raises(AssertionError):
        _assert_golden_differential(legacy_result, mutated_engine_result)
