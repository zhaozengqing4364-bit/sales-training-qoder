from __future__ import annotations

from typing import Any

import pytest

from sales_bot.websocket.stepfun_realtime_upstream import StepFunRealtimeUpstreamMixin
from sales_bot.websocket.stepfun_runtime_types import RealtimeResponseState
from training_runtime.stepfun_transport import StepFunSendResult, StepFunSendStatus


class FakeTransport:
    def __init__(self, result: StepFunSendResult) -> None:
        self.result = result
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    async def send_json(self, upstream_ws: Any, payload: dict[str, Any]) -> StepFunSendResult:
        self.calls.append((upstream_ws, payload))
        return self.result


class FakeManager:
    def __init__(self) -> None:
        self.sent_json: list[tuple[Any, dict[str, Any]]] = []

    async def send_json(self, websocket: Any, payload: dict[str, Any]) -> None:
        self.sent_json.append((websocket, payload))


class FakeUpstream(StepFunRealtimeUpstreamMixin):
    def __init__(self, transport: FakeTransport, upstream_ws: Any | None) -> None:
        self._stepfun_transport = transport
        self.upstream_ws = upstream_ws
        self.session_id = "session-1"
        self.activity_marks = 0

    def _mark_upstream_activity(self) -> None:
        self.activity_marks += 1


class FakeToolExecution:
    def __init__(self) -> None:
        self.build_policy_calls: list[dict[str, Any]] = []
        self.guardrail_calls: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    def build_tools_from_policy(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        self.build_policy_calls.append(policy)
        return [
            {"type": "function", "function": {"name": "search_internal_knowledge"}}
        ]

    def enforce_guardrails(
        self,
        tools: list[dict[str, Any]],
        policy: dict[str, Any],
    ) -> list[dict[str, Any]]:
        self.guardrail_calls.append((tools, policy))
        return [tool for tool in tools if tool.get("type") != "web_search"]


class FakeAudioFlow:
    def __init__(self) -> None:
        self.committed_inputs = 0
        self.output_audio: list[str] = []

    def commit_input_audio(self) -> list[str]:
        self.committed_inputs += 1
        return ["input-audio"]

    def append_output_audio(self, audio: str) -> None:
        self.output_audio.append(audio)


class CommitRespondingUpstream(FakeUpstream):
    def __init__(self, transport: FakeTransport, upstream_ws: Any | None) -> None:
        super().__init__(transport, upstream_ws)
        self.session_id = "session-1"
        self._has_uncommitted_audio = False
        self.scheduled_responses = 0
        self.created_responses = 0

    async def _schedule_response_after_commit(self) -> None:
        self.scheduled_responses += 1

    async def _create_response_from_pending_commit(self) -> bool:
        self.created_responses += 1
        return True


class AudioForwardingUpstream(FakeUpstream):
    def __init__(self, transport: FakeTransport, upstream_ws: Any | None) -> None:
        super().__init__(transport, upstream_ws)
        self.websocket = object()
        self.manager = FakeManager()
        self._active_response = RealtimeResponseState(
            request_id=3,
            stream_id="stream-output-flow",
        )
        self._stepfun_output_audio_format = "pcm16"
        self._stepfun_output_sample_rate = 24000
        self._stepfun_playback_rate = 1.25
        self._tts_chunk_protocol_version = "v1"
        self.statuses: list[str] = []

    async def _send_status(self, status: str) -> None:
        self.statuses.append(status)


class IdleTimeoutRecoveringUpstream(FakeUpstream):
    def __init__(self, transport: FakeTransport, upstream_ws: Any | None) -> None:
        super().__init__(transport, upstream_ws)
        self.session_id = "session-1"
        self.recover_calls: list[str] = []
        self.sent_errors: list[tuple[str, str]] = []

    def _compute_upstream_ws_lifetime_ms(self) -> float | None:
        return 61000.0

    async def _refresh_upstream_for_next_input(self, reason: str) -> bool:
        self.recover_calls.append(reason)
        return True

    async def _send_error(self, code: str, message: str) -> None:
        self.sent_errors.append((code, message))


class FakeVoiceRuntimeProfile:
    instructions = "profile base instructions"
    instruction_contract_hash = "profile-contract-hash"

    def __init__(self) -> None:
        self.compile_calls: list[dict[str, Any]] = []

    def compile_instructions(self, *, grounding_context: str = "") -> str:
        self.compile_calls.append({"grounding_context": grounding_context})
        return f"compiled profile instructions::{grounding_context}"


class ResponseCreatingUpstream(FakeUpstream):
    def __init__(
        self,
        transport: FakeTransport,
        upstream_ws: Any | None,
        profile: FakeVoiceRuntimeProfile | None,
    ) -> None:
        super().__init__(transport, upstream_ws)
        self.profile = profile
        self.session_id = "session-1"
        self._active_response = None
        self._pending_tool_followup_response = False
        self._pending_blocked_response_text = ""
        self.current_request_id = 0
        self.turn_count = 0
        self._pending_grounding_context = "  grounding ctx  "
        self._stepfun_instructions = "raw base instructions"
        self._instruction_contract_hash = "raw-contract-hash"
        self.statuses: list[str] = []
        self.grounding_debug_calls: list[tuple[str, dict[str, Any]]] = []

    def _active_voice_runtime_profile(self) -> FakeVoiceRuntimeProfile:
        if self.profile is None:
            raise AttributeError("profile unavailable")
        return self.profile

    async def _send_status(self, status: str) -> None:
        self.statuses.append(status)

    def _log_grounding_debug(self, event: str, **payload: Any) -> None:
        self.grounding_debug_calls.append((event, payload))


@pytest.mark.asyncio
async def test_upstream_delegates_send_to_transport() -> None:
    payload = {"type": "session.update", "session": {"voice": "qingchunshaonv"}}
    upstream_ws = object()
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = FakeUpstream(transport, upstream_ws)

    await upstream._send_upstream(payload)

    assert transport.calls == [(upstream_ws, payload)]
    assert transport.calls[0][1] is payload


@pytest.mark.asyncio
async def test_upstream_noops_when_upstream_ws_is_none() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = FakeUpstream(transport, None)

    await upstream._send_upstream({"type": "response.create"})

    assert transport.calls == []
    assert upstream.activity_marks == 0


@pytest.mark.asyncio
async def test_upstream_marks_activity_only_when_transport_send_succeeds() -> None:
    upstream_ws = object()
    sent_transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    sent_upstream = FakeUpstream(sent_transport, upstream_ws)

    await sent_upstream._send_upstream({"type": "session.update"})

    assert sent_upstream.activity_marks == 1

    failed_transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.FAILED))
    failed_upstream = FakeUpstream(failed_transport, upstream_ws)

    await failed_upstream._send_upstream({"type": "response.create"})

    assert failed_upstream.activity_marks == 0


