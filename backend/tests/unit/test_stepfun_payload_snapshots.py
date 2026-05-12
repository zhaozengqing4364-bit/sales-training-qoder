"""Q-02 characterization snapshots for StepFun realtime outward payloads.

These tests pin the observable payload shapes before any future StepFun handler
decomposition.  They intentionally avoid splitting the large handler; they make
the existing protocol safer to refactor incrementally.
"""

from __future__ import annotations

import copy
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from sales_bot.websocket.components.stepfun_function_call_helpers import (
    build_function_call_output_event,
)

if "websockets" not in sys.modules:
    websockets_stub = types.ModuleType("websockets")
    exceptions_stub = types.ModuleType("websockets.exceptions")

    class ConnectionClosed(Exception):
        pass

    setattr(exceptions_stub, "ConnectionClosed", ConnectionClosed)
    setattr(websockets_stub, "exceptions", exceptions_stub)
    sys.modules["websockets"] = websockets_stub
    sys.modules["websockets.exceptions"] = exceptions_stub

if "chromadb" not in sys.modules:
    chromadb_stub = types.ModuleType("chromadb")
    chromadb_api_stub = types.ModuleType("chromadb.api")
    chromadb_models_stub = types.ModuleType("chromadb.api.models")
    chromadb_collection_stub = types.ModuleType("chromadb.api.models.Collection")
    chromadb_config_stub = types.ModuleType("chromadb.config")

    class ClientAPI:
        pass

    class Collection:
        pass

    class Settings:
        def __init__(self, **_kwargs: object) -> None:
            pass

    setattr(chromadb_stub, "PersistentClient", lambda *_args, **_kwargs: None)
    setattr(chromadb_api_stub, "ClientAPI", ClientAPI)
    setattr(chromadb_collection_stub, "Collection", Collection)
    setattr(chromadb_config_stub, "Settings", Settings)
    sys.modules["chromadb"] = chromadb_stub
    sys.modules["chromadb.api"] = chromadb_api_stub
    sys.modules["chromadb.api.models"] = chromadb_models_stub
    sys.modules["chromadb.api.models.Collection"] = chromadb_collection_stub
    sys.modules["chromadb.config"] = chromadb_config_stub

import sales_bot.websocket.stepfun_realtime_handler as stepfun_handler_module
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


class CaptureManager:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, _websocket, payload: dict) -> None:
        self.sent.append(copy.deepcopy(payload))


class _SessionContext:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def __aenter__(self) -> AsyncSession:
        return self._db

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _scrub_dynamic_fields(payload: dict) -> dict:
    scrubbed = copy.deepcopy(payload)
    if "timestamp" in scrubbed:
        scrubbed["timestamp"] = "<timestamp>"
    if "trace_id" in scrubbed:
        scrubbed["trace_id"] = "<trace_id>"
    if "stream_id" in scrubbed:
        scrubbed["stream_id"] = "<stream_id>"
    return scrubbed


