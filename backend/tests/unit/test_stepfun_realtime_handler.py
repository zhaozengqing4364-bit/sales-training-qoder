"""
Unit tests for StepFunRealtimeHandler realtime channel behavior.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from common.error_handling.result import Result
import sales_bot.websocket.stepfun_realtime_handler as stepfun_module
from sales_bot.websocket.stepfun_realtime_handler import (
    RealtimeResponseState,
    StepFunRealtimeHandler,
)


@pytest.mark.asyncio
async def test_handle_client_text_persists_user_message_before_create_response():
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.turn_count = 0

    handler._persist_message = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="opening")
    handler._run_realtime_feedback = AsyncMock(return_value={"score_snapshot": {"overall_score": 82}})
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
    handler._prepare_grounding_context.assert_awaited_once_with("你好，给我介绍一下产品")
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
    handler._run_realtime_feedback = AsyncMock(return_value={"fuzzy_words": [{"category": "uncertain"}]})
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

    handler._tool_search_internal_knowledge.assert_awaited_once_with({"query": "价", "top_k": 3})
    assert "用户问题：价" in handler._pending_grounding_context
    assert "标准版报价可按年付费" in handler._pending_grounding_context


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
        StepFunRealtimeHandler._extract_text_payload(
            {"content": "兼容旧字段"}
        )
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
    handler._send_upstream.assert_awaited_once_with({"type": "input_audio_buffer.commit"})
    handler._schedule_response_after_commit.assert_awaited_once()
    assert handler._has_uncommitted_audio is False

    await handler._commit_and_respond()
    assert handler._send_upstream.await_count == 1
    assert handler._schedule_response_after_commit.await_count == 1


@pytest.mark.asyncio
async def test_execute_function_call_defers_followup_while_response_active():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(request_id=1, stream_id="stream-active")
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={"query": "产品", "count": 1, "results": [{"snippet": "石犀平台能力"}]}
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
async def test_response_done_triggers_pending_tool_followup_response():
    handler = StepFunRealtimeHandler()
    handler._pending_tool_followup_response = True
    handler._flush_active_response = AsyncMock()
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=False)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event({"type": "response.done", "response": {"output": []}})

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_awaited_once()
    handler._create_response.assert_awaited_once()
    assert handler._pending_tool_followup_response is False


@pytest.mark.asyncio
async def test_response_done_does_not_duplicate_followup_when_done_handler_already_triggered():
    handler = StepFunRealtimeHandler()
    handler._pending_tool_followup_response = True
    handler._flush_active_response = AsyncMock()
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=True)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event({"type": "response.done", "response": {"output": []}})

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_awaited_once()
    handler._create_response.assert_not_awaited()
    assert handler._pending_tool_followup_response is False


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

    monkeypatch.setattr(stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext())

    await handler._persist_runtime_metrics_to_session()

    assert session_obj.voice_policy_snapshot is not original_snapshot
    runtime = session_obj.voice_policy_snapshot.get("runtime_metrics", {}).get("knowledge_retrieval", {})
    assert runtime.get("attempt_count") == 2
    assert runtime.get("hit_query_count") == 1
    assert runtime.get("hit_rate") == 0.5
    assert session_obj.voice_policy_snapshot.get("knowledge_base_ids") == ["kb-1"]


@pytest.mark.asyncio
async def test_tool_search_internal_knowledge_includes_error_detail_on_failure(monkeypatch):
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
            return Result.fail("[KNOWLEDGE_SEARCH_UNAVAILABLE] [EMBEDDING_API_ERROR] 402")

    monkeypatch.setattr(stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext())
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge({"query": "十七科技实习产品", "top_k": 3})

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

    monkeypatch.setattr(stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext())
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge({"query": "实习产品是什么", "top_k": 3})

    assert payload["count"] == 1
    assert payload["retrieval_mode"] == "keyword_fallback"
    assert payload["results"][0]["retrieval_mode"] == "keyword_fallback"

    kwargs = handler._record_knowledge_runtime_metric.await_args.kwargs
    assert kwargs["status"] == "hit_keyword_fallback"
    assert kwargs["retrieval_mode"] == "keyword_fallback"


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


def test_apply_latest_scores_to_session_maps_dimensions():
    handler = StepFunRealtimeHandler()
    handler._latest_score_snapshot = {
        "overall_score": 84.0,
        "dimension_scores": {
            "专业度": 90.0,
            "沟通技巧": 82.0,
            "销售流程": 80.0,
        },
    }

    session = MagicMock()
    session.logic_score = None
    session.accuracy_score = None
    session.completeness_score = None

    handler._apply_latest_scores_to_session(session)

    assert session.logic_score == 90.0
    assert session.accuracy_score == 82.0
    assert session.completeness_score == 80.0