@pytest.mark.asyncio
async def test_upstream_commit_and_respond_commits_audio_flow_input() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = CommitRespondingUpstream(transport, object())
    audio_flow = FakeAudioFlow()
    setattr(upstream, "_audio_flow", audio_flow)

    await upstream._commit_and_respond()

    assert audio_flow.committed_inputs == 0
    assert transport.calls == []
    assert upstream.scheduled_responses == 0

    upstream._has_uncommitted_audio = True
    await upstream._commit_and_respond()

    assert audio_flow.committed_inputs == 1
    assert transport.calls[0][1] == {"type": "input_audio_buffer.commit"}
    assert upstream._has_uncommitted_audio is False
    assert upstream.scheduled_responses == 1
    assert upstream.created_responses == 0


@pytest.mark.asyncio
async def test_upstream_forward_audio_delta_appends_output_audio_without_payload_change() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = AudioForwardingUpstream(transport, object())
    audio_flow = FakeAudioFlow()
    setattr(upstream, "_audio_flow", audio_flow)

    await upstream._forward_audio_delta_chunk("AAECAw==")

    payload = upstream.manager.sent_json[0][1]
    assert payload["type"] == "tts_chunk"
    assert payload["stream_id"] == "stream-output-flow"
    assert payload["request_id"] == 3
    assert payload["data"] == {
        "chunk_index": 0,
        "audio": "AAECAw==",
        "duration_ms": 0,
        "is_final": False,
        "audio_format": "pcm16",
        "sample_rate": 24000,
        "playback_rate": 1.25,
    }
    assert audio_flow.output_audio == ["AAECAw=="]