@pytest.mark.asyncio
async def test_prd46_stepfun_session_update_payload_uses_snapshot_allowlist_only(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_upstream: list[dict] = []
    user = User(
        user_id="user-stepfun-snapshot",
        wechat_user_id="stepfun_snapshot_user",
        name="StepFun Snapshot User",
        role="user",
    )
    scenario = Scenario(
        scenario_id="scenario-stepfun-snapshot",
        scenario_type="sales",
        name="stepfun_snapshot_scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id="session-stepfun-snapshot",
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        agent_id="agent-v1",
        persona_id="persona-v1",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={
            "voice_mode": "stepfun_realtime",
            "runtime_profile_id": "runtime-v1",
            "model_name": "step-audio-2",
            "voice_name": "qingchunshaonv",
            "temperature": 0.4,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": "server_vad",
            "instructions": "snapshot instruction v1",
            "instruction_contract_hash": "sha256:instruction-v1",
            "knowledge_base_ids": ["kb-v1"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "network_access_mode": "off",
            },
            "practice_template": "must not enter session.update",
            "content_assets": ["must not enter session.update"],
            "hidden_information": "隐藏预算不能进入 StepFun 初始输入",
            "rubric": {"must": "not enter session.update"},
            "curriculum_snapshot": {"must": "not enter session.update"},
            "latest_practice_content": "must not enter session.update",
            "raw_template_content": "must not enter session.update",
        },
        curriculum_snapshot={
            "practice_template": {
                "asset_type": "practice_template",
                "asset_id": "template-latest",
                "version": 99,
                "hash": "sha256:latest-template",
                "snapshot_label": "published",
            },
            "content_assets": [
                {
                    "asset_type": "case_item",
                    "asset_id": "case-v1",
                    "version": 1,
                    "hash": "sha256:case-v1",
                    "hidden_information": "隐藏预算不能进入 StepFun 初始输入",
                }
            ],
            "latest_practice_content": "must not enter StepFun payload",
            "runtime": {
                "runtime_profile_id": "runtime-latest",
                "instruction_contract_hash": "sha256:latest-instruction",
            },
        },
    )
    test_db.add_all([user, scenario, session])
    await test_db.commit()

    async def fail_if_latest_policy_is_resolved(*_args: object, **_kwargs: object) -> dict:
        raise AssertionError("StepFun must not resolve latest curriculum/practice content")

    monkeypatch.setattr(
        stepfun_handler_module,
        "AsyncSessionLocal",
        lambda: _SessionContext(test_db),
    )
    monkeypatch.setattr(
        stepfun_handler_module.VoiceRuntimePolicyService,
        "resolve_effective_policy",
        fail_if_latest_policy_is_resolved,
    )
    monkeypatch.setattr(
        StepFunRealtimeHandler,
        "_refresh_sales_stage_runtime_config",
        AsyncMock(),
    )
    monkeypatch.setattr(
        StepFunRealtimeHandler,
        "_merge_kb_dictionary_into_effective_policy",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        stepfun_handler_module.websockets,
        "connect",
        AsyncMock(return_value=object()),
        raising=False,
    )

    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stepfun-snapshot"
    handler._send_upstream = AsyncMock(
        side_effect=lambda payload: sent_upstream.append(copy.deepcopy(payload))
    )
    handler._ensure_upstream_keepalive_task = MagicMock()
    handler._maybe_start_kb_lock_warmup = AsyncMock()

    await handler._load_effective_policy()
    await handler._connect_upstream()

    assert handler._effective_policy["runtime_profile_id"] == "runtime-v1"
    assert handler._effective_policy["knowledge_base_ids"] == ["kb-v1"]
    assert handler._stepfun_instructions.startswith("snapshot instruction v1")
    assert "must not enter StepFun payload" not in handler._stepfun_instructions
    assert handler._stepfun_model == "step-audio-2"
    assert len(sent_upstream) == 1

    session_update = sent_upstream[0]
    assert set(session_update) == {"type", "session"}
    assert session_update["type"] == "session.update"

    session_payload = session_update["session"]
    assert set(session_payload).issubset(
        {
            "voice",
            "temperature",
            "input_audio_format",
            "output_audio_format",
            "turn_detection",
            "input_audio_transcription",
            "instructions",
            "tools",
        }
    )
    assert session_payload["voice"] == "qingchunshaonv"
    assert session_payload["temperature"] == 0.4
    assert session_payload["input_audio_format"] == "pcm16"
    assert session_payload["output_audio_format"] == "pcm16"
    assert "turn_detection" in session_payload
    assert session_payload["input_audio_transcription"] == {"language": "zh"}
    assert session_payload["instructions"].startswith("snapshot instruction v1")
    assert session_payload["tools"][0]["type"] == "function"

    serialized_payload = json.dumps(session_update, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "practice_template",
        "content_assets",
        "hidden_information",
        "隐藏预算不能进入 StepFun 初始输入",
        "rubric",
        "curriculum_snapshot",
        "latest_practice_content",
        "raw_template_content",
        "template-latest",
        "sha256:latest-template",
        "runtime-latest",
        "sha256:latest-instruction",
        "must not enter session.update",
        "must not enter StepFun payload",
    ):
        assert forbidden not in serialized_payload


@pytest.mark.asyncio
async def test_q02_response_create_payload_snapshot_preserves_instruction_contract():
    handler = StepFunRealtimeHandler()
    handler._stepfun_instructions = "基础指令"
    handler._pending_grounding_context = "证据片段"
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()

    created = await handler._create_response(count_turn=True)

    assert created is True
    assert handler.current_request_id == 1
    assert handler.turn_count == 1
    handler._send_status.assert_awaited_once_with("thinking")
    handler._send_upstream.assert_awaited_once_with(
        {
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"],
                "instructions": "基础指令\n\n【当前轮内部知识依据】\n证据片段",
            },
        }
    )


