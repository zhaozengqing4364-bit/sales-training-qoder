"""
Unit tests for StepFunRealtimeHandler realtime channel behavior.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import sales_bot.websocket.stepfun_realtime_handler as stepfun_module
from common.error_handling.result import Result
from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.websocket.realtime_feedback_arbiter import RealtimeFeedbackPacingState
from sales_bot.websocket.stepfun_realtime_handler import (
    RealtimeResponseState,
    StepFunRealtimeHandler,
)


def test_stepfun_realtime_handler_defaults_to_latest_realtime_model(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("STEPFUN_REALTIME_MODEL", raising=False)

    handler = StepFunRealtimeHandler()

    assert handler._stepfun_model == "step-audio-r1.1"


@pytest.mark.asyncio
async def test_handle_client_text_persists_user_message_before_create_response():
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.turn_count = 0

    handler._persist_message = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="opening")
    handler._run_realtime_feedback = AsyncMock(
        return_value={"score_snapshot": {"overall_score": 82}}
    )
    handler._prepare_grounding_context = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._create_response = AsyncMock()

    await handler._handle_client_text(
        json.dumps(
            {
                "type": "text",
                "data": {"text": "你好，给我介绍一下产品"},
            }
        )
    )

    handler._persist_message.assert_awaited_once_with(
        turn_number=1,
        role="user",
        content="你好，给我介绍一下产品",
        sales_stage="opening",
        analysis_data={"score_snapshot": {"overall_score": 82}},
    )
    handler._analyze_and_emit_sales_stage.assert_awaited_once_with(
        user_text="你好，给我介绍一下产品",
        turn_number=1,
    )
    handler._run_realtime_feedback.assert_awaited_once_with(
        user_text="你好，给我介绍一下产品",
        turn_number=1,
        sales_stage="opening",
    )
    handler._prepare_grounding_context.assert_awaited_once_with(
        "你好，给我介绍一下产品"
    )
    handler._create_response.assert_awaited_once_with(count_turn=True)
    assert handler._send_upstream.await_count == 1

    payload = handler._send_upstream.await_args_list[0].args[0]
    assert payload["type"] == "conversation.item.create"
    assert payload["item"]["content"][0]["text"] == "你好，给我介绍一下产品"


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_persists_user_message_before_response_created():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(
        return_value={"fuzzy_words": [{"category": "uncertain"}]}
    )
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    await handler._handle_upstream_event(
        {
            "type": "input_audio_buffer.transcription.completed",
            "transcript": "这是语音最终识别文本",
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "这是语音最终识别文本",
        is_final=True,
    )
    handler._persist_message.assert_awaited_once_with(
        turn_number=3,
        role="user",
        content="这是语音最终识别文本",
        sales_stage="discovery",
        analysis_data={"fuzzy_words": [{"category": "uncertain"}]},
    )
    handler._analyze_and_emit_sales_stage.assert_awaited_once_with(
        user_text="这是语音最终识别文本",
        turn_number=3,
    )
    handler._run_realtime_feedback.assert_awaited_once_with(
        user_text="这是语音最终识别文本",
        turn_number=3,
        sales_stage="discovery",
    )
    handler._prepare_grounding_context.assert_awaited_once_with("这是语音最终识别文本")
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_persists_user_message_after_response_created():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2
    handler._active_response = RealtimeResponseState(
        request_id=9,
        stream_id="stream-after-create",
    )

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="presentation")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=False)

    await handler._handle_upstream_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "这是新一轮语音文本",
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "这是新一轮语音文本",
        is_final=True,
    )
    handler._persist_message.assert_awaited_once_with(
        turn_number=2,
        role="user",
        content="这是新一轮语音文本",
        sales_stage="presentation",
        analysis_data={},
    )
    handler._analyze_and_emit_sales_stage.assert_awaited_once_with(
        user_text="这是新一轮语音文本",
        turn_number=2,
    )
    handler._run_realtime_feedback.assert_awaited_once_with(
        user_text="这是新一轮语音文本",
        turn_number=2,
        sales_stage="presentation",
    )
    handler._prepare_grounding_context.assert_awaited_once_with("这是新一轮语音文本")
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_applies_transcript_normalization():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2
    handler._effective_policy = {
        "tool_policy": {
            "transcript_normalization_enabled": True,
            "transcript_normalization_lexicon": [
                {
                    "canonical_term": "石犀",
                    "aliases": ["石溪"],
                    "scope": "global",
                    "replace_on_final_only": True,
                }
            ],
        }
    }

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    await handler._handle_upstream_event(
        {
            "type": "input_audio_buffer.transcription.completed",
            "transcript": "这是石溪平台的最终识别文本",
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "这是石犀平台的最终识别文本",
        is_final=True,
    )
    persisted_kwargs = handler._persist_message.await_args.kwargs
    assert persisted_kwargs["content"] == "这是石犀平台的最终识别文本"
    assert persisted_kwargs["analysis_data"]["transcript_metadata"]["raw_text"] == "这是石溪平台的最终识别文本"
    handler._prepare_grounding_context.assert_awaited_once_with("这是石犀平台的最终识别文本")


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_does_not_schedule_followup_when_response_active():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=3,
        stream_id="stream-active-response",
    )

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()

    async def _fake_prepare(_transcript: str) -> None:
        handler._pending_grounding_context = "prefetched grounding"

    handler._prepare_grounding_context = AsyncMock(side_effect=_fake_prepare)
    handler._create_response_from_pending_commit = AsyncMock(return_value=False)

    await handler._handle_upstream_event(
        {
            "type": "input_audio_buffer.transcription.completed",
            "transcript": "介绍一下我们的产品",
        }
    )

    assert handler._pending_tool_followup_response is False
    assert handler._grounding_preparation_in_progress is False
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_waits_for_grounding_then_creates_response(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._grounding_preparation_in_progress = True
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    sleep_calls = 0

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            handler._grounding_preparation_in_progress = False

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._pending_response_timeout_fallback()

    handler._create_response_from_pending_commit.assert_awaited_once()
    assert sleep_calls >= 2


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_waits_for_transcription_before_creating_response(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._awaiting_transcription_after_commit = True
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    sleep_calls = 0

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            handler._awaiting_transcription_after_commit = False

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._pending_response_timeout_fallback()

    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_recover_upstream_after_disconnect_uses_shared_jitter_backoff(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.session_status = "in_progress"
    handler._upstream_auto_recover_enabled = True
    handler._upstream_auto_recover_max_retries = 1
    handler._upstream_auto_recover_base_delay_seconds = 0.4
    handler._upstream_auto_recover_max_delay_seconds = 5.0

    helper_calls = []

    def _fake_backoff(**kwargs):
        helper_calls.append(kwargs)
        return 0.05

    sleep_mock = AsyncMock()
    monkeypatch.setattr(
        stepfun_module,
        "compute_jitter_backoff_seconds",
        _fake_backoff,
    )
    monkeypatch.setattr(stepfun_module.asyncio, "sleep", sleep_mock)

    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_status = AsyncMock()

    recovered = await handler._recover_upstream_after_disconnect(
        close_code=1006,
        close_reason="socket closed",
        ws_lifetime_ms=2000.0,
    )

    assert recovered is True
    assert helper_calls == [
        {
            "attempt": 1,
            "base_delay_seconds": 0.4,
            "max_delay_seconds": 5.0,
        }
    ]
    sleep_mock.assert_awaited_once_with(0.05)


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_ignores_duplicate_transcript_within_window():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2
    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=False)

    event = {
        "type": "input_audio_buffer.transcription.completed",
        "transcript": "重复转写",
    }
    await handler._handle_upstream_event(event)
    await handler._handle_upstream_event(event)

    handler._send_transcript.assert_awaited_once_with("重复转写", is_final=True)
    handler._persist_message.assert_awaited_once()
    handler._prepare_grounding_context.assert_awaited_once_with("重复转写")
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_grounding_context_short_query_still_retrieves_knowledge():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        }
    }
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 1,
            "results": [
                {
                    "snippet": "标准版报价可按年付费，支持按席位扩容。",
                }
            ],
        }
    )

    await handler._prepare_grounding_context("价")

    handler._tool_search_internal_knowledge.assert_awaited_once_with(
        {"query": "价", "top_k": 3}
    )
    assert "用户问题：价" in handler._pending_grounding_context
    assert "标准版报价可按年付费" in handler._pending_grounding_context
    assert "以命中片段为准" in handler._pending_grounding_context


@pytest.mark.asyncio
async def test_prepare_grounding_context_empty_query_skips_retrieval():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        }
    }
    handler._tool_search_internal_knowledge = AsyncMock()

    await handler._prepare_grounding_context("   ")

    handler._tool_search_internal_knowledge.assert_not_awaited()
    assert handler._pending_grounding_context == ""


@pytest.mark.asyncio
async def test_prepare_grounding_context_forces_retrieval_when_kb_bound_and_internal_flag_disabled():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": False,
            "retrieval_top_k": 3,
        },
    }
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 1,
            "results": [
                {
                    "snippet": "实习专家产品名录包含标准版与企业版。",
                }
            ],
        }
    )

    await handler._prepare_grounding_context("请介绍实习专家产品名录")

    handler._tool_search_internal_knowledge.assert_awaited_once_with(
        {"query": "请介绍实习专家产品名录", "top_k": 3}
    )
    assert "实习专家产品名录" in handler._pending_grounding_context


@pytest.mark.asyncio
async def test_prepare_grounding_context_applies_internal_only_guardrail_when_kb_retrieval_empty():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        },
    }
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 0,
            "results": [],
            "message": "未命中",
        }
    )

    await handler._prepare_grounding_context("我们的产品线有哪些")

    assert "仅依据企业内部知识库回答" in handler._pending_grounding_context
    assert "我们的产品线有哪些" in handler._pending_grounding_context


@pytest.mark.asyncio
async def test_prepare_grounding_context_applies_internal_only_guardrail_when_kb_not_ready():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        },
    }
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 0,
            "results": [],
            "message": "内部知识库文档尚未处理完成，请稍后重试",
        }
    )

    await handler._prepare_grounding_context("请介绍实习专家产品名录")

    assert "仅依据企业内部知识库回答" in handler._pending_grounding_context
    assert "请介绍实习专家产品名录" in handler._pending_grounding_context
    assert "提供更具体的产品关键词或版本信息" in handler._pending_grounding_context


@pytest.mark.asyncio
async def test_prepare_grounding_context_sets_blocked_response_when_kb_lock_blocks(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "enable_internal_retrieval": True,
        },
    }
    handler._record_kb_lock_decision = AsyncMock()
    monkeypatch.setattr(
        stepfun_module,
        "evaluate_kb_lock_decision",
        AsyncMock(
            return_value=SimpleNamespace(
                allow_generation=False,
                status="blocked_empty",
                user_message="知识库未命中，请补充关键词",
                result_count=0,
                retrieval_mode="",
                error_detail="",
            )
        ),
    )

    await handler._prepare_grounding_context("介绍产品价格")

    assert handler._pending_blocked_response_text == "知识库未命中，请补充关键词"
    assert handler._pending_grounding_context == ""
    assert handler._record_kb_lock_decision.await_count == 1
    decision_kwargs = handler._record_kb_lock_decision.await_args.kwargs
    assert decision_kwargs["status"] == "blocked_empty"
    assert decision_kwargs["blocked"] is True


@pytest.mark.asyncio
async def test_prepare_grounding_context_timeout_degrades_to_coach_mode(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "kb_lock_mode": "coach_mode",
            "retrieval_top_k": 3,
        },
    }
    handler._record_kb_lock_decision = AsyncMock()

    async def _raise_timeout(*_args, **_kwargs):
        raise stepfun_module.asyncio.TimeoutError

    monkeypatch.setattr(stepfun_module.asyncio, "wait_for", _raise_timeout)

    await handler._prepare_grounding_context("请介绍石溪产品方案")

    assert handler._pending_blocked_response_text == ""
    assert "训练辅导模式" in handler._pending_grounding_context
    assert "请介绍石溪产品方案" in handler._pending_grounding_context
    decision_kwargs = handler._record_kb_lock_decision.await_args.kwargs
    assert decision_kwargs["status"] == "coach_search_timeout"
    assert decision_kwargs["blocked"] is False


def test_enforce_tool_policy_guardrails_auto_enables_kb_lock_for_legacy_snapshot(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "enable_web_search": False,
        },
        "source": {},
        "instructions": "角色设定",
    }
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    tool_policy = handler._effective_policy["tool_policy"]
    assert tool_policy["require_kb_grounding"] is True
    assert tool_policy["retrieval_priority"] == "kb_only"
    assert tool_policy["enable_web_search"] is False
    assert handler._effective_policy["source"]["kb_lock_default"] == "auto_enabled_when_kb_bound"


def test_enforce_tool_policy_guardrails_backfills_legacy_false_kb_lock(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-legacy-false-1"],
        "turn_detection": "server_vad",
        "tool_policy": {
            "require_kb_grounding": False,
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "enable_web_search": False,
        },
        "persona_policy": {"tool_policy": {}},
        "source": {},
        "instructions": "角色设定",
    }
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    tool_policy = handler._effective_policy["tool_policy"]
    assert tool_policy["require_kb_grounding"] is True
    assert handler._effective_policy["turn_detection"] is None
    assert (
        handler._effective_policy["source"]["kb_lock_legacy_snapshot_backfill"]
        == "require_kb_grounding_false_to_true"
    )
    assert (
        handler._effective_policy["source"]["turn_detection_enforcement"]
        == "manual_commit_required_by_kb_lock"
    )


def test_enforce_tool_policy_guardrails_respects_explicit_persona_disable(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-explicit-disable-1"],
        "tool_policy": {
            "require_kb_grounding": False,
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "enable_web_search": False,
        },
        "persona_policy": {
            "tool_policy": {"require_kb_grounding": False},
        },
        "source": {},
        "instructions": "角色设定",
    }
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    assert handler._effective_policy["tool_policy"]["require_kb_grounding"] is False
    assert "kb_lock_legacy_snapshot_backfill" not in handler._effective_policy["source"]


@pytest.mark.asyncio
async def test_create_response_uses_local_blocked_message_without_upstream_call():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._pending_blocked_response_text = "当前会话必须先命中知识库，暂不生成回答。"
    handler.turn_count = 0

    created = await handler._create_response(count_turn=True)

    assert created is True
    assert handler.turn_count == 1
    handler._send_upstream.assert_not_awaited()
    handler._persist_message.assert_awaited_once_with(
        turn_number=1,
        role="assistant",
        content="当前会话必须先命中知识库，暂不生成回答。",
    )
    assert handler.manager.send_json.await_count == 1
    payload = handler.manager.send_json.await_args_list[0].args[1]
    assert payload["type"] == "tts_audio"
    assert payload["data"]["text"] == "当前会话必须先命中知识库，暂不生成回答。"


@pytest.mark.asyncio
async def test_flush_active_response_persists_assistant_message_and_sends_final_chunk():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 3
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()

    handler._active_response = RealtimeResponseState(
        request_id=7,
        stream_id="stream-xyz",
        chunk_index=2,
        total_duration_ms=1200,
    )
    handler._persist_message = AsyncMock()
    handler._send_status = AsyncMock()

    await handler._flush_active_response(
        {
            "response": {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "这是 AI 回复"}],
                    }
                ]
            }
        }
    )

    handler._persist_message.assert_awaited_once_with(
        turn_number=3,
        role="assistant",
        content="这是 AI 回复",
    )
    handler._send_status.assert_awaited_once_with("listening")
    assert handler.manager.send_json.await_count == 1

    message = handler.manager.send_json.await_args_list[0].args[1]
    assert message["type"] == "tts_chunk"
    assert message["stream_id"] == "stream-xyz"
    assert message["request_id"] == 7
    assert message["data"]["is_final"] is True
    assert message["data"]["text"] == "这是 AI 回复"


def test_extract_text_payload_prefers_text_and_supports_legacy_content():
    assert (
        StepFunRealtimeHandler._extract_text_payload(
            {"text": "新字段优先", "content": "旧字段"}
        )
        == "新字段优先"
    )
    assert (
        StepFunRealtimeHandler._extract_text_payload({"content": "兼容旧字段"})
        == "兼容旧字段"
    )
    assert StepFunRealtimeHandler._extract_text_payload({}) == ""


@pytest.mark.asyncio
async def test_commit_and_respond_ignores_duplicate_without_new_audio():
    handler = StepFunRealtimeHandler()
    handler._send_upstream = AsyncMock()
    handler._schedule_response_after_commit = AsyncMock()

    handler._has_uncommitted_audio = False
    await handler._commit_and_respond()
    handler._send_upstream.assert_not_awaited()
    handler._schedule_response_after_commit.assert_not_awaited()

    handler._has_uncommitted_audio = True
    await handler._commit_and_respond()
    handler._send_upstream.assert_awaited_once_with(
        {"type": "input_audio_buffer.commit"}
    )
    handler._schedule_response_after_commit.assert_awaited_once()
    assert handler._has_uncommitted_audio is False

    await handler._commit_and_respond()
    assert handler._send_upstream.await_count == 1
    assert handler._schedule_response_after_commit.await_count == 1


@pytest.mark.asyncio
async def test_execute_function_call_defers_followup_while_response_active():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=1, stream_id="stream-active"
    )
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "query": "产品",
            "count": 1,
            "results": [{"snippet": "石犀平台能力"}],
        }
    )
    handler._send_upstream = AsyncMock()
    handler._create_response = AsyncMock()

    executed = await handler._execute_function_call(
        call_id="call-1",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"产品"}',
        trigger_followup_response=True,
    )

    assert executed is True
    assert handler._pending_tool_followup_response is True
    handler._create_response.assert_not_awaited()
    handler._send_upstream.assert_awaited_once()
    payload = handler._send_upstream.await_args.args[0]
    assert payload["item"]["type"] == "function_call_output"
    assert payload["item"]["call_id"] == "call-1"


@pytest.mark.asyncio
async def test_accumulate_function_call_arguments_prefers_done_payload_without_duplication():
    handler = StepFunRealtimeHandler()
    handler._execute_function_call = AsyncMock(return_value=True)

    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-dup",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"石犀',
        }
    )
    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-dup",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"石犀产品"}',
        },
        done=True,
    )

    handler._execute_function_call.assert_awaited_once_with(
        call_id="call-dup",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"石犀产品"}',
        trigger_followup_response=True,
    )


@pytest.mark.asyncio
async def test_accumulate_function_call_arguments_falls_back_to_delta_when_done_invalid():
    handler = StepFunRealtimeHandler()
    handler._execute_function_call = AsyncMock(return_value=True)

    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-fallback",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"石犀产品"}',
        }
    )
    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-fallback",
            "name": "search_internal_knowledge",
            "arguments": '{"query":',
        },
        done=True,
    )

    handler._execute_function_call.assert_awaited_once_with(
        call_id="call-fallback",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"石犀产品"}',
        trigger_followup_response=True,
    )


@pytest.mark.asyncio
async def test_response_done_triggers_pending_tool_followup_response():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=12,
        stream_id="stream-followup",
    )
    handler._pending_tool_followup_response = True
    handler._flush_active_response = AsyncMock(return_value=True)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=False)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"output": []}}
    )

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_awaited_once()
    handler._create_response.assert_awaited_once()
    assert handler._pending_tool_followup_response is False


@pytest.mark.asyncio
async def test_response_done_does_not_duplicate_followup_when_done_handler_already_triggered():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=13,
        stream_id="stream-done-handler",
    )
    handler._pending_tool_followup_response = True
    handler._flush_active_response = AsyncMock(return_value=True)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=True)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"output": []}}
    )

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_awaited_once()
    handler._create_response.assert_not_awaited()
    assert handler._pending_tool_followup_response is False


@pytest.mark.asyncio
async def test_response_done_clears_stale_followup_without_creating_when_no_active_response():
    handler = StepFunRealtimeHandler()
    handler._pending_tool_followup_response = True
    handler._flush_active_response = AsyncMock(return_value=False)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=False)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"output": []}}
    )

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_not_awaited()
    handler._create_response.assert_not_awaited()
    assert handler._pending_tool_followup_response is False


@pytest.mark.asyncio
async def test_response_done_skips_function_calls_when_no_active_response():
    handler = StepFunRealtimeHandler()
    handler._flush_active_response = AsyncMock(return_value=False)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=True)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"id": "resp-stale", "output": []}}
    )

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_not_awaited()
    handler._create_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_active_response_ignores_mismatched_done_response_id():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=9,
        stream_id="stream-current",
        response_id="resp-current",
    )
    handler._persist_message = AsyncMock()
    handler._send_status = AsyncMock()

    flushed = await handler._flush_active_response(
        {"response": {"id": "resp-stale", "output": []}}
    )

    assert flushed is False
    assert handler._active_response is not None
    assert handler._active_response.response_id == "resp-current"
    handler._persist_message.assert_not_awaited()
    handler._send_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_skips_stale_generation(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler._pending_response_generation = 4
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    async def _fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._pending_response_timeout_fallback(expected_generation=3)

    handler._create_response_from_pending_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_blocks_when_transcription_missing_under_kb_lock(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"require_kb_grounding": True},
    }
    handler._awaiting_transcription_after_commit = True
    handler._pending_response_after_commit = True
    handler._record_kb_lock_decision = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    monkeypatch.setattr(stepfun_module, "PENDING_RESPONSE_FALLBACK_SECONDS", 0.0)
    monkeypatch.setattr(stepfun_module, "TRANSCRIPTION_WAIT_GRACE_SECONDS", 0.0)
    monkeypatch.setattr(stepfun_module, "GROUNDING_WAIT_GRACE_SECONDS", 0.0)

    await handler._pending_response_timeout_fallback()

    assert "知识库强制模式" in handler._pending_blocked_response_text
    assert "语音转写尚未完成" in handler._pending_blocked_response_text
    handler._record_kb_lock_decision.assert_awaited_once_with(
        status="blocked_transcription_timeout",
        blocked=True,
    )
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upstream_response_created_cancels_unexpected_response_when_kb_lock_required():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {"require_kb_grounding": True},
    }
    handler._send_upstream = AsyncMock()

    await handler._handle_upstream_response_created(
        {"type": "response.created", "response": {"id": "resp-auto-1"}}
    )

    handler._send_upstream.assert_awaited_once_with({"type": "response.cancel"})


@pytest.mark.asyncio
async def test_persist_runtime_metrics_to_session_updates_snapshot_copy(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-test"
    handler._effective_policy = {
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 2,
                "hit_query_count": 1,
                "hit_rate": 0.5,
            }
        }
    }

    original_snapshot = {"knowledge_base_ids": ["kb-1"]}
    session_obj = SimpleNamespace(voice_policy_snapshot=original_snapshot)

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        async def execute(self, _stmt):
            return DummyResult()

        async def commit(self):
            return None

    class DummyDbSessionContext:
        def __init__(self):
            self.db = DummyDb()

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )

    await handler._persist_runtime_metrics_to_session()

    assert session_obj.voice_policy_snapshot is not original_snapshot
    runtime = session_obj.voice_policy_snapshot.get("runtime_metrics", {}).get(
        "knowledge_retrieval", {}
    )
    assert runtime.get("attempt_count") == 2
    assert runtime.get("hit_query_count") == 1
    assert runtime.get("hit_rate") == 0.5
    assert session_obj.voice_policy_snapshot.get("knowledge_base_ids") == ["kb-1"]


@pytest.mark.asyncio
async def test_load_effective_policy_prefers_frozen_session_snapshot_over_live_resolution(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-frozen"

    frozen_snapshot = {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "profile-frozen",
        "model_name": "step-audio-r1.1",
        "voice_name": "qingchunshaonv",
        "temperature": 0.7,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "output_sample_rate": 24000,
        "instructions": "frozen pressure instructions",
        "instruction_contract_hash": "hash-frozen",
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"enable_internal_retrieval": True},
        "customer_pressure": {
            "source": "explicit",
            "pressure_direction": {"sales_focus": "proof"},
            "follow_up_behavior": {"require_evidence": True},
        },
    }
    session_obj = SimpleNamespace(
        session_id="session-frozen",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        voice_policy_snapshot=frozen_snapshot,
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id="profile-frozen",
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, _stmt):
            return DummyResult()

    dummy_db = DummyDb()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return dummy_db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyVoiceRuntimePolicyService:
        def __init__(self, _db):
            pass

        async def resolve_effective_policy(self, **_kwargs):
            raise AssertionError("live voice policy should not be re-resolved")

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(
        stepfun_module,
        "VoiceRuntimePolicyService",
        DummyVoiceRuntimePolicyService,
    )

    handler._refresh_sales_stage_runtime_config = AsyncMock()
    handler._enforce_tool_policy_guardrails = MagicMock(return_value=False)
    handler._ensure_knowledge_runtime_metrics = MagicMock()

    await handler._load_effective_policy()

    assert handler._effective_policy == frozen_snapshot
    assert handler._stepfun_instructions == "frozen pressure instructions"
    assert handler._instruction_contract_hash == "hash-frozen"
    handler._refresh_sales_stage_runtime_config.assert_awaited_once()
    handler._enforce_tool_policy_guardrails.assert_called_once_with()
    handler._ensure_knowledge_runtime_metrics.assert_called_once_with()
    dummy_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_search_internal_knowledge_includes_error_detail_on_failure(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "retrieval_top_k": 3,
            "retrieval_similarity_threshold": 0.65,
        },
        "knowledge_base_ids": ["kb-1"],
    }
    handler._record_knowledge_runtime_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            return Result.fail(
                "[KNOWLEDGE_SEARCH_UNAVAILABLE] [EMBEDDING_API_ERROR] 402"
            )

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge(
        {"query": "十七科技实习产品", "top_k": 3}
    )

    assert payload["count"] == 0
    assert payload["message"] == "知识检索失败"
    assert "[EMBEDDING_API_ERROR]" in payload["error"]

    kwargs = handler._record_knowledge_runtime_metric.await_args.kwargs
    assert kwargs["status"] == "search_failed"
    assert kwargs["knowledge_base_ids"] == ["kb-1"]
    assert "[EMBEDDING_API_ERROR]" in str(kwargs["error_message"])


@pytest.mark.asyncio
async def test_tool_search_internal_knowledge_marks_keyword_fallback_hits(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "retrieval_top_k": 3,
            "retrieval_similarity_threshold": 0.65,
        },
        "knowledge_base_ids": ["kb-1"],
    }
    handler._record_knowledge_runtime_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "content": "十七科技实习产品支持智能销售训练",
                        "score": 0.81,
                        "retrieval_mode": "keyword_fallback",
                    }
                ]
            )

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge(
        {"query": "实习产品是什么", "top_k": 3}
    )

    assert payload["count"] == 1
    assert payload["retrieval_mode"] == "keyword_fallback"
    assert payload["results"][0]["retrieval_mode"] == "keyword_fallback"

    kwargs = handler._record_knowledge_runtime_metric.await_args.kwargs
    assert kwargs["status"] == "hit_keyword_fallback"
    assert kwargs["retrieval_mode"] == "keyword_fallback"


@pytest.mark.asyncio
async def test_tool_search_internal_knowledge_respects_hybrid_and_metadata_filter(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "retrieval_top_k": 4,
            "retrieval_similarity_threshold": 0.65,
            "retrieval_enable_hybrid": False,
            "retrieval_keyword_candidate_limit": 16,
            "retrieval_metadata_filter": {
                "product_line": "enterprise",
                "regions": ["cn", "sg"],
            },
        },
        "knowledge_base_ids": ["kb-1"],
    }
    handler._record_knowledge_runtime_metric = AsyncMock()

    captured: dict[str, object] = {}

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            captured.update(kwargs)
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "content": "企业版支持私有化部署和统一权限管理。",
                        "score": 0.88,
                        "retrieval_mode": "vector",
                    }
                ]
            )

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge(
        {
            "query": "请详细介绍企业版功能和部署流程以及安全策略",
            "top_k": 4,
            "metadata_filter": {
                "region": "cn",
                "levels": [1, " ", 2],
                "empty": "   ",
            },
        }
    )

    assert payload["count"] == 1
    assert captured["enable_hybrid"] is False
    assert captured["keyword_candidate_limit"] == 16
    assert captured["metadata_filter"] == {
        "region": "cn",
        "levels": [1, 2],
    }


def test_merge_sales_stage_runtime_config_persona_override_agent():
    merged = StepFunRealtimeHandler._merge_sales_stage_runtime_config(
        {
            "sales_stage": {
                "enabled": False,
                "history_window": 6,
                "enforce_transitions": False,
            }
        },
        {
            "sales_stage": {
                "enabled": True,
                "history_window": 4,
            }
        },
    )

    assert merged["enabled"] is True
    assert merged["history_window"] == 4
    assert merged["enforce_transitions"] is False


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_suppresses_duplicate_stage_events():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stage-1"
    handler._ensure_sales_stage_context = AsyncMock()
    handler._sales_stage_context = MagicMock()
    handler._sales_stage_context.turn_count = 0
    handler._sales_stage_context.add_message = MagicMock()
    handler._send_stage_update = AsyncMock()
    handler._sales_stage_capability.execute = AsyncMock(
        side_effect=[
            MagicMock(
                success=True,
                data={
                    "current_stage": "opening",
                    "stage_name": "开场破冰",
                    "key_actions": ["建立信任"],
                    "guidance": "保持自然开场",
                    "progress": 0.2,
                    "stage_changed": False,
                },
            ),
            MagicMock(
                success=True,
                data={
                    "current_stage": "opening",
                    "stage_name": "开场破冰",
                    "key_actions": ["建立信任"],
                    "guidance": "保持自然开场",
                    "progress": 0.2,
                    "stage_changed": False,
                },
            ),
        ]
    )

    first_stage = await handler._analyze_and_emit_sales_stage(
        user_text="你好，我们先认识一下",
        turn_number=1,
    )
    second_stage = await handler._analyze_and_emit_sales_stage(
        user_text="继续介绍背景",
        turn_number=2,
    )

    assert first_stage == "opening"
    assert second_stage == "opening"
    handler._send_stage_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_emits_on_stage_change():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stage-2"
    handler._ensure_sales_stage_context = AsyncMock()
    handler._sales_stage_context = MagicMock()
    handler._sales_stage_context.turn_count = 0
    handler._sales_stage_context.add_message = MagicMock()
    handler._send_stage_update = AsyncMock()
    handler._sales_stage_capability.execute = AsyncMock(
        side_effect=[
            MagicMock(
                success=True,
                data={
                    "current_stage": "opening",
                    "stage_name": "开场破冰",
                    "key_actions": ["建立信任"],
                    "guidance": "保持自然开场",
                    "progress": 0.2,
                    "stage_changed": False,
                },
            ),
            MagicMock(
                success=True,
                data={
                    "current_stage": "discovery",
                    "stage_name": "需求挖掘",
                    "key_actions": ["深入痛点"],
                    "guidance": "多问开放式问题",
                    "progress": 0.4,
                    "stage_changed": True,
                    "previous_stage": "opening",
                },
            ),
        ]
    )

    await handler._analyze_and_emit_sales_stage(
        user_text="你好，我们先认识一下",
        turn_number=1,
    )
    latest_stage = await handler._analyze_and_emit_sales_stage(
        user_text="你们当前最大的业务痛点是什么？",
        turn_number=2,
    )

    assert latest_stage == "discovery"
    assert handler._send_stage_update.await_count == 2


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_returns_none_when_disabled():
    handler = StepFunRealtimeHandler()
    handler._sales_stage_enabled = False
    handler._ensure_sales_stage_context = AsyncMock()

    result = await handler._analyze_and_emit_sales_stage(
        user_text="这段输入不应触发阶段分析",
        turn_number=1,
    )

    assert result is None
    handler._ensure_sales_stage_context.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_message_updates_stage_when_duplicate_key_hit():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-dup-1"
    handler._persisted_message_keys.add((1, "user", "同一条消息"))
    handler._update_existing_message_sales_stage = AsyncMock()

    await handler._persist_message(
        turn_number=1,
        role="user",
        content="同一条消息",
        sales_stage="discovery",
    )

    handler._update_existing_message_sales_stage.assert_awaited_once_with(
        turn_number=1,
        role="user",
        content="同一条消息",
        sales_stage="discovery",
        fuzzy_words=None,
        score_snapshot=None,
        ai_feedback=None,
    )


def test_apply_latest_scores_to_session_maps_sales_rollups_and_snapshot():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 4
    handler._latest_score_snapshot = {
        "overall_score": 84.0,
        "dimension_scores": {
            "价值表达": 90.0,
            "客户收益连接": 84.0,
            "证据使用": 58.0,
            "异议处理": 76.0,
            "推进下一步": 86.0,
        },
    }

    session = MagicMock()
    session.logic_score = None
    session.accuracy_score = None
    session.completeness_score = None

    handler._apply_latest_scores_to_session(session)

    assert session.logic_score == pytest.approx(87.6)
    assert session.accuracy_score == pytest.approx(69.7)
    assert session.completeness_score == pytest.approx(80.0)
    assert session.effectiveness_snapshot["main_issue"]["issue_type"] == "evidence_gap"
    assert session.effectiveness_snapshot["next_goal"]["goal_type"] == "evidence_backing"
    assert session.effectiveness_snapshot["evaluable"] is True


@pytest.mark.asyncio
async def test_create_response_merges_base_contract_and_grounding_instructions():
    handler = StepFunRealtimeHandler()
    handler._stepfun_instructions = "【系统总指令】始终扮演采购总监。"
    handler._pending_grounding_context = "用户问题：最新报价策略"
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()

    created = await handler._create_response(count_turn=True)

    assert created is True
    payload = handler._send_upstream.await_args.args[0]
    assert payload["type"] == "response.create"
    instructions = payload["response"]["instructions"]
    assert "始终扮演采购总监" in instructions
    assert "用户问题：最新报价策略" in instructions
    handler._send_status.assert_awaited_once_with("thinking")


def test_enforce_tool_policy_guardrails_disables_web_search_without_kb():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "enable_web_search": True,
            "enable_internal_retrieval": False,
            "network_access_mode": "controlled",
            "allow_web_search_without_kb": False,
        },
        "knowledge_base_ids": [],
        "source": {},
        "instructions": "原始指令",
    }

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    tool_policy = handler._effective_policy["tool_policy"]
    assert tool_policy["enable_web_search"] is False
    assert tool_policy["network_access_mode"] == "controlled"
    assert (
        handler._effective_policy["source"]["tool_policy_enforcement"] == "no_kb_no_web"
    )


@pytest.mark.asyncio
async def test_run_realtime_feedback_keeps_single_action_card_and_prioritizes_score_over_low_severity_fuzzy_detection():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-priority"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = True
    handler._realtime_scoring_enabled = True

    handler._fuzzy_detection_capability = MagicMock()
    handler._fuzzy_detection_capability.on_session_start = AsyncMock()
    handler._fuzzy_detection_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "detections": [
                    {
                        "category": "filler",
                        "matched": ["嗯"],
                        "suggestion": "减少填充词，保持表达流畅。",
                        "severity": "low",
                    }
                ]
            }
        )
    )
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 83.0,
                "dimension_scores": {
                    "价值表达": 83.0,
                    "客户收益连接": 81.0,
                    "证据使用": 60.0,
                    "异议处理": 78.0,
                    "推进下一步": 67.0,
                },
                "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们先聊聊产品价值。",
        turn_number=2,
        sales_stage="discovery",
    )

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_cards = [payload for payload in sent_payloads if payload["type"] == "action_card"]

    assert analysis["fuzzy_words"] == [
        {
            "category": "filler",
            "matched": ["嗯"],
            "suggestion": "减少填充词，保持表达流畅。",
            "severity": "low",
        }
    ]
    assert analysis["score_snapshot"]["overall_score"] == 83.0
    assert analysis["ai_feedback"] == "在确认痛点后，补一个同类客户案例、数据或ROI区间。"
    assert len(action_cards) == 1
    assert action_cards[0]["data"] == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }


@pytest.mark.asyncio
async def test_run_realtime_feedback_suppresses_duplicate_action_card_for_same_turn():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-suppress"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 82.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 80.0,
                    "证据使用": 61.0,
                    "异议处理": 76.0,
                    "推进下一步": 64.0,
                },
                "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
            }
        )
    )

    first_analysis = await handler._run_realtime_feedback(
        user_text="我们可以用客户案例说明ROI。",
        turn_number=3,
        sales_stage="discovery",
    )
    second_analysis = await handler._run_realtime_feedback(
        user_text="我们可以用客户案例说明ROI。",
        turn_number=3,
        sales_stage="discovery",
    )

    expected_action_card = {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_cards = [payload for payload in sent_payloads if payload["type"] == "action_card"]
    score_updates = [payload for payload in sent_payloads if payload["type"] == "score_update"]

    assert first_analysis["ai_feedback"] == "在确认痛点后，补一个同类客户案例、数据或ROI区间。"
    assert second_analysis == {
        "score_snapshot": {
            "overall_score": 82.0,
            "dimension_scores": {
                "价值表达": 84.0,
                "客户收益连接": 80.0,
                "证据使用": 61.0,
                "异议处理": 76.0,
                "推进下一步": 64.0,
            },
            "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
            "stage_name": "需求挖掘",
        },
        "objection_ledger": {
            "objection_family": "roi_proof",
            "promised_proof": "补充同类客户 ROI 案例",
            "next_expected_evidence": "给出 6 个月回本测算",
            "closure_state": "open",
        },
    }
    assert len(action_cards) == 1
    assert len(score_updates) == 2
    assert action_cards[0]["data"] == expected_action_card
    assert handler._latest_action_card == expected_action_card


@pytest.mark.asyncio
async def test_run_realtime_feedback_emits_canonical_sales_score_and_action_card():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-feedback"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 82.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 80.0,
                    "证据使用": 61.0,
                    "异议处理": 76.0,
                    "推进下一步": 64.0,
                },
                "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们可以用客户案例说明ROI。",
        turn_number=3,
        sales_stage="discovery",
    )

    expected_snapshot = {
        "overall_score": 82.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 80.0,
            "证据使用": 61.0,
            "异议处理": 76.0,
            "推进下一步": 64.0,
        },
        "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
        "stage_name": "需求挖掘",
    }
    expected_action_card = {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": {
            "objection_family": "roi_proof",
            "promised_proof": "补充同类客户 ROI 案例",
            "next_expected_evidence": "给出 6 个月回本测算",
            "closure_state": "open",
        },
        "ai_feedback": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
    }
    assert handler._latest_score_snapshot == expected_snapshot
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    score_update = next(payload for payload in sent_payloads if payload["type"] == "score_update")
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")

    assert score_update["data"] == {
        "session_id": "session-realtime-feedback",
        "turn_count": 3,
        "overall_score": 82.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 80.0,
            "证据使用": 61.0,
            "异议处理": 76.0,
            "推进下一步": 64.0,
        },
        "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
        "stage_name": "需求挖掘",
    }
    assert action_card["data"] == expected_action_card


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_retains_latest_rich_stage_data_for_followup_feedback():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stage-rich"
    handler._ensure_sales_stage_context = AsyncMock()
    handler._sales_stage_context = MagicMock()
    handler._sales_stage_context.turn_count = 0
    handler._sales_stage_context.add_message = MagicMock()
    handler._send_stage_update = AsyncMock()

    stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    handler._sales_stage_capability.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, data=stage_data)
    )

    latest_stage = await handler._analyze_and_emit_sales_stage(
        user_text="我们可以约下周确认试点。",
        turn_number=3,
    )

    assert latest_stage == "closing"
    assert getattr(handler, "_latest_stage_data", None) == stage_data


@pytest.mark.asyncio
async def test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-rich-context"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._latest_stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    raw_score_payload = {
        "overall": 78.0,
        "overall_score": 78.0,
        "dimension_scores": {
            "价值表达": 61.0,
            "客户收益连接": 63.0,
            "证据使用": 74.0,
            "异议处理": 72.0,
            "推进下一步": 65.0,
        },
        "dimensions": [
            {"name": "推进下一步", "score": 65.0, "delta": -6.0, "trend": "down"},
            {"name": "证据使用", "score": 74.0, "delta": 1.0, "trend": "up"},
        ],
        "feedback": "继续回应客户顾虑。",
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(data=raw_score_payload)
    )
    handler._feedback_arbiter = MagicMock()
    handler._feedback_arbiter.decide.return_value = SimpleNamespace(
        action_card=None,
        state=RealtimeFeedbackPacingState(),
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们可以约下周确认试点。",
        turn_number=4,
        sales_stage="closing",
    )

    expected_snapshot = {
        "overall_score": 78.0,
        "dimension_scores": {
            "价值表达": 61.0,
            "客户收益连接": 63.0,
            "证据使用": 74.0,
            "异议处理": 72.0,
            "推进下一步": 65.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
        "stage_name": "促成成交",
    }

    assert analysis == {"score_snapshot": expected_snapshot}
    assert handler._latest_score_snapshot == expected_snapshot

    handler._feedback_arbiter.decide.assert_called_once()
    arbiter_kwargs = handler._feedback_arbiter.decide.call_args.kwargs
    assert arbiter_kwargs["stage_context"] == {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    assert arbiter_kwargs["score_context"]["dimensions"] == raw_score_payload["dimensions"]
    assert arbiter_kwargs["score_context"]["feedback"] == "继续回应客户顾虑。"
    assert arbiter_kwargs["score_context"]["dimension_scores"] == raw_score_payload["dimension_scores"]
    assert arbiter_kwargs["score_context"]["stage_name"] == "促成成交"

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    score_update = next(payload for payload in sent_payloads if payload["type"] == "score_update")
    assert score_update["data"] == {
        "session_id": "session-realtime-rich-context",
        "turn_count": 4,
        "overall_score": 78.0,
        "dimension_scores": {
            "价值表达": 61.0,
            "客户收益连接": 63.0,
            "证据使用": 74.0,
            "异议处理": 72.0,
            "推进下一步": 65.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
        "stage_name": "促成成交",
    }
    assert "dimensions" not in score_update["data"]


@pytest.mark.asyncio
async def test_run_realtime_feedback_uses_declining_dimension_to_match_classic_action_card():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-declining-dimension"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._latest_stage_data = {
        "current_stage": "objection",
        "stage_name": "异议处理",
        "key_actions": ["承接顾虑"],
        "guidance": "围绕风险与证据回应",
        "progress": 0.6,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall": 76.0,
                "overall_score": 76.0,
                "dimension_scores": {
                    "价值表达": 82.0,
                    "客户收益连接": 79.0,
                    "证据使用": 66.0,
                    "异议处理": 72.0,
                    "推进下一步": 78.0,
                },
                "dimensions": [
                    {"name": "证据使用", "score": 66.0, "delta": 1.0, "trend": "up"},
                    {"name": "异议处理", "score": 72.0, "delta": -9.0, "trend": "down"},
                ],
                "feedback": "继续回应客户顾虑。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="客户担心实施风险和价格。",
        turn_number=5,
        sales_stage="objection",
    )

    expected_snapshot = {
        "overall_score": 76.0,
        "dimension_scores": {
            "价值表达": 82.0,
            "客户收益连接": 79.0,
            "证据使用": 66.0,
            "异议处理": 72.0,
            "推进下一步": 78.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
        "stage_name": "异议处理",
    }
    expected_action_card = {
        "issue": "客户顾虑出现后，承接与重构回应还不够完整。",
        "replacement": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
        "next_turn_rule": "下一轮先复述顾虑，再回应证据，最后给低风险推进方案。",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": {
            "objection_family": "price_pressure",
            "promised_proof": "补充报价依据和版本差异",
            "next_expected_evidence": "说明报价逻辑、预算回收或折扣边界",
            "closure_state": "open",
        },
        "ai_feedback": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
    }
    assert handler._latest_score_snapshot == expected_snapshot
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")
    assert action_card["data"] == expected_action_card


@pytest.mark.asyncio
async def test_run_realtime_feedback_reuses_open_objection_ledger_when_score_focus_drifts() -> None:
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-objection-ledger-drift"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._objection_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }
    handler._latest_stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 79.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 82.0,
                    "证据使用": 88.0,
                    "异议处理": 81.0,
                    "推进下一步": 52.0,
                },
                "feedback": "明确试点、会议、报价或负责人确认中的一个动作。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们可以先聊一下后面的协同流程。",
        turn_number=6,
        sales_stage="closing",
    )

    expected_snapshot = {
        "overall_score": 79.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 82.0,
            "证据使用": 88.0,
            "异议处理": 81.0,
            "推进下一步": 52.0,
        },
        "suggestions": ["明确试点、会议、报价或负责人确认中的一个动作。"],
        "stage_name": "促成成交",
    }
    expected_action_card = {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
    expected_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": expected_ledger,
        "ai_feedback": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
    }
    assert handler._objection_ledger == expected_ledger
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")
    assert action_card["data"] == expected_action_card


@pytest.mark.asyncio
async def test_run_realtime_feedback_marks_objection_ledger_gap_acknowledged_and_releases_focus() -> None:
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-objection-ledger-close"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._objection_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }
    handler._latest_stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 79.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 82.0,
                    "证据使用": 88.0,
                    "异议处理": 81.0,
                    "推进下一步": 52.0,
                },
                "feedback": "明确试点、会议、报价或负责人确认中的一个动作。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="这个 ROI 案例我们现在确实没有，得回去确认后再给你。",
        turn_number=6,
        sales_stage="closing",
    )

    expected_snapshot = {
        "overall_score": 79.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 82.0,
            "证据使用": 88.0,
            "异议处理": 81.0,
            "推进下一步": 52.0,
        },
        "suggestions": ["明确试点、会议、报价或负责人确认中的一个动作。"],
        "stage_name": "促成成交",
    }
    expected_action_card = {
        "issue": "对话快结束了，但下一步动作、时间点和责任人还没定下来。",
        "replacement": "明确试点、会议、报价或负责人确认中的一个动作。",
        "next_turn_rule": "下一轮先锁定动作、时间点和责任人，再结束本轮。",
    }
    expected_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "gap_acknowledged",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": expected_ledger,
        "ai_feedback": "明确试点、会议、报价或负责人确认中的一个动作。",
    }
    assert handler._objection_ledger == expected_ledger
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")
    assert action_card["data"] == expected_action_card


def test_create_state_snapshot_includes_objection_ledger_copy() -> None:
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-objection-ledger-save"
    handler._objection_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补同类客户 ROI 案例",
        "next_expected_evidence": "给出量化回本周期",
        "closure_state": "open",
    }

    snapshot = handler._create_state_snapshot()

    assert snapshot.runtime_state["objection_ledger"] == {
        "objection_family": "roi_proof",
        "promised_proof": "补同类客户 ROI 案例",
        "next_expected_evidence": "给出量化回本周期",
        "closure_state": "open",
    }

    handler._objection_ledger["closure_state"] = "gap_acknowledged"
    assert snapshot.runtime_state["objection_ledger"]["closure_state"] == "open"


@pytest.mark.asyncio
async def test_restore_session_state_rehydrates_objection_ledger() -> None:
    handler = StepFunRealtimeHandler()
    handler._send_reconnection_success = AsyncMock()

    state = SessionStateSnapshot(
        session_id="session-objection-ledger-restore",
        scenario="sales",
        turn_count=3,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "objection_ledger": {
                "objection_family": "implementation_risk",
                "promised_proof": "补实施排期与服务边界",
                "next_expected_evidence": "确认试点负责人",
                "closure_state": "open",
            }
        },
    )

    await handler._restore_session_state(state)

    assert handler._objection_ledger == {
        "objection_family": "implementation_risk",
        "promised_proof": "补实施排期与服务边界",
        "next_expected_evidence": "确认试点负责人",
        "closure_state": "open",
    }
    handler._send_reconnection_success.assert_awaited_once_with(state)