@pytest.mark.asyncio
async def test_upstream_idle_timeout_error_refreshes_connection_before_forwarding_error() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = IdleTimeoutRecoveringUpstream(transport, object())

    await upstream._handle_upstream_error(
        {"type": "error", "error": {"message": "too long without operation"}}
    )

    assert upstream.recover_calls == ["upstream_idle_timeout_error"]
    assert upstream.sent_errors == [
        (
            "[STEPFUN_UPSTREAM_RECOVERED]",
            "Realtime 上游连接已从空闲超时中恢复，请重新发送这一轮内容。",
        )
    ]


def test_upstream_builds_tools_through_tool_execution_module() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = FakeUpstream(transport, None)
    policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"internal_knowledge_enabled": True},
    }
    upstream._effective_policy = policy
    tool_execution = FakeToolExecution()
    setattr(upstream, "_tool_execution", tool_execution)

    tools = upstream._build_stepfun_tools_from_policy()

    assert tool_execution.build_policy_calls == [policy]
    assert tool_execution.build_policy_calls[0] is policy
    assert tools == [
        {"type": "function", "function": {"name": "search_internal_knowledge"}}
    ]


def test_upstream_enforces_tool_guardrails_through_tool_execution_module() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = FakeUpstream(transport, None)
    policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"network_access_mode": "off"},
    }
    upstream._effective_policy = policy
    tool_execution = FakeToolExecution()
    setattr(upstream, "_tool_execution", tool_execution)
    tools = [
        {"type": "function", "function": {"name": "search_internal_knowledge"}},
        {"type": "web_search"},
    ]

    filtered_tools = upstream._enforce_stepfun_tool_guardrails(tools)

    assert tool_execution.guardrail_calls == [(tools, policy)]
    assert tool_execution.guardrail_calls[0][0] is tools
    assert tool_execution.guardrail_calls[0][1] is policy
    assert filtered_tools == [
        {"type": "function", "function": {"name": "search_internal_knowledge"}}
    ]


def test_upstream_tool_guardrails_fall_back_without_tool_execution_module() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = FakeUpstream(transport, None)
    upstream._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "network_access_mode": "full",
            "allow_web_search_without_kb": True,
        },
    }
    tools = [
        {"type": "function", "function": {"name": "search_internal_knowledge"}},
        {"type": "web_search"},
    ]

    filtered_tools = upstream._enforce_stepfun_tool_guardrails(tools)

    assert filtered_tools == [
        {"type": "function", "function": {"name": "search_internal_knowledge"}}
    ]


@pytest.mark.asyncio
async def test_upstream_reads_voice_config_from_profile() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    profile = FakeVoiceRuntimeProfile()
    upstream = ResponseCreatingUpstream(transport, object(), profile)

    created = await upstream._create_response()

    assert created is True
    assert profile.compile_calls == [{"grounding_context": "grounding ctx"}]
    assert transport.calls[0][1] == {
        "type": "response.create",
        "response": {
            "modalities": ["audio", "text"],
            "instructions": "compiled profile instructions::grounding ctx",
        },
    }
    assert upstream._pending_grounding_context == ""
    assert upstream.grounding_debug_calls == [
        (
            "response_create",
            {
                "request_id": 1,
                "has_grounding_context": True,
                "grounding_context_length": len("grounding ctx"),
                "has_base_instructions": True,
                "final_instruction_length": len(
                    "compiled profile instructions::grounding ctx"
                ),
                "instruction_contract_hash": "profile-contract-hash",
            },
        )
    ]


@pytest.mark.asyncio
async def test_upstream_falls_back_to_raw_instructions_without_profile() -> None:
    transport = FakeTransport(StepFunSendResult(status=StepFunSendStatus.SENT))
    upstream = ResponseCreatingUpstream(transport, object(), None)

    created = await upstream._create_response()

    assert created is True
    assert transport.calls[0][1] == {
        "type": "response.create",
        "response": {
            "modalities": ["audio", "text"],
            "instructions": "raw base instructions\n\n【当前轮内部知识依据】\ngrounding ctx",
        },
    }
    assert upstream._pending_grounding_context == ""
    assert upstream.grounding_debug_calls[0][1]["instruction_contract_hash"] == (
        "raw-contract-hash"
    )