@pytest.mark.asyncio
async def test_q02_kb_lock_blocked_response_tts_payload_snapshot():
    handler = StepFunRealtimeHandler()
    manager = CaptureManager()
    blocked_text = "当前内部知识库没有足够依据回答这个问题。"
    setattr(handler, "manager", manager)
    handler.websocket = object()
    handler.session_id = "session-1"
    handler._pending_blocked_response_text = blocked_text
    handler._send_status = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._append_sales_stage_context_message = MagicMock()

    created = await handler._create_response(count_turn=True)

    assert created is True
    assert _scrub_dynamic_fields(manager.sent[0]) == {
        "type": "tts_audio",
        "timestamp": "<timestamp>",
        "stream_id": "<stream_id>",
        "request_id": 1,
        "data": {
            "text": blocked_text,
            "audio": "",
            "audio_format": "",
            "duration_ms": len(blocked_text) * 100,
            "fallback": "browser_tts",
            "playback_rate": 1.0,
        },
    }
    assert handler._pending_blocked_response_text == ""
    handler._send_status.assert_any_await("thinking")
    handler._send_status.assert_any_await("listening")


def test_q02_function_call_tool_result_payload_snapshot():
    event = build_function_call_output_event(
        call_id="call-001",
        output_payload={
            "query": "产品定价",
            "count": 1,
            "results": [{"knowledge_base_id": "kb-1", "snippet": "证据"}],
        },
    )

    assert event == {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": "call-001",
            "output": json.dumps(
                {
                    "query": "产品定价",
                    "count": 1,
                    "results": [{"knowledge_base_id": "kb-1", "snippet": "证据"}],
                },
                ensure_ascii=False,
            ),
        },
    }


@pytest.mark.asyncio
async def test_q02_realtime_feedback_score_update_payload_snapshot():
    handler = StepFunRealtimeHandler()
    manager = CaptureManager()
    setattr(handler, "manager", manager)
    handler.websocket = object()
    handler.session_id = "session-1"

    await handler._send_score_update(
        turn_number=3,
        overall_score=82.5,
        dimension_scores={"discovery": 80.0, "objection": 85.0},
        suggestions=["追问预算优先级"],
        stage_name="异议处理",
        claim_truth={"status": "supported"},
    )

    assert _scrub_dynamic_fields(manager.sent[0]) == {
        "type": "score_update",
        "timestamp": "<timestamp>",
        "trace_id": "<trace_id>",
        "data": {
            "session_id": "session-1",
            "turn_count": 3,
            "overall_score": 82.5,
            "dimension_scores": {"discovery": 80.0, "objection": 85.0},
            "suggestions": ["追问预算优先级"],
            "stage_name": "异议处理",
            "claim_truth": {"status": "supported"},
        },
    }


@pytest.mark.asyncio
async def test_q02_resume_message_routes_to_listening_status_snapshot():
    handler = StepFunRealtimeHandler()
    handler._apply_lifecycle_action = AsyncMock(return_value=object())
    handler._send_status = AsyncMock()

    await handler._handle_client_text(json.dumps({"type": "resume"}))

    handler._apply_lifecycle_action.assert_awaited_once_with("resume")
    handler._send_status.assert_awaited_once_with("listening")


@pytest.mark.asyncio
async def test_q02_text_response_create_failure_emits_stable_error_fallback():
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="opening")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response = AsyncMock(side_effect=RuntimeError("boom"))
    handler._send_error = AsyncMock()

    await handler._handle_client_text(
        json.dumps({"type": "text", "data": {"text": "介绍一下产品"}})
    )

    handler._send_error.assert_awaited_once_with(
        "[RESPONSE_CREATE_FAILED]",
        "响应生成暂时失败，请重试。",
    )
