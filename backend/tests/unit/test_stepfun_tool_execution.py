"""Unit tests for StepFun tool execution module."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sales_bot.websocket.stepfun_tool_execution import (
    StepFunToolExecutionModule,
    ToolExecutionContext,
)


def test_build_tools_from_policy_with_knowledge_tool():
    module = StepFunToolExecutionModule()

    tools = module.build_tools_from_policy(
        {
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "enable_web_search": True,
            },
        }
    )

    assert tools == [
        {
            "type": "function",
            "function": {
                "name": "search_internal_knowledge",
                "description": "检索企业内部知识库，用于回答产品、流程和策略问题。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "用户问题或检索关键词",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回条数（可选）",
                        },
                        "metadata_filter": {
                            "type": "object",
                            "description": "按知识条目元数据过滤（可选，例如 product_line 或 region）",
                        },
                    },
                    "required": ["query"],
                },
            },
        }
    ]


def test_build_tools_from_policy_without_knowledge_returns_empty():
    module = StepFunToolExecutionModule()

    tools = module.build_tools_from_policy(
        {
            "knowledge_base_ids": [],
            "tool_policy": {
                "enable_internal_retrieval": False,
                "enable_web_search": False,
            },
        }
    )

    assert tools == []


def test_enforce_guardrails_removes_disallowed_web_search_tool():
    module = StepFunToolExecutionModule()

    tools = module.enforce_guardrails(
        [
            {"type": "web_search", "function": {"options": {"top_k": 3}}},
            {"type": "function", "function": {"name": "search_internal_knowledge"}},
        ],
        {
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "network_access_mode": "controlled",
                "allow_web_search_without_kb": True,
            },
        },
    )

    assert tools == [
        {"type": "function", "function": {"name": "search_internal_knowledge"}}
    ]


def test_enforce_guardrails_keeps_allowed_internal_knowledge_tool_exactly():
    module = StepFunToolExecutionModule()
    internal_tool = {
        "type": "function",
        "function": {"name": "search_internal_knowledge", "description": "stable"},
    }

    tools = module.enforce_guardrails(
        [internal_tool],
        {
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"network_access_mode": "off"},
        },
    )

    assert tools == [internal_tool]


def test_build_tool_response_with_content():
    module = StepFunToolExecutionModule()

    event = module.build_tool_response(
        tool_call_id="call-1",
        result={"query": "产品", "count": 1, "results": [{"snippet": "石犀"}]},
    )

    assert event["type"] == "conversation.item.create"
    assert event["item"]["type"] == "function_call_output"
    assert event["item"]["call_id"] == "call-1"
    assert json.loads(event["item"]["output"]) == {
        "query": "产品",
        "count": 1,
        "results": [{"snippet": "石犀"}],
    }


def test_build_tool_error_response_with_error_message():
    module = StepFunToolExecutionModule()

    event = module.build_tool_error_response(
        tool_call_id="call-error",
        error="internal_search_error",
    )

    assert event["type"] == "conversation.item.create"
    assert event["item"]["type"] == "function_call_output"
    assert event["item"]["call_id"] == "call-error"
    assert json.loads(event["item"]["output"]) == {"error": "internal_search_error"}


@pytest.mark.asyncio
async def test_execute_tool_search_internal_knowledge_uses_injected_search_seam():
    seen: dict[str, Any] = {}

    async def fake_search(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {"query": "产品", "count": 1, "results": [{"snippet": "石犀"}]}

    async def record_metric(**_kwargs: Any) -> None:
        return None

    module = StepFunToolExecutionModule(internal_knowledge_searcher=fake_search)
    context = ToolExecutionContext(
        session_id="session-1",
        effective_policy={"knowledge_base_ids": ["kb-1"]},
        session_factory=lambda: object(),
        knowledge_service_factory=lambda db: object(),
        record_metric=record_metric,
    )

    result = await module.execute_tool(
        {"name": "search_internal_knowledge", "arguments": {"query": "产品"}},
        context=context,
    )

    assert result == {"query": "产品", "count": 1, "results": [{"snippet": "石犀"}]}
    assert seen["arguments_obj"] == {"query": "产品", "session_id": "session-1"}
    assert seen["effective_policy"] == {"knowledge_base_ids": ["kb-1"]}
    assert seen["session_factory"] is context.session_factory
    assert seen["knowledge_service_cls"] is context.knowledge_service_factory
    assert seen["record_metric"] is record_metric
